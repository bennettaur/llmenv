# Code Structure and Organization

## General Principles
- Use clear, descriptive names for variables, functions, and classes
- Follow the principle of least surprise - code should do what it looks like it does
- **NEW**: Write self-documenting code that tells a story
- Prefer composition over inheritance
- Keep functions small and focused on a single responsibility
- Use consistent indentation and formatting
- Group related functionality together

## Naming Conventions
- Use descriptive names that explain intent, not implementation
- Avoid abbreviations unless they're widely understood
- Use verb-noun patterns for functions (e.g., `getUserById`, `validateEmail`)
- Use nouns for classes and data structures
- Use UPPER_CASE for constants
- Use camelCase for variables and functions (unless language conventions dictate otherwise)

## File Organization
- One primary class/component per file
- Group related files in directories by feature or domain
- Use index files to create clean import paths
- Keep configuration files at the root or in a dedicated config directory