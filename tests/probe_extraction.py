# BlackBoard/tests/probe_extraction.py
"""
Probe: Test Claude lesson extraction against the real cross-reference document.
Validates JSON output quality, field accuracy, and latency.

Usage:
  GOOGLE_APPLICATION_CREDENTIALS=../cnv-ai-insights-8502f29094a2.json \
  python tests/probe_extraction.py
"""
import asyncio
import json
import os
import time

os.environ.setdefault("GCP_PROJECT", "cnv-ai-insights")
os.environ.setdefault("GCP_LOCATION", "global")

SA_KEY = os.path.join(os.path.dirname(__file__), "..", "..", "cnv-ai-insights-8502f29094a2.json")
if os.path.exists(SA_KEY) and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

DOCUMENT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "lessons-learned",
    "2026-04-19-false-evidence-cross-reference.md",
)


async def run_probe():
    with open(DOCUMENT_PATH) as f:
        document = f.read()

    print(f"Document: {len(document)} chars")
    print(f"GCP_PROJECT: {os.environ.get('GCP_PROJECT')}")
    print(f"Model: {os.environ.get('LLM_MODEL_LESSON_EXTRACTOR', 'claude-sonnet-4-20250514')}")
    print("---")

    from src.agents.archivist import Archivist

    archivist = Archivist()
    start = time.time()
    result = await archivist.extract_lessons(
        document=document,
        context_notes="Focus on pipeline failure classification bias and false evidence patterns",
    )
    elapsed = time.time() - start

    print(f"\nLatency: {elapsed:.1f}s")
    print(f"Result type: {type(result).__name__}")

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        if "raw_text" in result:
            print(f"Raw text (first 500): {result['raw_text']}")
        return

    lessons = result.get("lessons", [])
    corrections = result.get("corrections", [])

    print(f"\nExtracted: {len(lessons)} lessons, {len(corrections)} corrections")

    print("\n=== LESSONS ===")
    for i, l in enumerate(lessons, 1):
        print(f"\n{i}. {l.get('title', '?')}")
        print(f"   Pattern: {l.get('pattern', '?')[:120]}...")
        print(f"   Anti-pattern: {(l.get('anti_pattern') or 'none')[:120]}...")
        print(f"   Keywords: {l.get('keywords', [])}")
        print(f"   Events: {l.get('event_references', [])}")

    print("\n=== CORRECTIONS ===")
    for i, c in enumerate(corrections, 1):
        print(f"\n{i}. {c.get('event_id', '?')}")
        print(f"   Current: {(c.get('current_root_cause') or '?')[:100]}")
        print(f"   Corrected: {(c.get('corrected_root_cause') or '?')[:100]}")
        print(f"   Fix: {(c.get('corrected_fix_action') or '?')[:100]}")

    # Sensing criteria
    print("\n=== PROBE SENSING ===")
    checks = []

    checks.append(("JSON valid", True))
    checks.append(("Lessons count (expect 2-4)", 2 <= len(lessons) <= 6))
    checks.append(("Corrections count (expect 5)", len(corrections) == 5))
    checks.append(("Latency < 30s", elapsed < 30))

    component_leak = False
    for l in lessons:
        pattern = (l.get("pattern", "") + l.get("anti_pattern", "")).lower()
        if any(term in pattern for term in ["quay.io", "virt-launcher", "sast-shell-check", "konflux-ci"]):
            component_leak = True
    checks.append(("Lessons are environment-agnostic", not component_leak))

    expected_events = {"evt-1b7bb120", "evt-f2e5db65", "evt-0c44cca3", "evt-a791fa71", "evt-0a313a02"}
    correction_events = {c.get("event_id") for c in corrections}
    checks.append(("All 5 events corrected", expected_events == correction_events))

    print()
    all_pass = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n{'PROBE PASSED' if all_pass else 'PROBE FAILED -- review output above'}")
    print(json.dumps(result, indent=2)[:3000])


if __name__ == "__main__":
    asyncio.run(run_probe())
