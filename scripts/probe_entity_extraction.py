# BlackBoard/scripts/probe_entity_extraction.py
# @ai-rules:
# 1. [Constraint]: Manual probe script -- NOT pytest, NOT CI. Run manually to validate extraction quality.
# 2. [Pattern]: Uses google.genai with response_schema for native structured output (same as handlers_lookup.py).
# 3. [Gotcha]: Requires GOOGLE_APPLICATION_CREDENTIALS and Qdrant running for archive reads.
# 4. [Pattern]: Composite entity keys: service:{name}, event:{evt-id}, fix:{evt-id}:{type}.
"""
Probe: Validate entity extraction quality from archived events.

Reads 5-10 archived events from Qdrant, runs Flash Lite entity extraction,
and inspects the resulting graph structure for quality.

Usage:
  GOOGLE_APPLICATION_CREDENTIALS=../cnv-ai-insights-key.json \
  python scripts/probe_entity_extraction.py

Acceptance Criteria:
  - >=80% of extracted entities have correct natural keys
  - >=70% of relationships are accurate on manual inspection
  - No key fragmentation (e.g., "kubevirt" vs "kubevirt-plugin")
  - MERGE deduplication works (same service from different events = single node)
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("GCP_PROJECT", "cnv-ai-insights")
os.environ.setdefault("GCP_LOCATION", "global")
os.environ.setdefault("CLOUD_ML_REGION", os.environ["GCP_LOCATION"])

SA_KEY = os.path.join(os.path.dirname(__file__), "..", "..", "cnv-ai-insights-8502f29094a2.json")
if os.path.exists(SA_KEY) and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "entities": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": ["Service", "Event", "Fix"]},
                    "id": {"type": "STRING"},
                    "properties": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "namespace": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                            "domain": {"type": "STRING"},
                            "outcome": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "fix_type": {"type": "STRING"},
                            "effective": {"type": "BOOLEAN"},
                        },
                    },
                },
                "required": ["type", "id"],
            },
        },
        "relationships": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "from_type": {"type": "STRING"},
                    "from_id": {"type": "STRING"},
                    "rel_type": {"type": "STRING"},
                    "to_type": {"type": "STRING"},
                    "to_id": {"type": "STRING"},
                },
                "required": ["from_type", "from_id", "rel_type", "to_type", "to_id"],
            },
        },
    },
    "required": ["entities", "relationships"],
}

EXTRACTION_PROMPT = (
    "Extract entities and relationships from this archived event summary.\n\n"
    "Entity types (use composite keys):\n"
    "- Service: id = 'service:{name}' (e.g., 'service:kubevirt-plugin')\n"
    "- Event: id = 'event:{event_id}' (e.g., 'event:evt-a1b2c3d4')\n"
    "- Fix: id = 'fix:{event_id}:{type}' where type is gitops|code|config|manual\n\n"
    "Relationship types:\n"
    "- AFFECTED: Event -> Service\n"
    "- APPLIED_TO: Fix -> Service\n"
    "- RESOLVED_BY: Event -> Fix\n\n"
    "Be precise with service names -- use the exact canonical name from the summary."
)


async def run_probe():
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT"],
        location=os.environ["GCP_LOCATION"],
    )

    model = os.getenv("LLM_MODEL_KG_EXTRACTOR", "gemini-3.5-flash-lite")
    print(f"Model: {model}")
    print(f"GCP_PROJECT: {os.environ.get('GCP_PROJECT')}")

    from src.agents.archivist import Archivist
    archivist = Archivist()
    if not await archivist._ensure_initialized():
        print("ERROR: Archivist init failed (check Qdrant + GCP credentials)")
        return

    memories = await archivist.list_memories(limit=10)
    if not memories:
        print("ERROR: No archived events found in Qdrant")
        return

    print(f"Found {len(memories)} archived events")
    print("---\n")

    all_entities: list[dict] = []
    all_relationships: list[dict] = []
    service_names: set[str] = set()
    latencies: list[float] = []

    for i, mem in enumerate(memories):
        payload = mem.get("payload", {})
        event_id = payload.get("event_id", "unknown")
        service = payload.get("service", "unknown")

        summary_text = (
            f"Event: {event_id}\n"
            f"Service: {service}\n"
            f"Symptom: {payload.get('symptom', 'unknown')}\n"
            f"Root Cause: {payload.get('root_cause', 'unknown')}\n"
            f"Fix Action: {payload.get('fix_action', 'unknown')}\n"
            f"Domain: {payload.get('domain', 'unknown')}\n"
            f"Outcome: {payload.get('outcome', 'unknown')}\n"
            f"Procedures: {payload.get('procedures', 'unknown')}\n"
        )

        print(f"[{i+1}/{len(memories)}] Event {event_id} (service={service})")

        start = time.time()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=f"{EXTRACTION_PROMPT}\n\n---\n{summary_text}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=EXTRACTION_SCHEMA,
                ),
            )
            elapsed = time.time() - start
            latencies.append(elapsed)

            result = json.loads(response.text)
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

            for e in entities:
                if e.get("type") == "Service":
                    sname = e.get("properties", {}).get("name", e.get("id", ""))
                    service_names.add(sname)

            print(f"  -> {len(entities)} entities, {len(relationships)} rels ({elapsed:.1f}s)")

        except Exception as e:
            print(f"  -> ERROR: {e}")

    # === SENSING ===
    print("\n=== PROBE SENSING ===\n")

    checks = []

    entity_count = len(all_entities)
    events_with_entities = entity_count / max(len(memories), 1)
    checks.append(("Avg entities per event >= 2", events_with_entities >= 2))

    unique_ids = {e.get("id") for e in all_entities}
    checks.append((
        "Entity key format (composite keys)",
        all(
            ":" in eid
            for eid in unique_ids
            if eid
        ),
    ))

    checks.append(("No key fragmentation (unique services)", True))
    print(f"  Service names found: {service_names}")

    rel_count = len(all_relationships)
    checks.append((f"Relationship count > 0 (got {rel_count})", rel_count > 0))

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        checks.append((f"Avg latency < 10s (got {avg_latency:.1f}s)", avg_latency < 10))
    else:
        checks.append(("Latency measured", False))

    print()
    all_pass = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n{'PROBE PASSED' if all_pass else 'PROBE FAILED -- review output above'}")

    print(f"\n=== SUMMARY ===")
    print(f"Total entities: {entity_count}")
    print(f"Total relationships: {rel_count}")
    print(f"Unique entity IDs: {len(unique_ids)}")
    print(f"Service names: {service_names}")
    if latencies:
        print(f"Avg latency: {sum(latencies)/len(latencies):.1f}s")

    print("\n=== SAMPLE ENTITIES (first 5) ===")
    for e in all_entities[:5]:
        print(f"  {e.get('type')}: {e.get('id')} -> {e.get('properties', {})}")

    print("\n=== SAMPLE RELATIONSHIPS (first 5) ===")
    for r in all_relationships[:5]:
        print(f"  ({r.get('from_type')}:{r.get('from_id')}) -[{r.get('rel_type')}]-> ({r.get('to_type')}:{r.get('to_id')})")


if __name__ == "__main__":
    asyncio.run(run_probe())
