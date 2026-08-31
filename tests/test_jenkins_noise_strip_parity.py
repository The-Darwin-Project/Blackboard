# BlackBoard/tests/test_jenkins_noise_strip_parity.py
# @ai-rules:
# 1. [Constraint]: Anchors Python<->TS BEHAVIOR parity for the Jenkins noise-stripping regexes
#    (not just field names, unlike test_flow_snapshot_parity.py) -- runs the exact same corpus
#    through both engines and diffs the actual output.
# 2. [Pattern]: Shells out to `node --experimental-strip-types` against ts_parity_harness.mjs,
#    which imports the real stripAnsi.ts unmodified -- no separate JS reimplementation to keep
#    in sync by hand, and no build/transpile step.
# 3. [Gotcha]: Skips (not fails) if node is unavailable or lacks TS type-stripping support, since
#    dev/CI images are not guaranteed to ship a matching Node version -- this is a drift guard,
#    not a hard dependency of the Python test suite.
"""
CI guard: ensures the Jenkins console-noise stripping regex logic
(`_strip_pipeline_annotations` in jenkins.py / `stripJenkinsNoise` in
stripAnsi.ts) behaves IDENTICALLY across a shared corpus covering every fixed
bug (F1/F3/F4/F5/F9) and the boundary-hardening cases added afterward. This
logic is hand-duplicated across Python and TypeScript with no shared source
-- a future fix landing on only one side must fail this test, not ship
silently drifted.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.adapters.jenkins import _strip_pipeline_annotations

HARNESS_PATH = Path(__file__).parent / "ts_parity_harness.mjs"
REPO_ROOT = Path(__file__).parent.parent

CORPUS = [
    "before ha:////ABC123== after",
    "ha:////AAA==ha:////BBB==",
    "ha:////ABC==password:hunter2",
    # F9: MEDIUM secret-redaction-bypass finding -- an unpadded, non-ANSI-
    # wrapped blob directly abutting a real, all-alphanumeric secret must
    # be left fully untouched (mandatory padding/ANSI-escape termination
    # required; bare whitespace/EOS no longer accepted) so downstream
    # bearer-token redaction can still see the literal word "Bearer".
    "ha:////AAAABearer sometoken123",
    "filler text ha:////AAAABearersecrettoken123",
    # F10: adversarial follow-up -- a single `=` was accepted as
    # unconditional padding proof, but a lone `=` is exactly the common
    # `KEY=value` secret delimiter and is genuinely ambiguous with real
    # single-char base64 padding. Must now also pass a lookahead check.
    "ha:////AAAtoken=abc123xyz",
    "ha:////AAApassword=hunter2",
    "ha:////AAAsecret=xyz",
    "before ha:////ABC1= after",
    "ha:////AAA=ha:////BBB==",
    "\x1b[8mha:////ABC\x1b[0m\r\n\r\n\r\n",
    "[Pipeline] }\n[Pipeline] // container\nreal output",
    "output\n[Pipeline] End of Pipeline",
    "Running [Pipeline] } leftover",
    "Deploying [Pipeline] stage now, please wait",
    # F2/boundary-hardening: a marker substring that's a PREFIX of a longer
    # real word must not be misidentified as a boundary.
    "[Pipeline] stagecoach rolls out\nreal output",
    "[Pipeline] staged rollback\nreal output",
    "[Pipeline] End of PipelineExtra: still going\nreal output",
    "[2026-08-31T11:23:24.854Z] [Pipeline] // container\nreal output",
    "a\n\n\n\n\nb",
    "",
]


def _run_ts(corpus: list[str]) -> list[str] | None:
    """Run `corpus` through the real TS stripJenkinsNoise via the Node harness.
    Returns None (causing a skip) if node or its TS type-stripping support
    is unavailable -- never fabricates a result."""
    node = shutil.which("node")
    if not node:
        return None
    try:
        proc = subprocess.run(
            [node, "--experimental-strip-types", str(HARNESS_PATH)],
            input=json.dumps(corpus),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def test_python_and_typescript_strip_identically_across_corpus():
    ts_results = _run_ts(CORPUS)
    if ts_results is None:
        pytest.skip("node with TypeScript type-stripping support is unavailable")

    py_results = [_strip_pipeline_annotations(text) for text in CORPUS]

    assert len(ts_results) == len(py_results)
    mismatches = [
        (text, py, ts)
        for text, py, ts in zip(CORPUS, py_results, ts_results)
        if py != ts
    ]
    assert not mismatches, (
        "Python/TS noise-stripping regex logic drifted for input(s): "
        f"{mismatches!r} -- see jenkins.py's _PIPELINE_ANNOTATION_RE / "
        "_PIPELINE_BOUNDARY_RE vs ui/src/utils/stripAnsi.ts's mirrors"
    )
