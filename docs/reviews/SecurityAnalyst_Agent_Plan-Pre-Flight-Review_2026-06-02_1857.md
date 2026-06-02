# SecurityAnalyst Agent Plan -- Pre-Flight Review

**Plan:** `securityanalyst_agent_plan_d516a1ca.plan.md`
**Date:** 2026-06-02 18:57 UTC+3
**Reviewer:** Darwin Systems Architect (AI)

---

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 91%
* **Status:** :rocket: Ready
* **Critical Blockers:** None. Two items require minor plan amendments (see Gap Analysis).

---

## 2. Task-by-Task Analysis

| Step | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
|:-----|:-------------|:---------------|:-----------|:-----------------------|
| 1a | Create `security_analyst.md` persona rules (2 copies) | Simple | 98% | Template is well-defined. Persona draft in plan. |
| 1b | Register in `configmap-gemini-rules.yaml` | Simple | 100% | One-line YAML addition. Pattern is clear. |
| 1c | Create `darwin-security-audit/SKILL.md` + extend shared skills | Simple | 95% | Skill body not fully drafted yet -- workflow shape is described but needs authoring at execution time. |
| 7 (Dockerfile) | Add trivy, grype, syft, cosign, pip-audit to Dockerfile | Complicated | 82% | Install scripts fetch latest -- UBI9 compatibility and non-root user constraints need verification. See Gap Analysis. |
| 2 | Update 5 enum/description locations in `llm/types.py` | Simple | 100% | All 5 locations verified with exact line numbers. |
| 3a | Add `EPHEMERAL_ONLY_ROLES` frozenset to `brain.py` | Simple | 100% | Module-level constant, no interactions. |
| 3b | Insert Tier 0 gate before Tier 1 in `_run_agent_task` | Complicated | 90% | The gate itself is 2 lines. Risk: ordering matters -- must insert before L4470, after L4467 (`agent_id_override = None`). Verified: insertion point is clean. |
| 3c | Circuit breaker no-fallback path for ephemeral-only roles | Complicated | 88% | Two code paths to handle: `provision_result is None` (circuit breaker) AND `provision_result == INFRA_SENTINEL` (Tekton down). Plan only covers `None` -- see Gap Analysis. |
| 3d | Update cwd default in `dispatch.py` | Simple | 95% | One-line change. Minor risk: existing ephemeral agents already work with `/data/gitops` default -- changing to `/data/workspace` is correct for ephemeral-only but verify existing ephemeral behavior is unaffected. |
| 3e | Update `VOLUME_PATHS` in `brain.py` L333 | Simple | 100% | Dict addition, used only in `write_event_to_volume` (L5149). |
| 3e | Actor allowlists (brain.py, main.py, formatter.py) | Simple | 100% | Verified all 3 locations. |
| 3e | `routes/queue.py` L114 | Simple | 100% | Description string only (1 location, not 2 as plan states). |
| 3e | `models.py` L318 | Simple | 100% | Description string addition. |
| 4a | Update `00-identity.md` agent roster | Simple | 98% | Agent table format is clear (L62-88). Need to add SecurityAnalyst block with modes/capabilities. |
| 4b | Update `06-decision-guidelines.md` | Simple | 95% | Routing section draft in plan. |
| 4c | Update `coordination-triage.md` | Simple | 95% | Section draft in plan. Minor: plan text still says "CVE, Snyk, trivy" -- violates prompt engineering rule. |
| 4d | Update 4 additional brain_skills files | Simple | 90% | `quality-gate.md` and `agent-recommendations.md` reference Dev/QE patterns generically -- SecurityAnalyst fits without structural changes. `plan-activation.md` has no agent enum (steps are dynamic). `source/headhunter_jira.md` mentions agents in prose (L27). |
| 4e | Headhunter retarget (`headhunter_jira.py` + `audit-cve.md`) | Complicated | 85% | `headhunter_jira.py` L128 has casing drift (`sysAdmin`). Fix + add `security_analyst`. `audit-cve.md` needs scan steps retargeted from Developer to SecurityAnalyst. |
| 5 | Formatter maps (AGENT_COLORS, EMOJI, SHORTCODE) | Simple | 100% | 3 dict additions. |
| 5 | Formatter actor tuples (L282, L285) | Simple | 100% | Add to existing tuples. |
| 6 | Test/probe enum updates | Simple | 100% | Mechanical enum additions. Bonus: fix stale `qe` omission. |
| 8 | Helm/GitOps (no-op) | Simple | 100% | Correctly identified as no-change. |
| 9 | Documentation updates | Simple | 95% | `docs/architecture.md` + workspace rules. Low risk. |
| Verify | Manual probe: end-to-end ephemeral dispatch | Complicated | 85% | Requires deployed cluster + Tekton EventListener. Not automatable in CI. |

---

## 3. Gap Analysis

### Gap 1: `INFRA_SENTINEL` path not covered (Confidence: 88% -> needs fix)

**Ambiguity:** The plan's Tier 0 circuit breaker (Step 3c) only handles `provision_result is None`. But `ensure_agent()` also returns `INFRA_SENTINEL` when Tekton HTTP call fails (L4513-4519). For existing Tier 1 sources this defers correctly. For ephemeral-only roles, the existing `INFRA_SENTINEL` handler at L4513 already does the right thing (defer 60s + return) -- it is **source-agnostic**. So the existing code path handles it.

**However:** The plan should explicitly note that the `INFRA_SENTINEL` path at L4513 requires NO change because it already defers regardless of role. This is a documentation gap, not a code gap.

**Safety:** No code fix needed. Add a comment to the plan: "The `INFRA_SENTINEL` handler at L4513 already defers unconditionally -- no change required for ephemeral-only roles."

### Gap 2: Dockerfile UBI9 compatibility for security tools (Confidence: 82%)

**Context:** The plan uses upstream install scripts (`curl | sh`) for trivy, grype, syft, and cosign. These scripts download pre-built Linux amd64 binaries -- they should work on UBI9. However:

- The image runs as `USER 1001` (non-root) after L165. Security tools are installed earlier (root context) -- correct placement.
- `trivy` first-run downloads a vulnerability database (~40MB) which requires write access to `~/.cache/trivy`. As non-root user 1001, `HOME=/home/default` -- already writable. But ephemeral pods use `emptyDir` for `/data/workspace` -- the DB download happens on first scan, adding ~30s cold-start per pod.
- `grype` similarly downloads a DB on first run (~15MB).

**Safety:** Consider pre-warming the trivy/grype databases at build time (adds to image size but eliminates cold-start latency on ephemeral pods):

```dockerfile
RUN trivy fs --download-db-only && grype db update
```

This is an optimization, not a blocker. Probe-first: skip pre-warming, measure cold-start, add if needed.

### Gap 3: Prompt engineering slip in `coordination-triage.md` draft

**Ambiguity:** The plan's draft for `coordination-triage.md` (Section 4c) says "Dependency vulnerability scan (CVE, Snyk, trivy)" -- listing specific tool names violates the prompt engineering rule the plan itself established in Layer 1. Should say "Dependency vulnerability scan" without tool names.

**Safety:** Minor text fix during execution.

### Gap 4: `routes/queue.py` has 1 location, not 2

**Context:** Plan states L114 and L137-138. Verified: only L114 contains the agent role list. L338 mentions "event report as Markdown" -- no agent enum. Correct the plan reference.

### Gap 5: `dispatch.py` cwd default change affects existing ephemeral agents

**Safety:** Today, ephemeral agents for headhunter/timekeeper/kargo_stage already use the `AGENT_VOLUME_PATHS.get(role, "/data/gitops")` default. When the agent gets `role="sysadmin"`, the dict lookup succeeds and returns `/data/gitops-sysadmin` -- which doesn't exist on the ephemeral pod (no PVC). The ephemeral sidecar ignores cwd for investigation tasks (it clones repos into its own working directory). Changing the default from `/data/gitops` to `/data/workspace` is **safe for existing ephemeral agents** because:

1. Role-matched lookups (sysadmin, developer, etc.) still hit the dict.
2. Only roles NOT in the dict (like `security_analyst`) use the default.
3. `/data/workspace` is the emptyDir mount on ephemeral pods.

No risk to existing behavior.

---

## 4. Path to Green (Remediation)

- [x] **Architecture diagram:** Mermaid flowchart for Tier 0 dispatch is in the plan. Adequate.
- [ ] **Amend Plan 3c:** Add note: "`INFRA_SENTINEL` handler at L4513 already defers unconditionally -- no change required for ephemeral-only roles."
- [ ] **Amend Plan 4c:** Remove tool names from `coordination-triage.md` draft (say "Dependency vulnerability scan" not "CVE, Snyk, trivy").
- [ ] **Amend Plan 3e:** Correct `routes/queue.py` reference from "L114, L137-138" to "L114 only".
- [ ] **Consider (optional):** Pre-warm trivy/grype DBs in Dockerfile to avoid ephemeral cold-start. Mark as follow-up probe.
- [ ] **Execution order recommendation:** Layer 7 (Dockerfile) should execute FIRST since it requires a sidecar image rebuild + GHCR push before the SecurityAnalyst can actually scan anything. All other layers can deploy with the existing image (rules/skills/enums work immediately).

---

## Recommended Execution Order

1. **Dockerfile** (Layer 7) -- image rebuild is the long pole; start first, parallelize rest
2. **Sidecar persona + skills** (Layer 1) -- can execute in parallel with Dockerfile
3. **Brain enums** (Layer 2) -- no dependencies
4. **Brain dispatch Tier 0** (Layer 3) -- depends on understanding Layer 2 enum values
5. **Brain skills** (Layer 4) -- no dependencies, parallelize with Layer 3
6. **Formatter/UI** (Layer 5) + **Actor allowlists** (Layer 3e) -- parallelize
7. **Tests** (Layer 6) -- after all code changes
8. **Helm ConfigMap** (Layer 1b) -- last, triggers pod rollout
9. **Verify** -- manual probe after deploy
