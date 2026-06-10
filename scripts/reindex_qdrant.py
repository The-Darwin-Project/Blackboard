# BlackBoard/scripts/reindex_qdrant.py
# @ai-rules:
# 1. [Constraint]: Standalone script. Only imports google-genai + httpx (no BlackBoard src imports).
# 2. [Pattern]: Same env var pattern as other probe scripts (GCP_PROJECT, GCP_LOCATION, QDRANT_URL).
# 3. [Gotcha]: Must reconstruct embed_text identically to archivist.py for each collection.
# 4. [Pattern]: Dry-run by default (--dry-run). Pass --execute to actually write vectors.
# 5. [Constraint]: Rate-limits embed calls (BATCH_DELAY_S) to avoid Vertex AI quota spikes.
"""
Re-index all Qdrant vectors after an embedding model change.

Scrolls every point in darwin_events, darwin_lessons, and darwin_feedback,
re-embeds from payload text fields using the current EMBEDDING_MODEL, and
upserts with the same point ID + payload (only the vector changes).

Usage:
    export GCP_PROJECT=cnv-ai-insights
    export GCP_LOCATION=global
    export GOOGLE_APPLICATION_CREDENTIALS=path/to/sa-key.json

    # Dry run (counts points, no writes):
    python3 scripts/reindex_qdrant.py

    # Execute:
    python3 scripts/reindex_qdrant.py --execute

    # Single collection:
    python3 scripts/reindex_qdrant.py --execute --collection darwin_lessons
"""
import argparse
import asyncio
import json
import os
import sys
import time

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIMS = int(os.environ.get("EMBEDDING_DIMS", "768"))
BATCH_DELAY_S = float(os.environ.get("REINDEX_DELAY_S", "0.2"))

SA_KEY = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"),
)
if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

COLLECTIONS = ["darwin_events", "darwin_lessons", "darwin_feedback"]


def build_embed_text_events(p: dict) -> str:
    """Reconstruct embed text for darwin_events (matches archivist.archive_event)."""
    return (
        f"{p.get('symptom', '')} "
        f"{p.get('root_cause', '')} "
        f"{p.get('fix_action', '')} "
        f"{' '.join(p.get('pattern_keywords', p.get('keywords', [])))} "
        f"{' '.join(p.get('instance_keywords', []))} "
        f"{p.get('procedures', '')} "
        f"{p.get('outcome', '')}"
    ).strip()


def build_embed_text_lessons(p: dict) -> str:
    """Reconstruct embed text for darwin_lessons (matches archivist.store_lesson)."""
    return (
        f"{p.get('title', '')} {p.get('pattern', '')} "
        f"{p.get('anti_pattern', '')} {' '.join(p.get('keywords', []))}"
    ).strip()


def build_embed_text_feedback(p: dict) -> str:
    """Reconstruct embed text for darwin_feedback (matches archivist.store_feedback)."""
    return p.get("turn_text", "")[:500]


EMBED_BUILDERS = {
    "darwin_events": build_embed_text_events,
    "darwin_lessons": build_embed_text_lessons,
    "darwin_feedback": build_embed_text_feedback,
}


async def scroll_all(base_url: str, collection: str) -> list[dict]:
    """Scroll all points from a Qdrant collection."""
    import httpx

    points = []
    offset = None
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        while True:
            body = {"limit": 256, "with_payload": True}
            if offset is not None:
                body["offset"] = offset
            resp = await client.post(f"/collections/{collection}/points/scroll", json=body)
            resp.raise_for_status()
            data = resp.json().get("result", {})
            batch = data.get("points", [])
            points.extend(batch)
            offset = data.get("next_page_offset")
            if not offset or not batch:
                break
    return points


async def upsert_point(base_url: str, collection: str, point_id: str,
                       vector: list[float], payload: dict) -> None:
    """Upsert a single point to Qdrant."""
    import httpx

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        resp = await client.put(
            f"/collections/{collection}/points",
            json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
        )
        resp.raise_for_status()


async def embed(client, text: str) -> list[float]:
    """Generate embedding vector with output_dimensionality."""
    from google.genai import types

    r = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    return r.embeddings[0].values


async def reindex_collection(genai_client, collection: str, execute: bool) -> dict:
    """Re-index a single collection. Returns stats."""
    builder = EMBED_BUILDERS.get(collection)
    if not builder:
        return {"collection": collection, "error": f"No embed builder for {collection}"}

    print(f"\n{'='*60}")
    print(f"Collection: {collection}")
    print(f"{'='*60}")

    points = await scroll_all(QDRANT_URL, collection)
    print(f"  Points found: {len(points)}")

    if not points:
        return {"collection": collection, "total": 0, "reindexed": 0, "skipped": 0, "errors": 0}

    reindexed = 0
    skipped = 0
    errors = 0

    for i, point in enumerate(points):
        point_id = point.get("id")
        payload = point.get("payload", {})
        text = builder(payload)

        if not text.strip():
            print(f"  [{i+1}/{len(points)}] {point_id}: SKIP (empty embed text)")
            skipped += 1
            continue

        if execute:
            try:
                vector = await embed(genai_client, text)
                await upsert_point(QDRANT_URL, collection, point_id, vector, payload)
                reindexed += 1
                label = payload.get("event_id") or payload.get("title") or payload.get("lesson_id") or point_id
                print(f"  [{i+1}/{len(points)}] {label}: OK ({len(vector)} dims)")
                await asyncio.sleep(BATCH_DELAY_S)
            except Exception as e:
                errors += 1
                print(f"  [{i+1}/{len(points)}] {point_id}: ERROR {e}")
        else:
            label = payload.get("event_id") or payload.get("title") or payload.get("lesson_id") or point_id
            print(f"  [{i+1}/{len(points)}] {label}: would re-embed ({len(text)} chars)")
            reindexed += 1

    stats = {
        "collection": collection,
        "total": len(points),
        "reindexed": reindexed,
        "skipped": skipped,
        "errors": errors,
    }
    print(f"\n  Summary: {json.dumps(stats)}")
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Re-index Qdrant vectors after embedding model change")
    parser.add_argument("--execute", action="store_true", help="Actually write vectors (default: dry-run)")
    parser.add_argument("--collection", type=str, help="Re-index a single collection")
    args = parser.parse_args()

    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Output dims:     {EMBEDDING_DIMS}")
    print(f"Qdrant URL:      {QDRANT_URL}")
    print(f"GCP project:     {PROJECT}")
    print(f"Mode:            {'EXECUTE' if args.execute else 'DRY-RUN'}")

    from google import genai
    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    collections = [args.collection] if args.collection else COLLECTIONS
    all_stats = []
    start = time.time()

    for coll in collections:
        stats = await reindex_collection(client, coll, args.execute)
        all_stats.append(stats)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"COMPLETE ({elapsed:.1f}s)")
    print(f"{'='*60}")
    total_points = sum(s.get("total", 0) for s in all_stats)
    total_reindexed = sum(s.get("reindexed", 0) for s in all_stats)
    total_errors = sum(s.get("errors", 0) for s in all_stats)
    print(f"  Total points:    {total_points}")
    print(f"  Re-indexed:      {total_reindexed}")
    print(f"  Errors:          {total_errors}")
    if not args.execute:
        print(f"\n  This was a DRY RUN. Pass --execute to write vectors.")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
