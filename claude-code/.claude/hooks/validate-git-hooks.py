#!/usr/bin/env python3
"""
PreToolUse hook for Bash commands that run git.
Denies commands that skip git hooks (such as gitleaks): --no-verify and its
abbreviations, -n in any `git commit` flag group, overriding core.hooksPath,
and env vars that hook managers read to skip hooks.
Glob permission rules can't express these without also matching commit
message text, so this parses the command instead.
"""
import json
import os
import shlex
import sys

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}
HEREDOC_MARKERS = {"<<", "<<-"}

# pre-commit reads SKIP, husky reads HUSKY, lefthook reads LEFTHOOK; the
# GIT_CONFIG_* vars can set core.hooksPath without it appearing in argv.
HOOK_SKIP_ENV_VARS = {"SKIP", "HUSKY", "LEFTHOOK", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}

# git options that consume the following token, so it isn't read as a flag.
GIT_GLOBAL_OPTIONS_WITH_VALUE = {"-c", "-C", "--git-dir", "--work-tree", "--namespace"}
COMMIT_SHORT_OPTIONS_WITH_VALUE = set("mFCct")
COMMIT_SHORT_OPTIONS_WITH_ATTACHED_VALUE = set("Su")
COMMIT_LONG_OPTIONS_WITH_VALUE = {
    "--message", "--file", "--reuse-message", "--reedit-message", "--template",
    "--author", "--date", "--fixup", "--squash", "--cleanup", "--trailer",
    "--pathspec-from-file",
}

# git accepts any unambiguous prefix of a long option. "--no-ver" is
# ambiguous with --no-verbose, so "--no-veri" is the shortest that works.
NO_VERIFY = "--no-verify"
SHORTEST_NO_VERIFY_PREFIX = len("--no-veri")


def split_simple_commands(command):
    """Split a shell command into the token lists of its simple commands."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token in SEPARATORS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def is_no_verify(token):
    option = token.split("=", 1)[0]
    return len(option) >= SHORTEST_NO_VERIFY_PREFIX and NO_VERIFY.startswith(option)


def commit_skips_hooks(args):
    """Return True if `git commit` args include -n or --no-verify."""
    index = 0
    while index < len(args):
        token = args[index]
        index += 1
        if token == "--" or token in HEREDOC_MARKERS:
            return False
        if token.startswith("--"):
            if is_no_verify(token):
                return True
            if token in COMMIT_LONG_OPTIONS_WITH_VALUE:
                index += 1
            continue
        if not token.startswith("-") or token == "-":
            continue
        flags = token[1:]
        for position, flag in enumerate(flags):
            if flag == "n":
                return True
            if flag in COMMIT_SHORT_OPTIONS_WITH_ATTACHED_VALUE:
                break
            if flag in COMMIT_SHORT_OPTIONS_WITH_VALUE:
                if position == len(flags) - 1:
                    index += 1
                break
    return False


def find_hook_bypass(tokens):
    """Return a reason if this simple command skips git hooks, else None."""
    env_names = []
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        env_names.append(tokens[0].split("=", 1)[0])
        tokens = tokens[1:]
    if tokens and tokens[0] == "command":
        tokens = tokens[1:]
    if not tokens or os.path.basename(tokens[0]) != "git":
        return None

    skip_vars = HOOK_SKIP_ENV_VARS.intersection(env_names)
    if skip_vars:
        return f"sets {', '.join(sorted(skip_vars))}, which skips git hooks"

    args = tokens[1:]
    for token in args:
        if token in HEREDOC_MARKERS:
            break
        if "core.hookspath" in token.lower():
            return "overrides core.hooksPath"

    subcommand, subcommand_args = None, []
    index = 0
    while index < len(args):
        token = args[index]
        if token in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if not token.startswith("-"):
            subcommand = token
            subcommand_args = args[index + 1:]
            break
        index += 1

    if subcommand is None:
        return None
    if subcommand == "commit":
        if commit_skips_hooks(subcommand_args):
            return "uses -n or --no-verify, which skips commit hooks"
        return None
    for token in subcommand_args:
        if token in HEREDOC_MARKERS or token == "--":
            break
        if token.startswith("--") and is_no_verify(token):
            return f"uses --no-verify on git {subcommand}, which skips hooks"
    return None


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Blocked: this git command {reason}. Fix the hook failure instead of skipping it.",
        }
    }))
    sys.exit(0)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    command = input_data.get("tool_input", {}).get("command", "")
    if input_data.get("tool_name") != "Bash" or "git" not in command:
        sys.exit(0)

    try:
        simple_commands = split_simple_commands(command)
    except ValueError:
        # Unparseable quoting could hide a bypass, so don't let it through silently.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Couldn't parse this git command to check for skipped hooks",
            }
        }))
        sys.exit(0)

    for tokens in simple_commands:
        reason = find_hook_bypass(tokens)
        if reason:
            deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
