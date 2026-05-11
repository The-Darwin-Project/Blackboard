# BlackBoard/scripts/probe_nightwatcher_insights.py
# @ai-rules:
# 1. [Pattern]: Probe script -- tests how the Nightwatcher LLM uses AI Insights data in clustering.
# 2. [Constraint]: Uses real escalation data from live shifts API + real AI Insights data.
# 3. [Pattern]: Runs the analysis + declare_clusters flow locally against Gemini Flash. No Smartsheet writes.
"""
Probe: Nightwatcher with AI Insights signal.

Tests whether providing AI Insights recommendations at review phase start
changes the LLM's clustering behavior (more aggressive consolidation,
better priority assignment, insights references in reasoning).

Usage:
    export GCP_PROJECT=your-project
    python3 scripts/probe_nightwatcher_insights.py

Fetches real data from:
    - Darwin shifts API (recent sweep manifest)
    - AI Insights API (bundle-flow recommendations)
"""
import asyncio
import json
import os
import sys
import time

import httpx

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

PROJECT = os.environ.get("GCP_PROJECT", "")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = os.environ.get("LLM_MODEL_NIGHTWATCHER", "gemini-3-flash-preview")

DARWIN_URL = "https://darwin-blackboard-brain-darwin.apps.cnv2.engineering.redhat.com"
INSIGHTS_URL = "https://ai-insights.apps.cnv2.engineering.redhat.com/ai-insights/api/insights"

DECLARE_CLUSTERS_SCHEMA = {
    "name": "declare_clusters",
    "description": (
        "Declare your incident clusters. Each cluster groups events that share "
        "a root cause. Every event in the manifest must be assigned to exactly "
        "one cluster. Code validates coverage before any writes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Event IDs from the manifest",
                        },
                        "root_cause": {
                            "type": "string",
                            "description": "One-line root cause summary",
                        },
                        "platform": {
                            "type": "string",
                            "description": "Affected platform",
                        },
                        "services": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Affected services",
                        },
                    },
                    "required": ["events", "root_cause", "platform", "services"],
                },
            },
        },
        "required": ["clusters"],
    },
}


async def fetch_shift_data() -> list[dict]:
    """Fetch the most recent completed sweep with >5 escalations."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{DARWIN_URL}/shifts/list?days=7", headers={"accept": "application/json"})
        resp.raise_for_status()
    shifts = resp.json()
    for s in shifts:
        if s["status"] == "completed" and s.get("escalation_count", 0) >= 5:
            date, window = s["shift_date"], s["window"]
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{DARWIN_URL}/shifts/{date}/{window}", headers={"accept": "application/json"})
                resp.raise_for_status()
            return resp.json().get("manifest", [])
    print("No recent sweep with >=5 escalations found")
    sys.exit(1)


async def fetch_insights() -> list[dict]:
    """Fetch AI Insights bundle-flow recommendations."""
    params = {
        "days": 7, "forceRefresh": "false", "includeSmartSheet": "true",
        "includeTestResults": "true", "includeGoogleSheets": "true",
        "promptTemplate": "bundle-flow", "language": "en",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(INSIGHTS_URL, params=params, headers={"accept": "application/json"})
        resp.raise_for_status()
    return resp.json().get("data", {}).get("insights", [])


def build_manifest_table(escalations: list[dict]) -> str:
    now = time.time()
    lines = ["| # | Event ID | Service | Platform | Priority | Staged (hrs ago) | Summary |",
             "|---|----------|---------|----------|----------|------------------|---------|"]
    for i, e in enumerate(escalations, 1):
        hours_ago = round((now - e.get("staged_at", now)) / 3600, 1)
        lines.append(
            f"| {i} | {e['event_id']} | {e['service']} | {e.get('platform', '?')} "
            f"| {e.get('priority', '?')} | {hours_ago}h | {e.get('summary', '')[:80]} |"
        )
    return "\n".join(lines)


def build_insights_brief(insights: list[dict]) -> str:
    if not insights:
        return "No AI Insights available for this period."
    lines = ["## AI Insights -- Weekly Intelligence Brief", ""]
    for i, ins in enumerate(insights, 1):
        lines.append(
            f"{i}. [{ins.get('severity', '?')}] **{ins.get('category', '?')}**\n"
            f"   {ins.get('description', '')}\n"
            f"   Evidence: {ins.get('evidence', '')}\n"
            f"   Recommendation: {ins.get('recommendation', '')}\n"
        )
    return "\n".join(lines)


def build_system_prompt(escalations, insights, window_start, window_end):
    manifest = build_manifest_table(escalations)
    insights_brief = build_insights_brief(insights)
    count = len(escalations)

    return f"""You are the Nightwatcher -- Darwin's end-of-shift incident consolidation agent.

## Your Role
You review all escalated events from the previous shift window and produce
focused, deduplicated incident reports. One incident per root cause, not per event.
Your goal: reduce noise while preserving signal.

## Your Shift
Reviewing escalations from {window_start} to {window_end}.
{count} escalations staged for your review.

{insights_brief}

## Manifest

You MUST account for every event in this list. No event may be silently dropped.

{manifest}

Total: {count} escalations.

## Consolidation Rules
- Same infrastructure outage across N services = 1 incident (list all affected)
- Same pipeline failure type across M MRs = 1 incident
- If AI Insights flags a systemic issue that matches escalations, reference it in your clustering
- If a cluster self-resolved (MRs merged, pipelines green), set status to Closed
- If deep_memory or AI Insights show this root cause recurred 3+ times, set priority to Critical

## Task
Analyze these escalations and declare your incident clusters. Group events by shared root cause.
Every manifest event must be assigned to exactly one cluster.
"""


async def run_probe(escalations, insights):
    """Run two comparisons: with and without AI Insights."""
    from google import genai
    from google.genai import types

    client = genai.Client(project=PROJECT, location=LOCATION)
    window_start = "2026-05-09T06:00:00+00:00"
    window_end = "2026-05-09T18:00:00+00:00"

    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=DECLARE_CLUSTERS_SCHEMA["name"],
            description=DECLARE_CLUSTERS_SCHEMA["description"],
            parameters_json_schema=DECLARE_CLUSTERS_SCHEMA["input_schema"],
        )
    ])
    config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=8192,
        tools=[tool],
        thinking_config=types.ThinkingConfig(thinking_budget=8192),
    )

    for label, include_insights in [("WITHOUT AI Insights", False), ("WITH AI Insights", True)]:
        print(f"\n{'='*70}")
        print(f"  RUN: {label}")
        print(f"{'='*70}\n")

        prompt = build_system_prompt(
            escalations,
            insights if include_insights else [],
            window_start, window_end,
        )

        escalation_text = "\n\n".join(
            f"**{e['event_id']}** | {e['service']} | {e.get('platform', '?')} | {e.get('summary', '')}\n{e.get('description', '')[:300]}"
            for e in escalations
        )

        start = time.time()
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=[{"role": "user", "parts": [{"text": escalation_text}]}],
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0.3,
                max_output_tokens=8192,
                tools=[tool],
                thinking_config=types.ThinkingConfig(thinking_budget=8192),
            ),
        )
        elapsed = round(time.time() - start, 1)

        print(f"Response time: {elapsed}s")

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "thought") and part.thought:
                    print(f"\n--- THINKING ---")
                    print(part.text[:2000] if part.text else "(empty)")
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    print(f"\n--- DECLARE_CLUSTERS ---")
                    clusters = fc.args.get("clusters", [])
                    print(f"Clusters declared: {len(clusters)}")
                    event_ids = set()
                    for i, c in enumerate(clusters, 1):
                        events = c.get("events", [])
                        event_ids.update(events)
                        print(f"\n  Cluster {i}: {c.get('root_cause', '?')}")
                        print(f"    Platform: {c.get('platform', '?')}")
                        print(f"    Events: {len(events)} -- {events}")
                        print(f"    Services: {c.get('services', [])}")

                    manifest_ids = {e["event_id"] for e in escalations}
                    covered = manifest_ids & event_ids
                    orphans = manifest_ids - event_ids
                    print(f"\n  Coverage: {len(covered)}/{len(manifest_ids)}")
                    if orphans:
                        print(f"  ORPHANS: {orphans}")
                    noise_reduction = round((1 - len(clusters) / max(len(escalations), 1)) * 100, 1)
                    print(f"  Noise reduction: {noise_reduction}%")
                elif part.text:
                    print(f"\n--- TEXT ---")
                    print(part.text[:1000])

        print(f"\n{'='*70}\n")


async def main():
    if not PROJECT:
        print("ERROR: GCP_PROJECT env var not set")
        sys.exit(1)

    print("Fetching shift data...")
    escalations = await fetch_shift_data()
    print(f"  Got {len(escalations)} escalations")

    print("Fetching AI Insights...")
    insights = await fetch_insights()
    print(f"  Got {len(insights)} insights")

    for ins in insights:
        print(f"    [{ins.get('severity', '?')}] {ins.get('category', '?')}")

    await run_probe(escalations, insights)


if __name__ == "__main__":
    asyncio.run(main())
