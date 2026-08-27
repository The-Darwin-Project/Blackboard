// BlackBoard/ui/src/components/ShiftsPage.test.tsx
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { ShiftCard, ShiftDetailPanel } from './ShiftsPage';
import type { ShiftReportSummary, ShiftReportFull } from '../api/types';

afterEach(cleanup);

const baseSummary: ShiftReportSummary = {
  shift_date: '2026-04-29',
  window: 'morning',
  status: 'completed',
  escalation_count: 3,
  incident_count: 1,
  noise_reduction_pct: 66,
  failed_cluster_count: 0,
};

const baseReport: ShiftReportFull = {
  shift_date: '2026-04-29',
  window: 'morning',
  window_start: '2026-04-29T06:00:00Z',
  window_end: '2026-04-29T14:00:00Z',
  status: 'completed',
  manifest: [],
  incidents: [],
  investigations: [],
  summary_text: '',
  metrics: { escalation_count: 3, incident_count: 1, noise_reduction_pct: 66 },
  started_at: null,
  completed_at: null,
};

describe('ShiftCard failed cluster badge', () => {
  it('does not render the badge when failed_cluster_count is 0', () => {
    render(<ShiftCard dateStr="2026-04-29" window="morning" shift={baseSummary}
      onClick={() => {}} isSelected={false} />);
    expect(screen.queryByText(/failed/)).toBeNull();
  });

  it('renders the badge when failed_cluster_count is greater than 0', () => {
    render(<ShiftCard dateStr="2026-04-29" window="morning"
      shift={{ ...baseSummary, failed_cluster_count: 2 }}
      onClick={() => {}} isSelected={false} />);
    expect(screen.getByText('2 failed')).toBeTruthy();
  });
});

describe('ShiftDetailPanel failed cluster badge', () => {
  it('does not render the badge when metrics.failed_cluster_count is absent', () => {
    render(<ShiftDetailPanel report={baseReport} onClose={() => {}} />);
    expect(screen.queryByText(/clusters failed/)).toBeNull();
  });

  it('renders the badge when metrics.failed_cluster_count is greater than 0', () => {
    const report = { ...baseReport, metrics: { ...baseReport.metrics, failed_cluster_count: 4 } };
    render(<ShiftDetailPanel report={report} onClose={() => {}} />);
    expect(screen.getByText('4 clusters failed (Jira error)')).toBeTruthy();
  });
});
