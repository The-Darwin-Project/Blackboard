// BlackBoard/ui/src/utils/formatTokens.ts
// @ai-rules:
// 1. [Constraint]: Pure formatting functions — no side effects, no API calls.
// 2. [Pattern]: Shared by TreePrimitives, TokenUtilizationPage, FlowHistoryPage, and TpmUsagePanel.

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
