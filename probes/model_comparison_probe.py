# probes/model_comparison_probe.py
# @ai-rules:
# 1. [Purpose]: Head-to-head probe comparing gemini-3.1-pro vs gemini-3.7-flash for FRIDAY orchestrator role.
# 2. [Constraint]: Uses google-genai SDK (not google-cloud-aiplatform). Requires GOOGLE_API_KEY or ADC.
# 3. [Pattern]: Each scenario runs both models with identical SI + tools + conversation, compares outputs.
# 4. [Gotcha]: 3.7 Flash does not support thinking_level=MINIMAL. Use LOW as minimum.

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODELS = ["gemini-3.1-pro-preview-customtools", "gemini-3.7-flash"]

SYSTEM_INSTRUCTION = """You are FRIDAY, an autonomous AI operations orchestrator.
You manage events via function calling. You MUST follow these rules:

1. ALWAYS generate a visible text response to the user BEFORE calling wait_for_user.
2. When classifying events, call classify_event with the appropriate Cynefin domain.
3. When dispatching agents, call select_agent with the role and reasoning.
4. For casual conversations, respond naturally and park with wait_for_user.
5. NEVER call wait_for_user without first producing text output in the same response.
6. Use thinking to reason through complex triage decisions.

Actor Response Model:
- [USER]: Human operator messages. Respond conversationally.
- [SYSTEM]: Platform directives. Acknowledge internally, do not echo.
- [FRIDAY]: Your own prior outputs. Maintain continuity.
"""

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify the current event into a Cynefin domain. MUST be called before any agent dispatch.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "domain": types.Schema(type="STRING", enum=["clear", "complicated", "complex", "chaotic", "casual"]),
                    "reasoning": types.Schema(type="STRING", description="One sentence explaining classification"),
                    "severity": types.Schema(type="STRING", enum=["info", "warning", "critical"]),
                },
                required=["domain", "reasoning", "severity"],
            ),
        ),
        types.FunctionDeclaration(
            name="select_agent",
            description="Dispatch an agent to handle the current event. Requires prior classify_event call.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "agent_role": types.Schema(type="STRING", enum=["architect", "developer", "sysadmin", "explorer", "security_analyst", "code_reviewer", "qe"]),
                    "reasoning": types.Schema(type="STRING", description="Why this agent for this task"),
                    "task_summary": types.Schema(type="STRING", description="Brief task description for the agent"),
                },
                required=["agent_role", "reasoning", "task_summary"],
            ),
        ),
        types.FunctionDeclaration(
            name="wait_for_user",
            description="Park the conversation and wait for the next user message. You MUST generate a text response BEFORE calling this tool. If you call this without prior text output, the system will reject it.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reason": types.Schema(type="STRING", description="Why parking (e.g. 'waiting for user confirmation')"),
                },
                required=["reason"],
            ),
        ),
        types.FunctionDeclaration(
            name="consult_deep_memory",
            description="Search archived event history and lessons for relevant patterns.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="Natural language search query"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="defer_event",
            description="Defer processing for a specified duration.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "seconds": types.Schema(type="INTEGER", description="Seconds to defer"),
                    "reason": types.Schema(type="STRING", description="Why deferring"),
                },
                required=["seconds", "reason"],
            ),
        ),
    ])
]

# ---------------------------------------------------------------------------
# Test Scenarios
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    name: str
    description: str
    conversation: list[dict[str, str]]
    expected_behavior: str
    thinking_level: str = "medium"


SCENARIOS = [
    Scenario(
        name="casual_greeting",
        description="User greets FRIDAY casually. Should classify as CASUAL, respond warmly, and park.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: Hey FRIDAY, how's it going?"}]},
        ],
        expected_behavior="classify_event(casual) + text response + wait_for_user (in that order, text BEFORE wait)",
    ),
    Scenario(
        name="task_dispatch",
        description="User requests an investigation. Should classify as COMPLICATED and dispatch architect.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: I need you to investigate why the ArgoCD sync is failing on darwin-blackboard. Check the last 3 sync attempts."}]},
        ],
        expected_behavior="classify_event(complicated) + text acknowledgment + select_agent(sysadmin or architect)",
        thinking_level="high",
    ),
    Scenario(
        name="gate_compliance",
        description="Tests the critical pattern: model must generate text BEFORE calling wait_for_user.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: Thanks, that's all for now."}]},
            {"role": "model", "parts": [{"text": "You're welcome! Let me know if anything else comes up."}]},
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: 👍"}]},
        ],
        expected_behavior="Text response FIRST (even brief), THEN wait_for_user. Must NOT call wait_for_user as first action.",
    ),
    Scenario(
        name="multi_tool_chain",
        description="Complex scenario requiring classification then dispatch then park.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: The build pipeline on PR #200 failed with an OOM error. The pod got killed at 3.8GB. Can you get someone to look at it?"}]},
        ],
        expected_behavior="classify_event(complicated, warning) + text response + select_agent(developer or sysadmin) — all in one turn",
        thinking_level="high",
    ),
    Scenario(
        name="ambiguous_input",
        description="Vague user message. FRIDAY should ask for clarification, not dispatch blindly.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: something is weird"}]},
        ],
        expected_behavior="classify_event(disorder or casual) + ask clarifying question + wait_for_user. Should NOT dispatch an agent.",
    ),
    Scenario(
        name="response_loop_resistance",
        description="Simulates the gate feedback scenario. Model sees its own prior failed attempt.",
        conversation=[
            {"role": "user", "parts": [{"text": "[USER Tal Hason]: What's the status of the cluster?"}]},
            {"role": "model", "parts": [{"text": "Let me check the cluster status for you."}]},
            {"role": "model", "parts": [{"function_call": {"name": "consult_deep_memory", "args": {"query": "cluster health recent"}}}]},
            {"role": "function", "parts": [{"function_response": {"name": "consult_deep_memory", "response": {"result": "Last cluster check 2h ago: all nodes healthy, 3 pods pending in cnv-fbc-konflux."}}}]},
            {"role": "model", "parts": [{"text": "[GATE] wait_for_user blocked. No visible response generated since the last user message. Generate a text response to the user before parking."}]},
        ],
        expected_behavior="Generate a substantive text response about cluster status, THEN park. Must NOT repeat the gate error or spiral.",
        thinking_level="high",
    ),
]

# ---------------------------------------------------------------------------
# Probe Runner
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    model: str
    scenario: str
    latency_ms: float
    text_output: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_order: list[str] = field(default_factory=list)
    has_text_before_wait: bool = False
    error: str = ""
    thinking_text: str = ""


async def run_single_probe(client: genai.Client, model: str, scenario: Scenario) -> ProbeResult:
    """Run a single scenario against a single model."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.8,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(thinking_budget={"low": 1024, "medium": 4096, "high": 8192}[scenario.thinking_level]),
    )

    contents = []
    for msg in scenario.conversation:
        role = msg["role"]
        if role == "function":
            role = "user"
        parts = []
        for p in msg["parts"]:
            if "text" in p:
                parts.append(types.Part.from_text(text=p["text"]))
            elif "function_call" in p:
                fc = p["function_call"]
                parts.append(types.Part.from_function_call(name=fc["name"], args=fc["args"]))
            elif "function_response" in p:
                fr = p["function_response"]
                parts.append(types.Part.from_function_response(name=fr["name"], response=fr["response"]))
        contents.append(types.Content(role=role, parts=parts))

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        latency = (time.perf_counter() - start) * 1000
    except Exception as e:
        return ProbeResult(
            model=model, scenario=scenario.name,
            latency_ms=(time.perf_counter() - start) * 1000,
            text_output="", error=str(e),
        )

    text_parts = []
    thinking_parts = []
    tool_calls = []
    tool_call_order = []
    saw_text = False

    for part in response.candidates[0].content.parts:
        if hasattr(part, "thought") and part.thought:
            thinking_parts.append(part.text or "")
        elif hasattr(part, "text") and part.text and not (hasattr(part, "thought") and part.thought):
            text_parts.append(part.text)
            saw_text = True
        elif hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            tool_calls.append({"name": fc.name, "args": dict(fc.args) if fc.args else {}})
            tool_call_order.append(fc.name)
            if fc.name == "wait_for_user" and not saw_text:
                pass  # flag below

    has_text_before_wait = True
    if "wait_for_user" in tool_call_order:
        wait_idx = tool_call_order.index("wait_for_user")
        has_text_before_wait = saw_text or any(
            tc["name"] not in ("wait_for_user",) for tc in tool_calls[:wait_idx]
        )

    return ProbeResult(
        model=model,
        scenario=scenario.name,
        latency_ms=latency,
        text_output="\n".join(text_parts),
        tool_calls=tool_calls,
        tool_call_order=tool_call_order,
        has_text_before_wait=has_text_before_wait,
        thinking_text="\n".join(thinking_parts)[:500],
    )


async def run_probe():
    """Run all scenarios against both models."""
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "")),
        location=os.environ.get("GCP_LOCATION", "global"),
    )

    print("=" * 80)
    print("FRIDAY MODEL PROBE: gemini-3.1-pro vs gemini-3.7-flash")
    print("=" * 80)
    print()

    all_results: dict[str, list[ProbeResult]] = {m: [] for m in MODELS}

    for scenario in SCENARIOS:
        print(f"\n{'─' * 80}")
        print(f"SCENARIO: {scenario.name}")
        print(f"  {scenario.description}")
        print(f"  Expected: {scenario.expected_behavior}")
        print(f"  Thinking: {scenario.thinking_level}")
        print(f"{'─' * 80}")

        tasks = [run_single_probe(client, model, scenario) for model in MODELS]
        results = await asyncio.gather(*tasks)

        for result in results:
            all_results[result.model].append(result)
            print(f"\n  [{result.model}] ({result.latency_ms:.0f}ms)")
            if result.error:
                print(f"    ERROR: {result.error}")
                continue
            print(f"    Text: {result.text_output[:200]}{'...' if len(result.text_output) > 200 else ''}")
            print(f"    Tools: {' → '.join(result.tool_call_order) or '(none)'}")
            if result.tool_calls:
                for tc in result.tool_calls:
                    args_short = json.dumps(tc["args"], ensure_ascii=False)[:120]
                    print(f"      • {tc['name']}({args_short})")
            if "wait_for_user" in result.tool_call_order:
                gate = "✓ PASS" if result.has_text_before_wait else "✗ FAIL (wait without prior text)"
                print(f"    Gate compliance: {gate}")
            if result.thinking_text:
                print(f"    Thinking: {result.thinking_text[:150]}...")

    # Summary table
    print(f"\n\n{'=' * 80}")
    print("SUMMARY SCORECARD")
    print(f"{'=' * 80}")
    print(f"\n{'Scenario':<30} {'Metric':<20} {'3.1 Pro':<20} {'3.7 Flash':<20}")
    print(f"{'─' * 90}")

    for i, scenario in enumerate(SCENARIOS):
        pro = all_results[MODELS[0]][i]
        flash = all_results[MODELS[1]][i]

        print(f"{scenario.name:<30} {'Latency':<20} {pro.latency_ms:.0f}ms{'':<14} {flash.latency_ms:.0f}ms")
        print(f"{'':<30} {'Tools':<20} {' → '.join(pro.tool_call_order):<20} {' → '.join(flash.tool_call_order):<20}")

        if "wait_for_user" in pro.tool_call_order or "wait_for_user" in flash.tool_call_order:
            pro_gate = "✓" if pro.has_text_before_wait else "✗"
            flash_gate = "✓" if flash.has_text_before_wait else "✗"
            print(f"{'':<30} {'Gate':<20} {pro_gate:<20} {flash_gate:<20}")

        if pro.error or flash.error:
            print(f"{'':<30} {'Error':<20} {pro.error[:18]:<20} {flash.error[:18]:<20}")
        print()

    # Gate compliance summary
    pro_gate_pass = sum(1 for r in all_results[MODELS[0]] if r.has_text_before_wait or "wait_for_user" not in r.tool_call_order)
    flash_gate_pass = sum(1 for r in all_results[MODELS[1]] if r.has_text_before_wait or "wait_for_user" not in r.tool_call_order)
    total = len(SCENARIOS)

    print(f"\nGATE COMPLIANCE: 3.1 Pro {pro_gate_pass}/{total} | 3.7 Flash {flash_gate_pass}/{total}")

    avg_pro = sum(r.latency_ms for r in all_results[MODELS[0]]) / total
    avg_flash = sum(r.latency_ms for r in all_results[MODELS[1]]) / total
    print(f"AVG LATENCY:     3.1 Pro {avg_pro:.0f}ms | 3.7 Flash {avg_flash:.0f}ms")
    print(f"SPEEDUP:         {avg_pro / avg_flash:.1f}x faster (Flash)")


if __name__ == "__main__":
    asyncio.run(run_probe())
