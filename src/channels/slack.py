# BlackBoard/src/channels/slack.py
# @ai-rules:
# 1. [Constraint]: Single Socket Mode connection. If Brain scales, only one replica enables Slack.
# 2. [Pattern]: Events from Slack via /darwin (channels) or Assistant split-pane (DMs). Non-threaded bare DMs still ignored.
# 6. [Pattern]: Phase 2 -- Aligner events auto-open #darwin-infra threads on brain.route (agent dispatched). Trivial auto-closed events stay silent.
# 3. [Pattern]: broadcast_handler routes by message["type"]. Assistant threads: brain_thinking -> streaming, turn -> stream.stop(). Legacy: brain_thinking -> emoji, turn -> Block Kit.
# 4. [Gotcha]: Bolt's AsyncIgnoringSelfEvents middleware prevents infinite loops from bot's own thread replies.
# 5. [Pattern]: safe_react fails gracefully if reactions:write scope is missing.
# 7. [Pattern]: _assistant_context stores {channel, thread_ts, user_id, team_id} per event for streaming. Populated in user_message, consumed by broadcast_handler.
# 8. [Pattern]: _stream_sessions manages AsyncChatStream lifecycle. Created on first non-thought brain_thinking chunk, stopped on turn. Fallback to legacy on any error.
"""SlackChannel adapter -- bidirectional Slack integration via Socket Mode."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from slack_bolt.async_app import AsyncApp, AsyncAssistant
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from .formatter import (
    format_turn, format_event_summary, get_turn_attachment_color,
    get_agent_notification_text, create_feedback_block, format_task_card,
    extract_tables,
)
from ..models import EventEvidence

if TYPE_CHECKING:
    from ..agents.brain import Brain
    from ..state.blackboard import BlackboardState

logger = logging.getLogger("darwin.slack")


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
    ) -> None:
        self._app_token = app_token
        self._infra_channel = infra_channel
        self._mr_fallback_channel = mr_fallback_channel
        self._blackboard = blackboard
        self._brain = brain
        self._handler: AsyncSocketModeHandler | None = None
        self._user_name_cache: dict[str, tuple[str, float]] = {}
        self._USER_CACHE_TTL = 3600
        self._thinking_msg: dict[str, tuple[str, str]] = {}  # event_id -> (channel, msg_ts)
        self._assistant_context: dict[str, dict] = {}  # event_id -> {channel, thread_ts, user_id, team_id}
        self._stream_sessions: dict[str, Any] = {}  # event_id -> AsyncChatStream

        self._app = AsyncApp(token=bot_token)
        self._assistant = AsyncAssistant()
        self._register_assistant_handlers()
        self._app.use(self._assistant)
        self._register_handlers()

    async def _resolve_display_name(self, client: Any, user_id: str) -> str:
        """Resolve Slack user_id to display name with TTL cache."""
        cached = self._user_name_cache.get(user_id)
        if cached and (time.time() - cached[1]) < self._USER_CACHE_TTL:
            return cached[0]
        try:
            info = await client.users_info(user=user_id)
            profile = info["user"]["profile"]
            name = profile.get("display_name") or info["user"].get("real_name", user_id)
            self._user_name_cache[user_id] = (name, time.time())
            return name
        except Exception as e:
            logger.warning(f"Failed to resolve display name for {user_id}: {e}")
            return user_id

    def _register_assistant_handlers(self) -> None:
        """Register Assistant middleware handlers for split-pane AI experience."""

        @self._assistant.thread_started
        async def on_thread_started(say: Any, set_suggested_prompts: Any) -> None:
            try:
                event_ids = await self._blackboard.get_active_events()
                prompts = [{"title": "Check system health", "message": "What is the current status of all monitored services?"}]
                if event_ids:
                    prompts.insert(0, {
                        "title": f"Resume active event ({event_ids[0]})",
                        "message": f"What is the status of event {event_ids[0]}?",
                    })
                set_suggested_prompts(prompts=prompts)
                say("How can I help you?")
            except Exception as e:
                logger.warning(f"Assistant thread_started failed: {e}")
                say("How can I help you?")

        @self._assistant.user_message
        async def on_user_message(
            payload: dict, client: Any, set_status: Any, set_title: Any, say: Any,
        ) -> None:
            try:
                channel_id = payload["channel"]
                team_id = payload.get("team", "")
                thread_ts = payload["thread_ts"]
                user_id = payload["user"]
                text = payload.get("text", "")

                set_status("Darwin is thinking...")

                event_id = await self._blackboard.get_event_by_slack_thread(channel_id, thread_ts)

                if not event_id:
                    event_id = await self._blackboard.create_event(
                        source="slack",
                        service="general",
                        reason=text,
                        evidence=EventEvidence(
                            display_text=text,
                            source_type="slack",
                            domain="complicated",
                            severity="info",
                        ),
                    )
                    await self._blackboard.update_event_slack_context(
                        event_id, channel_id, thread_ts, user_id,
                    )
                    await self._blackboard.set_slack_mapping(channel_id, thread_ts, event_id)
                    set_title(f"evt-{event_id}: {text[:50]}")
                    logger.info(f"Assistant: new event {event_id} by {user_id}")
                else:
                    from ..models import ConversationTurn
                    event_doc = await self._blackboard.get_event(event_id)
                    if not event_doc:
                        say(":warning: Event not found.")
                        return
                    display_name = await self._resolve_display_name(client, user_id)
                    turn = ConversationTurn(
                        turn=len(event_doc.conversation) + 1,
                        actor="user",
                        action="message",
                        thoughts=text,
                        source="slack",
                        user_name=display_name,
                    )
                    await self._blackboard.append_turn(event_id, turn)
                    logger.info(f"Assistant: reply on {event_id} from {display_name}")

                self._assistant_context[event_id] = {
                    "channel": channel_id, "thread_ts": thread_ts,
                    "user_id": user_id, "team_id": team_id,
                }
                self._brain.clear_waiting(event_id)
            except Exception as e:
                logger.exception(f"Assistant user_message failed: {e}")
                say(f":warning: Something went wrong ({e})")

        @self._assistant.thread_context_changed
        async def on_context_changed() -> None:
            pass

    def _register_handlers(self) -> None:
        """Register Slack event listeners on the Bolt app."""

        @self._app.command("/darwin")
        async def handle_darwin_command(ack: Any, body: dict, client: Any, respond: Any) -> None:
            await ack()
            text = body.get("text", "").strip()
            user_id = body["user_id"]
            channel_id = body["channel_id"]

            if not text:
                await respond(text="Usage: `/darwin <describe the issue or task>`")
                return

            # Create event in Blackboard
            event_id = await self._blackboard.create_event(
                source="slack",
                service="general",
                reason=text,
                evidence=EventEvidence(
                    display_text=text,
                    source_type="slack",
                    domain="complicated",
                    severity="info",
                ),
            )

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

        @self._app.event("message")
        async def on_dm_message(event: dict, client: Any) -> None:
            # Skip bot's own messages and subtypes (edits, deletes, etc.)
            if event.get("bot_id") or event.get("subtype"):
                return

            # DMs + infra channel threads (Phase 2). Other channels are ignored.
            channel_type = event.get("channel_type", "")
            channel = event.get("channel", "")
            if channel_type != "im" and channel != self._infra_channel:
                return

            thread_ts = event.get("thread_ts")
            if thread_ts is None:
                # Not a thread reply -- ignore (events only via /darwin)
                return

            user = event["user"]
            text = event.get("text", "")

            # Lookup event by thread
            event_id = await self._blackboard.get_event_by_slack_thread(channel, thread_ts)
            if not event_id:
                return

            await self._safe_react(client, channel, event["ts"], "eyes")

            # Append user message to event conversation
            from ..models import ConversationTurn
            event_doc = await self._blackboard.get_event(event_id)
            if not event_doc:
                return
            display_name = await self._resolve_display_name(client, user)
            turn = ConversationTurn(
                turn=len(event_doc.conversation) + 1,
                actor="user",
                action="message",
                thoughts=text,
                source="slack",
                user_name=display_name,
            )
            await self._blackboard.append_turn(event_id, turn)
            self._brain.clear_waiting(event_id)
            logger.info(f"Slack DM reply on {event_id} from {display_name} ({user})")

        @self._app.action("darwin_approve")
        async def handle_approve(ack: Any, body: dict, client: Any) -> None:
            await ack()
            event_id = body["actions"][0]["value"]
            user = body["user"]["id"]
            channel = body["channel"]["id"]
            thread_ts = body["message"].get("thread_ts", body["message"]["ts"])

            from ..models import ConversationTurn
            event_doc = await self._blackboard.get_event(event_id)
            if not event_doc:
                return
            turn = ConversationTurn(
                turn=len(event_doc.conversation) + 1,
                actor="user",
                action="approve",
                thoughts="User approved the plan.",
                source="slack",
            )
            await self._blackboard.append_turn(event_id, turn)
            self._brain.clear_waiting(event_id)
            await self._safe_react(client, channel, thread_ts, "white_check_mark")
            logger.info(f"Slack approve on {event_id} by {user}")

        @self._app.action("darwin_reject")
        async def handle_reject(ack: Any, body: dict, client: Any) -> None:
            await ack()
            event_id = body["actions"][0]["value"]
            user = body["user"]["id"]
            channel = body["channel"]["id"]
            thread_ts = body["message"].get("thread_ts", body["message"]["ts"])

            from ..models import ConversationTurn
            event_doc = await self._blackboard.get_event(event_id)
            if not event_doc:
                return
            turn = ConversationTurn(
                turn=len(event_doc.conversation) + 1,
                actor="user",
                action="reject",
                thoughts="User rejected the plan.",
                source="slack",
            )
            await self._blackboard.append_turn(event_id, turn)
            self._brain.clear_waiting(event_id)
            await self._safe_react(client, channel, thread_ts, "x")
            logger.info(f"Slack reject on {event_id} by {user}")

        @self._app.action("darwin_feedback")
        async def handle_feedback(ack: Any, body: dict, client: Any) -> None:
            await ack()
            feedback = body["actions"][0]["value"]
            user_id = body["user"]["id"]
            msg_ts = body["message"]["ts"]
            logger.info(f"Feedback: {feedback} from {user_id} on {msg_ts}")
            text = (
                "Thanks for the feedback!"
                if feedback == "positive"
                else "Sorry about that. Your feedback helps Darwin improve."
            )
            await client.chat_postEphemeral(
                channel=body["channel"]["id"], user=user_id,
                thread_ts=msg_ts, text=text,
            )

        @self._app.event("app_home_opened")
        async def handle_app_home_opened(event: dict, client: Any) -> None:
            if event.get("tab") != "home":
                return
            user_id = event["user"]
            try:
                await self._publish_home_tab(client, user_id)
            except Exception as e:
                logger.warning(f"Home tab publish failed for {user_id}: {e}")

        @self._app.action("darwin_home_create_event")
        async def handle_home_create_event(ack: Any, body: dict, client: Any) -> None:
            await ack()
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
            text = view["state"]["values"]["event_description"]["description_input"]["value"]
            user_id = body["user"]["id"]
            if not text or not text.strip():
                return

            event_id = await self._blackboard.create_event(
                source="slack",
                service="general",
                reason=text.strip(),
                evidence=EventEvidence(
                    display_text=text.strip(),
                    source_type="slack",
                    domain="complicated",
                    severity="info",
                ),
            )
            event_doc = await self._blackboard.get_event(event_id)
            blocks = format_event_summary(event_doc) if event_doc else []
            result = await client.chat_postMessage(
                channel=user_id,
                text=f"Event `{event_id}` created: {text.strip()[:100]}",
                blocks=blocks,
            )
            thread_ts = result["ts"]

            await self._blackboard.update_event_slack_context(
                event_id, user_id, thread_ts, user_id,
            )
            await self._blackboard.set_slack_mapping(user_id, thread_ts, event_id)
            logger.info(f"Home tab create event: {event_id} by {user_id} (thread={thread_ts})")

        @self._app.action("darwin_home_open_dashboard")
        async def handle_home_open_dashboard(ack: Any, body: dict) -> None:
            await ack()

    async def _publish_home_tab(self, client: Any, user_id: str) -> None:
        """Gather data and publish the Home tab view for a user."""
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
    # Two-path router: Assistant threads use streaming, legacy uses emoji hack.
    # =========================================================================

    async def broadcast_handler(self, message: dict) -> None:
        """Route Brain broadcasts to Assistant streaming or legacy Block Kit path."""
        msg_type = message.get("type")
        event_id = message.get("event_id", "")
        is_assistant = event_id in self._assistant_context

        if msg_type == "brain_thinking":
            if is_assistant:
                await self._handle_assistant_thinking(event_id, message)
            else:
                await self._handle_legacy_thinking(event_id, message)
            return

        if msg_type == "brain_thinking_done":
            return

        if msg_type == "turn":
            if is_assistant and event_id in self._stream_sessions:
                await self._handle_assistant_turn(event_id, message)
            else:
                await self._handle_legacy_turn(event_id, message)

        elif msg_type == "event_closed":
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
            self._assistant_context.pop(event_id, None)
            stream = self._stream_sessions.pop(event_id, None)
            if stream:
                try:
                    await stream.stop()
                except Exception:
                    pass

    # =========================================================================
    # Assistant streaming path (split-pane DM threads)
    # =========================================================================

    async def _handle_assistant_thinking(self, event_id: str, message: dict) -> None:
        """Process brain_thinking broadcasts for Assistant threads via chat_stream."""
        text = message.get("text", "")
        is_thought = message.get("is_thought", False)

        if not text:
            ctx = self._assistant_context[event_id]
            try:
                await self._app.client.assistant_threads_setStatus(
                    channel_id=ctx["channel"], thread_ts=ctx["thread_ts"],
                    status="Darwin is analyzing...",
                )
            except Exception as e:
                logger.warning(f"setStatus failed for {event_id}: {e}")
            return

        if is_thought:
            return

        if event_id not in self._stream_sessions:
            ctx = self._assistant_context[event_id]
            try:
                stream = self._app.client.chat_stream(
                    channel=ctx["channel"],
                    thread_ts=ctx["thread_ts"],
                    recipient_user_id=ctx["user_id"],
                    recipient_team_id=ctx["team_id"],
                    buffer_size=256,
                )
                self._stream_sessions[event_id] = stream
                logger.debug(f"Stream started for {event_id}")
            except Exception as e:
                logger.warning(f"chat_stream start failed for {event_id}, will fallback: {e}")
                return

        try:
            await self._stream_sessions[event_id].append(markdown_text=text)
        except Exception as e:
            logger.warning(f"Stream append failed for {event_id}: {e}")
            self._stream_sessions.pop(event_id, None)

    async def _handle_assistant_turn(self, event_id: str, message: dict) -> None:
        """Finalize the stream with feedback blocks (and table blocks if present)."""
        from ..models import ConversationTurn
        turn = ConversationTurn(**message["turn"])

        if turn.actor == "user" and turn.source == "slack":
            return

        stream = self._stream_sessions.pop(event_id, None)
        if stream:
            try:
                if turn.actor == "brain" and turn.action == "route":
                    card = format_task_card(turn, status="in_progress")
                    await stream.append(markdown_text=f"\n\n{card}")

                raw_text = turn.result or turn.thoughts or ""
                _, table_blocks = extract_tables(raw_text)
                stop_blocks = table_blocks[:1] + create_feedback_block()
                await stream.stop(blocks=stop_blocks)
                logger.debug(f"Stream stopped for {event_id}")
                return
            except Exception as e:
                logger.warning(f"Stream stop failed for {event_id}, falling back: {e}")

        await self._handle_legacy_turn(event_id, message)

    # =========================================================================
    # Legacy path (channel threads, infra threads, fallback)
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

    async def _handle_legacy_turn(self, event_id: str, message: dict) -> None:
        """Post turn via Block Kit for non-Assistant threads (or streaming fallback)."""
        event_doc = await self._blackboard.get_event(event_id)
        if not event_doc:
            return
        from ..models import ConversationTurn
        turn = ConversationTurn(**message["turn"])

        if (
            not event_doc.slack_thread_ts
            and event_doc.source in ("aligner", "headhunter")
            and self._infra_channel
            and turn.actor == "brain"
            and turn.action == "route"
        ):
            await self.open_infra_thread(event_doc, event_doc.event.reason)
            event_doc = await self._blackboard.get_event(event_id)

        if not event_doc or not event_doc.slack_thread_ts:
            return
        if turn.actor == "user" and turn.source == "slack":
            return

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
        self, thinking: tuple[str, str], event_doc: Any, turn: Any,
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
                await self._app.client.chat_delete(channel=channel, ts=msg_ts)
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
            await self._app.client.chat_update(**kwargs)
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
        except Exception as e:
            logger.warning(f"Slack post failed: {e}")

    async def open_infra_thread(self, event_doc: Any, summary: str) -> None:
        """Post an event to #darwin-infra and store thread_ts (Phase 2)."""
        if not self._infra_channel:
            return
        blocks = format_event_summary(event_doc)
        try:
            result = await self._app.client.chat_postMessage(
                channel=self._infra_channel,
                text=f"Event `{event_doc.id}`: {summary}",
                blocks=blocks,
            )
            thread_ts = result["ts"]
            await self._blackboard.update_event_slack_context(
                event_doc.id, self._infra_channel, thread_ts,
            )
            await self._blackboard.set_slack_mapping(
                self._infra_channel, thread_ts, event_doc.id,
            )
        except Exception as e:
            logger.warning(f"Infra thread post failed: {e}")

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
