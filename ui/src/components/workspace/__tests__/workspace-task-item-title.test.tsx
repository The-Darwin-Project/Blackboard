// BlackBoard/ui/src/components/workspace/__tests__/workspace-task-item-title.test.tsx
// @ai-rules:
// 1. [Constraint]: Component unit tests for WorkspaceTaskItem title fallback hierarchy.
// 2. [Pattern]: RTL render with partial ActiveEvent fixture.
// 3. [Contract]: Priority order: evt.title || evt.service || evt.id.slice(4, 12).
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkspaceTaskItem from '../WorkspaceTaskItem';
import type { ActiveEvent } from '../../../api/types';

const makeEvent = (over: Partial<ActiveEvent> = {}): ActiveEvent =>
  ({
    id: 'evt-12345678abcdef',
    source: 'chat',
    service: 'auth-service',
    status: 'active',
    reason: 'test reason',
    turns: 0,
    created: '2026-10-29T10:00:00Z',
    ...over,
  }) as unknown as ActiveEvent;

describe('WorkspaceTaskItem Title Fallback Hierarchy (Step 10)', () => {
  it('renders evt.title when present', () => {
    render(<WorkspaceTaskItem evt={makeEvent({ title: 'Diagnose Redis Memory Leak' })} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText('Diagnose Redis Memory Leak')).toBeInTheDocument();
  });

  it('falls back to evt.service when title is absent', () => {
    render(<WorkspaceTaskItem evt={makeEvent({ title: null, service: 'auth-service' })} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText('auth-service')).toBeInTheDocument();
  });

  it('falls back to evt.id.slice(4, 12) when title and service are absent', () => {
    render(<WorkspaceTaskItem evt={makeEvent({ title: null, service: '' })} isSelected={false} onSelect={vi.fn()} />);
    // id is 'evt-12345678abcdef', slice(4, 12) is '12345678'
    expect(screen.getByText('12345678')).toBeInTheDocument();
  });
});
