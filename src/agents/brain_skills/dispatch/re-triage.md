---
description: "Re-triage rules when users report new issues within an active event"
tags: [dispatch, triage, user-input]
---
# Re-Triage on New User Issues

A new bug report within an active event is a new problem, not a continuation of the previous dispatch. Reusing the previous agent's mode or domain classification assumes the new issue has the same nature as the original — which is rarely true for user-reported crashes, errors, or behavioral regressions.

When a user reports NEW bugs, crashes, errors, or issues within an active event:

1. Route to Developer (`mode: implement`). The QE Verification Gate applies -- QE MUST verify before PR/merge.
2. Do NOT reuse the previous dispatch mode. Fresh issues warrant fresh classification.
3. Multiple distinct issues (2+) or any crash/error report warrants reassessing domain and severity.
