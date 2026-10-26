// BlackBoard/ui/src/components/workspace/WorkspaceSessionsHub.tsx
/**
 * Collapsible left panel for task session switching in Agent Workspace.
 * Lists active events with Cynefin domain badges and provides '+ New Task' trigger.
 */
import { useEffect } from 'react';
import { Plus } from 'lucide-react';
import { useActiveEvents } from '../../hooks/useQueue';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useOpsControl } from '../../contexts/OpsStateContext';
import WorkspaceTaskItem from './WorkspaceTaskItem';
import type { ActiveEvent } from '../../api/types';

interface WorkspaceSessionsHubProps {
  isOpen: boolean;
  selectedEventId?: string | null;
  onSelectEvent?: (eventId: string) => void;
  onNewTask: () => void;
}

export default function WorkspaceSessionsHub({
  isOpen,
  selectedEventId: propSelectedEventId,
  onSelectEvent: propOnSelectEvent,
  onNewTask,
}: WorkspaceSessionsHubProps) {
  const { data: events = [], isLoading } = useActiveEvents();
  const opsControl = useOpsControl();

  const selectedEventId = propSelectedEventId !== undefined ? propSelectedEventId : opsControl.selectedEventId;

  // Eviction listener: if an active event terminates and is no longer present, clear selection
  useEffect(() => {
    if (!isLoading && events.length > 0 && selectedEventId) {
      if (!events.some(e => e.id === selectedEventId)) {
        onNewTask();
      }
    }
  }, [events, isLoading, selectedEventId, onNewTask]);

  const handleSelect = (id: string) => {
    if (propOnSelectEvent) {
      propOnSelectEvent(id);
    } else {
      opsControl.selectEvent(id);
    }
  };

  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', min: 220, max: 450, defaultSize: 280,
    storageKey: 'darwin:workspaceSessionsWidth', enabled: isOpen,
  });

  if (!isOpen) return null;

  return (
    <aside ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-r border-border h-full flex flex-col relative select-none" style={{ width }}>
      <div className="p-3 border-b border-border flex items-center justify-between">
        <span className="text-xs font-semibold text-text-primary tracking-wider uppercase">Active Tasks</span>
        <button
          onClick={onNewTask}
          aria-label="+ New Task"
          className="flex items-center gap-1 px-2 py-1 rounded bg-accent/15 border border-accent/30 hover:bg-accent/25 text-accent text-xs font-medium transition-colors"
          title="Create New Task (+)"
        >
          <Plus size={13} />
          <span>+ New Task</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {isLoading && <div className="p-4 text-center text-xs text-text-muted animate-pulse">Loading tasks...</div>}
        {!isLoading && events.length === 0 && <div className="p-4 text-center text-xs text-text-muted">No active tasks. Click New to start.</div>}
        {events.map((evt: ActiveEvent) => (
          <WorkspaceTaskItem key={evt.id} evt={evt} isSelected={evt.id === selectedEventId} onSelect={handleSelect} />
        ))}
      </div>

      <div className={`absolute top-0 right-0 w-1.5 h-full cursor-col-resize group ${isResizing ? 'bg-accent/40' : ''}`} onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>
    </aside>
  );
}
