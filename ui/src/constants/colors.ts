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
  manager: '#06b6d4',
  qe: '#fb7185',
  security_analyst: '#ef4444',
  flash: '#06b6d4',
  aligner: '#6b7280',
  jarvis: '#14b8a6',   // Teal -- JARVIS meta-cognitive observer
  user: '#ec4899',
};

/** Display names for actors (backend uses short IDs, UI shows personas) */
export const ACTOR_LABELS: Record<string, string> = {
  brain: 'FRIDAY',
  jarvis: 'JARVIS',
};

export const DOMAIN_COLORS = {
  disorder:    { border: '#6b7280', bg: '#6b728015', text: '#9ca3af' },
  clear:       { border: '#22c55e', bg: '#22c55e15', text: '#4ade80' },
  complicated: { border: '#eab308', bg: '#eab30815', text: '#facc15' },
  complex:     { border: '#a855f7', bg: '#a855f715', text: '#c084fc' },
  chaotic:     { border: '#ef4444', bg: '#ef444415', text: '#f87171' },
  casual:      { border: '#06b6d4', bg: '#06b6d415', text: '#22d3ee' },
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
  dispatch:    { bg: '#14532d', text: '#86efac', border: '#22c55e', label: 'Dispatch' },
  verify:      { bg: '#4c1d95', text: '#c4b5fd', border: '#8b5cf6', label: 'Verify' },
  escalate:    { bg: '#7f1d1d', text: '#fca5a5', border: '#ef4444', label: 'Escalate' },
  close:       { bg: '#1c1917', text: '#a8a29e', border: '#57534e', label: 'Close' },
  // Alias entries during transition (backend _resolve_phase normalizes, but stale WS data may hit these)
  investigate: { bg: '#14532d', text: '#86efac', border: '#22c55e', label: 'Dispatch' },
  execute:     { bg: '#14532d', text: '#86efac', border: '#22c55e', label: 'Dispatch' },
};

/** Cortex neuron type colors (used by Sigma.js graph renderer) */
export const NEURON_COLORS: Record<string, string> = {
  lesson:    '#22c55e',   // green -- stable knowledge
  memory:    '#6b7280',   // slate -- past event memories
  knowledge: '#06b6d4',   // cyan -- infrastructure reference facts
  tool:      '#64748b',   // slate -- executive tools
  phase:     '#6366f1',   // indigo -- lifecycle phases
  agent:     '#8b5cf6',   // violet -- default; overridden per agent below
  domain:    '#eab308',   // amber -- default; overridden per domain below
};

export const DOMAIN_NEURON_COLORS: Record<string, string> = {
  clear:       '#22c55e', // green
  complicated: '#eab308', // amber
  complex:     '#a855f7', // purple
  chaotic:     '#ef4444', // red
  casual:      '#06b6d4', // cyan -- conversational, non-problem
  disorder:    '#6b7280', // slate
};

export const AGENT_NEURON_COLORS: Record<string, string> = {
  architect: '#3b82f6', // blue
  sysadmin:  '#22c55e', // green
  developer: '#f59e0b', // amber
  qe:        '#a855f7', // purple
  security_analyst: '#ef4444', // red
};

export const SHIFT_STATUS_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  empty:     { bg: '#33415515', text: '#64748b', border: '#334155', label: 'Empty' },
  completed: { bg: '#22c55e15', text: '#4ade80', border: '#22c55e', label: 'Completed' },
  running:   { bg: '#6366f115', text: '#818cf8', border: '#6366f1', label: 'Running' },
  pending:   { bg: '#f59e0b15', text: '#fcd34d', border: '#f59e0b', label: 'Pending' },
  failed:    { bg: '#ef444415', text: '#f87171', border: '#ef4444', label: 'Failed' },
};
