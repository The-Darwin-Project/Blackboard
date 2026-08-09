# scripts/migrate_obs_pipe_separator.py
"""One-time migration: rewrite colon-separated observation ZSET members to pipe-separated.

Run via: oc exec -n darwin $POD -c brain -- python3 scripts/migrate_obs_pipe_separator.py

Safe to re-run (idempotent — skips members already containing '|').
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate():
    import redis.asyncio as aioredis

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    password = os.getenv("REDIS_PASSWORD", "")
    r = aioredis.from_url(url, password=password, decode_responses=True)

    index_key = "darwin:obs:_index"
    prefix = "darwin:obs:"

    names = await r.smembers(index_key)
    print(f"Migrating {len(names)} observation series...")

    total_migrated = 0
    total_skipped = 0

    for name in sorted(names):
        key = f"{prefix}{name}"
        members = await r.zrange(key, 0, -1, withscores=True)

        pipe = r.pipeline(transaction=False)
        migrated_in_key = 0

        for member, score in members:
            if "|" in member:
                total_skipped += 1
                continue

            # Parse old colon format using rsplit(":", 5)
            segs = member.rsplit(":", 5)
            if len(segs) == 6:
                ts, val, unit, phase, eid, svc = segs
                new_member = f"{ts}|{val}|{unit}|{phase}|{eid}|{svc}|"
            elif len(segs) >= 4:
                segs4 = member.rsplit(":", 3)
                ts, val, unit, phase = segs4
                new_member = f"{ts}|{val}|{unit}|{phase}|||"
            else:
                total_skipped += 1
                continue

            pipe.zrem(key, member)
            pipe.zadd(key, {new_member: score})
            migrated_in_key += 1

        if migrated_in_key > 0:
            await pipe.execute()
            total_migrated += migrated_in_key
            print(f"  {name}: {migrated_in_key} members migrated")

    await r.aclose()
    print(f"\nDone. Migrated: {total_migrated}, Skipped (already pipe): {total_skipped}")


if __name__ == "__main__":
    asyncio.run(migrate())
