# Code Review Report: VMER-2208

**Date**: 2026-11-01 17:22  
**Target Branch**: `feat/user-facing-squad-dispatcher-vmer-2102-2103`  
**Jira Issue**: [VMER-2208](https://redhat.atlassian.net/browse/VMER-2208)  
**Execution Outcome**: `BlackBoard/VMER-2208-execution-outcome_20261101.md`  
**Risk Level**: **MEDIUM** (Critical data source bug identified by R2 + A11y/DOM touch findings by R1/C6/C9)  
**Recommendation**: **CHANGES REQUIRED (Fix in-session before `/open-mr`)**

---

### 1. Review Panel & Triage

| Slot | Lens / Reviewer | Status | High | Med | Low | Flagged Scope |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R1** | Principal System Architect (Claude CLI) | Complete | 0 | 1 | 7 | Nested controls, double-copy, textarea leak, tests |
| **R2** | Correctness Reviewer (Subagent) | Complete | 1 | 1 | 3 | Data source missing hook, Space preventDefault, py-0.2 |
| **R3** | Maintainability Reviewer (Subagent) | Complete | 0 | 1 | 4 | Hardcoded strings, line 1 headers, comments |
| **R4** | Plan Alignment Reviewer (Subagent) | Complete | 0 | 0 | 0 | 100% plan fidelity, 11/11 tasks verified |
| **R5** | Security Diff Reviewer (Subagent) | Complete | 0 | 0 | 2 | Text sanitization, readonly fallback textarea |
| **R6** | Security Sentinel (Subagent) | Complete | 0 | 1 | 0 | Orphaned textarea in fallback catch |
| **C1** | Testing Reviewer / TDD Gate (Subagent) | Complete | 1 | 2 | 2 | Scope test gap, missing approval & space tests, mocks |
| **C6** | Adversarial Reviewer (Claude CLI) | Complete | 0 | 3 | 4 | Touch dead-zone, untracked select-none, double-copy |
| **C9** | Frontend Races Reviewer (Subagent) | Complete | 0 | 2 | 1 | Unmount race condition, DOM textarea leak |
| **C12** | Project Standards Reviewer (Subagent) | Complete | 0 | 0 | 1 | Line 1 header, strict TS / verbatimModuleSyntax |

---

### 2. Consolidated Findings (Pessimistic Merge)

| ID | Severity | File(s) | Description | Reviewer(s) | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **H1** | **HIGH** | `WorkspaceSessionsHub.tsx` | `waitingApprovalTasks` is partitioned exclusively out of `rawActiveEvents` (`useActiveEvents()`). On Darwin backend, parked events move to `EVENT_WAITING_APPROVAL` (served by `useWaitingApprovalEvents()`). Result: folder is always empty, and active events parked for approval are wrongfully evicted to `/workspace`. | R2 | Import and call `useWaitingApprovalEvents()`, include in `allCurrentRawIds` and `availableProjects`, bypass eviction when fetching waiting events, and derive `waitingApprovalTasks` from `rawWaitingApprovalEvents`. |
| **H2** | **HIGH** | `workspace-sessions-hub.test.tsx` | Test at L460 asserts project selector is hidden when no events carry projects, but stayed in default 'My Tasks' scope where it's always hidden anyway, rather than clicking Global. | C1 | Click Global toggle (`fireEvent.click(screen.getByRole('button', { name: /Global/i }))`) before asserting selector absence. |
| **M1** | **MEDIUM** | `WorkspaceTaskItem.tsx` | Nested interactive `<button>` inside `<div role="button">` creates ARIA antipattern and dead-zone on touch devices (`opacity-0` still intercepts pointer events). Non-unique labels across list items. | R1, C6 | Add `pointer-events-none` when hidden (`group-hover:pointer-events-auto`, `group-focus-within:pointer-events-auto`). Disambiguate label with `Copy Event ID (${evt.id})`. |
| **M2** | **MEDIUM** | `CopyButton.tsx` | Native `<button>` synthesizes `click` on Enter and Space. `onKeyDown` also calling `handleCopy()` causes double-copy. Space keydown without `preventDefault()` causes page scroll. | R1, R2, C6, C9 | In `handleKeyDown`, prevent default on Space: `if (e.key === ' ') e.preventDefault(); e.stopPropagation();` and remove redundant `handleCopy()` call on keydown. |
| **M3** | **MEDIUM** | `CopyButton.tsx` | Hidden `<textarea>` fallback node is removed inside `try`, leaking into `document.body` if `select()` or `execCommand()` throws. | R1, R5, R6, C9 | Wrap node removal in a `finally` block and set `readOnly`, `tabIndex = -1`, `aria-hidden = 'true'`, and `pointerEvents = 'none'`. |
| **M4** | **MEDIUM** | `CopyButton.tsx` | Unmount race condition: resolving promise from `navigator.clipboard.writeText` after component unmount triggers state update on unmounted component. | C9 | Add `mountedRef` guard before calling `triggerCopySuccess()`. |
| **M5** | **MEDIUM** | `workspace-sessions-hub.test.tsx` | Missing test coverage for "Waiting for Approval" folder in 'My Tasks' view when personal tasks have `status: 'waiting_approval'`. | C1 | Add unit tests asserting folder appears in 'My Tasks' when personal pending approvals exist, and hides when empty. |
| **M6** | **MEDIUM** | `WorkspaceLayout.tsx`, test suite | Core Problem 3 fix (`select-none` removal) has zero test assertions in `workspace-layout.test.tsx`. | C6 | Add unit test verifying `WorkspaceLayout` root element does not contain `select-none`. |
| **L1** | **LOW** | `CopyButton.tsx` | Hardcoded `'Copied Event ID'` overrides custom `label` in `aria-label` and `aria-live`. | R2, R3 | Dynamically derive `currentLabel` from `label`. |
| **L2** | **LOW** | `CopyButton.tsx` | Sanitization: raw text written to clipboard without stripping terminal escape or CRLF characters. | R5 | Sanitize text: `text.replace(/[\r\n\x1b]/g, '')`. |
| **L3** | **LOW** | `WorkspaceSessionsHub.tsx`, `WorkspaceInspector.tsx` | Invalid Tailwind utility class `py-0.2` on count badges. | R1, R2 | Replace with `py-0.5`. |
| **L4** | **LOW** | `WorkspaceSessionsHub.tsx` | Rule 5 in `@ai-rules` header does not mention `waitingApprovalTasks`; section comments duplicated (`2. Active`, `2. Deferred`). Defensive `!evt` check in `deriveProject`. | R1, R2, R3 | Update header Rule 5, renumber comments (1..4), add defensive check in `deriveProject`. |
| **L5** | **LOW** | `copy-button.test.tsx`, `workspace-sessions-hub.test.tsx` | Missing line 1 header in `copy-button.test.tsx`; missing mock cleanup (`delete (document as any).execCommand` and `vi.restoreAllMocks()`). | R3, C1, C12 | Add header and cleanup in `afterEach`. |
| **L6** | **LOW** | `WorkspaceHeader.tsx` | File length is 104 lines; exceeds 100-line guideline. | R3 | Streamline agent dedup filter to bring under 100 lines. |
| **L7** | **LOW** | `WorkspaceInspector.tsx` | Missing `title={eventDoc.id}` tooltip on truncated Event ID row. | R1, C6 | Restore `title={eventDoc.id}` on Event ID span. |

---

### 3. Verdict & Path to Green

Per team guidelines, **Zero Technical Debt Deferred**: all findings H1-H2, M1-M6, and L1-L7 will be resolved directly in the codebase in this session, followed by clean verification (`npm test` and `npm run build`), before requesting user confirmation for git commit and `/open-mr`.
