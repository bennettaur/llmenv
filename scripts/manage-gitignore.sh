#!/usr/bin/env bash

# Helper script for managing .gitignore entries for cursor rules

set -euo pipefail

# Add gitignore entries to a file if they don't already exist
add_gitignore_entries() {
    local gitignore_file="$1"
    local entries_file="$2"
    
    # Create .gitignore if it doesn't exist
    if [[ ! -f "$gitignore_file" ]]; then
        touch "$gitignore_file"
    fi
    
    # Check if the entries already exist
    local needs_update=false
    while IFS= read -r entry; do
        if [[ -n "$entry" ]] && ! grep -qF "$entry" "$gitignore_file"; then
            needs_update=true
            break
        fi
    done < "$entries_file"
    
    # Add entries if needed
    if [[ "$needs_update" == true ]]; then
        echo "" >> "$gitignore_file"
        echo "# LLM Environment managed files" >> "$gitignore_file"
        cat "$entries_file" >> "$gitignore_file"
        echo "Added LLM environment entries to $gitignore_file"
    else
        echo "LLM environment entries already exist in $gitignore_file"
    fi
}

# Remove gitignore entries from a file
remove_gitignore_entries() {
    local gitignore_file="$1"
    local entries_file="$2"
    
    if [[ ! -f "$gitignore_file" ]]; then
        return 0
    fi
    
    # Create a temporary file with entries removed
    local temp_file=$(mktemp)
    cp "$gitignore_file" "$temp_file"
    
    while IFS= read -r entry; do
        if [[ -n "$entry" ]]; then
            sed -i.bak "/^$(echo "$entry" | sed 's/[[\.*^$()+?{|]/\\&/g')$/d" "$temp_file"
            rm -f "$temp_file.bak"
        fi
    done < "$entries_file"
    
    # Also remove the comment line if it exists
    sed -i.bak '/^# LLM Environment managed files$/d' "$temp_file"
    rm -f "$temp_file.bak"
    
    # Replace original file if changes were made
    if ! cmp -s "$gitignore_file" "$temp_file"; then
        mv "$temp_file" "$gitignore_file"
        echo "Removed LLM environment entries from $gitignore_file"
    else
        rm "$temp_file"
    fi
}

# Main function
main() {
    local action="$1"
    local gitignore_file="$2"
    local entries_file="$3"
    
    case "$action" in
        add)
            add_gitignore_entries "$gitignore_file" "$entries_file"
            ;;
        remove)
            remove_gitignore_entries "$gitignore_file" "$entries_file"
            ;;
        *)
            echo "Usage: $0 {add|remove} <gitignore_file> <entries_file>"
            exit 1
            ;;
    esac
}

main "$@"