# Open MR Outcome: Unified Actor Bubble Cards and Left-Aligned User Chat (VMER-2317)

**Date:** 2026-11-10  
**Jira Task:** [VMER-2317](https://redhat.atlassian.net/browse/VMER-2317) under Epic [VMER-62](https://redhat.atlassian.net/browse/VMER-62)  
**Pull Request:** [#318](https://github.com/The-Darwin-Project/Blackboard/pull/318) (`The-Darwin-Project/Blackboard`)  
**Target Branch:** `main`  
**State:** `MERGED`  
**Merge Commit:** `e8be120d696236e2c8bee62dc332460919ce43a2`  
**Merged At:** 2026-11-10T12:28:11Z  

---

## 1. Summary of Changes Shipped
- **Left-Aligned User Chat (`TurnBubble.tsx`)**: Removed `marginLeft: 'auto'`, `textAlign: 'right'`, and right accent borders for human user turns; unified all conversation turns into left-aligned actor cards with 3px color-coded left borders.
- **Card Enclosure Styling (`TurnBubble.tsx` & `ReportTurnCard.tsx`)**: Applied `rgba(15, 23, 42, 0.55)` background, `1px solid rgba(51, 65, 85, 0.4)` border, `8px` border radius, and subtle box-shadows.
- **Actor Label Normalization (`ReportTurnCard.tsx` & `colors.ts`)**: Added `user: 'User'` to `ACTOR_LABELS` and mapped all raw persona tags through `ACTOR_LABELS`.
- **Horizontal Overflow Guards**: Added `overflowX: 'auto'` to all `MarkdownPreview` and code block containers.
- **Delivery Status Check Receipt Gating**: Status checks (`✓`, `✓✓`, `✓✓●`) are gated strictly to human user turns (`{isHuman && <StatusCheck status={turn.status} />}`).
- **Comprehensive Farley ATDD Test Suite**:
  - `TurnBubble.test.tsx`: 45 acceptance test scenarios (T-1 to T-17d) covering alignments, actor card borders, approval modals, and badges.
  - `ReportTurnCard.test.tsx`: 13 test scenarios covering styling parity, actor normalization, and overflow guards.

---

## 2. Review & CI Verification Trail

| Phase | Runner | Verdict / Result |
| :--- | :--- | :--- |
| **Local Pre-Commit** | Vitest | 45 test files / 764 unit tests passed |
| **Local Build** | `tsc -b && vite build` | 5,205 modules transformed; build passed cleanly |
| **CI / Helm Lint** | GitHub Actions | PASSED (6s) |
| **CI / UI Build + Lint** | GitHub Actions | PASSED (1m08s) |
| **CI / Python Tests** | GitHub Actions | PASSED (3m40s) |
| **CI / Container Build** | GitHub Actions | PASSED (2m12s) |
| **AI Code Review** | `gitops-ci-reviewer` (`ai-review`) | `## ✅ AI Code Review: PASSED` (0 HIGH) |
| **Darwin Review** | `darwin-project-ai[bot]` (`evt-2aae6f01`) | **APPROVED / READY FOR MAINTAINER SQUASH-MERGE** (6-lens review + in-branch test remediation commit `6567e471` adding 49 tests + mutation check killing 31/34 mutants) |
| **Merge Action** | Maintainer Squash-Merge | PR #318 squashed and merged into `main` |

---

## 3. Artifact Reference
- Plan: `~/.cursor/plans/ui-actor-bubble-cards-2026-11-10.plan.md`
- Code Review: `BlackBoard/VMER-2317-Code_Review_20261110.md`
- Execution Outcome: `BlackBoard/VMER-2317-execution-outcome_20261110.md`
- Merge Commit: [`e8be120d696236e2c8bee62dc332460919ce43a2`](https://github.com/The-Darwin-Project/Blackboard/commit/e8be120d696236e2c8bee62dc332460919ce43a2)
