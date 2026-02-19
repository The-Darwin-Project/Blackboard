// BlackBoard/ui/src/components/Layout.tsx
// @ai-rules:
// 1. [Pattern]: Header uses useTopology, useWSConnection, useActiveEvents for status and Emergency Stop.
// 2. [Pattern]: Emergency Stop sends { type: "emergency_stop" } via WS; handles emergency_stop_ack to show cancelled count.
// 3. [Pattern]: Footer consumes useConfig for contactEmail/feedbackFormUrl (AI Transparency compliance).
/**
 * 3-pane "War Room" layout for Darwin Brain Dashboard.
 * Header with status badge, main content area with responsive grid.
 */
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Activity, AlertCircle, BookOpen, CheckCircle2, FileText, Home, Square, Wifi, WifiOff } from 'lucide-react';
import { useTopology, useConfig } from '../hooks';
import { useActiveEvents } from '../hooks/useQueue';
import { useWSConnection, useWSMessage } from '../contexts/WebSocketContext';
import WaitingBell from './WaitingBell';

function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const onReports = location.pathname.startsWith('/reports');
  const { isError, isFetching } = useTopology();
  const { data: config } = useConfig();
  const { connected, send } = useWSConnection();
  const { data: activeEvents } = useActiveEvents();
  const activeCount = activeEvents?.length ?? 0;
  const canEmergencyStop = connected && activeCount > 0;

  useWSMessage((msg) => {
    if (msg.type === 'emergency_stop_ack') {
      const cancelled = (msg as { cancelled?: number }).cancelled ?? 0;
      window.alert(`Emergency stop completed. ${cancelled} task(s) cancelled.`);
    }
  });

  // Determine system status based on API connectivity
  const isOnline = !isError;
  const statusColor = isOnline ? 'text-status-healthy' : 'text-status-critical';
  const statusText = isOnline ? 'Online' : 'Offline';
  const StatusIcon = isOnline ? (isFetching ? Activity : CheckCircle2) : AlertCircle;
  const ConnectionIcon = isOnline ? Wifi : WifiOff;

  return (
    <div className="h-screen bg-bg-primary flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 bg-bg-secondary border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Darwin Brain</h1>
            <p className="text-xs text-text-muted">Autonomous Infrastructure Control</p>
          </div>
        </div>

        {/* Right side: Reports + Emergency Stop + Waiting Bell + Status Badge */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => navigate(onReports ? '/' : '/reports')}
            title={onReports ? 'Back to Dashboard' : 'View Reports'}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
          >
            {onReports ? <Home className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
            {onReports ? 'Dashboard' : 'Reports'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/guide')}
            title="User Guide"
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
          >
            <BookOpen className="w-3.5 h-3.5" />
            Guide
          </button>
          <button
            type="button"
            onClick={() => {
              if (!window.confirm('Emergency stop will cancel all active tasks. Continue?')) return;
              send({ type: 'emergency_stop' });
            }}
            disabled={!canEmergencyStop}
            title={!canEmergencyStop ? (activeCount === 0 ? 'No active events' : 'Not connected') : 'Cancel all active tasks'}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold transition-colors ${
              canEmergencyStop
                ? 'bg-red-600 text-white hover:bg-red-700 cursor-pointer'
                : 'bg-red-600/50 text-white/70 opacity-50 cursor-not-allowed'
            }`}
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            STOP
          </button>
          <WaitingBell onEventClick={(eventId) => {
            window.dispatchEvent(new CustomEvent('darwin:selectEvent', { detail: eventId }));
          }} />

          {/* Status Badge */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
            isOnline ? 'border-status-healthy/30 bg-status-healthy/10' : 'border-status-critical/30 bg-status-critical/10'
          }`}>
            <ConnectionIcon className={`w-4 h-4 ${statusColor}`} />
            <StatusIcon className={`w-4 h-4 ${statusColor} ${isFetching ? 'animate-pulse' : ''}`} />
            <span className={`text-sm font-medium ${statusColor}`}>{statusText}</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="flex-shrink-0 bg-bg-secondary border-t border-border px-6 py-2">
        <p className="text-xs text-text-muted text-center">
          AI-powered system — review responses for accuracy •{' '}
          <button type="button" onClick={() => navigate('/guide')} className="underline hover:text-text-secondary cursor-pointer">User Guide</button>
          {config?.feedbackFormUrl && (
            <> • <a href={config.feedbackFormUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-text-secondary">Submit Feedback</a></>
          )}
          {' '}• Darwin Brain v{config?.appVersion || '1.0.0'}
        </p>
      </footer>
    </div>
  );
}

export default Layout;
