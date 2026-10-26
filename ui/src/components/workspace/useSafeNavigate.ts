// BlackBoard/ui/src/components/workspace/useSafeNavigate.ts
// @ai-rules:
// 1. [Constraint]: Returns null (never throws) when rendered outside a Router so workspace components stay unit-testable.
// 2. [Pattern]: Callers must treat a null result as "no router"; use optional chaining or a guard.
import { useNavigate, type NavigateFunction } from 'react-router-dom';

export function useSafeNavigate(): NavigateFunction | null {
  try {
    return useNavigate();
  } catch {
    return null;
  }
}
