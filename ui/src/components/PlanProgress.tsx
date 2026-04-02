// BlackBoard/ui/src/components/PlanProgress.tsx
// @ai-rules:
// 1. [Pattern]: Derives plan state from conversation turns -- no separate API. Same useEventDocument data.
// 2. [Constraint]: Last action="plan" turn = active plan. Last action="plan_step" per step_id = current status.
// 3. [Pattern]: Collapsible. Auto-expands when any step transitions to in_progress.
// 4. [Constraint]: Uses ACTOR_COLORS from constants/colors.ts -- single source of truth for agent colors.
import { useState, useMemo, useEffect } from 'react';
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

export function PlanProgress({ conversation }: PlanProgressProps) {
  const { planTurn, steps, hasActive } = useMemo(() => {
    let plan: ConversationTurn | null = null;
    for (let i = conversation.length - 1; i >= 0; i--) {
      const t = conversation[i];
      if (t.action === 'plan' && t.taskForAgent && (t.taskForAgent as Record<string, unknown>).steps) {
        plan = t;
        break;
      }
    }
    if (!plan) return { planTurn: null, steps: [] as PlanStep[], hasActive: false };

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

    const merged = Array.from(stepMap.values());
    return {
      planTurn: plan,
      steps: merged,
      hasActive: merged.some(s => s.status === 'in_progress'),
    };
  }, [conversation]);

  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (hasActive) setCollapsed(false);
  }, [hasActive]);

  if (!planTurn || steps.length === 0) return null;

  const done = steps.filter(s => s.status === 'completed').length;
  const source = (planTurn.taskForAgent as { source?: string })?.source || planTurn.actor;
  const agents = [...new Set(steps.map(s => s.agent))];
  const progressPct = steps.length > 0 ? (done / steps.length) * 100 : 0;

  return (
    <div style={{
      borderBottom: '1px solid #334155',
      background: '#1e293b',
      flexShrink: 0,
    }}>
      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          padding: '6px 12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>
            Plan {done}/{steps.length}
          </span>
          <span style={{ fontSize: 10, color: '#64748b' }}>by {source}</span>
          <span style={{ display: 'flex', gap: 4 }}>
            {agents.map(a => (
              <span key={a} style={{
                color: ACTOR_COLORS[a] || '#94a3b8',
                fontSize: 10,
                fontWeight: 600,
              }}>{a}</span>
            ))}
          </span>
        </div>
        <span style={{ color: '#64748b', fontSize: 11 }}>{collapsed ? '\u25B6' : '\u25BC'}</span>
      </div>

      <div style={{
        height: 2,
        background: '#334155',
        margin: '0 12px',
        borderRadius: 1,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${progressPct}%`,
          background: done === steps.length ? '#22c55e' : '#3b82f6',
          borderRadius: 1,
          transition: 'width 0.3s ease',
        }} />
      </div>

      {!collapsed && (
        <div style={{ padding: '6px 12px 8px' }}>
          {steps.map(step => (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 0',
                fontSize: 12,
                color: step.status === 'completed' ? '#64748b' : '#e2e8f0',
                textDecoration: step.status === 'completed' ? 'line-through' : 'none',
              }}
            >
              <span style={{ width: 18, textAlign: 'center', flexShrink: 0 }}>
                {STATUS_ICON[step.status] || STATUS_ICON.pending}
              </span>
              <span style={{
                color: ACTOR_COLORS[step.agent] || '#94a3b8',
                fontWeight: 600,
                fontSize: 10,
                minWidth: 60,
              }}>
                {step.agent}
              </span>
              <span style={{ flex: 1 }}>{step.summary || `Step ${step.id}`}</span>
              {step.timestamp && (
                <span style={{ fontSize: 10, color: '#475569', flexShrink: 0 }}>
                  {new Date(step.timestamp * 1000).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PlanProgress;
