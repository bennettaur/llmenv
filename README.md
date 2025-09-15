# LLM Environment Management

A modular system for managing prompts, rules, and settings across different LLM tools and programming languages. Uses symlinks to dynamically rendered templates for always-fresh configuration that automatically updates when base templates change.

## Key Features

🔗 **Symlink-based**: Configurations link to dynamically rendered files  
🔄 **Always Fresh**: Templates are re-rendered on demand, ensuring consistency  
📦 **Modular**: Reusable building blocks for different aspects of development  
🎯 **Language-specific**: Easy installation of language-specific rules  
⚡ **Easy Updates**: Single `sync` command updates all existing installations  

## Directory Structure

```
llmenv/
├── blocks/                 # Reusable prompt building blocks
│   ├── base/              # Common prompts (code-structure, pr-guidelines, etc.)
│   └── languages/         # Language-specific prompts (ruby, typescript, react, etc.)
├── templates/             # Tool-specific template files with include directives
│   ├── claude/            # Claude.md templates
│   └── cursor/            # Cursor rules templates
├── rendered/              # Dynamically generated files (gitignored)
│   ├── claude/            # Rendered Claude configurations
│   └── cursor/            # Rendered Cursor rules
├── scripts/               # Helper scripts (template renderer, installation manager)
└── bin/                   # Executable files (llmenv)
```

## Installation

1. **Setup the CLI tool**:
   ```bash
   ./install.sh
   ```

2. **Install base configuration**:
   ```bash
   llmenv install
   ```

3. **Install language-specific rules**:
   ```bash
   llmenv install ruby typescript react
   ```

## Usage

### Core Commands
```bash
llmenv install              # Install base configuration for all tools
llmenv install ruby         # Add Ruby-specific rules
llmenv sync                 # Update all existing installations with latest templates
llmenv list                 # Show available languages and current installations
llmenv status               # Display detailed configuration status
```

### How It Works

1. **Templates**: Stored in `templates/` with `<!-- include: path -->` directives
2. **Rendering**: Templates are processed to resolve includes and language sections
3. **Symlinks**: Target locations link to files in `rendered/` directory
4. **Updates**: `sync` command regenerates all rendered files, automatically updating all linked locations

### Example Workflow

```bash
# Initial setup
llmenv install                    # Sets up ~/.claude/CLAUDE.md -> rendered/claude/CLAUDE.md
llmenv install ruby typescript    # Adds language-specific sections

# Later, when base templates are updated
llmenv sync                       # All existing installations get the updates automatically

# In a new project
llmenv install react             # Adds React rules to existing configuration
```

## Supported Tools
- **Claude**: Global `~/.claude/CLAUDE.md` configuration
- **Cursor**: Project-local `.cursor/rules/rules.md` with automatic .gitignore management

## Supported Languages
- Ruby (Rails conventions, RSpec, best practices)
- TypeScript (type safety, modern JS, error handling)
- React (hooks, performance, testing)
- Terraform (infrastructure as code, security, testing)

## Benefits

✅ **No Sync Issues**: Templates always reflect latest changes  
✅ **Atomic Updates**: All installations update simultaneously  
✅ **Easy Maintenance**: Edit one file, update everywhere  
✅ **Fallback Support**: Automatic copying if symlinks aren't supported  
✅ **Installation Tracking**: JSON-based tracking of what's installed where