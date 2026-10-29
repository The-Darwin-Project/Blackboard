// BlackBoard/ui/src/components/PlanProgress.tsx
// @ai-rules:
// 1. [Pattern]: Derives plan state from conversation turns -- no separate API. Same useEventDocument data.
// 2. [Constraint]: Last action="plan" turn = active plan. Last action="plan_step" per step_id = current status.
// 3. [Pattern]: Vertical side panel layout -- sits as a flex column sibling of the event chat.
// 4. [Constraint]: Uses ACTOR_COLORS from constants/colors.ts -- single source of truth for agent colors.
import { useMemo } from 'react';
import { ACTOR_COLORS } from '../constants/colors';
import type { ConversationTurn } from '../api/types';

interface PlanStep {
  id: string;
  agent: string;
  summary: string;
  status: string;
  timestamp?: number;
  test_evidence?: string;
}

interface PlanProgressProps {
  conversation: ConversationTurn[];
}

const STATUS_ICON: Record<string, string> = {
  completed: '\u2705',
  green_verified: '\uD83D\uDFE2 \u2713',
  red_locked: '\uD83D\uDD34 \uD83D\uDD12',
  in_progress: '\uD83D\uDD04',
  blocked: '\u26A0\uFE0F',
  pending: '\u2B1C',
};

const BORDER_COLOR: Record<string, string> = {
  completed: '#22c55e',
  green_verified: '#10b981',
  red_locked: '#ef4444',
  in_progress: '#3b82f6',
  blocked: '#f59e0b',
  pending: '#334155',
};

export function usePlanState(conversation: ConversationTurn[]) {
  return useMemo(() => {
    let plan: ConversationTurn | null = null;
    for (let i = conversation.length - 1; i >= 0; i--) {
      const t = conversation[i];
      if (t.action === 'plan' && t.taskForAgent && (t.taskForAgent as Record<string, unknown>).steps) {
        plan = t;
        break;
      }
    }
    if (!plan) return { hasPlan: false, planTurn: null, steps: [] as PlanStep[] };

    const rawSteps = (plan.taskForAgent as { steps: Array<{ id: string; agent: string; summary?: string }> }).steps;
    const stepMap = new Map<string, PlanStep>();
    for (const s of rawSteps) {
      stepMap.set(s.id, { id: s.id, agent: s.agent || '', summary: s.summary || '', status: 'pending' });
    }

    for (const t of conversation) {
      if (t.action === 'plan_step' && t.taskForAgent) {
        const tf = t.taskForAgent as { step_id?: string; status?: string; summary?: string; test_evidence?: string };
        if (tf.step_id && stepMap.has(tf.step_id)) {
          const existing = stepMap.get(tf.step_id)!;
          existing.status = tf.status || 'completed';
          if (tf.summary) existing.summary = tf.summary;
          if (tf.test_evidence) existing.test_evidence = tf.test_evidence;
          existing.timestamp = t.timestamp;
        }
      }
    }

    return { hasPlan: true, planTurn: plan, steps: Array.from(stepMap.values()) };
  }, [conversation]);
}

export function PlanProgress({ conversation }: PlanProgressProps) {
  const { planTurn, steps } = usePlanState(conversation);

  if (!planTurn || steps.length === 0) return null;

  const done = steps.filter(s => s.status === 'completed' || s.status === 'green_verified').length;
  const source = (planTurn.taskForAgent as { source?: string })?.source || planTurn.actor;
  const reasoning = (planTurn.taskForAgent as { reasoning?: string })?.reasoning || '';
  const isAgentSourced = source !== 'architect' && source !== 'brain';
  const progressPct = steps.length > 0 ? (done / steps.length) * 100 : 0;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#0f172a',
      borderLeft: '1px solid #334155',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 10px',
        borderBottom: '1px solid #334155',
        background: '#1e293b',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#e2e8f0' }}>
            {isAgentSourced ? 'Investigation Findings' : 'Plan'}
          </span>
          <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>{done}/{steps.length}</span>
        </div>
        {reasoning && (
          <div style={{
            fontSize: 11,
            color: isAgentSourced ? '#f59e0b' : '#94a3b8',
            lineHeight: 1.3,
            marginBottom: 4,
            padding: '3px 0',
            borderBottom: '1px solid #334155',
          }}>
            {reasoning}
          </div>
        )}
        <div style={{
          height: 3,
          background: '#334155',
          borderRadius: 2,
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${progressPct}%`,
            background: done === steps.length ? '#22c55e' : '#3b82f6',
            borderRadius: 2,
            transition: 'width 0.3s ease',
          }} />
        </div>
        <div style={{ fontSize: 9, color: '#475569', marginTop: 3 }}>
          {isAgentSourced ? `suggested by ${source}` : `by ${source}`}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {steps.map((step) => {
          const isActive = step.status === 'in_progress';
          const isDone = step.status === 'completed' || step.status === 'green_verified';
          return (
            <div
              key={step.id}
              style={{
                padding: '6px 10px',
                borderLeft: `3px solid var(--step-border, ${BORDER_COLOR[step.status] || '#334155'})`,
                marginLeft: 4,
                marginBottom: 2,
                background: isActive ? '#1e3a5f15' : 'transparent',
              }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginBottom: 2,
              }}>
                <span style={{ fontSize: 12, flexShrink: 0 }}>
                  {STATUS_ICON[step.status] || STATUS_ICON.pending}
                </span>
                <span style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: ACTOR_COLORS[step.agent] || '#94a3b8',
                }}>
                  {step.agent}
                </span>
                {isAgentSourced && (
                  <span style={{ fontSize: 9, color: '#64748b' }}>
                    suggested
                  </span>
                )}
              </div>
              <div style={{
                fontSize: 11,
                color: isDone ? '#64748b' : '#e2e8f0',
                opacity: isDone ? 0.7 : 1,
                lineHeight: 1.3,
              }}>
                {step.summary || `Step ${step.id}`}
              </div>
              {step.test_evidence && (
                <details style={{ marginTop: 4, fontSize: 10, color: '#94a3b8' }}>
                  <summary style={{ cursor: 'pointer', color: '#38bdf8' }}>Test Evidence</summary>
                  <pre style={{
                    marginTop: 2,
                    padding: '4px 6px',
                    background: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: 4,
                    fontSize: 9,
                    color: '#e2e8f0',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {step.test_evidence}
                  </pre>
                </details>
              )}
              {step.timestamp && (
                <div style={{ fontSize: 9, color: '#475569', marginTop: 2 }}>
                  {new Date(step.timestamp * 1000).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default PlanProgress;
