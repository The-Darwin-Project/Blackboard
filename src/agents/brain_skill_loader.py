# BlackBoard/src/agents/brain_skill_loader.py
# @ai-rules:
# 1. [Constraint]: This module has ZERO dependency on Brain or any agent class. Testable in isolation.
#    Only coupling: models._resolve_phase (deferred import in build_skill_refs to avoid circular).
# 2. [Pattern]: Glob discovery at startup. All files cached in memory. Zero I/O per LLM call.
# 3. [Pattern]: YAML frontmatter parsed via yaml.safe_load between --- delimiters.
# 4. [Pattern]: Cross-skill dependencies resolved via BFS with cycle-safe seen set.
# 5. [Gotcha]: Dynamic template vars ({event.source}) resolved at resolve_dependencies call time, not at startup.
# 6. [Pattern]: _phase.yaml per folder declares thinking_level, temperature, priority for LLM param resolution.
# 7. [Pattern]: _resolve_bfs is the single BFS implementation. Both resolve_dependencies (list[str])
#    and resolve_dependencies_with_paths (list[tuple[str, str]]) delegate to it. Zero duplication.
# 8. [Pattern]: Semantic tag types resolved by get_tag_type(rel_path): frontmatter tag_type override
#    (validated against _VALID_TAG_TYPES allowlist) > _FOLDER_TAG_TYPE folder default > "skill".
# 9. [Pattern]: _SkillCorpus frozen dataclass holds all caches. Single-reference swap is GIL-safe.
#    Reload replaces self._corpus atomically -- no window of partial state.
# 10. [Pattern]: async discover_from_redis() reads HGETALL with sorted keys + corrupt JSON resilience.
#     Critical always/* corruption aborts swap (fail-closed). Non-critical phases skip with warning.
# 11. [Pattern]: TOOL_SKILL_MAP, PHASE_SKILL_MAP, build_skill_refs() own the tool→skill and
#     phase→skill mappings. Brain imports build_skill_refs and calls it for tool_result evidence.
#     Dedup via seen set prevents duplicate <skill id> tags when tool and phase map to the same skill.
"""
Filesystem-driven brain skill discovery, loading, and dependency resolution.

Skills are .md files organized in phase folders (e.g., always/, triage/, post-agent/).
Each file can declare YAML frontmatter with description, requires (dependencies), and tags.
Each folder can have a _phase.yaml declaring LLM parameters (thinking_level, temperature, priority).

Supports dual-source discovery: Redis (primary when available) with filesystem fallback.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from redis.asyncio import Redis

from src.skill_reconciler.constants import REDIS_KEY_CORPUS, REDIS_KEY_PHASE_CONFIG

logger = logging.getLogger(__name__)

_VALID_TAG_TYPES = frozenset({"rule", "skill", "protocol", "context", "navigation"})

_FOLDER_TAG_TYPE: dict[str, str] = {
    "always": "rule",
    "source": "rule",
    "context": "context",
    # "navigation" describes what the tag DOES (steers the LLM through decision graphs),
    # "domain" is where it LIVES (folder name). Intentional split: folder = content origin, tag = compliance signal.
    "domain": "navigation",
}


@dataclass(frozen=True)
class _SkillCorpus:
    """Immutable snapshot of all loaded skills. Single-reference swap is GIL-safe."""
    cache: dict[str, list[tuple[str, str, dict]]] = field(default_factory=dict)
    phase_meta: dict[str, dict] = field(default_factory=dict)
    tag_index: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    path_index: dict[str, tuple[str, dict]] = field(default_factory=dict)


class BrainSkillLoader:
    """Dual-source brain skill discovery and loading (Redis primary, filesystem fallback)."""

    def __init__(self, skills_dir: str, redis: "Redis | None" = None):
        self._skills_dir = Path(skills_dir)
        self._redis = redis
        self._corpus = _SkillCorpus()
        self._discover()

    def _discover(self) -> None:
        """Glob all skill folders at startup. Cache contents in memory."""
        if not self._skills_dir.is_dir():
            logger.warning(f"Brain skills directory not found: {self._skills_dir}")
            return

        cache: dict[str, list[tuple[str, str, dict]]] = {}
        phase_meta: dict[str, dict] = {}
        tag_index: dict[str, list[str]] = defaultdict(list)
        path_index: dict[str, tuple[str, dict]] = {}

        for phase_dir in sorted(self._skills_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            phase = phase_dir.name
            cache[phase] = []

            phase_yaml = phase_dir / "_phase.yaml"
            if phase_yaml.is_file():
                try:
                    phase_meta[phase] = yaml.safe_load(phase_yaml.read_text()) or {}
                except Exception as e:
                    logger.warning(f"Failed to parse {phase_yaml}: {e}")
                    phase_meta[phase] = {}

            for md_file in sorted(phase_dir.glob("*.md")):
                raw = md_file.read_text()
                body, meta = self._parse_frontmatter(raw)
                rel_path = f"{phase}/{md_file.name}"
                cache[phase].append((rel_path, body, meta))
                path_index[rel_path] = (body, meta)
                for tag in meta.get("tags", []):
                    tag_index[tag].append(rel_path)

        self._corpus = _SkillCorpus(
            cache=cache, phase_meta=phase_meta, tag_index=tag_index, path_index=path_index,
        )

        total_files = sum(len(v) for v in cache.values())
        total_tags = len(tag_index)
        logger.info(
            f"Brain skills loaded: {len(cache)} phases, "
            f"{total_files} files, {total_tags} tags"
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[str, dict]:
        """Parse YAML frontmatter from markdown. Returns (body, metadata)."""
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

    # ------------------------------------------------------------------
    # Async Redis discovery
    # ------------------------------------------------------------------

    async def discover_from_redis(self) -> bool:
        """Load skills from Redis HASHes. Returns True if valid data found.

        Sorted key ordering matches filesystem sorted() behavior.
        Corrupt JSON fields are skipped with warning. If any always/* skill
        fails parsing, the swap is aborted entirely (fail-closed).
        Both HGETALL calls use a pipeline (MULTI/EXEC) for atomic read.
        """
        if not self._redis:
            return False

        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.hgetall(REDIS_KEY_CORPUS)
            pipe.hgetall(REDIS_KEY_PHASE_CONFIG)
            raw_corpus, raw_phase = await pipe.execute()
        except Exception as e:
            logger.warning(f"Redis pipeline HGETALL failed during skill discovery: {e}")
            return False

        if not raw_corpus:
            return False

        cache: dict[str, list[tuple[str, str, dict]]] = {}
        phase_meta: dict[str, dict] = {}
        tag_index: dict[str, list[str]] = defaultdict(list)
        path_index: dict[str, tuple[str, dict]] = {}
        always_corrupt = False

        for key in sorted(raw_corpus.keys()):
            try:
                entry = json.loads(raw_corpus[key])
            except (json.JSONDecodeError, TypeError) as e:
                if key.startswith("always/"):
                    logger.error(f"Critical skill corrupt in Redis (aborting swap): {key}: {e}")
                    always_corrupt = True
                    break
                logger.warning(f"Skipping corrupt Redis skill field: {key}: {e}")
                continue

            body = entry.get("body", "")
            meta = entry.get("frontmatter", {})
            phase = key.split("/")[0]

            if phase not in cache:
                cache[phase] = []
            cache[phase].append((key, body, meta))
            path_index[key] = (body, meta)
            for tag in meta.get("tags", []):
                tag_index[tag].append(key)

        if always_corrupt:
            logger.error("Keeping previous corpus due to critical skill corruption")
            return False

        for phase_name in sorted(raw_phase.keys()):
            try:
                phase_meta[phase_name] = json.loads(raw_phase[phase_name])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Skipping corrupt phase config: {phase_name}: {e}")

        if "always" not in cache or not cache["always"]:
            logger.error("Redis corpus missing always/ phase -- aborting swap")
            return False

        self._corpus = _SkillCorpus(
            cache=cache, phase_meta=phase_meta, tag_index=tag_index, path_index=path_index,
        )
        total_files = sum(len(v) for v in cache.values())
        logger.info(f"Brain skills loaded from Redis: {len(cache)} phases, {total_files} files")
        return True

    async def reload_from_redis(self) -> bool:
        """Async reload from Redis. Falls back to filesystem if Redis has no data.

        Returns True if Redis data was loaded, False if fell back to filesystem.
        Brain uses this to decide whether to update _skills_version.
        """
        if await self.discover_from_redis():
            return True
        logger.info("Redis empty or invalid -- falling back to filesystem reload")
        self.reload()
        return False

    # ------------------------------------------------------------------
    # Getters (all read from self._corpus)
    # ------------------------------------------------------------------

    def get_phase(self, name: str) -> list[str]:
        """Return cached skill body contents for a phase."""
        return [body for _, body, _ in self._corpus.cache.get(name, [])]

    def get_with_meta(self, rel_path: str) -> tuple[str, dict] | None:
        """Return (content, frontmatter) for a specific skill by relative path.

        Returns a copy of the frontmatter dict to prevent callers from
        mutating the shared corpus cache.
        """
        entry = self._corpus.path_index.get(rel_path)
        if entry is None:
            return None
        body, meta = entry
        return (body, dict(meta))

    def get_phase_meta(self, name: str) -> dict:
        """Return _phase.yaml metadata for a phase (thinking_level, temperature, priority).

        Returns a copy to prevent callers from mutating the shared corpus cache.
        """
        return dict(self._corpus.phase_meta.get(name, {}))

    def get_tag_type(self, rel_path: str) -> str:
        """Return the semantic tag type for a skill path.

        Resolution order: frontmatter override (validated against allowlist) > folder default.
        """
        entry = self._corpus.path_index.get(rel_path)
        if entry:
            _, meta = entry
            if isinstance(meta, dict):
                override = meta.get("tag_type")
                if isinstance(override, str) and override in _VALID_TAG_TYPES:
                    return override
        folder = rel_path.split("/")[0]
        return _FOLDER_TAG_TYPE.get(folder, "skill")

    def get_all_paths_for_phase(self, name: str) -> list[str]:
        """Return list of relative paths in a phase."""
        return [rel for rel, _, _ in self._corpus.cache.get(name, [])]

    def find_by_tag(self, tag: str) -> list[str]:
        """Return skill body contents matching a tag."""
        results = []
        for rel_path in self._corpus.tag_index.get(tag, []):
            entry = self._corpus.path_index.get(rel_path)
            if entry:
                results.append(entry[0])
        return results

    def find_paths_by_tag(self, tag: str) -> list[str]:
        """Return relative paths matching a tag."""
        return list(self._corpus.tag_index.get(tag, []))

    def available_phases(self) -> list[str]:
        """Return list of discovered phase names."""
        return list(self._corpus.cache.keys())

    def list_skills_for_graph(self) -> list[dict[str, str]]:
        """Return graph-friendly skill metadata for the cognitive graph API."""
        return [
            {
                "id": f"skill:{rel_path}",
                "label": meta.get("description", rel_path.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ")),
                "phase_folder": rel_path.split("/", 1)[0] if "/" in rel_path else "",
                "tag_type": self.get_tag_type(rel_path),
            }
            for rel_path, (_body, meta) in self._corpus.path_index.items()
        ]

    def reload(self) -> None:
        """Re-discover from filesystem via atomic corpus swap."""
        self._discover()

    def _resolve_bfs(
        self,
        initial_paths: list[str],
        template_vars: dict[str, str] | None = None,
    ) -> list[tuple[str, str]]:
        """Core BFS dependency resolver. Returns (resolved_path, body) tuples."""
        resolved: list[tuple[str, str]] = []
        seen: set[str] = set()
        queue: list[str] = list(initial_paths)
        while queue:
            skill_path = queue.pop(0)
            if template_vars:
                for key, value in template_vars.items():
                    skill_path = skill_path.replace(f"{{{key}}}", value)
            if skill_path in seen:
                continue
            seen.add(skill_path)
            entry = self._corpus.path_index.get(skill_path)
            if not entry:
                logger.debug(f"Skill not found during dependency resolution: {skill_path}")
                continue
            body, meta = entry
            resolved.append((skill_path, body))
            for dep in meta.get("requires", []):
                if dep not in seen:
                    queue.append(dep)
        return resolved

    def resolve_dependencies(
        self,
        initial_paths: list[str],
        template_vars: dict[str, str] | None = None,
    ) -> list[str]:
        """Resolve cross-skill dependencies. Returns deduplicated, ordered skill contents.

        Transitive: if A requires B and B requires C, all three are loaded.
        Dynamic references: {event.source}, {event.service} resolved from template_vars.
        Cycle-safe: tracks seen paths to prevent infinite loops.
        """
        return [body for _, body in self._resolve_bfs(initial_paths, template_vars)]

    def resolve_dependencies_with_paths(
        self,
        initial_paths: list[str],
        template_vars: dict[str, str] | None = None,
    ) -> list[tuple[str, str]]:
        """Like resolve_dependencies, but returns (rel_path, body) tuples."""
        return self._resolve_bfs(initial_paths, template_vars)


TOOL_SKILL_MAP: dict[str, list[str]] = {
    "consult_deep_memory": ["always/04-deep-memory.md"],
    "classify_event": ["always/05-cynefin.md"],
    "set_phase": ["always/09-phase-lifecycle.md"],
    "defer_event": ["always/08-flow-engineering.md"],
    "select_agent": ["dispatch/decision-routing.md", "always/01-function-rules.md"],
    "wait_for_agent": ["always/12-actor-responses.md", "always/01-function-rules.md"],
    "close_event": ["close/when-to-close.md"],
    "report_incident": ["escalate/incident-tracking.md"],
    "refresh_gitlab_context": ["always/08-flow-engineering.md"],
    "refresh_kargo_context": ["always/08-flow-engineering.md"],
    "notify_user_slack": ["always/01-function-rules.md"],
    "reply_to_agent": ["always/12-actor-responses.md"],
    "message_agent": ["always/12-actor-responses.md"],
    "respond_to_jarvis": ["always/12-actor-responses.md"],
}

PHASE_SKILL_MAP: dict[str, str] = {
    "triage": "always/06-decision-guidelines.md",
    "dispatch": "dispatch/decision-routing.md",
    "verify": "always/03-control-theory.md",
    "escalate": "escalate/incident-tracking.md",
}


def build_skill_refs(
    tool_name: str,
    brain_phase: str | None = None,
    event_source: str | None = None,
) -> str:
    """Build skill pointer XML block for a tool_result turn.

    Returns newline-joined <skill id="..." /> tags for:
    - Tool-specific skills (what this tool relates to)
    - Phase-specific skill (what to do next in current phase)
    - Source-specific skill (event source behavioral context)
    Deduplicates when multiple layers map to the same skill.
    """
    from ..models import _resolve_phase  # noqa: deferred to avoid circular import

    refs: list[str] = []
    seen: set[str] = set()

    for skill in TOOL_SKILL_MAP.get(tool_name, []):
        if skill not in seen:
            refs.append(f'<skill id="{skill}" />')
            seen.add(skill)

    phase = _resolve_phase(brain_phase)
    phase_skill = PHASE_SKILL_MAP.get(phase, "always/06-decision-guidelines.md")
    if phase_skill not in seen:
        refs.append(f'<skill id="{phase_skill}" />')
        seen.add(phase_skill)

    if event_source:
        source_skill = f"source/{event_source}.md"
        if source_skill not in seen:
            refs.append(f'<skill id="{source_skill}" />')
            seen.add(source_skill)

    return "\n".join(refs)


