# BlackBoard/src/agents/brain_skill_loader.py
# @ai-rules:
# 1. [Constraint]: This module has ZERO dependency on Brain or any agent class. Testable in isolation.
# 2. [Pattern]: Glob discovery at startup. All files cached in memory. Zero I/O per LLM call.
# 3. [Pattern]: YAML frontmatter parsed via yaml.safe_load between --- delimiters.
# 4. [Pattern]: Cross-skill dependencies resolved via BFS with cycle-safe seen set.
# 5. [Gotcha]: Dynamic template vars ({event.source}) resolved at resolve_dependencies call time, not at startup.
# 6. [Pattern]: _phase.yaml per folder declares thinking_level, temperature, priority for LLM param resolution.
"""
Filesystem-driven brain skill discovery, loading, and dependency resolution.

Skills are .md files organized in phase folders (e.g., always/, triage/, post-agent/).
Each file can declare YAML frontmatter with description, requires (dependencies), and tags.
Each folder can have a _phase.yaml declaring LLM parameters (thinking_level, temperature, priority).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class BrainSkillLoader:
    """Filesystem-driven brain skill discovery and loading."""

    def __init__(self, skills_dir: str):
        self._skills_dir = Path(skills_dir)
        # phase -> [(rel_path, body_content, frontmatter_dict)]
        self._cache: dict[str, list[tuple[str, str, dict]]] = {}
        self._phase_meta: dict[str, dict] = {}
        self._tag_index: dict[str, list[str]] = defaultdict(list)
        # rel_path -> (body, frontmatter) for O(1) lookup in dependency resolution
        self._path_index: dict[str, tuple[str, dict]] = {}
        self._discover()

    def _discover(self) -> None:
        """Glob all skill folders at startup. Cache contents in memory."""
        if not self._skills_dir.is_dir():
            logger.warning(f"Brain skills directory not found: {self._skills_dir}")
            return

        for phase_dir in sorted(self._skills_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            phase = phase_dir.name
            self._cache[phase] = []

            phase_yaml = phase_dir / "_phase.yaml"
            if phase_yaml.is_file():
                try:
                    self._phase_meta[phase] = yaml.safe_load(phase_yaml.read_text()) or {}
                except Exception as e:
                    logger.warning(f"Failed to parse {phase_yaml}: {e}")
                    self._phase_meta[phase] = {}

            for md_file in sorted(phase_dir.glob("*.md")):
                raw = md_file.read_text()
                body, meta = self._parse_frontmatter(raw)
                rel_path = f"{phase}/{md_file.name}"
                self._cache[phase].append((rel_path, body, meta))
                self._path_index[rel_path] = (body, meta)
                for tag in meta.get("tags", []):
                    self._tag_index[tag].append(rel_path)

        total_files = sum(len(v) for v in self._cache.values())
        total_tags = len(self._tag_index)
        logger.info(
            f"Brain skills loaded: {len(self._cache)} phases, "
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

    def get_phase(self, name: str) -> list[str]:
        """Return cached skill body contents for a phase."""
        return [body for _, body, _ in self._cache.get(name, [])]

    def get_with_meta(self, rel_path: str) -> tuple[str, dict] | None:
        """Return (content, frontmatter) for a specific skill by relative path."""
        return self._path_index.get(rel_path)

    def get_phase_meta(self, name: str) -> dict:
        """Return _phase.yaml metadata for a phase (thinking_level, temperature, priority)."""
        return self._phase_meta.get(name, {})

    def get_all_paths_for_phase(self, name: str) -> list[str]:
        """Return list of relative paths in a phase."""
        return [rel for rel, _, _ in self._cache.get(name, [])]

    def find_by_tag(self, tag: str) -> list[str]:
        """Return skill body contents matching a tag."""
        results = []
        for rel_path in self._tag_index.get(tag, []):
            entry = self._path_index.get(rel_path)
            if entry:
                results.append(entry[0])
        return results

    def find_paths_by_tag(self, tag: str) -> list[str]:
        """Return relative paths matching a tag."""
        return list(self._tag_index.get(tag, []))

    def available_phases(self) -> list[str]:
        """Return list of discovered phase names."""
        return list(self._cache.keys())

    def reload(self) -> None:
        """Clear caches and re-discover (e.g., on SIGHUP or ConfigMap update)."""
        self._cache.clear()
        self._phase_meta.clear()
        self._tag_index.clear()
        self._path_index.clear()
        self._discover()

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
        resolved: list[str] = []
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
            entry = self._path_index.get(skill_path)
            if not entry:
                logger.debug(f"Skill not found during dependency resolution: {skill_path}")
                continue
            body, meta = entry
            resolved.append(body)
            for dep in meta.get("requires", []):
                if dep not in seen:
                    queue.append(dep)

        return resolved
