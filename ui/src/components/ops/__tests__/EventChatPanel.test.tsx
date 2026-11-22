// BlackBoard/ui/src/components/ops/__tests__/EventChatPanel.test.tsx
// @ai-rules:
// 1. [Pattern]: Guards the resize-handle gutter: panel root must carry pr-1.5 and the handle w-1.5 (token-exact classList, never substring toContain).
// 2. [Constraint]: ConversationFeed and heavy children are stubbed; only the loaded-panel root and its resize handle are under test.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import EventChatPanel from '../EventChatPanel';
import { useOpsControl } from '../../../contexts/OpsStateContext';
import { useEventDocument, useActiveEvents, useQueueInvalidation } from '../../../hooks/useQueue';
import { usePlanState } from '../../../hooks/usePlanState';

vi.mock('../../../contexts/OpsStateContext', () => ({ useOpsControl: vi.fn() }));
vi.mock('../../../hooks/useQueue', () => ({
  useEventDocument: vi.fn(),
  useActiveEvents: vi.fn(),
  useQueueInvalidation: vi.fn(),
}));
vi.mock('../../../hooks/usePlanState', () => ({ usePlanState: vi.fn() }));
vi.mock('../../ConversationFeed', () => ({ ConversationFeed: () => <div data-testid="feed" /> }));
vi.mock('../../PlanProgress', () => ({ PlanProgress: () => null }));
vi.mock('../../ChatInput', () => ({ default: () => null }));
vi.mock('../../DeferCountdownBar', () => ({ default: () => null }));
vi.mock('../../CiContextCard', () => ({ default: () => null }));

const EVENT_ID = 'evt-chat-1';

describe('EventChatPanel resize handle gutter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(useOpsControl).mockReturnValue({ connected: true, send: vi.fn(), openContentTile: vi.fn() } as never);
    vi.mocked(useActiveEvents).mockReturnValue({ data: [{ id: EVENT_ID, status: 'active', source: 'chat', service: 'svc', created: new Date().toISOString() }] } as never);
    vi.mocked(useQueueInvalidation).mockReturnValue({ invalidateActive: vi.fn() } as never);
    vi.mocked(usePlanState).mockReturnValue({ hasPlan: false, steps: [] } as never);
    vi.mocked(useEventDocument).mockReturnValue({
      data: {
        id: EVENT_ID,
        status: 'active',
        source: 'chat',
        service: 'svc',
        event: { reason: 'test', evidence: 'x', timeDate: '2026-01-01T00:00:00Z' },
        conversation: [],
      },
      isLoading: false,
      isError: false,
    } as never);
  });

  it('reserves a pr-1.5 gutter on the panel root so the w-1.5 resize handle never overlaps the inner scrollbar', () => {
    const { container } = render(<EventChatPanel eventId={EVENT_ID} onClose={vi.fn()} />);

    const root = container.firstElementChild as HTMLElement;
    const handle = root.querySelector('.cursor-col-resize') as HTMLElement | null;

    expect(root.classList.contains('pr-1.5')).toBe(true);
    expect(handle).not.toBeNull();
    expect(handle!.classList.contains('w-1.5')).toBe(true);
    expect(handle!.classList.contains('right-0')).toBe(true);
  });
});
