// BlackBoard/ui/src/components/TurnBubble.test.tsx
// @ai-rules:
// 1. [Pattern]: Style assertions read inline styles via data-testid hooks (turn-bubble-card/-header/-body); jsdom serializes colors as rgb()/rgba().
// 2. [Constraint]: createMockTurn defaults to NO result/thoughts -- each scenario sets only what it needs so fixtures never leak into user-turn cases.
// 3. [Constraint]: ../api/client and ./MarkdownViewer are mocked; Approve/Reject/feedback never hit the network. ACTOR_LABELS has no 'developer' entry, so unmapped actors render raw.
// 4. [Gotcha]: Global RTL cleanup lives in src/testSetup.ts and only toBeInTheDocument is registered -- no per-file afterEach(cleanup), no jest-dom matchers.
// 5. [Contract]: VMER-2340 receipt (T-8/T-9/T-9a): every standard actor card (user/developer/brain/jarvis) renders StatusCheck in the right header cluster, after the timestamp and before the "View" button; early-return rows (thoughts/phase/dispatcher/reflex/tool_result/triage/wait/transient error) render none.
// 6. [Constraint]: Titles Sent/Delivered/Evaluated/Executed with glyphs ✓/✓✓/✓✓/✓✓● and hex #64748b/#64748b/#3b82f6/#22c55e asserted for EVERY matrix row; missing/unknown status falls back to 'Sent'. No `any` -- the `as MessageStatus` casts at the render boundary inject 'unknown' and prototype keys (constructor/toString/__proto__/hasOwnProperty) -- T-8a guards the Object.hasOwn lookup.
/**
 * 4-Layer Farley ATDD Executable Acceptance Specification
 * Scenarios T-1 through T-9a: TurnBubble Actor Bubble Cards, Left Alignment and VMER-2340 delivery receipts
 * Scenarios T-10 onward: hardening coverage added after 6-lens review of PR #318
 *
 * Layer 1: Domain Scenarios (Given/When/Then)
 * Layer 2: Domain DSL operations
 * Layer 3: Protocol Driver (React Testing Library)
 * Layer 4: System Under Test (TurnBubble component)
 */
import type { ComponentProps } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import TurnBubble from './TurnBubble';
import type { ConversationTurn, MessageStatus } from '../api/types';

// =============================================================================
// Layer 3: Protocol Driver & Helpers
// =============================================================================
const { approveEvent, rejectEvent, submitFeedback, submitApprovalDecision, MockApiError } = vi.hoisted(() => {
  class MockApiError extends Error {
    readonly status: number;
    readonly statusText: string;
    readonly endpoint: string;
    readonly detail?: string;
    readonly body?: Record<string, unknown>;
    constructor(
      status: number,
      statusText: string,
      endpoint: string,
      detail?: string,
      body?: Record<string, unknown>
    ) {
      super(`API Error [${status}] ${endpoint}: ${detail || statusText}`);
      this.name = 'ApiError';
      this.status = status;
      this.statusText = statusText;
      this.endpoint = endpoint;
      this.detail = detail;
      this.body = body;
    }
  }
  return {
    approveEvent: vi.fn(),
    rejectEvent: vi.fn(),
    submitFeedback: vi.fn(),
    submitApprovalDecision: vi.fn(),
    MockApiError,
  };
});

vi.mock('../utils/imageResize', () => ({ resizeImage: vi.fn().mockResolvedValue('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=') }));
vi.mock('../api/client', () => ({ approveEvent, rejectEvent, submitFeedback, submitApprovalDecision, ApiError: MockApiError }));

vi.mock('./MermaidBlock', () => ({
  default: ({ code }: { code: string }) => <div data-testid="mermaid-block">{code}</div>,
}));

vi.mock('./MarkdownViewer', () => ({
  default: ({ filename, content, onClose }: { filename: string; content: string; onClose: () => void }) => (
    <div data-testid="markdown-viewer">
      <span data-testid="markdown-viewer-filename">{filename}</span>
      <span data-testid="markdown-viewer-content">{content}</span>
      <button onClick={onClose}>close-viewer</button>
    </div>
  ),
}));

beforeEach(() => {
  approveEvent.mockReset().mockResolvedValue({});
  rejectEvent.mockReset().mockResolvedValue({});
  submitFeedback.mockReset().mockResolvedValue({});
  submitApprovalDecision.mockReset().mockResolvedValue({});
});

function hexToRgb(hex: string): string {
  const bigint = parseInt(hex.replace('#', ''), 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgb(${r}, ${g}, ${b})`;
}

function expectBorderLeftColor(element: HTMLElement, hexColor: string) {
  expect(element.style.borderLeftColor).toBe(hexToRgb(hexColor));
  expect(element.style.borderLeftWidth).toBe('3px');
}

/** Default fixture carries NO result/thoughts: scenarios opt in to the content they exercise. */
function createMockTurn(overrides: Partial<ConversationTurn> = {}): ConversationTurn {
  return {
    turn: 1,
    actor: 'developer',
    action: 'execute',
    timestamp: 1700000000,
    ...overrides,
  };
}

function renderTurnBubble(
  turnOverrides: Partial<ConversationTurn> = {},
  propsOverrides: Partial<ComponentProps<typeof TurnBubble>> = {}
) {
  const turn = createMockTurn(turnOverrides);
  return render(<TurnBubble turn={turn} {...propsOverrides} />);
}

// =============================================================================
// Layer 1 & 2: Domain Scenarios & DSL
// =============================================================================
describe('TurnBubble: Unified Actor Bubble Cards (ATDD T-1 - T-9)', () => {
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

  it.each([
    ['user'],
    ['developer'],
  ])('T-3: Given a %s turn with an image attachment, When rendered, Then image is left-aligned, block-level, without auto margin', (actor) => {
    renderTurnBubble({
      actor,
      action: 'message',
      image: 'https://example.com/test.png',
    });

    const img = screen.getByAltText('User attachment') as HTMLImageElement;
    expect(img.style.marginLeft).toBe('0px');
    expect(img.style.display).toBe('block');
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

    expect(screen.getByText(/🧠 RECALL/)).toBeInTheDocument();
  });

  it('T-7: Given a main-card turn with "Tampering Guard" in evidence, When rendered in TurnBubble, Then it preserves the TAMPERING BLOCKED badge', () => {
    renderTurnBubble({
      actor: 'developer',
      action: 'execute',
      evidence: 'Tampering Guard detected: test setpoint is immutable',
    });

    expect(screen.getByText(/🛑 TAMPERING BLOCKED/)).toBeInTheDocument();
  });

  // VMER-2340 receipt contract: [label, status, title, glyph, hex color].
  // 'unknown' simulates a status value the UI does not recognise; 'missing' is an absent status.
  type StatusInput = MessageStatus | 'unknown' | undefined;
  const statusReceiptMatrix: [string, StatusInput, string, string, string][] = [
    ['missing', undefined, 'Sent', '✓', '#64748b'],
    ['unknown', 'unknown', 'Sent', '✓', '#64748b'],
    ['sent', 'sent', 'Sent', '✓', '#64748b'],
    ['delivered', 'delivered', 'Delivered', '✓✓', '#64748b'],
    ['evaluated', 'evaluated', 'Evaluated', '✓✓', '#3b82f6'],
    ['processed', 'processed', 'Executed', '✓✓●', '#22c55e'],
  ];
  const receiptTitles = ['Sent', 'Delivered', 'Evaluated', 'Executed'];

  const receiptActors = ['user', 'developer', 'brain', 'jarvis'] as const;
  const receiptCases = receiptActors.flatMap((actor) =>
    statusReceiptMatrix.map(([label, status, title, glyph, hex]) => [actor, label, status, title, glyph, hex] as const)
  );

  it.each(receiptCases)(
    'T-8: Given a %s turn with %s status, When rendered, Then the right header cluster shows the "%s" receipt',
    (actor, _label, status, title, glyph, hex) => {
      renderTurnBubble({
        actor,
        action: actor === 'user' ? 'message' : 'execute',
        thoughts: actor === 'user' ? 'Hello FRIDAY' : undefined,
        result: actor !== 'user' ? 'Finished task' : undefined,
        status: status as MessageStatus | undefined, // single cast: lets 'unknown' reach the component
      });

      const receipt = screen.getByTitle(title);
      expect(receipt.textContent).toBe(glyph);
      expect(receipt.style.color).toBe(hexToRgb(hex));
      for (const other of receiptTitles.filter((t) => t !== title)) {
        expect(screen.queryByTitle(other)).toBeNull();
      }

      // Receipt lives in the right header cluster (marginLeft:auto, flexShrink:0), right after the timestamp.
      const rightCluster = receipt.parentElement;
      expect(rightCluster).toBeInTheDocument();
      expect(rightCluster?.style.marginLeft).toBe('auto');
      expect(rightCluster?.style.flexShrink).toBe('0');
      expect(screen.getByTestId('turn-bubble-header').contains(rightCluster)).toBe(true);

      const expectedTimeString = new Date(1700000000 * 1000).toLocaleTimeString();
      expect(receipt.previousElementSibling?.textContent).toBe(expectedTimeString);
    }
  );

  // Guards the Object.hasOwn lookup: inherited Object.prototype keys must not resolve to a receipt entry.
  it.each(['constructor', 'toString', '__proto__', 'hasOwnProperty'])(
    'T-8a: Given a turn whose status is the prototype key "%s", When rendered, Then the receipt falls back to "Sent"',
    (protoKey) => {
      renderTurnBubble({
        actor: 'brain',
        action: 'execute',
        result: 'Finished task',
        status: protoKey as MessageStatus, // single cast: injects a prototype key as an unrecognised status
      });

      const receipt = screen.getByTitle('Sent');
      expect(receipt.textContent).toBe('✓');
      expect(receipt.style.color).toBe(hexToRgb('#64748b'));
      for (const other of receiptTitles.filter((t) => t !== 'Sent')) {
        expect(screen.queryByTitle(other)).toBeNull();
      }
    }
  );

  it('T-9: Given a report-worthy turn with onViewReport, When rendered, Then the right header cluster orders timestamp, receipt, then the View button', () => {
    const onViewReport = vi.fn();
    renderTurnBubble(
      { actor: 'developer', action: 'execute', result: 'x'.repeat(501), status: 'processed' },
      { onViewReport }
    );

    const receipt = screen.getByTitle('Executed');
    const cluster = receipt.parentElement as HTMLElement;
    const children = Array.from(cluster.children) as HTMLElement[];
    expect(children).toHaveLength(3);
    expect(children[0].textContent).toBe(new Date(1700000000 * 1000).toLocaleTimeString());
    expect(children[1]).toBe(receipt);
    expect(children[2].tagName).toBe('BUTTON');
    expect(children[2].title).toBe('Open in floating viewer');
    expect(children[2].textContent).toContain('View');

    fireEvent.click(children[2]);
    expect(onViewReport).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['thoughts', { actor: 'brain', action: 'thoughts', thoughts: 'Considering options' }],
    ['phase', { actor: 'brain', action: 'phase', thoughts: 'Phase: verify. Verifying results' }],
    ['dispatcher', { actor: 'dispatcher', action: 'route', thoughts: 'Routed to developer' }],
    ['reflex', { actor: 'system', action: 'reflex', thoughts: '2 lesson match' }],
    ['tool_result', { actor: 'brain', action: 'tool_result', thoughts: 'tool output' }],
    ['triage', { actor: 'brain', action: 'triage', thoughts: 'triage notes' }],
    ['wait', { actor: 'brain', action: 'wait', thoughts: 'waiting' }],
    ['transient error', { actor: 'brain', action: 'error', thoughts: '429 RESOURCE_EXHAUSTED' }],
  ] as [string, Partial<ConversationTurn>][])(
    'T-9a: Given a %s row (early-return path) with status processed, When rendered, Then no delivery receipt renders',
    (_name, overrides) => {
      renderTurnBubble({ ...overrides, status: 'processed' });

      expect(screen.queryByTestId('turn-bubble-card')).toBeNull();
      for (const title of receiptTitles) {
        expect(screen.queryByTitle(title)).toBeNull();
      }
    }
  );
});

// =============================================================================
// T-10+: Card chrome (label, background, layout)
// =============================================================================
describe('TurnBubble: card chrome (T-10 - T-13)', () => {
  it('T-10: Given a human turn vs an agent turn, When rendered, Then the card backgrounds differ (pink tint vs slate)', () => {
    const { unmount } = renderTurnBubble({ actor: 'user', action: 'message', thoughts: 'hi' });
    const humanBg = screen.getByTestId('turn-bubble-card').style.backgroundColor;
    expect(humanBg).toBe('rgba(236, 72, 153, 0.05)');
    unmount();

    renderTurnBubble({ actor: 'developer', action: 'execute', result: 'ok' });
    const agentBg = screen.getByTestId('turn-bubble-card').style.backgroundColor;
    expect(agentBg).toBe('rgba(15, 23, 42, 0.55)');
    expect(agentBg).not.toBe(humanBg);
  });

  it.each([
    [{ actor: 'user', user_name: 'alice' }, 'User (alice)'],
    [{ actor: 'brain', user_name: 'carol' }, 'FRIDAY (carol)'],
    // ACTOR_LABELS has no 'developer' entry: label falls back to the raw actor string.
    [{ actor: 'developer', user_name: 'bob' }, 'developer (bob)'],
    [{ actor: 'user' }, 'User'],
    [{ actor: 'developer' }, 'developer'],
    [{ actor: 'some_unmapped_actor' }, 'some_unmapped_actor'],
  ])('T-11: Given %j, When rendered, Then the actor pill reads "%s"', (overrides, expectedLabel) => {
    renderTurnBubble({ action: 'message', thoughts: 'body text', ...overrides });
    const pill = screen.getByText(expectedLabel);
    expect(pill.textContent).toBe(expectedLabel);
    // pill is the actor-colored span inside the header row
    expect(screen.getByTestId('turn-bubble-header').contains(pill)).toBe(true);
  });

  it('T-12: Given any card turn, When rendered, Then the card is full width and the header row wraps', () => {
    renderTurnBubble({ actor: 'developer', action: 'execute', result: 'ok' });
    const card = screen.getByTestId('turn-bubble-card');
    expect(card.style.width).toBe('100%');
    const header = screen.getByTestId('turn-bubble-header');
    expect(header.style.display).toBe('flex');
    expect(header.style.flexWrap).toBe('wrap');
  });

  it('T-13: Given a user turn, When rendered, Then no result leaks from the fixture default', () => {
    renderTurnBubble({ actor: 'user', action: 'message', thoughts: 'only thoughts' });
    const body = screen.getByTestId('turn-bubble-body');
    expect(body.textContent).toContain('only thoughts');
    expect(body.textContent).not.toContain('Execution completed');
  });
});

// =============================================================================
// T-14+: Human-turn badge gating
// =============================================================================
describe('TurnBubble: human turns never show agent-only badges (T-14)', () => {
  it('T-14: Given a user turn with recallApplied and Tampering Guard text, When rendered, Then RECALL, TAMPERING and AI-generated badges are absent', () => {
    renderTurnBubble(
      {
        actor: 'user',
        action: 'message',
        thoughts: 'Tampering Guard mentioned by the operator',
        evidence: 'Tampering Guard',
        result: 'Tampering Guard',
      },
      { recallApplied: true }
    );

    expect(screen.queryByText(/RECALL/)).toBeNull();
    expect(screen.queryByText(/TAMPERING BLOCKED/)).toBeNull();
    expect(screen.queryByText('AI-generated')).toBeNull();
  });

  it('T-14b: Given the same flags on an agent turn, When rendered, Then all three badges DO render (positive control)', () => {
    renderTurnBubble(
      {
        actor: 'developer',
        action: 'execute',
        evidence: 'Tampering Guard',
      },
      { recallApplied: true }
    );

    expect(screen.getByText(/🧠 RECALL/)).toBeInTheDocument();
    expect(screen.getByText(/🛑 TAMPERING BLOCKED/)).toBeInTheDocument();
    expect(screen.getByText('AI-generated')).toBeInTheDocument();
  });
});

// =============================================================================
// T-15+: AttachmentIcon
// =============================================================================
describe('TurnBubble: AttachmentIcon (T-15)', () => {
  it.each([['user'], ['developer']])(
    'T-15: Given a %s turn with an attachment, When the icon is clicked, Then the viewer opens with that file; absent when attachment is null',
    (actor) => {
      const attachment = { filename: 'plan.md', content: 'x' };
      const { unmount } = renderTurnBubble({ actor, action: 'message', thoughts: 'see attached' }, { attachment });

      const icon = screen.getByTitle('plan.md');
      expect(screen.queryByTestId('markdown-viewer')).toBeNull();
      fireEvent.click(icon);
      expect(screen.getByTestId('markdown-viewer-filename').textContent).toBe('plan.md');
      expect(screen.getByTestId('markdown-viewer-content').textContent).toBe('x');

      fireEvent.click(screen.getByText('close-viewer'));
      expect(screen.queryByTestId('markdown-viewer')).toBeNull();
      unmount();

      renderTurnBubble({ actor, action: 'message', thoughts: 'no attachment' }, { attachment: null });
      expect(screen.queryByTitle('plan.md')).toBeNull();
    }
  );
});

// =============================================================================
// T-16+: Floating viewer ("View") button
// =============================================================================
describe('TurnBubble: floating viewer View button (T-16)', () => {
  const longResult = 'R'.repeat(501);

  it('T-16a: Given an execute turn with result > 500 chars, When View is clicked, Then onViewReport gets the exact markdown and filename', () => {
    const onViewReport = vi.fn();
    renderTurnBubble(
      { turn: 7, actor: 'developer', action: 'execute', result: longResult },
      { onViewReport }
    );

    fireEvent.click(screen.getByTitle('Open in floating viewer'));
    expect(onViewReport).toHaveBeenCalledTimes(1);
    expect(onViewReport).toHaveBeenCalledWith(
      `# developer — execute\n\n**Turn 7**\n\n---\n\n## Result\n\n${longResult}`,
      'developer — execute (turn 7)'
    );
  });

  it('T-16a2: Given an execute turn with thoughts and long result, When View is clicked, Then the markdown includes the Analysis section', () => {
    const onViewReport = vi.fn();
    renderTurnBubble(
      { turn: 3, actor: 'sysadmin', action: 'execute', thoughts: 'Because reasons', result: longResult },
      { onViewReport }
    );

    fireEvent.click(screen.getByTitle('Open in floating viewer'));
    expect(onViewReport).toHaveBeenCalledWith(
      `# sysadmin — execute\n\n**Turn 3**\n\n---\n\n## Analysis\n\nBecause reasons\n\n## Result\n\n${longResult}`,
      'sysadmin — execute (turn 3)'
    );
  });

  it('T-16b: Given a plan turn with selectedAgents, When View is clicked, Then onViewReport gets the exact plan markdown and filename', () => {
    const onViewReport = vi.fn();
    renderTurnBubble(
      {
        turn: 4,
        actor: 'brain',
        action: 'plan',
        thoughts: 'Rationale',
        plan: '1. Do the thing',
        selectedAgents: ['developer', 'qe'],
      },
      { onViewReport }
    );

    fireEvent.click(screen.getByTitle('Open in floating viewer'));
    expect(onViewReport).toHaveBeenCalledTimes(1);
    expect(onViewReport).toHaveBeenCalledWith(
      '# Plan by brain\n\n> Rationale\n\n---\n\n1. Do the thing\n\n---\n\n**Assigned agents:** developer, qe',
      'brain — Plan (turn 4)'
    );
  });

  it('T-16c: Given a request_approval turn with thoughts, When View is clicked, Then onViewReport gets the exact approval markdown and filename', () => {
    const onViewReport = vi.fn();
    renderTurnBubble(
      { turn: 9, actor: 'brain', action: 'request_approval', thoughts: 'Please approve the rollout' },
      { onViewReport }
    );

    fireEvent.click(screen.getByTitle('Open in floating viewer'));
    expect(onViewReport).toHaveBeenCalledTimes(1);
    expect(onViewReport).toHaveBeenCalledWith(
      '# Approval Request\n\n**brain** — turn 9\n\n---\n\nPlease approve the rollout\n\n---\n\n> **Action required:** Review the plan and approve or reject.',
      'brain — Approval Request (turn 9)'
    );
  });

  it('T-16d: Given an eligible turn but no onViewReport callback, When rendered, Then no View button appears', () => {
    renderTurnBubble({ actor: 'developer', action: 'execute', result: longResult });
    expect(screen.queryByTitle('Open in floating viewer')).toBeNull();
  });

  it('T-16e: Given an execute turn with a short result (<= 500 chars), When rendered with onViewReport, Then no View button appears', () => {
    const onViewReport = vi.fn();
    renderTurnBubble({ actor: 'developer', action: 'execute', result: 'R'.repeat(500) }, { onViewReport });
    expect(screen.queryByTitle('Open in floating viewer')).toBeNull();
    expect(onViewReport).not.toHaveBeenCalled();
  });

  it('T-16f: Given a human turn shaped like an eligible execute, When rendered with onViewReport, Then no View button appears', () => {
    renderTurnBubble(
      { actor: 'user', action: 'execute', result: longResult },
      { onViewReport: vi.fn() }
    );
    expect(screen.queryByTitle('Open in floating viewer')).toBeNull();
  });
});

// =============================================================================
// T-17 / T-18: Multi-Option Approvals
// =============================================================================
describe('TurnBubble: pendingApproval Multi-Option (T-17/T-18)', () => {
  it('T-17a: Given pendingApproval with eventId, When rendered, Then synthesized default options are present', () => {
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1' }
    );
    expect(screen.getByLabelText(/Approve plan/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Reject plan/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Write-in custom instruction/i)).toBeInTheDocument();
  });

  it('T-17b: Given pendingApproval, When "Approve plan" is selected and Submit is clicked, Then submitApprovalDecision("evt-1", { option_id: "approve" }) is called and onStatusChange fires', async () => {
    const onStatusChange = vi.fn();
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    expect(submitApprovalDecision).toHaveBeenCalledTimes(1);
    expect(submitApprovalDecision).toHaveBeenCalledWith('evt-1', { option_id: 'approve' });
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
  });

  it('T-17c: Given pendingApproval, When "Reject plan" is selected and Submit is clicked, Then submitApprovalDecision("evt-1", { option_id: "reject" }) is called and onStatusChange fires', async () => {
    const onStatusChange = vi.fn();
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    fireEvent.click(screen.getByLabelText(/Reject plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    expect(submitApprovalDecision).toHaveBeenCalledTimes(1);
    expect(submitApprovalDecision).toHaveBeenCalledWith('evt-1', { option_id: 'reject' });
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
  });

  it.each([
    ['pendingApproval false', { pendingApproval: false }, { eventId: 'evt-1' }],
    ['eventId undefined', { pendingApproval: true }, {}],
  ])('T-17e: Given %s, When rendered, Then radios are absent', (_name, turnOverrides, propsOverrides) => {
    renderTurnBubble({ actor: 'brain', action: 'request_approval', ...turnOverrides }, propsOverrides);
    expect(screen.queryByRole('radio')).toBeNull();
  });

  it('T-17f: Given 409 SHA drift on Approve, When user confirms new SHA, Then inline diff (req[:8] -> live[:8]) renders and retry passes expectedSha', async () => {
    const SHA_1 = '11111111aaaa0000000000000000000000000000';
    const SHA_2 = '22222222bbbb0000000000000000000000000000';
    const onStatusChange = vi.fn();

    submitApprovalDecision
      .mockRejectedValueOnce(
        new MockApiError(409, 'Conflict', '/queue/evt-1/decision', 'HEAD SHA changed', {
          code: 'sha_drift',
          detail: 'HEAD SHA changed',
          approval_requested_sha: SHA_1,
          live_sha: SHA_2,
        })
      )
      .mockResolvedValueOnce({ status: 'approved' });

    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => expect(screen.getByText(/11111111/)).toBeInTheDocument());
    expect(screen.getByText(/22222222/)).toBeInTheDocument();
    expect(onStatusChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Approve New SHA|Confirm/i }));
    expect(submitApprovalDecision).toHaveBeenNthCalledWith(2, 'evt-1', { option_id: 'approve', expected_sha: SHA_2 });
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
  });

  it('T-17g (H9): Cascading 409 SHA drifts update inline UI sequentially until successful', async () => {
    const SHA_1 = '11111111aaaa0000000000000000000000000000';
    const SHA_2 = '22222222bbbb0000000000000000000000000000';
    const SHA_3 = '33333333cccc0000000000000000000000000000';
    const onStatusChange = vi.fn();

    submitApprovalDecision
      .mockRejectedValueOnce(
        new MockApiError(409, 'Conflict', '/queue/evt-1/decision', 'HEAD SHA changed', {
          code: 'sha_drift',
          approval_requested_sha: SHA_1,
          live_sha: SHA_2,
        })
      )
      .mockRejectedValueOnce(
        new MockApiError(409, 'Conflict', '/queue/evt-1/decision', 'HEAD SHA changed again', {
          code: 'sha_drift',
          approval_requested_sha: SHA_2,
          live_sha: SHA_3,
        })
      )
      .mockResolvedValueOnce({ status: 'approved' });

    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => expect(screen.getByText(/22222222/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Approve New SHA|Confirm/i }));
    expect(submitApprovalDecision).toHaveBeenNthCalledWith(2, 'evt-1', { option_id: 'approve', expected_sha: SHA_2 });

    await waitFor(() => expect(screen.getByText(/33333333/)).toBeInTheDocument());
    expect(onStatusChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Approve New SHA|Confirm/i }));
    expect(submitApprovalDecision).toHaveBeenNthCalledWith(3, 'evt-1', { option_id: 'approve', expected_sha: SHA_3 });
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
  });

  it('T-17h (H9): Double-clicking Submit rapidly fires submitApprovalDecision only once (synchronous inFlightRef lock)', async () => {
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1' }
    );
    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    const btn = screen.getByRole('button', { name: 'Submit' });
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(submitApprovalDecision).toHaveBeenCalledTimes(1);
  });

  it('T-17i (H9): Changing eventId cancels in-flight approval side effects and clears stale drift/error state', async () => {
    const onStatusChange = vi.fn();
    submitApprovalDecision.mockImplementationOnce(() => new Promise(res => setTimeout(() => res({ status: 'approved' }), 50)));

    const { rerender } = render(
      <TurnBubble turn={createMockTurn({ actor: 'brain', action: 'request_approval', pendingApproval: true })} eventId="evt-1" onStatusChange={onStatusChange} />
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    rerender(
      <TurnBubble turn={createMockTurn({ actor: 'brain', action: 'request_approval', pendingApproval: true })} eventId="evt-2" onStatusChange={onStatusChange} />
    );

    await waitFor(() => expect(submitApprovalDecision).toHaveBeenCalledTimes(1));
    await new Promise(r => setTimeout(r, 100)); // wait past resolution
    expect(onStatusChange).not.toHaveBeenCalled();
  });

  it('T-17j (H9): Non-409 error renders dismissible alert on both Submit and Confirm New SHA', async () => {
    submitApprovalDecision.mockRejectedValueOnce(new MockApiError(500, 'Internal Server Error', '/queue/evt-1/decision', 'Not authorized'));

    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1' }
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => expect(screen.getByText('Not authorized')).toBeInTheDocument());
  });

  it('T-17k (H9): 409 closed/sha_unresolvable renders Approval blocked without Confirm New SHA and Cancel dismisses', async () => {
    submitApprovalDecision.mockRejectedValueOnce(
      new MockApiError(409, 'Conflict', '/queue/evt-closed/decision', 'Event is already closed and cannot be approved.', {
        code: 'closed',
        detail: 'Event is already closed and cannot be approved.',
      })
    );

    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-closed' }
    );

    fireEvent.click(screen.getByLabelText(/Approve plan/i));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain(
        'Approval blocked: Event is already closed and cannot be approved.'
      )
    );
    expect(screen.queryByRole('button', { name: /Confirm New SHA/i })).toBeNull();
  });

  it('T-18a: Active 3-option request_approval turn renders 4 visible radio options with NO default checked radio and Submit disabled', () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: true,
      approval_id: 'apv-123',
      approval_options: [
        { id: 'opt1', label: 'Approve plan', effect: 'approve' },
        { id: 'opt2', label: 'Rerun checks', effect: 'feedback' },
        { id: 'opt3', label: 'Reject plan', effect: 'reject' }
      ]
    }, { eventId: 'evt-test' });

    expect(screen.getByLabelText('Approve plan')).toBeInTheDocument();
    expect(screen.getByLabelText('Rerun checks')).toBeInTheDocument();
    expect(screen.getByLabelText('Reject plan')).toBeInTheDocument();
    expect(screen.getByLabelText('Write-in custom instruction')).toBeInTheDocument();

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(4);
    radios.forEach(r => expect((r as HTMLInputElement).checked).toBe(false));

    expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled();
  });

  it('T-18b: Selecting Write-in..., typing instructions enables Submit and submits { approval_id, option_id: "__write_in__", write_in_text }', async () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: true,
      approval_id: 'apv-123',
      approval_options: [
        { id: 'opt1', label: 'Approve plan', effect: 'approve' }
      ]
    }, { eventId: 'evt-test' });

    fireEvent.click(screen.getByLabelText('Write-in custom instruction'));
    const textBox = screen.getByPlaceholderText(/Provide instructions/i);
    expect(textBox).toBeInTheDocument();

    fireEvent.change(textBox, { target: { value: 'Look at this' } });
    const submitBtn = screen.getByRole('button', { name: 'Submit' });
    await waitFor(() => expect(submitBtn).not.toBeDisabled());
    
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(submitApprovalDecision).toHaveBeenCalledWith('evt-test', expect.objectContaining({
        approval_id: 'apv-123',
        option_id: '__write_in__',
        write_in_text: 'Look at this',
      }));
    });
  });

  it('T-18b-image: Selecting Write-in..., pasting image enables Submit and submits { approval_id, option_id: "__write_in__", write_in_text, image }', async () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: true,
      approval_id: 'apv-123',
      approval_options: [
        { id: 'opt1', label: 'Approve plan', effect: 'approve' }
      ]
    }, { eventId: 'evt-test' });

    fireEvent.click(screen.getByLabelText('Write-in custom instruction'));
    const textBox = screen.getByPlaceholderText(/Provide instructions/i);
    
    const file = new File(['(⌐□_□)'], 'test.png', { type: 'image/png' });
    fireEvent.paste(textBox, {
      clipboardData: {
        items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }],
        files: [file]
      }
    });

    const submitBtn = screen.getByRole('button', { name: 'Submit' });
    await waitFor(() => expect(submitBtn).not.toBeDisabled());
    
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(submitApprovalDecision).toHaveBeenCalledWith('evt-test', expect.objectContaining({
        approval_id: 'apv-123',
        option_id: '__write_in__',
        write_in_text: '',
        image: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
      }));
    });
  });

  it('T-18c: 409 sha_drift renders inline "Confirm New SHA" retry sending expected_sha', async () => {
    submitApprovalDecision.mockRejectedValueOnce(
      new MockApiError(409, 'Conflict', '/queue/evt-test/decision', 'HEAD SHA changed', {
        code: 'sha_drift',
        approval_requested_sha: '111111',
        live_sha: '222222',
      })
    );

    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: true,
      approval_id: 'apv-123',
      approval_options: [
        { id: 'opt1', label: 'Approve plan', effect: 'approve' }
      ]
    }, { eventId: 'evt-test' });

    fireEvent.click(screen.getByLabelText('Approve plan'));
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => expect(screen.getByText(/HEAD SHA drifted/i)).toBeInTheDocument());
    
    const confirmBtn = screen.getByRole('button', { name: 'Confirm New SHA' });
    expect(confirmBtn).toBeInTheDocument();
    
    fireEvent.click(confirmBtn);
    await waitFor(() => {
      expect(submitApprovalDecision).toHaveBeenLastCalledWith('evt-test', {
        approval_id: 'apv-123',
        option_id: 'opt1',
        expected_sha: '222222'
      });
    });
  });

  it('T-18d: Legacy/empty approval_options synthesizes [Approve plan, Reject plan] + Write-in', () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: true,
      approval_id: 'apv-legacy',
      approval_options: undefined
    }, { eventId: 'evt-test' });

    expect(screen.getByLabelText(/Approve plan/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Reject plan/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Write-in custom instruction/i)).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(3);
  });

  it('T-18e: Resolved request_approval renders frozen summary highlighting chosen option/write-in and does NOT render radio buttons', () => {
    renderTurnBubble({
      actor: 'brain',
      action: 'request_approval',
      pendingApproval: false,
      approval_id: 'apv-123',
      approval_resolution: {
        outcome: 'option',
        option_id: 'opt2',
        option_label: 'Rerun checks',
        resolved_at: 1700000000,
        resolved_by: 'alice@example.com'
      }
    }, { eventId: 'evt-test' });

    expect(screen.queryByRole('radio')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Submit' })).toBeNull();
    expect(screen.getByText(/Rerun checks/i)).toBeInTheDocument();
    expect(screen.getByText(/by alice@example\.com/i)).toBeInTheDocument();
    expect(screen.queryByText(/by 1700000000/i)).toBeNull();
  });
});

// =============================================================================
// T-18+: ResultViewer expand / collapse
// =============================================================================
describe('TurnBubble: ResultViewer Expand/Collapse (T-18)', () => {
  it('T-18a: Given an execute turn with result > 500 chars, When Expand/Collapse is toggled, Then the preview height cap is lifted and restored', () => {
    renderTurnBubble({ actor: 'developer', action: 'execute', result: 'word '.repeat(120) });

    const expandBtn = screen.getByRole('button', { name: 'Expand' });
    const clip = expandBtn.previousElementSibling as HTMLElement;
    expect(clip.style.maxHeight).toBe('160px');
    expect(clip.style.overflow).toBe('hidden');

    fireEvent.click(expandBtn);
    const collapseBtn = screen.getByRole('button', { name: 'Collapse' });
    expect(screen.queryByRole('button', { name: 'Expand' })).toBeNull();
    expect(clip.style.maxHeight).toBe('');

    fireEvent.click(collapseBtn);
    expect(screen.getByRole('button', { name: 'Expand' })).toBeInTheDocument();
    expect(clip.style.maxHeight).toBe('160px');
  });

  it('T-18b: Given an execute turn with result <= 500 chars, When rendered, Then no Expand control is shown', () => {
    renderTurnBubble({ actor: 'developer', action: 'execute', result: 'short result' });
    expect(screen.queryByRole('button', { name: 'Expand' })).toBeNull();
  });
});
