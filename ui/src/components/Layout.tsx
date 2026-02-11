// BlackBoard/ui/src/components/Layout.tsx
/**
 * 3-pane "War Room" layout for Darwin Brain Dashboard.
 * Header with status badge, main content area with responsive grid.
 */
import { Outlet } from 'react-router-dom';
import { Activity, AlertCircle, CheckCircle2, Wifi, WifiOff } from 'lucide-react';
import { useTopology } from '../hooks';
import WaitingBell from './WaitingBell';

function Layout() {
  const { isError, isFetching } = useTopology();

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

        {/* Right side: Waiting Bell + Status Badge */}
        <div className="flex items-center gap-4">
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
          Darwin Brain v1.0.0 • Trinity Agents: Aligner, Architect, SysAdmin
        </p>
      </footer>
    </div>
  );
}

export default Layout;
