# BlackBoard/src/routes/approval_decision_helpers.py
# @ai-rules:
# 1. [Constraint]: Pure dataclasses and validation functions for approval routing.
# 2. [Constraint]: <= 100 lines.
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from ..models import ConversationTurn, WRITE_IN_OPTION_ID


class DecisionRequest(BaseModel):
    """Payload for POST /queue/{event_id}/decision."""
    approval_id: Optional[str] = None
    source: Optional[str] = None
    option_id: str = ""
    message: Optional[str] = Field(None, description="Required if option_id is __write_in__")
    write_in_text: Optional[str] = Field(None, description="Legacy write in text")
    image: Optional[str] = Field(None, description="Base64 data URI of an attached image")
    reject_reason: Optional[str] = Field(None, description="Legacy reject reason")
    expected_sha: Optional[str] = Field(None, description="Override for SHA drift confirmation")


@dataclass
class ApprovalDecisionOutcome:
    """The result of an execute_approval_decision attempt."""
    kind: str  # "ok", "auth_rejected", "not_waiting", "invalid_option", "invalid_image", "sha_drift"
    message: str
    turn: Optional[ConversationTurn] = None
    expected_sha: Optional[str] = None
    actual_sha: Optional[str] = None


def validate_image_attachment(image: str | None) -> str | None:
    """Validate base64 image constraints. Returns error message or None if OK."""
    if not image:
        return None
    if len(image) > 1_400_000:
        return "image_too_large"
    
    if not image.startswith("data:image/"):
        return "Invalid image URI scheme"
        
    mime_type = image.split(";")[0].split("/")[1]
    if mime_type not in ("png", "jpeg", "jpg", "webp", "gif"):
        return f"Unsupported image type: {mime_type}"
        
    try:
        header, b64_data = image.split(",", 1)
        b64_data = b64_data.strip()
        if len(b64_data) < 16:
            return "Image payload too small"
        raw_bytes = base64.b64decode(b64_data[:32])
        # Simple magic byte checks
        if mime_type == "png" and not raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "File content does not match PNG signature"
        elif mime_type in ("jpeg", "jpg") and not raw_bytes.startswith(b"\xff\xd8"):
            return "File content does not match JPEG signature"
        elif mime_type == "gif" and not raw_bytes.startswith(b"GIF8"):
            return "File content does not match GIF signature"
        elif mime_type == "webp" and not raw_bytes[8:12] == b"WEBP":
            return "File content does not match WEBP signature"
        base64.b64decode(b64_data, validate=True)
    except Exception:
        return "Invalid base64 encoding"

    return None


def resolve_selected_option(
    options: list, option_id: str | None, legacy_mode: str | None, msg: str | None,
) -> tuple[dict | None, ApprovalDecisionOutcome | None]:
    """Resolve and validate the selected option or write-in payload."""
    if option_id == WRITE_IN_OPTION_ID:
        if not msg or not msg.strip():
            return None, ApprovalDecisionOutcome(kind="invalid_option", message="Write-in requires a message")
        return {"id": WRITE_IN_OPTION_ID, "label": "Write-in", "effect": "steer"}, None
    matches = [
        o for o in options
        if (o.get("id") if isinstance(o, dict) else o.id) == option_id
        or (legacy_mode and (o.get("effect") if isinstance(o, dict) else o.effect) == legacy_mode)
    ]
    if legacy_mode and len(matches) > 1:
        return None, ApprovalDecisionOutcome(kind="ambiguous_options", message="Multiple options match this effect")
    if not matches:
        return None, ApprovalDecisionOutcome(kind="invalid_option", message="Invalid option selected")
    o = matches[0]
    sel = {"id": o.get("id"), "label": o.get("label", ""), "effect": o.get("effect")} if isinstance(o, dict) else {"id": o.id, "label": o.label, "effect": o.effect}
    return sel, None


