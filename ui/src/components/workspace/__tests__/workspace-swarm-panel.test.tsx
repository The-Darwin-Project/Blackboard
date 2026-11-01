import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkspaceSwarmPanel from '../WorkspaceSwarmPanel';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import type { AgentRegistryEntry } from '../../../api/types';

describe('WorkspaceSwarmPanel (T-7, T-8, T-9)', () => {
  const mockAgents: AgentRegistryEntry[] = [
    {
      agent_id: 'agent-1',
      role: 'architect',
      busy: true,
      bound_event_id: 'evt-123',
      current_event_id: 'evt-123',
      current_task_id: null,
      connected_at: 1700000000,
      cli: 'claude',
      model: 'claude-opus-5-5',
    },
    {
      agent_id: 'agent-2',
      role: 'developer',
      busy: false,
      bound_event_id: 'evt-123',
      current_event_id: null,
      current_task_id: null,
      connected_at: 1700000010,
      cli: 'claude',
      model: 'claude-sonnet-5-5',
    },
    {
      agent_id: 'agent-3',
      role: 'sysadmin',
      current_role: 'code_reviewer',
      busy: true,
      bound_event_id: 'evt-123',
      current_event_id: 'evt-123',
      current_task_id: null,
      connected_at: 1700000020,
      cli: 'claude',
      model: 'claude-sonnet-5-5',
    },
    {
      agent_id: 'agent-4',
      role: 'qe',
      busy: true,
      bound_event_id: 'evt-456',
      current_event_id: 'evt-456',
      current_task_id: null,
      connected_at: 1700000030,
      cli: 'claude',
      model: 'claude-sonnet-5-5',
    },
  ];

  it('T-8 & T-9: lists only agents attached to selectedEventId, displaying dynamic roles', () => {
    const fetchSpy = vi.spyOn(window, 'fetch');

    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      registeredAgents: mockAgents,
      ephemeralAgents: [],
      selectedEventId: null,
      selectEvent: vi.fn(),
      deselectEvent: vi.fn(),
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

    render(<WorkspaceSwarmPanel selectedEventId="evt-123" />);

    // Attached agents for evt-123 should be present
    expect(screen.getByText(/architect/i)).toBeInTheDocument();
    expect(screen.getByText(/developer/i)).toBeInTheDocument();
    // Specialized reviewer with current_role
    expect(screen.getByText(/code_reviewer/i)).toBeInTheDocument();

    // Agent attached to evt-456 should NOT be rendered
    expect(screen.queryByText(/qe/i)).not.toBeInTheDocument();

    // Zero additional REST fetch polling
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('T-7: renders empty state when selectedEventId is null (New Task) even when cluster agents exist', () => {
    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      registeredAgents: mockAgents,
      ephemeralAgents: [],
      selectedEventId: null,
      selectEvent: vi.fn(),
      deselectEvent: vi.fn(),
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

    render(<WorkspaceSwarmPanel selectedEventId={null} />);

    expect(screen.getByText(/no agents active for this task/i)).toBeInTheDocument();
    expect(screen.queryByText(/architect/i)).not.toBeInTheDocument();
  });

  it('renders empty state message when no agents match task', () => {
    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      registeredAgents: [],
      ephemeralAgents: [],
      selectedEventId: 'evt-999',
      selectEvent: vi.fn(),
      deselectEvent: vi.fn(),
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

    render(<WorkspaceSwarmPanel selectedEventId="evt-999" />);

    expect(screen.getByText(/no agents active for this task/i)).toBeInTheDocument();
  });
});
