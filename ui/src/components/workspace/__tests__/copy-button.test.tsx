// BlackBoard/ui/src/components/workspace/__tests__/copy-button.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import CopyButton from '../CopyButton';

describe('CopyButton', () => {
  let writeTextMock: ReturnType<typeof vi.fn>;
  let execCommandMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: writeTextMock,
      },
    });
    execCommandMock = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', {
      value: execCommandMock,
      writable: true,
      configurable: true,
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    delete (document as unknown as { execCommand?: unknown }).execCommand;
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('1. renders default Copy icon and accessible aria-label="Copy Event ID"', () => {
    render(<CopyButton text="evt-12345" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
    expect(button.getAttribute('title')).toBe('Copy Event ID');
    expect((button as HTMLButtonElement).disabled).toBe(false);

    // Default icon rendered
    const svg = button.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('2. copies provided text to clipboard on click and toggles to Check icon and aria-label="Copied Event ID"', async () => {
    render(<CopyButton text="evt-12345" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenCalledWith('evt-12345');
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');
    expect(button.getAttribute('title')).toBe('Copied Event ID');
  });

  it('3. reverts from Check back to Copy icon after 2,000ms timer expires', async () => {
    render(<CopyButton text="evt-12345" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');

    // Advance timers by 2000ms
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
    expect(button.getAttribute('title')).toBe('Copy Event ID');
  });

  it('4. stops click propagation; keydown is left to the native button (parent rows guard via e.target !== e.currentTarget)', () => {
    const parentClick = vi.fn();

    render(
      <div onClick={parentClick}>
        <CopyButton text="evt-12345" label="Copy Event ID" />
      </div>
    );

    fireEvent.click(screen.getByRole('button'));
    expect(parentClick).not.toHaveBeenCalled();
  });

  it('5. fallback execution: gracefully falls back to execCommand("copy") if navigator.clipboard.writeText rejects', async () => {
    writeTextMock.mockRejectedValue(new Error('Permission denied'));
    execCommandMock.mockReturnValue(true);

    render(<CopyButton text="evt-fallback" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(execCommandMock).toHaveBeenCalledWith('copy');
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');
  });

  it('6. failure safety: does not toggle to Check icon if both clipboard methods fail and cleans up textarea', async () => {
    writeTextMock.mockRejectedValue(new Error('Permission denied'));
    execCommandMock.mockImplementation(() => {
      throw new Error('execCommand failed');
    });

    render(<CopyButton text="evt-fail" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
    expect(button.getAttribute('title')).toBe('Copy Event ID');
    expect(document.querySelectorAll('textarea').length).toBe(0);
  });

  it('7. disabled state: renders disabled button when text is null or undefined', () => {
    const { rerender } = render(<CopyButton text={null} label="Copy Event ID" />);

    let button = screen.getByRole('button');
    expect((button as HTMLButtonElement).disabled).toBe(true);

    rerender(<CopyButton text={undefined} label="Copy Event ID" />);
    button = screen.getByRole('button');
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('8. clears pending timer on unmount without throwing', async () => {
    const { unmount } = render(<CopyButton text="evt-unmount" label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(() => unmount()).not.toThrow();
    // Advance timers after unmount should not throw or cause state update warnings
    expect(() => {
      act(() => {
        vi.advanceTimersByTime(2000);
      });
    }).not.toThrow();
  });

  it('9. sanitization: strips CRLF and terminal escape codes before copying', async () => {
    render(<CopyButton text={"evt-123\r\n\x1b[31mmalicious"} label="Copy Event ID" />);

    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenCalledWith('evt-123malicious');
  });

  it('9b. sanitization: strips C0/DEL/C1 controls, U+2028/U+2029 and bidi controls', async () => {
    const dirty = 'a\u0000b\u0007c\u007fd\u0085e\u009ff\u2028g\u2029h\u202ai\u202ej\u2066k\u2069l';
    render(<CopyButton text={dirty} label="Copy Event ID" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
      await Promise.resolve();
    });
    expect(writeTextMock).toHaveBeenCalledWith('abcdefghijkl');
  });

  it('10. keyboard: no custom keydown handler (no preventDefault / no double copy); native click does the copy', async () => {
    render(<CopyButton text="evt-keys" label="Copy Event ID" />);
    const button = screen.getByRole('button');

    const spaceEvent = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true });
    button.dispatchEvent(spaceEvent);
    expect(spaceEvent.defaultPrevented).toBe(false);

    const enterEvent = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    button.dispatchEvent(enterEvent);
    expect(enterEvent.defaultPrevented).toBe(false);
    expect(writeTextMock).not.toHaveBeenCalled();

    // Browser-synthesised click from Enter/Space copies exactly once
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    expect(writeTextMock).toHaveBeenCalledTimes(1);
  });

  it('11. dynamic feedback: dynamically derives copied label from custom label prop', async () => {
    render(<CopyButton text="my-service" label="Copy Service Name" />);
    const button = screen.getByRole('button');

    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(button.getAttribute('aria-label')).toBe('Copied Service Name');
    expect(button.getAttribute('title')).toBe('Copied Service Name');
  });

  it('12. unmount while the copied timer is pending leaves no timers behind', async () => {
    const { unmount } = render(<CopyButton text="evt-timer" label="Copy Event ID" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
      await Promise.resolve();
    });
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('12b. a copy that resolves after unmount does not start a feedback timer', async () => {
    let resolveWrite: () => void = () => {};
    writeTextMock.mockImplementation(() => new Promise<void>(r => { resolveWrite = r; }));
    const { unmount } = render(<CopyButton text="evt-late-unmount" label="Copy Event ID" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
      await Promise.resolve();
    });
    unmount();
    await act(async () => {
      resolveWrite();
      await Promise.resolve();
    });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('13a. rapid clicks reset the timer instead of stacking', async () => {
    render(<CopyButton text="evt-rapid" label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    act(() => { vi.advanceTimersByTime(1500); });
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    expect(vi.getTimerCount()).toBe(1);

    // 1500ms after the second click (3000ms total): still copied because the timer restarted
    act(() => { vi.advanceTimersByTime(1500); });
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');

    act(() => { vi.advanceTimersByTime(500); });
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
  });

  it('13b. timer boundary: still copied at 1999ms, reverted at 2000ms', async () => {
    render(<CopyButton text="evt-boundary" label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');
    act(() => { vi.advanceTimersByTime(1); });
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
  });

  it('14a. execCommand returning false does not set copied state and still removes the textarea', async () => {
    writeTextMock.mockRejectedValue(new Error('denied'));
    execCommandMock.mockReturnValue(false);
    render(<CopyButton text="evt-false" label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    expect(execCommandMock).toHaveBeenCalledWith('copy');
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
    expect(document.querySelectorAll('textarea').length).toBe(0);
    // (jsdom's textarea.select() queues its own 0ms select-event timer, so assert on observable state, not timer count)
    act(() => { vi.advanceTimersByTime(2000); });
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
  });

  it('14b. falls back to execCommand when navigator.clipboard is missing, and cleans up the textarea', async () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined });
    let selectedValue: string | undefined;
    execCommandMock.mockImplementation(() => {
      selectedValue = document.querySelector('textarea')?.value;
      return true;
    });
    render(<CopyButton text={'evt-nocb\n'} label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    expect(writeTextMock).not.toHaveBeenCalled();
    expect(selectedValue).toBe('evt-nocb');
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');
    expect(document.querySelectorAll('textarea').length).toBe(0);
  });

  it('14c. changing the text prop resets the copied state and cancels the pending timer', async () => {
    const { rerender } = render(<CopyButton text="evt-a" label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    expect(button.getAttribute('aria-label')).toBe('Copied Event ID');
    expect(vi.getTimerCount()).toBe(1);

    rerender(<CopyButton text="evt-b" label="Copy Event ID" />);
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
    expect(button.getAttribute('title')).toBe('Copy Event ID');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('14d. a copy that resolves after the text prop changed does not mark the new value as copied', async () => {
    let resolveWrite: () => void = () => {};
    writeTextMock.mockImplementation(() => new Promise<void>(r => { resolveWrite = r; }));
    const { rerender } = render(<CopyButton text="evt-old" label="Copy Event ID" />);
    const button = screen.getByRole('button');
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });
    rerender(<CopyButton text="evt-new" label="Copy Event ID" />);
    await act(async () => {
      resolveWrite();
      await Promise.resolve();
    });
    expect(button.getAttribute('aria-label')).toBe('Copy Event ID');
  });
});
