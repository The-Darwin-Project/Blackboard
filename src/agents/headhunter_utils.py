# BlackBoard/src/agents/headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: Zero-import module. No headhunter/adapter/blackboard imports allowed.
# 2. [Pattern]: Shared constants for all Headhunter adapters.
# 3. [Gotcha]: Imported by headhunter.py, headhunter_gitlab.py, and headhunter_github.py
#    — circular imports are fatal if this file imports any of those.
"""Shared constants for Headhunter adapters. Import-cycle-safe (no sibling imports)."""
from __future__ import annotations

import os

_COMMENT_LIMIT = int(os.getenv("HEADHUNTER_COMMENT_LIMIT", "2000"))
