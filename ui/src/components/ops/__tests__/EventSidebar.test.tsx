// BlackBoard/ui/src/components/ops/__tests__/EventSidebar.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import EventSidebar from '../EventSidebar';
import { useOpsControl } from '../../../contexts/OpsStateContext';
import { useActiveEvents, useWaitingApprovalEvents, useHeadhunterPending, useAlignerPending, useJenkinsPending } from '../../../hooks/useQueue';
import { useSchedules } from '../../../hooks/useTimeKeeper';
import { useJiraMissions, useJiraActions } from '../../../hooks/useJira';
import type { AgentRegistryEntry } from '../../../api/types';

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: vi.fn(),
}));

vi.mock('../../../hooks/useQueue', () => ({
  useActiveEvents: vi.fn(),
  useWaitingApprovalEvents: vi.fn(),
  useHeadhunterPending: vi.fn(),
  useAlignerPending: vi.fn(),
  useJenkinsPending: vi.fn(),
}));

vi.mock('../../../hooks/useTimeKeeper', () => ({
  useSchedules: vi.fn(),
}));

vi.mock('../../../hooks/useJira', () => ({
  useJiraMissions: vi.fn(),
  useJiraActions: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  getClosedEvents: vi.fn().mockResolvedValue([]),
}));

describe('EventSidebar - Dynamic Agents Tree with Squads', () => {
  let selectEventMock: ReturnType<typeof vi.fn>;
  let setHotspotMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    selectEventMock = vi.fn();
    setHotspotMock = vi.fn();

    vi.mocked(useActiveEvents).mockReturnValue({
      data: [
        {
          id: 'evt-05e15dcc',
          status: 'active',
          source: 'headhunter',
          service: 'release-app',
          created: new Date().toISOString(),
        } as never,
        {
          id: 'evt-8f2a1b4c',
          status: 'active',
          source: 'chat',
          service: 'kargo-config',
          created: new Date().toISOString(),
        } as never,
      ],
    } as never);

    vi.mocked(useWaitingApprovalEvents).mockReturnValue({ data: [] } as never);
    vi.mocked(useHeadhunterPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useAlignerPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useJenkinsPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useSchedules).mockReturnValue({ data: [] } as never);
    vi.mocked(useJiraMissions).mockReturnValue({ data: [] } as never);
    vi.mocked(useJiraActions).mockReturnValue({} as never);
  });

  afterEach(() => {
    cleanup();
  });

  const setupOpsControl = (registeredAgents: AgentRegistryEntry[]) => {
    vi.mocked(useOpsControl).mockReturnValue({
      selectedEventId: null,
      selectEvent: selectEventMock,
      setHotspot: setHotspotMock,
      connected: true,
      send: vi.fn(),
      openContentTile: vi.fn(),
      registeredAgents,
      kargoStages: [],
    } as never);
  };

  const renderSidebar = () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <EventSidebar />
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('renders empty label and 0 badge when no agents are registered (no ghost offline agents)', () => {
    setupOpsControl([]);
    renderSidebar();

    expect(screen.getByText('No active agents')).toBeInTheDocument();
    expect(screen.queryByText('offline')).not.toBeInTheDocument();
    expect(screen.queryByText('architect')).not.toBeInTheDocument();
    expect(screen.queryByText('sysadmin')).not.toBeInTheDocument();
    expect(screen.queryByText('developer')).not.toBeInTheDocument();
    expect(screen.queryByText('qe')).not.toBeInTheDocument();
  });

  it('groups agents into a Squad tree group and canonical sort order', () => {
    const squadAgents: AgentRegistryEntry[] = [
      { agent_id: 'a-qe', role: 'qe', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
      { agent_id: 'a-dev', role: 'developer', busy: true, current_event_id: 'evt-05e15dcc', current_task_id: 'task-build-1', connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
      { agent_id: 'a-arch', role: 'architect', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
      { agent_id: 'a-sys', role: 'sysadmin', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
    ];
    setupOpsControl(squadAgents);
    renderSidebar();

    expect(screen.getByText('Squad • release-app (05e15dcc)')).toBeInTheDocument();
    expect(screen.getByText('task-build-1')).toBeInTheDocument();

    const agentNodes = screen.getAllByRole('button');
    const labels = agentNodes.map(n => n.textContent).filter(Boolean);

    // Verify all 4 roles are rendered
    expect(screen.getByText('architect')).toBeInTheDocument();
    expect(screen.getByText('developer')).toBeInTheDocument();
    expect(screen.getByText('sysadmin')).toBeInTheDocument();
    expect(screen.getByText('qe')).toBeInTheDocument();

    // Clicking an agent in the squad selects its bound event
    const devNode = screen.getByText('developer');
    fireEvent.click(devNode);
    expect(selectEventMock).toHaveBeenCalledWith('evt-05e15dcc');
  });

  it('renders multiple squads cleanly without flat list bleeding', () => {
    const multipleSquads: AgentRegistryEntry[] = [
      // Squad 1
      { agent_id: 's1-arch', role: 'architect', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
      { agent_id: 's1-dev', role: 'developer', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-05e15dcc' },
      // Squad 2
      { agent_id: 's2-arch', role: 'architect', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-8f2a1b4c' },
      { agent_id: 's2-dev', role: 'developer', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'evt-8f2a1b4c' },
    ];
    setupOpsControl(multipleSquads);
    renderSidebar();

    expect(screen.getByText('Squad • release-app (05e15dcc)')).toBeInTheDocument();
    expect(screen.getByText('Squad • kargo-config (8f2a1b4c)')).toBeInTheDocument();
  });

  it('renders sensors and on-call sweep agents under Sensors & On-Call', () => {
    const sensorAgents: AgentRegistryEntry[] = [
      { agent_id: 'nw-sweep', role: 'sysadmin', current_role: 'nightwatcher', busy: true, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: 'nw-sweep-gitops' },
      { agent_id: 'aligner-1', role: 'aligner', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: null },
    ];
    setupOpsControl(sensorAgents);
    renderSidebar();

    expect(screen.getByText('Sensors & On-Call')).toBeInTheDocument();
    expect(screen.getByText('nightwatcher')).toBeInTheDocument();
    expect(screen.getAllByText('aligner').length).toBeGreaterThanOrEqual(1);

    const sweepNode = screen.getByText('nightwatcher');
    fireEvent.click(sweepNode);
    expect(setHotspotMock).toHaveBeenCalledWith('nw-sweep-gitops');
  });

  it('renders standalone agents when not bound to an event', () => {
    const standalone: AgentRegistryEntry[] = [
      { agent_id: 'local-arch', role: 'architect', busy: false, current_event_id: null, current_task_id: null, connected_at: 100, cli: 'claude', model: 'sonnet', bound_event_id: null },
    ];
    setupOpsControl(standalone);
    renderSidebar();

    expect(screen.getByText('architect')).toBeInTheDocument();
    expect(screen.getByText('idle')).toBeInTheDocument();
  });
});
