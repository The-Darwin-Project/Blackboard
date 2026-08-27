# BlackBoard/src/skills_catalog.py
# @ai-rules:
# 1. [Constraint]: stdlib + httpx ONLY. No src.agents imports (hexagonal boundary).
# 2. [Pattern]: Extracts SKILL.md from catalog ZIP downloads. Used by jenkins_observer.
# 3. [Gotcha]: Catalog download returns application/zip, not text. resp.text is binary garbage.
"""Shared helpers for the DevOps Skills Catalog ZIP downloads."""
from __future__ import annotations

import io
import zipfile


def download_skill_md(content: bytes, slug: str) -> str | None:
    """Extract SKILL.md text from a catalog ZIP download.

    The catalog API returns a ZIP archive where the SKILL.md lives at
    ``{slug}/SKILL.md``. Returns the decoded text, or None if the
    expected path is not found in the archive.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return None
    skill_path = f"{slug}/SKILL.md"
    if skill_path in zf.namelist():
        return zf.read(skill_path).decode("utf-8")
    return None
