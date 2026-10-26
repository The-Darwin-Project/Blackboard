// BlackBoard/ui/src/components/workspace/useWorkspaceShortcuts.ts
// @ai-rules:
// 1. [Constraint]: Cmd/Ctrl+B and Cmd/Ctrl+J toggle panels everywhere; Escape deselects only when focus is not in a text field.
// 2. [Gotcha]: Callbacks are effect dependencies; pass stable (useCallback) handlers to avoid re-binding the window listener each render.
/**
 * Keyboard shortcuts hook for Agent Workspace (Cmd+B, Cmd+J, Escape).
 */
import { useEffect } from 'react';

interface UseWorkspaceShortcutsOptions {
  selectedEventId: string | null;
  onToggleSessions: () => void;
  onToggleInspector: () => void;
  onDeselectEvent: () => void;
}

export function useWorkspaceShortcuts({
  selectedEventId,
  onToggleSessions,
  onToggleInspector,
  onDeselectEvent,
}: UseWorkspaceShortcutsOptions) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const active = document.activeElement;
      const inText = active && (
        active.tagName === 'INPUT' ||
        active.tagName === 'TEXTAREA' ||
        (active as HTMLElement)?.isContentEditable
      );

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        onToggleSessions();
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        onToggleInspector();
      } else if (e.key === 'Escape' && !inText) {
        if (selectedEventId) {
          e.preventDefault();
          onDeselectEvent();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedEventId, onToggleSessions, onToggleInspector, onDeselectEvent]);
}
