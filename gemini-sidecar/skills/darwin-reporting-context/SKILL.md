---
name: darwin-reporting-context
description: MR/PR context gathering and diagnostic reporting guidelines. Activates when working on events that reference MRs/PRs or when reporting investigation findings.
roles: [architect, sysadmin, developer, qe, security_analyst]
---

# MR/PR Context and Diagnostic Reporting

## MR/PR Context Prerequisite

When the task references an MR/PR (URL, ID, or branch): read the full MR/PR description BEFORE any analysis or modifications.

- Look for `### Bot Instructions` — these are constraints from the MR author or automation bot
- Include constraints in your report to FRIDAY (they are evidence, not optional metadata)
- If Bot Instructions restrict modifications: do NOT push changes. Report the constraint and let FRIDAY decide
- If no Bot Instructions are found, the source mutation approval gate still applies — report the proposed fix to FRIDAY and let FRIDAY authorize the push
- Architect-specific: flag constraint conflicts in plan steps so FRIDAY can gate dispatch

## Report Structure (Body + Steps)

The `steps` frontmatter field is parsed by brain.py into executable plan turns. Do NOT repurpose it for observations. The contract:

- **Body text** = diagnosis, understanding, constraints. What the situation IS. Include: root cause, modification constraints (Bot Instructions), component context (placeholder? stub? production?), prior attempts visible in MR comments.
- **`steps` field** = remediation proposals for FRIDAY to evaluate. What COULD be done. FRIDAY decides whether to dispatch, approve, or escalate — the agent does not have action authority over source mutations.

No source mutation without explicit FRIDAY approval — this invariant applies regardless of which skills are co-loaded.
