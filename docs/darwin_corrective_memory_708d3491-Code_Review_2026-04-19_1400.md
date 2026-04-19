# Code Review: Darwin Corrective Memory (`darwin_corrective_memory_708d3491`)

**Scope:** Implemented changes on `main` from `a3a25da` through `2cd08d8` (corrective memory CRUD, `darwin_lessons`, neutral summaries, Brain dual-search, Memory UI + Extract wizard, Claude extraction, probe script, template). Skill fix `04-deep-memory.md` landed separately in `a326c31`.

**Review architect:** Paired architecture pass (Cynefin → contracts → hex boundaries → logic → debt).

---

## 1. Summary

| Metric | Value |
| :--- | :--- |
| **Risk Level** | **Medium** (new mutating admin surface + LLM extraction cost; mitigations present) |
| **Cynefin Domain** | **Complicated** overall (known design, multiple integrated components). **Complex** sub-domain for extraction quality — explicitly probed via `tests/probe_extraction.py` before UI (aligned with plan Batch 5/6). |
| **Breaking Changes** | **No** for public event APIs. **Additive:** new Qdrant collection `darwin_lessons`; new `/queue/admin/*` routes; Brain `consult_deep_memory` output format change (lessons section + neutral labels) — consumers are the Brain LLM and dashboard only. |
| **Deferred Debt** | **Listed below** — none are silent; most are follow-up hardening, not correctness blockers for the stated plan. |

---

## 2. Layer 1 — Cynefin Classification

**Overall:** Complicated (Sense–Analyze–Respond). The reinforcement-loop fix is **Clear** (skill text + rendering order) and was correctly sequenced early (`a326c31`).

**Complex sub-problem (lesson extraction):** Addressed per plan: probe script + retry JSON path before shipping wizard. Appropriate **Probe–Sense–Respond** posture.

**Cross-issue correlation:** Skill change + Archivist embedding change + Brain rendering address the *same* failure mode (contaminated memory driving wrong shortcuts). Good — not unrelated symptom fixes.

---

## 3. Layer 2 — Dependency & Contract Impact

### Modified / new artifacts

| Area | Files | Contract notes |
| :--- | :--- | :--- |
| **Adapter (Qdrant)** | `src/memory/vector_store.py` | New `scroll`, `get_points`, `delete`. REST shapes must stay aligned with Qdrant server version. |
| **Domain-ish + adapter** | `src/agents/archivist.py` | Summarization prompt schema extended (`pattern_keywords`, `instance_keywords`). `embed_text` backward-compatible via `pattern_keywords` or `keywords`. |
| **Ports / orchestration** | `src/routes/queue.py` | Pydantic models for admin bodies; `LessonApplyRequest` reuses `CorrectMemoryRequest` for corrections — fields match apply path. |
| **Brain plumbing** | `src/agents/brain.py` | `consult_deep_memory` now calls `search_lessons` then `search`; output markdown contract changed (lessons block + “Pattern:” lines). |
| **UI** | `ui/src/api/client.ts`, `ui/src/components/memory/*`, `ui/src/hooks/useMemory.ts` | Typed payloads in `client.ts` (plan also mentioned `types.ts`; types live in `client.ts` — acceptable consolidation). |
| **Observability / ops** | `tests/probe_extraction.py`, `ui/public/lessons-learned-template.md` | Probe documents env assumptions. |
| **Deploy** | `helm/values.yaml` (image tag bump in range) | No new `LLM_MODEL_LESSON_EXTRACTOR` ConfigMap wiring yet — see findings. |

### Downstream impact

| Consumer | Dependency | Risk | Status |
| :--- | :--- | :--- | :--- |
| Brain LLM (`consult_deep_memory` tool result) | Markdown structure | Low | Updated in code; skills (`04-deep-memory.md`) aligned to interpret lessons + not skip investigation. |
| Qdrant | New collection + scroll API | Medium | `_ensure_initialized` creates collection; scroll uses `next_page_offset` — matches Qdrant REST. |
| Dashboard UI | `/queue/admin/*` | Medium | New Memory tab wired; same-origin `/lessons-learned-template.md` download link. |
| CI / agents | None breaking | Low | N/A |

**Schema evolution:** New summary fields optional for old points; `embed_text` falls back to `keywords`. **Backward compatible.**

---

## 4. Layer 3 — Architectural Guardrails (Hexagonal)

- **Separation:** Archivist owns summarization, embedding, and Qdrant persistence — consistent with existing pattern. `queue.py` remains thin HTTP boundary.
- **Brain constraint honored:** Decision policy still in prompts/skills; Python only augments tool result assembly (`brain.py` AI shebang).
- **Cross-boundary messaging:** `extract_lessons` is a **command** (document in → structured JSON out). Not idempotent by nature; UI “Apply” is the idempotent-ish user confirmation — acceptable.
- **Mechanism linkage:** Reinforcement loop broken by (1) skill text, (2) lessons-before-events ordering, (3) neutral-first rendering — each maps to a concrete artifact.

**Platform economics (LLM):** Extraction invokes Claude with up to 8k output tokens; capped input (`MAX_EXTRACTION_CHARS = 50_000`). Cost and latency are real operational parameters — should be **sensed** (logs already on extraction completion / failures).

---

## 5. Layer 4 — Logic & Integrity

### Strengths

- **Deterministic point IDs** for events (`uuid5`) preserved on `correct_memory` — true overwrite semantics.
- **JSON parse + single retry** for extraction reduces flake from markdown fences.
- **Event report truncation** (`[:3000]` per event) avoids runaway context when cross-referencing.
- **Deep memory guard** still keys off `"Deep memory"` substring — compatible with new `## Deep Memory` heading.

### Findings & fixes

| File | Severity | Issue type | Description & recommended fix |
| :--- | :--- | :--- | :--- |
| `archivist.py` | **MEDIUM** | **Ops / scale** | `list_memories` / `list_lessons` use a **single** `scroll` page with default `limit=200`. Collections beyond 200 points are **incomplete** in the UI. **Fix:** expose `offset` (or `next_page_offset`) query params on `GET /queue/admin/memories` and `GET /queue/admin/lessons`, pass through to `VectorStore.scroll`, and paginate the UI. |
| `queue.py` + deploy | **MEDIUM** | **Platform / config** | `LLM_MODEL_LESSON_EXTRACTOR` is read from env in code but **not** wired in Helm ConfigMap (unlike `LLM_MODEL_ARCHIVIST`). **Fix:** add `gcp.llm.lessonExtractor.model` (or similar) to `values.yaml` + `configmap.yaml` + `deployment.yaml` for parity and safer rollouts. |
| `queue.py` | **MEDIUM** | **Security / blast radius** | `/queue/admin/*` mutates Qdrant and triggers Claude spend (`/lessons/extract`). This matches existing “open API” style for `/queue` but **increases** abuse surface vs read-only endpoints. **Fix (if API is ever exposed beyond trusted mesh):** gate admin routes behind the same mechanism as other privileged operations (OIDC, internal network policy, or API key). Document threat model in runbook. |
| `archivist.py` | **LOW** | **Consistency** | `correct_memory` recomputes embedding from **corrected** root/fix but leaves `symptom` / `pattern_keywords` unchanged. Usually fine; if classification was wrong partly due to symptom text, vector may stay slightly misaligned. **Optional fix:** optional fields on `CorrectMemoryRequest` to refresh symptom/keywords, or document that operators should rebuild if needed. |
| `archivist.py` / `queue.py` | **LOW** | **API ergonomics** | `delete_lesson` returns **503** on any failure; missing lesson vs Qdrant error indistinguishable. Prefer **404** when point absent (may need `get_points` pre-check). |
| `tests/probe_extraction.py` | **LOW** | **Debt / docs** | Printed default model still references `claude-sonnet-4-20250514` while code default is `claude-sonnet-4-6`. **Fix:** print `Archivist.EXTRACTOR_MODEL` or read env after import. |
| Plan vs repo | **LOW** | **Process** | Plan asked for `ui/src/api/types.ts` additions; types are inlined in `client.ts`. **Fix:** either add re-exports in `types.ts` or update plan — no functional gap. |

---

## 6. Layer 5 — Zero Deferred Debt (explicit)

| Item | Resolution in same PR? | Note |
| :--- | :--- | :--- |
| Pre-existing `defer_event` RMW note in `brain.py` shebang | **N/A** | Documented debt; not introduced by memory work. |
| Pagination for large Qdrant collections | **No** | **Accepted follow-up** — should be tracked as a ticket if production memory count can exceed 200. |
| Helm wiring for extractor model | **No** | **Accepted follow-up** — defaults work; ops visibility is the gap. |
| Admin auth | **No** | **Environment-dependent** — acceptable if BlackBoard is only reachable on trusted network; otherwise harden. |

---

## 7. AI Shebang compliance (touched files)

Headers present and read for:

- `BlackBoard/src/agents/archivist.py` — extended rules cover corrective memory, lessons, Claude extraction, collections.
- `BlackBoard/src/memory/vector_store.py` — documents scroll/get/delete semantics.
- `BlackBoard/src/routes/queue.py` — route-order gotchas + report pattern.
- `BlackBoard/src/agents/brain.py` — large constraint set; includes honest defer RMW debt note.
- `BlackBoard/ui/src/components/memory/ExtractWizard.tsx` — wizard state machine documented.

**Skills:** `04-deep-memory.md` uses YAML frontmatter (not `// @ai-rules`) — appropriate for markdown skill files.

---

## 8. Verification plan

| Flow | How to verify |
| :--- | :--- |
| **Skill + Brain** | Automated event: confirm `consult_deep_memory` returns lessons block first, then events; Brain still dispatches investigate per updated skill. |
| **correct_memory** | `curl` `POST /queue/admin/correct-memory` for known `event_id`; confirm Qdrant payload `corrected: true` and embedding search still hits. |
| **Lessons CRUD** | `POST /queue/admin/lessons`, `GET /queue/admin/lessons`, `DELETE /queue/admin/lessons/{id}`. |
| **Extraction** | Run `python tests/probe_extraction.py` with valid GCP creds; inspect JSON shape, latency, and token/cost logs. |
| **UI** | Memory tab: list memories, correct one, manual lesson, full extract → review → apply. |
| **Neutral summaries** | Close a test event; inspect Qdrant payload for `pattern_keywords` / `instance_keywords`; optional `POST /queue/admin/rebuild-deep-memory` smoke on staging. |

**Sensing (feedback loop):**

- Structured logs: `Memory corrected`, `Lesson stored`, `Extraction complete`, archivist warnings on failures.
- Metrics (if available): Claude call count/latency for `/lessons/extract`; Qdrant error rates on scroll/upsert.

---

## 9. Verdict

**Approve with operational follow-ups:** implementation matches the architectural intent of the plan (two collections, dual search, neutral-first rendering, human-in-the-loop corrections, probe-before-wizard for extraction). Address **pagination** and **Helm parity for `LLM_MODEL_LESSON_EXTRACTOR`** before declaring the Memory UI production-complete at scale; reassess **admin auth** if the API boundary moves beyond a trusted control plane.

---

*Generated: 2026-04-19 (code review bootstrap against merged `main` in `BlackBoard` repo).*
