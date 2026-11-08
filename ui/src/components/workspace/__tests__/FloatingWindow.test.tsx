// BlackBoard/ui/src/components/workspace/__tests__/FloatingWindow.test.tsx
// @ai-rules:
// 1. [Pattern]: Tests FloatingWindow drag, resize, unmount listener cleanup, and viewport clamping.
// 2. [Constraint]: Asserts window stays fully bounded within viewport (pos + size <= innerWidth/innerHeight).
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

    const { unmount, container } = render(
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
});
