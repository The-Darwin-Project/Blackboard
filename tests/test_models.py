# tests/test_models.py
# @ai-rules:
# 1. [Pattern]: Pydantic model validation tests. Add tests for each new model in src/models.py.
# 2. [Constraint]: Test both valid construction and schema generation for API contract stability.
# 3. [Pattern]: EventDocument backward-compat tests verify that Redis blobs without new fields deserialize with defaults.
import json

import pytest
from src.models import EventDocument, EventInput, HealthResponse, EventEvidence


def test_health_response_valid():
    resp = HealthResponse(status="brain_online")
    assert resp.status == "brain_online"


def test_health_response_schema():
    schema = HealthResponse.model_json_schema()
    assert "status" in schema["properties"]


def test_event_document_created_by_email_default():
    """New EventDocument has created_by_email=None by default."""
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
    )
    assert event.created_by_email is None


def test_event_document_created_by_email_set():
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
        created_by_email="user@example.com",
    )
    assert event.created_by_email == "user@example.com"


def test_event_document_accepts_ci_gating_subject_type():
    """subject_type='ci_gating' is a valid Literal value (HIGH fix: aligner_ci_gating.md loader)."""
    event = EventDocument(
        source="aligner",
        service="pr-206",
        subject_type="ci_gating",
        event=EventInput(reason="test", evidence="test evidence"),
    )
    assert event.subject_type == "ci_gating"


def test_event_document_rejects_invalid_subject_type():
    with pytest.raises(Exception):
        EventDocument(
            source="chat",
            service="general",
            subject_type="not_a_real_type",
            event=EventInput(reason="test", evidence="test evidence"),
        )


def test_event_document_backward_compat_no_created_by_email():
    """Simulate deserializing a Redis blob that was stored before created_by_email existed."""
    legacy_blob = {
        "id": "evt-legacy01",
        "source": "chat",
        "status": "new",
        "service": "general",
        "event": {"reason": "old event", "evidence": "old evidence"},
        "conversation": [],
    }
    event = EventDocument(**legacy_blob)
    assert event.created_by_email is None
    assert event.id == "evt-legacy01"


def test_event_document_roundtrip_with_created_by_email():
    """Verify created_by_email survives JSON serialization roundtrip."""
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
        created_by_email="user@redhat.com",
    )
    blob = json.loads(json.dumps(event.model_dump()))
    restored = EventDocument(**blob)
    assert restored.created_by_email == "user@redhat.com"


def _fake_redis():
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_create_event_persists_created_by_email():
    """BlackboardState.create_event() round-trips created_by_email through Redis."""
    from src.state.blackboard import BlackboardState

    bb = BlackboardState(redis=_fake_redis())
    event_id = await bb.create_event(
        source="chat",
        service="general",
        reason="test message",
        evidence="test evidence",
        created_by_email="dev@redhat.com",
    )

    retrieved = await bb.get_event(event_id)
    assert retrieved is not None
    assert retrieved.created_by_email == "dev@redhat.com"
    assert retrieved.source == "chat"


@pytest.mark.asyncio
async def test_create_event_without_email_defaults_none():
    """Existing callers that don't pass created_by_email get None."""
    from src.state.blackboard import BlackboardState

    bb = BlackboardState(redis=_fake_redis())
    event_id = await bb.create_event(
        source="aligner",
        service="my-service",
        reason="CPU spike",
        evidence="test evidence",
    )

    retrieved = await bb.get_event(event_id)
    assert retrieved is not None
    assert retrieved.created_by_email is None


@pytest.mark.asyncio
async def test_create_event_seeds_initial_turns_before_queue_visible():
    """B-T1 (evt-996e33ec): the queued id is only ever visible WITH the seeded turn."""
    from src.models import ConversationTurn
    from src.state.blackboard import BlackboardState

    redis = _fake_redis()
    bb = BlackboardState(redis=redis)
    event_id = await bb.create_event(
        source="chat", service="general", reason="Hi Friday", evidence=EventEvidence(display_text="Hi Friday"),
        initial_turns=[ConversationTurn(turn=1, actor="user", action="message", thoughts="Hi Friday")],
    )

    popped = await redis.rpop(BlackboardState.EVENT_QUEUE)
    assert popped.decode() == event_id
    conv = json.loads(await redis.get(f"{BlackboardState.EVENT_PREFIX}{event_id}"))["conversation"]
    assert len(conv) == 1
    assert conv[0]["turn"] == 1
    assert conv[0]["actor"] == "user"
    assert conv[0]["thoughts"] == "Hi Friday"
    assert await redis.sismember(BlackboardState.EVENT_ACTIVE, event_id)


@pytest.mark.asyncio
async def test_create_event_is_one_transaction():
    """doc SET, active SADD and queue LPUSH are queued on ONE transaction=True pipeline;
    a failing EXEC leaves no partial state (no queue entry, no active member, no doc)."""
    from unittest.mock import patch

    from src.state.blackboard import BlackboardState

    redis = _fake_redis()
    bb = BlackboardState(redis=redis)
    real_pipeline = redis.pipeline
    seen_transaction_flags: list[bool] = []

    def spy_pipeline(*args, **kwargs):
        seen_transaction_flags.append(kwargs.get("transaction", True))
        pipe = real_pipeline(*args, **kwargs)

        async def boom():
            raise RuntimeError("EXEC failed")

        pipe.execute = boom
        return pipe

    with patch.object(redis, "pipeline", side_effect=spy_pipeline):
        with pytest.raises(RuntimeError):
            await bb.create_event(source="chat", service="general", reason="r", evidence=EventEvidence(display_text="e"))

    assert seen_transaction_flags == [True]
    assert await redis.llen(BlackboardState.EVENT_QUEUE) == 0
    assert await redis.scard(BlackboardState.EVENT_ACTIVE) == 0
    assert [k async for k in redis.scan_iter(f"{BlackboardState.EVENT_PREFIX}*")] == []


@pytest.mark.asyncio
async def test_create_event_numbers_multiple_initial_turns():
    """B-T2: seeded turns are renumbered 1..N; caller-supplied numbers are overwritten."""
    from src.models import ConversationTurn
    from src.state.blackboard import BlackboardState

    bb = BlackboardState(redis=_fake_redis())
    event_id = await bb.create_event(
        source="slack", service="general", reason="follow-up", evidence=EventEvidence(display_text="follow-up"),
        initial_turns=[
            ConversationTurn(turn=99, actor="brain", action="context", thoughts="ctx", source="system"),
            ConversationTurn(turn=7, actor="user", action="message", thoughts="hello", source="slack"),
        ],
    )

    event = await bb.get_event(event_id)
    assert [t.turn for t in event.conversation] == [1, 2]
    assert [t.actor for t in event.conversation] == ["brain", "user"]


@pytest.mark.asyncio
async def test_create_event_without_initial_turns_is_blank():
    """B-T3: back-compat -- automated sources still start with an empty conversation."""
    from src.state.blackboard import BlackboardState

    bb = BlackboardState(redis=_fake_redis())
    event_id = await bb.create_event(
        source="aligner", service="svc", reason="CPU spike", evidence=EventEvidence(display_text="x"),
    )

    event = await bb.get_event(event_id)
    assert event.conversation == []


def test_event_repository_protocol_create_event_accepts_initial_turns():
    """Port stays in lockstep with BlackboardState.create_event (evt-996e33ec)."""
    import inspect

    from src.state.blackboard import BlackboardState
    from src.state.ports import EventRepository

    port = inspect.signature(EventRepository.create_event).parameters
    impl = inspect.signature(BlackboardState.create_event).parameters
    assert "initial_turns" in port
    assert port["initial_turns"].default is None
    assert list(port) == list(impl)


def test_event_document_created_by_email_validator():
    """EventDocument.created_by_email validator normalizes whitespace to None."""
    # valid email
    event = EventDocument(source="chat", service="general", event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")), created_by_email="user@example.com")
    assert event.created_by_email == "user@example.com"
    
    # whitespace
    event2 = EventDocument(source="chat", service="general", event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")), created_by_email="   ")
    assert event2.created_by_email is None
    
    # empty string
    event3 = EventDocument(source="chat", service="general", event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")), created_by_email="")
    assert event3.created_by_email is None
    
    # None
    event4 = EventDocument(source="chat", service="general", event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")), created_by_email=None)
    assert event4.created_by_email is None
