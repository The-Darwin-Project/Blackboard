# Pre-Flight Review: VMER-2208 Darwin Agent Workspace Scoping & Visibility Parity (Round 2)

**Timestamp:** 2026-10-29T10:52:00+02:00  
**Overall Confidence:** **94%** (Pessimistic Merge: Minimum across auditors)  
**Status:** **Ready** (>=90% and no blockers)  
**Evaluator Panel:**
- **Auditor A (Rev 2)** (Architecture, Contracts & State): **96%** (Ready)
- **Auditor B (Rev 2)** (Correctness, Edge Cases & Eviction Guard): **95%** (Ready)
- **Auditor C (Rev 2)** (UI/UX, Performance & Test Coverage): **94%** (Ready)

---

## 1. Executive Verdict & Validation

All 6 architectural and implementation gaps identified in Round 1 have been completely resolved and verified in Revision 2:
1. **TypeScript Contracts**: `ActiveEvent` extended with `created_by_email` and `current_agent`; `EventEvidence` extended with `project`.
2. **OIDC Claims Path**: Safe resolution of `user.profile.email` (or `preferred_username`) with null-safety.
3. **Data Layer**: Centralized `useClosedEvents(limit = 50)` hook with query key `['closedEvents', limit]` preventing cache collision with the 20-item operational sidebar.
4. **WebSocket State Harmony**: `OpsStateContext` prevents auto-deselection of `selectedEventId` on `event_closed` while in workspace inspection mode.
5. **Robust Eviction Guard**: Checks raw unfiltered arrays, waits on `isFetchingActive || isFetchingClosed`, and seamlessly bridges the active-to-closed lifecycle transition.
6. **A11y DOM Semantics**: Task items use `<div role="button" tabIndex={0} onKeyDown={...}>` to avoid HTML5 `<button>` nesting violations with `<DeferCountdownBar>`.
7. **Folder Ergonomics**: "Closed & Failed" accordion defaults to collapsed, preserving viewport space for active work.

---

## 2. Auditor Scores & Cynefin Breakdown

| Task ID | Description | Cynefin | Score | Status |
| :--- | :--- | :---: | :---: | :---: |
| **step-1-contract-and-types** | Update `types.ts` & export `relativeAge` | Clear | 98% | Ready |
| **step-2-shared-query-hooks** | Parameterized `useClosedEvents` hook | Clear | 96% | Ready |
| **step-3-task-item-parity** | Parity badges, status dot & countdown bar in `WorkspaceTaskItem` | Complicated | 95% | Ready |
| **step-4-ops-state-context-ws-harmony** | Route-aware selection retention in `OpsStateContext` | Complicated | 93% | Ready |
| **step-5-sessions-hub-folders-and-eviction** | Scoping, Project filter, Folders & Eviction Guard in `WorkspaceSessionsHub` | Complicated | 94% | Ready |
| **step-6-unit-and-integration-tests** | Comprehensive Vitest coverage | Complicated | 95% | Ready |
| **step-7-build-and-lint-verification** | `tsc -b` and production bundle verification | Clear | 98% | Ready |

---

## 3. Path to Execution
The plan is converged and meets the **>=90% soft gate**. Ready to proceed to `/execute-plan`.
