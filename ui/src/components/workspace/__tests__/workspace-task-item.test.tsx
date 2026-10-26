import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
    created: '',
    ...over,
  }) as unknown as ActiveEvent;

const renderItem = (evt: ActiveEvent) =>
  render(<WorkspaceTaskItem evt={evt} isSelected={false} onSelect={vi.fn()} />);

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

  it('applies the domain colour class', () => {
    renderItem(makeEvent({ evidence: { brain_domain: 'chaotic' } }));
    expect(screen.getByText('chaotic').className).toContain('rose');
  });

  it.each(['weird', 'constructor', 'toString', '__proto__'])(
    'renders unknown domain %s with the casual colour',
    (domain) => {
      renderItem(makeEvent({ evidence: { brain_domain: domain } }));
      expect(screen.getByText(domain).className).toContain('indigo');
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
