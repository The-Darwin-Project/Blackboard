// BlackBoard/ui/src/App.tsx
// @ai-rules:
// 1. [Pattern]: Route structure: Layout wraps all authenticated routes. OpsStateProvider inside Layout.
// 2. [Pattern]: /callback route handles OIDC redirect outside the main layout.
// 3. [Constraint]: WebSocketProvider must wrap Layout (OpsStateContext uses useWSMessage).
// 4. [Pattern]: AuthGate shows LoginPage when auth enabled + not authenticated. Otherwise renders routes.
/**
 * Darwin Brain Dashboard - Main App component.
 * Sets up TanStack Query, Auth, WebSocket providers and routing.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
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
import { lazy, Suspense } from 'react';
const CortexDevPage = lazy(() => import('./components/cortex/CortexDevPage'));

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
      <Routes>
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
          <Route path="guide" element={<GuidePage />} />
          <Route path="timekeeper" element={<TimeKeeperPage />} />
          <Route path="shifts" element={<ShiftsPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="jarvis-memory" element={<JarvisMemoryPage />} />
          <Route path="cortex" element={<CortexPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
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
  const { isLoading } = useAuth();

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

  return <Navigate to="/" replace />;
}

export default App;
