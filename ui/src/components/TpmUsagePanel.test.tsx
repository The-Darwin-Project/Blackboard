// BlackBoard/ui/src/components/TpmUsagePanel.test.tsx
// @ai-rules:
// 1. [Pattern]: Verifies TPM usage panel metrics, threshold line wiring, and legacy FlowSnapshot fallback.
// 2. [Pattern]: Stubs Recharts ResponsiveContainer and ReferenceLine for JSDOM stability.
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';
import TpmUsagePanel from './TpmUsagePanel';
import FlowHistoryPage from './FlowHistoryPage';
import type { FlowSnapshot } from '../api/types';

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => <div style={{ width: 600, height: 120 }}>{children}</div>,
    LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    ReferenceLine: ({ y }: { y?: number }) => <div data-testid="tpm-limit-ref-line" data-y={y} />,
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

describe('TpmUsagePanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders latest TPM usage, limit, ReferenceLine, utilization color, and throttle counts', () => {
    const snapshots = [
      makeSnapshot({ timestamp: 1_700_000_000, tpm_used: 900_000, tpm_limit: 3_000_000, tpm_utilization_pct: 30.0, quota_throttle_delta: 1 }),
      makeSnapshot({ timestamp: 1_700_000_060, tpm_used: 1_500_000, tpm_limit: 3_000_000, tpm_utilization_pct: 50.0, quota_throttle_delta: 2 }),
    ];
    render(<TpmUsagePanel snapshots={snapshots} />);

    expect(screen.getByText('Gemini TPM Usage')).toBeInTheDocument();
    expect(screen.getByText('1.5M')).toBeInTheDocument();
    expect(screen.getByText('/ 3.0M limit')).toBeInTheDocument();
    expect(screen.getByTestId('tpm-limit-ref-line').getAttribute('data-y')).toBe('3000000');
    expect(screen.getByText('50.0%').style.color).toBe('rgb(34, 197, 94)');
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Latest: 2')).toBeInTheDocument();
  });

  it('renders amber >=80% utilization and falls back to earlier non-zero tpm_limit on cold-start tail', () => {
    const snapshots = [
      makeSnapshot({ timestamp: 1_700_000_000, tpm_used: 2_400_000, tpm_limit: 3_000_000, tpm_utilization_pct: 80.0 }),
      makeSnapshot({ timestamp: 1_700_000_060, tpm_used: 2_550_000, tpm_limit: 0, tpm_utilization_pct: 85.0 }),
    ];
    render(<TpmUsagePanel snapshots={snapshots} />);

    expect(screen.getByText('/ 3.0M limit')).toBeInTheDocument();
    expect(screen.getByTestId('tpm-limit-ref-line').getAttribute('data-y')).toBe('3000000');
    expect(screen.getByText('85.0%').style.color).toBe('rgb(245, 158, 11)');
  });

  it('tolerates legacy Redis snapshots without TPM fields', () => {
    render(<TpmUsagePanel snapshots={[makeSnapshot()]} />);
    expect(screen.getByText('Gemini TPM Usage')).toBeInTheDocument();
    expect(screen.getByText('0.0%')).toBeInTheDocument();
    expect(screen.queryByText(/limit$/)).toBeNull();
    expect(screen.queryByTestId('tpm-limit-ref-line')).toBeNull();
  });

  it('mounts inside a scrollable FlowHistoryPage (WIP tab)', () => {
    vi.mocked(useFlowHistory).mockReturnValue({
      data: [makeSnapshot({ tpm_used: 600_000, tpm_limit: 3_000_000, tpm_utilization_pct: 20.0, quota_throttle_delta: 0 })],
      isLoading: false, error: null,
    } as unknown as ReturnType<typeof useFlowHistory>);
    const { container } = render(<FlowHistoryPage />);

    const panel = screen.getByTestId('tpm-usage-panel');
    const queueCard = screen.getByText('Queue Depth');
    expect(container.firstElementChild?.className).toContain('h-full');
    expect(container.firstElementChild?.className).toContain('overflow-y-auto');
    expect(screen.getByText('Flow Health')).toBeInTheDocument();
    expect(panel).toBeInTheDocument();
    expect(panel.compareDocumentPosition(queueCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('600.0K')).toBeInTheDocument();
  });
});
