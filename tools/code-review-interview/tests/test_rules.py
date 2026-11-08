"""Round-rule tests, driven against the real `ask_question` handler.

These are the tests that would fail if the blind rounds started leaking
answers, so they exercise the handler itself rather than a stand-in. The only
thing substituted is the human at the keyboard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_review_interview.prompts import default_rounds, resume_note
from code_review_interview.runner import ASK_TOOL, FINISH_TOOL, RoundRunner
from code_review_interview.transcript import COMPLETE, IN_PROGRESS, Transcript
from code_review_interview.tui import Answer, InterviewUI

SECRET = "SECRET-ANSWER-TEXT-9f3a"


class ScriptedUI(InterviewUI):
    """Stands in for the interviewee. Everything else is the real code."""

    def __init__(self, *answers: Answer) -> None:
        super().__init__(show_agent_text=False)
        self.queue = list(answers)
        self.default = Answer(text=SECRET)
        self.asked: list[str] = []

    async def collect_answer(self) -> Answer:
        return self.queue.pop(0) if self.queue else self.default

    def question(self, number, index, target, question, context) -> None:
        self.asked.append(question)


def make_runner(tmp_path: Path, round_number: int, ui: InterviewUI, target: int = 4):
    transcript = Transcript.load_or_create(tmp_path / "t.json")
    transcript.start_round(round_number)
    config = default_rounds((target, target, target))[round_number - 1]
    runner = RoundRunner(transcript, ui, config)
    runner._build_server()  # populates runner.tools
    return runner, transcript


async def ask(runner, question: str = "Q?") -> str:
    result = await runner.tools["ask_question"].handler({"question": question})
    return result["content"][0]["text"]


def is_error(result) -> bool:
    return bool(result.get("is_error"))


# --- the invariant ----------------------------------------------------------


@pytest.mark.parametrize("round_number", [1, 2])
async def test_blind_rounds_record_the_answer_without_returning_it(tmp_path, round_number):
    runner, transcript = make_runner(tmp_path, round_number, ScriptedUI())

    returned = await ask(runner)

    assert SECRET not in returned, "blind round leaked the answer to the interviewer"
    assert "withheld" in returned
    assert transcript.round(round_number).entries[0].answer == SECRET


async def test_round_three_returns_the_answer_to_the_interviewer(tmp_path):
    runner, transcript = make_runner(tmp_path, 3, ScriptedUI())

    returned = await ask(runner)

    assert SECRET in returned
    assert transcript.round(3).entries[0].answer == SECRET


async def test_skip_tells_the_interviewer_nothing_but_the_skip(tmp_path):
    runner, transcript = make_runner(tmp_path, 1, ScriptedUI(Answer(skipped=True)))

    returned = await ask(runner)

    assert "skipped" in returned.lower()
    assert SECRET not in returned
    entry = transcript.round(1).entries[0]
    assert entry.skipped and entry.answer is None


# --- limits and endings -----------------------------------------------------


async def test_asking_past_the_hard_cap_is_refused(tmp_path):
    runner, transcript = make_runner(tmp_path, 1, ScriptedUI(), target=4)
    assert runner.hard_cap == 6

    for i in range(runner.hard_cap):
        await ask(runner, f"Q{i}?")

    result = await runner.tools["ask_question"].handler({"question": "one more?"})

    assert is_error(result)
    assert len(transcript.round(1).entries) == runner.hard_cap


async def test_stop_discards_the_open_question_and_closes_the_round(tmp_path):
    ui = ScriptedUI(Answer(text="kept"), Answer(stop_round=True))
    runner, transcript = make_runner(tmp_path, 1, ui)

    await ask(runner, "first?")
    returned = await ask(runner, "second?")

    assert "end the round" in returned
    assert [e.question for e in transcript.round(1).entries] == ["first?"]
    assert runner.state.asked == 1
    assert runner.state.stop_requested and not runner.state.interrupted
    assert is_error(await runner.tools["ask_question"].handler({"question": "third?"}))


async def test_interrupt_discards_the_question_and_leaves_the_round_resumable(tmp_path):
    class Interrupting(ScriptedUI):
        async def collect_answer(self):
            raise KeyboardInterrupt

    runner, transcript = make_runner(tmp_path, 1, Interrupting())

    result = await runner.tools["ask_question"].handler({"question": "Q?"})

    assert is_error(result)
    assert transcript.round(1).entries == []
    assert runner.state.interrupted and not runner.state.stop_requested
    # The distinction that matters: an interrupted round is not a finished one.
    assert transcript.round(1).status == IN_PROGRESS
    assert 1 in transcript.unfinished_rounds()


async def test_a_broken_prompt_does_not_strand_an_unanswered_entry(tmp_path):
    class Broken(ScriptedUI):
        async def collect_answer(self):
            raise OSError("terminal went away")

    runner, transcript = make_runner(tmp_path, 1, Broken())

    assert is_error(await runner.tools["ask_question"].handler({"question": "Q?"}))
    assert transcript.round(1).entries == []


async def test_finish_round_closes_the_round_and_refuses_a_second_call(tmp_path):
    runner, _ = make_runner(tmp_path, 1, ScriptedUI())

    first = await runner.tools["finish_round"].handler({"summary": "covered X"})
    second = await runner.tools["finish_round"].handler({"summary": "again"})

    assert not is_error(first)
    assert is_error(second)
    assert runner.state.summary == "covered X"
    assert is_error(await runner.tools["ask_question"].handler({"question": "after?"}))


async def test_a_second_concurrent_question_is_refused_not_crashed(tmp_path):
    runner, _ = make_runner(tmp_path, 1, ScriptedUI())

    await runner._ask_lock.acquire()
    try:
        result = await runner.tools["ask_question"].handler({"question": "Q?"})
    finally:
        runner._ask_lock.release()

    assert is_error(result)
    assert "one at a time" in result["content"][0]["text"]


# --- isolation --------------------------------------------------------------


async def test_the_interviewer_gets_no_tools_and_no_ambient_settings(tmp_path):
    runner, _ = make_runner(tmp_path, 1, ScriptedUI())

    options = runner.options()

    assert options.tools == []
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.cwd is not None and str(options.cwd) != str(Path.cwd())
    # allowed_tools must stay empty: a bare name there auto-approves before
    # can_use_tool runs, which would make the gate below unreachable.
    assert options.allowed_tools == []
    assert options.can_use_tool is not None


@pytest.mark.parametrize(
    ("tool_name", "allowed"),
    [(ASK_TOOL, True), (FINISH_TOOL, True), ("Bash", False), ("Read", False)],
)
async def test_the_permission_gate_allows_only_the_interview_tools(
    tmp_path, tool_name, allowed
):
    runner, _ = make_runner(tmp_path, 1, ScriptedUI())

    result = await runner.options().can_use_tool(tool_name, {}, None)

    assert (type(result).__name__ == "PermissionResultAllow") is allowed


# --- resume -----------------------------------------------------------------


async def test_round_two_sees_round_one_answers_but_not_its_own(tmp_path):
    transcript = Transcript.load_or_create(tmp_path / "t.json")
    transcript.start_round(1)
    entry = transcript.add_question(1, "R1 question?", None)
    transcript.record_answer(entry, "R1-ANSWER-TEXT")
    transcript.complete_round(1, "notes")

    config = default_rounds((4, 4, 4))[1]
    ui = ScriptedUI()
    runner = RoundRunner(transcript, ui, config)
    runner._build_server()

    prior = transcript.render_rounds([1], "nonce")
    assert "R1-ANSWER-TEXT" in prior, "round 2 must be able to read round 1's answers"

    returned = await ask(runner, "R2 question?")
    assert SECRET not in returned, "round 2 must not see its own answers"


def test_resume_lists_asked_questions_without_their_answers():
    note = resume_note(["what do you read first?", "what do you skip?"])

    assert "what do you read first?" in note
    assert "what do you skip?" in note
    assert "do not repeat" in note


def test_a_reset_round_is_run_again_from_scratch(tmp_path):
    transcript = Transcript.load_or_create(tmp_path / "t.json")
    transcript.start_round(1)
    entry = transcript.add_question(1, "old question?", None)
    transcript.record_answer(entry, "old answer")
    transcript.complete_round(1, "old notes")

    transcript.reset_round(1)

    rnd = transcript.round(1)
    assert rnd.entries == [] and rnd.summary is None
    assert rnd.status != COMPLETE
    assert 1 in transcript.unfinished_rounds()
