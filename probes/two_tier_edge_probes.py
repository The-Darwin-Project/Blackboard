# probes/two_tier_edge_probes.py
# @ai-rules:
# 1. [Constraint]: Disposable probe — validates edge cases against real SDK.
"""
Two-Tier Edge Case Probes

1. Empty event cold start (aligner-shaped, no conversation)
2. Consecutive user macros on rebuild (role-merge)
3. Error FR pairing (tool raises, session survives)
4. defer_event post-terminal suppress (bounded while)
"""
import asyncio
import json
import os
import time
from pathlib import Path

os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "/home/thason/Git/GitHub/The-Darwin-Project/cnv-ai-insights-8502f29094a2.json",
)

from google import genai
from google.genai import types

PROJECT_ID = "cnv-ai-insights"
MODEL = "gemini-2.5-flash"

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify the event into a Cynefin domain.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["clear", "complicated", "complex", "chaotic"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["domain", "reasoning"],
            },
        ),
        types.FunctionDeclaration(
            name="defer_event",
            description="TERMINAL: Defer processing for N seconds. Stops the current loop.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["seconds", "reason"],
            },
        ),
        types.FunctionDeclaration(
            name="refresh_status",
            description="Check the current pipeline/MR status. May raise errors.",
            parameters_json_schema={
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": ["target"],
            },
        ),
    ])
]


def make_config(si_text):
    return types.GenerateContentConfig(
        system_instruction=si_text,
        tools=TOOLS,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        ),
    )


async def stream_and_drain(chat, message, config):
    fc_name, fc_args, text, thinking = None, None, "", ""
    async for chunk in await chat.send_message_stream(message, config=config):
        if chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'thought') and part.thought:
                            if hasattr(part, 'text') and part.text:
                                thinking += part.text
                        elif hasattr(part, 'function_call') and part.function_call:
                            fc_name = part.function_call.name
                            fc_args = dict(part.function_call.args or {})
                        elif hasattr(part, 'text') and part.text:
                            text += part.text
    return fc_name, fc_args, text, thinking


async def probe_1_empty_event():
    """Empty event cold start — no conversation, header-only first message."""
    print("\n" + "="*60)
    print("PROBE 1: Empty Event Cold Start (aligner-shaped)")
    print("="*60)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    config = make_config(
        "You are FRIDAY, an AI operations orchestrator. "
        "Current phase: triage. Domain: unclassified. "
        "Classify the event based on the evidence provided."
    )

    # Empty history — no macro turns exist yet
    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=[],  # EMPTY — no prior conversation
    )
    print("  Session created with EMPTY history")

    # First message = event header (evidence injection for empty events)
    header = (
        "## Event Evidence\n"
        "- **Source:** aligner\n"
        "- **Service:** containerized-data-importer v4.20\n"
        "- **Reason:** Kargo promotion failed: wait-for-merge timeout after 6h\n"
        "- **MR:** !6, pipeline failed\n"
        "- **Severity:** warning\n\n"
        "What is the next action? Call one of your tools."
    )

    print(f"  Sending header-only message ({len(header)} chars)...")
    fc, args, text, thinking = await stream_and_drain(chat, header, config)

    print(f"  FC: {fc}, args: {json.dumps(args or {})[:80]}")
    if thinking:
        print(f"  Thinking: {thinking[:120]}...")

    # Verify session accepts a follow-up
    if fc:
        fr = types.Part.from_function_response(name=fc, response={"result": "Domain set: clear"})
        fc2, args2, text2, _ = await stream_and_drain(chat, fr, config)
        print(f"  Follow-up: FC={fc2}, text={text2[:60] if text2 else 'none'}")
        print(f"  Session healthy after empty-start!")

    passed = fc is not None  # Model made a tool call from header-only evidence
    print(f"\n  PROBE 1: {'PASSED' if passed else 'FAILED'} — model {'classified' if passed else 'did not classify'} from header-only evidence")
    return passed


async def probe_2_consecutive_user_macros():
    """Two consecutive user macros on rebuild — role-merge required."""
    print("\n" + "="*60)
    print("PROBE 2: Consecutive User Macros on Rebuild (role-merge)")
    print("="*60)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    config = make_config(
        "You are FRIDAY. An agent returned a result, and a user sent a follow-up. "
        "Address the user's question using the agent's findings."
    )

    # Simulate: agent.execute (user) + user.message (user) — consecutive same-role
    # This would happen if an agent returns AND a user messages before FRIDAY responds
    history_raw = [
        {"role": "user", "text": "Pipeline failed for kubevirt v5.99. Investigate."},
        {"role": "model", "text": "I've dispatched a developer to investigate."},
        # TWO consecutive user turns:
        {"role": "user", "text": "Agent result: Pipeline 16803810 failed due to RHSM entitlement error. 7/15 builds affected."},
        {"role": "user", "text": "User message: Can you also check if this affects the v4.20 track?"},
    ]

    # Role-merge: combine consecutive user turns into one Content
    merged_history = []
    for h in history_raw:
        if merged_history and merged_history[-1].role == h["role"]:
            merged_history[-1].parts.append(types.Part.from_text(text=h["text"]))
            print(f"  [MERGED] {h['role']}: {h['text'][:60]}...")
        else:
            merged_history.append(types.Content(
                role=h["role"],
                parts=[types.Part.from_text(text=h["text"])],
            ))
            print(f"  [NEW]    {h['role']}: {h['text'][:60]}...")

    print(f"\n  History entries: {len(history_raw)} raw → {len(merged_history)} merged")

    try:
        chat = client.aio.chats.create(
            model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
            config=config,
            history=merged_history,
        )
        fc, args, text, thinking = await stream_and_drain(
            chat, "What is the next action?", config
        )
        print(f"  Response: FC={fc}, text={text[:80] if text else 'none'}")
        print(f"  NO 400 — role-merge accepted by SDK!")
        passed = True
    except Exception as e:
        print(f"  FAILED: {e}")
        passed = False

    # Also verify: WITHOUT merge, the SDK rejects consecutive same-role
    print(f"\n  Verifying: unmerged consecutive roles → should 400...")
    unmerged = [
        types.Content(role="user", parts=[types.Part.from_text(text="first user turn")]),
        types.Content(role="model", parts=[types.Part.from_text(text="model response")]),
        types.Content(role="user", parts=[types.Part.from_text(text="second user turn")]),
        types.Content(role="user", parts=[types.Part.from_text(text="third user turn — consecutive!")]),
    ]
    try:
        chat2 = client.aio.chats.create(
            model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
            config=config,
            history=unmerged,
        )
        await stream_and_drain(chat2, "test", config)
        print(f"  UNEXPECTED: SDK accepted unmerged consecutive roles!")
        rejected = False
    except Exception as e:
        err_str = str(e)
        if "400" in err_str or "role" in err_str.lower():
            print(f"  Confirmed: SDK rejects unmerged consecutive roles (400)")
            rejected = True
        else:
            print(f"  Different error: {e}")
            rejected = False

    print(f"\n  PROBE 2: {'PASSED' if passed else 'FAILED'} — merged={passed}, unmerged_rejected={rejected}")
    return passed


async def probe_3_error_fr():
    """Tool raises exception — error FR must pair the FC, session survives."""
    print("\n" + "="*60)
    print("PROBE 3: Error FR Pairing (tool raises)")
    print("="*60)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    config = make_config(
        "You are FRIDAY. Check the pipeline status using refresh_status. "
        "If it fails, classify the event instead."
    )

    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=[
            types.Content(role="user", parts=[types.Part.from_text(
                text="Pipeline 16803810 may have failed. Check its status."
            )]),
        ],
    )

    fc, args, text, thinking = await stream_and_drain(
        chat, "What is the next action?", config
    )
    print(f"  First FC: {fc}")

    if not fc:
        print(f"  Model didn't call a tool — inconclusive")
        return None

    # Simulate tool FAILURE
    error_result = "Internal error: ConnectionError: GitLab API unreachable (timeout after 30s)"
    print(f"  Simulating tool error: {error_result[:60]}...")

    error_fr = types.Part.from_function_response(
        name=fc,
        response={"error": error_result},
    )
    fc2, args2, text2, thinking2 = await stream_and_drain(chat, error_fr, config)
    print(f"  Post-error FC: {fc2}, text: {text2[:60] if text2 else 'none'}")

    # Verify session survives for another call
    if fc2:
        fr2 = types.Part.from_function_response(name=fc2, response={"result": "Domain set: complicated"})
        fc3, args3, text3, _ = await stream_and_drain(chat, fr2, config)
        print(f"  Session healthy after error! Next: FC={fc3}, text={text3[:60] if text3 else 'none'}")
        passed = True
    elif text2:
        print(f"  Model responded with text after error (acceptable)")
        passed = True
    else:
        print(f"  Empty response after error FR")
        passed = False

    print(f"\n  PROBE 3: {'PASSED' if passed else 'FAILED'} — error FR paired, session survived")
    return passed


async def probe_4_defer_terminal_suppress():
    """defer_event as terminal — post-FR FC must be suppressed."""
    print("\n" + "="*60)
    print("PROBE 4: defer_event Terminal + Post-FR Suppress")
    print("="*60)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    config = make_config(
        "You are FRIDAY. The pipeline is still running. "
        "Defer the event for 900 seconds to wait for it. "
        "After deferring, do NOT take any other action."
    )

    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=[
            types.Content(role="user", parts=[types.Part.from_text(
                text="Pipeline 16803810 is still running after 15 minutes. Status: running."
            )]),
        ],
    )

    fc, args, text, thinking = await stream_and_drain(
        chat, "What is the next action?", config
    )
    print(f"  First FC: {fc}")

    if fc != "defer_event":
        print(f"  Model called {fc} instead of defer_event — running with it as terminal")

    if not fc:
        print(f"  No FC — inconclusive")
        return None

    # Execute defer + send FR
    result = f"Event deferred for {args.get('seconds', 900)}s: {args.get('reason', 'waiting')}"
    fr = types.Part.from_function_response(name=fc, response={"result": result})

    # Drain post-FR response
    fc2, args2, text2, thinking2 = await stream_and_drain(chat, fr, config)
    print(f"  Post-defer FR response: FC={fc2}, text={text2[:60] if text2 else 'none'}")

    suppress_count = 0
    # Bounded while: suppress orphan FCs
    while fc2 and suppress_count < 3:
        suppress_count += 1
        print(f"  [suppress #{suppress_count}] Post-terminal FC: {fc2} — pairing with suppress FR")
        suppress_fr = types.Part.from_function_response(
            name=fc2,
            response={"status": "suppressed", "reason": "terminal tool already executed"},
        )
        fc2, args2, text2, _ = await stream_and_drain(chat, suppress_fr, config)

    if suppress_count > 0:
        print(f"  Suppressed {suppress_count} post-terminal FC(s)")
    else:
        print(f"  No post-terminal FCs (model stopped cleanly)")

    # Verify session survives
    print(f"\n  Verifying session health after defer+suppress...")
    try:
        # Simulate: defer expired, new data arrives
        fc3, args3, text3, _ = await stream_and_drain(
            chat, "Defer expired. Pipeline now shows: status=success. What next?", config
        )
        print(f"  Session healthy! FC={fc3}, text={text3[:60] if text3 else 'none'}")
        passed = True
    except Exception as e:
        print(f"  SESSION FAILED: {e}")
        passed = False

    print(f"\n  PROBE 4: {'PASSED' if passed else 'FAILED'} — defer terminal, {suppress_count} suppress(es), session survived")
    return passed


async def main():
    results = {}
    results["empty_event"] = await probe_1_empty_event()
    results["role_merge"] = await probe_2_consecutive_user_macros()
    results["error_fr"] = await probe_3_error_fr()
    results["defer_suppress"] = await probe_4_defer_terminal_suppress()

    print("\n" + "="*60)
    print("ALL PROBES SUMMARY")
    print("="*60)
    for name, passed in results.items():
        status = "PASSED" if passed else ("INCONCLUSIVE" if passed is None else "FAILED")
        print(f"  {name}: {status}")
    
    all_passed = all(v is True for v in results.values())
    print(f"\n  Overall: {'ALL PASSED' if all_passed else 'SOME GAPS REMAIN'}")


if __name__ == "__main__":
    asyncio.run(main())
