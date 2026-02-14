# BlackBoard/src/observers/kubernetes.py
# @ai-rules:
# 1. [Constraint]: Agents (Aligner/Architect) cannot import kubernetes; this module is the only K8s touchpoint.
# 2. [Pattern]: Darwin annotation discovery (darwin.io/*) is additive; label-based discovery remains the fallback.
# 3. [Gotcha]: update_service_metadata requires version/cpu/memory/error_rate; K8s discovery supplies version (image tag), deps (env vars), error_rate (restart counts).
"""
Kubernetes Metrics Observer.

Polls Kubernetes metrics-server for pod resource usage.
Provides external observation that works even when apps are throttled.

This module is intentionally separate from agents (Aligner/Architect)
to respect the architecture constraint that agents cannot import kubernetes.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Optional, Callable, Awaitable

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Suppress debug noise from metrics polling

# Environment variable configuration
K8S_OBSERVER_ENABLED = os.getenv("K8S_OBSERVER_ENABLED", "false").lower() == "true"
K8S_OBSERVER_NAMESPACE = os.getenv("K8S_OBSERVER_NAMESPACE", "darwin")
K8S_OBSERVER_INTERVAL = int(os.getenv("K8S_OBSERVER_INTERVAL", "5"))  # Match darwin-client interval
K8S_OBSERVER_LABEL_SELECTOR = os.getenv("K8S_OBSERVER_LABEL_SELECTOR", "")

# Darwin annotation schema for Deployment-based service discovery
DARWIN_ANNOTATION_PREFIX = "darwin.io/"
DARWIN_MONITORED = f"{DARWIN_ANNOTATION_PREFIX}monitored"
DARWIN_SOURCE_REPO = f"{DARWIN_ANNOTATION_PREFIX}source-repo"
DARWIN_GITOPS_REPO = f"{DARWIN_ANNOTATION_PREFIX}gitops-repo"
DARWIN_CONFIG_PATH = f"{DARWIN_ANNOTATION_PREFIX}config-path"
DARWIN_SERVICE_NAME = f"{DARWIN_ANNOTATION_PREFIX}service-name"


class KubernetesObserver:
    """
    Observes Kubernetes pod metrics and feeds them to the Blackboard.
    
    Uses the metrics.k8s.io API (metrics-server) to get CPU/memory usage.
    Maps pod names to service names using the 'app' label.
    """
    
    # Unhealthy container states that should trigger investigation
    UNHEALTHY_STATES = {"ImagePullBackOff", "ErrImagePull", "CrashLoopBackOff", "OOMKilled", "Error", "CreateContainerError"}
    
    # K8s Event reasons that indicate pod-level issues (even when pod status is Running)
    WARNING_EVENT_REASONS = {"Unhealthy", "BackOff", "Failed", "FailedMount", "FailedScheduling"}
    # Minimum event count within the polling window to trigger an alert
    WARNING_EVENT_THRESHOLD = 3
    
    def __init__(
        self,
        blackboard: "BlackboardState",
        anomaly_callback: Optional[Callable[..., Awaitable[None]]] = None,
        pod_health_callback: Optional[Callable[[str, str, str], Awaitable[None]]] = None,
        namespace: str = K8S_OBSERVER_NAMESPACE,
        interval: int = K8S_OBSERVER_INTERVAL,
        label_selector: str = K8S_OBSERVER_LABEL_SELECTOR,
    ):
        """
        Initialize the observer.
        
        Args:
            blackboard: Blackboard state for storing metrics
            anomaly_callback: Async callback(service, cpu, memory, source) for anomaly detection
            pod_health_callback: Async callback(service, pod_name, reason) for unhealthy pod states
            namespace: Kubernetes namespace to watch
            interval: Polling interval in seconds
            label_selector: Optional label selector to filter pods
        """
        self.blackboard = blackboard
        self.anomaly_callback = anomaly_callback
        self.pod_health_callback = pod_health_callback
        self.namespace = namespace
        self.namespaces = [n.strip() for n in namespace.split(",") if n.strip()] if namespace else ["default"]
        self.interval = interval
        self.label_selector = label_selector
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._k8s_available = False
        
        # Pod resource limits cache: {pod_name: {"cpu_limit": millicores, "memory_limit": bytes}}
        self._pod_limits: dict[str, dict] = {}
        # Track already-reported unhealthy pods to avoid spam: {pod_name: reason}
        self._reported_unhealthy: dict[str, str] = {}
        # Track reported K8s Warning events: {"pod:reason" -> True}
        self._reported_events: dict[str, bool] = {}
        # Active warning events per service: {service -> reason_string}
        # Fed into anomaly_callback as elevated error_rate (30s buffer path)
        self._active_warnings: dict[str, str] = {}
        # Reconciliation cycle counter (runs every RECONCILE_EVERY_N_CYCLES polls)
        self._poll_count = 0
        self.RECONCILE_EVERY_N_CYCLES = 12  # ~60s at 5s interval
        # Set of service names with darwin.io/monitored annotation (populated by _poll_deployment_annotations)
        # Used to filter pod metrics: only 'app' labels matching monitored services get registered
        self._monitored_app_labels: set[str] = set()
    
    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            logger.warning("KubernetesObserver already running")
            return
        
        # Try to initialize Kubernetes client
        if not await self._init_k8s_client():
            logger.warning("KubernetesObserver disabled: K8s client not available")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._polling_loop())
        logger.info(
            f"KubernetesObserver started: namespace={self.namespace}, "
            f"interval={self.interval}s, label_selector={self.label_selector or 'none'}"
        )
    
    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("KubernetesObserver stopped")
    
    async def _init_k8s_client(self) -> bool:
        """
        Initialize the Kubernetes client.
        
        Returns True if successful, False otherwise.
        """
        try:
            from kubernetes import client, config
            
            # Try in-cluster config first (when running in a pod)
            try:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except config.ConfigException:
                # Fall back to kubeconfig (for local development)
                try:
                    config.load_kube_config()
                    logger.info("Loaded kubeconfig")
                except config.ConfigException as e:
                    logger.warning(f"No Kubernetes config available: {e}")
                    return False
            
            # Store clients for later use
            self._core_api = client.CoreV1Api()
            self._custom_api = client.CustomObjectsApi()
            self._apps_api = client.AppsV1Api()
            self._k8s_available = True
            return True
            
        except ImportError:
            logger.warning("kubernetes package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize K8s client: {e}")
            return False
    
    async def _polling_loop(self) -> None:
        """Main polling loop - runs until stopped."""
        while self._running:
            try:
                await self._poll_deployment_annotations()
                await self._poll_metrics()
                await self._poll_pod_health()
                await self._poll_warning_events()
                # Reconcile stale services on a slower cadence
                self._poll_count += 1
                if self._poll_count % self.RECONCILE_EVERY_N_CYCLES == 0:
                    await self._reconcile_services()
            except Exception as e:
                logger.error(f"Error polling K8s metrics: {e}")
            
            # Wait for next interval
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
    
    async def _poll_deployment_annotations(self) -> None:
        """
        Poll Deployments for darwin.io/* annotations and register/update services.

        When a Deployment has darwin.io/monitored: "true", extract service name,
        version from image tag, dependencies from env vars, gitops-repo, and helm-path,
        then register the service and its metadata in the Blackboard.
        """
        if not self._k8s_available:
            return

        for namespace in self.namespaces:
            try:
                deployments = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self._apps_api.list_namespaced_deployment(
                        ns,
                        label_selector=self.label_selector or None,
                    )
                )

                for deploy in deployments.items:
                    annotations = deploy.metadata.annotations or {}
                    if annotations.get(DARWIN_MONITORED, "").lower() != "true":
                        continue

                    service_name = annotations.get(DARWIN_SERVICE_NAME) or deploy.metadata.name
                    if not service_name:
                        continue

                    # Track which 'app' labels belong to monitored services
                    # so _poll_metrics only registers pods from monitored workloads
                    deploy_labels = deploy.metadata.labels or {}
                    if "app" in deploy_labels:
                        self._monitored_app_labels.add(deploy_labels["app"])

                    source_repo_url = annotations.get(DARWIN_SOURCE_REPO)
                    gitops_repo_url = annotations.get(DARWIN_GITOPS_REPO) or source_repo_url  # fallback to source if no separate gitops
                    helm_path = annotations.get(DARWIN_CONFIG_PATH)

                    gitops_repo = self._parse_gitops_repo_from_url(gitops_repo_url) if gitops_repo_url else None

                    # Extract version from first container image tag
                    containers = deploy.spec.template.spec.containers if deploy.spec and deploy.spec.template and deploy.spec.template.spec else []
                    if containers:
                        image = containers[0].image or ""
                        version = image.split(":")[-1] if ":" in image else "latest"
                        if len(version) >= 7 and all(c in "0123456789abcdef" for c in version.lower()):
                            version = version[:7]
                    else:
                        version = "k8s"

                    # Extract dependencies from env vars (SERVICE_URL, DB_HOST, etc.)
                    deps = self._extract_dependencies(containers)

                    await self.blackboard.redis.sadd("darwin:services", service_name)
                    for dep in deps:
                        await self.blackboard.add_edge(service_name, dep)

                    await self.blackboard.update_service_metadata(
                        name=service_name,
                        version=version,
                        cpu=0.0,
                        memory=0.0,
                        error_rate=0.0,
                        source_repo_url=source_repo_url,
                        gitops_repo=gitops_repo,
                        gitops_repo_url=gitops_repo_url,
                        gitops_config_path=helm_path,
                    )
                    logger.debug(
                        f"Registered service from annotations: {service_name} "
                        f"(version={version}, deps={deps}, gitops={gitops_repo}, helm_path={helm_path})"
                    )

            except Exception as e:
                logger.debug(f"Failed to poll deployment annotations in {namespace}: {e}")

    # Stale service threshold: remove services with no telemetry for 5 minutes
    STALE_SERVICE_SECONDS = 300

    async def _reconcile_services(self) -> None:
        """
        Reconcile Redis service registry against live cluster state.

        Removes services from darwin:services that have no matching Deployment
        or StatefulSet AND no recent telemetry (last_seen > STALE_SERVICE_SECONDS).
        This prevents ghost nodes from accumulating in the topology graph.
        """
        if not self._k8s_available:
            return

        import time

        try:
            # 1. Gather live workload names from the cluster
            live_services: set[str] = set()
            for namespace in self.namespaces:
                try:
                    # Deployments
                    deploys = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda ns=namespace: self._apps_api.list_namespaced_deployment(ns)
                    )
                    for d in deploys.items:
                        # Use annotation service name if available, else deployment name
                        annotations = d.metadata.annotations or {}
                        svc_name = annotations.get(DARWIN_SERVICE_NAME) or d.metadata.name
                        live_services.add(svc_name)
                        # Add 'app' label only for monitored deployments
                        labels = d.metadata.labels or {}
                        if "app" in labels and labels["app"] in self._monitored_app_labels:
                            live_services.add(labels["app"])

                    # StatefulSets -- only add the resource name, NOT bare 'app' labels
                    # (prevents ghost 'postgres' from app=postgres on internal StatefulSets)
                    sts_list = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda ns=namespace: self._apps_api.list_namespaced_stateful_set(ns)
                    )
                    for s in sts_list.items:
                        live_services.add(s.metadata.name)

                    # Services (K8s Service resources -- for dependency targets)
                    svc_list = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda ns=namespace: self._core_api.list_namespaced_service(ns)
                    )
                    for svc in svc_list.items:
                        live_services.add(svc.metadata.name)

                except Exception as e:
                    logger.debug(f"Reconciliation: failed to list resources in {namespace}: {e}")

            # 2. Compare against Redis service registry
            registered = await self.blackboard.get_services()
            now = time.time()
            removed = []

            for service in registered:
                # Skip if the service exists in the cluster
                if service in live_services:
                    continue

                # Skip external services (github.com, etc.) -- they have no cluster presence
                if "." in service and any(service.endswith(tld) for tld in
                        [".com", ".io", ".org", ".net", ".dev", ".cloud"]):
                    continue

                # Check last_seen -- only remove if stale
                metadata = await self.blackboard.get_service(service)
                if metadata and metadata.last_seen:
                    age = now - metadata.last_seen
                    if age < self.STALE_SERVICE_SECONDS:
                        continue  # Fresh telemetry, keep it

                # Ghost confirmed: not in cluster + no fresh telemetry
                await self.blackboard.remove_service(service)
                removed.append(service)

            if removed:
                logger.info(f"Reconciliation: removed {len(removed)} stale services: {removed}")

        except Exception as e:
            logger.error(f"Service reconciliation failed: {e}")

    @staticmethod
    def _parse_gitops_repo_from_url(url: Optional[str]) -> Optional[str]:
        """Parse owner/repo from Git URL (e.g. https://github.com/owner/repo.git -> owner/repo)."""
        if not url:
            return None
        try:
            url = url.rstrip("/")
            if url.endswith(".git"):
                url = url[:-4]
            parts = url.split("/")
            if len(parts) >= 2:
                return "/".join(parts[-2:])
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_dependencies(containers: list) -> list[str]:
        """
        Extract dependency names from env vars that look like service references.

        Looks for env vars with names containing _URL, _HOST, _SERVICE, _ADDR.
        Parses values like "http://darwin-store:8080" -> "darwin-store".
        """
        deps: set[str] = set()
        service_patterns = ["_URL", "_HOST", "_SERVICE", "_ADDR"]
        for container in containers or []:
            if not container.env:
                continue
            for env_var in container.env:
                if not hasattr(env_var, "value") or not env_var.value:
                    continue
                if not any(p in env_var.name for p in service_patterns):
                    continue
                value = env_var.value
                if "://" in value:
                    value = value.split("://", 1)[1]
                host = value.split(":")[0].split("/")[0]
                if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
                    deps.add(host)
        return list(deps)

    async def _poll_metrics(self) -> None:
        """Fetch pod metrics from metrics-server and process them."""
        if not self._k8s_available:
            return
        
        for ns in self.namespaces:
            try:
                # Get pod metrics from metrics.k8s.io API
                # This is an async-wrapped sync call
                metrics = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda n=ns: self._custom_api.list_namespaced_custom_object(
                        group="metrics.k8s.io",
                        version="v1beta1",
                        namespace=n,
                        plural="pods",
                        label_selector=self.label_selector or None,
                    )
                )
                
                items = metrics.get("items", [])
                logger.debug(f"Got metrics for {len(items)} pods in {ns}")
                
                for pod_metrics in items:
                    await self._process_pod_metrics(pod_metrics)
                    
            except Exception as e:
                # Don't crash on metrics-server errors (it might be temporarily unavailable)
                logger.warning(f"Failed to fetch pod metrics in {ns}: {e}")
    
    def _pod_key(self, namespace: str, pod_name: str) -> str:
        """Unique key for pod across namespaces."""
        return f"{namespace}/{pod_name}"

    async def _poll_pod_health(self) -> None:
        """
        Check pod container states for unhealthy conditions.

        Detects: ImagePullBackOff, CrashLoopBackOff, OOMKilled, Error, etc.
        Pods in these states won't report metrics, so _poll_metrics misses them.

        Also aggregates container restart counts per service and stores as error_rate
        in the Blackboard (passive K8s-native replacement for DarwinClient error telemetry).
        """
        if not self._k8s_available:
            return

        healthy_keys: set[str] = set()
        service_restarts: dict[str, int] = {}

        for namespace in self.namespaces:
            try:
                pods = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self._core_api.list_namespaced_pod(
                        ns,
                        label_selector=self.label_selector or None,
                    )
                )
                
                for pod in pods.items:
                    pod_name = pod.metadata.name
                    pod_key = self._pod_key(namespace, pod_name)
                    labels = pod.metadata.labels or {}
                    service_name = labels.get("app") or labels.get("app.kubernetes.io/name")
                    
                    if not service_name:
                        continue
                    
                    # Skip self-monitoring
                    if service_name in ("darwin-brain", "darwin-blackboard-brain"):
                        continue
                    
                    # Only monitor pods whose 'app' label matches a darwin.io/monitored workload.
                    # Prevents ghost nodes from unmonitored StatefulSets (e.g., postgres with app=postgres).
                    if self._monitored_app_labels and service_name not in self._monitored_app_labels:
                        continue
                    
                    # Aggregate restart counts per service for error_rate
                    total = sum(cs.restart_count or 0 for cs in (pod.status.container_statuses or []) + (pod.status.init_container_statuses or []))
                    service_restarts[service_name] = service_restarts.get(service_name, 0) + total
                    
                    # Check container statuses for unhealthy states
                    reason = self._get_unhealthy_reason(pod)
                    
                    if reason:
                        # Only report if not already reported for this pod+reason
                        if self._reported_unhealthy.get(pod_key) != reason:
                            self._reported_unhealthy[pod_key] = reason
                            logger.warning(f"Unhealthy pod: {pod_key} ({service_name}): {reason}")
                            if self.pod_health_callback:
                                await self.pod_health_callback(service_name, pod_name, reason)
                    else:
                        healthy_keys.add(pod_key)
                    
            except Exception as e:
                logger.debug(f"Failed to poll pod health in {namespace}: {e}")

        # Store restart-derived error_rate in Blackboard per service
        for service_name, total_restarts in service_restarts.items():
            error_rate = min(100.0, float(total_restarts) * 10.0) if total_restarts > 0 else 0.0
            await self.blackboard.record_metric(
                service_name, "error_rate", error_rate, source="kubernetes"
            )
            await self.blackboard.redis.sadd("darwin:services", service_name)
        
        # Clear resolved pods from tracking
        for pod_key in list(self._reported_unhealthy.keys()):
            if pod_key in healthy_keys:
                logger.info(f"Pod recovered: {pod_key}")
                del self._reported_unhealthy[pod_key]
    
    async def _poll_warning_events(self) -> None:
        """
        Poll K8s Warning events for probe failures and recurring issues.
        
        Catches problems invisible to container status checks:
        - Liveness/readiness probe failures (pod still Running, but failing probes)
        - Image pull secret warnings (pod Running, but secret missing)
        - Volume mount failures, scheduling issues
        
        Feeds through the anomaly_callback (30s metrics buffer) NOT the instant
        pod_health_callback. Probe failures can be transient (lazy loading,
        rolling deployments), so Flash needs the full 30s window to decide
        if it's sustained or noise.
        
        Only activates when the same warning repeats >= WARNING_EVENT_THRESHOLD times.
        """
        if not self._k8s_available or not self.anomaly_callback:
            return
        
        # Aggregate warnings across all namespaces
        service_warnings: dict[str, dict] = {}
        
        for namespace in self.namespaces:
            try:
                events = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self._core_api.list_namespaced_event(
                        ns,
                        field_selector="type=Warning",
                    )
                )
                
                for event in events.items:
                    reason = event.reason or ""
                    if reason not in self.WARNING_EVENT_REASONS:
                        message = event.message or ""
                        if "probe failed" not in message.lower() and "liveness" not in message.lower() and "readiness" not in message.lower():
                            continue
                    
                    obj = event.involved_object
                    if not obj or obj.kind != "Pod":
                        continue
                    pod_name = obj.name or ""
                    if not pod_name:
                        continue
                    
                    service_name = await self._get_service_name(pod_name, namespace)
                    if not service_name:
                        continue
                    
                    # Skip self-monitoring
                    if service_name in ("darwin-brain", "darwin-blackboard-brain"):
                        continue
                    
                    count = event.count or 1
                    if service_name not in service_warnings:
                        service_warnings[service_name] = {"total_count": 0, "reasons": []}
                    service_warnings[service_name]["total_count"] += count
                    
                    reason_str = f"{reason}: {(event.message or '')[:120]} ({count}x)"
                    if reason_str not in service_warnings[service_name]["reasons"]:
                        service_warnings[service_name]["reasons"].append(reason_str)
                        
            except Exception as e:
                logger.debug(f"Failed to poll K8s warning events in {namespace}: {e}")
        
        # Update active warnings per service (used by _process_pod_metrics)
        new_warnings: dict[str, str] = {}
        for svc, info in service_warnings.items():
            if info["total_count"] >= self.WARNING_EVENT_THRESHOLD:
                new_warnings[svc] = "; ".join(info["reasons"][:3])
                if svc not in self._active_warnings:
                    logger.warning(
                        f"K8s Warning events for {svc} ({info['total_count']}x): "
                        f"{new_warnings[svc]}"
                    )
        self._active_warnings = new_warnings
    
    def _get_unhealthy_reason(self, pod) -> Optional[str]:
        """Extract unhealthy reason from pod container statuses."""
        statuses = (pod.status.container_statuses or []) + (pod.status.init_container_statuses or [])
        
        for cs in statuses:
            # Check waiting state (ImagePullBackOff, CrashLoopBackOff, etc.)
            if cs.state and cs.state.waiting:
                reason = cs.state.waiting.reason or ""
                if reason in self.UNHEALTHY_STATES:
                    return f"{reason}: {cs.state.waiting.message or cs.name}"
            
            # Check terminated state (OOMKilled, Error)
            if cs.state and cs.state.terminated:
                reason = cs.state.terminated.reason or ""
                if reason in self.UNHEALTHY_STATES:
                    return f"{reason}: exit_code={cs.state.terminated.exit_code} ({cs.name})"
            
            # Check lastState for recent OOMKills (container restarted but was OOMKilled)
            if cs.last_state and cs.last_state.terminated:
                reason = cs.last_state.terminated.reason or ""
                if reason == "OOMKilled" and (cs.restart_count or 0) > 2:
                    return f"{reason}: {cs.restart_count} restarts ({cs.name})"
        
        return None
    
    async def _process_pod_metrics(self, pod_metrics: dict) -> None:
        """
        Process metrics for a single pod.
        
        Args:
            pod_metrics: Pod metrics from metrics.k8s.io API
        """
        try:
            metadata = pod_metrics.get("metadata", {})
            pod_name = metadata.get("name", "")
            namespace = metadata.get("namespace", self.namespaces[0] if self.namespaces else "default")
            containers = pod_metrics.get("containers", [])
            
            if not containers or not pod_name:
                return
            
            # Get service name from pod labels
            service_name = await self._get_service_name(pod_name, namespace)
            if not service_name:
                logger.debug(f"Skipping pod {pod_name}: no service name mapping")
                return
            
            # Skip self-monitoring: Brain should never create anomaly events for itself
            if service_name in ("darwin-brain", "darwin-blackboard-brain"):
                return
            
            # Get resource limits for percentage calculation
            limits = await self._get_pod_limits(pod_name, namespace)
            
            # Aggregate metrics across all containers
            total_cpu_nano = 0
            total_memory_bytes = 0
            
            for container in containers:
                usage = container.get("usage", {})
                cpu_str = usage.get("cpu", "0")
                memory_str = usage.get("memory", "0")
                
                total_cpu_nano += self._parse_cpu(cpu_str)
                total_memory_bytes += self._parse_memory(memory_str)
            
            # Calculate percentages
            cpu_percent = 0.0
            memory_percent = 0.0
            
            if limits.get("cpu_limit"):
                # CPU limit is in millicores, usage is in nanocores
                cpu_millicores = total_cpu_nano / 1_000_000
                cpu_percent = (cpu_millicores / limits["cpu_limit"]) * 100
            
            if limits.get("memory_limit"):
                memory_percent = (total_memory_bytes / limits["memory_limit"]) * 100
            
            logger.debug(
                f"K8s metrics: {service_name} cpu={cpu_percent:.1f}% mem={memory_percent:.1f}%"
            )
            
            # Ensure service is registered in topology (so it appears in UI)
            # This enables K8s-only services (postgres, redis) to show up
            await self.blackboard.redis.sadd("darwin:services", service_name)
            
            # Update service metadata with version (if available)
            version = getattr(self, '_service_versions', {}).get(service_name, "k8s")
            await self.blackboard.update_service_metadata(
                name=service_name,
                version=version,
                cpu=cpu_percent,
                memory=memory_percent,
                error_rate=0.0,  # K8s observer doesn't track error rate
            )
            
            # Update Blackboard with K8s-observed metrics
            await self.blackboard.record_metric(
                service_name, "cpu", cpu_percent, source="kubernetes"
            )
            await self.blackboard.record_metric(
                service_name, "memory", memory_percent, source="kubernetes"
            )
            
            # Update replica count for this service
            replicas = await self.get_deployment_replicas(service_name, namespace)
            if replicas:
                await self.blackboard.update_service_replicas(
                    service_name,
                    replicas["ready"],
                    replicas["desired"],
                )
            
            # Trigger anomaly detection callback.
            # If active K8s Warning events exist for this service (probe failures,
            # image pull warnings), inject an elevated error_rate into the buffer
            # so Flash sees it alongside CPU/memory data.
            error_rate = 0.0
            if service_name in self._active_warnings:
                error_rate = 100.0  # Signal to Flash: something is wrong
                logger.debug(f"Injecting error_rate=100% for {service_name}: {self._active_warnings[service_name]}")
            
            if self.anomaly_callback:
                await self.anomaly_callback(
                    service_name, cpu_percent, memory_percent, "kubernetes",
                    error_rate=error_rate,
                )
                
        except Exception as e:
            logger.warning(f"Error processing pod metrics: {e}")
    
    async def _get_service_name(self, pod_name: str, namespace: str) -> Optional[str]:
        """
        Get service name from pod labels.
        
        Uses the 'app' label as the service name.
        Also caches version info for service metadata.
        """
        try:
            pod = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._core_api.read_namespaced_pod(pod_name, namespace)
            )
            
            labels = pod.metadata.labels or {}
            
            # Use 'app' label as service name (matches Darwin client naming)
            service_name = labels.get("app")
            if not service_name:
                # Fallback: use app.kubernetes.io/name
                service_name = labels.get("app.kubernetes.io/name")
            
            # Only register pods from darwin.io/monitored workloads.
            # Prevents ghost nodes from internal deps (e.g., postgres StatefulSet with app=postgres).
            if service_name and self._monitored_app_labels and service_name not in self._monitored_app_labels:
                return None
            
            if service_name:
                # Extract version from container image tag
                version = self._extract_version_from_pod(pod)
                if version:
                    # Cache version for this service
                    if not hasattr(self, '_service_versions'):
                        self._service_versions: dict[str, str] = {}
                    self._service_versions[service_name] = version
                    
                return service_name
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to get labels for pod {pod_name}: {e}")
            return None
    
    def _extract_version_from_pod(self, pod) -> Optional[str]:
        """Extract version from pod's container image tag."""
        try:
            containers = pod.spec.containers or []
            if not containers:
                return None
            
            # Use first container's image
            image = containers[0].image
            if not image:
                return None
            
            # Extract tag from image (format: registry/image:tag)
            if ':' in image:
                tag = image.split(':')[-1]
                # If tag looks like a commit hash (7+ hex chars), truncate
                if len(tag) >= 7 and all(c in '0123456789abcdef' for c in tag.lower()):
                    return tag[:7]
                return tag
            
            return "latest"
        except Exception:
            return None
    
    async def _get_pod_limits(self, pod_name: str, namespace: str) -> dict:
        """
        Get resource limits for a pod.
        
        Returns dict with cpu_limit (millicores) and memory_limit (bytes).
        """
        cache_key = self._pod_key(namespace, pod_name)
        # Check cache first
        if cache_key in self._pod_limits:
            return self._pod_limits[cache_key]
        
        limits = {"cpu_limit": 0, "memory_limit": 0}
        
        try:
            pod = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._core_api.read_namespaced_pod(pod_name, namespace)
            )
            
            # Sum limits across all containers
            for container in pod.spec.containers:
                if container.resources and container.resources.limits:
                    cpu_limit = container.resources.limits.get("cpu")
                    mem_limit = container.resources.limits.get("memory")
                    
                    if cpu_limit:
                        limits["cpu_limit"] += self._parse_cpu(cpu_limit) / 1_000_000
                    if mem_limit:
                        limits["memory_limit"] += self._parse_memory(mem_limit)
            
            # Cache the limits
            self._pod_limits[cache_key] = limits
            
        except Exception as e:
            logger.debug(f"Failed to get limits for pod {cache_key}: {e}")
        
        return limits
    
    @staticmethod
    def _parse_cpu(cpu_str: str) -> int:
        """
        Parse CPU string to nanocores.
        
        Examples: "100m" -> 100_000_000, "1" -> 1_000_000_000, "500n" -> 500
        """
        if not cpu_str:
            return 0
        
        cpu_str = str(cpu_str).strip()
        
        if cpu_str.endswith("n"):
            return int(cpu_str[:-1])
        elif cpu_str.endswith("u"):
            return int(float(cpu_str[:-1]) * 1_000)
        elif cpu_str.endswith("m"):
            return int(float(cpu_str[:-1]) * 1_000_000)
        else:
            # Assume cores
            return int(float(cpu_str) * 1_000_000_000)
    
    async def get_deployment_replicas(self, service: str, namespace: str) -> Optional[dict]:
        """
        Get ready/desired replicas for a service's deployment.

        Queries apps/v1 Deployment by label app={service}.

        Returns dict with {"ready": N, "desired": M} or None if not found.
        """
        if not self._k8s_available:
            return None

        try:
            # List deployments with app={service} label
            deployments = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._apps_api.list_namespaced_deployment(
                    namespace,
                    label_selector=f"app={service}"
                )
            )
            
            if not deployments.items:
                return None
            
            # Use first matching deployment
            deploy = deployments.items[0]
            return {
                "ready": deploy.status.ready_replicas or 0,
                "desired": deploy.spec.replicas or 1,
            }
            
        except Exception as e:
            logger.debug(f"Failed to get replicas for {service}: {e}")
            return None
    
    @staticmethod
    def _parse_memory(mem_str: str) -> int:
        """
        Parse memory string to bytes.
        
        Examples: "128Mi" -> 134217728, "1Gi" -> 1073741824, "1000Ki" -> 1024000
        """
        if not mem_str:
            return 0
        
        mem_str = str(mem_str).strip()
        
        multipliers = {
            "Ki": 1024,
            "Mi": 1024 ** 2,
            "Gi": 1024 ** 3,
            "Ti": 1024 ** 4,
            "K": 1000,
            "M": 1000 ** 2,
            "G": 1000 ** 3,
            "T": 1000 ** 4,
        }
        
        for suffix, mult in multipliers.items():
            if mem_str.endswith(suffix):
                return int(float(mem_str[:-len(suffix)]) * mult)
        
        # Assume bytes
        return int(mem_str)
