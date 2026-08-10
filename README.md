# LLM Environment Management

A modular system for managing Claude Code configuration using GNU stow for symlink management and layered settings merging. Provides a clean separation between base, personal, and work configurations.

## Key Features

🔗 **Stow-based**: Simple symlink management using industry-standard tool
🎯 **Layered Settings**: Base → Personal → Work configuration merging
📦 **Modular**: Organized skills, agents, and commands
🔄 **Auto-merge**: Git hooks automatically merge settings after pulls
🐳 **Docker-ready**: Mount readonly configuration in containers

## Directory Structure

```
llmenv/
├── claude-code/           # Stow package for Claude Code configuration
│   └── .claude/           # Configuration directory (stowed to ~/.claude/)
│       ├── CLAUDE.md                      # Consolidated guidelines
│       ├── settings.base.json             # Base configuration (committed)
│       ├── settings.personal.json         # Personal overrides (committed)
│       ├── settings.wealthsimple.json     # Work config (gitignored)
│       ├── settings.json                  # Merged output (gitignored, generated)
│       ├── skills/                        # Skills (each in own directory)
│       │   ├── perform-review/SKILL.md
│       │   ├── pr-wrapup/SKILL.md
│       │   ├── react/SKILL.md
│       │   ├── reading-jira-tickets/SKILL.md
│       │   ├── refactor-pr-mergeability/SKILL.md
│       │   ├── ruby/SKILL.md
│       │   ├── terraform/SKILL.md
│       │   └── typescript/SKILL.md
│       └── agents/                        # Specialized agents (10 total)
│           ├── code-clarity-reviewer.md
│           ├── code-reviewer.md
│           ├── dead-code-cleaner.md
│           ├── documentation-updater.md
│           ├── performance-optimizer.md
│           ├── pr-readiness-assessment.md
│           ├── ruby-expert.md
│           ├── security-privacy-reviewer.md
│           ├── test-quality-enforcer.md
│           └── typescript-expert.md
├── bin/
│   └── merge-settings     # Python script for recursive settings merge
├── scripts/
│   └── hooks/
│       └── post-merge     # Git hook for auto-merge
├── tools/                 # Standalone tools — not stowed, each its own project
│   └── code-review-interview/  # Phased interview → Code Review Style doc
└── docker/                # Docker setup files
```

## Tools

`tools/` holds standalone programs rather than configuration. They are not part of the
stow package and are not symlinked anywhere — each is its own project, run from its own
directory.

- **[code-review-interview](tools/code-review-interview/)** — interviews you about how
  you review code across three phases, then writes a Code Review Style doc you can hand
  to another LLM. A `uv` project: `cd tools/code-review-interview && uv sync && uv run
  code-review-interview run`.

## Installation

### 1. Install Configuration with Stow

Use GNU stow to symlink the `.claude` directory to your home directory:

```bash
# From the llmenv directory
cd /path/to/llmenv
stow -t ~ claude-code
```

This creates `~/.claude/` as a symlink to `llmenv/claude-code/.claude/`.

### 2. Merge Settings

Generate the final `settings.json` by merging base, personal, and work settings:

```bash
# Add llmenv/bin to your PATH (or use full path)
export PATH="$PATH:/path/to/llmenv/bin"

# Merge settings
merge-settings --verbose
```

### 3. Setup Git Hook (Optional but Recommended)

Auto-merge settings after git operations:

```bash
# From the llmenv directory
ln -s ../../scripts/hooks/post-merge .git/hooks/post-merge
```

## Configuration

### Layered Settings

Settings are merged in order: **base → personal → work**

1. **Base Settings** (`settings.base.json`): Core configuration, committed to repo
2. **Personal Settings** (`settings.personal.json`): Your personal overrides, committed to repo
3. **Work Settings** (`settings.wealthsimple.json`): Work-specific config, gitignored

**Merge Rules:**
- Nested objects: Deep recursive merge
- Arrays: Concatenate (useful for `statusLine.context`)
- Primitives: Last value wins

### Example: Adding Personal Settings

Edit `claude-code/.claude/settings.personal.json`:

```json
{
  "statusLine": {
    "context": [
      "My custom status line item"
    ]
  },
  "hooks": {
    "myCustomHook": {
      "command": "echo 'Hello from personal config'",
      "description": "My personal hook"
    }
  }
}
```

Then merge:

```bash
merge-settings --verbose
```

### Example: Adding Work Settings

Create `claude-code/.claude/settings.wealthsimple.json`:

```json
{
  "enabledPlugins": {
    "superpowers@ws-claude-marketplace": true
  },
  "extraKnownMarketplaces": {
    "ws-claude-marketplace": {
      "source": {
        "source": "github",
        "repo": "wealthsimple/ws-claude-marketplace"
      }
    }
  }
}
```

Then merge:

```bash
merge-settings --verbose
```

## Usage

### merge-settings Command

```bash
# Basic merge with defaults
merge-settings

# Verbose output showing merge operations
merge-settings --verbose

# Dry run to preview merged output
merge-settings --dry-run

# Custom file locations
merge-settings -b ~/.claude/settings.base.json -p ~/.claude/settings.personal.json
```

**Options:**
- `-o, --output`: Output file (default: `~/.claude/settings.json`)
- `-b, --base`: Base settings file (default: `~/.claude/settings.base.json`)
- `-p, --personal`: Personal settings file (default: `~/.claude/settings.personal.json`)
- `-w, --work`: Work settings file (default: `~/.claude/settings.wealthsimple.json`)
- `--dry-run`: Print merged output without writing
- `-v, --verbose`: Show detailed merge operations

### Updating Configuration

Since `.claude` is a symlink to the repo, you can edit files directly:

```bash
# Edit base guidelines
vim ~/.claude/CLAUDE.md

# Edit a skill
vim ~/.claude/skills/typescript.md

# Edit an agent
vim ~/.claude/agents/code-reviewer.md

# Merge settings after changes
merge-settings --verbose
```

Changes are immediately reflected in Claude Code since it reads from the symlinked location.

### Uninstalling

```bash
# Remove symlink
stow -D -t ~ claude-code

# Remove generated settings
rm ~/.claude/settings.json
```

## Docker Setup

The Docker container mounts the `.claude` directory as readonly:

```yaml
volumes:
  - ./claude-code/.claude:/home/llmuser/.claude:ro
```

**Building and Running:**

```bash
# Build container
docker-compose build

# Start container
docker-compose up

# Verify configuration
docker-compose exec llmenv ls -la ~/.claude
```

## Available Skills

Skills are automatically loaded by Claude Code:

- **perform-review**: Orchestrates parallel code review agents for comprehensive feedback
- **pr-wrapup**: Creates PRs and monitors CI
- **react**: React development patterns
- **reading-jira-tickets**: Read and search JIRA tickets from the command line
- **refactor-pr-mergeability**: Refactors large branches into smaller, logical commits or PR stacks
- **ruby**: Ruby and Rails development
- **terraform**: Infrastructure-as-code guidelines
- **typescript**: TypeScript and modern JavaScript development

## Available Agents

Specialized agents for different tasks:

- **code-clarity-reviewer**: Reviews code clarity and readability
- **code-reviewer**: Reviews code for best practices and maintainability
- **dead-code-cleaner**: Identifies dead, unused, or poorly utilized code
- **documentation-updater**: Updates documentation after code changes
- **performance-optimizer**: Identifies performance optimization opportunities
- **pr-readiness-assessment**: Assesses whether a branch is ready for PR review
- **ruby-expert**: Ruby and Rails specialist
- **security-privacy-reviewer**: Reviews code for security vulnerabilities
- **test-quality-enforcer**: Verifies test coverage and quality
- **typescript-expert**: TypeScript development specialist

## Benefits

✅ **Simple**: Uses standard tools (stow, git hooks)
✅ **Flexible**: Easy to add personal or work-specific settings
✅ **Transparent**: All files are real, no template rendering
✅ **Maintainable**: Direct editing of markdown files
✅ **Docker-friendly**: Simple readonly mount
✅ **Version Control**: Base and personal configs are tracked

## Migration from Old System

If you previously used the template-based system:

1. Backup current `~/.claude/` directory
2. Remove old symlinks: `stow -D -t ~ claude-code` (if exists)
3. Follow installation steps above
4. The old `blocks/` and `templates/` directories are no longer used

## Troubleshooting

**Settings not updating?**
- Run `merge-settings --verbose` to see detailed merge operations
- Check that base settings file exists: `ls ~/.claude/settings.base.json`

**Stow conflicts?**
- Stow won't overwrite existing files
- Backup and remove existing `~/.claude/` directory first

**Git hook not working?**
- Verify hook is executable: `ls -l .git/hooks/post-merge`
- Check that `merge-settings` is in your PATH
- Test manually: `.git/hooks/post-merge`

## Contributing

To add new skills, agents, or commands:

1. Create file in appropriate directory (`skills/`, `agents/`, `commands/`)
2. Follow existing file format and frontmatter structure
3. Commit to repository
4. Changes are immediately available after `git pull` (if using git hook)
