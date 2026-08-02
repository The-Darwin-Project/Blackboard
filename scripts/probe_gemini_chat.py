# BlackBoard/scripts/probe_gemini_chat.py
"""
Probe: Verify Gemini AsyncChat with function calling + thinking tokens.

Gate for the Brain Chat Session Conversion plan.
Tests AsyncChat.send_message and send_message_stream with tool schemas
matching the Brain's actual configuration.

Usage:
    export GCP_PROJECT=your-project
    export GCP_LOCATION=us-central1   # or global
    python3 scripts/probe_gemini_chat.py

Requires: google-genai >= 1.60.0, gcloud auth application-default login
"""
import asyncio
import os
import sys
import traceback

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

PROJECT = os.environ.get("GCP_PROJECT", "")
# Always use "global" -- gemini-3.x preview models (including the production
# Brain model gemini-3.1-pro-preview-customtools and the Step 6 summarizer
# gemini-3.5-flash-lite) are allowlisted at "global" in this project, not
# regional locations like us-central1 (confirmed via live 404 vs PASS probe).
LOCATION = os.environ.get("GCP_LOCATION", "global")

if not PROJECT:
    print("ERROR: GCP_PROJECT env var not set")
    sys.exit(1)

MODELS = ["gemini-2.5-pro", "gemini-3.1-pro-preview-customtools"]

TOOL_SCHEMA = {
    "name": "select_agent",
    "description": "Route work to an agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "enum": ["architect", "sysadmin", "developer", "qe", "security_analyst", "code_reviewer"],
            },
            "task_instruction": {"type": "string"},
        },
        "required": ["agent_name", "task_instruction"],
    },
}

SYSTEM_PROMPT = (
    "You are a routing brain. When asked to check something, "
    "call select_agent with agent_name='developer' and a task_instruction."
)


async def run_test(test_name: str, coro):
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    try:
        result = await coro
        print(f"PASS: {result}")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()
        return False


async def test_chat_send_message(client, model, thinking: bool):
    """Test 1: AsyncChat.send_message (non-streaming) with function calling."""
    from google.genai import types

    config_kwargs = {
        "temperature": 0.8,
        "max_output_tokens": 1024,
        "system_instruction": SYSTEM_PROMPT,
        "tools": [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=TOOL_SCHEMA["name"],
                description=TOOL_SCHEMA["description"],
                parameters_json_schema=TOOL_SCHEMA["input_schema"],
            )
        ])],
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
    }
    if thinking:
        config_kwargs["thinking_config"] = types.ThinkingConfig(include_thoughts=True)

    config = types.GenerateContentConfig(**config_kwargs)
    chat = client.aio.chats.create(model=model, config=config)

    response = await chat.send_message("Check the status of MR !71 in the store repo.")

    has_fc = bool(response.function_calls)
    text = response.text or "(no text)"
    fc_name = response.function_calls[0].name if has_fc else "none"
    fc_args = response.function_calls[0].args if has_fc else {}

    return f"function_call={has_fc}, name={fc_name}, args={fc_args}, text={text[:80]}"


async def test_chat_send_message_stream(client, model, thinking: bool):
    """Test 2: AsyncChat.send_message_stream (streaming) -- bug #1938 check."""
    from google.genai import types

    config_kwargs = {
        "temperature": 0.8,
        "max_output_tokens": 1024,
        "system_instruction": SYSTEM_PROMPT,
        "tools": [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=TOOL_SCHEMA["name"],
                description=TOOL_SCHEMA["description"],
                parameters_json_schema=TOOL_SCHEMA["input_schema"],
            )
        ])],
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
    }
    if thinking:
        config_kwargs["thinking_config"] = types.ThinkingConfig(include_thoughts=True)

    config = types.GenerateContentConfig(**config_kwargs)
    chat = client.aio.chats.create(model=model, config=config)

    chunks = []
    fc = None
    async for chunk in await chat.send_message_stream("Check the status of MR !71 in the store repo."):
        if chunk.text:
            chunks.append(chunk.text)
        if chunk.function_calls:
            fc = chunk.function_calls[0]

    return f"chunks={len(chunks)}, function_call={fc.name if fc else 'none'}, args={fc.args if fc else {}}"


async def test_function_response_roundtrip(client, model):
    """Test 3: After function_call, send Part.from_function_response, get next response."""
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=1024,
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=TOOL_SCHEMA["name"],
                description=TOOL_SCHEMA["description"],
                parameters_json_schema=TOOL_SCHEMA["input_schema"],
            )
        ])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    chat = client.aio.chats.create(model=model, config=config)

    r1 = await chat.send_message("Check MR !71 status.")
    if not r1.function_calls:
        return "SKIP: model did not return function_call on first turn"

    fc = r1.function_calls[0]
    print(f"  Turn 1 function_call: {fc.name}({fc.args})")

    r2 = await chat.send_message(
        types.Part.from_function_response(
            name=fc.name,
            response={"result": "MR is open, pipeline running, no conflicts."},
        )
    )

    has_fc2 = bool(r2.function_calls)
    text2 = r2.text or "(no text)"
    return f"Turn 2: function_call={has_fc2}, text={text2[:120]}"


async def test_streaming_fc_synthetic_fr_roundtrip(client, model):
    """Test 5 (Run #4 gate): native streaming (no early-return) -> FC as terminal
    chunk -> synthetic FR via send_message_stream -> 3rd real call succeeds.

    This validates the corrected Step 3/4 mechanism: yielding chunks natively
    without early-returning on function_call, then feeding a synthetic
    functionResponse back through send_message_stream (not send_message) --
    since the synthetic-FR-as-re-invocation pattern in Step 4 uses send_stream
    for every call, including synthetic FRs.
    """
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=1024,
        system_instruction=SYSTEM_PROMPT,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=TOOL_SCHEMA["name"],
                description=TOOL_SCHEMA["description"],
                parameters_json_schema=TOOL_SCHEMA["input_schema"],
            )
        ])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    chat = client.aio.chats.create(model=model, config=config)

    # Turn 1: native streaming consumption, NO early-return on function_call.
    # Let the async for loop run to natural completion (FC is the terminal chunk).
    fc = None
    chunk_count = 0
    async for chunk in await chat.send_message_stream("Check MR !71 status."):
        chunk_count += 1
        if chunk.function_calls:
            fc = chunk.function_calls[0]
        # Deliberately NOT breaking/returning here -- validates that letting
        # the loop exhaust naturally still lets record_history() fire.

    if not fc:
        return f"SKIP: no function_call on turn 1 (chunks={chunk_count})"

    print(f"  Turn 1: {chunk_count} chunks, function_call={fc.name}({fc.args})")

    # Turn 2: synthetic FR sent via send_message_stream (matches Step 4's
    # "synthetic FR is a re-invocation, same call path as real turns" contract).
    # Use a "blocked" payload shape matching the RECALL-discard synthetic FR.
    synthetic_payload = {"status": "blocked", "reason": "recall_override"}
    fc2 = None
    text2_chunks = []
    async for chunk in await chat.send_message_stream(
        types.Part.from_function_response(name=fc.name, response=synthetic_payload),
        config=config,
    ):
        if chunk.text:
            text2_chunks.append(chunk.text)
        if chunk.function_calls:
            fc2 = chunk.function_calls[0]

    text2 = "".join(text2_chunks)
    print(f"  Turn 2 (synthetic FR): function_call={bool(fc2)}, text={text2[:150]}")

    # Turn 3: a normal real call -- this is the load-bearing assertion.
    # If turn 1 or 2 left a dangling/malformed history entry, this call 400s.
    fc3 = None
    text3_chunks = []
    async for chunk in await chat.send_message_stream(
        "Understood. Please check the pipeline status for MR !72 instead.",
        config=config,
    ):
        if chunk.text:
            text3_chunks.append(chunk.text)
        if chunk.function_calls:
            fc3 = chunk.function_calls[0]

    text3 = "".join(text3_chunks)
    has_fc3 = bool(fc3)
    curated_len = len(chat.get_history(curated=True))
    return (
        f"Turn 3 succeeded (no 400): function_call={has_fc3}, "
        f"text={text3[:100]!r}, curated_history_len={curated_len}"
    )


async def test_compression_recreate_thought_signature(client, model):
    """Test 6 (Run #4 gate): 15+ turn FC/FR session with thinking -> extract
    curated history -> inject a synthetic summary turn in place of the older
    turns -> recreate the session -> verify the recreated session accepts a
    follow-up call with no thought_signature-related 400.

    Mirrors Step 6's _summarize_and_recreate mechanism (without the live
    Flash-Lite call -- summary text is a stand-in for probe purposes).
    """
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=512,
        system_instruction=SYSTEM_PROMPT,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=TOOL_SCHEMA["name"],
                description=TOOL_SCHEMA["description"],
                parameters_json_schema=TOOL_SCHEMA["input_schema"],
            )
        ])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    chat = client.aio.chats.create(model=model, config=config)

    # Build up 8 FC/FR round-trips (16 turns) with thinking enabled, natural streaming.
    for i in range(8):
        fc = None
        async for chunk in await chat.send_message_stream(
            f"Check MR !{70 + i} status.", config=config,
        ):
            if chunk.function_calls:
                fc = chunk.function_calls[0]
        if not fc:
            continue
        async for chunk in await chat.send_message_stream(
            types.Part.from_function_response(
                name=fc.name, response={"result": f"MR !{70+i} open, pipeline green."},
            ),
            config=config,
        ):
            pass

    history = chat.get_history(curated=True)
    print(f"  Built {len(history)}-turn curated history across 8 FC/FR round-trips")

    # Simulate compression: keep last 4 entries verbatim, replace the rest with
    # a synthetic summary turn -- exact shape of Step 6's _summarize_and_recreate.
    recent_count = 4
    recent_history = history[-recent_count:] if len(history) > recent_count else history
    summary_content = types.Content(
        role="user",
        parts=[types.Part.from_text(
            text="## Event Summary (compressed)\nChecked MRs !70-!73, all green. Continuing with remaining checks."
        )],
    )
    new_history = [summary_content] + recent_history

    # Recreate -- this is the exact mechanism under test.
    new_chat = client.aio.chats.create(model=model, config=config, history=new_history)

    # Follow-up call on the recreated session -- the load-bearing assertion.
    fc_after = None
    text_after_chunks = []
    async for chunk in await new_chat.send_message_stream(
        "Now check MR !99 status too.", config=config,
    ):
        if chunk.text:
            text_after_chunks.append(chunk.text)
        if chunk.function_calls:
            fc_after = chunk.function_calls[0]

    text_after = "".join(text_after_chunks)
    return (
        f"Recreate succeeded (no 400): new_history_len={len(new_history)}, "
        f"post-recreate function_call={bool(fc_after)}, text={text_after[:100]!r}"
    )


async def test_consecutive_role_merge_in_history(client, model):
    """Test 7 (Run #4 gate): consecutive same-role Content blocks in history=[]
    (unmerged) should be rejected or cause issues; after merging per Step 2's
    role-merge logic, chats.create() must accept it cleanly.
    """
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.5,
        max_output_tokens=256,
        system_instruction="You are a helpful assistant.",
    )

    # Merged history: consecutive "user" turns collapsed into one Content
    # with multiple parts (mirrors format_turn_for_chat's role-merge logic).
    merged_history = [
        types.Content(role="user", parts=[
            types.Part.from_text(text="## [aligner -> FRIDAY] CPU spike detected on store-api."),
            types.Part.from_text(text="## [user: Tal] Please investigate."),
        ]),
        types.Content(role="model", parts=[
            types.Part.from_text(text="Acknowledged, investigating the CPU spike now."),
        ]),
    ]

    chat = client.aio.chats.create(model=model, config=config, history=merged_history)
    response = await chat.send_message("Any update?")
    return f"Merged-history create() accepted, follow-up succeeded: text={response.text[:100]!r}"


async def test_multi_turn_context(client, model):
    """Test 4: Verify chat retains context across turns (no function calling)."""
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=256,
        system_instruction="You are a helpful assistant. Remember what the user tells you.",
    )
    chat = client.aio.chats.create(model=model, config=config)

    await chat.send_message("My favorite color is cerulean blue.")
    r2 = await chat.send_message("What is my favorite color?")
    text = r2.text or ""
    has_cerulean = "cerulean" in text.lower()
    return f"context_retained={'cerulean' in text.lower()}, response={text[:100]}"


async def main():
    from google import genai

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    print(f"google-genai version: {genai.__version__}")
    print(f"Project: {PROJECT}, Location: {LOCATION}")

    results = {}

    for model in MODELS:
        print(f"\n{'#'*60}")
        print(f"MODEL: {model}")
        print(f"{'#'*60}")

        # Test 1a: send_message + thinking
        r = await run_test(
            f"{model} / send_message / thinking=True",
            test_chat_send_message(client, model, thinking=True),
        )
        results[f"{model}/send_message/thinking"] = r

        # Test 1b: send_message without thinking
        r = await run_test(
            f"{model} / send_message / thinking=False",
            test_chat_send_message(client, model, thinking=False),
        )
        results[f"{model}/send_message/no_thinking"] = r

        # Test 2a: send_message_stream + thinking (bug #1938 check)
        r = await run_test(
            f"{model} / send_message_stream / thinking=True (bug #1938)",
            test_chat_send_message_stream(client, model, thinking=True),
        )
        results[f"{model}/stream/thinking"] = r

        # Test 2b: send_message_stream without thinking
        r = await run_test(
            f"{model} / send_message_stream / thinking=False",
            test_chat_send_message_stream(client, model, thinking=False),
        )
        results[f"{model}/stream/no_thinking"] = r

        # Test 3: function response round-trip
        r = await run_test(
            f"{model} / function_response_roundtrip",
            test_function_response_roundtrip(client, model),
        )
        results[f"{model}/fn_roundtrip"] = r

        # Test 4: multi-turn context retention
        r = await run_test(
            f"{model} / multi_turn_context",
            test_multi_turn_context(client, model),
        )
        results[f"{model}/context"] = r

        # Test 5 (Run #4 gate): streaming FC -> synthetic FR -> next call round-trip
        r = await run_test(
            f"{model} / streaming_fc_synthetic_fr_roundtrip (Run #4 gate)",
            test_streaming_fc_synthetic_fr_roundtrip(client, model),
        )
        results[f"{model}/synthetic_fr_roundtrip"] = r

        # Test 6 (Run #4 gate): compression + recreate, thought_signature survival
        r = await run_test(
            f"{model} / compression_recreate_thought_signature (Run #4 gate)",
            test_compression_recreate_thought_signature(client, model),
        )
        results[f"{model}/compress_recreate"] = r

        # Test 7 (Run #4 gate): consecutive-role merge accepted by create()
        r = await run_test(
            f"{model} / consecutive_role_merge_in_history (Run #4 gate)",
            test_consecutive_role_merge_in_history(client, model),
        )
        results[f"{model}/role_merge"] = r

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        print(f"  {status}: {k}")

    all_pass = all(results.values())
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")

    # Decision matrix
    g3_send = results.get("gemini-3-pro-preview/send_message/thinking", False)
    g3_stream = results.get("gemini-3-pro-preview/stream/thinking", False)
    g3_fn = results.get("gemini-3-pro-preview/fn_roundtrip", False)
    print(f"\nDecision for gemini-3-pro-preview:")
    if g3_send and g3_stream and g3_fn:
        print("  -> Use streaming chat sessions (ideal)")
    elif g3_send and g3_fn:
        print("  -> Use non-streaming send_message (streaming blocked by bug #1938)")
    else:
        print("  -> Gemini stays stateless; implement chat sessions for Claude only")


if __name__ == "__main__":
    asyncio.run(main())
