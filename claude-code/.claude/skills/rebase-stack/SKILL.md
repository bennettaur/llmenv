---
name: rebase-stack
description: Rebase a whole stack of dependent GitHub pull requests onto the latest default branch (main or master) in one pass, resolve conflicts by understanding what each side was doing, verify each layer, and force-push every branch in the stack atomically. Handles stacks managed by the gh-stack extension and plain branch chains, and restacks cleanly after a lower PR in the stack was squash-merged. Use this whenever the user wants to "rebase my stack", "restack", "update the stack", "rebase the PRs on main", "catch the stack up with main", or fix a stack after its bottom PR merged. For a single branch that should be merged rather than rebased, use merge-default-branch instead.
---

# Rebase a Stack of PRs

A stack is a chain of PRs where each one's base is the branch of the PR below it, and the bottom PR's base is the default branch. Rebasing a stack one branch at a time is slow and easy to get wrong: you rebase layer 1, then rebase layer 2 onto the new layer 1 with the right `--onto` cut point, and so on, and any branch you forget is left on the old history. This skill rebases the whole chain with **one** rebase of the top branch, so every commit is replayed once and every branch ref moves together.

The rules that matter most:

- Every branch in the stack is rebased, not only the current one. Find the whole stack first, including layers above the current branch.
- Record every branch's SHA before touching anything. Those SHAs are the force-push leases and the undo path.
- Never push one branch of the stack without the others. Push all of them in one atomic push.

## Step 1: Establish a safe starting point

1. Capture the current branch: `git rev-parse --abbrev-ref HEAD`. If it prints `HEAD` (detached), stop and ask which stack to rebase.
2. Check the working tree is clean: `git status --porcelain`. If it isn't, stop and ask whether to commit the changes first. Don't stash: rebasing over in-progress work tangles it with conflict resolution.
3. `git fetch origin --prune`.
4. Detect the default branch the same way as merge-default-branch: `git symbolic-ref refs/remotes/origin/HEAD --short`, running `git remote set-head origin --auto` first if that ref isn't set. Fall back to whichever of `origin/main` / `origin/master` exists, and ask if both or neither do. Call it `<default>` (e.g. `origin/main`) and its short name `<default-name>` (e.g. `main`).
5. If the current branch is `<default-name>`, stop. There is nothing to rebase, and the default branch is never rewritten.

## Step 2: Find the whole stack

Build an ordered list of branches from bottom (closest to the default branch) to top. Use the first source that works.

**gh-stack.** If `gh stack view` succeeds on the current branch, the stack is managed by the gh-stack extension. Take the branch order from its output and use the gh-stack path in Step 5. gh-stack keeps its own metadata, so don't rebase its branches with plain git.

**Open PRs.** Otherwise, read the PR graph from GitHub:

```bash
gh pr list --state open --limit 200 --json number,headRefName,baseRefName,author,isCrossRepository
```

- Walk **down** from the current branch: follow `baseRefName` from PR to PR until you reach `<default-name>`.
- Walk **up**: find the PR whose `baseRefName` is the current top branch, and repeat until no PR has the top branch as its base.
- If a branch's base isn't `<default-name>` and has no open PR, check whether its PR merged: `gh pr list --state merged --head <base> --json number,headRefOid,mergeCommit`. A merged layer is handled in Step 3.
- If two open PRs share the same base, the stack branches into a tree. Stop and ask which branch to treat as the top. One rebase of the top only moves the branches below it.
- If the current branch has no PR at all, ask the user for the stack's branches in order.

**Ask before rewriting someone else's branch.** If a PR in the stack is from a fork (`isCrossRepository`) or authored by someone else, stop and confirm before including it. A force push rewrites their branch under them.

Report the stack you found as a short bottom-to-top list (`#101 feat-a → #102 feat-b → #103 feat-c`) and carry on without waiting, unless something above told you to ask.

## Step 3: Sync local branches and record the starting point

For each branch in the stack:

- If it doesn't exist locally, create it from the remote: `git branch <b> origin/<b>`.
- If local is behind `origin/<b>`, fast-forward it: `git branch -f <b> origin/<b>` (or `git merge --ff-only` if it's checked out).
- If local and `origin/<b>` have diverged, stop and ask. Someone pushed to that branch, or there is unpushed local work, and the rebase would pick one silently.

Then record each branch's SHA. The values on `origin` are the leases for the push in Step 7, and they are how the user undoes the rebase:

```bash
for b in <bottom> ... <top>; do echo "$b $(git rev-parse origin/$b)"; done
```

Keep this list. Include it in the final report.

**Check the stack is linear.** Each branch's tip must be an ancestor of the next one: `git merge-base --is-ancestor <lower> <upper>`. If a lower branch has commits the upper one doesn't (someone amended layer 1 and never restacked), the single rebase below would drop them from the upper layers. Fix that first: rebase the upper part of the stack onto the lower branch with `git rebase --update-refs --onto <lower> <old-lower-tip> <top>`, where `<old-lower-tip>` is the commit the upper branch was built on (`git merge-base <lower> <upper>` usually finds it). If you can't tell where the upper branch was cut, ask.

**Merged layers.** If one or more bottom layers have already merged into `<default-name>`:

- Their commits are already on the default branch, often squashed into a single commit with a different SHA. A plain rebase would try to replay the original commits and conflict with their own squashed copy.
- Find the cut point: the merged PR's last head commit, `headRefOid` from the query in Step 2. Everything after that commit belongs to the layers still open.
- Drop the merged branches from the list of branches to rebase and push.
- Note the lowest open PR. Its base must change to `<default-name>` after the push (Step 7).

## Step 4: Prepare worktrees and build context

**Worktrees.** `git rebase --update-refs` silently skips any branch that is checked out in another worktree. The rebase reports success, and that branch stays on the old history. So check first:

```bash
git worktree list --porcelain
```

For each stack branch checked out in a worktree other than this one:

1. Check that worktree is clean: `git -C <path> status --porcelain`. If it isn't, stop and ask.
2. Detach it so the rebase can move the branch: `git -C <path> switch --detach`.
3. Remember the path. Step 8 switches it back.

If you can't write to another worktree (a sandbox may block it), stop and tell the user which worktrees need detaching.

**Context.** Before rebasing, learn what each side is doing. A conflict resolution is only as good as your understanding of both sides.

```bash
git log --oneline <bottom-base>..<default>    # what is new on the default branch
git diff --stat <bottom-base>..<default>
for each layer: git log --oneline <layer-below>..<layer>   # what each PR does
```

`<bottom-base>` is `git merge-base <bottom> <default>`, or the merged PR's `headRefOid` when bottom layers merged. Form a one-sentence summary of what the incoming default-branch changes do and what each layer does. Files that appear in both the default-branch stat and a layer's diff are where conflicts will be.

## Step 5: Rebase the whole stack

### Plain git

Check out the top branch and rebase it. `--update-refs` moves every branch in the stack below it as the rebase passes their tips. Turning on `rerere` means a conflict you resolve once is applied again automatically if the same hunk conflicts in a later commit.

```bash
git checkout <top>
git -c rerere.enabled=true rebase --update-refs <default>
```

When bottom layers merged, cut at the merged PR's head so its commits aren't replayed:

```bash
git -c rerere.enabled=true rebase --update-refs --onto <default> <merged-head-oid> <top>
```

### gh-stack

```bash
gh stack rebase
```

Don't use `gh stack sync` here: it aborts and restores every branch on the first conflict. `gh stack rebase` stops for you to resolve it.

### Outcomes

- **Nothing to do** (each branch already contains the latest default branch): report and stop.
- **Clean rebase:** go to Step 6. A clean rebase can still break the build.
- **Conflict:** resolve it as in the next section, then continue with `GIT_EDITOR=true git rebase --continue` (plain git) or `gh stack rebase --continue` (gh-stack). Repeat until the rebase finishes.

### Resolving conflicts

During a rebase, "ours" and "theirs" are the reverse of a merge:

```bash
git show :1:path   # base: the replayed commit's parent, before this rebase
git show :2:path   # ours: the new base, i.e. the default branch plus the layers already replayed
git show :3:path   # theirs: the commit being replayed from the stack
```

`git log -1 REBASE_HEAD` shows the commit being replayed. Its message tells you which layer of the stack you are in.

Resolve by intent, the same way merge-default-branch does:

- **Same change on both sides:** take either.
- **Different changes in the same region:** combine them so both survive. This is the common case.
- **One side refactored the region the other changed:** re-apply the stack commit's change on top of the refactor. Don't take "ours" and silently drop the PR's change.
- **Lockfiles and generated files:** take "ours" (the new base) and regenerate, then stage the result.
- **modify/delete, or competing designs for the same behavior:** ask the user. State what each side does and lead with the option you'd pick.

Two rebase-specific cases:

- **A commit becomes empty** because its change is already on the default branch: run `git rebase --skip`. Mention it in the report.
- **The same conflict at every layer:** that is expected when several layers touch the same lines. `rerere` replays your resolution. Check each replayed one still makes sense for that layer before staging it.

Stage each resolved file with `git add <path>`. If the rebase gets into a state you don't understand, `git rebase --abort` (or `gh stack rebase --abort`) restores every branch and is always safe before you push.

## Step 6: Verify each layer

Every branch is now new code that has never been tested, so check each one. First confirm the branches really moved and that each layer still contains only its own changes:

```bash
git range-diff <old-lower>..<old-layer> <new-lower>..<new-layer>   # for each layer
```

`<old-lower>` and `<old-layer>` are the SHAs recorded in Step 3, and `<old-lower>` for the bottom layer is its old merge base with the default branch. Commits marked `=` are unchanged. Commits marked `!` changed, which should only be where you resolved conflicts. A missing commit, or a commit from another layer showing up, means the stack was cut at the wrong point. Stop and fix it before going further.

Then run the project's checks. Find the commands in `package.json`, `Makefile`, `Rakefile`, `pyproject.toml`, CI config, or CLAUDE.md.

- On the **top** branch, run the build, lint, and the full test suite. It contains every layer.
- On each **lower** branch where you resolved a conflict, check it out and run at least the build and the tests for the files involved. Each layer is its own PR, so it has to pass CI on its own.

If a check fails because of the rebase, fix it in a new commit on the layer where the problem belongs, then restack the layers above it with `git rebase --update-refs <layer> <top>` from the top branch. If you can't fix it, stop and report. Don't push a stack that fails verification.

## Step 7: Push every branch atomically

Push all the open branches in one atomic push, each with an explicit lease set to the SHA recorded in Step 3. If any branch moved on `origin` since then, the whole push is rejected and nothing is overwritten.

```bash
git push --atomic origin \
  --force-with-lease=<b1>:<old-sha-1> \
  --force-with-lease=<b2>:<old-sha-2> \
  <b1> <b2> ...
```

With gh-stack, run `gh stack push` instead. It does the same atomic, leased push and skips merged branches.

Never use a bare `--force`, and never skip hooks with `--no-verify`.

If the push is rejected:

- **Stale lease** (someone pushed to a stack branch): don't overwrite it. Fetch, see what they pushed, and ask the user how to fold it in.
- **A pre-push hook fails:** if the rebase caused it, fix it as in Step 6 and push again. Otherwise stop and report.
- **Branch protection or permissions:** stop and report. Don't work around it.

If bottom layers merged, retarget the lowest open PR once the push succeeds. GitHub usually does this when a merged branch is deleted, so check first:

```bash
gh pr view <lowest-open-pr> --json baseRefName
gh pr edit <lowest-open-pr> --base <default-name>   # only if it still points at the merged branch
```

## Step 8: Restore worktrees and report

Switch each worktree you detached in Step 4 back to its branch: `git -C <path> switch <branch>`. It now shows the rebased branch. Check out the branch you started on in this worktree.

Then report:

- The stack, bottom to top, with each PR number and branch.
- How many commits came in from the default branch.
- Each conflict you resolved: the layer, the file, and what you did. Call out every "combined both" and "re-applied on top of a refactor" decision, since that is where a wrong call hides. List any commits you skipped as empty.
- What you verified on which branch, and the result.
- Whether the push succeeded, and any PR base you changed.
- How to undo: the old SHAs from Step 3, and the command to put the stack back. Don't run it unless asked.

  ```bash
  git push --atomic origin \
    --force-with-lease=<b1>:<new-sha-1> <old-sha-1>:refs/heads/<b1> \
    --force-with-lease=<b2>:<new-sha-2> <old-sha-2>:refs/heads/<b2> ...
  ```

## Notes

- This skill rebases and force-pushes. To bring a single branch up to date without rewriting history, use merge-default-branch.
- It never rewrites or pushes the default branch.
- Each layer's commits are replayed once, so a conflict in layer 1 is resolved once, not once per branch above it.
