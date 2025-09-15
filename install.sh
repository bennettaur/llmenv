#!/usr/bin/env bash

# Installation script for LLM Environment Management Tool

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMENV_ROOT="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    log_error "Unsupported operating system: $OSTYPE"
    exit 1
fi

# Find user's shell profile
detect_shell_profile() {
    local shell_name="$(basename "$SHELL")"
    case "$shell_name" in
        bash)
            if [[ -f "$HOME/.bash_profile" ]]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        zsh)
            echo "$HOME/.zshrc"
            ;;
        fish)
            echo "$HOME/.config/fish/config.fish"
            ;;
        *)
            echo "$HOME/.profile"
            ;;
    esac
}

# Add to PATH if not already there
add_to_path() {
    local bin_dir="$LLMENV_ROOT/bin"
    local profile_file="$(detect_shell_profile)"
    
    # Check if already in PATH
    if echo "$PATH" | grep -q "$bin_dir"; then
        log_info "llmenv is already in PATH"
        return 0
    fi
    
    # Check if already added to profile
    if [[ -f "$profile_file" ]] && grep -q "llmenv/bin" "$profile_file"; then
        log_info "llmenv PATH entry already exists in $profile_file"
        return 0
    fi
    
    # Add to profile
    echo "" >> "$profile_file"
    echo "# LLM Environment Management Tool" >> "$profile_file"
    echo "export PATH=\"$bin_dir:\$PATH\"" >> "$profile_file"
    
    log_info "Added llmenv to PATH in $profile_file"
    log_warn "Please restart your shell or run: source $profile_file"
}

# Main installation
main() {
    log_info "Installing LLM Environment Management Tool..."
    log_info "Installation directory: $LLMENV_ROOT"
    
    # Make sure the binary is executable
    chmod +x "$LLMENV_ROOT/bin/llmenv"
    
    # Add to PATH
    add_to_path
    
    log_info "Installation complete!"
    echo ""
    echo "Usage:"
    echo "  llmenv install           # Install base configuration"
    echo "  llmenv install ruby      # Install Ruby-specific rules"
    echo "  llmenv list              # List available languages"
    echo "  llmenv help              # Show help"
    echo ""
    echo "If the command is not found, restart your shell or run:"
    echo "  source $(detect_shell_profile)"
}

main "$@"