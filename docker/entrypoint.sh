#!/bin/bash

set -e

# Activate mise environment
eval "$(mise activate bash)"

echo "================================="
echo "Vibe Kanban + Claude Code Container"
echo "================================="

# Setup MCP servers
echo "Setting up MCP servers..."
/workspace/llmenv/docker/mcp-setup.sh

# Change to repos directory
cd /workspace/repos

# Start vibe-kanban
echo ""
echo "Starting vibe-kanban on port $PORT..."
echo "Working directory: $(pwd)"
echo "Available repositories:"
ls -la . 2>/dev/null || echo "  No repositories found"
echo ""

# Run vibe-kanban in foreground
exec vibe-kanban