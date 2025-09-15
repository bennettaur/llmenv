# React Development Guidelines

## Component Design
- Use functional components with hooks
- Keep components small and focused
- Use composition over inheritance
- Prefer controlled components over uncontrolled
- Use TypeScript for prop definitions

## Hooks Best Practices
- Follow the Rules of Hooks
- Use custom hooks for shared stateful logic
- Use useCallback for functions passed to children
- Use useMemo for expensive calculations
- Use useEffect cleanup functions to prevent memory leaks

## State Management
- Use useState for local component state
- Use useContext for prop drilling solutions
- Consider useReducer for complex state logic
- Use external state management (Redux, Zustand) for global state
- Keep state as close to where it's used as possible

## Performance Optimization
- Use React.memo for expensive components
- Implement proper key props for lists
- Use lazy loading for routes and large components
- Optimize bundle size with code splitting
- Use React DevTools Profiler for performance analysis

## Testing
- Use React Testing Library for component tests
- Test user interactions, not implementation details
- Use MSW (Mock Service Worker) for API mocking
- Write integration tests for critical user flows
- Use Storybook for component documentation and testing