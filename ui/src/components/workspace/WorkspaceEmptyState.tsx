// BlackBoard/ui/src/components/workspace/WorkspaceEmptyState.tsx
// @ai-rules:
// 1. [Constraint]: When onSelectEvent is provided it owns selection AND navigation; do not also call navigate().
// 2. [Pattern]: Without onSelectEvent, fall back to opsControl.selectEvent + navigate to /workspace/:id.
/**
 * Cold-boot empty state for Agent Workspace when no session is selected.
 * Offers starter chips and dispatches new sessions via POST /chat/ (createChatEvent).
 */
import { useState, useRef, useEffect } from 'react';
import { Bot } from 'lucide-react';
import { createChatEvent } from '../../api/client';
import { useOpsControlSafe } from '../../contexts/OpsStateContext';
import { useQueueInvalidation } from '../../hooks/useQueue';
import WorkspaceStarterChips from './WorkspaceStarterChips';
import WorkspacePromptForm from './WorkspacePromptForm';
import { useSafeNavigate } from './useSafeNavigate';

interface WorkspaceEmptyStateProps {
  onSelectEvent?: (eventId: string) => void;
}

export default function WorkspaceEmptyState({ onSelectEvent }: WorkspaceEmptyStateProps) {
  const [prompt, setPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);
  const opsControl = useOpsControlSafe();
  const navigate = useSafeNavigate();
  const { invalidateActive } = useQueueInvalidation();

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleStartSession = async (messageText: string) => {
    if (!messageText.trim() || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await createChatEvent(messageText.trim(), 'general');
      if (res?.event_id) {
        invalidateActive();
        if (onSelectEvent) {
          // Parent handler selects the event and navigates; a second navigate() would duplicate history
          onSelectEvent(res.event_id);
        } else {
          opsControl?.selectEvent(res.event_id);
          navigate?.(`/workspace/${encodeURIComponent(res.event_id)}`);
        }
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to start session');
      }
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto h-full">
      <div className="w-14 h-14 rounded-2xl bg-accent/15 border border-accent/30 flex items-center justify-center mb-4 text-accent shadow-lg shadow-accent/5">
        <Bot size={32} />
      </div>

      <h1 className="text-xl font-semibold text-text-primary mb-2">How can I help you today?</h1>
      <p className="text-sm text-text-muted mb-6 max-w-md">
        Select a common workflow below or type an objective to coordinate the swarm.
      </p>

      <WorkspaceStarterChips onSelectPrompt={setPrompt} disabled={isSubmitting} />

      <WorkspacePromptForm
        prompt={prompt}
        isSubmitting={isSubmitting}
        onChangePrompt={setPrompt}
        onSubmitPrompt={(p) => void handleStartSession(p)}
      />

      {error && <div className="mt-3 text-xs text-rose-400 bg-rose-950/40 px-3 py-1.5 rounded border border-rose-800/40">{error}</div>}
    </div>
  );
}
