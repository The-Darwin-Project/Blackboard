# BlackBoard/src/agents/aligner.py
"""
Agent 1: The Aligner (The Listener)

Role: Truth Maintenance & Noise Filtering
Nature: Hybrid Daemon (Python + Gemini Flash via google-genai for configuration)

The Aligner processes incoming telemetry and updates the Blackboard layers.
It can be configured via natural language (e.g., "Ignore errors for 1h").

CLOSED-LOOP: The Aligner detects anomalies and triggers the Architect
for autonomous analysis, completing the observation → strategy loop.

AIR GAP: This module may import google-genai (for Flash model) but NOT kubernetes or git.
"""
# NOTE: Aligner uses google-genai SDK for Flash model (filter config, signal analysis).
# Independent of Brain's Pro model. Do NOT remove google.genai imports.
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

# Anomaly thresholds (configurable via env) -- used by Flash LLM prompt context
CPU_THRESHOLD = float(os.getenv("ALIGNER_CPU_THRESHOLD", "80.0"))
MEMORY_THRESHOLD = float(os.getenv("ALIGNER_MEMORY_THRESHOLD", "85.0"))
ERROR_RATE_THRESHOLD = float(os.getenv("ALIGNER_ERROR_RATE_THRESHOLD", "5.0"))


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
    - Configurable via natural language (Gemini Flash via google-genai)
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self.filter_rules: list[FilterRule] = []
        self._client = None
        self._model_name = None
        
        # Check if google-genai is configured
        self.vertex_enabled = bool(os.getenv("GCP_PROJECT"))
        
        # Closed-loop state tracking
        self._known_services: set[str] = set()
        self._service_versions: dict[str, str] = {}  # service -> last known version
        # Version observation buffer for LLM-based drift detection
        self._version_buffer: dict[str, list[tuple[float, str]]] = {}  # service -> [(timestamp, version)]
        self._version_analysis_pending: dict[str, bool] = {}  # service -> analysis scheduled
        # Unified metrics signal buffer for LLM-based anomaly analysis
        # Buffer is RETAINED across analysis windows (60s trim handles old entries).
        # This gives Flash continuity: each analysis sees up to 60s of data, not
        # just the last 30s, so sustained patterns aren't misclassified as transient.
        self._metrics_buffer: dict[str, list[dict]] = {}  # service -> [{timestamp, cpu, memory, error_rate, replicas}]
        self._metrics_analysis_pending: dict[str, bool] = {}  # service -> analysis scheduled
        self._last_analysis_time: dict[str, float] = {}  # service -> last analysis trigger time
        # Event creation cooldown -- prevents rapid event churn after close/resolve cycles
        self._last_event_creation: dict[str, float] = {}  # service -> last event creation timestamp
    
    async def _get_client(self):
        """Lazy-load google-genai Client for Aligner LLM calls."""
        if self._client is None and self.vertex_enabled:
            try:
                from google import genai
                
                project = os.getenv("GCP_PROJECT")
                location = os.getenv("GCP_LOCATION", "us-central1")
                self._model_name = os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview")
                
                self._client = genai.Client(
                    vertexai=True,
                    project=project,
                    location=location,
                )
                
                logger.info(f"Aligner initialized with google-genai Flash: {self._model_name}")
            except Exception as e:
                logger.warning(f"google-genai not available for Aligner: {e}")
                self._client = None
        
        return self._client
    
    async def configure_filter(self, instruction: str) -> Optional[FilterRule]:
        """
        Configure a filter rule from natural language instruction.
        
        Examples:
        - "Ignore errors for 1 hour"
        - "Ignore metrics from inventory-api for 30 minutes"
        - "Stop filtering errors"
        
        Uses Gemini Flash (via google-genai) to parse the instruction into a FilterRule.
        """
        client = await self._get_client()
        
        if client is None:
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
            
            response = await client.aio.models.generate_content(
                model=self._model_name, contents=prompt,
            )
            
            import json
            if not response.text:
                logger.warning("Aligner LLM returned empty response for filter config")
                return self._parse_simple_filter(instruction)
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
        
        # === CLOSED-LOOP: Version Drift Detection (LLM-assisted) ===
        # Buffer version observations over 30s window, then ask Flash to interpret
        # the pattern (rolling update? deployment? rollback?) before firing events.
        last_version = self._service_versions.get(payload.service)
        now = time.time()
        if last_version and last_version != payload.version:
            # Version changed -- buffer the observation
            if payload.service not in self._version_buffer:
                self._version_buffer[payload.service] = []
            self._version_buffer[payload.service].append((now, payload.version))
            # Also record the previous version if buffer is fresh
            if len(self._version_buffer[payload.service]) == 1:
                self._version_buffer[payload.service].insert(0, (now - 1, last_version))

        # Check buffer on EVERY telemetry cycle (not just on version change).
        # This ensures fast deployments that stabilize quickly still get analyzed.
        if payload.service in self._version_buffer and not self._version_analysis_pending.get(payload.service):
            buffer = self._version_buffer[payload.service]
            buffer_age = now - buffer[0][0]
            if buffer_age >= 30:
                self._version_analysis_pending[payload.service] = True
                await self._analyze_version_drift(payload.service)

        self._service_versions[payload.service] = payload.version
        
        # Delegate to Blackboard for storage
        await self.blackboard.process_telemetry(payload)
        
        # === CLOSED-LOOP: Anomaly Detection (LLM-assisted via Flash) ===
        await self._check_anomalies(payload)
        
        return True
    
    async def _analyze_version_drift(self, service: str) -> None:
        """
        Use Gemini Flash (via google-genai) to interpret version observation patterns.
        
        Instead of hardcoded cooldowns, ask the LLM to reason about what's happening:
        rolling update, completed deployment, rollback, or noise.
        """
        buffer = self._version_buffer.get(service, [])
        if not buffer:
            self._version_analysis_pending[service] = False
            return

        # Format observations for Flash
        observations = "\n".join(
            f"  {time.strftime('%H:%M:%S', time.localtime(ts))}: {ver}"
            for ts, ver in buffer
        )
        versions_seen = list(set(ver for _, ver in buffer))

        try:
            client = await self._get_client()
            if client:
                prompt = (
                    f"Service '{service}' reported these version observations over the last 30+ seconds:\n"
                    f"{observations}\n\n"
                    f"Unique versions seen: {versions_seen}\n\n"
                    f"What is happening? Respond with EXACTLY one of these words on the first line:\n"
                    f"- ROLLING_UPDATE (if versions are alternating -- pods with different versions during rollout)\n"
                    f"- DEPLOYMENT (if version changed and stabilized to a new version)\n"
                    f"- ROLLBACK (if version went to a new one then back to the old)\n"
                    f"- NOISE (if unclear or irrelevant)\n\n"
                    f"Then on the second line, a brief explanation."
                )

                response = await client.aio.models.generate_content(
                    model=self._model_name, contents=prompt,
                )
                result_text = response.text.strip() if response.text else "NOISE"
                first_line = result_text.split("\n")[0].strip().upper()

                logger.info(f"Flash version analysis for {service}: {first_line}")

                if first_line == "DEPLOYMENT":
                    # Stable deployment -- fire event with the latest version
                    latest_version = buffer[-1][1]
                    old_version = buffer[0][1]
                    await self.blackboard.record_event(
                        EventType.DEPLOYMENT_DETECTED,
                        {"service": service, "old_version": old_version, "new_version": latest_version},
                        narrative=f"Deployment confirmed: {service} updated from v{old_version} to v{latest_version}.",
                    )
                    logger.info(f"DEPLOYMENT CONFIRMED (Flash): {service} v{old_version} → v{latest_version}")

                elif first_line == "ROLLING_UPDATE":
                    # Rolling update in progress -- log but don't fire event yet
                    logger.info(f"Rolling update detected (Flash): {service} -- versions {versions_seen}, waiting for convergence")
                    # Don't fire event -- will re-analyze on next window

                elif first_line == "ROLLBACK":
                    old_version = buffer[0][1]
                    latest_version = buffer[-1][1]
                    await self.blackboard.record_event(
                        EventType.DEPLOYMENT_DETECTED,
                        {"service": service, "old_version": old_version, "new_version": latest_version},
                        narrative=f"Rollback detected: {service} reverted from v{old_version} to v{latest_version}.",
                    )
                    logger.info(f"ROLLBACK DETECTED (Flash): {service} v{old_version} → v{latest_version}")

                else:
                    logger.debug(f"Version drift noise for {service}: {first_line}")

            else:
                # Flash not available -- fallback to simple: if only one version in last observations, it's stable
                if len(versions_seen) == 1:
                    old_version = self._service_versions.get(service, "unknown")
                    await self.blackboard.record_event(
                        EventType.DEPLOYMENT_DETECTED,
                        {"service": service, "old_version": old_version, "new_version": versions_seen[0]},
                        narrative=f"Detected deployment: {service} updated to v{versions_seen[0]}.",
                    )
                else:
                    logger.info(f"Version drift for {service}: mixed versions {versions_seen}, likely rolling update")

        except Exception as e:
            logger.error(f"Version drift analysis failed for {service}: {e}")

        finally:
            # Clear buffer and reset pending flag
            self._version_buffer.pop(service, None)
            self._version_analysis_pending[service] = False
    
    def _buffer_metric(self, service: str, now: float, cpu: float, memory: float,
                       error_rate: float, replicas: str) -> None:
        """
        Add a metric observation to the buffer, merging with existing entries
        in the same 5s time bucket (max wins).
        
        Both self-reported telemetry (app-level CPU) and K8s observer (container-
        level CPU) feed this buffer. An app may self-report 0.2% CPU while the
        container is at 100% limit. By merging into time buckets with max(),
        the higher (more accurate) reading wins, preventing Flash from seeing
        a mix of low app values and high K8s values as "transient spikes."
        """
        if service not in self._metrics_buffer:
            self._metrics_buffer[service] = []

        # Bucket key: round timestamp to nearest 5s
        bucket_ts = round(now / 5) * 5
        buffer = self._metrics_buffer[service]

        # Check if a bucket already exists for this time window
        for entry in buffer:
            if abs(entry["timestamp"] - bucket_ts) < 3:  # Within same bucket
                # Merge: max of each metric (highest reading wins)
                entry["cpu"] = max(entry["cpu"], cpu)
                entry["memory"] = max(entry["memory"], memory)
                entry["error_rate"] = max(entry["error_rate"], error_rate)
                if replicas != "unknown":
                    entry["replicas"] = replicas
                return

        # New bucket
        buffer.append({
            "timestamp": bucket_ts,
            "cpu": cpu,
            "memory": memory,
            "error_rate": error_rate,
            "replicas": replicas,
        })

    async def _check_anomalies(self, payload) -> None:
        """
        Buffer metrics observations and use Flash to analyze patterns.
        
        Instead of firing on every threshold breach, collects data continuously
        then asks Flash every 30s: is this a sustained issue, a transient spike,
        or noise? Buffer is retained across analysis windows so Flash sees up to
        60s of history for pattern continuity.
        """
        service = payload.service
        now = time.time()

        # Get replica info for context
        svc = await self.blackboard.get_service(service)
        replicas = f"{svc.replicas_ready}/{svc.replicas_desired}" if svc and svc.replicas_ready is not None else "unknown"

        # Buffer the observation (merged with K8s data in same time bucket)
        self._buffer_metric(service, now, payload.metrics.cpu, payload.metrics.memory,
                            payload.metrics.error_rate, replicas)

        # Trim buffer to last 60s max (sliding window, not reset)
        cutoff = now - 60
        self._metrics_buffer[service] = [
            m for m in self._metrics_buffer[service] if m["timestamp"] > cutoff
        ]

        # Trigger analysis every 30s (time since last analysis, not buffer age).
        # Buffer is retained between windows so Flash sees continuity.
        time_since_analysis = now - self._last_analysis_time.get(service, 0)
        if time_since_analysis >= 30 and not self._metrics_analysis_pending.get(service):
            self._metrics_analysis_pending[service] = True
            await self._analyze_metrics_signals(service)
    
    async def _analyze_metrics_signals(self, service: str) -> None:
        """
        Use Flash to analyze buffered metrics and determine what's happening.
        
        Replaces hardcoded threshold checks with LLM reasoning over a 30s window.
        Flash interprets patterns: sustained anomaly, transient spike, recovery, 
        over-provisioning, or normal operation.
        """
        buffer = self._metrics_buffer.get(service, [])
        if not buffer:
            self._metrics_analysis_pending[service] = False
            return

        # Format observations for Flash
        observations = "\n".join(
            f"  {time.strftime('%H:%M:%S', time.localtime(m['timestamp']))}: "
            f"CPU={m['cpu']:.1f}% MEM={m['memory']:.1f}% ERR={m['error_rate']:.2f}% "
            f"Replicas={m['replicas']}"
            for m in buffer
        )

        # Compute simple stats for context
        avg_cpu = sum(m["cpu"] for m in buffer) / len(buffer)
        avg_mem = sum(m["memory"] for m in buffer) / len(buffer)
        avg_err = sum(m["error_rate"] for m in buffer) / len(buffer)
        max_cpu = max(m["cpu"] for m in buffer)
        max_err = max(m["error_rate"] for m in buffer)
        latest = buffer[-1]

        try:
            client = await self._get_client()
            if client:
                prompt = (
                    f"You are an observability analyst. Service '{service}' metrics over the last 30+ seconds:\n"
                    f"{observations}\n\n"
                    f"Stats: avg_cpu={avg_cpu:.1f}% max_cpu={max_cpu:.1f}% avg_mem={avg_mem:.1f}% "
                    f"avg_err={avg_err:.2f}% max_err={max_err:.2f}% replicas={latest['replicas']}\n"
                    f"Thresholds: CPU warning={CPU_THRESHOLD}% Memory warning={MEMORY_THRESHOLD}% Error critical={ERROR_RATE_THRESHOLD}%\n\n"
                    f"Analyze this data. Respond with EXACTLY one of these on the first line:\n"
                    f"- HIGH_CPU (sustained CPU above threshold -- not a transient spike)\n"
                    f"- HIGH_MEMORY (sustained memory above threshold)\n"
                    f"- HIGH_ERROR_RATE (sustained error rate above threshold)\n"
                    f"- OVER_PROVISIONED (multiple replicas but very low resource usage -- waste)\n"
                    f"- RECOVERING (was high, now trending down -- resolving on its own)\n"
                    f"- TRANSIENT_SPIKE (brief spike that already normalized -- no action needed)\n"
                    f"- NORMAL (everything within acceptable range)\n\n"
                    f"Second line: brief explanation (one sentence)."
                )

                response = await client.aio.models.generate_content(
                    model=self._model_name, contents=prompt,
                )
                result_text = response.text.strip() if response.text else "NORMAL"
                lines = result_text.split("\n")
                verdict = lines[0].strip().upper()
                explanation = lines[1].strip() if len(lines) > 1 else ""

                logger.info(f"Flash metrics analysis for {service}: {verdict} -- {explanation}")

                if verdict == "HIGH_CPU":
                    await self.blackboard.record_event(
                        EventType.HIGH_CPU_DETECTED,
                        {"service": service, "cpu": avg_cpu, "max_cpu": max_cpu},
                        narrative=f"Sustained high CPU on {service}: avg {avg_cpu:.1f}%, peak {max_cpu:.1f}%. {explanation}",
                    )
                    logger.warning(f"HIGH CPU (Flash): {service} avg={avg_cpu:.1f}% max={max_cpu:.1f}%")
                    await self._trigger_architect(service, "high_cpu")

                elif verdict == "HIGH_MEMORY":
                    await self.blackboard.record_event(
                        EventType.HIGH_MEMORY_DETECTED,
                        {"service": service, "memory": avg_mem},
                        narrative=f"Sustained high memory on {service}: avg {avg_mem:.1f}%. {explanation}",
                    )
                    logger.warning(f"HIGH MEMORY (Flash): {service} avg={avg_mem:.1f}%")
                    await self._trigger_architect(service, "high_memory")

                elif verdict == "HIGH_ERROR_RATE":
                    await self.blackboard.record_event(
                        EventType.HIGH_ERROR_RATE_DETECTED,
                        {"service": service, "error_rate": avg_err, "max_error_rate": max_err},
                        narrative=f"Sustained high error rate on {service}: avg {avg_err:.2f}%, peak {max_err:.2f}%. {explanation}",
                    )
                    logger.warning(f"HIGH ERROR RATE (Flash): {service} avg={avg_err:.2f}%")
                    await self._trigger_architect(service, "high_error_rate")

                elif verdict == "OVER_PROVISIONED":
                    await self.blackboard.record_event(
                        EventType.ANOMALY_RESOLVED,
                        {"service": service, "anomaly": "over_provisioned", "cpu": avg_cpu, "memory": avg_mem, "replicas": latest["replicas"]},
                        narrative=f"Service {service} appears over-provisioned: {latest['replicas']} replicas with avg CPU={avg_cpu:.1f}%, MEM={avg_mem:.1f}%. {explanation}",
                    )
                    logger.info(f"OVER-PROVISIONED (Flash): {service} {latest['replicas']} replicas, avg cpu={avg_cpu:.1f}%")
                    # Notify active events so the Brain sees the over-provisioned signal
                    await self._notify_active_events(
                        service,
                        f"Over-provisioned: {service} has {latest['replicas']} replicas "
                        f"with avg CPU={avg_cpu:.1f}%, MEM={avg_mem:.1f}%",
                    )
                    await self._trigger_architect(service, "over_provisioned")

                elif verdict == "RECOVERING":
                    await self.blackboard.record_event(
                        EventType.ANOMALY_RESOLVED,
                        {"service": service, "anomaly": "recovering", "cpu": latest["cpu"], "memory": latest["memory"]},
                        narrative=f"Service {service} is recovering: metrics trending back to normal. {explanation}",
                    )
                    logger.info(f"RECOVERING (Flash): {service} -- {explanation}")
                    # Notify active events so the Brain sees the resolution
                    await self._notify_active_events(
                        service,
                        f"Anomaly resolved (recovering): {service} metrics trending to normal. "
                        f"CPU={latest['cpu']:.1f}%, MEM={latest['memory']:.1f}%",
                    )

                elif verdict == "TRANSIENT_SPIKE":
                    logger.info(f"TRANSIENT SPIKE (Flash): {service} -- {explanation}. No action needed.")

                else:  # NORMAL
                    logger.debug(f"NORMAL (Flash): {service} -- {explanation}")

            else:
                # Flash not available -- fallback to simple threshold check
                if max_cpu >= CPU_THRESHOLD:
                    logger.warning(f"HIGH CPU (fallback): {service} at {max_cpu:.1f}%")
                    await self._trigger_architect(service, "high_cpu")
                elif max_err >= ERROR_RATE_THRESHOLD:
                    logger.warning(f"HIGH ERROR (fallback): {service} at {max_err:.2f}%")
                    await self._trigger_architect(service, "high_error_rate")

        except Exception as e:
            logger.error(f"Metrics analysis failed for {service}: {e}")

        finally:
            # DON'T clear the buffer -- retain it for continuity across analysis
            # windows. The 60s trim in _check_anomalies() handles old entries.
            # This ensures Flash sees a sliding 60s window, not isolated 30s slices.
            self._last_analysis_time[service] = time.time()
            self._metrics_analysis_pending[service] = False
    
    async def _trigger_architect(self, service: str, anomaly_type: str) -> None:
        """
        Create an event for the Brain to process -- with two-layer deduplication.
        
        Layer 1 (active-event check): skip if an event is already being worked on.
        Layer 2 (time-based cooldown): skip if we recently created an event for
        this service, even if it was closed fast. Prevents rapid event churn
        during oscillation cycles (scale up -> over-provisioned -> scale down).
        """
        # Layer 1: check if an active event already exists for this service
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            existing = await self.blackboard.get_event(eid)
            if existing and existing.service == service and existing.status.value in ("new", "active", "deferred"):
                logger.info(
                    f"Skipping event creation for {service} ({anomaly_type}) "
                    f"-- active event {eid} already exists (status: {existing.status.value})"
                )
                return

        # Layer 2: time-based cooldown (2 minutes between events per service)
        last_event_time = self._last_event_creation.get(service, 0)
        if time.time() - last_event_time < 120:
            logger.info(
                f"Skipping event for {service} ({anomaly_type}): "
                f"cooldown ({int(time.time() - last_event_time)}s since last)"
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
        self._last_event_creation[service] = time.time()
        logger.info(f"Created event for {service} ({anomaly_type})")
    
    async def check_anomalies_for_service(
        self,
        service: str,
        cpu: float,
        memory: float,
        source: str = "kubernetes",
        error_rate: float = 0.0,
    ) -> None:
        """
        Feed K8s Observer metrics into the unified buffer for LLM analysis.
        
        Called by the KubernetesObserver with metrics from metrics-server.
        Instead of instant hardcoded threshold checks, feeds the same 30s
        metrics buffer used by _check_anomalies(). Both telemetry push AND
        K8s Observer now converge on _analyze_metrics_signals() for a single
        LLM-based assessment.
        
        Args:
            service: Service name
            cpu: CPU usage percentage
            memory: Memory usage percentage
            source: Metrics source (for logging)
            error_rate: Error rate percentage (elevated when K8s warning events detected)
        """
        now = time.time()

        # Get replica info for context
        svc = await self.blackboard.get_service(service)
        replicas = f"{svc.replicas_ready}/{svc.replicas_desired}" if svc and svc.replicas_ready is not None else "unknown"

        # Buffer the observation (merged with self-reported data in same time bucket)
        self._buffer_metric(service, now, cpu, memory, error_rate, replicas)

        # Trim buffer to last 60s max
        cutoff = now - 60
        self._metrics_buffer[service] = [
            m for m in self._metrics_buffer[service] if m["timestamp"] > cutoff
        ]

        # Trigger analysis every 30s (time since last analysis, not buffer age)
        time_since_analysis = now - self._last_analysis_time.get(service, 0)
        if time_since_analysis >= 30 and not self._metrics_analysis_pending.get(service):
            self._metrics_analysis_pending[service] = True
            await self._analyze_metrics_signals(service)
    
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
    
    async def _notify_active_events(self, service: str, message: str) -> None:
        """Append an aligner.confirm turn to any active events for this service.

        When an anomaly resolves (e.g., CPU returns to normal), the Brain needs
        to see this in the event conversation -- otherwise it continues chasing
        a problem that no longer exists.
        """
        from ..models import ConversationTurn
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if event and event.service == service:
                turn = ConversationTurn(
                    turn=len(event.conversation) + 1,
                    actor="aligner",
                    action="confirm",
                    evidence=message,
                )
                await self.blackboard.append_turn(eid, turn)
                logger.info(f"Aligner notified active event {eid}: {message[:80]}")

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
