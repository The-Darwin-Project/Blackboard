# BlackBoard/src/agents/developer.py
"""Agent 4: The Developer -- thin subclass of AgentClient."""
from .base_client import AgentClient


class Developer(AgentClient):
    def __init__(self):
        super().__init__(
            agent_name="developer",
            sidecar_url_env="DEVELOPER_SIDECAR_URL",
            default_url="http://localhost:9093",
            cwd="/data/gitops-developer",
        )
