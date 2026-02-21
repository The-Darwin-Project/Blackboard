// BlackBoard/ui/src/components/AgentRegistryPanel.tsx
// @ai-rules:
// 1. [Pattern]: Polls GET /api/agents every 10s. Pure display component.
// 2. [Pattern]: Uses ACTOR_COLORS for role badges; status badge idle (green) / busy (amber).
// 3. [Gotcha]: connected_at is Unix timestamp (seconds); format as relative time.
/**
 * Agent Registry panel — shows connected sidecars with role, status, and current event.
 */
import { useState, useEffect, useCallback } from 'react';
import { Loader2, Users } from 'lucide-react';
import { getAgents } from '../api/client';
import type { AgentRegistryEntry } from '../api/types';
import { ACTOR_COLORS } from '../constants/colors';

function formatConnectedSince(ts: number): string {
  const sec = Math.floor(Date.now() / 1000 - ts);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function AgentRegistryPanel() {
  const [agents, setAgents] = useState<AgentRegistryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      const data = await getAgents();
      setAgents(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agents');
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
    const id = setInterval(fetchAgents, 10_000);
    return () => clearInterval(id);
  }, [fetchAgents]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[120px]">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[120px] text-text-muted gap-2">
        <Users className="w-12 h-12" />
        <p className="text-sm">Unable to load agents</p>
        <p className="text-xs">{error}</p>
      </div>
    );
  }

  if (!agents.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[120px] text-text-muted gap-2">
        <Users className="w-12 h-12" />
        <p className="text-sm">No agents connected</p>
        <p className="text-xs">Sidecars will appear when they connect</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 overflow-auto">
      {agents.map((a) => {
        const roleColor = ACTOR_COLORS[a.role] || '#64748b';
        return (
          <div
            key={a.agent_id}
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            <div className="flex items-center justify-between gap-2 mb-1">
              <span
                style={{
                  background: roleColor,
                  color: '#fff',
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {a.role}
              </span>
              <span
                style={{
                  background: a.busy ? '#f59e0b15' : '#22c55e15',
                  color: a.busy ? '#f59e0b' : '#22c55e',
                  padding: '1px 6px',
                  borderRadius: 8,
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                {a.busy ? 'busy' : 'idle'}
              </span>
            </div>
            <div className="text-xs text-text-muted font-mono truncate" title={a.agent_id}>
              {a.agent_id}
            </div>
            {a.current_event_id && (
              <div className="text-xs text-text-muted mt-1 truncate" title={a.current_event_id}>
                Event: {a.current_event_id.slice(0, 12)}…
              </div>
            )}
            <div className="text-xs text-text-muted mt-0.5">
              Connected {formatConnectedSince(a.connected_at)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default AgentRegistryPanel;
