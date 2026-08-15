# probes/parallel_fc_behavior_probe.py
# @ai-rules:
# 1. [Purpose]: Map Gemini's parallel FC behavior with FRIDAY's real tools/SI.
# 2. [Constraint]: Uses google-genai SDK. No code changes to brain.py — observation only.
# 3. [Pattern]: Collects 50 samples across varied prompts, reports statistics.
# 4. [Output]: JSON summary + console report of parallel FC patterns.

"""
Parallel FC Behavior Probe (Cynefin Complex — safe-to-fail experiment)

Answers:
1. What % of responses have >1 functionCall?
2. In what ORDER does the model emit parallel FCs?
3. Which tool combinations appear together?
4. Does classify_event always come before select_agent?
5. How does thought_signature distribute across parallel FCs?

Run:
    GOOGLE_APPLICATION_CREDENTIALS=../cnv-ai-insights-8502f29094a2.json \
    GCP_PROJECT=cnv-ai-insights GCP_LOCATION=global \
    python probes/parallel_fc_behavior_probe.py
"""

import asyncio
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from google import genai
from google.genai import types


MODELS = [
    "gemini-3.1-pro-preview-customtools",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
]

SYSTEM_INSTRUCTION = """You are FRIDAY, an autonomous AI operations orchestrator.
You manage events via function calling. Rules:
1. ALWAYS classify events before dispatching agents (call classify_event first).
2. After classification, dispatch the appropriate agent via select_agent.
3. For simple user messages, respond and park with wait_for_user.
4. Use thinking to reason through triage decisions.
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
                    "reasoning": types.Schema(type="STRING"),
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
                    "reasoning": types.Schema(type="STRING"),
                    "task_summary": types.Schema(type="STRING"),
                },
                required=["agent_role", "reasoning", "task_summary"],
            ),
        ),
        types.FunctionDeclaration(
            name="wait_for_user",
            description="Park the conversation and wait for the next user message.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reason": types.Schema(type="STRING"),
                },
                required=["reason"],
            ),
        ),
        types.FunctionDeclaration(
            name="consult_deep_memory",
            description="Search archived event history for relevant patterns.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING"),
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
                    "seconds": types.Schema(type="INTEGER"),
                    "reason": types.Schema(type="STRING"),
                },
                required=["seconds", "reason"],
            ),
        ),
    ])
]

PROMPTS = [
    "[USER]: The ArgoCD sync on darwin-blackboard has been failing for 20 minutes. Please investigate.",
    "[USER]: Build pipeline OOM on PR #200. Pod killed at 3.8GB. Get someone to fix it.",
    "[USER]: Security scan found a critical CVE in our base image. Need immediate assessment.",
    "[USER]: The nightly batch job hasn't completed. It's been running for 6 hours (normally takes 2).",
    "[USER]: MR !350 needs a code review. It touches the authentication layer.",
    "[USER]: Production latency spike — P99 went from 200ms to 3s in the last 10 minutes.",
    "[USER]: Can you check if there are any pending MRs that need my attention?",
    "[USER]: The developer agent reported back that the fix is ready. Can you verify it?",
    "[USER]: We need to roll back the last deployment. Users are seeing 500 errors.",
    "[USER]: Investigate why the Tekton pipeline is stuck in pending state for trigger-job.",
]


@dataclass
class FCObservation:
    model: str
    prompt_idx: int
    fc_count: int
    fc_names: list[str]
    fc_order: list[str]
    has_text_before_fc: bool
    signatures: dict[str, bool]  # fc_name → has_signature
    latency_ms: float
    error: str = ""


async def observe_single(client: genai.Client, model: str, prompt: str, prompt_idx: int) -> FCObservation:
    """Make one API call and observe the FC pattern."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        temperature=0.8,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model, contents=contents, config=config,
        )
        latency = (time.perf_counter() - start) * 1000
    except Exception as e:
        return FCObservation(
            model=model, prompt_idx=prompt_idx, fc_count=0,
            fc_names=[], fc_order=[], has_text_before_fc=False,
            signatures={}, latency_ms=(time.perf_counter() - start) * 1000,
            error=str(e)[:200],
        )

    fc_names = []
    fc_order = []
    signatures = {}
    has_text_before_fc = False
    saw_fc = False

    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text and not getattr(part, "thought", False):
            if not saw_fc:
                has_text_before_fc = True
        if hasattr(part, "function_call") and part.function_call:
            saw_fc = True
            name = part.function_call.name
            fc_names.append(name)
            fc_order.append(name)
            sig = getattr(part, "thought_signature", None) or getattr(part, "thoughtSignature", None)
            signatures[name] = sig is not None and len(sig) > 0

    return FCObservation(
        model=model,
        prompt_idx=prompt_idx,
        fc_count=len(fc_names),
        fc_names=fc_names,
        fc_order=fc_order,
        has_text_before_fc=has_text_before_fc,
        signatures=signatures,
        latency_ms=latency,
    )


async def run_probe():
    """Run the full probe: 50 observations across models and prompts."""
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "")),
        location=os.environ.get("GCP_LOCATION", "global"),
    )

    print("=" * 80)
    print("PARALLEL FC BEHAVIOR PROBE")
    print("Cynefin Complex — safe-to-fail observation experiment")
    print("=" * 80)
    print(f"\nModels: {', '.join(MODELS)}")
    print(f"Prompts: {len(PROMPTS)} scenarios")
    print(f"Target: ~{len(MODELS) * len(PROMPTS)} observations\n")

    all_obs: list[FCObservation] = []

    for model in MODELS:
        print(f"\n{'━' * 70}")
        print(f"MODEL: {model}")
        print(f"{'━' * 70}")

        # Run all prompts for this model concurrently (batch of 5 for rate limiting)
        for batch_start in range(0, len(PROMPTS), 5):
            batch = PROMPTS[batch_start:batch_start + 5]
            tasks = [
                observe_single(client, model, prompt, batch_start + i)
                for i, prompt in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks)
            all_obs.extend(results)

            for obs in results:
                if obs.error:
                    print(f"  [{obs.prompt_idx}] ERROR: {obs.error[:80]}")
                else:
                    fc_str = " → ".join(obs.fc_order) if obs.fc_order else "(no FC)"
                    sig_str = ", ".join(f"{k}:{'SIG' if v else 'no-sig'}" for k, v in obs.signatures.items())
                    parallel = "PARALLEL" if obs.fc_count > 1 else "single"
                    print(f"  [{obs.prompt_idx}] {parallel} ({obs.fc_count} FC): {fc_str} | {sig_str} | {obs.latency_ms:.0f}ms")

    # === ANALYSIS ===
    print(f"\n\n{'=' * 80}")
    print("ANALYSIS")
    print(f"{'=' * 80}")

    for model in MODELS:
        model_obs = [o for o in all_obs if o.model == model and not o.error]
        if not model_obs:
            continue

        print(f"\n--- {model} ({len(model_obs)} observations) ---")

        # Q1: Parallel FC frequency
        parallel = [o for o in model_obs if o.fc_count > 1]
        single = [o for o in model_obs if o.fc_count == 1]
        no_fc = [o for o in model_obs if o.fc_count == 0]
        print(f"\n  Q1: Parallel FC frequency")
        print(f"    Single FC: {len(single)} ({100*len(single)//len(model_obs)}%)")
        print(f"    Parallel FC (>1): {len(parallel)} ({100*len(parallel)//len(model_obs)}%)")
        print(f"    No FC: {len(no_fc)} ({100*len(no_fc)//len(model_obs)}%)")

        # Q2: Emission order for parallel FCs
        print(f"\n  Q2: Parallel FC emission order")
        order_counter: Counter = Counter()
        for o in parallel:
            order_counter[tuple(o.fc_order)] += 1
        for order, count in order_counter.most_common(10):
            print(f"    {' → '.join(order)}: {count}x")

        # Q3: Tool combinations
        print(f"\n  Q3: Tool combinations in parallel")
        combo_counter: Counter = Counter()
        for o in parallel:
            combo_counter[frozenset(o.fc_names)] += 1
        for combo, count in combo_counter.most_common(10):
            print(f"    {{{', '.join(sorted(combo))}}}:  {count}x")

        # Q4: Gate ordering (classify before select_agent)
        print(f"\n  Q4: Gate ordering (classify before select_agent in parallel)")
        both = [o for o in parallel if "classify_event" in o.fc_names and "select_agent" in o.fc_names]
        correct_order = [o for o in both if o.fc_order.index("classify_event") < o.fc_order.index("select_agent")]
        wrong_order = [o for o in both if o.fc_order.index("classify_event") > o.fc_order.index("select_agent")]
        print(f"    Both present: {len(both)}")
        print(f"    Correct (classify first): {len(correct_order)}")
        print(f"    WRONG (select_agent first): {len(wrong_order)}")
        if wrong_order:
            print(f"    ⚠️  MODEL DOES NOT ALWAYS RESPECT GATE ORDER")

        # Q5: Signature distribution
        print(f"\n  Q5: Thought signature distribution")
        for o in parallel:
            sig_summary = {name: "SIG" if has else "NO-SIG" for name, has in o.signatures.items()}
            print(f"    {' → '.join(o.fc_order)}: {sig_summary}")

        # Text before FC
        text_first = [o for o in model_obs if o.has_text_before_fc and o.fc_count > 0]
        print(f"\n  Text before FC: {len(text_first)}/{len([o for o in model_obs if o.fc_count > 0])} "
              f"({100*len(text_first)//max(1,len([o for o in model_obs if o.fc_count > 0]))}%)")

    # === SUMMARY ===
    print(f"\n\n{'=' * 80}")
    print("SUMMARY — KEY FINDINGS FOR PLAN DESIGN")
    print(f"{'=' * 80}")

    total_parallel = sum(1 for o in all_obs if o.fc_count > 1 and not o.error)
    total_valid = sum(1 for o in all_obs if not o.error)
    print(f"\n  Total observations: {total_valid}")
    print(f"  Parallel FC rate: {total_parallel}/{total_valid} ({100*total_parallel//max(1,total_valid)}%)")

    gate_violations = sum(1 for o in all_obs if o.fc_count > 1 and not o.error
                         and "classify_event" in o.fc_names and "select_agent" in o.fc_names
                         and o.fc_order.index("classify_event") > o.fc_order.index("select_agent"))
    print(f"  Gate order violations: {gate_violations}")

    # Save JSON
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": MODELS,
        "total_observations": total_valid,
        "parallel_fc_rate": total_parallel / max(1, total_valid),
        "gate_violations": gate_violations,
        "observations": [
            {
                "model": o.model, "prompt_idx": o.prompt_idx,
                "fc_count": o.fc_count, "fc_order": o.fc_order,
                "signatures": o.signatures, "has_text_before_fc": o.has_text_before_fc,
                "latency_ms": o.latency_ms, "error": o.error,
            }
            for o in all_obs
        ],
    }
    out_path = "probes/parallel_fc_probe_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {out_path}")
    print(f"\n{'=' * 80}")
    print("PROBE COMPLETE — Use results to design parallel FC execution plan")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(run_probe())
