# Pre-Flight Review: VMER-2208 (Round 1)

**Date**: 2026-11-01  
**Target Plan**: `BlackBoard/.plan.md`  
**Jira Issue**: [VMER-2208](https://redhat.atlassian.net/browse/VMER-2208)  
**Evaluators**:
- **Auditor A** (Cynefin & Architecture Depth): 95% (Ready)
- **Auditor B** (Gaps, Completeness & Testability): 90% (Caution)
- **Auditor C** (Contracts, A11y & Failure Modes via Claude CLI Reviewer): 74% (Caution)

---

## 1. Confidence Dashboard

| Metric | Value |
| :--- | :--- |
| **Overall Confidence** | **74%** (Pessimistic Minimum: Auditor C) |
| **Status** | **Caution (Not Ready for Execution)** |
| **Soft Gate** | ≥ 90% (Requires Round 2 convergence) |
| **Critical Blockers** | 1. Nested interactive element & keydown propagation in `WorkspaceTaskItem` (Enter/Space triggering session selection on copy).<br/>2. Dropdown scope-gating breaks 3 existing tests in `workspace-sessions-hub.test.tsx` (lines 377, 396, 406) expecting project select in default `'mine'` scope.<br/>3. Test matcher limitations (`testSetup.ts` lacks `jest-dom`; tests must use raw DOM attributes). |

---

## 2. Auditor Agreement Matrix

| Step | Task Summary | Auditor A (Arch) | Auditor B (Gaps) | Auditor C (Contracts) | Min Confidence | Agreement Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Create `CopyButton.tsx` Component | 95% | 95% | 74% | **74%** | Refine fallback, timer cleanup, and success-gated visual state. |
| **2** | Unit Tests for `CopyButton` | 100% | 95% | 70% | **70%** | Specify `vi.stubGlobal`, raw DOM assertions (no `jest-dom`), and async microtask flush. |
| **3** | Remove `select-none` from Layout & Asides | 100% | 100% | 96% | **96%** | Consensus: Verified safe and covered by `useResizablePanel`. |
| **4** | Fix Project Dropdown Scoping, Labeling & Matching | 100% | 100% | 88% | **88%** | Consensus on scoping & labeling; clarify reset of `selectedProject`. |
| **5** | Update `workspace-sessions-hub.test.tsx` | 100% | 100% | 68% | **68%** | Explicitly patch tests at lines 377, 396, and 406 to switch to Global scope first. |
| **6** | Add Copy Affordance in `WorkspaceCenterStage.tsx` | 100% | 90% | 92% | **90%** | Add explicit `import { CopyButton }` and verify no button role ambiguity. |
| **7** | Add Event ID Row with Copy Affordance in `WorkspaceInspector.tsx` | 100% | 90% | 88% | **88%** | Add explicit `import { CopyButton }` and ensure ID is rendered when `eventDoc` is present. |
| **8** | Add Copy Affordance in `WorkspaceHeader.tsx` | 100% | 90% | 78% | **78%** | Null-guard `effectiveEventId`, add `flex-shrink-0`, and add explicit import. |
| **9** | Add Hover/Focus Copy Affordance in `WorkspaceTaskItem.tsx` | 95% | 95% | 60% | **60%** | Guard keydown bubbling (`e.stopPropagation()`) so copying does not trigger `onSelect`. |
| **10** | Disambiguate Button Selectors in TaskItem Tests | 100% | 95% | 75% | **75%** | Disambiguate button selectors across task item tests using accessible names or container queries. |
| **11** | Full Regression Verification | 100% | 100% | 85% | **85%** | Pass all 36 test files and verify production build. |

---

## 3. Integration Risk Matrix

| # | Sev | Boundary / Interface | Risk | Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | **HIGH** | `WorkspaceTaskItem` DOM & Events | Keydown (`Enter`/`Space`) on CopyButton bubbles to card `handleKeyDown` triggering `onSelect`. | Add `onKeyDown={(e) => e.stopPropagation()}` to `CopyButton` and guard `WorkspaceTaskItem`'s `handleKeyDown` with `if (e.target !== e.currentTarget) return;`. |
| **C2** | **HIGH** | `WorkspaceTaskItem` A11y Tree | Nested interactive element (`<button>` inside `div[role="button"]`) violates WCAG 4.1.2. | Maintain accessible naming (`aria-label="Copy Event ID"`) and stop click/keydown propagation, or isolate CopyButton as a non-nested sibling where practical. |
| **C3** | **HIGH** | `workspace-sessions-hub.test.tsx` Scope Gating | Existing tests at lines 377, 396, and 406 query `/filter by project/i` in default `'mine'` scope and will throw when gated. | Step 5 must explicitly patch tests at lines 377, 396, and 406 to click the "Global" button before querying the dropdown. |
| **C4** | **MED** | Platform Clipboard API | `navigator.clipboard` is undefined in JSDOM and insecure HTTP contexts; `execCommand` may be restricted. | Use feature detection: try `navigator.clipboard?.writeText(text)`, fall back to hidden `<textarea>` + `document.execCommand('copy')`. Strictly gate `copied` state and `aria-live` confirmation on successful write. |
| **C5** | **MED** | Timer Lifecycle in React | 2,000ms feedback timeout not cleared on unmount causes React memory leak warnings. | Maintain `timerRef = useRef<NodeJS.Timeout | null>(null)` with `clearTimeout` on re-click and in `useEffect` cleanup on unmount. |
| **C6** | **MED** | Vitest Test Matcher Limitations | `testSetup.ts` provides only custom `toBeInTheDocument`; `@testing-library/jest-dom` matchers are unavailable. | Unit tests in Steps 2, 5, and 10 must use standard DOM property assertions (`.getAttribute('aria-label')`, `.textContent`) instead of `toHaveAttribute` or `toBeVisible`. |
| **C7** | **MED** | Component Import Boundaries | Steps 6–9 omit explicit import instructions for `CopyButton`. | Explicitly specify `import { CopyButton } from './CopyButton';` in Steps 6, 7, 8, and 9. |
| **C8** | **MED** | `WorkspaceHeader` Breadcrumb Layout | `effectiveEventId` is nullable (e.g. "New Task"); button may shrink in flex container. | Null-guard rendering (`effectiveEventId && ...`), add `flex-shrink-0`, and clarify accessible label. |

---

## 4. Gap Analysis (Tasks < 95% Confidence)

- **Step 1 (74%)**: Needs concrete specifications for timer cleanup on unmount, success-gated feedback (never show Check icon if both clipboard methods fail), explicit Lucide imports, and accessible `aria-live="polite"` region.
- **Step 2 (70%)**: Needs test harness specification without `jest-dom` matchers, explicit `vi.stubGlobal('navigator', ...)` setup, and microtask flushing before fake timer advancement.
- **Step 4 (88%)**: Clarify resetting `selectedProject` to `'all'` when switching from Global to "My Tasks".
- **Step 5 (68%)**: Plan generically stated "tests 377–418"; must explicitly enumerate lines 377, 396, and 406.
- **Step 6, 7, 8 (78%–90%)**: Needs explicit `import { CopyButton }` statements, null-guards, and `flex-shrink-0` on header breadcrumb.
- **Step 9 (60%)**: Needs complete keydown event isolation and CSS visibility spec (`opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity`) keeping button focusable in DOM.
- **Step 10 (75%)**: Ensure test disambiguation covers button role queries across task item tests without breaking existing test logic.

---

## 5. Path to Green (Amendment Directives for `/update-plan`)

1. **[BLOCKER] TaskItem Event Isolation (Step 9 & Step 1)**:
   - In `CopyButton.tsx`: Add `onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleCopy(); } }}` and `onClick={(e) => { e.stopPropagation(); handleCopy(); }}`.
   - In `WorkspaceTaskItem.tsx`: In `handleKeyDown`, add an early return: `if (e.target !== e.currentTarget) return;` so child interactions never trigger card selection.
   - Reveal styling: Keep button in DOM with `opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity`.
2. **[BLOCKER] Test Disambiguation in Hub Tests (Step 5)**:
   - Explicitly enumerate lines 377, 396, and 406 in `workspace-sessions-hub.test.tsx` to click `screen.getByRole('button', { name: /Global/i })` before querying project dropdown.
3. **[BLOCKER] Test Matcher Contract Compliance (Step 2 & Step 10)**:
   - Explicitly note in Step 2 that `testSetup.ts` lacks `jest-dom`; all assertions must use standard DOM properties (`button.getAttribute('aria-label')`, `button.querySelector('svg')`).
   - Specify clipboard mock using `vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: vi.fn() } })`.
   - Specify `await Promise.resolve()` microtask flush before `vi.advanceTimersByTime(2000)`.
4. **[PRECISION] CopyButton Robustness & Timer Cleanup (Step 1)**:
   - Use `useRef<ReturnType<typeof setTimeout> | null>(null)` for timer cleanup on unmount.
   - Only set `copied = true` upon successful clipboard write; catch rejections cleanly.
   - Add `aria-live="polite"` status or accessible label update.
   - Explicit imports: `import { Copy, Check } from 'lucide-react';`.
5. **[PRECISION] Explicit Component Imports & Layout Guards (Steps 6, 7, 8)**:
   - Explicitly add `import { CopyButton } from './CopyButton';` to `WorkspaceCenterStage.tsx`, `WorkspaceInspector.tsx`, and `WorkspaceHeader.tsx`.
   - In `WorkspaceHeader.tsx`, wrap CopyButton in `{effectiveEventId && <CopyButton text={effectiveEventId} label="Copy Event ID" className="flex-shrink-0" />}`.
