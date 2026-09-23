#!/usr/bin/env python3
"""
PreToolUse hook for Bash commands that run git.

Denies commands that skip git hooks (such as gitleaks): --no-verify and its
abbreviations, -n in a `git commit` or `git am` flag group, setting
core.hooksPath, and env vars that hook managers read to skip hooks. Asks
before force pushes, including forms the glob ask rules can't express, like
`git -C <path> push -uf`.

Glob permission rules can't express these without also matching commit
message text, so this parses the command instead. It guards against an agent
drifting into a bypass, not against deliberate obfuscation.
"""
import json
import os
import re
import shlex
import subprocess
import sys
from typing import NoReturn, Optional

CONTROL_CHARS = set(";&|()\n")

# Heredoc bodies are message text, not commands. Dropping them before lexing
# keeps quotes and flag-like words inside a message from being parsed.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|\)|$)", re.S)

# Words that can run the command after them.
COMMAND_PREFIXES = {
    "command", "builtin", "exec", "time", "nice", "nohup", "timeout", "xargs",
    "!", "{", "then", "do", "else", "if", "while", "until",
}
SHELLS = {"sh", "bash", "zsh"}
EXPORT_COMMANDS = {"export", "declare", "typeset", "local", "readonly"}

# Env vars hook managers read to skip hooks (pre-commit, husky, lefthook,
# overcommit), plus the git vars that can load config setting core.hooksPath.
HOOK_SKIP_ENV_VARS = {
    "SKIP", "HUSKY", "HUSKY_SKIP_HOOKS", "LEFTHOOK", "LEFTHOOK_EXCLUDE",
    "OVERCOMMIT_DISABLE", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
}

GIT_GLOBAL_OPTIONS_WITH_VALUE = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--config-env"}

# Subcommands where -n means --no-verify, with the short flags that take a
# separate value and the ones whose value is attached.
SHORT_NO_VERIFY_SUBCOMMANDS = {
    "commit": {"separate_value": set("mFCct"), "attached_value": set("Su")},
    "am": {"separate_value": set(), "attached_value": set("CpS")},
}
LONG_OPTIONS_WITH_VALUE = {
    "--message", "--file", "--reuse-message", "--reedit-message", "--template",
    "--author", "--date", "--fixup", "--squash", "--cleanup", "--trailer",
    "--pathspec-from-file", "--push-option", "--repo", "--receive-pack",
}
PUSH_SHORT_OPTIONS_WITH_VALUE = set("o")
GIT_BUILTINS_SEEN_OFTEN = {
    "add", "am", "branch", "checkout", "commit", "config", "diff", "fetch",
    "log", "merge", "pull", "push", "rebase", "reset", "rev-parse", "show",
    "stash", "status", "switch", "worktree",
}
CONFIG_READ_FLAGS = {
    "--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l",
    "--show-origin", "--show-scope", "--name-only", "get", "list",
}

# git accepts any unambiguous prefix of a long option. "--no-ver" is
# ambiguous with --no-verbose, so "--no-veri" is the shortest that works.
NO_VERIFY = "--no-verify"
SHORTEST_NO_VERIFY_PREFIX = len("--no-veri")


def split_simple_commands(command: str) -> list[list[str]]:
    """Split a shell command into the token lists of its simple commands."""
    command = HEREDOC.sub("<<HEREDOC", command)
    command = command.replace("\\\n", " ").replace("`", "\n")
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token and set(token) <= CONTROL_CHARS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def is_assignment(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token))


def is_no_verify(token: str) -> bool:
    option = token.split("=", 1)[0]
    return len(option) >= SHORTEST_NO_VERIFY_PREFIX and NO_VERIFY.startswith(option)


def short_flag_group_has(args: list[str], target: str, separate_value: set, attached_value: set) -> bool:
    """Return True if any short-flag group in args contains the target flag."""
    index = 0
    while index < len(args):
        token = args[index]
        index += 1
        if token == "--":
            return False
        if token.startswith("--"):
            if token in LONG_OPTIONS_WITH_VALUE:
                index += 1
            continue
        if not token.startswith("-") or token == "-":
            continue
        flags = token[1:]
        for position, flag in enumerate(flags):
            if flag == target:
                return True
            if flag in attached_value:
                break
            if flag in separate_value:
                if position == len(flags) - 1:
                    index += 1
                break
    return False


def has_long_no_verify(args: list[str]) -> bool:
    index = 0
    while index < len(args):
        token = args[index]
        index += 1
        if token == "--":
            return False
        if token in LONG_OPTIONS_WITH_VALUE or token in ("-m", "-F"):
            index += 1
        elif token.startswith("--") and is_no_verify(token):
            return True
    return False


def is_force_push(args: list[str]) -> bool:
    for token in args:
        if token == "--":
            return False
        if token.startswith("--force") or token == "--mirror":
            return True
        if not token.startswith("-") and token.startswith("+"):
            return True
    return short_flag_group_has(args, "f", PUSH_SHORT_OPTIONS_WITH_VALUE, set())


def sets_hooks_path_in_config(args: list[str]) -> bool:
    """Return True if `git config` args write core.hooksPath."""
    if CONFIG_READ_FLAGS.intersection(args):
        return False
    for position, token in enumerate(args):
        if token.lower() == "core.hookspath":
            return any(not later.startswith("-") for later in args[position + 1:])
    return False


def resolve_alias(subcommand: str) -> list[str]:
    """Expand a git alias such as `ci = commit` into its words."""
    # git ignores aliases that shadow built-in commands, so skip the lookup.
    if subcommand in GIT_BUILTINS_SEEN_OFTEN:
        return [subcommand]
    try:
        result = subprocess.run(
            ["git", "config", "--get", f"alias.{subcommand}"],
            capture_output=True, text=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return [subcommand]
    expansion = result.stdout.strip()
    if result.returncode != 0 or not expansion or expansion.startswith("!"):
        return [subcommand]
    return shlex.split(expansion)


def check_git_args(args: list[str]) -> Optional[tuple[str, str]]:
    """Return (decision, reason) for the arguments after `git`, or None."""
    subcommand_index = None
    index = 0
    while index < len(args):
        token = args[index]
        if token in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            if index + 1 < len(args) and "core.hookspath" in args[index + 1].lower():
                return "deny", "overrides core.hooksPath"
            index += 2
            continue
        if token.startswith(("-c", "--config-env")) and "core.hookspath" in token.lower():
            return "deny", "overrides core.hooksPath"
        if not token.startswith("-"):
            subcommand_index = index
            break
        index += 1
    if subcommand_index is None:
        return None

    words = resolve_alias(args[subcommand_index]) + args[subcommand_index + 1:]
    subcommand, subcommand_args = words[0], words[1:]

    if subcommand == "config" and sets_hooks_path_in_config(subcommand_args):
        return "deny", "sets core.hooksPath"
    if has_long_no_verify(subcommand_args):
        return "deny", f"uses --no-verify on git {subcommand}"
    short_flags = SHORT_NO_VERIFY_SUBCOMMANDS.get(subcommand)
    if short_flags and short_flag_group_has(subcommand_args, "n", **short_flags):
        return "deny", f"uses -n (--no-verify) on git {subcommand}"
    if subcommand == "push" and is_force_push(subcommand_args):
        return "ask", "force pushes"
    return None


def check_simple_command(tokens: list[str]) -> Optional[tuple[str, str]]:
    """Return (decision, reason) if this simple command skips hooks or force pushes."""
    env_names = []
    for position, token in enumerate(tokens):
        if is_assignment(token):
            env_names.append(token.split("=", 1)[0])
            continue
        if token in COMMAND_PREFIXES or token.startswith("-") or token.isdigit():
            continue
        if os.path.basename(token) in SHELLS and position + 2 < len(tokens) and tokens[position + 1] == "-c":
            return check_command(tokens[position + 2])
        if os.path.basename(token) == "git":
            skip_vars = HOOK_SKIP_ENV_VARS.intersection(env_names)
            if skip_vars:
                return "deny", f"sets {', '.join(sorted(skip_vars))}, which skips git hooks"
            return check_git_args(tokens[position + 1:])
        if token in EXPORT_COMMANDS:
            exported = {arg.split("=", 1)[0] for arg in tokens[position + 1:]}
            skip_vars = HOOK_SKIP_ENV_VARS.intersection(exported)
            if skip_vars:
                return "deny", f"exports {', '.join(sorted(skip_vars))}, which skips git hooks"
        return None
    return None


def check_command(command: str) -> Optional[tuple[str, str]]:
    """Return the strictest (decision, reason) across all simple commands."""
    result = None
    for tokens in split_simple_commands(command):
        decision = check_simple_command(tokens)
        if decision and decision[0] == "deny":
            return decision
        result = result or decision
    return result


def emit_decision(decision: str, reason: str) -> NoReturn:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    command = input_data.get("tool_input", {}).get("command", "")
    if input_data.get("tool_name") != "Bash" or "git" not in command:
        sys.exit(0)

    try:
        result = check_command(command)
    except Exception:
        # A parse failure could hide a bypass, so don't let it through silently.
        emit_decision("ask", "Couldn't parse this git command to check for skipped hooks")

    if result:
        decision, reason = result
        if decision == "deny":
            emit_decision("deny", f"Blocked: this git command {reason}. Fix the hook failure instead of skipping it.")
        emit_decision("ask", f"This git command {reason}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
