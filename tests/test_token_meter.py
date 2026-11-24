# tests/test_token_meter.py
"""TokenMeter unit tests: snapshot, drain, platform totals, system bucket."""
from src.agents.llm.token_meter import TokenMeter
from src.agents.llm.types import TokenUsage

EXPECTED_KEYS = {"input_tokens", "output_tokens", "thinking_tokens", "cached_tokens",
                 "tool_use_tokens", "total_tokens", "calls"}


def _usage(inp=0, out=0, think=0, cached=0, tool=0, total=0):
    return TokenUsage(input_tokens=inp, output_tokens=out, thinking_tokens=think,
                      cached_tokens=cached, tool_use_tokens=tool, total_tokens=total)


def test_record_and_snapshot_returns_deltas():
    meter = TokenMeter()
    meter.record("brain", "gemini-3-pro", _usage(inp=100, out=50, total=150), "evt-1")
    meter.record("aligner", "gemini-3.5-flash", _usage(inp=20, out=10, total=30))
    meter.record("brain", "gemini-3-pro", _usage(inp=80, out=40, total=120), "evt-1")

    snap = meter.snapshot()
    assert set(snap.keys()) == EXPECTED_KEYS
    assert snap["input_tokens"] == 200  # 100+20+80
    assert snap["output_tokens"] == 100
    assert snap["total_tokens"] == 300
    assert snap["calls"] == 3


def test_snapshot_resets_interval_counters():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100))
    meter.snapshot()

    snap2 = meter.snapshot()
    assert snap2["total_tokens"] == 0
    assert snap2["calls"] == 0


def test_platform_totals_are_cumulative():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100))
    meter.snapshot()  # resets interval
    meter.record("brain", "m", _usage(total=50))

    totals = meter.get_platform_totals()
    assert totals["total_tokens"] == 150
    assert totals["calls"] == 2


def test_drain_event_returns_totals_and_clears():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(inp=100, out=50, think=20, total=170), "evt-a")
    meter.record("brain", "m", _usage(inp=30, out=10, total=40), "evt-a")

    drained = meter.drain_event("evt-a")
    assert drained is not None
    assert set(drained.keys()) == EXPECTED_KEYS
    assert drained["input_tokens"] == 130
    assert drained["output_tokens"] == 60
    assert drained["thinking_tokens"] == 20
    assert drained["calls"] == 2


def test_drain_event_idempotent():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100), "evt-b")
    first = meter.drain_event("evt-b")
    assert first is not None

    second = meter.drain_event("evt-b")
    assert second is None


def test_system_bucket_not_in_drain():
    meter = TokenMeter()
    meter.record("aligner", "m", _usage(total=999))
    meter.record("brain", "m", _usage(total=50), "evt-c")

    drained = meter.drain_event("evt-c")
    assert drained is not None
    assert drained["total_tokens"] == 50

    drained_system = meter.drain_event("nonexistent")
    assert drained_system is None

    totals = meter.get_platform_totals()
    assert totals["total_tokens"] == 1049


# =============================================================================
# 4-Layer ATDD Specification: VMER-2450 Step 1 (T-1, T-2, T-3)
# =============================================================================


class TokenMeterDriver:
    """Layer 3 Protocol Driver wrapping TokenMeter (in-memory SUT)."""

    def __init__(self) -> None:
        self.meter = TokenMeter()

    def record(
        self,
        caller: str,
        model: str,
        *,
        inp: int = 0,
        out: int = 0,
        think: int = 0,
        cached: int = 0,
        tool: int = 0,
        total: int = 0,
        event_id: str | None = None,
    ) -> None:
        self.meter.record(
            caller,
            model,
            _usage(inp=inp, out=out, think=think, cached=cached, tool=tool, total=total),
            event_id,
        )


class TokenMeterDSL:
    """Layer 2 Domain DSL for per-caller metering, atomic drain, and contention."""

    def __init__(self, driver: TokenMeterDriver) -> None:
        self.driver = driver
        self.last_agg: dict[str, int] | None = None
        self.last_by_caller: dict[str, dict[str, int]] | None = None
        self.last_caller_totals: dict[str, dict[str, int]] | None = None

    def given_caller_usage(
        self,
        caller: str,
        *,
        inp: int = 0,
        cached: int = 0,
        out: int = 0,
        think: int = 0,
        total: int | None = None,
        event_id: str | None = None,
        model: str = "gemini-4-neon",
    ) -> None:
        computed_total = total if total is not None else (inp + out + think)
        self.driver.record(
            caller,
            model,
            inp=inp,
            out=out,
            think=think,
            cached=cached,
            total=computed_total,
            event_id=event_id,
        )

    def when_snapshot_with_callers_taken(self) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
        agg, by_caller = self.driver.meter.snapshot_with_callers()
        self.last_agg = agg
        self.last_by_caller = by_caller
        return agg, by_caller

    def when_legacy_snapshot_taken(self) -> dict[str, int]:
        return self.driver.meter.snapshot()

    def when_caller_totals_read(self) -> dict[str, dict[str, int]]:
        totals = self.driver.meter.get_caller_totals()
        self.last_caller_totals = totals
        return totals


class TestTokenMeterPerCallerATDD:
    """Layer 1 Domain Scenarios: Per-caller TokenMeter breakdown & atomicity (T-1..T-3)."""

    def test_t1_snapshot_with_callers_isolates_callers_and_preserves_frozen_keys(self):
        """
        Scenario T-1a:
        Given TokenMeter receives calls from "brain" and "aligner"
        When snapshot_with_callers() is called
        Then aggregate keys match frozen TokenUsageDict, by_caller isolates each caller's
        input/cached/calls deltas, and a second immediate snapshot drains to empty.
        """
        dsl = TokenMeterDSL(TokenMeterDriver())
        dsl.given_caller_usage("brain", inp=600, cached=500, out=50, event_id="evt-1")
        dsl.given_caller_usage("aligner", inp=500, cached=0, out=20, model="gemini-3.5-flash")
        dsl.given_caller_usage("brain", inp=400, cached=400, out=30, event_id="evt-1")

        agg, by_caller = dsl.when_snapshot_with_callers_taken()

        assert set(agg.keys()) == EXPECTED_KEYS
        assert agg["input_tokens"] == 1500
        assert agg["cached_tokens"] == 900
        assert agg["output_tokens"] == 100
        assert agg["total_tokens"] == 1600
        assert agg["calls"] == 3

        assert set(by_caller.keys()) == {"brain", "aligner"}
        assert set(by_caller["brain"].keys()) == EXPECTED_KEYS
        assert by_caller["brain"]["input_tokens"] == 1000
        assert by_caller["brain"]["cached_tokens"] == 900
        assert by_caller["brain"]["output_tokens"] == 80
        assert by_caller["brain"]["calls"] == 2

        assert set(by_caller["aligner"].keys()) == EXPECTED_KEYS
        assert by_caller["aligner"]["input_tokens"] == 500
        assert by_caller["aligner"]["cached_tokens"] == 0
        assert by_caller["aligner"]["calls"] == 1

        # Second drain with no new recordings resets both aggregate and per-caller intervals
        agg2, by_caller2 = dsl.when_snapshot_with_callers_taken()
        assert set(agg2.keys()) == EXPECTED_KEYS
        assert agg2["total_tokens"] == 0
        assert agg2["calls"] == 0
        assert by_caller2 == {}

    def test_t1_get_caller_totals_returns_non_destructive_cumulative_totals(self):
        """
        Scenario T-1b:
        Given TokenMeter records usage across multiple snapshot intervals
        When get_caller_totals() is called repeatedly
        Then cumulative per-caller totals persist across drains and return defensive copies.
        """
        dsl = TokenMeterDSL(TokenMeterDriver())
        dsl.given_caller_usage("brain", inp=1000, cached=900, out=50)
        dsl.given_caller_usage("aligner", inp=200, cached=0, out=10)
        dsl.when_snapshot_with_callers_taken()

        dsl.given_caller_usage("brain", inp=500, cached=450, out=25)
        totals = dsl.when_caller_totals_read()

        assert set(totals.keys()) == {"brain", "aligner"}
        assert set(totals["brain"].keys()) == EXPECTED_KEYS
        assert totals["brain"]["input_tokens"] == 1500
        assert totals["brain"]["cached_tokens"] == 1350
        assert totals["brain"]["calls"] == 2
        assert totals["aligner"]["input_tokens"] == 200
        assert totals["aligner"]["calls"] == 1

        # Non-destructive: mutating returned dict does not corrupt internal cumulative state
        totals["brain"]["input_tokens"] = -999
        totals_again = dsl.when_caller_totals_read()
        assert totals_again["brain"]["input_tokens"] == 1500

    def test_t1_legacy_snapshot_atomically_resets_interval_by_caller(self):
        """
        Scenario T-1c:
        Given TokenMeter has pending interval usage from "brain" and "aligner"
        When existing snapshot() is called
        Then _interval_by_caller is reset atomically so a subsequent snapshot_with_callers()
        returns empty by_caller (no divergence), while cumulative caller totals remain intact.
        """
        dsl = TokenMeterDSL(TokenMeterDriver())
        dsl.given_caller_usage("brain", inp=1000, cached=800, out=40)
        dsl.given_caller_usage("aligner", inp=300, cached=0, out=20)

        snap = dsl.when_legacy_snapshot_taken()
        assert set(snap.keys()) == EXPECTED_KEYS
        assert snap["input_tokens"] == 1300

        agg_after, by_caller_after = dsl.when_snapshot_with_callers_taken()
        assert agg_after["input_tokens"] == 0
        assert agg_after["calls"] == 0
        assert by_caller_after == {}

        totals = dsl.when_caller_totals_read()
        assert totals["brain"]["input_tokens"] == 1000
        assert totals["aligner"]["input_tokens"] == 300

    def test_t2_drain_event_double_drain_preserves_frozen_keys(self):
        """
        Scenario T-2:
        Given TokenMeter records event usage with cached tokens
        When drain_event() is called twice
        Then the first call returns exact frozen TokenUsageDict keys and the second returns None.
        """
        dsl = TokenMeterDSL(TokenMeterDriver())
        dsl.given_caller_usage("brain", inp=1000, cached=900, out=100, event_id="evt-t2")
        dsl.given_caller_usage("aligner", inp=250, cached=0, out=25)

        first = dsl.driver.meter.drain_event("evt-t2")
        assert first is not None
        assert set(first.keys()) == EXPECTED_KEYS
        assert first["input_tokens"] == 1000
        assert first["cached_tokens"] == 900
        assert first["calls"] == 1

        second = dsl.driver.meter.drain_event("evt-t2")
        assert second is None
        assert dsl.driver.meter.peek_event("evt-t2") is None
        assert set(dsl.driver.meter.get_platform_totals().keys()) == EXPECTED_KEYS

    def test_t3_concurrent_record_and_snapshot_with_callers_no_lost_or_double_counts(self):
        """
        Scenario T-3:
        Given concurrent threads calling record() and snapshot_with_callers() under contention
        When all threads finish and a final snapshot is drained
        Then summed aggregate snapshots equal get_platform_totals() AND summed per-caller
        snapshots equal get_caller_totals() with zero lost or double-counted tokens.
        """
        import threading

        meter = TokenMeter()
        writer_specs = [
            ("brain", 100, 90, 10, 200),
            ("brain", 50, 40, 5, 200),
            ("aligner", 30, 0, 10, 200),
            ("aligner", 20, 0, 5, 200),
        ]
        barrier = threading.Barrier(len(writer_specs) + 2)
        stop_readers = threading.Event()
        snapshots: list[tuple[dict[str, int], dict[str, dict[str, int]]]] = []
        snap_lock = threading.Lock()
        errors: list[BaseException] = []

        def writer(caller: str, inp: int, cached: int, out: int, count: int) -> None:
            try:
                barrier.wait(timeout=5)
                usage = _usage(inp=inp, cached=cached, out=out, total=inp + out)
                for _ in range(count):
                    meter.record(caller, "gemini-4-neon", usage)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def reader() -> None:
            try:
                barrier.wait(timeout=5)
                while not stop_readers.is_set():
                    snap = meter.snapshot_with_callers()
                    with snap_lock:
                        snapshots.append(snap)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        writers = [threading.Thread(target=writer, args=spec) for spec in writer_specs]
        readers = [threading.Thread(target=reader) for _ in range(2)]

        for t in writers + readers:
            t.start()
        for t in writers:
            t.join(timeout=10)
        stop_readers.set()
        for t in readers:
            t.join(timeout=10)

        if errors:
            raise errors[0]

        snapshots.append(meter.snapshot_with_callers())

        agg_sum = {k: 0 for k in EXPECTED_KEYS}
        caller_sums: dict[str, dict[str, int]] = {}
        for agg, by_caller in snapshots:
            assert set(agg.keys()) == EXPECTED_KEYS
            for k in EXPECTED_KEYS:
                agg_sum[k] += agg[k]
            for caller, c_dict in by_caller.items():
                assert set(c_dict.keys()) == EXPECTED_KEYS
                bucket = caller_sums.setdefault(caller, {k: 0 for k in EXPECTED_KEYS})
                for k in EXPECTED_KEYS:
                    bucket[k] += c_dict[k]

        platform_totals = meter.get_platform_totals()
        caller_totals = meter.get_caller_totals()

        assert agg_sum == platform_totals
        assert platform_totals["calls"] == 800
        assert platform_totals["input_tokens"] == (100 + 50 + 30 + 20) * 200
        assert platform_totals["cached_tokens"] == (90 + 40) * 200

        assert caller_sums == caller_totals
        assert caller_totals["brain"]["calls"] == 400
        assert caller_totals["brain"]["input_tokens"] == 150 * 200
        assert caller_totals["brain"]["cached_tokens"] == 130 * 200
        assert caller_totals["aligner"]["calls"] == 400
        assert caller_totals["aligner"]["input_tokens"] == 50 * 200
        assert caller_totals["aligner"]["cached_tokens"] == 0
