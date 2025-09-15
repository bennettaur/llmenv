#!/bin/bash

# Configure Claude Code in the container environment

set -euo pipefail

CLAUDE_DIR="/root/.claude"
LLMENV_ROOT="${LLMENV_ROOT:-/workspace/llmenv}"

echo "Configuring Claude Code in container..."

# Ensure Claude directory exists
mkdir -p "$CLAUDE_DIR"

# Check if we have user-mounted configuration or need to use defaults
if [[ ! -f "$CLAUDE_DIR/settings.json" ]]; then
    echo "No user configuration found, using default llmenv configuration..."
    
    # Copy pre-installed default configuration
    if [[ -d "/workspace/llmenv/docker/default-claude-config" ]]; then
        cp -r /workspace/llmenv/docker/default-claude-config/* "$CLAUDE_DIR/"
        echo "Copied default Claude Code configuration"
    else
        # Fallback: generate fresh configuration
        echo "Generating fresh llmenv configuration..."
        cd "$LLMENV_ROOT"
        LLMENV_ROOT="$LLMENV_ROOT" ./bin/llmenv install
        echo "Fresh Claude Code configuration installed"
    fi
else
    echo "Using mounted Claude Code configuration"
fi

# Update configuration with container-specific settings
if [[ -f "$CLAUDE_DIR/settings.json" ]]; then
    echo "Updating container-specific settings..."
    
    # Create a temporary updated config with container paths
    python3 -c "
import json
import os

config_path = '$CLAUDE_DIR/settings.json'
with open(config_path, 'r') as f:
    config = json.load(f)

# Update paths for container environment
config['env']['LLMENV_ROOT'] = '$LLMENV_ROOT'
config['env']['WORKSPACE_ROOT'] = '/workspace'
config['env']['REPOS_DIR'] = '/workspace/repos'
config['env']['MCP_SERVERS_DIR'] = '/workspace/mcp-servers'

# Add container-specific hooks if they don't exist
if 'hooks' not in config:
    config['hooks'] = {}

config['hooks']['containerInit'] = {
    'command': 'echo \"Container environment initialized\"',
    'description': 'Container initialization hook'
}

# Update agent paths to include container directories
if 'agents' in config and 'paths' in config['agents']:
    config['agents']['paths'] = [
        '~/.claude/agents',
        '/workspace/llmenv/templates/claude-code/agents'
    ]

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print('Container configuration updated')
"
fi

# List available configuration
echo ""
echo "Claude Code configuration summary:"
echo "- Settings: $CLAUDE_DIR/settings.json"
echo "- Agents directory: $CLAUDE_DIR/agents/"
echo "- Available agents:"
ls -1 "$CLAUDE_DIR/agents/" 2>/dev/null | sed 's/^/  - /' || echo "  No agents found"
echo "- LLMENV_ROOT: $LLMENV_ROOT"
echo "- Working directory: /workspace/repos"