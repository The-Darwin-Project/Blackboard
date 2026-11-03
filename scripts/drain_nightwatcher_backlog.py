# scripts/drain_nightwatcher_backlog.py
# @ai-rules:
# 1. [Constraint]: Mutations require an explicit --execute. Default and --dry-run are read-only.
# 2. [Constraint]: Every pruned member is appended to a JSONL backup (created 0o600) and fsynced BEFORE ZREM (deletion is otherwise irreversible).
# 3. [Constraint]: Memory/Redis work is bounded: ZRANGEBYSCORE ... LIMIT offset batch_size windows; never load the whole ZSET.
# 4. [Constraint]: Targets the same Redis the app uses: REDIS_URL wins, else REDIS_HOST/REDIS_PORT/REDIS_PASSWORD. The target host is always logged.
# 5. [Gotcha]: This script only AGES OFF stale members. It does NOT drain the live backlog -- the Nightwatcher sweep does that
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


def _open_backup(path: str):
    """Open the JSONL backup append-only with owner-only (0o600) permissions.

    The payloads contain service names, summaries and descriptions, so the file must not be
    group/world readable regardless of umask (mode only applies on creation; fchmod covers reuse).
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    return os.fdopen(fd, "a", encoding="utf-8")


def prune_stale(
    client: Redis,
    age_off_days: int,
    batch_size: int,
    protect_critical: bool = True,
    execute: bool = False,
    delay_seconds: int = 0,
    backup_path: str | None = None,
) -> tuple[int, int]:
    """Walk stale members (score < now - age_off_days) in bounded windows of batch_size.

    Memory and Redis work per call are O(batch_size): ZRANGEBYSCORE ... LIMIT offset batch_size,
    never the whole ZSET. Protected (Critical) members stay in the range, so the window offset
    advances past them; removed members shift the range down, so the offset does not advance for
    them. With execute=True each window is appended to the backup (fsynced) BEFORE its ZREM.
    Returns (stale_removed_or_would_remove, protected_kept).
    """
    cutoff_ts = time.time() - (age_off_days * 86400)
    max_score = f"({cutoff_ts}"  # exclusive upper bound: score < cutoff
    offset = 0
    removable = 0
    protected = 0
    backup = _open_backup(backup_path) if (execute and backup_path) else None
    try:
        while True:
            window = client.zrangebyscore(
                NIGHTWATCHER_PENDING, "-inf", max_score, start=offset, num=batch_size, withscores=True
            )
            if not window:
                break
            to_remove: list[tuple[str, float]] = []
            for raw_val, score in window:
                item_str = raw_val if isinstance(raw_val, str) else raw_val.decode()
                if protect_critical and _priority_of(item_str) == "Critical":
                    protected += 1
                else:
                    to_remove.append((item_str, score))
            removable += len(to_remove)
            kept = len(window) - len(to_remove)
            if not execute:
                offset += len(window)          # read-only scan: nothing shifts
            else:
                if to_remove:
                    for item_str, score in to_remove:
                        backup.write(json.dumps({"score": score, "member": item_str}) + "\n")
                    backup.flush()
                    os.fsync(backup.fileno())
                    pipe = client.pipeline()
                    for item_str, _ in to_remove:
                        pipe.zrem(NIGHTWATCHER_PENDING, item_str)
                    pipe.execute()
                    logger.info("Pruned %d stale items (total %d)", len(to_remove), removable)
                offset += kept
                if len(window) == batch_size and delay_seconds > 0:
                    time.sleep(delay_seconds)
            if len(window) < batch_size:
                break
    finally:
        if backup is not None:
            backup.close()
    return removable, protected


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger.info("Redis target: %s", _redis_target())
    client = get_redis_client()
    total_pending = client.zcard(NIGHTWATCHER_PENDING)
    logger.info("Current pending queue cardinality: %d", total_pending)

    execute = bool(args.execute) and not args.dry_run
    backup_path = None
    if execute:
        backup_path = args.backup_file or f"nightwatcher-pruned-{int(time.time())}.jsonl"
        logger.info("Pruning items older than %d days in windows of %d (backup: %s)...",
                    args.age_off_days, args.batch_size, backup_path)
    else:
        logger.info("Dry-run mode active (or --execute omitted). No mutations performed.")

    removable, protected = prune_stale(
        client, args.age_off_days, args.batch_size,
        protect_critical=not args.include_critical,
        execute=execute, delay_seconds=args.delay_seconds, backup_path=backup_path,
    )
    logger.info(
        "%s %d stale items older than %d days; %d stale Critical items %s; %d items remain",
        "Pruned" if execute else "Would prune", removable, args.age_off_days,
        protected, "included" if args.include_critical else "protected",
        total_pending - (removable if execute else 0),
    )
    if execute and removable:
        logger.info("Backup written to %s", backup_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
