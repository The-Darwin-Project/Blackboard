"""
Probe: Verify Gemini Live API session resumption + dual-session handoff.

Hypothesis:
  1. google.genai.types.SessionResumptionConfig exists and is accepted by LiveConnectConfig
  2. Two Live API sessions can coexist (old for report, new for observation)
  3. Resume handle from Session A can be used to resume context in Session B

Run: python -m probe_session_resumption
Requires: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION env vars (or ADC)
"""
import asyncio
import os
import time


async def probe():
    print("=" * 60)
    print("PROBE: Session Resumption + Dual-Session Handoff")
    print("=" * 60)

    # --- Step 1: Verify SDK types exist ---
    print("\n[1/4] Checking SDK types...")
    try:
        from google import genai
        from google.genai import types

        assert hasattr(types, "SessionResumptionConfig"), "SessionResumptionConfig not found"
        print("  OK: types.SessionResumptionConfig exists")

        cfg = types.SessionResumptionConfig()
        print(f"  OK: Instantiated empty config: {cfg}")

        cfg_with_handle = types.SessionResumptionConfig(handle="test-handle")
        print(f"  OK: Instantiated with handle: {cfg_with_handle}")
    except (ImportError, AssertionError, TypeError) as e:
        print(f"  FAIL: {e}")
        return

    # --- Step 2: Connect Session A with resumption enabled ---
    print("\n[2/4] Connecting Session A (with resumption)...")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT"))
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    model = os.getenv("LLM_MODEL_SYSTEM2", "gemini-live-2.5-flash")

    client = genai.Client(vertexai=True, project=project, location=location)

    config_a = types.LiveConnectConfig(
        response_modalities=[types.Modality.TEXT],
        generation_config=types.GenerationConfig(max_output_tokens=256, temperature=0.3),
        system_instruction=types.Content(
            parts=[types.Part(text="You are a test observer. Respond briefly.")]
        ),
        session_resumption=types.SessionResumptionConfig(),
    )

    session_handle = None
    ctx_a = client.aio.live.connect(model=model, config=config_a)
    session_a = await ctx_a.__aenter__()
    print("  OK: Session A connected")

    # Send a message so the session has context
    await session_a.send(input="Remember this: the magic word is 'banana'.", end_of_turn=True)
    print("  Sent context message to Session A")

    # Collect response + look for resumption handle
    async with asyncio.timeout(15):
        async for msg in session_a.receive():
            if hasattr(msg, "session_resumption_update") and msg.session_resumption_update:
                update = msg.session_resumption_update
                if hasattr(update, "new_handle") and update.new_handle:
                    session_handle = update.new_handle
                    print(f"  OK: Got resume handle ({len(session_handle)} chars)")
            if hasattr(msg, "server_content") and getattr(msg.server_content, "turn_complete", False):
                break

    if not session_handle:
        print("  WARN: No resume handle received (may need more turns)")

    # --- Step 3: Connect Session B (with handle from A) ---
    print("\n[3/4] Connecting Session B (resuming from A)...")
    config_b = types.LiveConnectConfig(
        response_modalities=[types.Modality.TEXT],
        generation_config=types.GenerationConfig(max_output_tokens=256, temperature=0.3),
        system_instruction=types.Content(
            parts=[types.Part(text="You are a test observer. Respond briefly.")]
        ),
        session_resumption=types.SessionResumptionConfig(
            handle=session_handle,
        ) if session_handle else types.SessionResumptionConfig(),
    )

    ctx_b = client.aio.live.connect(model=model, config=config_b)
    session_b = await ctx_b.__aenter__()
    print("  OK: Session B connected")

    # Test that B has context from A
    await session_b.send(input="What is the magic word?", end_of_turn=True)
    response_b = []
    async with asyncio.timeout(15):
        async for msg in session_b.receive():
            if hasattr(msg, "text") and msg.text:
                response_b.append(msg.text)
            if hasattr(msg, "server_content") and getattr(msg.server_content, "turn_complete", False):
                break

    response_text = "".join(response_b).strip()
    has_banana = "banana" in response_text.lower()
    print(f"  Session B response: {response_text[:200]}")
    print(f"  Context carried over: {'YES' if has_banana else 'NO'}")

    # --- Step 4: Dual session — send report prompt to A while B is alive ---
    print("\n[4/4] Dual session: report on A while B is alive...")
    try:
        await session_a.send(
            input="Summarize what happened in this session in one sentence.",
            end_of_turn=True,
        )
        report_parts = []
        async with asyncio.timeout(15):
            async for msg in session_a.receive():
                if hasattr(msg, "text") and msg.text:
                    report_parts.append(msg.text)
                if hasattr(msg, "server_content") and getattr(msg.server_content, "turn_complete", False):
                    break
        report = "".join(report_parts).strip()
        print(f"  OK: Report from A: {report[:200]}")
        print("  OK: Both sessions coexisted without conflict")
    except Exception as e:
        print(f"  FAIL: Dual session error: {e}")

    # Cleanup
    await ctx_a.__aexit__(None, None, None)
    await ctx_b.__aexit__(None, None, None)
    print("\n" + "=" * 60)
    print("PROBE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(probe())
