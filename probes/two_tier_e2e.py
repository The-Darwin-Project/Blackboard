# probes/two_tier_e2e.py
# @ai-rules:
# 1. [Constraint]: This is a disposable probe script — not production code.
# 2. [Pattern]: Validates the two-tier Chat-native architecture against the real SDK.
# 3. [Gotcha]: Uses synchronous JSON file as "Blackboard" to avoid Redis dependency.
"""
Two-Tier Chat-Native Architecture Probe

Validates the full reconciler loop against the real Gemini Chat SDK:
1. Evidence (role=user) → Chat session created
2. Internal FC/FR loop: classify_event → set_phase → select_agent
3. Terminal tool breaks the loop
4. FR always paired (no orphaned FC)
5. was_rebuilt gate (rebuild doesn't double-send)
6. Role merge (consecutive user macros merged)
7. Progress turns written but NOT replayed on rebuild

Uses a JSON file as the Blackboard and real Gemini Chat API.
"""
import asyncio
import json
import os
import time
from pathlib import Path

os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "/home/thason/Git/GitHub/The-Darwin-Project/cnv-ai-insights-8502f29094a2.json",
)

from google import genai
from google.genai import types

PROJECT_ID = "cnv-ai-insights"
MODEL = "gemini-2.5-flash"
BLACKBOARD_FILE = Path("/tmp/two_tier_probe_blackboard.json")
MAX_TOOL_CALLS = 8

# --- Tool declarations (simplified FRIDAY tools) ---
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify the event into a Cynefin domain (clear/complicated/complex/chaotic).",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["clear", "complicated", "complex", "chaotic"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["domain", "reasoning"],
            },
        ),
        types.FunctionDeclaration(
            name="set_phase",
            description="Transition to a new brain phase (triage/dispatch/verify/escalate/close).",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "phase": {"type": "string", "enum": ["triage", "dispatch", "verify", "escalate", "close"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["phase", "reasoning"],
            },
        ),
        types.FunctionDeclaration(
            name="select_agent",
            description="TERMINAL: Dispatch an agent to handle the task. This ends the current reasoning loop.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": ["developer", "architect", "sysadmin"]},
                    "task": {"type": "string"},
                },
                "required": ["agent", "task"],
            },
        ),
        types.FunctionDeclaration(
            name="web_search",
            description="Search the web for current information about a topic.",
            parameters_json_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
    ])
]

TERMINAL_TOOLS = {"select_agent", "close_event", "defer_event", "wait_for_user"}
STATE_MUTATING_TOOLS = {"set_phase", "classify_event"}

# --- Blackboard (JSON file) ---

def load_blackboard() -> dict:
    if BLACKBOARD_FILE.exists():
        return json.loads(BLACKBOARD_FILE.read_text())
    return {"event_id": "evt-probe-001", "status": "active", "phase": "triage", "domain": None, "conversation": []}

def save_blackboard(bb: dict):
    BLACKBOARD_FILE.write_text(json.dumps(bb, indent=2))

def append_turn(bb: dict, actor: str, action: str, content: str, chat_role: str | None = None):
    turn = {
        "turn": len(bb["conversation"]),
        "actor": actor,
        "action": action,
        "content": content,
        "chat_role": chat_role,
        "timestamp": time.time(),
    }
    bb["conversation"].append(turn)
    save_blackboard(bb)
    tier = "MACRO" if chat_role else "progress"
    print(f"  [{tier}] {actor}.{action}: {content[:100]}")

def get_macro_turns(bb: dict) -> list[dict]:
    return [t for t in bb["conversation"] if t.get("chat_role") in ("user", "model")]

def format_macro_for_rebuild(bb: dict) -> list[types.Content]:
    """Convert macro turns to SDK Content for rebuild. Merge consecutive same-role."""
    macros = get_macro_turns(bb)
    if not macros:
        return []
    
    history: list[types.Content] = []
    for t in macros:
        role = t["chat_role"]
        text = t["content"]
        if history and history[-1].role == role:
            # Role merge: append to existing content's parts
            history[-1].parts.append(types.Part.from_text(text=text))
        else:
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
    return history

def format_macro_delta(bb: dict) -> str:
    """Get new macro user turns since last macro model turn (the delta)."""
    macros = get_macro_turns(bb)
    # Find last model turn index
    last_model_idx = -1
    for i, t in enumerate(macros):
        if t["chat_role"] == "model":
            last_model_idx = i
    
    # Delta = user turns after last model turn
    delta_turns = [t for t in macros[last_model_idx + 1:] if t["chat_role"] == "user"]
    if not delta_turns:
        return ""
    # Merge into one text block
    return "\n\n".join(t["content"] for t in delta_turns)

# --- Tool execution (simulated) ---

def execute_tool(name: str, args: dict, bb: dict) -> str:
    """Execute a tool and return the result text."""
    if name == "classify_event":
        bb["domain"] = args.get("domain", "clear")
        save_blackboard(bb)
        return f"Domain set: {bb['domain']}. Reasoning: {args.get('reasoning', '')}"
    elif name == "set_phase":
        old = bb["phase"]
        bb["phase"] = args.get("phase", "triage")
        save_blackboard(bb)
        return f"Phase transition: {old} -> {bb['phase']}. Reasoning: {args.get('reasoning', '')}"
    elif name == "select_agent":
        return f"Agent {args.get('agent')} dispatched with task: {args.get('task', '')}"
    elif name == "web_search":
        return f"Web search results for '{args.get('query', '')}': [simulated] No results (probe mode)"
    else:
        return f"Unknown tool: {name}"

# --- The Reconciler ---

async def reconcile_chat(bb: dict):
    """The two-tier reconciler. This is what we're probing."""
    
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="us-central1",
    )
    
    # --- Build config ---
    system_prompt = (
        "You are FRIDAY, an AI operations orchestrator. "
        "You are processing an operational event. "
        f"Current phase: {bb['phase']}. Domain: {bb.get('domain', 'unclassified')}. "
        "Classify the event, set the phase to dispatch, then select an agent. "
        "Call tools in sequence. Do not output text between tool calls."
    )
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=TOOLS,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        ),
    )
    
    # --- Get or create session ---
    macro_history = format_macro_for_rebuild(bb)
    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=macro_history,
    )
    was_rebuilt = True  # always true on first call (or after pod restart)
    
    print(f"\n{'='*60}")
    print(f"Session created. History: {len(macro_history)} entries (macro only)")
    print(f"{'='*60}")
    
    # --- Build message ---
    if was_rebuilt:
        # After rebuild, session has full history — just send terminal prompt
        message = "What is the next action? Call one of your tools."
    else:
        delta = format_macro_delta(bb)
        message = delta if delta else "What is the next action? Call one of your tools."
    
    # --- Internal FC/FR loop ---
    tool_calls_made = 0
    
    async def stream_and_drain(msg, cfg) -> tuple:
        """Atomic send + drain. Returns (function_call_name, function_call_args, text, thinking)."""
        fc_name, fc_args, text, thinking = None, None, "", ""
        async for chunk in await chat.send_message_stream(msg, config=cfg):
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought:
                                if hasattr(part, 'text') and part.text:
                                    thinking += part.text
                            elif hasattr(part, 'function_call') and part.function_call:
                                fc_name = part.function_call.name
                                fc_args = dict(part.function_call.args or {})
                            elif hasattr(part, 'text') and part.text:
                                text += part.text
        return fc_name, fc_args, text, thinking
    
    # First send
    print(f"\n>>> Sending initial message: {message[:80]}...")
    fc_name, fc_args, text, thinking = await stream_and_drain(message, config)
    
    if thinking:
        print(f"  [thinking] {thinking[:120]}...")
    
    for iteration in range(MAX_TOOL_CALLS):
        if text and not fc_name:
            # Text-only response — this is the macro outcome
            append_turn(bb, "brain", "response", text, chat_role="model")
            print(f"\n  TEXT-ONLY RESPONSE (macro model turn written)")
            break
        
        if not fc_name:
            print(f"\n  EMPTY RESPONSE — no FC, no text. Breaking.")
            break
        
        print(f"\n  FC[{iteration}]: {fc_name}({json.dumps(fc_args)[:80]})")
        is_terminal = fc_name in TERMINAL_TOOLS
        is_state_mutating = fc_name in STATE_MUTATING_TOOLS
        
        # Execute tool
        result = execute_tool(fc_name, fc_args, bb)
        tool_calls_made += 1
        
        # Write progress turn (UI observability, NOT replayed)
        append_turn(bb, "brain", "tool_result", result, chat_role=None)
        
        # Send FR back (pair the FC)
        fr_part = types.Part.from_function_response(
            name=fc_name,
            response={"result": result},
        )
        
        # Rebuild config if state-mutating
        if is_state_mutating:
            config = types.GenerateContentConfig(
                system_instruction=(
                    "You are FRIDAY, an AI operations orchestrator. "
                    f"Current phase: {bb['phase']}. Domain: {bb.get('domain', 'unclassified')}. "
                    "Continue processing. Call the next tool."
                ),
                tools=TOOLS,
                temperature=0.3,
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                ),
            )
            print(f"  [config rebuilt: phase={bb['phase']}, domain={bb.get('domain')}]")
        
        # Send FR and drain response
        print(f"  >>> Sending FR for {fc_name}...")
        fc_name, fc_args, text, thinking = await stream_and_drain(fr_part, config)
        
        if thinking:
            print(f"  [thinking] {thinking[:120]}...")
        
        if is_terminal:
            # Terminal tool: we still need to handle post-FR response
            if fc_name:
                print(f"  [post-terminal FC ignored: {fc_name} — would need another FR or evict]")
                suppress_fr = types.Part.from_function_response(
                    name=fc_name,
                    response={"status": "suppressed", "reason": "terminal tool already executed"},
                )
                await stream_and_drain(suppress_fr, config)
                print(f"  [orphan FC paired with suppress FR]")
            
            # Write macro outcome using the TERMINAL tool's args (saved before FR send)
            append_turn(bb, "brain", "route", result, chat_role="model")
            print(f"\n  TERMINAL TOOL — loop broken after {tool_calls_made} tool calls")
            break
    else:
        # Cap hit
        print(f"\n  CAP HIT ({MAX_TOOL_CALLS} tools). Sending synthetic FR...")
        cap_fr = types.Part.from_function_response(
            name=fc_name or "unknown",
            response={"status": "capped", "reason": "max tool calls reached"},
        )
        await stream_and_drain(cap_fr, config)
        append_turn(bb, "brain", "response", "Reached tool call limit.", chat_role="model")
    
    # --- Verify session health (can we call again without 400?) ---
    print(f"\n{'='*60}")
    print(f"PROBE: Verifying session survives for next cycle...")
    
    # Simulate: an agent result arrives (new macro user turn)
    append_turn(bb, "developer", "execute", "Agent completed the task successfully.", chat_role="user")
    
    # Send again — this should NOT 400
    try:
        fc2, args2, text2, think2 = await stream_and_drain(
            "Agent returned. What is the next action?", config
        )
        print(f"  Session survived! Response: FC={fc2}, text={text2[:60] if text2 else 'none'}")
        print(f"  NO 400 ERROR — session healthy after full loop")
    except Exception as e:
        print(f"  SESSION FAILED: {e}")
        print(f"  THIS IS THE BUG — orphaned FC or role violation")
    
    # --- Verify rebuild works from macro turns only ---
    print(f"\n{'='*60}")
    print(f"PROBE: Testing cold-start rebuild from macro turns only...")
    
    macro_history_2 = format_macro_for_rebuild(bb)
    print(f"  Macro turns for rebuild: {len(macro_history_2)}")
    for i, h in enumerate(macro_history_2):
        print(f"    [{i}] role={h.role}, parts={len(h.parts)}, text={h.parts[0].text[:60] if h.parts else '?'}...")
    
    try:
        chat2 = client.aio.chats.create(
            model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
            config=config,
            history=macro_history_2,
        )
        # Verify the new session accepts a message without 400
        fc3_name, fc3_args, text3, think3 = None, None, "", ""
        async for chunk in await chat2.send_message_stream("Continue.", config=config):
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                fc3_name = part.function_call.name
                            elif hasattr(part, 'text') and part.text and not (hasattr(part, 'thought') and part.thought):
                                text3 += part.text
        print(f"  Rebuild succeeded! Response: FC={fc3_name}, text={text3[:60] if text3 else 'none'}")
        print(f"  NO 400 — two-tier rebuild is clean")
    except Exception as e:
        print(f"  REBUILD FAILED: {e}")
    
    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"PROBE SUMMARY")
    print(f"{'='*60}")
    print(f"  Tool calls made: {tool_calls_made}")
    print(f"  Total conversation turns: {len(bb['conversation'])}")
    print(f"  Macro turns: {len(get_macro_turns(bb))}")
    print(f"  Progress turns: {len(bb['conversation']) - len(get_macro_turns(bb))}")
    print(f"  Final phase: {bb['phase']}")
    print(f"  Final domain: {bb.get('domain')}")
    print(f"\n  Blackboard saved to: {BLACKBOARD_FILE}")


async def main():
    # Clean slate
    if BLACKBOARD_FILE.exists():
        BLACKBOARD_FILE.unlink()
    
    bb = load_blackboard()
    
    # Write evidence as the first macro turn (role=user)
    append_turn(
        bb, "aligner", "evidence",
        "Kargo promotion failed for containerized-data-importer v4.20: "
        "step 'wait-for-merge' timed out after 6h. "
        "MR !6 pipeline status: failed. "
        "Service: containerized-data-importer. "
        "This appears to be a known RHSM entitlement issue.",
        chat_role="user",
    )
    
    # Run the reconciler
    await reconcile_chat(bb)


if __name__ == "__main__":
    asyncio.run(main())
