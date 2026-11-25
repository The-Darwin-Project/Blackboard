# BlackBoard/src/channels/approval_blocks.py
# @ai-rules:
# 1. [Constraint]: Pure Slack UI block generation for approval decisions.
# 2. [Constraint]: <= 100 lines.
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from ..models import ConversationTurn, WRITE_IN_OPTION_ID

_WRITEIN_HMAC_KEY: bytes = os.environ.get("SLACK_SIGNING_SECRET", "").encode("utf-8") or os.urandom(32)

def _safe_text(text: str, max_len: int) -> str:
    cleaned = text.replace("\n", " ").strip()
    return cleaned[:max_len-3] + "..." if len(cleaned) > max_len else cleaned

def sign_writein_metadata(payload: dict[str, Any], ttl_sec: int = 900) -> str:
    ts = int(time.time())
    data = json.dumps({"p": payload, "t": ts, "ttl": ttl_sec})
    b64_data = base64.b64encode(data.encode()).decode()
    sig = hmac.new(_WRITEIN_HMAC_KEY, b64_data.encode(), hashlib.sha256).hexdigest()
    return f"{b64_data}.{sig}"

def verify_writein_metadata(token: str) -> dict[str, Any]:
    if "." not in token:
        raise ValueError("Invalid token format")
    b64_data, sig = token.split(".", 1)
    expected_sig = hmac.new(_WRITEIN_HMAC_KEY, b64_data.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature mismatch")
    data = json.loads(base64.b64decode(b64_data).decode())
    if int(time.time()) > data["t"] + data["ttl"]:
        raise ValueError("Token expired")
    return data["p"]

def format_frozen_approval_blocks(plan_text: str, options: list, resolution: Any, md_to_mrkdwn=None, truncate=None) -> list[dict[str, Any]]:
    md_to_mrkdwn = md_to_mrkdwn or (lambda x: x)
    truncate = truncate or (lambda x: x)
    icon = ":white_check_mark:" if resolution.effect == "approve" else (":x:" if resolution.effect == "reject" else ":compass:")
    label = getattr(resolution, "write_in_text", None) or getattr(resolution, "option_label", None) or getattr(resolution, "option_id", "")
    res_text = f"{icon} *{label}* (by {getattr(resolution, 'resolved_by', 'system')})"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*:clipboard: Plan ready:*\n{truncate(md_to_mrkdwn(plan_text))}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": res_text}}
    ]

def build_approval_blocks(turn: ConversationTurn, event_id: str, md_to_mrkdwn=None, truncate=None) -> list[dict[str, Any]]:
    md_to_mrkdwn = md_to_mrkdwn or (lambda x: x)
    truncate = truncate or (lambda x: x)
    plan_text = turn.plan or turn.thoughts or 'Plan ready for review.'
    res = getattr(turn, "approval_resolution", None)
    if res is not None or getattr(turn, "pendingApproval", None) is False:
        if res is None:
            from ..models import ApprovalResolution
            res = ApprovalResolution(outcome="closed", effect="reject", resolved_by="system", option_id="auto_closed", option_label="Auto closed")
        return format_frozen_approval_blocks(plan_text, turn.approval_options or [], res, md_to_mrkdwn, truncate)
    
    blocks: list[dict[str, Any]] = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*:clipboard: Plan ready:*\n{truncate(md_to_mrkdwn(plan_text))}"}}]
    options = turn.approval_options
    if not options:
        blocks.append({"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "action_id": "darwin_approve", "value": event_id}, {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "action_id": "darwin_reject", "value": event_id}]})
        return blocks
    slack_options = []
    for opt in options:
        o_id, o_lbl, o_desc = (opt.get("id"), opt.get("label", ""), opt.get("description", "")) if isinstance(opt, dict) else (opt.id, opt.label, getattr(opt, "description", ""))
        slack_opt = {"text": {"type": "plain_text", "text": _safe_text(o_lbl, 75), "emoji": True}, "value": o_id}
        if o_desc: slack_opt["description"] = {"type": "plain_text", "text": _safe_text(o_desc, 75), "emoji": True}
        slack_options.append(slack_opt)
        
    slack_options.append({"text": {"type": "plain_text", "text": "Write-in", "emoji": True}, "value": WRITE_IN_OPTION_ID})
    blocks.append({"type": "actions", "elements": [{"type": "radio_buttons", "action_id": "darwin_approval_radio", "options": slack_options}, {"type": "button", "text": {"type": "plain_text", "text": "Submit"}, "style": "primary", "action_id": "darwin_approval_submit", "value": event_id}]})
    return blocks

def build_writein_modal(event_id: str, chan_id: str = "", thread_ts: str = "", message_ts: str = "", approval_id: str = "") -> dict[str, Any]:
    token = sign_writein_metadata({"e": event_id, "c": chan_id, "th": thread_ts, "m": message_ts, "a": approval_id})
    return {
        "type": "modal", "callback_id": "darwin_approval_writein_modal", "private_metadata": token,
        "title": {"type": "plain_text", "text": "Write-in Response"}, "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [{"type": "input", "block_id": "writein_input_block", "element": {"type": "plain_text_input", "action_id": "writein_input", "multiline": True}, "label": {"type": "plain_text", "text": "Provide your guidance or feedback"}}]
    }