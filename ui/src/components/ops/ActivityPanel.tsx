// BlackBoard/ui/src/components/ops/ActivityPanel.tsx
// @ai-rules:
// 1. [Pattern]: Split bottom bar -- left: Activity feed (50%), right: status indicators + operation controls.
// 2. [Pattern]: Collapsed state shows compact status strip (bell count, WS status, version, user).
// 3. [Pattern]: Expanded state shows ActivityStream on left, controls on right.
// 4. [Pattern]: Receives bell, status, user props from Layout via OpsStateContext.
import { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronDown, ChevronUp, Wifi, WifiOff, Activity, CheckCircle2, AlertCircle, User, LogOut, Square } from 'lucide-react';
import ActivityStream from '../ActivityStream';
import FlowHealthWidget from './FlowHealthWidget';
import WaitingBell from '../WaitingBell';
import { useConfig } from '../../hooks/useConfig';
import { useTopology } from '../../hooks';
import { useOpsState } from '../../contexts/OpsStateContext';
import { useAuth } from '../../contexts/AuthContext';

const MIN_HEIGHT = 32;
const DEFAULT_HEIGHT = 180;
const MAX_HEIGHT = 350;

export default function ActivityPanel() {
  const { data: config } = useConfig();
  const { isError, isFetching } = useTopology();
  const { connected, send, autoHotspot, toggleAutoHotspot } = useOpsState();
  const { user, isAuthenticated, logout } = useAuth();
  const userName = user?.profile?.preferred_username || user?.profile?.name || user?.profile?.email || '';

  const [expanded, setExpanded] = useState(
    () => localStorage.getItem('darwin:activityExpanded') !== 'false',
  );

  useEffect(() => {
    const handler = () => setExpanded(e => !e);
    window.addEventListener('darwin:toggleActivity', handler);
    return () => window.removeEventListener('darwin:toggleActivity', handler);
  }, []);
  const [height, setHeight] = useState(() => {
    const stored = localStorage.getItem('darwin:activityHeight');
    return stored ? parseInt(stored) : DEFAULT_HEIGHT;
  });
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const isOnline = !isError;
  const statusColor = isOnline ? 'text-status-healthy' : 'text-status-critical';
  const StatusIcon = isOnline ? (isFetching ? Activity : CheckCircle2) : AlertCircle;
  const ConnectionIcon = isOnline ? Wifi : WifiOff;

  useEffect(() => {
    localStorage.setItem('darwin:activityExpanded', String(expanded));
  }, [expanded]);

  useEffect(() => {
    if (expanded) localStorage.setItem('darwin:activityHeight', String(height));
  }, [height, expanded]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      if (!panelRef.current) return;
      const rect = panelRef.current.getBoundingClientRect();
      setHeight(Math.min(MAX_HEIGHT, Math.max(80, rect.bottom - e.clientY)));
    };
    const onUp = () => setIsResizing(false);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const ToggleIcon = expanded ? ChevronDown : ChevronUp;

  return (
    <div ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-t border-border flex flex-col"
      style={{ height: expanded ? height : MIN_HEIGHT, transition: isResizing ? 'none' : 'height 0.15s ease' }}>

      {/* Resize handle (only when expanded) */}
      {expanded && (
        <div className={`h-1 flex-shrink-0 cursor-row-resize group ${isResizing ? 'bg-accent/20' : ''}`}
          onMouseDown={startResize}>
          <div className={`h-px w-full transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
        </div>
      )}

      {/* Status bar (always visible -- collapsed shows this only) */}
      <div className="flex items-center px-3 flex-shrink-0 gap-3" style={{ height: MIN_HEIGHT }}>
        {/* Left: Activity toggle */}
        <button onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary transition-colors cursor-pointer bg-transparent border-none p-0">
          <ToggleIcon size={14} />
          <span>Activity</span>
        </button>

        <div className="w-px h-4 bg-border" />

        {/* Center: Bell + Auto-Hotspot + Emergency */}
        <WaitingBell onEventClick={(eventId) => {
          window.dispatchEvent(new CustomEvent('darwin:selectEvent', { detail: eventId }));
        }} />

        <button type="button" onClick={toggleAutoHotspot}
          title={autoHotspot ? 'Auto-focus active agent (ON)' : 'Auto-focus active agent (OFF)'}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors border ${
            autoHotspot
              ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-400'
              : 'border-border bg-bg-tertiary text-text-muted hover:text-text-secondary'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${autoHotspot ? 'bg-emerald-400' : 'bg-slate-600'}`} />
          Auto
        </button>

        <button type="button"
          onClick={() => {
            if (!window.confirm('Emergency stop will cancel all active tasks. Continue?')) return;
            send({ type: 'emergency_stop' });
          }}
          disabled={!connected}
          title={!connected ? 'Not connected' : 'Cancel all active tasks'}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
            connected
              ? 'bg-red-600 text-white hover:bg-red-700 cursor-pointer'
              : 'bg-red-600/50 text-white/70 opacity-50 cursor-not-allowed'
          }`}>
          <Square className="w-3 h-3 fill-current" />
          STOP
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right: WS status + User + Version */}
        <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] ${
          isOnline ? 'border-status-healthy/30 bg-status-healthy/10' : 'border-status-critical/30 bg-status-critical/10'
        }`}>
          <ConnectionIcon className={`w-3.5 h-3.5 ${statusColor}`} />
          <StatusIcon className={`w-3.5 h-3.5 ${statusColor} ${isFetching ? 'animate-pulse' : ''}`} />
          <span className={`font-medium ${statusColor}`}>{isOnline ? 'Online' : 'Offline'}</span>
        </div>

        {isAuthenticated && userName && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-500/10">
            <User className="w-3 h-3 text-indigo-400" />
            <span className="text-[11px] font-medium text-indigo-300">{userName}</span>
            <button type="button"
              onClick={() => { if (window.confirm('Logout?')) logout(); }}
              title="Logout"
              className="p-0.5 rounded hover:bg-indigo-500/20 transition-colors cursor-pointer">
              <LogOut className="w-3 h-3 text-indigo-400" />
            </button>
          </div>
        )}

        <span className="text-[10px] text-text-muted">
          {config?.appVersion && <>v{config.appVersion}</>}
          {config?.feedbackFormUrl && (
            <> · <a href={config.feedbackFormUrl} target="_blank" rel="noopener noreferrer"
              className="underline hover:text-text-secondary">Feedback</a></>
          )}
        </span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="flex-1 overflow-hidden min-h-0 flex">
          {/* Left: Activity stream */}
          <div className="flex-1 overflow-auto border-r border-border">
            <ActivityStream />
          </div>
          {/* Right: Flow health + system logs */}
          <div className="flex-1 overflow-auto flex flex-col">
            <div className="flex-shrink-0 border-b border-border">
              <FlowHealthWidget />
            </div>
            <div className="flex-1 overflow-auto p-3 text-[12px] text-text-muted flex items-center justify-center">
              <span className="italic">System logs and quick actions</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
