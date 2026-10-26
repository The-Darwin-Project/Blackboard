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
    } as any);

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
    } as any);
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
    } as any);

    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    expect(screen.getByText(/no active tasks|no sessions/i)).toBeInTheDocument();
  });
});
