import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import Layout from './Layout';
import { useWSConnection } from '../contexts/WebSocketContext';
import { useAuth } from '../contexts/AuthContext';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OpsControlProvider } from '../contexts/OpsStateContext';
import { ActiveStreamsProvider } from '../contexts/ActiveStreamsContext';

vi.mock('../contexts/WebSocketContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...(actual as object),
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
    } as never);
  });

  it('renders Retry Now button when connectionDegraded is true', () => {
    const mockReconnect = vi.fn();
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: true,
      reconnect: mockReconnect,
    } as never);

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <OpsControlProvider>
          <ActiveStreamsProvider>
            <Layout>
              <div>content</div>
            </Layout>
          </ActiveStreamsProvider>
        </OpsControlProvider>
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
    } as never);

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <OpsControlProvider>
          <ActiveStreamsProvider>
            <Layout>
              <div>content</div>
            </Layout>
          </ActiveStreamsProvider>
        </OpsControlProvider>
      </MemoryRouter></QueryClientProvider>
    );

    expect(screen.queryByText(/Retry Now/i)).toBeNull();
  });

  it('resets ErrorBoundary when selectedEventId changes from crashed event to new event', () => {
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: false,
      reconnect: vi.fn(),
    } as never);

    // Suppress console.error from React error boundary during test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <OpsControlProvider>
          <ActiveStreamsProvider>
            <Layout>
              <div>content</div>
            </Layout>
          </ActiveStreamsProvider>
        </OpsControlProvider>
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

describe('Layout header branding', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders the Darwin logo image alongside the brand text', () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { profile: { email: 'test@example.com' } },
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(useWSConnection).mockReturnValue({
      connectionDegraded: false,
      reconnect: vi.fn(),
    } as unknown as ReturnType<typeof useWSConnection>);

    render(
      <QueryClientProvider client={new QueryClient()}><MemoryRouter>
        <OpsControlProvider>
          <ActiveStreamsProvider>
            <Layout>
              <div>content</div>
            </Layout>
          </ActiveStreamsProvider>
        </OpsControlProvider>
      </MemoryRouter></QueryClientProvider>
    );

    const logo = screen.getByAltText('Darwin');
    expect(logo.tagName).toBe('IMG');
    expect(logo.getAttribute('src')).toBe('/darwin.svg');
    expect(screen.getAllByText('Darwin').length).toBeGreaterThan(0);
  });
});
