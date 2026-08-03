# BlackBoard/src/agents/handlers_lookup.py
# @ai-rules:
# 1. [Pattern]: Lookup/query handlers (service, deep memory, journal). Read-heavy, no state mutation.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Gotcha]: consult_deep_memory cached guard uses string matching coupled to Archivist response text.
# 6. [Pattern]: consult_deep_memory scopes search_knowledge() via service_filter=svc or event.service --
#    explicit tool-call `service` arg wins, falling back to the event's own service.
# 7. [Pattern]: consult_deep_memory uses fetch-all then asyncio.gather(rerank x3) then format-all.
#    Reranking is per-collection via archivist.rerank() — gated by VERTEX_RANKER_MODEL env var.
#    Each rerank() catches its own exceptions (never raises past gather).
"""Lookup and query tool handlers (service, deep memory, journal)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from ..models import ConversationTurn
from .handler_utils import _safe_int

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


async def handle_lookup_service(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service_name = args.get("service_name", "")
    bb = ctx.get_blackboard()

    event_doc = await bb.get_event(event_id)
    subject_type = getattr(event_doc, "subject_type", "service") if event_doc else "service"
    if subject_type != "service":
        context_label = {
            "kargo_stage": "kargo_context",
            "jira": "jira_context",
            "system": "system-level context",
        }.get(subject_type, subject_type)
        result_text = (
            f"## lookup_service: Not applicable\n\n"
            f"This event's subject is a {subject_type}, not a monitored K8s deployment.\n"
            f"The relevant context ({context_label}) is already in your prompt."
        )
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            waitingFor="lookup_service",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    svc = await bb.get_service(service_name)
    if not svc and "/" not in service_name:
        known = await bb.get_services()
        matches = [k for k in known if k.endswith(f"/{service_name}")]
        if len(matches) == 1:
            service_name = matches[0]
            svc = await bb.get_service(service_name)
        elif matches:
            result_text = (
                f"## Service: {service_name}\n\n"
                f"Ambiguous — found in {len(matches)} namespaces:\n"
                + "\n".join(f"- `{m}`" for m in sorted(matches))
                + "\n\nSpecify the full `namespace/name` to disambiguate."
            )
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="lookup_service", evidence=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return False
    if svc:
        rows = [f"| Version | {svc.version} |"]
        if svc.gitops_repo:
            rows.append(f"| GitOps Repo | {svc.gitops_repo} |")
        if svc.gitops_repo_url:
            rows.append(f"| Repo URL | {svc.gitops_repo_url} |")
        if svc.gitops_config_path:
            rows.append(f"| Config Path | {svc.gitops_config_path} |")
        if svc.replicas_ready is not None:
            rows.append(f"| Replicas | {svc.replicas_ready}/{svc.replicas_desired} |")
        rows.append(f"| Health | {svc.health_status or 'unknown'} |")
        rows.append(f"| Sync | {svc.sync_status or 'unknown'} |")
        if svc.argocd_app:
            rows.append(f"| ArgoCD App | {svc.argocd_app} |")
        if svc.escalation_flag:
            scope_label = f" ({svc.escalation_scope})" if svc.escalation_scope else ""
            rows.append(f"| Escalation | Escalated{scope_label}: {svc.escalation_flag} |")
        result_text = f"## Service: {service_name}\n\n| Field | Value |\n|---|---|\n" + "\n".join(rows)
    else:
        known = await bb.get_services()
        result_text = f"## Service: {service_name}\n\nNot found. Known services: {', '.join(sorted(known)) if known else 'none'}"

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="lookup_service",
        evidence=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


async def handle_consult_deep_memory(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    query = args.get("query", "")
    time_range = _safe_int(args.get("time_range_hours"))
    min_dur = _safe_int(args.get("min_duration_minutes"))
    svc = str(args.get("service") or "").strip() or None
    bb = ctx.get_blackboard()

    conditions: list[dict] = []
    if time_range:
        cutoff = time.time() - (time_range * 3600)
        conditions.append({"key": "closed_at", "range": {"gte": cutoff}})
    if min_dur:
        conditions.append({"key": "duration_seconds", "range": {"gte": min_dur * 60}})
    if svc:
        conditions.append({"key": "service", "match": {"value": svc}})
    qdrant_filter = {"must": conditions} if conditions else None
    if qdrant_filter:
        logger.debug(
            "Deep memory filters applied: %s for event %s",
            [f for f in ['time_range' if time_range else '', 'min_dur' if min_dur else '', 'svc' if svc else ''] if f],
            event_id,
        )

    ev = await bb.get_event(event_id)
    safe_query = query.replace('"', '\\"')
    filter_parts: list[str] = []
    if time_range:
        filter_parts.append(f"time={time_range}h")
    if min_dur:
        filter_parts.append(f"dur>={min_dur}m")
    if svc:
        filter_parts.append(f"svc={svc}")
    filter_tag = f" [{','.join(filter_parts)}]" if filter_parts else " [unfiltered]"
    query_marker = f'Deep Memory: "{safe_query}"{filter_tag}'
    already_consulted = any(
        t.action in ("think", "thoughts", "intermediate", "response", "tool_result")
        and t.evidence and query_marker in (t.evidence or "")
        for t in (ev.conversation if ev else [])
    )
    if already_consulted:
        logger.info(f"Deep memory already consulted for {event_id} query={query!r} -- returning cached results")
        cached_evidence = next(
            (t.evidence for t in (ev.conversation if ev else [])
             if t.action in ("think", "thoughts", "intermediate", "response", "tool_result")
             and t.evidence and query_marker in t.evidence),
            "Deep memory was already consulted (no cached results).",
        )
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            waitingFor="consult_deep_memory",
            evidence=f"[Already consulted] {cached_evidence}",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        if "No historical patterns" in cached_evidence or "No results" in cached_evidence or "No events match" in cached_evidence:
            return False
        return True

    archivist = ctx.get_agent_instance("_archivist_memory")
    has_results = False

    from ..memory.pulse import PulseContext
    ev_for_ctx = ev or await bb.get_event(event_id)
    pulse_ctx = PulseContext(
        event_id=event_id,
        turn=len(ev_for_ctx.conversation) if ev_for_ctx else 0,
        event_elapsed_s=int(time.time() - ev_for_ctx.conversation[0].timestamp) if ev_for_ctx and ev_for_ctx.conversation else 0,
        event_source=ev_for_ctx.source if ev_for_ctx else None,
    )

    memory_text = f"# Deep Memory: \"{safe_query}\"{filter_tag}\n\n"

    query_vector = None
    if archivist and hasattr(archivist, "embed_query"):
        try:
            query_vector = await archivist.embed_query(query)
        except Exception as e:
            logger.debug(f"embed_query failed, each search will embed individually: {e}")

    knowledge = lessons = results = None

    if archivist and hasattr(archivist, "search_knowledge"):
        try:
            knowledge = await archivist.search_knowledge(
                query, limit=3, context=pulse_ctx, vector=query_vector,
                service_filter=svc or (ev.service if ev else None),
            )
        except Exception as e:
            logger.warning(f"Deep memory knowledge search failed: {e}")

    if archivist and hasattr(archivist, "search_lessons"):
        try:
            lessons = await archivist.search_lessons(query, limit=3, context=pulse_ctx, vector=query_vector)
        except Exception as e:
            logger.warning(f"Deep memory lesson search failed: {e}")

    if archivist and hasattr(archivist, "search"):
        try:
            results = await archivist.search(query, limit=5, context=pulse_ctx, vector=query_vector, filter=qdrant_filter)
        except Exception as e:
            logger.warning(f"Deep memory event search failed: {e}")

    if archivist and hasattr(archivist, "rerank"):
        # Defense-in-depth (codereview finding): rerank() is documented to never raise past
        # this call, but return_exceptions=True + per-result fallback means a future regression
        # in rerank() degrades one collection instead of failing the whole handler.
        orig_knowledge, orig_lessons, orig_results = knowledge or [], lessons or [], results or []
        gathered = await asyncio.gather(
            archivist.rerank(query, orig_knowledge, "knowledge"),
            archivist.rerank(query, orig_lessons, "lessons"),
            archivist.rerank(query, orig_results, "events"),
            return_exceptions=True,
        )
        knowledge, lessons, results = (
            orig if isinstance(reranked, Exception) else reranked
            for reranked, orig in zip(gathered, (orig_knowledge, orig_lessons, orig_results))
        )
        for label, reranked in zip(("knowledge", "lessons", "events"), gathered):
            if isinstance(reranked, Exception):
                logger.warning(f"Rerank raised unexpectedly for {label} (original order): {reranked}")

    if knowledge:
        has_results = True
        memory_text += "### Reference Facts\n"
        for i, r in enumerate(knowledge, 1):
            p = r.get("payload", {})
            stale_tag = " [STALE - verify before acting]" if r.get("stale") else ""
            fact_text = p.get("fact", "?")
            memory_text += (
                f"{i}. **{p.get('topic', '?')}** ({p.get('scope', '?')}, confidence: {p.get('confidence', '?')}){stale_tag}\n"
                f"   - {fact_text}\n"
                f"   - Source: {p.get('source', '?')}\n"
            )
        memory_text += "\n"

    if lessons:
        has_results = True
        memory_text += "### Lessons Learned\n"
        for i, r in enumerate(lessons, 1):
            p = r.get("payload", {})
            memory_text += (
                f"{i}. **{p.get('title', '?')}** (score: {r.get('score', 0):.2f}, "
                f"channel: {p.get('channel', '?')})\n"
                f"   - Pattern: {p.get('pattern', '?')}\n"
            )
        memory_text += "\n"

    if results:
        has_results = True
        memory_text += "### Past Events\n"
        for i, r in enumerate(results, 1):
            p = r.get("payload", {})
            dur = p.get("duration_seconds", 0)
            dur_m = f"{dur // 60}m" if dur else "?"
            defers = p.get("defer_patterns", [])
            total_defer = sum(d.get("duration_seconds", 0) for d in defers if isinstance(d, dict))
            defer_m = f"{total_defer // 60}m" if total_defer else "0m"
            timings = p.get("operational_timings", [])
            timing_str = ", ".join(
                f"{t.get('process', '?')}={t.get('duration_seconds', 0) // 60}m"
                for t in timings if isinstance(t, dict)
            ) or "none"
            domain_str = p.get("brain_domain", p.get("domain", "?"))
            corrected = " [CORRECTED]" if p.get("corrected") else ""
            memory_text += (
                f"{i}. domain: {domain_str} | score: {r.get('score', 0):.2f}{corrected}\n"
                f"   - Pattern: {p.get('symptom', '?')}\n"
                f"   - Root cause: {p.get('root_cause', '?')}\n"
                f"   - Fix: {p.get('fix_action', '?')}\n"
                f"   - Service: {p.get('service', '?')} | Duration: {dur_m}, defers: {defer_m}, timings: [{timing_str}], outcome: {p.get('outcome', '?')}\n"
            )

    if not has_results:
        if qdrant_filter:
            filter_desc = ", ".join(filter_parts) if filter_parts else "active filters"
            memory_text += (
                f"No events match the applied filters ({filter_desc}). "
                "Consider widening the time range, removing duration or service constraints, "
                "or searching with different keywords."
            )
        else:
            memory_text += (
                "No historical patterns match this query. "
                "Consider whether the event classification is accurate, "
                "or try searching with different keywords that describe the symptom or root cause. "
                "The ops journal for this service may also have relevant entries."
            )

    if ev and ev.source in ("chat", "slack"):
        last_user = next(
            (t for t in reversed(ev.conversation) if t.actor == "user"), None
        )
        if last_user:
            user_text = last_user.evidence or last_user.thoughts or ""
            if user_text:
                memory_text += f"\n\n---\nRespond to the user: {user_text}"

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="consult_deep_memory",
        evidence=memory_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


async def handle_lookup_journal(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service_name = args.get("service_name", "")
    bb = ctx.get_blackboard()
    if service_name:
        entries = await ctx.get_cached_journal(service_name)
        if entries:
            header = f"## Ops Journal: {service_name}\n\n{len(entries)} entries:\n\n"
            journal_text = header + "\n".join(f"- {e}" for e in entries)
        else:
            journal_text = f"## Ops Journal: {service_name}\n\nNo entries found."
    else:
        entries = await bb.get_recent_journal_entries()
        if entries:
            header = f"## Ops Journal: all services\n\n{len(entries)} entries:\n\n"
            journal_text = header + "\n".join(f"- {e}" for e in entries)
        else:
            journal_text = "## Ops Journal\n\nNo entries found across any service."
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="lookup_journal",
        evidence=journal_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


async def handle_web_search(
    ctx: "ToolContext", event_id: str, args: dict, response_parts=None,
) -> bool:
    """Search the web via Vertex AI Search (Discovery Engine). Returns True (continue)."""
    import asyncio
    import os

    _WEB_SEARCH_TIMEOUT_SEC = 15.0

    query = args.get("query", "").strip()[:500]
    if not query:
        turn = ConversationTurn(
            turn=0, actor="brain", action="tool_result",
            thoughts="web_search requires a 'query' argument.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    datastore_id = os.getenv("VERTEX_SEARCH_DATASTORE_ID", "")
    project_id = os.environ.get("GCP_PROJECT_ID", "")
    if not datastore_id or not project_id:
        turn = ConversationTurn(
            turn=0, actor="brain", action="tool_result",
            thoughts=f"Web search for: {query}\n\n(Search API not configured)",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    try:
        from google.cloud import discoveryengine_v1 as discoveryengine

        client = discoveryengine.SearchServiceAsyncClient()
        serving_config = (
            f"projects/{project_id}"
            f"/locations/global/collections/default_collection"
            f"/dataStores/{datastore_id}/servingConfigs/default_config"
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
        )

        async def _do_search():
            response = await client.search(request=request)
            results = []
            async for result in response:
                doc = result.document
                title = (doc.derived_struct_data.get("title", "") if doc.derived_struct_data else "")[:200]
                snippet = ""
                snippets = doc.derived_struct_data.get("snippets", []) if doc.derived_struct_data else []
                if snippets:
                    snippet = snippets[0].get("snippet", "")[:500]
                link = (doc.derived_struct_data.get("link", "") if doc.derived_struct_data else "")[:500]
                results.append(f"- [{title}]({link})\n  {snippet}")
                if len(results) >= 5:
                    break
            return results

        results = await asyncio.wait_for(_do_search(), timeout=_WEB_SEARCH_TIMEOUT_SEC)

        result_text = "\n\n".join(results) if results else "No results found."
        fenced = (
            f"<web_search_results untrusted=\"true\">\n"
            f"{result_text}\n"
            f"</web_search_results>"
        )
        turn = ConversationTurn(
            turn=0, actor="brain", action="tool_result",
            evidence=f"Web search: {query}\n\n{fenced}",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
    except asyncio.TimeoutError:
        logger.warning("web_search timed out for %s (query=%s)", event_id, query[:50])
        turn = ConversationTurn(
            turn=0, actor="brain", action="tool_result",
            thoughts=f"Web search for '{query}' timed out.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
    except Exception as e:
        logger.warning("web_search failed for %s: %s", event_id, e)
        turn = ConversationTurn(
            turn=0, actor="brain", action="tool_result",
            thoughts="Web search backend unavailable.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["lookup_service"] = handle_lookup_service
HANDLER_REGISTRY["consult_deep_memory"] = handle_consult_deep_memory
HANDLER_REGISTRY["lookup_journal"] = handle_lookup_journal
HANDLER_REGISTRY["web_search"] = handle_web_search
