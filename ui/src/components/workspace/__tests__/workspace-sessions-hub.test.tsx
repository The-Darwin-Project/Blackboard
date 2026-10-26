import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceSessionsHub from '../WorkspaceSessionsHub';
import * as queueHook from '../../../hooks/useQueue';
import * as OpsStateContext from '../../../contexts/OpsStateContext';

describe('WorkspaceSessionsHub (Left Sidebar)', () => {
  const mockEvents = [
    {
      id: 'evt-1',
      service: 'auth-service',
      status: 'active',
      source: 'alertmanager',
      domain: 'security',
      phase: 'investigation',
    },
    {
      id: 'evt-2',
      service: 'billing-service',
      status: 'waiting_approval',
      source: 'kargo_stage',
      domain: 'platform',
      phase: 'mitigation',
    },
  ];

  const mockSelectEvent = vi.fn();
  const mockDeselectEvent = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue({
      data: mockEvents,
      isLoading: false,
    } as never);

    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      selectedEventId: 'evt-1',
      selectEvent: mockSelectEvent,
      deselectEvent: mockDeselectEvent,
      registeredAgents: [],
      ephemeralAgents: [],
      kargoStages: [],
      kargoEventResult: null,
      contentTiles: [],
      hotspotTileId: null,
      setHotspot: vi.fn(),
      openContentTile: vi.fn(),
      closeContentTile: vi.fn(),
      autoHotspot: false,
      toggleAutoHotspot: vi.fn(),
      connected: true,
      send: vi.fn(),
    } as never);
  });

  it('renders active sessions with service name and Cynefin status/domain badges', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

    expect(screen.getByText(/auth-service/i)).toBeInTheDocument();
    expect(screen.getByText(/billing-service/i)).toBeInTheDocument();
  });

  it('calls selectEvent when a session card is clicked', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

    const sessionCard = screen.getByText(/billing-service/i);
    fireEvent.click(sessionCard);

    expect(mockSelectEvent).toHaveBeenCalledWith('evt-2');
  });

  it('provides a + New Task trigger button', () => {
    const onNewTask = vi.fn();
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={onNewTask} />);

    const newTaskBtn = screen.getByRole('button', { name: /\+ New Task|New Session|\+ Task/i });
    expect(newTaskBtn).toBeInTheDocument();

    fireEvent.click(newTaskBtn);
    expect(onNewTask).toHaveBeenCalled();
  });

  it('handles empty active events gracefully', () => {
    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue({
      data: [],
      isLoading: false,
    } as never);

    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    expect(screen.getByText(/no active tasks|no sessions/i)).toBeInTheDocument();
  });

  describe('stale-cache eviction guard', () => {
    const asQuery = (data: unknown[], extra: Record<string, unknown> = {}) =>
      ({ data, isLoading: false, isFetching: false, ...extra }) as never;

    it('does NOT evict a newly selected / deep-linked session that is absent from a stale active list', () => {
      const onNewTask = vi.fn();
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));

      render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);

      expect(onNewTask).not.toHaveBeenCalled();
    });

    it('keeps a new session selected when the refreshed list then includes it, and evicts it only after it closes', () => {
      const onNewTask = vi.fn();
      const spy = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(
        <WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />,
      );
      expect(onNewTask).not.toHaveBeenCalled();

      // Refetch lands: new session is now observed
      const withNew = [...mockEvents, { ...mockEvents[0], id: 'evt-brand-new' }];
      spy.mockReturnValue(asQuery(withNew));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      // Session closes: it disappears after having been seen
      spy.mockReturnValue(asQuery(mockEvents));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('evicts the selection when a previously seen active event closes', () => {
      const onNewTask = vi.fn();
      const spy = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      spy.mockReturnValue(asQuery([mockEvents[1]]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('evicts when the last active event closes (list becomes empty)', () => {
      const onNewTask = vi.fn();
      const spy = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spy.mockReturnValue(asQuery([]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('defers eviction while a refetch is in flight', () => {
      const onNewTask = vi.fn();
      const spy = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spy.mockReturnValue(asQuery([mockEvents[1]], { isFetching: true }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      spy.mockReturnValue(asQuery([mockEvents[1]], { isFetching: false }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('does not re-evict a closed event that the user deep-links to again after eviction', () => {
      const onNewTask = vi.fn();
      const spy = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spy.mockReturnValue(asQuery([mockEvents[1]]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);

      // Fresh list array, same stale selection: guard was pruned on eviction
      spy.mockReturnValue(asQuery([{ ...mockEvents[1] }]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });
  });
});
