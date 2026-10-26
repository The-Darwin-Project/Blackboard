import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceInspector from '../WorkspaceInspector';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import * as queueHook from '../../../hooks/useQueue';

// Mock child tabs
vi.mock('../../PlanProgress', () => ({
  default: ({ conversation }: { conversation: unknown[] }) => (
    <div data-testid="plan-progress">Plan with {conversation?.length || 0} turns</div>
  ),
}));

vi.mock('../WorkspaceDiffViewer', () => ({
  default: ({ diffs }: { diffs: string[] }) => (
    <div data-testid="workspace-diff-viewer">Diffs: {diffs?.length || 0}</div>
  ),
}));

vi.mock('../WorkspaceSwarmPanel', () => ({
  default: () => <div data-testid="workspace-swarm-panel">Swarm Panel</div>,
}));

vi.mock('../../ActivityStream', () => ({
  default: () => <div data-testid="activity-stream">Activity Logs</div>,
}));

describe('WorkspaceInspector (T-8 & Tabs)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    vi.spyOn(queueHook, 'useEventDocument').mockReturnValue({
      data: {
        id: 'evt-123',
        conversation: [
          {
            turn: 1,
            actor: 'developer',
            action: 'tool_result',
            timestamp: 1700000000,
            result: '```diff\ndiff --git a/file b/file\n@@ -1 +1 @@\n-a\n+b\n```',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as never);

    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      registeredAgents: [],
      ephemeralAgents: [],
      selectedEventId: 'evt-123',
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
  });

  const renderComponent = (props: {
    isOpen?: boolean;
    onClose?: () => void;
    selectedEventId?: string | null;
  } = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <WorkspaceInspector
          isOpen={props.isOpen ?? true}
          onClose={props.onClose || vi.fn()}
          selectedEventId={props.selectedEventId ?? 'evt-123'}
        />
      </QueryClientProvider>
    );
  };

  it('renders tab buttons (Plan, Diffs, Swarm, Logs) and allows switching between them', () => {
    renderComponent({ isOpen: true });

    // Verify tabs are available
    const planTab = screen.getByRole('button', { name: /plan/i });
    const diffsTab = screen.getByRole('button', { name: /diff/i });
    const swarmTab = screen.getByRole('button', { name: /swarm/i });
    const logsTab = screen.getByRole('button', { name: /log|stream/i });

    expect(planTab).toBeInTheDocument();
    expect(diffsTab).toBeInTheDocument();
    expect(swarmTab).toBeInTheDocument();
    expect(logsTab).toBeInTheDocument();

    // Default tab or clicking Plan
    fireEvent.click(planTab);
    expect(screen.getByTestId('plan-progress')).toBeInTheDocument();

    // Switch to Diffs
    fireEvent.click(diffsTab);
    expect(screen.getByTestId('workspace-diff-viewer')).toBeInTheDocument();

    // Switch to Swarm
    fireEvent.click(swarmTab);
    expect(screen.getByTestId('workspace-swarm-panel')).toBeInTheDocument();

    // Switch to Logs
    fireEvent.click(logsTab);
    expect(screen.getByTestId('activity-stream')).toBeInTheDocument();
  });

  it('renders nothing or collapsed state when isOpen is false', () => {
    const { container } = renderComponent({ isOpen: false });
    // When closed, either container is empty or hidden
    expect(container.querySelector('[data-testid="workspace-diff-viewer"]')).toBeNull();
  });
});
