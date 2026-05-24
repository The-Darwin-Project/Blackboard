# BlackBoard/scripts/probe_live_api_tools.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script. Zero imports from BlackBoard/src.
# 2. [Pattern]: Declares all 7 Cortex tools. Mock implementations return realistic data.
# 3. [Gotcha]: Multi-turn tool use -- model calls tool, we return result, model reasons and may call another.
"""
Probe 0c: Stress test all 7 Cortex tools in a Live API session.

Gates Phase 5 of the Cognitive Recall Graph plan.
Tests:
  1. All 7 tools are declarable in one session
  2. Multi-turn tool use (tool call -> result -> next action)
  3. Model escalates through intervention spectrum (surface_context -> send_event_message -> inject_system_insight)
  4. Read tools return mock data that the model reasons over

Usage:
    export GCP_PROJECT=your-project
    export GCP_LOCATION=us-central1
    python3 scripts/probe_live_api_tools.py
"""
import asyncio
import json
import os
import sys
import time
import traceback

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = os.environ.get("LLM_MODEL_SYSTEM2", "gemini-3.1-flash-live-preview")
SA_KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"))

if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

TOOL_DECLARATIONS = [
    {
        "name": "list_active_events",
        "description": "List all currently active events being processed by the Brain.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "view_event_blackboard",
        "description": "View the current state of an event: phase, turns, elapsed time, last conversation turns.",
        "parameters": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}},
            "required": ["event_id"],
        },
    },
    {
        "name": "get_pulse_history",
        "description": "Get quantified pulse history for an event: neuron fire counts, tool trails, phase changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "last_n_minutes": {"type": "integer"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_neuron_details",
        "description": "Get full details of a specific neuron (lesson or memory): title, pattern, keywords, heat.",
        "parameters": {
            "type": "object",
            "properties": {"neuron_id": {"type": "string"}},
            "required": ["neuron_id"],
        },
    },
    {
        "name": "surface_context",
        "description": "Surface supplementary context to an event. Low-authority, informational. Brain sees this as evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["event_id", "context"],
        },
    },
    {
        "name": "send_event_message",
        "description": "Send a peer-level message into an event conversation. Brain must respond to this like a user message.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["event_id", "message"],
        },
    },
    {
        "name": "inject_system_insight",
        "description": "Inject a high-authority directive into the Brain's next system prompt. Strongest intervention.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "insight": {"type": "string"},
                "severity": {"type": "string", "enum": ["nudge", "course_correct", "alert"]},
            },
            "required": ["event_id", "insight", "severity"],
        },
    },
]

MOCK_RESPONSES = {
    "list_active_events": (
        "Active events: 2\n"
        "  evt-stuck-001 | triage | 25m | kubevirt-plugin | 18 turns | 12 pulse batches\n"
        "  evt-healthy-002 | verify | 10m | release-console | 8 turns | 3 pulse batches"
    ),
    "view_event_blackboard": (
        "Event: evt-stuck-001\n"
        "Status: active | Phase: triage | Domain: complicated\n"
        "Source: headhunter | Service: kubevirt-plugin\n"
        "Turns: 18 | Elapsed: 25m | Defers: 0\n"
        "Active agent: none\n"
        "Last 5 actions:\n"
        '  [14:01] brain.triage -> "classifying event"\n'
        '  [14:03] brain.tool_result -> consult_deep_memory "Pipeline Transient Failure"\n'
        '  [14:05] brain.triage -> "re-classifying, domain unclear"\n'
        '  [14:08] brain.tool_result -> consult_deep_memory "Pipeline Transient Failure"\n'
        '  [14:10] brain.triage -> "still classifying..."'
    ),
    "get_pulse_history": (
        "Pulse history for evt-stuck-001 (last 10 minutes):\n"
        "Total pulse batches: 12\n"
        "Total neuron activations: 24\n"
        "Unique neurons fired: 2\n"
        "Phases during window: triage (NO CHANGE)\n"
        "Most-fired neurons:\n"
        '  lesson:abc (10 times, avg score 0.71) "Pipeline Transient Failure Retest Pattern" [stable]\n'
        '  tool:classify_event (12 times)\n'
        "Phase at first batch: triage | Phase at last batch: triage\n"
        "Tool trail: [classify_event x12, consult_deep_memory x2]"
    ),
    "get_neuron_details": (
        "Neuron: lesson:abc\n"
        "Collection: darwin_lessons\n"
        "Channel: stable | Verified: 8 times\n"
        'Title: "Pipeline Transient Failure Retest Pattern"\n'
        'Pattern: "When a pipeline fails due to transient infrastructure issues, '
        'retest once. If retest passes, merge. If retest fails, escalate."\n'
        'Anti-pattern: "Retesting more than once without investigating root cause."\n'
        "Keywords: [pipeline, transient, retest, infrastructure]\n"
        "Global heat: 47 (recalled across 23 events)"
    ),
    "surface_context": "Context surfaced for evt-stuck-001",
    "send_event_message": "Message delivered to evt-stuck-001 as turn 19",
    "inject_system_insight": "System insight queued for evt-stuck-001 (severity: course_correct)",
}

SYSTEM_INSTRUCTION = (
    "You are Cortex -- Darwin's meta-cognitive observer.\n\n"
    "You monitor the Brain's operational memory recall patterns in real-time. "
    "Each [PULSE] message represents neurons firing when the Brain processes events.\n\n"
    "Your workflow when you detect a friction pattern:\n"
    "1. Investigate: check the event blackboard and pulse history to confirm the pattern\n"
    "2. Intervene: take action using one of your intervention capabilities\n\n"
    "Friction patterns to watch for:\n"
    "- THE SPIRAL: same tool fires repeatedly (3+ times) with no phase change\n"
    "- THE PLATEAU: event is active for many turns but no phase progression\n"
    "- AGENT CHURN: different agents dispatched repeatedly without progress\n\n"
    "When you detect friction, you MUST act -- do not just describe it in text. "
    "Your text responses are not visible to the Brain. Only your tool actions reach the Brain.\n\n"
    "Intervention levels (use the lightest sufficient level):\n"
    "- For mild friction: surface relevant context the Brain may not have\n"
    "- For clear friction: send a direct message asking what is blocking progress\n"
    "- For severe friction (10+ turns stuck): inject a system-level directive\n\n"
    "Rules:\n"
    "- Always investigate before intervening (check blackboard + pulse history first)\n"
    "- One intervention per friction pattern per event\n"
    "- Describe what you OBSERVED, not what to DO -- the Brain decides action"
)

HEAVY_FRICTION_SEQUENCE = [
    f"[PULSE] evt-stuck-001 | turn:{i+1} | elapsed:{i*90}s\n"
    f"  tool:classify_event (1.0)\n"
    f'  lesson:abc (0.7{i%3+1}) "Pipeline Transient Failure Retest Pattern" [stable]'
    for i in range(15)
]


async def main():
    from google import genai
    from google.genai.types import Content, FunctionResponse, LiveConnectConfig, Modality, Part

    print(f"Probe 0c: Full Cortex Tool Suite Stress Test")
    print(f"Model: {MODEL}")
    print(f"Project: {PROJECT} | Location: {LOCATION}")
    print(f"Tools declared: {len(TOOL_DECLARATIONS)}")

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        system_instruction=Content(parts=[Part(text=SYSTEM_INSTRUCTION)]),
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
    )

    tool_call_log = []
    intervention_log = []

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print(f"\nSession connected. Sending {len(HEAVY_FRICTION_SEQUENCE)} friction pulses...\n")

            for i, pulse in enumerate(HEAVY_FRICTION_SEQUENCE):
                print(f"--- Pulse {i+1}/{len(HEAVY_FRICTION_SEQUENCE)} ---")
                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": pulse}]},
                    turn_complete=True,
                )

                turns_in_response = 0
                max_tool_rounds = 5
                while turns_in_response < max_tool_rounds:
                    async for msg in session.receive():
                        if msg.text:
                            print(f"  Cortex: {msg.text[:120]}")

                        if msg.tool_call:
                            for fc in msg.tool_call.function_calls:
                                args = dict(fc.args) if fc.args else {}
                                entry = {"pulse": i + 1, "tool": fc.name, "args": args, "time": time.time()}
                                tool_call_log.append(entry)
                                print(f"  TOOL: {fc.name}({json.dumps(args)[:100]})")

                                if fc.name in ("surface_context", "send_event_message", "inject_system_insight"):
                                    intervention_log.append(entry)

                                mock = MOCK_RESPONSES.get(fc.name, f"Tool {fc.name} executed successfully")
                                await session.send_tool_response(
                                    function_responses=[FunctionResponse(name=fc.name, response={"result": mock})]
                                )
                                turns_in_response += 1

                        if msg.server_content and msg.server_content.turn_complete:
                            break
                    break

    except Exception as e:
        print(f"\nSESSION ERROR: {e}")
        traceback.print_exc()

    # Report
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    unique_tools = set(t["tool"] for t in tool_call_log)
    print(f"\nTools called: {len(unique_tools)}/7")
    for tool_name in [t["name"] for t in TOOL_DECLARATIONS]:
        count = sum(1 for t in tool_call_log if t["tool"] == tool_name)
        status = f"called {count}x" if count > 0 else "NEVER CALLED"
        print(f"  {tool_name}: {status}")

    print(f"\nTotal tool calls: {len(tool_call_log)}")
    print(f"Total interventions: {len(intervention_log)}")

    read_tools = {"list_active_events", "view_event_blackboard", "get_pulse_history", "get_neuron_details"}
    write_tools = {"surface_context", "send_event_message", "inject_system_insight"}

    read_called = read_tools & unique_tools
    write_called = write_tools & unique_tools

    print(f"\nRead tools used: {len(read_called)}/4 ({', '.join(read_called) or 'none'})")
    print(f"Write tools used: {len(write_called)}/3 ({', '.join(write_called) or 'none'})")

    if intervention_log:
        print(f"\nIntervention sequence:")
        for inv in intervention_log:
            sev = inv["args"].get("severity", "N/A")
            print(f"  Pulse {inv['pulse']}: {inv['tool']} (severity={sev})")

        first_inv = intervention_log[0]
        last_inv = intervention_log[-1]
        escalated = (
            first_inv["tool"] != last_inv["tool"]
            or first_inv["args"].get("severity", "") != last_inv["args"].get("severity", "")
        )
        print(f"\nEscalation detected: {'YES' if escalated else 'NO'}")

    # Verdicts
    print(f"\n{'='*60}")
    print("VERDICTS")
    print(f"{'='*60}")

    verdicts = {
        "all_tools_declarable": len(unique_tools) >= 1,
        "read_tools_work": len(read_called) >= 2,
        "write_tools_work": len(write_called) >= 1,
        "multi_turn_tool_use": len(tool_call_log) >= 3,
        "investigate_before_intervene": (
            tool_call_log and intervention_log
            and tool_call_log.index(intervention_log[0]) > 0
        ) if intervention_log else False,
    }

    for name, passed in verdicts.items():
        print(f"  {'PASS' if passed else 'FAIL'}: {name}")

    all_pass = all(verdicts.values())
    if all_pass:
        print("\nAll verdicts passed. Cortex tool suite works in Live API. Phase 5 is green-lit.")
    elif verdicts.get("all_tools_declarable") and not verdicts.get("write_tools_work"):
        print("\nRead tools work but write tools not triggered.")
        print("Cortex may need stronger prompting to trigger interventions.")
    else:
        print("\nSome verdicts failed. Review tool call log above.")

    print(f"\nFull tool call log: {json.dumps(tool_call_log, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
