// ui/src/utils/safeOpen.ts
// @ai-rules:
// 1. [Constraint]: Only for external URLs from API data (GitLab, Jira, Kargo).
// 2. [Constraint]: Do NOT use for DOM-sourced URLs (img.src, blob:, data:) — those are safe by origin.
// 3. [Pattern]: Validates scheme before opening. Requires absolute http(s) URL (no base); rejects relative, protocol-relative, and javascript:/data:/blob: URLs.
export function safeOpen(url: string | undefined | null): void {
  if (!url) return;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      window.open(parsed.href, '_blank', 'noopener,noreferrer');
    }
  } catch { /* malformed or relative URL — silently drop */ }
}
