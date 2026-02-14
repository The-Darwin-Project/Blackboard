# BlackBoard/tests/probe_thinking.py
# Probe: Test if Gemini ThinkingConfig returns visible thoughts via streaming API

import asyncio
import os
import time


async def run_stream_test(client, model, prompt, config, label):
    """Run a streaming test and report chunk types."""
    print(f"\n{'-' * 60}")
    print(f"TEST: {label}")
    print(f"{'-' * 60}")

    t0 = time.time()
    chunks_text = 0
    chunks_fc = 0
    chunks_empty = 0
    chunks_thought = 0
    accumulated = ""

    try:
        from google.genai import types
        stream = await client.aio.models.generate_content_stream(
            model=model, contents=prompt, config=config,
        )
        async for chunk in stream:
            # Check for thought parts in candidates
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought:
                                chunks_thought += 1
                                text = part.text if hasattr(part, 'text') and part.text else ''
                                print(f"  THOUGHT {chunks_thought}: {text[:100]!r}")

            if chunk.text:
                chunks_text += 1
                accumulated += chunk.text
                if chunks_text <= 5:
                    print(f"  TEXT {chunks_text}: {chunk.text[:80]!r}")
                elif chunks_text == 6:
                    print(f"  ... (more text chunks)")

            if chunk.function_calls:
                chunks_fc += 1
                fc = chunk.function_calls[0]
                print(f"  FC: {fc.name}({list(fc.args.keys()) if fc.args else []})")

            if not chunk.text and not chunk.function_calls:
                chunks_empty += 1

        elapsed = time.time() - t0
        print(f"\n  Summary: text={chunks_text} fc={chunks_fc} empty={chunks_empty} thought={chunks_thought}")
        print(f"  Accumulated: {len(accumulated)} chars | Latency: {elapsed:.1f}s")

    except Exception as e:
        print(f"  ERROR: {e}")


async def main():
    print("=" * 60)
    print("Gemini ThinkingConfig Streaming Probe")
    print("=" * 60)

    from google import genai
    from google.genai import types

    project = os.getenv("GCP_PROJECT", "")
    location = os.getenv("GCP_LOCATION", "global")
    model = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")

    print(f"Project: {project} | Location: {location} | Model: {model}")

    client = genai.Client(vertexai=True, project=project, location=location)

    tools = [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="select_agent",
            description="Route work to an agent.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "enum": ["architect", "sysadmin", "developer"]},
                    "task_instruction": {"type": "string"},
                },
                "required": ["agent_name", "task_instruction"],
            },
        ),
    ])]

    fc_prompt = "darwin-store has 95% CPU. Route to the appropriate agent to investigate."
    system = "You are a brain orchestrator. Think step by step before calling a function."

    # Test 1: Baseline (no thinking config, with tools)
    await run_stream_test(client, model, fc_prompt, types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.8,
    ), "Baseline -- no ThinkingConfig, with tools")

    # Test 2: includeThoughts=True, with tools
    await run_stream_test(client, model, fc_prompt, types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.8,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    ), "includeThoughts=True, with tools")

    # Test 3: thinkingLevel=HIGH + includeThoughts, with tools
    await run_stream_test(client, model, fc_prompt, types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.8,
        thinking_config=types.ThinkingConfig(thinking_level="HIGH", include_thoughts=True),
    ), "thinkingLevel=HIGH + includeThoughts, with tools")

    # Test 4: Text-only (no tools) + includeThoughts
    await run_stream_test(client, model,
        "Explain briefly why high CPU on a kubernetes pod might happen.",
        types.GenerateContentConfig(
            temperature=0.8,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        ), "Text-only (no tools) + includeThoughts=True")

    print(f"\n{'=' * 60}")
    print("PROBE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
