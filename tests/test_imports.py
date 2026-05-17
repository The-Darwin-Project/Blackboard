# tests/test_imports.py
"""Import smoke tests -- catches broken relative imports that py_compile misses."""


def test_scheduling_package():
    from src.scheduling import ReconcileScheduler, FairQueue
    assert ReconcileScheduler is not None
    assert FairQueue is not None


def test_scheduling_triggers():
    from src.scheduling.triggers import QueueTrigger, ResyncTrigger, StalenessGuard
    assert QueueTrigger is not None
    assert ResyncTrigger is not None
    assert StalenessGuard is not None


def test_brain_imports_scheduling():
    """Verifies the Brain can resolve its lazy import of scheduling."""
    from src.agents.brain import Brain
    assert Brain is not None


def test_main_imports():
    from src.main import app
    assert app is not None
