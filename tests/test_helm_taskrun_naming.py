# tests/test_helm_taskrun_naming.py
# @ai-rules:
# 1. [Constraint]: Render-only Helm contract probes for TaskRun generateName values.
# 2. [Pattern]: Uses subprocess.run('helm template') from the BlackBoard root and parses YAML docs.
# 3. [Gotcha]: TriggerTemplate exists only when ephemeralAgents.enabled is rendered; values.yaml keeps it on by default.
# 4. [Contract]: Assert generateName on the oncall TriggerTemplate (darwin-ephemeral-agent, resourcetemplates[0]) and the separate prune TriggerTemplate (darwin-ephemeral-prune, resourcetemplates[0]) to guard against confusing the two.
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def _render_chart(*extra_args: str) -> list[dict]:
    result = subprocess.run(
        ["helm", "template", "darwin", "./helm", *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [doc for doc in yaml.safe_load_all(result.stdout) if isinstance(doc, dict)]


def _get_doc(docs: list[dict], kind: str, name: str) -> dict:
    return next(doc for doc in docs if doc.get("kind") == kind and doc.get("metadata", {}).get("name") == name)


class TestTaskRunNamingInTriggerTemplate:
    def test_oncall_taskrun_generate_name_includes_event_id_param(self):
        docs = _render_chart()
        trigger = _get_doc(docs, "TriggerTemplate", "darwin-ephemeral-agent")
        oncall = trigger["spec"]["resourcetemplates"][0]
        assert oncall["metadata"]["generateName"] == "darwin-oncall-$(tt.params.event_id)-"

    def test_prune_taskrun_generate_name_remains_unchanged(self):
        docs = _render_chart()
        trigger = _get_doc(docs, "TriggerTemplate", "darwin-ephemeral-prune")
        prune = trigger["spec"]["resourcetemplates"][0]
        assert prune["metadata"]["generateName"] == "darwin-prune-"
