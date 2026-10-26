// BlackBoard/ui/src/components/workspace/WorkspaceHeader.tsx
/**
 * Header for the Agent Workspace perspective.
 * Features PWA brand icon, active session title, swarm count, panel toggles, and Ops Center link.
 */
import { Link } from 'react-router-dom';
import { PanelLeft, PanelRight, Radio } from 'lucide-react';
import { useOpsControl } from '../../contexts/OpsStateContext';
import { useEventDocument } from '../../hooks/useQueue';

interface WorkspaceHeaderProps {
  selectedEventId?: string | null;
  isSessionsOpen: boolean;
  onToggleSessions: () => void;
  isInspectorOpen: boolean;
  onToggleInspector: () => void;
}

export default function WorkspaceHeader({
  selectedEventId,
  isSessionsOpen,
  onToggleSessions,
  isInspectorOpen,
  onToggleInspector,
}: WorkspaceHeaderProps) {
  const opsControl = useOpsControl();
  const effectiveEventId = selectedEventId ?? opsControl.selectedEventId;
  const { data: eventDoc } = useEventDocument(effectiveEventId || '');
  const activeAgentCount = (opsControl.agents || opsControl.registeredAgents || []).length;

  const sessionLabel = eventDoc?.service || effectiveEventId || 'New Task';

  return (
    <header className="flex-shrink-0 bg-bg-secondary border-b border-border px-4 py-2 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleSessions}
          className={`p-1.5 rounded transition-colors ${
            isSessionsOpen ? 'text-accent bg-accent/15' : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
          }`}
          title="Toggle Tasks Panel (Cmd+B)"
        >
          <PanelLeft size={16} />
        </button>

        <Link to="/workspace" className="flex items-center gap-2">
          <img src="/darwin.svg" alt="Darwin" className="w-6 h-6 rounded shadow-sm" />
          <span className="text-sm font-semibold text-text-primary tracking-tight">Darwin Workspace</span>
        </Link>

        <span className="text-text-muted text-xs">/</span>

        <span className="text-xs font-mono text-text-secondary truncate max-w-[200px]">
          {sessionLabel}
        </span>

        {activeAgentCount > 0 && (
          <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/40 border border-emerald-800/40 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {activeAgentCount} {activeAgentCount === 1 ? 'agent' : 'agents'}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <Link
          to="/"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-bg-tertiary border border-border hover:bg-bg-primary text-text-secondary text-xs font-medium transition-colors"
          title="Switch to Operations Center (Streams & Dashboards)"
        >
          <Radio size={13} className="text-blue-400" />
          <span className="hidden md:inline">Operations Center</span>
          <span className="md:hidden">Ops Center</span>
        </Link>

        <button
          onClick={onToggleInspector}
          className={`p-1.5 rounded transition-colors ${
            isInspectorOpen ? 'text-accent bg-accent/15' : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
          }`}
          title="Toggle Inspector (Cmd+J)"
        >
          <PanelRight size={16} />
        </button>
      </div>
    </header>
  );
}
