# tests/test_observations_reporter.py
# @ai-rules:
# 1. [Pattern]: Direct unit tests for _render_chart_svg — no stubbing, exercises real matplotlib rendering.
# 2. [Constraint]: No live Redis/LLM needed; this module only tests the pure chart-rendering function.
"""Unit tests for the observations report chart renderer."""
from __future__ import annotations

import base64
import concurrent.futures

from src.reports.observations_reporter import _render_chart_svg

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_series(name: str = "error_count", trend: str = "rising", n: int = 10) -> dict:
    return {
        "name": name,
        "trend": trend,
        "unit": "count",
        "points": [{"epoch": i, "value": float(i * 2)} for i in range(n)],
    }


class TestRenderChartSvg:
    def test_renders_valid_base64_png(self):
        """Real rendering produces a non-empty, decodable PNG payload."""
        result = _render_chart_svg(_make_series())
        assert result
        decoded = base64.b64decode(result)
        assert decoded[:8] == _PNG_MAGIC

    def test_empty_points_returns_empty_string(self):
        """No points → the empty-points guard short-circuits before touching matplotlib."""
        series = {"name": "no_data", "trend": "stable", "unit": "", "points": []}
        assert _render_chart_svg(series) == ""

    def test_each_trend_color_renders(self):
        """All three known trend states render without error."""
        for trend in ("rising", "falling", "stable"):
            result = _render_chart_svg(_make_series(trend=trend))
            assert result
            assert base64.b64decode(result)[:8] == _PNG_MAGIC

    def test_unknown_trend_falls_back_to_default_color(self):
        """An unrecognized trend value still renders (falls back to the default color)."""
        result = _render_chart_svg(_make_series(trend="unknown"))
        assert result

    def test_series_name_affects_chart_output(self):
        """The series name is used as the chart title. PNG is a raster format, so the name
        can't be substring-matched in the payload like the old SVG/XML text could -- instead
        assert the render is a valid PNG and that changing only the name (rendered as the
        title) changes the rasterized bytes."""
        result_a = _render_chart_svg(_make_series(name="pipeline_duration_m"))
        result_b = _render_chart_svg(_make_series(name="other_series_name"))
        decoded_a = base64.b64decode(result_a)
        decoded_b = base64.b64decode(result_b)
        assert decoded_a[:8] == _PNG_MAGIC
        assert decoded_a != decoded_b

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
        decoded_results = []
        for series, result in zip(series_list, results):
            assert result, f"empty render for {series['name']}"
            decoded = base64.b64decode(result)
            assert decoded[:8] == _PNG_MAGIC, f"invalid PNG magic bytes for {series['name']}"
            decoded_results.append(decoded)

        # Cross-contamination would manifest as two differently-named/titled series
        # producing byte-identical PNGs (e.g. one thread's buffer leaking into another's).
        assert len(set(decoded_results)) == len(decoded_results)
