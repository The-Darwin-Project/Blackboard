// BlackBoard/ui/src/components/TurnBubble.test.tsx
/**
 * 4-Layer Farley ATDD Executable Acceptance Specification
 * Scenarios T-1 through T-7: TurnBubble Actor Bubble Cards and Left Alignment
 *
 * Layer 1: Domain Scenarios (Given/When/Then)
 * Layer 2: Domain DSL operations
 * Layer 3: Protocol Driver (React Testing Library)
 * Layer 4: System Under Test (TurnBubble component)
 */
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import TurnBubble from './TurnBubble';
import type { ConversationTurn } from '../api/types';

afterEach(cleanup);

// =============================================================================
// Layer 3: Protocol Driver & Helpers
// =============================================================================
vi.mock('./MermaidBlock', () => ({
  default: ({ code }: { code: string }) => <div data-testid="mermaid-block">{code}</div>,
}));

function hexToRgb(hex: string): string {
  const bigint = parseInt(hex.replace('#', ''), 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgb(${r}, ${g}, ${b})`;
}

function expectBorderLeftColor(element: HTMLElement, hexColor: string) {
  const raw = element.style.borderLeft.toLowerCase();
  const longhand = element.style.borderLeftColor;
  const normalized = hexToRgb(hexColor);
  expect(raw.includes(hexColor.toLowerCase()) || raw.includes(normalized) || longhand === normalized).toBe(true);
}

function createMockTurn(overrides: Partial<ConversationTurn> = {}): ConversationTurn {
  return {
    turn: 1,
    actor: 'developer',
    action: 'execute',
    timestamp: 1700000000,
    result: 'Execution completed',
    ...overrides,
  } as unknown as ConversationTurn;
}

function renderTurnBubble(
  turnOverrides: Partial<ConversationTurn> = {},
  propsOverrides: Partial<React.ComponentProps<typeof TurnBubble>> = {}
) {
  const turn = createMockTurn(turnOverrides);
  return render(<TurnBubble turn={turn} {...propsOverrides} />);
}

// =============================================================================
// Layer 1 & 2: Domain Scenarios & DSL
// =============================================================================
describe('TurnBubble: Unified Actor Bubble Cards (ATDD T-1 - T-7)', () => {
  it('T-1: Given a user message turn, When rendered in TurnBubble, Then it renders strictly left-aligned with operator styling', () => {
    renderTurnBubble({
      actor: 'user',
      action: 'message',
      thoughts: 'User message here',
    });

    const card = screen.getByTestId('turn-bubble-card');
    expect(card.style.textAlign).toBe('left');
    expect(card.style.marginLeft).toBe('0px');
    expectBorderLeftColor(card, '#ec4899');
    expect(screen.getByText('User')).toBeInTheDocument();
  });

  it('T-2: Given an autonomous agent turn (brain), When rendered in TurnBubble, Then it renders as an Actor Card with AI-generated badge and footer feedback buttons', () => {
    renderTurnBubble(
      {
        actor: 'brain',
        action: 'response',
        result: 'Brain response text',
      },
      { eventId: 'evt-1' }
    );

    const card = screen.getByTestId('turn-bubble-card');
    expect(screen.getByText('AI-generated')).toBeInTheDocument();
    expectBorderLeftColor(card, '#8b5cf6');
    expect(screen.getByTitle('Helpful')).toBeInTheDocument();
    expect(screen.getByTitle('Not helpful')).toBeInTheDocument();
  });

  it('T-3: Given a turn with an image attachment, When rendered, Then image renders responsive and left-aligned without auto margin', () => {
    renderTurnBubble({
      actor: 'user',
      action: 'message',
      image: 'https://example.com/test.png',
    });

    const img = screen.getByRole('img');
    expect(img.style.marginLeft).not.toBe('auto');
    expect(img.style.marginLeft === '0px' || img.style.marginLeft === '').toBe(true);
  });

  it('T-4: Given a turn with long markdown text and code blocks, When rendered, Then container prevents horizontal blowout with overflow guard', () => {
    renderTurnBubble({
      actor: 'developer',
      action: 'execute',
      result: '```ts\nconst x = 1;\n```',
    });

    const body = screen.getByTestId('turn-bubble-body');
    expect(body.style.overflowX).toBe('auto');
  });

  it('T-5: Given a phase turn (action: phase, actor: brain), When rendered in TurnBubble, Then it early-returns the specialized phase ribbon', () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'phase',
      thoughts: 'Phase: verify. Verifying results',
    });

    expect(screen.queryByTestId('turn-bubble-card')).toBeNull();
    expect(screen.getByText('Verify')).toBeInTheDocument();
  });

  it('T-6: Given a main-card agent turn with recallApplied: true, When rendered in TurnBubble, Then it preserves the RECALL badge', () => {
    renderTurnBubble(
      {
        actor: 'developer',
        action: 'execute',
        result: 'Done with execution',
      },
      { recallApplied: true }
    );

    const card = screen.getByTestId('turn-bubble-card');
    expect(card).toBeInTheDocument();
    expect(screen.getByText(/🧠 RECALL/)).toBeInTheDocument();
  });

  it('T-7: Given a main-card turn with "Tampering Guard" in evidence, When rendered in TurnBubble, Then it preserves the TAMPERING BLOCKED badge', () => {
    renderTurnBubble({
      actor: 'developer',
      action: 'execute',
      evidence: 'Tampering Guard detected: test setpoint is immutable',
    });

    const card = screen.getByTestId('turn-bubble-card');
    expect(card).toBeInTheDocument();
    expect(screen.getByText(/🛑 TAMPERING BLOCKED/)).toBeInTheDocument();
  });

  it('T-8: Given an autonomous agent turn (e.g. developer), When rendered in TurnBubble, Then it does NOT render message delivery status checks (F-01)', () => {
    renderTurnBubble({
      actor: 'developer',
      action: 'execute',
      result: 'Finished command',
    });

    expect(screen.queryByTitle('Sent')).toBeNull();
    expect(screen.queryByTitle('Delivered')).toBeNull();
    expect(screen.queryByTitle('Read')).toBeNull();
    expect(screen.queryByTitle('Processed')).toBeNull();
  });

  it('T-9: Given a human message turn, When rendered in TurnBubble, Then it renders the appropriate status check receipt', () => {
    renderTurnBubble({
      actor: 'user',
      action: 'message',
      thoughts: 'Hello FRIDAY',
      status: 'delivered',
    });

    expect(screen.getByTitle('Delivered')).toBeInTheDocument();
  });
});
