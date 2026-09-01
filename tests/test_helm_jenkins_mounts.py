# tests/test_helm_jenkins_mounts.py
# @ai-rules:
# 1. [Constraint]: Render-only Helm contract probes for Jenkins Secret/env wiring.
# 2. [Pattern]: Uses subprocess.run('helm template') from the BlackBoard root and parses YAML docs.
# 3. [Gotcha]: TriggerTemplate exists only when ephemeralAgents.enabled is rendered; values.yaml keeps it on by default.
# 4. [Contract]: Assert mount/env presence by container or step name, not by line order in rendered YAML.
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


def _get_named(items: list[dict], name: str) -> dict:
    return next(item for item in items if item.get("name") == name)


def _mount_paths(item: dict) -> set[str]:
    return {mount.get("mountPath") for mount in item.get("volumeMounts", [])}


def _env_map(item: dict) -> dict[str, str]:
    return {
        env.get("name"): env.get("value")
        for env in item.get("env", [])
        if env.get("name")
    }


class TestJenkinsMountsInDeployment:
    def test_t9_sysadmin_mount_present_when_existing_secret_set(self):
        docs = _render_chart("--set", "jenkinsObserver.jenkins.existingSecret=test-secret")
        deployment = _get_doc(docs, "Deployment", "darwin-brain")
        sysadmin = _get_named(deployment["spec"]["template"]["spec"]["containers"], "sysadmin-sidecar")
        assert "/secrets/jenkins" in _mount_paths(sysadmin)
        assert _env_map(sysadmin)["JENKINS_URL"] == ""

    def test_t10_sysadmin_mount_absent_when_existing_secret_empty(self):
        docs = _render_chart()
        deployment = _get_doc(docs, "Deployment", "darwin-brain")
        sysadmin = _get_named(deployment["spec"]["template"]["spec"]["containers"], "sysadmin-sidecar")
        assert "/secrets/jenkins" not in _mount_paths(sysadmin)
        volume_names = {volume.get("name") for volume in deployment["spec"]["template"]["spec"]["volumes"]}
        assert "jenkins-secret" not in volume_names

    def test_t9b_developer_mount_present_when_existing_secret_set(self):
        docs = _render_chart("--set", "jenkinsObserver.jenkins.existingSecret=test-secret")
        deployment = _get_doc(docs, "Deployment", "darwin-brain")
        developer = _get_named(deployment["spec"]["template"]["spec"]["containers"], "developer-sidecar")
        assert "/secrets/jenkins" in _mount_paths(developer)
        assert _env_map(developer)["JENKINS_URL"] == ""


class TestJenkinsMountsInTriggerTemplate:
    def test_t11_trigger_template_mount_present_when_existing_secret_set(self):
        docs = _render_chart("--set", "jenkinsObserver.jenkins.existingSecret=test-secret")
        trigger = _get_doc(docs, "TriggerTemplate", "darwin-ephemeral-agent")
        agent = _get_named(trigger["spec"]["resourcetemplates"][0]["spec"]["taskSpec"]["steps"], "agent")
        assert "/secrets/jenkins" in _mount_paths(agent)
        env_map = _env_map(agent)
        assert "JENKINS_URL" in env_map
        assert env_map["JENKINS_INSECURE_TLS"] == "false"

    def test_t12_trigger_template_mount_absent_when_existing_secret_empty(self):
        docs = _render_chart()
        trigger = _get_doc(docs, "TriggerTemplate", "darwin-ephemeral-agent")
        agent = _get_named(trigger["spec"]["resourcetemplates"][0]["spec"]["taskSpec"]["steps"], "agent")
        assert "/secrets/jenkins" not in _mount_paths(agent)
        env_map = _env_map(agent)
        assert "JENKINS_URL" not in env_map
        assert "JENKINS_INSECURE_TLS" not in env_map
