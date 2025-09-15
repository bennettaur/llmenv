# Ruby Programming Guidelines

## Code Style
- Follow the Ruby Style Guide (https://rubystyle.guide/)
- Use 2 spaces for indentation
- Use snake_case for variables and methods
- Use CamelCase for classes and modules
- Use SCREAMING_SNAKE_CASE for constants

## Ruby Best Practices
- Prefer `String#include?` over `String#match` for simple substring checks
- Use `&:method_name` shorthand for simple blocks
- Prefer `each` over `for` loops
- Use `unless` for negative conditions when it improves readability
- Prefer string interpolation over concatenation

## Rails Conventions
- Follow Rails naming conventions for models, controllers, and views
- Use strong parameters for mass assignment protection
- Prefer ActiveRecord callbacks over manual calls when appropriate
- Use scopes for commonly used queries
- Follow RESTful routing conventions

## Testing with RSpec
- Use descriptive `describe` and `context` blocks
- Use `let` for shared setup
- Prefer `expect().to` over `should` syntax
- Use factories (FactoryBot) for test data
- Test behavior, not implementation

## Gems and Dependencies
- Use Bundler for dependency management
- Keep Gemfile organized with comments
- Use specific version constraints for production
- Regularly update dependencies and check for security issues