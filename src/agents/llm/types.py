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
    grounding_metadata: Optional[dict] = None  # Google Search grounding (queries + source chunks)


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
        tool_choice: dict | None = None,
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
        tool_choice: dict | None = None,
    ) -> AsyncIterator[LLMChunk]: ...


# =============================================================================
# Smartsheet column options (populated at boot via set_smartsheet_options)
# =============================================================================
# Empty defaults -- populated from Smartsheet column schema at startup.
# When empty, validation is skipped (graceful degradation).

VALID_PLATFORMS: list[str] = []
VALID_STATUSES: list[str] = []
VALID_PRIORITIES: list[str] = []
VALID_ISSUE_TYPES: list[str] = []
VALID_COMPONENTS: list[str] = []
VALID_LABELS: list[str] = []


# =============================================================================
# Brain Tool Schemas (plain dicts, provider-agnostic)
# =============================================================================
# Phase-gated by brain.py. Skills in brain_skills/ are the canonical behavioral docs.
# Each adapter converts these to its SDK's native format.

BRAIN_TOOL_SCHEMAS: list[dict] = [
    # --- Lookup tools (check BEFORE routing) ---
    {
        "name": "lookup_service",
        "description": (
            "Look up a monitored K8s deployment's GitOps metadata. Returns repo URL, helm path, "
            "version, replicas, and current metrics. Only returns results for services discovered "
            "via K8s annotations (darwin.io/monitored). For Kargo promotions, GitLab MR context, "
            "or Jira issues, the structured evidence is already in the event prompt."
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
    # --- Phase declaration (controls tool availability per workflow stage) ---
    {
        "name": "set_phase",
        "description": (
            "Declare your current processing phase. Tools are gated to the "
            "phase you declare -- e.g., report_incident requires escalate phase. "
            "Call once when transitioning to a new phase. Re-declaring the "
            "same phase is a no-op -- only transitions change the tool set. "
            "The phase is recorded on the blackboard as a visible turn. "
            "System states (agent working, waiting for user) are handled "
            "automatically -- you do not declare those."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "enum": [
                        "triage", "dispatch", "verify", "escalate", "close",
                        "investigate", "execute",
                    ],
                    "description": (
                        "triage: assess event, classify domain, check initial state. "
                        "Gate: entry phase for all events. "
                        "dispatch: agents investigate and execute. All agent routing, "
                        "Jira tools, and search grounding available. "
                        "Gate: enter when domain is COMPLICATED or COMPLEX. "
                        "CLEAR events skip dispatch -- route sysAdmin directly from triage. "
                        "verify: refresh state and check results after agent work or defer wake. "
                        "Gate: enter after every async boundary (agent return, defer wake). "
                        "This is the only checkpoint before a human is disturbed. "
                        "escalate: issue needs human awareness. "
                        "Gate: enter only after verify confirms the issue persists. "
                        "For CHAOTIC events, enter immediately from triage -- act first. "
                        "close: wrap up. Enter ONLY after you have replied to the user. "
                        "Gate: terminal phase. Reopen requires a new event. "
                        "investigate: legacy alias for dispatch (auto-resolved). "
                        "execute: legacy alias for dispatch (auto-resolved)."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are entering this phase (one sentence).",
                },
            },
            "required": ["phase", "reasoning"],
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
                    "enum": ["architect", "sysadmin", "developer", "qe", "security_analyst"],
                    "description": (
                        "Which agent to route to. "
                        "security_analyst: vulnerability scanning, CVE remediation assessment, "
                        "dependency audit, container image analysis, RBAC review, supply chain security. "
                        "Ephemeral only -- always spawns an on-call pod."
                    ),
                },
                "task_instruction": {
                    "type": "string",
                    "description": (
                        "What the agent should do. For investigate mode: include specific "
                        "questions the agent must answer (e.g., 'What error appears in the "
                        "failing build log?' not 'Check pipeline status'). "
                        "For all modes: be specific and actionable."
                    ),
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
        "description": (
            "Close the event as resolved. "
            "For user-initiated events (chat, slack): you MUST have sent a visible reply "
            "to the user before calling this. The close summary is an internal record -- "
            "the user needs YOUR response in the conversation, not just a closure notification. "
            "For automated events (headhunter, aligner, timekeeper): close directly after verification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Summary of what was done and the outcome. "
                        "Start with the event identifier: '[evt-XXXXXXX] summary text'. "
                        "Include the root cause or resolution, not just 'closed' or 'resolved'."
                    ),
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "request_user_approval",
        "description": "Pause and ask a human to authorize an action. Use for structural changes, fix proposals, or any action requiring human approval. This is the ONLY tool that can pause automated events for human input.",
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
                    "enum": ["architect", "sysadmin", "developer", "qe", "security_analyst"],
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
        "description": (
            "Schedule the next feedback sample for this event. Use when the "
            "domain strategy calls for observation at a calibrated interval "
            "(Ts). You will be woken after delay_seconds to measure the "
            "process variable and decide the next action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why this sampling interval was chosen (e.g., 'pipeline typically completes in 20min, sampling at Ts=15min')",
                },
                "delay_seconds": {
                    "type": "integer",
                    "description": "Sampling interval Ts in seconds (30-3600). Calibrate from deep memory baseline, severity multiplier, and progress signals.",
                },
            },
            "required": ["reason", "delay_seconds"],
        },
    },
    {
        "name": "wait_for_user",
        "description": (
            "Pause processing until the user responds. "
            "ONLY available for chat and slack events. "
            "Use ONLY when waiting for the user's decision or confirmation. "
            "NOT for automated events -- use request_user_approval instead."
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
                    "description": "Email address of the Slack user to notify. Use the maintainer email from evidence.gitlab_context.maintainer.emails when available.",
                },
                "message": {
                    "type": "string",
                    "description": (
                        "The notification message. Include the event identifier "
                        "(e.g., '[evt-XXXXXXX]') and the MR/PR URL when available. "
                        "For failures: include the specific error or root cause, not just 'pipeline failed'."
                    ),
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
                    "description": "Role name of the agent to reply to: 'developer', 'qe', 'sysadmin', 'architect', or 'security_analyst'. The system resolves this to the active agent working on the current event.",
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
            "'architect', or 'security_analyst'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Role name of the agent to message: 'developer', 'qe', 'sysadmin', 'architect', or 'security_analyst'. The system resolves this to the correct agent connection.",
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
                "summary": {
                    "type": "string",
                    "description": (
                        "MR comment summarizing what Darwin did. "
                        "Include the event identifier (e.g., '[evt-XXXXXXX]'). "
                        "For failures: include the specific error from investigation, not just 'pipeline failed'."
                    ),
                },
                "reassign_reviewer": {
                    "type": "boolean",
                    "description": "If true, re-tag the maintainer as MR reviewer (use on failure/escalation)",
                },
            },
            "required": ["project_id", "mr_iid", "result", "summary"],
        },
    },
    {
        "name": "fetch_jira_issue",
        "description": (
            "Retrieve the current state of a Jira issue -- description, comments, linked PRs, "
            "child issues, status, and priority. Returns structured content that can supplement "
            "the evidence snapshot taken at event creation time. Available for events with "
            "jira_context in evidence. Graceful degradation: proceed without if unavailable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue identifier from evidence.jira_context.issue_key",
                },
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "comment_jira_issue",
        "description": (
            "Post a progress update or final report to the Jira issue. The comment renders as "
            "structured content (headings, tables, code blocks, bold). For Jira-sourced events, "
            "the issue is the primary communication channel with the human who approved the plan. "
            "Mention the reporter when delivering final results so they receive a notification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue identifier from evidence.jira_context.issue_key",
                },
                "comment": {
                    "type": "string",
                    "description": "Markdown-formatted comment body (headings, lists, tables, code blocks supported)",
                },
                "mention_reporter": {
                    "type": "boolean",
                    "description": "Tag the issue reporter with an @mention so they receive a Jira notification",
                },
            },
            "required": ["issue_key", "comment"],
        },
    },
    {
        "name": "transition_jira_issue",
        "description": (
            "Move a Jira issue to a new workflow status. The issue status should reflect the "
            "event's execution state -- the Jira board becomes a live view of Darwin's progress. "
            "Returns available transitions if the requested status is not reachable from the "
            "current state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue identifier from evidence.jira_context.issue_key",
                },
                "target_status": {
                    "type": "string",
                    "description": "Workflow status name to transition to (e.g., In Progress, Dev Complete)",
                },
            },
            "required": ["issue_key", "target_status"],
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
                                "enum": ["architect", "sysadmin", "developer", "qe", "security_analyst"],
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
        "name": "report_incident",
        "description": (
            "Report an incident to the tracking system. When Nightwatcher is enabled, "
            "this stages the escalation for consolidated batch processing. When disabled, "
            "it writes directly to the incident tracking sheet. "
            "Use when an automated event (headhunter, timekeeper) results in a persistent "
            "failure requiring team investigation. Systemic fields (reporter, "
            "date, status, labels, issue type, components) are auto-populated. You only "
            "provide event-specific details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": VALID_PLATFORMS,
                    "description": "Affected platform (infer from event evidence)",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "One-line incident summary. Format: '[evt-XXXXXXX] summary'. "
                        "Must describe the specific failure, not just 'pipeline failed'."
                    ),
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Detailed description: event_id, what failed (specific error), "
                        "timeline, actions taken, evidence from agent investigation. "
                        "Include log excerpts or error messages when available."
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": VALID_PRIORITIES,
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
    {
        "name": "refresh_kargo_context",
        "description": (
            "Re-read current Kargo Stage promotion state without dispatching an agent. "
            "Returns promotion phase, failed step, and error message. Use after dispatching "
            "sysadmin to retry a promotion, or after deferring to check if a new promotion "
            "succeeded. Only available for events with kargo_context in evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "check_condition": {
                    "type": "string",
                    "description": "What to verify (e.g., 'promotion succeeded after retry', 'new promotion running')",
                },
            },
            "required": ["check_condition"],
        },
    },
    # --- JARVIS response (gated: when unanswered jarvis.message or jarvis.insight exists) ---
    {
        "name": "respond_to_jarvis",
        "description": (
            "Send a message to JARVIS. JARVIS ONLY sees what you send "
            "through this tool -- thinking and conversation turns do NOT reach JARVIS. "
            "Use for: (1) responding to a JARVIS advisory/nudge, "
            "(2) sharing your system review assessment on jarvis-sourced events. "
            "Always end with a question to keep the analytical exchange alive."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "minLength": 20,
                    "description": (
                        "Your substantive response to JARVIS (minimum 20 characters). "
                        "Structure: (1) what you observed, (2) agree or disagree and why, "
                        "(3) your next action, (4) end with a question for JARVIS. "
                        "The question keeps the analytical exchange alive."
                    ),
                },
            },
            "required": ["response"],
        },
    },
    # --- JARVIS wait (gated: jarvis-sourced events, after respond_to_jarvis) ---
    {
        "name": "wait_for_jarvis",
        "description": (
            "Wait for JARVIS to respond to your assessment. Sends periodic nudges "
            "if no response arrives. Auto-resolves after ~90s if JARVIS does not respond. "
            "Use after respond_to_jarvis to give JARVIS time to process and reply. "
            "Only one wait per event at a time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Brief note on what you sent JARVIS (for the wait turn log)",
                },
            },
            "required": ["context"],
        },
    },
    # --- inspect_event (gated: jarvis-sourced meta-events only) ---
    {
        "name": "inspect_event",
        "description": (
            "Read your own action history on another event. "
            "Use when JARVIS references a specific event and you need to understand "
            "what you did there -- your triage decisions, agent routing, phase transitions, "
            "and reasoning. Read-only: you cannot modify the inspected event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The event ID to inspect (e.g. evt-abc12345)",
                },
            },
            "required": ["event_id"],
        },
    },
    # --- post_sticky_note (gated: jarvis-sourced + close phase only) ---
    {
        "name": "post_sticky_note",
        "description": (
            "Write a note on another event's blackboard. You have a budget of 2 notes "
            "per target event -- consolidate your insights into comprehensive notes "
            "rather than many small ones. The note appears when you next process that event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "Target event ID to attach the note to (e.g., evt-abc12345)",
                },
                "content": {
                    "type": "string",
                    "description": "The note content — insight, reminder, or context for your future self",
                },
            },
            "required": ["event_id", "content"],
        },
    },
    # --- read_sticky_notes (gated: unread_notes > 0) ---
    {
        "name": "read_sticky_notes",
        "description": (
            "Read unread sticky notes on this event. "
            "Returns all notes with timestamps and marks them as read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "Event ID to read notes from (typically the current event)",
                },
            },
            "required": ["event_id"],
        },
    },
    # --- hold_watch (gated: jarvis-sourced + close phase only) ---
    {
        "name": "hold_watch",
        "description": (
            "Park with zero token cost while keeping this meta-event alive. The system "
            "wakes you when an event enters the deferred state (new idle member to observe) "
            "or when JARVIS sends a new message. Use in the close phase of jarvis-sourced "
            "events when you want to keep observing the deferred pool. Upon waking, assess "
            "the new context, respond, then hold_watch again. If nothing remains to observe, "
            "use close_event instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Brief note on what you observed before parking (for the wake turn log)",
                },
            },
            "required": ["context"],
        },
    },
    # --- Observation tools (gated: NOT available in close phase) ---
    {
        "name": "record_observation",
        "description": (
            "Record a numeric observation. Every quantifiable signal you encounter "
            "is worth recording -- error counts, durations, queue depths, retry "
            "attempts, replica counts, pipeline wait times. Numbers are evidence; "
            "text is opinion. Call this often. The series you build is your "
            "institutional memory and the operator's shared evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Short, consistent series name (e.g. 'error_count', 'p99_latency_ms', "
                        "'replica_count'). Reuse existing names when recording the same metric."
                    ),
                },
                "value": {
                    "type": "number",
                    "description": "The numeric value to record",
                },
                "unit": {
                    "type": "string",
                    "description": "Optional unit label (e.g. 'ms', '%', 'count', 'replicas')",
                },
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "list_observations",
        "description": (
            "Review all observations recorded across all events in the last 7 days. "
            "Returns each series with temporal stats (count, min, max, trend, span) "
            "and event provenance (event_id, service per point). "
            "Use before decisions to ground your reasoning in measured history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
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


# =============================================================================
# Nightwatcher Tool Schemas (shift consolidation agent)
# =============================================================================
# Phase-gated: tool descriptions indicate which phase(s) they are available in.
# The Nightwatcher's get_phase_tools() filters by current_phase at runtime.

NIGHTWATCHER_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "set_phase",
        "description": (
            "Transition between workflow phases. Phases are sequential: "
            "review -> investigate -> report. You cannot skip phases or go backwards. "
            "Call once when you are ready to move to the next phase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "enum": ["review", "investigate", "report"],
                    "description": (
                        "review: read event reports, journals, and deep memory to understand the shift. "
                        "investigate: dispatch on-call agents for live data on unresolved issues. "
                        "report: write consolidated incidents to the tracking sheet and post the shift summary."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are entering this phase (one sentence).",
                },
            },
            "required": ["phase", "reasoning"],
        },
    },
    {
        "name": "get_event_report",
        "description": (
            "(review, investigate) Read the full closed event report for a specific event. "
            "Returns the complete markdown conversation history with agent actions, "
            "plans, and outcomes. Use to understand WHAT happened, not just the manifest summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "Event ID from the manifest (e.g., evt-09ef9c7c)",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "search_journal",
        "description": (
            "(review, investigate) Read recent ops journal entries for a service. "
            "Returns timestamped entries showing recent event closures, anomaly "
            "patterns, and operational history. Use to detect oscillation patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service name to look up in the ops journal",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "consult_deep_memory",
        "description": (
            "(review, investigate) Search vectorized operational history for similar "
            "past events. Returns scored matches with symptom, root_cause, fix_action, "
            "and recurrence count. Use to determine if a root cause is recurring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Semantic search query describing the pattern (e.g., 's390x host pool exhaustion')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "dispatch_investigation",
        "description": (
            "(investigate only) Send an on-call sysadmin agent to check live cluster "
            "state for a service. The investigation uses a fixed template -- you only "
            "provide the service name. The agent reports pipeline health, current errors, "
            "and whether manual intervention is needed. "
            "The service must be in the manifest. Maximum 3 dispatches per sweep."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service name from the manifest to investigate",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "write_incident",
        "description": (
            "Write a consolidated incident report to the tracking sheet. "
            "Platform and affected events are pre-filled from your cluster plan. "
            "Provide your analysis: summary, root cause description, priority, and status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One-line consolidated root cause summary (max 200 chars)",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Full consolidated description including: root cause, "
                        "affected services list, timeline, investigation findings if any"
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": VALID_PRIORITIES,
                    "description": "Critical if deep_memory shows 3+ recurrences in 14 days or active crisis",
                },
                "status": {
                    "type": "string",
                    "enum": VALID_STATUSES,
                    "description": "New if still active at sweep time, Closed if probes confirmed recovery",
                },
            },
            "required": ["summary", "description", "priority"],
        },
    },
    {
        "name": "post_shift_summary",
        "description": (
            "Post the end-of-shift summary to the Slack infra channel. "
            "Include total escalations, incident count, noise reduction percentage, "
            "and critical findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "The shift report text for Slack notification",
                },
            },
            "required": ["summary"],
        },
    },
]


_COLUMN_MAP = {
    "Platform": VALID_PLATFORMS,
    "Status": VALID_STATUSES,
    "Priority": VALID_PRIORITIES,
    "Issue Type": VALID_ISSUE_TYPES,
    "Components": VALID_COMPONENTS,
    "Labels": VALID_LABELS,
}

_SCHEMA_FIELD_MAP = {
    "platform": VALID_PLATFORMS,
    "status": VALID_STATUSES,
    "priority": VALID_PRIORITIES,
}


def set_smartsheet_options(column_options: dict[str, list[str]]) -> None:
    """Populate all Smartsheet column option lists from column schema at boot.

    Also patches enum fields in BRAIN_TOOL_SCHEMAS and
    NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA so LLM tool declarations
    reflect the live Smartsheet values.
    """
    import logging
    log = logging.getLogger(__name__)
    for col_title, target_list in _COLUMN_MAP.items():
        opts = column_options.get(col_title, [])
        if opts:
            target_list.clear()
            target_list.extend(opts)
            log.info("Smartsheet %s: %d options loaded", col_title, len(opts))
    for schema_list in (BRAIN_TOOL_SCHEMAS, NIGHTWATCHER_TOOL_SCHEMAS, NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA):
        for tool in schema_list:
            _patch_enum_fields(tool.get("input_schema", {}))


def _patch_enum_fields(schema: dict) -> None:
    """Recursively find enum fields in a JSON schema and patch from live Smartsheet values.

    When the live list is populated, sets the enum. When empty, removes the
    enum key so the LLM sees an unconstrained string (avoids empty enum arrays
    which may be rejected by the provider).
    """
    props = schema.get("properties", {})
    for key, prop in props.items():
        if key in _SCHEMA_FIELD_MAP:
            live = _SCHEMA_FIELD_MAP[key]
            if live:
                prop["enum"] = list(live)
            elif "enum" in prop and not prop["enum"]:
                del prop["enum"]
        if prop.get("type") == "array" and "items" in prop:
            _patch_enum_fields(prop["items"])
        if prop.get("type") == "object":
            _patch_enum_fields(prop)


# =============================================================================
# Nightwatcher Declare-Clusters Schema (cart declaration step)
# =============================================================================
# Used ONLY in the shopping cart's cluster declaration phase.
# Code validates full manifest coverage before proceeding to write_incident calls.

NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA: list[dict] = [
    {
        "name": "declare_clusters",
        "description": (
            "Declare your incident clusters. Each cluster groups events that share "
            "a root cause. Every event in the manifest must be assigned to exactly "
            "one cluster. Code validates coverage before any writes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "clusters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "events": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Event IDs from the manifest that share this root cause",
                            },
                            "root_cause": {
                                "type": "string",
                                "description": "One-line root cause summary for this cluster",
                            },
                            "platform": {
                                "type": "string",
                                "enum": VALID_PLATFORMS,
                                "description": "Affected platform for this cluster",
                            },
                            "services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Affected service names in this cluster",
                            },
                        },
                        "required": ["events", "root_cause", "platform", "services"],
                    },
                    "description": "List of incident clusters covering all manifest events",
                },
            },
            "required": ["clusters"],
        },
    },
]

# Strip empty enum arrays from initial schema state (before set_smartsheet_options runs)
for _schema_list in (BRAIN_TOOL_SCHEMAS, NIGHTWATCHER_TOOL_SCHEMAS, NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA):
    for _tool in _schema_list:
        _patch_enum_fields(_tool.get("input_schema", {}))
