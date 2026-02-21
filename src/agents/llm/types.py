# src/agents/llm/types.py
# @ai-rules:
# 1. [Constraint]: All tool schemas are plain dicts (provider-agnostic). No google.genai or anthropic imports.
# 2. [Pattern]: LLMPort protocol defines generate() (blocking) and generate_stream() (async iterator).
# 3. [Gotcha]: Anthropic uses "input_schema" key; Gemini uses "parameters_json_schema". Adapters convert.
# 4. [Constraint]: BRAIN_TOOL_SCHEMAS must stay in sync with _execute_function_call() in brain.py.
"""
Provider-agnostic LLM types, protocol, and tool schemas.

Shared by GeminiAdapter and ClaudeAdapter. Consumers (Brain, Aligner) import
from this module and never touch SDK-specific types directly.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Optional, Protocol


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class FunctionCall:
    """Normalized function call from any LLM provider."""
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Blocking LLM response (used by Aligner + DevTeam Manager)."""
    function_call: Optional[FunctionCall] = None
    text: Optional[str] = None
    raw_parts: Optional[list] = None


@dataclass
class LLMChunk:
    """A single streaming chunk from the LLM (used by Brain)."""
    text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    done: bool = False
    is_thought: bool = False  # True for thinking/reasoning tokens (Gemini ThinkingConfig)
    raw_parts: Optional[list] = None  # Preserved response parts for thought_signature replay


# =============================================================================
# Port Protocol
# =============================================================================

class LLMPort(Protocol):
    """Hexagonal port -- adapters implement this for each LLM provider."""

    async def generate(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
    ) -> LLMResponse: ...

    async def generate_stream(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
    ) -> AsyncIterator[LLMChunk]: ...


# =============================================================================
# Brain Tool Schemas (11 tools -- plain dicts, provider-agnostic)
# =============================================================================
# Extracted from brain.py _build_brain_tools() FunctionDeclaration objects.
# Each adapter converts these to its SDK's native format.

BRAIN_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "select_agent",
        "description": "Route work to an agent. Use this to assign a task to Architect, sysAdmin, or Developer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["architect", "sysadmin", "developer"],
                    "description": "Which agent to route to",
                },
                "task_instruction": {
                    "type": "string",
                    "description": "What the agent should do (be specific and actionable)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["investigate", "execute", "rollback", "plan", "review", "analyze", "implement", "test"],
                    "description": "Behavioral mode for the agent. Determines scope of actions (e.g., investigate=read-only, execute=GitOps write, implement=full dev+QE team).",
                },
            },
            "required": ["agent_name", "task_instruction"],
        },
    },
    {
        "name": "close_event",
        "description": "Close the event as resolved. Use when the issue is fixed and verified, or the request is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was done and the outcome",
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "request_user_approval",
        "description": "Pause and ask the user to approve a plan. Use for structural changes (source code, templates).",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_summary": {
                    "type": "string",
                    "description": "Summary of the plan for the user to review",
                },
            },
            "required": ["plan_summary"],
        },
    },
    {
        "name": "re_trigger_aligner",
        "description": "Ask the Aligner to verify that a change took effect (e.g., replicas increased, CPU normalized).",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service to check",
                },
                "check_condition": {
                    "type": "string",
                    "description": "What condition to verify (e.g., 'replicas == 2', 'CPU < 80%')",
                },
            },
            "required": ["service", "check_condition"],
        },
    },
    {
        "name": "ask_agent_for_state",
        "description": "Ask an agent for information (e.g., ask sysAdmin for kubectl logs, pod status).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["architect", "sysadmin", "developer"],
                    "description": "Which agent to ask",
                },
                "question": {
                    "type": "string",
                    "description": "What information you need",
                },
            },
            "required": ["agent_name", "question"],
        },
    },
    {
        "name": "wait_for_verification",
        "description": "Mark that you are waiting for the Aligner to confirm a state change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "description": "What you are waiting for",
                },
            },
            "required": ["condition"],
        },
    },
    {
        "name": "defer_event",
        "description": "Defer an event for later processing. Use when an agent is busy, the issue is not urgent, or you want to retry after a cooldown period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why this event is being deferred (e.g., 'agent busy', 'waiting for cooldown')",
                },
                "delay_seconds": {
                    "type": "integer",
                    "description": "How many seconds to wait before re-processing (30-3600, i.e. up to 60 minutes)",
                },
            },
            "required": ["reason", "delay_seconds"],
        },
    },
    {
        "name": "wait_for_user",
        "description": (
            "Signal that the current question is answered but agent recommendations exist. "
            "Summarize findings and available next actions for the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of findings and available actions",
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "lookup_service",
        "description": (
            "Look up a service's GitOps metadata from telemetry data. Returns repo URL, helm path, "
            "version, replicas, and current metrics. Use this BEFORE routing to an agent when you "
            "need a service's repository URL or deployment details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name to look up (e.g., 'darwin-store')",
                },
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "lookup_journal",
        "description": (
            "Look up the ops journal for any service. Returns recent event history "
            "(closures, scaling actions, fixes). Use to check what happened recently "
            "to a service or its dependencies before making decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name to look up (e.g., 'darwin-store', 'postgres')",
                },
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "consult_deep_memory",
        "description": (
            "Search operational history for similar past events. Returns symptoms, root causes, "
            "and fixes from past incidents. Use before acting on unfamiliar issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g., 'high CPU on darwin-store')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "notify_user_slack",
        "description": (
            "Send a Slack DM notification to a user by email address. "
            "Use when an agent recommends notifying someone, or when the event outcome "
            "requires human attention (e.g., pipeline failure notification, escalation). "
            "The message is delivered as a DM from the Darwin bot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_email": {
                    "type": "string",
                    "description": "Email address of the Slack user to notify (e.g., 'user@company.com')",
                },
                "message": {
                    "type": "string",
                    "description": "The notification message to send",
                },
            },
            "required": ["user_email", "message"],
        },
    },
]


# =============================================================================
# Aligner Tool Schemas (3 tools -- plain dicts, provider-agnostic)
# =============================================================================
# Extracted from aligner.py _build_aligner_tools() FunctionDeclaration objects.

ALIGNER_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "create_event",
        "description": (
            "Create a new event for the Brain to investigate. "
            "Use when you detect a sustained anomaly that requires attention."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "observation": {
                    "type": "string",
                    "description": (
                        "Your full observation in natural language -- what you saw, "
                        "the numbers, the trend, and why it needs attention"
                    ),
                },
                "severity": {
                    "type": "string",
                    "enum": ["warning", "critical"],
                    "description": "How urgent: warning (degraded but functional) or critical (service impacted)",
                },
                "domain": {
                    "type": "string",
                    "enum": ["clear", "complicated", "complex", "chaotic"],
                    "description": (
                        "Cynefin domain: clear (known fix), complicated (needs analysis), "
                        "complex (unknown cause), chaotic (system down)"
                    ),
                },
                "execution_mode": {
                    "type": "string",
                    "description": (
                        "Cynefin response pattern: sense-categorize-respond, "
                        "sense-analyze-respond, probe-sense-respond, or act-sense-respond"
                    ),
                },
                "metrics": {
                    "type": "object",
                    "description": "Current metric snapshot",
                    "properties": {
                        "cpu": {"type": "number", "description": "CPU usage %"},
                        "memory": {"type": "number", "description": "Memory usage %"},
                        "error_rate": {"type": "number", "description": "Error rate %"},
                        "replicas": {"type": "integer", "description": "Replica count"},
                    },
                },
            },
            "required": ["service", "observation", "severity", "domain"],
        },
    },
    {
        "name": "update_active_event",
        "description": (
            "Add new metric observations to an active event the Brain is already working on. "
            "Use when you see new data relevant to an ongoing investigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "observation": {
                    "type": "string",
                    "description": (
                        "Your updated observation -- new metrics, trend changes, "
                        "or confirmation of ongoing issue"
                    ),
                },
            },
            "required": ["service", "observation"],
        },
    },
    {
        "name": "report_recovery",
        "description": (
            "Report that a service's metrics have returned to normal. "
            "Use ONLY when the latest metrics are clearly below ALL thresholds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "observation": {
                    "type": "string",
                    "description": (
                        "What you observed -- the peak values, current values, trend, "
                        "and why you believe the anomaly is resolved"
                    ),
                },
            },
            "required": ["service", "observation"],
        },
    },
]


# =============================================================================
# Manager Tool Schemas (8 tools -- Dev Team Manager function calling)
# =============================================================================

MANAGER_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "dispatch_developer",
        "description": "Route task to the developer agent only. Use for code changes, MR operations, single write actions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "What the developer should do (specific and actionable)"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "dispatch_qe",
        "description": "Route task to the QE agent only. Use for writing tests, verification, quality checks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "What QE should do (specific and actionable)"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "dispatch_both",
        "description": "Dispatch to developer AND QE concurrently. Use for feature implementations that need both code and tests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dev_task": {"type": "string", "description": "What the developer should implement"},
                "qe_task": {"type": "string", "description": "What QE should test/verify"},
            },
            "required": ["dev_task", "qe_task"],
        },
    },
    {
        "name": "request_review",
        "description": "Quality gate -- review the developer and QE outputs to decide next action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dev_output": {"type": "string", "description": "Developer's result"},
                "qe_output": {"type": "string", "description": "QE's result"},
            },
            "required": ["dev_output", "qe_output"],
        },
    },
    {
        "name": "approve_and_merge",
        "description": "Outputs are approved. Tell developer to open PR and merge.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dev_agent_id": {"type": "string", "description": "The agent_id of the developer who implemented the change"},
            },
            "required": ["dev_agent_id"],
        },
    },
    {
        "name": "request_fix",
        "description": "Send a fix or verify request to a specific agent (session affinity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "The agent_id to send the fix request to"},
                "feedback": {"type": "string", "description": "What needs to be fixed or verified"},
            },
            "required": ["agent_id", "feedback"],
        },
    },
    {
        "name": "report_to_brain",
        "description": "Return merged result to the Brain. Call this when the team's work is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Merged result summary (dev + qe + PR status)"},
                "status": {"type": "string", "enum": ["success", "partial", "failed"], "description": "Overall outcome"},
            },
            "required": ["summary", "status"],
        },
    },
    {
        "name": "reply_to_agent",
        "description": "Reply to a HuddleSendMessage from an agent. Sends the reply text back to the agent's CLI via the persistent WS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent to reply to"},
                "message": {"type": "string", "description": "Reply content"},
            },
            "required": ["agent_id", "message"],
        },
    },
]
