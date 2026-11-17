# tests/test_helm_trusted_ca_bundle.py
# @ai-rules:
# 1. [Constraint]: Render-only Helm contract probes for the OpenShift trusted CA bundle (VMER-2398).
# 2. [Pattern]: Uses subprocess.run('helm template') from the repo root and parses YAML docs (same as test_helm_jenkins_mounts.py).
# 3. [Contract]: trustedCaBundle.enabled=false (default) renders NO CA volume/mount/env; enabled=true mounts the
#    ConfigMap on the brain container (and skill-reconciler when enabled) and the volume is NEVER `optional`.
# 4. [Gotcha]: skill-reconciler only renders with skillReconciler.enabled=true; assert by container name, not order.
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CA_PATH = "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
VOLUME = "trusted-ca-bundle"


def _brain_pod_spec(*extra_args: str) -> dict:
    result = subprocess.run(
        ["helm", "template", "darwin", "./helm", *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for doc in yaml.safe_load_all(result.stdout):
        if isinstance(doc, dict) and doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "darwin-brain":
            return doc["spec"]["template"]["spec"]
    raise AssertionError("darwin-brain Deployment not rendered")


def _container(spec: dict, name: str) -> dict:
    return next(c for c in spec["containers"] if c["name"] == name)


def _env(container: dict) -> dict[str, str]:
    return {e["name"]: e.get("value") for e in container.get("env") or [] if e.get("name")}


def _ca_mounts(container: dict) -> list[dict]:
    return [m for m in container.get("volumeMounts") or [] if m.get("name") == VOLUME]


def _ca_volumes(spec: dict) -> list[dict]:
    return [v for v in spec.get("volumes") or [] if v.get("name") == VOLUME]


class TestTrustedCaBundleDisabled:
    @pytest.mark.parametrize("extra", [(), ("--set", "trustedCaBundle.enabled=false")])
    def test_default_render_has_no_ca_wiring(self, extra):
        spec = _brain_pod_spec(*extra)
        assert _ca_volumes(spec) == []
        for container in spec["containers"]:
            assert _ca_mounts(container) == []
            env = _env(container)
            assert env.get("SSL_CERT_FILE") != CA_PATH
            assert env.get("REQUESTS_CA_BUNDLE") != CA_PATH


class TestTrustedCaBundleEnabled:
    def test_brain_container_mounts_ca_bundle_and_exports_env(self):
        spec = _brain_pod_spec("--set", "trustedCaBundle.enabled=true")
        brain = _container(spec, "brain")
        assert _ca_mounts(brain) == [
            {"name": VOLUME, "mountPath": CA_PATH, "subPath": "ca-bundle.crt", "readOnly": True}
        ]
        env = _env(brain)
        assert env["SSL_CERT_FILE"] == CA_PATH
        assert env["REQUESTS_CA_BUNDLE"] == CA_PATH

    def test_configmap_volume_is_not_optional(self):
        """optional: true would mount an empty dir and leave SSL_CERT_FILE dangling; must fail fast instead."""
        spec = _brain_pod_spec("--set", "trustedCaBundle.enabled=true")
        volumes = _ca_volumes(spec)
        assert len(volumes) == 1
        assert volumes[0]["configMap"]["name"] == "config-trusted-cabundle"
        assert "optional" not in volumes[0]["configMap"]

    def test_custom_configmap_name_is_honoured(self):
        spec = _brain_pod_spec(
            "--set", "trustedCaBundle.enabled=true",
            "--set", "trustedCaBundle.configMapName=corp-ca",
        )
        assert _ca_volumes(spec)[0]["configMap"]["name"] == "corp-ca"

    def test_skill_reconciler_also_mounts_when_enabled(self):
        spec = _brain_pod_spec(
            "--set", "trustedCaBundle.enabled=true",
            "--set", "skillReconciler.enabled=true",
        )
        reconciler = _container(spec, "skill-reconciler")
        assert len(_ca_mounts(reconciler)) == 1
        assert _env(reconciler)["SSL_CERT_FILE"] == CA_PATH
        assert len(_ca_volumes(spec)) == 1
