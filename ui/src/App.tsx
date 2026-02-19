// BlackBoard/ui/src/App.tsx
/**
 * Darwin Brain Dashboard - Main App component.
 * Sets up TanStack Query provider and routing.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { WebSocketProvider } from './contexts/WebSocketContext';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import GuidePage from './components/GuidePage';
import ReportsPage from './components/ReportsPage';

// Configure QueryClient with default options
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <WebSocketProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="guide" element={<GuidePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </WebSocketProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
