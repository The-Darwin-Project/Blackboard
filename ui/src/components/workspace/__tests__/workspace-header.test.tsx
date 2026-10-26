import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import WorkspaceHeader from '../WorkspaceHeader';

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: () => ({
    registeredAgents: [{ role: 'developer', status: 'idle' }],
    ephemeralAgents: [],
    selectedEventId: 'evt-100',
  }),
}));

vi.mock('../../../hooks/useQueue', () => ({
  useEventDocument: () => ({
    data: {
      id: 'evt-100',
      service: 'payment-service',
      status: 'active',
    },
  }),
}));

describe('WorkspaceHeader (T-10)', () => {
  it('renders session breadcrumb and swarm pill', () => {
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

    expect(screen.getByText(/Darwin/i)).toBeInTheDocument();
    expect(screen.getByText(/payment-service|evt-100/i)).toBeInTheDocument();
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

    // Look for link or button pointing back to Ops Center
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
    // At least session and inspector toggle buttons exist
    expect(toggleButtons.length).toBeGreaterThanOrEqual(2);
  });
});
