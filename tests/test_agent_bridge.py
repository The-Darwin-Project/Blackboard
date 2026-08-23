# BlackBoard/tests/test_agent_bridge.py
# @ai-rules:
# 1. [Constraint]: Probe test -- validates TaskBridge + AgentRegistry + /agent/ws end-to-end.
# 2. [Pattern]: Minimal app fixture (no Redis) with test dispatch endpoint for concurrent trigger.
# 3. [Constraint]: ~120 lines target. Integration plumbing, not unit edge cases.
"""Mock agent integration tests: TaskBridge, AgentRegistry, /agent/ws endpoint."""
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.agents.agent_registry import AgentRegistry
from src.agents.agent_ws_handler import agent_websocket_handler
from src.agents.dispatch import RETRYABLE_SENTINEL, dispatch_to_agent
from src.agents.task_bridge import TaskBridge


def _make_minimal_app() -> FastAPI:
    """Minimal FastAPI app with agent routes only (no Redis)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry = AgentRegistry()
        bridge = TaskBridge()
        registry.set_task_orphaned_callback(bridge.put_error)
        app.state.agent_registry = registry
        app.state.task_bridge = bridge
        yield

    app = FastAPI(lifespan=lifespan)

    @app.websocket("/agent/ws")
    async def agent_ws(ws: WebSocket) -> None:
        r = getattr(app.state, "agent_registry", None)
        b = getattr(app.state, "task_bridge", None)
        if not r or not b:
            await ws.close(code=1013, reason="Registry not initialized")
            return
        await agent_websocket_handler(ws, r, b)

    @app.get("/api/agents", tags=["agents"])
    async def list_agents() -> list[dict]:
        r = getattr(app.state, "agent_registry", None)
        return await r.list_agents() if r else []

    @app.post("/api/test/dispatch", tags=["test"])
    async def test_dispatch(role: str, event_id: str, task: str) -> dict:
        r, b = app.state.agent_registry, app.state.task_bridge
        out, sid = await dispatch_to_agent(r, b, role, event_id, task)
        return {"result": out, "session_id": sid}

    return app


@pytest.fixture
def client() -> TestClient:
    app = _make_minimal_app()
    with TestClient(app) as c:
        yield c


@pytest.mark.xfail(reason="Starlette TestClient cannot interleave WS + HTTP from separate threads reliably")
def test_bridge_end_to_end(client: TestClient) -> None:
    """Full flow: register -> dispatch -> progress -> result -> idle."""
    ws_done = threading.Event()

    def ws_thread() -> None:
        with client.websocket_connect("/agent/ws") as ws:
            ws.send_json({
                "type": "register",
                "agent_id": "test-agent-1",
                "role": "developer",
                "capabilities": [],
                "cli": "gemini",
                "model": "test",
            })
            task_id: str | None = None
            while not ws_done.is_set():
                try:
                    msg = ws.receive_json()
                    if msg.get("type") == "task":
                        task_id = msg.get("task_id")
                        ws.send_json({"type": "progress", "task_id": task_id, "message": "working..."})
                        ws.send_json({"type": "result", "task_id": task_id, "output": "done", "source": "callback"})
                        break
                except Exception:
                    break
        ws_done.set()

    t = threading.Thread(target=ws_thread)
    t.start()

    for _ in range(10):
        time.sleep(0.1)
        resp = client.get("/api/agents")
        agents = resp.json()
        if len(agents) == 1:
            break
    assert len(agents) == 1
    assert agents[0]["role"] == "developer"
    assert agents[0]["busy"] is False

    resp = client.post("/api/test/dispatch?role=developer&event_id=evt-test&task=test+task")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "done"
    assert data["session_id"] is None

    # Check agent idle before ws closes (dispatch finally-block marks idle)
    resp = client.get("/api/agents")
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["busy"] is False
    t.join(timeout=5)


def test_evict_on_reconnect(client: TestClient) -> None:
    """Second sidecar with same role prefix evicts the first."""
    first_closed = threading.Event()

    def first_ws() -> None:
        with client.websocket_connect("/agent/ws") as ws:
            ws.send_json({
                "type": "register",
                "agent_id": "dev-pod-aaa",
                "role": "developer",
                "capabilities": [],
                "cli": "gemini",
                "model": "test",
            })
            try:
                while True:
                    ws.receive_json()
            except Exception:
                first_closed.set()

    t1 = threading.Thread(target=first_ws)
    t1.start()
    time.sleep(0.1)

    with client.websocket_connect("/agent/ws") as ws2:
        ws2.send_json({
            "type": "register",
            "agent_id": "dev-pod-bbb",
            "role": "developer",
            "capabilities": [],
            "cli": "gemini",
            "model": "test",
        })
        time.sleep(0.15)
        first_closed.wait(timeout=2)
        resp = client.get("/api/agents")
        agents = resp.json()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "dev-pod-bbb"
    t1.join(timeout=2)


def test_disconnect_unblocks_dispatch(client: TestClient) -> None:
    """When sidecar disconnects mid-dispatch, dispatch returns error."""
    def ws_thread() -> None:
        with client.websocket_connect("/agent/ws") as ws:
            ws.send_json({
                "type": "register",
                "agent_id": "test-agent-1",
                "role": "developer",
                "capabilities": [],
                "cli": "gemini",
                "model": "test",
            })
            msg = ws.receive_json()
            if msg.get("type") == "task":
                pass  # Don't send result -- close to simulate crash

    t = threading.Thread(target=ws_thread)
    t.start()
    time.sleep(0.15)

    dispatch_done = threading.Event()
    result_holder: list[dict] = []

    def dispatch_thread() -> None:
        resp = client.post("/api/test/dispatch?role=developer&event_id=evt-x&task=boom")
        result_holder.append(resp.json())
        dispatch_done.set()

    t2 = threading.Thread(target=dispatch_thread)
    t2.start()
    time.sleep(0.2)  # Let dispatch send task and block on queue
    t.join(timeout=1)  # WS context exits, unregister fires, put_error injects sentinel
    dispatch_done.wait(timeout=3)
    t2.join(timeout=1)

    assert len(result_holder) == 1
    assert "Error:" in result_holder[0]["result"]


def test_busy_message_routes_through_real_ws_handler_to_retryable_sentinel(client: TestClient) -> None:
    """A sidecar 'busy' reply must survive agent_ws_handler.py's real _ROUTED_TYPES
    allowlist and reach dispatch_to_agent as RETRYABLE_SENTINEL -- not a plain
    "Error: ..." string (which would trip Brain's circuit breaker).

    Regression test for PR #203's HIGH findings: earlier code review found that
    injecting a busy-shaped message directly via bridge.put() (bypassing the WS
    handler) could never have caught the routing-layer gap where 'busy' was
    dropped as an unknown message type before this fix.
    """
    def ws_thread() -> None:
        with client.websocket_connect("/agent/ws") as ws:
            ws.send_json({
                "type": "register",
                "agent_id": "busy-agent-1",
                "role": "developer",
                "capabilities": [],
                "cli": "gemini",
                "model": "test",
            })
            msg = ws.receive_json()
            if msg.get("type") == "task":
                # Real wire format emitted by the fixed gemini-sidecar/ws-client.js
                # busy-guard: type 'busy' (not 'error'), carrying task_id via sendMsg().
                ws.send_json({
                    "type": "busy",
                    "task_id": msg["task_id"],
                    "event_id": msg["event_id"],
                    "message": "Agent busy, task rejected.",
                })

    t = threading.Thread(target=ws_thread)
    t.start()
    for _ in range(20):
        time.sleep(0.05)
        if client.get("/api/agents").json():
            break

    resp = client.post("/api/test/dispatch?role=developer&event_id=evt-busy&task=do+it")
    t.join(timeout=5)

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == RETRYABLE_SENTINEL
    assert data["session_id"] is None


@pytest.mark.xfail(
    reason=(
        "Confirmed bug in PR #203's send_cancel()-on-timeout fix, not fixed here per "
        "QE/Developer pair-programming boundaries -- reported to Developer for a "
        "follow-up commit. Non-blocking (adds latency, does not corrupt state)."
    ),
    strict=False,
)
def test_timeout_cancel_path_does_not_add_unnecessary_delay(client: TestClient, monkeypatch) -> None:
    """dispatch_to_agent's asyncio.wait_for timeout now calls send_cancel() before
    returning (PR #203 MEDIUM fix). send_cancel() polls up to 5s for the queue to
    be deleted as a signal the sidecar responded -- but nothing can delete that
    queue while send_cancel() is still running, since dispatch_to_agent's own
    `finally: bridge.delete_queue(task_id)` only runs *after* send_cancel()
    returns. In this call site the poll can therefore never resolve early: every
    dispatch timeout is silently taxed with the full 5s poll on top of the
    configured timeout, with no sidecar activity to explain the wait.
    """
    monkeypatch.setenv("DISPATCH_TIMEOUT_S", "1")

    def ws_thread() -> None:
        with client.websocket_connect("/agent/ws") as ws:
            ws.send_json({
                "type": "register",
                "agent_id": "slow-agent-1",
                "role": "developer",
                "capabilities": [],
                "cli": "gemini",
                "model": "test",
            })
            ws.receive_json()  # receive the "task" message once, then go silent
            # Hold the connection open (simulate a silently hung sidecar) long enough
            # to span the 1s timeout plus send_cancel()'s up-to-5s poll -- do NOT loop
            # on receive_json() forever, or the `with` block never exits to close the
            # socket cleanly and fixture teardown hangs waiting for this thread.
            time.sleep(8)

    t = threading.Thread(target=ws_thread)
    t.start()
    for _ in range(20):
        time.sleep(0.05)
        if client.get("/api/agents").json():
            break

    try:
        start = time.monotonic()
        resp = client.post("/api/test/dispatch?role=developer&event_id=evt-slow&task=do+it")
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert "timed out" in resp.json()["result"]
        # Configured timeout is 1s; a generous 2s bound leaves headroom for the test
        # harness but still catches the ~5s send_cancel() poll tax documented above.
        assert elapsed < 2.0, (
            f"dispatch timeout took {elapsed:.2f}s for a 1s configured timeout -- "
            "send_cancel()'s 5s poll-for-queue-deletion likely fired needlessly "
            "(see docstring); known issue, reported to Developer, not fixed by QE"
        )
    finally:
        # Always join the sidecar thread (even on assertion failure above) --
        # otherwise it's still mid-sleep holding the WS open when the `client`
        # fixture tears down, and teardown hangs waiting for that connection.
        t.join(timeout=10)
