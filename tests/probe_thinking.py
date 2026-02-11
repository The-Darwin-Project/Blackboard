# BlackBoard/tests/probe_thinking.py
# Probe: Test if Gemini ThinkingConfig returns visible thoughts via streaming API

import asyncio
import os
import time


async def main():
    print("=" * 60)
    print("Gemini ThinkingConfig Streaming Probe")
    print("=" * 60)

    from google import genai
    from google.genai import types

    project = os.getenv("GCP_PROJECT", "cnv-ai-insights")
    location = os.getenv("GCP_LOCATION", "global")
    model = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")

    client = genai.Client(vertexai=True, project=project, location=location)

    # Tool for function calling test
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

    prompt = "darwin-store has 95% CPU. What should you do? Route to the appropriate agent."
    system = "You are a brain orchestrator. Think through your reasoning step by step before calling a function."

    # =========================================================================
    # Test 1: Streaming WITHOUT ThinkingConfig (baseline)
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 1: Streaming WITHOUT ThinkingConfig")
    print("-" * 60)
    t0 = time.time()
    chunks_text = 0
    chunks_fc = 0
    chunks_empty = 0
    accumulated = ""
    try:
        async for chunk in client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.8,
            ),
        ):
            if chunk.text:
                chunks_text += 1
                accumulated += chunk.text
                print(f"  TEXT chunk {chunks_text}: {chunk.text[:80]!r}")
            if chunk.function_calls:
                chunks_fc += 1
                fc = chunk.function_calls[0]
                print(f"  FC chunk: {fc.name}({list(fc.args.keys()) if fc.args else []})")
            if not chunk.text and not chunk.function_calls:
                chunks_empty += 1

        elapsed = time.time() - t0
        print(f"\n  Text chunks: {chunks_text}, FC chunks: {chunks_fc}, Empty: {chunks_empty}")
        print(f"  Accumulated text: {len(accumulated)} chars")
        print(f"  Latency: {elapsed:.1f}s")
    except Exception as e:
        print(f"  ERROR: {e}")

    # =========================================================================
    # Test 2: Streaming WITH ThinkingConfig(includeThoughts=True)
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 2: Streaming WITH includeThoughts=True")
    print("-" * 60)
    t0 = time.time()
    chunks_text = 0
    chunks_fc = 0
    chunks_empty = 0
    chunks_thought = 0
    accumulated = ""
    try:
        async for chunk in client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.8,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                ),
            ),
        ):
            # Check all parts in candidates for thought flag
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought:
                                chunks_thought += 1
                                text = part.text if hasattr(part, 'text') else ''
                                print(f"  THOUGHT chunk {chunks_thought}: {text[:80]!r}")

            if chunk.text:
                chunks_text += 1
                accumulated += chunk.text
                print(f"  TEXT chunk {chunks_text}: {chunk.text[:80]!r}")
            if chunk.function_calls:
                chunks_fc += 1
                fc = chunk.function_calls[0]
                print(f"  FC chunk: {fc.name}({list(fc.args.keys()) if fc.args else []})")
            if not chunk.text and not chunk.function_calls:
                chunks_empty += 1

        elapsed = time.time() - t0
        print(f"\n  Text chunks: {chunks_text}, FC chunks: {chunks_fc}, Empty: {chunks_empty}, Thought: {chunks_thought}")
        print(f"  Accumulated text: {len(accumulated)} chars")
        print(f"  Latency: {elapsed:.1f}s")
    except Exception as e:
        print(f"  ERROR: {e}")

    # =========================================================================
    # Test 3: Streaming WITH ThinkingConfig(thinkingLevel=HIGH)
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 3: Streaming WITH thinkingLevel=HIGH")
    print("-" * 60)
    t0 = time.time()
    chunks_text = 0
    chunks_fc = 0
    chunks_empty = 0
    chunks_thought = 0
    accumulated = ""
    try:
        async for chunk in client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.8,
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH",
                    include_thoughts=True,
                ),
            ),
        ):
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought:
                                chunks_thought += 1
                                text = part.text if hasattr(part, 'text') else ''
                                print(f"  THOUGHT chunk {chunks_thought}: {text[:80]!r}")

            if chunk.text:
                chunks_text += 1
                accumulated += chunk.text
                print(f"  TEXT chunk {chunks_text}: {chunk.text[:80]!r}")
            if chunk.function_calls:
                chunks_fc += 1
                fc = chunk.function_calls[0]
                print(f"  FC chunk: {fc.name}({list(fc.args.keys()) if fc.args else []})")
            if not chunk.text and not chunk.function_calls:
                chunks_empty += 1

        elapsed = time.time() - t0
        print(f"\n  Text chunks: {chunks_text}, FC chunks: {chunks_fc}, Empty: {chunks_empty}, Thought: {chunks_thought}")
        print(f"  Accumulated text: {len(accumulated)} chars")
        print(f"  Latency: {elapsed:.1f}s")
    except Exception as e:
        print(f"  ERROR: {e}")

    # =========================================================================
    # Test 4: Text-only (no tools) WITH ThinkingConfig -- does it stream?
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 4: Text-only (no tools) WITH includeThoughts=True")
    print("-" * 60)
    t0 = time.time()
    chunks_text = 0
    chunks_thought = 0
    accumulated = ""
    try:
        async for chunk in client.aio.models.generate_content_stream(
            model=model,
            contents="Explain why high CPU on a kubernetes pod might happen. Be brief.",
            config=types.GenerateContentConfig(
                temperature=0.8,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                ),
            ),
        ):
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought:
                                chunks_thought += 1
                                text = part.text if hasattr(part, 'text') else ''
                                print(f"  THOUGHT: {text[:100]!r}")

            if chunk.text:
                chunks_text += 1
                accumulated += chunk.text
                if chunks_text <= 3:
                    print(f"  TEXT chunk {chunks_text}: {chunk.text[:80]!r}")
                elif chunks_text == 4:
                    print(f"  ... (more chunks)")

        elapsed = time.time() - t0
        print(f"\n  Text chunks: {chunks_text}, Thought chunks: {chunks_thought}")
        print(f"  Accumulated: {len(accumulated)} chars")
        print(f"  Latency: {elapsed:.1f}s")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("PROBE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
