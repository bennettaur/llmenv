# TypeScript Programming Guidelines

## Type Safety
- Use strict TypeScript configuration
- Prefer interfaces over type aliases for object shapes
- Use union types instead of `any` when possible
- Define return types for public functions
- Use generic types for reusable components

## Code Organization
- Use barrel exports (index.ts files) for clean imports
- Organize types in separate files when they're shared
- Use enums for fixed sets of values
- Prefer const assertions for literal types

## Modern JavaScript/TypeScript
- Use async/await over Promises.then()
- Prefer arrow functions for short functions
- Use destructuring for object and array manipulation
- Use template literals for string interpolation
- Prefer `const` and `let` over `var`

## Error Handling
- Use Result/Either patterns for error-prone operations
- Create custom error classes for specific error types
- Validate inputs at boundaries (API endpoints, user inputs)
- Use type guards for runtime type checking

## Performance
- Use lazy loading for large modules
- Implement proper memoization for expensive calculations
- Use React.memo, useMemo, and useCallback appropriately
- Profile and optimize bundle size