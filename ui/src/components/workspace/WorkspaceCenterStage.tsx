// BlackBoard/ui/src/components/workspace/WorkspaceCenterStage.tsx
// @ai-rules:
// 1. [Constraint]: Close Session must go through onDeselectEvent (or opsControl.deselectEvent + navigate('/workspace', { replace: true })).
//    Never call onSelectEvent('') -- it navigates to the malformed '/workspace/'.
// 2. [Pattern]: ConversationFeed/ErrorBoundary are keyed by selectedEventId so a session switch resets feed state.
/**
 * Center stage for Agent Workspace.
 * Switches between cold-boot WorkspaceEmptyState and interactive ConversationFeed + ChatInput.
 */
import { useOpsControlSafe } from '../../contexts/OpsStateContext';
import { useQueueInvalidation } from '../../hooks/useQueue';
import ConversationFeed from '../ConversationFeed';
import ChatInput from '../ChatInput';
import ErrorBoundary from '../ErrorBoundary';
import WorkspaceEmptyState from './WorkspaceEmptyState';
import { X } from 'lucide-react';
import { useSafeNavigate } from './useSafeNavigate';

interface WorkspaceCenterStageProps {
  selectedEventId: string | null;
  onSelectEvent?: (id: string) => void;
  onDeselectEvent?: () => void;
}

export default function WorkspaceCenterStage({
  selectedEventId,
  onSelectEvent,
  onDeselectEvent,
}: WorkspaceCenterStageProps) {
  const opsControl = useOpsControlSafe();
  const navigate = useSafeNavigate();
  const { invalidateActive } = useQueueInvalidation();

  const hasEvent = Boolean(selectedEventId && selectedEventId.trim());

  if (!hasEvent || !selectedEventId) {
    return <WorkspaceEmptyState onSelectEvent={onSelectEvent} />;
  }

  const handleCloseSession = () => {
    if (onDeselectEvent) {
      onDeselectEvent();
      return;
    }
    opsControl?.deselectEvent();
    navigate?.('/workspace', { replace: true });
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-bg-primary relative">
      {/* Sub-header for active session */}
      <div className="flex-shrink-0 px-4 py-2 border-b border-border bg-bg-secondary/40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-mono font-medium text-text-primary">{selectedEventId}</span>
        </div>
        <button
          onClick={handleCloseSession}
          className="p-1 rounded text-text-muted hover:text-text-secondary hover:bg-bg-tertiary transition-colors"
          title="Close Session"
        >
          <X size={15} />
        </button>
      </div>

      {/* Main conversation feed */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        <ErrorBoundary
          key={selectedEventId}
          fallback={
            <div className="p-6 text-center text-text-muted text-sm">
              Conversation feed encountered an error. Try switching sessions.
            </div>
          }
        >
          <ConversationFeed
            key={selectedEventId}
            eventId={selectedEventId}
            onInvalidateActive={invalidateActive}
          />
        </ErrorBoundary>
      </div>

      {/* Pinned interactive ChatInput */}
      <div className="flex-shrink-0 border-t border-border bg-bg-secondary/30">
        <ChatInput
          eventId={selectedEventId}
          wsSend={opsControl?.connected ? (opsControl.send as (msg: object) => void) : undefined}
        />
      </div>
    </div>
  );
}
