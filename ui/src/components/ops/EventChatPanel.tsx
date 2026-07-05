// BlackBoard/ui/src/components/ops/EventChatPanel.tsx
// @ai-rules:
// 1. [Origin]: Extracted from EventSidebar lines 390-500. Full-height event conversation panel.
// 2. [Pattern]: Two-header design: identity card + ConversationFeed (owns its own actions header).
// 3. [Pattern]: key={eventId} on ConversationFeed forces state reset on event switch.
// 4. [Pattern]: Resize handle on right edge. Width persisted in localStorage (darwin:chatPanelWidth).
// 5. [Constraint]: ConversationFeed gets onOpenContentTile from OpsStateContext for grid content tiles.
import { X } from 'lucide-react';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useOpsControl } from '../../contexts/OpsStateContext';
import { useEventDocument, useActiveEvents, useQueueInvalidation } from '../../hooks/useQueue';
import { STATUS_COLORS } from '../../constants/colors';
import { MOCK_EVENTS, MOCK_EVENT_DOC } from './mockData';
import SourceIcon from '../SourceIcon';
import { ConversationFeed } from '../ConversationFeed';
import { PlanProgress, usePlanState } from '../PlanProgress';
import ChatInput from '../ChatInput';
import CollapsibleSection from '../CollapsibleSection';
import DeferCountdownBar from '../DeferCountdownBar';
import MockConversationFeed from './MockConversationFeed';
import type { ConversationTurn } from '../../api/types';

const DEV_MODE = import.meta.env.DEV;
const MIN_WIDTH = 350;
const DEFAULT_WIDTH = 500;
const MAX_WIDTH = 900;

interface EventChatPanelProps {
  eventId: string;
  onClose: () => void;
}

export default function EventChatPanel({ eventId, onClose }: EventChatPanelProps) {
  const { connected, send, openContentTile } = useOpsControl();
  const { data: eventDoc, isLoading: docLoading, isError: docError } = useEventDocument(eventId);
  const { data: activeEvents } = useActiveEvents();
  const { hasPlan, steps: planSteps } = usePlanState(eventDoc?.conversation || []);
  const { invalidateActive } = useQueueInvalidation();

  const isDemoMode = DEV_MODE && (!activeEvents || activeEvents.length === 0);
  const isMockEvent = isDemoMode && eventId?.startsWith('evt-demo');
  const events = isDemoMode ? MOCK_EVENTS : activeEvents || [];
  const listEvt = events.find(e => e.id === eventId);

  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', min: MIN_WIDTH, max: MAX_WIDTH, defaultSize: DEFAULT_WIDTH,
    storageKey: 'darwin:chatPanelWidth',
  });

  if (!isMockEvent && docLoading) {
    return (
      <div ref={panelRef} className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex flex-col" style={{ width }}>
        <div className="flex items-center justify-between px-3 py-2 border-b border-border flex-shrink-0">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Event</span>
          <button onClick={onClose} className="p-1 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-secondary" title="Close"><X size={16} /></button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-text-muted text-sm animate-pulse">Loading event...</div>
        </div>
      </div>
    );
  }

  if (!isMockEvent && (docError || !eventDoc)) {
    return (
      <div ref={panelRef} className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex flex-col" style={{ width }}>
        <div className="flex items-center justify-between px-3 py-2 border-b border-border flex-shrink-0">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Event</span>
          <button onClick={onClose} className="p-1 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-secondary" title="Close"><X size={16} /></button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-2 px-4">
          <span className="text-text-muted text-sm">Event conversation unavailable</span>
          <span className="text-text-muted text-xs">Document may have been archived or cleaned up.</span>
          <button onClick={onClose}
            className="mt-2 text-xs px-3 py-1 rounded border border-border hover:bg-bg-tertiary text-text-secondary transition-colors">
            Close
          </button>
        </div>
      </div>
    );
  }

  const doc = isMockEvent ? MOCK_EVENT_DOC : eventDoc!;

  return (
    <div ref={panelRef} className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex relative" style={{ width }}>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Identity card header */}
        <div className="flex-shrink-0 px-1.5 pt-2 pb-1 border-b border-border">
          <div className="flex flex-col gap-2 px-3 py-2 rounded-lg border"
            style={{ background: `${STATUS_COLORS[doc.status]?.border || '#3b82f6'}08`, borderColor: `${STATUS_COLORS[doc.status]?.border || '#3b82f6'}30` }}>
            <div className="flex items-center gap-2.5 min-w-0">
              {isDemoMode && <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold flex-shrink-0">DEMO</span>}
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: STATUS_COLORS[doc.status]?.border || '#3b82f6' }} />
              <SourceIcon source={doc.source} size={16} />
              <span className="text-[13px] font-mono truncate flex-1" style={{ color: STATUS_COLORS[doc.status]?.text || '#93c5fd' }}>{eventId}</span>
              <span className="text-[11px] px-1.5 py-0.5 rounded font-medium flex-shrink-0"
                style={{ background: STATUS_COLORS[doc.status]?.bg || '#1e293b', color: STATUS_COLORS[doc.status]?.text || '#93c5fd' }}>
                {STATUS_COLORS[doc.status]?.label || doc.status}
              </span>
              <button onClick={onClose}
                className="flex items-center justify-center w-6 h-6 rounded border border-border hover:border-red-500/50 hover:bg-red-500/10 text-text-muted hover:text-red-400 transition-colors text-sm font-bold flex-shrink-0"
                title="Close event">&times;</button>
            </div>
            {doc.status === 'deferred' && (
              <DeferCountdownBar
                deferUntil={listEvt?.defer_until}
                deferStartedAt={listEvt?.defer_started_at}
                conversation={doc.conversation as ConversationTurn[]}
              />
            )}
          </div>
        </div>

        {/* Conversation feed — flex-1, ConversationFeed owns its own actions header */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {isMockEvent
            ? <MockConversationFeed />
            : <ConversationFeed
                key={eventId}
                eventId={eventId}
                onInvalidateActive={invalidateActive}
                onOpenContentTile={openContentTile}
              />
          }
        </div>

        {/* Plan + Details — constrained bottom section */}
        <div className="flex-shrink-0 overflow-auto px-1.5 pb-1" style={{ maxHeight: '30%' }}>
          {hasPlan && (
            <CollapsibleSection title="Plan" badge={
              <span className="text-[12px] text-text-muted">{planSteps.filter(s => s.status === 'completed').length}/{planSteps.length}</span>
            }>
              <PlanProgress conversation={doc.conversation as ConversationTurn[]} />
            </CollapsibleSection>
          )}
          <CollapsibleSection title="Details">
            <div className="space-y-1.5 text-[13px] text-text-muted">
              <div className="flex justify-between"><span>Source</span><span className="flex items-center gap-1"><SourceIcon source={doc.source} size={18} />{doc.source}</span></div>
              <div className="flex justify-between"><span>{doc.subject_type === 'kargo_stage' ? 'Stage' : 'Service'}</span><span className="text-text-secondary">{doc.service}</span></div>
              {doc.event?.evidence?.triggered_by && (
                <div className="flex justify-between"><span>User</span><span className="text-text-secondary">{doc.event.evidence.triggered_by}</span></div>
              )}
              <div className="flex justify-between"><span>Status</span>
                <span className="px-1.5 py-0.5 rounded text-[12px] font-medium"
                  style={{ background: STATUS_COLORS[doc.status]?.bg || '#1e293b', color: STATUS_COLORS[doc.status]?.text || '#94a3b8' }}>
                  {doc.status}
                </span>
              </div>
              <div className="flex justify-between"><span>Turns</span><span>{doc.conversation.length}</span></div>
            </div>
          </CollapsibleSection>
          {doc.sticky_notes && doc.sticky_notes.length > 0 && (
            <CollapsibleSection title="Sticky Notes" badge={
              <span className="text-[12px] text-yellow-400">{doc.sticky_notes.length}</span>
            }>
              <div className="space-y-1.5">
                {doc.sticky_notes.map((note: { timestamp: string; content: string; read: boolean }, i: number) => (
                  <div key={i} className="text-[13px] rounded px-2 py-1.5"
                    style={{
                      borderLeft: `3px solid ${note.read ? '#475569' : '#facc15'}`,
                      background: note.read ? '#1e293b40' : '#facc1508',
                      opacity: note.read ? 0.6 : 1,
                    }}>
                    <div className="text-text-muted text-[11px] mb-0.5">
                      {new Date(note.timestamp).toLocaleString()}
                    </div>
                    <div className="text-text-secondary">{note.content}</div>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>

        {/* ChatInput pinned bottom */}
        <div className="flex-shrink-0 border-t border-border">
          <ChatInput eventId={eventId} wsSend={connected ? send as (msg: object) => void : undefined} />
        </div>
      </div>

      {/* Resize handle */}
      <div className={`absolute top-0 right-0 w-1.5 h-full cursor-col-resize group ${isResizing ? 'bg-accent/30' : ''}`}
        onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>
    </div>
  );
}
