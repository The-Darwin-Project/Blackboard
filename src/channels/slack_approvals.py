# BlackBoard/src/channels/slack_approvals.py
# @ai-rules:
# 1. [Constraint]: Register Slack Bolt handlers for approvals. <= 100 lines.
from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any

from .. import auth
from ..auth import get_user_from_slack
from ..models import ApprovalResolution, WRITE_IN_OPTION_ID
from ..routes.approval_decision import execute_approval_decision
from ..routes.approval_decision_helpers import DecisionRequest
from .approval_blocks import build_writein_modal, format_frozen_approval_blocks, verify_writein_metadata
from .slack_approval_helpers import (
    EVENT_ID_RE, extract_action_context, extract_selected_option,
    extract_view_fields, get_slack_user_context, post_slack_ephemeral_error,
)

logger = logging.getLogger(__name__)

def register_approval_handlers(app: Any, channel: Any) -> None:
    @app.action("darwin_approval_radio")
    async def handle_radio(ack: Any, body: dict, client: Any) -> None:
        await ack()

    @app.action("darwin_approval_submit")
    async def handle_submit(ack: Any, body: dict, client: Any, respond: Any = None) -> None:
        await ack()
        event_id, user_id, chan_id, thread_ts, msg_ts = extract_action_context(body)
        if not event_id or not EVENT_ID_RE.match(event_id): return
        selected = extract_selected_option(body)
        if not selected: return await post_slack_ephemeral_error(client, chan_id, user_id, thread_ts, ":warning: Please select an option.")
        opt_val = selected.get("value")
        if opt_val == WRITE_IN_OPTION_ID:
            try: await client.views_open(trigger_id=body.get("trigger_id"), view=build_writein_modal(event_id, chan_id, thread_ts, msg_ts))
            except Exception as e: logger.warning(f"Failed to open write-in modal: {e}")
            return
        await _process_decision(client, channel, event_id, user_id, chan_id, thread_ts, opt_val, message_ts=msg_ts)

    @app.view("darwin_approval_writein_modal")
    async def handle_writein_modal(ack: Any, body: dict, client: Any, respond: Any = None) -> None:
        meta, user_id, msg, _, _ = extract_view_fields(body)
        try:
            p = verify_writein_metadata(meta)
            event_id = p.get("e") or p.get("id", "")
            chan_id, thread_ts, msg_ts, approval_id = p.get("c", ""), p.get("th", ""), p.get("m", ""), p.get("a", "")
        except Exception: return await ack(response_action="errors", errors={"writein_input_block": "Invalid or expired session."})
        if not event_id or not EVENT_ID_RE.match(event_id): return await ack(response_action="errors", errors={"writein_input_block": "Invalid event ID."})
        if not msg.strip(): return await ack(response_action="errors", errors={"writein_input_block": "Message cannot be empty."})
        await ack()
        await _process_decision(client, channel, event_id, user_id, chan_id, thread_ts, WRITE_IN_OPTION_ID, msg, message_ts=msg_ts, approval_id=approval_id)

async def _process_decision(client, channel, event_id, user_id, chan_id, thread_ts, opt_id, msg=None, legacy_mode=None, req=None, message_ts=None, approval_id=None, decision=None):
    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if decision:
        user_ctx = get_user_from_slack(user_id, decision.display_name, decision.email, roles=channel._maintainer_roles(decision.email))
    elif hasattr(channel, "_authorize_plan_decision") and inspect.iscoroutinefunction(channel._authorize_plan_decision):
        decision = await channel._authorize_plan_decision(client, event_id=event_id, user=user_id, channel=chan_id, thread_ts=thread_ts, verb="approve")
        if not decision: return
        user_ctx = get_user_from_slack(user_id, decision.display_name, decision.email, roles=channel._maintainer_roles(decision.email))
    else: user_ctx = await get_slack_user_context(client, user_id, auth_enabled)
    
    out = await execute_approval_decision(
        blackboard=channel._blackboard, brain=channel._brain, event_id=event_id, user=user_ctx,
        auth_enabled=auth_enabled, req=req or DecisionRequest(option_id=opt_id or "", message=msg, approval_id=approval_id),
        legacy_mode=legacy_mode, source="slack", head_sha_resolver=None,
    )
    if out.kind == "auth_rejected" and chan_id: await post_slack_ephemeral_error(client, chan_id, user_id, thread_ts, ":no_entry_sign: Insufficient permissions")
    elif out.kind == "sha_drift" and chan_id:
        val = json.dumps({"e": event_id, "a": (req.approval_id if req else approval_id) or "", "o": opt_id or "", "s": out.actual_sha}) if opt_id else f"{event_id}:{out.actual_sha}"
        b = [{"type": "section", "text": {"type": "mrkdwn", "text": f":warning: HEAD SHA changed. Confirm for `{(out.actual_sha or 'unknown')[:8]}`?"}}, {"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Approve New SHA"}, "style": "primary", "action_id": "darwin_approve_sha", "value": val}]}]
        try: await client.chat_postEphemeral(channel=chan_id, user=user_id, thread_ts=thread_ts, text="SHA Drift", blocks=b)
        except Exception: pass
    elif out.kind != "ok" and chan_id:
        await post_slack_ephemeral_error(client, chan_id, user_id, thread_ts, ":warning: Approval blocked: Event state changed" if out.kind in ("not_found", "closed") else f":warning: {out.message}")
    elif out.kind == "ok" and chan_id:
        if message_ts and out.turn:
            res = getattr(out.turn, "approval_resolution", None)
            if not res:
                res = ApprovalResolution(outcome="closed", effect="approve", resolved_by=user_ctx.display_name, option_id=opt_id, option_label=opt_id, resolved_at=time.time())
            try: await client.chat_update(channel=chan_id, ts=message_ts, text="Decision recorded", blocks=format_frozen_approval_blocks(out.turn.thoughts or "", out.turn.approval_options or [], res))
            except Exception as e: logger.warning(f"Failed to freeze approval message: {e}")
        try: await channel._safe_react(client, chan_id, thread_ts, "white_check_mark")
        except Exception: pass