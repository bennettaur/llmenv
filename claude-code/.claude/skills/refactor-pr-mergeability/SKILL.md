---
name: refactor-pr-mergeability
description: Helps refactor a large, messy branch with many changes into smaller, logical commits or a Graphite stack of PRs. Ensures tests and linting pass at each step, and maintains the exact final state of the code.
disable-model-invocation: true
---

# Refactor PR into Logical Commits/Stack

## Description
Helps refactor a large, messy branch with many changes into smaller, logical commits or a Graphite stack of PRs. Ensures tests and linting pass at each step, and maintains the exact final state of the code.

## When to Use
- You have a branch with many changes that should be broken up for easier review
- You want to create a logical progression of commits that tell a story
- You want to use Graphite to create a stack of dependent PRs
- You need to reorganize commits without losing any work

## Capabilities
- Analyzes git history and current changes to understand what was done
- Interactively asks how you want to split up the changes
- Identifies dependencies between different components
- Creates a structured plan for commit/stack organization
- Executes the plan while ensuring tests pass at each step
- Supports both simple commit splitting and Graphite stack creation
- Excludes specified files if requested

## Instructions

### Step 1: Understand the Current State

1. **Verify you're in a git repository**
   - Check current branch and status
   - Identify the source branch with all changes
   - Confirm the target branch to base new work on (usually `main`)

2. **Analyze the changes**
   - Use `git log` to review commit history
   - Use `git diff` against the base branch to see all changes
   - Identify the main files/directories that were modified
   - Use file exploration tools to understand the codebase structure

3. **Check for tooling**
   - Verify if Graphite (`gt`) is installed and initialized
   - Check what test commands are available (`pytest`, `npm test`, etc.)
   - Check what linting commands are available (`ruff`, `eslint`, etc.)

### Step 2: Gather Requirements from User

Ask the user the following questions using AskUserQuestion:

1. **Splitting Strategy**: "How would you like to split up this PR?"
   - Option A: "Logical feature groupings" - Split by related features/components
   - Option B: "Chronological order" - Follow the order things were built
   - Option C: "Dependency order" - Split by what depends on what
   - Option D: "Custom breakdown" - User will specify exact groupings

2. **Graphite Usage** (if `gt` is available): "Do you want to create a Graphite stack?"
   - Option A: "Yes, create separate PRs for each commit" (Recommended if 3+ commits)
   - Option B: "No, just create logical commits on one branch"

3. **Files to Exclude**: "Are there any files you want to exclude from the refactored version?"
   - Provide text input for comma-separated file paths
   - Examples: CLI tools, experimental code, temporary files

4. **Testing Requirements**: "What level of testing should be done at each step?"
   - Option A: "Full test suite + linting" (Recommended)
   - Option B: "Affected tests only + linting"
   - Option C: "Linting only (faster, less safe)"
   - Option D: "Skip testing (not recommended)"

5. **Additional Splitting Criteria** (if Option D "Custom breakdown" was selected):
   - Ask user to describe their preferred breakdown
   - Have them list the logical groupings in order
   - Note any dependencies between groups

### Step 3: Create the Refactoring Plan

Based on the user's answers, create a detailed plan that includes:

1. **Prerequisites**
   - Backup branch creation
   - Tool verification (gt, testing, linting)
   - New branch creation from base

2. **For each commit/stack**:
   - **Purpose**: One-line description of what this commit achieves
   - **Files to include**: Specific files/directories to add
   - **Dependencies**: What this commit depends on from previous commits
   - **Tests to run**: Specific test commands to verify this commit
   - **Commit message**: Draft commit message following conventional commits format
   - **Expected outcome**: What should work after this commit

3. **Final verification steps**
   - Full test suite execution
   - Comparison with source branch (excluding specified files)
   - Smoke tests or manual verification steps

4. **Submission steps**
   - If using Graphite: `gt submit --no-interactive` to create PRs
   - If not: Instructions for creating a single PR

### Step 4: Execute the Plan

For each commit in the plan:

1. **Copy/create files** from the source branch
   - Use `git show source-branch:path/to/file > path/to/file` to copy files
   - Or recreate files as needed
   - Stage files with `git add`

2. **Run tests and linting**
   - Execute the specified test commands
   - Execute linting commands
   - If tests fail, investigate and fix (or note as pre-existing failure)

3. **Create the commit**
   - If using Graphite: Use `gt create` with the commit message
   - If not using Graphite: Use `git commit` with heredoc for multi-line messages
   - Follow commit message format:
     ```
     Short summary line (imperative mood)

     Detailed description of what this commit does and why.
     Can be multiple paragraphs.

     Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
     ```

4. **Verify commit was created**
   - Check `git log` to confirm
   - Verify `git status` is clean

5. **Update todo list** to mark this commit complete

### Step 5: Final Verification

After all commits are created:

1. **Run full test suite**
   - Execute all tests to ensure nothing is broken
   - Run all linters

2. **Compare with source branch**
   - Use `git diff source-branch` to see differences
   - Should only show excluded files as different
   - Verify all intended changes are present

3. **Visual inspection**
   - Quickly review the commit log with `git log --oneline --graph`
   - Ensure the progression makes sense

### Step 6: Submit to Remote

1. **If using Graphite**:
   - Run `gt submit --no-interactive` to create all PRs
   - Provide the PR URLs to the user
   - Mention the stack URL for easy editing

2. **If not using Graphite**:
   - Push the branch to remote: `git push -u origin branch-name`
   - Provide instructions for creating a PR via GitHub CLI or web UI

3. **Provide summary**:
   - List all commits created
   - Show test results summary
   - Link to PR(s)
   - Note any issues or warnings

## Important Guidelines

### Commit Organization
- Each commit should be self-contained and compilable/runnable
- Tests should pass (or at least not regress) at each commit
- Commits should tell a story of how the feature was built
- Dependencies should flow in one direction (no circular dependencies)

### Testing Strategy
- Always run tests before committing
- If a test fails, investigate whether it's:
  - A new failure (must fix)
  - A pre-existing failure in source branch (document and continue)
  - An expected failure that will be fixed in a later commit (document)

### Graphite Best Practices
- Use `gt track` to track branches if needed
- Each commit in the stack should build on the previous one
- Keep stack depth reasonable (3-7 commits ideal)
- Use descriptive branch names if Graphite creates them

### Error Handling
- If git operations fail, explain the issue to the user
- If tests fail unexpectedly, ask user how to proceed
- If files are missing from source branch, notify user
- Always offer to continue, skip, or abort

### Communication
- Keep user informed of progress with todo list updates
- Explain what's happening at each step
- If something takes longer than expected, let user know
- Provide clear next steps at completion

## Example Workflow

1. User: "I have a messy branch with 50 files changed, help me split it up"
2. Analyze: Review changes, find they added a new API module
3. Ask Questions: Get user's preferred split (by feature), confirm Graphite usage
4. Create Plan:
   - Stack 1: Core API types and interfaces
   - Stack 2: Database models and migrations
   - Stack 3: API endpoints
   - Stack 4: Tests and documentation
5. Execute: Create each commit, run tests, verify
6. Submit: Use `gt submit` to create 4 PRs in a stack
7. Done: Provide PR links and summary

## Notes

- This skill does NOT modify the source branch - it creates new commits on a new branch
- The final code state should be identical to source (minus excluded files)
- If the source branch has merge conflicts with base, resolve those first
- Works with any language/framework that has testable code
- Supports both monorepos and single-project repos
