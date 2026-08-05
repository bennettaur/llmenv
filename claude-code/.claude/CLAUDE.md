# Claude Configuration

This file contains my preferred settings and guidelines for Claude interactions.

# Agent Behavior & Conventions

## Human-Agent Relationship

**Human Capabilities:**

- Evaluating solutions
- Final decision making

**Agent Capabilities:**

- Log analysis and debugging
- Code implementation
- Pattern recognition

**Agent Limitations:**

- Cannot make architectural decisions without approval
- **_Must_** admit knowledge gaps

## Interaction Protocols

### General conversation style

- DO NOT BE OVERLY PEDANTIC
- Be honest, the human can be wrong, if you think the human's suggestion is wrong, call it out and provide an explanation
- If you're being told you're hallucinating, assume the human is right unless you can provide proof as to why you are not
- You can challenge ideas and assumptions from the human, ask clarifying questions, and create better understanding

### Complexity Detection

**Ask for confirmation when:**

- Solution requires fighting framework conventions
- Meta-programming becomes necessary
- Writing significant code without clear requirements
- Multiple valid approaches exist

**Required action:**

1. Stop work
2. Summarize current progress
3. Present options with trade-offs
4. Wait for user decision

### Escalation Triggers

**Signs of overly complex solution:**

- Working against framework patterns
- Creating abstraction layers to avoid fixing root cause
- Generating significant code without issue tracking
- Rewriting instead of modifying existing code

**Response:** Request confirmation before proceeding.

### Writing Style

**Required:**

- Clear and direct language
- Admit uncertainty explicitly

**Forbidden:**

- Claims of "robust", "thorough", or "comprehensive"
- Vague or hedging language when clarity is possible
- Temporal references in code comments ("recently changed", "new implementation")

## Code Modification Rules

### Change Scope

**CRITICAL RULE:** Only make changes directly related to assigned task.

### Rewrite Prohibition

**FORBIDDEN:** Throwing away existing implementation and rewriting from scratch.

**Required process:**

1. STOP before rewriting
2. Request explicit permission from user
3. Explain why rewrite is necessary
4. Wait for approval

**Exception:** User explicitly requests rewrite.

### Comment Management

**Default to no comment.** A comment must earn its place. If a better name or a
smaller function removes the need for it, do that instead.

**Comment the WHY, not the WHAT:**

- Business rules and the reasoning behind them ("regulator requires T+2
  settlement", "free tier capped at 5 to match billing plan")
- Why this approach over the obvious alternative ("sequential because the
  upstream API rate-limits concurrent writes")
- Non-obvious constraints, invariants, and consequences of changing the code
- Links to tickets, RFCs, specs, or upstream bug reports that carry the context
- The WHAT only when the code itself is genuinely hard to follow — dense
  algorithms, bit manipulation, non-obvious math, gnarly regex

**Be succinct:**

- One or two lines is the target. A paragraph needs justification
- No restating the code in English (`// increment counter` above `counter++`)
- No section-header or step-by-step banners narrating obvious control flow
  (`// Step 1: validate input`)
- Trim, don't stack: prefer editing an existing comment over adding another
  next to it

**Docblocks follow the language and codebase convention:**

- Where the language expects docblocks for public API (Python docstrings,
  Ruby YARD, Go doc comments, JSDoc/TSDoc), write them. They feed generated
  documentation and IDE tooling — that's a real consumer, not clutter
- Use the exact format the codebase already uses (Google-style, NumPy,
  reStructuredText, etc.). Match the surrounding files, not a personal
  preference
- Document every parameter, return value, and raised exception the convention
  calls for. Explain what each parameter *means* — its units, valid range,
  ownership, side effects — rather than restating its name and type
- Keep the summary line to one sentence. The succinctness rules above still
  apply to the prose inside a docblock
- Where the language and codebase do not use docblocks, don't introduce them

**Evergreen — describe the current state only:**

- No temporal context: "recently changed", "new implementation", "after
  refactor", "was previously", "now uses", "moved from"
- No change narration or migration history — that belongs in git and the PR
- No AI reasoning artifacts: don't explain what you tried, why you chose the
  approach during this session, or address the reviewer ("note that I've...",
  "as requested", "keeping this for backwards compat with the old version").
  Durable design rationale is fine; session narrative is not
- No TODO/FIXME referencing this session's work. Real TODOs need a ticket
  reference
- A comment must read correctly to someone seeing the file for the first time,
  with no knowledge of its history

**NEVER:**

- Remove comments unless provably false or made obsolete by the change
- Comment out code (delete instead)
- Leave commented code in place

**ALWAYS:**

- Preserve existing comments
- Keep comments relevant to file context
- Match the comment density and style already present in the file

### Code Style

**Primary concern:** Consistency within existing file.

**Priority order:**

1. Consistency with existing file
2. Readability and maintainability
3. Performance
4. Conciseness

# Completing a session

When you believe you've implemented the user's intent for the session, proceed autonomously — do not wait to be told — to get as close to a complete PR as possible:

1. Commit the work.
2. Run the self-review agents and address valid feedback (see Pull Request Guidelines below).
3. Push up a draft PR.

Still honor the mid-work gates in Complexity Detection and Rewrite Prohibition — those pauses apply while implementing, not to this completion flow.

# Interacting with Github

Use the `gh` CLI tool to interact with Github PRs.
ALWAYS push PRs up as drafts, unless explicitely instructed to do otherwise

## Code Structure and Organization

### General Principles
- Use clear, descriptive names for variables, functions, and classes
- Follow the principle of least surprise - code should do what it looks like it does
- **NEW**: Write self-documenting code that tells a story
- Prefer composition over inheritance
- Keep functions small and focused on a single responsibility
- Use consistent indentation and formatting
- Group related functionality together

### Naming Conventions
- Use descriptive names that explain intent, not implementation
- Avoid abbreviations unless they're widely understood
- Use verb-noun patterns for functions (e.g., `getUserById`, `validateEmail`)
- Use nouns for classes and data structures
- Use UPPER_CASE for constants
- Use camelCase for variables and functions (unless language conventions dictate otherwise)

#### Lockfile registry hygiene (IMPORTANT)
My machine's package managers may resolve through a private/internal registry
proxy. Committing a lockfile generated locally can pin every package's tarball
URL to that internal proxy, which public/CI runners cannot reach — they then
fail with `403 Forbidden` on every package during install.

- **Any time you add, remove, or update a dependency** (`bun add`, `npm install`,
  `yarn add`, etc.), inspect the lockfile (`bun.lock`, `package-lock.json`,
  `yarn.lock`) before committing and confirm resolved sources point at the
  **public registry** (`https://registry.npmjs.org/`), not an internal host.
- If the lockfile pins internal-proxy URLs, rewrite the host prefix back to the
  public registry. Internal proxies mirror npm's path layout and integrity
  hashes are content-addressed, so this is a safe source swap; verify with
  `bun install --frozen-lockfile` (or the equivalent) afterward.
- Quick check before committing a lockfile: every resolved URL should be on the
  public registry host, with no internal/corporate hostnames present.

### File Organization
- One primary class/component per file
- Group related files in directories by feature or domain
- Use index files to create clean import paths
- Keep configuration files at the root or in a dedicated config directory

## Pull Request Guidelines
- Run the `/do-code-review` skill for a thorough self-review of the code. Assess any feedback it returns for validity and whether it impacts the goal of our implementation. If you're unsure, ask the user about the validity of the feedback
- Use the pr-readiness-assessment agent to determine whether we are ready to submit a high-quality PR
- If we are indeed ready to submit a PR, use the pr-wrapup skill

## Testing Best Practices

### Test Structure
- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern
- One assertion per test when possible
- Group related tests in describe/context blocks

### Test Coverage
- Aim for high test coverage but focus on critical paths
- Test edge cases and error conditions
- Include integration tests for key workflows
- Mock external dependencies appropriately

### Test Organization
- Mirror the source code directory structure in tests
- Use factory patterns for test data creation
- Keep test data minimal and relevant
- Use beforeEach/setUp for common test setup

### Performance Testing
- Include performance tests for critical operations
- Set reasonable timeout limits
- Test with realistic data volumes
- Monitor and benchmark key metrics

## Security Best Practices

### General Security
- Never commit secrets, API keys, or passwords to version control
- Use environment variables for configuration
- Validate all user inputs
- Use parameterized queries to prevent SQL injection
- Implement proper authentication and authorization
- Follow principle of least privilege

### Data Handling
- Encrypt sensitive data at rest and in transit
- Sanitize data before displaying to prevent XSS
- Use HTTPS for all communications
- Implement proper session management
- Hash passwords with appropriate algorithms (bcrypt, Argon2)

### Dependencies
- Keep dependencies up to date
- Audit dependencies regularly for vulnerabilities
- Use dependency scanning tools
- Minimize the number of dependencies
- Pin dependency versions in production

## Communication Preferences
- Be concise and direct
- Provide examples when explaining concepts
- Ask clarifying questions when requirements are unclear
- Suggest improvements and best practices
- Focus on maintainable and readable code

## Tool Preferences
- Use existing libraries and frameworks when available
- Follow established patterns in the codebase
- Prefer TypeScript over JavaScript when available
- Use descriptive variable and function names
- Include appropriate error handling

# Tracking our work
If you have access to a Notion MCP, we keep our work tracked in this notion doc: https://www.notion.so/wealthsimple/What-is-Mike-B-up-to-1f541167bd9680af9bc2c1ce1fa115c2?source=copy_link#30b41167bd968007a475eb20d91dc767 and specifically tracking active work inside a toggle heading with the title `Active Log`. Completed items can be moved inside another toggle heading labeled `Done`. Finally, if the user mentions we should brag about something, add it inside the toggle heading `Brag Doc`
