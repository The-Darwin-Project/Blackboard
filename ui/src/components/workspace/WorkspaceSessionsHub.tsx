// BlackBoard/ui/src/components/workspace/WorkspaceSessionsHub.tsx
// @ai-rules:
// 1. [Constraint]: Only evict selectedEventId if it was previously OBSERVED in activeEvents and has since disappeared.
//    A newly created / deep-linked ID is absent from a stale cache; evicting it would bounce the user to /workspace.
// 2. [Pattern]: Eviction calls onNewTask (WorkspaceLayout.handleDeselectEvent uses replace:true so Back is not trapped).
// 3. [Gotcha]: Skip eviction while a refetch is in flight; the cached list may still be stale.
/**
 * Collapsible left panel for task session switching in Agent Workspace.
 * Lists active events with Cynefin domain badges and provides '+ New Task' trigger.
 */
import { useEffect, useRef } from 'react';
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
  const { data: events = [], isLoading, isFetching } = useActiveEvents();
  const opsControl = useOpsControl();

  const selectedEventId = propSelectedEventId !== undefined ? propSelectedEventId : opsControl.selectedEventId;

  // IDs seen in the active list. Pruned on eviction so a re-opened closed event is not evicted again.
  const seenActiveIdsRef = useRef<Set<string>>(new Set());

  // Eviction listener: clear selection only when a previously active event has left the active list
  useEffect(() => {
    if (isLoading) return;
    const seen = seenActiveIdsRef.current;
    const currentIds = new Set(events.map(e => e.id));
    if (selectedEventId && seen.has(selectedEventId) && !currentIds.has(selectedEventId)) {
      if (isFetching) return;
      seen.delete(selectedEventId);
      onNewTask();
      return;
    }
    currentIds.forEach(id => seen.add(id));
  }, [events, isLoading, isFetching, selectedEventId, onNewTask]);

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
          aria-label="New Task"
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-accent/15 border border-accent/30 hover:bg-accent/25 text-accent text-xs font-medium transition-colors"
          title="Create New Task (+)"
        >
          <Plus size={13} />
          <span>New Task</span>
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
