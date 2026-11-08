// BlackBoard/ui/src/utils/planState.ts
// @ai-rules:
// 1. [Pattern]: Pure derivation of plan state from conversation turns -- no React, no separate API.
// 2. [Constraint]: Last action="plan" turn = active plan. Only plan_step turns at or after that turn index update step status.
// 3. [Pattern]: canonicalRole lowercases and maps '-' / ' ' to '_' so "Code-Reviewer" === "code_reviewer".
// 4. [Pattern]: Lives outside PlanProgress.tsx so that file only exports components (react-refresh/only-export-components).
import type { ConversationTurn } from '../api/types';

export interface PlanStep {
  id: string;
  agent: string;
  summary: string;
  status: string;
  timestamp?: number;
  // Backend (PlanStepRequest.test_evidence) sends a dict; legacy/other producers may send a plain string.
  test_evidence?: string | Record<string, unknown>;
}

export interface PlanState {
  hasPlan: boolean;
  planTurn: ConversationTurn | null;
  steps: PlanStep[];
}

export const TERMINAL_STATUSES = new Set(['completed', 'green_verified', 'blocked', 'red_locked']);

export function canonicalRole(role?: string): string {
  return (role || '').trim().toLowerCase().replace(/[- ]/g, '_');
}

export function derivePlanState(conversation: ConversationTurn[]): PlanState {
  let plan: ConversationTurn | null = null;
  let planTurnIndex = -1;

  for (let i = conversation.length - 1; i >= 0; i--) {
    const t = conversation[i];
    if (t.action === 'plan' && t.taskForAgent && (t.taskForAgent as Record<string, unknown>).steps) {
      plan = t;
      planTurnIndex = i;
      break;
    }
  }

  if (!plan || planTurnIndex === -1) {
    return { hasPlan: false, planTurn: null, steps: [] };
  }

  const rawSteps = (plan.taskForAgent as { steps?: Array<{ id: string; agent?: string; summary?: string }> }).steps;
  const stepMap = new Map<string, PlanStep>();
  if (Array.isArray(rawSteps)) {
    for (const s of rawSteps) {
      if (s && s.id) {
        stepMap.set(s.id, { id: s.id, agent: s.agent || '', summary: s.summary || '', status: 'pending' });
      }
    }
  }

  // Process only plan_step turns arriving on or after the latest plan turn
  const startSlice = planTurnIndex;
  for (let i = startSlice; i < conversation.length; i++) {
    const t = conversation[i];
    if (t.action === 'plan_step' && t.taskForAgent) {
      const tf = t.taskForAgent as { step_id?: string; status?: string; test_evidence?: string | Record<string, unknown> };
      if (tf.step_id && stepMap.has(tf.step_id)) {
        const existing = stepMap.get(tf.step_id)!;
        existing.status = tf.status || 'completed';
        if (tf.test_evidence) existing.test_evidence = tf.test_evidence;
        existing.timestamp = t.timestamp;
      }
    }
  }

  return { hasPlan: true, planTurn: plan, steps: Array.from(stepMap.values()) };
}
