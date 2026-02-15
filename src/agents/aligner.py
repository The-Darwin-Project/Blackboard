# BlackBoard/src/agents/aligner.py
# @ai-rules:
# 1. [Pattern]: check_active_verifications extracts target_service from evidence field (target_service:xxx).
# 2. [Pattern]: Dedup guard before appending confirm turns -- skip if previous confirm still SENT/DELIVERED.
# 3. [Gotcha]: _notify_active_events uses conversation-state gate: skips if Brain's last action is route/verify/defer/wait with no response yet.
# 4. [Constraint]: AIR GAP: No kubernetes or git imports allowed. LLM access via .llm adapter only.
# 5. [Constraint]: All generate() calls MUST set max_output_tokens explicitly (1024 for text, 4096 for tool-calling).
# 6. [Pattern]: Aligner always uses GeminiAdapter (Flash) -- never Claude. Provider is hardcoded to "gemini".
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
# NOTE: Aligner uses GeminiAdapter (Flash model) via .llm subpackage.
# Independent of Brain's Pro model. Always uses "gemini" provider.
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

# ---------------------------------------------------------------------------
# Aligner System Prompt -- guides Flash's reasoning and tool usage
# ---------------------------------------------------------------------------
ALIGNER_SYSTEM_PROMPT = """You are the Aligner -- the eyes and ears of the Darwin autonomous operations system.

Your job is to OBSERVE service metrics and REPORT anomalies to the Brain.
You do NOT fix problems. You detect them and describe what you see.

## Your Personality
- Precise and evidence-based
- First person: "I detected...", "I observed...", "I noticed..."
- Always include the numbers: actual values, thresholds, trend direction
- Be honest about uncertainty: "The CPU dropped briefly but may spike again"

## Thresholds (for reference, not rigid rules)
- CPU warning: {cpu_threshold}%
- Memory warning: {memory_threshold}%
- Error rate critical: {error_rate_threshold}%
- Over-provisioned: multiple replicas with CPU < 10% and MEM < 20%

## Cynefin Sense-Making Framework
When creating events, classify the situation into a domain. This tells the Brain HOW to respond:

| Domain      | Meaning                          | You see...                                                    | Response pattern              |
|-------------|----------------------------------|---------------------------------------------------------------|-------------------------------|
| clear       | Known problem, known fix         | CPU pegged, single replica, no errors -- just needs scaling   | sense-categorize-respond      |
| complicated | Known unknowns, needs analysis   | Intermittent errors, unclear root cause, multiple symptoms     | sense-analyze-respond         |
| complex     | Unknown unknowns, novel          | Cascading failures, never-seen-before pattern, contradictory data | probe-sense-respond       |
| chaotic     | Crisis, system down              | All pods crashing, complete service outage, data loss risk     | act-sense-respond             |

Most infrastructure anomalies are "clear" (known fix) or "complicated" (needs investigation).
Use "complex" or "chaotic" only when the data is genuinely confusing or the system is in crisis.

## When to call create_event
- Sustained metrics above threshold across multiple observations (not a single spike)
- A pattern that requires investigation or action
- Set severity: warning (degraded but functional) or critical (service impacted)

## When to call update_active_event
- New metric data relevant to an event the Brain is already handling
- Metrics getting worse or changing character (e.g. CPU resolved but error rate climbing)

## When to call report_recovery
- Metrics have dropped BELOW thresholds and stabilized
- ONLY when the LATEST readings are clearly normal, not just trending down
- A drop from 100% to 95% is NOT recovery -- still above the 80% threshold

## When to do nothing (return text only)
- Metrics are normal, nothing noteworthy
- Transient blip that already normalized within the observation window
- The ops journal shows this exact issue was JUST resolved (within the last 5 minutes) -- it is a residual alert, not a new incident

## Ops Journal Context
Your prompt may include recent ops journal entries for the service. Use this temporal context:
- If the journal shows "closed in N turns" for the same anomaly type within the last few minutes, this is likely a residual alert from the same incident. Do NOT create a new event.
- If the journal shows repeated closures of the same pattern (3+ times), consider escalating with a different reason that highlights the recurrence.
- The journal gives you memory across analysis cycles -- use it to avoid alert fatigue.
""".format(
    cpu_threshold=CPU_THRESHOLD,
    memory_threshold=MEMORY_THRESHOLD,
    error_rate_threshold=ERROR_RATE_THRESHOLD,
)



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
    - Configurable via natural language (Gemini Flash via LLM adapter)
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self.filter_rules: list[FilterRule] = []
        self._adapter = None
        
        # LLM config -- Aligner always uses Gemini Flash
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE_ALIGNER", "0.3"))
        
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
    
    async def _get_adapter(self):
        """Lazy-load LLM adapter (always Gemini Flash for Aligner)."""
        if self._adapter is None and self._llm_enabled:
            try:
                from .llm import create_adapter
                
                project = os.getenv("GCP_PROJECT")
                location = os.getenv("GCP_LOCATION", "us-central1")
                model_name = os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview")
                
                self._adapter = create_adapter("gemini", project, location, model_name)
                logger.info(f"Aligner LLM adapter initialized: gemini/{model_name}")
            except Exception as e:
                logger.warning(f"LLM adapter not available for Aligner: {e}")
                self._adapter = None
        
        return self._adapter
    
    async def configure_filter(self, instruction: str) -> Optional[FilterRule]:
        """
        Configure a filter rule from natural language instruction.
        
        Examples:
        - "Ignore errors for 1 hour"
        - "Ignore metrics from inventory-api for 30 minutes"
        - "Stop filtering errors"
        
        Uses Gemini Flash (via LLM adapter) to parse the instruction into a FilterRule.
        """
        adapter = await self._get_adapter()
        
        if adapter is None:
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
            
            response = await adapter.generate(
                system_prompt="", contents=prompt, max_output_tokens=1024,
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
            adapter = await self._get_adapter()
            if adapter:
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

                response = await adapter.generate(
                    system_prompt="", contents=prompt, max_output_tokens=1024,
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

        # Check if there's an active event for this service (context for Flash)
        has_active = await self._has_active_event_for(service)

        # Temporal context: recent ops journal entries for this service
        # Prevents re-escalating events that were just closed (residual alerts)
        journal_context = ""
        try:
            journal_entries = await self.blackboard.get_journal(service)
            if journal_entries:
                # Last 5 entries, newest last
                recent = journal_entries[-5:]
                journal_context = (
                    f"\nRecent ops journal for {service}:\n"
                    + "\n".join(f"  {entry}" for entry in recent)
                    + "\n"
                )
        except Exception:
            pass  # Journal unavailable is not fatal

        try:
            adapter = await self._get_adapter()
            if adapter:
                from .llm import ALIGNER_TOOL_SCHEMAS

                # Build context prompt -- Flash reasons freely about the data
                prompt = (
                    f"Service '{service}' metrics over the last 30+ seconds:\n"
                    f"{observations}\n\n"
                    f"Stats: avg_cpu={avg_cpu:.1f}% max_cpu={max_cpu:.1f}% avg_mem={avg_mem:.1f}% "
                    f"avg_err={avg_err:.2f}% max_err={max_err:.2f}% replicas={latest['replicas']}\n"
                    f"Latest reading: CPU={latest['cpu']:.1f}% MEM={latest['memory']:.1f}% ERR={latest['error_rate']:.2f}%\n"
                    f"Active event exists for this service: {'yes' if has_active else 'no'}\n"
                    f"{journal_context}\n"
                    f"Analyze this data. If the ops journal shows this issue was JUST resolved (within the last few minutes), "
                    f"do NOT create a new event -- it is likely a residual alert. Use your tools to report what you observe, "
                    f"or return text only if everything is normal or recently resolved."
                )

                response = await adapter.generate(
                    system_prompt=ALIGNER_SYSTEM_PROMPT,
                    contents=prompt,
                    tools=ALIGNER_TOOL_SCHEMAS,
                    temperature=self.temperature,
                    max_output_tokens=4096,
                )

                # Handle function calls from Flash
                if response.function_call:
                    func_name = response.function_call.name
                    args = response.function_call.args
                    observation = args.get("observation", "")

                    logger.info(f"Flash {func_name} for {service}: {observation[:150]}")

                    if func_name == "create_event":
                        severity = args.get("severity", "warning")
                        domain = args.get("domain", "complicated")
                        execution_mode = args.get("execution_mode", "")
                        metrics = args.get("metrics", {})

                        # Record to Blackboard timeline -- Flash's full structured analysis
                        await self.blackboard.record_event(
                            EventType.ALIGNER_OBSERVATION,
                            {
                                "service": service,
                                "severity": severity,
                                "domain": domain,
                                "execution_mode": execution_mode,
                                "metrics": metrics,
                            },
                            narrative=observation,
                        )
                        # Notify active events if one exists (dual path for ongoing investigations)
                        if has_active:
                            await self._notify_active_events(service, observation)
                        # "clear" domain = recovery signal, NOT a new anomaly.
                        # Only notify active events (above), never create new ones.
                        if domain == "clear":
                            logger.info(f"Skipping event creation for {service} ({severity}_{domain}): recovery signal, not actionable")
                        else:
                            # Dedup + create Brain event (anomaly_type used for dedup key only)
                            await self._trigger_architect(service, f"{severity}_{domain}")

                    elif func_name == "update_active_event":
                        await self._notify_active_events(service, observation)

                    elif func_name == "report_recovery":
                        # Hard guard: verify metrics are ACTUALLY below thresholds
                        # Flash may still call report_recovery when values are borderline
                        still_hot = (
                            latest["cpu"] >= CPU_THRESHOLD
                            or latest["memory"] >= MEMORY_THRESHOLD
                            or latest["error_rate"] >= ERROR_RATE_THRESHOLD
                        )
                        if still_hot:
                            logger.warning(
                                f"Flash called report_recovery but metrics still above threshold: "
                                f"CPU={latest['cpu']:.1f}%, MEM={latest['memory']:.1f}%, "
                                f"ERR={latest['error_rate']:.1f}%. Ignoring recovery signal."
                            )
                        else:
                            await self.blackboard.record_event(
                                EventType.ANOMALY_RESOLVED,
                                {"service": service},
                                narrative=observation,
                            )
                            await self._notify_active_events(service, observation)

                elif response.text:
                    # Flash returned text only (no function call) -- normal state, log and skip
                    logger.debug(f"Flash observation for {service}: {response.text.strip()}")

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
    
    async def _has_active_event_for(self, service: str) -> bool:
        """Check if an active event exists for this service."""
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            existing = await self.blackboard.get_event(eid)
            if existing and existing.service == service and existing.status.value in ("new", "active", "deferred"):
                return True
        return False

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

        # Layer 2: time-based cooldown (5 minutes between events per service)
        # Check in-memory cache first, then Redis (survives pod restarts)
        COOLDOWN_SECONDS = 300
        now = time.time()
        last_event_time = self._last_event_creation.get(service, 0)
        if not last_event_time:
            # In-memory miss -- check Redis (populated by previous pod lifecycle)
            redis_ts = await self.blackboard.redis.get(f"darwin:aligner:cooldown:{service}")
            if redis_ts:
                last_event_time = float(redis_ts)
                self._last_event_creation[service] = last_event_time
        if now - last_event_time < COOLDOWN_SECONDS:
            logger.info(
                f"Skipping event for {service} ({anomaly_type}): "
                f"cooldown ({int(now - last_event_time)}s/{COOLDOWN_SECONDS}s since last)"
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
        self._last_event_creation[service] = now
        # Persist to Redis so cooldown survives pod restarts (TTL = cooldown + buffer)
        await self.blackboard.redis.set(
            f"darwin:aligner:cooldown:{service}", str(now), ex=COOLDOWN_SECONDS + 60
        )
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
        """Scan active events for unanswered verification requests from Brain.

        Scans all turns (not just last) so a user message arriving after
        brain.verify doesn't silently drop the verification request.
        """
        active_ids = await self.blackboard.get_active_events()
        for event_id in active_ids:
            event = await self.blackboard.get_event(event_id)
            if not event or not event.conversation:
                continue
            # Find the latest brain.verify turn waiting for aligner
            verify_turn = None
            for t in reversed(event.conversation):
                if t.actor == "brain" and t.waitingFor == "aligner":
                    verify_turn = t
                    break
                # Stop scanning if we hit an aligner confirm (already answered)
                if t.actor == "aligner" and t.action == "confirm":
                    break
            if not verify_turn:
                continue
            # Dedup: skip if a previous confirm is still unprocessed
            pending_confirms = [
                t for t in event.conversation
                if t.actor == "aligner" and t.action == "confirm"
                and t.status.value in ("sent", "delivered")
            ]
            if pending_confirms:
                logger.debug(f"Skipping confirm for {event_id}: previous confirm not yet evaluated")
                continue
            # Extract target service from verify turn (falls back to event.service)
            target_service = event.service
            if verify_turn.evidence and verify_turn.evidence.startswith("target_service:"):
                target_service = verify_turn.evidence.split(":", 1)[1]
            # Check if the condition is met
            svc = await self.blackboard.get_service(target_service)
            if svc:
                from ..models import ConversationTurn
                confirm_turn = ConversationTurn(
                    turn=len(event.conversation) + 1,
                    actor="aligner",
                    action="confirm",
                    evidence=(
                        f"Service: {target_service}, "
                        f"CPU: {svc.metrics.cpu:.1f}%, "
                        f"Memory: {svc.metrics.memory:.1f}%, "
                        f"Replicas: {svc.replicas_ready}/{svc.replicas_desired}"
                        if svc.replicas_ready is not None else
                        f"Service: {target_service}, CPU: {svc.metrics.cpu:.1f}%"
                    ),
                )
                await self.blackboard.append_turn(event_id, confirm_turn)
                logger.info(f"Aligner confirmed verification for event {event_id}")
    
    async def _notify_active_events(self, service: str, message: str) -> None:
        """Append an aligner.confirm turn to any active events for this service.

        When an anomaly resolves (e.g., CPU returns to normal), the Brain needs
        to see this in the event conversation -- otherwise it continues chasing
        a problem that no longer exists.

        Noise suppression (conversation-state-aware):
        1. Skip DEFERRED events (Brain explicitly chose to wait)
        2. Skip if Brain is busy -- last brain turn is route/verify/defer/wait
           with no subsequent agent/aligner response (Brain is waiting for something)
        3. Skip if a previous confirm is still unprocessed (SENT/DELIVERED)
        """
        from ..models import ConversationTurn
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if event and event.service == service:
                # Skip DEFERRED events -- Brain explicitly chose to wait
                if event.status.value == "deferred":
                    logger.debug(f"Skipping notify for deferred event {eid}")
                    continue
                # Conversation-state gate: find the last brain turn and check
                # if the Brain is waiting for something. If so, periodic
                # observations are noise -- the Brain already knows and acted.
                last_brain_turn = next(
                    (t for t in reversed(event.conversation) if t.actor == "brain"),
                    None,
                )
                if last_brain_turn and last_brain_turn.action in ("route", "verify", "defer", "wait"):
                    # Check if an agent/aligner has responded AFTER this brain turn
                    brain_idx = next(
                        i for i, t in enumerate(event.conversation)
                        if t is last_brain_turn
                    )
                    response_after = any(
                        t.actor in ("architect", "sysadmin", "developer", "aligner")
                        for t in event.conversation[brain_idx + 1:]
                    )
                    if not response_after:
                        logger.debug(
                            f"Skipping notify for {eid}: Brain is waiting "
                            f"({last_brain_turn.action}), no response yet"
                        )
                        continue
                # Dedup: skip if a previous confirm is still unprocessed
                pending = [
                    t for t in event.conversation
                    if t.actor == "aligner" and t.action == "confirm"
                    and t.status.value in ("sent", "delivered")
                ]
                if pending:
                    logger.debug(f"Skipping confirm for {eid}: previous confirm not yet evaluated")
                    continue
                turn = ConversationTurn(
                    turn=len(event.conversation) + 1,
                    actor="aligner",
                    action="confirm",
                    evidence=message,
                )
                await self.blackboard.append_turn(eid, turn)
                logger.info(f"Aligner notified active event {eid}: {message}")

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
