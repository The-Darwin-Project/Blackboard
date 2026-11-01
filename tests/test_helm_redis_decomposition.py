# BlackBoard/tests/test_helm_redis_decomposition.py
# @ai-rules:
# 1. [Constraint]: Verify Helm chart manifests render standalone Redis and decoupled Brain.
# 2. [Pattern]: Subprocess helm template with yaml parsing against generated manifests.
# 3. [Gotcha]: Brain strategy must remain Recreate in PR 1 to prevent Ceph RBD RWO deadlock.
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
import yaml

HELM_DIR = Path(__file__).parent.parent / "helm"


def _render_helm_manifests(release_name: str = "darwin-test", extra_args: list[str] | None = None) -> list[dict]:
    cmd = ["helm", "template", release_name, str(HELM_DIR)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    docs = []
    for raw in result.stdout.split("---"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            doc = yaml.safe_load(raw)
            if isinstance(doc, dict) and "kind" in doc:
                docs.append(doc)
        except Exception:
            pass
    return docs


class TestHelmRedisDecomposition:
    """ATDD Suite: Helm Manifests for Standalone Redis Decomposition (PR 1)."""

    @pytest.fixture(scope="class")
    def manifests(self):
        return _render_helm_manifests("test-release", ["--set", "skillReconciler.enabled=true"])

    def test_standalone_redis_deployment_exists(self, manifests):
        """T-3: Standalone Redis deployment must exist with replicas 1 and Recreate strategy."""
        redis_deps = [
            m for m in manifests
            if m["kind"] == "Deployment" and m["metadata"]["name"] == "test-release-redis"
        ]
        assert len(redis_deps) == 1, "Expected test-release-redis Deployment"
        dep = redis_deps[0]
        assert dep["spec"]["replicas"] == 1
        assert dep["spec"]["strategy"]["type"] == "Recreate"
        
        pod_spec = dep["spec"]["template"]["spec"]
        assert pod_spec.get("automountServiceAccountToken") is False
        
        containers = pod_spec["containers"]
        assert len(containers) == 1
        c = containers[0]
        assert c["name"] == "redis"
        assert c["ports"][0]["containerPort"] == 6379
        assert "tcpSocket" in c["livenessProbe"]
        assert c["livenessProbe"]["tcpSocket"]["port"] == 6379
        assert "exec" in c["readinessProbe"]
        assert "redis-cli" in " ".join(c["readinessProbe"]["exec"]["command"])

    def test_standalone_redis_service_exists(self, manifests):
        """T-3: Standalone Redis Service must expose port 6379 as ClusterIP."""
        redis_svcs = [
            m for m in manifests
            if m["kind"] == "Service" and m["metadata"]["name"] == "test-release-redis"
        ]
        assert len(redis_svcs) == 1, "Expected test-release-redis Service"
        svc = redis_svcs[0]
        assert svc["spec"]["type"] == "ClusterIP"
        port_entry = next((p for p in svc["spec"]["ports"] if p["port"] == 6379), None)
        assert port_entry is not None
        assert svc["spec"]["selector"]["app"] == "darwin-redis"

    def test_redis_network_policy_exists(self, manifests):
        """T-3: Redis NetworkPolicy must restrict ingress to Brain selector labels."""
        nps = [
            m for m in manifests
            if m["kind"] == "NetworkPolicy" and "redis" in m["metadata"]["name"]
        ]
        assert len(nps) == 1, "Expected redis NetworkPolicy"
        np = nps[0]
        assert np["spec"]["podSelector"]["matchLabels"]["app"] == "darwin-redis"
        ingress = np["spec"]["ingress"]
        assert len(ingress) >= 1
        from_rules = ingress[0]["from"]
        assert any(
            r.get("podSelector", {}).get("matchLabels", {}).get("app") == "darwin-brain"
            for r in from_rules
        )

    def test_redis_pod_disruption_budget(self, manifests):
        """PodDisruptionBudget for darwin-redis with minAvailable 1."""
        pdbs = [
            m for m in manifests
            if m["kind"] == "PodDisruptionBudget" and "redis" in m["metadata"]["name"]
        ]
        assert len(pdbs) == 1, "Expected redis PodDisruptionBudget"
        pdb = pdbs[0]
        assert pdb["spec"]["minAvailable"] == 1
        assert pdb["spec"]["selector"]["matchLabels"]["app"] == "darwin-redis"

    def test_brain_deployment_decoupled_from_redis(self, manifests):
        """T-4: Brain Deployment must not contain redis container, but strategy remains Recreate."""
        brain_deps = [
            m for m in manifests
            if m["kind"] == "Deployment" and m["metadata"]["name"] == "test-release-brain"
        ]
        assert len(brain_deps) == 1, "Expected test-release-brain Deployment"
        dep = brain_deps[0]
        # In VMER-2103 (Phase 3) squad sidecars and CephFS PVC are pruned, enabling RollingUpdate
        assert dep["spec"]["strategy"]["type"] in ("Recreate", "RollingUpdate")
        
        containers = dep["spec"]["template"]["spec"]["containers"]
        container_names = [c["name"] for c in containers]
        assert "redis" not in container_names, "Redis container must be removed from Brain pod"

    def test_brain_and_reconciler_redis_host_configuration(self, manifests):
        """T-4: Brain and Skill-Reconciler point to standalone Redis host."""
        brain_deps = [
            m for m in manifests
            if m["kind"] == "Deployment" and m["metadata"]["name"] == "test-release-brain"
        ]
        dep = brain_deps[0]
        containers = {c["name"]: c for c in dep["spec"]["template"]["spec"]["containers"]}
        
        # Brain container
        brain = containers["brain"]
        brain_envs = {e["name"]: e.get("value") for e in brain.get("env", [])}
        assert brain_envs.get("REDIS_HOST") == "test-release-redis"
        
        # Skill reconciler container
        reconciler = containers["skill-reconciler"]
        reconciler_envs = {e["name"]: e.get("value") for e in reconciler.get("env", [])}
        assert reconciler_envs.get("REDIS_HOST") == "test-release-redis"
