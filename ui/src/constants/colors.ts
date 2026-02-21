// BlackBoard/ui/src/constants/colors.ts
// @ai-rules:
// 1. [Constraint]: STATUS_COLORS and DOMAIN_COLORS are shared across ticket cards and badges; any new field must be documented.
// 2. [Pattern]: border drives card left border color (status-based), bg/text drive pill badges.
// 3. [Gotcha]: DOMAIN_COLORS border is for pill badges only; card border uses STATUS_COLORS.border.
/** Shared agent/actor color map used by ConversationFeed, AgentStreamCard, etc. */
export const ACTOR_COLORS: Record<string, string> = {
  brain: '#8b5cf6',
  architect: '#3b82f6',
  sysadmin: '#f59e0b',
  developer: '#10b981',
  manager: '#ea580c',  // Orange -- Flash Manager moderator (distinct from amber sysadmin)
  qe: '#a855f7',      // Purple -- QE pair partner
  flash: '#64748b',    // Slate gray -- Flash Manager moderator
  aligner: '#6b7280',
  user: '#ec4899',
};

export const DOMAIN_COLORS = {
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
