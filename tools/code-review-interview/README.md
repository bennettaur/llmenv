# code-review-interview

A three-phase interview about how *you* review code, run by a Claude agent, that ends
with a **Code Review Style** document another LLM can follow — to review your PRs the
way you would, dig deeper than you have time for, and walk you through the parts you
care most about.

The point of the phasing is bias control. An interviewer that reads each answer as it
arrives narrows fast: it chases the first interesting thread and never asks about the
territory it happened not to stumble into. So the first two rounds are **blind** — the
agent asks, the answer is recorded to disk, and the agent is told only that it landed.

| Round | Agent is given | Agent sees your answers | Purpose |
|---|---|---|---|
| 1 | nothing | no | breadth — stake out the whole territory |
| 2 | round 1 Q&A | no | depth — push on thin spots, cover what round 1 missed |
| 3 | rounds 1–2 Q&A | **yes, immediately** | drill in, resolve contradictions, close gaps |

## Requirements

- [`uv`](https://docs.astral.sh/uv/)
- The `claude` CLI, logged in. The interview runs on your Claude **subscription** — the
  tool unsets `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` for the run so a stray key
  doesn't silently bill the API instead. Pass `--allow-api-key` to keep them.

## Use

```sh
cd tools/code-review-interview
uv sync

uv run code-review-interview run              # rounds 1 → 3, resumes where you left off
uv run code-review-interview show --full      # read the transcript back
uv run code-review-interview synthesize       # write code-review-style.md
```

`run` offers to write the style doc once all three rounds are done, so the
`synthesize` subcommand is only needed to regenerate it (or to pass `--force` and build
one from a partial interview).

### Answering

Answers are multi-line. While one is open:

| | |
|---|---|
| `Esc` then `Enter` | submit (a line containing only `.` also submits) |
| `Enter` | newline |
| `/edit` | write the answer in `$VISUAL`, else `$EDITOR`, else `vi` |
| `/skip` | skip this question; the agent is told, and moves on |
| `/stop` (or `/done`, `/end`, `Ctrl-D`) | end the round here; the agent writes its summary and the round is marked complete |
| `/help` | reprint the key bindings |
| `Ctrl-C` | abandon the round; it stays **in progress** and the next `run` resumes it |

Commands are case-insensitive and submit on their own line. A command word inside a
longer answer is treated as ordinary text.

Long answers are good. Concrete beats abstract — the synthesis step leans on your war
stories far more than on your generalisations.

### Options

```sh
uv run code-review-interview run \
  -t interview.json \        # transcript file (default: code-review-interview.json)
  -o style.md \              # style doc output (default: code-review-style.md)
  -r 2 \                     # run only round 2
  -q 18,12,10 \              # target questions per round
  -m opus \                  # model alias or id
  --force \                  # discard an already-complete round and run it again
  --quiet-agent              # hide the interviewer's own commentary
```

## Resuming

The transcript is rewritten after every answer, so an interruption costs only the
question that was on screen. Re-running `run` picks up the first unfinished round; a
partially-finished round resumes with its already-asked questions listed to the agent so
it doesn't repeat them. Answers stay withheld in rounds 1 and 2 across a resume, same as
a clean run.

A round is marked complete when the agent closes it, when you `/stop`, or when it hits
the question cap. Anything else — `Ctrl-C`, a crash, an agent that wanders off without
closing the round — leaves it in progress and therefore resumable.

## Where your answers live

The transcript is your unfiltered prose about your employer's codebase, incidents, and
team, and the style doc is the distilled version of the same material. Both are written
**to the directory you run from** — `code-review-interview.json` and
`code-review-style.md` — at mode `0600`, and stay there until you delete them. If you
run this inside a repo, either pass `-t`/`-o` to put them somewhere else or make sure
they're ignored; this tool's own `.gitignore` only covers its own directory.

## How the round rules are enforced

The agent has **no built-in tools** — no file access, no web, no bash. Its only actions
are two in-process MCP tools:

- `ask_question(question, context?)` — blocks until you answer. Returns the answer text
  only in round 3; in rounds 1 and 2 it returns a bare acknowledgement plus a progress
  count. Withholding happens in `runner.py`, not in the prompt, so it holds even if the
  agent is asked to ignore its instructions. Past `target + 35%` the tool refuses
  outright and tells the agent to wrap up (24/16/14 questions at the default targets).
  Concurrent calls are refused rather than serviced, so two questions can never land on
  screen at once.
- `finish_round(summary)` — ends the round and records the agent's own notes. Calling it
  twice, or asking anything after it, is refused.

A `can_use_tool` gate denies every other tool. It is the *only* approval path —
`allowed_tools` is deliberately left unset, because a bare name there auto-approves
before the callback runs. `setting_sources=[]`, `strict_mcp_config=True`, and a scratch
working directory keep your `CLAUDE.md`, project settings, ambient MCP servers, and
current repo out of the interviewer's context — otherwise the questions get coloured by
whatever you happen to be working on.

Recorded answers are fenced with a per-run nonce (`<answer_3f9a…>`) wherever they are
fed back into a prompt, and both agents are told that fenced content is data to describe,
never instructions to follow. Answers routinely contain pasted diffs and PR text, and the
synthesised document becomes another agent's instructions — so the boundary needs to be
one the content cannot forge.

Because an answer blocks the tool call for as long as you take to type it,
`MCP_TOOL_TIMEOUT` is raised to 4 hours for the run (via `setdefault`, so your own value
wins).

## Files

| | |
|---|---|
| `code_review_interview/prompts.py` | round configuration and every system prompt — start here to tune the interview |
| `code_review_interview/runner.py` | agent session, the two tools, round-rule enforcement |
| `code_review_interview/isolation.py` | the agent posture both entry points share |
| `code_review_interview/transcript.py` | the durable record; 0600 atomic writes |
| `code_review_interview/tui.py` | question rendering and answer capture |
| `code_review_interview/synthesize.py` | transcript → style doc |
| `code_review_interview/cli.py` | subcommands, defaults, credential and timeout handling |
| `tests/test_rules.py` | the round rules, against the real tool handler |
| `tests/test_tui.py` | answer capture and transcript persistence |
| `tests/test_cli.py` | argument parsing, round selection, credential handling |
| `tests/smoke_round.py` | live end-to-end round with scripted answers |
| `tests/smoke_synth.py` | live synthesis on a hand-built transcript |

```sh
uv run pytest                            # offline, no API calls
uv run ruff check . && uv run ruff format --check .

uv run python tests/smoke_round.py 1     # live: blind round
uv run python tests/smoke_round.py 3     # live: interactive round
uv run python tests/smoke_synth.py       # live: synthesis
```

The smoke tests assert the blind contract on the live path too: round 1 checks that no
answer text ever reaches the interviewer, round 3 checks that it does.
