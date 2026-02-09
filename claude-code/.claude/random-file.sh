#!/usr/bin/env bash

set -euo pipefail

# Script to randomly pick a file from a directory
# Usage: random-file <directory>

show_usage() {
    echo "Usage: $(basename "$0") <directory>"
    echo "Randomly selects one file from the specified directory"
    exit 1
}

# Check if directory argument was provided
if [ $# -eq 0 ]; then
    echo "Error: No directory specified" >&2
    show_usage
fi

DIR="$1"

# Check if the directory exists
if [ ! -d "$DIR" ]; then
    echo "Error: '$DIR' is not a valid directory" >&2
    exit 1
fi

# Get all files (not directories) in the specified directory
# Using an array to handle filenames with spaces
mapfile -t files < <(find "$DIR" -maxdepth 1 -type f)

# Check if there are any files
if [ ${#files[@]} -eq 0 ]; then
    echo "Error: No files found in '$DIR'" >&2
    exit 1
fi

# Randomly select one file
random_index=$((RANDOM % ${#files[@]}))
selected_file="${files[$random_index]}"

# Output the selected file
echo "$selected_file"
