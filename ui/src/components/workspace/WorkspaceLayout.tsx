// BlackBoard/ui/src/components/workspace/WorkspaceLayout.tsx
/**
 * 3-Column IDE Workspace perspective with responsive auto-collapse and keyboard shortcuts.
 * Route parameter :eventId? is the primary source of truth for session selection.
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useOpsControl } from '../../contexts/OpsStateContext';
import WorkspaceHeader from './WorkspaceHeader';
import WorkspaceSessionsHub from './WorkspaceSessionsHub';
import WorkspaceCenterStage from './WorkspaceCenterStage';
import WorkspaceInspector from './WorkspaceInspector';
import { useWorkspaceShortcuts } from './useWorkspaceShortcuts';

export default function WorkspaceLayout() {
  const { eventId: routeEventId } = useParams<{ eventId?: string }>();
  const navigate = useNavigate();
  const { selectedEventId, selectEvent, deselectEvent } = useOpsControl();

  const [isSessionsOpen, setIsSessionsOpen] = useState(() => window.innerWidth >= 1024);
  const [isInspectorOpen, setIsInspectorOpen] = useState(() => window.innerWidth >= 1024);

  // Route param is primary source of truth: sync route param -> context
  useEffect(() => {
    if (routeEventId && routeEventId !== selectedEventId) {
      selectEvent(routeEventId);
    } else if (!routeEventId && selectedEventId) {
      deselectEvent();
    }
  }, [routeEventId, selectedEventId, selectEvent, deselectEvent]);

  // Handle explicit event selection from UI: navigate to updated route
  const handleSelectEvent = useCallback((id: string) => {
    selectEvent(id);
    navigate(`/workspace/${encodeURIComponent(id)}`);
  }, [selectEvent, navigate]);

  const handleDeselectEvent = useCallback(() => {
    deselectEvent();
    navigate('/workspace');
  }, [deselectEvent, navigate]);

  // Responsive listener: auto-collapse when viewport < 1024px
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setIsSessionsOpen(false);
        setIsInspectorOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useWorkspaceShortcuts({
    selectedEventId,
    onToggleSessions: () => setIsSessionsOpen(prev => !prev),
    onToggleInspector: () => setIsInspectorOpen(prev => !prev),
    onDeselectEvent: handleDeselectEvent,
  });

  return (
    <div className="h-screen bg-bg-primary flex flex-col overflow-hidden select-none">
      <WorkspaceHeader
        selectedEventId={selectedEventId}
        isSessionsOpen={isSessionsOpen}
        onToggleSessions={() => setIsSessionsOpen(prev => !prev)}
        isInspectorOpen={isInspectorOpen}
        onToggleInspector={() => setIsInspectorOpen(prev => !prev)}
      />

      <div className="flex flex-1 overflow-hidden min-h-0">
        <WorkspaceSessionsHub
          isOpen={isSessionsOpen}
          selectedEventId={selectedEventId}
          onSelectEvent={handleSelectEvent}
          onNewTask={handleDeselectEvent}
        />

        <WorkspaceCenterStage
          selectedEventId={selectedEventId}
          onSelectEvent={handleSelectEvent}
        />

        <WorkspaceInspector
          isOpen={isInspectorOpen}
          onClose={() => setIsInspectorOpen(false)}
          selectedEventId={selectedEventId}
        />
      </div>
    </div>
  );
}
