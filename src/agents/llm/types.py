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
    """Blocking LLM response (used by Aligner)."""
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
        thinking_level: str = "",
    ) -> LLMResponse: ...

    async def generate_stream(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
        thinking_level: str = "",
    ) -> AsyncIterator[LLMChunk]: ...


# =============================================================================
# Brain Tool Schemas (11 tools -- plain dicts, provider-agnostic)
# =============================================================================
# Extracted from brain.py _build_brain_tools() FunctionDeclaration objects.
# Each adapter converts these to its SDK's native format.

BRAIN_TOOL_SCHEMAS: list[dict] = [
    # --- Lookup tools (check BEFORE routing) ---
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
            "Look up the ops journal. When service_name is provided, returns history for that "
            "specific service. When omitted, returns recent entries across all services -- useful "
            "for cross-service timing, pipeline patterns, and operational trends. Use FIRST for "
            "any question about what happened, recent events, service history, or status. Can "
            "directly answer user questions without needing an agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name to look up. service_name is optional, name can be omitted for cross-service/source results.",
                },
            },
        },
    },
    {
        "name": "consult_deep_memory",
        "description": (
            "Search operational history for past events. Returns incident details, operational "
            "timings, defer patterns, and procedural workflows. Use for: recurring issues, "
            "timing questions, past event queries, or pattern analysis. MUST be called before "
            "select_agent for recurring issues, past event queries, or unfamiliar symptoms. "
            "Can directly answer user questions about history without needing an agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g., 'average pipeline time', 'high CPU on darwin-store')",
                },
            },
            "required": ["query"],
        },
    },
    # --- Classification (mandatory gate before routing) ---
    {
        "name": "classify_event",
        "description": (
            "Classify this event's Cynefin domain. Called once during initial triage -- "
            "select_agent requires a prior classification. Reclassify only when NEW evidence "
            "changes the domain (e.g., agent reports unexpected complexity). "
            "Do NOT reclassify just because a new processing cycle started."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["clear", "complicated", "complex", "chaotic"],
                    "description": "Your assessed Cynefin domain",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One sentence explaining why this domain (not the source's suggestion)",
                },
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "description": (
                        "Optional severity override. Use when evidence warrants escalation "
                        "(e.g., third consecutive pipeline failure -> critical). "
                        "Omit to keep the source classification."
                    ),
                },
            },
            "required": ["domain", "reasoning"],
        },
    },
    # --- Routing tools (use AFTER classification when agent action is needed) ---
    {
        "name": "select_agent",
        "description": (
            "Route work to an agent. Use ONLY when the task requires agent capabilities "
            "(infrastructure operations, code changes, cluster inspection). Do NOT use for questions answerable from "
            "lookup_journal, consult_deep_memory, or lookup_service."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["architect", "sysadmin", "developer", "qe"],
                    "description": "Which agent to route to",
                },
                "task_instruction": {
                    "type": "string",
                    "description": "What the agent should do (be specific and actionable)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["investigate", "execute", "rollback", "plan", "review", "analyze", "implement", "test"],
                    "description": (
                        "Mode controls which skills and tools load on the agent. "
                        "investigate=read-only cluster and service inspection. "
                        "execute=git actions, MR comments, merge, retest (no cluster investigation). "
                        "implement=code changes, feature development. "
                        "test=QE verification, browser testing. "
                        "If the task needs both action AND investigation, split into separate dispatches with different modes."
                    ),
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
        "description": "Ask an agent for information (e.g., ask sysAdmin for cluster status, ask QE for test results).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["architect", "sysadmin", "developer", "qe"],
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
        "name": "wait_for_agent",
        "description": (
            "Signal that the Brain is waiting for an agent to complete its task. "
            "Pauses the event until the agent reports back. Use when you have dispatched "
            "an agent and need to wait for its result before proceeding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "What the Brain is waiting for (e.g., 'Waiting for QE to complete pagination tests')",
                },
            },
            "required": ["summary"],
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
    {
        "name": "reply_to_agent",
        "description": (
            "Reply to an agent's team_huddle message. Sends the reply directly to the "
            "agent's CLI via its persistent WebSocket. The agent is blocked waiting for "
            "this reply -- keep it concise and actionable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Role name of the agent to reply to: 'developer', 'qe', 'sysadmin', or 'architect'. The system resolves this to the active agent working on the current event.",
                },
                "message": {
                    "type": "string",
                    "description": "Reply content -- guidance, acknowledgment, or next-step instruction",
                },
            },
            "required": ["agent_id", "message"],
        },
    },
    {
        "name": "message_agent",
        "description": (
            "Send an ad-hoc message to an agent. If the agent is busy, the message is "
            "delivered at its next tool boundary. If idle, the agent wakes to process "
            "the message and the response appears in the conversation. Use for quick "
            "questions, status checks, and coordination -- NOT for work plans (use "
            "select_agent for those). Pass the role name: 'developer', 'qe', 'sysadmin', "
            "or 'architect'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Role name of the agent to message: 'developer', 'qe', 'sysadmin', or 'architect'. The system resolves this to the correct agent connection.",
                },
                "message": {
                    "type": "string",
                    "description": "Message content",
                },
            },
            "required": ["agent_id", "message"],
        },
    },
    {
        "name": "notify_gitlab_result",
        "description": (
            "Post a result comment on a GitLab MR and optionally re-assign the reviewer. "
            "Use for headhunter-sourced events when the task is complete or needs escalation. "
            "The MR details are in evidence.gitlab_context. "
            "If evidence.gitlab_context is missing, this tool returns an error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "GitLab project ID from evidence.gitlab_context.project_id"},
                "mr_iid": {"type": "integer", "description": "MR internal ID from evidence.gitlab_context.mr_iid"},
                "result": {
                    "type": "string",
                    "enum": ["success", "failure", "escalation"],
                    "description": "Outcome: success (merged/resolved), failure (still broken), escalation (needs human)",
                },
                "summary": {"type": "string", "description": "Text to post as MR comment summarizing what Darwin did"},
                "reassign_reviewer": {
                    "type": "boolean",
                    "description": "If true, re-tag the maintainer as MR reviewer (use on failure/escalation)",
                },
            },
            "required": ["project_id", "mr_iid", "result", "summary"],
        },
    },
    {
        "name": "create_plan",
        "description": (
            "Chalk a structured plan on the blackboard. Use for COMPLICATED or COMPLEX "
            "events to define the intended agent sequence before routing. Each step specifies "
            "which agent handles it. The plan is visible to all agents and the dashboard. "
            "For CLEAR or CHAOTIC events, route directly -- the routing turn IS the plan. "
            "If you need this tool but are in CLEAR/CHAOTIC, reclassify the event first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Step number (e.g., '1', '2')"},
                            "agent": {
                                "type": "string",
                                "enum": ["architect", "sysadmin", "developer", "qe"],
                                "description": "Which agent handles this step",
                            },
                            "summary": {"type": "string", "description": "What this step accomplishes"},
                        },
                        "required": ["id", "agent", "summary"],
                    },
                    "description": "Ordered list of plan steps",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why this plan sequence (one sentence)",
                },
            },
            "required": ["steps", "reasoning"],
        },
    },
    {
        "name": "get_plan_progress",
        "description": (
            "Read the current plan and step completion status for this event. "
            "Returns the active plan steps with their assigned agents and current status "
            "(pending, in_progress, completed, blocked). Use to decide which step to "
            "execute next or whether to close the event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_incident",
        "description": (
            "Create an incident report in the CNV Release Incident tracking sheet. "
            "Use when an automated event (headhunter, timekeeper) results in a persistent "
            "failure requiring team investigation -- e.g., pipeline fails after retest, "
            "infrastructure outage, or repeated CI failures. Systemic fields (reporter, "
            "date, status, labels, issue type, components) are auto-populated. You only "
            "provide event-specific details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": [
                        "CPaaS", "Konflux", "Kargo", "CNV2 Cluster",
                        "QE-Smoke tests", "QE-Gating", "CVP", "GitLab CEE",
                        "Quay", "Brew", "Errata", "Candidate-releases",
                        "Downstream-Sync", "Jira",
                    ],
                    "description": "Affected platform (infer from event evidence)",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line incident summary",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description: what failed, timeline, actions taken",
                },
                "priority": {
                    "type": "string",
                    "enum": ["Normal", "Minor", "Major", "Critical", "Blocker"],
                    "description": "Normal for transient retests, Major for persistent failures, Critical/Blocker for outages",
                },
                "affected_versions": {
                    "type": "string",
                    "description": "Affected versions, e.g. 'v4.22' or 'v4.22, v5.99'",
                },
            },
            "required": ["platform", "summary", "description", "priority"],
        },
    },
    {
        "name": "refresh_gitlab_context",
        "description": (
            "Quick-check: ask the Headhunter to re-fetch current MR and pipeline "
            "state from GitLab WITHOUT dispatching an agent. Returns a snapshot of "
            "the current state. Use in two patterns: "
            "(1) Pre-dispatch triage: refresh before selecting an agent so you can "
            "give precise instructions (e.g., 'pipeline failed' vs 'pipeline passed, merge'). "
            "(2) Post-defer check: after deferring for a running pipeline, refresh to "
            "see the outcome before deciding next action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "check_condition": {
                    "type": "string",
                    "description": "What to verify (e.g., 'pipeline passed after retest', 'MR merged', 'pipeline completed after defer')",
                },
            },
            "required": ["check_condition"],
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
                    "enum": ["complicated", "complex", "chaotic"],
                    "description": (
                        "Cynefin domain: complicated (needs expert analysis), "
                        "complex (unknown cause, needs investigation), "
                        "chaotic (sustained saturation, service degraded, act immediately)"
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
