// BlackBoard/ui/src/components/workspace/WorkspaceSwarmPanel.tsx
// @ai-rules:
// 1. [Constraint]: Read agents from useOpsControl (WebSocket-fed); do not add REST polling here.
// 2. [Pattern]: Prefer opsControl.agents, falling back to registeredAgents.
// 3. [Constraint]: Filter agents strictly by effectiveEventId (bound_event_id or current_event_id).
/**
 * Agent Swarm topology panel for Workspace Inspector.
 * Strictly scoped to the currently selected task/event.
 */
import { Bot } from 'lucide-react';
import { useOpsControl } from '../../contexts/OpsStateContext';
import type { AgentRegistryEntry } from '../../api/types';

interface WorkspaceSwarmPanelProps {
  selectedEventId?: string | null;
}

export default function WorkspaceSwarmPanel({ selectedEventId }: WorkspaceSwarmPanelProps = {}) {
  const opsControl = useOpsControl();
  const { registeredAgents, ephemeralAgents, agents } = opsControl;
  const agentList: AgentRegistryEntry[] = agents || registeredAgents || [];
  const ephemerals: AgentRegistryEntry[] = ephemeralAgents || [];

  const seenIds = new Set<string>();
  const allAgents: AgentRegistryEntry[] = [];

  for (const agent of [...agentList, ...ephemerals]) {
    const key = agent.agent_id || agent.role || '';
    if (key && !seenIds.has(key)) {
      seenIds.add(key);
      allAgents.push(agent);
    } else if (!key) {
      allAgents.push(agent);
    }
  }

  const effectiveEventId = selectedEventId !== undefined ? selectedEventId : opsControl.selectedEventId;

  const attachedAgents = allAgents.filter((agent) =>
    Boolean(effectiveEventId) && (
      agent.bound_event_id === effectiveEventId ||
      agent.current_event_id === effectiveEventId
    )
  );

  if (attachedAgents.length === 0) {
    return (
      <div className="p-8 text-center text-text-muted text-xs">
        <Bot size={24} className="mx-auto mb-2 opacity-40" />
        No agents active for this task.
      </div>
    );
  }

  return (
    <div className="p-3 space-y-2">
      {attachedAgents.map((agent: AgentRegistryEntry, idx) => {
        const isBusy = Boolean(agent.busy);
        const statusLabel = isBusy ? 'Busy' : 'Idle';
        const identifier = agent.current_role || agent.role || agent.agent_id || `agent-${idx}`;
        const activeEvent = agent.current_event_id || agent.bound_event_id || '—';

        return (
          <div
            key={agent.agent_id || agent.role || idx}
            className="p-3 rounded-lg border border-border bg-bg-primary flex flex-col gap-1.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isBusy ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'
                  }`}
                />
                <span className="text-xs font-semibold text-text-primary capitalize">
                  {identifier}
                </span>
                {agent.ephemeral && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-purple-950/50 text-purple-400 border border-purple-800/40">
                    ephemeral
                  </span>
                )}
              </div>

              <span className="text-[11px] text-text-muted font-mono">
                {statusLabel}
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-text-muted pt-1 border-t border-border/50">
              <span className="truncate max-w-[150px]">{agent.model || 'Autonomous'}</span>
              <span className="font-mono text-[10px] text-text-secondary">
                {activeEvent}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
