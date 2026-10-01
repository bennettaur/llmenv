"""Runs one interview round against a Claude Agent SDK session.

The interviewer agent has no built-in tools. Its only way to act is the
in-process MCP server defined here, which is what enforces the round rules:
`ask_question` returns the answer text only in rounds configured with
`reveal_answers`, and returns a bare acknowledgement otherwise. The rules are
also stated in the prompt, but the prompt is not what holds them.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolAnnotations,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)

from .isolation import agent_options
from .prompts import RoundConfig, kickoff_prompt, resume_note
from .transcript import Transcript, new_nonce
from .tui import InterviewUI

SERVER_NAME = "interview"
ASK_TOOL = f"mcp__{SERVER_NAME}__ask_question"
FINISH_TOOL = f"mcp__{SERVER_NAME}__finish_round"
INTERVIEW_TOOLS = frozenset({ASK_TOOL, FINISH_TOOL})

ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question to put to the interviewee, verbatim.",
        },
        "context": {
            "type": "string",
            "description": (
                "Optional single sentence of framing shown above the question. "
                "Omit unless the question needs it."
            ),
        },
    },
    "required": ["question"],
}

FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "What this round covered and what you think is still unknown. "
                "Recorded in the transcript and shown to the next round."
            ),
        }
    },
    "required": ["summary"],
}

# How many times we prod an agent that stopped early without finishing.
MAX_NUDGES = 3
# Rejected calls return instantly with no human in the loop, so a stuck agent
# can spin. Past this many in a row we stop the round ourselves.
MAX_REJECTIONS = 3


def overrun_allowance(target: int) -> int:
    """Slack past the target before `ask_question` forces a wrap-up.

    A third over target: enough that a genuinely uncovered area can still be
    reached, tight enough that a blind agent — which has no answers to tell it
    when it has enough — cannot double the interview's length.
    """
    return max(2, round(target * 0.35))


def _progress(asked: int, target: int, hard_cap: int) -> str:
    """Progress line the agent sees after each answer, with a wrap-up cue."""
    if asked < target:
        return f"{asked} of ~{target} asked"
    if asked < hard_cap:
        return (
            f"{asked} asked — you have reached the target of ~{target}. Call "
            "finish_round unless a genuinely important area is still uncovered; "
            f"the hard limit is {hard_cap}"
        )
    return f"{asked} asked — hard limit reached. Call finish_round now"


def _tool_result(message: str, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": message}]}
    if is_error:
        result["is_error"] = True
    return result


@dataclass
class RoundState:
    """Live state of one round.

    The three ways a round can end are deliberately distinct: `finished` means
    the agent called finish_round, `stop_requested` means the interviewee typed
    /stop, and `interrupted` means something aborted the answer prompt. Only
    the first two mean the round is done — an interrupted round stays
    resumable.
    """

    asked: int = 0
    finished: bool = False
    stop_requested: bool = False
    interrupted: bool = False
    rejections: int = 0
    summary: str | None = None

    @property
    def should_stop(self) -> bool:
        return self.finished or self.stop_requested or self.interrupted


class RoundRunner:
    def __init__(
        self,
        transcript: Transcript,
        ui: InterviewUI,
        config: RoundConfig,
        model: str | None = None,
    ) -> None:
        self.transcript = transcript
        self.ui = ui
        self.config = config
        self.model = model
        self.state = RoundState()
        self.hard_cap = config.target_questions + overrun_allowance(config.target_questions)
        # One question on screen at a time. The SDK dispatches each tool call as
        # its own task, so two tool_use blocks in one turn would otherwise re-enter
        # prompt_toolkit and trip its "Application is already running" assert.
        self._ask_lock = asyncio.Lock()
        self.tools: dict[str, Any] = {}

    # --- tools ------------------------------------------------------------

    def _build_server(self) -> Any:
        @tool(
            "ask_question",
            (
                "Put one question to the interviewee and wait for their answer. "
                "Blocks until they respond, which can take several minutes. "
                "Ask exactly one question per call."
            ),
            ASK_SCHEMA,
            annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False),
        )
        async def ask_question(args: dict[str, Any]) -> dict[str, Any]:
            refusal = self._refuse_ask()
            if refusal is not None:
                return refusal

            question = (args.get("question") or "").strip()
            if not question:
                return self._reject("`question` was empty. Send the question text.")
            context = (args.get("context") or "").strip() or None

            if self._ask_lock.locked():
                return self._reject(
                    "A question is already open and waiting for an answer. Ask one "
                    "at a time; wait for this result before calling again."
                )

            async with self._ask_lock:
                return await self._ask(question, context)

        @tool(
            "finish_round",
            "End the round. Call this once, when you have no more questions to ask.",
            FINISH_SCHEMA,
            annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
        )
        async def finish_round(args: dict[str, Any]) -> dict[str, Any]:
            if self.state.finished:
                return _tool_result("This round is already closed. Stop.", is_error=True)
            self.state.finished = True
            self.state.summary = (args.get("summary") or "").strip() or None
            return _tool_result("Round closed. Stop here — do not ask further questions.")

        self.tools = {"ask_question": ask_question, "finish_round": finish_round}
        return create_sdk_mcp_server(
            name=SERVER_NAME,
            version="1.0.0",
            tools=[ask_question, finish_round],
        )

    def _reject(self, message: str) -> dict[str, Any]:
        self.state.rejections += 1
        if self.state.rejections >= MAX_REJECTIONS:
            self.state.interrupted = True
            return _tool_result(
                f"{message} Too many rejected calls; the round is being ended.",
                is_error=True,
            )
        return _tool_result(message, is_error=True)

    def _refuse_ask(self) -> dict[str, Any] | None:
        """Reasons the agent may not ask anything else."""
        if self.state.finished:
            return self._reject("This round is closed. Stop — do not ask further questions.")
        if self.state.stop_requested or self.state.interrupted:
            return self._reject("The interviewee has ended this round. Call finish_round now.")
        if self.state.asked >= self.hard_cap:
            return self._reject(
                f"Question limit for this round reached ({self.hard_cap}). "
                "Call finish_round now."
            )
        return None

    async def _ask(self, question: str, context: str | None) -> dict[str, Any]:
        entry = self.transcript.add_question(self.config.number, question, context)
        self.state.asked += 1
        self.ui.question(
            self.config.number,
            entry.index,
            self.config.target_questions,
            question,
            context,
        )

        try:
            answer = await self.ui.collect_answer()
        except KeyboardInterrupt:
            self._abandon(entry)
            self.state.interrupted = True
            return _tool_result(
                "The interviewee interrupted the session. Call finish_round now "
                "with a summary of what you covered.",
                is_error=True,
            )
        # Deliberately broad: whatever broke the prompt, the entry must not be
        # left in the transcript as a question that was never answered.
        except Exception as exc:  # noqa: BLE001
            self._abandon(entry)
            self.state.interrupted = True
            self.ui.error(f"Answer prompt failed: {exc}")
            return _tool_result(
                f"The answer prompt failed ({exc}). Call finish_round now.", is_error=True
            )

        if answer.stop_round:
            self._abandon(entry)
            self.state.stop_requested = True
            return _tool_result(
                "The interviewee asked to end the round here. Call finish_round "
                "now with a summary of what you covered and what is still unknown."
            )

        self.state.rejections = 0
        progress = _progress(self.state.asked, self.config.target_questions, self.hard_cap)

        if answer.skipped:
            self.transcript.record_answer(entry, None, skipped=True)
            self.ui.info("Skipped.")
            return _tool_result(
                f"The interviewee skipped that question ({progress}). Move on; do "
                "not rephrase and re-ask it."
            )

        self.transcript.record_answer(entry, answer.text)
        if self.config.reveal_answers:
            self.ui.info("Recorded — the interviewer can see this answer.")
            return _tool_result(f"Answer to Q{entry.index} ({progress}):\n\n{answer.text}")

        self.ui.info("Recorded — withheld from the interviewer this round.")
        return _tool_result(
            f"Answer recorded ({progress}). Its content is withheld from you this "
            "round by design. Ask your next question."
        )

    def _abandon(self, entry: Any) -> None:
        self.transcript.drop_entry(self.config.number, entry)
        self.state.asked -= 1

    # --- session ----------------------------------------------------------

    def options(self) -> ClaudeAgentOptions:
        return agent_options(
            system_prompt=self.config.system_prompt(),
            allowed_tools=INTERVIEW_TOOLS,
            model=self.model,
            mcp_servers={SERVER_NAME: self._build_server()},
            # A rejected ask returns instantly, so an agent ignoring the refusal
            # could loop within one turn. This is the backstop under MAX_REJECTIONS.
            max_turns=self.hard_cap * 2 + 8,
        )

    async def run(self) -> RoundState:
        rnd = self.transcript.start_round(self.config.number)
        already_asked = [e.question for e in rnd.entries]
        self.state.asked = len(rnd.entries)

        prompt = kickoff_prompt(
            self.config,
            self.transcript.render_rounds(list(self.config.prior_rounds), new_nonce()),
        )
        if already_asked:
            prompt = f"{prompt}\n\n{resume_note(already_asked)}"

        async with ClaudeSDKClient(options=self.options()) as client:
            await client.query(prompt)
            nudges = 0
            while True:
                await self._drain(client)

                if self.state.should_stop or self.state.asked >= self.hard_cap:
                    break
                if nudges >= MAX_NUDGES:
                    self.ui.warn(
                        "The interviewer stopped without closing the round. Leaving "
                        "the round open — re-run to resume it."
                    )
                    break

                nudges += 1
                await client.query(
                    f"You have asked {self.state.asked} of about "
                    f"{self.config.target_questions} questions and have not called "
                    "finish_round. If you have more ground to cover, ask the next "
                    "question now with ask_question. If you are genuinely done, call "
                    "finish_round."
                )

        # An interrupted round, or one the agent abandoned, stays in_progress so
        # `run` picks it up again. Only a closed or explicitly stopped round is done.
        if (
            self.state.finished
            or self.state.stop_requested
            or self.state.asked >= self.hard_cap
        ):
            self.transcript.complete_round(self.config.number, self.state.summary)
        return self.state

    async def _drain(self, client: ClaudeSDKClient) -> None:
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        self.ui.agent_text(block.text)
                    elif isinstance(block, ToolUseBlock) and block.name not in INTERVIEW_TOOLS:
                        self.ui.info(f"(interviewer tried {block.name}; denied)")
            elif isinstance(message, ResultMessage) and message.subtype != "success":
                self.ui.warn(f"Interviewer turn ended: {message.subtype}")
