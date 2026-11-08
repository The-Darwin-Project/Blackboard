// BlackBoard/ui/src/__tests__/planState.test.ts
// @ai-rules:
// 1. [Pattern]: Unit tests for utils/planState.ts (canonicalRole normalization, derivePlanState replan slicing, status mapping).
import { describe, it, expect } from 'vitest';
import { canonicalRole, derivePlanState, TERMINAL_STATUSES } from '../utils/planState';
import type { ConversationTurn } from '../api/types';

const plan = (steps: Array<{ id: string; agent?: string; summary?: string }>, turn = 1): ConversationTurn =>
  ({ turn, actor: 'architect', action: 'plan', timestamp: 1, taskForAgent: { steps } }) as unknown as ConversationTurn;
const step = (stepId: string, status: string | undefined, turn: number): ConversationTurn =>
  ({ turn, actor: 'developer', action: 'plan_step', timestamp: 100 + turn, taskForAgent: { step_id: stepId, status } }) as unknown as ConversationTurn;

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

  it('exposes the expected terminal statuses', () => {
    expect([...TERMINAL_STATUSES].sort()).toEqual(['blocked', 'completed', 'green_verified', 'red_locked']);
  });
});
