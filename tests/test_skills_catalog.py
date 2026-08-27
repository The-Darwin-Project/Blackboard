# tests/test_skills_catalog.py
# @ai-rules:
# 1. [Purpose]: Tests the skills_catalog.py helper (Step 12 observer ZIP fix).
# 2. [Constraint]: No network calls. Uses in-memory ZIP archives built with zipfile stdlib.
# 3. [Pattern]: Tests assert against the planned public interface:
#    download_skill_md(content: bytes, slug: str) -> str | None
# 4. [Gotcha]: Implementation runs in parallel — tests may need adjustment at reconciliation.
"""
T-C1: Observer ZIP fix — skills_catalog.py download_skill_md helper.

Validates that ZIP binary content is properly extracted to SKILL.md text,
replacing the broken resp.text[:10000] on binary ZIP data.
"""
from __future__ import annotations

import io
import zipfile

import pytest


def _make_skill_zip(slug: str, skill_md_content: str,
                    extra_files: dict[str, str] | None = None) -> bytes:
    """Build an in-memory ZIP archive matching the catalog download format.

    Archive structure: {slug}/SKILL.md (+ optional extra files).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}/SKILL.md", skill_md_content)
        if extra_files:
            for path, content in extra_files.items():
                zf.writestr(f"{slug}/{path}", content)
    return buf.getvalue()


def _make_corrupt_zip() -> bytes:
    """Return bytes that are not a valid ZIP archive."""
    return b"PK\x03\x04this-is-not-a-real-zip-just-starts-with-pk-magic"


def _make_empty_zip() -> bytes:
    """Return a valid but empty ZIP archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        pass
    return buf.getvalue()


# =========================================================================
# T-C1: download_skill_md extracts SKILL.md text, not binary garbage
# =========================================================================

class TestTC1DownloadSkillMd:
    """T-C1: Observer ZIP fix. download_skill_md must return the text content
    of {slug}/SKILL.md from a ZIP archive, not binary garbage."""

    def test_valid_zip_returns_skill_md_text(self):
        """Happy path: ZIP with {slug}/SKILL.md → utf-8 text."""
        from src.skills_catalog import download_skill_md

        content = "---\ndescription: Test skill\n---\n# My Skill\n\nThis is the skill body."
        zip_bytes = _make_skill_zip("cnv-gating-workflow", content)

        result = download_skill_md(zip_bytes, "cnv-gating-workflow")

        assert result is not None
        assert result == content
        assert "# My Skill" in result
        assert "binary" not in result.lower() or "binary" in content.lower()

    def test_result_is_text_not_binary(self):
        """The result must be a str (decoded UTF-8), not bytes."""
        from src.skills_catalog import download_skill_md

        zip_bytes = _make_skill_zip("test-slug", "Hello World")
        result = download_skill_md(zip_bytes, "test-slug")

        assert isinstance(result, str), "Result must be str, not bytes"

    def test_missing_skill_md_returns_none(self):
        """ZIP without {slug}/SKILL.md → None."""
        from src.skills_catalog import download_skill_md

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("wrong-slug/SKILL.md", "content")
        zip_bytes = buf.getvalue()

        result = download_skill_md(zip_bytes, "expected-slug")
        assert result is None

    def test_empty_zip_returns_none(self):
        """Empty ZIP archive → None."""
        from src.skills_catalog import download_skill_md

        result = download_skill_md(_make_empty_zip(), "any-slug")
        assert result is None

    def test_corrupt_zip_raises_or_returns_none(self):
        """Corrupt ZIP data must not crash — either raises BadZipFile or returns None."""
        from src.skills_catalog import download_skill_md

        try:
            result = download_skill_md(_make_corrupt_zip(), "any-slug")
            assert result is None
        except zipfile.BadZipFile:
            pass  # Also acceptable — caller wraps in try/except per Step 12

    def test_unicode_content_preserved(self):
        """UTF-8 content with non-ASCII characters preserved correctly."""
        from src.skills_catalog import download_skill_md

        content = "# Gating Workflow — résumé of changes\n\nDüsseldorf → München"
        zip_bytes = _make_skill_zip("unicode-test", content)

        result = download_skill_md(zip_bytes, "unicode-test")
        assert result == content

    def test_large_skill_md_extracted(self):
        """Real catalog skills can be 10-15KB. Extraction must handle full content."""
        from src.skills_catalog import download_skill_md

        content = "# Large Skill\n\n" + ("x" * 15000)
        zip_bytes = _make_skill_zip("large-skill", content)

        result = download_skill_md(zip_bytes, "large-skill")
        assert result is not None
        assert len(result) == len(content)

    def test_zip_with_extra_files_only_returns_skill_md(self):
        """ZIP with references/ and scripts/ alongside SKILL.md — only SKILL.md returned."""
        from src.skills_catalog import download_skill_md

        skill_content = "# My Skill"
        zip_bytes = _make_skill_zip("multi-file", skill_content, extra_files={
            "references/arch.md": "architecture notes",
            "scripts/run.sh": "#!/bin/bash\necho hello",
        })

        result = download_skill_md(zip_bytes, "multi-file")
        assert result == skill_content
        assert "architecture notes" not in result
