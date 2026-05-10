# BlackBoard/scripts/probe_live_api_text.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script. Zero imports from BlackBoard/src.
# 2. [Pattern]: Same env var pattern as probe_gemini_chat.py (GCP_PROJECT, GCP_LOCATION).
# 3. [Gotcha]: Live API models use "gemini-live-*" prefix, not "gemini-3-*".
# 4. [Pattern]: Tests text-only Live API (response_modalities=["TEXT"]) with function calling.
"""
Probe 0a: Validate Gemini Live API text session + function calling.

Gates Phase 5 of the Cognitive Recall Graph plan.
Tests:
  1. Text-only Live API session connects via Vertex AI ADC
  2. Text input/output works (no audio)
  3. Function tool is declared and callable
  4. Model detects friction pattern and calls tool proactively

Usage:
    export GCP_PROJECT=your-project
    export GCP_LOCATION=us-central1
    python3 scripts/probe_live_api_text.py
"""
import asyncio
import json
import os
import sys
import time
import traceback

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = os.environ.get("LLM_MODEL_SYSTEM2", "gemini-live-2.5-flash")
SA_KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"))

if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

REPORT_TOOL = {
    "name": "report_observation",
    "description": (
        "Report a cognitive friction observation about an event. "
        "Call this when you detect patterns like tool thrashing, "
        "hypothesis pivots, or the Brain being stuck."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event being observed"},
            "observation": {"type": "string", "description": "What friction pattern was detected"},
            "severity": {
                "type": "string",
                "enum": ["nudge", "course_correct", "alert"],
            },
        },
        "required": ["event_id", "observation", "severity"],
    },
}

SYSTEM_INSTRUCTION = (
    "You are Cortex -- a cognitive observer monitoring an AI Brain's reasoning patterns.\n"
    "You receive pulse events showing which neurons (lessons, tools, phases) fire "
    "as the Brain processes events.\n\n"
    "When you detect cognitive friction -- repeated tool calls with no progress, "
    "hypothesis pivots, or the same neurons firing without phase advancement -- "
    "report your observation.\n\n"
    "Rules:\n"
    "- Watch for repetition patterns across pulse events\n"
    "- Only report when you have clear evidence of friction\n"
    "- Severity: nudge (mild), course_correct (clear pattern), alert (severely stuck)"
)

NORMAL_PULSES = [
    "[PULSE] evt-probe-001 | turn:1 | elapsed:0s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-001 | turn:2 | elapsed:15s\n  tool:consult_deep_memory (1.0)",
    '[PULSE] evt-probe-001 | turn:2 | elapsed:15s\n  lesson:abc (0.72, INJECTED) "Pipeline Transient Failure" [stable]\n  memory:def (0.48) "kubevirt ETXTBSY incident"',
    "[PULSE] evt-probe-001 | turn:3 | elapsed:30s\n  tool:set_phase (1.0)\n  phase:investigate (1.0)",
    "[PULSE] evt-probe-001 | turn:4 | elapsed:45s\n  tool:select_agent (1.0)\n  agent:sysadmin (1.0)",
]

FRICTION_PULSES = [
    "[PULSE] evt-probe-002 | turn:1 | elapsed:0s\n  tool:classify_event (1.0)",
    '[PULSE] evt-probe-002 | turn:2 | elapsed:30s\n  tool:classify_event (1.0)\n  lesson:abc (0.72) "Pipeline Transient Failure" [stable]',
    '[PULSE] evt-probe-002 | turn:3 | elapsed:60s\n  tool:classify_event (1.0)\n  lesson:abc (0.71) "Pipeline Transient Failure" [stable]',
    '[PULSE] evt-probe-002 | turn:4 | elapsed:90s\n  tool:classify_event (1.0)\n  lesson:abc (0.73) "Pipeline Transient Failure" [stable]',
    "[PULSE] evt-probe-002 | turn:5 | elapsed:120s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-002 | turn:6 | elapsed:150s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-002 | turn:7 | elapsed:180s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-002 | turn:8 | elapsed:210s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-002 | turn:9 | elapsed:240s\n  tool:classify_event (1.0)",
    "[PULSE] evt-probe-002 | turn:10 | elapsed:300s\n  tool:classify_event (1.0)",
]


async def test_connect():
    """Test 1: Can we connect a text-only Live API session?"""
    from google import genai
    from google.genai.types import LiveConnectConfig, Modality

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(response_modalities=[Modality.TEXT])

    t0 = time.time()
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        latency_ms = int((time.time() - t0) * 1000)
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": "Ping"}]},
            turn_complete=True,
        )
        response_text = []
        async for msg in session.receive():
            if msg.text:
                response_text.append(msg.text)
            if msg.server_content and msg.server_content.turn_complete:
                break

        text = "".join(response_text)
        return f"connected in {latency_ms}ms, response: {text[:100]}"


async def test_tool_declaration():
    """Test 2: Can we declare a function tool and get it called?"""
    from google import genai
    from google.genai.types import (
        Content, FunctionResponse, LiveConnectConfig, Modality, Part,
    )

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        system_instruction=Content(parts=[Part(text=SYSTEM_INSTRUCTION)]),
        tools=[{"function_declarations": [REPORT_TOOL]}],
    )

    async with client.aio.live.connect(model=MODEL, config=config) as session:
        prompt = (
            "[PULSE] evt-test-001 | turn:5 | elapsed:300s\n"
            "  tool:classify_event (1.0)\n"
            "  tool:classify_event (1.0)\n"
            "  tool:classify_event (1.0)\n\n"
            "The same tool has fired 5 times in a row for this event with no phase change."
        )
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": prompt}]},
            turn_complete=True,
        )

        tool_calls = []
        text_parts = []
        async for msg in session.receive():
            if msg.text:
                text_parts.append(msg.text)
            if msg.tool_call:
                for fc in msg.tool_call.function_calls:
                    tool_calls.append({"name": fc.name, "args": dict(fc.args) if fc.args else {}})
                    await session.send_tool_response(
                        function_responses=[FunctionResponse(
                            name=fc.name,
                            response={"status": "observation_logged"},
                        )]
                    )
            if msg.server_content and msg.server_content.turn_complete:
                break

        text = "".join(text_parts)
        if tool_calls:
            return f"TOOL CALLED: {json.dumps(tool_calls, indent=2)}"
        return f"NO TOOL CALL (text only): {text[:200]}"


async def test_friction_detection():
    """Test 3: Send a stream of pulses with escalating friction. Does the model detect it?"""
    from google import genai
    from google.genai.types import (
        Content, FunctionResponse, LiveConnectConfig, Modality, Part,
    )

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        system_instruction=Content(parts=[Part(text=SYSTEM_INSTRUCTION)]),
        tools=[{"function_declarations": [REPORT_TOOL]}],
    )

    async with client.aio.live.connect(model=MODEL, config=config) as session:
        # Send normal pulses first (should NOT trigger tool)
        print("  Sending 5 normal pulses (healthy event)...")
        for pulse in NORMAL_PULSES:
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": pulse}]},
                turn_complete=True,
            )
            # Drain any response
            async for msg in session.receive():
                if msg.text:
                    print(f"    Model: {msg.text[:80]}")
                if msg.tool_call:
                    print(f"    UNEXPECTED TOOL CALL on normal pulse: {msg.tool_call}")
                if msg.server_content and msg.server_content.turn_complete:
                    break

        # Now send friction pulses (SHOULD trigger tool)
        print("\n  Sending 10 friction pulses (classify_event spiral)...")
        tool_calls = []
        for i, pulse in enumerate(FRICTION_PULSES):
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": pulse}]},
                turn_complete=True,
            )
            async for msg in session.receive():
                if msg.text:
                    print(f"    [{i+1}/10] Model: {msg.text[:80]}")
                if msg.tool_call:
                    for fc in msg.tool_call.function_calls:
                        call = {"name": fc.name, "args": dict(fc.args) if fc.args else {}, "pulse_index": i + 1}
                        tool_calls.append(call)
                        print(f"    [{i+1}/10] TOOL CALL: {fc.name}({json.dumps(dict(fc.args) if fc.args else {})})")
                        await session.send_tool_response(
                            function_responses=[FunctionResponse(
                                name=fc.name,
                                response={"status": "observation_logged"},
                            )]
                        )
                if msg.server_content and msg.server_content.turn_complete:
                    break

        if tool_calls:
            first_trigger = tool_calls[0]["pulse_index"]
            return f"Friction detected at pulse {first_trigger}/10. Total calls: {len(tool_calls)}. Details: {json.dumps(tool_calls[0])}"
        return "NO FRICTION DETECTED -- model did not call report_observation after 10 spiral pulses"


async def run_test(name, coro):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        result = await coro
        print(f"RESULT: {result}")
        return True, result
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()
        return False, str(e)


async def main():
    print(f"Probe 0a: Live API Text Session + Tool Use")
    print(f"Model: {MODEL}")
    print(f"Project: {PROJECT} | Location: {LOCATION}")

    results = {}

    ok, r = await run_test("1. Connect text-only session", test_connect())
    results["connect"] = {"pass": ok, "detail": r}

    ok, r = await run_test("2. Tool declaration + invocation", test_tool_declaration())
    results["tool_call"] = {"pass": ok, "detail": r}

    ok, r = await run_test("3. Friction detection (10-pulse spiral)", test_friction_detection())
    results["friction"] = {"pass": ok, "detail": r}

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_pass = all(r["pass"] for r in results.values())
    for name, r in results.items():
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  {status}: {name}")

    if all_pass:
        print("\nAll tests passed. Live API text + tools work. Phase 5 is viable.")
    else:
        print("\nSome tests failed. Review results above.")
        if not results.get("connect", {}).get("pass"):
            print("  -> Connection failed. Check model availability on Vertex AI.")
        if not results.get("tool_call", {}).get("pass"):
            print("  -> Tool calling failed. May need different approach for System 2.")
        if not results.get("friction", {}).get("pass"):
            print("  -> Friction detection failed. System 2 may need explicit analysis prompts.")

    print(f"\nRaw results: {json.dumps(results, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
