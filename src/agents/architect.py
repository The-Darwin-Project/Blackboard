# BlackBoard/src/agents/architect.py
"""Agent 2: The Architect -- thin subclass of AgentClient."""
from .base_client import AgentClient


class Architect(AgentClient):
    def __init__(self):
        super().__init__(
            agent_name="architect",
            sidecar_url_env="ARCHITECT_SIDECAR_URL",
            default_url="http://localhost:9091",
            cwd="/data/gitops-architect",
        )
