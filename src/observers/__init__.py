"""
Darwin Brain Observer modules.

Observers monitor external systems and feed data to the Blackboard.
They run independently of the request/response cycle.
"""
from .kargo import KargoObserver
from .argocd import ArgoCDObserver
from .flow_collector import FlowCollector

__all__ = ["KargoObserver", "ArgoCDObserver", "FlowCollector"]
