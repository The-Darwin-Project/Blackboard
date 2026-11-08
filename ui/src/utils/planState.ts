// BlackBoard/ui/src/utils/planState.ts
// @ai-rules:
// 1. [Pattern]: Pure derivation of plan state from conversation turns -- no React, no separate API.
// 2. [Constraint]: Latest orchestrator plan (brain/architect/headhunter/aligner) is authoritative.
//    Agent-sourced proposals only take effect if no orchestrator plan exists.
// 3. [Pattern]: Only assigned agent or orchestrator can update step status (prevents cross-agent step hijacking).
// 4. [Pattern]: Agent completion turns (execute/plan result) complete uncompleted step assigned to that agent.
// 5. [Pattern]: canonicalRole lowercases and maps '-' / ' ' to '_' so "Code-Reviewer" === "code_reviewer".
// 6. [Pattern]: Lives outside PlanProgress.tsx so that file only exports components (react-refresh/only-export-components).
import type { ConversationTurn } from '../api/types';

export interface PlanStep {
  id: string;
  agent: string;
  summary: string;
  status: string;
  timestamp?: number;
  test_evidence?: string | Record<string, unknown>;
}

export interface PlanState {
  hasPlan: boolean;
  planTurn: ConversationTurn | null;
  steps: PlanStep[];
}

export const TERMINAL_STATUSES = new Set(['completed', 'green_verified', 'blocked', 'red_locked']);
export const ORCHESTRATOR_ROLES = new Set(['brain', 'architect', 'headhunter', 'aligner']);

export function canonicalRole(role?: string): string {
  return (role || '').trim().toLowerCase().replace(/[- ]/g, '_');
}

export function isOrchestratorPlan(t: ConversationTurn): boolean {
  if (t.action !== 'plan') return false;
  const actor = canonicalRole(t.actor);
  if (ORCHESTRATOR_ROLES.has(actor)) return true;
  const source = canonicalRole((t.taskForAgent as { source?: string })?.source);
  if (ORCHESTRATOR_ROLES.has(source)) return true;
  return false;
}

export function derivePlanState(conversation: ConversationTurn[]): PlanState {
  let latestOrchestratorPlan: ConversationTurn | null = null;
  let latestOrchestratorIndex = -1;
  let latestAgentPlan: ConversationTurn | null = null;
  let latestAgentIndex = -1;

  for (let i = conversation.length - 1; i >= 0; i--) {
    const t = conversation[i];
    if (t.action === 'plan' && t.taskForAgent && (t.taskForAgent as Record<string, unknown>).steps) {
      if (isOrchestratorPlan(t)) {
        if (!latestOrchestratorPlan) {
          latestOrchestratorPlan = t;
          latestOrchestratorIndex = i;
        }
      } else {
        if (!latestAgentPlan) {
          latestAgentPlan = t;
          latestAgentIndex = i;
        }
      }
    }
  }

  const plan = latestOrchestratorPlan || latestAgentPlan;
  const planTurnIndex = latestOrchestratorPlan ? latestOrchestratorIndex : latestAgentIndex;

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

  // Process turns arriving on or after the plan turn index
  for (let i = planTurnIndex; i < conversation.length; i++) {
    const t = conversation[i];
    if (t.action === 'plan_step' && t.taskForAgent) {
      const tf = t.taskForAgent as { step_id?: string; status?: string; test_evidence?: string | Record<string, unknown> };
      if (tf.step_id && stepMap.has(tf.step_id)) {
        const existing = stepMap.get(tf.step_id)!;
        const actorRole = canonicalRole(t.actor);
        const assignedRole = canonicalRole(existing.agent);
        // Only assigned agent or orchestrator can update step status
        if (assignedRole && !ORCHESTRATOR_ROLES.has(actorRole) && actorRole !== assignedRole) {
          continue;
        }
        existing.status = tf.status || 'completed';
        if (tf.test_evidence) existing.test_evidence = tf.test_evidence;
        existing.timestamp = t.timestamp;
      }
    } else if (
      (t.action === 'execute' || (!isOrchestratorPlan(t) && t.action === 'plan')) &&
      t.actor
    ) {
      // Agent completion turn: marks first uncompleted step assigned to this agent as completed
      const actorRole = canonicalRole(t.actor);
      if (actorRole && !ORCHESTRATOR_ROLES.has(actorRole)) {
        for (const step of stepMap.values()) {
          const stepRole = canonicalRole(step.agent);
          if (stepRole === actorRole && (step.status === 'pending' || step.status === 'in_progress')) {
            step.status = 'completed';
            step.timestamp = t.timestamp;
            break;
          }
        }
      }
    }
  }

  return { hasPlan: true, planTurn: plan, steps: Array.from(stepMap.values()) };
}
