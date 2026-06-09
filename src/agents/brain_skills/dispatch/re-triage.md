---
description: "Re-triage rules when users report new issues within an active event"
tags: [dispatch, triage, user-input]
---
# Re-Triage on New User Issues

When a user reports NEW bugs, crashes, errors, or issues within an active event:

1. Route to Developer (`mode: implement`). The QE Verification Gate applies -- QE MUST verify before PR/merge.
2. Do NOT reuse the previous dispatch mode. Fresh issues warrant fresh classification.
3. Multiple distinct issues (2+) or any crash/error report warrants reassessing domain and severity.
