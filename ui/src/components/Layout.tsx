// BlackBoard/ui/src/components/Layout.tsx
// @ai-rules:
// 1. [Pattern]: Operations Center shell -- header (logo + tabs only), persistent sidebar, main content (Outlet), bottom bar.
// 2. [Pattern]: OpsStateProvider wraps children. All controls (bell, status, user, STOP, auto) live in ActivityPanel bottom bar.
// 3. [Pattern]: Header tabs are route-based (useLocation + useNavigate). Active tab highlighted.
// 4. [Gotcha]: darwin:selectEvent custom event listener bridges WaitingBell -> OpsStateContext.selectEvent.
/**
 * Darwin Operations Center layout.
 * Header: logo + tabs only (clean, minimal).
 * Bottom bar: activity feed + bell + status + controls (XProtect-style status strip).
 */
import { useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { OpsStateProvider, useOpsState } from '../contexts/OpsStateContext';
import EventSidebar from './ops/EventSidebar';
import ActivityPanel from './ops/ActivityPanel';

const TABS = [
  { id: '/', label: 'Streams' },
  { id: '/topology', label: 'Topology' },
  { id: '/reports', label: 'Reports' },
  { id: '/timekeeper', label: 'TimeKeeper' },
  { id: '/guide', label: 'Guide' },
] as const;

function LayoutInner() {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectEvent } = useOpsState();

  const activeTab = TABS.find(t => t.id === location.pathname)?.id
    || (location.pathname.startsWith('/reports') ? '/reports' : '/');

  useEffect(() => {
    const handler = (e: Event) => {
      const eventId = (e as CustomEvent).detail;
      if (eventId) selectEvent(eventId);
    };
    window.addEventListener('darwin:selectEvent', handler);
    return () => window.removeEventListener('darwin:selectEvent', handler);
  }, [selectEvent]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const active = document.activeElement;
      if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
      if (!e.altKey) return;
      const tabIndex = parseInt(e.key);
      if (tabIndex >= 1 && tabIndex <= TABS.length) {
        e.preventDefault();
        navigate(TABS[tabIndex - 1].id);
      }
      if (e.key === '[') { e.preventDefault(); window.dispatchEvent(new CustomEvent('darwin:toggleSidebar')); }
      if (e.key === ']') { e.preventDefault(); window.dispatchEvent(new CustomEvent('darwin:toggleSidebar')); }
      if (e.key === '`') { e.preventDefault(); window.dispatchEvent(new CustomEvent('darwin:toggleActivity')); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [navigate]);

  return (
    <div className="h-screen bg-bg-primary flex flex-col overflow-hidden">
      {/* Header -- clean: logo + tabs only */}
      <header className="flex-shrink-0 bg-bg-secondary border-b border-border px-4 py-1.5 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <Activity className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="text-sm font-semibold text-text-primary hidden lg:block">Darwin</span>
        </div>

        <nav className="flex items-center gap-0.5">
          {TABS.map((tab) => (
            <button key={tab.id} onClick={() => navigate(tab.id)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-accent/20 text-accent'
                  : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
              }`}>
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Body: Sidebar + Main Content */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        <EventSidebar />
        <main className="flex-1 overflow-hidden min-w-0 relative">
          <div className="absolute inset-0">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Bottom bar: Activity feed + Status strip + Controls */}
      <ActivityPanel />
    </div>
  );
}

export default function Layout() {
  return (
    <OpsStateProvider>
      <LayoutInner />
    </OpsStateProvider>
  );
}
