# BlackBoard/src/agents/aligner.py
"""
Agent 1: The Aligner (The Listener)

Role: Truth Maintenance & Noise Filtering
Nature: Hybrid Daemon (Python + Vertex AI Flash for configuration)

The Aligner processes incoming telemetry and updates the Blackboard layers.
It can be configured via natural language (e.g., "Ignore errors for 1h").

CLOSED-LOOP: The Aligner detects anomalies and triggers the Architect
for autonomous analysis, completing the observation → strategy loop.

AIR GAP: This module may import vertexai (for Flash model) but NOT kubernetes or git.
"""
# NOTE: Aligner keeps vertexai Flash for filter configuration
# (independent of Brain's Vertex AI Pro). Do NOT remove vertexai imports.
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Optional

# AIR GAP ENFORCEMENT: Only these imports allowed
# import kubernetes  # FORBIDDEN
# import git  # FORBIDDEN

from ..models import EventType

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# Anomaly thresholds (configurable via env)
CPU_THRESHOLD = float(os.getenv("ALIGNER_CPU_THRESHOLD", "80.0"))
MEMORY_THRESHOLD = float(os.getenv("ALIGNER_MEMORY_THRESHOLD", "85.0"))
ERROR_RATE_THRESHOLD = float(os.getenv("ALIGNER_ERROR_RATE_THRESHOLD", "5.0"))
# Cooldown between anomaly events for same service (seconds)
ANOMALY_COOLDOWN = int(os.getenv("ALIGNER_ANOMALY_COOLDOWN", "60"))

# Scale-down thresholds: if BOTH cpu and memory are below these AND replicas > 1
SCALE_DOWN_CPU_THRESHOLD = float(os.getenv("ALIGNER_SCALE_DOWN_CPU", "30.0"))
SCALE_DOWN_MEMORY_THRESHOLD = float(os.getenv("ALIGNER_SCALE_DOWN_MEMORY", "40.0"))
# Cooldown between scale-down evaluations per service (seconds)
SCALE_DOWN_COOLDOWN = int(os.getenv("ALIGNER_SCALE_DOWN_COOLDOWN", "300"))


class FilterRule:
    """A filter rule for noise reduction."""
    
    def __init__(
        self,
        name: str,
        ignore_errors: bool = False,
        ignore_metrics: bool = False,
        until: Optional[float] = None,
        service: Optional[str] = None,
    ):
        self.name = name
        self.ignore_errors = ignore_errors
        self.ignore_metrics = ignore_metrics
        self.until = until  # Unix timestamp when rule expires
        self.service = service  # Optional: apply only to this service
    
    def is_active(self) -> bool:
        """Check if rule is still active."""
        if self.until is None:
            return True
        return time.time() < self.until
    
    def applies_to(self, service: str) -> bool:
        """Check if rule applies to a service."""
        if self.service is None:
            return True
        return self.service == service


class Aligner:
    """
    The Aligner agent - processes telemetry and maintains truth.
    
    Responsibilities:
    - Normalize and validate incoming telemetry
    - Apply filter rules for noise reduction
    - Update Blackboard state layers
    - Detect anomalies and trigger Architect (closed-loop)
    - Configurable via natural language (Vertex AI Flash)
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self.filter_rules: list[FilterRule] = []
        self._model = None
        
        # Check if Vertex AI is configured
        self.vertex_enabled = bool(os.getenv("GCP_PROJECT"))
        
        # Closed-loop state tracking
        self._known_services: set[str] = set()
        self._service_versions: dict[str, str] = {}  # service -> last known version
        self._anomaly_state: dict[str, dict] = {}  # service -> {type, timestamp}
        self._scale_down_last_check: dict[str, float] = {}  # service -> last evaluation timestamp
    
    async def _get_model(self):
        """Lazy-load Vertex AI Flash model for configuration parsing."""
        if self._model is None and self.vertex_enabled:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                
                project = os.getenv("GCP_PROJECT")
                location = os.getenv("GCP_LOCATION", "us-central1")
                model_name = os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview")
                
                vertexai.init(project=project, location=location)
                self._model = GenerativeModel(model_name)
                
                logger.info(f"Aligner initialized with Vertex AI Flash: {model_name}")
            except Exception as e:
                logger.warning(f"Vertex AI not available for Aligner: {e}")
                self._model = None
        
        return self._model
    
    async def configure_filter(self, instruction: str) -> Optional[FilterRule]:
        """
        Configure a filter rule from natural language instruction.
        
        Examples:
        - "Ignore errors for 1 hour"
        - "Ignore metrics from inventory-api for 30 minutes"
        - "Stop filtering errors"
        
        Uses Vertex AI Flash to parse the instruction into a FilterRule.
        """
        model = await self._get_model()
        
        if model is None:
            # Fallback: simple parsing without AI
            return self._parse_simple_filter(instruction)
        
        try:
            prompt = f"""
            Parse this filter instruction into JSON:
            "{instruction}"
            
            Return ONLY valid JSON with these fields:
            - name: string (description of the rule)
            - ignore_errors: boolean (true if ignoring error rate)
            - ignore_metrics: boolean (true if ignoring all metrics)
            - duration_minutes: integer (how long the rule should last, 0 for permanent)
            - service: string or null (specific service to apply to, or null for all)
            
            Example response:
            {{"name": "Ignore errors for maintenance", "ignore_errors": true, "ignore_metrics": false, "duration_minutes": 60, "service": null}}
            """
            
            response = await model.generate_content_async(prompt)
            
            import json
            data = json.loads(response.text.strip())
            
            until = None
            if data.get("duration_minutes", 0) > 0:
                until = time.time() + (data["duration_minutes"] * 60)
            
            rule = FilterRule(
                name=data.get("name", instruction),
                ignore_errors=data.get("ignore_errors", False),
                ignore_metrics=data.get("ignore_metrics", False),
                until=until,
                service=data.get("service"),
            )
            
            self.filter_rules.append(rule)
            logger.info(f"Filter rule added: {rule.name}")
            
            return rule
        
        except Exception as e:
            logger.error(f"Failed to parse filter instruction: {e}")
            return None
    
    def _parse_simple_filter(self, instruction: str) -> Optional[FilterRule]:
        """Simple fallback parsing without AI."""
        instruction_lower = instruction.lower()
        
        # Parse duration
        duration_minutes = 60  # Default 1 hour
        if "30 min" in instruction_lower:
            duration_minutes = 30
        elif "1 hour" in instruction_lower or "1h" in instruction_lower:
            duration_minutes = 60
        elif "2 hour" in instruction_lower or "2h" in instruction_lower:
            duration_minutes = 120
        
        # Parse what to ignore
        ignore_errors = "error" in instruction_lower
        ignore_metrics = "metric" in instruction_lower
        
        if not ignore_errors and not ignore_metrics:
            return None
        
        until = time.time() + (duration_minutes * 60)
        
        rule = FilterRule(
            name=instruction,
            ignore_errors=ignore_errors,
            ignore_metrics=ignore_metrics,
            until=until,
        )
        
        self.filter_rules.append(rule)
        logger.info(f"Filter rule added (simple parse): {rule.name}")
        
        return rule
    
    def clear_expired_rules(self) -> int:
        """Remove expired filter rules. Returns count of removed rules."""
        original_count = len(self.filter_rules)
        self.filter_rules = [r for r in self.filter_rules if r.is_active()]
        removed = original_count - len(self.filter_rules)
        
        if removed > 0:
            logger.info(f"Cleared {removed} expired filter rules")
        
        return removed
    
    def should_filter(self, service: str, is_error: bool = False) -> bool:
        """Check if data should be filtered based on active rules."""
        self.clear_expired_rules()
        
        for rule in self.filter_rules:
            if not rule.applies_to(service):
                continue
            
            if is_error and rule.ignore_errors:
                return True
            
            if rule.ignore_metrics:
                return True
        
        return False
    
    async def process_telemetry(self, payload) -> bool:
        """
        Process incoming telemetry through the Aligner.
        
        Implements closed-loop:
        1. Detect new services → emit SERVICE_DISCOVERED
        2. Check thresholds → emit anomaly events
        3. Trigger Architect analysis on anomalies
        
        Returns True if telemetry was processed, False if filtered.
        """
        from ..models import TelemetryPayload
        
        # Type check
        if not isinstance(payload, TelemetryPayload):
            logger.warning(f"Invalid telemetry payload type: {type(payload)}")
            return False
        
        # Check filter rules
        is_error = payload.metrics.error_rate > 0
        if self.should_filter(payload.service, is_error):
            logger.debug(f"Telemetry from {payload.service} filtered by active rule")
            return False
        
        # === CLOSED-LOOP: Service Discovery ===
        if payload.service not in self._known_services:
            self._known_services.add(payload.service)
            self._service_versions[payload.service] = payload.version
            await self.blackboard.record_event(
                EventType.SERVICE_DISCOVERED,
                {"service": payload.service, "version": payload.version},
                narrative=f"I discovered a new service '{payload.service}' (v{payload.version}) reporting telemetry.",
            )
            logger.info(f"New service discovered: {payload.service} v{payload.version}")
        
        # === CLOSED-LOOP: Version Drift Detection ===
        last_version = self._service_versions.get(payload.service)
        if last_version and last_version != payload.version:
            await self.blackboard.record_event(
                EventType.DEPLOYMENT_DETECTED,
                {
                    "service": payload.service,
                    "old_version": last_version,
                    "new_version": payload.version,
                },
                narrative=f"Detected deployment: {payload.service} updated from v{last_version} to v{payload.version}.",
            )
            logger.info(
                f"DEPLOYMENT DETECTED: {payload.service} "
                f"v{last_version} → v{payload.version}"
            )
            self._service_versions[payload.service] = payload.version
        
        # Delegate to Blackboard for storage
        await self.blackboard.process_telemetry(payload)
        
        # === CLOSED-LOOP: Anomaly Detection ===
        await self._check_anomalies(payload)
        
        # === CLOSED-LOOP: Over-Provisioning Check (HPA scale-down) ===
        await self._check_over_provisioned(payload)
        
        return True
    
    async def _check_anomalies(self, payload) -> None:
        """
        Check for anomalies and trigger Architect if needed.
        
        Implements cooldown to avoid event spam.
        """
        service = payload.service
        now = time.time()
        
        # Get or create anomaly state for this service
        if service not in self._anomaly_state:
            self._anomaly_state[service] = {"high_cpu": 0, "high_memory": 0, "high_error": 0, "active": set()}
        
        state = self._anomaly_state[service]
        
        # Check CPU threshold
        if payload.metrics.cpu >= CPU_THRESHOLD:
            if "high_cpu" not in state["active"]:
                # New anomaly detected
                if now - state["high_cpu"] > ANOMALY_COOLDOWN:
                    state["high_cpu"] = now
                    state["active"].add("high_cpu")
                    
                    await self.blackboard.record_event(
                        EventType.HIGH_CPU_DETECTED,
                        {"service": service, "cpu": payload.metrics.cpu, "threshold": CPU_THRESHOLD},
                        narrative=f"Warning: {service} CPU usage ({payload.metrics.cpu:.1f}%) exceeds the {CPU_THRESHOLD:.0f}% threshold. Escalating to Architect for analysis.",
                    )
                    logger.warning(f"HIGH CPU detected: {service} at {payload.metrics.cpu:.1f}%")
                    
                    # Trigger Architect analysis
                    await self._trigger_architect(service, "high_cpu")
        else:
            # CPU back to normal
            if "high_cpu" in state["active"]:
                state["active"].remove("high_cpu")
                await self.blackboard.record_event(
                    EventType.ANOMALY_RESOLVED,
                    {"service": service, "anomaly": "high_cpu", "cpu": payload.metrics.cpu},
                    narrative=f"Good news: The high CPU issue on {service} has returned to normal levels ({payload.metrics.cpu:.1f}%).",
                )
                logger.info(f"CPU anomaly resolved: {service} now at {payload.metrics.cpu:.1f}%")
                # Evaluate scale-down (HPA-like behavior)
                await self._trigger_architect(service, "anomaly_resolved_cpu")
        
        # Check Memory threshold
        if payload.metrics.memory >= MEMORY_THRESHOLD:
            if "high_memory" not in state["active"]:
                if now - state["high_memory"] > ANOMALY_COOLDOWN:
                    state["high_memory"] = now
                    state["active"].add("high_memory")
                    
                    await self.blackboard.record_event(
                        EventType.HIGH_MEMORY_DETECTED,
                        {"service": service, "memory": payload.metrics.memory, "threshold": MEMORY_THRESHOLD},
                        narrative=f"Warning: {service} memory usage ({payload.metrics.memory:.1f}%) exceeds the {MEMORY_THRESHOLD:.0f}% threshold.",
                    )
                    logger.warning(f"HIGH MEMORY detected: {service} at {payload.metrics.memory:.1f}%")
                    
                    # Trigger Architect analysis
                    await self._trigger_architect(service, "high_memory")
        else:
            # Memory back to normal
            if "high_memory" in state["active"]:
                state["active"].remove("high_memory")
                await self.blackboard.record_event(
                    EventType.ANOMALY_RESOLVED,
                    {"service": service, "anomaly": "high_memory", "memory": payload.metrics.memory},
                    narrative=f"Good news: The high memory issue on {service} has returned to normal levels ({payload.metrics.memory:.1f}%).",
                )
                logger.info(f"Memory anomaly resolved: {service} now at {payload.metrics.memory:.1f}%")
                # Evaluate scale-down (HPA-like behavior)
                await self._trigger_architect(service, "anomaly_resolved_memory")
        
        # Check Error Rate threshold
        if payload.metrics.error_rate >= ERROR_RATE_THRESHOLD:
            if "high_error" not in state["active"]:
                if now - state["high_error"] > ANOMALY_COOLDOWN:
                    state["high_error"] = now
                    state["active"].add("high_error")
                    
                    await self.blackboard.record_event(
                        EventType.HIGH_ERROR_RATE_DETECTED,
                        {"service": service, "error_rate": payload.metrics.error_rate, "threshold": ERROR_RATE_THRESHOLD},
                        narrative=f"Alert: {service} error rate ({payload.metrics.error_rate:.2f}%) is critically high! Immediate attention required.",
                    )
                    logger.warning(f"HIGH ERROR RATE detected: {service} at {payload.metrics.error_rate:.2f}%")
                    
                    # Trigger Architect analysis
                    await self._trigger_architect(service, "high_error_rate")
        else:
            # Error rate back to normal
            if "high_error" in state["active"]:
                state["active"].remove("high_error")
                await self.blackboard.record_event(
                    EventType.ANOMALY_RESOLVED,
                    {"service": service, "anomaly": "high_error_rate", "error_rate": payload.metrics.error_rate},
                    narrative=f"Good news: The high error rate issue on {service} has returned to normal levels ({payload.metrics.error_rate:.2f}%).",
                )
                logger.info(f"Error rate anomaly resolved: {service} now at {payload.metrics.error_rate:.2f}%")
    
    async def _check_over_provisioned(self, payload) -> None:
        """
        Periodic check: is a service over-provisioned (replicas > 1 but low usage)?
        
        HPA-like behavior: if CPU and memory are both well below threshold
        and the service has more than 1 replica, ask the Architect to evaluate
        scaling down. Uses cooldown to avoid spamming.
        """
        service = payload.service
        now = time.time()
        
        # Cooldown: don't check too frequently per service
        last_check = self._scale_down_last_check.get(service, 0)
        if now - last_check < SCALE_DOWN_COOLDOWN:
            return
        
        # Only evaluate if no active anomalies for this service
        state = self._anomaly_state.get(service, {})
        if state.get("active"):
            return
        
        # Check if service has more than 1 replica
        svc = await self.blackboard.get_service(service)
        if not svc or not svc.replicas_desired or svc.replicas_desired <= 1:
            return
        
        # Check if both CPU and memory are well below thresholds
        cpu = payload.metrics.cpu
        memory = payload.metrics.memory
        
        if cpu < SCALE_DOWN_CPU_THRESHOLD and memory < SCALE_DOWN_MEMORY_THRESHOLD:
            self._scale_down_last_check[service] = now
            
            logger.info(
                f"Over-provisioned: {service} has {svc.replicas_desired} replicas "
                f"but CPU={cpu:.1f}% (<{SCALE_DOWN_CPU_THRESHOLD}%) "
                f"MEM={memory:.1f}% (<{SCALE_DOWN_MEMORY_THRESHOLD}%)"
            )
            
            await self.blackboard.record_event(
                EventType.ANOMALY_RESOLVED,
                {
                    "service": service,
                    "anomaly": "over_provisioned",
                    "cpu": cpu,
                    "memory": memory,
                    "replicas": svc.replicas_desired,
                },
                narrative=(
                    f"Service {service} appears over-provisioned: "
                    f"{svc.replicas_desired} replicas running with only "
                    f"CPU={cpu:.1f}% and MEM={memory:.1f}% usage. "
                    f"Asking Architect to evaluate scale-down."
                ),
            )
            
            await self._trigger_architect(service, "over_provisioned")
    
    async def _trigger_architect(self, service: str, anomaly_type: str) -> None:
        """
        Create an event for the Brain to process -- with deduplication.
        
        Before creating a new event, checks if an active event already exists
        for the same service. If so, skips creation (the existing event is
        already being handled by the Brain/agents).
        """
        # Dedup: check if an active event already exists for this service
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            existing = await self.blackboard.get_event(eid)
            if existing and existing.service == service and existing.status.value in ("new", "active", "deferred"):
                logger.info(
                    f"Skipping event creation for {service} ({anomaly_type}) "
                    f"-- active event {eid} already exists (status: {existing.status.value})"
                )
                return

        # Get current metrics for evidence
        svc = await self.blackboard.get_service(service)
        evidence_parts = [f"Service: {service}", f"Anomaly: {anomaly_type}"]
        if svc:
            evidence_parts.append(f"CPU: {svc.metrics.cpu:.1f}%")
            evidence_parts.append(f"Memory: {svc.metrics.memory:.1f}%")
            evidence_parts.append(f"Error Rate: {svc.metrics.error_rate:.2f}%")
            if svc.replicas_ready is not None:
                evidence_parts.append(f"Replicas: {svc.replicas_ready}/{svc.replicas_desired}")
        evidence = ", ".join(evidence_parts)
        
        await self.blackboard.create_event(
            source="aligner",
            service=service,
            reason=anomaly_type.replace("_", " "),
            evidence=evidence,
        )
        logger.info(f"Created event for {service} ({anomaly_type})")
    
    async def check_anomalies_for_service(
        self,
        service: str,
        cpu: float,
        memory: float,
        source: str = "kubernetes",
    ) -> None:
        """
        Check for anomalies from external metrics (e.g., Kubernetes observer).
        
        This is called by the KubernetesObserver with metrics from metrics-server.
        Reuses the same threshold logic as _check_anomalies but for external sources.
        
        Args:
            service: Service name
            cpu: CPU usage percentage
            memory: Memory usage percentage
            source: Metrics source (for event metadata)
        """
        now = time.time()
        
        # Get or create anomaly state for this service
        if service not in self._anomaly_state:
            self._anomaly_state[service] = {"high_cpu": 0, "high_memory": 0, "high_error": 0, "active": set()}
        
        state = self._anomaly_state[service]
        
        # Check CPU threshold
        if cpu >= CPU_THRESHOLD:
            if "high_cpu" not in state["active"]:
                if now - state["high_cpu"] > ANOMALY_COOLDOWN:
                    state["high_cpu"] = now
                    state["active"].add("high_cpu")
                    
                    await self.blackboard.record_event(
                        EventType.HIGH_CPU_DETECTED,
                        {"service": service, "cpu": cpu, "threshold": CPU_THRESHOLD, "source": source},
                        narrative=f"Warning: {service} CPU usage ({cpu:.1f}%) exceeds the {CPU_THRESHOLD:.0f}% threshold. Escalating to Architect for analysis.",
                    )
                    logger.warning(f"HIGH CPU detected ({source}): {service} at {cpu:.1f}%")
                    
                    await self._trigger_architect(service, "high_cpu")
        else:
            if "high_cpu" in state["active"]:
                state["active"].remove("high_cpu")
                await self.blackboard.record_event(
                    EventType.ANOMALY_RESOLVED,
                    {"service": service, "anomaly": "high_cpu", "cpu": cpu, "source": source},
                    narrative=f"Good news: The high CPU issue on {service} has returned to normal levels ({cpu:.1f}%).",
                )
                logger.info(f"CPU anomaly resolved ({source}): {service} now at {cpu:.1f}%")
                # Evaluate scale-down (HPA-like behavior)
                await self._trigger_architect(service, "anomaly_resolved_cpu")
        
        # Check Memory threshold
        if memory >= MEMORY_THRESHOLD:
            if "high_memory" not in state["active"]:
                if now - state["high_memory"] > ANOMALY_COOLDOWN:
                    state["high_memory"] = now
                    state["active"].add("high_memory")
                    
                    await self.blackboard.record_event(
                        EventType.HIGH_MEMORY_DETECTED,
                        {"service": service, "memory": memory, "threshold": MEMORY_THRESHOLD, "source": source},
                        narrative=f"Warning: {service} memory usage ({memory:.1f}%) exceeds the {MEMORY_THRESHOLD:.0f}% threshold.",
                    )
                    logger.warning(f"HIGH MEMORY detected ({source}): {service} at {memory:.1f}%")
                    
                    await self._trigger_architect(service, "high_memory")
        else:
            if "high_memory" in state["active"]:
                state["active"].remove("high_memory")
                await self.blackboard.record_event(
                    EventType.ANOMALY_RESOLVED,
                    {"service": service, "anomaly": "high_memory", "memory": memory, "source": source},
                    narrative=f"Good news: The high memory issue on {service} has returned to normal levels ({memory:.1f}%).",
                )
                logger.info(f"Memory anomaly resolved ({source}): {service} now at {memory:.1f}%")
                # Evaluate scale-down (HPA-like behavior)
                await self._trigger_architect(service, "anomaly_resolved_memory")
    
    async def handle_unhealthy_pod(self, service: str, pod_name: str, reason: str) -> None:
        """
        Handle unhealthy pod detected by K8s observer.
        
        Called for ImagePullBackOff, CrashLoopBackOff, OOMKilled, etc.
        Records event and triggers investigation + Architect analysis.
        """
        # Map pod state reasons to anomaly types
        if "OOMKilled" in reason:
            anomaly_type = "oom_killed"
        elif "ImagePull" in reason:
            anomaly_type = "image_pull_error"
        elif "CrashLoop" in reason:
            anomaly_type = "crash_loop"
        else:
            anomaly_type = "pod_unhealthy"
        
        await self.blackboard.record_event(
            EventType.HIGH_ERROR_RATE_DETECTED,
            {
                "service": service,
                "pod": pod_name,
                "reason": reason,
                "anomaly_type": anomaly_type,
            },
            narrative=f"Detected unhealthy pod {pod_name} for service {service}: {reason}. Triggering investigation.",
        )
        logger.warning(f"Unhealthy pod detected: {pod_name} ({service}): {reason}")
        
        await self._trigger_architect(service, anomaly_type)
    
    async def check_active_verifications(self) -> None:
        """Scan active events for verification requests from Brain."""
        active_ids = await self.blackboard.get_active_events()
        for event_id in active_ids:
            event = await self.blackboard.get_event(event_id)
            if not event or not event.conversation:
                continue
            last_turn = event.conversation[-1]
            if last_turn.waitingFor == "aligner" and last_turn.actor == "brain":
                # Check if the condition is met
                svc = await self.blackboard.get_service(event.service)
                if svc:
                    from ..models import ConversationTurn
                    confirm_turn = ConversationTurn(
                        turn=len(event.conversation) + 1,
                        actor="aligner",
                        action="confirm",
                        evidence=(
                            f"Service: {event.service}, "
                            f"CPU: {svc.metrics.cpu:.1f}%, "
                            f"Memory: {svc.metrics.memory:.1f}%, "
                            f"Replicas: {svc.replicas_ready}/{svc.replicas_desired}"
                            if svc.replicas_ready is not None else
                            f"Service: {event.service}, CPU: {svc.metrics.cpu:.1f}%"
                        ),
                    )
                    await self.blackboard.append_turn(event_id, confirm_turn)
                    logger.info(f"Aligner confirmed verification for event {event_id}")
    
    async def check_state(self, service: str) -> dict:
        """Return current state of a service for Brain re-trigger."""
        svc = await self.blackboard.get_service(service)
        if not svc:
            return {"service": service, "status": "not_found"}
        return {
            "service": service,
            "cpu": svc.metrics.cpu,
            "memory": svc.metrics.memory,
            "error_rate": svc.metrics.error_rate,
            "replicas_ready": svc.replicas_ready,
            "replicas_desired": svc.replicas_desired,
            "version": svc.version,
        }
    
    def get_active_rules(self) -> list[dict]:
        """Get list of active filter rules."""
        self.clear_expired_rules()
        
        return [
            {
                "name": rule.name,
                "ignore_errors": rule.ignore_errors,
                "ignore_metrics": rule.ignore_metrics,
                "service": rule.service,
                "expires_in_seconds": (rule.until - time.time()) if rule.until else None,
            }
            for rule in self.filter_rules
        ]
