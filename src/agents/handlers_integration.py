# BlackBoard/src/agents/handlers_integration.py
# @ai-rules:
# 1. [Pattern]: Group D "external integration" handlers. I/O-heavy, Brain-state-light.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Gotcha]: notify_user_slack uses _resolve_slack_user (extracted as standalone helper).
"""Group D: 7 external integration tool handlers."""
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

import httpx

from ..models import ConversationTurn

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


# ---------------------------------------------------------------------------
# Helpers (extracted from Brain static/private methods)
# ---------------------------------------------------------------------------
def _resolve_maintainer_enum(event) -> list[str]:
    """Extract valid maintainer emails from event evidence + static config."""
    emails: list[str] = []
    evidence = getattr(getattr(event, "event", None), "evidence", None)
    if evidence:
        gl = getattr(evidence, "gitlab_context", None) or {}
        if isinstance(gl, dict):
            maintainer = gl.get("maintainer", {})
            emails.extend(maintainer.get("emails", []))
    if not emails:
        static = os.getenv("HEADHUNTER_MAINTAINERS", "")
        emails = [e.strip() for e in static.split(",") if e.strip()]
    if event and getattr(event, "slack_user_id", None):
        emails.append(event.slack_user_id)
    seen: set[str] = set()
    return [e for e in emails if e and e not in seen and not seen.add(e)]


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

    subscription_active = False
    state_watcher = ctx.get_state_watcher()
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
                    key = inc.get("key", "?")
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
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["notify_user_slack"] = handle_notify_user_slack
HANDLER_REGISTRY["fetch_jira_issue"] = handle_fetch_jira_issue
HANDLER_REGISTRY["comment_jira_issue"] = handle_comment_jira_issue
HANDLER_REGISTRY["transition_jira_issue"] = handle_transition_jira_issue
HANDLER_REGISTRY["refresh_gitlab_context"] = handle_refresh_gitlab_context
HANDLER_REGISTRY["refresh_kargo_context"] = handle_refresh_kargo_context
HANDLER_REGISTRY["notify_gitlab_result"] = handle_notify_gitlab_result
HANDLER_REGISTRY["search_open_incidents"] = handle_search_open_incidents
