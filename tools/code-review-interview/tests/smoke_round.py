"""End-to-end smoke test: runs a tiny real round with scripted answers.

Hits the live API through your Claude subscription. Usage:

    uv run python tests/smoke_round.py [round_number]

Named `smoke_*` so a plain `pytest` run does not collect it.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from code_review_interview.cli import prepare_env
from code_review_interview.prompts import default_rounds
from code_review_interview.runner import RoundRunner
from code_review_interview.transcript import Transcript
from code_review_interview.tui import Answer, InterviewUI

CANNED = [
    (
        "I read the tests first. If the tests don't describe the behaviour change, "
        "I stop and ask before reading the implementation."
    ),
    (
        "Naming. I let it go unless the name is actively misleading about what the "
        "thing does — misleading names cost the next reader an hour."
    ),
    (
        "Once shipped an N+1 in a loop that only showed up at 10k rows. Now I always "
        "check any query inside a loop."
    ),
]


class ScriptedUI(InterviewUI):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.tool_results: list[str] = []

    async def collect_answer(self) -> Answer:
        answer = CANNED[self.calls % len(CANNED)]
        self.calls += 1
        self.console.print(f"[magenta]<scripted answer {self.calls}>[/magenta] {answer}")
        return Answer(text=answer)


class SpyRunner(RoundRunner):
    """Records what the tool handed back, so the live run checks the blind
    contract itself rather than only the wiring around it."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.returned: list[str] = []

    async def _ask(self, question: str, context: str | None) -> dict:
        result = await super()._ask(question, context)
        self.returned.append(result["content"][0]["text"])
        return result


async def main() -> int:
    number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ui = ScriptedUI()
    prepare_env(allow_api_key=False, ui=ui)

    tmp = Path(tempfile.mkdtemp()) / "smoke.json"
    transcript = Transcript.load_or_create(tmp)

    # Seed earlier rounds so rounds 2 and 3 have prior context to read.
    for earlier in range(1, number):
        transcript.start_round(earlier)
        for text in CANNED[:2]:
            entry = transcript.add_question(earlier, f"[seed] {text[:40]}?", None)
            transcript.record_answer(entry, text)
        transcript.complete_round(earlier, "seeded")

    config = default_rounds((2, 2, 2))[number - 1]
    ui.round_banner(config.number, config.title, config.blurb)

    runner = SpyRunner(transcript, ui, config, model=None)
    state = await runner.run()

    rnd = transcript.round(number)
    answers_on_disk = [e.answer for e in rnd.answered_entries]
    handed_back = "\n".join(runner.returned)
    leaked = any(answer in handed_back for answer in CANNED)

    print()
    print(f"asked={state.asked} finished={state.finished} answers={len(answers_on_disk)}")
    print(f"round status={rnd.status}")
    print(f"answer text visible to the interviewer: {leaked}")
    print(f"summary={state.summary!r}")
    print(f"transcript={tmp}")

    ok = state.finished and len(answers_on_disk) >= 2 and leaked is config.reveal_answers
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
