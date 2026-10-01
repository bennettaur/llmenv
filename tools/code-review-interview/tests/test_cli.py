"""CLI wiring: argument parsing, round selection, credential handling."""

from __future__ import annotations

import argparse
import json
import os

import pytest

from code_review_interview.cli import (
    DEFAULT_TARGETS,
    TIMEOUT_ENV,
    _load,
    _parse_targets,
    build_parser,
    prepare_env,
    prepare_round,
)
from code_review_interview.transcript import COMPLETE, Transcript
from code_review_interview.tui import InterviewUI


@pytest.fixture
def ui() -> InterviewUI:
    return InterviewUI(show_agent_text=False)


# --- argument parsing -------------------------------------------------------


def test_targets_parse_into_three_ints():
    assert _parse_targets("18,12,10") == (18, 12, 10)


@pytest.mark.parametrize("raw", ["18,12", "18,12,10,8", "a,b,c", "18,12,0", "18,-1,10", ""])
def test_bad_targets_are_rejected(raw):
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_targets(raw)


def test_run_defaults():
    args = build_parser().parse_args(["run"])
    assert args.questions == DEFAULT_TARGETS
    assert args.force is False
    assert args.allow_api_key is False
    assert args.round is None


# --- round selection --------------------------------------------------------


def _completed(tmp_path):
    transcript = Transcript.load_or_create(tmp_path / "t.json")
    transcript.start_round(1)
    entry = transcript.add_question(1, "old question?", None)
    transcript.record_answer(entry, "old answer")
    transcript.complete_round(1, "old notes")
    return transcript


def test_a_complete_round_is_skipped(tmp_path, ui):
    transcript = _completed(tmp_path)

    assert prepare_round(transcript, 1, force=False, ui=ui) is False
    assert transcript.round(1).status == COMPLETE
    assert len(transcript.round(1).entries) == 1


def test_force_discards_the_round_rather_than_appending_to_it(tmp_path, ui):
    transcript = _completed(tmp_path)

    assert prepare_round(transcript, 1, force=True, ui=ui) is True

    rnd = transcript.round(1)
    assert rnd.entries == [], "--force must start over, not resume at the old count"
    assert rnd.summary is None
    assert rnd.status != COMPLETE


def test_an_unfinished_round_is_resumed(tmp_path, ui):
    transcript = Transcript.load_or_create(tmp_path / "t.json")
    transcript.start_round(1)
    transcript.add_question(1, "asked already?", None)

    assert prepare_round(transcript, 1, force=False, ui=ui) is True
    assert len(transcript.round(1).entries) == 1


# --- credentials and timeouts -----------------------------------------------


def test_api_credentials_are_unset_so_the_subscription_pays(monkeypatch, ui):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-should-not-be-used")

    prepare_env(allow_api_key=False, ui=ui)

    assert "ANTHROPIC_API_KEY" not in os.environ
    assert "ANTHROPIC_AUTH_TOKEN" not in os.environ


def test_allow_api_key_keeps_the_key(monkeypatch, ui):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-keep-me")

    prepare_env(allow_api_key=True, ui=ui)

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-keep-me"


def test_an_existing_tool_timeout_wins(monkeypatch, ui):
    monkeypatch.setenv("MCP_TOOL_TIMEOUT", "1234")

    prepare_env(allow_api_key=True, ui=ui)

    assert os.environ["MCP_TOOL_TIMEOUT"] == "1234"


def test_the_tool_timeout_is_set_when_absent(monkeypatch, ui):
    monkeypatch.delenv("MCP_TOOL_TIMEOUT", raising=False)

    prepare_env(allow_api_key=True, ui=ui)

    assert os.environ["MCP_TOOL_TIMEOUT"] == TIMEOUT_ENV["MCP_TOOL_TIMEOUT"]


# --- bad transcripts report, not traceback ----------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("missing", None),
        ("bad-json", "not json at all"),
        (
            "bad-version",
            json.dumps({"version": 99, "created_at": "x", "updated_at": "x", "rounds": []}),
        ),
        (
            "unexpected-field",
            json.dumps(
                {
                    "version": 1,
                    "created_at": "x",
                    "updated_at": "x",
                    "rounds": [
                        {
                            "number": 1,
                            "status": "pending",
                            "entries": [{"index": 1, "question": "q", "surprise": 1}],
                            "summary": None,
                            "started_at": None,
                            "completed_at": None,
                        }
                    ],
                }
            ),
        ),
    ],
)
def test_a_broken_transcript_exits_with_a_message(tmp_path, name, content):
    path = tmp_path / f"{name}.json"
    if content is not None:
        path.write_text(content)

    with pytest.raises(SystemExit) as excinfo:
        _load(path)

    assert "error:" in str(excinfo.value)
