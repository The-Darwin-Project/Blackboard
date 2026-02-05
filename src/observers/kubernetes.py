# BlackBoard/src/observers/kubernetes.py
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

# Environment variable configuration
K8S_OBSERVER_ENABLED = os.getenv("K8S_OBSERVER_ENABLED", "false").lower() == "true"
K8S_OBSERVER_NAMESPACE = os.getenv("K8S_OBSERVER_NAMESPACE", "darwin")
K8S_OBSERVER_INTERVAL = int(os.getenv("K8S_OBSERVER_INTERVAL", "5"))  # Match darwin-client interval
K8S_OBSERVER_LABEL_SELECTOR = os.getenv("K8S_OBSERVER_LABEL_SELECTOR", "")


class KubernetesObserver:
    """
    Observes Kubernetes pod metrics and feeds them to the Blackboard.
    
    Uses the metrics.k8s.io API (metrics-server) to get CPU/memory usage.
    Maps pod names to service names using the 'app' label.
    """
    
    def __init__(
        self,
        blackboard: "BlackboardState",
        anomaly_callback: Optional[Callable[[str, float, float, str], Awaitable[None]]] = None,
        namespace: str = K8S_OBSERVER_NAMESPACE,
        interval: int = K8S_OBSERVER_INTERVAL,
        label_selector: str = K8S_OBSERVER_LABEL_SELECTOR,
    ):
        """
        Initialize the observer.
        
        Args:
            blackboard: Blackboard state for storing metrics
            anomaly_callback: Async callback(service, cpu, memory, source) for anomaly detection
            namespace: Kubernetes namespace to watch
            interval: Polling interval in seconds
            label_selector: Optional label selector to filter pods
        """
        self.blackboard = blackboard
        self.anomaly_callback = anomaly_callback
        self.namespace = namespace
        self.interval = interval
        self.label_selector = label_selector
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._k8s_available = False
        
        # Pod resource limits cache: {pod_name: {"cpu_limit": millicores, "memory_limit": bytes}}
        self._pod_limits: dict[str, dict] = {}
    
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
                await self._poll_metrics()
            except Exception as e:
                logger.error(f"Error polling K8s metrics: {e}")
            
            # Wait for next interval
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
    
    async def _poll_metrics(self) -> None:
        """Fetch pod metrics from metrics-server and process them."""
        if not self._k8s_available:
            return
        
        try:
            # Get pod metrics from metrics.k8s.io API
            # This is an async-wrapped sync call
            metrics = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._custom_api.list_namespaced_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    namespace=self.namespace,
                    plural="pods",
                    label_selector=self.label_selector or None,
                )
            )
            
            items = metrics.get("items", [])
            logger.debug(f"Got metrics for {len(items)} pods in {self.namespace}")
            
            for pod_metrics in items:
                await self._process_pod_metrics(pod_metrics)
                
        except Exception as e:
            # Don't crash on metrics-server errors (it might be temporarily unavailable)
            logger.warning(f"Failed to fetch pod metrics: {e}")
    
    async def _process_pod_metrics(self, pod_metrics: dict) -> None:
        """
        Process metrics for a single pod.
        
        Args:
            pod_metrics: Pod metrics from metrics.k8s.io API
        """
        try:
            pod_name = pod_metrics["metadata"]["name"]
            containers = pod_metrics.get("containers", [])
            
            if not containers:
                return
            
            # Get service name from pod labels
            service_name = await self._get_service_name(pod_name)
            if not service_name:
                logger.debug(f"Skipping pod {pod_name}: no service name mapping")
                return
            
            # Get resource limits for percentage calculation
            limits = await self._get_pod_limits(pod_name)
            
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
            replicas = await self.get_deployment_replicas(service_name)
            if replicas:
                await self.blackboard.update_service_replicas(
                    service_name,
                    replicas["ready"],
                    replicas["desired"],
                )
            
            # Trigger anomaly detection callback
            if self.anomaly_callback:
                await self.anomaly_callback(
                    service_name, cpu_percent, memory_percent, "kubernetes"
                )
                
        except Exception as e:
            logger.warning(f"Error processing pod metrics: {e}")
    
    async def _get_service_name(self, pod_name: str) -> Optional[str]:
        """
        Get service name from pod labels.
        
        Uses the 'app' label as the service name.
        Also caches version info for service metadata.
        """
        try:
            pod = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._core_api.read_namespaced_pod(pod_name, self.namespace)
            )
            
            labels = pod.metadata.labels or {}
            
            # Use 'app' label as service name (matches Darwin client naming)
            service_name = labels.get("app")
            if not service_name:
                # Fallback: use app.kubernetes.io/name
                service_name = labels.get("app.kubernetes.io/name")
            
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
    
    async def _get_pod_limits(self, pod_name: str) -> dict:
        """
        Get resource limits for a pod.
        
        Returns dict with cpu_limit (millicores) and memory_limit (bytes).
        """
        # Check cache first
        if pod_name in self._pod_limits:
            return self._pod_limits[pod_name]
        
        limits = {"cpu_limit": 0, "memory_limit": 0}
        
        try:
            pod = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._core_api.read_namespaced_pod(pod_name, self.namespace)
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
            self._pod_limits[pod_name] = limits
            
        except Exception as e:
            logger.debug(f"Failed to get limits for pod {pod_name}: {e}")
        
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
    
    async def get_deployment_replicas(self, service: str) -> Optional[dict]:
        """
        Get ready/desired replicas for a service's deployment.
        
        Queries apps/v1 Deployment by label app={service}.
        
        Returns dict with {"ready": N, "desired": M} or None if not found.
        """
        if not self._k8s_available:
            return None
        
        try:
            from kubernetes import client
            apps_api = client.AppsV1Api()
            
            # List deployments with app={service} label
            deployments = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: apps_api.list_namespaced_deployment(
                    self.namespace,
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
