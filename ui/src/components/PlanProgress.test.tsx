// BlackBoard/ui/src/components/PlanProgress.test.tsx
/**
 * 4-Layer Farley ATDD Executable Acceptance Specification
 * Scenario T-5: PlanProgress Farley ATDD Status Transitions & Done Counter
 * Scenario T-6: PlanProgress Dual-Correlation, Stream Affordance & Animations
 *
 * Layer 1: Domain Scenarios (Given/When/Then)
 * Layer 2: Domain DSL operations
 * Layer 3: Protocol Driver (React Testing Library)
 * Layer 4: System Under Test (PlanProgress component)
 */
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { PlanProgress } from './PlanProgress';
import type { ConversationTurn } from '../api/types';

afterEach(cleanup);

// =============================================================================
// Layer 3: Protocol Driver
// =============================================================================
class PlanProgressDriver {
  private container: HTMLElement | null = null;

  renderComponent(
    turns: ConversationTurn[],
    options?: {
      activeAgentRoles?: Set<string>;
      onOpenStream?: (role: string) => void;
    }
  ) {
    const result = render(
      <PlanProgress
        conversation={turns}
        activeAgentRoles={options?.activeAgentRoles}
        onOpenStream={options?.onOpenStream}
      />
    );
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
    return summaryEl.closest('[data-testid="plan-step"]') || summaryEl.parentElement as HTMLElement;
  }

  getStepIcon(summary: string): string {
    const stepEl = this.getStepElement(summary);
    const iconSpan = stepEl.querySelector('span[style*="font-size: 12px"]') || stepEl.querySelector('span');
    return iconSpan?.textContent?.trim() || '';
  }

  getTestEvidenceText(): string {
    if (!this.container) throw new Error('Not rendered');
    return this.container.querySelector('details pre')?.textContent || '';
  }

  getStepBorderStyle(summary: string): string {
    const stepEl = this.getStepElement(summary);
    return stepEl.style.borderLeft || '';
  }

  queryWorkingBeacon(summary: string): HTMLElement | null {
    const stepEl = this.getStepElement(summary);
    return stepEl.querySelector('[data-testid="plan-step-working-beacon"]');
  }

  queryStreamButton(summary: string): HTMLElement | null {
    const stepEl = this.getStepElement(summary);
    return stepEl.querySelector('button[data-testid="plan-step-stream-btn"]');
  }
}

// =============================================================================
// Layer 2: Domain DSL
// =============================================================================
class PlanProgressDSL {
  private driver: PlanProgressDriver;
  private turns: ConversationTurn[] = [];
  private activeAgentRoles: Set<string> | undefined = undefined;
  private onOpenStream: ReturnType<typeof vi.fn> | undefined = undefined;

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

  givenReplanWithSteps(steps: Array<{ id: string; agent: string; summary: string }>) {
    this.turns.push({
      turn: this.turns.length + 1,
      actor: 'architect',
      action: 'plan',
      thoughts: 'Plan updated with revised steps',
      timestamp: 1700000050 + this.turns.length,
      taskForAgent: {
        steps,
      },
    } as unknown as ConversationTurn);
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

  givenStepUpdatedWithEvidence(stepId: string, status: string, agent: string, testEvidence: unknown) {
    this.turns.push({
      turn: this.turns.length + 1,
      actor: agent,
      action: 'plan_step',
      thoughts: `Updating step ${stepId} to ${status}`,
      timestamp: 1700000010 + this.turns.length,
      taskForAgent: {
        step_id: stepId,
        status,
        test_evidence: testEvidence,
      },
    } as unknown as ConversationTurn);
  }

  givenActiveAgentRoles(roles: string[]) {
    this.activeAgentRoles = new Set(roles);
  }

  givenOnOpenStreamCallback(callback: ReturnType<typeof vi.fn>) {
    this.onOpenStream = callback;
  }

  whenRendered() {
    return this.driver.renderComponent(this.turns, {
      activeAgentRoles: this.activeAgentRoles,
      onOpenStream: this.onOpenStream,
    });
  }

  thenTestEvidenceTextContains(...fragments: string[]) {
    const text = this.driver.getTestEvidenceText();
    for (const f of fragments) expect(text).toContain(f);
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

  thenStepShowsWorkingBeacon(summary: string) {
    const beacon = this.driver.queryWorkingBeacon(summary);
    expect(beacon).not.toBeNull();
    expect(beacon?.textContent).toContain('Working...');
  }

  thenStepDoesNotShowWorkingBeacon(summary: string) {
    const beacon = this.driver.queryWorkingBeacon(summary);
    expect(beacon).toBeNull();
  }

  thenStepShowsStreamButton(summary: string) {
    const btn = this.driver.queryStreamButton(summary);
    expect(btn).not.toBeNull();
  }

  thenStepDoesNotShowStreamButton(summary: string) {
    const btn = this.driver.queryStreamButton(summary);
    expect(btn).toBeNull();
  }

  whenStreamButtonClicked(summary: string) {
    const btn = this.driver.queryStreamButton(summary);
    if (!btn) throw new Error(`Stream button not found on ${summary}`);
    fireEvent.click(btn);
  }
}

// =============================================================================
// Layer 1: Domain Scenarios (Scenario T-5 & T-6)
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

  it('T-5.4: renders dict test_evidence (backend contract) without throwing React Error #31', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    // Given a step whose plan_step turn carries test_evidence as an object, exactly as PlanStepRequest emits it
    dsl.givenPlanWithSteps([{ id: '1', agent: 'qe', summary: 'Step 1: Red test locked' }]);
    dsl.givenStepUpdatedWithEvidence('1', 'red_locked', 'qe', {
      exit_code: 1,
      output: 'FAILED tests/test_feature.py::test_x - AssertionError',
    });

    // When rendered, then it must not throw ("Objects are not valid as a React child") and shows the serialized JSON
    expect(() => dsl.whenRendered()).not.toThrow();
    dsl.thenTestEvidenceTextContains('"exit_code": 1', 'AssertionError');
  });

  it('T-5.5: still renders string test_evidence verbatim', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    dsl.givenPlanWithSteps([{ id: '1', agent: 'developer', summary: 'Step 1: Green' }]);
    dsl.givenStepUpdatedWithEvidence('1', 'green_verified', 'developer', '12 passed in 0.4s');

    dsl.whenRendered();
    dsl.thenTestEvidenceTextContains('12 passed in 0.4s');
  });
});

describe('Scenario T-6: Dual-Correlation, Stream Affordance & Animations Acceptance Specification', () => {
  it('T-6.1: highlights only the first pending step when multiple steps share the same agent role', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    dsl.givenPlanWithSteps([
      { id: '1', agent: 'developer', summary: 'Step 1: First dev task' },
      { id: '2', agent: 'developer', summary: 'Step 2: Second dev task' },
    ]);
    dsl.givenActiveAgentRoles(['developer']);

    dsl.whenRendered();

    // Only step 1 should show the working beacon and stream affordance
    dsl.thenStepShowsWorkingBeacon('Step 1: First dev task');
    dsl.thenStepDoesNotShowWorkingBeacon('Step 2: Second dev task');
  });

  it('T-6.2: canonicalizes agent roles case-insensitively and ignores empty string agent', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    dsl.givenPlanWithSteps([
      { id: '1', agent: 'SysAdmin', summary: 'Step 1: Server setup' },
      { id: '2', agent: '', summary: 'Step 2: Unassigned step' },
    ]);
    dsl.givenActiveAgentRoles(['sysadmin', '']);

    dsl.whenRendered();

    dsl.thenStepShowsWorkingBeacon('Step 1: Server setup');
    dsl.thenStepDoesNotShowWorkingBeacon('Step 2: Unassigned step');
  });

  it('T-6.3: suppresses active beacon when all steps are terminal even if agent is active', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    dsl.givenPlanWithSteps([
      { id: '1', agent: 'developer', summary: 'Step 1: Done dev task' },
    ]);
    dsl.givenStepUpdated('1', 'completed', 'developer', 'Step 1: Done dev task');
    dsl.givenActiveAgentRoles(['developer']);

    dsl.whenRendered();

    dsl.thenStepDoesNotShowWorkingBeacon('Step 1: Done dev task');
    dsl.thenStepDoesNotShowStreamButton('Step 1: Done dev task');
  });

  it('T-6.4: fires onOpenStream with agent role when Stream ↗ button is clicked', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);
    const streamSpy = vi.fn();

    dsl.givenPlanWithSteps([
      { id: '1', agent: 'developer', summary: 'Step 1: Live dev task' },
    ]);
    dsl.givenActiveAgentRoles(['developer']);
    dsl.givenOnOpenStreamCallback(streamSpy);

    dsl.whenRendered();

    dsl.thenStepShowsStreamButton('Step 1: Live dev task');
    dsl.whenStreamButtonClicked('Step 1: Live dev task');

    expect(streamSpy).toHaveBeenCalledWith('developer');
  });

  it('T-6.5: safely slices replan turns and ignores steps from prior plan action', () => {
    const driver = new PlanProgressDriver();
    const dsl = new PlanProgressDSL(driver);

    // Initial plan with step 1
    dsl.givenPlanWithSteps([
      { id: '1', agent: 'developer', summary: 'Step 1: Old plan step' },
    ]);
    dsl.givenStepUpdated('1', 'completed', 'developer', 'Step 1: Old plan step');

    // Replan arrives with step 2
    dsl.givenReplanWithSteps([
      { id: '2', agent: 'developer', summary: 'Step 2: Re-planned task' },
    ]);
    dsl.givenActiveAgentRoles(['developer']);

    dsl.whenRendered();

    // Step 2 should be active and pending in the latest plan
    dsl.thenStepShowsWorkingBeacon('Step 2: Re-planned task');
    dsl.thenDoneCounterShows('0/1');
  });

  it('T-6.6: does not violate React rules of hooks when re-rendering from empty conversation to populated plan', () => {
    const { rerender } = render(<PlanProgress conversation={[]} activeAgentRoles={new Set(['developer'])} />);
    expect(screen.queryByText('Plan')).toBeNull();

    const planTurn: ConversationTurn = {
      turn: 1,
      actor: 'architect',
      action: 'plan',
      timestamp: 1000,
      taskForAgent: {
        steps: [{ id: '1', agent: 'developer', summary: 'Step 1: Implementation' }],
      },
    };

    expect(() => {
      rerender(<PlanProgress conversation={[planTurn]} activeAgentRoles={new Set(['developer'])} />);
    }).not.toThrow();

    expect(screen.getByText('Step 1: Implementation')).toBeInTheDocument();
  });
});
