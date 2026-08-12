"""Terminal UI: renders questions, collects answers."""

from __future__ import annotations

import asyncio
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

SUBMIT_SENTINEL = "."

# Typed on a line of their own, these submit immediately — no Esc+Enter needed.
STOP_COMMANDS = {"/stop", "/done", "/end"}
COMMANDS = STOP_COMMANDS | {"/skip", "/edit", "/help"}

HELP = (
    "Esc then Enter (or a line containing only '.') submits · "
    "/edit opens $EDITOR · /skip skips · /stop ends the round"
)


@dataclass
class Answer:
    """What the interviewee did with a question."""

    text: str | None = None
    skipped: bool = False
    stop_round: bool = False


def _build_keybindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event) -> None:
        buffer = event.current_buffer
        current = buffer.document.current_line
        if buffer.text.strip().lower() in COMMANDS:
            # A command on its own submits straight away.
            buffer.validate_and_handle()
        elif current.strip() == SUBMIT_SENTINEL:
            # Drop the sentinel line, then submit what came before it.
            buffer.delete_before_cursor(len(current))
            buffer.validate_and_handle()
        else:
            buffer.insert_text("\n")

    return kb


async def _edit_in_editor() -> str:
    """Open $VISUAL/$EDITOR on a scratch file and return what was written.

    Uses create_subprocess_exec rather than a thread so a Ctrl-C while the
    editor is open can actually cancel; a thread would pin the event loop until
    the editor exited. The whole directory goes away afterwards, which also
    takes editor sidecars (vim .swp, backups~) with it.
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    directory = Path(tempfile.mkdtemp(prefix="code-review-interview-answer-"))
    path = directory / "answer.md"
    path.touch()
    try:
        # shlex.split so EDITOR="code -w" and quoted paths both work.
        process = await asyncio.create_subprocess_exec(*shlex.split(editor), str(path))
        await process.wait()
        return path.read_text(encoding="utf-8")
    finally:
        for leftover in directory.iterdir():
            leftover.unlink(missing_ok=True)
        directory.rmdir()


class InterviewUI:
    def __init__(
        self,
        show_agent_text: bool = True,
        pt_input=None,
        pt_output=None,
    ) -> None:
        self.console = Console()
        self.show_agent_text = show_agent_text
        # Injected only by the tests, which drive prompt_toolkit over a pipe.
        self._pt_input = pt_input
        self._pt_output = pt_output
        self._session: PromptSession | None = None
        self._confirm_session: PromptSession | None = None

    # --- output -----------------------------------------------------------

    def rule(self, title: str) -> None:
        self.console.print(Rule(title, style="cyan"))

    def info(self, message: str) -> None:
        self.console.print(f"[dim]{message}[/dim]")

    def warn(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/yellow]")

    def error(self, message: str) -> None:
        self.console.print(f"[red]{message}[/red]")

    def round_banner(self, number: int, title: str, blurb: str) -> None:
        self.console.print()
        self.console.print(
            Panel(
                Text(blurb, style="white"),
                title=f"[bold cyan]Round {number} — {title}[/bold cyan]",
                border_style="cyan",
            )
        )

    def agent_text(self, text: str) -> None:
        text = text.strip()
        if not text or not self.show_agent_text:
            return
        self.console.print(f"[dim italic]interviewer: {text}[/dim italic]")

    def question(
        self, number: int, index: int, target: int, question: str, context: str | None
    ) -> None:
        header = f"[bold]Round {number} · question {index}[/bold]"
        if index <= target:
            header += f" [dim]of ~{target}[/dim]"
        body = Text()
        if context:
            body.append(context.strip() + "\n\n", style="dim")
        body.append(question.strip(), style="bold white")
        self.console.print()
        self.console.print(Panel(body, title=header, border_style="green", padding=(1, 2)))

    def markdown(self, text: str) -> None:
        self.console.print(Markdown(text))

    # --- input ------------------------------------------------------------

    def _session_kwargs(self) -> dict:
        kwargs: dict = {}
        if self._pt_input is not None:
            kwargs["input"] = self._pt_input
        if self._pt_output is not None:
            kwargs["output"] = self._pt_output
        return kwargs

    def _get_session(self) -> PromptSession:
        if self._session is None:
            self._session = PromptSession(
                multiline=True,
                key_bindings=_build_keybindings(),
                bottom_toolbar=HTML(f"<b>{HELP}</b>"),
                **self._session_kwargs(),
            )
        return self._session

    async def collect_answer(self) -> Answer:
        """Prompt until the interviewee submits, skips, or stops the round."""
        session = self._get_session()
        while True:
            try:
                raw = await session.prompt_async(
                    HTML("<ansigreen>your answer &gt; </ansigreen>")
                )
            except EOFError:
                return Answer(stop_round=True)

            stripped = raw.strip()
            command = stripped.lower()

            if command == "/skip":
                return Answer(skipped=True)
            if command in STOP_COMMANDS:
                return Answer(stop_round=True)
            if command == "/edit":
                try:
                    text = (await _edit_in_editor()).strip()
                except OSError as exc:
                    self.warn(f"Could not run your editor ({exc}). Type the answer here.")
                    continue
                if not text:
                    self.warn("Editor came back empty — nothing recorded, try again.")
                    continue
                return Answer(text=text)
            if command == "/help":
                self.info(HELP)
                continue
            if not stripped:
                self.warn("Empty answer. Type something, or /skip to move on.")
                continue

            return Answer(text=raw.rstrip())

    async def confirm(self, question: str, default: bool = True) -> bool:
        if self._confirm_session is None:
            self._confirm_session = PromptSession(**self._session_kwargs())
        suffix = "[Y/n]" if default else "[y/N]"
        try:
            raw = await self._confirm_session.prompt_async(f"{question} {suffix} ")
        except EOFError:
            return default
        raw = raw.strip().lower()
        if not raw:
            return default
        return raw.startswith("y")
