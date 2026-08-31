# BlackBoard/src/agents/handlers_integration.py
# @ai-rules:
# 1. [Pattern]: Group D "external integration" handlers. I/O-heavy, Brain-state-light.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Gotcha]: notify_user_slack uses _resolve_slack_user (extracted as standalone helper).
"""Group D: 12 external integration tool handlers."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING

import httpx

from ..models import ConversationTurn
from ..utils import redact_pii
from ..utils.maintainers import resolve_maintainer_emails

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


# ---------------------------------------------------------------------------
# Helpers (extracted from Brain static/private methods)
# ---------------------------------------------------------------------------
def _resolve_maintainer_enum(event) -> list[str]:
    """Extract valid maintainer emails from event evidence + static config.

    Thin wrapper around the shared resolver in src/utils/maintainers.py -- kept as a
    standalone function (not imported from Brain) per this module's no-Brain-import
    constraint. See that module for source precedence and env-fallback selection.
    """
    return resolve_maintainer_emails(event)


async def _resolve_slack_user(slack_channel, user_email: str, event_doc) -> str | None:
    """Resolve user_email to a Slack user ID with maintainer fallback."""
    if user_email.startswith("U") and user_email.isalnum():
        return user_email

    async def _lookup(email: str) -> str | None:
        try:
            info = await slack_channel._app.client.users_lookupByEmail(email=email)
            return info["user"]["id"]
        except Exception as exc:
            logger.debug("Slack user lookup failed for '%s': %s", email, exc)
            return None

    if "@" in user_email:
        uid = await _lookup(user_email)
        if uid:
            return uid
        logger.warning(
            "notify_user_slack: '%s' not found in Slack, trying maintainer fallback",
            user_email,
        )

    maintainer_emails = _resolve_maintainer_enum(event_doc) if event_doc else []
    for fallback_email in maintainer_emails:
        if "@" not in fallback_email:
            continue
        if fallback_email == user_email:
            continue
        uid = await _lookup(fallback_email)
        if uid:
            logger.info("notify_user_slack: resolved via maintainer fallback '%s'", fallback_email)
            return uid

    if event_doc and event_doc.slack_user_id:
        logger.warning(
            "notify_user_slack: all lookups failed, using event slack_user_id %s",
            event_doc.slack_user_id,
        )
        return event_doc.slack_user_id
    return None


# ---------------------------------------------------------------------------
# notify_user_slack
# ---------------------------------------------------------------------------
async def handle_notify_user_slack(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    user_email = args.get("user_email", "")
    message = args.get("message", "")
    slack_channel = ctx.get_slack_channel()
    bb = ctx.get_blackboard()
    if not slack_channel:
        result_text = "Slack integration not available. Cannot send notification."
        await ctx.emit_pulse(event_id, [("tool:notify_user_slack", "tool", 0.3)])
    elif not user_email or not message:
        result_text = "Missing user_email or message parameter."
        await ctx.emit_pulse(event_id, [("tool:notify_user_slack", "tool", 0.3)])
    else:
        try:
            event_doc = await bb.get_event(event_id)
            slack_user_id = await _resolve_slack_user(slack_channel, user_email, event_doc)
            if not slack_user_id:
                result_text = f"Could not resolve Slack user for '{user_email}'. No valid maintainer found."
                turn = ConversationTurn(
                    turn=(await ctx.next_turn_number(event_id)),
                    actor="brain", action="notify",
                    thoughts=result_text, waitingFor="notify_user_slack",
                    response_parts=response_parts,
                )
                await ctx.append_and_broadcast(event_id, turn)
                await ctx.emit_pulse(event_id, [("tool:notify_user_slack", "tool", 0.0)])
                return True
            dm = await slack_channel._app.client.conversations_open(users=slack_user_id)
            dm_channel = dm["channel"]["id"]
            is_bidirectional = (
                event_doc
                and not event_doc.slack_thread_ts
                and event_doc.source != "chat"
            )
            dashboard_url = os.environ.get("DARWIN_DASHBOARD_URL", "")
            event_link = f"\n<{dashboard_url}/events/{event_id}|View in Darwin Dashboard>" if dashboard_url else ""
            full_dm_text = (
                f":bell: *Darwin Notification*\n\n"
                f"{message}{event_link}\n\n"
                f"_Reply in this thread to follow up on this event._\n\n"
                f"_AI-generated by Darwin Brain. Review for accuracy before acting._"
            )

            logger.info(f"notify_user_slack: user={slack_user_id} dm_channel={dm_channel} event={event_id} bidirectional={is_bidirectional}")

            if is_bidirectional:
                event_context = f"*Event:* {event_doc.event.reason[:200]}\n\n"
                bidir_text = f":bell: *Darwin Notification*\n\n{event_context}{message}{event_link}\n\n_Reply in this thread to follow up on this event._\n\n_AI-generated by Darwin Brain. Review for accuracy before acting._"
                result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=bidir_text)
                msg_ts = result["ts"]
                await bb.set_slack_mapping(dm_channel, msg_ts, event_id)
                await bb.update_event_slack_context(event_id, dm_channel, msg_ts, slack_user_id)
                if event_doc.conversation:
                    from ..channels.formatter import build_event_report_md
                    report_md = build_event_report_md(event_doc)
                    try:
                        await slack_channel._app.client.files_upload_v2(
                            channel=dm_channel,
                            thread_ts=msg_ts,
                            content=report_md,
                            filename=f"{event_id}-report.md",
                            title=f"Event {event_id} -- Conversation Report",
                            initial_comment="Conversation history up to this point:",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to upload conversation report for {event_id}: {e}")
                logger.info(f"Slack notification sent to {user_email} for event {event_id} (thread={msg_ts}, bidirectional)")
                result_text = f"Slack DM sent to {user_email}. They can reply in the thread to interact with this event."

            elif slack_channel._infra_channel:
                if not event_doc.slack_thread_ts:
                    await slack_channel.open_infra_thread(event_doc, event_doc.event.reason)
                    event_doc = await bb.get_event(event_id)

                dm_text = full_dm_text
                if event_doc and event_doc.slack_thread_ts:
                    try:
                        await slack_channel._app.client.chat_postMessage(
                            channel=event_doc.slack_channel_id,
                            thread_ts=event_doc.slack_thread_ts,
                            text=f":bell: *Notification for <@{slack_user_id}>*\n\n{message}",
                        )
                        workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                        ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                        thread_link = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
                        dm_text = (
                            f":bell: *Darwin Notification*\n\n"
                            f"{message[:500]}\n\n"
                            f":point_right: <{thread_link}|Continue in #darwin-infra>\n\n"
                            f"_Reply here or in the thread above to interact with this event._\n\n"
                            f"_AI-generated by Darwin Brain. Review for accuracy before acting._"
                        )
                        logger.info(f"notify_user_slack: posted to infra thread {event_doc.slack_channel_id}/{event_doc.slack_thread_ts}")
                    except Exception as e:
                        logger.warning(f"Infra thread notification failed for {event_id}, DM-only fallback: {e}")

                dm_result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=dm_text)
                await bb.set_slack_mapping(dm_channel, dm_result["ts"], event_id)
                result_text = f"Notification sent to {user_email} (infra thread + DM pointer)." if dm_text != full_dm_text else f"Slack DM sent to {user_email}. They can reply in the thread to follow up."
                logger.info(f"notify_user_slack: DM sent to {user_email} for {event_id}")

            else:
                dm_result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=full_dm_text)
                await bb.set_slack_mapping(dm_channel, dm_result["ts"], event_id)
                logger.info(f"Slack notification sent to {user_email} for event {event_id} (DM-only, no infra channel)")
                result_text = f"Slack DM sent to {user_email}. They can reply in the thread to follow up."
        except Exception as e:
            result_text = f"Failed to send Slack DM to {user_email}: {e}"
            logger.warning(f"Slack notification failed for {user_email}: {e}")
            await ctx.emit_pulse(event_id, [("tool:notify_user_slack", "tool", 0.0)])

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="notify",
        thoughts=result_text,
        waitingFor="notify_user_slack",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# fetch_jira_issue
# ---------------------------------------------------------------------------
async def handle_fetch_jira_issue(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    issue_key = args.get("issue_key", "")
    jira_url = os.getenv("JIRA_URL", "")
    jira_email = os.getenv("JIRA_EMAIL", "")
    jira_token = os.getenv("JIRA_API_TOKEN", "")
    if not jira_url or not jira_token:
        result_text = "Jira not configured (JIRA_URL or JIRA_API_TOKEN missing). Proceeding without Jira context."
    else:
        try:
            import base64
            auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{jira_url}/rest/api/3/issue/{issue_key}",
                    headers={"Authorization": f"Basic {auth}"},
                    params={"fields": "summary,description,status,comment,issuelinks,subtasks,labels,fixVersions"},
                )
            if resp.status_code == 404:
                result_text = f"Jira issue {issue_key} not found."
            elif resp.status_code == 429:
                result_text = "Jira rate limited. Proceeding without additional context."
            elif resp.status_code >= 400:
                result_text = f"Jira fetch failed ({resp.status_code}). Proceeding without context."
            else:
                from .headhunter_jira import format_jira_for_llm
                result_text = format_jira_for_llm(resp.json())
        except Exception as e:
            result_text = f"Jira fetch error: {e}. Proceeding without context."
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="fetch_jira_issue",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# comment_jira_issue
# ---------------------------------------------------------------------------
async def handle_comment_jira_issue(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    issue_key = args.get("issue_key", "")
    comment_text = args.get("comment", "")
    mention_reporter = args.get("mention_reporter", False)
    jira_url = os.getenv("JIRA_URL", "")
    jira_email = os.getenv("JIRA_EMAIL", "")
    jira_token = os.getenv("JIRA_API_TOKEN", "")
    if not jira_url or not jira_token:
        result_text = "Cannot comment on Jira: not configured."
    else:
        try:
            import base64
            from marklassian import markdown_to_adf
            auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
            adf_doc = markdown_to_adf(comment_text)
            if mention_reporter:
                reporter_id = await _get_jira_reporter(issue_key, jira_url, jira_email, jira_token)
                if reporter_id:
                    mention_node = {"type": "paragraph", "content": [
                        {"type": "mention", "attrs": {"id": reporter_id, "text": "@reporter", "accessLevel": ""}},
                        {"type": "text", "text": " "},
                    ]}
                    adf_doc["content"].insert(0, mention_node)
            adf_body = {"body": adf_doc}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{jira_url}/rest/api/3/issue/{issue_key}/comment",
                    headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                    json=adf_body,
                )
            if resp.status_code < 300:
                result_text = f"Comment posted to {issue_key}. Jira communication complete -- proceed with next action."
            else:
                result_text = f"Failed to comment on {issue_key}: {resp.status_code}"
        except Exception as e:
            result_text = f"Jira comment error: {e}"
    logger.info(f"comment_jira_issue: event={event_id} issue={issue_key} result={result_text[:100]}")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="comment_jira_issue",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


async def _get_jira_reporter(issue_key: str, jira_url: str, jira_email: str, jira_token: str) -> str:
    """Fetch the reporter accountId for a Jira issue."""
    try:
        import base64
        auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{jira_url}/rest/api/3/issue/{issue_key}",
                headers={"Authorization": f"Basic {auth}"},
                params={"fields": "reporter"},
            )
        if resp.status_code < 300:
            return resp.json().get("fields", {}).get("reporter", {}).get("accountId", "")
    except Exception as e:
        logger.debug(f"Failed to fetch reporter for {issue_key}: {e}")
    return ""


# ---------------------------------------------------------------------------
# transition_jira_issue
# ---------------------------------------------------------------------------
async def handle_transition_jira_issue(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    issue_key = args.get("issue_key", "")
    target_status = args.get("target_status", "")
    jira_url = os.getenv("JIRA_URL", "")
    jira_email = os.getenv("JIRA_EMAIL", "")
    jira_token = os.getenv("JIRA_API_TOKEN", "")
    if not jira_url or not jira_token:
        result_text = "Cannot transition Jira issue: not configured."
    else:
        try:
            import base64
            auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=15) as client:
                tr_resp = await client.get(
                    f"{jira_url}/rest/api/3/issue/{issue_key}/transitions",
                    headers=headers,
                )
            if tr_resp.status_code >= 400:
                result_text = f"Failed to get transitions for {issue_key}: {tr_resp.status_code}"
            else:
                transitions = tr_resp.json().get("transitions", [])
                match = next(
                    (t for t in transitions if t["name"].lower() == target_status.lower()),
                    None,
                )
                if not match:
                    available = [t["name"] for t in transitions]
                    result_text = f"Transition '{target_status}' not available for {issue_key}. Available: {available}"
                else:
                    async with httpx.AsyncClient(timeout=15) as client:
                        post_resp = await client.post(
                            f"{jira_url}/rest/api/3/issue/{issue_key}/transitions",
                            headers=headers,
                            json={"transition": {"id": match["id"]}},
                        )
                    if post_resp.status_code < 300:
                        result_text = f"{issue_key} transitioned to '{target_status}'. Jira status updated -- proceed with next action."
                    else:
                        result_text = f"Transition failed for {issue_key}: {post_resp.status_code}"
        except Exception as e:
            result_text = f"Jira transition error: {e}"
    logger.info(f"transition_jira_issue: event={event_id} issue={issue_key} target={target_status} result={result_text[:100]}")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="transition_jira_issue",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# refresh_gitlab_context
# ---------------------------------------------------------------------------
async def handle_refresh_gitlab_context(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_check = await bb.get_event(event_id)
    if event_check and event_check.event and event_check.event.evidence:
        if getattr(event_check.event.evidence, "github_context", None):
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence="This event has GitHub context, not GitLab. Use refresh_github_context instead.",
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True

    condition = args.get("check_condition", "")
    headhunter = ctx.get_agent_instance("_headhunter")
    bb = ctx.get_blackboard()
    if not headhunter:
        result_text = "Headhunter not available (GITLAB_HOST not configured). Use select_agent to check MR state manually."
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="refresh_gitlab_context",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    override_project_id = None
    override_mr_iid = None
    mr_url = (args.get("mr_url") or "").strip()
    if mr_url:
        parsed = headhunter.parse_mr_url(mr_url)
        if parsed:
            raw_pid, override_mr_iid = parsed
            override_project_id = await headhunter.resolve_project_id(raw_pid)
            if not override_project_id:
                result_text = f"Could not resolve project from URL: {mr_url}"
                turn = ConversationTurn(
                    turn=(await ctx.next_turn_number(event_id)),
                    actor="brain", action="tool_result",
                    waitingFor="refresh_gitlab_context",
                    evidence=result_text,
                    response_parts=response_parts,
                )
                await ctx.append_and_broadcast(event_id, turn)
                return True
        else:
            result_text = f"Could not parse MR URL: {mr_url}"
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True

    # Pipeline-by-ID path (no MR required) vs. existing MR path -- mutually exclusive.
    state_watcher = ctx.get_state_watcher()
    subscription_active = False
    pipeline_id_arg = args.get("pipeline_id")
    if pipeline_id_arg is not None and not mr_url:
        try:
            pipeline_id_int = int(pipeline_id_arg)
        except (TypeError, ValueError):
            pipeline_id_int = None
        if pipeline_id_int is None or pipeline_id_int <= 0:
            result_text = "pipeline_id must be a positive integer."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        event = await bb.get_event(event_id)
        gl_ctx = (getattr(event.event.evidence, "gitlab_context", None) or {}) if event and event.event and event.event.evidence else {}
        project_id = gl_ctx.get("project_id")
        if not project_id:
            result_text = "No project_id available. Supply mr_url or ensure gitlab_context has project_id."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        # Mirror the MR path's graceful-degradation contract (codereview finding,
        # R1/C4): poll_gitlab_pipeline_status is designed to raise (StateWatcher's
        # subscription loop has its own try/except+backoff), but THIS call site is
        # a direct, synchronous handler invocation with no such wrapper -- an
        # unhandled raise here falls through to _execute_function_call's generic
        # catch-all, losing waitingFor="refresh_gitlab_context" (making the failure
        # invisible to BUDGET_EXHAUSTED's refresh-count tracking) and collapsing a
        # specific GitLab error into a truncated "Internal error executing ..." turn.
        try:
            state = await headhunter.poll_gitlab_pipeline_status(project_id, pipeline_id_int)
        except httpx.HTTPStatusError as e:
            result_text = f"Pipeline ID: {pipeline_id_int}\nError: GitLab returned {e.response.status_code} for this pipeline."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        except httpx.HTTPError as e:
            result_text = f"Pipeline ID: {pipeline_id_int}\nError: GitLab request failed ({type(e).__name__})."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        except ValueError as e:
            # resp.json() raises json.JSONDecodeError (a ValueError subclass) on a
            # 200 with a non-JSON body -- catch it explicitly so it doesn't fall
            # through to _execute_function_call's generic catch-all and lose
            # waitingFor="refresh_gitlab_context".
            result_text = f"Pipeline ID: {pipeline_id_int}\nError: GitLab returned an invalid response ({type(e).__name__})."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        result_text = f"Pipeline Status: {state['pipeline_status']}\nPipeline ID: {pipeline_id_int}"
        if args.get("subscribe") and state_watcher:
            from ..scheduling import SubscriptionSpec, GitLabPipelineRef
            interval = max(15, min(int(args.get("poll_interval", 30)), 300))
            spec = SubscriptionSpec(
                event_id=event_id,
                resource_type="gitlab_pipeline",
                resource_ref=GitLabPipelineRef(project_id=project_id, pipeline_id=pipeline_id_int),
                poll_fn=headhunter.poll_gitlab_pipeline_status,
                interval=interval,
                state_key=headhunter.extract_pipeline_state_key(state),
                registered_at=time.time(),
                cycle_id=ctx.get_cycle_id(event_id),
            )
            subscription_active = state_watcher.register(spec)
            if subscription_active:
                await ctx.broadcast({"type": "subscription_changed", "event_id": event_id, "active": True})
    else:
        state = await headhunter.refresh_mr_state(
            event_id,
            override_project_id=override_project_id,
            override_mr_iid=override_mr_iid,
        )
        mr_state = state.get("mr_state", "unknown")

        if mr_url and override_project_id and override_mr_iid and "error" not in state:
            await bb.update_event_gitlab_context(event_id, {
                "project_id": override_project_id,
                "mr_iid": override_mr_iid,
                "target_url": mr_url,
            })
        if "error" in state:
            from datetime import datetime as _dt
            result_text = (
                f"MR State: {mr_state}\n"
                f"Pipeline: {state.get('pipeline_status', '?')}\n"
                f"Severity: {state.get('severity', '?')}\n"
                f"Error: {state['error']}"
            )
        elif mr_state in ("merged", "closed"):
            from datetime import datetime as _dt
            lines = [
                f"MR State: {mr_state}",
                f"Pipeline: {state['pipeline_status']}",
                f"Pipeline ID: {state.get('pipeline_id') or 'unknown'}",
                f"Severity: {state['severity']}",
            ]
            changed_at = state.get("state_changed_at", "")
            if changed_at:
                try:
                    dt = _dt.fromisoformat(changed_at.replace("Z", "+00:00"))
                    age = int(time.time() - dt.timestamp())
                    m, s = divmod(age, 60)
                    lines.append(f"{mr_state.title()} {m}m {s}s ago")
                except (ValueError, TypeError):
                    pass
            result_text = "\n".join(lines)
        else:
            merge_status = state['merge_status']
            merge_line = f"Merge Readiness: {merge_status}"
            if merge_status == "need_rebase":
                merge_line = "Merge Blocked: needs rebase (new commits on target branch)"
            elif merge_status == "conflict":
                merge_line = "Merge Blocked: merge conflicts (requires human resolution)"
            elif merge_status in ("ci_must_pass", "ci_still_running"):
                merge_line = f"Merge Blocked: {merge_status} (wait for pipeline)"
            elif merge_status == "not_approved":
                merge_line = "Merge Blocked: not approved (requires human approval)"
            result_text = (
                f"MR State: {mr_state}\n"
                f"Pipeline: {state['pipeline_status']}\n"
                f"Pipeline ID: {state.get('pipeline_id') or 'unknown'}\n"
                f"{merge_line}\n"
                f"Severity: {state['severity']}"
            )

        if args.get("subscribe") and state_watcher and "error" not in state:
            event = await bb.get_event(event_id)
            gl_ctx = getattr(event.event.evidence, "gitlab_context", None) if event and event.event and event.event.evidence else None
            if gl_ctx:
                from ..scheduling import SubscriptionSpec, GitLabMrRef
                interval = max(15, min(int(args.get("poll_interval", 30)), 300))
                spec = SubscriptionSpec(
                    event_id=event_id,
                    resource_type="gitlab_mr",
                    resource_ref=GitLabMrRef(
                        project_id=gl_ctx.get("project_id", 0),
                        mr_iid=gl_ctx.get("mr_iid", 0),
                    ),
                    poll_fn=headhunter.poll_gitlab_mr_status,
                    interval=interval,
                    state_key=headhunter.extract_gitlab_state_key(state),
                    registered_at=time.time(),
                    cycle_id=ctx.get_cycle_id(event_id),
                )
                subscription_active = state_watcher.register(spec)
                if subscription_active:
                    await ctx.broadcast({"type": "subscription_changed", "event_id": event_id, "active": True})

    evidence = f"Checking: {condition}\n{result_text}" if condition else result_text
    if args.get("subscribe"):
        evidence += f"\nsubscription_active: {str(subscription_active).lower()}"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        waitingFor="refresh_gitlab_context",
        evidence=evidence,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# refresh_kargo_context
# ---------------------------------------------------------------------------
async def handle_refresh_kargo_context(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    condition = args.get("check_condition", "")
    kargo_observer = ctx.get_agent_instance("_kargo_observer")
    bb = ctx.get_blackboard()
    if not kargo_observer:
        result_text = (
            "Promotion pipeline status is not available in this environment. "
            "Consider checking the ops journal for this service, "
            "or dispatching an agent who has pipeline access."
        )
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="refresh_kargo_context",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    event = await bb.get_event(event_id)
    kc = {}
    if event and event.event and event.event.evidence:
        kc = getattr(event.event.evidence, "kargo_context", None) or {}
    project = (args.get("kargo_project") or "").strip() or kc.get("project", "")
    stage = (args.get("kargo_stage") or "").strip() or kc.get("stage", "")
    if not project or not stage:
        result_text = "Kargo Stage: unknown\nError: No Kargo reference available. Supply kargo_project and kargo_stage, or ensure the event has kargo_context."
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="refresh_kargo_context",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    if (args.get("kargo_project") or args.get("kargo_stage")) and not kc.get("project"):
        await bb.update_event_kargo_context(event_id, {
            "project": project,
            "stage": stage,
        })

    promotion_id = (args.get("promotion_id") or "").strip()
    state = await kargo_observer.get_stage_status(project, stage, promotion_id=promotion_id)
    if "error" in state:
        result_text = (
            f"Kargo Stage: {stage}@{project}\n"
            f"Error: {state['error']}"
        )
    else:
        new_mr_url = state.get("mr_url", "")
        old_mr_url = kc.get("mr_url", "")
        if new_mr_url and new_mr_url != old_mr_url:
            await bb.update_event_kargo_context(event_id, {"mr_url": new_mr_url})
            logger.info(f"Updated kargo_context.mr_url for {event_id}: {new_mr_url}")
        result_text = (
            f"Kargo Stage: {stage}@{project}\n"
            f"Promotion: {state.get('promotion', '?')}\n"
            f"Phase: {state.get('phase', '?')}\n"
            f"Failed Step: {state.get('failed_step', 'N/A')}\n"
            f"Message: {state.get('message', '')}\n"
            f"MR URL: {new_mr_url or 'N/A'}"
        )

    subscription_active = False
    state_watcher = ctx.get_state_watcher()
    if args.get("subscribe") and state_watcher and "error" not in state:
        from ..scheduling import SubscriptionSpec, KargoStageRef
        from ..observers.kargo import KargoObserver as _KO
        interval = max(15, min(int(args.get("poll_interval", 30)), 300))
        promo_status = state.get("_promo_status", {})
        spec = SubscriptionSpec(
            event_id=event_id,
            resource_type="kargo_stage",
            resource_ref=KargoStageRef(project=project, stage=stage),
            poll_fn=kargo_observer.poll_kargo_stage_status,
            interval=interval,
            state_key=_KO.extract_kargo_state_key(promo_status) if promo_status else {
                "phase": state.get("phase", "unknown"),
                "failed_step": state.get("failed_step"),
            },
            registered_at=time.time(),
            cycle_id=ctx.get_cycle_id(event_id),
        )
        subscription_active = state_watcher.register(spec)
        if subscription_active:
            await ctx.broadcast({"type": "subscription_changed", "event_id": event_id, "active": True})

    evidence = f"Checking: {condition}\n{result_text}" if condition else result_text
    if args.get("subscribe"):
        evidence += f"\nsubscription_active: {str(subscription_active).lower()}"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        waitingFor="refresh_kargo_context",
        evidence=evidence,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# notify_gitlab_result
# ---------------------------------------------------------------------------
async def handle_notify_gitlab_result(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    gl_ctx = None
    if event_doc and event_doc.event.evidence:
        ev = event_doc.event.evidence
        gl_ctx = getattr(ev, "gitlab_context", None) if hasattr(ev, "gitlab_context") else None
    if not gl_ctx:
        result_text = "Cannot notify GitLab: no gitlab_context in event evidence. This tool is for headhunter-sourced events only."
        await ctx.emit_pulse(event_id, [("tool:notify_gitlab_result", "tool", 0.3)])
    else:
        project_id = args.get("project_id", gl_ctx.get("project_id"))
        mr_iid = args.get("mr_iid", gl_ctx.get("mr_iid"))
        result_type = args.get("result", "success")
        summary = args.get("summary", "")
        reassign = args.get("reassign_reviewer", False)
        result_text = (
            f"GitLab notification queued: {result_type} on !{mr_iid} (project {project_id}). "
            f"Summary: {summary[:200]}. Reassign reviewer: {reassign}. "
            f"Feedback will be posted by Headhunter feedback loop on event close."
        )
        logger.info(f"notify_gitlab_result: event={event_id} project={project_id} mr=!{mr_iid} result={result_type}")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="notify",
        thoughts=result_text,
        waitingFor="notify_gitlab_result",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# search_open_incidents
# ---------------------------------------------------------------------------
async def handle_search_open_incidents(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    adapter = ctx.get_incident_adapter()
    if not adapter:
        result_text = "Incident tracking not configured."
    else:
        try:
            open_incidents = await adapter.search_open_incidents()
            if not open_incidents:
                result_text = "No open incidents found."
            else:
                lines = [f"Found {len(open_incidents)} open incident(s):\n"]
                for inc in open_incidents[:20]:
                    key = inc.get("issue_key", "?")
                    summary = inc.get("summary", "")
                    status = inc.get("status", "")
                    priority = inc.get("priority", "")
                    lines.append(f"- **{key}** [{status}] (P:{priority}) {summary}")
                result_text = "\n".join(lines)
        except Exception as e:
            result_text = f"Failed to search incidents: {e}"
            logger.warning(f"search_open_incidents failed for {event_id}: {e}")

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=result_text,
        waitingFor="search_open_incidents",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.emit_pulse(event_id, [("tool:search_open_incidents", "tool", 1.0 if "Found" in result_text else 0.3)])
    return True


# ---------------------------------------------------------------------------
# refresh_github_context
# ---------------------------------------------------------------------------
async def handle_refresh_github_context(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_check = await bb.get_event(event_id)
    if event_check and event_check.event and event_check.event.evidence:
        if getattr(event_check.event.evidence, "gitlab_context", None):
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_github_context",
                evidence="This event has GitLab context, not GitHub. Use refresh_gitlab_context instead.",
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True

    condition = args.get("check_condition", "")
    headhunter = ctx.get_agent_instance("_headhunter")
    gh_platform = getattr(headhunter, "_github", None) if headhunter else None
    if not gh_platform:
        result_text = "GitHub integration not available. Use select_agent to check PR state manually."
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="refresh_github_context",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    override_owner = None
    override_repo = None
    override_pr_number = None
    pr_url = (args.get("pr_url") or "").strip()
    if pr_url:
        parsed = gh_platform.parse_pr_url(pr_url)
        if parsed:
            override_owner, override_repo, override_pr_number = parsed
        else:
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_github_context",
                evidence=f"Could not parse PR URL: {pr_url}",
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True

    state = await gh_platform.refresh_pr_state(
        event_id,
        override_owner=override_owner,
        override_repo=override_repo,
        override_pr_number=override_pr_number,
    )

    if pr_url and override_owner and override_pr_number and "error" not in state:
        await bb.update_event_github_context(event_id, {
            "owner": override_owner,
            "repo": override_repo,
            "pr_number": override_pr_number,
            "pr_url": pr_url,
        })

    pr_state = state.get("pr_state", "unknown")
    if "error" in state:
        result_text = (
            f"PR State: {pr_state}\n"
            f"Checks: {state.get('check_status', '?')}\n"
            f"Severity: {state.get('severity', '?')}\n"
            f"Error: {state['error']}"
        )
    elif pr_state in ("closed",):
        result_text = (
            f"PR State: {pr_state}\n"
            f"Checks: {state.get('check_status', '?')}\n"
            f"Severity: {state.get('severity', '?')}"
        )
    else:
        result_text = (
            f"PR State: {pr_state}\n"
            f"Checks: {state['check_status']}\n"
            f"Severity: {state['severity']}"
        )

    subscription_active = False
    state_watcher = ctx.get_state_watcher()
    if args.get("subscribe") and state_watcher and "error" not in state:
        event = await bb.get_event(event_id)
        gh_ctx = getattr(event.event.evidence, "github_context", None) if event and event.event and event.event.evidence else None
        if gh_ctx:
            from ..scheduling import SubscriptionSpec, GitHubPrRef
            interval = max(15, min(int(args.get("poll_interval", 30)), 300))
            owner = gh_ctx.get("owner", "") if isinstance(gh_ctx, dict) else getattr(gh_ctx, "owner", "")
            repo = gh_ctx.get("repo", "") if isinstance(gh_ctx, dict) else getattr(gh_ctx, "repo", "")
            pr_num = gh_ctx.get("pr_number", 0) if isinstance(gh_ctx, dict) else getattr(gh_ctx, "pr_number", 0)
            if owner and repo and pr_num:
                spec = SubscriptionSpec(
                    event_id=event_id,
                    resource_type="github_pr",
                    resource_ref=GitHubPrRef(owner=owner, repo=repo, pr_number=pr_num),
                    poll_fn=gh_platform.poll_github_pr_status,
                    interval=interval,
                    state_key=gh_platform.extract_github_state_key(state),
                    registered_at=time.time(),
                    cycle_id=ctx.get_cycle_id(event_id),
                )
                subscription_active = state_watcher.register(spec)
                if subscription_active:
                    await ctx.broadcast({"type": "subscription_changed", "event_id": event_id, "active": True})

    evidence = f"Checking: {condition}\n{result_text}" if condition else result_text
    if args.get("subscribe"):
        evidence += f"\nsubscription_active: {str(subscription_active).lower()}"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        waitingFor="refresh_github_context",
        evidence=evidence,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# greenwave (pre-closure CI gating validation)
# ---------------------------------------------------------------------------
async def handle_greenwave(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    decision_context = args.get("decision_context", "")
    product_version = args.get("product_version", "")
    subject_identifier = args.get("subject_identifier", "")
    greenwave_url = os.getenv("GREENWAVE_URL", "")
    if not greenwave_url:
        result_text = "GreenWave not configured (GREENWAVE_URL missing). Cannot validate gating decision."
    elif not decision_context or not product_version or not subject_identifier:
        result_text = "Missing required parameters: decision_context, product_version, and subject_identifier are all required."
    else:
        try:
            payload = {
                "decision_context": decision_context,
                "product_version": product_version,
                "subject_type": "koji_build",
                "subject_identifier": subject_identifier,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{greenwave_url}/api/v1.0/decision",
                    json=payload,
                )
            if resp.status_code >= 400:
                result_text = (
                    f"GreenWave returned HTTP {resp.status_code}. "
                    f"Verification could not be completed — retry later or check GreenWave service health."
                )
            else:
                data = resp.json()
                satisfied = data.get("policies_satisfied", False)
                unsatisfied = data.get("unsatisfied_requirements", [])
                if satisfied:
                    result_text = (
                        f"GreenWave: SATISFIED\n"
                        f"Decision context: {decision_context}\n"
                        f"Product version: {product_version}\n"
                        f"Subject: {subject_identifier}\n"
                        f"All gating policies passed."
                    )
                else:
                    req_lines = []
                    for req in unsatisfied[:10]:
                        if isinstance(req, dict):
                            req_lines.append(
                                f"  - {req.get('type', '?')}: {req.get('testcase', req.get('subject_identifier', '?'))}"
                            )
                        else:
                            req_lines.append(f"  - {req}")
                    unsatisfied_text = "\n".join(req_lines) if req_lines else "  (details unavailable)"
                    result_text = (
                        f"GreenWave: NOT SATISFIED\n"
                        f"Decision context: {decision_context}\n"
                        f"Product version: {product_version}\n"
                        f"Subject: {subject_identifier}\n"
                        f"Unsatisfied requirements ({len(unsatisfied)}):\n{unsatisfied_text}"
                    )
        except Exception as e:
            result_text = (
                f"GreenWave request failed: {e}. "
                f"Verification could not be completed — retry later."
            )
            logger.warning("greenwave failed for %s: %s", event_id, e)

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="greenwave",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# ask_release_ai (release-console AI RCA query via SSE)
# ---------------------------------------------------------------------------
_RELEASE_AI_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)

async def handle_ask_release_ai(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    question = args.get("question", "")
    release_ai_url = os.getenv("RELEASE_AI_URL", "")
    release_ai_email = os.getenv("RELEASE_AI_EMAIL", "")
    release_ai_token = os.getenv("RELEASE_AI_BFF_TOKEN", "")
    if not release_ai_url:
        result_text = "Release AI not configured (RELEASE_AI_URL missing). Proceed without RCA context."
    elif not release_ai_email:
        result_text = "Release AI not configured (RELEASE_AI_EMAIL missing). Proceed without RCA context."
    elif not release_ai_token:
        result_text = "Release AI not configured (RELEASE_AI_BFF_TOKEN missing). Proceed without RCA context."
    elif not question:
        result_text = "Missing required parameter: question."
    else:
        try:
            headers = {"X-Forwarded-Email": release_ai_email, "X-BFF-Token": release_ai_token}
            async with httpx.AsyncClient(timeout=_RELEASE_AI_TIMEOUT) as client:
                init_resp = await client.post(
                    f"{release_ai_url}/api/chat/init",
                    json={"persona": "technical", "dataPayload": {}},
                    headers=headers,
                )
            if init_resp.status_code >= 400:
                result_text = (
                    f"Release AI init failed (HTTP {init_resp.status_code}). "
                    f"Proceed without RCA context."
                )
            else:
                session_id = init_resp.json().get("data", {}).get("sessionId", "")
                if not session_id:
                    result_text = "Release AI returned no sessionId. Proceed without RCA context."
                else:
                    accumulated: list[str] = []
                    error_msg = ""
                    async with asyncio.timeout(330):
                        async with httpx.AsyncClient(timeout=_RELEASE_AI_TIMEOUT) as client:
                            async with client.stream(
                                "POST",
                                f"{release_ai_url}/api/chat/stream",
                                json={"sessionId": session_id, "text": question},
                                headers=headers,
                            ) as stream:
                                async for line in stream.aiter_lines():
                                    if not line.startswith("data: "):
                                        continue
                                    raw = line[6:]
                                    try:
                                        chunk = json.loads(raw)
                                    except (ValueError, TypeError):
                                        continue
                                    chunk_type = chunk.get("type", "")
                                    if chunk_type == "text":
                                        accumulated.append(chunk.get("text", ""))
                                    elif chunk_type == "error":
                                        error_msg = chunk.get("error", "Unknown error")
                                        break
                                    elif chunk_type == "done":
                                        break
                    if error_msg:
                        result_text = f"Release AI error: {error_msg}. Proceed without RCA context."
                    elif accumulated:
                        answer = redact_pii("".join(accumulated)[:8000])
                        result_text = f"Release AI response:\n\n{answer}"
                    else:
                        result_text = "Release AI returned an empty response. Proceed without RCA context."
        except Exception as e:
            result_text = (
                f"Release AI unavailable: {e}. Proceed without RCA context."
            )
            logger.warning("ask_release_ai failed for %s: %s", event_id, e)

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="ask_release_ai",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# retrigger_jenkins_build
# ---------------------------------------------------------------------------
_JENKINS_RETRIGGER_COOLDOWN = int(os.getenv("JENKINS_RETRIGGER_COOLDOWN_SECONDS", "21600"))
# Hard wall-clock ceiling for the sequential Jenkins calls in _do_retrigger
# (get_job_run_state + get_build_details + restart_job -- 3 calls now that
# get_build_details skips its console-tail sub-request for this call site),
# distinct from the adapter's per-request timeout (JenkinsAdapter default 15s,
# see JENKINS_TIMEOUT in main.py). Worst case is 3 * 15s = 45s; set comfortably
# above that so a run of legitimately-slow-but-successful calls isn't mistaken
# for a hang.
_JENKINS_RETRIGGER_HANDLER_TIMEOUT = 60

# Wrapper jobs re-run every lane in the CI view, so a wrapper retrigger is far
# costlier than a leaf retrigger. This is a SEPARATE, system-wide (not per-job)
# rate limit on top of the per-job cooldown above -- it caps how often ANY
# wrapper job can be retriggered, regardless of which one, since two different
# wrappers retriggered back-to-back are just as costly as the same one twice.
_JENKINS_WRAPPER_RETRIGGER_COOLDOWN = int(
    os.getenv("JENKINS_WRAPPER_RETRIGGER_COOLDOWN_SECONDS", str(_JENKINS_RETRIGGER_COOLDOWN))
)
_JENKINS_WRAPPER_RETRIGGER_LOCK_KEY = "darwin:jenkins:retrigger:wrapper:global"

# Marker appended to a cooldown key's stored value when the cooldown was kept
# because the job was OBSERVED already building/queued, not because Darwin
# actually POSTed a retrigger. Lets a later blocked caller get an accurate
# message instead of being told the job "was already retriggered" when no
# retrigger ever happened.
_NOOP_COOLDOWN_MARKER = ":observed-running"


async def handle_retrigger_jenkins_build(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    """Retrigger a Jenkins job scoped to this event's failed_jobs, with per-job rate cap."""
    job_name = (args.get("job_name") or "").strip()
    bb = ctx.get_blackboard()

    if not job_name:
        result_text = "Missing required parameter: job_name."
    else:
        event_doc = await bb.get_event(event_id)
        ci_context = None
        if event_doc and event_doc.event and event_doc.event.evidence:
            ci_context = getattr(event_doc.event.evidence, "ci_context", None)

        if not ci_context:
            result_text = f"No CI context on event {event_id}. Cannot scope retrigger."
        else:
            failed_jobs = ci_context.get("failed_jobs", [])
            matched = next(
                (j for j in failed_jobs if j.get("job_name") == job_name), None
            )
            if not matched:
                available = [j.get("job_name", "?") for j in failed_jobs[:10]]
                result_text = (
                    f"Job '{job_name}' is not in this event's failed_jobs. "
                    f"Available: {available}. Retrigger rejected (scope check)."
                )
            else:
                cooldown_key = f"darwin:jenkins:retrigger:{job_name}"
                acquired = await bb.redis.set(
                    cooldown_key, event_id, nx=True, ex=_JENKINS_RETRIGGER_COOLDOWN
                )
                if not acquired:
                    holder_event = await bb.redis.get(cooldown_key)
                    if holder_event and holder_event.endswith(_NOOP_COOLDOWN_MARKER):
                        origin_event = holder_event[: -len(_NOOP_COOLDOWN_MARKER)]
                        result_text = (
                            f"Job '{job_name}' is already running or queued (observed "
                            f"by event {origin_event}; Darwin did not retrigger it). "
                            f"Cooldown stays active until it finishes or the window "
                            f"({_JENKINS_RETRIGGER_COOLDOWN}s) expires."
                        )
                    elif holder_event and holder_event != event_id:
                        result_text = (
                            f"Job '{job_name}' was already retriggered within the "
                            f"cooldown window ({_JENKINS_RETRIGGER_COOLDOWN}s) by a "
                            f"different event ({holder_event}). This may be an "
                            f"unrelated new failure being suppressed by the rate "
                            f"cap, not abuse -- investigate directly in Jenkins if "
                            f"this failure looks distinct from the earlier one."
                        )
                    else:
                        result_text = (
                            f"Job '{job_name}' was already retriggered within the "
                            f"cooldown window ({_JENKINS_RETRIGGER_COOLDOWN}s). "
                            f"Wait for cooldown to expire before retrying."
                        )
                else:
                    result_text = await _do_retrigger(
                        ctx, bb, event_id, job_name, matched, cooldown_key
                    )

    logger.info("retrigger_jenkins_build: event=%s job=%s result=%s", event_id, job_name, result_text[:120])
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="retrigger_jenkins_build",
        thoughts=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


async def _alert_wrapper_retrigger(ctx: ToolContext, event_id: str, job_name: str, build_number: int) -> None:
    """Best-effort structured alert for an actual wrapper-job retrigger (all lanes re-run).

    Always emits a structured log line -- observable via log-based monitoring even
    with no Slack configured. The Slack post is best-effort on top of that: a
    Slack outage must never affect the retrigger's own result, so failures here
    are swallowed after logging.
    """
    logger.warning(
        "JENKINS_WRAPPER_RETRIGGER: event=%s job=%s build=%s -- all lanes will re-run",
        event_id, job_name, build_number,
    )
    slack_channel = ctx.get_slack_channel()
    infra_channel = getattr(slack_channel, "_infra_channel", None)
    if not slack_channel or not infra_channel:
        return
    try:
        await slack_channel._app.client.chat_postMessage(
            channel=infra_channel,
            text=(
                f":rotating_light: *Wrapper job retriggered*: `{job_name}` #{build_number} "
                f"(event `{event_id}`) — all lanes will re-run."
            ),
        )
    except Exception as exc:
        logger.warning("Wrapper-retrigger Slack alert failed for %s: %s", job_name, exc)


async def _do_retrigger(
    ctx: ToolContext, bb, event_id: str, job_name: str, matched: dict, cooldown_key: str,
) -> str:
    """Execute the retrigger after scope + rate checks pass. Releases cooldown key on failure."""
    observer = ctx.get_agent_instance("_jenkins_observer")
    adapter = getattr(observer, "_adapter", None) if observer else None

    success = False
    wrapper_gate_owned = False
    # True only once an actual wrapper retrigger POST has succeeded -- distinct
    # from `success`, which is also set True on the no-op "observed already
    # running/queued" path to keep the per-job cooldown tagged. The wrapper
    # global lock must NOT be held for the no-op path; only `success` would
    # falsely keep it locked for the full cooldown with nothing to show for it.
    wrapper_retrigger_posted = False
    try:
        if not adapter or not adapter.enabled():
            reason = "circuit breaker open" if (adapter and adapter.breaker_open) else "not configured"
            return f"Jenkins adapter {reason}. Retrigger skipped. Escalate to maintainer."

        build_number = matched.get("build_number")
        if not build_number:
            return f"No build_number for '{job_name}' — cannot fetch fresh parameters. Escalate to maintainer."

        job_metadata = matched.get("job_metadata") or {}
        is_wrapper = job_metadata.get("type") == "wrapper"

        if is_wrapper:
            # Wrapper-specific hard gate (HIGH fix): distinct from, and in addition
            # to, the per-job cooldown above. Re-running a wrapper is costly
            # regardless of which wrapper job it is, so this is a single
            # system-wide lock rather than scoped to job_name.
            wrapper_gate_owned = await bb.redis.set(
                _JENKINS_WRAPPER_RETRIGGER_LOCK_KEY,
                job_name,
                nx=True,
                ex=_JENKINS_WRAPPER_RETRIGGER_COOLDOWN,
            )
            if not wrapper_gate_owned:
                holder = await bb.redis.get(_JENKINS_WRAPPER_RETRIGGER_LOCK_KEY)
                return (
                    f"Wrapper job '{job_name}' retrigger blocked: wrapper retriggers "
                    f"re-run every lane and are rate-limited system-wide "
                    f"({_JENKINS_WRAPPER_RETRIGGER_COOLDOWN}s), independent of the "
                    f"per-job cooldown. '{holder}' was retriggered within that "
                    f"window. Escalate to maintainer if this is urgent."
                )

        async with asyncio.timeout(_JENKINS_RETRIGGER_HANDLER_TIMEOUT):
            run_state = await adapter.get_job_run_state(job_name)
            if run_state is None:
                return (
                    f"Could not fetch job run state for '{job_name}'. "
                    f"Jenkins may be unreachable. Escalate to maintainer."
                )
            if run_state.building or run_state.in_queue:
                success = True
                try:
                    # Tag the cooldown value so a later blocked caller can tell
                    # "job was observed already running" apart from "Darwin
                    # actually retriggered it" (MEDIUM fix -- see
                    # _NOOP_COOLDOWN_MARKER).
                    await bb.redis.set(
                        cooldown_key, f"{event_id}{_NOOP_COOLDOWN_MARKER}",
                        xx=True, keepttl=True,
                    )
                except Exception as redis_exc:
                    logger.error("Failed to tag cooldown key %s as observed-running: %s", cooldown_key, redis_exc)
                state_bits: list[str] = []
                if run_state.building:
                    state_bits.append("already running")
                if run_state.in_queue:
                    state_bits.append("already queued")
                state_text = " and ".join(state_bits)
                last_build_suffix = ""
                if run_state.last_build_number is not None:
                    last_build_suffix = f" Last build: #{run_state.last_build_number}."
                return (
                    f"Job '{job_name}' is {state_text}; retrigger skipped. "
                    f"Defer until the current run finishes. Cooldown remains in place."
                    f"{last_build_suffix}"
                )

            # get_build_details requires a separate network call to fetch fresh
            # parameters (avoiding a repost of redacted ci_context values).
            # include_console_tail=False skips its second (console-log) HTTP call
            # since only `.parameters` is used here -- keeps this handler to 3
            # sequential Jenkins calls instead of 4 (see _JENKINS_RETRIGGER_HANDLER_TIMEOUT).
            fresh_details = await adapter.get_build_details(
                job_name, build_number, include_console_tail=False,
            )
            if not fresh_details:
                return (
                    f"Could not fetch build details for {job_name} #{build_number}. "
                    f"Jenkins may be unreachable. Escalate to maintainer."
                )

            success = await adapter.restart_job(job_name, fresh_details.parameters)
            if is_wrapper:
                wrapper_retrigger_posted = success
        if not success:
            return f"Retrigger failed for '{job_name}'. Jenkins rejected the request — check credentials/permissions."

        if is_wrapper:
            await _alert_wrapper_retrigger(ctx, event_id, job_name, build_number)
        suffix = " (wrapper job — all lanes will re-run)" if is_wrapper else ""
        return (
            f"Successfully retriggered '{job_name}' #{build_number}. "
            f"Monitor for new build result.{suffix}"
        )
    except TimeoutError:
        logger.error("Timed out retriggering %s after %ds", job_name, _JENKINS_RETRIGGER_HANDLER_TIMEOUT)
        return f"Retrigger for '{job_name}' timed out after {_JENKINS_RETRIGGER_HANDLER_TIMEOUT}s. Escalate to maintainer."
    except Exception as e:
        logger.error("Error in _do_retrigger for %s: %s", job_name, e)
        return f"Internal error during retrigger for '{job_name}'. Escalate to maintainer."
    finally:
        if not success:
            try:
                await bb.redis.delete(cooldown_key)
            except Exception as redis_exc:
                logger.error("Failed to release cooldown key %s: %s", cooldown_key, redis_exc)
        # Release the wrapper lock whenever we own it and no wrapper retrigger
        # was actually posted -- covers the no-op "observed already running"
        # path (where `success` is True but nothing was retriggered) as well
        # as every failure/exception path, not just `not success`.
        if wrapper_gate_owned and not wrapper_retrigger_posted:
            try:
                await bb.redis.delete(_JENKINS_WRAPPER_RETRIGGER_LOCK_KEY)
            except Exception as redis_exc:
                logger.error("Failed to release wrapper cooldown key: %s", redis_exc)


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["notify_user_slack"] = handle_notify_user_slack
HANDLER_REGISTRY["fetch_jira_issue"] = handle_fetch_jira_issue
HANDLER_REGISTRY["comment_jira_issue"] = handle_comment_jira_issue
HANDLER_REGISTRY["transition_jira_issue"] = handle_transition_jira_issue
HANDLER_REGISTRY["refresh_gitlab_context"] = handle_refresh_gitlab_context
HANDLER_REGISTRY["refresh_kargo_context"] = handle_refresh_kargo_context
HANDLER_REGISTRY["refresh_github_context"] = handle_refresh_github_context
HANDLER_REGISTRY["notify_gitlab_result"] = handle_notify_gitlab_result
HANDLER_REGISTRY["search_open_incidents"] = handle_search_open_incidents
HANDLER_REGISTRY["greenwave"] = handle_greenwave
HANDLER_REGISTRY["ask_release_ai"] = handle_ask_release_ai
HANDLER_REGISTRY["retrigger_jenkins_build"] = handle_retrigger_jenkins_build
