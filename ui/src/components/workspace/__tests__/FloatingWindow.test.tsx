// BlackBoard/ui/src/components/workspace/__tests__/FloatingWindow.test.tsx
// @ai-rules:
// 1. [Pattern]: Tests FloatingWindow drag, resize, unmount listener cleanup, viewport clamping, auto-scroll, and Copy logs.
// 2. [Constraint]: Asserts window stays fully bounded within viewport (pos + size <= innerWidth/innerHeight).
// 3. [Constraint]: Copy logs assertions use exact clipboard payloads (newlines preserved, ANSI sequences fully removed).
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { FloatingWindow } from '../FloatingWindow';

describe('FloatingWindow Component', () => {
  beforeEach(() => {
    vi.stubGlobal('innerWidth', 1024);
    vi.stubGlobal('innerHeight', 768);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders agent name, event ID and messages safely', () => {
    const onClose = vi.fn();
    render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['compiling src/main.ts', 'tests passing']}
        onClose={onClose}
      />
    );

    expect(screen.getByText('developer')).toBeInTheDocument();
    expect(screen.getByText('evt-123')).toBeInTheDocument();
    expect(screen.getByText('compiling src/main.ts')).toBeInTheDocument();
    expect(screen.getByText('tests passing')).toBeInTheDocument();
  });

  it('renders "Idle" safely when messages is empty or undefined', () => {
    const { rerender } = render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={[]}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('Idle')).toBeInTheDocument();

    rerender(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={undefined}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['hello']}
        onClose={onClose}
      />
    );

    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('clamps coordinates to viewport boundaries during drag (preventing off-screen drag)', () => {
    const { container } = render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['log']}
        onClose={vi.fn()}
      />
    );

    const windowEl = container.firstElementChild as HTMLElement;
    const headerEl = screen.getByText('developer').parentElement?.parentElement as HTMLElement;

    // Start dragging header
    fireEvent.mouseDown(headerEl, { clientX: 200, clientY: 100 });

    // Drag far beyond top-left negative bounds
    fireEvent.mouseMove(window, { clientX: -500, clientY: -500 });
    fireEvent.mouseUp(window);

    expect(windowEl.style.left).toBe('0px');
    expect(windowEl.style.top).toBe('0px');

    // Drag far beyond bottom-right viewport (1024x768 - min constraints 320x220)
    fireEvent.mouseDown(headerEl, { clientX: 10, clientY: 10 });
    fireEvent.mouseMove(window, { clientX: 3000, clientY: 3000 });
    fireEvent.mouseUp(window);

    const left = parseInt(windowEl.style.left, 10);
    const top = parseInt(windowEl.style.top, 10);
    const width = parseInt(windowEl.style.width, 10);
    const height = parseInt(windowEl.style.height, 10);

    // Entire window (including header & close button) must remain on-screen
    expect(left + width).toBeLessThanOrEqual(1024);
    expect(top + height).toBeLessThanOrEqual(768);
    expect(left).toBe(1024 - 700);
    expect(top).toBe(768 - 500);
  });

  it('preserves minimum resize constraints (320x220) and clamps to viewport bounds', () => {
    const { container } = render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['log']}
        onClose={vi.fn()}
      />
    );

    const windowEl = container.firstElementChild as HTMLElement;
    const resizeHandle = container.querySelector('[style*="cursor: nwse-resize"]') as HTMLElement;
    expect(resizeHandle).toBeInTheDocument();

    // Resize smaller than 320x220
    fireEvent.mouseDown(resizeHandle, { clientX: 820, clientY: 580 });
    fireEvent.mouseMove(window, { clientX: 100, clientY: 100 });
    fireEvent.mouseUp(window);

    expect(parseInt(windowEl.style.width, 10)).toBeGreaterThanOrEqual(320);
    expect(parseInt(windowEl.style.height, 10)).toBeGreaterThanOrEqual(220);
  });

  it('cleans up window event listeners on unmount during active drag and resize', () => {
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    const { unmount } = render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['log']}
        onClose={vi.fn()}
      />
    );

    const headerEl = screen.getByText('developer').parentElement?.parentElement as HTMLElement;
    fireEvent.mouseDown(headerEl, { clientX: 200, clientY: 100 });

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('mousemove', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('mouseup', expect.any(Function));
  });

  it('re-clamps window position and dimensions on window resize event', () => {
    const { container } = render(
      <FloatingWindow
        agentName="developer"
        eventId="evt-123"
        messages={['log']}
        onClose={vi.fn()}
      />
    );

    const windowEl = container.firstElementChild as HTMLElement;

    // Simulate shrinking browser viewport
    vi.stubGlobal('innerWidth', 400);
    vi.stubGlobal('innerHeight', 300);

    fireEvent(window, new Event('resize'));

    const left = parseInt(windowEl.style.left, 10);
    const top = parseInt(windowEl.style.top, 10);
    const width = parseInt(windowEl.style.width, 10);
    const height = parseInt(windowEl.style.height, 10);

    expect(left + width).toBeLessThanOrEqual(400);
    expect(top + height).toBeLessThanOrEqual(300);
  });
  it('clamps resize to the remaining viewport (max-clamp from the window position)', () => {
    const { container } = render(
      <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
    );
    const windowEl = container.firstElementChild as HTMLElement;
    const resizeHandle = container.querySelector('[style*="cursor: nwse-resize"]') as HTMLElement;

    // Window starts at (120, 80); dragging the handle far past the viewport must stop at the viewport edge
    fireEvent.mouseDown(resizeHandle, { clientX: 820, clientY: 580 });
    fireEvent.mouseMove(window, { clientX: 5000, clientY: 5000 });
    fireEvent.mouseUp(window);

    expect(windowEl.style.left).toBe('120px');
    expect(windowEl.style.top).toBe('80px');
    expect(windowEl.style.width).toBe(`${1024 - 120}px`);
    expect(windowEl.style.height).toBe(`${768 - 80}px`);
  });

  it('uses the latest size when dragging after a resize (stable handlers read live refs)', () => {
    const { container } = render(
      <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
    );
    const windowEl = container.firstElementChild as HTMLElement;
    const resizeHandle = container.querySelector('[style*="cursor: nwse-resize"]') as HTMLElement;
    const headerEl = screen.getByText('developer').parentElement?.parentElement as HTMLElement;

    // Shrink to 400x300 (start 700x500 -> move handle by -300,-200)
    fireEvent.mouseDown(resizeHandle, { clientX: 820, clientY: 580 });
    fireEvent.mouseMove(window, { clientX: 520, clientY: 380 });
    fireEvent.mouseUp(window);
    expect(windowEl.style.width).toBe('400px');
    expect(windowEl.style.height).toBe('300px');

    // Drag far bottom-right: the clamp must use the new 400x300 size, not the stale 700x500
    fireEvent.mouseDown(headerEl, { clientX: 10, clientY: 10 });
    fireEvent.mouseMove(window, { clientX: 5000, clientY: 5000 });
    fireEvent.mouseUp(window);
    expect(windowEl.style.left).toBe(`${1024 - 400}px`);
    expect(windowEl.style.top).toBe(`${768 - 300}px`);

    // And a following resize uses the new position as the max-clamp origin
    fireEvent.mouseDown(resizeHandle, { clientX: 1000, clientY: 700 });
    fireEvent.mouseMove(window, { clientX: 5000, clientY: 5000 });
    fireEvent.mouseUp(window);
    expect(windowEl.style.width).toBe('400px');
    expect(windowEl.style.height).toBe('300px');
  });

  describe('initial geometry', () => {
    const geometry = (el: HTMLElement) => ({
      left: parseInt(el.style.left, 10),
      top: parseInt(el.style.top, 10),
      width: parseInt(el.style.width, 10),
      height: parseInt(el.style.height, 10),
    });

    it('opens at the default 700x500 at (120, 80) on a large viewport', () => {
      const { container } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
      );
      expect(geometry(container.firstElementChild as HTMLElement)).toEqual({ left: 120, top: 80, width: 700, height: 500 });
    });

    it('clamps initial size and position to a smaller viewport so the whole window is visible', () => {
      vi.stubGlobal('innerWidth', 500);
      vi.stubGlobal('innerHeight', 400);
      const { container } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
      );
      const g = geometry(container.firstElementChild as HTMLElement);
      expect(g.width).toBe(500);
      expect(g.height).toBe(400);
      expect(g.left).toBe(0);
      expect(g.top).toBe(0);
    });

    it('keeps the default position when it already fits (partial clamp)', () => {
      vi.stubGlobal('innerWidth', 900);
      vi.stubGlobal('innerHeight', 700);
      const { container } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
      );
      const g = geometry(container.firstElementChild as HTMLElement);
      expect(g).toEqual({ left: 120, top: 80, width: 700, height: 500 });
      expect(g.left + g.width).toBeLessThanOrEqual(900);
      expect(g.top + g.height).toBeLessThanOrEqual(700);
    });

    it('never goes below the 320x220 minimum on a tiny viewport', () => {
      vi.stubGlobal('innerWidth', 200);
      vi.stubGlobal('innerHeight', 150);
      const { container } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={['log']} onClose={vi.fn()} />
      );
      expect(geometry(container.firstElementChild as HTMLElement)).toEqual({ left: 0, top: 0, width: 320, height: 220 });
    });
  });

  describe('auto-scroll', () => {
    let scrollTopSetter: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      scrollTopSetter = vi.fn();
      Object.defineProperty(HTMLElement.prototype, 'scrollHeight', { configurable: true, get: () => 4321 });
      Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
        configurable: true,
        get: () => 0,
        set: (v: number) => scrollTopSetter(v),
      });
    });

    afterEach(() => {
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollHeight;
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollTop;
    });

    it('scrolls to the bottom on mount and when new messages arrive', () => {
      const { rerender } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={['a']} onClose={vi.fn()} />
      );
      expect(scrollTopSetter).toHaveBeenLastCalledWith(4321);
      scrollTopSetter.mockClear();

      rerender(<FloatingWindow agentName="developer" eventId="evt-123" messages={['a', 'b']} onClose={vi.fn()} />);
      expect(scrollTopSetter).toHaveBeenCalledWith(4321);
    });

    it('keeps scrolling when the capped buffer rolls over with an unchanged length', () => {
      const full = Array.from({ length: 100 }, (_, i) => `line ${i}`);
      const { rerender } = render(
        <FloatingWindow agentName="developer" eventId="evt-123" messages={full} onClose={vi.fn()} />
      );
      scrollTopSetter.mockClear();

      // Same length (100), new array identity: the oldest line is dropped and a new one appended
      const rolled = [...full.slice(1), 'line 100'];
      expect(rolled).toHaveLength(full.length);
      rerender(<FloatingWindow agentName="developer" eventId="evt-123" messages={rolled} onClose={vi.fn()} />);
      expect(scrollTopSetter).toHaveBeenCalledWith(4321);
    });
  });

  describe('Copy logs', () => {
    const ESC = '\u001b';
    let writeText: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      writeText = vi.fn().mockResolvedValue(undefined);
      vi.stubGlobal('navigator', { clipboard: { writeText } });
    });

    const renderWith = (messages?: string[]) =>
      render(<FloatingWindow agentName="developer" eventId="evt-123" messages={messages} onClose={vi.fn()} />);

    it('copies multi-line logs preserving newlines/tabs and fully stripping ANSI and control characters', () => {
      renderWith([`${ESC}[31mcompiling${ESC}[0m`, 'step\tone\r\nstep two', `${ESC}]0;title\u0007done\u0000`]);
      fireEvent.click(screen.getByRole('button', { name: 'Copy logs' }));
      expect(writeText).toHaveBeenCalledTimes(1);
      expect(writeText).toHaveBeenCalledWith('compiling\nstep\tone\nstep two\ndone');
    });

    it('does not call the clipboard when there are no messages', () => {
      renderWith([]);
      fireEvent.click(screen.getByRole('button', { name: 'Copy logs' }));
      expect(writeText).not.toHaveBeenCalled();
    });

    it('does not call the clipboard when messages is undefined', () => {
      renderWith(undefined);
      fireEvent.click(screen.getByRole('button', { name: 'Copy logs' }));
      expect(writeText).not.toHaveBeenCalled();
    });

    it('does not throw when navigator.clipboard is undefined', () => {
      vi.stubGlobal('navigator', {});
      renderWith(['line']);
      expect(() => fireEvent.click(screen.getByRole('button', { name: 'Copy logs' }))).not.toThrow();
    });

    it('does not produce an unhandled rejection when writeText rejects', async () => {
      const unhandled = vi.fn();
      process.on('unhandledRejection', unhandled);
      try {
        writeText.mockRejectedValue(new Error('denied'));
        renderWith(['line']);
        expect(() => fireEvent.click(screen.getByRole('button', { name: 'Copy logs' }))).not.toThrow();
        await new Promise((r) => setTimeout(r, 10));
        expect(writeText).toHaveBeenCalledWith('line');
        expect(unhandled).not.toHaveBeenCalled();
      } finally {
        process.off('unhandledRejection', unhandled);
      }
    });
  });
});
