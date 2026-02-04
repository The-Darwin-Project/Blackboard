# BlackBoard/src/agents/aligner.py
"""
Agent 1: The Aligner (The Listener)

Role: Truth Maintenance & Noise Filtering
Nature: Hybrid Daemon (Python + Vertex AI Flash for configuration)

The Aligner processes incoming telemetry and updates the Blackboard layers.
It can be configured via natural language (e.g., "Ignore errors for 1h").

AIR GAP: This module may import vertexai (for Flash model) but NOT kubernetes or git.
"""
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
    - Configurable via natural language (Vertex AI Flash)
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self.filter_rules: list[FilterRule] = []
        self._model = None
        
        # Check if Vertex AI is configured
        self.vertex_enabled = bool(os.getenv("GCP_PROJECT"))
    
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
        
        # Delegate to Blackboard for storage
        await self.blackboard.process_telemetry(payload)
        
        return True
    
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
