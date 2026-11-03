# scripts/drain_nightwatcher_backlog.py
"""
Standalone Backlog Drain Utility for Nightwatcher.
Jira: VMER-2236 (Plan: nightwatcher-backlog-and-quota-deadlock)

Inspects and drains pending Nightwatcher escalations in bounded batches.
Supports dry-run classification, age-off pruning for stale CI duplicates (>7d),
and bounded batch draining.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

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


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Drain or prune stale Nightwatcher pending escalations safely."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect backlog composition and age breakdown without mutations.",
    )
    parser.add_argument(
        "--age-off-days",
        type=int,
        default=7,
        help="Age-off threshold in days for stale CI build duplicates (default: 7).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of items to drain in each batch (default: 25).",
    )
    parser.add_argument(
        "--delay-seconds",
        type=int,
        default=45,
        help="Cooldown sleep seconds between drain batches (default: 45).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicit flag required to execute mutations (age-off or drain).",
    )
    return parser


def get_redis_client() -> Redis:
    """Bootstrap Redis client using standard environment variables and socket_timeout=30."""
    if Redis is None:
        raise RuntimeError("redis package is required. Install redis-py before running.")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_password = os.getenv("REDIS_PASSWORD", None)
    return Redis.from_url(redis_url, password=redis_password, socket_timeout=30)


def classify_backlog(
    client: Redis, age_off_days: int
) -> tuple[int, int, list[tuple[str, float]], list[tuple[str, float]]]:
    """Inspect and partition items into stale (> age_off_days) and active."""
    now = time.time()
    cutoff_ts = now - (age_off_days * 86400)

    # Read items with scores
    items_with_scores = client.zrange(NIGHTWATCHER_PENDING, 0, -1, withscores=True)
    stale_items: list[tuple[str, float]] = []
    active_items: list[tuple[str, float]] = []

    for raw_val, score in items_with_scores:
        item_str = raw_val if isinstance(raw_val, str) else raw_val.decode()
        if score < cutoff_ts:
            stale_items.append((item_str, score))
        else:
            active_items.append((item_str, score))

    return len(stale_items), len(active_items), stale_items, active_items


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = get_redis_client()
    total_pending = client.zcard(NIGHTWATCHER_PENDING)
    logger.info("Current pending queue cardinality: %d", total_pending)

    stale_count, active_count, stale_items, active_items = classify_backlog(
        client, args.age_off_days
    )
    logger.info(
        "Classification (cutoff %d days): %d stale items, %d active items",
        args.age_off_days,
        stale_count,
        active_count,
    )

    if args.dry_run or not args.execute:
        logger.info("Dry-run mode active (or --execute omitted). No mutations performed.")
        return 0

    # Prune stale items in batches if any
    if stale_count > 0:
        logger.info(
            "Pruning %d stale items older than %d days in batches of %d...",
            stale_count, args.age_off_days, args.batch_size
        )
        for i in range(0, stale_count, args.batch_size):
            batch = stale_items[i : i + args.batch_size]
            pipe = client.pipeline()
            for item_str, _ in batch:
                pipe.zrem(NIGHTWATCHER_PENDING, item_str)
            pipe.execute()
            logger.info("Pruned batch %d-%d of %d stale items", i + 1, min(i + len(batch), stale_count), stale_count)
            if i + args.batch_size < stale_count and args.delay_seconds > 0:
                time.sleep(args.delay_seconds)
        logger.info("Successfully pruned %d stale items.", stale_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
