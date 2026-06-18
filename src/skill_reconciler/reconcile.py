# BlackBoard/src/skill_reconciler/reconcile.py
# @ai-rules:
# 1. [Constraint]: ZERO imports from Brain, agents, or any async code. Standalone sync module.
# 2. [Pattern]: Git Trees API polling with SHA-based change detection. Fetch tree only on commit change.
# 3. [Pattern]: Redis MULTI/EXEC pipeline for atomic writes. Version key SET last within pipeline.
# 4. [Pattern]: Full-replace with HKEYS diff for deletion handling (stale key cleanup).
# 5. [Gotcha]: GitHubAppAuth imported from utils/github_app.py -- self-contained, zero Brain deps.
# 6. [Constraint]: All config via env vars. No hardcoded hostnames, tokens, or paths.
"""
Git-to-Redis skill reconciler sidecar.

Polls a Git repo's tree via API, writes skill files to Redis HASHes,
and bumps a version key. Brain reads from Redis with filesystem fallback.

Run as: python src/skill_reconciler/reconcile.py
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure the app root (/app) is on sys.path for src.* imports
_app_root = str(Path(__file__).resolve().parent.parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import httpx
import redis
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skill_reconciler")

from src.skill_reconciler.constants import (
    REDIS_KEY_CORPUS, REDIS_KEY_PHASE_CONFIG, REDIS_KEY_SYNC_STATE, REDIS_KEY_VERSION,
)

POLL_INTERVAL = int(os.getenv("SKILL_RECONCILER_POLL_INTERVAL", "60"))
GIT_PROVIDER = os.getenv("SKILL_RECONCILER_GIT_PROVIDER", "github")
REPO = os.getenv("SKILL_RECONCILER_REPO", "")
BRANCH = os.getenv("SKILL_RECONCILER_BRANCH", "main")
SKILLS_PATH = os.getenv("SKILL_RECONCILER_SKILLS_PATH", "src/agents/brain_skills")


def _build_redis_client() -> redis.Redis:
    """Build sync Redis client using keyword args (no URL string -- avoids password leak in crash logs)."""
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD", "") or None
    return redis.Redis(host=host, port=port, password=password, db=0, decode_responses=True, socket_timeout=30)


_github_auth = None


def _get_github_headers() -> dict[str, str]:
    global _github_auth
    if _github_auth is None:
        from src.utils.github_app import GitHubAppAuth
        _github_auth = GitHubAppAuth()
    token = _github_auth.get_token()
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_gitlab_headers() -> dict[str, str]:
    token_path = os.getenv("GITLAB_TOKEN_PATH", "/secrets/gitlab/token")
    try:
        with open(token_path) as f:
            token = f.read().strip()
    except FileNotFoundError:
        token = os.getenv("GITLAB_TOKEN", "")
    return {"PRIVATE-TOKEN": token}


def _fetch_commit_sha(client: httpx.Client) -> str | None:
    """Fetch the latest commit SHA for the configured branch."""
    if GIT_PROVIDER == "github":
        url = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
        headers = _get_github_headers()
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["sha"]
    else:
        host = os.getenv("GITLAB_HOST", "")
        encoded_repo = REPO.replace("/", "%2F")
        url = f"https://{host}/api/v4/projects/{encoded_repo}/repository/commits/{BRANCH}"
        resp = client.get(url, headers=_get_gitlab_headers())
        resp.raise_for_status()
        return resp.json()["id"]


def _fetch_tree(client: httpx.Client) -> list[dict]:
    """Fetch the recursive git tree for the skills path."""
    if GIT_PROVIDER == "github":
        url = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
        resp = client.get(url, headers=_get_github_headers())
        resp.raise_for_status()
        tree = resp.json().get("tree", [])
        return [
            e for e in tree
            if e["path"].startswith(f"{SKILLS_PATH}/") and e["type"] == "blob"
        ]
    else:
        host = os.getenv("GITLAB_HOST", "")
        encoded_repo = REPO.replace("/", "%2F")
        url = f"https://{host}/api/v4/projects/{encoded_repo}/repository/tree"
        params: dict[str, str] = {"ref": BRANCH, "path": SKILLS_PATH, "recursive": "true", "per_page": "100"}
        all_entries: list[dict] = []
        page = 1
        while True:
            params["page"] = str(page)
            resp = client.get(url, headers=_get_gitlab_headers(), params=params)
            resp.raise_for_status()
            entries = resp.json()
            all_entries.extend(e for e in entries if e["type"] == "blob")
            if len(entries) < 100:
                break
            page += 1
        return all_entries


def _fetch_file_content(client: httpx.Client, path: str) -> str:
    """Fetch raw file content from the repo."""
    if GIT_PROVIDER == "github":
        url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}"
        headers = {**_get_github_headers(), "Accept": "application/vnd.github.raw+json"}
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text
    else:
        host = os.getenv("GITLAB_HOST", "")
        encoded_repo = REPO.replace("/", "%2F")
        encoded_path = path.replace("/", "%2F")
        url = f"https://{host}/api/v4/projects/{encoded_repo}/repository/files/{encoded_path}/raw"
        resp = client.get(url, headers=_get_gitlab_headers(), params={"ref": BRANCH})
        resp.raise_for_status()
        return resp.text


def _parse_frontmatter(text: str) -> tuple[str, dict]:
    """Parse YAML frontmatter. Mirrors BrainSkillLoader._parse_frontmatter."""
    if not text.startswith("---"):
        return text, {}
    end = text.find("---", 3)
    if end == -1:
        return text, {}
    try:
        meta = yaml.safe_load(text[3:end]) or {}
    except Exception:
        meta = {}
    body = text[end + 3:].strip()
    return body, meta


def _reconcile(rdb: redis.Redis, http: httpx.Client, last_sha: str | None) -> str | None:
    """Single reconciliation cycle. Returns new SHA on change, None on no-op."""
    commit_sha = _fetch_commit_sha(http)
    if not commit_sha:
        return last_sha

    if commit_sha == last_sha:
        logger.debug("No change (SHA=%s)", commit_sha[:8])
        return last_sha

    logger.info("Change detected: %s -> %s", (last_sha or "init")[:8], commit_sha[:8])
    tree = _fetch_tree(http)

    corpus: dict[str, str] = {}
    phase_config: dict[str, str] = {}
    prefix_len = len(SKILLS_PATH) + 1

    for entry in tree:
        full_path = entry.get("path", entry.get("name", ""))
        if not full_path:
            continue
        rel_path = full_path[prefix_len:] if full_path.startswith(f"{SKILLS_PATH}/") else full_path

        if not (rel_path.endswith(".md") or rel_path.endswith("_phase.yaml")):
            continue

        content = _fetch_file_content(http, full_path if GIT_PROVIDER == "github" else full_path)
        blob_sha = entry.get("sha", entry.get("id", ""))

        if rel_path.endswith("_phase.yaml"):
            phase_name = rel_path.split("/")[0]
            phase_config[phase_name] = json.dumps(yaml.safe_load(content) or {}, default=str)
        else:
            body, meta = _parse_frontmatter(content)
            corpus[rel_path] = json.dumps({"body": body, "frontmatter": meta, "blob_sha": blob_sha}, default=str)

    # Atomic write via MULTI/EXEC pipeline
    existing_corpus_keys = set(rdb.hkeys(REDIS_KEY_CORPUS))
    existing_phase_keys = set(rdb.hkeys(REDIS_KEY_PHASE_CONFIG))
    new_corpus_keys = set(corpus.keys())
    new_phase_keys = set(phase_config.keys())

    pipe = rdb.pipeline(transaction=True)

    if corpus:
        pipe.hset(REDIS_KEY_CORPUS, mapping=corpus)
    for stale_key in existing_corpus_keys - new_corpus_keys:
        pipe.hdel(REDIS_KEY_CORPUS, stale_key)

    if phase_config:
        pipe.hset(REDIS_KEY_PHASE_CONFIG, mapping=phase_config)
    for stale_key in existing_phase_keys - new_phase_keys:
        pipe.hdel(REDIS_KEY_PHASE_CONFIG, stale_key)

    pipe.hset(REDIS_KEY_SYNC_STATE, mapping={
        "last_success_at": datetime.now(timezone.utc).isoformat(),
        "last_error": "",
        "file_count": str(len(corpus)),
        "source_sha": commit_sha,
    })

    pipe.set(REDIS_KEY_VERSION, commit_sha)
    pipe.execute()

    logger.info("Reconciled %d skills, %d phase configs (SHA=%s)", len(corpus), len(phase_config), commit_sha[:8])
    return commit_sha


def main() -> None:
    if not REPO:
        logger.error("SKILL_RECONCILER_REPO not set. Exiting.")
        sys.exit(1)

    rdb = _build_redis_client()
    logger.info("Skill reconciler starting (provider=%s, repo=%s, branch=%s, interval=%ds)", GIT_PROVIDER, REPO, BRANCH, POLL_INTERVAL)

    last_sha: str | None = None
    backoff = 0

    while True:
        try:
            # H6 fix: detect Redis flush -- if version key disappeared, reset in-memory SHA
            try:
                redis_version = rdb.get(REDIS_KEY_VERSION)
                if redis_version is None and last_sha is not None:
                    logger.warning("Redis version key missing (flush?). Resetting for full re-sync.")
                    last_sha = None
            except Exception:
                pass

            with httpx.Client(timeout=30) as http:
                last_sha = _reconcile(rdb, http, last_sha)
            backoff = 0
        except Exception as e:
            backoff = min(backoff + 1, 8)
            jitter = random.uniform(0, min(2 ** backoff, 300))
            try:
                rdb.hset(REDIS_KEY_SYNC_STATE, "last_error", type(e).__name__)
            except Exception:
                pass
            logger.warning("Reconcile failed (backoff=%.0fs): %s", 2 ** backoff + jitter, e)
            time.sleep(min(2 ** backoff + jitter, 300))
            continue

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
