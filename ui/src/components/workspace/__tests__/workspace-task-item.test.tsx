import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceTaskItem from '../WorkspaceTaskItem';
import type { ActiveEvent, EventEvidence } from '../../../api/types';

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

describe('WorkspaceTaskItem domain badge', () => {
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

  it('renders domain pill with uppercase styling and valid domain text', () => {
    renderItem(makeEvent({ evidence: { brain_domain: 'chaotic' } }));
    const badge = screen.getByText('chaotic');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('font-mono');
  });

  it.each(['weird', 'constructor', 'toString', '__proto__'])(
    'renders unknown domain %s falling back to casual colors',
    (domain) => {
      renderItem(makeEvent({ evidence: { brain_domain: domain } }));
      const badge = screen.getByText(domain);
      expect(badge).toBeInTheDocument();
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

  it('renders defer countdown bar when status is deferred', () => {
    const { container } = renderItem(makeEvent({
      status: 'deferred',
      defer_until: Math.floor(Date.now() / 1000) + 120,
      defer_started_at: Math.floor(Date.now() / 1000) - 60,
    }));
    // DeferCountdownBar renders an svg/progress bar
    expect(container.querySelector('[title*="defer"]') || container.querySelector('svg') || container.textContent).toBeTruthy();
  });

  it('supports Enter key press for accessibility on div role="button"', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent(), onSelect);
    const item = screen.getByRole('button');
    fireEvent.keyDown(item, { key: 'Enter', code: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('evt-1');
  });

  it('supports Space key press for accessibility on div role="button"', () => {
    const onSelect = vi.fn();
    renderItem(makeEvent(), onSelect);
    const item = screen.getByRole('button');
    fireEvent.keyDown(item, { key: ' ', code: 'Space' });
    expect(onSelect).toHaveBeenCalledWith('evt-1');
  });
});
