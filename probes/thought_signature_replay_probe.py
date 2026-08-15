# probes/thought_signature_replay_probe.py
# @ai-rules:
# 1. [Purpose]: Validate that correct FC/FR format with thought_signature produces valid continuations.
# 2. [Constraint]: Uses google-genai SDK. Requires ADC or GOOGLE_APPLICATION_CREDENTIALS.
# 3. [Pattern]: Makes real API calls to compare CORRECT vs BROKEN replay formats.
# 4. [Gotcha]: 3.7 Flash requires thought_signature on functionCall — returns 400 without it.

"""
Local probe: Validates the thought_signature fix approach against live Gemini API.

Tests three replay formats:
1. CORRECT: model:[functionCall+thoughtSignature] → user:[functionResponse]
2. BROKEN:  user:[text+thought_signature] (current brain.py behavior)
3. CHAIN:   Full multi-step FC sequence with signatures preserved

Success = format 1 produces valid text continuation, format 2 fails or degrades.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types


MODELS = ["gemini-3.5-flash", "gemini-3.7-flash"]

SYSTEM_INSTRUCTION = """You are FRIDAY, an autonomous AI operations orchestrator.
Respond to function results with a brief natural language summary."""

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify the current event into a Cynefin domain.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "domain": types.Schema(type="STRING", enum=["clear", "complicated", "complex", "chaotic", "casual"]),
                    "reasoning": types.Schema(type="STRING"),
                },
                required=["domain", "reasoning"],
            ),
        ),
        types.FunctionDeclaration(
            name="select_agent",
            description="Dispatch an agent to handle the event.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "agent_role": types.Schema(type="STRING", enum=["architect", "developer", "sysadmin"]),
                    "task_summary": types.Schema(type="STRING"),
                },
                required=["agent_role", "task_summary"],
            ),
        ),
        types.FunctionDeclaration(
            name="wait_for_user",
            description="Park and wait for next user message.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reason": types.Schema(type="STRING"),
                },
                required=["reason"],
            ),
        ),
    ])
]


@dataclass
class ProbeResult:
    name: str
    model: str
    success: bool
    text_output: str = ""
    tool_calls: list[str] = field(default_factory=list)
    error: str = ""
    latency_ms: float = 0
    has_thought_signature: bool = False


async def step1_get_function_call(client: genai.Client, model: str) -> dict | None:
    """Step 1: Get a real functionCall + thought_signature from the model."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.7,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    contents = [
        types.Content(role="user", parts=[
            types.Part.from_text(text="[USER]: The ArgoCD sync on darwin-blackboard has been failing for 20 minutes. Please investigate.")
        ])
    ]

    response = await client.aio.models.generate_content(
        model=model, contents=contents, config=config,
    )

    candidate = response.candidates[0]
    raw_content = candidate.content

    result = {
        "role": raw_content.role,
        "parts": [],
        "has_signature": False,
        "has_fc": False,
        "has_text": False,
    }

    for part in raw_content.parts:
        part_dict = {}
        if hasattr(part, "text") and part.text:
            part_dict["text"] = part.text
            if hasattr(part, "thought") and part.thought:
                part_dict["thought"] = True
            result["has_text"] = True
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            part_dict["functionCall"] = {
                "name": str(fc.name),
                "args": dict(fc.args) if fc.args else {},
            }
            result["has_fc"] = True
        sig = getattr(part, "thought_signature", None) or getattr(part, "thoughtSignature", None)
        if sig:
            import base64
            part_dict["thought_signature"] = base64.b64encode(sig).decode("ascii") if isinstance(sig, bytes) else str(sig)
            result["has_signature"] = True
        if part_dict:
            result["parts"].append(part_dict)

    return result


async def probe_correct_format(client: genai.Client, model: str, step1_result: dict) -> ProbeResult:
    """Probe: CORRECT format — model:[FC+sig] → user:[functionResponse]."""
    import base64

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.7,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    # Build contents with CORRECT format
    user_prompt = types.Content(role="user", parts=[
        types.Part.from_text(text="[USER]: The ArgoCD sync on darwin-blackboard has been failing for 20 minutes.")
    ])

    # Model's response: functionCall + thought_signature (as returned by API)
    model_parts = []
    fc_name = None
    for p in step1_result["parts"]:
        sdk_part_kwargs = {}
        if p.get("text"):
            if p.get("thought"):
                model_parts.append(types.Part(text=p["text"], thought=True))
            else:
                model_parts.append(types.Part(text=p["text"]))
            continue
        if p.get("functionCall"):
            fc_name = p["functionCall"]["name"]
            fc_part = types.Part.from_function_call(
                name=fc_name,
                args=p["functionCall"]["args"],
            )
            if p.get("thought_signature"):
                sig_bytes = base64.b64decode(p["thought_signature"])
                fc_part.thought_signature = sig_bytes
            model_parts.append(fc_part)

    model_content = types.Content(role="model", parts=model_parts)

    # User's functionResponse
    fr_content = types.Content(role="user", parts=[
        types.Part.from_function_response(
            name=fc_name or "classify_event",
            response={"domain": "complicated", "service": "darwin-blackboard", "action_taken": "classified"},
        )
    ])

    contents = [user_prompt, model_content, fr_content]

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model, contents=contents, config=config,
        )
        latency = (time.perf_counter() - start) * 1000

        text_parts = []
        tool_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text and not (hasattr(part, "thought") and part.thought):
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                tool_calls.append(part.function_call.name)

        return ProbeResult(
            name="CORRECT_FORMAT",
            model=model,
            success=bool(text_parts) or bool(tool_calls),
            text_output="\n".join(text_parts)[:300],
            tool_calls=tool_calls,
            latency_ms=latency,
            has_thought_signature=step1_result["has_signature"],
        )
    except Exception as e:
        return ProbeResult(
            name="CORRECT_FORMAT", model=model, success=False,
            error=str(e), latency_ms=(time.perf_counter() - start) * 1000,
        )


async def probe_broken_format(client: genai.Client, model: str, step1_result: dict) -> ProbeResult:
    """Probe: BROKEN format — user:[text+thought_signature] (current brain.py behavior)."""
    import base64

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.7,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    user_prompt = types.Content(role="user", parts=[
        types.Part.from_text(text="[USER]: The ArgoCD sync on darwin-blackboard has been failing for 20 minutes.")
    ])

    # BROKEN: Simulate what brain.py currently does
    # Take the functionCall's thought_signature and put it on a TEXT part in USER role
    sig_bytes = None
    fc_name = "classify_event"
    for p in step1_result["parts"]:
        if p.get("thought_signature"):
            sig_bytes = base64.b64decode(p["thought_signature"])
        if p.get("functionCall"):
            fc_name = p["functionCall"]["name"]

    broken_text = f"[SYSTEM {fc_name}]: domain=complicated, reasoning=ArgoCD sync failure investigation"
    broken_part = types.Part(text=broken_text)
    if sig_bytes:
        broken_part.thought_signature = sig_bytes

    broken_content = types.Content(role="user", parts=[broken_part])

    contents = [user_prompt, broken_content]

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model, contents=contents, config=config,
        )
        latency = (time.perf_counter() - start) * 1000

        text_parts = []
        tool_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text and not (hasattr(part, "thought") and part.thought):
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                tool_calls.append(part.function_call.name)

        return ProbeResult(
            name="BROKEN_FORMAT",
            model=model,
            success=bool(text_parts) or bool(tool_calls),
            text_output="\n".join(text_parts)[:300],
            tool_calls=tool_calls,
            latency_ms=latency,
        )
    except Exception as e:
        return ProbeResult(
            name="BROKEN_FORMAT", model=model, success=False,
            error=str(e), latency_ms=(time.perf_counter() - start) * 1000,
        )


async def probe_multi_step_chain(client: genai.Client, model: str, step1_result: dict) -> ProbeResult:
    """Probe: Multi-step chain — classify → functionResponse → select_agent."""
    import base64

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.7,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    user_prompt = types.Content(role="user", parts=[
        types.Part.from_text(text="[USER]: Build pipeline OOM on PR #200. Pod killed at 3.8GB. Get someone to fix it.")
    ])

    # Step 1: model calls classify_event (with signature from step1)
    fc_part = types.Part.from_function_call(
        name="classify_event",
        args={"domain": "complicated", "reasoning": "Build OOM is a known-unknown requiring expert analysis"},
    )
    for p in step1_result["parts"]:
        if p.get("thought_signature"):
            fc_part.thought_signature = base64.b64decode(p["thought_signature"])
            break

    model_step1 = types.Content(role="model", parts=[fc_part])

    # Step 1 response
    fr_step1 = types.Content(role="user", parts=[
        types.Part.from_function_response(
            name="classify_event",
            response={"domain": "complicated", "classified": True},
        )
    ])

    contents = [user_prompt, model_step1, fr_step1]

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model, contents=contents, config=config,
        )
        latency = (time.perf_counter() - start) * 1000

        text_parts = []
        tool_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text and not (hasattr(part, "thought") and part.thought):
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                tool_calls.append(part.function_call.name)

        # Success = model continues with select_agent or text (chain intact)
        return ProbeResult(
            name="MULTI_STEP_CHAIN",
            model=model,
            success=bool(text_parts) or "select_agent" in tool_calls,
            text_output="\n".join(text_parts)[:300],
            tool_calls=tool_calls,
            latency_ms=latency,
        )
    except Exception as e:
        return ProbeResult(
            name="MULTI_STEP_CHAIN", model=model, success=False,
            error=str(e), latency_ms=(time.perf_counter() - start) * 1000,
        )


async def run_probe():
    """Run all probes against both models."""
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "")),
        location=os.environ.get("GCP_LOCATION", "global"),
    )

    print("=" * 80)
    print("THOUGHT SIGNATURE REPLAY FORMAT PROBE")
    print("Validates: correct FC/FR format vs broken text+sig format")
    print("=" * 80)

    for model in MODELS:
        print(f"\n\n{'━' * 80}")
        print(f"MODEL: {model}")
        print(f"{'━' * 80}")

        # Step 1: Get a real function call + signature
        print(f"\n  [Step 1] Getting real functionCall + thought_signature...")
        try:
            step1 = await step1_get_function_call(client, model)
        except Exception as e:
            print(f"    FATAL: Could not get initial FC: {e}")
            continue

        print(f"    Has functionCall: {step1['has_fc']}")
        print(f"    Has thought_signature: {step1['has_signature']}")
        print(f"    Has text: {step1['has_text']}")
        print(f"    Parts: {len(step1['parts'])}")
        for i, p in enumerate(step1["parts"]):
            keys = [k for k in p.keys() if k not in ("text",) or not p.get("thought")]
            val_preview = ""
            if p.get("functionCall"):
                val_preview = f"  → {p['functionCall']['name']}({json.dumps(p['functionCall']['args'])[:80]})"
            elif p.get("text"):
                val_preview = f"  → {p['text'][:80]}..."
            print(f"      [{i}] {keys}{val_preview}")

        if not step1["has_fc"]:
            print(f"    WARNING: Model did not call a function. Using synthetic FC for remaining probes.")
            step1["parts"].append({
                "functionCall": {"name": "classify_event", "args": {"domain": "complicated", "reasoning": "sync failure"}},
            })

        # Probe 1: CORRECT format
        print(f"\n  [Probe 1] CORRECT FORMAT: model:[FC+sig] → user:[functionResponse]")
        result_correct = await probe_correct_format(client, model, step1)
        status = "✓ PASS" if result_correct.success else "✗ FAIL"
        print(f"    Result: {status} ({result_correct.latency_ms:.0f}ms)")
        if result_correct.error:
            print(f"    Error: {result_correct.error[:200]}")
        if result_correct.text_output:
            print(f"    Text: {result_correct.text_output[:150]}")
        if result_correct.tool_calls:
            print(f"    Tools: {' → '.join(result_correct.tool_calls)}")

        # Probe 2: BROKEN format
        print(f"\n  [Probe 2] BROKEN FORMAT: user:[text+thought_signature]")
        result_broken = await probe_broken_format(client, model, step1)
        status = "✓ (works)" if result_broken.success else "✗ (fails/degrades)"
        print(f"    Result: {status} ({result_broken.latency_ms:.0f}ms)")
        if result_broken.error:
            print(f"    Error: {result_broken.error[:200]}")
        if result_broken.text_output:
            print(f"    Text: {result_broken.text_output[:150]}")
        if result_broken.tool_calls:
            print(f"    Tools: {' → '.join(result_broken.tool_calls)}")

        # Probe 3: Multi-step chain
        print(f"\n  [Probe 3] MULTI-STEP CHAIN: classify → FR → next action")
        result_chain = await probe_multi_step_chain(client, model, step1)
        status = "✓ PASS" if result_chain.success else "✗ FAIL"
        print(f"    Result: {status} ({result_chain.latency_ms:.0f}ms)")
        if result_chain.error:
            print(f"    Error: {result_chain.error[:200]}")
        if result_chain.text_output:
            print(f"    Text: {result_chain.text_output[:150]}")
        if result_chain.tool_calls:
            print(f"    Tools: {' → '.join(result_chain.tool_calls)}")

        # Summary
        print(f"\n  {'─' * 60}")
        print(f"  SUMMARY for {model}:")
        print(f"    Correct format:  {'PASS' if result_correct.success else 'FAIL'}")
        print(f"    Broken format:   {'works (no 400)' if result_broken.success else 'FAILS (400 or empty)'}")
        print(f"    Multi-step:      {'PASS' if result_chain.success else 'FAIL'}")
        print(f"    Signature found: {step1['has_signature']}")

    print(f"\n\n{'=' * 80}")
    print("PROBE COMPLETE")
    print("Expected: CORRECT passes, BROKEN degrades or fails, CHAIN proves continuity")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(run_probe())
