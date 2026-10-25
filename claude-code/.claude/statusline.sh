#!/bin/bash

# One jq call for every field keeps the script fast. Fields are split on \x1f
# because tab is whitespace to `read`, which would collapse empty fields.
IFS=$'\x1f' read -r model dir context_pct pr_number pr_url pr_review_state \
  five_hour_pct five_hour_reset seven_day_pct seven_day_reset < <(
  jq -r '
    def pct: if type == "number" then floor else "" end;
    def reset_time(fmt): if type == "number" then floor | strflocaltime(fmt) else "" end;
    [
      .model.display_name // "unknown",
      .workspace.current_dir // .cwd // "",
      (.context_window.used_percentage | pct),
      .pr.number // "",
      .pr.url // "",
      .pr.review_state // "",
      (.rate_limits.five_hour.used_percentage | pct),
      (.rate_limits.five_hour.resets_at | reset_time("%-I:%M%p")),
      (.rate_limits.seven_day.used_percentage | pct),
      (.rate_limits.seven_day.resets_at | reset_time("%a %-I%p"))
    ] | map(tostring) | join("\u001f")' 2>/dev/null
)
model=${model:-unknown}
context_pct=${context_pct:-0}

# Real escape bytes, so the line prints with %s and backslashes in the data
# are never treated as escapes.
GREEN=$'\033[38;2;0;255;65m'
ORANGE=$'\033[38;2;255;165;0m'
RED=$'\033[38;2;255;100;100m'
CYAN=$'\033[38;2;0;206;200m'
WHITE=$'\033[97m'
DIM=$'\033[2m'
RESET=$'\033[0m'

# Prints the color for a percent: green below warn_at, orange below alert_at, red otherwise.
color_for_pct() {
  local pct=$1 warn_at=$2 alert_at=$3
  if [ "$pct" -lt "$warn_at" ]; then
    printf '%s' "$GREEN"
  elif [ "$pct" -lt "$alert_at" ]; then
    printf '%s' "$ORANGE"
  else
    printf '%s' "$RED"
  fi
}

# Get git branch, and where it sits in a gh-stack stack
branch="no git"
stack=""
if git_info=$(git -C "${dir:-.}" rev-parse --abbrev-ref HEAD --git-common-dir 2>/dev/null); then
  branch=${git_info%%$'\n'*}
  common_dir=${git_info#*$'\n'}
  # git prints a path relative to $dir outside linked worktrees.
  [[ "$common_dir" = /* ]] || common_dir="${dir:-.}/$common_dir"

  # Reads gh-stack's local file instead of running `gh stack`, so no network call.
  if [ -f "$common_dir/gh-stack" ]; then
    stack=$(jq -r --arg b "$branch" 'first(
      .stacks[].branches | map(.branch) | index($b) as $i
      | select($i != null) | "\($i + 1)/\(length)"
    )' "$common_dir/gh-stack" 2>/dev/null)
  fi
fi

line="👤 $(color_for_pct "$context_pct" 25 50)${model} (${context_pct}%)${RESET}"
line+=" | 📁 ${WHITE}${dir/#$HOME/~}${RESET}"
line+=" | 🌳 ${CYAN}${branch}${RESET}"
[ -n "$stack" ] && line+=" ${DIM}📚 ${stack}${RESET}"
if [ -n "$pr_number" ]; then
  if [ -n "$pr_url" ]; then
    # OSC 8 makes the PR number a clickable link.
    line+=" | 🔀 "$'\033]8;;'"${pr_url}"$'\a'"#${pr_number}"$'\033]8;;\a'
  else
    line+=" | 🔀 #${pr_number}"
  fi
  [ -n "$pr_review_state" ] && line+=" ${DIM}${pr_review_state//_/ }${RESET}"
fi
printf '%s\n' "$line"

# rate_limits is only sent to Pro/Max subscribers, after the first response.
limits=()
if [ -n "$five_hour_pct" ]; then
  limit="⏳ 5h $(color_for_pct "$five_hour_pct" 50 80)${five_hour_pct}%${RESET}"
  [ -n "$five_hour_reset" ] && limit+=" ${DIM}resets ${five_hour_reset}${RESET}"
  limits+=("$limit")
fi
if [ -n "$seven_day_pct" ]; then
  limit="📅 7d $(color_for_pct "$seven_day_pct" 50 80)${seven_day_pct}%${RESET}"
  [ -n "$seven_day_reset" ] && limit+=" ${DIM}resets ${seven_day_reset}${RESET}"
  limits+=("$limit")
fi
if [ ${#limits[@]} -gt 0 ]; then
  joined=$(printf '%s | ' "${limits[@]}")
  printf '%s\n' "${joined% | }"
fi
