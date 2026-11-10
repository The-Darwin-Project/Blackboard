# Pre-Flight Review: VMER-2208 Darwin Agent Workspace Scoping & Visibility Parity (Round 1)

**Timestamp:** 2026-10-29T10:48:00+02:00  
**Overall Confidence:** **62%** (Pessimistic Merge: Minimum across auditors)  
**Status:** **Stop** (<70% or critical blockers)  
**Evaluator Panel:**
- **Auditor A** (Architecture, Contracts & State): **62%** (Stop)
- **Auditor B** (Correctness, Edge Cases & Eviction Guard): **82%** (Caution)
- **Auditor C** (UI/UX, Performance & Test Coverage): **78%** (Caution)

---

## 1. Executive Verdict & Critical Findings

While the design direction is strongly validated, the panel identified **4 critical architectural blockers** that would cause execution failure or runtime regressions if not incorporated into the plan:

1. **Global WebSocket Deselection in `OpsStateContext.tsx`**:
   `OpsStateContext.tsx` has an explicit handler on `event_closed` that immediately zeroes out `selectedEventId = null` in global state and removes it from `sessionStorage`. Any workspace user viewing an active task when it completes would be forcefully kicked out to `/workspace` at the global state level, regardless of local eviction logic in `WorkspaceSessionsHub`.
2. **OIDC Auth Identity Contract Mismatch**:
   The plan specifies `user.email`. `oidc-client-ts` stores standard claims on `user.profile.email` (or `preferred_username`). Evaluating `user?.email` yields `undefined`, breaking "My Workspace" filtering.
3. **Missing Properties on TypeScript Interfaces (`types.ts`)**:
   `ActiveEvent` in `ui/src/api/types.ts` does not declare `created_by_email` or `current_agent`, and `EventEvidence` does not declare `project`. The TypeScript build (`tsc -b`) will fail.
4. **React Query Key Collision & Data Layer Fragmentation**:
   `EventSidebar.tsx` queries `['closedEvents']` with limit 20 every 10s. The plan proposed querying bare `['closedEvents']` with limit 50 every 15s in the component. TanStack Query will collide on the key and overwrite array limits. `useQueue.ts` needs a shared, parameterized `useClosedEvents(limit = 50)` with query key `['closedEvents', limit]`.
5. **Interactive A11y DOM Nesting & Missing Helper Export**:
   `WorkspaceTaskItem` is a `<button>`. Nesting `<DeferCountdownBar>` (which has `role="progressbar"` and interactive states) inside a `<button>` violates HTML5/a11y standards. Also, `relativeAge` is currently an unexported private helper in `TreePrimitives.tsx`.

---

## 2. Auditor Scores & Cynefin Breakdown

| Task ID | Description | Cynefin | Score | Blockers / Risks |
| :--- | :--- | :---: | :---: | :--- |
| **step-1-task-item-parity** | Visibility parity in `WorkspaceTaskItem` | Complicated | 80% | `ActiveEvent` lacks `current_agent`; `<button>` nesting violation with `DeferCountdownBar`; `relativeAge` unexported. |
| **step-2-sessions-hub-folders** | Scoping, Project filter & Accordion Folders | Complex | 65% | `user.profile.email` vs `user.email`; missing `useClosedEvents(limit)` hook; Closed folder must default collapsed. |
| **step-3-query-and-eviction-guard** | Query integration & Eviction Guard | Complex | 45% | **Critical Blocker**: `OpsStateContext` forces `selectedEventId = null` on WS `event_closed`; hydration race between WS removal and REST closed poll. |
| **step-4-unit-and-integration-tests** | Unit test suite expansion | Complicated | 80% | Existing tests assert eviction on event close; must update to reflect closed task retention and mock `useAuth`. |
| **step-5-build-and-lint-verification** | Build & lint verification | Clear | 90% | Will succeed once type contracts and helper exports are in place. |

---

## 3. Path to Green (Amendment Ledger for Update-Plan)

1. **Update Target Files**: Include `BlackBoard/ui/src/contexts/OpsStateContext.tsx`, `BlackBoard/ui/src/hooks/useQueue.ts`, and `BlackBoard/ui/src/api/types.ts`.
2. **Extend Types in `api/types.ts`**:
   - Add `created_by_email?: string | null` and `current_agent?: string | null` to `ActiveEvent`.
   - Add `project?: string | null` to `EventEvidence`.
3. **Export `relativeAge` Utility**:
   - Export `relativeAge` from `TreePrimitives.tsx` (or extract to `utils/date.ts`).
4. **Centralize `useClosedEvents` in `hooks/useQueue.ts`**:
   - Provide `useClosedEvents(limit = 50)` with query key `['closedEvents', limit]`.
   - Update `useQueueInvalidation` to invalidate `['closedEvents']` (prefix match).
5. **Harmonize `OpsStateContext` & Eviction Guard**:
   - In `OpsStateContext.tsx`, do NOT clear `selectedEventId` on `event_closed` if the user is in `/workspace` route or browsing the event document.
   - In `WorkspaceSessionsHub.tsx`, verify that eviction only fires if an event is neither in active nor closed lists AND both `!isFetchingActive && !isFetchingClosed`.
6. **Correct OIDC Auth Extraction**:
   - `const userEmail = user?.profile?.email || (user?.profile as Record<string, unknown>)?.preferred_username;`
7. **Fix Task Item HTML Semantics & Folder Defaults**:
   - Use `<div role="button" tabIndex={0} onKeyDown={...}>` in `WorkspaceTaskItem` for safe nesting of `DeferCountdownBar`.
   - Default **Closed & Failed** accordion to collapsed (`false`).
