# BlackBoard/src/agents/aligner.py
# @ai-rules:
# 1. [Pattern]: Poll-driven event creation — _drain_once() fires every ALIGNER_POLL_INTERVAL seconds,
#    re-checks health/sync state from Redis before creating events. No in-memory dwell state.
# 2. [Pattern]: TimeKeeper lifecycle — start()/stop() own an asyncio.Task running _poll_loop().
# 3. [Pattern]: _trigger_architect returns outcome string ("created", "suppressed_active",
#    "suppressed_cooldown", "suppressed_escalation") for drain disposition.
# 4. [Constraint]: AIR GAP: No kubernetes or git imports allowed. LLM access via .llm adapter only.
# 5. [Constraint]: All generate() calls MUST set max_output_tokens explicitly.
# 6. [Pattern]: pending_count is an in-memory property updated at drain cycle start/end.
# 7. [Gotcha]: Post-restart gap: _initial_sync(suppress_callbacks=True) won't re-populate
#    pending for already-unhealthy apps. Same as prior edge-triggered behavior.
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

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

from ..models import ESCALATION_SCOPE_MAP

# AIR GAP ENFORCEMENT: Only these imports allowed
# import kubernetes  # FORBIDDEN
# import git  # FORBIDDEN

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)


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
        
        # Event creation cooldown -- prevents rapid event churn after close/resolve cycles
        self._last_event_creation: dict[str, float] = {}  # service -> last event creation timestamp

        # Poll loop state (TimeKeeper pattern)
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._poll_interval = int(os.getenv("ALIGNER_POLL_INTERVAL", "30"))
        self._dwell_seconds = float(os.getenv("ALIGNER_DWELL_SECONDS", "30"))
        self._pending_count: int = 0
    
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

    # =========================================================================
    # Poll Loop Lifecycle (TimeKeeper pattern)
    # =========================================================================

    @property
    def pending_count(self) -> int:
        """In-memory pending count updated each drain cycle."""
        return self._pending_count

    async def start(self) -> None:
        """Start the poll loop task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Aligner poll loop started (interval=%ds, dwell=%ds)",
                    self._poll_interval, self._dwell_seconds)

    async def stop(self) -> None:
        """Stop the poll loop task. Idempotent when never started."""
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

    async def _poll_loop(self) -> None:
        """Periodic drain loop — fires _drain_once every poll interval."""
        while self._running:
            try:
                await self._drain_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Aligner drain cycle failed")
            await asyncio.sleep(self._poll_interval)

    async def _drain_once(self) -> None:
        """Drain dwell-expired signals: re-check health, create events or discard."""
        keys = await self.blackboard.drain_aligner_pending(self._dwell_seconds)
        if not keys:
            return
        self._pending_count = await self.blackboard.count_aligner_pending()
        created = resolved = restaged = 0
        for key in keys:
            try:
                meta_json = await self.blackboard.redis.hget(
                    "darwin:aligner:pending:meta", key
                )
                if meta_json is None:
                    logger.warning("Orphan pending key %s, cleaning up", key)
                    await self.blackboard.commit_aligner_signal(key)
                    continue
                meta = json.loads(meta_json)
                if "|" not in key:
                    logger.warning("Malformed pending key %s, cleaning up", key)
                    await self.blackboard.commit_aligner_signal(key)
                    continue
                target, _ = key.split("|", 1)
                subject_type = meta.get("subject_type", "service")

                # Re-check current state before event creation
                if subject_type == "service":
                    svc = await self.blackboard.get_service(target)
                    if svc is None or svc.health_status in ("Healthy", "Progressing"):
                        await self.blackboard.commit_aligner_signal(key)
                        if svc and svc.health_status == "Healthy":
                            await self._notify_active_events(target, "self-resolved")
                            try:
                                await self.blackboard.clear_escalation_flag(target, scope="health")
                            except Exception:
                                pass
                        resolved += 1
                        continue
                else:
                    sync_val = await self.blackboard.redis.hget(
                        f"darwin:argocd_app_sync:{target}", "sync_status"
                    )
                    if sync_val in ("Synced", None):
                        await self.blackboard.commit_aligner_signal(key)
                        resolved += 1
                        continue

                # Still sick — attempt event creation
                anomaly_type = meta.get("anomaly_type", "health")
                outcome = await self._trigger_architect(
                    target, anomaly_type.replace("_", " "),
                    meta["display_text"],
                    domain=meta.get("domain", "complicated"),
                    severity_level=meta.get("severity", "warning"),
                    subject_type=subject_type,
                    argocd_app=meta.get("argocd_app", ""),
                )
                if outcome in ("created", "suppressed_active"):
                    await self.blackboard.commit_aligner_signal(key)
                    if outcome == "created":
                        created += 1
                else:
                    await self.blackboard.restage_aligner_signal(key, meta)
                    restaged += 1
            except Exception:
                logger.exception("Drain error for key %s, committing to prevent retry loop", key)
                try:
                    await self.blackboard.commit_aligner_signal(key)
                except Exception:
                    pass
        self._pending_count = await self.blackboard.count_aligner_pending()
        if keys:
            logger.info(
                "Aligner drain: %d expired, %d events, %d self-resolved, %d re-dwelled",
                len(keys), created, resolved, restaged,
            )

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
    
    async def handle_recovery(self, target: str, message: str, scope: str) -> None:
        """Handle a recovery signal from the observer.

        scope="health": notify active events + clear escalation flag + ZREM pending
        scope="sync": ZREM pending only (sync never had a recovery-notify path)
        """
        if scope == "health":
            await self._notify_active_events(target, message)
            try:
                await self.blackboard.clear_escalation_flag(target, scope="health")
            except Exception as e:
                logger.warning("Failed to clear escalation flag on recovery: %s", e)
        key = f"{target}|{scope}"
        await self.blackboard.remove_aligner_pending(key)

    async def _check_escalation_gate(self, service: str, scope: str) -> bool:
        """Layer 3 escalation suppression gate — direct HGET, not get_service().

        Returns True if an escalation flag exists for the given scope (= suppress event).
        Uses direct get_escalation_flag() which works for both real service keys AND
        synthetic argocd_app keys (unlike get_service() which returns None for synthetics).
        """
        try:
            flag = await self.blackboard.get_escalation_flag(service, scope=scope)
        except Exception:
            flag = None
        if flag:
            flag_eid = flag.split('|')[0]
            logger.info(f"Escalation gate: suppressing {service} scope={scope} (pending {flag_eid})")
            return True
        return False

    async def _trigger_architect(
        self, service: str, anomaly_type: str, display_text: str,
        domain: str = "complicated", severity_level: str = "warning",
        subject_type: str = "service", argocd_app: str = "",
    ) -> str:
        """
        Create an event for the Brain to process -- with three-layer deduplication.
        
        Returns outcome string for poll loop disposition:
        - "created": event was created, caller should commit pending signal
        - "suppressed_active": active event already covers this service
        - "suppressed_cooldown": cooldown period active, caller should restage
        - "suppressed_escalation": escalation flag set, caller should restage
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
                return "suppressed_active"

        # Layer 2: time-based cooldown (5 minutes between events per service)
        COOLDOWN_SECONDS = 300
        now = time.time()
        last_event_time = self._last_event_creation.get(service, 0)
        if not last_event_time:
            redis_ts = await self.blackboard.redis.get(f"darwin:aligner:cooldown:{service}")
            if redis_ts:
                last_event_time = float(redis_ts)
                self._last_event_creation[service] = last_event_time
        if now - last_event_time < COOLDOWN_SECONDS:
            logger.info(
                f"Skipping event for {service} ({anomaly_type}): "
                f"cooldown ({int(now - last_event_time)}s/{COOLDOWN_SECONDS}s since last)"
            )
            return "suppressed_cooldown"

        # Layer 3: escalation suppression (flag set by Brain on report_incident)
        scope = ESCALATION_SCOPE_MAP.get(subject_type, "health")
        if await self._check_escalation_gate(service, scope):
            logger.info(f"Skipping event for {service} ({anomaly_type}): escalation gate (scope={scope})")
            return "suppressed_escalation"

        from ..models import EventEvidence
        evidence_obj = EventEvidence(
            display_text=display_text,
            source_type="aligner",
            triggered_by="system",
            domain=domain,
            domain_confidence="assessed",
            severity=severity_level,
            metrics=None,
            argocd_app=argocd_app or None,
        )

        await self.blackboard.create_event(
            source="aligner",
            service=service,
            reason=anomaly_type.replace("_", " "),
            evidence=evidence_obj,
            subject_type=subject_type,
        )
        self._last_event_creation[service] = now
        await self.blackboard.redis.set(
            f"darwin:aligner:cooldown:{service}", str(now), ex=COOLDOWN_SECONDS + 60
        )
        logger.info(f"Created event for {service} ({anomaly_type})")
        return "created"

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
                    chat_role="user",
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

        # Layer 3: escalation suppression (kargo scope)
        if await self._check_escalation_gate(service, "kargo"):
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
                await self.blackboard.clear_escalation_flag(service, scope="kargo")
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
