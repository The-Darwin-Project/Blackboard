# BlackBoard/src/agents/aligner.py
# @ai-rules:
# 1. [Pattern]: Deterministic event-driven state transitions -- NO LLM in the health/sync loop.
#    handle_health_change/handle_sync_drift decide escalation via fixed rules, not Flash reasoning.
# 2. [Pattern]: Last-write-wins: updates pending confirm evidence via update_turn_evidence() instead of skipping when previous confirm still SENT/DELIVERED.
# 3. [Pattern]: _notify_active_events always delivers updates (dedup + deferred-skip only).
# 4. [Constraint]: AIR GAP: No kubernetes or git imports allowed. LLM access via .llm adapter only.
# 5. [Constraint]: All generate() calls MUST set max_output_tokens explicitly (via LLM_MAX_TOKENS_ALIGNER or per-call override).
# 6. [Pattern]: Aligner uses GeminiAdapter (model from LLM_MODEL_ALIGNER) ONLY for configure_filter() NLP
#    parsing. Flash is no longer in the health/sync escalation path (see rule 1).
"""
Agent 1: The Aligner (The Listener)

Role: Truth Maintenance & Deterministic Health/Sync Escalation
Nature: Hybrid Daemon (Python + Gemini LLM via google-genai for filter configuration only)

The Aligner reacts to ArgoCDObserver health/sync state transitions and creates
events for the Brain -- deterministically, not via LLM judgment. It can still be
configured via natural language (e.g., "Ignore errors for 1h") for noise filtering.

CLOSED-LOOP: The Aligner detects state transitions and creates events for the
Brain to process, completing the observation -> triage loop.

AIR GAP: This module may import google-genai (for configure_filter) but NOT kubernetes or git.
"""
# NOTE: Aligner uses GeminiAdapter via .llm subpackage (model from LLM_MODEL_ALIGNER),
# used exclusively by configure_filter(). Independent of Brain's Pro model.
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Optional

# AIR GAP ENFORCEMENT: Only these imports allowed
# import kubernetes  # FORBIDDEN
# import git  # FORBIDDEN

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# Sync drift dwell-time debounce -- Application must stay OutOfSync this long before escalating
SYNC_DRIFT_DWELL_SECONDS = 60


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
    The Aligner agent - reacts to ArgoCD health/sync transitions and maintains truth.
    
    Responsibilities:
    - Apply filter rules for noise reduction
    - Deterministic escalation on ArgoCD health/sync state transitions (no LLM)
    - Detect state transitions and create events for Brain (closed-loop)
    - Provide check_state() for Brain inline verification
    - Configurable via natural language (Gemini Flash via LLM adapter, filter config only)
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self.filter_rules: list[FilterRule] = []
        self._adapter = None
        
        # LLM config -- Aligner uses Gemini (model from LLM_MODEL_ALIGNER) for configure_filter() only
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE_ALIGNER", "0.3"))
        
        # Closed-loop state tracking
        self._known_services: set[str] = set()
        self._service_versions: dict[str, str] = {}  # service -> last known version

        # Sync drift dwell-time tracking -- argocd_app -> first-seen-OutOfSync timestamp
        self._sync_drift_first_seen: dict[str, float] = {}
        
        # Event creation cooldown -- prevents rapid event churn after close/resolve cycles
        self._last_event_creation: dict[str, float] = {}  # service -> last event creation timestamp
    
    async def _get_adapter(self):
        """Lazy-load LLM adapter (always Gemini for Aligner, model from LLM_MODEL_ALIGNER)."""
        if self._adapter is None and self._llm_enabled:
            try:
                from .llm import create_adapter
                
                project = os.getenv("GCP_PROJECT")
                location = os.getenv("GCP_LOCATION", "us-central1")
                model_name = os.getenv("LLM_MODEL_ALIGNER", "gemini-3.6-flash")
                
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
                thinking_level=os.getenv("LLM_THINKING_ALIGNER", "low"),
            )
            from .llm import record_token_usage
            record_token_usage("aligner", response.usage)
            
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
    
    async def handle_health_change(
        self, service: str, old_health: str, new_health: str, resources_summary: dict,
    ) -> None:
        """Deterministic escalation on ArgoCD health transitions -- no LLM in the loop.

        Called by ArgoCDObserver whenever a Deployment's health.status changes.
        Degraded or Missing always creates an event: these states directly indicate
        replica/pod failure, unlike Progressing (normal deploy transient) or Healthy.
        Recovering to Healthy from a failed state notifies active events and clears
        any pending escalation flag -- the deterministic analog of the old report_recovery path.
        """
        if new_health == "Healthy" and old_health in ("Degraded", "Missing"):
            msg = f"ArgoCD health recovered: {old_health} -> {new_health} for {service}"
            try:
                await self._notify_active_events(service, msg)
            finally:
                try:
                    await self.blackboard.clear_escalation_flag(service)
                except Exception as ce:
                    logger.warning(f"Failed to clear escalation flag on recovery for {service}: {ce}")
            return

        if new_health not in ("Degraded", "Missing"):
            logger.debug(f"ArgoCD health change for {service}: {old_health} -> {new_health} (no escalation)")
            return

        argocd_app = resources_summary.get("argocd_app", "")
        namespace = resources_summary.get("namespace", "")
        severity = "critical" if new_health == "Degraded" else "warning"
        display_text = (
            f"ArgoCD health: {old_health} -> {new_health} "
            f"(service={service}, namespace={namespace}, app={argocd_app})"
        )
        await self._trigger_architect(
            service, f"argocd_health_{new_health.lower()}", display_text,
            domain="complicated", severity_level=severity,
        )

    async def handle_sync_drift(
        self, argocd_app: str, old_sync: Optional[str], new_sync: str,
    ) -> None:
        """Deterministic escalation on sustained ArgoCD sync drift (dwell-time debounced).

        Called by ArgoCDObserver once per Application per watch tick -- already gated
        on spec.syncPolicy.automated existing (manual-sync apps never reach here).
        Escalates only after the Application has stayed OutOfSync for
        SYNC_DRIFT_DWELL_SECONDS -- avoids alerting on transient drift during a normal
        deploy cycle. Clears the dwell timer as soon as the Application reports Synced.
        """
        now = time.time()
        if new_sync == "Synced":
            self._sync_drift_first_seen.pop(argocd_app, None)
            return

        first_seen = self._sync_drift_first_seen.get(argocd_app)
        if first_seen is None:
            self._sync_drift_first_seen[argocd_app] = now
            return

        if now - first_seen < SYNC_DRIFT_DWELL_SECONDS:
            return

        display_text = (
            f"ArgoCD sync: {old_sync or 'unknown'} -> {new_sync} for {argocd_app} "
            f"(out of sync {SYNC_DRIFT_DWELL_SECONDS}s+, auto-sync enabled)"
        )
        await self._trigger_architect(
            argocd_app, "argocd_sync_drift", display_text,
            domain="clear", severity_level="warning",
            subject_type="system",
        )

    async def _has_active_event_for(self, service: str) -> bool:
        """Check if an active event exists for this service."""
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            existing = await self.blackboard.get_event(eid)
            if existing and existing.service == service and existing.status.value in ("new", "active", "deferred"):
                return True
        return False

    async def _trigger_architect(
        self, service: str, anomaly_type: str, display_text: str,
        domain: str = "complicated", severity_level: str = "warning",
        subject_type: str = "service",
    ) -> None:
        """
        Create an event for the Brain to process -- with three-layer deduplication.
        
        Layer 1 (active-event check): skip if an event is already being worked on.
        Layer 2 (time-based cooldown): skip if we recently created an event for
        this key, even if it was closed fast. Prevents rapid event churn during
        oscillation cycles (e.g. flapping health/sync states).
        Layer 3 (escalation suppression): skip while Brain's report_incident flag
        is pending on the target service.
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

        # Layer 3: escalation suppression (flag set by Brain on report_incident).
        # get_service() returns None for synthetic keys like argocd_app -- the
        # check is null-safe and simply skips for those (real service names only).
        try:
            svc = await self.blackboard.get_service(service)
        except Exception:
            svc = None
        if svc and svc.escalation_flag:
            flag_eid = svc.escalation_flag.split('|')[0]
            logger.info(
                f"Skipping event for {service} ({anomaly_type}): "
                f"escalation pending ({flag_eid})"
            )
            return

        from ..models import EventEvidence
        evidence_obj = EventEvidence(
            display_text=display_text,
            source_type="aligner",
            triggered_by="system",
            domain=domain,
            domain_confidence="assessed",
            severity=severity_level,
            metrics=None,
        )

        await self.blackboard.create_event(
            source="aligner",
            service=service,
            reason=anomaly_type.replace("_", " "),
            evidence=evidence_obj,
            subject_type=subject_type,
        )
        self._last_event_creation[service] = now
        # Persist to Redis so cooldown survives pod restarts (TTL = cooldown + buffer)
        await self.blackboard.redis.set(
            f"darwin:aligner:cooldown:{service}", str(now), ex=COOLDOWN_SECONDS + 60
        )
        logger.info(f"Created event for {service} ({anomaly_type})")

    async def _notify_active_events(self, service: str, message: str) -> None:
        """Append an aligner.confirm turn to any active events for this service.

        When an anomaly resolves (e.g., CPU returns to normal), the Brain needs
        to see this in the event conversation -- otherwise it continues chasing
        a problem that no longer exists.

        Noise suppression:
        1. Skip DEFERRED events (Brain explicitly chose to wait)
        2. Skip if a previous confirm is still unprocessed (SENT/DELIVERED)
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
                # Dedup: skip if a previous confirm is still unprocessed
                pending = [
                    t for t in event.conversation
                    if t.actor == "aligner" and t.action == "confirm"
                    and t.status.value in ("sent", "delivered")
                ]
                if pending:
                    pending[0].evidence = message
                    await self.blackboard.update_turn_evidence(eid, pending[0].turn, message)
                    logger.info(f"Updated pending confirm for {eid} with fresh metrics")
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
            "health_status": svc.health_status,
            "sync_status": svc.sync_status,
            "argocd_app": svc.argocd_app,
            "replicas_ready": svc.replicas_ready,
            "replicas_desired": svc.replicas_desired,
            "version": svc.version,
        }
    
    async def handle_failed_promotion(
        self, *, service: str, project: str, stage: str, promotion: str,
        freight: str, phase: str, message: str, failed_step: str,
        mr_url: str, started_at: str = "", finished_at: str = "",
    ) -> Optional[str]:
        """Create an event for a failed Kargo promotion (called by KargoObserver).

        Returns the event_id on creation, None if skipped (active event or cooldown).
        """
        active_ids = await self.blackboard.get_active_events()
        for eid in active_ids:
            existing = await self.blackboard.get_event(eid)
            if existing and existing.service == service and existing.status.value in ("new", "active", "deferred"):
                logger.info(f"Skipping Kargo event for {service}: active event {eid} exists")
                return None

        COOLDOWN_SECONDS = 300
        now = time.time()
        last_event_time = self._last_event_creation.get(service, 0)
        if not last_event_time:
            redis_ts = await self.blackboard.redis.get(f"darwin:aligner:cooldown:{service}")
            if redis_ts:
                last_event_time = float(redis_ts)
                self._last_event_creation[service] = last_event_time
        if now - last_event_time < COOLDOWN_SECONDS:
            logger.info(f"Skipping Kargo event for {service}: cooldown ({int(now - last_event_time)}s/{COOLDOWN_SECONDS}s)")
            return None

        # Layer 3: escalation suppression
        try:
            flag = await self.blackboard.get_escalation_flag(service)
        except Exception:
            flag = None
        if flag:
            flag_eid = flag.split('|')[0]
            logger.info(f"Skipping Kargo event for {service}: escalation pending ({flag_eid})")
            return None

        from ..models import EventEvidence
        evidence = EventEvidence(
            display_text=f"[kargo] Promotion failed: {stage}@{project} -- {message[:200]}",
            source_type="aligner",
            triggered_by="system",
            domain="clear",
            domain_confidence="assessed",
            severity="warning",
            kargo_context={
                "project": project,
                "stage": stage,
                "promotion": promotion,
                "freight": freight,
                "phase": phase,
                "message": message,
                "failed_step": failed_step,
                "mr_url": mr_url,
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )
        event_id = await self.blackboard.create_event(
            source="aligner",
            service=service,
            reason=f"kargo promotion failed: {failed_step or phase}",
            evidence=evidence,
            subject_type="kargo_stage",
        )
        self._last_event_creation[service] = now
        await self.blackboard.redis.set(
            f"darwin:aligner:cooldown:{service}", str(now), ex=COOLDOWN_SECONDS + 60
        )
        logger.info(f"Created Kargo event for {service} ({phase}: {failed_step})")
        return event_id

    async def handle_promotion_recovery(
        self, *, service: str, project: str, stage: str, promotion: str,
    ) -> None:
        """Notify active events that a newer promotion succeeded (called by KargoObserver)."""
        msg = f"[kargo] Promotion succeeded: {stage}@{project} (promotion={promotion})"
        try:
            await self._notify_active_events(service, msg)
        finally:
            try:
                await self.blackboard.clear_escalation_flag(service)
            except Exception as ce:
                logger.warning(f"Failed to clear escalation flag on Kargo recovery for {service}: {ce}")

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
