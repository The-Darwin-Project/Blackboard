// ui/src/utils/eventFormat.ts

export function extractReasonDisplay(reason: string): string {
  if (!reason.startsWith('---')) return reason;
  const match = reason.match(/plan:\s*"?([^"\n]+)"?/);
  return match?.[1]?.trim() || reason.replace(/---[\s\S]*?---/, '').trim() || reason;
}
