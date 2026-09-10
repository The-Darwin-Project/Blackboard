// BlackBoard/ui/src/__tests__/WaitingBell.test.tsx
// Regression coverage for the code_reviewer MEDIUM finding on evt-321b0b68's
// verification pass: WaitingBell must not drop an event from the bell once
// its courtesy idle-timeout warning turn (is_courtesy_warning=true) becomes
// the last conversation turn -- that turn never sets waitingFor itself.
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import type { EventDocument } from '../api/types';

// Referentially stable across renders -- a fresh array literal per call would
// change the useEffect's [activeEvents] dependency every render and loop forever.
const ACTIVE_EVENTS = [{ id: 'evt-1', service: 'svc-a' }];
vi.mock('../hooks/useQueue', () => ({
  useActiveEvents: () => ({ data: ACTIVE_EVENTS }),
}));

vi.mock('../api/client', () => ({
  getEventDocument: vi.fn(),
}));

import WaitingBell from '../components/WaitingBell';
import { getEventDocument } from '../api/client';

const mockGetEventDocument = vi.mocked(getEventDocument);

function makeDoc(overrides: Partial<EventDocument> = {}): EventDocument {
  return {
    id: 'evt-1',
    source: 'chat',
    status: 'waiting_approval',
    service: 'svc-a',
    event: {
      reason: 'test',
      evidence: { display_text: 'test', source_type: 'chat', domain: 'complicated', severity: 'info' },
      timeDate: new Date().toISOString(),
    },
    conversation: [],
    ...overrides,
  } as unknown as EventDocument;
}

describe('WaitingBell', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('still shows an event whose last turn is a courtesy idle-timeout warning', async () => {
    const parkTs = Math.floor(Date.now() / 1000) - 600;
    mockGetEventDocument.mockResolvedValue(makeDoc({
      conversation: [
        {
          turn: 1,
          actor: 'brain',
          action: 'request_approval',
          thoughts: 'Please approve the plan',
          pendingApproval: true,
          waitingFor: 'user',
          timestamp: parkTs,
        },
        {
          turn: 2,
          actor: 'brain',
          action: 'response',
          thoughts: "If nothing else is needed, I'll close this in 5 minutes.",
          is_courtesy_warning: true,
          timestamp: parkTs + 500,
        },
      ],
    }));

    render(<WaitingBell onEventClick={() => {}} />);

    await waitFor(() => {
      expect(screen.queryByLabelText(/1 event.*waiting for approval/i)).not.toBeNull();
    });
  });

  it('does not show an event once a real (non-courtesy) turn clears waitingFor', async () => {
    mockGetEventDocument.mockResolvedValue(makeDoc({
      conversation: [
        {
          turn: 1,
          actor: 'brain',
          action: 'request_approval',
          waitingFor: 'user',
          timestamp: Math.floor(Date.now() / 1000) - 600,
        },
        {
          turn: 2,
          actor: 'user',
          action: 'message',
          thoughts: 'approved',
          timestamp: Math.floor(Date.now() / 1000) - 10,
        },
      ],
    }));

    render(<WaitingBell onEventClick={() => {}} />);

    await waitFor(() => {
      expect(screen.queryByLabelText('No events waiting')).not.toBeNull();
    });
  });
});
