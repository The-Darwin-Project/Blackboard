import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkspaceSwarmPanel from '../WorkspaceSwarmPanel';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import type { AgentRegistryEntry } from '../../../api/types';

describe('WorkspaceSwarmPanel (T-8)', () => {
  const mockAgents: AgentRegistryEntry[] = [
    {
      agent_id: 'agent-1',
      role: 'architect',
      busy: true,
      current_event_id: 'evt-123',
      current_task_id: null,
      connected_at: 1700000000,
      cli: 'claude',
      model: 'claude-3-7-sonnet',
    },
    {
      agent_id: 'agent-2',
      role: 'developer',
      busy: false,
      current_event_id: null,
      current_task_id: null,
      connected_at: 1700000010,
      cli: 'claude',
      model: 'claude-3-7-sonnet',
    },
  ];

  it('lists active agents from useOpsControl without duplicate polling', () => {
    // Spy on fetch / window.fetch to confirm zero additional fetch calls
    const fetchSpy = vi.spyOn(window, 'fetch');

    // Mock useOpsControl to return mock registeredAgents / agents
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
    } as any);

    render(<WorkspaceSwarmPanel />);

    // Verify agent roles are rendered
    expect(screen.getByText(/architect/i)).toBeInTheDocument();
    expect(screen.getByText(/developer/i)).toBeInTheDocument();

    // Verify agent statuses
    expect(screen.getByText(/busy/i)).toBeInTheDocument();
    expect(screen.getByText(/idle/i)).toBeInTheDocument();

    // Verify current event link/text if busy
    expect(screen.getByText(/evt-123/i)).toBeInTheDocument();

    // DoD T-8: 0 new fetch() calls triggered
    expect(fetchSpy).not.toHaveBeenCalled();

    fetchSpy.mockRestore();
  });

  it('renders empty state message when no agents are registered', () => {
    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      registeredAgents: [],
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
    } as any);

    render(<WorkspaceSwarmPanel />);

    expect(screen.getByText(/no active agents|no agents connected/i)).toBeInTheDocument();
  });
});
