# BlackBoard/src/observers/__init__.py
"""
Darwin Brain Observer modules.

Observers monitor external systems and feed data to the Blackboard.
They run independently of the request/response cycle.
"""
from .kubernetes import KubernetesObserver
from .kargo import KargoObserver

__all__ = ["KubernetesObserver", "KargoObserver"]
