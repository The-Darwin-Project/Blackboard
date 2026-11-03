# scripts/drain_nightwatcher_backlog.py
# @ai-rules:
# 1. [Constraint]: Mutations require an explicit --execute. Default and --dry-run are read-only.
# 2. [Constraint]: Every pruned member is appended to a JSONL backup BEFORE ZREM (deletion is otherwise irreversible).
# 3. [Constraint]: Targets the same Redis the app uses: REDIS_URL wins, else REDIS_HOST/REDIS_PORT/REDIS_PASSWORD. The target host is always logged.
# 4. [Gotcha]: This script only AGES OFF stale members. It does NOT drain the live backlog -- the Nightwatcher sweep does that
#    (NIGHTWATCHER_BATCH_SIZE x NIGHTWATCHER_MAX_BATCHES per sweep).
"""
Standalone backlog age-off utility for Nightwatcher.
Jira: VMER-2236 (Plan: nightwatcher-backlog-and-quota-deadlock)

Inspects the pending ZSET and, with --execute, removes members older than
--age-off-days in bounded batches. It filters on age only (plus a priority guard:
Critical items are kept unless --include-critical), so review the --dry-run output
first. Removed members are written to a JSONL backup file before deletion.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from urllib.parse import urlparse

try:
    from redis import Redis
except ImportError:
    Redis = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("drain_nightwatcher_backlog")

NIGHTWATCHER_PENDING = "darwin:nightwatcher:pending"
NIGHTWATCHER_INFLIGHT = "darwin:nightwatcher:inflight"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}")
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {parsed}")
    return parsed


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}")
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {parsed}")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Inspect and age off stale Nightwatcher pending escalations safely."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect backlog composition and age breakdown without mutations (default without --execute).",
    )
    parser.add_argument(
        "--age-off-days",
        type=_positive_int,
        default=7,
        help="Remove pending items older than this many days (must be > 0, default: 7).",
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=25,
        help="Number of items to remove per batch (must be > 0, default: 25).",
    )
    parser.add_argument(
        "--delay-seconds",
        type=_non_negative_int,
        default=45,
        help="Cooldown sleep seconds between removal batches (default: 45).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicit flag required to execute mutations.",
    )
    parser.add_argument(
        "--backup-file",
        default=None,
        help="JSONL file receiving every removed member before deletion "
             "(default: ./nightwatcher-pruned-<unix-ts>.jsonl).",
    )
    parser.add_argument(
        "--include-critical",
        action="store_true",
        help="Also remove stale items with priority Critical (kept by default).",
    )
    return parser


def _redis_target() -> str:
    """Human-readable Redis target (no credentials) for logging."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        parsed = urlparse(redis_url)
        return f"{parsed.hostname or 'localhost'}:{parsed.port or 6379} (REDIS_URL)"
    return f"{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')} (REDIS_HOST/REDIS_PORT)"


def get_redis_client() -> Redis:
    """Bootstrap Redis client: REDIS_URL if set, else REDIS_HOST/REDIS_PORT like the app. socket_timeout=30."""
    if Redis is None:
        raise RuntimeError("redis package is required. Install redis-py before running.")
    redis_password = os.getenv("REDIS_PASSWORD") or None
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return Redis.from_url(redis_url, password=redis_password, socket_timeout=30)
    try:
        port = int(os.getenv("REDIS_PORT", "6379"))
    except ValueError:
        raise RuntimeError(f"Invalid REDIS_PORT={os.getenv('REDIS_PORT')!r}")
    return Redis(
        host=os.getenv("REDIS_HOST", "localhost"), port=port,
        password=redis_password, socket_timeout=30,
    )


def _priority_of(item_str: str) -> str:
    try:
        return str(json.loads(item_str).get("priority", ""))
    except Exception:
        return ""


def classify_backlog(
    client: Redis, age_off_days: int, protect_critical: bool = False
) -> tuple[int, int, list[tuple[str, float]], list[tuple[str, float]]]:
    """Partition items into stale (older than age_off_days) and active.

    With protect_critical, stale items whose priority is Critical are classified active (kept).
    """
    now = time.time()
    cutoff_ts = now - (age_off_days * 86400)

    items_with_scores = client.zrange(NIGHTWATCHER_PENDING, 0, -1, withscores=True)
    stale_items: list[tuple[str, float]] = []
    active_items: list[tuple[str, float]] = []

    for raw_val, score in items_with_scores:
        item_str = raw_val if isinstance(raw_val, str) else raw_val.decode()
        if score < cutoff_ts and not (protect_critical and _priority_of(item_str) == "Critical"):
            stale_items.append((item_str, score))
        else:
            active_items.append((item_str, score))

    return len(stale_items), len(active_items), stale_items, active_items


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger.info("Redis target: %s", _redis_target())
    client = get_redis_client()
    total_pending = client.zcard(NIGHTWATCHER_PENDING)
    logger.info("Current pending queue cardinality: %d", total_pending)

    stale_count, active_count, stale_items, active_items = classify_backlog(
        client, args.age_off_days, protect_critical=not args.include_critical
    )
    logger.info(
        "Classification (cutoff %d days, critical %s): %d stale items, %d kept",
        args.age_off_days,
        "included" if args.include_critical else "protected",
        stale_count,
        active_count,
    )

    if args.dry_run or not args.execute:
        logger.info("Dry-run mode active (or --execute omitted). No mutations performed.")
        return 0

    if stale_count > 0:
        backup_path = args.backup_file or f"nightwatcher-pruned-{int(time.time())}.jsonl"
        logger.info(
            "Pruning %d stale items older than %d days in batches of %d (backup: %s)...",
            stale_count, args.age_off_days, args.batch_size, backup_path,
        )
        with open(backup_path, "a", encoding="utf-8") as backup:
            for i in range(0, stale_count, args.batch_size):
                batch = stale_items[i : i + args.batch_size]
                for item_str, score in batch:
                    backup.write(json.dumps({"score": score, "member": item_str}) + "\n")
                backup.flush()
                os.fsync(backup.fileno())
                pipe = client.pipeline()
                for item_str, _ in batch:
                    pipe.zrem(NIGHTWATCHER_PENDING, item_str)
                pipe.execute()
                logger.info("Pruned batch %d-%d of %d stale items", i + 1, min(i + len(batch), stale_count), stale_count)
                if i + args.batch_size < stale_count and args.delay_seconds > 0:
                    time.sleep(args.delay_seconds)
        logger.info("Successfully pruned %d stale items (backup: %s).", stale_count, backup_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
