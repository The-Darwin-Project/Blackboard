# BlackBoard/src/adapters/__init__.py
"""Infrastructure adapters (Hexagonal Architecture outer layer)."""
from .oidc_adapter import OIDCKeyAdapter
from .dashboard_ws import DashboardWSAdapter

__all__ = ["OIDCKeyAdapter", "DashboardWSAdapter"]
