// BlackBoard/ui/src/components/graph/constants.ts
// @ai-rules:
// 1. [Pattern]: Shared graph constants extracted from ServiceNode.tsx for reuse by AppNode.tsx.

export const ARGOCD_HEALTH_COLORS: Record<string, string> = {
  Healthy: '#22c55e',
  Progressing: '#eab308',
  Degraded: '#ef4444',
  Missing: '#6b7280',
  Unknown: '#6b7280',
};

export const SYNC_ICONS: Record<string, string> = {
  Synced: '\u2713',
  OutOfSync: '\u26a0',
};
