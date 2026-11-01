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
    expect(button.getAttribute('title')).toBe('Copied!');
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

  it('4. stops click and keydown (Enter, Space) event propagation (stopPropagation)', () => {
    const parentClick = vi.fn();
    const parentKeyDown = vi.fn();

    render(
      <div onClick={parentClick} onKeyDown={parentKeyDown}>
        <CopyButton text="evt-12345" label="Copy Event ID" />
      </div>
    );

    const button = screen.getByRole('button');

    // Click
    fireEvent.click(button);
    expect(parentClick).not.toHaveBeenCalled();

    // Enter
    fireEvent.keyDown(button, { key: 'Enter' });
    expect(parentKeyDown).not.toHaveBeenCalled();

    // Space
    fireEvent.keyDown(button, { key: ' ' });
    expect(parentKeyDown).not.toHaveBeenCalled();
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

    expect(writeTextMock).toHaveBeenCalledWith('evt-123[31mmalicious');
  });

  it('10. keyboard: calls preventDefault on Space and Enter keydown to prevent scrolling and double-activation', () => {
    render(<CopyButton text="evt-keys" label="Copy Event ID" />);
    const button = screen.getByRole('button');

    const spaceEvent = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true });
    button.dispatchEvent(spaceEvent);
    expect(spaceEvent.defaultPrevented).toBe(true);

    const enterEvent = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    button.dispatchEvent(enterEvent);
    expect(enterEvent.defaultPrevented).toBe(true);
  });

  it('11. dynamic feedback: dynamically derives copied label from custom label prop', async () => {
    render(<CopyButton text="my-service" label="Copy Service Name" />);
    const button = screen.getByRole('button');

    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(button.getAttribute('aria-label')).toBe('Copied Service Name');
    expect(button.getAttribute('title')).toBe('Copied!');
  });
});
