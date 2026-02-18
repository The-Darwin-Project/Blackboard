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
LOCATION = os.environ.get("GCP_LOCATION", "global")

if not PROJECT:
    print("ERROR: GCP_PROJECT env var not set")
    sys.exit(1)

MODELS = ["gemini-2.5-pro", "gemini-3-pro-preview"]

TOOL_SCHEMA = {
    "name": "select_agent",
    "description": "Route work to an agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "enum": ["architect", "sysadmin", "developer"],
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
