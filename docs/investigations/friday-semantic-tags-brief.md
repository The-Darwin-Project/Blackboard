# FRIDAY Semantic Tag Differentiation -- Pre-Evidence Brief

## Problem Statement

All 45 FRIDAY brain skills are currently wrapped with a uniform `<skill_section id="phase/file.md">` tag via `_wrap_skill_section()` in `brain.py`. This flattens the compliance gradient -- the LLM cannot distinguish between a hard constraint (e.g., safety rules) and optional reference material (e.g., Kargo environment details) from the tag name alone.

Following the JARVIS extraction pattern (this PR), the same semantic vocabulary (`rule`, `protocol`, `mode`, `context`, `skill`) should differentiate FRIDAY's skill tags to encode compliance intent.

## Proposed Tag Mapping

### Folder → Default Tag Type

| Folder | Current Tag | Proposed Tag | Rationale |
|---|---|---|---|
| `always/` | `skill_section` | `rule_section` | Always-on constraints, invariants, safety guardrails |
| `source/` | `skill_section` | `rule_section` | Per-source behavioral constraints |
| `context/` | `skill_section` | `context_section` | Reference material: environment, topology, architecture |
| `dispatch/` | `skill_section` | `skill_section` (KEEP) | Phase-specific capabilities, contextual know-how |
| `post-agent/` | `skill_section` | `skill_section` (KEEP) | Post-agent evaluation capabilities |
| `close/` | `skill_section` | `skill_section` (KEEP) | Closure evaluation capability |
| `defer-wake/` | `skill_section` | `skill_section` (KEEP) | Defer-wake verification capability |
| `escalate/` | `skill_section` | `skill_section` (KEEP) | Escalation protocol capability |
| `waiting/` | `skill_section` | `skill_section` (KEEP) | Wait protocol capability |
| `coordination/` | `skill_section` | `skill_section` (KEEP) | Multi-event coordination capabilities |
| `intermediate/` | `skill_section` | `skill_section` (KEEP) | System-state awareness capability |
| `multi-user/` | `skill_section` | `skill_section` (KEEP) | Multi-user protocol capability |

### Per-File Overrides (within folders)

| File | Folder Default | Override | Rationale |
|---|---|---|---|
| `always/09-phase-lifecycle.md` | rule | `protocol_section` | Decision tree / state machine, not a constraint |
| `source/jarvis-self-audit.md` | rule | `protocol_section` | Step sequence for responding to JARVIS |
| `source/_compound-instructions.md` | rule | `context_section` | Assembly instructions, reference material |

## Classification Summary (45 files)

| Semantic Type | Count | Files |
|---|---|---|
| `rule_section` | 17 | 8 always/ + 7 source/ (excl. overrides) + 2 source/ with hard constraints |
| `skill_section` | 20 | 6 dispatch/ + 5 post-agent/ + 1 close/ + 1 defer-wake/ + 1 escalate/ + 1 waiting/ + 2 coordination/ + 1 intermediate/ + 1 multi-user/ + 1 dispatch/gitops-context (edge case) |
| `context_section` | 5 | 4 context/ + 1 source/_compound-instructions |
| `protocol_section` | 3 | always/09-phase-lifecycle + source/jarvis-self-audit + escalate/incident-tracking |

**Classification confidence**: 40/45 files have clear type assignment. 5 edge cases identified (below).

## Edge Cases / Ambiguous Classifications

1. **`dispatch/gitops-context.md`** -- Reference material in a skill folder. Could be `context_section`. Need to check if it contains actionable procedures or just reference.
2. **`dispatch/deep-memory-fixes.md`** -- Contains both reference patterns AND actionable procedures. Lean toward `skill_section`.
3. **`escalate/incident-tracking.md`** -- Protocol-like (step sequence for escalation) but in a skill folder. Could be `protocol_section`.
4. **`always/06-decision-guidelines.md`** -- Guidelines, not hard rules. Could be `mode` or keep as `rule` given always/ folder convention.
5. **`context/aligner.md`** -- In context/ but may contain behavioral constraints. Verify content.

## Impact Analysis

### `_wrap_skill_section()` Call Chain

```
brain.py L380: def _wrap_skill_section(path: str, body: str) -> str
  ├── brain.py L1797: resolved_contents (main skill resolution loop)
  └── brain.py L1812: Kargo skills (find_paths_by_tag resolution)
```

**Modification needed**: `_wrap_skill_section()` must accept a `tag_type` parameter (default `"skill_section"` for backward compat), or the function is renamed to a generic `_wrap_section()` that takes the type.

### Cross-References to `<skill_section>`

| Location | Reference | Update Needed |
|---|---|---|
| `jarvis_instructions.py` L253 | "matching `<skill_section>` tags in her instructions" | Update to mention all tag types |
| `probe_skill_tokens.py` L110 | `<skill_section id="phase/filename.md">` | Update to handle multiple tag types |
| `brain_skills/source/jarvis-self-audit.md` L14 | `<skill_section id="phase/filename.md">` | Update reference |
| `brain.py` L45 shebang | "wraps each resolved skill body with `<skill_section>`" | Update shebang |
| `brain.py` L47 shebang | "skill_section id values must be ASCII path chars" | Generalize to all section types |

### BrainSkillLoader Integration

The loader already provides the `phase` (folder name) for each skill. The tag type can be derived from a mapping:

```python
_FOLDER_TAG_TYPE = {
    "always": "rule_section",
    "source": "rule_section",
    "context": "context_section",
    # All others default to "skill_section"
}
```

Per-file overrides could use frontmatter: `tag_type: protocol_section`.

## Open Questions

1. **Probe token format**: `skill::dispatch/execution-method.md` uses the literal word "skill". If tags differentiate, should the probe token change to `section::` or keep `skill::` as a generic prefix?
2. **JARVIS reference update**: JARVIS tells FRIDAY "matching `<skill_section>` tags" -- this needs to become generic. Ship in same PR or separate?
3. **Backward compatibility**: Any external tool that parses FRIDAY's system prompt for `<skill_section>` tags? (Likely just the probe script.)
4. **A/B testing**: Should we test compliance differences with one event before bulk-renaming 45 tags?

## Recommendation

**Pass condition met**: 40+ files clearly classified. Proceed to `/architect-bootstrap` for the FRIDAY differentiation PR with this brief as input evidence.

**Suggested PR scope**: 
1. Modify `_wrap_skill_section()` to accept tag type
2. Add `_FOLDER_TAG_TYPE` mapping in brain.py or BrainSkillLoader
3. Update cross-references (3 files)
4. CI test: extend `test_jarvis_tag_pairs_structural` pattern to FRIDAY

**Risk**: Low. Tags are consumed by the LLM only -- no downstream parsing depends on `<skill_section>` except the probe script (1-line fix).
