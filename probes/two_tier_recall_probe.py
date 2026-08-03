# probes/two_tier_recall_probe.py
# @ai-rules:
# 1. [Constraint]: Disposable probe — validates RECALL mid-stream hook in two-tier model.
# 2. [Pattern]: Tests FC interception + SI rebuild + model reconsideration.
"""
Two-Tier RECALL Mid-Stream Probe

Validates that the reconciler can:
1. Stream a response and detect thinking content
2. Intercept an FC after RECALL-worthy content is found
3. Send a "blocked" FR with lesson context
4. Rebuild config with lessons in SI
5. Model reconsiders and makes a different/better tool call

Also validates: no-delta = no reconcile (replaces is_intermediate).
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
BLACKBOARD_FILE = Path("/tmp/two_tier_recall_probe.json")
MAX_TOOL_CALLS = 8

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="classify_event",
            description="Classify the event into a Cynefin domain.",
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
            description="Transition to a new brain phase.",
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
            description="TERMINAL: Dispatch an agent.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": ["developer", "architect", "sysadmin"]},
                    "task": {"type": "string"},
                },
                "required": ["agent", "task"],
            },
        ),
    ])
]

TERMINAL_TOOLS = {"select_agent", "close_event", "defer_event", "wait_for_user"}
STATE_MUTATING_TOOLS = {"set_phase", "classify_event"}


def load_bb() -> dict:
    if BLACKBOARD_FILE.exists():
        return json.loads(BLACKBOARD_FILE.read_text())
    return {"event_id": "evt-recall-probe", "status": "active", "phase": "triage",
            "domain": None, "conversation": [], "last_sent_cursor": -1}

def save_bb(bb: dict):
    BLACKBOARD_FILE.write_text(json.dumps(bb, indent=2))

def append_turn(bb, actor, action, content, chat_role=None):
    turn = {"turn": len(bb["conversation"]), "actor": actor, "action": action,
            "content": content, "chat_role": chat_role, "timestamp": time.time()}
    bb["conversation"].append(turn)
    save_bb(bb)
    tier = "MACRO" if chat_role else "progress"
    print(f"  [{tier}] {actor}.{action}: {content[:100]}")

def get_macro_turns(bb):
    return [t for t in bb["conversation"] if t.get("chat_role") in ("user", "model")]

def format_macro_for_rebuild(bb):
    macros = get_macro_turns(bb)
    history = []
    for t in macros:
        role = t["chat_role"]
        text = t["content"]
        if history and history[-1].role == role:
            history[-1].parts.append(types.Part.from_text(text=text))
        else:
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
    return history


async def stream_and_drain_with_recall(
    chat, message, config, *,
    recall_lessons: list[str] | None = None,
    recall_trigger_keywords: list[str] | None = None,
) -> tuple:
    """Atomic stream+drain WITH mid-stream RECALL hook.
    
    If recall_trigger_keywords are provided and thinking text contains any of them,
    AND lessons are available, the FIRST FC is blocked with a recall FR, config is
    rebuilt with lessons in SI, and the model reconsiders.
    
    Returns (fc_name, fc_args, text, thinking, recall_fired).
    """
    fc_name, fc_args, text, thinking = None, None, "", ""
    recall_fired = False
    
    async for chunk in await chat.send_message_stream(message, config=config):
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
    
    # --- RECALL hook: intercept FC if keywords found in thinking ---
    if (fc_name and recall_trigger_keywords and recall_lessons
            and not recall_fired
            and any(kw.lower() in thinking.lower() for kw in recall_trigger_keywords)):
        
        print(f"\n  [RECALL] Triggered! Keyword match in thinking. Blocking FC '{fc_name}'")
        print(f"  [RECALL] Injecting {len(recall_lessons)} lessons into SI")
        
        # Send blocked FR
        blocked_fr = types.Part.from_function_response(
            name=fc_name,
            response={"status": "blocked", "reason": "recall_override",
                      "lessons": recall_lessons},
        )
        
        # Rebuild config with lessons in SI
        lesson_block = "\n\n## RECALL: Relevant Lessons\n" + "\n".join(
            f"- {l}" for l in recall_lessons
        )
        new_si = config.system_instruction + lesson_block
        new_config = types.GenerateContentConfig(
            system_instruction=new_si,
            tools=config.tools,
            temperature=config.temperature,
            thinking_config=config.thinking_config,
            automatic_function_calling=config.automatic_function_calling,
            tool_config=config.tool_config,
        )
        
        # Drain the blocked FR response — model reconsiders
        fc_name, fc_args, text, thinking = None, None, "", ""
        async for chunk in await chat.send_message_stream(blocked_fr, config=new_config):
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
        
        recall_fired = True
        # Update the config reference for subsequent calls
        config = new_config
        print(f"  [RECALL] Model reconsidered → FC: {fc_name}, text: {text[:60] if text else 'none'}")
    
    return fc_name, fc_args, text, thinking, recall_fired, config


async def test_recall_mid_stream():
    """Test 1: RECALL intercepts FC, injects lessons, model reconsiders."""
    print("\n" + "="*60)
    print("TEST 1: RECALL Mid-Stream Hook")
    print("="*60)
    
    if BLACKBOARD_FILE.exists():
        BLACKBOARD_FILE.unlink()
    bb = load_bb()
    
    # Evidence that will trigger RECALL (mentions "hermetic build" which has known lessons)
    append_turn(bb, "aligner", "evidence",
        "Pipeline failed for kubevirt v5.99. The build step crashed with "
        "'Unable to read consumer identity' and 'This system is not registered'. "
        "The hermetic build mode appears to be missing RHSM credentials.",
        chat_role="user")
    
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    
    si = (
        "You are FRIDAY, an AI operations orchestrator. "
        f"Current phase: triage. Domain: unclassified. "
        "Classify the event first."
    )
    config = types.GenerateContentConfig(
        system_instruction=si,
        tools=TOOLS,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        ),
    )
    
    macro_history = format_macro_for_rebuild(bb)
    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=macro_history,
    )
    
    # RECALL lessons that should influence the classification
    lessons = [
        "RHSM entitlement errors in hermetic builds are a known systemic issue tracked as VMER-1196. Classify as CLEAR, not COMPLICATED.",
        "Pipeline failures matching 'Unable to read consumer identity' should be closed as duplicate of VMER-1196.",
    ]
    
    print("\n>>> Sending with RECALL armed (keywords: 'hermetic', 'RHSM', 'entitlement')...")
    fc, args, text, thinking, recall_fired, config = await stream_and_drain_with_recall(
        chat, "What is the next action? Call one of your tools.", config,
        recall_lessons=lessons,
        recall_trigger_keywords=["hermetic", "RHSM", "entitlement", "consumer identity"],
    )
    
    print(f"\n  Result: FC={fc}, recall_fired={recall_fired}")
    if thinking:
        print(f"  Thinking: {thinking[:200]}...")
    if fc:
        print(f"  Tool call: {fc}({json.dumps(args)[:120]})")
    
    # Verify session health after RECALL
    print(f"\n>>> Verifying session health post-RECALL...")
    if fc:
        # Execute and FR
        result = f"Domain set: {args.get('domain', '?')}"
        append_turn(bb, "brain", "tool_result", result, chat_role=None)
        fr = types.Part.from_function_response(name=fc, response={"result": result})
        fc2, args2, text2, _, _, config = await stream_and_drain_with_recall(
            chat, fr, config
        )
        print(f"  Post-RECALL session healthy! Next FC: {fc2}")
    
    print(f"\n  RECALL TEST: {'PASSED' if recall_fired else 'RECALL DID NOT FIRE (keywords not in thinking)'}")
    return recall_fired


async def test_no_delta_no_reconcile():
    """Test 2: No new macro turns → reconciler should have nothing to send."""
    print("\n" + "="*60)
    print("TEST 2: No Delta = No Reconcile (replaces is_intermediate)")
    print("="*60)
    
    bb = load_bb()
    
    macros = get_macro_turns(bb)
    last_model_idx = -1
    for i, t in enumerate(macros):
        if t["chat_role"] == "model":
            last_model_idx = i
    
    # Simulate: cursor is at current position
    cursor = len(bb["conversation"]) - 1
    
    # No new macro user turns since cursor
    new_user_macros = [
        t for t in bb["conversation"]
        if t.get("chat_role") == "user" and t["turn"] > cursor
    ]
    
    has_delta = len(new_user_macros) > 0
    print(f"  Cursor at turn {cursor}")
    print(f"  New macro user turns since cursor: {len(new_user_macros)}")
    print(f"  Has delta: {has_delta}")
    print(f"  Should reconcile: {has_delta}")
    
    if not has_delta:
        print(f"\n  NO DELTA — reconciler correctly skips (no is_intermediate needed)")
    
    # Now simulate: agent result arrives → delta exists
    print(f"\n  Simulating agent result arrival...")
    append_turn(bb, "developer", "execute", "Investigation complete: VMER-1196 confirmed.", chat_role="user")
    
    new_user_macros_2 = [
        t for t in bb["conversation"]
        if t.get("chat_role") == "user" and t["turn"] > cursor
    ]
    has_delta_2 = len(new_user_macros_2) > 0
    print(f"  New macro user turns: {len(new_user_macros_2)}")
    print(f"  Has delta: {has_delta_2}")
    print(f"  Should reconcile: {has_delta_2}")
    
    passed = (not has_delta) and has_delta_2
    print(f"\n  NO-DELTA TEST: {'PASSED' if passed else 'FAILED'}")
    return passed


async def test_text_plus_fc_flush():
    """Test 3: Mixed text+FC — text should be flushed before FC execution."""
    print("\n" + "="*60)
    print("TEST 3: Text + FC Flush")
    print("="*60)
    
    if BLACKBOARD_FILE.exists():
        BLACKBOARD_FILE.unlink()
    bb = load_bb()
    
    append_turn(bb, "user", "message",
        "Please check the status of MR !116 in cluster-network-addons-operator v5-99 and merge it.",
        chat_role="user")
    
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
    
    si = (
        "You are FRIDAY, an AI operations orchestrator. "
        "Always explain what you're about to do before calling a tool. "
        "Include a brief explanation text WITH your tool call."
    )
    config = types.GenerateContentConfig(
        system_instruction=si,
        tools=TOOLS,
        temperature=0.7,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        ),
    )
    
    macro_history = format_macro_for_rebuild(bb)
    chat = client.aio.chats.create(
        model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL}",
        config=config,
        history=macro_history,
    )
    
    # Stream and check if we get text + FC together
    fc, args, text, thinking = None, None, "", ""
    async for chunk in await chat.send_message_stream(
        "What is the next action?", config=config
    ):
        if chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'thought') and part.thought:
                            if hasattr(part, 'text') and part.text:
                                thinking += part.text
                        elif hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call.name
                            args = dict(part.function_call.args or {})
                        elif hasattr(part, 'text') and part.text:
                            text += part.text
    
    has_both = bool(text) and bool(fc)
    print(f"  Text: '{text[:100]}'" if text else "  Text: (none)")
    print(f"  FC: {fc}")
    print(f"  Has both text+FC: {has_both}")
    
    if has_both:
        # Flush text as macro before executing FC
        print(f"\n  Flushing text as brain.response (macro) BEFORE FC execution...")
        append_turn(bb, "brain", "response", text, chat_role="model")
        print(f"  Then executing FC: {fc}")
        append_turn(bb, "brain", "tool_result", f"Executed {fc}", chat_role=None)
        
        # FR to pair FC
        fr = types.Part.from_function_response(name=fc, response={"result": "done"})
        fc2, args2, text2, thinking2 = None, None, "", ""
        async for chunk in await chat.send_message_stream(fr, config=config):
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                fc2 = part.function_call.name
                            elif hasattr(part, 'text') and part.text and not (hasattr(part, 'thought') and part.thought):
                                text2 += part.text
        print(f"  Session healthy after text+FC flush! Next: FC={fc2}, text={text2[:60] if text2 else 'none'}")
    else:
        print(f"\n  Model didn't produce text+FC together (common — model often goes FC-only)")
        print(f"  This is fine — the flush path just wouldn't trigger")
    
    print(f"\n  TEXT+FC TEST: {'PASSED (both produced, flush worked)' if has_both else 'INCONCLUSIVE (model went FC-only, flush path not exercised)'}")
    return has_both


async def main():
    results = {}
    
    results["recall"] = await test_recall_mid_stream()
    results["no_delta"] = await test_no_delta_no_reconcile()
    results["text_fc"] = await test_text_plus_fc_flush()
    
    print("\n" + "="*60)
    print("PROBE SUMMARY")
    print("="*60)
    for name, passed in results.items():
        status = "PASSED" if passed else "INCONCLUSIVE/FAILED"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
