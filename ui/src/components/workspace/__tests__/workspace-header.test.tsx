import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WorkspaceHeader from '../WorkspaceHeader';

const opsState: { registeredAgents: unknown[]; ephemeralAgents: unknown[]; selectedEventId: string | null } = {
  registeredAgents: [],
  ephemeralAgents: [],
  selectedEventId: 'evt-100',
};
const resetOpsState = () => {
  opsState.registeredAgents = [{ role: 'developer', status: 'idle', bound_event_id: 'evt-100' }];
  opsState.ephemeralAgents = [];
  opsState.selectedEventId = 'evt-100';
};
resetOpsState();

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: () => opsState,
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
  beforeEach(() => resetOpsState());

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

  describe('activeAgentCount', () => {
    const renderHeader = (id = 'evt-100') =>
      render(
        <MemoryRouter>
          <WorkspaceHeader
            selectedEventId={id}
            isSessionsOpen={true}
            isInspectorOpen={true}
            onToggleSessions={vi.fn()}
            onToggleInspector={vi.fn()}
          />
        </MemoryRouter>
      );

    it('dedups duplicate keyed agents across registered and ephemeral lists', () => {
      opsState.registeredAgents = [{ agent_id: 'dev-1', role: 'developer', bound_event_id: 'evt-100' }];
      opsState.ephemeralAgents = [{ agent_id: 'dev-1', role: 'developer', current_event_id: 'evt-100' }];
      renderHeader();
      expect(screen.getByText(/^1 agent$/)).toBeInTheDocument();
    });

    it('counts distinct agents separately', () => {
      opsState.registeredAgents = [
        { agent_id: 'dev-1', role: 'developer', bound_event_id: 'evt-100' },
        { agent_id: 'qe-1', role: 'qe', bound_event_id: 'evt-100' },
      ];
      renderHeader();
      expect(screen.getByText(/^2 agents$/)).toBeInTheDocument();
    });

    it('keeps keyless active agents instead of dropping them', () => {
      opsState.registeredAgents = [
        { bound_event_id: 'evt-100' },
        { bound_event_id: 'evt-100' },
        { agent_id: 'dev-1', bound_event_id: 'evt-100' },
      ];
      renderHeader();
      expect(screen.getByText(/^3 agents$/)).toBeInTheDocument();
    });

    it('counts a single keyless agent', () => {
      opsState.registeredAgents = [{ current_event_id: 'evt-100' }];
      renderHeader();
      expect(screen.getByText(/^1 agent$/)).toBeInTheDocument();
    });

    it('counts bound and unbound agents only when they match the selected event', () => {
      opsState.registeredAgents = [
        { agent_id: 'dev-1', bound_event_id: 'evt-100' },
        { agent_id: 'qe-1', bound_event_id: null },
        { agent_id: 'sre-1', bound_event_id: 'evt-other' },
      ];
      opsState.ephemeralAgents = [{ agent_id: 'eph-1', current_event_id: 'evt-100' }];
      renderHeader();
      expect(screen.getByText(/^2 agents$/)).toBeInTheDocument();
    });

    it('hides the pill when no agent is attached to the selected event', () => {
      opsState.registeredAgents = [{ agent_id: 'qe-1', bound_event_id: null }];
      renderHeader();
      expect(screen.queryByText(/agents?$/)).not.toBeInTheDocument();
    });
  });

  it('does not leak the "Copied" state when the selected event changes', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    const props = { isSessionsOpen: true, isInspectorOpen: true, onToggleSessions: vi.fn(), onToggleInspector: vi.fn() };
    const { rerender } = render(
      <MemoryRouter><WorkspaceHeader selectedEventId="evt-100" {...props} /></MemoryRouter>
    );
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Copy Event ID' }));
      await Promise.resolve();
    });
    expect(screen.getByRole('button', { name: 'Copied Event ID' })).toBeInTheDocument();

    rerender(<MemoryRouter><WorkspaceHeader selectedEventId="evt-200" {...props} /></MemoryRouter>);
    expect(screen.getByRole('button', { name: 'Copy Event ID' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copied Event ID' })).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
