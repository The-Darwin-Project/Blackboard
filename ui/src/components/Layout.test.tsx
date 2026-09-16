import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import Layout from './Layout';
import { useWSConnection } from '../contexts/WebSocketContext';
import { useAuth } from '../contexts/AuthContext';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../contexts/WebSocketContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual as any,
  useWSConnection: vi.fn(),
  useWSReconnect: vi.fn(),
  useWSMessage: vi.fn(),
  };
});

vi.mock('../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));


vi.mock('./ops/EventChatPanel', () => ({
  default: ({ eventId }: { eventId: string }) => {
    if (eventId === 'bad-event') {
      throw new Error('Simulated panel render crash');
    }
    return <div data-testid="chat-panel">Chat for {eventId}</div>;
  },
}));
describe('Layout connection degraded banner', () => {
  afterEach(() => {
    cleanup();
  });

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
    expect(retryButton).toBeTruthy();
    
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

    expect(screen.queryByText(/Retry Now/i)).toBeNull();
  });

  it('resets ErrorBoundary when selectedEventId changes from crashed event to new event', () => {
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: false,
      reconnect: vi.fn(),
    } as any);

    // Suppress console.error from React error boundary during test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { rerender } = render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter></QueryClientProvider>
    );

    // Trigger selectEvent for 'bad-event' via custom event bridge
    fireEvent(window, new CustomEvent('darwin:selectEvent', { detail: 'bad-event' }));

    expect(screen.getByText(/Event panel encountered an error/i)).toBeTruthy();

    // Now switch to 'good-event' -- key change must reset ErrorBoundary
    fireEvent(window, new CustomEvent('darwin:selectEvent', { detail: 'good-event' }));

    expect(screen.queryByText(/Event panel encountered an error/i)).toBeNull();
    expect(screen.getByTestId('chat-panel')).toBeTruthy();
    expect(screen.getByText('Chat for good-event')).toBeTruthy();

    consoleSpy.mockRestore();
  });
});
