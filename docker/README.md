# Vibe Kanban + Claude Code Docker Setup

A containerized environment for running vibe-kanban with Claude Code integration and MCP server support.

## Features

- **Vibe Kanban**: AI coding agent orchestration platform
- **Claude Code**: Integrated AI development assistant
- **LLM Environment Management**: Unified configuration across tools
- **MCP Server Support**: Extensible tool ecosystem
- **Volume Mounts**: Local repository and configuration access

## Quick Start

1. **Setup the environment**:
   ```bash
   ./docker/setup.sh
   ```

2. **Add repositories to work with**:
   ```bash
   # Clone repositories into the repos directory
   cd repos
   git clone https://github.com/your-org/your-repo.git
   
   # Or symlink existing repositories
   ln -s /path/to/existing/repo ./my-repo
   ```

3. **Start the container**:
   ```bash
   docker-compose up vibe-kanban
   ```

4. **Access vibe-kanban**:
   - Open http://localhost:9001

## Directory Structure

```
llmenv/
├── repos/                  # Repository working directory (mounted)
├── mcp-servers/           # MCP server implementations (mounted)
├── docker/
│   ├── claude-config/     # Production Claude configuration (mounted)
│   ├── claude-config-dev/ # Development Claude configuration (mounted)
│   ├── setup.sh          # Environment setup script
│   ├── configure-claude.sh # Claude Code configuration
│   └── mcp-setup.sh      # MCP server discovery and setup
├── Dockerfile
└── docker-compose.yml
```

## Configuration

### Claude Code Settings

Claude Code is automatically configured with:
- **Settings**: Environment-specific permissions and hooks
- **Agents**: Language-specific sub-agents (Ruby, TypeScript, etc.)
- **LLM Environment**: Integrated prompt management system

Configuration files:
- Production: `./docker/claude-config/`
- Development: `./docker/claude-config-dev/`

### MCP Servers

MCP servers are automatically discovered and configured from `./mcp-servers/`. Supported formats:

**Node.js MCP Server**:
```
mcp-servers/my-tool/
├── package.json
└── index.js
```

**Python MCP Server**:
```
mcp-servers/my-tool/
├── requirements.txt
└── main.py
```

### Environment Variables

- `PORT=9001` - Vibe Kanban server port
- `LLMENV_ROOT=/workspace/llmenv` - LLM environment root
- `NODE_ENV=production|development` - Runtime environment

## Usage Examples

### Production Environment

```bash
# Start production container
docker-compose up vibe-kanban

# View logs
docker-compose logs -f vibe-kanban

# Stop container
docker-compose down
```

### Development Environment

```bash
# Start development container (with additional mounts)
docker-compose --profile dev up vibe-kanban-dev

# Access on port 9002
open http://localhost:9002
```

### Working with Repositories

```bash
# Add a new repository
cd repos
git clone https://github.com/example/project.git

# Container automatically picks up new repositories
docker-compose restart vibe-kanban
```

### Adding MCP Servers

1. **Create MCP server directory**:
   ```bash
   mkdir -p mcp-servers/my-custom-tool
   cd mcp-servers/my-custom-tool
   ```

2. **Add implementation** (Node.js example):
   ```bash
   npm init -y
   npm install @modelcontextprotocol/sdk
   # Add your server implementation to index.js
   ```

3. **Restart container to pick up new server**:
   ```bash
   docker-compose restart vibe-kanban
   ```

### Managing Language-Specific Rules

```bash
# Access container shell
docker-compose exec vibe-kanban bash

# Add language-specific rules
llmenv install react
llmenv install terraform

# Sync configurations
llmenv sync

# Check status
llmenv status
```

## Troubleshooting

### Container Issues

```bash
# View container logs
docker-compose logs vibe-kanban

# Access container shell
docker-compose exec vibe-kanban bash

# Rebuild container
docker-compose build --no-cache vibe-kanban
```

### MCP Server Issues

```bash
# Check MCP server configuration
docker-compose exec vibe-kanban cat /root/.claude/mcp-servers.json

# Manually run MCP setup
docker-compose exec vibe-kanban /workspace/llmenv/docker/mcp-setup.sh
```

### Claude Code Issues

```bash
# Check Claude configuration
docker-compose exec vibe-kanban llmenv status

# Reconfigure Claude
docker-compose exec vibe-kanban /workspace/llmenv/docker/configure-claude.sh
```

## Advanced Configuration

### Custom Claude Settings

Edit `docker/claude-config/settings.json` before starting the container:

```json
{
  "permissions": {
    "allowDataAccess": true,
    "allowNetworkAccess": true,
    "allowExecutableExecution": true
  },
  "env": {
    "CUSTOM_VAR": "value"
  }
}
```

### Custom MCP Server Configuration

Create `mcp-servers/custom-config.json`:

```json
{
  "mcpServers": {
    "custom-tool": {
      "command": "python3",
      "args": ["/workspace/mcp-servers/custom-tool/server.py"],
      "env": {
        "CUSTOM_ENV": "value"
      }
    }
  }
}
```

## Performance Tips

1. **Use .dockerignore** to exclude unnecessary files
2. **Mount specific directories** instead of entire file systems
3. **Use multi-stage builds** for production optimization
4. **Limit container resources** if needed:
   ```bash
   docker-compose up --memory=2g --cpus=2 vibe-kanban
   ```

## Security Considerations

- **Review MCP servers** before adding them to the container
- **Limit network access** in production environments
- **Use read-only mounts** for sensitive directories
- **Regular updates** of base images and dependencies