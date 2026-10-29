// BlackBoard/ui/src/components/PlanProgress.test.tsx
/**
 * 4-Layer Farley ATDD Executable Acceptance Specification
 * Scenario T-5: PlanProgress Farley ATDD Status Transitions & Done Counter
 *
 * Layer 1: Domain Scenarios (Given/When/Then)
 * Layer 2: Domain DSL operations
 * Layer 3: Protocol Driver (React Testing Library)
 * Layer 4: System Under Test (PlanProgress component)
 */
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { PlanProgress } from './PlanProgress';
import type { ConversationTurn } from '../api/types';

afterEach(cleanup);

// =============================================================================
// Layer 3: Protocol Driver
// =============================================================================
class PlanProgressDriver {
  private container: HTMLElement | null = null;

  renderComponent(turns: ConversationTurn[]) {
    const result = render(<PlanProgress conversation={turns} />);
    this.container = result.container;
    return result;
  }

  getDoneCounterText(): string {
    if (!this.container) throw new Error('Not rendered');
    const header = this.container.querySelector('span[style*="monospace"]');
    return header?.textContent?.trim() || '';
  }

  getStepElement(summary: string): HTMLElement {
    if (!this.container) throw new Error('Not rendered');
    const summaryEl = screen.getByText(summary);
    // Return step item container
    return summaryEl.parentElement as HTMLElement;
  }

  getStepIcon(summary: string): string {
    const stepEl = this.getStepElement(summary);
    const iconSpan = stepEl.querySelector('span[style*="font-size: 12px"]') || stepEl.querySelector('span');
    return iconSpan?.textContent?.trim() || '';
  }

  getStepBorderStyle(summary: string): string {
    const stepEl = this.getStepElement(summary);
    return stepEl.style.borderLeft || '';
  }
}

// =============================================================================
// Layer 2: Domain DSL
// =============================================================================
class PlanProgressDSL {
  private driver: PlanProgressDriver;
  private turns: ConversationTurn[] = [];

  constructor(driver: PlanProgressDriver) {
    this.driver = driver;
  }

  givenPlanWithSteps(steps: Array<{ id: string; agent: string; summary: string }>) {
    this.turns = [
      {
        turn: 1,
        actor: 'architect',
        action: 'plan',
        thoughts: 'Execution plan created',
        timestamp: 1700000000,
        taskForAgent: {
          steps,
        },
      } as unknown as ConversationTurn,
    ];
  }

  givenStepUpdated(stepId: string, status: string, agent: string, summary: string) {
    this.turns.push({
      turn: this.turns.length + 1,
      actor: agent,
      action: 'plan_step',
      thoughts: `Updating step ${stepId} to ${status}`,
      timestamp: 1700000010 + this.turns.length,
      taskForAgent: {
        step_id: stepId,
        status,
        summary,
      },
    } as unknown as ConversationTurn);
  }

  whenRendered() {
    return this.driver.renderComponent(this.turns);
  }

  thenDoneCounterShows(expected: string) {
    const actual = this.driver.getDoneCounterText();
    expect(actual).toBe(expected);
  }

  thenStepIconIs(summary: string, expectedIcon: string) {
    const icon = this.driver.getStepIcon(summary);
    expect(icon).toBe(expectedIcon);
  }

  thenStepBorderColorIs(summary: string, expectedColor: string) {
    const border = this.driver.getStepBorderStyle(summary);
    expect(border).toContain(expectedColor);
  }
}

// =============================================================================
// Layer 1: Domain Scenarios (Scenario T-5)
// =============================================================================
describe('Scenario T-5: Farley ATDD PlanProgress Acceptance Specification', () => {
  it('T-5.1: counts green_verified steps as done alongside completed steps', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    // Given 3 plan steps: 1 completed, 1 green_verified, 1 pending
    dsl.givenPlanWithSteps([
      { id: '1', agent: 'qe', summary: 'Step 1: Authors Farley ATDD red test' },
      { id: '2', agent: 'developer', summary: 'Step 2: Implementation verified' },
      { id: '3', agent: 'sysadmin', summary: 'Step 3: Deployment release' },
    ]);
    dsl.givenStepUpdated('1', 'completed', 'qe', 'Step 1: Authors Farley ATDD red test');
    dsl.givenStepUpdated('2', 'green_verified', 'developer', 'Step 2: Implementation verified');

    // When rendered in UI
    dsl.whenRendered();

    // Then progress fraction must count green_verified as done (2/3, not 1/3)
    dsl.thenDoneCounterShows('2/3');
  });

  it('T-5.2: displays red_locked status icon 🔴 🔒 and green_verified icon 🟢 ✓', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    // Given plan with red_locked and green_verified steps
    dsl.givenPlanWithSteps([
      { id: '1', agent: 'qe', summary: 'Step 1: Red test locked' },
      { id: '2', agent: 'developer', summary: 'Step 2: Green verified' },
    ]);
    dsl.givenStepUpdated('1', 'red_locked', 'qe', 'Step 1: Red test locked');
    dsl.givenStepUpdated('2', 'green_verified', 'developer', 'Step 2: Green verified');

    // When rendered in UI
    dsl.whenRendered();

    // Then distinct Farley ATDD icons must render
    dsl.thenStepIconIs('Step 1: Red test locked', '🔴 🔒');
    dsl.thenStepIconIs('Step 2: Green verified', '🟢 ✓');
  });

  it('T-5.3: styles red_locked with #ef4444 border and green_verified with #10b981 border', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    // Given plan with red_locked and green_verified steps
    dsl.givenPlanWithSteps([
      { id: '1', agent: 'qe', summary: 'Step 1: Red test locked' },
      { id: '2', agent: 'developer', summary: 'Step 2: Green verified' },
    ]);
    dsl.givenStepUpdated('1', 'red_locked', 'qe', 'Step 1: Red test locked');
    dsl.givenStepUpdated('2', 'green_verified', 'developer', 'Step 2: Green verified');

    // When rendered in UI
    dsl.whenRendered();

    // Then border styling reflects Farley ATDD status
    dsl.thenStepBorderColorIs('Step 1: Red test locked', '#ef4444');
    dsl.thenStepBorderColorIs('Step 2: Green verified', '#10b981');
  });
});
