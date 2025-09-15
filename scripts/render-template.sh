#!/usr/bin/env bash

# Template renderer for LLM environment management
# Processes includes and language-specific sections dynamically

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMENV_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Process include statements, language conditionals, and environment variables
process_template() {
    local template_file="$1"
    local languages=("${@:2}")  # Remaining args are enabled languages
    
    if [[ ! -f "$template_file" ]]; then
        log_error "Template file not found: $template_file"
        return 1
    fi
    
    local current_dir="$(dirname "$template_file")"
    local in_language_section=false
    local current_language=""
    local language_enabled=false
    
    while IFS= read -r line; do
        # Handle include statements: <!-- include: path -->
        if [[ $line =~ ^[[:space:]]*\<!--[[:space:]]*include:[[:space:]]*([^[:space:]]+)[[:space:]]*--\>[[:space:]]*$ ]]; then
            local include_path="${BASH_REMATCH[1]}"
            local full_path=""
            
            # Handle relative paths
            if [[ "$include_path" = /* ]]; then
                full_path="$include_path"
            else
                full_path="$current_dir/$include_path"
            fi
            
            if [[ -f "$full_path" ]]; then
                cat "$full_path"
                echo ""  # Add newline after include
            else
                log_warn "Include file not found: $full_path"
                echo "$line"
            fi
            continue
        fi
        
        # Handle language section markers: <!-- language-includes-start -->
        if [[ $line =~ language-includes-start ]]; then
            in_language_section=true
            echo "$line"
            
            # Add language-specific includes
            for lang in "${languages[@]}"; do
                local lang_file="$LLMENV_ROOT/blocks/languages/$lang.md"
                if [[ -f "$lang_file" ]]; then
                    echo ""
                    echo "## $lang Guidelines"
                    echo "<!-- include: $lang_file -->"
                    cat "$lang_file"
                    echo ""
                fi
            done
            continue
        fi
        
        # Handle language section end: <!-- language-includes-end -->
        if [[ $line =~ language-includes-end ]]; then
            in_language_section=false
            echo "$line"
            continue
        fi
        
        # Skip content between language markers (it will be regenerated)
        if [[ "$in_language_section" == true ]]; then
            # Skip existing language content - it will be regenerated above
            continue
        fi
        
        # Handle language-specific conditional sections: <!-- if:language -->
        if [[ $line =~ ^[[:space:]]*\<!--[[:space:]]*if:([^[:space:]]+)[[:space:]]*--\>[[:space:]]*$ ]]; then
            current_language="${BASH_REMATCH[1]}"
            language_enabled=false
            
            # Check if this language is enabled
            for lang in "${languages[@]}"; do
                if [[ "$lang" == "$current_language" ]]; then
                    language_enabled=true
                    break
                fi
            done
            
            # Don't output the conditional marker
            continue
        fi
        
        # Handle end of language conditional: <!-- /if:language -->
        if [[ $line =~ ^[[:space:]]*\<!--[[:space:]]*/if:([^[:space:]]+)[[:space:]]*--\>[[:space:]]*$ ]]; then
            current_language=""
            language_enabled=false
            continue
        fi
        
        # Output line if not in a disabled language section
        if [[ "$current_language" == "" ]] || [[ "$language_enabled" == true ]]; then
            # Process environment variable substitutions: <!-- env:VAR_NAME -->
            local processed_line="$line"
            if [[ "$line" =~ \<!--[[:space:]]*env:([^[:space:]]+)[[:space:]]*--\> ]]; then
                local env_var="${BASH_REMATCH[1]}"
                local env_value=""
                case "$env_var" in
                    LLMENV_ROOT)
                        env_value="$LLMENV_ROOT"
                        ;;
                    *)
                        env_value="${!env_var:-}"
                        ;;
                esac
                processed_line="${processed_line//<!-- env:$env_var -->/$env_value}"
            fi
            echo "$processed_line"
        fi
        
    done < "$template_file"
}

# Main function
main() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <template_file> [language1] [language2] ..." >&2
        exit 1
    fi
    
    local template_file="$1"
    shift
    local languages=("$@")
    
    process_template "$template_file" "${languages[@]}"
}

main "$@"