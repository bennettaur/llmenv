#!/bin/bash

# Setup MCP servers in the container environment

set -euo pipefail

MCP_DIR="/workspace/mcp-servers"
CLAUDE_DIR="/root/.claude"

echo "Setting up MCP servers..."

# Create MCP servers directory if it doesn't exist
mkdir -p "$MCP_DIR"

# Discover and configure available MCP servers
configure_mcp_servers() {
    local mcp_config="$CLAUDE_DIR/mcp-servers.json"
    
    echo "Scanning for MCP servers in $MCP_DIR..."
    
    # Start with empty configuration
    cat > "$mcp_config" << 'EOF'
{
  "mcpServers": {}
}
EOF
    
    # Find all MCP server directories
    for server_dir in "$MCP_DIR"/*; do
        if [[ -d "$server_dir" ]]; then
            local server_name="$(basename "$server_dir")"
            echo "Found MCP server: $server_name"
            
            # Check for different server types
            if [[ -f "$server_dir/package.json" ]]; then
                # Node.js MCP server
                echo "  Type: Node.js"
                configure_nodejs_mcp_server "$server_name" "$server_dir" "$mcp_config"
            elif [[ -f "$server_dir/requirements.txt" ]] || [[ -f "$server_dir/main.py" ]]; then
                # Python MCP server
                echo "  Type: Python"
                configure_python_mcp_server "$server_name" "$server_dir" "$mcp_config"
            else
                echo "  Type: Unknown (skipping)"
            fi
        fi
    done
    
    echo "MCP server configuration complete: $mcp_config"
}

configure_nodejs_mcp_server() {
    local name="$1"
    local dir="$2"
    local config="$3"
    
    # Install dependencies if needed
    if [[ -f "$dir/package.json" ]] && [[ ! -d "$dir/node_modules" ]]; then
        echo "  Installing Node.js dependencies..."
        (cd "$dir" && npm install)
    fi
    
    # Add to MCP configuration
    python3 -c "
import json
with open('$config', 'r') as f:
    config = json.load(f)

config['mcpServers']['$name'] = {
    'command': 'node',
    'args': ['$dir/index.js'],
    'cwd': '$dir'
}

with open('$config', 'w') as f:
    json.dump(config, f, indent=2)
"
}

configure_python_mcp_server() {
    local name="$1"
    local dir="$2"
    local config="$3"
    
    # Install dependencies if needed
    if [[ -f "$dir/requirements.txt" ]]; then
        echo "  Installing Python dependencies..."
        pip3 install -r "$dir/requirements.txt"
    fi
    
    # Determine entry point
    local entry_point="main.py"
    if [[ -f "$dir/server.py" ]]; then
        entry_point="server.py"
    elif [[ -f "$dir/app.py" ]]; then
        entry_point="app.py"
    fi
    
    # Add to MCP configuration
    python3 -c "
import json
with open('$config', 'r') as f:
    config = json.load(f)

config['mcpServers']['$name'] = {
    'command': 'python3',
    'args': ['$dir/$entry_point'],
    'cwd': '$dir'
}

with open('$config', 'w') as f:
    json.dump(config, f, indent=2)
"
}

# Create example MCP server if none exist
create_example_mcp_server() {
    local example_dir="$MCP_DIR/example-tools"
    
    if [[ ! -d "$example_dir" ]]; then
        echo "Creating example MCP server..."
        mkdir -p "$example_dir"
        
        # Create a simple Node.js MCP server
        cat > "$example_dir/package.json" << 'EOF'
{
  "name": "example-tools-mcp-server",
  "version": "1.0.0",
  "description": "Example MCP server with basic tools",
  "main": "index.js",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0"
  }
}
EOF
        
        cat > "$example_dir/index.js" << 'EOF'
#!/usr/bin/env node

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');

const server = new Server(
  {
    name: "example-tools",
    version: "1.0.0"
  },
  {
    capabilities: {
      tools: {}
    }
  }
);

// Add a simple tool
server.setRequestHandler("tools/list", async () => {
  return {
    tools: [
      {
        name: "echo",
        description: "Echo back the input text",
        inputSchema: {
          type: "object",
          properties: {
            text: {
              type: "string",
              description: "Text to echo back"
            }
          },
          required: ["text"]
        }
      }
    ]
  };
});

server.setRequestHandler("tools/call", async (request) => {
  const { name, arguments: args } = request.params;
  
  if (name === "echo") {
    return {
      content: [
        {
          type: "text",
          text: `Echo: ${args.text}`
        }
      ]
    };
  }
  
  throw new Error(`Unknown tool: ${name}`);
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Example MCP server running on stdio");
}

main().catch(console.error);
EOF
        
        echo "Created example MCP server at $example_dir"
    fi
}

# Main execution
if [[ ! -d "$MCP_DIR" ]] || [[ -z "$(ls -A "$MCP_DIR" 2>/dev/null)" ]]; then
    create_example_mcp_server
fi

configure_mcp_servers

echo "MCP server setup complete!"
echo "Available servers:"
if [[ -f "$CLAUDE_DIR/mcp-servers.json" ]]; then
    python3 -c "
import json
with open('$CLAUDE_DIR/mcp-servers.json', 'r') as f:
    config = json.load(f)
for name in config.get('mcpServers', {}):
    print(f'  - {name}')
"
else
    echo "  No MCP servers configured"
fi