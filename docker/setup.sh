#!/bin/bash

# Setup script for vibe-kanban Docker environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo "Setting up vibe-kanban Docker environment..."
echo "============================================"

# Create necessary directories
log_info "Creating directory structure..."
mkdir -p "$PROJECT_ROOT"/{repos,mcp-servers}

# Initialize Claude configuration in Docker volumes (optional)
log_info "Setting up Claude configuration for containers..."

# Note: Configuration is now pre-installed in the Docker image
# These volumes are optional for user customization

# Create volume directories with .gitkeep files
mkdir -p "$PROJECT_ROOT/docker/claude-config"
if [[ ! -f "$PROJECT_ROOT/docker/claude-config/.gitkeep" ]]; then
    cat > "$PROJECT_ROOT/docker/claude-config/.gitkeep" << 'EOF'
# Optional: Add custom Claude Code configuration files here
# If this directory is empty, the container will use the default llmenv configuration
# To customize:
# 1. Run: docker-compose run --rm vibe-kanban llmenv status
# 2. Copy desired configuration files here
# 3. Restart the container
EOF
    log_info "Created Claude configuration volume directory (optional customization)"
fi

mkdir -p "$PROJECT_ROOT/docker/claude-config-dev"
if [[ ! -f "$PROJECT_ROOT/docker/claude-config-dev/.gitkeep" ]]; then
    cat > "$PROJECT_ROOT/docker/claude-config-dev/.gitkeep" << 'EOF'
# Optional: Add custom Claude Code configuration files for development
# This is used by the development container profile
EOF
    log_info "Created development Claude configuration volume directory"
fi

# Create example MCP server configuration
if [[ ! -f "$PROJECT_ROOT/mcp-servers/README.md" ]]; then
    cat > "$PROJECT_ROOT/mcp-servers/README.md" << 'EOF'
# MCP Servers Directory

This directory is mounted into the vibe-kanban container for MCP (Model Context Protocol) server access.

## Structure
```
mcp-servers/
├── server1/
│   ├── package.json
│   └── index.js
└── server2/
    ├── requirements.txt
    └── main.py
```

## Adding MCP Servers
1. Create a subdirectory for each MCP server
2. Include the server implementation and dependencies
3. The container will have access to these servers for tool integration
EOF
    log_info "Created MCP servers directory with documentation"
fi

# Create repos directory info
if [[ ! -f "$PROJECT_ROOT/repos/README.md" ]]; then
    cat > "$PROJECT_ROOT/repos/README.md" << 'EOF'
# Repository Directory

This directory is mounted into the vibe-kanban container as the working directory.

## Usage
- Clone or symlink your repositories here
- vibe-kanban will operate on repositories in this directory
- Claude Code will have access to these repositories for AI coding assistance

## Example
```bash
# Clone a repository
git clone https://github.com/your-org/your-repo.git

# Or create a symlink to an existing local repo
ln -s /path/to/your/local/repo ./your-repo
```
EOF
    log_info "Created repos directory with documentation"
fi

echo ""
log_info "Setup complete! You can now:"
echo "  1. Add repositories to ./repos/"
echo "  2. Add MCP servers to ./mcp-servers/"
echo "  3. Run: docker-compose up vibe-kanban"
echo "  4. Access vibe-kanban at: http://localhost:9001"
echo ""
echo "For development mode:"
echo "  docker-compose --profile dev up vibe-kanban-dev"
echo "  (Runs on http://localhost:9002)"