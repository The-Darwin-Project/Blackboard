# BlackBoard/src/dependencies.py
"""FastAPI dependency injection for Darwin Blackboard."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .state.blackboard import BlackboardState
from .state.redis_client import get_redis

if TYPE_CHECKING:
    from .agents.aligner import Aligner
    from .agents.architect import Architect
    from .agents.brain import Brain
    from .agents.developer import Developer
    from .agents.sysadmin import SysAdmin

# Global instances (initialized in main.py lifespan)
_blackboard: Optional[BlackboardState] = None
_aligner: Optional["Aligner"] = None
_architect: Optional["Architect"] = None
_sysadmin: Optional["SysAdmin"] = None
_developer: Optional["Developer"] = None
_brain: Optional["Brain"] = None


def set_blackboard(blackboard: BlackboardState) -> None:
    """Set the global Blackboard instance."""
    global _blackboard
    _blackboard = blackboard


def set_agents(
    aligner: "Aligner",
    architect: "Architect",
    sysadmin: "SysAdmin",
    developer: "Developer",
) -> None:
    """Set the global agent instances."""
    global _aligner, _architect, _sysadmin, _developer
    _aligner = aligner
    _architect = architect
    _sysadmin = sysadmin
    _developer = developer


def set_brain(brain: "Brain") -> None:
    """Set the global Brain instance."""
    global _brain
    _brain = brain


async def get_blackboard() -> BlackboardState:
    """
    Get the Blackboard state instance.
    
    FastAPI dependency.
    """
    if _blackboard is None:
        raise RuntimeError("Blackboard not initialized. Check startup sequence.")
    return _blackboard


async def get_aligner() -> "Aligner":
    """Get the Aligner agent instance."""
    if _aligner is None:
        raise RuntimeError("Aligner not initialized. Check startup sequence.")
    return _aligner


async def get_architect() -> "Architect":
    """Get the Architect agent instance."""
    if _architect is None:
        raise RuntimeError("Architect not initialized. Check startup sequence.")
    return _architect


async def get_sysadmin() -> "SysAdmin":
    """Get the SysAdmin agent instance."""
    if _sysadmin is None:
        raise RuntimeError("SysAdmin not initialized. Check startup sequence.")
    return _sysadmin


async def get_developer() -> "Developer":
    """Get the Developer agent instance."""
    if _developer is None:
        raise RuntimeError("Developer not initialized. Check startup sequence.")
    return _developer


async def get_brain() -> "Brain":
    """Get the Brain orchestrator instance."""
    if _brain is None:
        raise RuntimeError("Brain not initialized. Check startup sequence.")
    return _brain
