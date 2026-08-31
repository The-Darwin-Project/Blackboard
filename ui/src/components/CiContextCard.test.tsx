// BlackBoard/ui/src/components/CiContextCard.test.tsx
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import CiContextCard from './CiContextCard';
import type { CiContext } from '../api/types';
import { stripJenkinsNoise } from '../utils/stripAnsi';

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
      fireEvent.click(screen.getByText('Jenkins \u2192'));
      expect(mockSafeOpen).toHaveBeenCalledWith('https://jenkins.example.com/job/build/5');
    });

    it('constructs a fallback link from jenkins_url + job_name + build_number', () => {
      const context: CiContext = {
        jenkins_url: 'https://jenkins.example.com/',
        failed_jobs: [{ job_name: 'build', build_number: 42 }],
      };
      render(<CiContextCard context={context} />);
      fireEvent.click(screen.getByText('Jenkins \u2192'));
      expect(mockSafeOpen).toHaveBeenCalledWith('https://jenkins.example.com/job/build/42');
    });

    it('renders no link when neither jenkins_link nor jenkins_url is available', () => {
      const context: CiContext = {
        failed_jobs: [{ job_name: 'build' }],
      };
      render(<CiContextCard context={context} />);
      expect(screen.queryByText('Jenkins \u2192')).toBeNull();
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

    it('strips ha:////  blobs and [Pipeline] boundary noise before rendering', () => {
      const context: CiContext = {
        failed_jobs: [{
          job_name: 'build',
          console_tail: 'ha:////ABC123==\n[Pipeline] // container\nFinished: UNSTABLE',
        }],
      };
      const { container } = render(<CiContextCard context={context} />);
      expect(container.querySelector('pre')?.textContent).toBe('Finished: UNSTABLE');
    });
  });

  describe('stripJenkinsNoise (F1/F3/F4/F8/F9/F10 hardening regressions)', () => {
    it('strips a ha:////  blob, preserving surrounding text', () => {
      expect(stripJenkinsNoise('before ha:////ABC123== after')).toBe('before  after');
    });

    it('removes [Pipeline] boundary marker lines, preserving real output', () => {
      const text = '[Pipeline] }\n[Pipeline] // container\nreal output';
      expect(stripJenkinsNoise(text)).toBe('real output');
    });

    it('preserves a mid-line [Pipeline] substring not at line start (F1)', () => {
      const text = 'Running [Pipeline] } leftover';
      expect(stripJenkinsNoise(text)).toBe(text);
    });

    it('preserves a mid-line boundary-alternation word ("stage") appearing in real prose', () => {
      const text = 'Deploying [Pipeline] stage now, please wait';
      expect(stripJenkinsNoise(text)).toBe(text);
    });

    it('fully strips two adjacent ha:////  blobs with no separator (F3)', () => {
      const result = stripJenkinsNoise('ha:////AAA==ha:////BBB==');
      expect(result).toBe('');
      expect(result).not.toContain(':////');
    });

    it('preserves an abutting secret key:value intact for downstream redaction (F4)', () => {
      const result = stripJenkinsNoise('ha:////ABC==password:hunter2');
      expect(result).toContain('password:hunter2');
    });

    it('preserves an unpadded blob abutting an alphanumeric secret verbatim, mid-string (F9)', () => {
      // MEDIUM secret-redaction-bypass finding: an unpadded, non-ANSI-wrapped
      // blob directly abutted by a real all-alphanumeric secret (e.g. the
      // literal word "Bearer") must be left fully untouched -- mandatory
      // padding or a trailing ANSI escape is now required to terminate a
      // match; bare whitespace is no longer accepted as a delimiter.
      const text = 'ha:////AAAABearer sometoken123';
      expect(stripJenkinsNoise(text)).toBe(text);
    });

    it('preserves an unpadded blob abutting an alphanumeric secret verbatim, end-of-string (F9)', () => {
      // Same finding, end-of-string variant: bare end-of-string is also no
      // longer accepted as a delimiter.
      const text = 'filler text ha:////AAAABearersecrettoken123';
      expect(stripJenkinsNoise(text)).toBe(text);
    });

    it('preserves a single-`=` "token=" delimiter abutment verbatim (F10)', () => {
      // F10 regression: F9's fix accepted a single `=` as sufficient
      // padding proof unconditionally, but a lone `=` is exactly the
      // common KEY=value secret delimiter and is genuinely ambiguous with
      // real single-char base64 padding. Must now also require a safe
      // lookahead terminator (whitespace/ANSI/another blob/EOS) before a
      // single `=` counts -- absent here, so the whole match fails.
      const text = 'ha:////AAAtoken=abc123xyz';
      expect(stripJenkinsNoise(text)).toBe(text);
    });

    it.each(['secret', 'password', 'passwd', 'pwd', 'key', 'credential', 'authorization'])(
      'preserves a single-`=` "%s=" delimiter abutment verbatim (F10 board sweep)',
      (keyword) => {
        const text = `ha:////AAA${keyword}=xyz`;
        expect(stripJenkinsNoise(text)).toBe(text);
      },
    );

    it('still strips when a single `=` is followed by a safe lookahead terminator (F10 positive control)', () => {
      expect(stripJenkinsNoise('before ha:////ABC1= after')).toBe('before  after');
    });

    it('double-`==` padding remains self-sufficient, no regression (F10)', () => {
      expect(stripJenkinsNoise('before ha:////ABC123== after')).toBe('before  after');
      expect(stripJenkinsNoise('ha:////AAA==ha:////BBB==')).toBe('');
    });

    it('still strips a Timestamper-prefixed [Pipeline] boundary line (F8 parity)', () => {
      const text = '[2026-08-31T11:23:24.854Z] [Pipeline] // container\nreal output';
      expect(stripJenkinsNoise(text)).toBe('real output');
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
