#!/usr/bin/env bash
# Runs validate-git-hooks.py against known commands. Each case is
# EXPECTED|command, with \n for newlines. Requires jq.
set -uo pipefail
hook="$(dirname "$0")/validate-git-hooks.py"
failures=0
while IFS='|' read -r expected command; do
  command=$(printf '%b' "$command")
  output=$(jq -n --arg c "$command" '{tool_name:"Bash",tool_input:{command:$c}}' | "$hook")
  actual=$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"' 2>/dev/null || echo allow)
  actual=$(printf '%s' "${actual:-allow}" | tr '[:lower:]' '[:upper:]')
  if [ "$actual" != "$expected" ]; then
    failures=$((failures + 1))
    echo "FAIL expected=$expected actual=$actual :: $command"
  fi
done <<'CASES'
DENY|git commit -n -m x
DENY|git commit -nm x
DENY|git commit -an -m x
DENY|git commit -m x -n
DENY|git commit --no-verify -m x
DENY|git commit --no-verif -m x
DENY|git commit --no-veri
DENY|git push --no-verify
DENY|git push -u origin b --no-verify
DENY|cd repo && git commit -an -m "x"
DENY|git -c core.hooksPath=/dev/null commit -m x
ASK|git config core.hooksPath /tmp/empty
DENY|SKIP=gitleaks git commit -m x
DENY|HUSKY=0 git commit -m x
DENY|/usr/bin/git commit -n
DENY|git merge --no-verify main
ALLOW|git commit -m "fix -n handling"
ALLOW|git commit -m 'mention --no-verify in docs'
ALLOW|git commit -F - <<'EOF2'\nAdd -n flag support --no-verify\nEOF2
ALLOW|git commit --no-edit
ALLOW|git commit --amend --no-edit
ALLOW|git commit --no-gpg-sign -m x
ALLOW|git commit -am x
ALLOW|git commit -S -m x
ALLOW|git diff --name-only
ALLOW|git log -n 5
ALLOW|git push -u origin HEAD
ALLOW|git commit --message "-n"
ALLOW|git -C /some/path commit -m x
ALLOW|ls -la
ALLOW|git status && git commit -m "a; b -n"
DENY|cd repo\ngit commit --no-verify -m x
DENY|git add -A\ngit commit -n -m x
DENY|(cd repo); git commit -n -m x
DENY|true&&(git commit -n -m x)
DENY|export HUSKY=0 && git commit -m x
DENY|export SKIP=gitleaks; git commit -m x
DENY|time git commit -n -m x
DENY|timeout 60 git commit -n -m x
DENY|{ git commit -n -m x; }
DENY|if true; then git commit -n -m x; fi
DENY|! git commit -n
DENY|xargs git commit -n
DENY|sh -c 'git commit -n -m x'
DENY|bash -c "git commit --no-verify"
DENY|git --config-env core.hooksPath=FOO commit -m x
DENY|git -ccore.hooksPath=/dev/null commit -m x
DENY|git am -n x.patch
DENY|GIT_CONFIG_GLOBAL=/tmp/cfg git commit -m x
DENY|LEFTHOOK_EXCLUDE=gitleaks git commit -m x
ASK|git config set core.hooksPath /tmp/x
DENY|echo `git commit -n`
ASK|git push --force
ASK|git push --force-with-lease origin b
ASK|git -C /repo push -uf origin main
ASK|git push origin +main
ASK|git push --mirror
ALLOW|git commit -m "document core.hooksPath setting"
ALLOW|git config --get core.hooksPath
ALLOW|git config core.hooksPath
ALLOW|git log --grep=core.hooksPath
ALLOW|git commit -m "$(cat <<'EOF2'\nBlock "git commit -n" and HUSKY=0\nEOF2\n)"
ALLOW|git commit -F - <<'EOF2'\nDon't skip -n\nEOF2
ALLOW|git push -n origin b
ALLOW|git push -u origin HEAD
ALLOW|git push -o ci.skip origin b
ALLOW|git tag -n
ALLOW|git merge --no-verify-signatures main
ALLOW|echo git commit -n
ALLOW|grep -rn git src
ALLOW|git commit -mn
ALLOW|git commit --message -n
DENY|env HUSKY=0 git commit -m x
DENY|cd repo \&\& env SKIP=gitleaks git commit -m x
DENY|env git commit -n -m x
DENY|cat > /tmp/msg <<'EOF2' \&\& git commit -n -F /tmp/msg\nFix thing\nEOF2
DENY|git commit -F - <<'EOF2' --no-verify\nFix thing\nEOF2
DENY|bash -lc 'git commit -n -m x'
DENY|bash -l -c 'git commit -n -m x'
DENY|timeout 30s git push --no-verify
DENY|bash <<'EOF2'\ngit commit -n -m x\nEOF2
DENY|git rebase -i --exec 'git commit --amend --no-verify' HEAD~2
DENY|git rebase -x 'git commit -n' HEAD~2
ASK|git config core.hooksPath .githooks
ALLOW|bash scripts/build.sh
ALLOW|git rebase --exec 'make test' HEAD~3
CASES
echo "$failures failure(s)"
[ "$failures" -eq 0 ]
