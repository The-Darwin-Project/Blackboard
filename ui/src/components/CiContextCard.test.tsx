// BlackBoard/ui/src/components/CiContextCard.test.tsx
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import CiContextCard from './CiContextCard';
import type { CiContext } from '../api/types';

vi.mock('../utils/safeOpen', () => ({
  safeOpen: vi.fn(),
}));

import { safeOpen } from '../utils/safeOpen';

const mockSafeOpen = vi.mocked(safeOpen);

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(cleanup);

describe('CiContextCard', () => {
  describe('failed jobs badge (3-way state)', () => {
    it('shows no pass/fail badge when failed_jobs is undefined', () => {
      render(<CiContextCard context={{}} />);
      expect(screen.queryByText('All passing')).toBeNull();
      expect(screen.queryByText(/failed/)).toBeNull();
    });

    it('shows "All passing" when failed_jobs is an empty array', () => {
      render(<CiContextCard context={{ failed_jobs: [] }} />);
      expect(screen.getByText('All passing')).toBeTruthy();
    });

    it('shows the failed count badge when failed_jobs has entries', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }, { job_name: 'test' }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.getByText('2 failed')).toBeTruthy();
      expect(screen.queryByText('All passing')).toBeNull();
    });
  });

  describe('Jenkins link fallback logic', () => {
    it('uses job.jenkins_link when provided', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build', jenkins_link: 'https://jenkins.example.com/job/build/5' }],
      };
      render(<CiContextCard context={context} />);
      fireEvent.click(screen.getByText('Jenkins →'));
      expect(mockSafeOpen).toHaveBeenCalledWith('https://jenkins.example.com/job/build/5');
    });

    it('constructs a fallback link from jenkins_url + job_name + build_number', () => {
      const context: CiContext = {
        jenkins_url: 'https://jenkins.example.com/',
        failed_jobs: [{ job_name: 'build', build_number: 42 }],
      };
      render(<CiContextCard context={context} />);
      fireEvent.click(screen.getByText('Jenkins →'));
      expect(mockSafeOpen).toHaveBeenCalledWith('https://jenkins.example.com/job/build/42');
    });

    it('renders no link when neither jenkins_link nor jenkins_url is available', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.queryByText('Jenkins →')).toBeNull();
    });
  });

  describe('missing jobs disclosure', () => {
    it('reveals missing job rows only after expanding', () => {
      const context: CiContext = {
        missing_jobs: [{ job_name: 'nightly', last_result: 'SUCCESS' }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.queryByText('nightly')).toBeNull();
      fireEvent.click(screen.getByText('Missing Jobs (1)'));
      expect(screen.getByText('nightly')).toBeTruthy();
    });
  });

  describe('LLM triage disclosure', () => {
    it('reveals triage rows only after expanding', () => {
      const context: CiContext = {
        llm_triage: [{ job_name: 'build', classification: 'flaky' }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.queryByText('flaky')).toBeNull();
      fireEvent.click(screen.getByText('LLM Triage (1)'));
      expect(screen.getByText('flaky')).toBeTruthy();
    });
  });

  describe('ConsoleTailBlock (stripAnsi + expand/collapse)', () => {
    it('strips ANSI escape codes from console_tail before rendering', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build', console_tail: '[31mERROR[0m: build failed' }],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.querySelector('pre')?.textContent).toBe('ERROR: build failed');
    });

    it('shows only the last 8 lines by default when console_tail has more than 8 lines', () => {
      const lines = Array.from({ length: 10 }, (_, i) => `line ${i + 1}`);
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build', console_tail: lines.join('\n') }],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.querySelector('pre')?.textContent).toBe(lines.slice(-8).join('\n'));
      expect(screen.getByText('Show all 10 lines')).toBeTruthy();
    });

    it('expands to show every line on click, then collapses back to the preview', () => {
      const lines = Array.from({ length: 10 }, (_, i) => `line ${i + 1}`);
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build', console_tail: lines.join('\n') }],
      };
      const { container } = render(<CiContextCard context={context} />);
      const pre = () => container.querySelector('pre');

      fireEvent.click(screen.getByText('Show all 10 lines'));
      expect(pre()?.textContent).toBe(lines.join('\n'));

      fireEvent.click(screen.getByText('Collapse'));
      expect(pre()?.textContent).toBe(lines.slice(-8).join('\n'));
    });

    it('renders no expand toggle when console_tail has 8 or fewer lines', () => {
      const lines = Array.from({ length: 5 }, (_, i) => `line ${i + 1}`);
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build', console_tail: lines.join('\n') }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.queryByText(/Show all/)).toBeNull();
      expect(screen.queryByText('Collapse')).toBeNull();
    });
  });

  describe('llm_triage to failed_jobs correlation (triageMap by job_name)', () => {
    it('attaches the recommendation to the failed job whose job_name matches an llm_triage entry', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }, { job_name: 'test' }],
        llm_triage: [
          { job_name: 'build', classification: 'flaky', confidence: 0.87, recommended_action: 'Retry the build' },
        ],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.textContent).toContain('Retry the build');
      expect(container.textContent).toContain('flaky');
      expect(container.textContent).toContain('87%');
    });

    it('does not attach a recommendation to a failed job with no matching triage entry', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }],
        llm_triage: [{ job_name: 'other-job', recommended_action: 'should not appear on build' }],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.textContent).not.toContain('should not appear on build');
    });

    it('ignores llm_triage entries with no job_name when building the correlation map', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }],
        llm_triage: [{ recommended_action: 'orphaned triage, no job_name to key on' }],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.textContent).not.toContain('orphaned triage');
    });

    it('correlates each failed job to its own triage entry independently', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }, { job_name: 'test' }],
        llm_triage: [
          { job_name: 'build', recommended_action: 'fix build' },
          { job_name: 'test', recommended_action: 'fix test' },
        ],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.textContent).toContain('fix build');
      expect(container.textContent).toContain('fix test');
    });
  });
});
