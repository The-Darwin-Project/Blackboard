// BlackBoard/ui/src/components/ErrorBoundary.tsx
// @ai-rules:
// 1. [Pattern]: Generic reusable error boundary. Catches render errors in children, shows fallback instead of crashing the whole app.
// 2. [Constraint]: Class component required -- React error boundaries have no hook equivalent.
// 3. [Pattern]: resetKey prop resets hasError when changed without unmounting children when healthy.
import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  resetKey?: unknown;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-4 text-text-muted">Something went wrong. Try refreshing.</div>
      );
    }
    return this.props.children;
  }
}
