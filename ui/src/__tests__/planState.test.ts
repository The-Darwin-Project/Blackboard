// BlackBoard/ui/src/__tests__/planState.test.ts
// @ai-rules:
// 1. [Pattern]: Unit tests for utils/planState.ts (canonicalRole normalization, derivePlanState replan slicing, status mapping).
import { describe, it, expect } from 'vitest';
import { canonicalRole, derivePlanState, isOrchestratorPlan, TERMINAL_STATUSES } from '../utils/planState';
import type { ConversationTurn } from '../api/types';

const plan = (
  steps: Array<{ id: string; agent?: string; summary?: string }>,
  turn = 1,
  actor = 'architect',
  source = 'architect',
): ConversationTurn =>
  ({ turn, actor, action: 'plan', timestamp: 1, taskForAgent: { steps, source } }) as unknown as ConversationTurn;

const step = (stepId: string, status: string | undefined, turn: number, actor = 'developer'): ConversationTurn =>
  ({ turn, actor, action: 'plan_step', timestamp: 100 + turn, taskForAgent: { step_id: stepId, status } }) as unknown as ConversationTurn;

const execute = (actor: string, turn: number, result = 'done'): ConversationTurn =>
  ({ turn, actor, action: 'execute', timestamp: 100 + turn, result }) as unknown as ConversationTurn;

describe('canonicalRole', () => {
  it.each([
    ['developer', 'developer'],
    ['Developer', 'developer'],
    ['  QE  ', 'qe'],
    ['code-reviewer', 'code_reviewer'],
    ['Code Reviewer', 'code_reviewer'],
    ['code_reviewer', 'code_reviewer'],
    ['a-b c', 'a_b_c'],
    ['', ''],
    [undefined, ''],
  ])('canonicalRole(%j) === %j', (input, expected) => {
    expect(canonicalRole(input as string | undefined)).toBe(expected);
  });
});

describe('isOrchestratorPlan', () => {
  it('identifies orchestrator roles (brain, architect, headhunter, aligner)', () => {
    expect(isOrchestratorPlan(plan([], 1, 'brain', 'brain'))).toBe(true);
    expect(isOrchestratorPlan(plan([], 1, 'architect', 'architect'))).toBe(true);
    expect(isOrchestratorPlan(plan([], 1, 'headhunter', 'headhunter'))).toBe(true);
    expect(isOrchestratorPlan(plan([], 1, 'aligner', 'aligner'))).toBe(true);
    expect(isOrchestratorPlan(plan([], 1, 'developer', 'developer'))).toBe(false);
  });
});

describe('derivePlanState', () => {
  it('reports no plan for an empty conversation or a plan turn without steps', () => {
    expect(derivePlanState([]).hasPlan).toBe(false);
    const noSteps = { turn: 1, actor: 'architect', action: 'plan', timestamp: 1, taskForAgent: {} } as unknown as ConversationTurn;
    expect(derivePlanState([noSteps])).toEqual({ hasPlan: false, planTurn: null, steps: [] });
  });

  it('defaults status to pending and applies the latest plan_step status per step', () => {
    const state = derivePlanState([
      plan([{ id: '1', agent: 'developer', summary: 'a' }, { id: '2', agent: 'qe', summary: 'b' }]),
      step('1', 'in_progress', 2),
      step('1', 'green_verified', 3),
    ]);
    expect(state.steps.map((s) => [s.id, s.status])).toEqual([['1', 'green_verified'], ['2', 'pending']]);
  });

  it('treats a plan_step without a status as completed', () => {
    const state = derivePlanState([plan([{ id: '1' }]), step('1', undefined, 2)]);
    expect(state.steps[0].status).toBe('completed');
  });

  it('ignores plan_step turns that arrived before the latest plan turn, even for a reused step id', () => {
    const state = derivePlanState([
      plan([{ id: '1', agent: 'developer', summary: 'old' }]),
      step('1', 'completed', 2),
      plan([{ id: '1', agent: 'developer', summary: 'new' }], 3),
    ]);
    expect(state.steps).toHaveLength(1);
    expect(state.steps[0]).toMatchObject({ id: '1', summary: 'new', status: 'pending' });
    expect(state.steps[0].timestamp).toBeUndefined();
  });

  it('ignores plan_step turns for unknown step ids', () => {
    const state = derivePlanState([plan([{ id: '1' }]), step('9', 'completed', 2)]);
    expect(state.steps[0].status).toBe('pending');
  });

  it('prioritizes orchestrator plan over worker agent plan proposal', () => {
    const orchPlan = plan(
      [
        { id: '1', agent: 'code_reviewer', summary: 'review' },
        { id: '2', agent: 'developer', summary: 'fix' },
        { id: '3', agent: 'qe', summary: 'verify' },
      ],
      10,
      'brain',
      'brain',
    );
    const agentProposal = plan(
      [{ id: '3', agent: '', summary: 'Remediation pushed' }],
      36,
      'developer',
      'developer',
    );

    const state = derivePlanState([orchPlan, agentProposal]);
    expect(state.hasPlan).toBe(true);
    expect(state.planTurn?.turn).toBe(10);
    expect(state.steps).toHaveLength(3);
    expect(state.steps.map((s) => s.id)).toEqual(['1', '2', '3']);
  });

  it('falls back to agent-sourced plan when no orchestrator plan exists', () => {
    const agentProposal = plan(
      [{ id: '1', agent: 'developer', summary: 'Investigate issue' }],
      5,
      'developer',
      'developer',
    );
    const state = derivePlanState([agentProposal]);
    expect(state.hasPlan).toBe(true);
    expect(state.planTurn?.turn).toBe(5);
    expect(state.steps).toHaveLength(1);
    expect(state.steps[0].summary).toBe('Investigate issue');
    // The fallback plan turn must not self-complete its own step.
    expect(state.steps[0].status).toBe('pending');
  });

  it('completes the fallback plan step only on a subsequent worker execute turn', () => {
    const fallback = plan([{ id: '1', agent: 'developer', summary: 'Investigate' }], 5, 'developer', 'developer');
    expect(derivePlanState([fallback]).steps[0].status).toBe('pending');
    const state = derivePlanState([fallback, execute('developer', 6)]);
    expect(state.steps[0].status).toBe('completed');
  });

  it('rejects cross-agent step hijacking (developer cannot complete qe step)', () => {
    const orchPlan = plan(
      [
        { id: '1', agent: 'developer', summary: 'fix' },
        { id: '2', agent: 'qe', summary: 'verify' },
      ],
      1,
      'brain',
      'brain',
    );
    // Developer attempts to mark step 2 (qe) as completed
    const state = derivePlanState([orchPlan, step('2', 'completed', 2, 'developer')]);
    expect(state.steps.find((s) => s.id === '2')?.status).toBe('pending');
  });

  it('marks step completed when assigned agent finishes with execute or report plan turn', () => {
    const orchPlan = plan(
      [
        { id: '1', agent: 'code_reviewer', summary: 'review' },
        { id: '2', agent: 'developer', summary: 'fix' },
        { id: '3', agent: 'qe', summary: 'verify' },
      ],
      10,
      'brain',
      'brain',
    );
    const crExecute = execute('code_reviewer', 22);
    const devPlan = plan([{ id: '3', summary: 'commit' }], 36, 'developer', 'developer');

    const state = derivePlanState([orchPlan, crExecute, devPlan]);
    expect(state.steps[0].status).toBe('completed');
    expect(state.steps[1].status).toBe('completed');
    expect(state.steps[2].status).toBe('pending');
  });

  it('lets an orchestrator plan_step override any agent step', () => {
    const orch = plan([{ id: '1', agent: 'developer', summary: 'fix' }, { id: '2', agent: 'qe', summary: 'verify' }], 1, 'brain', 'brain');
    const state = derivePlanState([orch, step('2', 'completed', 2, 'brain'), step('1', 'blocked', 3, 'Architect')]);
    expect(state.steps.find((s) => s.id === '2')?.status).toBe('completed');
    expect(state.steps.find((s) => s.id === '1')?.status).toBe('blocked');
  });

  it('ignores orchestrator execute turns for worker steps', () => {
    const orch = plan([{ id: '1', agent: 'developer', summary: 'fix' }], 1, 'brain', 'brain');
    const state = derivePlanState([orch, execute('brain', 2), execute('architect', 3)]);
    expect(state.steps[0].status).toBe('pending');
  });

  it('prefers an in_progress step over an earlier pending step for the same agent', () => {
    const orch = plan(
      [{ id: '1', agent: 'developer', summary: 'a' }, { id: '2', agent: 'developer', summary: 'b' }],
      1, 'brain', 'brain',
    );
    const state = derivePlanState([orch, step('2', 'in_progress', 2), execute('developer', 3)]);
    expect(state.steps.find((s) => s.id === '1')?.status).toBe('pending');
    expect(state.steps.find((s) => s.id === '2')?.status).toBe('completed');
  });

  it('completes only one step per execute turn', () => {
    const orch = plan(
      [{ id: '1', agent: 'developer', summary: 'a' }, { id: '2', agent: 'developer', summary: 'b' }],
      1, 'brain', 'brain',
    );
    const state = derivePlanState([orch, execute('developer', 2)]);
    expect(state.steps.map((s) => s.status)).toEqual(['completed', 'pending']);
    const two = derivePlanState([orch, execute('developer', 2), execute('developer', 3)]);
    expect(two.steps.map((s) => s.status)).toEqual(['completed', 'completed']);
  });

  it('never overwrites a blocked step via auto-completion', () => {
    const orch = plan([{ id: '1', agent: 'developer', summary: 'a' }], 1, 'brain', 'brain');
    const state = derivePlanState([orch, step('1', 'blocked', 2, 'brain'), execute('developer', 3)]);
    expect(state.steps[0].status).toBe('blocked');
  });

  it('does not auto-complete a step from a failed/error execute turn', () => {
    const orch = plan([{ id: '1', agent: 'developer', summary: 'a' }], 1, 'brain', 'brain');
    const state = derivePlanState([orch, execute('developer', 2, 'Error: Agent task failed')]);
    expect(state.steps[0].status).toBe('pending');
  });

  it('evaluates orchestrator status from both actor and taskForAgent.source (parity)', () => {
    // actor is a worker but source is orchestrator -> orchestrator plan
    expect(isOrchestratorPlan(plan([], 1, 'developer', 'Brain'))).toBe(true);
    // actor is orchestrator but source is a worker -> still orchestrator
    expect(isOrchestratorPlan(plan([], 1, 'Architect', 'developer'))).toBe(true);
    // neither
    expect(isOrchestratorPlan(plan([], 1, 'developer', 'qe'))).toBe(false);
    // missing taskForAgent / source
    expect(isOrchestratorPlan({ turn: 1, actor: 'developer', action: 'plan' } as unknown as ConversationTurn)).toBe(false);
    // precedence: source-orchestrator plan beats a later worker-actor proposal
    const orch = plan([{ id: '1', agent: 'developer', summary: 'orch' }], 1, 'developer', 'brain');
    const worker = plan([{ id: '1', agent: 'developer', summary: 'worker' }], 2, 'developer', 'developer');
    expect(derivePlanState([orch, worker]).steps[0].summary).toBe('orch');
  });

  it('correctly derives plan state for the full evt-e3805021 sequence', () => {
    const turns: ConversationTurn[] = [
      plan(
        [
          { id: '1', agent: 'code_reviewer', summary: 'Inspect PR #316 metadata' },
          { id: '2', agent: 'developer', summary: 'Remediate findings in-branch' },
          { id: '3', agent: 'qe', summary: 'Verify in-branch fixes with test suite' },
        ],
        10,
        'brain',
        'brain',
      ),
      execute('code_reviewer', 22),
      step('3', 'completed', 34, 'developer'), // Errant step_id from developer
      plan([{ id: '3', summary: 'In-branch remediation pushed as 3dcba8eb' }], 36, 'developer', 'developer'),
    ];

    const state = derivePlanState(turns);
    expect(state.hasPlan).toBe(true);
    expect(state.planTurn?.turn).toBe(10);
    expect(state.steps).toHaveLength(3);
    expect(state.steps[0]).toMatchObject({ id: '1', agent: 'code_reviewer', status: 'completed' });
    expect(state.steps[1]).toMatchObject({ id: '2', agent: 'developer', status: 'completed' });
    expect(state.steps[2]).toMatchObject({ id: '3', agent: 'qe', status: 'pending' });
  });

  it('exposes the expected terminal statuses', () => {
    expect([...TERMINAL_STATUSES].sort()).toEqual(['blocked', 'completed', 'green_verified', 'red_locked']);
  });
});

// ---------------------------------------------------------------------------
// QE edge-case coverage (mutation-driven): failed-turn precision, malformed turns, role canonicalisation,
// timestamps / test_evidence propagation, latest-plan selection, missing taskForAgent.
// ---------------------------------------------------------------------------
describe('derivePlanState edge cases (QE)', () => {
  const orch = (steps: Array<{ id: string; agent?: string; summary?: string }>, turn = 1) => plan(steps, turn, 'brain', 'brain');
  const rawTurn = (t: Record<string, unknown>) => t as unknown as ConversationTurn;
  const statuses = (s: ReturnType<typeof derivePlanState>) => s.steps.map((x) => x.status);

  it('isOrchestratorPlan is false for any non-plan action even for orchestrator actors', () => {
    expect(isOrchestratorPlan(rawTurn({ turn: 1, actor: 'brain', action: 'execute', taskForAgent: { source: 'brain' } }))).toBe(false);
    expect(isOrchestratorPlan(rawTurn({ turn: 1, actor: 'brain', action: 'plan_step' }))).toBe(false);
  });

  // KNOWN PARITY GAP (QE finding, LOW): backend _is_orchestrator_turn guards `isinstance(source, str)` and returns False for a
  // non-string source; the UI's canonicalRole() calls .trim() on it and throws TypeError (crashes derivePlanState).
  // it.fails documents the gap without turning CI red; flip to a plain `it` once isOrchestratorPlan guards typeof source.
  it.fails('isOrchestratorPlan treats a non-string source like the backend (false, no throw)', () => {
    expect(isOrchestratorPlan(rawTurn({ turn: 1, actor: 'developer', action: 'plan', taskForAgent: { source: 42 } }))).toBe(false);
  });

  it('isOrchestratorPlan treats null / missing source safely', () => {
    expect(isOrchestratorPlan(rawTurn({ turn: 1, actor: 'developer', action: 'plan', taskForAgent: { source: null } }))).toBe(false);
    expect(isOrchestratorPlan(rawTurn({ turn: 1, actor: 'developer', action: 'plan', taskForAgent: {} }))).toBe(false);
  });

  it.each(['Error: x', '  Error: x', '\n\t Error: boom', 'Error:'])('treats result %j as a failed turn', (result) => {
    const state = derivePlanState([orch([{ id: '1', agent: 'developer' }]), execute('developer', 2, result)]);
    expect(statuses(state)).toEqual(['pending']);
  });

  it.each([undefined, '', '   ', 'Errors were fixed', 'Error', 'error: lowercase is not the convention', 'Fixed. Earlier run printed Error: foo'])(
    'does not treat result %j as failed (step still completes)',
    (result) => {
      const exec = rawTurn({ turn: 2, actor: 'developer', action: 'execute', timestamp: 102, result });
      const state = derivePlanState([orch([{ id: '1', agent: 'developer' }]), exec]);
      expect(statuses(state)).toEqual(['completed']);
    },
  );

  it('an error-action turn never completes a step', () => {
    const err = rawTurn({ turn: 2, actor: 'developer', action: 'error', result: 'boom' });
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'developer' }]), err]))).toEqual(['pending']);
  });

  it('a failed execute does not consume the step; a later successful execute completes it', () => {
    const state = derivePlanState([
      orch([{ id: '1', agent: 'developer' }]),
      execute('developer', 2, 'Error: transient'),
      execute('developer', 3),
    ]);
    expect(statuses(state)).toEqual(['completed']);
    expect(state.steps[0].timestamp).toBe(103);
  });

  it('a failed worker plan turn does not auto-complete', () => {
    const bad = rawTurn({
      turn: 2, actor: 'developer', action: 'plan', timestamp: 102, result: 'Error: nope',
      taskForAgent: { steps: [{ id: '9', agent: 'developer', summary: 'x' }], source: 'developer' },
    });
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'developer' }]), bad]))).toEqual(['pending']);
  });

  it('a post-plan worker plan turn with no taskForAgent completes the step without crashing', () => {
    const bare = rawTurn({ turn: 2, actor: 'developer', action: 'plan', timestamp: 102 });
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'developer' }]), bare]))).toEqual(['completed']);
  });

  it('a post-plan orchestrator-sourced plan turn without steps does not auto-complete worker steps', () => {
    const sourced = rawTurn({ turn: 2, actor: 'developer', action: 'plan', timestamp: 102, taskForAgent: { source: 'brain' } });
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'developer' }]), sourced]))).toEqual(['pending']);
  });

  it('ignores an orchestrator execute even when the step is assigned to an orchestrator role', () => {
    const state = derivePlanState([orch([{ id: '1', agent: 'architect', summary: 'design' }]), execute('architect', 2)]);
    expect(statuses(state)).toEqual(['pending']);
  });

  it('ignores malformed plan_step turns (no taskForAgent, no step_id, unknown id) without crashing', () => {
    const noPayload = rawTurn({ turn: 2, actor: 'brain', action: 'plan_step' });
    const noId = rawTurn({ turn: 3, actor: 'brain', action: 'plan_step', taskForAgent: { status: 'completed' } });
    const unknown = step('99', 'completed', 4, 'brain');
    const state = derivePlanState([orch([{ id: '1', agent: 'qe' }]), noPayload, noId, unknown]);
    expect(state.steps.map((s) => s.id)).toEqual(['1']);
    expect(statuses(state)).toEqual(['pending']);
  });

  it('skips plan steps that have no usable id', () => {
    const state = derivePlanState([
      orch([{ id: '', agent: 'qe', summary: 'empty id' }, { agent: 'qe', summary: 'no id' } as never, null as never, { id: '1', agent: 'qe', summary: 'ok' }]),
    ]);
    expect(state.steps.map((s) => s.id)).toEqual(['1']);
  });

  it('latest worker plan wins when there is no orchestrator plan', () => {
    const first = plan([{ id: '1', agent: 'developer', summary: 'first' }], 1, 'developer', 'developer');
    const second = plan([{ id: '1', agent: 'qe', summary: 'second' }], 2, 'qe', 'qe');
    const state = derivePlanState([first, second]);
    expect(state.steps[0].summary).toBe('second');
    expect(state.planTurn?.turn).toBe(2);
  });

  it('latest orchestrator plan wins over an earlier orchestrator plan', () => {
    const state = derivePlanState([
      orch([{ id: '1', agent: 'developer', summary: 'first' }], 1),
      plan([{ id: '1', agent: 'developer', summary: 'second' }], 2, 'architect', 'architect'),
    ]);
    expect(state.steps[0].summary).toBe('second');
    expect(state.planTurn?.turn).toBe(2);
  });

  it('slices at the latest plan index: turns after an older worker plan but before the orchestrator plan are ignored', () => {
    const worker = plan([{ id: '1', agent: 'developer', summary: 'w' }], 1, 'developer', 'developer');
    const early = execute('developer', 2);
    const o = orch([{ id: '1', agent: 'developer', summary: 'o' }], 3);
    expect(statuses(derivePlanState([worker, early, o]))).toEqual(['pending']);
    expect(statuses(derivePlanState([worker, early, o, execute('developer', 4)]))).toEqual(['completed']);
  });

  it('propagates turn timestamps and test_evidence (object and string) from plan_step turns; ignores falsy evidence', () => {
    const withObj = rawTurn({
      turn: 2, actor: 'qe', action: 'plan_step', timestamp: 555,
      taskForAgent: { step_id: '1', status: 'green_verified', test_evidence: { exit_code: 0 } },
    });
    const withStr = rawTurn({
      turn: 3, actor: 'qe', action: 'plan_step', timestamp: 556,
      taskForAgent: { step_id: '2', status: 'red_locked', test_evidence: '1 failed' },
    });
    const noEv = rawTurn({ turn: 4, actor: 'qe', action: 'plan_step', timestamp: 557, taskForAgent: { step_id: '3', status: 'completed', test_evidence: '' } });
    const state = derivePlanState([
      orch([{ id: '1', agent: 'qe' }, { id: '2', agent: 'qe' }, { id: '3', agent: 'qe' }]),
      withObj, withStr, noEv,
    ]);
    expect(state.steps[0]).toMatchObject({ status: 'green_verified', test_evidence: { exit_code: 0 }, timestamp: 555 });
    expect(state.steps[1]).toMatchObject({ status: 'red_locked', test_evidence: '1 failed', timestamp: 556 });
    expect(state.steps[2].test_evidence).toBeUndefined();
    expect(state.steps[2].timestamp).toBe(557);
  });

  it('auto-completion stamps the completing turn timestamp', () => {
    const state = derivePlanState([orch([{ id: '1', agent: 'developer' }]), execute('developer', 5)]);
    expect(state.steps[0]).toMatchObject({ status: 'completed', timestamp: 105 });
  });

  it('a plan_step without a status completes the step', () => {
    const noStatus = rawTurn({ turn: 2, actor: 'qe', action: 'plan_step', timestamp: 102, taskForAgent: { step_id: '1' } });
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'qe' }]), noStatus]))).toEqual(['completed']);
  });

  it('unassigned steps accept plan_step updates from any actor', () => {
    const state = derivePlanState([orch([{ id: '1', agent: '' }, { id: '2' }]), step('1', 'completed', 2, 'developer'), step('2', 'in_progress', 3, 'qe')]);
    expect(statuses(state)).toEqual(['completed', 'in_progress']);
  });

  it.each(['code-reviewer', 'Code Reviewer', '  CODE_REVIEWER  ', 'Code-Reviewer'])('canonicalises actor %j against step agents', (actor) => {
    const o = orch([{ id: '1', agent: 'code_reviewer' }, { id: '2', agent: 'Code-Reviewer' }]);
    expect(statuses(derivePlanState([o, execute(actor, 2)]))).toEqual(['completed', 'pending']);
    expect(statuses(derivePlanState([o, step('1', 'in_progress', 2, actor), step('2', 'in_progress', 3, actor)]))).toEqual(['in_progress', 'in_progress']);
  });

  it.each(['Brain', ' brain ', 'ARCHITECT', 'Headhunter', 'ALIGNER'])('orchestrator actor %j can override any step via plan_step', (actor) => {
    expect(statuses(derivePlanState([orch([{ id: '1', agent: 'qe' }]), step('1', 'blocked', 2, actor)]))).toEqual(['blocked']);
  });
});
