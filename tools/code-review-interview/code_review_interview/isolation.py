"""Agent isolation, shared by the interview rounds and the synthesis pass.

Both agents see the interviewee's raw words, so both get the same posture:
no built-in tools, no filesystem settings, no ambient MCP servers, and a
scratch working directory. This lives in one place so the two entry points
cannot drift apart.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
)

Gate = Callable[[str, dict[str, Any], Any], Awaitable[Any]]


@functools.cache
def isolated_cwd() -> str:
    """A scratch directory to run agents in, removed when the process exits."""
    path = tempfile.mkdtemp(prefix="code-review-interview-")
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path


def make_gate(allowed: frozenset[str]) -> Gate:
    """Deny every tool call except the named ones.

    This is the only approval path: `allowed_tools` is deliberately left unset,
    because a bare name there auto-approves *before* the callback runs, which
    would make this gate unreachable and emit a shadowing warning mid-TUI.
    """

    async def gate(tool_name: str, input_data: dict[str, Any], context: Any) -> Any:
        if tool_name in allowed:
            return PermissionResultAllow(updated_input=input_data)
        return PermissionResultDeny(
            message=(
                f"{tool_name} is not available in this interview. "
                f"Use only: {', '.join(sorted(allowed))}."
            )
        )

    return gate


def agent_options(
    *,
    system_prompt: str,
    allowed_tools: frozenset[str] = frozenset(),
    model: str | None = None,
    **extra: Any,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        # tools=[] removes every built-in. This is a security control, not
        # tidiness: it is what stops the agent reading the transcript file and
        # seeing the answers the blind rounds withhold from it.
        tools=[],
        can_use_tool=make_gate(allowed_tools),
        # Keep the agent clean: no CLAUDE.md, no project settings, no MCP
        # servers from user or plugin config, and a cwd with nothing in it.
        setting_sources=[],
        strict_mcp_config=True,
        cwd=isolated_cwd(),
        **extra,
    )
