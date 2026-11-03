// BlackBoard/ui/src/components/workspace/WorkspaceHeader.tsx
// @ai-rules:
// 1. [Constraint]: Hooks only; selection comes from the selectedEventId prop with opsControl as fallback, and the header never mutates selection.
// 2. [Pattern]: The Ops Center link is a router <Link> to '/', leaving the isolated workspace perspective.
// 3. [Gotcha]: activeAgentCount dedups by agent_id || role across registered + ephemeral agents; keyless agents get a unique fallback key so they still count.
// 4. [Gotcha]: CopyButton is keyed by the effective event id so the transient "Copied" state never leaks across selection changes.
/**
 * Header for the Agent Workspace perspective.
 * Features PWA brand icon, active session title, swarm count, panel toggles, and Ops Center link.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PanelLeft, PanelRight, Radio, Pencil } from 'lucide-react';
import { useOpsControl } from '../../contexts/OpsStateContext';
import { useEventDocument } from '../../hooks/useQueue';
import { updateEventTitle } from '../../api/client';
import CopyButton from './CopyButton';
import type { AgentRegistryEntry } from '../../api/types';

interface WorkspaceHeaderProps {
  selectedEventId?: string | null;
  isSessionsOpen: boolean;
  onToggleSessions: () => void;
  isInspectorOpen: boolean;
  onToggleInspector: () => void;
}

export default function WorkspaceHeader({
  selectedEventId, isSessionsOpen, onToggleSessions, isInspectorOpen, onToggleInspector,
}: WorkspaceHeaderProps) {
  const opsControl = useOpsControl();
  const effectiveEventId = selectedEventId !== undefined ? selectedEventId : opsControl.selectedEventId;
  const { data: eventDoc } = useEventDocument(effectiveEventId || '');
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const agents: AgentRegistryEntry[] = [...(opsControl.agents || opsControl.registeredAgents || []), ...(opsControl.ephemeralAgents || [])];
  // Dedup by agent_id || role; keyless agents are kept (unique per-index fallback key) rather than dropped.
  const activeAgentCount = effectiveEventId
    ? new Set(
        agents
          .filter(a => a.bound_event_id === effectiveEventId || a.current_event_id === effectiveEventId)
          .map((a, i) => a.agent_id || a.role || `__keyless:${i}`),
      ).size
    : 0;
  const sessionLabel = eventDoc?.service || effectiveEventId || 'New Task';

  const startEditing = () => {
    setErrorMessage(null);
    setDraftTitle(eventDoc?.title || '');
    setIsEditing(true);
  };

  const handleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (isSubmitting) return;
      const clean = draftTitle.trim().replace(/\s+/g, ' ');
      if (clean && clean !== eventDoc?.title && effectiveEventId) {
        setIsSubmitting(true);
        setErrorMessage(null);
        try {
          await updateEventTitle(effectiveEventId, clean);
          setIsEditing(false);
        } catch (err) {
          console.error('Failed to update event title:', err);
          setErrorMessage('Failed to rename event');
        } finally {
          setIsSubmitting(false);
        }
      } else {
        setIsEditing(false);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (isSubmitting) return;
      setErrorMessage(null);
      setIsEditing(false);
    }
  };

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

        {isEditing ? (
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              aria-label="Event Title"
              autoFocus
              disabled={isSubmitting}
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => {
                if (!isSubmitting) {
                  setErrorMessage(null);
                  setIsEditing(false);
                }
              }}
              className="text-xs font-mono bg-bg-tertiary border border-accent rounded px-1.5 py-0.5 text-text-primary outline-none max-w-[220px] disabled:opacity-50"
            />
            {errorMessage && (
              <span className="text-[10px] text-red-400 font-sans" role="alert">{errorMessage}</span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              onClick={startEditing}
              className="text-xs font-mono text-text-secondary truncate max-w-[200px] cursor-pointer hover:text-text-primary"
              title={eventDoc?.title ? `${eventDoc.title} (Click to rename)` : undefined}
            >
              {eventDoc?.title || sessionLabel}
            </span>
            {effectiveEventId && (
              <button
                onClick={startEditing}
                className="p-1 text-text-muted hover:text-text-secondary rounded hover:bg-bg-tertiary transition-colors"
                aria-label="Rename Event"
                title="Rename Event"
              >
                <Pencil size={11} />
              </button>
            )}
          </div>
        )}

        {effectiveEventId && (
          <CopyButton key={effectiveEventId} text={effectiveEventId} label="Copy Event ID" iconSize={12} className="flex-shrink-0" />
        )}

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
