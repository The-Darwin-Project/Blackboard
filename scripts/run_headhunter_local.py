# BlackBoard/scripts/run_headhunter_local.py
# @ai-rules:
# 1. [Constraint]: Standalone script -- no Brain, no Redis write. Prints events to stdout.
# 2. [Pattern]: --dry-run skips LLM analysis, prints raw todo context.
# 3. [Pattern]: --collect-samples saves raw todos to probe-data/ for Step 3 prompt iteration.
"""
Run Headhunter locally against a real GitLab instance.

Validates: API connection, todo fetching, context gathering, LLM analysis, event structure.
Does NOT push events to Redis -- prints them to stdout for inspection.

Usage:
  GITLAB_HOST=gitlab.example.com \
  GITLAB_TOKEN_PATH=/path/to/token \
  GCP_PROJECT=my-project \
  python -m scripts.run_headhunter_local [--dry-run] [--limit 3] [--collect-samples]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EventEvidence

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("headhunter.local")


class StubBlackboard:
    """Minimal stub that captures create_event calls without Redis."""

    def __init__(self):
        self.events: list[dict] = []
        self._event_counter = 0

    async def create_event(self, source: str, service: str, reason: str, evidence) -> str:
        self._event_counter += 1
        eid = f"local-{self._event_counter:04d}"
        self.events.append({
            "id": eid,
            "source": source,
            "service": service,
            "reason": reason[:200],
            "evidence": evidence.model_dump() if hasattr(evidence, "model_dump") else str(evidence),
        })
        return eid

    async def get_active_events(self) -> list[str]:
        return []

    async def get_event(self, event_id: str):
        return None

    async def get_services(self) -> dict:
        return {}


async def run(args: argparse.Namespace) -> None:
    from src.agents.headhunter import Headhunter

    blackboard = StubBlackboard()
    hh = Headhunter(blackboard)

    logger.info(f"Connecting to GitLab: {hh._gitlab_host}")

    todos = await hh.poll_cycle()
    if not todos:
        logger.info("No actionable todos found.")
        return

    logger.info(f"Found {len(todos)} actionable todo(s)")

    if args.limit:
        todos = todos[: args.limit]

    for i, todo in enumerate(todos, 1):
        target = todo.get("target", {})
        project = todo.get("project", {})
        logger.info(
            f"[{i}/{len(todos)}] {todo['action_name']} on "
            f"!{target.get('iid')} in {project.get('path_with_namespace')}"
        )

        context = await hh.fetch_context(todo)

        if args.collect_samples:
            sample_dir = Path("probe-data/headhunter-samples")
            sample_dir.mkdir(parents=True, exist_ok=True)
            sample_file = sample_dir / f"todo_{todo['id']}.json"
            sample_file.write_text(json.dumps({"todo": todo, "context": context}, indent=2, default=str))
            logger.info(f"  Sample saved: {sample_file}")

        if args.dry_run:
            print(json.dumps(context, indent=2, default=str))
            continue

        plan_text, domain = await hh.analyze_and_plan(context)
        logger.info(f"  Domain: {domain}")

        evidence = EventEvidence(
            display_text=f"GitLab: {todo['action_name']} on !{target['iid']} in {project['path_with_namespace']}",
            source_type="headhunter",
            domain=domain,
            severity="info",
            gitlab_context={
                "todo_id": todo["id"],
                "action_name": todo["action_name"],
                "project_id": project["id"],
                "project_path": project["path_with_namespace"],
                "mr_iid": target["iid"],
                "mr_title": target.get("title", ""),
            },
        )
        try:
            evidence.model_validate(evidence.model_dump())
            logger.info("  EventEvidence: VALID")
        except Exception as e:
            logger.error(f"  EventEvidence: INVALID -- {e}")
            continue

        event_id = await hh.create_headhunter_event(todo, plan_text, domain)
        logger.info(f"  Event created: {event_id}")
        print(f"\n--- Event {event_id} ---")
        print(f"Plan:\n{plan_text[:500]}")
        print(f"Evidence:\n{json.dumps(evidence.model_dump(), indent=2, default=str)}")

    logger.info(f"\nTotal events created: {len(blackboard.events)}")
    for ev in blackboard.events:
        print(f"\n  {ev['id']}: [{ev['source']}] {ev['service']} -- {ev['reason']}")


def main():
    parser = argparse.ArgumentParser(description="Run Headhunter locally (no Redis)")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM analysis, print raw context")
    parser.add_argument("--limit", type=int, default=None, help="Max todos to process")
    parser.add_argument("--collect-samples", action="store_true", help="Save raw todos to probe-data/")
    args = parser.parse_args()

    if not os.getenv("GITLAB_HOST"):
        logger.error("GITLAB_HOST env var required")
        sys.exit(1)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
