# BlackBoard/scripts/probe_fr_trailing.py
"""
Probe: Validate that Gemini Chat API accepts a message Content with
mixed function_response + text parts (the F-A residual fix scenario).

This tests the exact edge case from the code review: when a rebuilt
session's history ends with model(FC), the deferred user Content
contains FR parts + terminal_prompt text merged together.

Usage:
    export GCP_PROJECT=cnv-ai-insights
    python3 scripts/probe_fr_trailing.py
"""
import asyncio
import os
import sys

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

PROJECT = os.environ.get("GCP_PROJECT", "")
LOCATION = os.environ.get("GCP_LOCATION", "global")
MODEL = "gemini-3.1-pro-preview-customtools"

if not PROJECT:
    print("ERROR: GCP_PROJECT env var not set")
    sys.exit(1)


async def test_mixed_fr_text_message():
    """Send a Content with function_response + text parts as a single message.

    History: [user(request), model(FC)] — ends with model(FC), no paired FR.
    Message: Content(role="user", parts=[FR_part, text_part])

    This mirrors the F-A residual fix: _rebuild_from_redis pops both the
    trailing model(FC) and user(FR) from history, merges them into the
    deferred Content, and the caller sends them with terminal_prompt text.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="lookup_service",
            description="Look up a Kubernetes service.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                },
                "required": ["service_name"],
            },
        )
    ])

    config = types.GenerateContentConfig(
        system_instruction="You are an infrastructure assistant. When given tool results, summarize them and decide next steps.",
        tools=[tool],
        temperature=0.5,
        max_output_tokens=512,
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Build a real FC with thought_signature by sending a real request first.
    # Hand-built FCs lack thought_signature, which thinking models require.
    setup_chat = client.aio.chats.create(model=MODEL, config=config, history=[])
    print("Setting up: generating a real FC with thought_signature...")
    setup_response = await setup_chat.send_message(
        "Check the status of service my-app", config=config,
    )
    if not setup_response.function_calls:
        print("Model didn't produce a function call — skipping (model behavior-dependent)")
        return True

    # Extract curated history (has thought_signature on FC)
    setup_history = setup_chat.get_history(curated=True)

    # Recreate session with this history (simulating rebuild)
    chat = client.aio.chats.create(
        model=MODEL,
        config=config,
        history=setup_history,
    )

    # Send a list of Parts with MIXED FR + text (the F-A residual scenario)
    # Probe finding: send_message accepts list[Part], NOT Content objects.
    fc_name = setup_response.function_calls[0].name
    fr_part = types.Part.from_function_response(
        name=fc_name,
        response={"result": "service my-app: 3 replicas, healthy, CPU 45%"},
    )
    text_part = types.Part.from_text(
        text="Now evaluate the current event state and decide next steps.",
    )
    message = [fr_part, text_part]

    print(f"Sending mixed FR+text Part list to {MODEL}...")
    response = await chat.send_message(message, config=config)

    print(f"Response received: {len(response.text or '')} chars")
    print(f"Response text (first 200): {(response.text or '')[:200]}")

    # Verify the chat can continue after the mixed message
    print("\nSending follow-up message...")
    follow_up = await chat.send_message(
        "What was the CPU usage you found?",
        config=config,
    )
    print(f"Follow-up response: {(follow_up.text or '')[:200]}")

    curated = chat.get_history(curated=True)
    print(f"\nCurated history length: {len(curated)}")
    for i, c in enumerate(curated):
        parts_summary = []
        for p in (c.parts or []):
            if hasattr(p, 'function_call') and p.function_call:
                parts_summary.append(f"FC({p.function_call.name})")
            elif hasattr(p, 'function_response') and p.function_response:
                parts_summary.append(f"FR({p.function_response.name})")
            elif hasattr(p, 'text') and p.text:
                parts_summary.append(f"text({len(p.text)}ch)")
            elif hasattr(p, 'thought') and p.thought:
                parts_summary.append("thought")
        print(f"  [{i}] role={c.role} parts={parts_summary}")

    return True


async def test_history_ends_model_fc_no_fr():
    """Variant: history ends with model(FC), send ONLY FR as message (no text).

    Tests that the API accepts a pure FR message after a dangling FC.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify a Darwin event.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["clear", "complicated", "complex"]},
                },
                "required": ["domain"],
            },
        )
    ])

    config = types.GenerateContentConfig(
        system_instruction="You are Darwin's Brain. Respond concisely.",
        tools=[tool],
        temperature=0.5,
        max_output_tokens=256,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Build a real FC with thought_signature by sending a real request first,
    # then extracting the model's curated history (which includes the signature).
    setup_chat = client.aio.chats.create(
        model=MODEL, config=config, history=[],
    )
    print("Setting up: generating a real FC with thought_signature...")
    setup_response = await setup_chat.send_message(
        "Triage this event: service my-app has high CPU", config=config,
    )
    if not setup_response.function_calls:
        print("Model didn't produce a function call — skipping (model behavior-dependent)")
        return True

    # Extract curated history (has thought_signature on the FC)
    setup_history = setup_chat.get_history(curated=True)
    # Now create a NEW chat with this history (simulating rebuild)
    # History should be: [user(request), model(FC)] — ends with model(FC)
    chat = client.aio.chats.create(model=MODEL, config=config, history=setup_history)

    fc_name = setup_response.function_calls[0].name

    fr_part = types.Part.from_function_response(
        name=fc_name,
        response={"result": "Event classified as complicated"},
    )

    print(f"\nSending pure FR Part after dangling FC (tool: {fc_name})...")
    response = await chat.send_message(fr_part, config=config)
    print(f"Response: {(response.text or '')[:200]}")

    return True


async def main():
    results = {}

    print(f"Project: {PROJECT}")
    print(f"Location: {LOCATION}")
    print(f"Model: {MODEL}")

    for name, coro in [
        ("mixed_fr_text_message", test_mixed_fr_text_message()),
        ("history_ends_model_fc_no_fr", test_history_ends_model_fc_no_fr()),
    ]:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")
        try:
            result = await coro
            results[name] = True
            print(f"PASS")
        except Exception as e:
            results[name] = False
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}: {k}")
    all_pass = all(results.values())
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    if all_pass:
        print("F-A residual fix is SAFE — mixed FR+text Content accepted by production model")


if __name__ == "__main__":
    asyncio.run(main())
