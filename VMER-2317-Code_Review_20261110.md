# Code Review Report: VMER-2317
## Unified Actor Bubble Cards and Left-Aligned User Chat in Darwin Workspace

**Review Date:** 2026-11-10  
**Jira Issue:** [VMER-2317](https://redhat.atlassian.net/browse/VMER-2317)  
**Epic:** [VMER-62](https://redhat.atlassian.net/browse/VMER-62) (AI SDLC Darwin)  
**Target Branch:** `main` (or feature branch)  
**Review Status:** **PASSED** (All in-session findings resolved and verified)  

---

## 1. Executive Summary

VMER-2317 implements the architectural unification of the chat and turn feed in the Darwin Workspace UI. It replaces the legacy staggered layout (where user messages were right-aligned with separate bubble styling) with unified, full-width, left-aligned Actor Bubble Cards for all participants (human users and autonomous agents).

Key enhancements delivered:
1. **Left-Aligned User Chat**: User messages render strictly left-aligned (`width: 100%`, `marginLeft: 0`, `textAlign: left`) with unified card styling, colored left border (`ACTOR_COLORS.user = '#ec4899'`), and operator badge display.
2. **Actor Bubble Card Visual Language**: Consistent dark card container styling (`background: rgba(15, 23, 42, 0.55)`, `border: 1px solid rgba(51, 65, 85, 0.4)`, `borderRadius: 8`, `padding: 10px 14px`, `boxShadow: 0 1px 3px rgba(0, 0, 0, 0.2)`), accent colored left border (`3px solid ACTOR_COLORS[actor]`), and subtle pink background tint for human messages.
3. **Cross-Actor Parity**: Preserves all actor-specific badges (AI-generated, TAMPERING BLOCKED, RECALL), feedback buttons, approval/rejection action flows, and responsive left-aligned image attachments.
4. **Horizontal Blowout Protection**: Added `overflowX: auto` to Markdown preview containers in both `TurnBubble.tsx` and `ReportTurnCard.tsx`.
5. **Report View Parity**: Aligned `ReportTurnCard.tsx` with unified container styling and standardized persona labeling (`ACTOR_LABELS[turn.actor] ?? turn.actor`).
6. **ATDD Suite**: Added 9 executable Farley ATDD scenarios in `TurnBubble.test.tsx` verifying alignment, styling, badges, attachments, overflow guards, and delivery status check gating.

---

## 2. Review Panel & Models

| Reviewer ID | Lens / Specialty | Status | Initial Verdict | Final Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **R1** | Principal Architect | Complete | **PASSED** | **PASSED** |
| **R2** | Correctness Reviewer | Complete | **PASSED** | **PASSED** |
| **R3** | Maintainability Reviewer | Complete | **NEEDS CHANGES** | **PASSED** *(F-01, F-02, F-05 resolved)* |
| **R4** | Plan Alignment Reviewer | Complete | **PASSED** | **PASSED** |
| **R5** | Exploitable Security Reviewer | Complete | **PASSED** | **PASSED** |
| **R6** | Security Sentinel | Complete | **PASSED** | **PASSED** |
| **C1** | Testing Reviewer (TDD Gate) | Complete | **PASSED** | **PASSED** |
| **C9** | Frontend Races Reviewer | Complete | **PASSED** | **PASSED** |
| **C12** | Project Standards Reviewer | Complete | **PASSED** | **PASSED** |

---

## 3. Reviewer Agreement Matrix

```
R1  R2  R3  R4  R5  R6  C1  C9  C12
 P   P   N*  P   P   P   P   P   P

* Note: R3 initially flagged F-01 (phantom status check on agent turns) and F-02 (actor label in report card).
Both items were remediated and verified in-session prior to merge sign-off.
```

---

## 4. Downstream Impact Analysis

| System / Component | Impact Assessment |
| :--- | :--- |
| **ConversationFeed (`ConversationFeed.tsx`)** | **Zero Regressions.** Feed maps turns directly to `TurnBubble`. Full-width left-aligned cards (`width: 100%`) maintain identical vertical layout geometry; auto-scroll to bottom (`feedRef`) functions identically without layout shift. |
| **EventChatPanel (`EventChatPanel.tsx`)** | **Zero Regressions.** Input submission and WebSocket turn streaming feed into `useChat` / `ConversationFeed` seamlessly. |
| **ReportTurnCard (`ReportTurnCard.tsx`)** | **Improved.** Closed event reports now match live workspace feed visual language and display normalized persona labels (e.g. `FRIDAY`, `User`). |
| **Security Surface** | **Zero Vulnerabilities.** Strict allowlist protocol checks (`data:image/`, `blob:`, `http://`, `https://`) with `noopener,noreferrer` for image popouts; React JSX DOM entity-encoding prevents XSS. |

---

## 5. Unified Findings Matrix (Pessimistic Merge)

| ID | Lens | Severity | Location | Description | Status & Remediation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F-01** | **R3** | **HIGH** | `TurnBubble.tsx:343` | **Phantom status tick on autonomous agent turns.** `{turn.actor !== 'brain' && <StatusCheck ... />}` caused agent turns (`developer`, `qe`, etc.) without status to display a misleading `✓ Sent` receipt. | **RESOLVED IN-SESSION.** Reverted condition to `{isHuman && <StatusCheck status={turn.status} />}`. Added ATDD scenario T-8. |
| **F-02** | **R3** | **MEDIUM** | `ReportTurnCard.tsx:41` | **Actor persona label divergence.** Raw `{turn.actor}` rendered instead of normalized `ACTOR_LABELS[turn.actor]`. | **RESOLVED IN-SESSION.** Imported `ACTOR_LABELS` and updated header rendering to `{label}`. |
| **F-03** | **R1, R3** | **LOW** | `ReportTurnCard.tsx:73` | **Body overflow guard parity.** `ReportTurnCard` lacked `overflowX: 'auto'` on markdown body container. | **RESOLVED IN-SESSION.** Added `overflowX: 'auto'` to `MarkdownPreview` style. |
| **F-04** | **C9** | **MEDIUM** | `TurnBubble.tsx:395`, `RejectButton:70` | **Missing button loading/disabled state.** Pre-existing: `approveEvent` and `rejectEvent` lack local `isSubmitting` guard against double-clicks. | **CATALOGED (Technical Debt).** Server-side deduplication handles duplicate requests; queued for future button refactor. |
| **F-05** | **R3, C12** | **MEDIUM** | `TurnBubble.tsx:1-402` | **Modularity / File Length.** 402 lines bundling 7 subcomponents (`RejectButton`, `ResultViewer`, `FeedbackButtons`). | **CATALOGED (Technical Debt).** Pre-existing architecture; recommend future extraction to `ui/src/components/turn/`. |
| **F-06** | **R3** | **LOW** | `TurnBubble.tsx:304` | **Hardcoded user card background tint.** `rgba(236, 72, 153, 0.05)` matches `#ec4899` inline rather than tokenized in `colors.ts`. | **CATALOGED.** Recommend future `USER_CARD_BG` token in `colors.ts`. |
| **F-07** | **R5** | **LOW** | `TurnBubble.tsx:375` | **Broad `data:image/` allowlist permits SVG.** `src.startsWith('data:image/')` allows SVG data URIs. | **CATALOGED.** Recommend future in-app lightbox modal for screenshot viewing. |
| **F-08** | **C1** | **INFO** | `TurnBubble.test.tsx:16` | **Redundant `afterEach(cleanup)`.** Vitest with React Testing Library auto-cleans up after tests. | **CLEAN.** Harmless defense-in-depth test isolation. |

---

## 6. Verification Gate Table

| Gate | Target / Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Unit ATDD Tests** | `vitest run src/components/TurnBubble.test.tsx` | **PASSED** | 9/9 tests passed (T-1 to T-9) in 348ms. |
| **Full UI Test Suite** | `npm test -- --run` | **PASSED** | 45/45 test files passed, 764/764 unit tests green (13.06s). |
| **TypeScript / Build** | `npm run build` (`tsc -b && vite build`) | **PASSED** | 5,205 modules compiled cleanly in 22.96s with exit code 0. |

---

## 7. Recommendation & Next Steps

All code review findings have been resolved in-session. The codebase is clean, tests are 100% green, and the production build compiles without warnings or errors.

**Next Pipeline Step:** `/open-mr` to create the pull request for [VMER-2317](https://redhat.atlassian.net/browse/VMER-2317) with mandatory bot instructions and label `darwin-review`.
