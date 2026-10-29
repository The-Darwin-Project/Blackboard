import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkspaceSessionsHub from '../WorkspaceSessionsHub';
import * as queueHook from '../../../hooks/useQueue';
import * as OpsStateContext from '../../../contexts/OpsStateContext';
import * as AuthContext from '../../../contexts/AuthContext';

describe('WorkspaceSessionsHub (Left Sidebar)', () => {
  const mockEvents = [
    {
      id: 'evt-1',
      service: 'auth-service',
      status: 'active',
      source: 'alertmanager',
      created_by_email: 'developer@redhat.com',
      evidence: {
        domain: 'complicated',
        project: 'ProjectAlpha',
        display_text: 'Auth service latency alert',
      },
      reason: 'Latency high',
      turns: 2,
      created: '2026-10-29T10:00:00Z',
    },
    {
      id: 'evt-2',
      service: 'billing-service',
      status: 'waiting_approval',
      source: 'kargo_stage',
      created_by_email: 'bot@redhat.com',
      evidence: {
        domain: 'casual',
        project: 'ProjectBeta',
        display_text: 'Billing promotion approval',
      },
      reason: 'Approval needed',
      turns: 1,
      created: '2026-10-29T10:05:00Z',
    },
    {
      id: 'evt-3',
      service: 'payment-service',
      status: 'deferred',
      source: 'jira',
      created_by_email: 'developer@redhat.com',
      evidence: {
        domain: 'complex',
        project: 'ProjectAlpha',
        display_text: 'Payment retry deferred',
      },
      reason: 'Rate limit backoff',
      defer_until: Math.floor(Date.now() / 1000) + 300,
      defer_started_at: Math.floor(Date.now() / 1000) - 30,
      turns: 4,
      created: '2026-10-29T09:50:00Z',
    },
  ];

  const mockClosedEvents = [
    {
      id: 'evt-closed-1',
      service: 'cache-service',
      status: 'closed',
      source: 'chat',
      created_by_email: 'developer@redhat.com',
      evidence: {
        domain: 'clear',
        project: 'ProjectAlpha',
        display_text: 'Cache flushed successfully',
      },
      reason: 'Resolved',
      turns: 3,
      created: '2026-10-29T09:00:00Z',
    },
  ];

  const mockSelectEvent = vi.fn();
  const mockDeselectEvent = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue({
      data: mockEvents,
      isLoading: false,
      isFetching: false,
    } as never);

    vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue({
      data: mockClosedEvents,
      isLoading: false,
      isFetching: false,
    } as never);

    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: {
        profile: {
          email: 'developer@redhat.com',
          preferred_username: 'developer',
        },
      },
      isAuthenticated: true,
      isLoading: false,
    } as never);

    vi.spyOn(OpsStateContext, 'useOpsControl').mockReturnValue({
      selectedEventId: 'evt-1',
      selectEvent: mockSelectEvent,
      deselectEvent: mockDeselectEvent,
      registeredAgents: [],
      ephemeralAgents: [],
      kargoStages: [],
      kargoEventResult: null,
      contentTiles: [],
      hotspotTileId: null,
      setHotspot: vi.fn(),
      openContentTile: vi.fn(),
      closeContentTile: vi.fn(),
      autoHotspot: false,
      toggleAutoHotspot: vi.fn(),
      connected: true,
      send: vi.fn(),
    } as never);
  });

  it('renders active sessions with service name and Cynefin status/domain badges', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

    expect(screen.getByText(/auth-service/i)).toBeInTheDocument();
  });

  it('calls selectEvent when an active session card is clicked', () => {
    // Switch to global scope to see evt-2 (bot task)
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Global/i }));

    const sessionCard = screen.getByText(/billing-service/i);
    fireEvent.click(sessionCard);

    expect(mockSelectEvent).toHaveBeenCalledWith('evt-2');
  });

  it('provides a New Task trigger button', () => {
    const onNewTask = vi.fn();
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={onNewTask} />);

    const newTaskBtn = screen.getByRole('button', { name: /^New Task$/ });
    expect(newTaskBtn).toBeInTheDocument();

    fireEvent.click(newTaskBtn);
    expect(onNewTask).toHaveBeenCalled();
  });

  it('handles empty active events gracefully', () => {
    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    } as never);

    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    expect(screen.getByText(/No active tasks/i)).toBeInTheDocument();
  });

  it('shows the loading banner and suppresses empty-state text while either query is loading', () => {
    const q = (isLoading: boolean) => ({ data: [], isLoading, isFetching: isLoading }) as never;
    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(q(true));
    vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(q(false));
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    expect(screen.getByText(/Loading tasks/i)).toBeInTheDocument();
    expect(screen.queryByText(/No active tasks/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No deferred tasks/i)).not.toBeInTheDocument();
  });

  it('suppresses the closed empty-state while only the closed query is loading', () => {
    const q = (isLoading: boolean) => ({ data: [], isLoading, isFetching: isLoading }) as never;
    vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(q(false));
    vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(q(true));
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Closed & Failed/i }));
    expect(screen.getByText(/Loading tasks/i)).toBeInTheDocument();
    expect(screen.getByText(/No active tasks/i)).toBeInTheDocument();
    expect(screen.queryByText(/No closed tasks/i)).not.toBeInTheDocument();
  });

  it('filters by "My Tasks" vs "Global" scope correctly', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

    // In 'My Tasks' mode (default), user only sees their own tasks (evt-1 and evt-3)
    expect(screen.getByText(/auth-service/i)).toBeInTheDocument();
    expect(screen.queryByText(/billing-service/i)).not.toBeInTheDocument();

    // Toggle to Global scope
    fireEvent.click(screen.getByRole('button', { name: /Global/i }));
    expect(screen.getByText(/billing-service/i)).toBeInTheDocument();
  });

  it('filters tasks by project dropdown', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Global/i }));

    const projectSelect = screen.getByLabelText(/filter by project/i);
    expect(projectSelect).toBeInTheDocument();

    fireEvent.change(projectSelect, { target: { value: 'ProjectBeta' } });
    expect(screen.queryByText(/auth-service/i)).not.toBeInTheDocument();
    expect(screen.getByText(/billing-service/i)).toBeInTheDocument();
  });

  it('allows toggling Closed & Failed accordion folder', () => {
    render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

    // Default is collapsed, so cache-service is not visible yet
    expect(screen.queryByText(/cache-service/i)).not.toBeInTheDocument();

    const closedAccordion = screen.getByRole('button', { name: /Closed & Failed/i });
    fireEvent.click(closedAccordion);

    expect(screen.getByText(/cache-service/i)).toBeInTheDocument();
  });

  describe('stale-cache eviction guard', () => {
    const asQuery = (data: unknown[], extra: Record<string, unknown> = {}) =>
      ({ data, isLoading: false, isFetching: false, ...extra }) as never;

    it('does NOT evict a newly selected / deep-linked session that is absent from a stale active list', () => {
      const onNewTask = vi.fn();
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));

      render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);

      expect(onNewTask).not.toHaveBeenCalled();
    });

    it('keeps a new session selected when the refreshed list then includes it, and evicts it only after it closes', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(
        <WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />,
      );
      expect(onNewTask).not.toHaveBeenCalled();

      // Refetch lands: new session is now observed in active list
      const withNew = [...mockEvents, { ...mockEvents[0], id: 'evt-brand-new' }];
      spyActive.mockReturnValue(asQuery(withNew));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      // Session closes: it disappears from BOTH active and closed lists
      spyActive.mockReturnValue(asQuery(mockEvents));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-brand-new" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('evicts the selection when a previously seen active event closes and is absent from closed list', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      spyActive.mockReturnValue(asQuery([mockEvents[1]]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('evicts when all events become empty and absent from closed list', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spyActive.mockReturnValue(asQuery([]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('defers eviction while a refetch is in flight', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spyActive.mockReturnValue(asQuery([mockEvents[1]], { isFetching: true }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      spyActive.mockReturnValue(asQuery([mockEvents[1]], { isFetching: false }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });

    it('does not re-evict a closed event that the user deep-links to again after eviction', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spyActive.mockReturnValue(asQuery([mockEvents[1]]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);

      // Fresh list array, same stale selection: guard was pruned on eviction
      spyActive.mockReturnValue(asQuery([{ ...mockEvents[1] }]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });
  });
  describe('closed refetch eviction guard (active -> closed transition)', () => {
    const asQuery = (data: unknown[], extra: Record<string, unknown> = {}) =>
      ({ data, isLoading: false, isFetching: false, ...extra }) as never;

    it('does not evict while the closed list is refetching after the event left the active list', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const spyClosed = vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      // Active list settles without evt-1 while the closed list is still refetching (stale, lacks evt-1)
      spyActive.mockReturnValue(asQuery([mockEvents[1]]));
      spyClosed.mockReturnValue(asQuery([], { isFetching: true }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      // Closed refetch lands and now contains evt-1 -> still not evicted
      spyClosed.mockReturnValue(asQuery([{ ...mockEvents[0], status: 'closed' }]));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();
    });

    it('still evicts once both lists settle without the previously seen event', () => {
      const onNewTask = vi.fn();
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const spyClosed = vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);

      spyActive.mockReturnValue(asQuery([mockEvents[1]]));
      spyClosed.mockReturnValue(asQuery([], { isFetching: true }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).not.toHaveBeenCalled();

      spyClosed.mockReturnValue(asQuery([], { isFetching: false }));
      rerender(<WorkspaceSessionsHub isOpen={true} selectedEventId="evt-1" onNewTask={onNewTask} />);
      expect(onNewTask).toHaveBeenCalledTimes(1);
    });
  });

  describe('project filter', () => {
    const asQuery = (data: unknown[]) => ({ data, isLoading: false, isFetching: false }) as never;
    const ctxEvent = (id: string, service: string, evidence: Record<string, unknown>) => ({
      ...mockEvents[0],
      id,
      service,
      evidence: { domain: 'clear', display_text: 'context event', ...evidence },
    });

    it('resets to "all" when the selected project leaves availableProjects', () => {
      const spyActive = vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery(mockEvents));
      const { rerender } = render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: /Global/i }));
      const select = screen.getByLabelText(/filter by project/i) as HTMLSelectElement;
      fireEvent.change(select, { target: { value: 'ProjectBeta' } });
      expect(select.value).toBe('ProjectBeta');
      expect(screen.queryByText(/auth-service/i)).not.toBeInTheDocument();

      // ProjectBeta (evt-2) disappears from every list
      spyActive.mockReturnValue(asQuery([mockEvents[0], mockEvents[2]]));
      rerender(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

      expect((screen.getByLabelText(/filter by project/i) as HTMLSelectElement).value).toBe('all');
      expect(screen.getByText(/auth-service/i)).toBeInTheDocument();
      expect(screen.getByText(/payment-service/i)).toBeInTheDocument();
    });

    it('derives the project from gitlab_context / github_context / kargo_context', () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        ctxEvent('evt-gl', 'gl-service', { gitlab_context: { project: 'group/gitlab-proj' } }),
        ctxEvent('evt-gh', 'gh-service', { github_context: { repo: 'org/github-repo' } }),
        ctxEvent('evt-kg', 'kg-service', { kargo_context: { project: 'kargo-proj' } }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);

      const select = screen.getByLabelText(/filter by project/i) as HTMLSelectElement;
      const options = Array.from(select.options).map(o => o.value);
      expect(options).toEqual(['all', 'group/gitlab-proj', 'kargo-proj', 'org/github-repo']);

      fireEvent.change(select, { target: { value: 'org/github-repo' } });
      expect(screen.getByText(/gh-service/i)).toBeInTheDocument();
      expect(screen.queryByText(/gl-service/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/kg-service/i)).not.toBeInTheDocument();
    });

    it('prefers evidence.project over context payloads', () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        ctxEvent('evt-p', 'pref-service', { project: 'Primary', gitlab_context: { project: 'Secondary' } }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      const options = Array.from((screen.getByLabelText(/filter by project/i) as HTMLSelectElement).options).map(o => o.value);
      expect(options).toEqual(['all', 'Primary']);
    });

    it('matches events whose project has surrounding whitespace', () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        ctxEvent('evt-ws', 'ws-service', { project: '  Padded  ' }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      const select = screen.getByLabelText(/filter by project/i) as HTMLSelectElement;
      const padded = Array.from(select.options).filter(o => o.value !== 'all');
      expect(padded.map(o => o.value)).toEqual(['Padded']);
      expect(padded.map(o => o.textContent)).toEqual(['Padded']);
      fireEvent.change(select, { target: { value: 'Padded' } });
      expect(screen.getByText(/ws-service/i)).toBeInTheDocument();
    });

    it('hides the project selector when no event carries a project', () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([ctxEvent('evt-np', 'np-service', {})]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      expect(screen.queryByLabelText(/filter by project/i)).not.toBeInTheDocument();
    });
  });

  describe('"My Tasks" scope across sections', () => {
    const asQuery = (data: unknown[]) => ({ data, isLoading: false, isFetching: false }) as never;
    const other = (over: Record<string, unknown>) => ({ ...mockEvents[0], created_by_email: 'someone@else.com', ...over });

    const withOthers = () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        ...mockEvents,
        other({ id: 'evt-other-active', service: 'other-active' }),
        other({ id: 'evt-other-deferred', service: 'other-deferred', status: 'deferred' }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([
        ...mockClosedEvents,
        other({ id: 'evt-other-closed', service: 'other-closed', status: 'closed' }),
      ]));
    };

    it('shows only my tasks in active, deferred and closed sections, and everything under Global', () => {
      withOthers();
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: /Closed & Failed/i }));

      expect(screen.getByText('auth-service')).toBeInTheDocument();
      expect(screen.getByText('payment-service')).toBeInTheDocument();
      expect(screen.getByText('cache-service')).toBeInTheDocument();
      expect(screen.queryByText('other-active')).not.toBeInTheDocument();
      expect(screen.queryByText('other-deferred')).not.toBeInTheDocument();
      expect(screen.queryByText('other-closed')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /Global/i }));
      expect(screen.getByText('other-active')).toBeInTheDocument();
      expect(screen.getByText('other-deferred')).toBeInTheDocument();
      expect(screen.getByText('other-closed')).toBeInTheDocument();
    });

    it('matches on preferred_username when the profile has no email, via triggered_by', () => {
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
        user: { profile: { preferred_username: 'Developer' } },
        isAuthenticated: true,
        isLoading: false,
      } as never);
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        other({ id: 'evt-u', service: 'user-owned', created_by_email: null, evidence: { ...mockEvents[0].evidence, triggered_by: 'developer' } }),
        other({ id: 'evt-x', service: 'not-mine' }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      expect(screen.getByText('user-owned')).toBeInTheDocument();
      expect(screen.queryByText('not-mine')).not.toBeInTheDocument();
    });

    it('does not treat an ownerless event as mine when a profile identity is known', () => {
      vi.spyOn(queueHook, 'useActiveEvents').mockReturnValue(asQuery([
        other({ id: 'evt-n', service: 'ownerless', created_by_email: null }),
      ]));
      vi.spyOn(queueHook, 'useClosedEvents').mockReturnValue(asQuery([]));
      render(<WorkspaceSessionsHub isOpen={true} onNewTask={vi.fn()} />);
      expect(screen.queryByText('ownerless')).not.toBeInTheDocument();
    });
  });
});
