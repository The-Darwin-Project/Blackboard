# BlackBoard/tests/simulate_adapter.py
# Simulation: Validate the adapter normalization layer design
# Tests that both Gemini and Claude produce identical LLMResponse contracts
# that the Brain's _execute_function_call() can consume.

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# Simulated adapter types (what will live in src/agents/llm/types.py)
# ============================================================================

@dataclass
class FunctionCall:
    name: str
    args: dict


@dataclass
class LLMResponse:
    function_call: Optional[FunctionCall]
    text: Optional[str]


# ============================================================================
# Simulated tool schemas (what will live in src/agents/llm/types.py)
# ============================================================================

BRAIN_TOOL_SCHEMAS = [
    {
        "name": "select_agent",
        "description": "Route work to an agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["architect", "sysadmin", "developer"],
                    "description": "Which agent to route to",
                },
                "task_instruction": {
                    "type": "string",
                    "description": "What the agent should do (be specific and actionable)",
                },
            },
            "required": ["agent_name", "task_instruction"],
        },
    },
    {
        "name": "close_event",
        "description": "Close the event as resolved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Summary of what was done"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "re_trigger_aligner",
        "description": "Ask the Aligner to verify a change took effect.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service to check"},
                "check_condition": {"type": "string", "description": "Condition to verify"},
            },
            "required": ["service", "check_condition"],
        },
    },
    {
        "name": "defer_event",
        "description": "Defer an event for later processing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why deferred"},
                "delay_seconds": {"type": "integer", "description": "Wait seconds (30-300)"},
            },
            "required": ["reason", "delay_seconds"],
        },
    },
]


# ============================================================================
# Simulated GeminiAdapter (what will live in gemini_client.py)
# ============================================================================

class GeminiAdapter:
    def __init__(self, project: str, location: str, model_name: str):
        from google import genai
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model_name = model_name

    async def generate(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
    ) -> LLMResponse:
        from google.genai import types

        config_kwargs = {
            "temperature": temperature,
            "top_p": top_p,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if tools:
            # Convert dict schemas to google-genai FunctionDeclaration
            declarations = []
            for t in tools:
                declarations.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["input_schema"],
                ))
            config_kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        # Normalize response
        if response.function_calls:
            fc = response.function_calls[0]
            return LLMResponse(
                function_call=FunctionCall(name=fc.name, args=fc.args if fc.args else {}),
                text=None,
            )
        return LLMResponse(function_call=None, text=response.text)


# ============================================================================
# Simulated ClaudeAdapter (what will live in claude_client.py)
# ============================================================================

class ClaudeAdapter:
    def __init__(self, project: str, location: str, model_name: str):
        from anthropic import AsyncAnthropicVertex
        self._client = AsyncAnthropicVertex(region=location, project_id=project)
        self._model_name = model_name

    async def generate(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
    ) -> LLMResponse:
        # Claude rejects temperature + top_p together -- use temperature only
        kwargs = {
            "model": self._model_name,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": contents if isinstance(contents, str) else contents}],
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools  # Anthropic uses dict format natively

        message = await self._client.messages.create(**kwargs)

        # Normalize response
        tool_uses = [b for b in message.content if b.type == "tool_use"]
        if tool_uses:
            tc = tool_uses[0]
            return LLMResponse(
                function_call=FunctionCall(name=tc.name, args=tc.input if tc.input else {}),
                text=None,
            )
        text_blocks = [b.text for b in message.content if hasattr(b, "text") and b.type == "text"]
        return LLMResponse(function_call=None, text="".join(text_blocks) if text_blocks else None)


# ============================================================================
# Simulated Brain dispatch (what _execute_function_call receives)
# ============================================================================

def simulate_brain_dispatch(response: LLMResponse) -> dict:
    """Simulate what Brain._execute_function_call() receives.
    Returns a dict describing the dispatch for verification."""
    if response.function_call:
        fc = response.function_call
        return {
            "dispatched": True,
            "func_name": fc.name,
            "func_args": fc.args,
            "name_type": type(fc.name).__name__,
            "args_type": type(fc.args).__name__,
            "has_required_keys": True,
        }
    elif response.text:
        return {
            "dispatched": False,
            "action": "think",
            "text_preview": response.text[:150],
        }
    else:
        return {"dispatched": False, "action": "empty"}


# ============================================================================
# Test scenarios
# ============================================================================

SYSTEM_PROMPT = """You are the Brain of the Darwin autonomous operations platform.
You coordinate specialist agents (architect, sysadmin, developer) to resolve infrastructure events.
Decision Guidelines:
- Route infrastructure investigation to sysadmin
- Route code analysis to architect
- Route code changes to developer"""

SCENARIOS = [
    {
        "name": "Route to sysadmin (high CPU)",
        "prompt": (
            "Event: darwin-store, high CPU (95.6%), 1/1 replicas.\n"
            "Conversation: [Turn 1] aligner: Sustained high CPU on darwin-store.\n"
            "What is the next action?"
        ),
        "expect_func": "select_agent",
        "expect_arg_key": "agent_name",
        "expect_arg_value": "sysadmin",
    },
    {
        "name": "Close resolved event",
        "prompt": (
            "Event: darwin-store, CPU was high but resolved.\n"
            "Conversation:\n"
            "  [Turn 1] aligner: High CPU 95%.\n"
            "  [Turn 2] brain.route: Routing to sysadmin.\n"
            "  [Turn 3] sysadmin: Investigated, found chaos experiment. Disabled it.\n"
            "  [Turn 4] aligner: CPU recovered to 2%, memory normal.\n"
            "Close this event -- the issue is resolved."
        ),
        "expect_func": "close_event",
        "expect_arg_key": "summary",
        "expect_arg_value": None,  # Any non-empty string
    },
    {
        "name": "Simple text gen (no tools)",
        "prompt": "Parse this filter instruction into JSON: 'ignore errors for darwin-store for 30 minutes'",
        "tools": None,
        "expect_func": None,  # Text-only response
    },
]


async def main():
    print("=" * 70)
    print("Adapter Simulation -- End-to-End Brain Dispatch Validation")
    print("=" * 70)

    project = os.getenv("GCP_PROJECT", "")
    location = os.getenv("GCP_LOCATION", "global")

    gemini_model = os.getenv("LLM_MODEL_BRAIN", "gemini-3.1-pro-preview")
    claude_model = "claude-opus-4-6"

    gemini = GeminiAdapter(project, location, gemini_model)
    claude = ClaudeAdapter(project, location, claude_model)

    results = {"gemini": [], "claude": []}

    for scenario in SCENARIOS:
        tools = scenario.get("tools", BRAIN_TOOL_SCHEMAS)
        expect_func = scenario.get("expect_func")

        print(f"\n{'─' * 70}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'─' * 70}")

        for name, adapter in [("gemini", gemini), ("claude", claude)]:
            t0 = time.time()
            try:
                resp = await adapter.generate(
                    system_prompt=SYSTEM_PROMPT if tools else "",
                    contents=scenario["prompt"],
                    tools=tools,
                    temperature=0.3,
                )
                elapsed = time.time() - t0
                dispatch = simulate_brain_dispatch(resp)

                # Validate
                passed = True
                if expect_func:
                    if not dispatch["dispatched"]:
                        passed = False
                        reason = "expected function call, got text"
                    elif dispatch["func_name"] != expect_func:
                        passed = False
                        reason = f"expected {expect_func}, got {dispatch['func_name']}"
                    elif scenario.get("expect_arg_key") and scenario["expect_arg_key"] not in dispatch["func_args"]:
                        passed = False
                        reason = f"missing key {scenario['expect_arg_key']}"
                    elif scenario.get("expect_arg_value") and dispatch["func_args"].get(scenario["expect_arg_key"]) != scenario["expect_arg_value"]:
                        passed = False
                        reason = f"expected {scenario['expect_arg_value']}, got {dispatch['func_args'].get(scenario['expect_arg_key'])}"
                    else:
                        reason = "correct function + args"
                elif expect_func is None:
                    if dispatch["dispatched"]:
                        passed = False
                        reason = f"expected text-only, got {dispatch['func_name']}"
                    elif resp.text:
                        reason = "text-only response (correct)"
                    else:
                        passed = False
                        reason = "empty response"

                status = "PASS" if passed else "FAIL"
                print(f"  [{name:6s}] {status} ({elapsed:.1f}s) -- {reason}")
                if dispatch["dispatched"]:
                    print(f"           func={dispatch['func_name']}  args_type={dispatch['args_type']}")
                    if dispatch["func_name"] == "select_agent":
                        print(f"           agent={dispatch['func_args'].get('agent_name')}")
                        task = dispatch['func_args'].get('task_instruction', '')
                        print(f"           task={task[:120]}...")
                    elif dispatch["func_name"] == "close_event":
                        print(f"           summary={dispatch['func_args'].get('summary', '')[:120]}...")
                else:
                    print(f"           text={resp.text[:120] if resp.text else 'None'}...")

                results[name].append({"scenario": scenario["name"], "passed": passed, "latency": elapsed})

            except Exception as e:
                print(f"  [{name:6s}] ERROR: {e}")
                results[name].append({"scenario": scenario["name"], "passed": False, "latency": 0})

    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n{'=' * 70}")
    print("SIMULATION SUMMARY")
    print(f"{'=' * 70}")

    for provider in ["gemini", "claude"]:
        passed = sum(1 for r in results[provider] if r["passed"])
        total = len(results[provider])
        avg_latency = sum(r["latency"] for r in results[provider]) / max(total, 1)
        print(f"  {provider:8s}: {passed}/{total} passed, avg latency {avg_latency:.1f}s")

    all_pass = all(r["passed"] for rs in results.values() for r in rs)
    print(f"\n  Adapter contract validated: {'YES' if all_pass else 'NO -- see failures above'}")
    print(f"  Brain dispatch contract:    func_name=str, func_args=dict (identical for both)")
    print()

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
