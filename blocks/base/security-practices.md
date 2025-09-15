# Security Best Practices

## General Security
- Never commit secrets, API keys, or passwords to version control
- Use environment variables for configuration
- Validate all user inputs
- Use parameterized queries to prevent SQL injection
- Implement proper authentication and authorization
- Follow principle of least privilege

## Data Handling
- Encrypt sensitive data at rest and in transit
- Sanitize data before displaying to prevent XSS
- Use HTTPS for all communications
- Implement proper session management
- Hash passwords with appropriate algorithms (bcrypt, Argon2)

## Dependencies
- Keep dependencies up to date
- Audit dependencies regularly for vulnerabilities
- Use dependency scanning tools
- Minimize the number of dependencies
- Pin dependency versions in production