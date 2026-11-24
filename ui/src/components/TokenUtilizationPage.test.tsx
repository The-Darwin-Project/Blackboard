import { render, screen } from '@testing-library/react';
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';
import TokenUtilizationPage from './TokenUtilizationPage';
import type { FlowSnapshot } from '../api/types';

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => <div style={{ width: 600, height: 120 }}>{children}</div>,
    LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  };
});

vi.mock('../hooks/useFlowHistory', () => ({ useFlowHistory: vi.fn() }));
import { useFlowHistory } from '../hooks/useFlowHistory';

function makeSnapshot(overrides: Partial<FlowSnapshot> = {}): FlowSnapshot {
  return {
    timestamp: 1_700_000_000, queue_depth: 1, active_events: 4, deferred_events: 1,
    waiting_approval_events: 0, headhunter_pending: 0, aligner_pending: 0, jenkins_pending: 0,
    jenkins_breaker_open: false, jenkins_view_unhealthy: false, wip_used: 5, wip_cap: 20,
    wip_utilization_pct: 25, wip_available: 15, busy_agents: 2, idle_agents: 1,
    active_subscriptions: 3, avg_event_age_sec: 12, avg_reconcile_ms: 8.5,
    reconcile_count_delta: 5, error_count_delta: 0, token_input_delta: 1000,
    token_output_delta: 200, token_thinking_delta: 500, token_cached_delta: 300,
    token_tool_use_delta: 0, token_total_delta: 2000, token_calls_delta: 2,
    token_total_cumulative: 100_000, ...overrides,
  };
}

describe('TokenUtilizationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders correctly with populated FlowSnapshot entries (calculates aggregate and Brain hit percentages)', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [
        makeSnapshot({
          token_input_delta: 1000,
          token_cached_delta: 600,
          brain_token_input_delta: 1000,
          brain_token_cached_delta: 900,
        }),
      ],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<TokenUtilizationPage />);
    
    expect(screen.getByText('60.0% hit (Brain: 90.0%)')).toBeInTheDocument();
  });

  it('handles pre-rollout/partial entries gracefully (undefined brain tokens)', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [
        makeSnapshot({
          token_input_delta: 1000,
          token_cached_delta: undefined,
          brain_token_input_delta: undefined,
          brain_token_cached_delta: undefined,
        }),
      ],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<TokenUtilizationPage />);
    
    expect(screen.getByText('0.0% hit (Brain: 0.0%)')).toBeInTheDocument();
  });

  it('handles zero-input snapshots safely (avoids division by zero/NaN)', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [
        makeSnapshot({
          token_input_delta: 0,
          token_cached_delta: 0,
          brain_token_input_delta: 0,
          brain_token_cached_delta: 0,
        }),
      ],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<TokenUtilizationPage />);
    
    expect(screen.getByText('0.0% hit (Brain: 0.0%)')).toBeInTheDocument();
  });

  it('handles loading state', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as any);

    const { container } = render(<TokenUtilizationPage />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('handles error state', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [],
      isLoading: false,
      error: new Error('Failed to fetch'),
      refetch: vi.fn(),
    } as any);

    render(<TokenUtilizationPage />);
    expect(screen.getByText(/Token data unavailable/)).toBeInTheDocument();
  });

  it('handles empty snapshot state', () => {
    const mockUseFlowHistory = vi.mocked(useFlowHistory);
    mockUseFlowHistory.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<TokenUtilizationPage />);
    expect(screen.getByText('Collecting data... first snapshot in ~60s.')).toBeInTheDocument();
  });
});
