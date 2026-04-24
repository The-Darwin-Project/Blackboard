// BlackBoard/ui/src/constants/colors.ts
// @ai-rules:
// 1. [Constraint]: All color maps are shared across multiple components; any new field must be documented.
// 2. [Pattern]: border drives card left border color (status-based), bg/text drive pill badges.
// 3. [Gotcha]: DOMAIN_COLORS border is for pill badges only; card border uses STATUS_COLORS.border.
// 4. [Pattern]: SEVERITY_COLORS used by ReportHeader and ReportGrid for severity badge pills.
/** Shared agent/actor color map used by ConversationFeed, AgentStreamCard, etc. */
export const ACTOR_COLORS: Record<string, string> = {
  brain: '#8b5cf6',
  architect: '#3b82f6',
  sysadmin: '#f59e0b',
  developer: '#10b981',
  manager: '#06b6d4',  // Cyan -- Manager moderator (distinct from amber sysadmin)
  qe: '#fb7185',      // Coral -- QE pair partner
  flash: '#06b6d4',    // Cyan -- Manager moderator (alias for manager)
  aligner: '#6b7280',
  user: '#ec4899',
};

export const DOMAIN_COLORS = {
  disorder:    { border: '#6b7280', bg: '#6b728015', text: '#9ca3af' },
  clear:       { border: '#22c55e', bg: '#22c55e15', text: '#4ade80' },
  complicated: { border: '#eab308', bg: '#eab30815', text: '#facc15' },
  complex:     { border: '#a855f7', bg: '#a855f715', text: '#c084fc' },
  chaotic:     { border: '#ef4444', bg: '#ef444415', text: '#f87171' },
} as const;

export const STATUS_COLORS: Record<string, { bg: string; text: string; label: string; border: string }> = {
  new:              { bg: '#1e40af', text: '#93c5fd', label: 'New',      border: '#3b82f6' },
  active:           { bg: '#1d4ed8', text: '#93c5fd', label: 'Active',   border: '#3b82f6' },
  waiting_approval: { bg: '#92400e', text: '#fcd34d', label: 'Awaiting', border: '#f59e0b' },
  deferred:         { bg: '#4c1d95', text: '#c4b5fd', label: 'Deferred', border: '#8b5cf6' },
  resolved:         { bg: '#14532d', text: '#86efac', label: 'Resolved', border: '#22c55e' },
  closed:           { bg: '#14532d', text: '#86efac', label: 'Closed',   border: '#22c55e' },
};

export const SEVERITY_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  info:     { bg: '#1e3a5f', text: '#7dd3fc', label: 'Info' },
  warning:  { bg: '#78350f', text: '#fcd34d', label: 'Warning' },
  critical: { bg: '#7f1d1d', text: '#fca5a5', label: 'Critical' },
};

export const PHASE_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  triage:      { bg: '#1e3a5f', text: '#7dd3fc', border: '#3b82f6', label: 'Triage' },
  investigate: { bg: '#1e3a5f', text: '#93c5fd', border: '#60a5fa', label: 'Investigate' },
  execute:     { bg: '#14532d', text: '#86efac', border: '#22c55e', label: 'Execute' },
  verify:      { bg: '#4c1d95', text: '#c4b5fd', border: '#8b5cf6', label: 'Verify' },
  escalate:    { bg: '#7f1d1d', text: '#fca5a5', border: '#ef4444', label: 'Escalate' },
  close:       { bg: '#1c1917', text: '#a8a29e', border: '#57534e', label: 'Close' },
};
