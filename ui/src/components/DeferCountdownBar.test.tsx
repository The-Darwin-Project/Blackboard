// BlackBoard/ui/src/components/DeferCountdownBar.test.tsx
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import DeferCountdownBar from './DeferCountdownBar';

vi.mock('../hooks/useDeferCountdown', () => ({
  useDeferCountdown: vi.fn(),
}));

import { useDeferCountdown } from '../hooks/useDeferCountdown';

const mockHook = vi.mocked(useDeferCountdown);

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(cleanup);

describe('DeferCountdownBar', () => {
  describe('rendering', () => {
    it('renders nothing when timeline is null', () => {
      mockHook.mockReturnValue({
        timeline: null, ratio: 0, remainingLabel: '', expired: false,
        ariaValueNow: 0, ariaValueMax: 100,
      });

      const { container } = render(<DeferCountdownBar />);
      expect(container.firstChild).toBeNull();
    });

    it('renders progressbar when defer is active', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 9999999999, defer_started_at: 1000000000 },
        ratio: 0.6, remainingLabel: '18m', expired: false,
        ariaValueNow: 60, ariaValueMax: 100,
      });

      const { container } = render(
        <DeferCountdownBar deferUntil={9999999999} deferStartedAt={1000000000} />,
      );

      const bar = container.querySelector('[role="progressbar"]');
      expect(bar).not.toBeNull();
      expect(bar?.getAttribute('aria-valuenow')).toBe('60');
      expect(bar?.getAttribute('aria-valuemax')).toBe('100');
      expect(bar?.getAttribute('aria-valuemin')).toBe('0');
    });

    it('shows remaining time label', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 9999999999, defer_started_at: 1000000000 },
        ratio: 0.4, remainingLabel: '12m 30s', expired: false,
        ariaValueNow: 40, ariaValueMax: 100,
      });

      render(<DeferCountdownBar deferUntil={9999999999} />);
      expect(screen.getByText('12m 30s')).toBeTruthy();
      expect(screen.getByText('Deferred')).toBeTruthy();
    });
  });

  describe('expired state', () => {
    it('shows expired label when defer has ended', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 1000000000, defer_started_at: 999999000 },
        ratio: 0, remainingLabel: 'Waking up', expired: true,
        ariaValueNow: 0, ariaValueMax: 100,
      });

      render(<DeferCountdownBar deferUntil={1000000000} />);
      expect(screen.getByText('Defer ended')).toBeTruthy();
      expect(screen.getByText('Waking up')).toBeTruthy();
    });

    it('sets accessible label for expired state', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 1000000000, defer_started_at: 999999000 },
        ratio: 0, remainingLabel: 'Waking up', expired: true,
        ariaValueNow: 0, ariaValueMax: 100,
      });

      const { container } = render(<DeferCountdownBar deferUntil={1000000000} />);
      const bar = container.querySelector('[role="progressbar"]');
      expect(bar?.getAttribute('aria-label')).toBe(
        'Defer period ended, waiting for FRIDAY to resume',
      );
    });
  });

  describe('accessibility', () => {
    it('progressbar aria-label includes remaining time', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 9999999999, defer_started_at: 1000000000 },
        ratio: 0.75, remainingLabel: '22m 15s', expired: false,
        ariaValueNow: 75, ariaValueMax: 100,
      });

      const { container } = render(<DeferCountdownBar deferUntil={9999999999} />);
      const bar = container.querySelector('[role="progressbar"]');
      expect(bar?.getAttribute('aria-label')).toBe('Defer time remaining: 22m 15s');
    });

    it('clock icon is hidden from assistive technology', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 9999999999, defer_started_at: 1000000000 },
        ratio: 0.5, remainingLabel: '15m', expired: false,
        ariaValueNow: 50, ariaValueMax: 100,
      });

      const { container } = render(<DeferCountdownBar deferUntil={9999999999} />);
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('aria-hidden')).toBe('true');
    });
  });

  describe('compact mode', () => {
    it('uses h-1 track instead of h-1.5', () => {
      mockHook.mockReturnValue({
        timeline: { defer_until: 9999999999, defer_started_at: 1000000000 },
        ratio: 0.5, remainingLabel: '15m', expired: false,
        ariaValueNow: 50, ariaValueMax: 100,
      });

      const { container } = render(<DeferCountdownBar deferUntil={9999999999} compact />);
      const track = container.querySelector('[role="progressbar"]');
      expect(track?.className).toContain('h-1');
      expect(track?.className).not.toContain('h-1.5');
    });
  });

  describe('hook invocation', () => {
    it('passes props through to useDeferCountdown', () => {
      mockHook.mockReturnValue({
        timeline: null, ratio: 0, remainingLabel: '', expired: false,
        ariaValueNow: 0, ariaValueMax: 100,
      });

      render(
        <DeferCountdownBar deferUntil={123} deferStartedAt={100} conversation={[]} />,
      );

      expect(mockHook).toHaveBeenCalledWith(123, 100, [], true);
    });
  });
});
