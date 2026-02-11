// BlackBoard/ui/src/constants/colors.ts
/** Shared agent/actor color map used by ConversationFeed, AgentStreamCard, etc. */
export const ACTOR_COLORS: Record<string, string> = {
  brain: '#8b5cf6',
  architect: '#3b82f6',
  sysadmin: '#f59e0b',
  developer: '#10b981',
  qe: '#a855f7',      // Purple -- QE pair partner
  flash: '#64748b',    // Slate gray -- Flash Manager moderator
  aligner: '#6b7280',
  user: '#ec4899',
};

export const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  new: { bg: '#1e40af', text: '#93c5fd', label: 'New' },
  active: { bg: '#065f46', text: '#6ee7b7', label: 'Active' },
  waiting_approval: { bg: '#92400e', text: '#fcd34d', label: 'Awaiting' },
  deferred: { bg: '#4c1d95', text: '#c4b5fd', label: 'Deferred' },
  resolved: { bg: '#14532d', text: '#86efac', label: 'Resolved' },
  closed: { bg: '#374151', text: '#9ca3af', label: 'Closed' },
};
