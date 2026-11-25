# src/channels/slack_approval_helpers.py
# @ai-rules:
# 1. [Constraint]: Pure helper functions for Slack approvals, <= 100 lines.
from __future__ import annotations

import re
from typing import Any

from ..auth import UserContext

EVENT_ID_RE = re.compile(r"\A[a-zA-Z0-9_-]{1,64}\Z")


def extract_action_context(body: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Safely extract (raw_value, user_id, channel_id, thread_ts, message_ts) from a Slack action body."""
    if not isinstance(body, dict):
        return "", "", "", "", ""
    actions = body.get("actions")
    raw_val = actions[0].get("value") if isinstance(actions, list) and actions and isinstance(actions[0], dict) else ""
    val = raw_val if isinstance(raw_val, str) else ""
    user_obj = body.get("user")
    raw_user = user_obj.get("id") if isinstance(user_obj, dict) else ""
    user = raw_user if isinstance(raw_user, str) else ""
    chan_obj = body.get("channel")
    raw_chan = chan_obj.get("id") if isinstance(chan_obj, dict) else ""
    channel = raw_chan if isinstance(raw_chan, str) else ""
    msg = body.get("message")
    container = body.get("container")
    raw_ts = (msg.get("thread_ts") or msg.get("ts")) if isinstance(msg, dict) else ""
    thread_ts = raw_ts if isinstance(raw_ts, str) else ""
    msg_ts = (msg.get("ts") if isinstance(msg, dict) else None) or (container.get("message_ts") if isinstance(container, dict) else "")
    message_ts = msg_ts if isinstance(msg_ts, str) else ""
    return val, user, channel, thread_ts, message_ts

def extract_action_fields(body: dict[str, Any]) -> tuple[str, str, str, str]:
    """Backward-compatible extraction."""
    val, user, chan, thread, _ = extract_action_context(body)
    return val, user, chan, thread

def extract_view_fields(body: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Safely extract (private_metadata, user_id, input_value, chan_id, thread_ts) from a Slack view submission."""
    view = body.get("view", {})
    private_metadata = view.get("private_metadata", "")
    user_obj = body.get("user")
    user = user_obj.get("id") if isinstance(user_obj, dict) else ""
    
    state_values = view.get("state", {}).get("values", {})
    input_val = ""
    if "writein_input_block" in state_values:
        input_dict = state_values["writein_input_block"].get("writein_input", {})
        input_val = input_dict.get("value", "")
    
    return private_metadata, user, input_val, "", ""


async def get_slack_user_context(client: Any, user_id: str, auth_enabled: bool) -> UserContext:
    if not auth_enabled:
        return UserContext(user_id=user_id, display_name=f"<@{user_id}>")
    try:
        res = await client.users_info(user=user_id)
        if not res.get("ok"):
            return UserContext(user_id=user_id, display_name=f"<@{user_id}>")
        user_info = res["user"]
        prof = user_info.get("profile", {})
        email = prof.get("email")
        dname = prof.get("display_name") or prof.get("real_name") or user_info.get("name") or user_id
        return UserContext(user_id=user_id, email=email, display_name=dname)
    except Exception:
        return UserContext(user_id=user_id, display_name=f"<@{user_id}>")


async def post_slack_ephemeral_error(client: Any, channel: str, user: str, thread_ts: str, text: str) -> None:
    try:
        await client.chat_postEphemeral(
            channel=channel,
            user=user,
            thread_ts=thread_ts,
            text=text
        )
    except Exception:
        pass


def extract_selected_option(body: dict[str, Any]) -> dict[str, Any] | None:
    """Return selected radio option dict from a Slack block state payload."""
    state = body.get("state", {}).get("values", {})
    for block in state.values():
        for action in block.values():
            if isinstance(action, dict) and "selected_option" in action:
                return action["selected_option"]
    return None
