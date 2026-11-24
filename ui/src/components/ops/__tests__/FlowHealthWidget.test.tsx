// BlackBoard/ui/src/components/ops/__tests__/FlowHealthWidget.test.tsx
// @ai-rules:
// 1. [Pattern]: 4-layer ATDD spec (T-15 / T-16) for FlowHealthWidget Headhunter circuit-breaker badges.
// 2. [Constraint]: Pure presentational test -- mocks useFlowMetrics() only.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import FlowHealthWidget from '../FlowHealthWidget';
import { useFlowMetrics } from '../../../hooks/useFlowMetrics';
import type { FlowMetrics } from '../../../api/types';

vi.mock('../../../hooks/useFlowMetrics', () => ({
  useFlowMetrics: vi.fn(),
}));

type FlowMetricsWithHeadhunter = FlowMetrics & {
  headhunter_gitlab_pending?: number;
  headhunter_github_pending?: number;
  headhunter_gitlab_breaker?: 'closed' | 'open' | 'half_open';
  headhunter_github_breaker?: 'closed' | 'open' | 'half_open';
};

function makeFlowMetrics(overrides: Partial<FlowMetricsWithHeadhunter> = {}): FlowMetricsWithHeadhunter {
  return {
    queue_depth: 0,
    active_events: 2,
    busy_agents: 1,
    idle_agents: 2,
    active_subscriptions: 0,
    avg_event_age_sec: 15,
    deferred_events: 0,
    waiting_approval_events: 0,
    headhunter_pending: 0,
    headhunter_gitlab_pending: 0,
    headhunter_github_pending: 0,
    headhunter_gitlab_breaker: 'closed',
    headhunter_github_breaker: 'closed',
    aligner_pending: 0,
    jenkins_pending: 0,
    jenkins_breaker_open: false,
    jenkins_view_unhealthy: false,
    wip_used: 1,
    wip_cap: 5,
    wip_utilization_pct: 20,
    wip_available: 4,
    avg_reconcile_ms: 12,
    token_total_60s: 0,
    token_calls_60s: 0,
    snapshot_timestamp: 1700000000,
    agents_by_role: {},
    staleness_guards: [],
    ...overrides,
  };
}

function badgeClassTree(el: HTMLElement): string {
  return `${el.className} ${el.parentElement?.className ?? ''} ${el.parentElement?.innerHTML ?? ''}`;
}

describe('FlowHealthWidget - Headhunter Circuit Breaker Badges (T-15 / T-16)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('Given GitLab breaker is open and GitHub breaker is half_open, When FlowHealthWidget renders, Then distinct GL CB (red) and GH CB (amber/yellow) badges render', () => {
    vi.mocked(useFlowMetrics).mockReturnValue({
      data: makeFlowMetrics({
        headhunter_gitlab_breaker: 'open',
        headhunter_github_breaker: 'half_open',
      }),
      isError: false,
      isLoading: false,
    } as never);

    render(<FlowHealthWidget />);

    const glBadge = screen.getByText('GL CB');
    const ghBadge = screen.getByText('GH CB');
    expect(glBadge).toBeInTheDocument();
    expect(ghBadge).toBeInTheDocument();
    expect(badgeClassTree(glBadge)).toMatch(/red/);
    expect(badgeClassTree(ghBadge)).toMatch(/amber|yellow/);
  });

  it('Given GitLab breaker is half_open and GitHub breaker is open, When FlowHealthWidget renders, Then GL CB uses amber/yellow and GH CB uses red styling', () => {
    vi.mocked(useFlowMetrics).mockReturnValue({
      data: makeFlowMetrics({
        headhunter_gitlab_breaker: 'half_open',
        headhunter_github_breaker: 'open',
      }),
      isError: false,
      isLoading: false,
    } as never);

    render(<FlowHealthWidget />);

    const glBadge = screen.getByText('GL CB');
    const ghBadge = screen.getByText('GH CB');
    expect(badgeClassTree(glBadge)).toMatch(/amber|yellow/);
    expect(badgeClassTree(ghBadge)).toMatch(/red/);
  });

  it('Given both GitLab and GitHub breakers are closed, When FlowHealthWidget renders, Then GL CB and GH CB breaker alert badges do not render', () => {
    vi.mocked(useFlowMetrics).mockReturnValue({
      data: makeFlowMetrics({
        headhunter_gitlab_breaker: 'closed',
        headhunter_github_breaker: 'closed',
      }),
      isError: false,
      isLoading: false,
    } as never);

    render(<FlowHealthWidget />);

    expect(screen.queryByText('GL CB')).toBeNull();
    expect(screen.queryByText('GH CB')).toBeNull();
  });
});
