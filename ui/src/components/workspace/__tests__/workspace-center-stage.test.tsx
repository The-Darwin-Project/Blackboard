import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WorkspaceCenterStage from '../WorkspaceCenterStage';
import * as client from '../../../api/client';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const navigateMock = vi.hoisted(() => vi.fn());
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigateMock,
}));

// Mock dependencies
vi.mock('../../../api/client', () => ({
  createChatEvent: vi.fn(),
  enforceCasualDomain: vi.fn(),
  closeEvent: vi.fn(),
  getEventReport: vi.fn(),
}));

vi.mock('../../ConversationFeed', () => ({
  ConversationFeed: ({ eventId }: { eventId: string }) => (
    <div data-testid="conversation-feed" data-event-id={eventId}>
      Feed for {eventId}
    </div>
  ),
  default: ({ eventId }: { eventId: string }) => (
    <div data-testid="conversation-feed" data-event-id={eventId}>
      Feed for {eventId}
    </div>
  ),
}));

describe('WorkspaceCenterStage (T-5, T-6)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  const renderComponent = (props: {
    selectedEventId: string | null;
    onSelectEvent?: (id: string) => void;
  }) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <WorkspaceCenterStage
          selectedEventId={props.selectedEventId}
          onSelectEvent={props.onSelectEvent || vi.fn()}
        />
      </QueryClientProvider>
    );
  };

  it('T-5: renders Empty State with prompt chips when selectedEventId is null or empty', () => {
    const { rerender } = renderComponent({ selectedEventId: null });

    // Should display Empty State (greeting or chips)
    expect(screen.queryByTestId('conversation-feed')).not.toBeInTheDocument();
    expect(screen.getAllByText(/Ask Darwin|Review PR|Debug Pipeline|Investigate Incident|What would you like/i).length).toBeGreaterThan(0);

    // Rerender with empty string
    rerender(
      <QueryClientProvider client={queryClient}>
        <WorkspaceCenterStage
          selectedEventId=""
          onSelectEvent={vi.fn()}
        />
      </QueryClientProvider>
    );

    expect(screen.queryByTestId('conversation-feed')).not.toBeInTheDocument();
    // Must not show infinite loading spinner
    expect(screen.queryByText(/Loading event\.\.\./i)).not.toBeInTheDocument();
  });

  it('T-6: renders ConversationFeed with eventId when selectedEventId is valid', () => {
    renderComponent({ selectedEventId: 'evt-123' });

    const feed = screen.getByTestId('conversation-feed');
    expect(feed).toBeInTheDocument();
    expect(feed.getAttribute('data-event-id')).toBe('evt-123');
    expect(screen.getByText(/Feed for evt-123/i)).toBeInTheDocument();
  });

  it('T-5 cold-boot submission: triggers createChatEvent REST endpoint and calls onSelectEvent', async () => {
    const onSelectEvent = vi.fn();
    vi.mocked(client.createChatEvent).mockResolvedValueOnce({
      event_id: 'evt-new-456',
      status: 'created',
    } as never);

    renderComponent({ selectedEventId: null, onSelectEvent });

    // Look for chat input inside empty state
    const input = screen.getByPlaceholderText(/message|ask|prompt|instruct/i);
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: 'Fix pipeline failure' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(client.createChatEvent).toHaveBeenCalledWith(
        expect.stringMatching(/Fix pipeline failure/),
        expect.anything()
      );
      expect(onSelectEvent).toHaveBeenCalledWith('evt-new-456');
    });
  });

  describe('Close Session', () => {
    it('calls onDeselectEvent and never onSelectEvent(\'\') (which navigated to /workspace/)', () => {
      const onSelectEvent = vi.fn();
      const onDeselectEvent = vi.fn();
      render(
        <QueryClientProvider client={queryClient}>
          <WorkspaceCenterStage selectedEventId="evt-123" onSelectEvent={onSelectEvent} onDeselectEvent={onDeselectEvent} />
        </QueryClientProvider>
      );

      fireEvent.click(screen.getByTitle('Close Session'));

      expect(onDeselectEvent).toHaveBeenCalledTimes(1);
      expect(onSelectEvent).not.toHaveBeenCalled();
      expect(navigateMock).not.toHaveBeenCalled();
    });

    it('without onDeselectEvent: deselects via opsControl and replaces history with /workspace (not /workspace/)', () => {
      const deselectEvent = vi.fn();
      vi.spyOn(OpsStateContext, 'useOpsControlSafe').mockReturnValue({ deselectEvent, connected: false } as never);
      const onSelectEvent = vi.fn();
      render(
        <QueryClientProvider client={queryClient}>
          <WorkspaceCenterStage selectedEventId="evt-123" onSelectEvent={onSelectEvent} />
        </QueryClientProvider>
      );

      fireEvent.click(screen.getByTitle('Close Session'));

      expect(deselectEvent).toHaveBeenCalledTimes(1);
      expect(onSelectEvent).not.toHaveBeenCalled();
      expect(navigateMock).toHaveBeenCalledTimes(1);
      expect(navigateMock).toHaveBeenCalledWith('/workspace', { replace: true });
    });
  });
});
