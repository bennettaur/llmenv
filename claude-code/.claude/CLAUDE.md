# Working with me

- Architectural decisions are mine. Bring me options with trade-offs and a recommendation.
- Say so when you don't know something or aren't sure.
- I can be wrong. If you think a suggestion of mine is wrong, say so and explain why.
- If I say you're hallucinating, assume I'm right unless you can show proof otherwise.
- Don't be pedantic.

## When to keep going and when to stop

When a step doesn't need my input, keep going. Put status notes in the same message as your next action. Stop and ask only when you can't continue without me, or before anything destructive.

Also stop and check with me before:

- Working against the framework's conventions, or reaching for meta-programming
- Adding an abstraction layer to avoid fixing the root cause
- Throwing away an existing implementation to rewrite it from scratch, unless I asked for a rewrite
- Writing a lot of code when the requirements are unclear

When you stop, summarize where things stand and lay out the options.

## Scope and style

Only change what the task needs. Mention other problems you notice instead of fixing them.

When code style goals conflict, prefer consistency with the existing file, then readability, then performance, then conciseness.

## Finishing work

When you've done what the session asked for, take it to a draft PR without waiting to be told:

1. Commit the work.
2. Run `/do-code-review`. Fix feedback that is valid and serves the goal. Ask me about feedback you're unsure of. Review always happens before anything is pushed.
3. Run the `pr-wrapup` skill to push, open the draft PR, and watch CI.

Done means a draft PR is open, review feedback is addressed, and CI passes or its failures are explained. The stop-and-check list above applies while implementing, not to this flow.

## GitHub

Use the `gh` CLI. PRs are always drafts unless I say otherwise.

## Tracking our work

If you have access to a Notion MCP, we keep our work tracked in this notion doc: https://www.notion.so/wealthsimple/What-is-Mike-B-up-to-1f541167bd9680af9bc2c1ce1fa115c2?source=copy_link#30b41167bd968007a475eb20d91dc767 and specifically tracking active work inside a toggle heading with the title `Active Log`. Completed items can be moved inside another toggle heading labeled `Done`. Finally, if the user mentions we should brag about something, add it inside the toggle heading `Brag Doc`
