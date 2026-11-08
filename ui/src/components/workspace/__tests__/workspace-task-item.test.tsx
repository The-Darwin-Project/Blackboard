// BlackBoard/ui/src/components/workspace/__tests__/workspace-task-item.test.tsx
// @ai-rules:
// 1. [Pattern]: Unit tests for WorkspaceTaskItem rendering, selection, and context menu triggers.
// 2. [Contract]: Verifies unconditional preventDefault and event payload propagation on contextmenu.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceTaskItem from '../WorkspaceTaskItem';
import type { ActiveEvent, EventEvidence } from '../../../api/types';
import { DOMAIN_COLORS, STATUS_COLORS } from '../../../constants/colors';

// jsdom normalises inline colours to rgb(); convert the hex constants the same way for comparison.
const rgb = (hex: string) => {
  const probe = document.createElement('span');
  probe.style.color = hex;
  return probe.style.color;
};

const makeEvent = (over: Partial<Omit<ActiveEvent, 'evidence'>> & { evidence?: Partial<EventEvidence> | null } = {}): ActiveEvent =>
  ({
    id: 'evt-1',
    source: 'chat',
    service: 'svc',
    status: 'active',
    reason: '',
    turns: 0,
    created: '2026-10-29T10:00:00Z',
    ...over,
  }) as unknown as ActiveEvent;

const renderItem = (evt: ActiveEvent, onSelect = vi.fn()) =>
  render(<WorkspaceTaskItem evt={evt} isSelected={false} onSelect={onSelect} />);

describe('WorkspaceTaskItem', () => {
  let writeTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: writeTextMock,
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe('domain badge', () => {
  it('prefers brain_domain over the source-assessed domain', () => {
    renderItem(makeEvent({ evidence: { brain_domain: 'complex', domain: 'disorder' } }));
    expect(screen.getByText('complex')).toBeInTheDocument();
    expect(screen.queryByText('disorder')).not.toBeInTheDocument();
  });

  it.each([null, '', undefined])('falls back to evidence.domain when brain_domain is %j', (brain) => {
    renderItem(makeEvent({ evidence: { brain_domain: brain as unknown as string, domain: 'clear' } }));
    expect(screen.getByText('clear')).toBeInTheDocument();
  });

  it("falls back to 'casual' when the event has no evidence", () => {
    renderItem(makeEvent());
    expect(screen.getByText('casual')).toBeInTheDocument();
  });

  it.each(['chaotic', 'CHAOTIC'])('renders %s with the chaotic palette (case-insensitive)', (domain) => {
    renderItem(makeEvent({ evidence: { brain_domain: domain } }));
    const badge = screen.getByText(domain);
    expect(badge.className).toContain('font-mono');
    expect(badge.style.color).toBe(rgb(DOMAIN_COLORS.chaotic.text));
    expect(badge.style.color).not.toBe(rgb(DOMAIN_COLORS.casual.text));
  });

  it.each(['weird', 'constructor', 'toString', '__proto__'])(
    'renders unknown/prototype domain %s falling back to casual colors',
    (domain) => {
      renderItem(makeEvent({ evidence: { brain_domain: domain } }));
      const badge = screen.getByText(domain);
      expect(badge.style.color).toBe(rgb(DOMAIN_COLORS.casual.text));
      expect(badge.style.background).toBe(rgb(DOMAIN_COLORS.casual.bg));
    },
  );
});

describe('WorkspaceTaskItem summary', () => {
  it('prefers display_text over reason', () => {
    renderItem(makeEvent({ reason: 'the reason', evidence: { display_text: 'clean text' } }));
    expect(screen.getByText('clean text')).toBeInTheDocument();
    expect(screen.queryByText('the reason')).not.toBeInTheDocument();
  });

  it('falls back to reason when display_text is empty', () => {
    renderItem(makeEvent({ reason: 'the reason', evidence: { display_text: '' } }));
    expect(screen.getByText('the reason')).toBeInTheDocument();
  });

  it('falls back to reason when display_text is whitespace-only', () => {
    renderItem(makeEvent({ reason: 'the reason', evidence: { display_text: '   \n\t ' } }));
    expect(screen.getByText('the reason')).toBeInTheDocument();
  });

  it("falls back to 'Interactive session' when display_text and reason are blank", () => {
    renderItem(makeEvent({ reason: '  ', evidence: { display_text: ' ' } }));
    expect(screen.getByText('Interactive session')).toBeInTheDocument();
  });
});

describe('WorkspaceTaskItem operational visibility parity', () => {
  it('renders agent badge when current_agent is present', () => {
    renderItem(makeEvent({ current_agent: 'architect' }));
    expect(screen.getByText('architect')).toBeInTheDocument();
  });

  it('renders status dot and service name', () => {
    renderItem(makeEvent({ service: 'order-service' }));
    expect(screen.getByText('order-service')).toBeInTheDocument();
  });

  it.each(['constructor', '__proto__', 'unknown_status'])(
    'renders the status dot with the fallback (active) color for prototype/unknown status %s',
    (status) => {
      const { container } = renderItem(makeEvent({ status: status as ActiveEvent['status'] }));
      const dot = container.querySelector<HTMLElement>('span.rounded-full.w-2');
      expect(dot).not.toBeNull();
      expect(dot!.style.background).toBe(rgb(STATUS_COLORS.active.border));
    },
  );

  it('renders the status dot with the matching palette for a known status', () => {
    const { container } = renderItem(makeEvent({ status: 'resolved' as ActiveEvent['status'] }));
    const dot = container.querySelector<HTMLElement>('span.rounded-full.w-2');
    expect(dot!.style.background).toBe(rgb(STATUS_COLORS.resolved.border));
    expect(dot!.style.background).not.toBe(rgb(STATUS_COLORS.active.border));
  });

  it('renders the defer countdown bar when status is deferred', () => {
    renderItem(makeEvent({
      status: 'deferred',
      defer_until: Math.floor(Date.now() / 1000) + 120,
      defer_started_at: Math.floor(Date.now() / 1000) - 60,
    }));
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('Deferred')).toBeInTheDocument();
  });

  it.each(['active', 'waiting_approval', 'closed'])('does not render the defer bar for %s status', (status) => {
    renderItem(makeEvent({
      status: status as ActiveEvent['status'],
      defer_until: Math.floor(Date.now() / 1000) + 120,
      defer_started_at: Math.floor(Date.now() / 1000) - 60,
    }));
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('falls back to id.slice(4, 12) when service is empty', () => {
    renderItem(makeEvent({ id: 'evt-abcdef123456', service: '' }));
    expect(screen.getByText('abcdef12')).toBeInTheDocument();
  });

  it('ignores prototype keys as current_agent when picking the agent colour', () => {
    renderItem(makeEvent({ current_agent: 'constructor' }));
    expect(screen.getByText('constructor').style.color).toBe(rgb('#64748b'));
  });

  it('does not re-fire onSelect for auto-repeated keydown events', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent(), onSelect);
    const card = screen.getAllByRole('button')[0];
    fireEvent.keyDown(card, { key: 'Enter', repeat: true });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('supports Enter key press for accessibility on div role="button"', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent(), onSelect);
    const card = screen.getAllByRole('button')[0];
    fireEvent.keyDown(card, { key: 'Enter', code: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('evt-1');
  });

  it('supports Space key press for accessibility on div role="button"', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent(), onSelect);
    const card = screen.getAllByRole('button')[0];
    fireEvent.keyDown(card, { key: ' ', code: 'Space' });
    expect(onSelect).toHaveBeenCalledWith('evt-1');
  });

  it('renders CopyButton with accessible aria-label="Copy Event ID (evt-copy-test)"', () => {
    renderItem(makeEvent({ id: 'evt-copy-test' }));
    const copyBtn = screen.getByRole('button', { name: 'Copy Event ID (evt-copy-test)' });
    expect(copyBtn).toBeInTheDocument();
  });

  it('clicking CopyButton copies event ID without triggering card onSelect', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent({ id: 'evt-copy-test' }), onSelect);
    const copyBtn = screen.getByRole('button', { name: 'Copy Event ID (evt-copy-test)' });
    fireEvent.click(copyBtn);
    expect(writeTextMock).toHaveBeenCalledWith('evt-copy-test');
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('Enter on the nested CopyButton does not trigger the row onSelect (e.target !== e.currentTarget guard)', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent({ id: 'evt-copy-test' }), onSelect);
    const copyBtn = screen.getByRole('button', { name: 'Copy Event ID (evt-copy-test)' });
    fireEvent.keyDown(copyBtn, { key: 'Enter', code: 'Enter' });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('Space on the nested CopyButton does not trigger the row onSelect (e.target !== e.currentTarget guard)', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent({ id: 'evt-copy-test' }), onSelect);
    const copyBtn = screen.getByRole('button', { name: 'Copy Event ID (evt-copy-test)' });
    fireEvent.keyDown(copyBtn, { key: ' ', code: 'Space' });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('Enter/Space on the row itself still selects it', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent({ id: 'evt-copy-test' }), onSelect);
    const row = screen.getByTitle('evt-copy-test');
    fireEvent.keyDown(row, { key: 'Enter' });
    fireEvent.keyDown(row, { key: ' ' });
    expect(onSelect).toHaveBeenCalledTimes(2);
    expect(onSelect).toHaveBeenCalledWith('evt-copy-test');
  });

  it('reveals the copy affordance on hover/focus-within via group utilities and has no redundant focus-within utilities', () => {
    renderItem(makeEvent({ id: 'evt-copy-test' }));
    const copyBtn = screen.getByRole('button', { name: 'Copy Event ID (evt-copy-test)' });
    expect(copyBtn.className).toContain('group-hover:opacity-100');
    expect(copyBtn.className).toContain('group-focus-within:opacity-100');
    expect(copyBtn.className).not.toMatch(/(^|\s)focus-within:/);
  });

  describe('context menu', () => {
    it('fires onContextMenu when right-clicked on the task row with mouse event and event object', () => {
      const onContextMenu = vi.fn();
      const evt = makeEvent({ id: 'evt-ctx-test' });
      render(
        <WorkspaceTaskItem
          evt={evt}
          isSelected={false}
          onSelect={vi.fn()}
          onContextMenu={onContextMenu}
        />
      );

      const row = screen.getByTitle('evt-ctx-test');
      fireEvent.contextMenu(row, { clientX: 120, clientY: 240 });

      expect(onContextMenu).toHaveBeenCalledTimes(1);
      expect(onContextMenu).toHaveBeenCalledWith(expect.any(Object), evt);
    });
  });
});
});
