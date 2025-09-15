FROM node:18-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    build-essential \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PORT=9001
ENV NODE_ENV=production
ENV LLMENV_ROOT=/workspace/llmenv

# Install vibe-kanban globally
RUN npm install -g vibe-kanban

# Install Claude Code CLI
# Note: This is a placeholder - actual installation may vary
# You may need to adjust this based on the actual Claude Code installation method
RUN echo "Claude Code installation placeholder - update with actual installation command"

# Create working directory
WORKDIR /workspace

# Create directories for mounted repositories and configuration
RUN mkdir -p /workspace/repos \
    && mkdir -p /root/.claude \
    && mkdir -p /workspace/mcp-servers

# Copy llmenv configuration
COPY templates/ /workspace/llmenv/templates/
COPY blocks/ /workspace/llmenv/blocks/
COPY bin/llmenv /workspace/llmenv/bin/llmenv
COPY scripts/ /workspace/llmenv/scripts/
COPY docker/configure-claude.sh /workspace/llmenv/docker/configure-claude.sh
COPY docker/mcp-setup.sh /workspace/llmenv/docker/mcp-setup.sh

# Make scripts executable
RUN chmod +x /workspace/llmenv/bin/llmenv \
    && chmod +x /workspace/llmenv/docker/configure-claude.sh \
    && chmod +x /workspace/llmenv/docker/mcp-setup.sh \
    && ln -s /workspace/llmenv/bin/llmenv /usr/local/bin/llmenv

# Pre-install Claude Code configuration in the container
RUN cd /workspace/llmenv && ./bin/llmenv install \
    && mkdir -p /workspace/llmenv/docker/default-claude-config \
    && cp -r /root/.claude/* /workspace/llmenv/docker/default-claude-config/

# Expose the port for vibe-kanban
EXPOSE 9001

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "================================="\n\
echo "Vibe Kanban + Claude Code Container"\n\
echo "================================="\n\
\n\
# Configure Claude Code if needed\n\
echo "Configuring Claude Code..."\n\
/workspace/llmenv/docker/configure-claude.sh\n\
\n\
# Setup MCP servers\n\
echo "Setting up MCP servers..."\n\
/workspace/llmenv/docker/mcp-setup.sh\n\
\n\
# Change to repos directory\n\
cd /workspace/repos\n\
\n\
# Start vibe-kanban\n\
echo ""\n\
echo "Starting vibe-kanban on port $PORT..."\n\
echo "Working directory: $(pwd)"\n\
echo "Available repositories:"\n\
ls -la . 2>/dev/null || echo "  No repositories found"\n\
echo ""\n\
\n\
# Run vibe-kanban in foreground\n\
exec vibe-kanban\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]