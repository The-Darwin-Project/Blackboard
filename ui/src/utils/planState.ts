// BlackBoard/ui/src/utils/planState.ts
// @ai-rules:
// 1. [Pattern]: Pure derivation of plan state from conversation turns -- no React, no separate API.
// 2. [Constraint]: Latest orchestrator plan (brain/architect/headhunter/aligner) is authoritative.
//    Agent-sourced proposals only take effect if no orchestrator plan exists.
// 3. [Pattern]: Only assigned agent or orchestrator can update step status (prevents cross-agent step hijacking).
// 4. [Pattern]: Agent completion turns (execute / non-orchestrator plan) strictly AFTER the plan turn complete ONE step
//    assigned to that agent (in_progress preferred over pending; blocked/completed never touched; error turns ignored).
//    The plan-establishing turn itself never completes a step.
// 5. [Constraint]: Orchestrator detection (actor OR taskForAgent.source) mirrors src/agents/handlers_planning.py -- keep in sync.
// 6. [Pattern]: canonicalRole lowercases and maps '-' / ' ' to '_' so "Code-Reviewer" === "code_reviewer"; non-string input -> ''.
// 6b. [Pattern]: normalizeStepId (non-empty trimmed string or finite number; else null) mirrors _normalize_step_id in
//    src/agents/handlers_planning.py -- keep in sync.
// 7. [Pattern]: Lives outside PlanProgress.tsx so that file only exports components (react-refresh/only-export-components).
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
export const ORCHESTRATOR_ROLES = new Set(['brain', 'architect', 'headhunter', 'aligner']);

// Non-string input (malformed stored payloads) yields '' instead of throwing. Mirrors handlers_planning._canonical_role.
export function canonicalRole(value?: unknown): string {
  if (typeof value !== 'string') return '';
  return value.trim().toLowerCase().replace(/[- ]/g, '_');
}

// Step ids: non-empty (trimmed) strings and finite numbers are valid; null/undefined/boolean/empty/NaN/objects are
// rejected. Mirrors handlers_planning._normalize_step_id.
export function normalizeStepId(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

export function isOrchestratorPlan(t: ConversationTurn): boolean {
  if (t.action !== 'plan') return false;
  const actor = canonicalRole(t.actor);
  if (ORCHESTRATOR_ROLES.has(actor)) return true;
  const source = canonicalRole((t.taskForAgent as { source?: unknown } | undefined)?.source);
  return ORCHESTRATOR_ROLES.has(source);
}

// A failed/aborted worker turn must not auto-complete a plan step (backend "Error:" result convention).
function isFailedTurn(t: ConversationTurn): boolean {
  return t.action === 'error' || (typeof t.result === 'string' && t.result.trimStart().startsWith('Error:'));
}

// Complete ONE step for the agent: prefer in_progress, else first pending. blocked/completed are never touched.
function autoCompleteStep(stepMap: Map<string, PlanStep>, agentRole: string, timestamp?: number): void {
  const mine = Array.from(stepMap.values()).filter((s) => canonicalRole(s.agent) === agentRole);
  const target = mine.find((s) => s.status === 'in_progress') ?? mine.find((s) => s.status === 'pending');
  if (target) {
    target.status = 'completed';
    target.timestamp = timestamp;
  }
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

  const rawSteps = (plan.taskForAgent as { steps?: unknown }).steps;
  const stepMap = new Map<string, PlanStep>();
  if (Array.isArray(rawSteps)) {
    for (const s of rawSteps as Array<Record<string, unknown> | null>) {
      const id = s && typeof s === 'object' ? normalizeStepId(s.id) : null;
      if (s && id !== null) {
        stepMap.set(id, {
          id,
          agent: typeof s.agent === 'string' ? s.agent : '',
          summary: typeof s.summary === 'string' ? s.summary : '',
          status: 'pending',
        });
      }
    }
  }

  // Process only turns strictly AFTER the plan turn: the plan-establishing turn (esp. a worker-authored
  // fallback plan) must never complete its own step.
  for (let i = planTurnIndex + 1; i < conversation.length; i++) {
    const t = conversation[i];
    if (t.action === 'plan_step' && t.taskForAgent) {
      const tf = t.taskForAgent as { step_id?: unknown; status?: string; test_evidence?: string | Record<string, unknown> };
      const stepId = normalizeStepId(tf.step_id);
      if (stepId !== null && stepMap.has(stepId)) {
        const existing = stepMap.get(stepId)!;
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
      (t.action === 'execute' || (t.action === 'plan' && !isOrchestratorPlan(t))) &&
      t.actor &&
      !isFailedTurn(t)
    ) {
      const actorRole = canonicalRole(t.actor);
      if (actorRole && !ORCHESTRATOR_ROLES.has(actorRole)) {
        autoCompleteStep(stepMap, actorRole, t.timestamp);
      }
    }
  }

  return { hasPlan: true, planTurn: plan, steps: Array.from(stepMap.values()) };
}
