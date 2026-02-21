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
from src.agents.dispatch import dispatch_to_agent
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
    time.sleep(0.15)

    resp = client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
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
