// BlackBoard/ui/src/components/ChatInput.test.tsx
// @ai-rules:
// 1. [Constraint]: Covers the evt-dc56392b regression (code-review HIGH finding: "missing UI
//    regression test") -- ChatInput must thread eventId to useChat's REST fallback whenever
//    wsSend is unavailable (WS disconnected), and must use the WS path directly when eventId
//    and wsSend are both present. A future refactor dropping eventId in either branch should
//    fail this test.
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ChatInput from './ChatInput';

const mockSendMessage = vi.fn();

vi.mock('../hooks', () => ({
  useChat: () => ({ sendMessage: mockSendMessage, isPending: false }),
}));

// Capture the latest handler ChatInput registers via useWSMessage so tests can
// simulate an inbound WS error envelope without a real WebSocketProvider.
let latestWsHandler: ((msg: { type: string; event_id?: string; message?: unknown }) => void) | null = null;
vi.mock('../contexts/WebSocketContext', () => ({
  useWSMessage: (handler: (msg: { type: string; event_id?: string; message?: unknown }) => void) => {
    latestWsHandler = handler;
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  latestWsHandler = null;
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

describe('ChatInput Step 9 resilience (WS error envelope handling)', () => {
  function getTextarea() {
    return screen.getByPlaceholderText(/reply to event|ask the brain/i) as HTMLTextAreaElement;
  }

  it('renders no error banner before any WS error envelope arrives', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    expect(screen.queryByLabelText('Dismiss error')).toBeNull();
  });

  it('shows a dismissible banner with the server-provided message on a WS error envelope', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    expect(latestWsHandler).toBeTruthy();

    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1', message: 'Message rejected: rate limited' });
    });

    expect(screen.getByText('Message rejected: rate limited')).toBeTruthy();
    expect(screen.getByLabelText('Dismiss error')).toBeTruthy();
  });

  it('falls back to a generic message when the server error envelope omits one', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1' });
    });
    expect(screen.getByText('Message rejected by server')).toBeTruthy();
  });

  it('dismisses the banner when the dismiss button is clicked', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1', message: 'boom' });
    });
    expect(screen.getByText('boom')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('Dismiss error'));

    expect(screen.queryByText('boom')).toBeNull();
  });

  it('ignores non-error message types', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    act(() => {
      latestWsHandler!({ type: 'agent_update', event_id: 'evt-1', message: 'should not show' });
    });
    expect(screen.queryByText('should not show')).toBeNull();
    expect(screen.queryByLabelText('Dismiss error')).toBeNull();
  });

  it('ignores error envelopes addressed to a different event_id', () => {
    render(<ChatInput eventId="evt-1" wsSend={vi.fn()} />);
    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-other', message: 'not for you' });
    });
    expect(screen.queryByText('not for you')).toBeNull();
  });

  it('clears a previous error banner on the next submit attempt', () => {
    const wsSend = vi.fn();
    render(<ChatInput eventId="evt-1" wsSend={wsSend} />);
    const textarea = getTextarea();

    fireEvent.change(textarea, { target: { value: 'first' } });
    fireEvent.submit(textarea.closest('form')!);
    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1', message: 'failed once' });
    });
    expect(screen.getByText('failed once')).toBeTruthy();

    fireEvent.change(textarea, { target: { value: 'second try' } });
    fireEvent.submit(textarea.closest('form')!);

    expect(screen.queryByText('failed once')).toBeNull();
  });

  it('restores the submitted text into the (now empty) input on a WS error (non-clobbering restore)', async () => {
    const wsSend = vi.fn();
    render(<ChatInput eventId="evt-1" wsSend={wsSend} />);
    const textarea = getTextarea();

    fireEvent.change(textarea, { target: { value: 'hello world' } });
    fireEvent.submit(textarea.closest('form')!);

    // Submission clears the input synchronously (optimistic clear).
    await waitFor(() => expect(textarea.value).toBe(''));
    expect(wsSend).toHaveBeenCalledWith(expect.objectContaining({ message: 'hello world' }));

    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1', message: 'send failed' });
    });

    expect(textarea.value).toBe('hello world');
  });

  it('does not clobber text the user already typed after the failed submission', () => {
    const wsSend = vi.fn();
    render(<ChatInput eventId="evt-1" wsSend={wsSend} />);
    const textarea = getTextarea();

    fireEvent.change(textarea, { target: { value: 'first message' } });
    fireEvent.submit(textarea.closest('form')!);

    // User starts typing something new before the error envelope arrives.
    fireEvent.change(textarea, { target: { value: 'new unrelated draft' } });

    act(() => {
      latestWsHandler!({ type: 'error', event_id: 'evt-1', message: 'send failed' });
    });

    expect(textarea.value).toBe('new unrelated draft');
  });

  it('does not restore a stale submission after switching events before the error arrives', () => {
    const wsSend = vi.fn();
    const { rerender } = render(<ChatInput eventId="evt-1" wsSend={wsSend} />);
    const textarea = getTextarea();

    fireEvent.change(textarea, { target: { value: 'reply on evt-1' } });
    fireEvent.submit(textarea.closest('form')!);

    // User switches to a different event before the (event_id-less) error envelope arrives.
    rerender(<ChatInput eventId="evt-2" wsSend={wsSend} />);

    act(() => {
      latestWsHandler!({ type: 'error', message: 'stale error' });
    });

    expect(textarea.value).toBe('');
  });
});
