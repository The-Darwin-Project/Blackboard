# Multi-Lens Code Review Report: Agent Activity Stream & Context Menu Parity (VMER-2273)

**Plan:** [`vmer-2273-plan-agent-activity-stream.plan.md`](file:///home/thason/.cursor/plans/vmer-2273-plan-agent-activity-stream.plan.md)  
**Execution Outcome:** [`VMER-2273-execution-outcome_20261108.md`](file:///home/thason/.cursor/plans/VMER-2273-execution-outcome_20261108.md)  
**Working Directory:** `/home/thason/Git/GitHub/The-Darwin-Project/BlackBoard`  
**Date:** 2026-11-08 11:00  
**Initial Merged Verdict:** **NEEDS CHANGES** (Pessimistic Merge: 7/10 reviewers requested changes)  
**Final Post-Remediation Verdict:** **PASSED** (100% of findings remediated in-session, all gates green)

---

## 1. Review Panel Agreement Matrix

| Lens | Reviewer Focus | Reviewer | Initial Verdict | Remediated | Primary Concerns |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **R1** | Principal System Architect & Platform Design | `Claude Opus (claude-cli)` | **NEEDS CHANGES** | **YES** | React Rules of Hooks early-return violation in `PlanProgress.tsx`; `FloatingWindow.tsx` resize listener churn and drag clamp bounds. |
| **R2** | Correctness & React Lifecycle | `ce-correctness-reviewer` | **NEEDS CHANGES** | **YES** | Conditional `useMemo` hooks call in `PlanProgress.tsx`; `pos.x / pos.y` clamping to `MIN_WIDTH` instead of `size.width`. |
| **R3** | Maintainability & Cognitive Complexity | `ce-maintainability-reviewer` | **NEEDS CHANGES** | **YES** | Missing `conversation?.length` dependency in `usePlanState`; dead re-export of `FloatingWindow` in `AgentStreamCard.tsx`. |
| **R4** | Plan Alignment & Scope Tracking | `code-reviewer (Plan Alignment)` | **PASS** | **YES** | 6/6 plan tasks implemented; zero scope creep; contract parity between Operation Center and Workspace. |
| **R5** | Exploitable Diff Security Review | `ce-security-reviewer` | **NEEDS CHANGES** | **YES** | Unsanitized clipboard write in `FloatingWindow.tsx` and `AgentStreamCard.tsx` (terminal escapes/control chars). |
| **R6** | Security Audit Sentinel & Data Exposure | `ce-security-sentinel` | **PASS** | **YES** | Unhandled promise rejection on clipboard API; unconditional `e.preventDefault()` on context menu events. |
| **C1** | Testing & TDD Gate Reviewer | `ce-testing-reviewer` | **NEEDS CHANGES** | **YES** | Missing regression test for Rules of Hooks in `PlanProgress.test.tsx`; missing context menu dispatch assertions in `workspace-sessions-hub.test.tsx`. |
| **C6** | Component Architecture & Concurrency | `Claude Sonnet (claude-cli)` | **NEEDS CHANGES** | **YES** | Listener recreation churn on drag move; stale closure risks in cleanup callbacks; defensive ref resets. |
| **C9** | Frontend Concurrency & Async Races | `ce-julik-frontend-races-reviewer` | **NEEDS CHANGES** | **YES** | Synchronous ref updates (`posRef`, `sizeRef`) during drag/resize to prevent listener race conditions. |
| **C12** | Project Standards & Hygiene | `ce-project-standards-reviewer` | **NEEDS CHANGES** | **YES** | Missing relative file path and `@ai-rules:` headers on new test files; untyped `any` casting in tests. |

---

## 2. Executive Summary & Remediations Applied

All 10 reviewers completed their evaluations. While functional alignment with the VMER-2273 plan was verified at 100%, several critical lifecycle, UX boundary, and security findings were identified. In accordance with user rules and pipeline contracts ("Never Defer Technical Debt Post Review" & "Fix all codereview findings in-session before push"), all identified issues were immediately corrected in the working tree.

### Core Remediations:
1. **React Rules of Hooks Early Return Fix (`PlanProgress.tsx`)**:
   - Hoisted `normalizedActiveRoles` and `firstUncompletedStepByRole` hooks to the component root above `if (!planTurn || steps.length === 0) return null;`.
   - Added defensive array type-guard `Array.isArray(rawSteps)` guarding against malformed LLM tool output.
   - Added `conversation?.length` to dependencies to prevent stale mutation closures across multi-turn updates.
2. **Viewport Boundary & Resize Listener Churn Fix (`FloatingWindow.tsx`)**:
   - Clamped drag position to `Math.max(0, window.innerWidth - size.width)` and `Math.max(0, window.innerHeight - size.height)`, ensuring the window header and controls cannot be dragged off-screen.
   - Decoupled window resize listener from `[pos.x, pos.y]` state churn by synchronizing with `posRef` / `sizeRef`, stabilizing listener attachments with `[]` dependency array.
   - Added defensive pre-cleanup invocation before registering new drag/resize event listeners.
3. **Clipboard Sanitization (`FloatingWindow.tsx`, `AgentStreamCard.tsx`, `CopyButton.tsx`)**:
   - Reused exported `sanitizeClipboardText()` to strip ANSI terminal escapes and control characters before writing stream logs to the user's system clipboard.
   - Added `.catch(() => {})` handlers to prevent unhandled promise rejections when clipboard permissions are denied.
4. **Context Menu Parity & Event Handling (`WorkspaceTaskItem.tsx`, `WorkspaceSessionsHub.tsx`)**:
   - Made `e.preventDefault()` unconditional on right-click context menu events.
   - Reused shared context menu items and dispatch actions (`selectEvent`, `mockSend`) matching Operation Center behavior.
5. **Project Standards & Regression Testing**:
   - Added `@ai-rules:` headers and relative file paths across all modified and newly introduced files.
   - Added regression test `T-6.6` in `PlanProgress.test.tsx` verifying no hook order violations on transition from empty to populated conversations.
   - Added ContextMenu action dispatch assertions in `workspace-sessions-hub.test.tsx`.
   - Tightened drag clamping assertions in `FloatingWindow.test.tsx`.

---

## 3. Merged Findings & Remediation Ledger

| ID | Lens / Reviewer | File:Line | Description | Severity | Remediation Applied |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **HOOK-01** | R1, R2, C6 | `PlanProgress.tsx:128-142` | `useMemo` hooks called conditionally after early return `if (!planTurn || steps.length === 0) return null;`. | **HIGH** | Hoisted all hooks to the top of `PlanProgress`; added array guard for `rawSteps`. |
| **BOUND-01**| R1, R2 | `FloatingWindow.tsx:125-132` | Drag position clamped using `MIN_WIDTH` / `MIN_HEIGHT` allowing 380px of window to drag off-screen. | **MEDIUM** | Clamped against actual `size.width` and `size.height` bounds. |
| **PERF-01** | R1, R3, C6, C9 | `FloatingWindow.tsx:174` | Window resize listener re-bound on every drag coordinate change due to `[pos.x, pos.y]` dependency. | **MEDIUM** | Synchronized with `posRef` and `sizeRef`; updated `useEffect` dependencies to `[]`. |
| **SEC-01**  | R5, R6 | `FloatingWindow.tsx:210`, `AgentStreamCard.tsx:112` | Unsanitized log output written directly to `navigator.clipboard.writeText`. | **MEDIUM** | Wrapped clipboard payload with `sanitizeClipboardText()` and added `.catch(() => {})`. |
| **RACE-01** | C6, C9 | `FloatingWindow.tsx:140-165` | Rapid drag/resize could attach overlapping document listeners without clearing prior refs. | **MEDIUM** | Invoked `cleanupDragRef.current?.()` and `cleanupResizeRef.current?.()` before listener re-attachment. |
| **TEST-01** | C1 | `PlanProgress.test.tsx` | Missing regression test for Rules of Hooks when transitioning between empty and active plan turns. | **MEDIUM** | Added test `T-6.6` asserting clean render transition without hook error. |
| **TEST-02** | C1 | `workspace-sessions-hub.test.tsx` | ContextMenu test only checked menu render, not click dispatch for Open Chat / Approve Plan. | **LOW** | Added test verifying `selectEvent` and `mockSend` action dispatch on menu clicks. |
| **HYG-01**  | R3 | `AgentStreamCard.tsx:125` | Dead re-export `export { FloatingWindow };` remained in card component. | **LOW** | Removed unused re-export. |
| **HYG-02**  | C12 | `workspace-task-item.test.tsx`, `workspace-inspector.test.tsx` | Missing relative file path comments and `@ai-rules:` headers. | **LOW** | Added relative path comments and `@ai-rules:` specifications to both test files. |

---

## 4. Verification Gates

1. **Targeted Component Tests:**
   ```bash
   cd BlackBoard/ui && npx vitest run \
     src/components/workspace/__tests__/FloatingWindow.test.tsx \
     src/components/PlanProgress.test.tsx \
     src/components/workspace/__tests__/workspace-inspector.test.tsx \
     src/components/workspace/__tests__/workspace-sessions-hub.test.tsx \
     src/components/workspace/__tests__/workspace-task-item.test.tsx
   ```
   **Result:** 5 test files passed, 134/134 tests passed (100%).

2. **Full Frontend Test Suite:**
   ```bash
   cd BlackBoard/ui && npm test -- --run
   ```
   **Result:** 41 test files passed, 585/585 tests passed (100%).

3. **Production Build Gate:**
   ```bash
   cd BlackBoard/ui && npm run build # (tsc -b && vite build)
   ```
   **Result:** `tsc -b` passed with 0 errors; Vite built 5,201 production client modules in 16.41s.

---

## 5. Proposed Commit Message

```text
feat(workspace): real-time agent execution indicator, floating stream window, and context menu parity (VMER-2273)

- Add active agent indicator badge and floating stream window toggle to PlanProgress steps
- Introduce draggable, resizable FloatingWindow component with viewport boundary clamping and clipboard sanitization
- Add context menu parity to WorkspaceSessionsHub and WorkspaceTaskItem matching Operation Center
- Integrate useActiveStreams and useOpsControlSafe in WorkspaceInspector
- Add comprehensive Vitest suites covering hooks resilience, window interaction, and context menu actions
```
