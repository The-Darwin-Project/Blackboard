# BlackBoard/src/agents/headhunter_smartsheet.py
# @ai-rules:
# 1. [Constraint]: Stub -- not yet implemented. Returns None for all lookups.
# 2. [Pattern]: Will be replaced with real Smartsheet API client when HEADHUNTER_MAINTAINER_SOURCE=smartsheet is needed.
"""
Smartsheet maintainer resolution (stub).

This module is imported by headhunter.py when HEADHUNTER_MAINTAINER_SOURCE=smartsheet.
Currently returns None for all lookups -- the static maintainer list covers v1.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class SmartsheetMaintainerCache:
    """Stub -- returns None until real Smartsheet API integration is implemented."""

    def __init__(self, api_token: str, sheet_id: str):
        self._token = api_token
        self._sheet_id = sheet_id
        logger.warning(
            "SmartsheetMaintainerCache is a stub -- all lookups return None. "
            "Use HEADHUNTER_MAINTAINER_SOURCE=static until this module is implemented."
        )

    async def get_maintainer(self, component: str) -> dict | None:
        return None

    async def get_release_maintainer(self) -> dict | None:
        return None
