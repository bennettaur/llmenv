#!/usr/bin/env bash
# Runs bin/merge-settings against settings files in a temp dir. Requires jq.
set -uo pipefail
ms="$(cd "$(dirname "$0")/.." && pwd)/bin/merge-settings"
failures=0
export PYTHONDONTWRITEBYTECODE=1

fail() {
  failures=$((failures + 1))
  echo "FAIL $1"
}

expect_json() {
  local file=$1 filter=$2 expected=$3 name=$4
  local actual
  actual=$(jq -c "$filter" "$file")
  [ "$actual" = "$expected" ] || fail "$name: $filter in $(basename "$file") expected=$expected actual=$actual"
}

# Interactive mode only runs on a terminal, so pretend stdin is one.
run_interactive() {
  python3 -c 'import runpy, sys; sys.stdin.isatty = lambda: True; sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name="__main__")' "$ms" "$@"
}

edit_settings() {
  jq "$1" settings.json > settings.json.edit && mv settings.json.edit settings.json
}

setup() {
  # Fixtures must never land in the caller's directory
  dir=$(mktemp -d "${TMPDIR:-/tmp}/merge-settings.XXXXXX") &&[ -n "$dir" ] && cd "$dir" || { echo "could not create a temp dir"; exit 1; }
  echo '{"env": {"A": "1"}, "permissions": {"allow": ["x"]}}' > settings.base.json
  echo '{"env": {"B": "2"}}' > settings.personal.json
  echo '{"env": {"B": "3"}, "permissions": {"allow": ["y"]}}' > settings.work.json
  echo '{"theme": "dark"}' > settings.other.json
  "$ms" -p personal -p work > /dev/null 2>&1 || fail "setup merge exited non-zero"
}

name="applies profiles in the order given"
setup
expect_json settings.json '.env' '{"A":"1","B":"3"}' "$name"
expect_json settings.json '.permissions.allow' '["x","y"]' "$name"
cmp -s settings.json settings.json.spec || fail "$name: spec differs from settings.json"

name="-p base alone writes only base settings"
setup
rm settings.json settings.json.spec
"$ms" -p base > /dev/null 2>&1
expect_json settings.json '.' "$(jq -c . settings.base.json)" "$name"

name="refuses to overwrite drifted settings.json without a terminal"
setup
edit_settings '.env.C = "9"'
cp settings.json before.json
output=$("$ms" -p personal -p work < /dev/null 2>&1)
[ $? -eq 1 ] || fail "$name: expected exit 1"
cmp -s settings.json before.json || fail "$name: settings.json was overwritten"
grep -q '+ C: "9"' <<< "$output" || fail "$name: change not listed"

name="accepts drift that only reorders list items"
setup
edit_settings '.permissions.allow |= reverse'
"$ms" -p personal -p work < /dev/null > /dev/null 2>&1 || fail "$name: expected exit 0"
expect_json settings.json '.permissions.allow' '["x","y"]' "$name"

name="detects removing one copy of a duplicated list item"
setup
echo '{"permissions": {"allow": ["x"]}}' > settings.personal.json
"$ms" -p personal -p work > /dev/null 2>&1
edit_settings '.permissions.allow = ["x", "y"]'
output=$("$ms" -p personal -p work < /dev/null 2>&1)
grep -q '\- "x"' <<< "$output" || fail "$name: removal not listed"

name="moves an added key into the chosen profile"
setup
edit_settings '.env.C = "9"'
printf '1\n2\n' | run_interactive -p personal -p work > /dev/null 2>&1 || fail "$name: expected exit 0"
expect_json settings.personal.json '.env' '{"B":"2","C":"9"}' "$name"
expect_json settings.json '.env.C' '"9"' "$name"
cmp -s settings.json settings.json.spec || fail "$name: spec differs from settings.json"

name="quitting part way writes no files"
setup
edit_settings '.env.C = "9" | .env.D = "8"'
cp settings.json before.json
cp settings.personal.json personal-before.json
printf '1\n2\nq\n' | run_interactive -p personal -p work > /dev/null 2>&1
[ $? -eq 1 ] || fail "$name: expected exit 1"
cmp -s settings.json before.json || fail "$name: settings.json changed"
cmp -s settings.personal.json personal-before.json || fail "$name: profile changed"

name="ignoring a change drops it from settings.json"
setup
edit_settings '.env.C = "9"'
printf '1\ni\n' | run_interactive -p personal -p work > /dev/null 2>&1
expect_json settings.json '.env.C' 'null' "$name"

name="removing a key prunes the block it emptied"
setup
edit_settings 'del(.env.B)'
# Only personal and work hold env.B; pick work
printf '1\n2\n' | run_interactive -p personal -p work > /dev/null 2>&1
expect_json settings.work.json 'has("env")' 'false' "$name"

name="warns when another file in the merge overrides the change"
setup
edit_settings '.env.B = "5"'
output=$(printf '1\n2\n' | run_interactive -p personal -p work 2>&1)
grep -q 'is set by another file in this merge' <<< "$output" || fail "$name: no warning"

name="offers profiles outside the merge without warning about them"
setup
edit_settings '.env.C = "9"'
output=$(printf '1\n4\n' | run_interactive -p personal -p work 2>&1)
grep -q 'settings.other.json  (not in this merge)' <<< "$output" || fail "$name: other profile not offered"
expect_json settings.other.json '.env.C' '"9"' "$name"
grep -q 'is set by another file' <<< "$output" && fail "$name: unexpected warning"

name="does not offer a file with a conflicting type"
setup
echo '{"env": "oops"}' > settings.other.json
edit_settings '.env.C = "9"'
output=$(printf '1\nb\nq\n' | run_interactive -p personal -p work 2>&1)
grep -q 'settings.other.json' <<< "$output" && fail "$name: conflicting file offered"

[ "$failures" -eq 0 ]
