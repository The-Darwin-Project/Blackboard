# tests/test_memgraph_sync_options.py
# Regression test for evt-f867e2ce: ArgoCD cannot patch the memgraph
# StatefulSet because of an immutable field change. The fix adds the
# Replace=true sync-option annotation so ArgoCD deletes/recreates the
# resource instead of patching it. This locks that annotation in place.
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HELM_DIR = Path(__file__).resolve().parent.parent / "helm"


def _render_chart():
    result = subprocess.run(
        ["helm", "template", "darwin-blackboard", str(HELM_DIR)],
        capture_output=True,
        text=True,
        check=True,
    )
    return list(yaml.safe_load_all(result.stdout))


@pytest.fixture(scope="module")
def rendered_manifests():
    if shutil.which("helm") is None:
        pytest.skip("helm binary not available")
    return _render_chart()


def _find_memgraph_statefulset(manifests):
    for doc in manifests:
        if not doc:
            continue
        if doc.get("kind") == "StatefulSet" and "memgraph" in doc["metadata"]["name"]:
            return doc
    return None


def test_memgraph_statefulset_has_replace_sync_option(rendered_manifests):
    statefulset = _find_memgraph_statefulset(rendered_manifests)
    assert statefulset is not None, "memgraph StatefulSet not found in rendered chart"

    annotations = statefulset["metadata"].get("annotations", {})
    assert annotations.get("argocd.argoproj.io/sync-options") == "Replace=true"


def test_replace_annotation_on_statefulset_not_pod_template(rendered_manifests):
    statefulset = _find_memgraph_statefulset(rendered_manifests)
    assert statefulset is not None

    pod_annotations = statefulset["spec"]["template"]["metadata"].get("annotations", {})
    assert "argocd.argoproj.io/sync-options" not in pod_annotations


def test_helm_lint_passes():
    if shutil.which("helm") is None:
        pytest.skip("helm binary not available")
    result = subprocess.run(
        ["helm", "lint", str(HELM_DIR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
