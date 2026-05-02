# BlackBoard/scripts/inject_l4_lessons.py
# @ai-rules:
# 1. [Constraint]: One-shot script. Run once after deploying L4 skill changes.
# 2. [Pattern]: Uses Archivist.store_lesson() API. Lessons use uuid4 IDs -- re-running creates duplicates.
# 3. [Gotcha]: Must be run from the Brain pod (oc exec) so google-genai + Qdrant are accessible.
"""
Inject L4 Autonomous AI Lessons Learned into the darwin_lessons Qdrant collection.

Derived from the Brain's self-observation in evt-0e413329, where it identified
three behavioral gaps preventing L4 autonomy. These lessons surface at triage
time via consult_deep_memory to reinforce the skill file changes.

Usage:
    oc exec -n darwin <brain-pod> -c brain -- python3 -m scripts.inject_l4_lessons
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


LESSONS = [
    {
        "title": "Propose Known Fixes Instead of Blind Escalation",
        "pattern": (
            "When a pipeline failure matches a previously resolved error signature "
            "in Deep Memory (score >= 0.65, outcome resolved/user_closed), include the "
            "proven fix as an actionable proposal in the Slack notification. Use "
            "notify_user_slack as the authorization channel ('Reply to authorize this "
            "fix'), report_incident as the offline record, and wait_for_user to keep "
            "the event alive for seamless continuation."
        ),
        "anti_pattern": (
            "Escalating with a generic failure description and closing the "
            "event, even when Deep Memory contains a proven fix for the same error. "
            "This forces the maintainer to re-investigate from scratch."
        ),
        "keywords": [
            "escalation", "deep-memory", "fix-proposal", "propose-and-prompt",
            "pipeline-failure", "dockerfile", "dependency", "build-config",
        ],
        "event_references": ["evt-0e413329", "evt-4f30a7bf", "evt-b25271ff"],
    },
    {
        "title": "Transfer Proven Fixes Across Components With Same Error Signature",
        "pattern": (
            "When a user-approved structural fix (Dockerfile patch, dependency "
            "bump) resolves an error in one component, and the same error signature "
            "appears in a different component within 7 days, propose the same fix to "
            "the maintainer instead of treating it as a novel failure. Cap at 3 "
            "concurrent proposals; batch the rest into a summary notification."
        ),
        "anti_pattern": (
            "Treating each component as an isolated silo for safety "
            "constraints, re-escalating the same known fix when it hits a different "
            "repository. The Brain sees the fix in Deep Memory but does not propose it "
            "because the approval was scoped to the original event and repository."
        ),
        "keywords": [
            "cross-event", "pattern-transfer", "same-error", "different-component",
            "structural-fix", "dockerfile", "CDN-404", "go-version",
        ],
        "event_references": ["evt-0e413329", "evt-b25271ff", "evt-4f30a7bf", "evt-c1ee1e57"],
    },
    {
        "title": "Use MR Branches as Safe-to-Fail Probes for Build Fixes",
        "pattern": (
            "MR source branches are inherently safe-to-fail: if a speculative "
            "fix is wrong, the pipeline fails and main is untouched. When a build "
            "failure has no proven fix in Deep Memory but a plausible fix exists, "
            "reclassify to COMPLEX and dispatch the Developer to push the fix to the "
            "MR branch. If the pipeline passes, propose to the maintainer. Limit: one "
            "probe per event."
        ),
        "anti_pattern": (
            "Anchoring in COMPLICATED domain and escalating build failures "
            "that could be probed on the MR branch. Treating Dockerfile patches on MR "
            "branches the same as main-branch structural changes."
        ),
        "keywords": [
            "mr-branch", "safe-to-fail", "probe", "cynefin-complex",
            "speculative-fix", "build-failure", "pipeline",
        ],
        "event_references": ["evt-0e413329"],
    },
]


async def main():
    from src.agents.archivist import Archivist

    archivist = Archivist()
    print(f"Injecting {len(LESSONS)} L4 lessons into darwin_lessons...")
    failures = 0

    for lesson in LESSONS:
        lesson_id = await archivist.store_lesson(
            title=lesson["title"],
            pattern=lesson["pattern"],
            anti_pattern=lesson["anti_pattern"],
            keywords=lesson["keywords"],
            event_references=lesson["event_references"],
        )
        if lesson_id:
            print(f"  Stored: {lesson['title']} -> {lesson_id}")
        else:
            print(f"  FAILED: {lesson['title']}")
            failures += 1

    if failures:
        print(f"Done with {failures} failure(s).")
        sys.exit(1)
    else:
        print("Done. All lessons injected successfully.")


if __name__ == "__main__":
    asyncio.run(main())
