// BlackBoard/ui/src/App.tsx
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
import LoginPage from './components/LoginPage';
import TimeKeeperPage from './components/timekeeper/TimeKeeperPage';

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
          <Route path="reports" element={<ReportsPage />} />
          <Route path="guide" element={<GuidePage />} />
          <Route path="timekeeper" element={<TimeKeeperPage />} />
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
