"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .prompts import DEFAULT_TARGETS, default_rounds
from .runner import RoundRunner
from .synthesize import synthesize
from .transcript import COMPLETE, Transcript
from .tui import InterviewUI

DEFAULT_TRANSCRIPT = Path("code-review-interview.json")
DEFAULT_OUTPUT = Path("code-review-style.md")

_HOUR_MS = 60 * 60 * 1000
_MINUTE_MS = 60 * 1000

# An answer blocks the tool call for as long as the interviewee takes to type
# it, which the CLI's default MCP tool timeout does not allow for. Four hours
# covers any real answer while still letting a forgotten session die.
TIMEOUT_ENV = {
    "MCP_TOOL_TIMEOUT": str(4 * _HOUR_MS),
    "MCP_TIMEOUT": str(_MINUTE_MS),
}


def prepare_env(allow_api_key: bool, ui: InterviewUI) -> None:
    for name, value in TIMEOUT_ENV.items():
        os.environ.setdefault(name, value)

    if allow_api_key:
        return
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        if os.environ.pop(name, None) is not None:
            ui.warn(
                f"Unset {name} for this run so the interview bills against your "
                "Claude subscription. Pass --allow-api-key to keep it."
            )


def _parse_targets(raw: str) -> tuple[int, int, int]:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 3 or not all(p.isdigit() and int(p) > 0 for p in parts):
        raise argparse.ArgumentTypeError(
            "expected three comma-separated positive integers, e.g. 18,12,10"
        )
    return int(parts[0]), int(parts[1]), int(parts[2])


def _load(path: Path) -> Transcript:
    try:
        return Transcript.load(path)
    except FileNotFoundError:
        raise SystemExit(f"error: no transcript at {path} — run the interview first")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {path} is not valid JSON ({exc})")
    except TypeError as exc:
        raise SystemExit(f"error: {path} has unexpected fields ({exc})")
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")


def prepare_round(transcript: Transcript, number: int, force: bool, ui: InterviewUI) -> bool:
    """Decide whether to run a round, resetting or resuming it as needed.

    Returns False when the round should be skipped.
    """
    rnd = transcript.round(number)
    if rnd.status == COMPLETE:
        if not force:
            ui.info(f"Round {number} is already complete — skipping.")
            return False
        ui.warn(f"--force: discarding round {number} and starting it over.")
        transcript.reset_round(number)
        return True
    if rnd.entries:
        ui.info(f"Resuming round {number} ({len(rnd.entries)} questions already asked).")
    return True


async def _run(args: argparse.Namespace) -> int:
    ui = InterviewUI(show_agent_text=not args.quiet_agent)
    prepare_env(args.allow_api_key, ui)

    transcript = (
        _load(args.transcript)
        if args.transcript.exists()
        else Transcript.load_or_create(args.transcript)
    )
    configs = {c.number: c for c in default_rounds(args.questions)}

    if args.round:
        rounds_to_run = [args.round]
    else:
        rounds_to_run = transcript.unfinished_rounds()
        if not rounds_to_run:
            ui.info("All three rounds are already complete.")
            ui.info(f"Run `code-review-interview synthesize -t {args.transcript}` next.")
            return 0

    for number in rounds_to_run:
        config = configs[number]
        if not prepare_round(transcript, number, force=args.force, ui=ui):
            continue
        rnd = transcript.round(number)

        ui.round_banner(number, config.title, config.blurb)
        state = await RoundRunner(transcript, ui, config, args.model).run()

        ui.rule(f"Round {number} ended — {len(rnd.answered_entries)} answers recorded")
        if state.summary:
            ui.info(f"Interviewer's note: {state.summary}")
        ui.info(f"Saved to {transcript.path}")

        if state.interrupted:
            # The round is still in progress. Moving on would run the rounds out
            # of order, which is the one thing the phasing exists to prevent.
            ui.warn(
                f"Round {number} was interrupted and is unfinished. Resume it with "
                f"`code-review-interview run -t {args.transcript}`."
            )
            return 0

        remaining = [n for n in rounds_to_run if n > number]
        if remaining and not await ui.confirm(f"Continue to round {remaining[0]}?"):
            ui.info(
                f"Stopped. Resume later with `code-review-interview run -t {args.transcript}`."
            )
            return 0

    if not transcript.unfinished_rounds() and await ui.confirm(
        "All rounds done. Write the Code Review Style doc now?"
    ):
        path = await synthesize(transcript, args.output, ui, args.model)
        ui.rule(f"Wrote {path}")
    return 0


async def _synthesize(args: argparse.Namespace) -> int:
    ui = InterviewUI()
    prepare_env(args.allow_api_key, ui)
    transcript = _load(args.transcript)
    incomplete = transcript.unfinished_rounds()
    if incomplete and not args.force:
        ui.error(f"Rounds {incomplete} are not finished. Pass --force to synthesize anyway.")
        return 1
    path = await synthesize(transcript, args.output, ui, args.model)
    ui.rule(f"Wrote {path}")
    return 0


def _show(args: argparse.Namespace) -> int:
    ui = InterviewUI()
    transcript = _load(args.transcript)
    for rnd in transcript.rounds:
        answered = len(rnd.answered_entries)
        ui.rule(f"Round {rnd.number} — {rnd.status} — {answered} answered")
        if rnd.summary:
            ui.info(f"Interviewer's note: {rnd.summary}")
    if args.full:
        for rnd in transcript.rounds:
            for entry in rnd.entries:
                ui.markdown(f"**R{rnd.number} Q{entry.index}. {entry.question}**")
                if entry.skipped:
                    ui.info("(skipped)")
                elif entry.answer:
                    ui.markdown(entry.answer)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-review-interview",
        description=(
            "Interview yourself about how you review code, in three phases, then "
            "generate a Code Review Style doc for other LLMs to follow."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-t",
            "--transcript",
            type=Path,
            default=DEFAULT_TRANSCRIPT,
            help=f"transcript file (default: {DEFAULT_TRANSCRIPT})",
        )

    run = sub.add_parser("run", help="run the interview (resumes where it left off)")
    common(run)
    run.add_argument("-r", "--round", type=int, choices=(1, 2, 3), help="run only this round")
    run.add_argument("-m", "--model", help="model alias or id (default: the CLI's default)")
    run.add_argument(
        "-q",
        "--questions",
        type=_parse_targets,
        default=DEFAULT_TARGETS,
        metavar="R1,R2,R3",
        help=f"target question count per round (default: {','.join(map(str, DEFAULT_TARGETS))})",
    )
    run.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"where to write the style doc (default: {DEFAULT_OUTPUT})",
    )
    run.add_argument(
        "--force",
        action="store_true",
        help="discard a round that is already complete and run it again",
    )
    run.add_argument(
        "--quiet-agent", action="store_true", help="hide the interviewer's own commentary"
    )
    run.add_argument(
        "--allow-api-key",
        action="store_true",
        help="keep ANTHROPIC_API_KEY set instead of using your subscription",
    )

    synth = sub.add_parser("synthesize", help="write the style doc from a transcript")
    common(synth)
    synth.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"where to write the style doc (default: {DEFAULT_OUTPUT})",
    )
    synth.add_argument("-m", "--model", help="model alias or id")
    synth.add_argument(
        "--force", action="store_true", help="synthesize before all rounds finish"
    )
    synth.add_argument(
        "--allow-api-key",
        action="store_true",
        help="keep ANTHROPIC_API_KEY set instead of using your subscription",
    )

    show = sub.add_parser("show", help="print transcript status")
    common(show)
    show.add_argument("--full", action="store_true", help="print every question and answer")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return asyncio.run(_run(args))
        if args.command == "synthesize":
            return asyncio.run(_synthesize(args))
        return _show(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (KeyError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted — transcript saved", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
