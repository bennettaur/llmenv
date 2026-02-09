---
name: code-review
description: "Orchestrate comprehensive code review by running specialized review agents in parallel. Use when: (1) User explicitly requests code review, (2) Before creating a pull request, (3) After completing a feature or major implementation, (4) When user indicates they're done with changes and ready to submit/merge. This skill coordinates multiple review agents (code quality, security, performance, testing, documentation, clarity) to provide thorough feedback."
---

# Code Review Orchestration

This skill coordinates parallel execution of specialized review agents to provide comprehensive code feedback.

## Review Agent Selection

Based on the context, select relevant agents:

**Always run:**
- `superpowers:code-reviewer` - Reviews against original plan and coding standards
- `code-clarity-reviewer` - Reviews code readability, comments, and beginner-friendliness
- `security-privacy-reviewer` - Identifies security vulnerabilities and privacy risks

**Conditionally run based on changes:**
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

2. **Determine agent set**
   Based on changed files:
   - Code files (.ts, .js, .py, .rb, etc.) → Include test-quality-enforcer, performance-optimizer, dead-code-cleaner
   - Config/docs only → Skip test/performance/dead-code agents
   - API/public interface changes → Include documentation-updater
   - User input handling → Emphasize security-privacy-reviewer
   - Refactoring or significant code changes → Emphasize dead-code-cleaner

3. **Launch agents in parallel**
   Use a SINGLE message with multiple Task tool calls to launch all selected agents simultaneously.

   Example structure:
   ```
   [Single message containing:]
   - Task tool call for superpowers:code-reviewer
   - Task tool call for code-clarity-reviewer
   - Task tool call for security-privacy-reviewer
   - Task tool call for performance-optimizer (if applicable)
   - Task tool call for test-quality-enforcer (if applicable)
   - Task tool call for documentation-updater (if applicable)
   - Task tool call for dead-code-cleaner (if applicable)
   ```

4. **Collect and synthesize feedback**
   After all agents complete:
   - Group findings by severity (blocking issues vs improvements)
   - Identify common themes across agents
   - Prioritize actionable items
   - Present consolidated summary to user

5. **Follow-up actions**
   If blocking issues found:
   - Fix issues before proceeding to PR
   - Re-run affected agents to verify fixes

   If only improvements suggested:
   - Ask user whether to implement improvements or proceed with PR
   - Respect user's decision on scope

## Agent-Specific Context

**superpowers:code-reviewer**: Requires implementation plan context. If no plan exists, skip or use general coding standards.

**code-clarity-reviewer**: Focus on whether code tells a story and is accessible to team members.

**security-privacy-reviewer**: Prioritize user data handling, authentication/authorization, input validation, and logging.

**performance-optimizer**: Look for N+1 queries, inefficient algorithms, unnecessary re-renders, and caching opportunities.

**test-quality-enforcer**: Verify coverage of new/changed code, edge cases, and error conditions.

**documentation-updater**: Check README, API docs, inline docs, and migration guides for accuracy.

**dead-code-cleaner**: Identify unused code, dead functions, orphaned tests, and cleanup opportunities in current changes.

## Example Invocation

When user says "Review my authentication implementation":

1. Check git diff (authentication changes = security-critical)
2. Launch in parallel:
   - All "always run" agents
   - performance-optimizer (auth often has DB queries)
   - test-quality-enforcer (new implementation)
   - documentation-updater (likely API changes)
   - dead-code-cleaner (especially if refactored from old auth pattern)
3. Synthesize findings focusing on security issues
4. Present prioritized feedback

## Important Notes

- **Parallel execution is mandatory** - Always use a single message with multiple Task calls
- **Context matters** - Don't run irrelevant agents (e.g., test-quality-enforcer on README-only changes)
- **Respect scope** - If user wants quick review, ask which aspects to focus on
- **No false reassurance** - If agents find issues, don't minimize them. Report honestly.
