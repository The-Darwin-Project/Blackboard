# BlackBoard/scripts/probe_live_api_models.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script. Zero imports from BlackBoard/src.
# 2. [Pattern]: Tests both Live API model candidates side-by-side.
# 3. [Gotcha]: gemini-3.1-flash-live-preview may not be on Vertex AI yet -- handle gracefully.
"""
Probe 0b: Compare Live API models + test session rotation.

Gates Phase 5 of the Cognitive Recall Graph plan.
Tests:
  1. gemini-live-2.5-flash-native-audio (GA) -- text + tool use
  2. gemini-3.1-flash-live-preview -- text + tool use (may fail if not on Vertex AI)
  3. Session rotation: connect -> 10 turns -> summarize -> reconnect with summary
  4. Latency comparison

Usage:
    export GCP_PROJECT=your-project
    export GCP_LOCATION=us-central1
    python3 scripts/probe_live_api_models.py
"""
import asyncio
import json
import os
import sys
import time
import traceback

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
SA_KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"))

if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

MODELS = [
    "gemini-live-2.5-flash",
    "gemini-3.1-flash-live-preview",
]

REPORT_TOOL = {
    "name": "report_observation",
    "description": "Report a cognitive friction observation about an event.",
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "observation": {"type": "string"},
            "severity": {"type": "string", "enum": ["nudge", "course_correct", "alert"]},
        },
        "required": ["event_id", "observation", "severity"],
    },
}

SYSTEM_INSTRUCTION = (
    "You are Cortex -- a cognitive observer monitoring an AI Brain's reasoning patterns. "
    "You receive pulse events showing which neurons fire as the Brain processes events. "
    "When you detect cognitive friction, report your observation."
)

PULSE_SEQUENCE = [
    f"[PULSE] evt-model-test | turn:{i+1} | elapsed:{i*30}s\n  tool:classify_event (1.0)"
    for i in range(10)
]


async def send_and_receive(session, text):
    """Send text, collect response (text + tool calls). Returns (text, tool_calls, latency_ms)."""
    from google.genai.types import FunctionResponse

    t0 = time.time()
    await session.send_client_content(
        turns={"role": "user", "parts": [{"text": text}]},
        turn_complete=True,
    )
    text_parts = []
    tool_calls = []
    async for msg in session.receive():
        if msg.text:
            text_parts.append(msg.text)
        if msg.tool_call:
            for fc in msg.tool_call.function_calls:
                tool_calls.append({"name": fc.name, "args": dict(fc.args) if fc.args else {}})
                await session.send_tool_response(
                    function_responses=[FunctionResponse(name=fc.name, response={"status": "ok"})]
                )
        if msg.server_content and msg.server_content.turn_complete:
            break

    latency_ms = int((time.time() - t0) * 1000)
    return "".join(text_parts), tool_calls, latency_ms


async def test_model(model_name: str):
    """Run the full test suite against one model."""
    from google import genai
    from google.genai.types import Content, LiveConnectConfig, Modality, Part

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        system_instruction=Content(parts=[Part(text=SYSTEM_INSTRUCTION)]),
        tools=[{"function_declarations": [REPORT_TOOL]}],
    )

    results = {"model": model_name, "connect": False, "text_io": False,
               "tool_call": False, "session_rotation": False, "latencies_ms": []}

    # Test 1: Connect
    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            results["connect"] = True
            print(f"    Connected to {model_name}")

            # Test 2: Text I/O -- send a pulse, get text response
            text, tools, lat = await send_and_receive(session, PULSE_SEQUENCE[0])
            results["latencies_ms"].append(lat)
            results["text_io"] = bool(text or tools)
            print(f"    Text I/O: {'PASS' if results['text_io'] else 'FAIL'} ({lat}ms)")

            # Test 3: Send 9 more friction pulses, check for tool call
            for pulse in PULSE_SEQUENCE[1:]:
                text, tools, lat = await send_and_receive(session, pulse)
                results["latencies_ms"].append(lat)
                if tools:
                    results["tool_call"] = True
                    print(f"    Tool call triggered: {tools[0]['name']}({json.dumps(tools[0]['args'])})")

            if not results["tool_call"]:
                print("    Tool call: not triggered during pulse sequence")

    except Exception as e:
        print(f"    Connection/session error: {e}")
        if "not found" in str(e).lower() or "404" in str(e):
            print(f"    Model {model_name} likely not available on Vertex AI")
        results["error"] = str(e)
        return results

    # Test 4: Session rotation
    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            # Send a few turns to build context
            for pulse in PULSE_SEQUENCE[:3]:
                await send_and_receive(session, pulse)

            # Ask for summary
            summary_text, _, _ = await send_and_receive(
                session,
                "Summarize your current observations about all active events in 2-3 sentences."
            )
            print(f"    Session summary: {summary_text[:150]}")

        # Reconnect with summary as context
        async with client.aio.live.connect(model=model_name, config=config) as session2:
            context_text, _, lat = await send_and_receive(
                session2,
                f"Previous session summary: {summary_text}\n\n"
                f"Continuing observation. New pulse:\n{PULSE_SEQUENCE[5]}"
            )
            results["session_rotation"] = bool(context_text)
            print(f"    Session rotation: {'PASS' if results['session_rotation'] else 'FAIL'} ({lat}ms)")

    except Exception as e:
        print(f"    Session rotation error: {e}")
        results["rotation_error"] = str(e)

    # Latency stats
    lats = results["latencies_ms"]
    if lats:
        results["avg_latency_ms"] = sum(lats) // len(lats)
        results["max_latency_ms"] = max(lats)
        results["min_latency_ms"] = min(lats)
        print(f"    Latency: avg={results['avg_latency_ms']}ms, min={results['min_latency_ms']}ms, max={results['max_latency_ms']}ms")

    return results


async def main():
    print("Probe 0b: Live API Model Comparison")
    print(f"Project: {PROJECT} | Location: {LOCATION}")

    all_results = {}
    for model in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")
        all_results[model] = await test_model(model)

    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Feature':<25} | {'2.5 Flash (GA)':<20} | {'3.1 Flash (Preview)':<20}")
    print(f"{'-'*25}-+-{'-'*20}-+-{'-'*20}")

    r25 = all_results.get(MODELS[0], {})
    r31 = all_results.get(MODELS[1], {})
    for feat in ["connect", "text_io", "tool_call", "session_rotation"]:
        v25 = "PASS" if r25.get(feat) else "FAIL"
        v31 = "PASS" if r31.get(feat) else "FAIL"
        print(f"{feat:<25} | {v25:<20} | {v31:<20}")

    avg25 = r25.get("avg_latency_ms", "N/A")
    avg31 = r31.get("avg_latency_ms", "N/A")
    print(f"{'avg_latency_ms':<25} | {str(avg25):<20} | {str(avg31):<20}")

    # Recommendation
    print(f"\n{'='*60}")
    print("RECOMMENDATION")
    print(f"{'='*60}")
    if r31.get("connect") and r31.get("tool_call"):
        print(f"Use {MODELS[1]} (3.1 Flash) as primary -- better instruction following.")
        print(f"Keep {MODELS[0]} (2.5 Flash) as fallback.")
    elif r25.get("connect") and r25.get("tool_call"):
        print(f"Use {MODELS[0]} (2.5 Flash GA) -- 3.1 not available or tool calling broken.")
    elif r25.get("connect"):
        print(f"{MODELS[0]} connects but tool calling doesn't work.")
        print("System 2 needs explicit analysis prompts instead of proactive detection.")
    else:
        print("Neither model works for text + tools on Vertex AI.")
        print("Fallback: standard generateContent multi-turn with managed state.")

    print(f"\nRaw results: {json.dumps(all_results, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
