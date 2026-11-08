// BlackBoard/ui/src/components/AgentStreamCard.test.tsx
// @ai-rules:
// 1. [Pattern]: Tests the 'Copy stream' button (clipboard payload/guards), pop-out FloatingWindow wiring, and auto-scroll at buffer cap.
// 2. [Constraint]: Clipboard assertions use exact payloads: newlines preserved, ANSI sequences removed completely.
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AgentStreamCard from './AgentStreamCard';

const ESC = '\u001b';

describe('AgentStreamCard', () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollHeight;
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollTop;
  });

  const renderCard = (messages: string[]) =>
    render(<AgentStreamCard agentName="developer" eventId="evt-123456789012" messages={messages} isActive />);

  describe('Copy stream', () => {
    it('copies multi-line stream logs preserving newlines/tabs and stripping ANSI/control characters', () => {
      renderCard([`${ESC}[31merror${ESC}[0m: boom`, 'at\tfoo.ts:1\r\nat bar.ts:2', `${ESC}]0;t\u0007ok\u0000`]);
      fireEvent.click(screen.getByRole('button', { name: 'Copy stream' }));
      expect(writeText).toHaveBeenCalledTimes(1);
      expect(writeText).toHaveBeenCalledWith('error: boom\nat\tfoo.ts:1\nat bar.ts:2\nok');
    });

    it('does not call the clipboard when there are no messages', () => {
      renderCard([]);
      fireEvent.click(screen.getByRole('button', { name: 'Copy stream' }));
      expect(writeText).not.toHaveBeenCalled();
    });

    it('does not throw when navigator.clipboard is undefined', () => {
      vi.stubGlobal('navigator', {});
      renderCard(['line']);
      expect(() => fireEvent.click(screen.getByRole('button', { name: 'Copy stream' }))).not.toThrow();
    });

    it('does not produce an unhandled rejection when writeText rejects', async () => {
      const unhandled = vi.fn();
      process.on('unhandledRejection', unhandled);
      try {
        writeText.mockRejectedValue(new Error('denied'));
        renderCard(['line']);
        expect(() => fireEvent.click(screen.getByRole('button', { name: 'Copy stream' }))).not.toThrow();
        await new Promise((r) => setTimeout(r, 10));
        expect(writeText).toHaveBeenCalledWith('line');
        expect(unhandled).not.toHaveBeenCalled();
      } finally {
        process.off('unhandledRejection', unhandled);
      }
    });
  });

  it('pops out a FloatingWindow with the same messages and closes it', () => {
    renderCard(['alpha', 'beta']);
    expect(screen.queryByTestId('floating-window')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pop out' }));
    const win = screen.getByTestId('floating-window');
    expect(win).toBeInTheDocument();
    expect(win.textContent).toContain('alpha');
    expect(win.textContent).toContain('beta');

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByTestId('floating-window')).not.toBeInTheDocument();
  });

  it('keeps auto-scrolling when the capped buffer rolls over with an unchanged length', () => {
    const scrollTopSetter = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', { configurable: true, get: () => 999 });
    Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
      configurable: true,
      get: () => 0,
      set: (v: number) => scrollTopSetter(v),
    });

    const full = Array.from({ length: 100 }, (_, i) => `line ${i}`);
    const { rerender } = renderCard(full);
    scrollTopSetter.mockClear();

    const rolled = [...full.slice(1), 'line 100'];
    rerender(<AgentStreamCard agentName="developer" eventId="evt-123456789012" messages={rolled} isActive />);
    expect(scrollTopSetter).toHaveBeenCalledWith(999);
  });
});
