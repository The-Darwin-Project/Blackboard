# tests/test_jenkins_tools.py
# @ai-rules:
# 1. [Pattern]: Tool handler tests for ask_release_ai and greenwave. No Redis, no Brain import.
# 2. [Constraint]: Handlers under test are in src/agents/handlers_integration.py. Mock ToolContext and httpx.
# 3. [Pattern]: ToolContext mocked via AsyncMock with next_turn_number/append_and_broadcast stubs.
# 4. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio needed.
# 5. [Gotcha]: Tests mock httpx at the module level — implementation uses client.stream() for SSE, not client.post().
"""T-6, T-7, T-8, T-19: Tool handler tests for ask_release_ai and greenwave."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx() -> AsyncMock:
    """Build a minimal ToolContext mock matching the Protocol in tool_router.py."""
    ctx = AsyncMock()
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.emit_pulse = AsyncMock()
    return ctx


def _captured_turn(ctx: AsyncMock):
    """Extract the ConversationTurn passed to append_and_broadcast."""
    assert ctx.append_and_broadcast.call_count >= 1, "append_and_broadcast was never called"
    return ctx.append_and_broadcast.call_args[0][1]


# ---------------------------------------------------------------------------
# T-6: ask_release_ai returns formatted answer
# ---------------------------------------------------------------------------

class TestAskReleaseAi:

    async def test_returns_formatted_answer(self):
        """T-6: Successful SSE stream is accumulated into a ConversationTurn."""
        from src.agents.handlers_integration import handle_ask_release_ai

        ctx = _make_ctx()
        event_id = "evt-test0001"
        args = {"question": "Why is CNV 4.23 tier1 failing?"}

        sse_lines = [
            'data: {"type":"text","text":"The failure is"}',
            '',
            'data: {"type":"text","text":" caused by flaky tests"}',
            '',
            'data: {"type":"done","usage":{}}',
            '',
        ]

        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {"data": {"sessionId": "s-123"}}
        mock_init_resp.raise_for_status = MagicMock()

        mock_stream = AsyncMock()

        async def _aiter_lines():
            for line in sse_lines:
                yield line

        mock_stream.aiter_lines = _aiter_lines

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com/vertex-api",
                "RELEASE_AI_EMAIL": "test@example.com",
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

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        assert turn.waitingFor == "ask_release_ai"

        turn_text = turn.thoughts or turn.evidence or ""
        assert "flaky tests" in turn_text

    async def test_error_produces_evidence_turn_no_exception(self):
        """ask_release_ai: HTTP error does not raise; produces an error evidence turn."""
        from src.agents.handlers_integration import handle_ask_release_ai

        ctx = _make_ctx()
        event_id = "evt-test0002"
        args = {"question": "What happened?"}

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "RELEASE_AI_URL": "https://release-ai.example.com/vertex-api",
                "RELEASE_AI_EMAIL": "test@example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_ask_release_ai(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "unavailable" in turn_text.lower() or "error" in turn_text.lower() or "failed" in turn_text.lower()

    async def test_missing_env_produces_evidence_turn(self):
        """ask_release_ai: Missing RELEASE_AI_URL does not raise; produces a config-missing turn."""
        from src.agents.handlers_integration import handle_ask_release_ai

        ctx = _make_ctx()
        event_id = "evt-test0003"
        args = {"question": "test"}

        with patch.dict("os.environ", {"RELEASE_AI_URL": "", "RELEASE_AI_EMAIL": ""}, clear=False):
            result = await handle_ask_release_ai(ctx, event_id, args, None)

        assert result is True
        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"


# ---------------------------------------------------------------------------
# T-7: greenwave returns satisfaction status (policies_satisfied: true)
# ---------------------------------------------------------------------------

class TestGreenwaveSatisfied:

    async def test_satisfied_gate(self):
        """T-7: GreenWave satisfied → evidence turn confirms gate passed."""
        from src.agents.handlers_integration import handle_greenwave

        ctx = _make_ctx()
        event_id = "evt-test0010"
        args = {
            "decision_context": "cnv_nightly_build_gate",
            "product_version": "4.23",
            "subject_identifier": "verify-cnv-4.23.z-build-tier1",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "policies_satisfied": True,
            "unsatisfied_requirements": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "GREENWAVE_URL": "https://greenwave.example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        assert turn.waitingFor == "greenwave"

        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "satisf" in turn_text.lower()


# ---------------------------------------------------------------------------
# T-8: greenwave handles unsatisfied gate
# ---------------------------------------------------------------------------

class TestGreenwaveUnsatisfied:

    async def test_unsatisfied_gate_lists_requirements(self):
        """T-8: GreenWave unsatisfied → evidence turn lists unsatisfied requirements."""
        from src.agents.handlers_integration import handle_greenwave

        ctx = _make_ctx()
        event_id = "evt-test0011"
        args = {
            "decision_context": "cnv_candidate_build_gate",
            "product_version": "4.23",
            "subject_identifier": "verify-cnv-4.23.z-build-tier2",
        }

        unsatisfied = [
            {"type": "test-result-missing", "testcase": "smoke.tier2.basic", "item": {"type": "koji_build", "identifier": "cnv-4.23.z-build"}},
            {"type": "test-result-failed", "testcase": "smoke.tier2.advanced", "item": {"type": "koji_build", "identifier": "cnv-4.23.z-build"}},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "policies_satisfied": False,
            "unsatisfied_requirements": unsatisfied,
        }
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "GREENWAVE_URL": "https://greenwave.example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        assert turn.waitingFor == "greenwave"

        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower_text = turn_text.lower()
        assert "not satisfied" in lower_text or "unsatisfied" in lower_text or "false" in lower_text
        assert "missing" in lower_text or "failed" in lower_text or "requirement" in lower_text
        assert "smoke.tier2.basic" in turn_text or "smoke.tier2.advanced" in turn_text


# ---------------------------------------------------------------------------
# T-19: GreenWave error response handled (4xx/5xx)
# ---------------------------------------------------------------------------

class TestGreenwaveError:

    async def test_http_500_no_exception(self):
        """T-19a: GreenWave 500 does not raise; evidence turn states retry."""
        from src.agents.handlers_integration import handle_greenwave

        ctx = _make_ctx()
        event_id = "evt-test0012"
        args = {
            "decision_context": "cnv_stable_build_gate",
            "product_version": "4.23",
            "subject_identifier": "verify-cnv-4.23.z-build-tier1",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "GREENWAVE_URL": "https://greenwave.example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"

        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower_text = turn_text.lower()
        assert "fail" in lower_text or "retry" in lower_text or "error" in lower_text or "unavailable" in lower_text

    async def test_http_404_no_exception(self):
        """T-19b: GreenWave 404 does not raise; evidence turn indicates failure."""
        from src.agents.handlers_integration import handle_greenwave

        ctx = _make_ctx()
        event_id = "evt-test0013"
        args = {
            "decision_context": "cnv_nightly_build_gate",
            "product_version": "4.99",
            "subject_identifier": "nonexistent-job",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "GREENWAVE_URL": "https://greenwave.example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"

        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower_text = turn_text.lower()
        assert "fail" in lower_text or "retry" in lower_text or "error" in lower_text or "404" in lower_text

    async def test_connection_timeout_no_exception(self):
        """T-19c: GreenWave timeout does not raise; evidence turn states retry."""
        from src.agents.handlers_integration import handle_greenwave
        import httpx

        ctx = _make_ctx()
        event_id = "evt-test0014"
        args = {
            "decision_context": "cnv_nightly_build_gate",
            "product_version": "4.23",
            "subject_identifier": "verify-cnv-4.23.z-build-tier1",
        }

        with (
            patch("src.agents.handlers_integration.httpx.AsyncClient") as MockClient,
            patch.dict("os.environ", {
                "GREENWAVE_URL": "https://greenwave.example.com",
            }),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectTimeout("Connection timed out")
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True

        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"

        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower_text = turn_text.lower()
        assert "fail" in lower_text or "retry" in lower_text or "timeout" in lower_text or "error" in lower_text

    async def test_missing_greenwave_url_no_exception(self):
        """GreenWave: Missing GREENWAVE_URL does not raise."""
        from src.agents.handlers_integration import handle_greenwave

        ctx = _make_ctx()
        event_id = "evt-test0015"
        args = {
            "decision_context": "cnv_nightly_build_gate",
            "product_version": "4.23",
            "subject_identifier": "verify-cnv-4.23.z-build-tier1",
        }

        with patch.dict("os.environ", {"GREENWAVE_URL": ""}, clear=False):
            result = await handle_greenwave(ctx, event_id, args, None)

        assert result is True
        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
