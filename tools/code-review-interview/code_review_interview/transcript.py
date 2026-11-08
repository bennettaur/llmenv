"""Persistent record of every question asked and every answer given.

The transcript is the only durable state. It is rewritten after each answer via
a 0600 temp file plus `os.replace`, so an interrupted session loses nothing but
the in-flight question, and the file never widens to the umask default — it
holds the interviewee's unfiltered prose about their employer's codebase.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = 1

Status = Literal["pending", "in_progress", "complete"]

PENDING: Status = "pending"
IN_PROGRESS: Status = "in_progress"
COMPLETE: Status = "complete"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Entry:
    """One question and the answer it received."""

    index: int
    question: str
    context: str | None = None
    answer: str | None = None
    skipped: bool = False
    asked_at: str = field(default_factory=_now)
    answered_at: str | None = None

    @property
    def answered(self) -> bool:
        return self.answer is not None or self.skipped


@dataclass
class Round:
    number: int
    status: Status = PENDING
    entries: list[Entry] = field(default_factory=list)
    summary: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    @property
    def answered_entries(self) -> list[Entry]:
        return [e for e in self.entries if e.answered]


@dataclass
class Transcript:
    path: Path
    version: int = SCHEMA_VERSION
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    rounds: list[Round] = field(default_factory=list)

    # --- construction -----------------------------------------------------

    @classmethod
    def load_or_create(cls, path: Path, round_count: int = 3) -> Transcript:
        if path.exists():
            return cls.load(path)
        transcript = cls(path=path)
        transcript.rounds = [Round(number=n) for n in range(1, round_count + 1)]
        transcript.save()
        return transcript

    @classmethod
    def load(cls, path: Path) -> Transcript:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != SCHEMA_VERSION:
            raise ValueError(
                f"{path} has schema version {raw.get('version')}, "
                f"this build understands {SCHEMA_VERSION}"
            )
        rounds = [
            Round(
                number=r["number"],
                status=r["status"],
                entries=[Entry(**e) for e in r["entries"]],
                summary=r.get("summary"),
                started_at=r.get("started_at"),
                completed_at=r.get("completed_at"),
            )
            for r in raw["rounds"]
        ]
        return cls(
            path=path,
            version=raw["version"],
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            rounds=rounds,
        )

    # --- persistence ------------------------------------------------------

    def save(self) -> None:
        self.updated_at = _now()
        payload = {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rounds": [asdict(r) for r in self.rounds],
        }
        write_private(self.path, json.dumps(payload, indent=2) + "\n")

    # --- accessors --------------------------------------------------------

    def round(self, number: int) -> Round:
        for r in self.rounds:
            if r.number == number:
                return r
        raise KeyError(f"no round {number} in {self.path}")

    def unfinished_rounds(self) -> list[int]:
        return [r.number for r in self.rounds if r.status != COMPLETE]

    def start_round(self, number: int) -> Round:
        rnd = self.round(number)
        rnd.status = IN_PROGRESS
        rnd.started_at = rnd.started_at or _now()
        self.save()
        return rnd

    def complete_round(self, number: int, summary: str | None = None) -> None:
        rnd = self.round(number)
        rnd.status = COMPLETE
        rnd.completed_at = _now()
        if summary:
            rnd.summary = summary
        self.save()

    def reset_round(self, number: int) -> None:
        """Throw a round away so it can be run again from scratch."""
        rnd = self.round(number)
        rnd.status = PENDING
        rnd.entries = []
        rnd.summary = None
        rnd.started_at = None
        rnd.completed_at = None
        self.save()

    def add_question(self, number: int, question: str, context: str | None) -> Entry:
        rnd = self.round(number)
        entry = Entry(index=len(rnd.entries) + 1, question=question, context=context)
        rnd.entries.append(entry)
        self.save()
        return entry

    def record_answer(self, entry: Entry, answer: str | None, skipped: bool = False) -> None:
        entry.answer = answer
        entry.skipped = skipped
        entry.answered_at = _now()
        self.save()

    def drop_entry(self, number: int, entry: Entry) -> None:
        """Remove a question that never got an answer (e.g. Ctrl-C mid-question)."""
        rnd = self.round(number)
        if entry in rnd.entries:
            rnd.entries.remove(entry)
            self.save()

    # --- rendering for prompts -------------------------------------------

    def render_rounds(self, numbers: list[int], nonce: str) -> str:
        """Markdown view of prior rounds, for feeding to the next round's agent.

        Answers are fenced with a per-run nonce. They routinely contain pasted
        diffs, PR text, and markdown headings of their own, and this rendering
        ends up inside a prompt whose output becomes another agent's
        instructions — so the boundary between record and directive has to be
        one the content cannot forge.
        """
        chunks: list[str] = []
        for number in numbers:
            rnd = self.round(number)
            if not rnd.entries:
                continue
            lines = [f"## Round {number}"]
            for entry in rnd.entries:
                lines.append(f"\n### Q{entry.index}. {entry.question}")
                if entry.context:
                    lines.append(f"_(framing given: {entry.context})_")
                if entry.skipped:
                    lines.append("\n**Answer:** _(skipped by the interviewee)_")
                elif entry.answer:
                    lines.append(f"\n**Answer:**\n{fence(entry.answer, nonce)}")
                else:
                    lines.append("\n**Answer:** _(never answered)_")
            chunks.append("\n".join(lines))
        return "\n\n".join(chunks)

    def total_answered(self) -> int:
        return sum(len(r.answered_entries) for r in self.rounds)


def write_private(path: Path, text: str) -> None:
    """Write a file only its owner can read, atomically.

    Both the transcript and the style doc carry the interviewee's account of
    their employer's codebase. mkstemp gives 0600 and an unpredictable name;
    os.replace then moves that inode over the destination, so the mode survives
    every rewrite rather than reverting to the umask default.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise


def new_nonce() -> str:
    return os.urandom(4).hex()


def fence(text: str, nonce: str) -> str:
    """Wrap recorded text in nonce-tagged markers it cannot break out of."""
    return f"<answer_{nonce}>\n{text.replace(nonce, '')}\n</answer_{nonce}>"
