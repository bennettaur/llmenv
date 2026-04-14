---
name: do-code-review
description: "Orchestrate comprehensive code review by launching specialized reviewer subagents in parallel. Use when: (1) User explicitly requests code review, (2) Before creating a pull request, (3) After completing a feature or major implementation, (4) When user indicates they're done with changes and ready to submit/merge. This skill coordinates multiple reviewer subagents (code quality, security, performance, testing, documentation, clarity) to provide thorough feedback."
---

# Code Review Orchestration

This skill coordinates parallel execution of specialized reviewer subagents to provide comprehensive code feedback. Each reviewer is defined as a thin wrapper agent in the `agents/` directory that preloads its corresponding skill, allowing you to pass context and instructions via the Agent tool's `prompt` parameter.

## How It Works

Each reviewer lives in `agents/<name>.md` and has its corresponding skill preloaded via the `skills` frontmatter field. When you launch a reviewer using the **Agent tool**, the subagent starts with the full skill instructions already in its context. Your `prompt` parameter provides the specific review context — changed files, the original task goal, and any additional instructions.

This approach (Agent tool + preloaded skills) replaces the previous `context: fork` pattern because it allows the parent to pass tailored instructions to each subagent.

## Reviewer Selection

Based on the context, select relevant reviewers to launch:

**Always run:**
- `superpowers:code-reviewer` - (If it's available) Reviews against original plan and coding standards
- `code-clarity-reviewer` - Reviews code readability, comments, and beginner-friendliness
- `security-privacy-reviewer` - Identifies security vulnerabilities and privacy risks
- `scope-drift-reviewer` - Detects changes that drift from the original goal or prompt

**Conditionally run based on changes:**
- `code-best-practices-reviewer` - Run if code files changed (detects tech stack and applies best practices hierarchy)
- `performance-optimizer` - Run if performance-sensitive code changed (database queries, loops, API calls, data processing)
- `test-quality-enforcer` - Run if implementation code changed (skip for docs-only, config-only changes)
- `documentation-updater` - Run if feature changes, API changes, or behavior modifications occurred
- `dead-code-cleaner` - Run if implementation code changed, especially after refactoring or feature completion
- `llm-usage-security-reviewer` - Run if code involves LLM API calls, prompt construction, agent frameworks, or AI/ML integration (imports from anthropic, openai, langchain, llamaindex, etc.)

## Execution Workflow

1. **Identify changed files**
   ```bash
   git status
   git diff --name-only origin/main...HEAD
   ```

2. **Determine reviewer set**
   Based on changed files:
   - Code files (.ts, .js, .py, .rb, etc.) → Include code-best-practices-reviewer, test-quality-enforcer, performance-optimizer, dead-code-cleaner
   - Config/docs only → Skip best-practices/test/performance/dead-code reviewers
   - API/public interface changes → Include documentation-updater
   - User input handling → Emphasize security-privacy-reviewer
   - Refactoring or significant code changes → Emphasize dead-code-cleaner
   - LLM integration code (anthropic/openai SDK imports, prompt templates, agent configs) → Include llm-usage-security-reviewer

3. **Launch subagents in parallel**
   Use a SINGLE message with multiple Agent tool calls to launch all selected reviewers simultaneously. Each Agent call should:
   - Set `subagent_type` to the reviewer's agent name (e.g., `"code-clarity-reviewer"`)
   - Provide a `description` summarizing the review task
   - Include a `prompt` with the review context: changed files list, diff summary, and the original task goal (especially important for scope-drift-reviewer)

   Example structure:
   ```
   [Single message containing:]
   - Agent(subagent_type="code-clarity-reviewer", description="Code clarity review", prompt="Review these changes: <files and context>")
   - Agent(subagent_type="security-privacy-reviewer", description="Security review", prompt="Review these changes for security issues: <files and context>")
   - Agent(subagent_type="scope-drift-reviewer", description="Scope drift review", prompt="Original goal: <goal>. Review these changes for drift: <files and context>")
   - Agent(subagent_type="code-best-practices-reviewer", description="Best practices review", prompt="Review these changes: <files and context>") (if applicable)
   - Agent(subagent_type="performance-optimizer", description="Performance review", prompt="Review these changes: <files and context>") (if applicable)
   - Agent(subagent_type="test-quality-enforcer", description="Test quality review", prompt="Review these changes: <files and context>") (if applicable)
   - Agent(subagent_type="documentation-updater", description="Documentation review", prompt="Review these changes: <files and context>") (if applicable)
   - Agent(subagent_type="dead-code-cleaner", description="Dead code review", prompt="Review these changes: <files and context>") (if applicable)
   - Agent(subagent_type="llm-usage-security-reviewer", description="LLM security review", prompt="Review these changes: <files and context>") (if applicable)
   ```

4. **Collect and synthesize feedback**
   After all subagents complete:
   - Deduplicate findings — if multiple reviewers flag the same issue, merge into one entry and list all discovering reviewers
   - Assign each unique issue a global number (sequential across all severity groups)
   - Classify each issue into one of four severity levels (see output format below)
   - Present the consolidated report using the **exact format** specified below

5. **Consolidated Report Output Format**

   Use this structure exactly. Omit any severity section that has zero issues.

   ```
   # Code Review Summary

   **Files reviewed:** <count>
   **Issues found:** <total count>
   **Reviewed by:** <comma-separated list of all reviewers that ran>

   ---

   ## Blocking (must fix before merge)

   **#1 — <Short issue title>**
   <Description of the issue: what's wrong, where it occurs (file:line if possible), and why it matters.>
   _Found by: <reviewer-name>, <reviewer-name>_

   **#2 — <Short issue title>**
   ...

   ---

   ## High (strongly recommended)

   **#3 — <Short issue title>**
   <Description of the issue.>
   _Found by: <reviewer-name>_

   ---

   ## Medium (recommended)

   **#4 — <Short issue title>**
   <Description of the issue.>
   _Found by: <reviewer-name>, <reviewer-name>_

   ---

   ## Low (nice to have)

   **#5 — <Short issue title>**
   <Description of the issue.>
   _Found by: <reviewer-name>_
   ```

   **Severity classification guide:**
   - **Blocking:** Security vulnerabilities, data loss risks, broken functionality, crashes, correctness bugs
   - **High:** Significant best-practice violations, missing tests for critical paths, meaningful performance issues, scope drift that changes behavior
   - **Medium:** Code clarity improvements, minor performance optimizations, missing edge-case tests, documentation gaps
   - **Low:** Style nits, optional refactors, nice-to-have documentation, minor dead code

6. **Follow-up actions**
   If blocking issues found:
   - Fix issues before proceeding to PR
   - Re-run affected reviewers to verify fixes

   If only improvements suggested:
   - Ask user whether to implement improvements or proceed with PR
   - Respect user's decision on scope

## Reviewer-Specific Context

When crafting the `prompt` for each Agent call, include the following context:

**superpowers:code-reviewer**: Requires implementation plan context. If no plan exists, skip or use general coding standards.

**code-clarity-reviewer**: Focus on whether code tells a story and is accessible to team members.

**security-privacy-reviewer**: Prioritize user data handling, authentication/authorization, input validation, and logging.

**code-best-practices-reviewer**: Mention the detected tech stack so it can apply best practices in priority order: codebase conventions, framework patterns, language standards, then general engineering principles.

**performance-optimizer**: Highlight any database queries, loops, API calls, and data processing in the changes.

**test-quality-enforcer**: Include the list of implementation files that changed so it can verify coverage.

**documentation-updater**: Note any feature changes, API changes, or behavior modifications.

**dead-code-cleaner**: Mention if this was a refactoring or feature completion — these are high-value contexts for dead code detection.

**scope-drift-reviewer**: Include the original user prompt/plan so the subagent can assess whether changes serve the original goal. This context is critical for accurate drift detection.

**llm-usage-security-reviewer**: Highlight any LLM API call sites, prompt construction, agent loop configuration, and tool definitions in the changes.

## Example Invocation

When user says "Review my authentication implementation":

1. Check git diff (authentication changes = security-critical)
2. Launch in parallel via Agent tool calls:
   - All "always run" reviewers (scope-drift-reviewer with the original prompt as context)
   - code-best-practices-reviewer (code files changed)
   - performance-optimizer (auth often has DB queries)
   - test-quality-enforcer (new implementation)
   - documentation-updater (likely API changes)
   - dead-code-cleaner (especially if refactored from old auth pattern)
3. Synthesize findings from all subagents — prioritize security issues, best practice violations, and any scope drift flags
4. Present prioritized feedback

## Important Notes

- **Parallel execution is mandatory** - Always use a single message with multiple Agent tool calls
- **Pass context via prompt** - Each subagent has its skill preloaded but needs the review context (files, diffs, original goal) from you
- **Context matters** - Don't run irrelevant reviewers (e.g., test-quality-enforcer on README-only changes)
- **Respect scope** - If user wants quick review, ask which aspects to focus on
- **No false reassurance** - If reviewers find issues, don't minimize them. Report honestly.
