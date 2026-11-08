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
