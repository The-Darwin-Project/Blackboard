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
});
