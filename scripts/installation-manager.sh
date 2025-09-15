#!/usr/bin/env bash

# Installation tracking and management for LLM environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMENV_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALLATIONS_FILE="$LLMENV_ROOT/.llmenv/installations.json"

# Ensure installations file exists
ensure_installations_file() {
    if [[ ! -f "$INSTALLATIONS_FILE" ]]; then
        mkdir -p "$(dirname "$INSTALLATIONS_FILE")"
        echo '{}' > "$INSTALLATIONS_FILE"
    fi
}

# Get installation info for a tool
get_installation() {
    local tool="$1"
    ensure_installations_file
    
    if command -v jq >/dev/null 2>&1; then
        jq -r ".\"$tool\" // empty" "$INSTALLATIONS_FILE"
    else
        # Fallback without jq
        grep -o "\"$tool\":{[^}]*}" "$INSTALLATIONS_FILE" 2>/dev/null || echo ""
    fi
}

# Record installation
record_installation() {
    local tool="$1"
    local target_path="$2"
    local languages=("${@:3}")
    
    ensure_installations_file
    
    local timestamp=$(date -Iseconds)
    local languages_json="[]"
    
    if [[ ${#languages[@]} -gt 0 ]]; then
        if command -v jq >/dev/null 2>&1; then
            languages_json=$(printf '%s\n' "${languages[@]}" | jq -R . | jq -s .)
        else
            # Simple fallback without jq
            languages_json="[$(printf '"%s",' "${languages[@]}" | sed 's/,$//')]"
        fi
    fi
    
    if command -v jq >/dev/null 2>&1; then
        jq ".\"$tool\" = {
            \"target_path\": \"$target_path\",
            \"languages\": $languages_json,
            \"installed_at\": \"$timestamp\"
        }" "$INSTALLATIONS_FILE" > "$INSTALLATIONS_FILE.tmp" && mv "$INSTALLATIONS_FILE.tmp" "$INSTALLATIONS_FILE"
    else
        # Fallback without jq - simple append/replace
        local new_entry="\"$tool\":{\"target_path\":\"$target_path\",\"languages\":$languages_json,\"installed_at\":\"$timestamp\"}"
        
        if grep -q "\"$tool\":" "$INSTALLATIONS_FILE"; then
            # Replace existing entry (simple approach)
            sed "s/\"$tool\":{[^}]*}/$new_entry/" "$INSTALLATIONS_FILE" > "$INSTALLATIONS_FILE.tmp" && mv "$INSTALLATIONS_FILE.tmp" "$INSTALLATIONS_FILE"
        else
            # Add new entry
            sed 's/}$//; s/$/,'"$new_entry"'}/' "$INSTALLATIONS_FILE" | sed 's/^{,/{/' > "$INSTALLATIONS_FILE.tmp" && mv "$INSTALLATIONS_FILE.tmp" "$INSTALLATIONS_FILE"
        fi
    fi
}

# Remove installation record
remove_installation() {
    local tool="$1"
    ensure_installations_file
    
    if command -v jq >/dev/null 2>&1; then
        jq "del(.\"$tool\")" "$INSTALLATIONS_FILE" > "$INSTALLATIONS_FILE.tmp" && mv "$INSTALLATIONS_FILE.tmp" "$INSTALLATIONS_FILE"
    else
        # Fallback without jq
        sed "/\"$tool\":{[^}]*},*/d" "$INSTALLATIONS_FILE" > "$INSTALLATIONS_FILE.tmp" && mv "$INSTALLATIONS_FILE.tmp" "$INSTALLATIONS_FILE"
    fi
}

# List all installations
list_installations() {
    ensure_installations_file
    
    if command -v jq >/dev/null 2>&1; then
        jq -r 'to_entries[] | "\(.key): \(.value.target_path) (languages: \(.value.languages | join(", ")))"' "$INSTALLATIONS_FILE"
    else
        # Simple fallback
        cat "$INSTALLATIONS_FILE"
    fi
}

# Get languages for a tool
get_languages() {
    local tool="$1"
    ensure_installations_file
    
    if command -v jq >/dev/null 2>&1; then
        jq -r ".\"$tool\".languages[]? // empty" "$INSTALLATIONS_FILE"
    else
        # Fallback parsing
        get_installation "$tool" | grep -o '"languages":\[[^]]*\]' | sed 's/.*\[\(.*\)\].*/\1/' | tr ',' '\n' | sed 's/[" ]//g'
    fi
}

# Main command dispatcher
main() {
    case "${1:-}" in
        get)
            get_installation "$2"
            ;;
        record)
            shift
            record_installation "$@"
            ;;
        remove)
            remove_installation "$2"
            ;;
        list)
            list_installations
            ;;
        languages)
            get_languages "$2"
            ;;
        *)
            echo "Usage: $0 {get|record|remove|list|languages} [args...]" >&2
            exit 1
            ;;
    esac
}

main "$@"