# AI Transparency Compliance -- Code Changes Review

**Date:** 2026-02-19 19:00
**Plan:** `ai_transparency_compliance_203ddc78.plan.md`
**Scope:** 21 files (656 insertions, 285 deletions) -- Backend, UI, Helm

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** **Low** -- No breaking API changes. All new endpoints are additive. Component extract is a clean refactor. Feature flag not needed (transparency features are always-on by design).
* **Breaking Changes:** None. ConversationFeed component extract preserves identical behavior and import contract (TurnBubble + StatusBadge exported).

---

## 2. Downstream Impact Analysis

| Consumer | Impact | Risk |
|----------|--------|------|
| `ConversationFeed.tsx` | Now imports TurnBubble + StatusBadge from `./TurnBubble` and MarkdownViewer from `./MarkdownViewer` | **None** -- verified in diff |
| `Layout.tsx` | Now imports `useConfig` from `../hooks` | **None** -- hook exported in barrel |
| `App.tsx` | New `/guide` route added | **None** -- additive |
| `main.py` | New `feedback_router` + `/config` endpoint registered | **None** -- additive |
| `dependencies.py` | New `set_archivist` / `get_archivist` | **None** -- follows existing `set_agents` pattern |
| `archivist.py` | New `store_feedback()` + `darwin_feedback` collection | **None** -- existing `_ensure_initialized` + `VectorStore.upsert` pattern |
| `formatter.py` | Context block appended to non-user turns | **Low** -- Slack clients handle context blocks gracefully |

---

## 3. Findings & Fixes

| # | File | Severity | Issue Type | Description |
|---|------|----------|------------|-------------|
| 1 | `TurnBubble.tsx` line 125 | LOW | Dead Prop (fixed) | `ResultViewer` originally had `{ actor: string; result: string }` prop -- `actor` was unused. The staged version correctly removes it: `{ result: string }`. Pre-flight finding addressed. |
| 2 | `feedback.py` line 43 | LOW | Iteration | Turn lookup iterates full conversation list to find turn by number. For typical event sizes (5-30 turns) this is negligible. If events grow to 100+ turns, a dict lookup would be faster, but not needed now. |
| 3 | `archivist.py` line 224 | INFO | Deterministic ID | `uuid5(NAMESPACE_URL, f"feedback:{event_id}:{turn_number}")` means a second feedback on the same turn overwrites the first (upsert behavior). This is correct -- prevents duplicate feedback, last rating wins. |
| 4 | `brain.py` line 1480 | INFO | Consistency | The AI-generated disclaimer is appended to `notify_user_slack` as plain mrkdwn (correct per pre-flight v2). Consistent with the `context` block approach in `formatter.py` for threaded messages. |
| 5 | `GuidePage.tsx` | INFO | Content | All 9 sections present. Contact email and feedback URL consume `useConfig()` with loading states. No PII fields. |
| 6 | `useConfig.ts` | INFO | Caching | `staleTime: Infinity` ensures a single fetch across all consumers. Follows the TanStack Query pattern used by `useTopology`, `useQueue`, etc. |

**No HIGH or CRITICAL issues found.**

---

## 4. Component Extract Verification

The ConversationFeed extract is the highest-risk change (284 lines removed, 2 new files created). Verified:

| Check | Status |
|-------|--------|
| TurnBubble exported as default + StatusBadge named export | OK |
| MarkdownViewer exported as default | OK |
| ConversationFeed imports both correctly | OK |
| All sub-components preserved: StatusBadge, AttachmentIcon, RejectButton, HuddleResultViewer, ResultViewer, StatusCheck, FeedbackButtons | OK |
| MarkdownViewer shared: used by AttachmentIcon (TurnBubble) and report viewer (ConversationFeed) | OK |
| No orphaned imports in ConversationFeed | OK -- removed `ACTOR_COLORS`, `STATUS_COLORS`, `resizeImage`, `RefreshCw`, `MarkdownPreview`, `getCodeString`, `MermaidBlock` |

---

## 5. Verification Plan

### Build Check
- `cd ui && npm run build` -- TypeScript compilation + Vite bundle

### Backend Check
- `POST /feedback` with valid event_id + turn_number -> 200 + Qdrant storage
- `POST /feedback` with invalid event_id -> 404
- `POST /feedback` with rating "invalid" -> 422 (Pydantic validation)
- `GET /config` -> returns contactEmail, feedbackFormUrl, appVersion

### UI Visual Check
- Every non-user turn in ConversationFeed shows "AI-generated" badge + thumbs buttons
- ActivityStream entries show "(AI-generated)" suffix
- Footer shows "AI-powered system" + Guide link + version
- `/guide` page renders all 9 sections with config data
- Feedback thumbs-down -> comment input -> submit -> "Thanks" confirmation

### Slack Check
- New event via `/darwin` -> all non-user Slack messages have context block disclaimer
- `notify_user_slack` DM -> plain-text disclaimer at bottom

---

## 6. Summary

| Severity | Count | Action |
|----------|-------|--------|
| HIGH | 0 | -- |
| MEDIUM | 0 | -- |
| LOW | 2 | Non-blocking |
| INFO | 4 | Verification notes |

**Safe to merge.** Clean implementation matching the plan. All pre-flight v2 corrections applied. The component extract is a pure refactor with zero behavior change. Feedback backend correctly reuses the Archivist's embedding pipeline via the existing VectorStore API.

Commit message: `feat(transparency): AI-generated tagging, feedback mechanism, user guide, /config endpoint -- compliance with AI transparency requirements`
