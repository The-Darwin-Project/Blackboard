# BlackBoard/src/channels/slack.py
# @ai-rules:
# 1. [Constraint]: Single Socket Mode connection. If Brain scales, only one replica enables Slack.
# 2. [Pattern]: agent_view model. DMs arrive as message.im events. Top-level DMs (no thread_ts) create events;
#    threaded replies map to existing events. No AsyncAssistant middleware — all routing is in on_dm_message.
# 3. [Pattern]: Phase 2 -- Aligner events auto-open #darwin-infra threads on brain.route (agent dispatched). Trivial auto-closed events stay silent.
# 4. [Pattern]: broadcast_handler routes by message["type"]. DM threads: brain_thinking -> setStatus only,
#    turn -> Block Kit. Legacy: brain_thinking -> emoji, turn -> Block Kit.
# 5. [Gotcha]: Bolt's AsyncIgnoringSelfEvents middleware prevents infinite loops from bot's own thread replies.
# 6. [Pattern]: safe_react fails gracefully if reactions:write scope is missing.
# 7. [Pattern]: _dm_context stores {channel, thread_ts, user_id, team_id, _last_status_at} per event for setStatus
#    calls and DM routing. Populated in on_dm_message create branch, handle_create_event_modal, and
#    open_dm_thread. Self-heals on reply if missing (restart recovery).
#    Lazy hydration via _ensure_dm_context() in broadcast_handler (protects against BRPOP race).
# 8. [Pattern]: _INTERNAL_TURNS (actor, action) frozenset prevents internal turns from leaking into
#    user Slack threads. Applied in _handle_legacy_turn via tuple matching. Extensible for non-brain
#    actors (e.g., system.notification). The is_quiet whitelist is the inverse for infra threads.
#    tool_result is handled separately: _USER_VISIBLE_TOOL_RESULTS whitelist + slack_thread_ts gate.
# 9. [Pattern]: SlackAccessGate (OCP Group-based) gates 8 entry points via _gate_check helper.
#    Intentionally ungated: handle_feedback (feedback on rejection messages).
#    Approve/reject share _authorize_plan_decision (gate -> closed-event -> identity -> can_approve_event).
#    Maintainers (SlackAccessGate.is_maintainer) get APPROVER_GROUPS/OBS_ADMIN_GROUPS roles only when
#    configured; unset groups yield no roles (fail-closed, never a synthesized "admin").
#    users_info returns AsyncSlackResponse (not a dict): read via .get(), never isinstance(dict).
#    Home tab forks to access-denied view for unauthorized users.
# 10. [Gotcha]: chat.postMessage(channel=user_id) returns the real DM channel_id in result["channel"].
#    Always use result["channel"] for mappings, never user_id.
# 11. [Pattern]: Tool-driven progress messages (feature-flagged via SLACK_PROGRESS_ENABLED) replace raw
#    LLM text streaming. On brain.tool_result turns in DM threads, _progress_ts/_progress_last_phrase
#    post/update a single ephemeral status message per event (see _TOOL_PROGRESS_PHRASES). Deleted via
#    chat_delete when brain.response arrives or on event_closed (orphan cleanup). _SLACK_API_TIMEOUT
#    (5s) on all Slack API calls in broadcast path. All chat.delete calls wrapped in try/except --
#    Block Kit response posting proceeds unconditionally even if cleanup fails.
# 12. [Pattern]: _ensure_dm_context lazy hydration: if _dm_context missing at broadcast time,
#    queries blackboard for DM channel events (source=slack, channel starts with "D").
#    Protects against Brain BRPOP race consuming event before on_dm_message dict assignment.
"""SlackChannel adapter -- bidirectional Slack integration via Socket Mode."""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, NamedTuple

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError

from .formatter import (
    format_turn, format_event_summary, get_turn_attachment_color,
    get_agent_notification_text, extract_tables, table_block_to_code_block,
    truncate_text, MAX_SECTION_TEXT,
)
from ..agents.event_namer import spawn_event_namer_task
from ..utils.prompt_sanitize import fallback_title
from ..models import ConversationTurn, EventEvidence

if TYPE_CHECKING:
    from ..agents.brain import Brain
    from ..slack_gate import SlackAccessGate
    from ..state.blackboard import BlackboardState

logger = logging.getLogger("darwin.slack")

_CANONICAL_WORKER_ROLES = (
    "architect", "sysadmin", "developer", "qe",
    "security_analyst", "code_reviewer", "explorer",
)
_WORKER_ACTIONS = (
    "execute", "plan_step", "run_command", "cancel",
    "error", "message", "huddle", "teammate",
)

_INTERNAL_TURNS = frozenset(
    {
        ("brain", "triage"), ("brain", "phase"), ("brain", "respond_jarvis"),
        ("brain", "hold_watch"), ("brain", "intermediate"),
        ("brain", "hold_watch_wake"), ("brain", "think"),
        ("brain", "plan"),
        ("system", "notification"),
        ("jarvis", "message"), ("jarvis", "evidence"), ("jarvis", "insight"),
        ("dispatcher", "acknowledge"), ("dispatcher", "connected"),
        ("dispatcher", "paused"), ("dispatcher", "failed"),
    }
    | {
        (role, action)
        for role in _CANONICAL_WORKER_ROLES
        for action in _WORKER_ACTIONS
    }
)

# Tools whose tool_result turns contain user-relevant confirmations/data.
# Maintenance: add new user-facing tools here when created.
_USER_VISIBLE_TOOL_RESULTS = frozenset({
    "take_note",
})

_SLACK_API_TIMEOUT = 5.0

# Tool-driven progress phrases shown in DM threads while FRIDAY works.
# Maintenance: add new phrases here as tools are added; unknown tools fall back
# to a generic phrase via .get().
_TOOL_PROGRESS_PHRASES: dict[str, str] = {
    "classify_event": "Assessing the situation...",
    "consult_deep_memory": "Checking knowledge base...",
    "refresh_github_context": "Reviewing GitHub status...",
    "refresh_gitlab_context": "Checking GitLab pipeline...",
    "search_open_incidents": "Looking for related incidents...",
    "set_phase": "Working on your request...",
    "take_note": "Taking notes...",
    "record_observation": "Taking notes...",
    "list_observations": "Reviewing observations...",
}


class _PlanDecision(NamedTuple):
    """Result of a passed approve/reject authorization check."""
    event_doc: Any
    display_name: str
    email: str
    clean_ident: str
    clean_name: str


class SlackChannel:
    """Adapter wrapping Slack Bolt AsyncApp with Socket Mode."""

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        infra_channel: str,
        mr_fallback_channel: str,
        blackboard: "BlackboardState",
        brain: "Brain",
        access_gate: "SlackAccessGate | None" = None,
    ) -> None:
        self._app_token = app_token
        self._access_gate = access_gate
        self._infra_channel = infra_channel
        self._mr_fallback_channel = mr_fallback_channel
        self._blackboard = blackboard
        self._brain = brain
        self._handler: AsyncSocketModeHandler | None = None
        self._user_name_cache: dict[str, tuple[str, float]] = {}
        self._user_email_cache: dict[str, str] = {}
        self._USER_CACHE_TTL = 3600
        self._thinking_msg: dict[str, tuple[str, str]] = {}  # event_id -> (channel, msg_ts)
        self._dm_context: dict[str, dict] = {}  # event_id -> {channel, thread_ts, user_id, team_id, _last_status_at}
        self._quiet_events: set[str] = set()  # events from @mention -- suppress noise, show only results

        # Tool-driven progress messages (DM only, feature-flagged)
        self._progress_ts: dict[str, str] = {}  # event_id -> Slack message ts
        self._progress_last_phrase: dict[str, str] = {}  # event_id -> last posted phrase (dedup)
        self._progress_failed: set[str] = set()  # event_id -> circuit breaker (skip after post/update failure)
        self._progress_locks: dict[str, asyncio.Lock] = {}  # event_id -> serializes post/update/cleanup
        self._progress_enabled = os.getenv("SLACK_PROGRESS_ENABLED", "false").lower() == "true"

        self._app = AsyncApp(token=bot_token)
        self._register_handlers()

    async def _resolve_display_name(self, client: Any, user_id: str) -> str:
        """Resolve Slack user_id to display name with TTL cache.

        ``users_info`` returns ``AsyncSlackResponse`` in production (not a ``dict``
        subclass), so the payload is read via ``.get()`` rather than ``isinstance(dict)``.
        Failed lookups or a missing ``user`` object are NOT cached: caching an empty
        email would make SlackAccessGate deny the user (``no_email``) until restart.
        """
        cached = self._user_name_cache.get(user_id)
        if cached and (time.time() - cached[1]) < self._USER_CACHE_TTL:
            return cached[0]
        try:
            info = await client.users_info(user=user_id)
            user_obj = info.get("user") if hasattr(info, "get") else None
            if not user_obj or not hasattr(user_obj, "get"):
                logger.warning(f"users_info for {user_id} returned no user object; not caching")
                return user_id
            profile = user_obj.get("profile") or {}
            name = profile.get("display_name") or user_obj.get("real_name") or user_id
            email = profile.get("email", "")
            name = str(name) if isinstance(name, str) else user_id
            email = str(email) if isinstance(email, str) else ""
            self._user_name_cache[user_id] = (name, time.time())
            self._user_email_cache[user_id] = email
            return name
        except Exception as e:
            logger.warning(f"Failed to resolve display name for {user_id}: {e}")
            return user_id

    def _get_cached_email(self, user_id: str) -> str | None:
        """Return cached email for a Slack user_id, or None on cache miss.

        Returns empty string if profile was resolved but had no email.
        Distinguishes 'not checked yet' (None) from 'checked, no email' ("")."""
        return self._user_email_cache.get(user_id)

    async def _gate_check(self, client: Any, user_id: str) -> bool:
        """Check if a Slack user is authorized via the OCP Group gate.

        Resolves email on cache miss (first interaction from new user).
        Returns True if no gate is configured (gate disabled).
        """
        if not self._access_gate:
            return True
        email = self._get_cached_email(user_id)
        if email is None:
            await self._resolve_display_name(client, user_id)
            email = self._get_cached_email(user_id) or ""
        return self._access_gate.check(email)

    def _maintainer_roles(self, email: str) -> list[str]:
        """Map a verified Slack maintainer email onto the configured approver groups.

        Maintainer status is established by SlackAccessGate (static maintainer emails).
        It grants approve/reject rights only when APPROVER_GROUPS (or, failing that,
        OBS_ADMIN_GROUPS) is configured: the maintainer is given those group names as
        roles so can_approve_event's role check applies unchanged. When both are unset
        this returns [] -- no placeholder role is synthesized -- so unowned events stay
        fail-closed (can_approve_event denies when auth is enabled).
        """
        from ..auth import APPROVER_GROUPS, OBS_ADMIN_GROUPS

        if not (self._access_gate and email and self._access_gate.is_maintainer(email)):
            return []
        return list(APPROVER_GROUPS or OBS_ADMIN_GROUPS)

    async def _authorize_plan_decision(
        self,
        client: Any,
        *,
        event_id: str,
        user: str,
        channel: str,
        thread_ts: str,
        verb: str,
    ) -> "_PlanDecision | None":
        """Shared gate + closed-event + identity + RBAC checks for approve/reject buttons.

        Returns a _PlanDecision when the user may act, or None after the denial (or
        closed/missing event) has been handled. ``verb`` is "approve" or "reject".
        """
        from ..auth import (
            get_user_from_slack, can_approve_event, resolve_approval_identity,
            DEX_ENABLED, TRUSTED_PROXY_ENABLED,
        )
        from ..slack_gate import _mask_email

        async def _deny(text: str, log_label: str) -> None:
            if not (channel and user):
                return
            try:
                await asyncio.wait_for(
                    client.chat_postEphemeral(
                        channel=channel, user=user, thread_ts=thread_ts, text=text,
                    ),
                    timeout=_SLACK_API_TIMEOUT,
                )
            except Exception as e:
                logger.warning(f"Slack {verb} {log_label} ephemeral failed: {e}")

        if not await self._gate_check(client, user):
            await _deny(
                ":lock: Access denied. Contact the app maintainer to be added to the authorized group.",
                "gate",
            )
            return None

        event_doc = await self._blackboard.get_event(event_id)
        if not event_doc or getattr(event_doc, "status", None) == "closed":
            return None

        display_name = await self._resolve_display_name(client, user)
        email = self._get_cached_email(user)
        email_str = email if isinstance(email, str) else ""
        clean_ident, clean_name = resolve_approval_identity(email_str, display_name, fallback=user)
        clean_name_str = clean_name if isinstance(clean_name, str) else user
        clean_ident_str = clean_ident if isinstance(clean_ident, str) else user

        user_ctx = get_user_from_slack(
            user, display_name, email_str, roles=self._maintainer_roles(email_str),
        )
        # auth_enabled passed explicitly (matching queue.py/dashboard_ws.py) rather than
        # relying on can_approve_event's bool(DEX_ENABLED or TRUSTED_PROXY_ENABLED) default --
        # Slack identity is always named regardless of Dex, but the APPROVER_GROUPS RBAC
        # gate this call enforces must still apply whenever either auth mode is on.
        auth_enabled = bool(DEX_ENABLED or TRUSTED_PROXY_ENABLED)
        if not can_approve_event(user_ctx, event_doc, auth_enabled=auth_enabled):
            logger.warning(
                f"Slack {verb} forbidden on {event_id} by {user} ({_mask_email(email_str)})"
            )
            noun = "approve" if verb == "approve" else "reject"
            plural = "Approvals" if verb == "approve" else "Rejections"
            await _deny(
                f":lock: You are not authorized to {noun} this plan on event {event_id}. "
                f"{plural} require ownership or approver permissions.",
                "forbidden",
            )
            return None

        return _PlanDecision(
            event_doc=event_doc,
            display_name=display_name,
            email=email_str,
            clean_ident=clean_ident_str,
            clean_name=clean_name_str,
        )

    @staticmethod
    def _build_prior_context(event_doc: Any) -> str:
        """Extract evidence + last agent/close turn from a closed event for follow-up seeding."""
        from datetime import datetime, timezone
        closed_at = getattr(event_doc, "closed_at", None)
        if closed_at:
            closed_dt = datetime.fromtimestamp(closed_at, tz=timezone.utc)
            age = datetime.now(timezone.utc) - closed_dt
            age_str = f"{int(age.total_seconds() // 3600)}h {int((age.total_seconds() % 3600) // 60)}m ago"
        else:
            age_str = "unknown time ago"
        turns = len(event_doc.conversation)
        parts = [
            f"This is a follow-up to event [{event_doc.id}] which closed {age_str} "
            f"({turns} turns, service: {event_doc.service}). "
            f"The closed event's context is attached below. "
            f"Use it as your starting point -- review what was done and continue from there || What is the next step?",
            "",
        ]
        evidence = getattr(getattr(event_doc, "event", None), "evidence", None)
        if evidence:
            display = getattr(evidence, "display_text", str(evidence))
            parts.append(f"Original evidence: {display[:500]}")
        close_reason = None
        last_action = None
        for t in reversed(event_doc.conversation):
            if t.action == "close" and not close_reason:
                close_reason = t.thoughts or t.result or ""
            elif t.actor != "user" and t.action in ("execute", "plan", "investigate") and not last_action:
                last_action = f"{t.actor}.{t.action}: {(t.result or t.thoughts or '')[:500]}"
            if close_reason and last_action:
                break
        if close_reason:
            parts.append(f"Close reason: {close_reason[:500]}")
        if last_action:
            parts.append(f"Last agent action: {last_action}")
        return "\n".join(parts)

    async def _create_followup_event(
        self, event_doc: Any, original_id: str, text: str,
        channel: str, thread_ts: str, user_id: str, display_name: str,
    ) -> str:
        """Create a follow-up event from a closed event with prior context seeding.

        Returns the new event ID. Caller handles UI-specific actions (set_title, react).
        """
        prior_context = self._build_prior_context(event_doc)
        # Seeded WITH the event (create_event persists them before LPUSH) so the Brain
        # never pops a blank event (evt-996e33ec). create_event renumbers them 1..N.
        ctx_turn = ConversationTurn(
            turn=1, actor="brain", action="context",
            thoughts=prior_context, source="system",
        )
        user_turn = ConversationTurn(
            turn=2, actor="user", action="message",
            thoughts=text, source="slack",
            user_name=display_name,
        )
        email = self._get_cached_email(user_id) or ""
        created_by_email = email or None
        fallback = fallback_title(text)
        new_event_id = await self._blackboard.create_event(
            source="slack",
            service=event_doc.service,
            reason=f"Follow-up on {original_id}: {text[:200]}",
            evidence=EventEvidence(
                display_text=f"Follow-up on [{original_id}]: {text}",
                source_type="slack",
                triggered_by=display_name,
                domain="disorder",
                severity="info",
            ),
            slack_channel_id=channel,
            slack_thread_ts=thread_ts,
            slack_user_id=user_id,
            created_by_email=created_by_email,
            initial_turns=[ctx_turn, user_turn],
            title=fallback,
            title_source="fallback",
        )
        if getattr(event_doc, "id", None) in self._quiet_events:
            self._quiet_events.add(new_event_id)
        try:
            spawn_event_namer_task(self._blackboard, self._brain, new_event_id, text, "slack")
        except Exception as e:
            logger.warning("Failed to spawn event namer task for %s: %s", new_event_id, e)
        await self._blackboard.set_slack_mapping(channel, thread_ts, new_event_id)
        return new_event_id

    def _register_handlers(self) -> None:
        """Register Slack event listeners on the Bolt app."""

        @self._app.command("/darwin")
        async def handle_darwin_command(ack: Any, body: dict, client: Any, respond: Any) -> None:
            await ack()
            text = (body.get("text", "")).strip()
            user_id = body.get("user_id", "")
            channel_id = body.get("channel_id", "")

            if not text:
                await respond(text="Usage: `/darwin <describe the issue or task>`")
                return

            if not await self._gate_check(client, user_id):
                if respond:
                    await respond(text=":lock: You don't have access to Darwin. Contact the app maintainer to be added.")
                return

            display_name = await self._resolve_display_name(client, user_id)
            email = self._get_cached_email(user_id) or ""
            created_by_email = email or None
            fallback = fallback_title(text)
            event_id = await self._blackboard.create_event(
                source="slack",
                service="general",
                reason=text,
                evidence=EventEvidence(
                    display_text=text,
                    source_type="slack",
                    triggered_by=display_name,
                    domain="disorder",
                    severity="info",
                ),
                created_by_email=created_by_email,
                initial_turns=[ConversationTurn(
                    turn=1, actor="user", action="message",
                    thoughts=text, source="slack",
                    user_name=display_name,
                )],
                title=fallback,
                title_source="fallback",
            )
            try:
                spawn_event_namer_task(self._blackboard, self._brain, event_id, text, "slack")
            except Exception as e:
                logger.warning("Failed to spawn event namer task for %s: %s", event_id, e)

            # Post visible thread-parent message
            event_doc = await self._blackboard.get_event(event_id)
            blocks = format_event_summary(event_doc) if event_doc else []
            result = await client.chat_postMessage(
                channel=channel_id,
                text=f"Event `{event_id}` created: {text}",
                blocks=blocks,
            )
            thread_ts = result["ts"]

            # Store forward (event -> slack) and reverse (slack -> event) mappings
            await self._blackboard.update_event_slack_context(
                event_id, channel_id, thread_ts, user_id,
            )
            await self._blackboard.set_slack_mapping(channel_id, thread_ts, event_id)

            await self._safe_react(client, channel_id, thread_ts, "ticket")
            logger.info(f"Slack /darwin: event {event_id} by {user_id} in {channel_id}")

        @self._app.event("app_mention")
        async def handle_app_mention(event: dict, client: Any) -> None:
            if event.get("bot_id") or event.get("subtype"):
                return

            channel = event.get("channel", "")
            user_id = event["user"]

            if not await self._gate_check(client, user_id):
                try:
                    await asyncio.wait_for(
                        client.chat_postEphemeral(
                            channel=channel, user=user_id,
                            text=":lock: You don't have access to Darwin. Contact the app maintainer to be added.",
                        ),
                        timeout=_SLACK_API_TIMEOUT,
                    )
                except Exception as e:
                    logger.debug(f"Slack app_mention gate ephemeral failed: {e}")
                return

            raw_text = event.get("text", "")
            text = re.sub(r"<@[A-Z0-9]+>\s*", "", raw_text, count=1).strip()

            if not text:
                return

            thread_ts = event.get("thread_ts", event["ts"])

            existing_event_id = await self._blackboard.get_event_by_slack_thread(channel, thread_ts)
            if existing_event_id:
                event_doc = await self._blackboard.get_event(existing_event_id)
                if event_doc and event_doc.status == "closed":
                    display_name = await self._resolve_display_name(client, user_id)
                    new_event_id = await self._create_followup_event(
                        event_doc, existing_event_id, text, channel, thread_ts, user_id, display_name,
                    )
                    await self._safe_react(client, channel, event["ts"], "brain")
                    logger.info(f"Slack @mention: smart-routed to new event {new_event_id} (original {existing_event_id} was closed)")
                    return
                elif event_doc and event_doc.status != "closed":
                    display_name = await self._resolve_display_name(client, user_id)
                    turn = ConversationTurn(
                        turn=len(event_doc.conversation) + 1,
                        actor="user", action="message",
                        thoughts=text, source="slack",
                        user_name=display_name,
                    )
                    await self._blackboard.append_turn(existing_event_id, turn)
                    self._brain.clear_waiting(existing_event_id)
                    await self._brain.resume_if_parked(existing_event_id)
                    self._brain.enqueue_for_processing(existing_event_id)
                    await self._safe_react(client, channel, event["ts"], "eyes")
                    logger.info(f"Slack @mention: reply on {existing_event_id} from {display_name}")
                    return

            display_name = await self._resolve_display_name(client, user_id)
            email = self._get_cached_email(user_id) or ""
            created_by_email = email or None
            fallback = fallback_title(text)
            event_id = await self._blackboard.create_event(
                source="slack",
                service="general",
                reason=text,
                evidence=EventEvidence(
                    display_text=text,
                    source_type="slack",
                    triggered_by=display_name,
                    domain="disorder",
                    severity="info",
                ),
                created_by_email=created_by_email,
                slack_channel_id=channel,
                slack_thread_ts=thread_ts,
                slack_user_id=user_id,
                initial_turns=[ConversationTurn(
                    turn=1, actor="user", action="message",
                    thoughts=text, source="slack",
                    user_name=display_name,
                )],
                title=fallback,
                title_source="fallback",
            )
            try:
                spawn_event_namer_task(self._blackboard, self._brain, event_id, text, "slack")
            except Exception as e:
                logger.warning("Failed to spawn event namer task for %s: %s", event_id, e)

            await self._blackboard.set_slack_mapping(channel, thread_ts, event_id)

            self._quiet_events.add(event_id)
            await self._safe_react(client, channel, event["ts"], "brain")
            logger.info(f"Slack @mention: event {event_id} (quiet) by {user_id} in thread {thread_ts}")

        @self._app.event("message")
        async def on_dm_message(event: dict, client: Any) -> None:
            if event.get("bot_id") or event.get("subtype"):
                return

            text = event.get("text", "")
            if re.match(r"<@[A-Z0-9]+>", text):
                return

            channel_type = event.get("channel_type", "")
            channel = event.get("channel", "")
            if channel_type != "im" and channel != self._infra_channel:
                return

            thread_ts = event.get("thread_ts")
            is_top_level_dm = False

            if thread_ts is None:
                if channel_type != "im":
                    return
                thread_ts = event["ts"]
                is_top_level_dm = True

            user = event["user"]

            if not await self._gate_check(client, user):
                if is_top_level_dm:
                    await client.chat_postMessage(
                        channel=channel, thread_ts=thread_ts,
                        text=":lock: You don't have access to Darwin.",
                    )
                return

            event_id = await self._blackboard.get_event_by_slack_thread(channel, thread_ts)

            # Widened create gate: top-level DMs AND cutover window where message.im
            # arrives WITH thread_ts for threads we haven't mapped yet.
            if not event_id and channel_type == "im":
                display_name = await self._resolve_display_name(client, user)
                user_email = self._get_cached_email(user)
                team_id = event.get("team", "")

                try:
                    await client.assistant_threads_setStatus(
                        channel_id=channel, thread_ts=thread_ts,
                        status="FRIDAY is thinking...",
                    )
                except Exception as e:
                    logger.debug(f"setStatus failed (non-fatal): {e}")

                fallback = fallback_title(text)
                event_id = await self._blackboard.create_event(
                    source="slack",
                    service="general",
                    reason=text,
                    evidence=EventEvidence(
                        display_text=text,
                        source_type="slack",
                        triggered_by=display_name,
                        domain="disorder",
                        severity="info",
                    ),
                    created_by_email=user_email or None,
                    slack_channel_id=channel,
                    slack_thread_ts=thread_ts,
                    slack_user_id=user,
                    initial_turns=[ConversationTurn(
                        turn=1, actor="user", action="message",
                        thoughts=text, source="slack",
                        user_name=display_name,
                    )],
                    title=fallback,
                    title_source="fallback",
                )
                try:
                    spawn_event_namer_task(self._blackboard, self._brain, event_id, text, "slack")
                except Exception as e:
                    logger.warning("Failed to spawn event namer task for %s: %s", event_id, e)
                self._dm_context[event_id] = {
                    "channel": channel, "thread_ts": thread_ts,
                    "user_id": user, "team_id": team_id,
                    "_last_status_at": time.time(),
                }
                await self._blackboard.set_slack_mapping(channel, thread_ts, event_id)

                try:
                    await client.assistant_threads_setTitle(
                        channel_id=channel, thread_ts=thread_ts,
                        title=f"{event_id}: {text[:50]}",
                    )
                except Exception as e:
                    logger.debug(f"setTitle failed for {event_id}: {e}")

                logger.info(f"agent_view DM: new event {event_id} by {user}")
                return

            if not event_id:
                return

            event_doc = await self._blackboard.get_event(event_id)
            if not event_doc:
                return

            display_name = await self._resolve_display_name(client, user)
            team_id = event.get("team", "")

            # Hydrate _dm_context on EVERY reply (self-healing after restart/legacy events)
            if channel_type == "im" and event_id not in self._dm_context:
                self._dm_context[event_id] = {
                    "channel": channel, "thread_ts": thread_ts,
                    "user_id": user, "team_id": team_id,
                    "_last_status_at": 0,
                }

            if event_doc.status == "closed":
                new_event_id = await self._create_followup_event(
                    event_doc, event_id, text, channel, thread_ts, user, display_name,
                )
                if channel_type == "im":
                    self._dm_context[new_event_id] = {
                        "channel": channel, "thread_ts": thread_ts,
                        "user_id": user, "team_id": team_id,
                        "_last_status_at": 0,
                    }
                try:
                    await client.assistant_threads_setTitle(
                        channel_id=channel, thread_ts=thread_ts,
                        title=f"{new_event_id}: {text[:50]}",
                    )
                except Exception:
                    pass
                await self._safe_react(client, channel, event["ts"], "brain")
                logger.info(f"DM reply: follow-up {new_event_id} (original {event_id} closed)")
                return

            is_channel_thread = channel_type != "im"

            turn = ConversationTurn(
                turn=len(event_doc.conversation) + 1,
                actor="user", action="message",
                thoughts=text, source="slack",
                user_name=display_name,
            )
            await self._blackboard.append_turn(event_id, turn)

            if is_channel_thread:
                await self._safe_react(client, channel, event["ts"], "eyes")
                logger.info(f"Infra thread reply on {event_id} from {display_name}")
            else:
                self._brain.clear_waiting(event_id)
                await self._brain.resume_if_parked(event_id)
                self._brain.enqueue_for_processing(event_id)
                await self._safe_react(client, channel, event["ts"], "eyes")
                if event_doc.slack_channel_id and event_doc.slack_thread_ts and event_doc.slack_channel_id != channel:
                    try:
                        workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                        ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                        thread_link = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
                        await client.chat_postMessage(
                            channel=channel, thread_ts=thread_ts,
                            text=f":white_check_mark: Message received. :point_right: <{thread_link}|Continue in #darwin-infra>",
                        )
                    except Exception as e:
                        logger.warning(f"DM ack failed for {event_id}: {e}")
                logger.info(f"DM reply on {event_id} from {display_name}")

        @self._app.action("darwin_approve")
        async def handle_approve(ack: Any, body: dict, client: Any) -> None:
            await ack()
            actions = body.get("actions", [])
            event_id = actions[0].get("value", "") if actions and isinstance(actions[0], dict) else ""
            user = body.get("user", {}).get("id", "")
            channel = body.get("channel", {}).get("id", "")
            msg = body.get("message", {})
            thread_ts = msg.get("thread_ts") or msg.get("ts", "")

            from ..utils.vcs_approval import resolve_live_head_sha

            decision = await self._authorize_plan_decision(
                client, event_id=event_id, user=user, channel=channel,
                thread_ts=thread_ts, verb="approve",
            )
            if decision is None:
                return
            event_doc = decision.event_doc
            email_str = decision.email
            clean_name_str = decision.clean_name
            clean_ident_str = decision.clean_ident

            mr_id, mr_sha = await resolve_live_head_sha(event_doc)

            stamp_res = self._blackboard.stamp_event(
                event_id,
                approved_by=clean_ident_str,
                approved_mr_id=mr_id,
                approved_mr_sha=mr_sha,
            )
            if inspect.isawaitable(stamp_res):
                await stamp_res

            thought_msg = "User approved the plan."
            if mr_id and mr_sha:
                thought_msg = f"User approved plan for MR/PR !{mr_id} at HEAD {mr_sha[:8]}."

            conv_len = len(event_doc.conversation) if event_doc and event_doc.conversation else 0
            turn = ConversationTurn(
                turn=conv_len + 1,
                actor="user",
                action="approve",
                thoughts=thought_msg,
                source="slack",
                user=clean_name_str,
                user_name=clean_name_str,
                user_email=email_str,
                approved_by=clean_ident_str,
                approved_mr_id=mr_id,
                approved_mr_sha=mr_sha,
            )
            await self._blackboard.append_turn(event_id, turn)
            self._brain.clear_waiting(event_id)
            await self._brain.resume_if_parked(event_id)
            self._brain.enqueue_for_processing(event_id)
            await self._safe_react(client, channel, thread_ts, "white_check_mark")
            logger.info(f"Slack approve on {event_id} by {user} (mr_id={mr_id}, sha={mr_sha})")

        @self._app.action("darwin_reject")
        async def handle_reject(ack: Any, body: dict, client: Any) -> None:
            await ack()
            actions = body.get("actions", [])
            event_id = actions[0].get("value", "") if actions and isinstance(actions[0], dict) else ""
            user = body.get("user", {}).get("id", "")
            channel = body.get("channel", {}).get("id", "")
            msg = body.get("message", {})
            thread_ts = msg.get("thread_ts") or msg.get("ts", "")

            decision = await self._authorize_plan_decision(
                client, event_id=event_id, user=user, channel=channel,
                thread_ts=thread_ts, verb="reject",
            )
            if decision is None:
                return
            event_doc = decision.event_doc
            email_str = decision.email
            clean_name_str = decision.clean_name

            # A rejection supersedes any prior approval stamp (see queue.py reject_event) --
            # otherwise GET /{event_id}/approval keeps reporting a stale approved_mr_sha.
            if event_doc.approved_by or event_doc.approved_mr_id or event_doc.approved_mr_sha:
                clear_res = self._blackboard.stamp_event(
                    event_id, approved_by=None, approved_mr_id=None, approved_mr_sha=None,
                )
                if inspect.isawaitable(clear_res):
                    await clear_res

            conv_len = len(event_doc.conversation) if event_doc and event_doc.conversation else 0
            turn = ConversationTurn(
                turn=conv_len + 1,
                actor="user",
                action="reject",
                thoughts="User rejected the plan.",
                source="slack",
                user=clean_name_str,
                user_name=clean_name_str,
                user_email=email_str,
            )
            await self._blackboard.append_turn(event_id, turn)
            self._brain.clear_waiting(event_id)
            await self._brain.resume_if_parked(event_id)
            self._brain.enqueue_for_processing(event_id)
            await self._safe_react(client, channel, thread_ts, "x")
            logger.info(f"Slack reject on {event_id} by {user}")

        @self._app.action("darwin_feedback")
        async def handle_feedback(ack: Any, body: dict, client: Any) -> None:
            await ack()
            actions = body.get("actions", [])
            feedback = actions[0].get("value") if actions and isinstance(actions[0], dict) else ""
            user_id = (body.get("user") or {}).get("id", "")
            channel_id = (body.get("channel") or {}).get("id", "")
            msg = body.get("message") or {}
            msg_ts = msg.get("ts", "")
            logger.info(f"Feedback: {feedback} from {user_id} on {msg_ts}")
            text = (
                "Thanks for the feedback!"
                if feedback == "positive"
                else "Sorry about that. Your feedback helps Darwin improve."
            )
            if channel_id and user_id:
                try:
                    await asyncio.wait_for(
                        client.chat_postEphemeral(
                            channel=channel_id, user=user_id,
                            thread_ts=msg_ts, text=text,
                        ),
                        timeout=_SLACK_API_TIMEOUT,
                    )
                except Exception as e:
                    logger.warning(f"Slack feedback ephemeral failed: {e}")

        @self._app.event("app_home_opened")
        async def handle_app_home_opened(event: dict, client: Any) -> None:
            tab = event.get("tab")
            user_id = event["user"]

            if tab == "messages":
                try:
                    prompts: list[dict[str, str]] = []
                    authorized = await self._gate_check(client, user_id)
                    if authorized:
                        event_ids = await self._blackboard.get_active_events()
                        if event_ids:
                            prompts.append({
                                "title": f"What's happening with {event_ids[0]}?",
                                "message": f"Give me a full status update on event {event_ids[0]} -- current phase, what agents have done, and what's pending.",
                            })
                    prompts.append({
                        "title": "Run a pipeline retest",
                        "message": "Retest the latest failed pipeline on this MR: <paste MR URL>",
                    })
                    prompts.append({
                        "title": "Investigate a failure",
                        "message": "Investigate why this service is failing: <paste service name or error>",
                    })
                    await client.assistant_threads_setSuggestedPrompts(
                        channel_id=event.get("channel", ""),
                        prompts=prompts,
                    )
                except Exception as e:
                    logger.debug(f"setSuggestedPrompts failed: {e}")
                return

            if tab != "home":
                return
            try:
                await self._publish_home_tab(client, user_id)
            except Exception as e:
                logger.warning(f"Home tab publish failed for {user_id}: {e}")

        @self._app.action("darwin_home_create_event")
        async def handle_home_create_event(ack: Any, body: dict, client: Any) -> None:
            await ack()
            if not await self._gate_check(client, body["user"]["id"]):
                return
            await client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "darwin_create_event_modal",
                    "title": {"type": "plain_text", "text": "Create Event"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "event_description",
                            "label": {"type": "plain_text", "text": "Describe the issue or task"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "description_input",
                                "multiline": True,
                                "placeholder": {"type": "plain_text", "text": "e.g., darwin-store backend is returning 500 errors on /products"},
                            },
                        },
                    ],
                },
            )

        @self._app.view("darwin_create_event_modal")
        async def handle_create_event_modal(ack: Any, body: dict, client: Any, view: dict) -> None:
            await ack()
            if not await self._gate_check(client, body["user"]["id"]):
                return
            text = view["state"]["values"]["event_description"]["description_input"]["value"]
            user_id = body["user"]["id"]
            if not text or not text.strip():
                return

            display_name = await self._resolve_display_name(client, user_id)
            email = self._get_cached_email(user_id) or ""
            created_by_email = email or None
            fallback = fallback_title(text)
            event_id = await self._blackboard.create_event(
                source="slack",
                service="general",
                reason=text.strip(),
                evidence=EventEvidence(
                    display_text=text.strip(),
                    source_type="slack",
                    triggered_by=display_name,
                    domain="disorder",
                    severity="info",
                ),
                created_by_email=created_by_email,
                initial_turns=[ConversationTurn(
                    turn=1, actor="user", action="message",
                    thoughts=text.strip(), source="slack",
                    user_name=display_name,
                )],
                title=fallback,
                title_source="fallback",
            )
            try:
                spawn_event_namer_task(self._blackboard, self._brain, event_id, text.strip(), "slack")
            except Exception as e:
                logger.warning("Failed to spawn event namer task for %s: %s", event_id, e)
            event_doc = await self._blackboard.get_event(event_id)
            blocks = format_event_summary(event_doc) if event_doc else []
            result = await client.chat_postMessage(
                channel=user_id,
                text=f"Event `{event_id}` created: {text.strip()[:100]}",
                blocks=blocks,
            )
            thread_ts = result["ts"]
            dm_channel = result["channel"]

            await self._blackboard.update_event_slack_context(
                event_id, dm_channel, thread_ts, user_id,
            )
            await self._blackboard.set_slack_mapping(dm_channel, thread_ts, event_id)
            self._dm_context[event_id] = {
                "channel": dm_channel, "thread_ts": thread_ts,
                "user_id": user_id, "team_id": "",
                "_last_status_at": 0,
            }
            logger.info(f"Home tab create event: {event_id} by {user_id} in {dm_channel} (thread={thread_ts})")

        @self._app.action("darwin_home_open_dashboard")
        async def handle_home_open_dashboard(ack: Any, body: dict) -> None:
            await ack()

    async def _publish_home_tab(self, client: Any, user_id: str) -> None:
        """Gather data and publish the Home tab view for a user."""
        if not await self._gate_check(client, user_id):
            from .formatter import build_access_denied_home_view
            view = build_access_denied_home_view()
            await client.views_publish(user_id=user_id, view=view)
            return

        from .formatter import build_home_tab_view

        event_ids = await self._blackboard.get_active_events()
        active_events = []
        for eid in event_ids:
            event = await self._blackboard.get_event(eid)
            if event:
                active_events.append({
                    "id": event.id,
                    "source": event.source,
                    "service": event.service,
                    "subject_type": getattr(event, "subject_type", "service"),
                    "status": event.status.value,
                    "reason": event.event.reason,
                    "turns": len(event.conversation),
                })

        import time as _time
        cutoff = _time.time() - 86400
        closed_ids = await self._blackboard.redis.zrangebyscore(
            self._blackboard.EVENT_CLOSED, cutoff, "+inf",
        )
        recent_closed = []
        if closed_ids:
            async with self._blackboard.redis.pipeline(transaction=False) as pipe:
                for eid in closed_ids:
                    pipe.get(f"{self._blackboard.EVENT_PREFIX}{eid}")
                raw = await pipe.execute()
            import json as _json
            for raw_doc in raw:
                if not raw_doc:
                    continue
                try:
                    doc = _json.loads(raw_doc)
                    last_turn = doc.get("conversation", [{}])[-1] if doc.get("conversation") else {}
                    recent_closed.append({
                        "id": doc.get("id", "?"),
                        "service": doc.get("service", "general"),
                        "summary": last_turn.get("thoughts") or last_turn.get("result") or "Closed",
                    })
                except Exception:
                    continue
        recent_closed = recent_closed[-8:]

        agents = await self._brain.list_connected_agents()

        import os as _os
        dashboard_url = _os.getenv("DARWIN_DASHBOARD_URL", "")

        view = build_home_tab_view(active_events, recent_closed, agents, dashboard_url)
        await client.views_publish(user_id=user_id, view=view)

    # =========================================================================
    # Broadcast handler (registered on Brain via register_channel)
    # Unified Block Kit router for all thread types.
    # =========================================================================

    async def broadcast_handler(self, message: dict) -> None:
        """Route Brain broadcasts to Block Kit path for all thread types."""
        msg_type = message.get("type")
        event_id = message.get("event_id", "")
        is_dm = await self._ensure_dm_context(event_id)
        is_quiet = event_id in self._quiet_events

        if msg_type == "brain_thinking":
            if is_quiet:
                if event_id not in self._thinking_msg:
                    await self._handle_legacy_thinking(event_id, message)
                return

            if is_dm:
                await self._refresh_thinking_status(event_id)
            else:
                await self._handle_legacy_thinking(event_id, message)
            return

        if msg_type == "brain_thinking_done":
            if is_dm:
                await self._clear_thinking_status(event_id)
            return

        if msg_type == "turn":
            turn_data = message.get("turn", {})
            action = turn_data.get("action", "")
            if is_quiet:
                if action not in ("execute", "request_approval", "error", "wait", "close", "response"):
                    return
            await self._handle_legacy_turn(event_id, message)

        elif msg_type == "event_status_changed":
            status = message.get("status")
            if status == "deferred":
                # Event deferred — clean up progress bubble (FRIDAY is waiting, not working)
                await self._cleanup_progress_bubble(event_id, "deferred")

        elif msg_type == "event_title_updated":
            title = message.get("title")
            if title and event_id:
                event_doc = await self._blackboard.get_event(event_id)
                if event_doc and event_doc.slack_channel_id and event_doc.slack_thread_ts:
                    if event_doc.slack_channel_id.startswith("D") or is_dm:
                        try:
                            await self._app.client.assistant_threads_setTitle(
                                channel_id=event_doc.slack_channel_id,
                                thread_ts=event_doc.slack_thread_ts,
                                title=title[:100],
                            )
                        except Exception as e:
                            logger.debug("Slack title sync ignored: %s", e)

        elif msg_type == "event_closed":
            # Orphan progress message cleanup
            await self._cleanup_progress_bubble(event_id, "event_closed")

            # Orphan thinking indicator message cleanup for channel threads (T-8)
            thinking = self._thinking_msg.pop(event_id, None)
            if thinking:
                ch, ts = (thinking["channel"], thinking["ts"]) if isinstance(thinking, dict) else thinking
                if ch and ts and not ch.startswith("D"):
                    try:
                        await asyncio.wait_for(
                            self._app.client.chat_delete(channel=ch, ts=ts),
                            timeout=_SLACK_API_TIMEOUT,
                        )
                    except Exception as exc:
                        logger.debug("Failed to delete thinking message on event_closed for %s: %s", event_id, exc)

            event_doc = await self._blackboard.get_event(event_id)
            if event_doc and event_doc.slack_thread_ts:
                summary = message.get("summary", "Event closed.")
                await self._post_to_thread(
                    event_doc.slack_channel_id,
                    event_doc.slack_thread_ts,
                    f":heavy_check_mark: *Event `{event_id}` closed:* {summary}",
                )
                await self._safe_react(
                    self._app.client, event_doc.slack_channel_id,
                    event_doc.slack_thread_ts, "heavy_check_mark",
                )
                await self._blackboard.delete_slack_mapping(
                    event_doc.slack_channel_id, event_doc.slack_thread_ts,
                )
            self._dm_context.pop(event_id, None)
            self._thinking_msg.pop(event_id, None)
            self._quiet_events.discard(event_id)
            self._progress_locks.pop(event_id, None)

    # =========================================================================
    # DM status path (agent_view — setStatus debounce)
    # =========================================================================

    async def _refresh_thinking_status(self, event_id: str) -> None:
        """Refresh setStatus for DM events with 20s debounce."""
        ctx = self._dm_context.get(event_id)
        if not ctx:
            return
        now = time.time()
        if now - ctx.get("_last_status_at", 0) < 20:
            return
        ctx["_last_status_at"] = now
        try:
            await asyncio.wait_for(
                self._app.client.assistant_threads_setStatus(
                    channel_id=ctx["channel"], thread_ts=ctx["thread_ts"],
                    status="FRIDAY is thinking...",
                ),
                timeout=_SLACK_API_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"setStatus refresh failed for {event_id}: {e}")

    async def _clear_thinking_status(self, event_id: str) -> None:
        """Clear setStatus for DM events."""
        ctx = self._dm_context.get(event_id)
        if not ctx:
            return
        # Reset phrase dedup so the next tool progress phrase re-posts after a clear.
        ctx.pop("_last_tool_phrase", None)
        try:
            await asyncio.wait_for(
                self._app.client.assistant_threads_setStatus(
                    channel_id=ctx["channel"], thread_ts=ctx["thread_ts"],
                    status="",
                ),
                timeout=_SLACK_API_TIMEOUT,
            )
        except Exception as e:
            logger.debug(f"Clear setStatus failed for {event_id}: {e}")

    async def _ensure_dm_context(self, event_id: str) -> bool:
        """Lazily hydrate _dm_context from event document if missing. Returns True if DM."""
        if event_id in self._dm_context:
            return True
        event_doc = await self._blackboard.get_event(event_id)
        if not event_doc:
            return False
        ch = event_doc.slack_channel_id or ""
        if event_doc.source == "slack" and ch.startswith("D"):
            self._dm_context[event_id] = {
                "channel": ch,
                "thread_ts": event_doc.slack_thread_ts or "",
                "user_id": event_doc.slack_user_id or "",
                "team_id": "",
                "_last_status_at": 0,
            }
            return True
        return False

    def _get_progress_lock(self, event_id: str) -> asyncio.Lock:
        """Return the per-event lock serializing progress-bubble post/update/cleanup.

        Lazily initializes _progress_locks so this works even for instances built
        via SlackChannel.__new__() (as the test suite does) without running __init__.
        """
        locks = getattr(self, "_progress_locks", None)
        if locks is None:
            locks = {}
            self._progress_locks = locks
        lock = locks.get(event_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[event_id] = lock
        return lock

    async def _cleanup_progress_bubble(self, event_id: str, reason: str) -> None:
        """Pop progress-bubble tracking state for event_id and delete its Slack message.

        Shared teardown for the defer, close, and response call sites -- the
        tool-driven-progress equivalent of the old single _cleanup_stream() helper.
        """
        async with self._get_progress_lock(event_id):
            progress_ts = self._progress_ts.pop(event_id, None)
            self._progress_last_phrase.pop(event_id, None)
            self._progress_failed.discard(event_id)
        if not progress_ts:
            return
        ctx = self._dm_context.get(event_id, {})
        try:
            await asyncio.wait_for(
                self._app.client.chat_delete(
                    channel=ctx.get("channel", ""), ts=progress_ts,
                ),
                timeout=_SLACK_API_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"Progress cleanup ({reason}) failed for {event_id}: {e}")

    # =========================================================================
    # Legacy path (channel threads, infra threads, all turn delivery)
    # =========================================================================

    async def _handle_legacy_thinking(self, event_id: str, message: dict) -> None:
        """Post emoji thinking indicator for non-Assistant threads."""
        if event_id in self._thinking_msg:
            return
        event_doc = await self._blackboard.get_event(event_id)
        if not event_doc or not event_doc.slack_thread_ts:
            return
        try:
            result = await self._app.client.chat_postMessage(
                channel=event_doc.slack_channel_id,
                thread_ts=event_doc.slack_thread_ts,
                text=":thinkingemoji: Darwin is thinking...",
            )
            self._thinking_msg[event_id] = (event_doc.slack_channel_id, result["ts"])
        except Exception as e:
            logger.warning(f"Slack thinking indicator failed: {e}")

    async def _handle_tool_progress(self, turn: ConversationTurn, event_doc: Any) -> None:
        """Update DM assistant status and channel thinking message with active tool progress."""
        if not turn.waitingFor:
            return

        event_id = getattr(event_doc, "id", "")
        phrase = _TOOL_PROGRESS_PHRASES.get(turn.waitingFor, "FRIDAY is working...")

        # Channel thinking indicator update (T-7)
        if event_id in self._thinking_msg:
            thinking = self._thinking_msg[event_id]
            ch, ts = (thinking["channel"], thinking["ts"]) if isinstance(thinking, dict) else thinking
            if ch and ts:
                try:
                    await asyncio.wait_for(
                        self._app.client.chat_update(
                            channel=ch,
                            ts=ts,
                            text=f":thinkingemoji: {phrase}",
                        ),
                        timeout=_SLACK_API_TIMEOUT,
                    )
                except Exception as exc:
                    logger.debug("Failed to update channel thinking indicator for %s: %s", event_id, exc)
                    # Keep the tracking entry on transient errors so the indicator can still
                    # be deleted later; drop it only when Slack says the message is gone.
                    if isinstance(exc, SlackApiError) and getattr(exc, "response", None) is not None:
                        err = exc.response.get("error") if hasattr(exc.response, "get") else None
                        if err in ("message_not_found", "channel_not_found"):
                            self._thinking_msg.pop(event_id, None)

        # DM assistant status update
        if event_id in self._dm_context:
            ctx = self._dm_context[event_id]
            if ctx.get("_last_tool_phrase") != phrase:
                ctx["_last_tool_phrase"] = phrase
                try:
                    await asyncio.wait_for(
                        self._app.client.assistant_threads_setStatus(
                            channel_id=ctx["channel"],
                            thread_ts=ctx["thread_ts"],
                            status=phrase,
                        ),
                        timeout=_SLACK_API_TIMEOUT,
                    )
                except Exception as e:
                    logger.debug("assistant_threads_setStatus failed for %s: %s", event_id, e)

            # Progress message update (whitelist-independent, DM only) -- fires
            # BEFORE the _USER_VISIBLE_TOOL_RESULTS gate.
            if (
                self._progress_enabled
                and event_id not in self._progress_failed
            ):
                async with self._get_progress_lock(event_id):
                    if self._progress_last_phrase.get(event_id) != phrase:
                        try:
                            if event_id not in self._progress_ts:
                                result = await asyncio.wait_for(
                                    self._app.client.chat_postMessage(
                                        channel=ctx["channel"], thread_ts=ctx["thread_ts"],
                                        text=phrase,
                                    ),
                                    timeout=_SLACK_API_TIMEOUT,
                                )
                                self._progress_ts[event_id] = result["ts"]
                            else:
                                await asyncio.wait_for(
                                    self._app.client.chat_update(
                                        channel=ctx["channel"], ts=self._progress_ts[event_id],
                                        text=phrase,
                                    ),
                                    timeout=_SLACK_API_TIMEOUT,
                                )
                            self._progress_last_phrase[event_id] = phrase
                        except Exception as e:
                            logger.warning(f"Progress message failed for {event_id}: {e}")
                            self._progress_failed.add(event_id)

    async def _handle_legacy_turn(self, event_id: str, message: dict) -> None:
        """Post turn via Block Kit for all thread types (DM + legacy)."""
        event_doc = await self._blackboard.get_event(event_id)
        if not event_doc:
            return
        turn = ConversationTurn(**message["turn"])

        if turn.actor == "brain" and turn.action == "response":
            # Clean up progress message before posting the Block Kit response.
            # Always proceeds to post regardless of chat_delete success/failure.
            await self._cleanup_progress_bubble(event_id, "response")

        if turn.actor == "brain" and turn.action == "thoughts":
            return

        if turn.actor == "brain" and turn.action == "tool_result":
            await self._handle_tool_progress(turn, event_doc)
            if not (event_doc.slack_thread_ts and turn.waitingFor in _USER_VISIBLE_TOOL_RESULTS):
                return

        if (turn.actor, turn.action) in _INTERNAL_TURNS:
            return

        if (
            not event_doc.slack_thread_ts
            and event_doc.source in ("aligner", "headhunter")
            and self._infra_channel
            and turn.actor == "brain"
            and turn.action in ("triage", "route")
        ):
            logger.info(f"Opening infra thread for {event_id} (source={event_doc.source}, channel={self._infra_channel})")
            await self.open_infra_thread(event_doc, event_doc.event.reason)
            event_doc = await self._blackboard.get_event(event_id)
        elif not event_doc.slack_thread_ts and event_doc.source in ("aligner", "headhunter"):
            logger.warning(
                f"Infra thread skipped for {event_id}: "
                f"thread_ts={event_doc.slack_thread_ts}, source={event_doc.source}, "
                f"infra_channel={'set' if self._infra_channel else 'EMPTY'}, "
                f"turn={turn.actor}.{turn.action}"
            )

        if not event_doc or not event_doc.slack_thread_ts:
            return
        if turn.actor == "user" and turn.source == "slack":
            return

        if turn.actor == "brain" and turn.action == "wait" and event_doc.slack_user_id:
            if turn.thoughts and f"<@{event_doc.slack_user_id}>" not in turn.thoughts:
                turn.thoughts = f"<@{event_doc.slack_user_id}> {turn.thoughts}"

        thinking = self._thinking_msg.pop(event_id, None)
        if thinking:
            await self._update_turn_in_thread(thinking, event_doc, turn)
        else:
            await self._send_turn_to_thread(event_doc, turn)

    # =========================================================================
    # Outbound helpers
    # =========================================================================

    async def _send_turn_to_thread(self, event_doc: Any, turn: Any) -> None:
        """Format a ConversationTurn and post it to the event's Slack thread."""
        raw_text = turn.result or turn.thoughts or ""
        cleaned, table_blocks = extract_tables(raw_text)

        original_result, original_thoughts = turn.result, turn.thoughts
        if turn.result:
            turn.result = cleaned
        else:
            turn.thoughts = cleaned

        blocks = format_turn(turn, event_id=event_doc.id)
        turn.result, turn.thoughts = original_result, original_thoughts

        fallback = f"{turn.actor}.{turn.action}: {raw_text}"[:200]
        color = get_turn_attachment_color(turn)
        await self._post_to_thread(
            event_doc.slack_channel_id, event_doc.slack_thread_ts,
            get_agent_notification_text(turn) if color else fallback,
            blocks, attachment_color=color,
            table_blocks=table_blocks[:1],
        )

    async def _update_turn_in_thread(
        self, thinking: tuple[str, str] | dict[str, str], event_doc: Any, turn: Any,
    ) -> None:
        """Replace the thinking indicator message with the formatted turn.

        If the turn contains tables, delete the thinking indicator and post a
        new message via _send_turn_to_thread (chat_update cannot render table blocks).
        """
        channel, msg_ts = thinking
        raw_text = turn.result or turn.thoughts or ""
        _, table_blocks = extract_tables(raw_text)

        if table_blocks:
            try:
                await asyncio.wait_for(
                    self._app.client.chat_delete(channel=channel, ts=msg_ts),
                    timeout=_SLACK_API_TIMEOUT,
                )
            except Exception:
                pass
            await self._send_turn_to_thread(event_doc, turn)
            return

        blocks = format_turn(turn, event_id=event_doc.id)
        fallback = f"{turn.actor}.{turn.action}: {turn.thoughts or turn.result or ''}"[:200]
        color = get_turn_attachment_color(turn)
        try:
            kwargs: dict[str, Any] = {"channel": channel, "ts": msg_ts, "text": get_agent_notification_text(turn) if color else fallback}
            if color and blocks:
                kwargs["attachments"] = [{"color": color, "blocks": blocks}]
            elif blocks:
                kwargs["blocks"] = blocks
            await asyncio.wait_for(
                self._app.client.chat_update(**kwargs),
                timeout=_SLACK_API_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"Slack thinking->turn update failed, falling back to new post: {e}")
            await self._send_turn_to_thread(event_doc, turn)

    async def _post_to_thread(
        self, channel: str, thread_ts: str, text: str,
        blocks: list | None = None, attachment_color: str | None = None,
        table_blocks: list | None = None,
    ) -> None:
        """Post a message to a Slack thread.

        If attachment_color is set, blocks are wrapped in a legacy attachment
        to render a colored side bar (per-agent visual identity).
        table_blocks are appended as a separate attachment (one table per message).
        """
        try:
            kwargs: dict[str, Any] = {
                "channel": channel, "thread_ts": thread_ts, "text": text,
            }
            attachments: list[dict] = []
            if attachment_color and blocks:
                attachments.append({"color": attachment_color, "blocks": blocks})
            elif blocks:
                kwargs["blocks"] = blocks
            if table_blocks:
                attachments.append({"blocks": table_blocks})
            if attachments:
                kwargs["attachments"] = attachments
            await self._app.client.chat_postMessage(**kwargs)
        except SlackApiError as e:
            if table_blocks and any(err in str(e) for err in ("invalid_blocks", "invalid_attachments", "uneven_table_rows_not_allowed")):
                logger.warning("Slack rejected table blocks (%s); falling back to monospaced code block", e)
                retry_attachments = [a for a in attachments if a.get("blocks") is not table_blocks]
                fallback_section_blocks = []
                for tb in table_blocks:
                    code_block = table_block_to_code_block(tb)
                    fallback_text = truncate_text(code_block, MAX_SECTION_TEXT)
                    fallback_section_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": fallback_text}})
                retry_kwargs: dict[str, Any] = {
                    "channel": channel, "thread_ts": thread_ts, "text": text,
                }
                if retry_attachments:
                    # In Slack, top-level blocks render above attachments.
                    # When attachment_color is used, append fallback sections to the attachment
                    # so the table appears below the message body.
                    if "blocks" in retry_attachments[0]:
                        retry_attachments[0]["blocks"] = list(retry_attachments[0]["blocks"]) + fallback_section_blocks
                    else:
                        retry_attachments.append({"blocks": fallback_section_blocks})
                    retry_kwargs["attachments"] = retry_attachments
                else:
                    fallback_blocks = list(kwargs.get("blocks", [])) + fallback_section_blocks
                    if fallback_blocks:
                        retry_kwargs["blocks"] = fallback_blocks
                try:
                    await self._app.client.chat_postMessage(**retry_kwargs)
                except Exception as retry_err:
                    logger.warning("Slack fallback post failed: %s", retry_err)
            else:
                logger.warning("Slack post failed: %s", e)
        except Exception as e:
            logger.warning(f"Slack post failed: {e}")

    async def post_nightwatcher_summary(self, summary: str) -> None:
        """Post a Nightwatcher shift summary to the infra channel."""
        if not self._infra_channel:
            logger.warning("post_nightwatcher_summary: SLACK_INFRA_CHANNEL is empty, skipping")
            return
        truncated = summary[:3900] if len(summary) > 4000 else summary
        try:
            result = await self._app.client.chat_postMessage(
                channel=self._infra_channel,
                text=truncated,
            )
            if result.get("ok"):
                logger.info("Nightwatcher shift summary posted to %s (%d chars)", self._infra_channel, len(truncated))
            else:
                error = result.get("error", "unknown")
                logger.warning("Nightwatcher Slack summary rejected: %s", error)
                raise RuntimeError(f"Slack API rejected: {error}")
        except RuntimeError:
            raise
        except Exception as e:
            error_detail = ""
            if hasattr(e, "response") and hasattr(e.response, "data"):
                error_detail = e.response.data.get("error", "")
            logger.warning("Nightwatcher Slack summary failed: %s (detail: %s)", e, error_detail)
            raise RuntimeError(f"Slack post failed: {error_detail or e}") from e

    async def open_infra_thread(self, event_doc: Any, summary: str) -> None:
        """Post an event to #darwin-infra and store thread_ts (Phase 2)."""
        if not self._infra_channel:
            logger.warning("open_infra_thread: SLACK_INFRA_CHANNEL is empty, skipping")
            return
        blocks = format_event_summary(event_doc)
        try:
            result = await self._app.client.chat_postMessage(
                channel=self._infra_channel,
                text=f"Event `{event_doc.id}`: {summary[:200]}",
                blocks=blocks,
            )
            thread_ts = result["ts"]
            await self._blackboard.update_event_slack_context(
                event_doc.id, self._infra_channel, thread_ts,
            )
            await self._blackboard.set_slack_mapping(
                self._infra_channel, thread_ts, event_doc.id,
            )
            logger.info(f"Infra thread created: {event_doc.id} -> {self._infra_channel}/{thread_ts}")
        except Exception as e:
            logger.error(f"Infra thread post FAILED for {event_doc.id} to {self._infra_channel}: {e}")

    async def open_dm_thread(self, slack_user_id: str, event_doc: Any, summary: str) -> None:
        """Open a DM with a user for an event (Phase 3)."""
        try:
            dm = await self._app.client.conversations_open(users=slack_user_id)
            channel_id = dm["channel"]["id"]
            blocks = format_event_summary(event_doc)
            result = await self._app.client.chat_postMessage(
                channel=channel_id,
                text=f"Event `{event_doc.id}`: {summary}",
                blocks=blocks,
            )
            thread_ts = result["ts"]
            await self._blackboard.update_event_slack_context(
                event_doc.id, channel_id, thread_ts, slack_user_id,
            )
            await self._blackboard.set_slack_mapping(channel_id, thread_ts, event_doc.id)
            self._dm_context[event_doc.id] = {
                "channel": channel_id, "thread_ts": thread_ts,
                "user_id": slack_user_id, "team_id": "",
                "_last_status_at": 0,
            }
        except Exception as e:
            logger.warning(f"DM thread open failed: {e}")

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start Socket Mode connection."""
        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        await self._handler.connect_async()
        logger.info("Slack Socket Mode connected")

    async def stop(self) -> None:
        """Graceful shutdown."""
        for event_id in list(self._progress_ts.keys()):
            await self._cleanup_progress_bubble(event_id, "shutdown")
        if self._handler:
            await self._handler.close_async()
            logger.info("Slack Socket Mode disconnected")

    @staticmethod
    async def _safe_react(client: Any, channel: str, ts: str, reaction: str) -> None:
        """Add reaction emoji, fail gracefully if scope missing."""
        try:
            await client.reactions_add(channel=channel, timestamp=ts, name=reaction)
        except Exception as e:
            logger.debug(f"Reaction :{reaction}: failed: {e}")
