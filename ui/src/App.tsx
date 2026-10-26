// BlackBoard/ui/src/App.tsx
// @ai-rules:
// 1. [Pattern]: Route structure: Layout wraps Ops routes; /workspace/:eventId? renders isolated Agent Workspace.
// 2. [Pattern]: OpsControlProvider & ActiveStreamsProvider lifted inside AuthGate to serve both Layout and Workspace.
// 3. [Pattern]: /callback route handles OIDC redirect outside the main layout.
// 4. [Constraint]: WebSocketProvider must wrap Layout and Workspace routes (OpsStateContext uses useWSMessage).
// 5. [Pattern]: AuthGate shows LoginPage when auth enabled + not authenticated. Otherwise renders routes.
/**
 * Darwin Brain Dashboard - Main App component.
 * Sets up TanStack Query, Auth, WebSocket providers and routing.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { OpsControlProvider } from './contexts/OpsStateContext';
import { ActiveStreamsProvider } from './contexts/ActiveStreamsContext';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import GuidePage from './components/GuidePage';
import ReportsPage from './components/ReportsPage';
import EventHistory from './components/EventHistory';
import LoginPage from './components/LoginPage';
import IncidentsPage from './components/IncidentsPage';
import InsightsPage from './components/InsightsPage';
import TimeKeeperPage from './components/timekeeper/TimeKeeperPage';
import TopologyView from './components/ops/TopologyView';
import MemoryPage from './components/memory/MemoryPage';
import ShiftsPage from './components/ShiftsPage';
import JarvisMemoryPage from './components/JarvisMemoryPage';
import CortexPage from './components/cortex/CortexPage';
import { lazy, Suspense, Component, type ReactNode } from 'react';
const CortexDevPage = lazy(() => import('./components/cortex/CortexDevPage'));
const WorkspaceLayout = lazy(() => import('./components/workspace/WorkspaceLayout'));

function WorkspaceLoading() {
  return (
    <div className="h-screen bg-bg-primary flex items-center justify-center text-text-muted text-sm">
      Loading Workspace...
    </div>
  );
}
import FlowHistoryPage from './components/FlowHistoryPage';
import TokenUtilizationPage from './components/TokenUtilizationPage';
import ErrorBoundary from './components/ErrorBoundary';

class WipErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean}> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return <div className="p-4 text-text-muted">WIP tab encountered an error. Try refreshing.</div>;
    }
    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthGate() {
  const { isAuthenticated, isLoading, authConfig } = useAuth();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#030712', color: '#64748b',
      }}>
        Loading...
      </div>
    );
  }

  if (authConfig?.enabled && !isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <WebSocketProvider>
      <OpsControlProvider>
        <ActiveStreamsProvider>
          <Routes>
            <Route
              path="/workspace/:eventId?"
              element={
                <ErrorBoundary
                  fallback={
                    <div className="h-screen bg-bg-primary flex items-center justify-center text-rose-400 text-sm">
                      Agent Workspace encountered an error. Try refreshing or navigating back to Ops Center.
                    </div>
                  }
                >
                  <Suspense fallback={<WorkspaceLoading />}>
                    <WorkspaceLayout />
                  </Suspense>
                </ErrorBoundary>
              }
            />
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="topology" element={<TopologyView />} />
              <Route path="reports" element={
                import.meta.env.VITE_EVENT_HISTORY_ENABLED === 'true'
                  ? <EventHistory />
                  : <ReportsPage />
              } />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="insights" element={<InsightsPage />} />
              <Route path="wip" element={
                <WipErrorBoundary>
                  <FlowHistoryPage />
                </WipErrorBoundary>
              } />
              <Route path="flow/tokens" element={
                <WipErrorBoundary>
                  <TokenUtilizationPage />
                </WipErrorBoundary>
              } />
              <Route path="guide" element={<GuidePage />} />
              <Route path="timekeeper" element={<TimeKeeperPage />} />
              <Route path="shifts" element={<ShiftsPage />} />
              <Route path="memory" element={<MemoryPage />} />
              <Route path="jarvis-memory" element={<JarvisMemoryPage />} />
              <Route path="cortex" element={<CortexPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ActiveStreamsProvider>
      </OpsControlProvider>
    </WebSocketProvider>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/callback" element={<AuthCallbackHandler />} />
            <Route path="/cortex-dev" element={<Suspense fallback={<div>Loading...</div>}><CortexDevPage /></Suspense>} />
            <Route path="*" element={<AuthGate />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AuthCallbackHandler() {
  const { isLoading, postLoginRedirect } = useAuth();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#030712', color: '#64748b',
      }}>
        Completing login...
      </div>
    );
  }

  return <Navigate to={postLoginRedirect} replace />;
}

export default App;
