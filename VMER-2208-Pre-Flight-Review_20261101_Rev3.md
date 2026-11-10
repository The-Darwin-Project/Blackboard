# Pre-Flight Verification Review: VMER-2208 (Rev 3)

**Date**: 2026-11-01 15:42  
**Target Plan**: `BlackBoard/.plan.md`  
**Jira Issue**: [VMER-2208](https://redhat.atlassian.net/browse/VMER-2208)  
**Status**: **Ready (>=90% Confidence Threshold Met)**  
**Auditor Panel**:
- **Auditor A** (`pro`: Architecture, Contracts, Component Boundaries): **100% (Ready)**
- **Auditor B** (`pro`: Implementation Gaps, Test Harness Constraints): **98% (Ready)**
- **Auditor C** (`claude-opus-4-8`: Contracts, a11y, Regression Vectors): **93% (Ready)**
- **Pessimistic Composite (Min Score)**: **93% (Ready)**

---

## 1. Confidence Dashboard

| Metric | Score / Status |
| :--- | :--- |
| **Auditor A Confidence (Architecture)** | **100%** |
| **Auditor B Confidence (Gaps & Hygiene)** | **98%** |
| **Auditor C Confidence (Contracts & a11y)** | **93%** |
| **Pessimistic Minimum Confidence** | **93%** |
| **Gate Status** | **Ready** (Passes >=90% Gate) |
| **Blockers** | **None** |
| **Path / Link Hygiene** | **100% Clean** (Zero `file:///` or `/home/` paths) |

---

## 2. Iteration & Convergence History

| Round / Rev | Auditor A | Auditor B | Auditor C | Pessimistic Min | Verdict | Key Findings & Actions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Round 1** (15:06) | 95% | 90% | 74% | **74%** | Caution | A-1: Card selection on Enter/Space; A-2: timerRef memory leak; A-3: Vitest/jest-dom limits; A-4: Hub tests 377, 396, 406. |
| **Round 2** (15:19) | 98% | 100% | 82% | **82%** | Caution | A-7: L38 `e.repeat` guard; A-8: L406 whitespace vs mine test; A-9: disabled state & sr-only; A-11: L174 selectedProject reset. |
| **Round 3 / Scope Add** (15:33) | 100% | 98% | 86% | **86%** | Caution | User added "Waiting for Approval" section to Global View. C-1/C-2 Hub helper & labels resolved. C-3/C-4 Inspector Event ID JSX concrete. |
| **Round 4 / Rev 3** (15:42) | 100% | 98% | 93% | **93%** | **Ready** | A-19: Preserved Lucide icons (User, Globe, Filter) in Hub; A-20: Nested Waiting for Approval tests in main describe; A-21: TaskItem clipboard stubbing; A-22: Promise.resolve timer flush. |

---

## 3. Task-by-Task Confidence Breakdown

| Step | Component / Task | Domain | Confidence | Risk / Verification Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | `CopyButton.tsx` Component | Complicated | 98% | Success-gated visual feedback, timerRef cleanup, `e.stopPropagation` on click/keydown, `disabled={!text}`, `<span className="sr-only" aria-live="polite">`. |
| **Step 2** | `CopyButton` Unit Tests | Complicated | 96% | Vitest raw DOM assertions (no `jest-dom`), clipboard stubbing with `afterEach` teardown, `await Promise.resolve()` microtask flush before fake timers. |
| **Step 3** | Remove Redundant `select-none` | Clear | 100% | Verified at `WorkspaceLayout.tsx:67`, `WorkspaceSessionsHub.tsx:155`, and `WorkspaceInspector.tsx:111`. Active drag protected by `useResizablePanel.ts`. |
| **Step 4** | Project Dropdown Scoping & "Waiting for Approval" Folder | Complicated | 95% | Gated on `scope === 'all' && availableProjects.length > 0`, labeled `"All Repositories / Projects"`, `selectedProject` reset at L174. Active events partitioned into `waitingApprovalTasks`, `activeTasks`, `deferredTasks`. Dedicated amber accordion with `AlertCircle`, badge count, default expanded. Minimal Lucide import preserves `User`, `Globe`, `Filter`. |
| **Step 5** | `workspace-sessions-hub.test.tsx` Updates | Complicated | 94% | Prepend Global toggle on lines 377, 396, 406. Dedicated test for dropdown absence in 'mine' scope using `ctxEvent` and `asQuery`. Dedicated tests for "Waiting for Approval" folder rendering and accordion toggle nested inside `describe('WorkspaceSessionsHub (Left Sidebar)')`. |
| **Step 6** | `WorkspaceCenterStage.tsx` Copy Affordance | Clear | 98% | CopyButton beside `{selectedEventId}` in subheader. Surviving tests verified. |
| **Step 7** | `WorkspaceInspector.tsx` Event ID Row & Copy Affordance | Clear | 96% | Concrete JSX prepended inside `{isOverviewOpen && (...)}` (L193–229) with `label="Copy Event ID"`. No collision with overview card toggle button. |
| **Step 8** | `WorkspaceHeader.tsx` Copy Affordance | Clear | 98% | CopyButton beside `sessionLabel` with `flex-shrink-0`. Surviving test `expect(toggleButtons.length).toBeGreaterThanOrEqual(2)` remains green. |
| **Step 9** | `WorkspaceTaskItem.tsx` Hover/Focus Copy Affordance | Complicated | 95% | `e.target !== e.currentTarget` + `e.repeat` guards in `handleKeyDown`. Visible on `group-hover` and `group-focus-within`. Documented WCAG 4.1.2 containment. |
| **Step 10** | `workspace-task-item.test.tsx` Selector Disambiguation | Complicated | 95% | Disambiguates row vs copy button via `getAllByRole('button')[0]`. Clipboard mock harness with `afterEach` teardown. Asserts keydown/click isolation. |
| **Step 11** | Full Regression Verification | Clear | 95% | `npm --prefix BlackBoard/ui test` (36/36 test files) and `npm run build` (`tsc -b`). Zero type errors. |

---

## 4. Integration Risk Matrix

| Boundary | Pattern | Risk | Resolution / Recommendation |
| :--- | :--- | :--- | :--- |
| **Event Bubbling** (`WorkspaceTaskItem` <-> `CopyButton`) | Nested `<button>` inside `<div role="button">` | Low | Dual defense: `e.stopPropagation()` in child on click and keydown; `e.target !== e.currentTarget` early return in parent row handler. |
| **State Partitioning** (`WorkspaceSessionsHub`) | `useMemo` single-pass categorization | Low | Partitions `rawActiveEvents` into `waitingApprovalTasks`, `activeTasks`, `deferredTasks`. Respects `filterFn` without duplicating filter operations. |
| **Lucide Icon Imports** (`WorkspaceSessionsHub`) | Named import list | Low | Preserves existing `User`, `Globe`, `Filter` while adding `AlertCircle`. Omits unused icons to prevent TS6133 under `noUnusedLocals: true`. |
| **Test Mock Inheritance** (`workspace-sessions-hub.test.tsx`) | Nested describe scoping | Low | New Waiting for Approval tests nested inside main `describe('WorkspaceSessionsHub (Left Sidebar)')` adjacent to line 210 to inherit `beforeEach` setup. |
| **JSDOM Clipboard API** (`workspace-task-item.test.tsx`) | Global clipboard stub | Low | `vi.stubGlobal('navigator', ...)` with `afterEach(() => vi.unstubAllGlobals())` ensures clipboard write assertions pass in headless JSDOM. |

---

## 5. Path to Green Ledger

- [x] **A-1**: Added `e.stopPropagation()` on click/keydown in CopyButton, and early return `if (e.target !== e.currentTarget) return;` in `WorkspaceTaskItem`'s `handleKeyDown` to stop Enter/Space card selection.
- [x] **A-2**: Added timer lifecycle cleanup (`useRef` + `clearTimeout` on unmount/re-click) and success-gated visual feedback in `CopyButton`.
- [x] **A-3**: Updated Step 2 with Vitest/JSDOM constraints (`testSetup.ts` lacks `jest-dom`; raw DOM property assertions required), `vi.stubGlobal` clipboard mocking, and microtask flush before fake timers.
- [x] **A-4**: Updated Step 5 with exact lines 377, 396, and 406 in `workspace-sessions-hub.test.tsx` to click Global button before querying project filter, and updated line 420.
- [x] **A-5**: Added explicit `import { CopyButton }` instructions to Steps 6, 7, 8, and 9, and added `flex-shrink-0` to header breadcrumb CopyButton.
- [x] **A-6**: Updated Step 10 to disambiguate button queries in `workspace-task-item.test.tsx` and assert keydown/click isolation.
- [x] **A-7**: Restored `if (e.repeat) return;` guard in `WorkspaceTaskItem.tsx` line 38 `handleKeyDown` (fixes test L145 and contract).
- [x] **A-8**: Corrected Step 5 test targeting: line 406 whitespace test clicks Global at L411; added new dedicated test for dropdown absence in 'mine' scope.
- [x] **A-9**: Added `disabled={!text}` and `<span className="sr-only" aria-live="polite">` screen reader announcement to `CopyButton.tsx`.
- [x] **A-10**: Added `afterEach` test cleanup (`vi.unstubAllGlobals()`, `vi.useRealTimers()`) to Step 2.
- [x] **A-11**: Added concrete `selectedProject` reset at line 174 of `WorkspaceSessionsHub.tsx`.
- [x] **A-12**: Normalized all file paths to `BlackBoard/ui/src/...`.
- [x] **A-13**: Added "Waiting for Approval" accordion section to `WorkspaceSessionsHub.tsx` (partition `waitingApprovalTasks`, amber `AlertCircle` header, count badge, default expanded) in Global View and when present in personal tasks.
- [x] **A-14**: Rewrote Step 5 new test snippet using real file helpers (`ctxEvent`, `asQuery`) with context nested under `evidence.gitlab_context.project`.
- [x] **A-15**: Corrected Step 5 test description labels (L377: context project derivation; L396: evidence.project precedence).
- [x] **A-16**: Added concrete Event ID row JSX inside `{isOverviewOpen && (...)}` in Step 7 (`WorkspaceInspector.tsx`).
- [x] **A-17**: Added surviving test audit notes to Steps 6, 7, and 8 confirming un-mocked suites (`workspace-header`, `workspace-center-stage`, `workspace-inspector`) remain green.
- [x] **A-18**: Specified `execCommand` spy and `vi.waitFor` microtask flush mechanics in Step 2.
- [x] **A-19**: Corrected Step 4 `lucide-react` import to preserve `User`, `Globe`, `Filter` and omit unused icons, preventing `tsc -b` build failures.
- [x] **A-20**: Nested new Waiting for Approval tests inside `describe('WorkspaceSessionsHub (Left Sidebar)')` adjacent to line 210 to inherit top-level `beforeEach` mocks.
- [x] **A-21**: Added JSDOM clipboard stubbing (`vi.stubGlobal('navigator', ...)`) and `afterEach` teardown to `workspace-task-item.test.tsx` (Step 10).
- [x] **A-22**: Clarified `await Promise.resolve()` microtask flush before fake timer advancement in Step 2.

---

## 6. Gating Decision

**Verdict**: **READY FOR EXECUTION (93% >= 90% Soft Gate)**  
All 22 pre-flight amendments have been verified and reconciled into `BlackBoard/.plan.md`. Zero critical blockers remain. The plan is fully ready for execution via `/execute-plan`.
