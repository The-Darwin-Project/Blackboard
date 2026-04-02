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
}

interface PlanProgressProps {
  conversation: ConversationTurn[];
}

const STATUS_ICON: Record<string, string> = {
  completed: '\u2705',
  in_progress: '\uD83D\uDD04',
  blocked: '\u26A0\uFE0F',
  pending: '\u2B1C',
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
        const tf = t.taskForAgent as { step_id?: string; status?: string };
        if (tf.step_id && stepMap.has(tf.step_id)) {
          const existing = stepMap.get(tf.step_id)!;
          existing.status = tf.status || 'completed';
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

  const done = steps.filter(s => s.status === 'completed').length;
  const source = (planTurn.taskForAgent as { source?: string })?.source || planTurn.actor;
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#e2e8f0' }}>Plan</span>
          <span style={{ fontSize: 10, color: '#64748b' }}>{done}/{steps.length}</span>
        </div>
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
        <div style={{ fontSize: 9, color: '#475569', marginTop: 3 }}>by {source}</div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {steps.map((step) => {
          const isActive = step.status === 'in_progress';
          const isDone = step.status === 'completed';
          const isBlocked = step.status === 'blocked';
          return (
            <div
              key={step.id}
              style={{
                padding: '6px 10px',
                borderLeft: `3px solid ${
                  isDone ? '#22c55e' : isActive ? '#3b82f6' : isBlocked ? '#f59e0b' : '#334155'
                }`,
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
              </div>
              <div style={{
                fontSize: 11,
                color: isDone ? '#64748b' : '#e2e8f0',
                textDecoration: isDone ? 'line-through' : 'none',
                lineHeight: 1.3,
              }}>
                {step.summary || `Step ${step.id}`}
              </div>
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
