// ui/src/utils/formatTokens.ts
// @ai-rules:
// 1. [Constraint]: Pure formatting function — no side effects, no API calls.
// 2. [Pattern]: Shared by TreePrimitives (sidebar badge) and TokenUtilizationPage (SparkCards).

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
