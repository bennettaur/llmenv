FROM node:22-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    build-essential \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install additional development tools
RUN curl -fsSL https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -o /usr/local/bin/yq \
    && chmod +x /usr/local/bin/yq \
    && curl -fsSL https://github.com/junegunn/fzf/releases/download/0.44.1/fzf-0.44.1-linux_amd64.tar.gz | tar -xz -C /usr/local/bin \
    && curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.0.3/ripgrep-14.0.3-x86_64-unknown-linux-musl.tar.gz | tar -xz --strip-components=1 -C /usr/local/bin ripgrep-14.0.3-x86_64-unknown-linux-musl/rg

# Set environment variables
ENV PORT=9001
ENV NODE_ENV=production
ENV LLMENV_ROOT=/workspace/llmenv

# Install vibe-kanban globally
RUN npm install -g vibe-kanban

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

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
COPY docker/entrypoint.sh /entrypoint.sh

# Make scripts executable
RUN chmod +x /workspace/llmenv/bin/llmenv \
    && chmod +x /workspace/llmenv/docker/configure-claude.sh \
    && chmod +x /workspace/llmenv/docker/mcp-setup.sh \
    && chmod +x /entrypoint.sh \
    && ln -s /workspace/llmenv/bin/llmenv /usr/local/bin/llmenv

# Pre-render Claude Code configuration templates without installation tracking
RUN cd /workspace/llmenv \
    && mkdir -p /workspace/llmenv/rendered/claude /workspace/llmenv/rendered/claude-code/agents \
    && ./scripts/render-template.sh ./templates/claude/CLAUDE.md > /workspace/llmenv/rendered/claude/CLAUDE.md \
    && ./scripts/render-template.sh ./templates/claude-code/settings.json > /workspace/llmenv/rendered/claude-code/settings.json \
    && for agent in ./templates/claude-code/agents/*.md; do \
        ./scripts/render-template.sh "$agent" > "/workspace/llmenv/rendered/claude-code/agents/$(basename "$agent")"; \
    done \
    && mkdir -p /workspace/llmenv/docker/default-claude-config/agents \
    && cp /workspace/llmenv/rendered/claude/CLAUDE.md /workspace/llmenv/docker/default-claude-config/ \
    && cp /workspace/llmenv/rendered/claude-code/settings.json /workspace/llmenv/docker/default-claude-config/ \
    && cp /workspace/llmenv/rendered/claude-code/agents/* /workspace/llmenv/docker/default-claude-config/agents/

# Expose the port for vibe-kanban
EXPOSE 9001

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]