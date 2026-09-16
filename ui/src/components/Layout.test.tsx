import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Layout from './Layout';
import { useWSConnection } from '../contexts/WebSocketContext';
import { useAuth } from '../contexts/AuthContext';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../contexts/WebSocketContext', () => ({
  useWSConnection: vi.fn(),
  useWSReconnect: vi.fn(),
  useWSMessage: vi.fn(),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('Layout connection degraded banner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { profile: { email: 'test@example.com' } },
    } as any);
  });

  it('renders Retry Now button when connectionDegraded is true', () => {
    const mockReconnect = vi.fn();
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: true,
      reconnect: mockReconnect,
    } as any);

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter></QueryClientProvider>
    );

    const retryButton = screen.getByText(/Retry Now/i);
    expect(retryButton).toBeInTheDocument();
    
    fireEvent.click(retryButton);
    expect(mockReconnect).toHaveBeenCalledTimes(1);
  });

  it('does not render degraded banner when connectionDegraded is false', () => {
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: false,
      reconnect: vi.fn(),
    } as any);

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter></QueryClientProvider>
    );

    expect(screen.queryByText(/Retry Now/i)).not.toBeInTheDocument();
  });
});
