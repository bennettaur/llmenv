---
name: merge-default-branch
description: Merge the origin remote's default branch (main or master, whichever the repo uses) into the current branch and resolve any merge conflicts intelligently — by understanding what the incoming changes were doing and what the current branch (the PR) is doing, then combining their intent rather than blindly picking a side. Then pushes the branch so CI runs on the merged result. Use this whenever the user wants to bring their branch up to date with main/master, "merge in main", "catch up with the default branch", "update my branch", or "merge and fix the conflicts", and when a PR is behind its base branch and needs the latest changes merged in.
model: sonnet
---

# Merge the Default Branch and Resolve Conflicts

The mechanical part of this — running `git merge` — is trivial. The valuable part is resolving conflicts *well*: a conflict means two changes touched the same place, and the right resolution almost always preserves the **intent of both sides**, not just the text of one. To do that you first have to understand what each side was trying to do. That's why the steps below front-load building context before you touch a single conflict marker.

A textual merge that "succeeds" can still be broken — the default branch may have renamed a function the current branch calls, or changed a signature — so verification at the end is not optional.

## Step 1: Establish a safe starting point

1. Confirm you're in a git repository and capture the current branch:
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   If this is the default branch itself (e.g. you're on `main`), there's nothing to merge in — stop and tell the user. If it prints `HEAD`, you're in detached HEAD state with no branch to push — stop and tell the user.

2. Check the working tree is clean:
   ```bash
   git status --porcelain
   ```
   If there are uncommitted changes, **stop and ask** whether to stash them (`git stash push -u`) or commit first. Don't merge over a dirty tree — it tangles the user's in-progress work with the merge and makes conflicts impossible to reason about. If you stash, remember to `git stash pop` after the merge completes and resolve any resulting conflicts the same way.

## Step 2: Identify the default branch

The default branch differs by repo (`main`, `master`, occasionally something else), so detect it rather than assuming:

```bash
git fetch origin
git symbolic-ref refs/remotes/origin/HEAD --short   # → e.g. "origin/main"
```

If that ref isn't set, populate it and retry:
```bash
git remote set-head origin --auto
```

If detection still fails (no network, unusual setup), fall back to checking which of `origin/main` / `origin/master` exists (`git branch -r`), and if both or neither do, ask the user. Call the result `<default>` (e.g. `origin/main`) below.

If the current branch from Step 1 has the same name as `<default>` (e.g. you're on `main` and `<default>` is `origin/main`), stop and tell the user. Step 7 pushes, and it must never push to the default branch.

## Step 3: Build context BEFORE merging

This is the step that makes the difference between a thoughtful merge and a guess. Before merging, learn what each side changed since they diverged:

```bash
BASE=$(git merge-base HEAD <default>)
git log --oneline $BASE..HEAD          # what THIS branch (the PR) did
git log --oneline $BASE..<default>     # what came in on the default branch
git diff --stat $BASE..HEAD            # files the PR touched
git diff --stat $BASE..<default>       # files the incoming changes touched
```

Read the commit messages on both sides — they're the cheapest source of intent. The files that appear in **both** stat lists are where conflicts are likely. Form a one-sentence understanding of each side's goal (e.g. "the PR adds rate limiting to the auth client; main refactored that same client to be async"). Keep this in mind; it's what you'll use to judge resolutions and to explain choices to the user.

## Step 4: Run the merge

```bash
git merge <default>
```

- **"Already up to date"** → nothing to do; report and stop.
- **Clean merge** → skip to Step 6 (verify). Even a clean merge can break semantically.
- **Conflicts** → proceed to Step 5. List them with:
  ```bash
  git diff --name-only --diff-filter=U
  ```

## Step 5: Resolve conflicts by intent

For each conflicted file, the three merge stages are your most powerful tool — they let you see what *each side changed relative to the common ancestor*, which is exactly the intent you need:

```bash
git show :1:path/to/file   # base — the common ancestor (what both started from)
git show :2:path/to/file   # ours — the current branch (the PR)
git show :3:path/to/file   # theirs — the incoming default branch
```

Diffing base→ours and base→theirs tells you what each side was actually trying to accomplish, which is far clearer than staring at the raw `<<<<<<<` markers. `git log --merge -p path/to/file` shows the specific commits in conflict.

Then classify each conflict hunk and resolve accordingly:

- **Same change on both sides** — take either; they agree.
- **Different, non-overlapping intents in the same region** — combine them so both intents survive. This is the most common case and usually the correct resolution. Example: the PR added a new field to a struct and main added a different field to the same struct — keep both fields.
- **One side refactored the region the other modified** — re-apply the other side's intent on top of the refactor. Example: main made a function async and the PR added a guard clause to it — keep it async *and* keep the guard clause. Don't just pick "theirs" and silently drop the PR's change.
- **Mechanical / generated conflicts** (lockfiles like `package-lock.json`, `Gemfile.lock`, `yarn.lock`, generated code, import ordering) — don't hand-merge these. Take the appropriate side and regenerate: accept the default branch's lockfile then re-run the install/lock command so it reflects the merged dependency set. Hand-edited lockfiles are a frequent source of subtle breakage.
- **modify/delete** (one side deleted a file the other changed) — this is genuinely ambiguous: was the file intentionally removed upstream, or does the PR still need it? **Ask.**

### When to ask the user

Resolve confidently when the intent is clear and the combination is unambiguous. **Stop and ask** (use AskUserQuestion) when:

- Both sides change the *same behavior* in incompatible ways and you can't tell which the final code should have.
- A modify/delete or rename conflict makes it unclear whether functionality should survive.
- The two sides reflect competing design decisions (e.g. different error-handling patterns for the same path) and picking one changes how the code behaves.

When you ask, don't dump raw conflict markers. State your understanding of each side: "main changed X to do A (commit abc, 'refactor to async'); this branch changed X to do B ('add retry logic'). I can (1) keep both by applying retries to the async version, (2) keep main's async version only, (3) keep this branch's version only." Lead with the option you think is right and say why. Most of the time you'll resolve it yourself — only escalate the genuinely judgment-dependent ones.

After resolving a file, stage it: `git add path/to/file`. When all conflicts are staged, `git diff --name-only --diff-filter=U` should print nothing.

## Step 6: Verify

A merge can be textually clean but semantically broken, so check the merged result actually works before committing. Look for the project's commands (in `package.json` scripts, `Makefile`, `Rakefile`, `pyproject.toml`, CI config, or CLAUDE.md) and run what's quick and available — typically build, lint, and the test suite, or at least the tests covering the files involved in the merge.

If verification fails:
- If the failure is caused by the merge (a semantic conflict the text-merge missed), fix it the same way as a normal conflict — by reconciling both sides' intent — then re-verify.
- If you can't confidently fix it, **stop and report** rather than committing broken code. Show the user the failure and the conflicts you resolved. Do not commit or push a merge that doesn't pass verification.

## Step 7: Complete the merge, push, and report

Once conflicts are resolved and verification passes, finalize the merge commit:

```bash
git commit --no-edit
```

(`--no-edit` keeps git's default merge message. A clean merge in Step 4 already created the merge commit, so skip this command in that case. If you stashed in Step 1, `git stash pop` now and resolve any conflicts the same way. The popped changes stay uncommitted and are not part of the push.)

Note the merge commit's SHA (`git rev-parse HEAD`) for the report.

Then push the current branch to its same-named branch on `origin`, so CI runs against the merged result:

```bash
git push -u origin HEAD
```

The explicit `origin HEAD` pushes to `origin/<current-branch>` even if the branch tracks something else, such as `origin/main`. Never force push. A merge only adds commits, so it never needs one.

If the push fails:
- **Rejected because `origin/<current-branch>` has commits you don't have** (someone else pushed to the branch): run `git pull --no-rebase origin <current-branch>`, resolve any conflicts as in Step 5, verify as in Step 6, commit, then push again.
- **A pre-push hook fails**: if the merge caused the failure, fix it in a new commit, verify again, and push. Otherwise, or if you can't fix it, stop and report. Never skip hooks with `--no-verify`, on push or on commit.
- **Rejected for any other reason** (branch protection, missing permissions): stop and report the error. Don't work around it.

Then report to the user:
- Which default branch was merged in and how many commits it brought.
- Each conflict you resolved and the reasoning — especially any "combine both" or "re-apply on top of refactor" decisions, since those are where a wrong call hides.
- The verification results (what you ran, that it passed).
- Whether the push succeeded, so CI is running on the merged result, or why it didn't.
- How to undo if they disagree with anything: `git revert -m 1 <merge-sha>` undoes the merge with a new commit that can be pushed normally. Warn them that after this revert, merging the default branch again won't bring those changes back. They have to revert the revert first. Don't run `git reset` or force push to undo the merge unless the user explicitly asks for it.

## Notes

- This skill merges and pushes; it does not rebase. Skip the push only if the user asked for a local-only merge.
- It reads from `origin` (`git fetch`) and writes only to the current branch, locally and on `origin`. It never modifies the default branch.
- If the merge gets into a state you don't understand, `git merge --abort` is always safe before the merge is committed and returns you to the starting point.
