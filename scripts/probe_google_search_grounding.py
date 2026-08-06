# BlackBoard/scripts/probe_google_search_grounding.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script. Zero imports from BlackBoard/src.
# 2. [Pattern]: Validates the "googleSearch as function call" workaround -- isolated
#    generateContent with grounding only, no function declarations.
# 3. [Gotcha]: google_search tool and function_declarations CANNOT coexist in one request.
#    This probe proves the isolated-call pattern works as a workaround.
"""
Probe: Google Search grounding via isolated generateContent call.

Validates the architecture:
  FRIDAY/JARVIS ---> googleSearch FC ---> isolated generateContent (grounding only) ---> return output

Tests:
  1. Isolated call with google_search tool returns grounded text + groundingMetadata
  2. groundingChunks contain web URIs and titles (structured data for function response)
  3. Latency measurement for the isolated call
  4. Verify the response shape is suitable for returning as a function_response

Usage:
    python3 scripts/probe_google_search_grounding.py
    python3 scripts/probe_google_search_grounding.py "What CVEs affect glibc on RHEL 9?"
"""
import asyncio
import json
import os
import sys
import time

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = os.environ.get("GROUNDING_MODEL", "gemini-2.0-flash")

SA_KEY = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"),
)

if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

TEST_QUERIES = [
    "What is the latest Kubernetes release version and when was it released?",
    "CVE glibc RHEL 9 2026",
    "OpenShift 4.17 known issues with Tekton pipelines",
]


async def grounded_search(client, query: str) -> dict:
    """Execute an isolated grounded search -- the core of the workaround.

    This is exactly what the function call handler would do:
    receive query from FRIDAY/JARVIS, make isolated call, return structured result.
    """
    from google.genai import types

    t0 = time.perf_counter()

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.0,
            max_output_tokens=2048,
        ),
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    grounding_meta = None
    chunks = []
    search_queries = []

    if response.candidates:
        candidate = response.candidates[0]
        gm = getattr(candidate, "grounding_metadata", None)
        if gm:
            grounding_meta = gm
            raw_chunks = getattr(gm, "grounding_chunks", None) or []
            for chunk in raw_chunks:
                web = getattr(chunk, "web", None)
                if web:
                    chunks.append({
                        "title": getattr(web, "title", ""),
                        "uri": getattr(web, "uri", ""),
                    })
            raw_queries = getattr(gm, "web_search_queries", None) or []
            search_queries = list(raw_queries)

    summary_text = response.text or ""

    return {
        "query": query,
        "summary": summary_text,
        "chunks": chunks,
        "search_queries": search_queries,
        "elapsed_ms": round(elapsed_ms, 1),
        "has_grounding": grounding_meta is not None,
        "chunk_count": len(chunks),
    }


def format_function_response(result: dict) -> dict:
    """Format as what we'd return to FRIDAY/JARVIS as the function_response payload."""
    return {
        "summary": result["summary"][:3000],
        "sources": result["chunks"][:10],
        "search_queries_used": result["search_queries"],
    }


async def main():
    from google import genai

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    print(f"google-genai version: {genai.__version__}")
    print(f"Project: {PROJECT}, Location: {LOCATION}, Model: {MODEL}")
    print(f"SA key: {SA_KEY}")
    print()

    queries = TEST_QUERIES
    if len(sys.argv) > 1:
        queries = [" ".join(sys.argv[1:])]

    results = []
    for query in queries:
        print(f"{'='*70}")
        print(f"QUERY: {query}")
        print(f"{'='*70}")

        try:
            result = await grounded_search(client, query)
            results.append(result)

            print(f"  Latency: {result['elapsed_ms']}ms")
            print(f"  Has grounding: {result['has_grounding']}")
            print(f"  Chunks: {result['chunk_count']}")
            print(f"  Search queries used: {result['search_queries']}")
            print(f"  Summary (first 300 chars):")
            print(f"    {result['summary'][:300]}")
            print()

            if result["chunks"]:
                print(f"  Sources:")
                for i, chunk in enumerate(result["chunks"][:5], 1):
                    print(f"    {i}. {chunk['title'][:60]}")
                    print(f"       {chunk['uri']}")
                print()

            fn_resp = format_function_response(result)
            print(f"  Function response payload (what FRIDAY would see):")
            print(f"    {json.dumps(fn_resp, indent=2)[:1000]}")
            print()

        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append({"query": query, "error": str(e)})
            print()

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        status = "PASS" if r.get("has_grounding") else "FAIL"
        latency = f"{r.get('elapsed_ms', '?')}ms"
        chunks = r.get("chunk_count", 0)
        print(f"  {status} | {latency:>8} | {chunks} chunks | {r['query'][:50]}")

    all_pass = all(r.get("has_grounding") for r in results)
    avg_latency = sum(r.get("elapsed_ms", 0) for r in results) / max(len(results), 1)
    print(f"\n  Average latency: {avg_latency:.0f}ms")
    print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")

    if all_pass:
        print("\n  CONCLUSION: Isolated grounded search works.")
        print("  Safe to implement as a function call handler for FRIDAY + JARVIS.")
    else:
        print("\n  CONCLUSION: Grounding not returning metadata. Check model/region support.")


if __name__ == "__main__":
    asyncio.run(main())
