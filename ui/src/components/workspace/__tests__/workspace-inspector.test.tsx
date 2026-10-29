import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceInspector from '../WorkspaceInspector';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import * as queueHook from '../../../hooks/useQueue';
import { DOMAIN_COLORS } from '../../../constants/colors';

// jsdom normalises inline colours to rgb(); convert the hex constants the same way for comparison.
const rgb = (hex: string) => {
  const probe = document.createElement('span');
  probe.style.color = hex;
  return probe.style.color;
};

// Mock child tabs
vi.mock('../../PlanProgress', () => ({
  default: ({ conversation }: { conversation: unknown[] }) => (
    <div data-testid="plan-progress">Plan with {conversation?.length || 0} turns</div>
  ),
  usePlanState: (conversation: unknown[]) => {
    const hasPlan = Array.isArray(conversation) && (conversation as { action?: string }[]).some((t) => t.action === 'plan');
    return {
      hasPlan,
      planTurn: hasPlan ? conversation[0] : null,
      steps: hasPlan ? [{ id: '1', agent: 'developer', summary: 'Step 1', status: 'completed' }] : [],
    };
  },
}));

vi.mock('../WorkspaceDiffViewer', () => ({
  default: ({ diffs }: { diffs: string[] }) => (
    <div data-testid="workspace-diff-viewer">Diffs: {diffs?.length || 0}</div>
  ),
}));

vi.mock('../WorkspaceSwarmPanel', () => ({
  default: () => <div data-testid="workspace-swarm-panel">Swarm Panel</div>,
}));

vi.mock('../../CiContextCard', () => ({
  default: ({ context }: { context: { cnv_version?: string } }) => (
    <div data-testid="ci-context-card">CI {context.cnv_version}</div>
  ),
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
        service: 'order-service',
        status: 'active',
        source: 'gitlab',
        created_by_email: 'alice@example.com',
        token_usage: {
          total_tokens: 5000,
          input_tokens: 3000,
          output_tokens: 1500,
          thinking_tokens: 500,
          cached_tokens: 0,
          calls: 2,
        },
        conversation: [
          {
            turn: 1,
            actor: 'developer',
            action: 'plan',
            timestamp: 1700000000,
            taskForAgent: {
              steps: [
                { id: '1', agent: 'developer', summary: 'Check codebase' },
              ],
            },
          },
          {
            turn: 2,
            actor: 'developer',
            action: 'tool_result',
            timestamp: 1700000001,
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

  it('renders session overview details, token telemetry, and fallback message when no plan is present', () => {
    // Override eventDoc to have conversation turns but NO structured plan
    vi.spyOn(queueHook, 'useEventDocument').mockReturnValue({
      data: {
        id: 'evt-1528dc00',
        service: 'general',
        status: 'active',
        source: 'chat',
        created_by_email: 'dhansis@redhat.com',
        token_usage: {
          total_tokens: 12500,
          input_tokens: 8000,
          output_tokens: 3500,
          thinking_tokens: 1000,
          cached_tokens: 0,
          calls: 4,
        },
        conversation: [
          {
            turn: 1,
            actor: 'user',
            action: 'message',
            timestamp: 1700000000,
            message: 'Please review and edit guide',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as never);

    renderComponent({ isOpen: true, selectedEventId: 'evt-1528dc00' });

    // Verify session overview card rendered
    expect(screen.getByText('general')).toBeInTheDocument();
    expect(screen.getByText('dhansis@redhat.com')).toBeInTheDocument();
    expect(screen.getByText('12.5K')).toBeInTheDocument(); // token formatting
    expect(screen.getByText('4 calls')).toBeInTheDocument();

    // Verify Plan tab fallback renders friendly message instead of returning null
    expect(screen.getByText('No execution plan for this session')).toBeInTheDocument();
    expect(screen.getByText(/Structured execution plans appear here/i)).toBeInTheDocument();
  });
  describe('session overview', () => {
    const mockDoc = (over: Record<string, unknown>) =>
      vi.spyOn(queueHook, 'useEventDocument').mockReturnValue({
        data: {
          id: 'evt-ov',
          service: 'overview-svc',
          status: 'active',
          source: 'chat',
          conversation: [],
          ...over,
        },
        isLoading: false,
        isError: false,
      } as never);

    it.each([
      ['absent', {}],
      ['zero total', { token_usage: { total_tokens: 0, input_tokens: 0, output_tokens: 0, thinking_tokens: 0, cached_tokens: 0, calls: 0 } }],
    ])('hides the token telemetry when token_usage is %s', (_label, over) => {
      mockDoc(over);
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('overview-svc')).toBeInTheDocument();
      expect(screen.queryByText('Tokens')).not.toBeInTheDocument();
      expect(screen.queryByText(/calls/)).not.toBeInTheDocument();
    });

    it('shows the live marker only while the session is not closed', () => {
      mockDoc({ token_usage: { total_tokens: 100, input_tokens: 100, calls: 1 } });
      const { unmount } = renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('live')).toBeInTheDocument();
      unmount();

      mockDoc({ status: 'closed', token_usage: { total_tokens: 100, input_tokens: 100, calls: 1 } });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.queryByText('live')).not.toBeInTheDocument();
    });

    it('prefers evidence.triggered_by over created_by_email', () => {
      mockDoc({
        created_by_email: 'creator@example.com',
        event: { evidence: { triggered_by: 'trigger@example.com' } },
      });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('trigger@example.com')).toBeInTheDocument();
      expect(screen.queryByText('creator@example.com')).not.toBeInTheDocument();
    });

    it('falls back to created_by_email when triggered_by is absent or null', () => {
      mockDoc({ created_by_email: 'creator@example.com', event: { evidence: { triggered_by: null } } });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('creator@example.com')).toBeInTheDocument();
    });

    it('renders no triggering user when neither identity is present', () => {
      mockDoc({});
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.queryByText(/@/)).not.toBeInTheDocument();
    });

    it('renders the CI context card when evidence.ci_context is present and omits it otherwise', () => {
      mockDoc({ event: { evidence: { ci_context: { cnv_version: '4.22' } } } });
      const { unmount } = renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByTestId('ci-context-card').textContent).toBe('CI 4.22');
      unmount();

      mockDoc({ event: { evidence: {} } });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.queryByTestId('ci-context-card')).not.toBeInTheDocument();
    });

    it('collapses and expands the overview card', () => {
      mockDoc({ created_by_email: 'creator@example.com' });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('creator@example.com')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /overview-svc/ }));
      expect(screen.queryByText('creator@example.com')).not.toBeInTheDocument();
    });

    it.each(['constructor', '__proto__', 'weird'])('renders unknown/prototype domain %s with the casual fallback color', (domain) => {
      mockDoc({ event: { evidence: { brain_domain: domain } } });
      renderComponent({ selectedEventId: 'evt-ov' });
      const badge = screen.getByText(domain);
      expect(badge.style.color).toBe(rgb(DOMAIN_COLORS.casual.text));
    });

    it('lowercases the domain and applies its palette (case-insensitive)', () => {
      mockDoc({ event: { evidence: { brain_domain: 'CHAOTIC' } } });
      renderComponent({ selectedEventId: 'evt-ov' });
      const badge = screen.getByText('chaotic');
      expect(badge.style.color).toBe(rgb(DOMAIN_COLORS.chaotic.text));
      expect(badge.style.color).not.toBe(rgb(DOMAIN_COLORS.casual.text));
    });

    it('prefers brain_domain over evidence.domain', () => {
      mockDoc({ event: { evidence: { brain_domain: 'complex', domain: 'disorder' } } });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('complex').style.color).toBe(rgb(DOMAIN_COLORS.complex.text));
      expect(screen.queryByText('disorder')).not.toBeInTheDocument();
    });

    it.each(['disorder', 'complicated'] as const)(
      'falls back to evidence.domain (%s) when brain_domain is absent',
      (domain) => {
        for (const brain of [null, undefined, '']) {
          mockDoc({ event: { evidence: { brain_domain: brain, domain } } });
          const { unmount } = renderComponent({ selectedEventId: 'evt-ov' });
          const badge = screen.getByText(domain);
          expect(badge.style.color).toBe(rgb(DOMAIN_COLORS[domain].text));
          unmount();
        }
      },
    );

    it.each([
      ['both null', { brain_domain: null, domain: null }],
      ['both undefined', {}],
    ])("defaults to 'disorder' when brain_domain and evidence.domain are %s", (_label, evidence) => {
      mockDoc({ event: { evidence } });
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('disorder').style.color).toBe(rgb(DOMAIN_COLORS.disorder.text));
    });

    it("defaults to 'disorder' when the event has no evidence at all", () => {
      mockDoc({});
      renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('disorder').style.color).toBe(rgb(DOMAIN_COLORS.disorder.text));
    });

    it('includes tool_use_tokens in the token breakdown bar and legend', () => {
      mockDoc({
        token_usage: {
          total_tokens: 1000, input_tokens: 600, output_tokens: 0, thinking_tokens: 0,
          cached_tokens: 0, tool_use_tokens: 400, calls: 2,
        },
      });
      const { container } = renderComponent({ selectedEventId: 'evt-ov' });
      expect(screen.getByText('Tools')).toBeInTheDocument();
      expect(screen.getByText('400')).toBeInTheDocument();
      const segment = Array.from(container.querySelectorAll<HTMLElement>('div[style]'))
        .find(el => el.style.width === '40%');
      expect(segment).toBeDefined();
      expect(segment!.style.background).toBe(rgb('#38bdf8'));
    });
  });
});
