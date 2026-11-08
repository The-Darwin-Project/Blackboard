// BlackBoard/ui/src/contexts/activeStreamsStore.ts
// @ai-rules:
// 1. [Pattern]: Holds the ActiveStreams context object and its consumer hooks. Kept separate from ActiveStreamsContext.tsx so that
//    file only exports a component (react-refresh/only-export-components).
// 2. [Constraint]: useActiveStreams throws outside the provider; useActiveStreamsSafe falls back to a frozen empty default.
import { createContext, useContext } from 'react';
import type { Streams } from '../utils/streamReducers';

export interface ActiveStreamsState {
  activeStreams: Streams;
}

export const ActiveStreamsContext = createContext<ActiveStreamsState | null>(null);

const DEFAULT_ACTIVE_STREAMS: ActiveStreamsState = Object.freeze({ activeStreams: Object.freeze({}) });

export function useActiveStreams(): ActiveStreamsState {
  const ctx = useContext(ActiveStreamsContext);
  if (!ctx) throw new Error('useActiveStreams must be used within ActiveStreamsProvider');
  return ctx;
}

export function useActiveStreamsSafe(): ActiveStreamsState {
  return useContext(ActiveStreamsContext) ?? DEFAULT_ACTIVE_STREAMS;
}
