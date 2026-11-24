// BlackBoard/ui/src/components/ops/__tests__/EventSidebar.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import EventSidebar from '../EventSidebar';
import { useOpsControl } from '../../../contexts/OpsStateContext';
import {
  useActiveEvents,
  useWaitingApprovalEvents,
  useHeadhunterPending,
  useHeadhunterStatus,
  useTriggerHeadhunterPoll,
  useResetHeadhunterBreaker,
  useHeadhunterItemAction,
  useAlignerPending,
  useJenkinsPending,
} from '../../../hooks/useQueue';
import { useSchedules } from '../../../hooks/useTimeKeeper';
import { useJiraMissions, useJiraActions } from '../../../hooks/useJira';
import { getClosedEvents } from '../../../api/client';
import type { AgentRegistryEntry, KargoStageStatus } from '../../../api/types';

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: vi.fn(),
}));

vi.mock('../../../hooks/useQueue', () => ({
  useActiveEvents: vi.fn(),
  useWaitingApprovalEvents: vi.fn(),
  useHeadhunterPending: vi.fn(),
  useHeadhunterStatus: vi.fn(),
  useTriggerHeadhunterPoll: vi.fn(),
  useResetHeadhunterBreaker: vi.fn(),
  useHeadhunterItemAction: vi.fn(),
  useAlignerPending: vi.fn(),
  useJenkinsPending: vi.fn(),
}));

vi.mock('../../../hooks/useTimeKeeper', () => ({
  useSchedules: vi.fn(),
}));

vi.mock('../../../hooks/useJira', () => ({
  useJiraMissions: vi.fn(),
  useJiraActions: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  getClosedEvents: vi.fn().mockResolvedValue([]),
}));

const SQUAD_A = 'evt-05e15dcc';
const SQUAD_B = 'evt-8f2a1b4c';

const hexToRgb = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

/** Build a registry entry with sensible defaults. */
const agent = (over: Partial<AgentRegistryEntry> & { agent_id: string }): AgentRegistryEntry => ({
  role: '',
  busy: false,
  current_event_id: null,
  current_task_id: null,
  connected_at: 100,
  cli: 'claude',
  model: 'sonnet',
  bound_event_id: null,
  ...over,
});

/** The <div> wrapping a TreeGroup (header button + children). */
const groupSection = (label: string) => {
  const header = screen.getByText(label).closest('button');
  if (!header) throw new Error(`group header not found: ${label}`);
  return { header, section: header.parentElement as HTMLElement };
};

/** Count badge text of a TreeGroup header (last span in the button). */
const groupBadge = (label: string) => {
  const { header } = groupSection(label);
  return header.querySelector('span:last-child') as HTMLElement;
};

/** Agent node labels in DOM order inside a container (TreeNodes carry role="button" explicitly). */
const agentLabels = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('[role="button"]')).map(n => n.querySelector('span.truncate')?.textContent);

const agentNode = (container: HTMLElement, label: string) => {
  const node = Array.from(container.querySelectorAll('[role="button"]'))
    .find(n => n.querySelector('span.truncate')?.textContent === label);
  if (!node) throw new Error(`agent node not found: ${label}`);
  return node as HTMLElement;
};

describe('EventSidebar - Dynamic Agents Tree with Squads', () => {
  let selectEventMock: ReturnType<typeof vi.fn>;
  let setHotspotMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    selectEventMock = vi.fn();
    setHotspotMock = vi.fn();
    vi.mocked(getClosedEvents).mockResolvedValue([]);

    vi.mocked(useActiveEvents).mockReturnValue({
      data: [
        {
          id: SQUAD_A,
          status: 'active',
          source: 'headhunter',
          service: 'release-app',
          created: new Date().toISOString(),
        } as never,
        {
          id: SQUAD_B,
          status: 'active',
          source: 'chat',
          service: 'kargo-config',
          created: new Date().toISOString(),
        } as never,
      ],
    } as never);

    vi.mocked(useWaitingApprovalEvents).mockReturnValue({ data: [] } as never);
    vi.mocked(useHeadhunterPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useHeadhunterStatus).mockReturnValue({ data: undefined } as never);
    vi.mocked(useTriggerHeadhunterPoll).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
    vi.mocked(useResetHeadhunterBreaker).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
    vi.mocked(useHeadhunterItemAction).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
    vi.mocked(useAlignerPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useJenkinsPending).mockReturnValue({ data: [] } as never);
    vi.mocked(useSchedules).mockReturnValue({ data: [] } as never);
    vi.mocked(useJiraMissions).mockReturnValue({ data: [] } as never);
    vi.mocked(useJiraActions).mockReturnValue({} as never);
  });

  afterEach(() => {
    localStorage.clear();
    cleanup();
  });

  const setupOpsControl = (
    registeredAgents: AgentRegistryEntry[],
    overrides: { selectedEventId?: string | null; closedEvents?: unknown[]; kargoStages?: KargoStageStatus[] } = {},
  ) => {
    vi.mocked(getClosedEvents).mockResolvedValue((overrides.closedEvents ?? []) as never);
    vi.mocked(useOpsControl).mockReturnValue({
      selectedEventId: overrides.selectedEventId ?? null,
      selectEvent: selectEventMock,
      setHotspot: setHotspotMock,
      connected: true,
      send: vi.fn(),
      openContentTile: vi.fn(),
      registeredAgents,
      kargoStages: overrides.kargoStages ?? [],
    } as never);
  };

  const renderSidebar = () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <EventSidebar />
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  describe('empty state, badges and collapse', () => {
    it('renders empty label and a 0 badge when no agents are registered (no ghost offline agents)', () => {
      setupOpsControl([]);
      renderSidebar();

      expect(screen.getByText('No active agents')).toBeInTheDocument();
      expect(groupBadge('Agents').textContent).toBe('0');
      expect(groupBadge('Agents').style.color).toBe(hexToRgb('#64748b'));
      for (const role of ['offline', 'architect', 'sysadmin', 'developer', 'qe']) {
        expect(screen.queryByText(role)).toBeNull();
      }
    });

    it('shows the total count and busy colour on the Agents badge when any agent is busy', () => {
      setupOpsControl([
        agent({ agent_id: 'a1', role: 'architect' }),
        agent({ agent_id: 'a2', role: 'developer', busy: true }),
      ]);
      renderSidebar();

      expect(groupBadge('Agents').textContent).toBe('2');
      expect(groupBadge('Agents').style.color).toBe(hexToRgb('#22c55e'));
      expect(screen.queryByText('No active agents')).toBeNull();
    });

    it('keeps the Agents badge idle-coloured when every agent is idle', () => {
      setupOpsControl([agent({ agent_id: 'a1', role: 'architect' })]);
      renderSidebar();

      expect(groupBadge('Agents').style.color).toBe(hexToRgb('#64748b'));
    });

    it('collapses the System section and force-collapses the Agents group when an event is selected', () => {
      setupOpsControl([agent({ agent_id: 'a1', role: 'architect' })], { selectedEventId: SQUAD_A });
      renderSidebar();

      // System section starts closed while an event is selected
      const systemToggle = screen.getAllByText('System')
        .map(n => n.closest('button'))
        .find(b => b?.getAttribute('aria-expanded') === 'false') as HTMLElement;
      expect(systemToggle).toBeTruthy();
      expect(screen.queryByText('Agents')).toBeNull();

      fireEvent.click(systemToggle);
      const agentsHeader = groupSection('Agents').header;
      expect(agentsHeader.getAttribute('aria-expanded')).toBe('false');
      expect(screen.queryByText('architect')).toBeNull();
      // Badge still reflects the registry while collapsed
      expect(groupBadge('Agents').textContent).toBe('1');

      // User can override the forced collapse
      fireEvent.click(agentsHeader);
      expect(agentsHeader.getAttribute('aria-expanded')).toBe('true');
      expect(screen.getByText('architect')).toBeInTheDocument();
    });

    it('expands the Agents group when no event is selected', () => {
      setupOpsControl([agent({ agent_id: 'a1', role: 'architect' })]);
      renderSidebar();

      expect(groupSection('Agents').header.getAttribute('aria-expanded')).toBe('true');
    });
  });

  describe('squads', () => {
    it('groups agents into a Squad and renders them in canonical order (architect, developer, sysadmin, qe)', () => {
      setupOpsControl([
        agent({ agent_id: 'a-qe', role: 'qe', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'a-dev', role: 'developer', busy: true, current_event_id: SQUAD_A, current_task_id: 'task-build-1', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'a-arch', role: 'architect', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'a-sys', role: 'sysadmin', bound_event_id: SQUAD_A }),
      ]);
      renderSidebar();

      const { section } = groupSection('Squad • release-app (05e15dcc)');
      expect(agentLabels(section)).toEqual(['architect', 'developer', 'sysadmin', 'qe']);
      expect(within(section).getByText('task-build-1')).toBeInTheDocument();
      expect(groupBadge('Squad • release-app (05e15dcc)').textContent).toBe('4');

      fireEvent.click(within(section).getByText('developer'));
      expect(selectEventMock).toHaveBeenCalledWith(SQUAD_A);
      expect(setHotspotMock).not.toHaveBeenCalled();
    });

    it('sorts unknown roles after known ones, alphabetically among themselves', () => {
      setupOpsControl([
        agent({ agent_id: 'z', role: 'zeta', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'q', role: 'qe', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'a', role: 'alpha', bound_event_id: SQUAD_A }),
      ]);
      renderSidebar();

      const { section } = groupSection('Squad • release-app (05e15dcc)');
      expect(agentLabels(section)).toEqual(['qe', 'alpha', 'zeta']);
    });

    it('isolates agents per squad and shows per-squad badge counts', () => {
      setupOpsControl([
        agent({ agent_id: 's1-arch', role: 'architect', bound_event_id: SQUAD_A }),
        agent({ agent_id: 's1-dev', role: 'developer', bound_event_id: SQUAD_A }),
        agent({ agent_id: 's1-qe', role: 'qe', bound_event_id: SQUAD_A }),
        agent({ agent_id: 's2-sys', role: 'sysadmin', busy: true, bound_event_id: SQUAD_B }),
        agent({ agent_id: 's2-dev', role: 'developer', bound_event_id: SQUAD_B }),
      ]);
      renderSidebar();

      const a = groupSection('Squad • release-app (05e15dcc)');
      const b = groupSection('Squad • kargo-config (8f2a1b4c)');
      expect(agentLabels(a.section)).toEqual(['architect', 'developer', 'qe']);
      expect(agentLabels(b.section)).toEqual(['developer', 'sysadmin']);
      expect(groupBadge('Squad • release-app (05e15dcc)').textContent).toBe('3');
      expect(groupBadge('Squad • kargo-config (8f2a1b4c)').textContent).toBe('2');
      // Only squad B has a busy agent
      expect(groupBadge('Squad • release-app (05e15dcc)').style.color).toBe(hexToRgb('#64748b'));
      expect(groupBadge('Squad • kargo-config (8f2a1b4c)').style.color).toBe(hexToRgb('#22c55e'));

      fireEvent.click(agentNode(b.section, 'sysadmin'));
      expect(selectEventMock).toHaveBeenCalledWith(SQUAD_B);
    });

    it('resolves the squad title from recently closed events when the event is no longer active', async () => {
      setupOpsControl(
        [agent({ agent_id: 'c1', role: 'architect', bound_event_id: 'evt-closed01x' })],
        { closedEvents: [{ id: 'evt-closed01x', status: 'closed', source: 'chat', service: 'closed-svc', created: new Date().toISOString() }] },
      );
      renderSidebar();

      expect(await screen.findByText('Squad • closed-svc (closed01)')).toBeInTheDocument();
      expect(screen.queryByText('Squad • closed01')).toBeNull();
    });

    it('falls back to "Squad • <shortId>" when no active or closed event matches (stale squad)', () => {
      setupOpsControl([agent({ agent_id: 'st1', role: 'architect', bound_event_id: 'evt-0000aaaa11' })]);
      renderSidebar();

      expect(screen.getByText('Squad • 0000aaaa')).toBeInTheDocument();
      // Stale squads are still rendered and still route to their event
      fireEvent.click(screen.getByText('architect'));
      expect(selectEventMock).toHaveBeenCalledWith('evt-0000aaaa11');
    });

    it('uses the first 8 characters when the bound id has no evt- prefix', () => {
      setupOpsControl([agent({ agent_id: 'x1', role: 'architect', bound_event_id: 'task-abcdef123456' })]);
      renderSidebar();

      expect(screen.getByText('Squad • task-abc')).toBeInTheDocument();
    });

    it('puts headhunter / timekeeper bound to an evt- id in a Squad, not in Sensors', () => {
      setupOpsControl([
        agent({ agent_id: 'hh', role: 'headhunter', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'tk', role: '', current_role: 'timekeeper', bound_event_id: SQUAD_A }),
      ]);
      renderSidebar();

      expect(screen.queryByText('Sensors & On-Call')).toBeNull();
      const { section } = groupSection('Squad • release-app (05e15dcc)');
      expect(agentLabels(section)).toEqual(['headhunter', 'timekeeper']);
      fireEvent.click(within(section).getByText('timekeeper'));
      expect(selectEventMock).toHaveBeenCalledWith(SQUAD_A);
    });
  });

  describe('sensors and on-call agents', () => {
    it('classifies sensors by display role (role OR current_role) when unbound, with exact membership', () => {
      setupOpsControl([
        // Real on-call registration shape: role '' + per-dispatch current_role
        agent({ agent_id: 'oc-hh', role: '', current_role: 'headhunter' }),
        agent({ agent_id: 'oc-tk', role: 'timekeeper' }),
        agent({ agent_id: 'oc-al', role: 'aligner' }),
        agent({ agent_id: 'oc-nw', role: 'sysadmin', current_role: 'nightwatcher' }),
        agent({ agent_id: 'plain', role: 'architect' }),
      ]);
      renderSidebar();

      const { section } = groupSection('Sensors & On-Call');
      expect(agentLabels(section)).toEqual(['aligner', 'headhunter', 'timekeeper', 'nightwatcher']);
      expect(groupBadge('Sensors & On-Call').textContent).toBe('4');
      // The non-sensor is NOT inside Sensors; with sensors present it lands under Standalone
      const standalone = groupSection('Standalone');
      expect(agentLabels(standalone.section)).toEqual(['architect']);
    });

    it('routes a nw-sweep- bound agent to setHotspot(boundId)', () => {
      setupOpsControl([
        agent({ agent_id: 'nw', role: 'sysadmin', current_role: 'nightwatcher', busy: true, bound_event_id: 'nw-sweep-gitops' }),
      ]);
      renderSidebar();

      const { section } = groupSection('Sensors & On-Call');
      expect(agentLabels(section)).toEqual(['nightwatcher']);
      fireEvent.click(within(section).getByText('nightwatcher'));
      expect(setHotspotMock).toHaveBeenCalledWith('nw-sweep-gitops');
      expect(selectEventMock).not.toHaveBeenCalled();
    });

    it('never selectEvent()s a nw- bound id that is not a sweep; focuses the role tile instead', () => {
      setupOpsControl([
        agent({ agent_id: 'nw2', role: 'sysadmin', current_role: 'nightwatcher', bound_event_id: 'nw-other-1' }),
      ]);
      renderSidebar();

      expect(agentLabels(groupSection('Sensors & On-Call').section)).toEqual(['nightwatcher']);
      fireEvent.click(screen.getByText('nightwatcher'));
      expect(selectEventMock).not.toHaveBeenCalled();
      expect(setHotspotMock).toHaveBeenCalledWith('nightwatcher');
    });

    it('routes an unbound sensor click to setHotspot(displayRole)', () => {
      setupOpsControl([agent({ agent_id: 'al', role: 'aligner' })]);
      renderSidebar();

      // SourceIcon titles also contain "aligner", so scope to the Sensors group
      fireEvent.click(within(groupSection('Sensors & On-Call').section).getByText('aligner'));
      expect(setHotspotMock).toHaveBeenCalledTimes(1);
      expect(setHotspotMock).toHaveBeenCalledWith('aligner');
      expect(selectEventMock).not.toHaveBeenCalled();
    });
  });

  describe('standalone agents', () => {
    it('renders standalone agents flat (no "Standalone" sub-header) when they are the only group', () => {
      setupOpsControl([agent({ agent_id: 'local-arch', role: 'architect' })]);
      renderSidebar();

      expect(screen.getByText('architect')).toBeInTheDocument();
      expect(screen.getByText('idle')).toBeInTheDocument();
      expect(screen.queryByText('Standalone')).toBeNull();
      expect(screen.queryByText('Sensors & On-Call')).toBeNull();
    });

    it('nests standalone agents under a "Standalone" heading when squads and sensors also exist', () => {
      setupOpsControl([
        agent({ agent_id: 'sq', role: 'developer', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'se', role: 'aligner' }),
        agent({ agent_id: 'st', role: 'architect' }),
      ]);
      renderSidebar();

      expect(agentLabels(groupSection('Squad • release-app (05e15dcc)').section)).toEqual(['developer']);
      expect(agentLabels(groupSection('Sensors & On-Call').section)).toEqual(['aligner']);
      expect(agentLabels(groupSection('Standalone').section)).toEqual(['architect']);
      expect(groupBadge('Standalone').textContent).toBe('1');
    });

    it('nests standalone agents under "Standalone" when only a squad exists alongside them', () => {
      setupOpsControl([
        agent({ agent_id: 'sq', role: 'developer', bound_event_id: SQUAD_A }),
        agent({ agent_id: 'st', role: 'qe' }),
      ]);
      renderSidebar();

      expect(agentLabels(groupSection('Standalone').section)).toEqual(['qe']);
    });
  });

  describe('node rendering fallbacks', () => {
    it('busy sublabel prefers current_task_id over current_event_id (truncated to 12 chars)', () => {
      setupOpsControl([
        agent({ agent_id: 'b', role: 'developer', busy: true, current_task_id: 'task-0123456789abcdef', current_event_id: 'evt-should-lose' }),
      ]);
      renderSidebar();

      expect(screen.getByText('task-0123456')).toBeInTheDocument();
      expect(screen.queryByText('evt-should-l')).toBeNull();
    });

    it('busy sublabel falls back to current_event_id when there is no task id', () => {
      setupOpsControl([
        agent({ agent_id: 'b', role: 'developer', busy: true, current_event_id: 'evt-05e15dcc-long-tail' }),
      ]);
      renderSidebar();

      expect(screen.getByText('evt-05e15dcc')).toBeInTheDocument();
    });

    it("busy sublabel falls back to 'working' with neither task nor event id", () => {
      setupOpsControl([agent({ agent_id: 'b', role: 'developer', busy: true })]);
      renderSidebar();

      expect(screen.getByText('working')).toBeInTheDocument();
      expect(screen.queryByText('idle')).toBeNull();
    });

    it('idle agents show "idle" even when stale task/event ids are present', () => {
      setupOpsControl([agent({ agent_id: 'i', role: 'developer', busy: false, current_task_id: 'task-stale', current_event_id: 'evt-stale' })]);
      renderSidebar();

      expect(screen.getByText('idle')).toBeInTheDocument();
      expect(screen.queryByText('task-stale')).toBeNull();
    });

    it('current_role overrides role for label, sort and click routing', () => {
      setupOpsControl([
        agent({ agent_id: 'o', role: 'sysadmin', current_role: 'qe' }),
      ]);
      renderSidebar();

      expect(screen.getByText('qe')).toBeInTheDocument();
      expect(screen.queryByText('sysadmin')).toBeNull();
      fireEvent.click(screen.getByText('qe'));
      expect(setHotspotMock).toHaveBeenCalledWith('qe');
    });

    it("renders unknown/empty role as 'oncall' with the fallback colour and does not focus a non-existent tile", () => {
      setupOpsControl([agent({ agent_id: 'anon', role: '' })]);
      renderSidebar();

      const label = screen.getByText('oncall');
      expect(label.style.color).toBe(hexToRgb('#8b5cf6'));
      fireEvent.click(label);
      expect(setHotspotMock).not.toHaveBeenCalled();
      expect(selectEventMock).not.toHaveBeenCalled();
    });

    it('uses the known role colour for known roles', () => {
      setupOpsControl([agent({ agent_id: 'k', role: 'architect' })]);
      renderSidebar();

      expect(screen.getByText('architect').style.color).toBe(hexToRgb('#3b82f6'));
    });
  });

  describe('context menu', () => {
    it('opens the agent context menu on right click and "Focus in Grid" focuses the role tile', () => {
      setupOpsControl([agent({ agent_id: 'ctx-dev', role: 'developer', bound_event_id: SQUAD_A })]);
      renderSidebar();

      fireEvent.contextMenu(screen.getByText('developer'));
      expect(screen.getByText('Agent Info')).toBeInTheDocument();
      expect(screen.getByText('Copy Agent ID')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Focus in Grid'));
      expect(setHotspotMock).toHaveBeenCalledWith('developer');
      expect(selectEventMock).not.toHaveBeenCalled();
    });

    it("'Focus in Grid' is a no-op for an agent without a resolvable role", () => {
      setupOpsControl([agent({ agent_id: 'anon', role: '' })]);
      renderSidebar();

      fireEvent.contextMenu(screen.getByText('oncall'));
      fireEvent.click(screen.getByText('Focus in Grid'));
      expect(setHotspotMock).not.toHaveBeenCalled();
    });
  });

  describe('resize handle gutter', () => {
    it('reserves a pr-1.5 gutter on the panel root so the w-1.5 resize handle never overlaps the inner scrollbar', () => {
      setupOpsControl([]);
      const { container } = renderSidebar();

      const root = container.firstElementChild as HTMLElement;
      const handle = root.querySelector('.cursor-col-resize') as HTMLElement | null;

      expect(root.classList.contains('pr-1.5')).toBe(true);
      expect(handle).not.toBeNull();
      expect(handle!.classList.contains('w-1.5')).toBe(true);
      expect(handle!.classList.contains('right-0')).toBe(true);
    });
  });

  describe('Headhunter Queue VCS parity (T-16)', () => {
    const glTodo = {
      todo_id: 101,
      platform: 'gitlab' as const,
      action: 'queued',
      priority: 1,
      mr_iid: 12,
      mr_title: 'Fix TLS',
      project_path: 'group/repo',
      author: 'alice',
      pipeline_status: 'success',
      check_status: 'passed',
      queue_position: 1,
      created_at: '2026-11-22T10:00:00Z',
      target_url: 'https://gitlab.com/group/repo/-/merge_requests/12',
    };

    const ghTodo = {
      platform: 'github' as const,
      action: 'queued',
      priority: 1,
      pr_number: 45,
      pr_title: 'Add webhook',
      project_path: 'org/app',
      author: 'bob',
      pipeline_status: 'failed',
      check_status: 'failed',
      queue_position: 2,
      created_at: '2026-11-22T10:01:00Z',
      target_url: 'https://github.com/org/app/pull/45',
    };

    it('renders distinct GitLab and GitHub SourceIcons on Headhunter items', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo, ghTodo] } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      expect(within(section).getByTitle('gitlab')).toBeInTheDocument();
      expect(within(section).getByTitle('github')).toBeInTheDocument();
    });

    it('renders Q{queue_position} badge and check/pipeline status dots for passed, failed, running, and pending', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({
        data: [
          { ...glTodo, todo_id: 1, mr_iid: 1, queue_position: 1, check_status: 'passed', pipeline_status: 'success' },
          { ...ghTodo, pr_number: 2, queue_position: 2, check_status: 'failed', pipeline_status: 'failed' },
          { ...ghTodo, pr_number: 3, queue_position: 3, check_status: 'running', pipeline_status: 'running' },
          { ...glTodo, todo_id: 4, mr_iid: 4, queue_position: 4, check_status: 'pending', pipeline_status: 'pending' },
        ],
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      expect(within(section).getByText('Q1')).toBeInTheDocument();
      expect(within(section).getByText('Q2')).toBeInTheDocument();
      expect(within(section).getByText('Q3')).toBeInTheDocument();
      expect(within(section).getByText('Q4')).toBeInTheDocument();

      expect(within(section).getByTitle(/passed/i)).toBeInTheDocument();
      expect(within(section).getByTitle(/failed/i)).toBeInTheDocument();
      expect(within(section).getByTitle(/running/i)).toBeInTheDocument();
      expect(within(section).getByTitle(/pending/i)).toBeInTheDocument();
    });

    it('filters displayed Headhunter items via All | GitLab | GitHub platform filter toggles', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo, ghTodo] } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      const allBtn = within(section).getByRole('button', { name: /^All$/i });
      const glBtn = within(section).getByRole('button', { name: /^GitLab$/i });
      const ghBtn = within(section).getByRole('button', { name: /^GitHub$/i });

      expect(within(section).getByText('!12 Fix TLS')).toBeInTheDocument();
      expect(within(section).getByText('#45 Add webhook')).toBeInTheDocument();

      fireEvent.click(glBtn);
      expect(within(section).getByText('!12 Fix TLS')).toBeInTheDocument();
      expect(within(section).queryByText('#45 Add webhook')).toBeNull();

      fireEvent.click(ghBtn);
      expect(within(section).queryByText('!12 Fix TLS')).toBeNull();
      expect(within(section).getByText('#45 Add webhook')).toBeInTheDocument();

      fireEvent.click(allBtn);
      expect(within(section).getByText('!12 Fix TLS')).toBeInTheDocument();
      expect(within(section).getByText('#45 Add webhook')).toBeInTheDocument();
    });

    it('renders breaker banner when GitLab breaker is open with Reset calling resetBreaker("gitlab") and Poll Now calling triggerPoll()', () => {
      const resetMutate = vi.fn();
      const pollMutate = vi.fn();
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo] } as never);
      vi.mocked(useResetHeadhunterBreaker).mockReturnValue({ mutate: resetMutate, isPending: false } as never);
      vi.mocked(useTriggerHeadhunterPoll).mockReturnValue({ mutate: pollMutate, isPending: false } as never);
      vi.mocked(useHeadhunterStatus).mockReturnValue({
        data: {
          platforms: {
            gitlab: {
              enabled: true,
              pending_count: 1,
              queued_count: 1,
              last_poll_at: 1700000000,
              partial_error: null,
              breaker: { state: 'open', consecutive_failures: 3, next_retry_at: 1700000300, last_error: 'GitLab 502' },
            },
            github: {
              enabled: true,
              pending_count: 0,
              queued_count: 0,
              last_poll_at: 1700000000,
              partial_error: null,
              breaker: { state: 'closed', consecutive_failures: 0, next_retry_at: null, last_error: null },
            },
          },
        },
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      expect(within(section).getByText(/open/i)).toBeInTheDocument();

      fireEvent.click(within(section).getByRole('button', { name: /Reset/i }));
      expect(resetMutate).toHaveBeenCalledWith('gitlab');

      fireEvent.click(within(section).getByRole('button', { name: /Poll Now/i }));
      expect(pollMutate).toHaveBeenCalledTimes(1);
    });

    it('renders breaker banner when GitHub breaker is half_open and Reset calls resetBreaker("github")', () => {
      const resetMutate = vi.fn();
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [ghTodo] } as never);
      vi.mocked(useResetHeadhunterBreaker).mockReturnValue({ mutate: resetMutate, isPending: false } as never);
      vi.mocked(useHeadhunterStatus).mockReturnValue({
        data: {
          platforms: {
            gitlab: {
              enabled: true,
              pending_count: 0,
              queued_count: 0,
              last_poll_at: 1700000000,
              partial_error: null,
              breaker: { state: 'closed', consecutive_failures: 0, next_retry_at: null, last_error: null },
            },
            github: {
              enabled: true,
              pending_count: 1,
              queued_count: 1,
              last_poll_at: 1700000000,
              partial_error: null,
              breaker: { state: 'half_open', consecutive_failures: 3, next_retry_at: null, last_error: 'GitHub 503' },
            },
          },
        },
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      expect(within(section).getByText(/half[_ ]open/i)).toBeInTheDocument();

      fireEvent.click(within(section).getByRole('button', { name: /Reset/i }));
      expect(resetMutate).toHaveBeenCalledWith('github');
    });

    it('renders "No matching todos" when platform filter yields 0 items', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo] } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      fireEvent.click(within(section).getByRole('button', { name: /^GitHub$/i }));
      expect(within(section).getByText('No matching todos')).toBeInTheDocument();
      expect(within(section).queryByText('No pending todos')).toBeNull();
    });

    it('renders failed mutation error alert banner and dismisses it cleanly', () => {
      const resetFn = vi.fn();
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo] } as never);
      vi.mocked(useResetHeadhunterBreaker).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        error: new Error('Breaker reset failed'),
        reset: resetFn,
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      const alert = within(section).getByRole('alert');
      expect(alert.textContent).toContain('Breaker reset failed');

      fireEvent.click(within(section).getByRole('button', { name: 'Dismiss error' }));
      expect(within(section).queryByRole('alert')).toBeNull();
      expect(resetFn).toHaveBeenCalledTimes(1);
    });

    it('renders debounced notice when mutation returns debounced: true', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo] } as never);
      vi.mocked(useTriggerHeadhunterPoll).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        data: { triggered: false, debounced: true },
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      const status = within(section).getByRole('status');
      expect(status.textContent).toContain('Poll request debounced');
    });

    it('disables Promote/Requeue/Dismiss menu actions while hhItemAction.isPending is true', () => {
      const itemMutate = vi.fn();
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo] } as never);
      vi.mocked(useHeadhunterItemAction).mockReturnValue({
        mutate: itemMutate,
        isPending: true,
      } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      fireEvent.contextMenu(within(section).getByText('!12 Fix TLS'));

      for (const label of ['Promote', 'Requeue', 'Dismiss']) {
        const item = screen.getByRole('menuitem', { name: label }) as HTMLButtonElement;
        expect(item.disabled).toBe(true);
        fireEvent.click(item);
      }
      expect(itemMutate).not.toHaveBeenCalled();
    });

    it('renders red sublabel for failed GitHub check_status', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [ghTodo] } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      const sublabel = within(section).getByText('queued');
      expect(sublabel.style.color).toBe(hexToRgb('#ef4444'));
    });

    it('closes open Headhunter context menu when platform filter changes', () => {
      setupOpsControl([]);
      vi.mocked(useHeadhunterPending).mockReturnValue({ data: [glTodo, ghTodo] } as never);
      renderSidebar();

      const { section } = groupSection('Headhunter Queue');
      fireEvent.contextMenu(within(section).getByText('!12 Fix TLS'));
      expect(screen.getByRole('menu')).toBeInTheDocument();

      fireEvent.click(within(section).getByRole('button', { name: /^GitHub$/i }));
      expect(screen.queryByRole('menu')).toBeNull();
    });
  });

  describe('Kargo Stages verification & promotion sublabels (T-18)', () => {
    it('renders "verify: <phase>" sublabel for verification failures', () => {
      setupOpsControl([], {
        kargoStages: [
          {
            project: 'v4-22',
            stage: 'verify-release-chart',
            promotion: 'verify-release-chart.01m83xf2.dae4bb2',
            freight: 'dae4bb27ec6bad98e8f2fbee9ed5f6a39d7b1091',
            phase: 'Failed',
            message: 'Metric "check-chart-exists" assessed Failed',
            failed_step: '',
            service: 'verify-release-chart@v4-22',
            mr_url: '',
            failure_type: 'verification',
            verification_id: '1605daa6-92cb-4050-addd-89465a90f331',
            analysis_run: 'verify-release-chart.01m83xf2.3aa0ebb',
          },
        ],
      });
      renderSidebar();

      const { section } = groupSection('Kargo Stages');
      expect(within(section).getByText('verify-release-chart')).toBeInTheDocument();
      expect(within(section).getByText('verify: Failed')).toBeInTheDocument();
    });

    it('preserves failed_step || phase sublabel for promotion failures (explicit or omitted failure_type)', () => {
      setupOpsControl([], {
        kargoStages: [
          {
            project: 'v4-22',
            stage: 'promote-stage',
            promotion: 'promote-stage.01abc',
            phase: 'Errored',
            message: 'step timed out',
            failed_step: 'wait-for-merge',
            service: 'promote-stage@v4-22',
            mr_url: 'https://gitlab.com/org/repo/-/merge_requests/1',
            failure_type: 'promotion',
          },
          {
            project: 'v4-22',
            stage: 'legacy-stage',
            promotion: 'legacy-stage.02def',
            phase: 'Errored',
            message: 'generic failure',
            failed_step: '',
            service: 'legacy-stage@v4-22',
            mr_url: '',
          },
        ],
      });
      renderSidebar();

      const { section } = groupSection('Kargo Stages');
      expect(within(section).getByText('promote-stage')).toBeInTheDocument();
      expect(within(section).getByText('wait-for-merge')).toBeInTheDocument();
      expect(within(section).getByText('legacy-stage')).toBeInTheDocument();
      expect(within(section).getByText('Errored')).toBeInTheDocument();
    });
  });
});
