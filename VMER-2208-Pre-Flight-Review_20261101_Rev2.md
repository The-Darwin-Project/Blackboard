# Pre-Flight Review: VMER-2208 (Round 2)

**Date**: 2026-11-01  
**Target Plan**: `BlackBoard/.plan.md`  
**Jira Issue**: [VMER-2208](https://redhat.atlassian.net/browse/VMER-2208)  
**Evaluators**:
- **Auditor A** (Cynefin & Architecture Depth): 98% (Ready)
- **Auditor B** (Gaps, Completeness & Testability): 100% (Ready)
- **Auditor C** (Contracts, A11y & Failure Modes via Claude CLI Reviewer): 82% (Caution)

---

## 1. Confidence Dashboard

| Metric | Value |
| :--- | :--- |
| **Overall Confidence** | **82%** (Pessimistic Minimum: Auditor C) |
| **Delta from Round 1** | **+8%** (74% → 82%, positive convergence trend) |
| **Status** | **Caution (Not Ready for Execution)** |
| **Soft Gate** | ≥ 90% (Requires Round 3 convergence) |
| **Critical Blockers** | 1. **HIGH-1 (Step 5 / L406)**: Line 406 in `workspace-sessions-hub.test.tsx` tests whitespace-trim matching and calls `screen.getByLabelText(/filter by project/i)` at L412; it must click Global first (not be replaced with a scope test). Add the "dropdown absent in mine" check as a separate test.<br/>2. **HIGH-2 (Step 9 / L38)**: Replacement `handleKeyDown` in `WorkspaceTaskItem.tsx` dropped the `if (e.repeat) return;` guard, which would break test L145 and violate component contract. |

---

## 2. Auditor Agreement Matrix

| Step | Task Summary | Auditor A | Auditor B | Auditor C | Min Confidence | Status / Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Create `CopyButton.tsx` Component | 98% | 100% | 86% | **86%** | Add `sr-only` live region and `!text` disabled/no-op behavior. |
| **2** | Unit Tests for `CopyButton` | 95% | 100% | 85% | **85%** | Add `afterEach` cleanup (`vi.unstubAllGlobals()`, `vi.useRealTimers()`). |
| **3** | Remove `select-none` from Layout & Asides | 100% | 100% | 98% | **98%** | Consensus: Verified safe. |
| **4** | Fix Project Dropdown Scoping, Labeling & Matching | 98% | 100% | 92% | **92%** | Specify concrete `onClick={() => { setScope('mine'); setSelectedProject('all'); }}` at L174. |
| **5** | Update `workspace-sessions-hub.test.tsx` | 95% | 100% | 55% | **55%** | **Blocker**: Patch L406 whitespace test to click Global; add scope absence as new test. |
| **6** | Add Copy Affordance in `WorkspaceCenterStage.tsx` | 98% | 100% | 95% | **95%** | Consensus: Ready. |
| **7** | Add Event ID Row with Copy Affordance in `WorkspaceInspector.tsx` | 98% | 100% | 90% | **90%** | Ready; verified safe with `eventDoc`. |
| **8** | Add Copy Affordance in `WorkspaceHeader.tsx` | 98% | 100% | 92% | **92%** | Ready; null-guard and `flex-shrink-0` specified. |
| **9** | Add Hover/Focus Copy Affordance in `WorkspaceTaskItem.tsx` | 98% | 100% | 55% | **55%** | **Blocker**: Retain `if (e.repeat) return;` alongside target check; use `KeyboardEvent<HTMLDivElement>`. |
| **10** | Disambiguate Button Selectors in TaskItem Tests | 98% | 100% | 90% | **90%** | Ready; verified `getAllByRole('button')[0]` targets card. |
| **11** | Full Regression Verification | 98% | 100% | 70% | **70%** | Gated on Steps 5 and 9 fixes. |

---

## 3. Path to Green (Round 2 Amendments)

1. **[BLOCKER 1] Step 9 Keydown Guard & Typing**:
   - In `BlackBoard/ui/src/components/workspace/WorkspaceTaskItem.tsx` (handler at line 38):
     ```ts
     const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
       if (e.target !== e.currentTarget) return;
       if (e.repeat) return;
       if (e.key === 'Enter' || e.key === ' ') {
         e.preventDefault();
         onSelect(evt.id);
       }
     };
     ```
   - Retaining `if (e.repeat) return;` prevents regression on test L145.
   - Document WCAG 4.1.2 nested interactive tradeoff: Row is `div[role="button"]` and CopyButton is `<button>`. Strict event propagation (`e.stopPropagation()` on click/keydown + `e.target !== e.currentTarget` on row) provides 100% behavioral and keyboard isolation.
2. **[BLOCKER 2] Step 5 Test Updates**:
   - In `BlackBoard/ui/src/components/workspace/__tests__/workspace-sessions-hub.test.tsx`:
     - Line 377 (`filters active events by selected project`): Prepend `fireEvent.click(screen.getByRole('button', { name: /Global/i }))`.
     - Line 396 (`clears project filter when 'all' is re-selected`): Prepend `fireEvent.click(screen.getByRole('button', { name: /Global/i }))`.
     - Line 406 (`matches events whose project has surrounding whitespace`): Prepend `fireEvent.click(screen.getByRole('button', { name: /Global/i }))` after its render at L411.
     - Add a separate, dedicated test: `it('does not render project dropdown when scope is mine', ...)` asserting `expect(screen.queryByLabelText(/filter by project/i)).toBeNull()`.
     - Line 420 (`hides selector when no projects available`): Switch to Global scope and verify selector is absent.
3. **[REFINEMENT 3] Step 1 CopyButton A11y & Robustness**:
   - If `!text`, render disabled `<button disabled ...>`.
   - Screen reader announcement: Add `<span className="sr-only" aria-live="polite">{copied ? 'Copied Event ID' : ''}</span>` inside button (and remove `aria-live` on button itself).
4. **[REFINEMENT 4] Step 2 Test Harness Cleanup**:
   - In `copy-button.test.tsx`: Add `afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });`.
   - Add spy for `document.execCommand` when testing fallback.
5. **[REFINEMENT 5] Step 4 Concrete Scope Reset**:
   - In `WorkspaceSessionsHub.tsx` L174: Update "My Tasks" button to `onClick={() => { setScope('mine'); setSelectedProject('all'); }}`.
6. **[PATH CONSISTENCY]**:
   - Normalize all file paths in steps to `BlackBoard/ui/src/...`.
