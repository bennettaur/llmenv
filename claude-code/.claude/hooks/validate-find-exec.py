#!/usr/bin/env python3
"""
PreToolUse hook for Bash(find:*) commands.
Checks if the find command uses exec options (-exec, -execdir, -ok, -okdir).
If detected, asks for user permission. Otherwise, auto-approves.
"""
import json
import re
import sys


def has_exec_option(command: str) -> bool:
    """
    Check if a find command uses any exec-related options.

    Returns True if command contains:
    - -exec
    - -execdir
    - -ok
    - -okdir
    """
    # Match exec options as separate arguments (with word boundaries)
    exec_pattern = r'\s-(?:exec(?:dir)?|ok(?:dir)?)\s'
    return bool(re.search(exec_pattern, command))


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only process Bash tool calls with find commands
    if tool_name != "Bash" or not command or "find" not in command:
        # Let normal permission flow proceed
        sys.exit(0)

    # Check if the find command uses exec options
    if has_exec_option(command):
        # Ask user for permission
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Find command uses exec option (-exec/-execdir/-ok/-okdir) which can execute arbitrary commands"
            }
        }
    else:
        # Auto-approve find commands without exec
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Find command without exec options auto-approved"
            },
            "suppressOutput": True  # Don't clutter verbose mode
        }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
