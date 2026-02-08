# BlackBoard/src/agents/sysadmin.py
"""Agent 3: The SysAdmin -- thin subclass of AgentClient."""
from .base_client import AgentClient


class SysAdmin(AgentClient):
    def __init__(self):
        super().__init__(
            agent_name="sysadmin",
            sidecar_url_env="SYSADMIN_SIDECAR_URL",
            default_url="http://localhost:9092",
            cwd="/data/gitops-sysadmin",
        )
