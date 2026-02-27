# Code Review v2: LLM Config Restructure (post-fix pass)

**Plan:** `llm_config_restructure_a07217ab.plan.md`
**Date:** 2026-02-27
**Reviewer:** Systems Architect (AI)
**Scope:** 13 staged files (Helm chart + 5 Python agents + 3 tests + README + v1 review doc)
**Previous:** v1 review identified 2 HIGH, 4 MEDIUM, 5 LOW findings. This v2 covers the fix pass.

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** **Low** (downgraded from v1 Medium) -- all contract gaps are closed. Every `LLM_*` env var published by the ConfigMap is consumed by at least one Python agent.
* **Breaking Changes:** `gcp.models.*` and `gcp.temperature.*` Helm paths removed. Pre-flight verified `darwin-blackboard.yaml` (ArgoCD) has no stale overrides. **No live breakage.**

---

## 2. Downstream Impact Analysis

### Affected Consumers (full env var chain)

| ConfigMap Key | values.yaml Path | Deployment Env | Python Consumer | Verified |
|---|---|---|---|---|
| `LLM_PROVIDER` | `gcp.provider` | `LLM_PROVIDER` | `brain.py:269` | OK |
| `LLM_MODEL_BRAIN` | `gcp.llm.brain.model` | `LLM_MODEL_BRAIN` | `brain.py:271` | OK |
| `LLM_TEMPERATURE_BRAIN` | `gcp.llm.brain.temperature` | `LLM_TEMPERATURE_BRAIN` | `brain.py:270` | OK |
| `LLM_MAX_TOKENS_BRAIN` | `gcp.llm.brain.maxOutputTokens` | `LLM_MAX_TOKENS_BRAIN` | `brain.py:272,530` | OK |
| `LLM_MODEL_MANAGER` | `gcp.llm.manager.model` | `LLM_MODEL_MANAGER` | `dev_team.py:69`, `developer.py:33` | OK |
| `LLM_TEMPERATURE_MANAGER` | `gcp.llm.manager.temperature` | `LLM_TEMPERATURE_MANAGER` | `dev_team.py:100,339` | OK |
| `LLM_THINKING_MANAGER` | `gcp.llm.manager.thinkingLevel` | `LLM_THINKING_MANAGER` | `dev_team.py:101,340` | OK |
| `LLM_MAX_TOKENS_MANAGER` | `gcp.llm.manager.maxOutputTokens` | `LLM_MAX_TOKENS_MANAGER` | `developer.py:122,145` | OK (fixed) |
| `LLM_MODEL_ALIGNER` | `gcp.llm.aligner.model` | `LLM_MODEL_ALIGNER` | `aligner.py:187` | OK |
| `LLM_TEMPERATURE_ALIGNER` | `gcp.llm.aligner.temperature` | `LLM_TEMPERATURE_ALIGNER` | `aligner.py:163` | OK |
| `LLM_THINKING_ALIGNER` | `gcp.llm.aligner.thinkingLevel` | `LLM_THINKING_ALIGNER` | `aligner.py:232,495` | OK |
| `LLM_MAX_TOKENS_ALIGNER` | `gcp.llm.aligner.maxOutputTokens` | `LLM_MAX_TOKENS_ALIGNER` | `aligner.py:494` | OK |
| `LLM_MODEL_ARCHIVIST` | `gcp.llm.archivist.model` | `LLM_MODEL_ARCHIVIST` | `archivist.py:32` | OK |
| `LLM_MAX_TOKENS_ARCHIVIST` | `gcp.llm.archivist.maxOutputTokens` | `LLM_MAX_TOKENS_ARCHIVIST` | `archivist.py:121` | OK (fixed) |

### Risk Assessment

- All 14 `LLM_*` keys: values.yaml -> configmap.yaml -> deployment.yaml -> Python code. **Fully wired.**
- Zero `VERTEX_MODEL_*` references in `src/`, `tests/`, `README.md`, or Helm templates.
- `helm template` output: 14 unique `LLM_*` keys in ConfigMap, 14 matching env vars in Deployment. Zero `VERTEX_MODEL_*`. 4 `ANTHROPIC_VERTEX_*` (sidecar, unrelated -- expected).
- Existing tests updated to use new env var names with correct defaults.

---

## 3. Findings & Fixes

### v1 Findings Resolution

| v1 ID | Severity | Status | Resolution |
|---|---|---|---|
| HIGH #1 developer.py max_output_tokens | HIGH | **FIXED** | Now reads `LLM_MAX_TOKENS_MANAGER` with default `"4096"` (L122, L145). |
| HIGH #2 archivist.py max_output_tokens | HIGH | **FIXED** | Now reads `LLM_MAX_TOKENS_ARCHIVIST` with default `"4096"` (L121). |
| MEDIUM tests/probe_*.py stale refs | MEDIUM | **FIXED** | All 3 test files updated: `VERTEX_MODEL_PRO` -> `LLM_MODEL_BRAIN`. |
| MEDIUM README.md stale docs | MEDIUM | **FIXED** | Env var table updated to `LLM_MODEL_BRAIN/MANAGER/ALIGNER/ARCHIVIST`. |
| LOW dev_team.py shebangs | LOW | **FIXED** | Shebang, docstring, and class docstring updated: "Flash LLM" -> "Manager LLM". |
| LOW archivist.py shebangs | LOW | **FIXED** | Shebang, docstring, and log messages updated: "Flash" -> "LLM". |
| LOW developer.py temp divergence | LOW | **FIXED** | `MANAGER_TEMPERATURE = 0.7` extracted as documented constant (L34). |
| LOW aligner.py docstring | LOW | **FIXED** | Module docstring L13 updated: "Gemini Flash" -> "Gemini LLM". |

### New Findings (v2)

| File | Severity | Issue Type | Description |
|---|---|---|---|
| `developer.py:33` | LOW | Naming | Variable still named `FLASH_MODEL` but now reads `LLM_MODEL_MANAGER` (Pro, not Flash). Used at L119, L142. Rename to `MANAGER_MODEL` for clarity. Same applies to `archivist.py:32`. |
| `developer.py:4,5,11,15` | LOW | Stale Shebang | AI shebang (L4: "Flash Manager moderates", L5: "flash_note") and docstring (L11: "Flash Manager moderation", L15: "Flash Manager reviews") still reference "Flash". Should match the model rename. |
| `aligner.py:5` | LOW | Stale Shebang | Shebang says "1024 for text, 4096 for tool-calling" but both are now env-configurable. The constraint (always set explicitly) is valid; the numbers are misleading. |
| `aligner.py:8` | LOW | Stale Shebang | Says "Aligner always uses GeminiAdapter (Pro, low thinking)" -- "always" is misleading since model/thinking are now configurable via env vars. |
| `llm_config_restructure-..._1930.md` | LOW | Stale Artifact | v1 review doc is staged. It references unresolved findings that are now fixed. Consider unstaging or replacing with this v2 doc. |

---

## 4. Verification Plan

### Pre-Commit (all passed)

| Check | Result |
|---|---|
| `helm template` -- zero `VERTEX_MODEL_*` | PASS |
| `helm template` -- 14 unique `LLM_*` keys | PASS (14 ConfigMap + 14 Deployment env) |
| Grep `VERTEX_MODEL` in `src/` | PASS (zero matches) |
| Grep `VERTEX_MODEL` in `tests/` | PASS (zero matches) |
| Grep `gemini-3-flash` or `gemini-3-pro-preview` (stale defaults) in `src/` | PASS (zero matches) |

### Post-Deploy Verification

1. **Brain:** `Brain initialized (provider=gemini, model=gemini-3.1-pro-preview, ...)` in startup log
2. **Aligner:** `Aligner LLM adapter initialized: gemini/gemini-3.1-pro-preview` on first analysis cycle
3. **DevTeam:** `DevTeam loaded N manager skill files` at startup; first dispatch confirms `LLM_MODEL_MANAGER`
4. **Archivist:** `Archivist initialized (LLM + embedding + Qdrant, ...)` on first event archival
5. **Negative:** No `gemini-3-flash-preview` in any agent log (would indicate stale defaults)

### Env Var Override Smoke Test

Set a values override with a distinct Aligner model (e.g., `gcp.llm.aligner.model: "gemini-2.0-flash"`) and verify the Aligner startup log reflects it. This confirms the full config -> env -> code path.

---

## 5. Verdict

**APPROVE with minor nits.** The core refactoring is clean. All v1 HIGH/MEDIUM findings resolved. Remaining findings are LOW (naming consistency, stale shebangs) and can be addressed in a follow-up commit. The config-code contract is fully closed for all 14 env vars.
