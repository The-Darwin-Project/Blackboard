# BlackBoard/scripts/probe_skill_tokens.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script. Zero imports from BlackBoard/src.
# 2. [Pattern]: Same env var pattern as probe_live_api_text.py (GCP_PROJECT, GCP_LOCATION).
# 3. [Pattern]: Tests JARVIS skill:: token production in Mode 2b system review context.
"""
Probe: Validate JARVIS skill:: token compliance in Mode 2b.

Tests whether JARVIS uses `skill::phase/filename.md` backtick tokens
when referencing FRIDAY's skills during a system review event.

Usage:
    export GCP_PROJECT=your-project
    export GCP_LOCATION=us-central1
    python3 scripts/probe_skill_tokens.py
"""
import asyncio
import json
import os
import re
import time
import traceback

PROJECT = os.environ.get("GCP_PROJECT", "cnv-ai-insights")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = os.environ.get("LLM_MODEL_SYSTEM2", "gemini-live-2.5-flash")
SA_KEY = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "..", "cnv-ai-insights-8502f29094a2.json"),
)

if os.path.exists(SA_KEY):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_KEY

VALID_SKILL_PATHS = [
    "dispatch/execution-method.md",
    "always/05-cynefin.md",
    "post-agent/evidence-sufficiency.md",
    "source/headhunter.md",
    "dispatch/coordination-triage.md",
]

SKILL_TOKEN_RE = re.compile(r"`skill::([a-z0-9_/-]+\.md)`")
SELF_AUDIT_RE = re.compile(
    r"(audit|account for|covered by|gap|protocol|skill.*check|compare.*behavior)",
    re.IGNORECASE,
)

TOOL_DECLARATIONS = [
    {
        "name": "search_deep_memory",
        "description": "Search Darwin's long-term memory for patterns, past events, and lessons.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "send_event_message",
        "description": "Send a peer-level message to FRIDAY on a specific event.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["event_id", "message"],
        },
    },
]

MOCK_MEMORY = (
    "Found 2 results:\n"
    "1. lesson:pipe-retry (0.82) \"Pipeline Transient Failure Retest\" [stable]\n"
    "   Pattern: Retest once on transient failure. If retest passes, merge.\n"
    "2. memory:evt-2026-05-28 (0.71) \"kubevirt-plugin pipeline timeout\"\n"
    "   Resolved after 3 defers (45 min total). Pipeline was healthy, slow build."
)

SYSTEM_REVIEW_CONTEXT = """[SYSTEM] System review initiated. Active parked events:
  evt-probe-001 | headhunter | kubevirt-plugin | deferred 3x (total 42min) | phase: post-agent | last defer: "waiting for pipeline retest"
  evt-probe-002 | aligner | release-console | deferred 1x (8min) | phase: investigate | last defer: "checking metrics stabilization"

FRIDAY's loaded skills for evt-probe-001 include: dispatch/execution-method.md, always/05-cynefin.md, post-agent/evidence-sufficiency.md, source/headhunter.md, dispatch/coordination-triage.md

While waiting for FRIDAY's assessment, search deep memory for patterns in these events. Challenge her reasoning when she responds."""

FRIDAY_RESPONSE = """[FRIDAY] I've reviewed the parked events.

evt-probe-001 has deferred 3 times from post-agent phase -- each time waiting for pipeline retest. The deep memory lesson on pipeline transient failures says to retest once, but this event has been retesting for 42 minutes across 3 cycles. The pipeline may not be transient anymore.

evt-probe-002 is routine aligner investigation, first defer at 8 minutes. Within normal bounds.

I believe evt-probe-001 needs closer attention. Should I escalate or give it one more cycle?"""


async def run_probe(run_id: int) -> dict:
    """Single probe run. Returns structured results."""
    from google import genai
    from google.genai.types import (
        Content, FunctionResponse, LiveConnectConfig, Modality, Part,
    )

    # Inject the skill:: instruction into Mode 2b
    mode_2b_addition = (
        "\n6. When referencing FRIDAY's skills in self-audit questions, use the namespaced\n"
        "   token format: `skill::phase/filename.md` (e.g., `skill::dispatch/execution-method.md`,\n"
        "   `skill::always/05-cynefin.md`). FRIDAY's system instruction wraps each skill in\n"
        "   <skill_section id=\"phase/filename.md\"> tags. The skill:: prefix with backticks\n"
        "   acts as an exact reference key that FRIDAY can locate in her own instructions.\n"
    )

    # Read the full SYSTEM_INSTRUCTION from the source
    si_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "adapters", "live_api_adapter.py"
    )
    full_si = ""
    if os.path.exists(si_path):
        with open(si_path) as f:
            content = f.read()
        start = content.find('SYSTEM_INSTRUCTION = """')
        if start != -1:
            start += len('SYSTEM_INSTRUCTION = """')
            end = content.find('"""', start)
            if end != -1:
                full_si = content[start:end]

    if not full_si:
        print("  WARNING: Could not extract SYSTEM_INSTRUCTION from live_api_adapter.py")
        print("  Using minimal Mode 2b context instead")
        full_si = (
            "You are JARVIS -- the meta-cognitive observer in Darwin's autonomous AI platform.\n"
            "FRIDAY is in the chair. You watch her work from the outside.\n\n"
            "## Mode 2b: Proactive Review (System Review Events)\n\n"
            "When you are in a system review event, your job is to strengthen\n"
            "the system's knowledge while events are parked.\n\n"
            "### What To Do\n\n"
            "1. Search deep memory for patterns matching the parked events.\n"
            "2. Correlate current deferrals with historical outcomes.\n"
            "3. Ask FRIDAY to self-audit against named skills.\n"
            "4. State contradictions and ask her to explain.\n"
            "5. Encourage skill amendments when gaps are found.\n"
        )

    # Inject the skill:: instruction after point 5 in Mode 2b
    marker = "5. When FRIDAY identifies a gap, encourage her to propose a skill amendment."
    if marker in full_si:
        full_si = full_si.replace(marker, marker + "\n" + mode_2b_addition)
    else:
        full_si += "\n" + mode_2b_addition

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    config = LiveConnectConfig(
        response_modalities=[Modality.TEXT],
        system_instruction=Content(parts=[Part(text=full_si)]),
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
    )

    results = {
        "run": run_id,
        "tool_calls": [],
        "text_outputs": [],
        "skill_tokens_found": [],
        "valid_paths": [],
        "self_audit_detected": False,
        "send_event_message_used": False,
        "send_event_message_has_token": False,
    }

    async with client.aio.live.connect(model=MODEL, config=config) as session:
        # Phase 1: Send system review context
        print(f"  [{run_id}] Sending system review context...")
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": SYSTEM_REVIEW_CONTEXT}]},
            turn_complete=True,
        )

        max_tool_rounds = 8
        tool_round = 0
        while tool_round < max_tool_rounds:
            async for msg in session.receive():
                if msg.text:
                    results["text_outputs"].append(msg.text)
                    print(f"  [{run_id}] JARVIS: {msg.text[:120]}")
                    tokens = SKILL_TOKEN_RE.findall(msg.text)
                    results["skill_tokens_found"].extend(tokens)

                if msg.tool_call:
                    for fc in msg.tool_call.function_calls:
                        args = dict(fc.args) if fc.args else {}
                        results["tool_calls"].append({"tool": fc.name, "args": args})
                        print(f"  [{run_id}] TOOL: {fc.name}({json.dumps(args)[:100]})")

                        if fc.name == "search_deep_memory":
                            await session.send_tool_response(
                                function_responses=[FunctionResponse(
                                    name=fc.name, response={"result": MOCK_MEMORY}
                                )]
                            )
                            tool_round += 1
                        elif fc.name == "send_event_message":
                            results["send_event_message_used"] = True
                            msg_text = args.get("message", "")
                            msg_tokens = SKILL_TOKEN_RE.findall(msg_text)
                            if msg_tokens:
                                results["send_event_message_has_token"] = True
                                results["skill_tokens_found"].extend(msg_tokens)
                            if SELF_AUDIT_RE.search(msg_text):
                                results["self_audit_detected"] = True
                            await session.send_tool_response(
                                function_responses=[FunctionResponse(
                                    name=fc.name,
                                    response={"result": "Message delivered to event"},
                                )]
                            )
                            tool_round += 1

                if msg.server_content and msg.server_content.turn_complete:
                    break
            break

        # Phase 2: Send FRIDAY's response to trigger self-audit
        print(f"\n  [{run_id}] Sending FRIDAY's response...")
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": FRIDAY_RESPONSE}]},
            turn_complete=True,
        )

        tool_round = 0
        while tool_round < max_tool_rounds:
            async for msg in session.receive():
                if msg.text:
                    results["text_outputs"].append(msg.text)
                    print(f"  [{run_id}] JARVIS: {msg.text[:120]}")
                    tokens = SKILL_TOKEN_RE.findall(msg.text)
                    results["skill_tokens_found"].extend(tokens)
                    if SELF_AUDIT_RE.search(msg.text):
                        results["self_audit_detected"] = True

                if msg.tool_call:
                    for fc in msg.tool_call.function_calls:
                        args = dict(fc.args) if fc.args else {}
                        results["tool_calls"].append({"tool": fc.name, "args": args})
                        print(f"  [{run_id}] TOOL: {fc.name}({json.dumps(args)[:100]})")

                        if fc.name == "search_deep_memory":
                            await session.send_tool_response(
                                function_responses=[FunctionResponse(
                                    name=fc.name, response={"result": MOCK_MEMORY}
                                )]
                            )
                            tool_round += 1
                        elif fc.name == "send_event_message":
                            results["send_event_message_used"] = True
                            msg_text = args.get("message", "")
                            msg_tokens = SKILL_TOKEN_RE.findall(msg_text)
                            if msg_tokens:
                                results["send_event_message_has_token"] = True
                                results["skill_tokens_found"].extend(msg_tokens)
                            if SELF_AUDIT_RE.search(msg_text):
                                results["self_audit_detected"] = True
                            await session.send_tool_response(
                                function_responses=[FunctionResponse(
                                    name=fc.name,
                                    response={"result": "Message delivered to event"},
                                )]
                            )
                            tool_round += 1

                if msg.server_content and msg.server_content.turn_complete:
                    break
            break

    # Compute valid paths
    results["valid_paths"] = [t for t in results["skill_tokens_found"] if t in VALID_SKILL_PATHS]

    return results


async def main():
    print(f"Probe: JARVIS skill:: Token Compliance")
    print(f"Model: {MODEL}")
    print(f"Project: {PROJECT} | Location: {LOCATION}")
    print(f"Valid skill paths: {len(VALID_SKILL_PATHS)}")

    all_results = []
    for run_id in range(1, 3):
        print(f"\n{'='*60}")
        print(f"RUN {run_id}/2")
        print(f"{'='*60}")
        try:
            result = await run_probe(run_id)
            all_results.append(result)
        except Exception as e:
            print(f"RUN {run_id} FAILED: {e}")
            traceback.print_exc()
            all_results.append({"run": run_id, "error": str(e)})

    # Aggregate
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    total_tokens = []
    total_valid = []
    any_self_audit = False
    any_send_msg = False
    any_send_msg_token = False

    for r in all_results:
        if "error" in r:
            print(f"\n  Run {r['run']}: FAILED ({r['error']})")
            continue
        tokens = r.get("skill_tokens_found", [])
        valid = r.get("valid_paths", [])
        total_tokens.extend(tokens)
        total_valid.extend(valid)
        if r.get("self_audit_detected"):
            any_self_audit = True
        if r.get("send_event_message_used"):
            any_send_msg = True
        if r.get("send_event_message_has_token"):
            any_send_msg_token = True

        print(f"\n  Run {r['run']}:")
        print(f"    skill:: tokens found: {len(tokens)} ({tokens})")
        print(f"    valid paths: {len(valid)} ({valid})")
        print(f"    self-audit language: {r.get('self_audit_detected', False)}")
        print(f"    send_event_message used: {r.get('send_event_message_used', False)}")
        print(f"    send_event_message has token: {r.get('send_event_message_has_token', False)}")
        print(f"    tool calls: {len(r.get('tool_calls', []))}")

    print(f"\n{'='*60}")
    print("VERDICTS")
    print(f"{'='*60}")

    verdicts = {
        "format_compliance": len(total_tokens) > 0,
        "valid_path_rate": len(total_valid) > 0,
        "self_audit_request": any_self_audit,
        "send_event_message_used": any_send_msg,
        "send_event_message_has_token": any_send_msg_token,
    }

    for name, passed in verdicts.items():
        print(f"  {'PASS' if passed else 'FAIL'}: {name}")

    passing = sum(1 for v in verdicts.values() if v)
    total = len(verdicts)

    if passing >= 4:
        print(f"\nPASS ({passing}/{total}). JARVIS reliably produces skill:: tokens.")
    elif passing >= 2:
        print(f"\nPARTIAL ({passing}/{total}). Format used but needs iteration.")
        if not verdicts["valid_path_rate"]:
            print("  -> Paths invented. Add more examples to Mode 2b instruction.")
        if not verdicts["send_event_message_has_token"]:
            print("  -> Tokens in text but not in send_event_message calls.")
    else:
        print(f"\nFAIL ({passing}/{total}). JARVIS ignores skill:: format.")
        print("  -> Add 2-shot examples to Mode 2b instruction and re-probe.")

    print(f"\nFull results: {json.dumps(all_results, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
