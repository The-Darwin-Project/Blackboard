# BlackBoard/tests/probe_claude_opus.py
# Probe: Verify Claude Opus 4.6 works via AnthropicVertex SDK on Vertex AI
# Tests: basic text gen, function calling (Brain pattern), response format parity

import asyncio
import json
import os
import sys
import time


async def main():
    print("=" * 60)
    print("Claude Opus 4.6 -- Vertex AI Probe (Anthropic SDK)")
    print("=" * 60)

    # --- Setup ---
    try:
        from anthropic import AnthropicVertex, AsyncAnthropicVertex
    except ImportError:
        print("FAIL: anthropic SDK not installed (pip install anthropic)")
        sys.exit(1)

    project = os.getenv("GCP_PROJECT", "cnv-ai-insights")
    region = os.getenv("GCP_LOCATION", "global")
    model_name = "claude-opus-4-6"

    import anthropic
    print(f"\nProject:  {project}")
    print(f"Region:   {region}")
    print(f"Model:    {model_name}")
    print(f"SDK ver:  {anthropic.__version__}")

    client = AsyncAnthropicVertex(region=region, project_id=project)

    # =========================================================================
    # Test 1: Basic text generation
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 1: Basic text generation")
    print("-" * 60)
    t0 = time.time()
    try:
        message = await client.messages.create(
            model=model_name,
            max_tokens=256,
            messages=[{"role": "user", "content": "Say hello in exactly 5 words."}],
        )
        elapsed = time.time() - t0
        text = message.content[0].text if message.content else "EMPTY"
        print(f"  Response:   {text}")
        print(f"  Stop:       {message.stop_reason}")
        print(f"  Usage:      in={message.usage.input_tokens} out={message.usage.output_tokens}")
        print(f"  Latency:    {elapsed:.2f}s")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # =========================================================================
    # Test 2: Function calling -- single tool (Anthropic tool-use format)
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 2: Function calling -- single tool")
    print("-" * 60)

    simple_tools = [
        {
            "name": "close_event",
            "description": "Close the event as resolved.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was done",
                    },
                },
                "required": ["summary"],
            },
        },
    ]

    t0 = time.time()
    try:
        message = await client.messages.create(
            model=model_name,
            max_tokens=512,
            system="You are a system operations brain. Use close_event when issues are resolved.",
            messages=[
                {
                    "role": "user",
                    "content": "The CPU issue on darwin-store is resolved. CPU dropped to 2%. Close this event.",
                }
            ],
            tools=simple_tools,
        )
        elapsed = time.time() - t0

        tool_uses = [b for b in message.content if b.type == "tool_use"]
        if tool_uses:
            tc = tool_uses[0]
            print(f"  Function:   {tc.name}")
            print(f"  Args:       {json.dumps(tc.input, indent=4)}")
            print(f"  Stop:       {message.stop_reason}")
            print(f"  Latency:    {elapsed:.2f}s")
            print("  PASS -- tool_use works")
        else:
            text_blocks = [b.text for b in message.content if hasattr(b, "text")]
            print(f"  Text:       {''.join(text_blocks)[:200]}")
            print(f"  Latency:    {elapsed:.2f}s")
            print("  WARN -- no tool_use returned")
    except Exception as e:
        print(f"  FAIL: {e}")

    # =========================================================================
    # Test 3: Function calling -- full Brain tool set
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 3: Function calling -- full Brain tool set (routing test)")
    print("-" * 60)

    brain_tools = [
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
                    "summary": {"type": "string", "description": "Summary"},
                },
                "required": ["summary"],
            },
        },
        {
            "name": "request_user_approval",
            "description": "Pause and ask the user to approve a plan.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "plan_summary": {"type": "string", "description": "Plan summary"},
                },
                "required": ["plan_summary"],
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
        {
            "name": "wait_for_user",
            "description": "Signal that the current question is answered.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Findings summary"},
                },
                "required": ["summary"],
            },
        },
    ]

    system_prompt = """You are the Brain of the Darwin autonomous operations platform.
You coordinate specialist agents (architect, sysadmin, developer) to resolve infrastructure events.

Decision Guidelines:
- Route infrastructure investigation to sysadmin
- Route code analysis to architect
- Route code changes to developer
- After an agent executes a fix, use re_trigger_aligner to verify
- For code/template changes, request_user_approval first"""

    event_prompt = """Event ID: evt-test-001
Source: aligner
Service: darwin-store
Status: new
Reason: High CPU usage detected
Evidence: Service: darwin-store, CPU: 95.6%, Memory: 26.3%, Replicas: 1/1

Conversation:
[Turn 1] aligner.confirm: "Sustained high CPU on darwin-store: avg 95.6%, peak 100.0%. The service is consistently at nearly 100% CPU."

What action should you take?"""

    t0 = time.time()
    try:
        message = await client.messages.create(
            model=model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": event_prompt}],
            tools=brain_tools,
        )
        elapsed = time.time() - t0

        tool_uses = [b for b in message.content if b.type == "tool_use"]
        text_blocks = [b.text for b in message.content if hasattr(b, "text") and b.type == "text"]

        if text_blocks:
            print(f"  Thinking:   {text_blocks[0][:200]}")
        if tool_uses:
            tc = tool_uses[0]
            print(f"  Function:   {tc.name}")
            print(f"  Args:       {json.dumps(tc.input, indent=4)}")
            print(f"  Stop:       {message.stop_reason}")
            print(f"  Latency:    {elapsed:.2f}s")

            if tc.name == "select_agent" and tc.input.get("agent_name") == "sysadmin":
                print("  PASS -- correctly routed to sysadmin for CPU investigation")
            elif tc.name == "select_agent":
                print(f"  WARN -- routed to {tc.input.get('agent_name')} (expected sysadmin)")
            else:
                print(f"  INFO -- chose {tc.name} instead of select_agent")
        else:
            print(f"  Text only:  {''.join(text_blocks)[:300]}")
            print("  WARN -- no tool_use in response")
    except Exception as e:
        print(f"  FAIL: {e}")

    # =========================================================================
    # Test 4: Response structure inspection
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 4: Response structure (for adapter design)")
    print("-" * 60)
    try:
        message = await client.messages.create(
            model=model_name,
            max_tokens=512,
            system="You are an operations brain. Use select_agent to route tasks.",
            messages=[
                {"role": "user", "content": "Route this to sysadmin: check pod logs for darwin-store"}
            ],
            tools=brain_tools,
        )

        print(f"  message.id:           {message.id}")
        print(f"  message.model:        {message.model}")
        print(f"  message.stop_reason:  {message.stop_reason}")
        print(f"  message.role:         {message.role}")
        print(f"  content blocks:       {len(message.content)}")
        for i, block in enumerate(message.content):
            print(f"    [{i}] type={block.type}", end="")
            if block.type == "tool_use":
                print(f"  name={block.name}  input_keys={list(block.input.keys())}")
            elif block.type == "text":
                print(f"  text={block.text[:80]!r}")
            else:
                print()
        print(f"  usage:                in={message.usage.input_tokens} out={message.usage.output_tokens}")
        print("  PASS -- structure mapped")
    except Exception as e:
        print(f"  FAIL: {e}")

    # =========================================================================
    # Test 5: Gemini Pro baseline (google-genai, same prompt)
    # =========================================================================
    print("\n" + "-" * 60)
    print("TEST 5: Gemini Pro baseline (google-genai, same prompt)")
    print("-" * 60)
    try:
        from google import genai
        from google.genai import types

        g_client = genai.Client(vertexai=True, project=project, location=region)
        gemini_model = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")

        # Convert to google-genai format
        g_tools = types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=t["name"], description=t["description"],
                parameters_json_schema=t["input_schema"],
            ) for t in brain_tools
        ])

        t0 = time.time()
        resp = await g_client.aio.models.generate_content(
            model=gemini_model,
            contents=event_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[g_tools],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.8, top_p=0.95,
            ),
        )
        elapsed = time.time() - t0

        if resp.function_calls:
            fc = resp.function_calls[0]
            print(f"  Gemini:     {fc.name}({json.dumps(fc.args)[:200]})")
            print(f"  Latency:    {elapsed:.2f}s")
        elif resp.text:
            print(f"  Gemini:     text: {resp.text[:200]}")
            print(f"  Latency:    {elapsed:.2f}s")
        print("  (baseline for comparison)")
    except Exception as e:
        print(f"  SKIP: {e}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("PROBE COMPLETE -- API Contract Comparison")
    print("=" * 60)
    print("""
  google-genai (Gemini)         | anthropic (Claude)
  ------------------------------|-------------------------------
  client.aio.models.            | client.messages.create()
    generate_content()          |
  resp.function_calls[0].name   | msg.content[i].name
  resp.function_calls[0].args   |   (where .type == 'tool_use')
  resp.text                     | msg.content[i].input
  types.FunctionDeclaration     | msg.content[i].text
  types.Tool                    |   (where .type == 'text')
                                | tools=[{name, input_schema}]
  
  Swap requires: adapter layer in Brain to normalize both APIs.
  OR: dual-client with shared tool schema (dict -> SDK-specific).
""")


if __name__ == "__main__":
    asyncio.run(main())
