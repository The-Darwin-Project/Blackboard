# BlackBoard/src/agents/jenkins_observer.py
# @ai-rules:
# 1. [Pattern]: Poll-driven event creation — _drain_once() fires every poll interval,
#    checks Jenkins for failed/missing/unstable CI gating jobs, triages with Flash Lite.
# 2. [Pattern]: TimeKeeper lifecycle — start()/stop() own an asyncio.Task running _poll_loop().
# 3. [Constraint]: AIR GAP: No Brain logic. Creates events via blackboard, never routes agents.
# 4. [Pattern]: pending_count is an in-memory property updated at drain cycle start/end.
# 5. [Pattern]: Service naming: {job_name}|{version} (NOT @ — PII regex collision).
# 6. [Pattern]: Lazy skills fetch with 5-min TTL (mirrors headhunter_github._load_issue_triage_instruction).
# 7. [Pattern]: Dry-run default — JENKINS_OBSERVER_DRY_RUN=true logs evidence but skips create_event.
# 8. [Pattern]: Dedup tuple includes waiting_approval (deliberate improvement over Aligner).
# 9. [Pattern]: Flood consolidation merges whole group into ONE event (Aligner pattern).
"""
JenkinsObserver: CI gating reconciliation daemon.

Polls Jenkins for failed/missing gating jobs, triages with Flash Lite,
creates events with source="aligner" + subject_type="ci_gating" for FRIDAY.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from ..adapters.jenkins import JenkinsAdapter
    from ..state.blackboard import BlackboardState

from ..models import EventEvidence

logger = logging.getLogger(__name__)

_DEDUP_STATUSES = ("new", "active", "deferred", "waiting_approval")

_FALLBACK_SI = (
    "You are a CI gating triage assistant. Classify Jenkins job failures as "
    "infrastructure (flaky infra, cluster issues), test (real test failures), "
    "or product (genuine product bugs). Recommend: restart, investigate, or escalate."
)


class JenkinsObserver:
    """CI gating reconciliation daemon — mirrors Aligner poll pattern."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        jenkins_adapter: Optional["JenkinsAdapter"] = None,
    ):
        self.blackboard = blackboard
        self._adapter = jenkins_adapter
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._pending_count: int = 0

        self._poll_interval = int(os.getenv("JENKINS_OBSERVER_POLL_INTERVAL", "300"))
        self._startup_delay = int(os.getenv("JENKINS_OBSERVER_STARTUP_DELAY", "180"))
        self._dwell_seconds = float(os.getenv("JENKINS_OBSERVER_DWELL_SECONDS", "60"))
        self._flood_threshold = int(os.getenv("JENKINS_OBSERVER_FLOOD_THRESHOLD", "3"))
        self._dry_run = os.getenv("JENKINS_OBSERVER_DRY_RUN", "true").lower() == "true"
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        self._versions = [
            v.strip() for v in os.getenv("JENKINS_OBSERVER_VERSIONS", "").split(",") if v.strip()
        ]

        self._skills_si: str = _FALLBACK_SI
        self._skills_loaded_at: float = 0.0
        self._skills_ttl: float = 300.0  # 5 minutes

        self._llm_adapter = None

    @property
    def pending_count(self) -> int:
        """In-memory pending count updated each drain cycle."""
        return self._pending_count

    @property
    def breaker_open(self) -> bool:
        """Circuit breaker state from the Jenkins adapter."""
        if self._adapter:
            return self._adapter.breaker_open
        return False

    async def start(self) -> None:
        """Start the poll loop task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "JenkinsObserver started (interval=%ds, dwell=%ds, versions=%s, dry_run=%s)",
            self._poll_interval, self._dwell_seconds, self._versions, self._dry_run,
        )

    async def stop(self) -> None:
        """Stop the poll loop task."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._adapter:
            await self._adapter.close()

    async def _poll_loop(self) -> None:
        """Periodic drain loop with startup delay."""
        await asyncio.sleep(self._startup_delay)
        while self._running:
            try:
                await self._drain_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("JenkinsObserver: drain cycle failed, continuing")
            await asyncio.sleep(self._poll_interval)

    async def _ensure_skills_loaded(self) -> None:
        """Lazy-fetch Skills Catalog instructions. Never raises."""
        if time.time() - self._skills_loaded_at < self._skills_ttl:
            return
        try:
            catalog_url = os.getenv("SKILLS_CATALOG_URL", "")
            skills_csv = os.getenv("SKILLS_CATALOG_SKILLS", "cnv-gating-workflow")
            if not catalog_url:
                self._skills_loaded_at = time.time()
                return

            parts = []
            async with httpx.AsyncClient(timeout=10) as client:
                for slug in skills_csv.split(","):
                    slug = slug.strip()
                    if not slug:
                        continue
                    resp = await client.get(f"{catalog_url}/api/v1/skills/{slug}/download")
                    if resp.status_code == 200:
                        parts.append(resp.text[:10000])
            if parts:
                self._skills_si = "\n\n---\n\n".join(parts)
            self._skills_loaded_at = time.time()
        except Exception as e:
            logger.warning("JenkinsObserver: Skills Catalog fetch failed (%s), using fallback SI", e)
            self._skills_loaded_at = time.time()

    async def _get_llm_adapter(self):
        """Lazy-load own GeminiAdapter instance for Flash Lite triage."""
        if self._llm_adapter is None:
            from ..agents.llm.gemini_adapter import GeminiAdapter
            model = os.getenv("LLM_MODEL_JENKINS_OBSERVER", "gemini-3.5-flash-lite")
            self._llm_adapter = GeminiAdapter(
                model=model,
                temperature=float(os.getenv("LLM_TEMPERATURE_JENKINS_OBSERVER", "0.3")),
                max_output_tokens=int(os.getenv("LLM_MAX_TOKENS_JENKINS_OBSERVER", "4096")),
            )
        return self._llm_adapter

    async def _get_wip_headroom(self) -> int:
        """Query current WIP usage and return available headroom."""
        try:
            status_map = await self.blackboard.get_active_events_with_status()
            wip_used = sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))
            return max(0, self._wip_cap - wip_used)
        except Exception as e:
            logger.warning("JenkinsObserver: WIP headroom query failed (%s), defaulting to 5", e)
            return 5

    async def _drain_once(self) -> None:
        """Single drain cycle: poll → stage → dwell → triage → create."""
        await self._ensure_skills_loaded()

        if not self._adapter or not self._adapter.enabled():
            return

        # Step 1: Poll Jenkins for all configured versions
        for version in self._versions:
            smoke_jobs = await self._adapter.poll_smoke_jobs(version)
            gating_jobs = await self._adapter.poll_gating_jobs(version)

            all_jobs = smoke_jobs + gating_jobs
            for job in all_jobs:
                if job.result in ("FAILURE", "UNSTABLE", "ABORTED") or job.result is None:
                    key = f"{job.job_name}|{version}"
                    metadata = {
                        "job_name": job.job_name,
                        "version": version,
                        "result": job.result or "MISSING",
                        "build_number": job.build_number,
                        "url": job.url,
                        "staged_at": time.time(),
                    }
                    await self.blackboard.stage_jenkins_signal(key, metadata)

        # Step 2: Drain expired items
        expired_keys = await self.blackboard.drain_jenkins_pending(self._dwell_seconds)
        if not expired_keys:
            self._pending_count = await self.blackboard.count_jenkins_pending()
            return

        self._pending_count = await self.blackboard.count_jenkins_pending()

        # Step 3: Re-check Jenkins — discard self-resolved
        candidates: list[tuple[str, dict]] = []
        for key in expired_keys:
            raw = await self.blackboard.redis.hget(
                self.blackboard.JENKINS_PENDING_META, key
            )
            if not raw:
                await self.blackboard.commit_jenkins_signal(key)
                continue
            meta = json.loads(raw)
            job_name = meta.get("job_name", "")
            version = meta.get("version", "")

            # Quick recheck: if the job is now healthy, discard
            if self._adapter and job_name and version:
                recheck = await self._adapter.poll_gating_jobs(version)
                resolved = any(
                    j.job_name == job_name and j.result == "SUCCESS"
                    for j in recheck
                )
                if resolved:
                    await self.blackboard.commit_jenkins_signal(key)
                    continue

            candidates.append((key, meta))

        if not candidates:
            self._pending_count = await self.blackboard.count_jenkins_pending()
            return

        # Step 4: Flood consolidation (group by version)
        by_version: dict[str, list[tuple[str, dict]]] = {}
        for key, meta in candidates:
            v = meta.get("version", "unknown")
            by_version.setdefault(v, []).append((key, meta))

        creation_candidates: list[tuple[str, list[tuple[str, dict]]]] = []
        for version, signals in by_version.items():
            if len(signals) > self._flood_threshold:
                creation_candidates.append((version, signals))
            else:
                for key, meta in signals:
                    creation_candidates.append((meta.get("job_name", key) + "|" + version, [(key, meta)]))

        # Step 5: WIP headroom (computed ONCE after flood consolidation)
        available = await self._get_wip_headroom()

        # Step 6: Per-candidate dedup + creation
        for service_key, signals in creation_candidates:
            if len(signals) > 1:
                service_name = f"ci-gating-flood|{signals[0][1].get('version', '')}"
            else:
                k, m = signals[0]
                service_name = f"{m.get('job_name', k)}|{m.get('version', '')}"

            # Active-event dedup check (Layer 1)
            try:
                status_map = await self.blackboard.get_active_events_with_status()
                existing = False
                for eid, status in status_map.items():
                    if status in _DEDUP_STATUSES:
                        evt = await self.blackboard.get_event(eid)
                        if evt and evt.service == service_name:
                            existing = True
                            break
                if existing:
                    for key, _ in signals:
                        await self.blackboard.commit_jenkins_signal(key)
                    continue
            except Exception:
                pass

            # Escalation-gate check (Layer 3)
            try:
                flag = await self.blackboard.get_escalation_flag(service_name, scope="jenkins")
                if flag:
                    for key, _ in signals:
                        await self.blackboard.commit_jenkins_signal(key)
                    continue
            except Exception:
                pass

            # WIP gate
            if available <= 0:
                for key, meta in signals:
                    await self.blackboard.restage_jenkins_signal(key, meta)
                continue
            available -= 1

            # Triage with Flash Lite
            evidence_obj = await self._triage_and_build_evidence(signals)

            # Dry-run gate
            if self._dry_run:
                logger.info(
                    "JenkinsObserver DRY-RUN: would create event for service=%s evidence=%s",
                    service_name, json.dumps(evidence_obj.model_dump(), default=str)[:500],
                )
                for key, _ in signals:
                    await self.blackboard.commit_jenkins_signal(key)
                continue

            # Create event
            try:
                reason = f"CI gating failure: {service_name}"
                await self.blackboard.create_event(
                    source="aligner",
                    service=service_name,
                    reason=reason,
                    evidence=evidence_obj,
                    subject_type="ci_gating",
                )
                for key, _ in signals:
                    await self.blackboard.commit_jenkins_signal(key)
            except Exception:
                logger.exception("JenkinsObserver: event creation failed for %s, restaging", service_name)
                for key, meta in signals:
                    await self.blackboard.restage_jenkins_signal(key, meta)

        self._pending_count = await self.blackboard.count_jenkins_pending()

    async def _triage_and_build_evidence(
        self, signals: list[tuple[str, dict]]
    ) -> EventEvidence:
        """Run Flash Lite triage on failed jobs and build structured evidence."""
        failed_jobs = []
        missing_jobs = []
        version = signals[0][1].get("version", "") if signals else ""
        jenkins_url = os.getenv("JENKINS_URL", "")

        for _, meta in signals:
            result = meta.get("result", "UNKNOWN")
            job_entry = {
                "job_name": meta.get("job_name", ""),
                "build_number": meta.get("build_number"),
                "result": result,
                "jenkins_link": meta.get("url", ""),
            }
            if result == "MISSING" or meta.get("build_number") is None:
                missing_jobs.append({
                    "job_name": meta.get("job_name", ""),
                    "last_build_number": meta.get("build_number"),
                    "last_result": result,
                })
            else:
                # Fetch console tail for failed jobs
                if self._adapter and meta.get("build_number"):
                    details = await self._adapter.get_build_details(
                        meta["job_name"], meta["build_number"]
                    )
                    if details:
                        job_entry["console_tail"] = details.console_tail[:3000]
                        job_entry["parameters"] = details.parameters
                failed_jobs.append(job_entry)

        # LLM triage
        llm_triage = []
        try:
            adapter = await self._get_llm_adapter()
            prompt = self._build_triage_prompt(failed_jobs, missing_jobs, version)
            response = await adapter.generate(
                prompt=prompt,
                system_instruction=self._skills_si,
                max_output_tokens=int(os.getenv("LLM_MAX_TOKENS_JENKINS_OBSERVER", "4096")),
            )
            if response and response.text:
                llm_triage = self._parse_triage_response(response.text)
        except Exception as e:
            logger.warning("JenkinsObserver: LLM triage failed (%s), continuing without", e)

        ci_context = {
            "cnv_version": version,
            "jenkins_url": jenkins_url,
            "failed_jobs": failed_jobs,
            "missing_jobs": missing_jobs,
            "llm_triage": llm_triage,
        }

        display_parts = []
        if failed_jobs:
            display_parts.append(f"{len(failed_jobs)} failed CI gating job(s)")
        if missing_jobs:
            display_parts.append(f"{len(missing_jobs)} missing job(s)")
        display_text = f"CNV {version}: {', '.join(display_parts)}" if display_parts else f"CNV {version}: CI gating issue"

        return EventEvidence(
            display_text=display_text,
            source_type="aligner",
            domain="disorder",
            domain_confidence="default",
            severity="warning",
            ci_context=ci_context,
        )

    def _build_triage_prompt(
        self, failed_jobs: list[dict], missing_jobs: list[dict], version: str
    ) -> str:
        """Build a triage prompt for Flash Lite."""
        lines = [f"CNV version: {version}", ""]
        if failed_jobs:
            lines.append("## Failed Jobs")
            for j in failed_jobs[:10]:
                lines.append(f"- {j['job_name']} #{j.get('build_number', '?')} [{j.get('result', '?')}]")
                if j.get("console_tail"):
                    lines.append(f"  Console (last 500 chars): {j['console_tail'][-500:]}")
        if missing_jobs:
            lines.append("\n## Missing Jobs (never ran)")
            for j in missing_jobs[:10]:
                lines.append(f"- {j['job_name']}")
        lines.append("\nFor each job, classify as: infrastructure, test, or product failure.")
        lines.append("Recommend: restart, investigate, or escalate.")
        lines.append("Return JSON array: [{\"job_name\": ..., \"classification\": ..., \"confidence\": 0.0-1.0, \"recommended_action\": ..., \"failed_leaves\": [...], \"owner\": ..., \"component\": ...}]")
        return "\n".join(lines)

    def _parse_triage_response(self, text: str) -> list[dict]:
        """Parse LLM triage JSON response. Tolerant of markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        return []
