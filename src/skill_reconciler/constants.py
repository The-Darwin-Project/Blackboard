# BlackBoard/src/skill_reconciler/constants.py
# @ai-rules:
# 1. [Constraint]: Shared Redis key constants for skill reconciler + loader. No imports from agents/.
# 2. [Pattern]: Single source of truth for darwin:skills:* key names.
"""Redis key constants for the skill hot-reload system."""

REDIS_KEY_VERSION = "darwin:skills:version"
REDIS_KEY_CORPUS = "darwin:skills:corpus"
REDIS_KEY_PHASE_CONFIG = "darwin:skills:phase_config"
REDIS_KEY_SYNC_STATE = "darwin:skills:sync_state"
