# Brain Skills Phase Architecture Refactor

## Architecture Diagram

```mermaid
graph TD
    subgraph "Skill Loading (_match_phases + _build_system_prompt)"
        BM[brain.py _match_phases] --> AL[always/]
        BM --> SRC[source/{event.source}.md]
        BM --> CTX[context/ if related events]
        BM --> MU[multi-user/ if slack participant]
        BM --> BP{brain_phase}
        BP -->|triage| NONE1[no extra folders]
        BP -->|investigate| DISP[dispatch/]
        BP -->|execute| DISP2[dispatch/ + coordination/]
        BP -->|verify| PA[post-agent/ + defer-wake/]
        BP -->|escalate| PA2[post-agent/]
        BP -->|close| NONE2["❌ no extra folders"]
    end

    subgraph "Problem: always/ loads every turn"
        AL --> A00[00-identity ✅]
        AL --> A01["01-function-rules ⚠️ close seq L39-55"]
        AL --> A02[02-safety ✅]
        AL --> A03[03-control-theory ✅]
        AL --> A04["04-deep-memory ⚠️ auth workflow L35-46"]
        AL --> A05["05-cynefin ⚠️ action prescriptions"]
        AL --> A06["06-decision-guidelines ⚠️ 167 lines, mixed concerns"]
        AL --> A07["07-incident-tracking ⚠️ 123 lines, full escalation"]
        AL --> A08[08-flow-engineering ✅]
        AL --> A09["09-phase-lifecycle ⚠️ close seq in body"]
    end

    subgraph "Problem: close phase has no skills"
        NONE2 -.->|"UNLOADS"| PA3[post-agent/when-to-close.md]
        PA3 -.->|"needed but absent"| CLOSE_PHASE[close phase]
    end

    style NONE2 fill:#f66,stroke:#333
    style A01 fill:#ff9,stroke:#333
    style A04 fill:#ff9,stroke:#333
    style A05 fill:#ff9,stroke:#333
    style A06 fill:#ff9,stroke:#333
    style A07 fill:#ff9,stroke:#333
    style A09 fill:#ff9,stroke:#333
```

## Evidence Summary

### Affected Files

| File | Lines | Problem | Evidence |
|------|-------|---------|----------|
| `brain.py` L343-350 | 8 | `close: []` means no phase-specific skills load | `BRAIN_PHASE_SKILLS` dict |
| `always/07-incident-tracking.md` | 123 | Full escalation workflow (evidence gate, temporal drift, terminal failure gate, incident template) loaded during triage/investigate | Entire file is escalation procedure |
| `always/06-decision-guidelines.md` | 167 | Mixed: triage routing (always) + MR lifecycle (dispatch) + close actions + web search + JARVIS events | L98-143 MR lifecycle, L144-156 auto-retry, L158-167 JARVIS |
| `always/01-function-rules.md` L39-55 | 17 | Close sequence duplicated here | Close seq steps 0-8 |
| `always/04-deep-memory.md` L35-46 | 12 | Authorization workflow (notify_user_slack, report_incident, wait_for_user) = post-agent behavior | "notify_user_slack" + "report_incident" + "wait_for_user" |
| `always/05-cynefin.md` | 67 | Action prescriptions mixed with framework (L22 "Skip Architect", L29 "Send agents", L36 "dispatching Developer") | Domain descriptions contain dispatch instructions |
| `always/09-phase-lifecycle.md` | 126 | Close sequence in L93-99 (after escalation), transition guidance L114-125 | Duplicated close sequence |
| `post-agent/when-to-close.md` | 48 | Canonical close source but UNLOADS in close phase (only loaded in verify+escalate) | `BRAIN_PHASE_SKILLS["close"] = []` |
| `source/headhunter.md` L36-62 | 27 | Close protocol with authorization workflow duplicates `when-to-close.md` + `04-deep-memory.md` | Close sequence + proposed fix flow |

### Duplication Map (Close Sequences)

| Location | Steps | Numbering | Notes |
|----------|-------|-----------|-------|
| `always/01-function-rules.md` L39-55 | 0-8 | 0-indexed | Includes "set_phase(verify)" at step 0 |
| `post-agent/when-to-close.md` L34-48 | 0-9 | 0-indexed with patience gate (step 3) | Most complete, has defer loop |
| `always/09-phase-lifecycle.md` L93-99 | Prose | Narrative form | "transition to close" |
| `source/headhunter.md` L36-62 | Narrative | Embedded in Close Protocol section | Source-specific variant |

**Canonical source:** `post-agent/when-to-close.md` (most complete, includes patience gate at step 3).

### What Belongs in `always/`

Files that pass the "needed regardless of phase" test:

| File | Verdict | Rationale |
|------|---------|-----------|
| `00-identity.md` | ✅ KEEP | Identity, voice, agent roster -- always needed |
| `01-function-rules.md` | ⚠️ TRIM | Job description + notification authority = always. Close sequence = remove |
| `02-safety.md` | ✅ KEEP | Safety guardrails -- always needed |
| `03-control-theory.md` | ✅ KEEP | 12 lines, pure framework |
| `04-deep-memory.md` | ⚠️ SPLIT | Memory consultation (always) vs authorization workflow (post-agent) |
| `05-cynefin.md` | ⚠️ SPLIT | Domain definitions (always) vs action prescriptions (dispatch) |
| `06-decision-guidelines.md` | ⚠️ SPLIT | Self-answer-first + severity (always) vs routing + MR lifecycle (dispatch) |
| `07-incident-tracking.md` | ❌ MOVE | Entire file is escalation procedure |
| `08-flow-engineering.md` | ✅ KEEP | Congestion/flow principles -- always needed |
| `09-phase-lifecycle.md` | ⚠️ TRIM | Phase definitions (always) vs close sequence + after-escalation (remove) |

## Implementation Strategy

**Pattern:** Split-and-relocate. Extract phase-specific content from `always/` files into the correct phase folders. Create a new `close/` folder. Deduplicate close sequences to one canonical file.

**Breaking changes:** None. No tool schema changes, no API changes, no Python code changes beyond `BRAIN_PHASE_SKILLS["close"]` and `BRAIN_PREFILL_MODEL`.

**Cynefin classification:** COMPLICATED -- known unknowns around LLM behavioral regression when prompt structure changes. Requires verification probes.

## Atomic Execution Steps

### Step 1: Create `close/` folder and update `BRAIN_PHASE_SKILLS` [CLEAR]

**What:** Create `brain_skills/close/` with `_phase.yaml`. Update `BRAIN_PHASE_SKILLS["close"]` in `brain.py`.

**Files:**
- CREATE `brain_skills/close/_phase.yaml` (copy from `post-agent/_phase.yaml`, adjust description)
- EDIT `brain.py` L349: `"close": []` → `"close": ["close"]`
- EDIT `brain.py` L356-364: Update `BRAIN_PREFILL_MODEL` to remove "(4) Source-aware close rules" (this moves to phase-gated)

**Evidence:** `_match_phases` L1682 iterates `BRAIN_PHASE_SKILLS[brain_phase]` and appends folders. Adding `"close"` to the list is the same mechanism used by all other phases.

**Verification:** Unit test `test_match_phases` (if exists) or manual: confirm `_match_phases` returns `["always", "source", "close"]` when `brain_phase="close"`.

---

### Step 2: Move `when-to-close.md` from `post-agent/` to `close/` [CLEAR]

**What:** Move the canonical close sequence to the `close/` folder so it loads when FRIDAY enters close phase.

**Files:**
- MOVE `brain_skills/post-agent/when-to-close.md` → `brain_skills/close/when-to-close.md`
- UPDATE frontmatter `phase: close` (currently has no explicit phase field, it inherits from folder)

**Evidence:** `when-to-close.md` is the most complete close sequence (steps 0-9 with patience gate). It's currently loaded in verify+escalate phases via `post-agent/`. After the move, it loads in close phase only, which is correct -- FRIDAY needs it when she's closing.

**Trade-off:** verify and escalate phases lose `when-to-close.md`. This is INTENTIONAL -- verify/escalate should focus on verification/escalation, not close procedures. The close sequence is only actionable in close phase.

**Verification:** Process a headhunter event through to close phase. Confirm FRIDAY follows the close sequence correctly.

---

### Step 3: Remove close sequences from `always/01-function-rules.md` [CLEAR]

**What:** Delete L39-55 (close sequence for automated events with failures + close sequence for successful events). Replace with a single cross-reference line.

**Files:**
- EDIT `always/01-function-rules.md`: Remove L39-55, replace with: `Close sequences are phase-gated -- see close/ skills when in close phase.`

**Evidence:** L39-55 duplicates `post-agent/when-to-close.md` with 0-indexed numbering (vs the canonical 0-9 with patience gate). Keeping this creates numbering drift.

**Verification:** `wc -l always/01-function-rules.md` should drop from ~120 to ~105. Build passes.

---

### Step 4: Remove close/escalation content from `always/09-phase-lifecycle.md` [CLEAR]

**What:** Trim "After Escalation" section (L89-99) which contains close sequence prose. Keep phase definitions, transition guidance, and CHAOTIC handling.

**Files:**
- EDIT `always/09-phase-lifecycle.md`: Remove L89-99 ("After Escalation" section). The transition guidance at L114-125 ("Common flows") stays -- it shows phase TRANSITIONS, not close PROCEDURES.

**Evidence:** L93-99 says "transition to close" with inline steps that duplicate `when-to-close.md`. The transition guidance section only lists flow patterns (arrows) without procedure details.

**Verification:** File stays under 100 lines. Phase definitions and transition patterns remain intact.

---

### Step 5: Move `always/07-incident-tracking.md` to `escalate/` [CLEAR]

**What:** Create `brain_skills/escalate/` folder. Move the incident tracking skill there. Update `BRAIN_PHASE_SKILLS["escalate"]`.

**Files:**
- CREATE `brain_skills/escalate/_phase.yaml` (same as `post-agent/_phase.yaml`)
- MOVE `always/07-incident-tracking.md` → `brain_skills/escalate/incident-tracking.md`
- EDIT `brain.py` L348: `"escalate": ["post-agent"]` → `"escalate": ["post-agent", "escalate"]`

**Evidence:** The entire 123-line file is escalation procedure (evidence gate, temporal drift, terminal failure gate, incident template). None of it is needed during triage/investigate. Loading it always primes FRIDAY to think about escalation prematurely.

**Verification:** Process an event in triage phase. Confirm system prompt does NOT contain "Evidence Gate" or "Terminal Failure Gate" text. Process an event in escalate phase -- confirm it DOES contain them.

---

### Step 6: Split `always/04-deep-memory.md` -- move authorization workflow to `post-agent/` [COMPLICATED]

**What:** Extract L26-51 (the "Deep Memory Fix Proposals" section with notify_user_slack/report_incident/wait_for_user authorization flow) into a new `post-agent/deep-memory-fixes.md`. Keep L1-25 (memory consultation guidance) in `always/04-deep-memory.md`.

**Files:**
- EDIT `always/04-deep-memory.md`: Remove L26-51 ("Deep Memory Fix Proposals" section)
- CREATE `brain_skills/post-agent/deep-memory-fixes.md` with the extracted content + frontmatter

**Evidence:** L35-46 contains `notify_user_slack`, `report_incident`, `wait_for_user` -- these are tools gated to escalate/close phases. Instructing FRIDAY about them during triage is noise.

**Verification:** `always/04-deep-memory.md` drops to ~25 lines. `post-agent/deep-memory-fixes.md` contains the authorization workflow. Both files have correct frontmatter.

---

### Step 7: Split `always/05-cynefin.md` -- move action prescriptions to `dispatch/` [COMPLICATED]

**What:** Extract the action lines from each domain section into `dispatch/cynefin-actions.md`. Leave the domain DEFINITIONS (names, patterns, constraints, flows) in `always/05-cynefin.md`.

Specifically, extract from each domain section:
- CLEAR L22: "Skip Architect. Send sysAdmin directly..."
- COMPLICATED L29: "Send agents to investigate, then Architect..."
- COMPLEX L36-41: "Run a small safe-to-fail probe. For build failures..."
- CHAOTIC L48: "Immediate stabilization (rollback, scale up...)"

**Files:**
- EDIT `always/05-cynefin.md`: Replace action lines with: `Action: see dispatch skills for domain-specific routing.`
- CREATE `brain_skills/dispatch/cynefin-actions.md` with the extracted actions + domain context

**Evidence:** The dispatch/ folder already contains `execution-method.md` and `gitops-context.md`. Cynefin actions are dispatch-time decisions. The framework DEFINITIONS (what each domain means, when to reclassify) remain always-loaded.

**Verification:** `always/05-cynefin.md` stays under 50 lines. `dispatch/cynefin-actions.md` contains all four domain action prescriptions with clear domain headers.

---

### Step 8: Split `always/06-decision-guidelines.md` [COMPLICATED]

**What:** This 167-line file mixes always-needed guidance with dispatch-specific content. Split into:

**Keep in `always/06-decision-guidelines.md`** (~40 lines):
- "Self-Answer First" (L9-16) -- always needed
- "Web Search Context" (L72-96) -- always needed (search grounding)
- "Severity Escalation" (L109-119) -- always needed
- "JARVIS System Review Events" (L158-167) -- always needed

**Move to `dispatch/decision-routing.md`** (~90 lines):
- "Agent Routing" (L17-42) -- dispatch-time decisions
- "Investigation Dispatch: Questions" (L44-56) -- dispatch instructions
- "Investigation Dispatch: Find Fixes" (L58-70) -- dispatch instructions
- "Known Transient Error Auto-Retry" (L144-156) -- dispatch behavior

**Move to `dispatch/mr-lifecycle.md`** (~40 lines):
- "Headhunter Events: MR/PR Lifecycle Awareness" (L98-125) -- dispatch context
- "MR/PR Pipeline Fix Principle" (L127-143) -- dispatch context

**Files:**
- EDIT `always/06-decision-guidelines.md`: Keep only always-needed sections
- CREATE `brain_skills/dispatch/decision-routing.md`
- CREATE `brain_skills/dispatch/mr-lifecycle.md`

**Evidence:** The dispatch/ folder loads during investigate+execute phases (L345-346 of brain.py). Agent routing and investigation dispatch instructions are only useful when FRIDAY is about to dispatch an agent.

**Verification:** `always/06-decision-guidelines.md` drops to ~40 lines. `dispatch/` folder gains two new files. All three files have correct frontmatter with appropriate tags.

---

### Step 9: Deduplicate headhunter close protocol in `source/headhunter.md` [CLEAR]

**What:** Replace the inline Close Protocol section (L36-62) with a cross-reference to `close/when-to-close.md` and `escalate/incident-tracking.md`. Keep headhunter-specific guidance (silent close for merged MRs, bot MR handling).

**Files:**
- EDIT `source/headhunter.md` L36-62: Replace with condensed headhunter-specific rules + `requires: close/when-to-close.md` in frontmatter (dependency resolution will pull it when both source and close phases are active)

**Note:** The `requires` mechanism in the skill loader resolves dependencies -- `source/headhunter.md` already uses `requires: context/gitlab-environment.md`. Adding `close/when-to-close.md` as a soft reference (documented, not enforced) avoids loading close skills during triage while still documenting the dependency.

**Verification:** `source/headhunter.md` drops below 70 lines. Close-specific content is canonical in one place.

---

### Step 10: Update `BRAIN_PREFILL_MODEL` in `brain.py` [CLEAR]

**What:** Update the prefill to reflect the new structure. Remove references to skills that are no longer always-loaded.

**Files:**
- EDIT `brain.py` L356-364: Update prefill to:
  ```
  "Darwin online. Protocols locked: "
  "(1) Deep memory before routing -- history beats guesswork. "
  "(2) Cynefin triage on every event. "
  "(3) Never drop agent recommendations. "
  "(4) Phase-gated close and escalation. "
  "(5) Voice: confident peer, Cynefin-gated tone. "
  "Let's get to work."
  ```

**Evidence:** Current prefill item (4) says "Source-aware close rules" which referenced the always-loaded close content. Now close is phase-gated.

**Verification:** String comparison. No functional change beyond prompt text.

## Verification Plan

### Unit Tests
1. **_match_phases with close phase:** Confirm `_match_phases` returns `"close"` in active phases when `brain_phase="close"`.
2. **_match_phases with escalate phase:** Confirm `"escalate"` folder appears alongside `"post-agent"` when `brain_phase="escalate"`.
3. **System prompt assembly:** Confirm `_build_system_prompt` for close phase includes `when-to-close.md` content.

### Integration Checks
1. Process a headhunter event through full lifecycle (triage → investigate → verify → escalate → close). Confirm close sequence is available in close phase.
2. Process a chat event through triage. Confirm system prompt does NOT contain "Evidence Gate", "Terminal Failure Gate", or "report_incident" procedure text.
3. Process an event into escalate phase. Confirm incident tracking content IS present.

### Behavioral Regression Check
1. Compare system prompt token counts before/after for each phase. `always/` token count should drop ~40%. Phase-specific prompts should grow proportionally.
2. Run 3 headhunter test events. Confirm FRIDAY does not attempt to escalate/close during triage phase (the primary behavioral goal).

### File Inventory (Post-Refactor)

```
always/
  00-identity.md          ✅ unchanged
  01-function-rules.md    ✏️ trimmed (close seq removed)
  02-safety.md            ✅ unchanged
  03-control-theory.md    ✅ unchanged
  04-deep-memory.md       ✏️ trimmed (auth workflow removed)
  05-cynefin.md           ✏️ trimmed (action prescriptions removed)
  06-decision-guidelines.md ✏️ trimmed (routing + MR lifecycle removed)
  08-flow-engineering.md  ✅ unchanged
  09-phase-lifecycle.md   ✏️ trimmed (after-escalation removed)

dispatch/
  execution-method.md     ✅ unchanged
  gitops-context.md       ✅ unchanged
  coordination-triage.md  ✅ unchanged
  cynefin-actions.md      🆕 from always/05-cynefin.md
  decision-routing.md     🆕 from always/06-decision-guidelines.md
  mr-lifecycle.md         🆕 from always/06-decision-guidelines.md

escalate/
  _phase.yaml             🆕
  incident-tracking.md    📦 from always/07-incident-tracking.md

close/
  _phase.yaml             🆕
  when-to-close.md        📦 from post-agent/when-to-close.md

post-agent/
  _phase.yaml             ✅ unchanged
  agent-recommendations.md ✅ unchanged
  evidence-sufficiency.md ✅ unchanged
  plan-activation.md      ✅ unchanged
  post-execution.md       ✅ unchanged
  deep-memory-fixes.md    🆕 from always/04-deep-memory.md
```

### Updated `BRAIN_PHASE_SKILLS`

```python
BRAIN_PHASE_SKILLS: dict[str, list[str]] = {
    "triage":       [],
    "investigate":  ["dispatch"],
    "execute":      ["dispatch", "coordination"],
    "verify":       ["post-agent", "defer-wake"],
    "escalate":     ["post-agent", "escalate"],
    "close":        ["close"],
}
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| FRIDAY loses context needed during triage because it moved to dispatch/ | Medium | Medium | Cynefin DEFINITIONS stay in always/. Only ACTION prescriptions move. Self-answer-first stays in always/. |
| Close phase too thin (only 1 file) | Low | Low | `when-to-close.md` is comprehensive (48 lines). Source-specific close rules remain in `source/` (always loaded). |
| Dependency resolution breaks for `requires:` references | Low | High | Test dependency resolution with the moved files. The skill loader resolves `requires:` by path, not folder. |
| LLM behavioral regression from prompt restructuring | Medium | Medium | Compare token counts. Run behavioral tests. The content is identical -- only the loading phase changes. |
