# BlackBoard/src/reports/observations_reporter.py
# @ai-rules:
# 1. [Pattern]: LLM pipeline: N per-series (parallel, return_exceptions) + 1 cross-series summary.
# 2. [Constraint]: matplotlib chart rendering via asyncio.to_thread — NEVER block the event loop.
# 3. [Pattern]: _sample_points(max_n=50) for LLM input — uniform downsampling.
# 4. [Constraint]: 30s asyncio.timeout per LLM call, 15s per chart render. Failures get
#    placeholder text/blank chart rather than propagating -- keeps the caller's outer 90s
#    report timeout (observations_mgmt.py) from being consumed by any single slow step.
# 5. [Pattern]: Charts use dark theme matching Darwin UI (bg=#0f172a).
"""LLM-powered observation analysis report with embedded SVG charts."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

_CHART_RENDER_TIMEOUT = 15

_SERIES_PROMPT = (
    "Analyze this operational time series from a Kubernetes/CI platform. "
    "Identify: trend direction and rate of change, anomalies or inflection points, "
    "operational significance, and recommended action if any. Be specific and quantitative."
)

_SUMMARY_PROMPT = (
    "Synthesize these operational observations into a cohesive report. "
    "Identify correlations between series, systemic patterns, risk assessment, "
    "and prioritized recommendations."
)


def _sample_points(points: list[dict], max_n: int = 50) -> list[dict]:
    if len(points) <= max_n:
        return points
    step = len(points) / max_n
    return [points[int(i * step)] for i in range(max_n)]


async def _analyze_series(client, model: str, series: dict) -> str:
    sampled = _sample_points(series["points"])
    data_block = "\n".join(
        f"  {p['timestamp']}  {p['value']} {series.get('unit', '')}" for p in sampled
    )
    prompt = (
        f"Series: {series['name']}\n"
        f"Trend: {series['trend']} | Range: {series['min']}-{series['max']} "
        f"{series.get('unit', '')} | Points: {series['count']} | "
        f"Span: {series['span_minutes']}m\n\n"
        f"Data sample ({len(sampled)} of {series['count']} points):\n{data_block}\n\n"
        f"{_SERIES_PROMPT}"
    )
    async with asyncio.timeout(30):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config={"max_output_tokens": 512, "temperature": 0.2},
        )
    return response.text or ""


async def _summarize(client, model: str, analyses: list[str], context: str) -> str:
    combined = "\n\n---\n\n".join(analyses)
    prompt = f"{combined}\n\n"
    if context:
        prompt += f"User context: {context}\n\n"
    prompt += _SUMMARY_PROMPT
    async with asyncio.timeout(30):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config={"max_output_tokens": 1024, "temperature": 0.2},
        )
    return response.text or ""


def _render_chart_svg(series: dict) -> str:
    """Render a dark-themed SVG sparkline chart. Runs in a thread."""
    trend_colors = {"rising": "#f59e0b", "falling": "#22c55e", "stable": "#64748b"}
    color = trend_colors.get(series.get("trend", "stable"), "#64748b")

    points = series.get("points", [])
    if not points:
        return ""

    epochs = [p["epoch"] for p in points]
    values = [p["value"] for p in points]

    fig = Figure(figsize=(6, 2))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    ax.plot(epochs, values, color=color, linewidth=1.2)
    ax.fill_between(epochs, values, alpha=0.15, color=color)
    ax.tick_params(colors="#64748b", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#334155")
    ax.spines["bottom"].set_color("#334155")
    ax.set_ylabel(series.get("unit", ""), color="#94a3b8", fontsize=8)
    ax.set_title(series["name"], color="#e2e8f0", fontsize=9, pad=4)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", facecolor="#0f172a", edgecolor="none")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


async def _render_chart_with_timeout(series: dict) -> str:
    """Bound chart rendering to _CHART_RENDER_TIMEOUT so one slow render can't silently
    consume the caller's whole outer report timeout. Returns "" (chart omitted) on timeout,
    matching the existing missing-chart handling in _assemble_report."""
    try:
        async with asyncio.timeout(_CHART_RENDER_TIMEOUT):
            return await asyncio.to_thread(_render_chart_svg, series)
    except TimeoutError:
        logger.warning("Chart render timed out after %ss for series %s", _CHART_RENDER_TIMEOUT, series.get("name"))
        return ""


def _assemble_report(
    summary: str,
    analyses: list[str],
    charts: list[str],
    selected: list[dict],
) -> dict:
    now = datetime.now(timezone.utc)
    lines = [
        "# Observations Analysis Report",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC | Series: {len(selected)} selected",
        "",
        "## Executive Summary",
        summary,
        "",
        "---",
    ]

    for i, series in enumerate(selected):
        lines.append(f"\n## {i + 1}. {series['name']}")
        if i < len(charts) and charts[i]:
            lines.append(f"![{series['name']} trend](data:image/svg+xml;base64,{charts[i]})")
        lines.append("")
        lines.append(
            f"**Trend:** {series['trend'].capitalize()} | "
            f"**Range:** {series['min']} - {series['max']} {series.get('unit', '')} | "
            f"**Points:** {series['count']} | **Span:** {series['span_minutes']}m"
        )
        lines.append("")
        lines.append("### Analysis")
        lines.append(analyses[i] if i < len(analyses) else "[Analysis unavailable]")
        lines.append("\n---")

    markdown = "\n".join(lines)
    return {
        "markdown": markdown,
        "filename": f"observations-report-{now.strftime('%Y-%m-%d')}.md",
        "series_count": len(selected),
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def generate_report(
    blackboard,
    client,
    model: str,
    series_names: list[str],
    context: str = "",
) -> dict:
    """Generate an LLM-powered analysis report for selected observation series."""
    obs_data = await blackboard.list_observations()
    name_set = set(series_names)
    selected = [s for s in obs_data.get("observations", []) if s["name"] in name_set][
        :BlackboardState.OBS_MAX_REPORT_SERIES
    ]

    if not selected:
        return _assemble_report(
            "No matching observation series found.", [], [], [],
        )

    results = await asyncio.gather(
        *[_analyze_series(client, model, s) for s in selected],
        return_exceptions=True,
    )
    analyses: list[str] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Report analysis failed for %s: %s", selected[i]["name"], r)
            analyses.append("[Analysis unavailable — LLM error]")
        else:
            analyses.append(r)

    valid = [a for a in analyses if not a.startswith("[Analysis unavailable")]
    try:
        summary = (
            await _summarize(client, model, valid, context)
            if valid
            else "Insufficient data for cross-series summary."
        )
    except Exception as e:
        logger.warning("Cross-series summary failed: %s", e)
        summary = "Cross-series summary unavailable."

    charts_raw = await asyncio.gather(
        *[_render_chart_with_timeout(s) for s in selected],
        return_exceptions=True,
    )
    charts: list[str] = []
    for c in charts_raw:
        charts.append(c if isinstance(c, str) else "")

    return _assemble_report(summary, analyses, charts, selected)
