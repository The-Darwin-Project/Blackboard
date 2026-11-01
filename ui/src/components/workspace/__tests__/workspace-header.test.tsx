import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WorkspaceHeader from '../WorkspaceHeader';

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: () => ({
    registeredAgents: [{ role: 'developer', status: 'idle', bound_event_id: 'evt-100' }],
    ephemeralAgents: [],
    selectedEventId: 'evt-100',
  }),
}));

vi.mock('../../../hooks/useQueue', () => ({
  useEventDocument: (id: string) => ({
    data: id === 'evt-100' ? {
      id: 'evt-100',
      service: 'payment-service',
      status: 'active',
    } : null,
  }),
}));

describe('WorkspaceHeader (T-7, T-8, T-10)', () => {
  it('renders session breadcrumb and swarm pill when event is selected', () => {
    render(
      <MemoryRouter>
        <WorkspaceHeader
          selectedEventId="evt-100"
          isSessionsOpen={true}
          isInspectorOpen={true}
          onToggleSessions={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByText(/Darwin/i)).toBeInTheDocument();
    expect(screen.getByText(/payment-service|evt-100/i)).toBeInTheDocument();
    expect(screen.getByText(/1 agent/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Event ID' })).toBeInTheDocument();
  });

  it('T-7: hides swarm pill when selectedEventId is null (New Task)', () => {
    render(
      <MemoryRouter>
        <WorkspaceHeader
          selectedEventId={null}
          isSessionsOpen={true}
          isInspectorOpen={true}
          onToggleSessions={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByText(/Darwin/i)).toBeInTheDocument();
    expect(screen.getByText(/New Task/i)).toBeInTheDocument();
    expect(screen.queryByText(/agent/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy Event ID' })).not.toBeInTheDocument();
  });

  it('T-10: contains perspective switcher link to Operations Center (/)', () => {
    render(
      <MemoryRouter>
        <WorkspaceHeader
          isSessionsOpen={true}
          isInspectorOpen={true}
          onToggleSessions={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      </MemoryRouter>
    );

    const opsLink = screen.getByRole('link', { name: /ops center|operations/i }) || screen.getByText(/ops center|operations/i);
    expect(opsLink).toBeInTheDocument();
  });

  it('provides toggle buttons for left Sessions panel and right Inspector panel', () => {
    const onToggleSessions = vi.fn();
    const onToggleInspector = vi.fn();

    render(
      <MemoryRouter>
        <WorkspaceHeader
          isSessionsOpen={true}
          isInspectorOpen={true}
          onToggleSessions={onToggleSessions}
          onToggleInspector={onToggleInspector}
        />
      </MemoryRouter>
    );

    const toggleButtons = screen.getAllByRole('button');
    expect(toggleButtons.length).toBeGreaterThanOrEqual(2);
  });
});
