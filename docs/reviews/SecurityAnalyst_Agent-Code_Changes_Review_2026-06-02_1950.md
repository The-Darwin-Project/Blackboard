# SecurityAnalyst Agent -- Code Changes Review

**Date:** 2026-06-02 19:50 UTC+3
**Plan:** SecurityAnalyst Agent (securityanalyst_agent_plan_d516a1ca)
**Pre-flight:** SecurityAnalyst_Agent_Plan-Pre-Flight-Review_2026-06-02_1857.md
**Scope:** 26 modified files + 4 new files
**Reviewers:** 3 parallel codereview subagents (A: full-spectrum, B: contract/type/prompt, C: security/reliability/architecture)

---

## 1. Summary

| Metric | Value |
| :--- | :--- |
| **Risk Level** | Medium |
| **Cynefin Domain** | Complicated |
| **Breaking Changes** | Yes -- `dispatch.py` cwd default change (mitigated, see Finding F1) |
| **Deferred Debt** | 2 items (F3: hardcoded defer reason, F8: prompt-only READ-ONLY enforcement) |
| **Total Findings** | 9 (0 HIGH, 3 MEDIUM, 6 LOW) |
| **Enum Consistency** | Verified across all 5 `types.py` locations + `headhunter_jira.py` + all test/probe files |
| **Dual Rules Sync** | Verified -- `gemini-sidecar/rules/security_analyst.md` and `helm/files/security_analyst.md` are identical |
| **Tier 0 Gate Ordering** | Correct -- fires before Tier 1, Tier 1 guarded with `if not use_ephemeral` |
| **Actor Allowlists** | Complete -- `brain.py`, `main.py`, `formatter.py`, `models.py`, `routes/queue.py` all updated |
| **sysAdmin Casing Fix** | Verified -- `headhunter_jira.py` enum fixed from `sysAdmin` to `sysadmin` |

---

## 2. Downstream Impact

| Consumer File | Dependency | Risk | Status |
| :--- | :--- | :--- | :--- |
| `src/agents/brain.py` L741 | Agent turn counter tuple | Actor missed = undercounted turns | **Updated** |
| `src/agents/brain.py` L4478 | `EPHEMERAL_ONLY_ROLES` + Tier 0 gate | New dispatch path | **Updated** |
| `src/agents/brain.py` L4511 | Circuit breaker no-fallback | New defer path | **Updated** |
| `src/main.py` L555 | Event flow agent turn counter | Actor missed = wrong flow metrics | **Updated** |
| `src/channels/formatter.py` L285/288 | `format_turn` actor tuples | Missing actor = unformatted turns | **Updated** |
| `src/channels/formatter.py` L37/44/53 | COLOR/EMOJI/SHORTCODE dicts | Missing key = fallback to `:gear:` | **Updated** |
| `src/agents/dispatch.py` L131 | `cwd` default | Changed from `/data/gitops` to `/data/workspace` | **Updated** (see F1) |
| `src/agents/llm/types.py` (5 locations) | Tool schema enums | Missing enum = FRIDAY can't route | **Updated** |
| `src/models.py` L318 | `ConversationTurn.actor` description | Documentation only | **Updated** |
| `src/routes/queue.py` L114 | Query param description | Documentation only | **Updated** |
| `src/agents/headhunter_jira.py` L128 | Plan step agent enum | Missing enum = invalid plan steps | **Updated** + casing fix |
| `gemini-sidecar/cli-setup.js` L267 | `swapActiveRules(role)` | Checks `/tmp/agent-rules/${role}.md` | **No change needed** -- data-driven |
| `gemini-sidecar/ws-client.js` | Pre-warm gate | New role-gated code path | **Updated** |
| `helm/templates/configmap-gemini-rules.yaml` | ConfigMap key | Missing = no rules file mounted | **Updated** |
| `src/agents/brain_skills/post-agent/plan-activation.md` | Agent routing examples | Uses illustrative names, not enum | **No change needed** |

---

## 3. Findings & Fixes

### F1: `dispatch.py` cwd default change -- potential blast radius

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/dispatch.py` L131 |
| **Severity** | LOW |
| **Issue Type** | Breaking Change (mitigated) |
| **Flagged By** | Reviewer A, C |

**Description:** Default `cwd` changed from `/data/gitops` to `/data/workspace`. This affects any role NOT in `AGENT_VOLUME_PATHS`. All 4 existing roles (architect, sysadmin, developer, qe) have explicit entries, so the default only fires for unknown roles.

**Verdict:** Safe. The only current consumer of the default is `security_analyst`, which is explicitly in the dict as `/data/workspace`. The default change is a defensive improvement -- if a future ephemeral-only role is added without a VOLUME_PATHS entry, `/data/workspace` (emptyDir) is safer than `/data/gitops` (may not exist). No fix needed.

---

### F2: Ephemeral provisioner disabled + FRIDAY selects security_analyst

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/brain.py` L4477-4478 |
| **Severity** | **MEDIUM** |
| **Issue Type** | Logic Gap |
| **Flagged By** | Reviewer C |

**Description:** The Tier 0 gate checks `agent_name in self.EPHEMERAL_ONLY_ROLES and self._ephemeral_provisioner`. If `self._ephemeral_provisioner` is `None` (ephemeral provisioning disabled), the gate doesn't fire. `use_ephemeral` stays `False`. The code falls through to L4545-4548 where it attempts `dispatch_to_agent` to a local sidecar -- which doesn't exist for `security_analyst`. This would fail at the registry lookup (`registry.get_available("security_analyst")` returns `None`), then timeout or error.

**Fix:** Add a guard after Tier 2 (before the `if use_ephemeral:` block at L4508):

```python
# Safety: ephemeral-only roles require the provisioner
if agent_name in self.EPHEMERAL_ONLY_ROLES and not use_ephemeral:
    logger.warning(
        "Ephemeral-only role %s selected but provisioner unavailable for %s -- deferring",
        agent_name, event_id,
    )
    await self._execute_function_call(
        event_id, "defer_event",
        {"delay_seconds": 60, "reason": f"Role {agent_name} requires ephemeral provisioner (disabled)"},
        response_parts=None,
    )
    return
```

**Impact:** Without this fix, disabling the ephemeral provisioner while FRIDAY can still select `security_analyst` creates a silent dispatch failure. Low probability (provisioner is always enabled in production), but the failure mode is confusing.

---

### F3: Hardcoded defer reason in circuit breaker

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/brain.py` L4518 |
| **Severity** | LOW |
| **Issue Type** | Coupling / Scalability |
| **Flagged By** | Reviewer C |

**Description:** The defer reason string hardcodes `"Security analyst unavailable"` instead of using `agent_name`:

```python
{"delay_seconds": 60, "reason": f"Security analyst unavailable (ephemeral circuit breaker, no local fallback)"}
```

If a second ephemeral-only role is added later, this string would be misleading.

**Fix (deferred):** Replace with `f"Role {agent_name} unavailable (ephemeral circuit breaker, no local fallback)"`. Acceptable as-is since there's only one ephemeral-only role today. Track as minor tech debt.

---

### F4: `audit-cve.md` lists explicit tool names in LLM prompt

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/headhunter_skills/audit-cve.md` L22-26, L29, L84, L88 |
| **Severity** | **MEDIUM** |
| **Issue Type** | Prompt Engineering |
| **Flagged By** | Reviewer B |

**Description:** The headhunter skill `audit-cve.md` is an LLM prompt (injected into the Headhunter's Flash Lite context). It lists explicit tool names: `npm audit --json`, `yarn audit --json`, `pip-audit --format=json`, `safety check --json`, `trivy image --format json`, `grype`, `syft`, `npm audit fix`, `pip-audit --fix`. Per prompt engineering rules, LLM prompts should describe the TASK not the TOOL.

**Fix:** Replace the "Scan Tools" section (L21-26) with ecosystem-task descriptions:

```markdown
2. **Scan Approach** (based on ecosystem):
   - Node.js/TypeScript: audit dependencies via package manager, output as JSON
   - Python: audit installed packages for known CVEs, output as JSON
   - Go: check modules for known vulnerabilities
   - Container images: scan base image and installed packages for vulnerabilities
   - General: generate SBOM for supply chain audits
3. **Fix Criteria** (what to fix autonomously vs flag for human):
   - **Auto-fix**: Minor/patch version bumps that resolve Critical or High CVEs
   - **Auto-fix**: Use package manager's built-in fix command when available
```

Also remove explicit tool names from L84 (`syft` generation) and L88 (`npm, pip, go, trivy, etc.`). These teach the model to reproduce tool names as text output instead of discovering tools from its environment.

---

### F5: `cosign` named in LLM skill prompt

| Attribute | Value |
| :--- | :--- |
| **File** | `gemini-sidecar/skills/darwin-security-audit/SKILL.md` L33 |
| **Severity** | LOW |
| **Issue Type** | Prompt Engineering |
| **Flagged By** | Reviewer A, B |

**Description:** Line 33 says `"check container image signatures when cosign is available"`. Per prompt engineering rules, LLM prompts should describe the TASK, not the TOOL. The persona rules file (`security_analyst.md`) correctly avoids tool names -- the skill file has one instance.

**Fix:** Change to `"verify container image signatures and provenance when signing tools are available"`.

---

### F5a: `ws-client.js` pre-warm -- sequential 60s timeouts

| Attribute | Value |
| :--- | :--- |
| **File** | `gemini-sidecar/ws-client.js` L256-257 |
| **Severity** | LOW |
| **Issue Type** | Reliability |
| **Flagged By** | Reviewer C |

**Description:** Two sequential `execSync` calls, each with 60s timeout. Worst case: 120s total blocking before CLI spawn begins. The `handleTask` function is already async, but `execSync` blocks the event loop.

**Verdict:** Acceptable for Phase 1. Security analyst is ephemeral-only (no shared event loop with other agents), and DB downloads typically take 15-30s each. The progress messages keep FRIDAY/UI informed. If this becomes an issue, refactor to `execFile` with `Promise` wrappers. No fix required now.

---

### F6: `headhunter_jira.py` prompt text -- `sysAdmin` casing + missing `security_analyst`

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/headhunter_jira.py` L93 |
| **Severity** | **MEDIUM** |
| **Issue Type** | Prompt Engineering / Completeness |
| **Flagged By** | Reviewer B |

**Description:** The enum at L128 was correctly fixed (`sysAdmin` -> `sysadmin`, added `security_analyst`). However, the **LLM prompt text** at L93 still says `sysAdmin` (camelCase) and does not mention `security_analyst` at all:

```
- sysAdmin: infrastructure, deployment, cluster operations, pipeline investigation
```

This prompt is injected into Flash Lite's context for Jira plan generation. Without a `security_analyst` role description, Flash Lite will never route scanning steps to SecurityAnalyst -- it doesn't know the role exists.

**Fix:** Update L90-93 to:

```
- architect: code review, analysis, design assessment, plan creation (READ-ONLY)
- developer: implementation, code changes, bug fixes, creating branches/MRs (WRITE access)
- qe: testing, verification, running test suites, validating fixes (READ + EXECUTE tests)
- sysadmin: infrastructure, deployment, cluster operations, pipeline investigation
- security_analyst: vulnerability scanning, CVE assessment, dependency audits, SBOM generation (READ-ONLY, ephemeral)
```

---

### F7: Dockerfile -- unpinned install scripts (supply chain)

| Attribute | Value |
| :--- | :--- |
| **File** | `gemini-sidecar/Dockerfile` L103-108 |
| **Severity** | LOW |
| **Issue Type** | Security / Supply Chain |
| **Flagged By** | Reviewer C |

**Description:** All four tool installs (`trivy`, `grype`, `syft`, `cosign`) use `latest` release scripts piped to shell. The cosign binary download is unverified (no checksum validation). This is consistent with the existing Dockerfile pattern (kubectl, helm, argocd all install the same way), but it's a supply chain risk.

**Verdict:** Acceptable -- consistent with existing patterns in the same Dockerfile. The Darwin project's evolutionary policy rule says "NEVER hardcode version numbers. Always use `:latest` tags and install the latest stable packages." This follows that policy. The cosign download from `github.com/sigstore/cosign/releases/latest` is the official distribution channel.

---

### F8: READ-ONLY enforcement is prompt-only, not architectural

| Attribute | Value |
| :--- | :--- |
| **File** | `gemini-sidecar/rules/security_analyst.md` L52, 73 |
| **Severity** | LOW |
| **Issue Type** | Architecture |
| **Flagged By** | Reviewer C |

**Description:** The persona rules say "READ-ONLY for cluster access" and "NEVER use kubectl/oc to make changes", but this is enforced by prompt, not by RBAC or CLI permission mode. The sidecar runs with `bypassPermissions` (same as all agents).

**Verdict:** Acceptable for Phase 1. This is consistent with all other agents -- SysAdmin has `FORBIDDEN_PATTERNS` in `security.py` as a secondary safety net, but the primary enforcement for all agents is prompt-based. A future improvement would be to add SecurityAnalyst-specific `FORBIDDEN_PATTERNS` (block `kubectl apply`, `kubectl delete`, `git push`). Track as future hardening, not a blocker.

---

### F9: `brain_skills/always/00-identity.md` uses `sysAdmin` casing in existing content

| Attribute | Value |
| :--- | :--- |
| **File** | `src/agents/brain_skills/always/00-identity.md` L69 |
| **Severity** | LOW |
| **Issue Type** | Consistency |
| **Flagged By** | Reviewer A |

**Description:** The existing line 69 says `**sysAdmin**` (camelCase) in the agent roster prose. The new SecurityAnalyst addition at L90+ uses consistent naming. The casing drift in the existing content is pre-existing debt, not introduced by this change.

**Verdict:** Out of scope for this PR. The `sysAdmin` casing in brain_skills prose is descriptive (matches the tool's description strings in `types.py` L341), not an enum value. No fix needed in this change.

---

## 4. Reviewer Disagreements

| Topic | Reviewer A | Reviewer B | Reviewer C | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| F2 severity | Not flagged | Not flagged | MEDIUM (called HIGH) | **MEDIUM adopted** -- silent dispatch failure to non-existent sidecar is a real gap, but low probability in production |
| F4 severity | Not flagged | HIGH | Not flagged | **MEDIUM adopted** -- Flash Lite will generate plans without SecurityAnalyst if prompt text is missing, but Brain can still manually route |
| F7 supply chain | Not flagged | Not flagged | HIGH | **LOW adopted** -- consistent with existing Dockerfile patterns + evolutionary policy explicitly says use `:latest` |
| Blocking pre-warm | LOW | Not flagged | MEDIUM | **LOW adopted** -- acceptable for ephemeral-only agent, sequential worst case is 120s but typical is 30-45s |

---

## 5. Verification Plan

| # | Check | Command / Method | Confirms |
| :--- | :--- | :--- | :--- |
| 1 | Python import | `cd BlackBoard && python -c "from src.agents.llm.types import BRAIN_TOOL_SCHEMAS; print('OK')"` | types.py enum changes parse correctly |
| 2 | Dual rules sync | `diff gemini-sidecar/rules/security_analyst.md helm/files/security_analyst.md` | Files are identical |
| 3 | Enum grep sweep | `grep -rn 'security_analyst' src/ tests/ scripts/ gemini-sidecar/ helm/` | Present in all expected locations |
| 4 | No stale sysAdmin enums | `grep -rn 'sysAdmin' src/agents/headhunter_jira.py` | Returns zero results (fixed) |
| 5 | Tier 0 ordering | Manual code read: brain.py L4474-4490 | Tier 0 before Tier 1, Tier 1 guarded by `if not use_ephemeral` |
| 6 | Circuit breaker paths | Manual code read: brain.py L4510-4541 | `None` → ephemeral-only defer; `INFRA_SENTINEL` → unconditional defer; else → sidecar fallback |
| 7 | Probe: chat event | Create chat event "run a dependency audit on the store app" | Ephemeral pod spawns with role=security_analyst |
| 8 | Probe: Slack format | Check Slack notification for SecurityAnalyst turn | Shield emoji (:shield:) renders correctly |
| 9 | Regression: existing agents | Create chat event for architect/sysadmin/developer/qe | No dispatch behavior change for existing roles |
| 10 | Probe: provisioner disabled | Temporarily disable ephemeral provisioner, dispatch security_analyst | Verify graceful failure (requires F2 fix) |

---

## 6. Action Items

| # | Priority | Action | Status |
| :--- | :--- | :--- | :--- |
| 1 | **Must fix** | F2: Add provisioner-disabled guard for ephemeral-only roles (5-line guard in `brain.py`) | Open |
| 2 | **Must fix** | F6: Add `security_analyst` role description to `headhunter_jira.py` L93 prompt + fix `sysAdmin` casing | Open |
| 3 | **Should fix** | F4: Remove explicit tool names from `audit-cve.md` (prompt engineering violation) | Open |
| 4 | Should fix | F5: Remove `cosign` tool name from `darwin-security-audit/SKILL.md` L33 | Open |
| 5 | Nice to have | F3: Parameterize defer reason with `agent_name` instead of hardcoded "Security analyst" | Deferred (tech debt) |
| 6 | Future hardening | F8: Add SecurityAnalyst-specific FORBIDDEN_PATTERNS in `security.py` | Deferred |

**Recommendation:** Fix F2 + F6 before merge (both are functional gaps that affect dispatch correctness). Fix F4 + F5 in the same commit (prompt engineering cleanup). F3, F8, F9 can be deferred.
