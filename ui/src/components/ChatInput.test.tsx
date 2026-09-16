// BlackBoard/ui/src/components/ChatInput.test.tsx
// @ai-rules:
// 1. [Constraint]: Covers the evt-dc56392b regression (code-review HIGH finding: "missing UI
//    regression test") -- ChatInput must thread eventId to useChat's REST fallback whenever
//    wsSend is unavailable (WS disconnected), and must use the WS path directly when eventId
//    and wsSend are both present. A future refactor dropping eventId in either branch should
//    fail this test.
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
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

describe('ChatInput draft restore', () => {
  it('restores draft when switching eventId away and back', async () => {
    const { rerender } = render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    const textarea = screen.getByPlaceholderText(/reply to event|ask the brain/i);
    
    // Type draft for evt-1
    fireEvent.change(textarea, { target: { value: 'draft for evt-1' } });
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('draft for evt-1'));
    
    // Switch to evt-2
    rerender(<ChatInput eventId="evt-2" wsSend={vi.fn()} />);
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe(''));
    
    // Type draft for evt-2
    fireEvent.change(textarea, { target: { value: 'draft for evt-2' } });
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('draft for evt-2'));
    
    // Switch back to evt-1
    rerender(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('draft for evt-1'));
  });

  it('does not clobber new text typed immediately after switch with stale draft', async () => {
    const { rerender } = render(<ChatInput eventId="evt-3" wsSend={vi.fn()} />);
    const textarea = screen.getByPlaceholderText(/reply to event|ask the brain/i);
    
    // Type draft for evt-3
    fireEvent.change(textarea, { target: { value: 'draft for evt-3' } });
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('draft for evt-3'));
    
    // Switch to evt-4
    rerender(<ChatInput eventId="evt-4" wsSend={vi.fn()} />);
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe(''));
    
    // Type new text immediately before any async restore could fire
    fireEvent.change(textarea, { target: { value: 'new text for evt-4' } });
    
    // Simulate the restore firing late (e.g. by re-rendering with same eventId)
    // The functional updater should protect 'new text for evt-4'
    rerender(<ChatInput eventId="evt-4" wsSend={vi.fn()} />);
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('new text for evt-4'));
  });

  it('switching to eventId with no saved draft yields empty input', async () => {
    const { rerender } = render(<ChatInput eventId="evt-5" wsSend={vi.fn()} />);
    const textarea = screen.getByPlaceholderText(/reply to event|ask the brain/i);
    
    // Type draft for evt-5
    fireEvent.change(textarea, { target: { value: 'draft for evt-5' } });
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('draft for evt-5'));
    
    // Switch to evt-6 (no draft)
    rerender(<ChatInput eventId="evt-6" wsSend={vi.fn()} />);
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe(''));
  });
});
