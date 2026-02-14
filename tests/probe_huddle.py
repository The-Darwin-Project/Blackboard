# BlackBoard/tests/probe_huddle.py
# @ai-rules:
# 1. [Constraint]: Standalone script -- no imports from BlackBoard src. Uses websockets + google-genai + stdlib.
# 2. [Pattern]: Podman containers share ./shared via bind mount. Bootstrap plan written before dispatch.
# 3. [Pattern]: Dev uses Claude Opus, QE uses Gemini Pro. Flash Manager (Gemini Flash) moderates.
# 4. [Pattern]: as_completed fires both CLIs, Flash reviews first finisher immediately, full review when both done.
# 5. [Pattern]: Flash Manager decides review rounds (max 2). Dev fix -> QE verify -> Flash final.
"""
Huddle Probe: Dev + QE pair with Flash Manager moderation.

Flow:
  1. Bootstrap: write shared plan
  2. Fire Dev + QE concurrently
  3. Flash reviews first finisher immediately
  4. Flash full review when both done
  5. Review rounds if needed (max 2)
  6. Report merged results

Usage:
    python tests/probe_huddle.py [--no-cleanup]

Requires:
    - podman installed
    - GCP service account key (for Vertex AI)
    - pip install websockets google-genai
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' required. Run: pip install websockets")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIDECAR_IMAGE = os.getenv(
    "SIDECAR_IMAGE", "localhost/gemini-sidecar-fixed:latest"
)
GCP_SA_KEY = os.getenv(
    "GCP_SA_KEY",
    "",  # Set GCP_SA_KEY env var to service account JSON path
)
GCP_PROJECT = os.getenv("GCP_PROJECT", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")

# Set credentials for google-genai SDK (Flash Manager runs in this process)
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", GCP_SA_KEY)

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("ERROR: 'google-genai' required. Run: pip install google-genai")
    sys.exit(1)

DEV_PORT = 9093
QE_PORT = 9094
DEV_NAME = "darwin-dev-probe"
QE_NAME = "darwin-qe-probe"
EVENT_ID = "probe-1"
FLASH_MODEL = "gemini-3-flash-preview"
MAX_REVIEW_ROUNDS = 2

PROBE_DIR = Path("./probe-data")

# ---------------------------------------------------------------------------
# QE rules (inline)
# ---------------------------------------------------------------------------
QE_RULES = """\
# Darwin QE Agent - CLI Context

You are the QE (Quality Engineering) agent in the Darwin autonomous system.
You work concurrently with the Developer as a pair.

## Your Role
- Independently assess quality for the same event the Developer is implementing
- Write comprehensive tests for the expected behavior
- Identify quality risks, test coverage gaps, and potential regressions
- Prepare verification criteria for the expected fix

## How You Work
1. Read the huddle plan file provided in your prompt for full context
2. Create tests in your working directory for the expected behavior
3. Check for common quality issues and edge cases
4. Define verification criteria: what should be true after a correct fix?
5. Write your findings to the shared notes file specified in the plan

## Pair Communication
- You work concurrently with a Developer agent
- Write your findings to your notes file (path in the huddle plan)
- Read the Developer's notes file to see their approach
- You are independently assessing the same problem from a QE perspective

## Rules
- Focus on writing tests and quality assessment
- Be concise and actionable
- If you find nothing notable, say so briefly

## Completion
Write your deliverable to ./results/findings.md with:
- Tests created (file paths)
- Quality risks identified
- Verification criteria
"""

# ---------------------------------------------------------------------------
# Dev rules (local probe -- no git push)
# ---------------------------------------------------------------------------
DEV_RULES = """\
# Darwin Developer Agent - CLI Context (Local Probe)

You are the Developer agent. You implement code changes.

## Your Role
Implement source code changes based on the task description.

## How You Work
1. Read the huddle plan file for full context
2. Create the requested files in your working directory
3. Write clean, production-ready code
4. Write your approach to the shared notes file

## Pair Communication
- You work concurrently with a QE agent
- Write your progress to your notes file (path in the huddle plan)
- Read the QE's findings file to see their quality assessment

## Rules
- Keep code simple and well-structured
- Do NOT attempt git operations (local test, no repo to push to)
- Focus on creating the files described in the task

## Completion
Write your deliverable to ./results/findings.md with:
- Files created (paths)
- Summary of implementation
"""

# ---------------------------------------------------------------------------
# Bootstrap plan
# ---------------------------------------------------------------------------
PLAN_TEMPLATE = """\
# Huddle: Event {event_id}

## Pair
- **Developer** (agent 1): Implement the solution
- **QE** (agent 2): Write tests and assess quality independently

## Task
Create a simple Python "Hello World" web app using Flask:
- app.py with / and /health endpoints
- requirements.txt with Flask dependency
- Proper error handling and production-ready structure

## Communication
You are working concurrently as a pair on the same task.
A shared directory is mounted at ./shared/{event_id}/ in your working directory.
- Developer: write your progress to ./shared/{event_id}/dev-notes.md
- QE: write your findings to ./shared/{event_id}/qe-notes.md
- Read your partner's file periodically to coordinate.
"""


# ---------------------------------------------------------------------------
# Flash Manager (Gemini Flash -- moderates the pair)
# ---------------------------------------------------------------------------
MANAGER_SYSTEM = """\
You are the Huddle Manager moderating a Developer + QE pair.
Review their outputs and decide the next action.

Respond with JSON only:
{
  "done": true/false,
  "dev_action": "none" | "fix" | "review",
  "qe_action": "none" | "verify" | "review",
  "dev_message": "instruction for dev (if action != none)",
  "qe_message": "instruction for qe (if action != none)",
  "summary": "one-line status"
}

Rules:
- If QE found real issues that Dev should address: dev_action="fix"
- If Dev made changes that QE should verify: qe_action="verify"
- If both outputs look good and complementary: done=true
- Keep messages concise and actionable -- they go directly to CLI agents.
- After round 2, force done=true with a merged summary.
- Do NOT wrap JSON in markdown code fences.
"""


async def flash_decide(dev_output: str, qe_output: str, round_num: int) -> dict:
    """Call Gemini Flash to review both outputs and decide next action."""
    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    prompt = (
        f"## Review Round {round_num}\n\n"
        f"## Developer Output\n{dev_output[:4000]}\n\n"
        f"## QE Output\n{qe_output[:4000]}\n\n"
        f"What should happen next?"
    )
    response = await client.aio.models.generate_content(
        model=FLASH_MODEL, contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=MANAGER_SYSTEM,
            temperature=0.7,
            max_output_tokens=65000,
        ),
    )
    text = response.text.strip()
    # Strip markdown code fences if model wraps JSON anyway
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [FLASH] Failed to parse JSON, raw: {text[:300]}")
        return {"done": True, "summary": f"Parse error. Raw: {text[:200]}",
                "dev_action": "none", "qe_action": "none"}


async def flash_note(agent: str, output: str) -> str:
    """Quick Flash note when first agent finishes. One-liner assessment."""
    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    prompt = (
        f"The {agent} agent just finished their task. "
        f"Give a one-sentence assessment of their output quality:\n\n"
        f"{output[:2000]}"
    )
    response = await client.aio.models.generate_content(
        model=FLASH_MODEL, contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.7, max_output_tokens=65000,
        ),
    )
    return response.text.strip()


# ---------------------------------------------------------------------------
# Container management
# ---------------------------------------------------------------------------
def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, print it, return result."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        if result.stderr:
            print(f"  STDERR: {result.stderr.strip()}")
        if check:
            result.check_returncode()
    return result


def cleanup_containers():
    """Stop and remove probe containers."""
    for name in (DEV_NAME, QE_NAME):
        run_cmd(["podman", "rm", "-f", name], check=False)


def start_containers():
    """Start dev and qe sidecar containers."""
    cleanup_containers()

    workspace = str(PROBE_DIR.resolve() / "workspace")
    dev_rules = str(PROBE_DIR.resolve() / "dev-rules.md")
    qe_rules = str(PROBE_DIR.resolve() / "qe-rules.md")

    common_env = [
        "-e", f"GOOGLE_CLOUD_PROJECT={GCP_PROJECT}",
        "-e", f"GOOGLE_CLOUD_LOCATION={GCP_LOCATION}",
        "-e", f"GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/sa.json",
    ]
    common_opts = ["--security-opt", "label=disable", "--userns=keep-id"]
    common_vols = [
        "-v", f"{GCP_SA_KEY}:/var/secrets/google/sa.json:ro",
    ]

    # Developer sidecar (Claude Opus)
    dev_cmd = [
        "podman", "run", "-d", "--name", DEV_NAME,
        "--network", "host", *common_opts,
        "-e", f"PORT={DEV_PORT}",
        "-e", "AGENT_CLI=claude",
        "-e", "AGENT_MODEL=claude-opus-4-6",
        "-e", "CLAUDE_CODE_USE_VERTEX=1",
        "-e", f"ANTHROPIC_VERTEX_PROJECT_ID={GCP_PROJECT}",
        "-e", f"CLOUD_ML_REGION={GCP_LOCATION}",
        "-e", "ANTHROPIC_MODEL=claude-opus-4-6",
        *common_env,
        *common_vols,
        "-v", f"{workspace}:/data/gitops-developer",
        "-v", f"{dev_rules}:/home/default/.claude/CLAUDE.md:ro",
        SIDECAR_IMAGE,
    ]

    # QE sidecar (Gemini Pro)
    qe_cmd = [
        "podman", "run", "-d", "--name", QE_NAME,
        "--network", "host", *common_opts,
        "-e", f"PORT={QE_PORT}",
        "-e", "AGENT_CLI=gemini",
        "-e", "AGENT_MODEL=gemini-3-pro-preview",
        "-e", "GOOGLE_GENAI_USE_VERTEXAI=true",
        "-e", "GEMINI_MODEL=gemini-3-pro-preview",
        *common_env,
        *common_vols,
        "-v", f"{workspace}:/data/gitops-qe",
        "-v", f"{qe_rules}:/home/default/.gemini/GEMINI.md:ro",
        SIDECAR_IMAGE,
    ]

    print("\n[1/7] Starting containers...")
    run_cmd(dev_cmd)
    run_cmd(qe_cmd)
    print("  Containers started.")


def wait_for_health(port: int, name: str, timeout: int = 60):
    """Wait for sidecar /health endpoint."""
    import urllib.request
    url = f"http://localhost:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    print(f"  {name} healthy: {data.get('cliType', '?')} / {data.get('cliModel', '?')}")
                    return True
        except Exception:
            pass
        time.sleep(2)
    print(f"  ERROR: {name} not healthy after {timeout}s")
    return False


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def setup_probe_dirs():
    """Create probe directories and write rules + bootstrap plan."""
    print("\n[2/7] Setting up probe directories...")

    # Prune old probe data (podman unshare handles UID-mapped files)
    if PROBE_DIR.exists():
        print("  Pruning old probe data...")
        subprocess.run(["podman", "unshare", "rm", "-rf", str(PROBE_DIR.resolve())],
                       capture_output=True, check=False)
        # Fallback if podman unshare fails
        if PROBE_DIR.exists():
            shutil.rmtree(PROBE_DIR, ignore_errors=True)

    # Single shared workspace -- both agents see same files (simulates same repo clone)
    for subdir in ("workspace", "workspace/results", "workspace/tests",
                    "workspace/shared", f"workspace/shared/{EVENT_ID}"):
        (PROBE_DIR / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ("workspace", "workspace/results", "workspace/tests",
                    "workspace/shared", f"workspace/shared/{EVENT_ID}"):
        os.chmod(PROBE_DIR / subdir, 0o777)

    (PROBE_DIR / "dev-rules.md").write_text(DEV_RULES)
    (PROBE_DIR / "qe-rules.md").write_text(QE_RULES)

    event_dir = PROBE_DIR / "workspace" / "shared" / EVENT_ID
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "plan.md").write_text(PLAN_TEMPLATE.format(event_id=EVENT_ID))
    print(f"  Bootstrap plan written to {event_dir / 'plan.md'}")


# ---------------------------------------------------------------------------
# WebSocket agent interaction
# ---------------------------------------------------------------------------
async def send_task_to_agent(
    port: int, label: str, event_id: str, prompt: str, cwd: str,
) -> str:
    """Connect to sidecar WS, send task, stream progress, return result."""
    url = f"ws://localhost:{port}/ws"
    print(f"\n  [{label}] Connecting to {url}...")

    async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
        await ws.send(json.dumps({
            "type": "task", "event_id": event_id,
            "prompt": prompt, "cwd": cwd, "autoApprove": True,
        }))
        print(f"  [{label}] Task sent ({len(prompt)} chars)")

        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "progress":
                text = msg.get("message", "")
                display = text[:120] + "..." if len(text) > 120 else text
                print(f"  [{label}] {display}")
            elif msg_type == "result":
                output = msg.get("output", "")
                print(f"  [{label}] DONE ({len(str(output))} chars)")
                return str(output)
            elif msg_type == "error":
                err = msg.get("message", "Unknown error")
                print(f"  [{label}] ERROR: {err}")
                return f"Error: {err}"
            elif msg_type == "busy":
                print(f"  [{label}] BUSY -- agent occupied")
                return "Error: agent busy"

    return "Error: WebSocket closed without result"


# ---------------------------------------------------------------------------
# Huddle orchestration (as_completed + Flash review rounds)
# ---------------------------------------------------------------------------
async def run_huddle():
    """Full huddle: fire both, Flash reviews as results arrive, review rounds."""
    shared_rel = f"./shared/{EVENT_ID}"

    dev_prompt = (
        f"Read the huddle plan at {shared_rel}/plan.md. You are the Developer.\n\n"
        f"Create a simple Python Flask hello world app in your working directory:\n"
        f"- app.py with / and /health endpoints\n"
        f"- requirements.txt with Flask\n"
        f"- Proper error handling\n\n"
        f"Write your approach and progress to {shared_rel}/dev-notes.md.\n"
        f"Read your QE partner's findings at {shared_rel}/qe-notes.md "
        f"periodically -- they may flag risks relevant to your implementation."
    )

    qe_prompt = (
        f"Read the huddle plan at {shared_rel}/plan.md. You are the QE.\n\n"
        f"Independently write comprehensive pytest tests for a Flask hello world app:\n"
        f"- test_app.py testing / and /health endpoints\n"
        f"- Check for edge cases and error handling\n"
        f"- Define verification criteria\n\n"
        f"Write your findings to {shared_rel}/qe-notes.md.\n"
        f"Read the Developer's progress at {shared_rel}/dev-notes.md "
        f"periodically -- their approach may inform your test design."
    )

    # ---- Phase 1: Fire both, collect as they arrive ----
    print("\n[4a/7] Firing Dev + QE concurrently...")
    dev_task = asyncio.create_task(
        send_task_to_agent(DEV_PORT, "DEV", EVENT_ID, dev_prompt, "/data/gitops-developer")
    )
    qe_task = asyncio.create_task(
        send_task_to_agent(QE_PORT, "QE", EVENT_ID, qe_prompt, "/data/gitops-qe")
    )

    dev_result = None
    qe_result = None

    # Wait for first finisher
    done, pending = await asyncio.wait(
        [dev_task, qe_task], return_when=asyncio.FIRST_COMPLETED,
    )
    for task in done:
        result = task.result() if not task.cancelled() else "Error: cancelled"
        if isinstance(result, Exception):
            result = f"Error: {result}"
        if task is dev_task:
            dev_result = str(result)
            first_agent = "Developer"
        else:
            qe_result = str(result)
            first_agent = "QE"

    # Flash quick note on first finisher
    print(f"\n  [FLASH] {first_agent} finished first. Quick review...")
    first_output = dev_result if dev_result else qe_result
    note = await flash_note(first_agent, first_output)
    print(f"  [FLASH] {note}")

    # Wait for second finisher
    print(f"\n  Waiting for {'QE' if first_agent == 'Developer' else 'Developer'}...")
    for task in pending:
        result = await task
        if isinstance(result, Exception):
            result = f"Error: {result}"
        if task is dev_task:
            dev_result = str(result)
        else:
            qe_result = str(result)

    # ---- Phase 2: Flash full review + review rounds ----
    print("\n[4b/7] Both done. Flash Manager full review...")
    for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
        decision = await flash_decide(dev_result, qe_result, round_num)
        summary = decision.get("summary", "")
        dev_act = decision.get("dev_action", "none")
        qe_act = decision.get("qe_action", "none")
        print(f"\n  [FLASH R{round_num}] {summary}")
        print(f"    dev_action={dev_act}  qe_action={qe_act}")

        if decision.get("done", False):
            print(f"  [FLASH] Huddle complete.")
            break

        # Follow-up: Dev fix/review
        if dev_act in ("fix", "review"):
            msg = decision.get("dev_message", "Review QE findings and fix issues.")
            print(f"\n  [FLASH -> DEV] {msg[:150]}")
            dev_result = await send_task_to_agent(
                DEV_PORT, f"DEV-R{round_num}", EVENT_ID,
                f"Your QE partner has feedback:\n\n{msg}\n\n"
                f"Read their notes at {shared_rel}/qe-notes.md. "
                f"Address the issues and update {shared_rel}/dev-notes.md.",
                "/data/gitops-developer",
            )

        # Follow-up: QE verify/review
        if qe_act in ("verify", "review"):
            msg = decision.get("qe_message", "Verify the Developer's changes.")
            print(f"\n  [FLASH -> QE] {msg[:150]}")
            qe_result = await send_task_to_agent(
                QE_PORT, f"QE-R{round_num}", EVENT_ID,
                f"The Developer has updated their work:\n\n{msg}\n\n"
                f"Read their notes at {shared_rel}/dev-notes.md. "
                f"Verify and update {shared_rel}/qe-notes.md.",
                "/data/gitops-qe",
            )
    else:
        # Max rounds reached -- force final
        print(f"\n  [FLASH] Max review rounds ({MAX_REVIEW_ROUNDS}) reached. Finalizing.")

    return str(dev_result or ""), str(qe_result or "")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def print_report(dev_result: str, qe_result: str):
    """Print merged results and shared filesystem contents."""
    print("\n" + "=" * 70)
    print("HUDDLE PROBE RESULTS")
    print("=" * 70)

    print("\n--- Developer Result ---")
    print(dev_result[:3000] if len(dev_result) > 3000 else dev_result)

    print("\n--- QE Assessment ---")
    print(qe_result[:3000] if len(qe_result) > 3000 else qe_result)

    # Check shared notes
    print("\n--- Shared Notes ---")
    shared_dir = PROBE_DIR / "workspace" / "shared" / EVENT_ID
    if shared_dir.exists():
        for f in sorted(shared_dir.iterdir()):
            if f.is_file():
                print(f"\n  [{f.name}] ({f.stat().st_size} bytes)")
                content = f.read_text()
                print("  " + content[:500].replace("\n", "\n  "))
                if len(content) > 500:
                    print("  ... (truncated)")

    # Check shared workspace (both agents' files)
    print("\n--- Shared Workspace ---")
    ws_dir = PROBE_DIR / "workspace"
    if ws_dir.exists():
        for f in sorted(ws_dir.rglob("*")):
            if f.is_file() and ".git" not in str(f) and ".pytest_cache" not in str(f):
                print(f"  {f.relative_to(ws_dir)} ({f.stat().st_size} bytes)")

    print("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Huddle Probe: Dev + QE + Flash Manager")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep containers after test")
    args = parser.parse_args()

    if not Path(GCP_SA_KEY).exists():
        print(f"ERROR: GCP SA key not found: {GCP_SA_KEY}")
        sys.exit(1)

    print("=" * 70)
    print("HUDDLE PROBE: Dev + QE Pair + Flash Manager")
    print("=" * 70)
    print(f"  Image:    {SIDECAR_IMAGE}")
    print(f"  SA Key:   {GCP_SA_KEY}")
    print(f"  Project:  {GCP_PROJECT}")
    print(f"  Dev:      localhost:{DEV_PORT} (Claude Opus)")
    print(f"  QE:       localhost:{QE_PORT} (Gemini Pro)")
    print(f"  Manager:  Gemini Flash (in-process)")

    try:
        setup_probe_dirs()
        start_containers()

        print("\n[3/7] Waiting for containers to be healthy...")
        dev_ok = wait_for_health(DEV_PORT, "Developer")
        qe_ok = wait_for_health(QE_PORT, "QE")
        if not (dev_ok and qe_ok):
            print("ERROR: Containers not healthy.")
            subprocess.run(["podman", "logs", DEV_NAME], check=False)
            subprocess.run(["podman", "logs", QE_NAME], check=False)
            sys.exit(1)

        dev_result, qe_result = asyncio.run(run_huddle())

        print("\n[5/7] Collecting results...")
        print_report(dev_result, qe_result)

    finally:
        if args.no_cleanup:
            print("\n[6/7] Skipping cleanup (--no-cleanup).")
            print(f"  Inspect: ls -la {PROBE_DIR}/workspace/shared/{EVENT_ID}/")
            print(f"  Dev logs: podman logs {DEV_NAME}")
            print(f"  QE logs:  podman logs {QE_NAME}")
        else:
            print("\n[6/7] Cleaning up...")
            cleanup_containers()
            print("  Containers removed. Probe data at: ./probe-data/")

    print("\n[7/7] Done.")


if __name__ == "__main__":
    main()
