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

## Names used below

Fill these in as you go and use the same names throughout:

- `<default>` / `<default-name>`: the default branch as a remote ref (`origin/main`) and as a branch name (`main`). Set in Step 1.
- `<b1>` … `<bN>`: the open stack branches, bottom to top. `<top>` is `<bN>`. Set in Step 2.
- `<cut>`: the commit the bottom open branch was built on. Everything after it belongs to the stack. Set in Step 2.
- `<old-bK>`: each branch's SHA before the rebase. Set in Step 4.

Quote branch names in every shell command. They come from GitHub and can contain shell metacharacters.

## Step 1: Establish a safe starting point

1. Capture the current branch: `git rev-parse --abbrev-ref HEAD`. If it prints `HEAD` (detached), stop and ask which stack to rebase.
2. Check the working tree is clean: `git status --porcelain`. If it isn't, stop and ask whether to commit the changes first. Don't stash: rebasing over in-progress work tangles it with conflict resolution.
3. `git fetch origin --prune`.
4. Detect the default branch: `git symbolic-ref refs/remotes/origin/HEAD --short`, running `git remote set-head origin --auto` first if that ref isn't set. Fall back to whichever of `origin/main` / `origin/master` exists, and ask if both or neither do.
5. If the current branch is `<default-name>`, stop. There is nothing to rebase, and the default branch is never rewritten.

## Step 2: Find the whole stack

Build the ordered list `<b1>` … `<bN>`. Use the first source that works.

**gh-stack.** If `gh stack view --json` succeeds on the current branch, the stack is managed by the gh-stack extension. Take the order from `.branches[]`, skipping merged ones, and use the gh-stack paths in the steps below. Don't run `gh stack view` without `--json`: it opens an interactive view that hangs. gh-stack keeps its own metadata, so never move its branches with plain git.

**Open PRs.** Otherwise, read the PR graph from GitHub:

```bash
gh api user --jq .login     # the current user
gh pr list --state open --limit 200 \
  --json number,headRefName,baseRefName,author,isCrossRepository,headRefOid
```

- Walk **down** from the current branch: follow `baseRefName` from PR to PR until you reach `<default-name>`.
- Walk **up**: find the open PR whose `baseRefName` is the highest branch found so far, and repeat until there is none.
- If a base along the way is not `<default-name>` and has no open PR, check whether its PR merged (`gh pr list --state merged --head "<base>" --json number,headRefOid,baseRefName`). If it has no merged PR either (for example `develop` or a release branch), stop and ask. Never treat a branch without a PR as a stack layer.
- If a stack branch is the base of two or more open PRs, the stack branches into a tree. Stop and ask which branch is the top. One rebase of the top only moves the branches below it.
- If the current branch has no PR at all, ask the user for the stack's branches in order.

**Leave out branches you can't or shouldn't push.** Drop any PR with `isCrossRepository: true`: its branch lives in a fork, and a same-named branch on `origin` is a different branch. If a PR's `author.login` isn't the current user, stop and confirm before including it. A force push rewrites their branch under them. This applies to the gh-stack path too.

**Find merged layers, every time.** A lower layer may already have merged, often squashed into one commit with a different SHA. Its original commits are still in the branches above it, and a plain rebase would replay them and conflict with their own squashed copy. GitHub usually retargets the next PR to `<default-name>` when the merged branch is deleted, so the walk above won't always notice. Check directly:

```bash
gh pr list --state merged --base "<default-name>" --limit 50 --json number,headRefName,headRefOid
```

Keep the PRs whose `headRefOid` is an ancestor of `<b1>` (`git merge-base --is-ancestor <oid> "<b1>"`). If that commit isn't local, fetch it first with `git fetch origin "refs/pull/<number>/head"`. If one or more match, `<cut>` is the `headRefOid` of the highest of them, the one directly below `<b1>`. If none match, `<cut>` is `git merge-base "<b1>" <default>`.

Report the stack as a short bottom-to-top list (`#101 feat-a → #102 feat-b → #103 feat-c`, plus any merged layers) and carry on, unless something above told you to ask.

## Step 3: Free branches checked out in other worktrees

`git rebase --update-refs` silently skips any branch that is checked out in another worktree. The rebase reports success, and that branch stays on the old history. `git branch -f` refuses to move such a branch at all. So deal with worktrees before anything moves a branch:

```bash
git worktree list --porcelain
```

For each stack branch checked out in a worktree other than this one:

1. Check that worktree is clean: `git -C <path> status --porcelain`. If it isn't, stop and ask.
2. Detach it: `git -C <path> switch --detach`. Note the path and the SHA it was detached at.

From here on, **every way this skill ends** (success, "nothing to do", abort, or stopping to ask) must first switch those worktrees back. Before switching, check `git -C <path> rev-parse HEAD` still equals the SHA it was detached at. If it doesn't, someone committed there while detached. Stop and report instead of switching, or those commits are orphaned.

If you can't write to another worktree (a sandbox may block it), stop and tell the user which worktrees need detaching.

Do this on the gh-stack path too. It isn't known whether `gh stack rebase` handles other worktrees itself.

## Step 4: Sync local branches and record the starting point

For each stack branch, compare local with the remote: `git rev-list --left-right --count "<b>...origin/<b>"` (left = local only, right = remote only).

- **Missing locally:** `git branch "<b>" "origin/<b>"`.
- **Behind only:** fast-forward it, `git branch -f "<b>" "origin/<b>"`. For the branch checked out in this worktree, use `git merge --ff-only "origin/<b>"`.
- **Ahead only** (unpushed local commits): stop and ask whether to include them. The push would publish them.
- **Diverged:** stop and ask. Someone pushed to that branch, or there is unpushed local work, and the rebase would pick one silently.
- **Not on `origin` yet:** its lease in Step 8 is `--force-with-lease="<b>":` (empty value means "must not exist").

Then record each branch's SHA. These are the push leases and the undo path:

```bash
for b in "<b1>" ... "<bN>"; do echo "$b $(git rev-parse "origin/$b")"; done
```

**Check the stack is linear.** Each branch's tip must be an ancestor of the next one: `git merge-base --is-ancestor "<lower>" "<upper>"`. If not, a lower branch was amended and the layers above were never restacked. The single rebase in Step 6 would drop the amendment from the upper layers.

- With gh-stack, skip this. `gh stack rebase` restacks the layers onto each other itself.
- With plain git, the upper part has to be cut at the **old** tip of the lower branch, the commit the upper branch was built on. Find it with `git merge-base --fork-point "<lower>" "<upper>"` (it reads the reflog). Don't use plain `git merge-base`: after an amend it returns the commit before the old tip, and the rebase replays the pre-amend commit. Then run `git rebase --update-refs --onto "<lower>" <old-lower-tip> "<top>"` and resolve conflicts as in Step 6. If `--fork-point` prints nothing, or you aren't sure the commit is right, ask.

**Check for stray branches.** `--update-refs` moves *every* local branch that points at a commit being rewritten, not only stack branches. List them first:

```bash
git log --oneline --decorate "<cut>..<top>"
```

Note any branch name in the output that isn't in the stack (a backup branch, say). After the rebase, move it back with `git branch -f "<x>" <its-old-sha>`.

## Step 5: Build context

Before rebasing, learn what each side is doing. A conflict resolution is only as good as your understanding of both sides.

```bash
git log --oneline "<cut>..<default>"        # what is new on the default branch
git diff --stat "<cut>..<default>"
```

For each layer, run `git log --oneline` and `git diff --stat` over `"<layer-below>..<layer>"`, using `<cut>` as the layer below `<b1>`.

Form a one-sentence summary of what the incoming default-branch changes do and what each layer does. Files that appear in both the default-branch stat and a layer's stat are where conflicts will be.

## Step 6: Rebase the whole stack

### Plain git

Rebase the top branch onto the default branch, cutting at `<cut>`. `--update-refs` moves every stack branch below the top as the rebase passes their tips. Turning on `rerere` records each resolution, so an identical conflict that comes up again (for example after an abort and retry) is resolved for you.

```bash
git -c rerere.enabled=true rebase --update-refs --onto <default> <cut> "<top>"
```

When no layer merged, `<cut>` is the merge base, and this is the same as a plain `git rebase --update-refs <default>`.

### gh-stack

```bash
gh stack rebase
```

Don't use `gh stack sync` here: it aborts and restores every branch on the first conflict. `gh stack rebase` stops for you to resolve it.

### Outcomes

- **Nothing to do** (each branch already contains the latest default branch): restore worktrees (Step 3), report, and stop.
- **Clean rebase:** go to Step 7. A clean rebase can still break the build.
- **Conflict:** resolve it as in the next section, then continue with `GIT_EDITOR=true git -c rerere.enabled=true rebase --continue` or `GIT_EDITOR=true gh stack rebase --continue`. Repeat until the rebase finishes.

When it finishes, compare git's "Updated the following refs" list with the stack, and reset any stray branch you noted in Step 4.

### Resolving conflicts

During a rebase, "ours" and "theirs" are the reverse of a merge:

```bash
git show :1:path   # base: the replayed commit's parent, before this rebase
git show :2:path   # ours: the new base, i.e. the default branch plus the layers already replayed
git show :3:path   # theirs: the commit being replayed from the stack
```

`git log -1 REBASE_HEAD` shows the commit being replayed. Its message tells you which layer of the stack you are in.

Resolve by intent:

- **Same change on both sides:** take either.
- **Different changes in the same region:** combine them so both survive. This is the common case.
- **One side refactored the region the other changed:** re-apply the stack commit's change on top of the refactor. Don't take "ours" and silently drop the PR's change.
- **Lockfiles and generated files:** take "ours" (the new base) and regenerate, then stage the result.
- **modify/delete, or competing designs for the same behavior:** ask the user. State what each side does and lead with the option you'd pick.

Stage each resolved file with `git add <path>`.

Git drops some commits on its own. A commit whose change is already on the default branch is skipped ("skipped previously applied commit"). A commit that your resolution leaves empty is dropped on `--continue`. Watch the rebase output for these and list them in the report.

If the rebase gets into a state you don't understand, `git rebase --abort` (or `gh stack rebase --abort`) restores every branch. Restore worktrees too (Step 3).

## Step 7: Verify each layer

Every branch is now new code that has never been tested, so check each one. First confirm the branches really moved and that each layer still contains only its own commits:

```bash
git range-diff <old-lower>..<old-layer> "<lower>..<layer>"
```

`<old-layer>` and `<old-lower>` are the SHAs from Step 4, and the new side is the local branch names. For the bottom layer, the old side is `<cut>..<old-b1>` and the new side is `<default>..<b1>`. Example for the second layer: `git range-diff <old-b1>..<old-b2> "<b1>..<b2>"`.

Commits marked `=` are unchanged. Commits marked `!` changed, which should only happen where you resolved a conflict. A commit marked `<` with no match was dropped, which is expected only for the ones git skipped in Step 6. Any other missing commit, or a commit from another layer showing up, means the stack was cut at the wrong point. Stop and fix it before going further.

Then run the project's checks. Find the commands in `package.json`, `Makefile`, `Rakefile`, `pyproject.toml`, CI config, or CLAUDE.md.

- On the **top** branch, run the build, lint, and the full test suite. It contains every layer.
- On each **lower** branch where you resolved a conflict, check it out and run at least the build and the tests for the files involved. Each layer is its own PR, so it has to pass CI on its own.

If a check fails because of the rebase, fix it in a new commit on the layer where the problem belongs. Then restack the layers above it: `git rebase --update-refs "<layer>" "<top>"`, or `gh stack rebase --upstack` from that layer with gh-stack. If a check also fails on the old branches, it isn't caused by the rebase. Say so in the report and carry on. If you can't fix a rebase-caused failure, stop and report. Don't push a stack that fails verification.

## Step 8: Confirm, then push every branch atomically

Check the push list one last time. It must contain only the open stack branches from Step 2, and never `<default-name>`.

Then ask the user once before pushing. Show each branch with its old → new SHA, the conflicts you resolved, and the verification result. This rewrites every PR in the stack, so it gets one explicit yes.

Push all the branches in one atomic push, each with an explicit lease set to the SHA recorded in Step 4. If any branch moved on `origin` since then, the whole push is rejected and nothing is overwritten.

```bash
git push --atomic origin \
  --force-with-lease="<b1>":<old-b1> \
  --force-with-lease="<b2>":<old-b2> \
  "<b1>" "<b2>" ...
```

With gh-stack, run `gh stack push` instead. Its help says it pushes with `--force-with-lease --atomic` and skips merged branches. That is untested against a real stack, so if the push reports anything unexpected, stop and report.

Never use a bare `--force`, and never skip hooks with `--no-verify`.

If the push is rejected:

- **Stale lease** (someone pushed to a stack branch): don't overwrite it. Fetch, see what they pushed, and ask the user how to fold it in.
- **A pre-push hook fails:** if the rebase caused it, fix it as in Step 7 and push again. Otherwise stop and report.
- **Branch protection or permissions:** stop and report. Don't work around it.

After a successful push, record each branch's new SHA (`git rev-parse "<b>"`). The undo command needs them.

If layers merged, check the lowest open PR's base. GitHub usually retargets it when the merged branch is deleted:

```bash
gh pr view <b1-pr-number> --json baseRefName
gh pr edit <b1-pr-number> --base "<default-name>"   # only if it still points at the merged branch
```

## Step 9: Restore worktrees and report

Switch each worktree you detached back to its branch, with the HEAD check from Step 3. Check out the branch you started on in this worktree.

Then report:

- The stack, bottom to top, with each PR number and branch, and any merged layers you cut out.
- How many commits came in from the default branch.
- Each conflict you resolved: the layer, the file, and what you did. Call out every "combined both" and "re-applied on top of a refactor" decision, since that is where a wrong call hides. List any commits git dropped.
- What you verified on which branch, and the result.
- Whether the push succeeded, and any PR base you changed.
- How to undo, using the old SHAs from Step 4 and the new SHAs from Step 8. Don't run it unless asked. It restores the remote branches. Running `git branch -f "<b>" <old-bK>` for each branch restores the local ones, and any PR base you changed has to be set back with `gh pr edit --base`. If you put SHAs in shell variables, write `${sha}:refs/heads/...`, because zsh reads `$sha:r` as a modifier.

  ```bash
  git push --atomic origin \
    --force-with-lease="<b1>":<new-b1> <old-b1>:refs/heads/<b1> \
    --force-with-lease="<b2>":<new-b2> <old-b2>:refs/heads/<b2> ...
  ```

## Notes

- This skill rebases and force-pushes. To bring a single branch up to date without rewriting history, use merge-default-branch.
