// BlackBoard/ui/src/hooks/useDebouncedValue.ts
// @ai-rules:
// 1. [Pattern]: Generic debounce hook -- extracted from the inline pattern in EventHistory.tsx
//    so Memory tab search inputs (Knowledge/Lessons/Memories/ExtractWizard) share one
//    implementation instead of four copies of the same setTimeout/clearTimeout pair.
import { useEffect, useState } from 'react';

/** Returns `value` after it has been stable for `delayMs` (default 300ms). */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
