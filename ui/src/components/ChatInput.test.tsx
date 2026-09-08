// BlackBoard/ui/src/components/ChatInput.test.tsx
// @ai-rules:
// 1. [Constraint]: Covers the evt-dc56392b regression (code-review HIGH finding: "missing UI
//    regression test") -- ChatInput must thread eventId to useChat's REST fallback whenever
//    wsSend is unavailable (WS disconnected), and must use the WS path directly when eventId
//    and wsSend are both present. A future refactor dropping eventId in either branch should
//    fail this test.
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ChatInput from './ChatInput';

const mockSendMessage = vi.fn();

vi.mock('../hooks', () => ({
  useChat: () => ({ sendMessage: mockSendMessage, isPending: false }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function typeAndSubmit(text: string) {
  const textarea = screen.getByPlaceholderText(/reply to event|ask the brain/i);
  fireEvent.change(textarea, { target: { value: text } });
  fireEvent.submit(textarea.closest('form')!);
}

describe('ChatInput REST-fallback branch (wsSend unavailable)', () => {
  it('threads eventId through to useChat.sendMessage when WS is disconnected', () => {
    render(<ChatInput eventId="evt-active01" wsSend={undefined} />);
    typeAndSubmit('reply here');

    expect(mockSendMessage).toHaveBeenCalledTimes(1);
    expect(mockSendMessage).toHaveBeenCalledWith('reply here', undefined, undefined, 'evt-active01');
  });

  it('passes undefined eventId when no event is selected', () => {
    render(<ChatInput eventId={undefined} wsSend={undefined} />);
    typeAndSubmit('ask the brain');

    expect(mockSendMessage).toHaveBeenCalledTimes(1);
    expect(mockSendMessage).toHaveBeenCalledWith('ask the brain', undefined, undefined, undefined);
  });
});

describe('ChatInput WS branch (wsSend connected + eventId set)', () => {
  it('sends directly over wsSend instead of the REST fallback', () => {
    const wsSend = vi.fn();
    render(<ChatInput eventId="evt-active02" wsSend={wsSend} />);
    typeAndSubmit('reply over ws');

    expect(wsSend).toHaveBeenCalledTimes(1);
    expect(wsSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'user_message', event_id: 'evt-active02', message: 'reply over ws' })
    );
    expect(mockSendMessage).not.toHaveBeenCalled();
  });
});
