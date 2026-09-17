# tests/test_loop_breaker.py
# @ai-rules:
# 1. [Pattern]: Test suite for Darwin <-> Release AI distributed loop breaker & tool de-biasing.
# 2. [Constraint]: Tests written independently against plan specifications (Steps 1, 2, 2b, 8).
# 3. [Pattern]: ToolContext mocked via AsyncMock with get_blackboard/next_turn_number/append_and_broadcast stubs.
# 4. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio decorator needed.

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(event_doc: EventDocument | None = None, bb: AsyncMock | None = None) -> AsyncMock:
    """Build a ToolContext mock matching the Protocol in tool_router.py."""
    ctx = AsyncMock()
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.emit_pulse = AsyncMock()

    mock_bb = bb or AsyncMock()
    if bb is None:
        mock_bb.get_event = AsyncMock(return_value=event_doc)
    ctx.get_blackboard = MagicMock(return_value=mock_bb)
    return ctx


def _captured_turn(ctx: AsyncMock) -> ConversationTurn:
    """Extract the ConversationTurn passed to append_and_broadcast."""
    assert ctx.append_and_broadcast.call_count >= 1, "append_and_broadcast was never called"
    return ctx.append_and_broadcast.call_args[0][1]


def _make_mock_stream(sse_lines: list[str], status_code: int = 200, error_body: bytes = b""):
    """Build a mock httpx streaming response."""
    mock_stream = AsyncMock()
    mock_stream.status_code = status_code

    async def _aiter_lines():
        for line in sse_lines:
            yield line

    mock_stream.aiter_lines = _aiter_lines
    mock_stream.aread = AsyncMock(return_value=error_body)
    return mock_stream


# ---------------------------------------------------------------------------
# Suite 1: Caller Email Derivation & Outbound Headers
# ---------------------------------------------------------------------------

class TestCallerEmailDerivation:

    async def test_derives_caller_email_from_release_ai_email_domain(self):
        """Derives caller_email as {event_id}@{domain} and attaches tracing headers."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-f227b3f0"
        ctx = _make_ctx(event_doc=None)
        args = {"question": "Why did CNV Tier 1 fail?"}

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-test-1"}}

        sse_lines = [
            'data: {"type":"text","text":"RCA response"}',
            'data: {"type":"done","usage":{}}',
        ]
        mock_stream = _make_mock_stream(sse_lines)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "custom-service-account@enterprise.com",
                "RELEASE_AI_BFF_TOKEN": "secret-bff-token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, args, None)

        assert result is True

        # Verify headers in POST (init)
        assert mock_client.post.call_count == 1
        post_headers = mock_client.post.call_args.kwargs["headers"]
        expected_caller = f"{event_id}@enterprise.com"
        assert post_headers.get("X-Forwarded-Email") == expected_caller
        assert post_headers.get("X-Darwin-Caller") == "brain"
        assert post_headers.get("X-Calling-Agent") == "darwin-blackboard"
        assert post_headers.get("X-Darwin-Event-Id") == event_id
        assert post_headers.get("X-BFF-Token") == "secret-bff-token"

        # Verify headers in stream call
        stream_headers = mock_client.stream.call_args.kwargs["headers"]
        assert stream_headers.get("X-Forwarded-Email") == expected_caller
        assert stream_headers.get("X-Darwin-Caller") == "brain"
        assert stream_headers.get("X-Calling-Agent") == "darwin-blackboard"
        assert stream_headers.get("X-Darwin-Event-Id") == event_id

    async def test_fallback_to_darwin_project_io_when_email_missing_or_malformed(self):
        """Falls back gracefully to darwin-project.io domain when RELEASE_AI_EMAIL is unset or invalid."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-c78e678d"
        ctx = _make_ctx(event_doc=None)
        args = {"question": "Investigate flake"}

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-test-2"}}

        mock_stream = _make_mock_stream(['data: {"type":"done","usage":{}}'])

        # Test case: RELEASE_AI_EMAIL has no '@' domain
        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "invalid-no-domain",
                "RELEASE_AI_BFF_TOKEN": "token-abc",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, args, None)

        assert result is True
        post_headers = mock_client.post.call_args.kwargs["headers"]
        # Expected fallback caller
        assert post_headers.get("X-Forwarded-Email") == f"{event_id}@darwin-project.io"
        assert post_headers.get("X-Darwin-Caller") == "brain"
        assert post_headers.get("X-Darwin-Event-Id") == event_id


# ---------------------------------------------------------------------------
# Suite 2: Ancestry Loop Guard
# ---------------------------------------------------------------------------

class TestAncestryLoopGuard:

    def _make_event_doc(self, created_by_email: str | None, source: str = "chat") -> EventDocument:
        return EventDocument(
            id="evt-subtask-001",
            source=source,
            service="general",
            event=EventInput(
                reason="Investigate gating failure",
                evidence=EventEvidence(
                    display_text="Investigate gating failure",
                    source_type=source,
                    domain="disorder",
                    severity="info",
                ),
            ),
            created_by_email=created_by_email,
        )

    async def test_ancestry_loop_guard_blocks_evt_prefix_created_by(self):
        """When event has created_by_email starting with evt-, skips Release AI and broadcasts explanation."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-001"
        event_doc = self._make_event_doc(created_by_email="evt-abc12345@darwin-project.io")
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "test@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why failed?"}, None)

        # Must return True per HandlerFn contract
        assert result is True

        # HTTP client must NOT have been called (loop broken)
        MockClient.assert_not_called()

        # Turn must be broadcast explaining loop prevention
        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        assert turn.waitingFor == "ask_release_ai"
        assert "Cannot invoke ask_release_ai" in (turn.thoughts or "")
        assert "re-entrant call prevented" in (turn.thoughts or "")
        assert "evt-abc12345@darwin-project.io" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_blocks_custom_domain_evt_prefix(self):
        """Dynamic caller identities on custom domains (e.g. evt-xxx@redhat.com) trigger loop guard."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-002"
        event_doc = self._make_event_doc(created_by_email="evt-f227b3f0@redhat.com")
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "agent@redhat.com",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Recursive question"}, None)

        assert result is True
        MockClient.assert_not_called()

        turn = _captured_turn(ctx)
        assert turn.waitingFor == "ask_release_ai"
        assert "re-entrant call prevented" in (turn.thoughts or "")

    async def test_chat_source_darwin_domain_human_like_email_is_not_blocked(self):
        """Regression test for the false-positive HIGH finding on PR #251: a
        chat-sourced event whose created_by_email merely contains "darwin" or
        sits on the darwin-project.io domain -- but does not exactly match the
        configured service account identity, nor a known Darwin-owned prefix --
        must NOT be treated as re-entrant. The previous bare substring/suffix
        check silently and permanently blocked legitimate human chat users
        whose real email happened to contain "darwin"."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-003"
        event_doc = self._make_event_doc(
            created_by_email="bot@darwin-project.io",
            source="chat",
        )
        ctx = _make_ctx(event_doc=event_doc)

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-3"}}
        mock_stream = _make_mock_stream(['data: {"type":"done","usage":{}}'])

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                # Configured service account differs from created_by_email above --
                # only an exact match (or an evt-/darwin-evt-/darwin-agent@ prefix)
                # should ever be treated as re-entrant.
                "RELEASE_AI_EMAIL": "test@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        # Not blocked: Release AI must be called since this caller is not the
        # exact configured service-account identity.
        assert mock_client.post.call_count == 1
        turn = _captured_turn(ctx)
        assert "Cannot invoke ask_release_ai" not in (turn.thoughts or "")

    async def test_ancestry_loop_guard_blocks_exact_match_to_configured_service_account(self):
        """A chat-sourced event whose created_by_email is an EXACT match to the
        configured RELEASE_AI_EMAIL service account is the genuine re-entrant
        case (Darwin calling itself) and must still be blocked."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-003b"
        event_doc = self._make_event_doc(
            created_by_email="test@darwin-project.io",
            source="chat",
        )
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "test@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        MockClient.assert_not_called()

        turn = _captured_turn(ctx)
        assert "Cannot invoke ask_release_ai" in (turn.thoughts or "")
        assert "re-entrant call prevented" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_blocks_darwin_agent_prefix(self):
        """created_by_email starting with the darwin-agent@ fallback service
        account prefix is blocked regardless of the configured RELEASE_AI_EMAIL."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-003c"
        event_doc = self._make_event_doc(
            created_by_email="darwin-agent@darwin-project.io",
            source="chat",
        )
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "someone-else@enterprise.com",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        MockClient.assert_not_called()

        turn = _captured_turn(ctx)
        assert "re-entrant call prevented" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_blocks_darwin_evt_prefix(self):
        """Events created with darwin-evt- prefix trigger loop guard."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-004"
        event_doc = self._make_event_doc(created_by_email="darwin-evt-custom@enterprise.com")
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "test@enterprise.com",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        MockClient.assert_not_called()
        turn = _captured_turn(ctx)
        assert "re-entrant call prevented" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_blocks_uppercase_evt_prefix(self):
        """Case-insensitive ancestry check catches uppercase EVT- identities."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-subtask-005"
        event_doc = self._make_event_doc(created_by_email="EVT-F227B3F0@REDHAT.COM")
        ctx = _make_ctx(event_doc=event_doc)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "test@redhat.com",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        MockClient.assert_not_called()
        turn = _captured_turn(ctx)
        assert "re-entrant call prevented" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_fails_closed_on_db_exception(self):
        """When blackboard.get_event raises a connection error, fail closed for Darwin events."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-failed-lookup-001"
        mock_bb = AsyncMock()
        mock_bb.get_event = AsyncMock(side_effect=ConnectionError("Redis connection lost"))
        ctx = _make_ctx(bb=mock_bb)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "test@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            result = await handle_ask_release_ai(ctx, event_id, {"question": "Why?"}, None)

        assert result is True
        MockClient.assert_not_called()
        turn = _captured_turn(ctx)
        assert "re-entrant call prevented" in (turn.thoughts or "")
        assert "database unavailable during ancestry check" in (turn.thoughts or "")

    async def test_ancestry_loop_guard_allows_regular_human_caller(self):
        """Events created by legitimate human users do NOT trigger loop guard."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-human-001"
        event_doc = self._make_event_doc(created_by_email="john.doe@redhat.com", source="chat")
        ctx = _make_ctx(event_doc=event_doc)

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-1"}}
        mock_stream = _make_mock_stream(['data: {"type":"done","usage":{}}'])

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "agent@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, {"question": "Legitimate question"}, None)

        assert result is True
        # Release AI was called because caller is human
        assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# Suite 3: HTTP Stream Status Code >= 400
# ---------------------------------------------------------------------------

class TestStreamStatusCodeErrorHandling:

    async def test_stream_http_500_posts_failure_turn(self):
        """When Release AI stream returns HTTP 500, reads error snippet and posts failure turn."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-err-500"
        ctx = _make_ctx(event_doc=None)

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-err"}}

        # Stream responds with 500 status code
        error_payload = b"Internal Server Error: Vertex quota exceeded for model"
        mock_stream = _make_mock_stream([], status_code=500, error_body=error_payload)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "agent@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, {"question": "Quota test"}, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        assert turn.waitingFor == "ask_release_ai"

        turn_text = turn.thoughts or ""
        assert "HTTP 500" in turn_text
        assert "Vertex quota exceeded" in turn_text
        assert "Proceed without RCA context" in turn_text

    async def test_stream_http_400_truncates_long_error_snippet(self):
        """When stream returns HTTP 400 with huge error body, snippet is capped."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-err-400"
        ctx = _make_ctx(event_doc=None)

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-err-400"}}

        # Long error response > 1000 bytes
        long_body = b"Bad Request: " + (b"X" * 1500)
        mock_stream = _make_mock_stream([], status_code=400, error_body=long_body)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "agent@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, {"question": "Bad request test"}, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert "HTTP 400" in (turn.thoughts or "")
        # Verification that error body is truncated per plan snippet limit ([:500])
        assert len(turn.thoughts) < 800

    async def test_stream_http_500_redacts_pii_in_error_body(self):
        """Sensitive tokens or authorization secrets in error body are redacted."""
        from src.agents.handlers_integration import handle_ask_release_ai

        event_id = "evt-err-pii"
        ctx = _make_ctx(event_doc=None)

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-pii"}}

        # Error body containing bearer token
        raw_error = b"Unauthorized: invalid Bearer sha256~AbCdEf1234567890 secret passed in request"
        mock_stream = _make_mock_stream([], status_code=500, error_body=raw_error)

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com",
                "RELEASE_AI_EMAIL": "agent@darwin-project.io",
                "RELEASE_AI_BFF_TOKEN": "token",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_stream),
                __aexit__=AsyncMock(return_value=False),
            ))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, {"question": "Token leak test"}, None)

        assert result is True
        turn = _captured_turn(ctx)
        # Token must be redacted
        assert "[redacted-token]" in (turn.thoughts or "")


# ---------------------------------------------------------------------------
# Suite 4: UI Header User Email Mapping (dashboard_ws.py _handle_chat)
# ---------------------------------------------------------------------------

class TestUIHeaderUserEmail:

    async def test_handle_chat_maps_user_email_to_triggered_by(self):
        """When user.email is provided, evidence.triggered_by is set to user.email."""
        from src.adapters.dashboard_ws import DashboardWSAdapter

        mock_blackboard = AsyncMock()
        mock_blackboard.create_event = AsyncMock(return_value="evt-chat-001")
        mock_blackboard.append_turn = AsyncMock()
        mock_brain = MagicMock()

        adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=False)

        ws = AsyncMock()
        user = MagicMock()
        user.email = "thason@redhat.com"
        user.source = "release-console"
        user.label = "thason"

        chat_data = {
            "message": "Investigate cluster alert",
            "service": "general",
        }

        await adapter._handle_chat(ws, chat_data, user)

        mock_blackboard.create_event.assert_called_once()
        call_kwargs = mock_blackboard.create_event.call_args.kwargs
        evidence: EventEvidence = call_kwargs["evidence"]

        # Critical assertion: triggered_by displays human user email in Darwin UI header
        assert evidence.triggered_by == "thason@redhat.com"
        assert call_kwargs["created_by_email"] == "thason@redhat.com"

    async def test_handle_chat_falls_back_to_user_source_when_email_missing(self):
        """When user.email is None or empty, evidence.triggered_by falls back to user.source."""
        from src.adapters.dashboard_ws import DashboardWSAdapter

        mock_blackboard = AsyncMock()
        mock_blackboard.create_event = AsyncMock(return_value="evt-chat-002")
        mock_blackboard.append_turn = AsyncMock()
        mock_brain = MagicMock()

        adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=False)

        ws = AsyncMock()
        user = MagicMock()
        user.email = None
        user.source = "dashboard"
        user.label = "anonymous"

        chat_data = {
            "message": "Anonymous question",
            "service": "general",
        }

        await adapter._handle_chat(ws, chat_data, user)

        mock_blackboard.create_event.assert_called_once()
        evidence: EventEvidence = mock_blackboard.create_event.call_args.kwargs["evidence"]

        assert evidence.triggered_by == "dashboard"
