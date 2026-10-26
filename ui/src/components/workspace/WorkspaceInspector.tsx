// BlackBoard/ui/src/components/workspace/WorkspaceInspector.tsx
/**
 * Collapsible & resizable right sidebar for Agent Workspace.
 * Hosts Plan execution, Diff viewer, Swarm topology, and Live Logs tabs.
 */
import { useState, useMemo } from 'react';
import { ListTodo, GitCompare, Users, Terminal, X } from 'lucide-react';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useEventDocument } from '../../hooks/useQueue';
import PlanProgress from '../PlanProgress';
import WorkspaceDiffViewer from './WorkspaceDiffViewer';
import WorkspaceSwarmPanel from './WorkspaceSwarmPanel';
import ActivityStream from '../ActivityStream';
import { extractDiffsFromConversation } from './diffParser';
import type { ConversationTurn } from '../../api/types';

interface WorkspaceInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selectedEventId: string | null;
}

type TabType = 'plan' | 'diffs' | 'swarm' | 'logs';

export default function WorkspaceInspector({ isOpen, onClose, selectedEventId }: WorkspaceInspectorProps) {
  const [activeTab, setActiveTab] = useState<TabType>('plan');
  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', anchor: 'right', min: 300, max: 700, defaultSize: 420,
    storageKey: 'darwin:workspaceInspectorWidth', enabled: isOpen,
  });

  const { data: eventDoc } = useEventDocument(selectedEventId);
  const conversation = (eventDoc?.conversation as ConversationTurn[]) || [];
  const diffs = useMemo(() => extractDiffsFromConversation(conversation), [conversation]);

  if (!isOpen) return null;

  return (
    <aside ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-l border-border h-full flex flex-col relative select-none" style={{ width }}>
      <div className="absolute top-0 left-0 w-1.5 h-full cursor-col-resize group" onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>

      <div className="flex-shrink-0 px-3 py-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-1 bg-bg-tertiary p-0.5 rounded-lg text-xs">
          <button onClick={() => setActiveTab('plan')} className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${activeTab === 'plan' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}`}>
            <ListTodo size={13} /><span>Plan</span>
          </button>
          <button onClick={() => setActiveTab('diffs')} className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${activeTab === 'diffs' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}`}>
            <GitCompare size={13} /><span>Diffs{diffs.length > 0 && ` (${diffs.length})`}</span>
          </button>
          <button onClick={() => setActiveTab('swarm')} className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${activeTab === 'swarm' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}`}>
            <Users size={13} /><span>Swarm</span>
          </button>
          <button onClick={() => setActiveTab('logs')} className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${activeTab === 'logs' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}`}>
            <Terminal size={13} /><span>Logs</span>
          </button>
        </div>
        <button onClick={onClose} aria-label="Close Inspector" title="Close Inspector (Cmd+J)" className="p-1 rounded text-text-muted hover:text-text-secondary hover:bg-bg-tertiary transition-colors"><X size={15} /></button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === 'plan' && (
          conversation.length > 0
            ? <PlanProgress conversation={conversation} />
            : <div className="p-8 text-center text-text-muted text-xs">No active execution plan for this session.</div>
        )}
        {activeTab === 'diffs' && <WorkspaceDiffViewer diffs={diffs} />}
        {activeTab === 'swarm' && <WorkspaceSwarmPanel />}
        {activeTab === 'logs' && <ActivityStream />}
      </div>
    </aside>
  );
}
