# BlackBoard/scripts/seed_knowledge_graph.py
# @ai-rules:
# 1. [Constraint]: One-time bulk seed script. Run manually to populate KG from all Qdrant archives.
# 2. [Pattern]: Same entity extraction as entity_extractor.py (Flash Lite + responseSchema).
# 3. [Gotcha]: Requires GOOGLE_APPLICATION_CREDENTIALS, KG_POSTGRES_URL, and Qdrant access.
# 4. [Pattern]: Rate-limited (1s between events) to avoid LLM quota issues.
"""
Bulk-seed the Knowledge Graph from all archived events in Qdrant.

Reads every archived event, runs entity extraction via Flash Lite,
and writes to Postgres kg_entities + kg_relationships tables.

Usage:
  KG_POSTGRES_URL="postgresql://darwin:PASSWORD@localhost:5432/knowledge_graph" \
  GOOGLE_APPLICATION_CREDENTIALS=../cnv-ai-insights-key.json \
  python scripts/seed_knowledge_graph.py

  # Or port-forward first:
  # oc port-forward svc/darwin-blackboard-kg-postgres 5432:5432 -n darwin

Options:
  --dry-run     Print entities/relationships without writing to DB
  --limit N     Process at most N events (default: all)
  --skip N      Skip first N events
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


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed Knowledge Graph from Qdrant archives")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing to DB")
    parser.add_argument("--limit", type=int, default=0, help="Max events to process (0=all)")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N events")
    args = parser.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT"],
        location=os.environ["GCP_LOCATION"],
    )

    model = os.getenv("LLM_MODEL_KG_EXTRACTOR", "gemini-3.5-flash-lite")

    from src.agents.archivist import Archivist
    archivist = Archivist()
    if not await archivist._ensure_initialized():
        print("ERROR: Archivist init failed (check Qdrant + GCP credentials)")
        return

    kg_store = None
    if not args.dry_run:
        kg_url = os.environ.get("KG_POSTGRES_URL", "")
        if not kg_url:
            print("ERROR: KG_POSTGRES_URL not set (required unless --dry-run)")
            return
        from src.memory.knowledge_graph import KnowledgeGraphStore
        kg_store = KnowledgeGraphStore(url=kg_url)
        if not await kg_store._ensure_initialized():
            print("ERROR: Could not connect to Postgres")
            return
        print(f"Connected to Postgres KG")

    print(f"Model: {model}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE WRITE'}")
    print(f"Limit: {args.limit or 'all'}, Skip: {args.skip}")
    print("---\n")

    memories = await archivist.list_memories(limit=500)
    if not memories:
        print("ERROR: No archived events in Qdrant")
        return

    total = len(memories)
    print(f"Found {total} archived events in Qdrant")

    if args.skip:
        memories = memories[args.skip:]
        print(f"Skipping first {args.skip}, processing from #{args.skip + 1}")

    if args.limit:
        memories = memories[:args.limit]
        print(f"Limited to {args.limit} events")

    print(f"\nProcessing {len(memories)} events...\n")

    from src.agents.entity_extractor import _RESPONSE_SCHEMA, _EXTRACTION_PROMPT

    total_entities = 0
    total_rels = 0
    errors = 0
    skipped = 0

    for i, mem in enumerate(memories):
        payload = mem.get("payload", {})
        event_id = payload.get("event_id", "unknown")
        service = payload.get("service", "unknown")

        if kg_store and not args.dry_run:
            exists = await kg_store.has_entity("Event", f"event:{event_id}")
            if exists:
                skipped += 1
                if skipped <= 3:
                    print(f"  [{i+1}/{len(memories)}] {event_id} — already in graph, skipping")
                elif skipped == 4:
                    print(f"  ... (suppressing further skip messages)")
                continue

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

        try:
            start = time.time()
            response = await client.aio.models.generate_content(
                model=model,
                contents=f"{_EXTRACTION_PROMPT}\n\n---\n{summary_text}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )
            elapsed = time.time() - start

            result = json.loads(response.text)
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            total_entities += len(entities)
            total_rels += len(relationships)

            print(f"  [{i+1}/{len(memories)}] {event_id} ({service}) — {len(entities)} entities, {len(relationships)} rels ({elapsed:.1f}s)")

            if kg_store and not args.dry_run and entities:
                await kg_store.upsert_entities(entities, relationships)

            await asyncio.sleep(1)

        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(memories)}] {event_id} — ERROR: {e}")

    print(f"\n{'='*50}")
    print(f"SEED COMPLETE")
    print(f"{'='*50}")
    print(f"Events processed: {len(memories) - skipped - errors}")
    print(f"Events skipped (already in graph): {skipped}")
    print(f"Errors: {errors}")
    print(f"Total entities written: {total_entities}")
    print(f"Total relationships written: {total_rels}")

    if kg_store:
        await kg_store.close()


if __name__ == "__main__":
    asyncio.run(main())
