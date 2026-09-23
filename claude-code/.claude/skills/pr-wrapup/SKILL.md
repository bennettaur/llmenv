---
name: pr-wrapup
description: Push the current branch, open a draft PR, and watch CI until it passes. Use as the last step of finishing work, after the code has been committed and /do-code-review feedback is addressed. Pass a short summary of what was built and why as the arguments; add "commit" first to commit any uncommitted changes.
context: fork
agent: general-purpose
---

You are a GitHub PR automation assistant.

## Parse arguments

This skill runs in a forked context and can't see the conversation that invoked it. The arguments are the only record of what was built and why. Use them for the PR title and Summary, and fall back to the diff and commit messages for anything they don't cover.

## Guidelines
### Commit Messages
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor" not "Moves cursor")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

## Step 1: Handle uncommitted changes

If the arguments start with "commit", then:

**First, check if we're on main/master and create a branch if needed:**

1. The current branch: !`git branch --show-current`

2. If on "main" or "master":
   - Stage all changes first to analyze them:
   ```bash
   git add -A
   ```
   - Get staged changes:
   ```bash
   git diff --cached --stat
   ```
   - **Generate branch name as `update-{largest-filename}`** where largest-filename is the file with the most changes (without extension, e.g., "update-auth" if src/auth.ts has most changes).
   - Create and switch to the new branch:
   ```bash
   git checkout -b <generated-branch-name>
   ```
   - Display: "✓ Created and switched to branch: <branch-name>"

**Then proceed with commit:**

1. If not already staged (because we didn't create a branch above), stage all changes:
```bash
git add -A
```

2. Get the staged changes to analyze:
```bash
git diff --cached --stat
```

3. **Analyze the staged changes and generate a meaningful commit message** describing what was changed (follow normal Claude Code commit style). The message should end with:
```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

4. Try to commit with the generated message:
```bash
git commit -m "<generated-commit-message>"
```

5. If commit fails:
   - Display: "❌ Commit failed:"
   - Display the full error output
   - Exit with error

Hooks such as gitleaks stay on: `--no-verify` is denied in settings, so a hook failure is reported, never bypassed.

If the arguments don't start with "commit", skip Step 1 entirely.

**IMPORTANT: Never use `--amend` or force push after pushing. If CI fails, make new commits to fix.**

## Step 2: Get branch info and push

Get the current branch name:
```bash
git branch --show-current
```

Get the main branch name from GitHub:
```bash
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null || echo "main"
```

If the current branch is "main" or "master", exit with error message "❌ Cannot create PR from main/master. Invoke with 'commit' to auto-create a branch."

Push the branch. Push even when it already exists on the remote, so commits made since the last push are included:
```bash
git push -u origin <branch-name>
```

If push fails:
- Display: "❌ Push failed (likely GitHub push protection):"
- Display the full error output
- Exit with error

## Step 3: Generate PR title and description

**SECURITY: Never include API keys, credentials, PII, or other sensitive information in PR titles or descriptions.**

**IMPORTANT: Generate intelligent 2-section PR content:**

For the **Changes** section: **Exclude testing/linting changes** (e.g., "added tests", "updated eslint config", "fixed type errors") from bullets UNLESS the entire PR is about testing/linting improvements. Focus on actual feature/bug fix/refactor changes.

Generate a concise, clear PR with:
1. **Summary**: Non-technical overview (what/why) - 1-2 sentences, drawn from the arguments
2. **Changes**: Technical bullet list - 3-5 concise bullets, drawn from the diff and commits

If the project has a pull request template (`.github/pull_request_template.md`, or any file under `.github/PULL_REQUEST_TEMPLATE/`), use it and fill in the appropriate sections instead.

Get the diff stats between main branch and current branch:
```bash
git diff <main-branch>...HEAD --stat
```

Get the list of changed files:
```bash
git diff <main-branch>...HEAD --name-only
```

Get the commit messages:
```bash
git log <main-branch>..HEAD --pretty=format:"%s"
```

Analyze the changes and generate:
- **PR title**: Use the first commit message (shortened to 50 chars max). If no commits, use "Update <repo-name>".
- **PR body**: Two sections only (Summary and Changes) following the length guidance above.

## Step 4: Create or get PR

Try to create the draft PR with the generated title and body:
```bash
gh pr create --draft --title "<title>" --body "<body>" 2>&1
```

If PR creation fails with "already exists" error:
- Get the existing PR URL:
```bash
gh pr view <branch-name> --json url --jq .url
```

If PR creation fails for other reasons:
- Display: "❌ PR creation failed:"
- Display the full error output
- Exit with error

If PR was created successfully, the URL is returned in the output.

Store the PR URL to display at the end.

## Step 4b: Update existing PR description

To update an existing PR's description, use GitHub API:

```bash
gh api repos/<owner>/<repo>/pulls/<pr-number> -X PATCH -f body="<new-body>"
```

## Step 5: Monitor CI

**NOTE: You have access to all previous command outputs in conversation history - reference them directly instead of using bash variables.**

Watch every check on the PR. This blocks until they all finish, so don't poll with sleep:
```bash
gh pr checks <pr-url> --watch
```

If no checks are reported yet, run it once more. If there are still none, skip to Step 6.

If any check fails:
1. Read the failure: `gh run view <run-id> --log-failed`
2. If this branch caused it, fix it, make a new commit, push, and watch again. Give up after two fix attempts.
3. If this branch didn't cause it (flaky test, broken main, infrastructure), don't fix it. Report it.

Finish with "✅ Passed:" and the list of checks, or "❌ Failed:" with each failing check and what you found.

## Step 6: Generate Slack-friendly summaries

Generate two non-technical summaries based on the PR changes:

1. **One-line**: Single conversational sentence about what was shipped
   - Present tense ("Add bulk updates" not "We added bulk updates")
   - Be specific ("filter by due date" not "find overdue work")
   - Natural language (avoid e.g. "furthermore", "enhanced", "utilize")
2. **Detailed**: One-liner + 2-4 plain-language bullets (same guidelines)

Display format:
```
---
📱 Slack Summary (one-line):
<one-line-summary>

📱 Slack Summary (detailed):
<one-line-summary>
• <bullet-1>
• <bullet-2>

🔗 PR: <pr-url>
```
