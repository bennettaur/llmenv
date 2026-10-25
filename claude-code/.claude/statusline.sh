#!/bin/bash

json=$(cat)

# One jq call for every field keeps the script fast. Fields are split on \x1f
# because tab is whitespace to `read`, which would collapse empty fields.
IFS=$'\x1f' read -r model dir usage_pct pr_number pr_url pr_state \
  five_pct five_reset week_pct week_reset < <(
  echo "$json" | jq -r '[
    .model.display_name // "unknown",
    .workspace.current_dir // .cwd // "",
    (.context_window.used_percentage // 0 | floor),
    .pr.number // "",
    .pr.url // "",
    .pr.review_state // "",
    (.rate_limits.five_hour.used_percentage // "" | if . == "" then . else floor end),
    .rate_limits.five_hour.resets_at // "",
    (.rate_limits.seven_day.used_percentage // "" | if . == "" then . else floor end),
    .rate_limits.seven_day.resets_at // ""
  ] | map(tostring) | join("\u001f")'
)

GREEN="\033[38;2;0;255;65m"
ORANGE="\033[38;2;255;165;0m"
RED="\033[38;2;255;100;100m"
CYAN="\033[38;2;0;206;200m"
WHITE="\033[97m"
DIM="\033[2m"
RESET="\033[0m"

# Prints the color for a percent: green below $2, orange below $3, red above.
color_for() {
  if [ "$1" -lt "$2" ]; then
    printf '%s' "$GREEN"
  elif [ "$1" -lt "$3" ]; then
    printf '%s' "$ORANGE"
  else
    printf '%s' "$RED"
  fi
}

# Formats epoch seconds with a date(1) format string, on macOS or GNU date.
format_epoch() {
  date -r "$1" "$2" 2>/dev/null || date -d "@$1" "$2" 2>/dev/null
}

# Get git branch, and where it sits in a gh-stack stack
branch="no git"
stack=""
if git_info=$(git -C "${dir:-.}" rev-parse --abbrev-ref HEAD --git-common-dir 2>/dev/null); then
  branch=$(sed -n 1p <<< "$git_info")
  common_dir=$(sed -n 2p <<< "$git_info")
  [[ "$common_dir" = /* ]] || common_dir="${dir:-.}/$common_dir"

  # Reads gh-stack's local file instead of running `gh stack`, so no network call.
  if [ -f "$common_dir/gh-stack" ]; then
    stack=$(jq -r --arg b "$branch" '
      .stacks[].branches | map(.branch) | index($b) as $i
      | select($i != null) | "\($i + 1)/\(length)"
    ' "$common_dir/gh-stack" 2>/dev/null | head -1)
  fi
fi

line="👤 $(color_for "$usage_pct" 25 50)${model} (${usage_pct}%)${RESET}"
line+=" | 📁 ${WHITE}${dir/#$HOME/~}${RESET}"
line+=" | 🌳 ${CYAN}${branch}${RESET}"
[ -n "$stack" ] && line+=" ${DIM}📚 ${stack}${RESET}"
if [ -n "$pr_number" ]; then
  # OSC 8 makes the PR number a clickable link.
  line+=" | 🔀 \033]8;;${pr_url}\a#${pr_number}\033]8;;\a"
  [ -n "$pr_state" ] && line+=" ${DIM}${pr_state//_/ }${RESET}"
fi
printf '%b\n' "$line"

# rate_limits is only sent to Pro/Max subscribers, after the first response.
limits=()
if [ -n "$five_pct" ]; then
  limits+=("⏳ 5h $(color_for "$five_pct" 50 80)${five_pct}%${RESET} ${DIM}resets $(format_epoch "$five_reset" '+%-I:%M%p')${RESET}")
fi
if [ -n "$week_pct" ]; then
  limits+=("📅 7d $(color_for "$week_pct" 50 80)${week_pct}%${RESET} ${DIM}resets $(format_epoch "$week_reset" '+%a %-I%p')${RESET}")
fi
if [ ${#limits[@]} -gt 0 ]; then
  joined=$(printf '%s | ' "${limits[@]}")
  printf '%b\n' "${joined% | }"
fi
