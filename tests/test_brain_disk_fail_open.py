# tests/test_brain_disk_fail_open.py
"""Tests fail-open resilience of Brain volume writes when PVC is missing or read-only."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.agents.brain import Brain, VOLUME_PATHS


@pytest.fixture
def mock_brain():
    """Create minimal Brain instance with mocked dependencies for volume writing."""
    brain = Brain.__new__(Brain)
    brain.blackboard = AsyncMock()
    mock_event = MagicMock()
    mock_event.service = "release-service"
    brain.blackboard.get_event = AsyncMock(return_value=mock_event)
    brain.blackboard.get_service = AsyncMock(return_value={"tier": "tier-1"})
    brain._event_to_markdown = MagicMock(return_value="# Test Event Markdown")
    return brain


@pytest.mark.asyncio
async def test_write_event_to_volume_mkdir_oserror_fail_open(mock_brain, tmp_path):
    """Verifies that OSError on mkdir (e.g. unmounted PVC) is logged and does not crash."""
    with patch.dict(VOLUME_PATHS, {"architect": str(tmp_path / "gitops-architect")}):
        with patch("pathlib.Path.mkdir", side_effect=OSError("Read-only file system / PVC unmounted")):
            with patch("src.agents.brain.logger.warning") as mock_warning:
                # Should not raise exception
                await mock_brain.write_event_to_volume("evt-fail-100", "architect")
                mock_warning.assert_called_once()
                assert "Failed to write event document %s" in mock_warning.call_args[0][0]
                assert mock_warning.call_args[0][1] == "evt-fail-100"


@pytest.mark.asyncio
async def test_write_event_to_volume_skips_unmounted_legacy_gitops_path(mock_brain, tmp_path):
    """Legacy /data/gitops-<role> paths are not created when the volume is not mounted."""
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        await mock_brain.write_event_to_volume("evt-skip-400", "architect")
        mock_mkdir.assert_not_called()


@pytest.mark.asyncio
async def test_write_event_to_volume_write_text_oserror_fail_open(mock_brain, tmp_path):
    """Verifies that OSError on write_text is logged and does not crash."""
    with patch.dict(VOLUME_PATHS, {"architect": str(tmp_path / "gitops-architect")}):
        with patch("pathlib.Path.write_text", side_effect=OSError("Disk quota exceeded")):
            with patch("src.agents.brain.logger.warning") as mock_warning:
                await mock_brain.write_event_to_volume("evt-fail-200", "architect")
                mock_warning.assert_called_once()
                assert "Failed to write event document %s" in mock_warning.call_args[0][0]
                assert mock_warning.call_args[0][1] == "evt-fail-200"


@pytest.mark.asyncio
async def test_write_event_to_volume_success(mock_brain, tmp_path):
    """Verifies successful write when volume path exists and is writable."""
    target_vol = tmp_path / "gitops-dev"
    with patch.dict(VOLUME_PATHS, {"developer": str(target_vol)}):
        await mock_brain.write_event_to_volume("evt-ok-300", "developer")
        out_file = target_vol / "events" / "event-evt-ok-300.md"
        assert out_file.exists()
        assert out_file.read_text() == "# Test Event Markdown"
