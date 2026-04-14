---
name: do-code-review
description: "Orchestrate comprehensive code review by running specialized review skills in parallel as forked subagents. Use when: (1) User explicitly requests code review, (2) Before creating a pull request, (3) After completing a feature or major implementation, (4) When user indicates they're done with changes and ready to submit/merge. This skill coordinates multiple review subagents (code quality, security, performance, testing, documentation, clarity) to provide thorough feedback."
---

# Code Review Orchestration

This skill coordinates parallel execution of specialized review skills to provide comprehensive code feedback. Each reviewer skill uses `context: fork` to run in an isolated subagent, analyzing the code independently and returning findings.

## How It Works

Each reviewer skill below has `context: fork` in its frontmatter, which means invoking it via the Skill tool automatically spawns a dedicated subagent. The subagent receives the skill's instructions as its prompt, runs its analysis in isolation (no conversation history), and returns its findings.

## Review Skill Selection

Based on the context, select relevant skills to invoke:

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

## Execution Workflow

1. **Identify changed files**
   ```bash
   git status
   git diff --name-only origin/main...HEAD
   ```

2. **Determine skill set**
   Based on changed files:
   - Code files (.ts, .js, .py, .rb, etc.) → Include code-best-practices-reviewer, test-quality-enforcer, performance-optimizer, dead-code-cleaner
   - Config/docs only → Skip best-practices/test/performance/dead-code skills
   - API/public interface changes → Include documentation-updater
   - User input handling → Emphasize security-privacy-reviewer
   - Refactoring or significant code changes → Emphasize dead-code-cleaner

3. **Launch skills in parallel**
   Use a SINGLE message with multiple Skill tool calls to invoke all selected reviewer skills simultaneously. Each skill with `context: fork` will automatically spawn its own subagent.

   Example structure:
   ```
   [Single message containing:]
   - Skill tool call for superpowers:code-reviewer
   - Skill tool call for code-clarity-reviewer
   - Skill tool call for security-privacy-reviewer
   - Skill tool call for scope-drift-reviewer
   - Skill tool call for code-best-practices-reviewer (if applicable)
   - Skill tool call for performance-optimizer (if applicable)
   - Skill tool call for test-quality-enforcer (if applicable)
   - Skill tool call for documentation-updater (if applicable)
   - Skill tool call for dead-code-cleaner (if applicable)
   ```

4. **Collect and synthesize feedback**
   After all subagents complete:
   - Deduplicate findings — if multiple skills flag the same issue, merge into one entry and list all discovering skills
   - Assign each unique issue a global number (sequential across all severity groups)
   - Classify each issue into one of four severity levels (see output format below)
   - Present the consolidated report using the **exact format** specified below

5. **Consolidated Report Output Format**

   Use this structure exactly. Omit any severity section that has zero issues.

   ```
   # Code Review Summary

   **Files reviewed:** <count>
   **Issues found:** <total count>
   **Reviewed by:** <comma-separated list of all skills that ran>

   ---

   ## Blocking (must fix before merge)

   **#1 — <Short issue title>**
   <Description of the issue: what's wrong, where it occurs (file:line if possible), and why it matters.>
   _Found by: <skill-name>, <skill-name>_

   **#2 — <Short issue title>**
   ...

   ---

   ## High (strongly recommended)

   **#3 — <Short issue title>**
   <Description of the issue.>
   _Found by: <skill-name>_

   ---

   ## Medium (recommended)

   **#4 — <Short issue title>**
   <Description of the issue.>
   _Found by: <skill-name>, <skill-name>_

   ---

   ## Low (nice to have)

   **#5 — <Short issue title>**
   <Description of the issue.>
   _Found by: <skill-name>_
   ```

   **Severity classification guide:**
   - **Blocking:** Security vulnerabilities, data loss risks, broken functionality, crashes, correctness bugs
   - **High:** Significant best-practice violations, missing tests for critical paths, meaningful performance issues, scope drift that changes behavior
   - **Medium:** Code clarity improvements, minor performance optimizations, missing edge-case tests, documentation gaps
   - **Low:** Style nits, optional refactors, nice-to-have documentation, minor dead code

6. **Follow-up actions**
   If blocking issues found:
   - Fix issues before proceeding to PR
   - Re-run affected skills to verify fixes

   If only improvements suggested:
   - Ask user whether to implement improvements or proceed with PR
   - Respect user's decision on scope

## Skill-Specific Context

**superpowers:code-reviewer**: Requires implementation plan context. If no plan exists, skip or use general coding standards.

**code-clarity-reviewer**: Focus on whether code tells a story and is accessible to team members.

**security-privacy-reviewer**: Prioritize user data handling, authentication/authorization, input validation, and logging.

**code-best-practices-reviewer**: Detects the tech stack and applies best practices in priority order: codebase conventions, framework patterns, language standards, then general engineering principles.

**performance-optimizer**: Look for N+1 queries, inefficient algorithms, unnecessary re-renders, and caching opportunities.

**test-quality-enforcer**: Verify coverage of new/changed code, edge cases, and error conditions.

**documentation-updater**: Check README, API docs, inline docs, and migration guides for accuracy.

**dead-code-cleaner**: Identify unused code, dead functions, orphaned tests, and cleanup opportunities in current changes.

**scope-drift-reviewer**: Evaluate whether all changes serve the original goal. Requires the original prompt/plan as context — pass the user's original request and any implementation plan so the subagent can assess drift. Flags changes classified as "Beneficial but Unrelated" or "Unnecessary Drift".

## Example Invocation

When user says "Review my authentication implementation":

1. Check git diff (authentication changes = security-critical)
2. Launch in parallel via Skill tool calls:
   - All "always run" skills (including scope-drift-reviewer with the original prompt as context)
   - code-best-practices-reviewer (code files changed)
   - performance-optimizer (auth often has DB queries)
   - test-quality-enforcer (new implementation)
   - documentation-updater (likely API changes)
   - dead-code-cleaner (especially if refactored from old auth pattern)
3. Synthesize findings from all subagents — prioritize security issues, best practice violations, and any scope drift flags
4. Present prioritized feedback

## Important Notes

- **Parallel execution is mandatory** - Always use a single message with multiple Skill tool calls
- **Context matters** - Don't run irrelevant skills (e.g., test-quality-enforcer on README-only changes)
- **Respect scope** - If user wants quick review, ask which aspects to focus on
- **No false reassurance** - If skills find issues, don't minimize them. Report honestly.
