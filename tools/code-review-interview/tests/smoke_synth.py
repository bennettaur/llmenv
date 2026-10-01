"""Smoke test for the synthesis step, on a small hand-built transcript.

    uv run python tests/smoke_synth.py

Named `smoke_*` so a plain `pytest` run does not collect it.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from code_review_interview.cli import prepare_env
from code_review_interview.synthesize import REQUIRED_HEADINGS, synthesize
from code_review_interview.transcript import Transcript
from code_review_interview.tui import InterviewUI

QA = [
    (
        "Walk me through the last PR you reviewed properly. What did you open first?",
        (
            "Tests first, always. If the tests don't describe the behaviour change I stop "
            "and ask before reading the implementation. Then the diff of the core module, "
            "then config and migrations last."
        ),
    ),
    (
        "What do you deliberately not comment on?",
        (
            "Formatting, import order, anything a linter owns. Naming too, unless the name "
            "is actively misleading — those cost the next reader an hour."
        ),
    ),
    (
        "What has burned you that is now a standing check?",
        (
            "An N+1 in a loop that only showed up at 10k rows. Any query inside a loop now "
            "gets read twice. Also unbounded retries without a jitter."
        ),
    ),
    (
        "What would you want an LLM reviewer to hand you?",
        (
            "A ranked list, worst first, each with the file and line and a one-line failure "
            "scenario. No praise, no summary of what the PR does — I read the PR."
        ),
    ),
]


async def main() -> int:
    ui = InterviewUI()
    prepare_env(allow_api_key=False, ui=ui)

    tmp = Path(tempfile.mkdtemp())
    transcript = Transcript.load_or_create(tmp / "synth.json")
    for number in (1, 2, 3):
        transcript.start_round(number)
        for question, answer in QA:
            entry = transcript.add_question(number, question, None)
            transcript.record_answer(entry, answer)
        transcript.complete_round(number, f"round {number} notes")

    out = await synthesize(transcript, tmp / "style.md", ui)
    text = out.read_text(encoding="utf-8")
    print(text[:1200])
    print("...")

    missing = [h for h in REQUIRED_HEADINGS if h not in text]
    ok = len(text) > 800 and not missing
    print(f"\nwrote {out} ({len(text)} chars), missing sections: {missing or 'none'}")
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
