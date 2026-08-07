# tests/test_observations_reporter.py
# @ai-rules:
# 1. [Pattern]: Direct unit tests for _render_chart_svg — no stubbing, exercises real matplotlib rendering.
# 2. [Constraint]: No live Redis/LLM needed; this module only tests the pure chart-rendering function.
"""Unit tests for the observations report chart renderer."""
from __future__ import annotations

import base64
import concurrent.futures

from src.reports.observations_reporter import _render_chart_svg


def _make_series(name: str = "error_count", trend: str = "rising", n: int = 10) -> dict:
    return {
        "name": name,
        "trend": trend,
        "unit": "count",
        "points": [{"epoch": i, "value": float(i * 2)} for i in range(n)],
    }


class TestRenderChartSvg:
    def test_renders_valid_base64_svg(self):
        """Real rendering produces a non-empty, decodable SVG payload."""
        result = _render_chart_svg(_make_series())
        assert result
        decoded = base64.b64decode(result).decode()
        assert decoded.startswith("<?xml")
        assert "<svg" in decoded

    def test_empty_points_returns_empty_string(self):
        """No points → the empty-points guard short-circuits before touching matplotlib."""
        series = {"name": "no_data", "trend": "stable", "unit": "", "points": []}
        assert _render_chart_svg(series) == ""

    def test_each_trend_color_renders(self):
        """All three known trend states render without error."""
        for trend in ("rising", "falling", "stable"):
            result = _render_chart_svg(_make_series(trend=trend))
            assert result
            assert base64.b64decode(result).decode().startswith("<?xml")

    def test_unknown_trend_falls_back_to_default_color(self):
        """An unrecognized trend value still renders (falls back to the default color)."""
        result = _render_chart_svg(_make_series(trend="unknown"))
        assert result

    def test_series_name_embedded_in_svg_title(self):
        """The series name is used as the chart title."""
        result = _render_chart_svg(_make_series(name="pipeline_duration_m"))
        decoded = base64.b64decode(result).decode()
        assert "pipeline_duration_m" in decoded

    def test_concurrent_rendering_is_thread_safe(self):
        """Rendering many charts concurrently across threads must not corrupt or
        cross-contaminate any individual chart's output (regression test for the
        stateful-pyplot thread-safety bug — Figure objects are created independently
        per call, so no shared global figure-manager state is touched)."""
        series_list = [_make_series(name=f"series_{i}", trend=("rising", "falling", "stable")[i % 3])
                        for i in range(20)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(_render_chart_svg, series_list))

        assert len(results) == len(series_list)
        for series, result in zip(series_list, results):
            assert result, f"empty render for {series['name']}"
            decoded = base64.b64decode(result).decode()
            assert decoded.startswith("<?xml")
            assert series["name"] in decoded
