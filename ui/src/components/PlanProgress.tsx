// BlackBoard/ui/src/components/PlanProgress.tsx
// @ai-rules:
// 1. [Pattern]: Derives plan state from conversation turns -- no separate API. Same useEventDocument data.
// 2. [Constraint]: Last action="plan" turn = active plan. Last action="plan_step" per step_id >= plan turn = current status.
// 3. [Pattern]: Dual-correlation: step.status === 'in_progress' OR first uncompleted step matching active agent role.
// 4. [Constraint]: Uses ACTOR_COLORS from constants/colors.ts -- single source of truth for agent colors.
// 5. [Constraint]: Exports components only (react-refresh). usePlanState lives in hooks/usePlanState.ts; canonicalRole/PlanStep in utils/planState.ts.
import { useMemo } from 'react';
import { ACTOR_COLORS } from '../constants/colors';
import { usePlanState } from '../hooks/usePlanState';
import { canonicalRole, TERMINAL_STATUSES } from '../utils/planState';
import type { ConversationTurn } from '../api/types';

export interface PlanProgressProps {
  conversation?: ConversationTurn[];
  activeAgentRoles?: Set<string>;
  onOpenStream?: (agentRole: string) => void;
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

export function PlanProgress({
  conversation,
  activeAgentRoles,
  onOpenStream,
}: PlanProgressProps) {
  const { planTurn, steps } = usePlanState(conversation);

  // Normalized active roles (hooks MUST run unconditionally before any early returns)
  const normalizedActiveRoles = useMemo(() => {
    const set = new Set<string>();
    if (activeAgentRoles) {
      for (const r of activeAgentRoles) {
        const c = canonicalRole(r);
        if (c !== '') set.add(c);
      }
    }
    return set;
  }, [activeAgentRoles]);

  // Identify first uncompleted step id per agent role for fallback correlation
  const firstUncompletedStepByRole = useMemo(() => {
    const map = new Map<string, string>();
    for (const step of steps) {
      const roleStr = canonicalRole(step.agent);
      if (roleStr !== '' && !TERMINAL_STATUSES.has(step.status) && !map.has(roleStr)) {
        map.set(roleStr, step.id);
      }
    }
    return map;
  }, [steps]);

  if (!planTurn || steps.length === 0) return null;

  const done = steps.filter(s => s.status === 'completed' || s.status === 'green_verified').length;
  const allTerminal = steps.length > 0 && steps.every(s => TERMINAL_STATUSES.has(s.status));
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
          const roleStr = canonicalRole(step.agent);
          const isExplicitActive = step.status === 'in_progress';
          const isCorrelatedActive =
            !allTerminal &&
            roleStr !== '' &&
            firstUncompletedStepByRole.get(roleStr) === step.id &&
            normalizedActiveRoles.has(roleStr);

          const isActive = isExplicitActive || isCorrelatedActive;
          const isDone = step.status === 'completed' || step.status === 'green_verified';

          return (
            <div
              key={step.id}
              data-testid="plan-step"
              className={isActive ? 'relative overflow-hidden transition-all duration-300' : ''}
              style={{
                position: 'relative',
                padding: '6px 10px',
                borderLeft: `3px solid var(--step-border, ${isActive ? '#10b981' : (BORDER_COLOR[step.status] || '#334155')})`,
                marginLeft: 4,
                marginBottom: 4,
                background: isActive ? 'rgba(16, 185, 129, 0.08)' : 'transparent',
                borderTopRightRadius: 6,
                borderBottomRightRadius: 6,
                boxShadow: isActive ? '0 0 12px rgba(16,185,129,0.15)' : 'none',
              }}
            >
              {/* Radar shimmer effect on active step card */}
              {isActive && (
                <div
                  className="absolute inset-0 pointer-events-none opacity-20 animate-pulse bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent"
                  style={{ animationDuration: '2.5s' }}
                />
              )}

              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 2,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
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
                  {/* Working Beacon with animated bouncing dots */}
                  {isActive && (
                    <span
                      data-testid="plan-step-working-beacon"
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                      <span>Working...</span>
                    </span>
                  )}
                </div>

                {/* Stream button */}
                {isActive && onOpenStream && step.agent && (
                  <button
                    data-testid="plan-step-stream-btn"
                    onClick={() => onOpenStream(step.agent)}
                    title={`Open live stream for ${step.agent}`}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 hover:scale-105 transition-all cursor-pointer"
                  >
                    <span>Stream</span>
                    <span className="text-[9px]">↗</span>
                  </button>
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
                    {typeof step.test_evidence === 'string' ? step.test_evidence : JSON.stringify(step.test_evidence, null, 2)}
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
