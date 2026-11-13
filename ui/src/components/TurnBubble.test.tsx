// BlackBoard/ui/src/components/TurnBubble.test.tsx
// @ai-rules:
// 1. [Pattern]: Style assertions read inline styles via data-testid hooks (turn-bubble-card/-header/-body); jsdom serializes colors as rgb()/rgba().
// 2. [Constraint]: createMockTurn defaults to NO result/thoughts -- each scenario sets only what it needs so fixtures never leak into user-turn cases.
// 3. [Constraint]: ../api/client and ./MarkdownViewer are mocked; Approve/Reject/feedback never hit the network. ACTOR_LABELS has no 'developer' entry, so unmapped actors render raw.
// 4. [Gotcha]: Global RTL cleanup lives in src/testSetup.ts and only toBeInTheDocument is registered -- no per-file afterEach(cleanup), no jest-dom matchers.
// 5. [Contract]: VMER-2340 receipt (T-8/T-9/T-9a): every standard actor card (user/developer/brain/jarvis) renders StatusCheck in the right header cluster, after the timestamp and before the "View" button; early-return rows (thoughts/phase/dispatcher/reflex/tool_result/triage/wait/transient error) render none.
// 6. [Constraint]: Titles Sent/Delivered/Evaluated/Executed with glyphs ✓/✓✓/✓✓/✓✓● and hex #64748b/#64748b/#3b82f6/#22c55e asserted for EVERY matrix row; missing/unknown status falls back to 'Sent'. No `any` -- the single `as MessageStatus | undefined` cast at the render boundary injects 'unknown'.
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
const { approveEvent, rejectEvent, submitFeedback } = vi.hoisted(() => ({
  approveEvent: vi.fn(),
  rejectEvent: vi.fn(),
  submitFeedback: vi.fn(),
}));

vi.mock('../api/client', () => ({ approveEvent, rejectEvent, submitFeedback }));

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
// T-17+: Approve / Reject
// =============================================================================
describe('TurnBubble: pendingApproval Approve / Reject (T-17)', () => {
  it('T-17a: Given pendingApproval with eventId, When rendered, Then Approve and Reject buttons are present', () => {
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1' }
    );
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
  });

  it('T-17b: Given pendingApproval, When Approve is clicked, Then approveEvent("evt-1") is called and onStatusChange fires', async () => {
    const onStatusChange = vi.fn();
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(approveEvent).toHaveBeenCalledTimes(1);
    expect(approveEvent).toHaveBeenCalledWith('evt-1');
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
    expect(rejectEvent).not.toHaveBeenCalled();
  });

  it('T-17c: Given pendingApproval, When Reject is confirmed in the modal, Then rejectEvent("evt-1", default reason) is called and onStatusChange fires', async () => {
    const onStatusChange = vi.fn();
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1', onStatusChange }
    );

    // First Reject opens the modal; nothing is sent yet.
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    expect(rejectEvent).not.toHaveBeenCalled();
    expect(screen.getByText('Reject Plan')).toBeInTheDocument();

    // The modal exposes a second Reject button (portal on document.body) that submits.
    const rejectButtons = screen.getAllByRole('button', { name: 'Reject' });
    expect(rejectButtons).toHaveLength(2);
    fireEvent.click(rejectButtons[1]);

    expect(rejectEvent).toHaveBeenCalledTimes(1);
    expect(rejectEvent).toHaveBeenCalledWith('evt-1', 'User rejected the plan.', undefined);
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledTimes(1));
    expect(approveEvent).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByText('Reject Plan')).toBeNull());
  });

  it('T-17d: Given a typed rejection reason, When Reject is confirmed, Then the reason is forwarded to rejectEvent', async () => {
    renderTurnBubble(
      { actor: 'brain', action: 'request_approval', pendingApproval: true },
      { eventId: 'evt-1' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    fireEvent.change(screen.getByPlaceholderText(/Reason for rejection/), { target: { value: '  too risky  ' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[1]);

    expect(rejectEvent).toHaveBeenCalledWith('evt-1', 'too risky', undefined);
    await waitFor(() => expect(screen.queryByText('Reject Plan')).toBeNull());
  });

  it.each([
    ['pendingApproval false', { pendingApproval: false }, { eventId: 'evt-1' }],
    ['pendingApproval omitted', {}, { eventId: 'evt-1' }],
    ['eventId undefined', { pendingApproval: true }, {}],
  ])('T-17e: Given %s, When rendered, Then Approve/Reject are absent', (_name, turnOverrides, propsOverrides) => {
    renderTurnBubble({ actor: 'brain', action: 'request_approval', ...turnOverrides }, propsOverrides);
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
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
