// BlackBoard/ui/src/components/ConversationFeed.test.tsx
// @ai-rules:
// 1. [Pattern]: Guards that the feed edge-fade is applied via the .fade-edges-y class (not an inline full-width mask) only when turns > 3.
// 2. [Constraint]: TurnBubble/MarkdownViewer are stubbed; the scroll container is located via its inline position/overflow styles.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { ConversationFeed } from './ConversationFeed';
import { useEventDocument, useQueueInvalidation } from '../hooks/useQueue';

vi.mock('../hooks/useQueue', () => ({
  useEventDocument: vi.fn(),
  useQueueInvalidation: vi.fn(),
}));
vi.mock('../contexts/WebSocketContext', () => ({ useWSMessage: vi.fn() }));
vi.mock('../api/client', () => ({
  closeEvent: vi.fn(),
  enforceCasualDomain: vi.fn(),
  getEventReport: vi.fn(),
}));
vi.mock('./TurnBubble', () => ({
  default: () => <div data-testid="turn" />,
  StatusBadge: () => null,
}));
vi.mock('./MarkdownViewer', () => ({ default: () => null }));

const turns = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ turn: i + 1, actor: 'brain', action: 'think', thoughts: `t${i}`, timestamp: 1 + i }));

const renderFeed = (n: number) => {
  vi.mocked(useEventDocument).mockReturnValue({
    data: {
      id: 'evt-feed-1',
      source: 'chat',
      status: 'active',
      service: 'svc',
      event: { reason: 'r', evidence: 'e', timeDate: '2026-01-01T00:00:00Z' },
      conversation: turns(n),
    },
    isError: false,
  } as never);
  const { container } = render(<ConversationFeed eventId="evt-feed-1" onClose={vi.fn()} />);
  const feed = Array.from(container.querySelectorAll<HTMLElement>('div')).find(
    (el) => el.style.overflow === 'auto' && el.style.position === 'absolute',
  );
  if (!feed) throw new Error('feed scroll container not found');
  return feed;
};

describe('ConversationFeed edge fade', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useQueueInvalidation).mockReturnValue({
      invalidateActive: vi.fn(),
      invalidateEvent: vi.fn(),
      optimisticUpdateTurnStatus: vi.fn(),
    } as never);
  });

  it('applies fade-edges-y when there are more than 3 turns, without an inline mask', () => {
    const feed = renderFeed(4);
    expect(feed.classList.contains('fade-edges-y')).toBe(true);
    expect(feed.style.maskImage).toBeFalsy();
    expect(feed.style.overflow).toBe('auto');
  });

  it('does not apply fade-edges-y with 3 or fewer turns', () => {
    const feed = renderFeed(3);
    expect(feed.classList.contains('fade-edges-y')).toBe(false);
  });
});
