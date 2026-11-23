# BlackBoard/tests/test_headhunter_contract.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD Contract Suite (T-19) exercising the full multi-head pipeline
#    poll_work_items -> fetch_context -> _build_analysis_prompt -> analyze_and_plan ->
#    create_platform_event -> build_event_header -> post_feedback + get_platform_snapshot.
# 2. [Constraint]: Zero live network or Redis; HTTP via httpx.MockTransport and state via JSON-roundtripped
#    in-memory Blackboard store proving Redis EventDocument schema compatibility.
"""
4-Layer Farley ATDD Contract Suite (T-19)
Multi-head Headhunter pipeline contract for GitLab MR and GitHub PR + VcsWorkItem/VcsContext.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.headhunter import Headhunter
from src.agents.headhunter_models import PlatformSnapshot, VcsContext, VcsWorkItem
from src.agents.headhunter_port import VcsPlatformPort
from src.agents.llm.prompt import build_event_header
from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput, EventStatus


# =============================================================================
# Layer 3: Protocol Drivers (In-Memory JSON-Roundtripping Blackboard & HTTP)
# =============================================================================


class InMemoryContractBlackboard:
    """In-memory BlackboardState double that serializes EventDocument through JSON."""

    def __init__(self) -> None:
        self._events_json: dict[str, str] = {}
        self._active: dict[str, str] = {}
        self._waiting: set[str] = set()
        self._feedback_sent: set[str] = set()
        self._feedback_note_sent: set[str] = set()
        self._gitlab_mr_sha: dict[tuple[int, int], str] = {}
        self._github_pr_sha: dict[tuple[str, str, int], str] = {}
        self._counter = 0
        self.redis = AsyncMock()
        self.redis.get = AsyncMock(return_value=None)
        self.redis.set = AsyncMock(return_value=True)

    async def create_event(
        self,
        *,
        source: str,
        service: str,
        reason: str,
        evidence: EventEvidence,
    ) -> str:
        self._counter += 1
        eid = f"evt-contract-{self._counter:04d}"
        doc = EventDocument(
            id=eid,
            source=source,
            service=service,
            status=EventStatus.NEW,
            event=EventInput(reason=reason, evidence=evidence),
        )
        self._events_json[eid] = doc.model_dump_json()
        self._active[eid] = "new"
        return eid

    async def get_event(self, event_id: str) -> EventDocument | None:
        raw = self._events_json.get(event_id)
        if not raw:
            return None
        return EventDocument.model_validate_json(raw)

    async def save_event(self, doc: EventDocument) -> None:
        self._events_json[doc.id] = doc.model_dump_json()

    async def get_active_events(self) -> list[str]:
        return list(self._active.keys())

    async def get_active_events_with_status(self) -> dict[str, str]:
        return dict(self._active)

    async def get_waiting_approval_events(self) -> list[str]:
        return list(self._waiting)

    async def list_gitlab_queue(self) -> list[dict]:
        return []

    async def remove_gitlab_queue(self, project_id: int, mr_iid: int) -> bool:
        return True

    async def is_feedback_sent(self, event_id: str) -> bool:
        return event_id in self._feedback_sent

    async def mark_feedback_sent(self, event_id: str) -> None:
        self._feedback_sent.add(event_id)

    async def is_feedback_note_sent(self, event_id: str) -> bool:
        return event_id in self._feedback_note_sent

    async def mark_feedback_note_sent(self, event_id: str) -> None:
        self._feedback_note_sent.add(event_id)

    async def set_gitlab_mr_sha(self, project_id: int, mr_iid: int, sha: str) -> None:
        self._gitlab_mr_sha[(int(project_id), int(mr_iid))] = sha

    async def get_gitlab_mr_sha(self, project_id: int, mr_iid: int) -> str | None:
        return self._gitlab_mr_sha.get((int(project_id), int(mr_iid)))

    async def set_github_pr_sha(self, owner: str, repo: str, pr_number: int, sha: str) -> None:
        self._github_pr_sha[(owner, repo, int(pr_number))] = sha

    async def get_github_pr_sha(self, owner: str, repo: str, pr_number: int) -> str | None:
        return self._github_pr_sha.get((owner, repo, int(pr_number)))

    async def clear_event_approval(self, event_id: str) -> None:
        doc = await self.get_event(event_id)
        if doc:
            doc.approved_by = None
            doc.approved_mr_id = None
            doc.approved_mr_sha = None
            doc.approval_requested_sha = None
            await self.save_event(doc)


def _make_gitlab_transport(captured: dict) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        captured["requests"].append((request.method, path))
        if request.method == "GET" and path == "/api/v4/todos":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 701,
                        "action_name": "review_requested",
                        "created_at": "2026-09-01T00:00:00Z",
                        "target_url": "https://gitlab.example.com/group/repo/-/merge_requests/42",
                        "project": {"id": 100, "path_with_namespace": "group/repo"},
                        "target": {
                            "iid": 42,
                            "title": "Fix contract pipeline",
                            "state": "opened",
                            "merge_status": "can_be_merged",
                            "source_branch": "feat/contract",
                            "target_branch": "main",
                            "description": "MR body",
                            "author": {"username": "alice"},
                            "labels": ["ci"],
                            "sha": "abc1234567890abcdef1234567890abcdef12345",
                        },
                    }
                ],
            )
        if request.method == "GET" and path == "/api/v4/projects/100/merge_requests/42":
            return httpx.Response(
                200,
                json={
                    "iid": 42,
                    "title": "Fix contract pipeline",
                    "state": "opened",
                    "detailed_merge_status": "mergeable",
                    "sha": "abc1234567890abcdef1234567890abcdef12345",
                },
            )
        if request.method == "GET" and path == "/api/v4/projects/100/merge_requests/42/diffs":
            return httpx.Response(200, json=[{"new_path": "src/main.py"}])
        if request.method == "GET" and path == "/api/v4/projects/100/merge_requests/42/pipelines":
            return httpx.Response(200, json=[{"id": 9001, "status": "success"}])
        if request.method == "GET" and path == "/api/v4/projects/100/merge_requests/42/notes":
            return httpx.Response(200, json=[])
        if request.method == "POST" and path == "/api/v4/projects/100/merge_requests/42/notes":
            captured["posted_notes"].append(json.loads(request.content.decode()))
            return httpx.Response(201, json={"id": 888})
        if request.method == "POST" and path == "/api/v4/todos/701/mark_as_done":
            captured["marked_done"].append(701)
            return httpx.Response(200, json={"id": 701, "state": "done"})
        return httpx.Response(404, json={"error": f"unhandled {request.method} {path}"})

    return httpx.MockTransport(_handler)


def _make_github_transport(captured: dict) -> httpx.MockTransport:
    head_sha = "11223344556677889900aabbccddeeff11223344"

    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        captured["requests"].append((request.method, path))
        if request.method == "GET" and path == "/repos/org/repo/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 77,
                        "title": "Fix GitHub contract",
                        "state": "open",
                        "user": {"login": "octocat"},
                        "labels": [{"name": "darwin-review"}],
                        "html_url": "https://github.com/org/repo/pull/77",
                        "created_at": "2026-09-01T00:00:00Z",
                        "head": {"sha": head_sha, "ref": "feat/gh"},
                        "base": {"ref": "main"},
                        "draft": False,
                    }
                ],
            )
        if request.method == "GET" and path == "/repos/org/repo/pulls/77":
            return httpx.Response(
                200,
                json={
                    "number": 77,
                    "title": "Fix GitHub contract",
                    "state": "open",
                    "merged": False,
                    "draft": False,
                    "mergeable": True,
                    "mergeable_state": "clean",
                    "body": "PR description",
                    "head": {"sha": head_sha, "ref": "feat/gh"},
                    "base": {"ref": "main"},
                    "html_url": "https://github.com/org/repo/pull/77",
                },
            )
        if request.method == "GET" and path == "/repos/org/repo/pulls/77/files":
            return httpx.Response(200, json=[{"filename": "src/app.py"}])
        if request.method == "GET" and path == f"/repos/org/repo/commits/{head_sha}/check-runs":
            return httpx.Response(200, json={"check_runs": [{"name": "ci", "conclusion": "success", "status": "completed"}]})
        if request.method == "GET" and path == f"/repos/org/repo/commits/{head_sha}/status":
            return httpx.Response(200, json={"state": "success", "statuses": []})
        if request.method == "GET" and path == "/repos/org/repo/issues/77/comments":
            return httpx.Response(200, json=[])
        if request.method == "GET" and path == "/repos/org/repo/pulls/77/reviews":
            return httpx.Response(200, json=[])
        if request.method == "GET" and path == "/repos/org/repo/pulls/77/comments":
            return httpx.Response(200, json=[])
        if request.method == "POST" and path == "/repos/org/repo/issues/77/labels":
            payload = json.loads(request.content.decode())
            captured["added_labels"].extend(payload.get("labels", []))
            return httpx.Response(200, json=[])
        if request.method == "DELETE" and path.startswith("/repos/org/repo/issues/77/labels/"):
            captured["removed_labels"].append(path.rsplit("/", 1)[-1])
            return httpx.Response(200, json=[])
        if request.method == "POST" and path == "/repos/org/repo/issues/77/comments":
            captured["posted_comments"].append(json.loads(request.content.decode())["body"])
            return httpx.Response(201, json={"id": 999})
        return httpx.Response(404, json={"error": f"unhandled {request.method} {path}"})

    return httpx.MockTransport(_handler)


class MultiHeadContractDSL:
    """Layer 2 Domain DSL for end-to-end Headhunter contract execution."""

    def __init__(self, bb: InMemoryContractBlackboard, hh: Headhunter) -> None:
        self.bb = bb
        self.hh = hh
        self.items: list = []
        self.context: object = None
        self.prompt: str = ""
        self.plan_text: str = ""
        self.event_id: str = ""
        self.event: EventDocument | None = None
        self.header: str = ""
        self.snapshot: PlatformSnapshot | None = None

    async def execute_full_lifecycle(self, adapter: VcsPlatformPort) -> None:
        assert isinstance(adapter, VcsPlatformPort)
        self.items = list(await adapter.poll_work_items())
        assert len(self.items) == 1

        self.context = await adapter.fetch_context(self.items[0])
        assert self.context is not None

        self.prompt = self.hh._build_analysis_prompt(self.context)
        assert "Produce a YAML frontmatter work plan." in self.prompt

        si = adapter.load_triage_instruction()
        self.plan_text = await self.hh.analyze_and_plan(self.context, si)
        assert "plan:" in self.plan_text

        self.event_id = await adapter.create_platform_event(self.items[0], self.plan_text, self.context)
        assert self.event_id.startswith("evt-")

        self.event = await self.bb.get_event(self.event_id)
        assert self.event is not None

        self.header = build_event_header(self.event)
        assert self.event_id in self.header

        # Simulate Brain closing the event and Headhunter delivering feedback
        self.event.conversation.append(
            ConversationTurn(turn=1, actor="brain", action="close", result="Done", evidence="resolved")
        )
        await self.bb.save_event(self.event)
        await adapter.post_feedback(self.event)
        assert await self.bb.is_feedback_sent(self.event_id)

        self.snapshot = adapter.get_platform_snapshot()
        assert isinstance(self.snapshot, PlatformSnapshot)


# =============================================================================
# Layer 1: Domain Scenarios (T-19)
# =============================================================================


class TestHeadhunterMultiHeadContractT19:
    """Layer 1-4 ATDD contract scenarios across GitLab MR and GitHub PR heads."""

    @pytest.mark.asyncio
    async def test_t19a_gitlab_mr_end_to_end_pipeline_and_snapshot_contract(self):
        """Given mocked GitLab HTTP API + in-memory JSON-roundtripping Blackboard
        When poll_work_items -> fetch_context -> _build_analysis_prompt -> analyze_and_plan ->
             create_platform_event -> build_event_header -> post_feedback -> get_platform_snapshot execute
        Then all seams complete with zero key drift and live mr_sha + feedback persisted."""
        bb = InMemoryContractBlackboard()
        captured = {"requests": [], "posted_notes": [], "marked_done": []}
        transport = _make_gitlab_transport(captured)
        fake_client = httpx.AsyncClient(transport=transport)

        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=SimpleNamespace(
                text="---\nplan: \"Investigate MR !42\"\nrisk: low\nsteps:\n  - id: \"1\"\n    agent: developer\n    summary: \"Check CI\"\n---",
                usage=SimpleNamespace(input_tokens=10, output_tokens=10, total_tokens=20),
            )
        )

        with patch.dict(
            os.environ,
            {
                "HEADHUNTER_ENABLED": "true",
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_MAINTAINERS": "maint@example.com",
                "GCP_PROJECT": "test-proj",
            },
            clear=False,
        ):
            with patch("src.utils.vcs_approval.resolve_ca_bundle", return_value=True):
                hh = Headhunter(bb, gitlab_enabled=True)
                hh._adapter = mock_adapter
                hh._gitlab._get_token = MagicMock(return_value="fake-gl-token")
                hh._gitlab._client = fake_client

                dsl = MultiHeadContractDSL(bb, hh)
                try:
                    await dsl.execute_full_lifecycle(hh._gitlab)
                finally:
                    await fake_client.aclose()

        assert dsl.event is not None
        assert dsl.event.event.evidence.gitlab_context["mr_iid"] == 42
        assert dsl.event.event.evidence.gitlab_context["todo_id"] == 701
        assert "MR: !42" in dsl.header
        assert "Project: " in dsl.header
        assert captured["marked_done"] == [701]
        assert len(captured["posted_notes"]) == 1
        assert await bb.get_gitlab_mr_sha(100, 42) == "abc1234567890abcdef1234567890abcdef12345"
        assert dsl.snapshot is not None
        assert dsl.snapshot.platform == "gitlab"

    @pytest.mark.asyncio
    async def test_t19b_github_pr_end_to_end_pipeline_and_snapshot_contract(self):
        """Given mocked GitHub HTTP API + in-memory JSON-roundtripping Blackboard
        When poll_work_items -> fetch_context -> _build_analysis_prompt -> analyze_and_plan ->
             create_platform_event -> build_event_header -> post_feedback -> get_platform_snapshot execute
        Then all seams complete with zero key drift, label swaps, and pr_sha persistence."""
        bb = InMemoryContractBlackboard()
        captured = {"requests": [], "added_labels": [], "removed_labels": [], "posted_comments": []}
        transport = _make_github_transport(captured)
        fake_http = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

        async def _gh_get(url, **kw):
            return await fake_http.get(url, params=kw.get("params"))

        async def _gh_post(url, **kw):
            return await fake_http.post(url, json=kw.get("json"))

        async def _gh_delete(url, **kw):
            return await fake_http.delete(url)

        gh_client = MagicMock()
        gh_client.get = AsyncMock(side_effect=_gh_get)
        gh_client.post = AsyncMock(side_effect=_gh_post)
        gh_client.delete = AsyncMock(side_effect=_gh_delete)

        fake_manager = MagicMock()
        fake_manager.get_clients_with_repos = AsyncMock(return_value=[("inst-1", gh_client, ["org/repo"])])
        fake_manager.get_client_for_repo = AsyncMock(return_value=("inst-1", gh_client))
        fake_manager.get_client_for = AsyncMock(return_value=gh_client)

        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=SimpleNamespace(
                text="---\nplan: \"Review PR #77\"\nrisk: low\nsteps:\n  - id: \"1\"\n    agent: developer\n    summary: \"Review\"\n---",
                usage=SimpleNamespace(input_tokens=10, output_tokens=10, total_tokens=20),
            )
        )

        with patch.dict(
            os.environ,
            {
                "HEADHUNTER_GITHUB_ENABLED": "true",
                "HEADHUNTER_GITHUB_REPOS": "org/repo",
                "HEADHUNTER_MAINTAINERS": "maint@example.com",
                "GCP_PROJECT": "test-proj",
            },
            clear=False,
        ):
            hh = Headhunter(bb, gitlab_enabled=False)
            hh._adapter = mock_adapter
            hh._github._manager = fake_manager
            hh._github._repos = ["org/repo"]

            dsl = MultiHeadContractDSL(bb, hh)
            try:
                await dsl.execute_full_lifecycle(hh._github)
            finally:
                await fake_http.aclose()

        assert dsl.event is not None
        assert dsl.event.event.evidence.github_context["pr_number"] == 77
        assert "PR: #77" in dsl.header
        assert "Repo: org/repo" in dsl.header
        assert "darwin-active" in captured["added_labels"]
        assert "darwin-done" in captured["added_labels"]
        assert await bb.get_github_pr_sha("org", "repo", 77) == "11223344556677889900aabbccddeeff11223344"
        assert dsl.snapshot is not None
        assert dsl.snapshot.platform == "github"

    @pytest.mark.asyncio
    async def test_t19c_typed_vcs_models_and_legacy_redis_event_backward_compat(self):
        """Given canonical VcsWorkItem/VcsContext and legacy Redis EventDocument JSON (todo_id + issue body)
        When flowing through _build_analysis_prompt, analyze_and_plan, and build_event_header
        Then zero key drift occurs and legacy Redis payloads deserialize and render cleanly."""
        work_item = VcsWorkItem(
            platform="gitlab",
            item_kind="mr",
            item_id=42,
            project_ref="group/repo",
            title="Typed MR",
            author="alice",
            action="review_requested",
            ci_status="success",
            head_sha="abc123",
            url="https://gitlab.example.com/group/repo/-/merge_requests/42",
        )
        ctx = VcsContext(
            platform="gitlab",
            item_kind="mr",
            item_id=42,
            project_ref="group/repo",
            title=work_item.title,
            description="Typed description",
            author=work_item.author,
            source_branch="feat/a",
            target_branch="main",
            head_sha=work_item.head_sha,
            state="opened",
            ci_status="success",
            url=work_item.url,
            raw={"action_name": "review_requested", "merge_status": "can_be_merged"},
        )
        hh = Headhunter(MagicMock(), gitlab_enabled=False)
        prompt = hh._build_analysis_prompt(ctx)
        assert "MR: Typed MR" in prompt
        assert "Project: group/repo" in prompt
        assert "Typed description" in prompt

        legacy_json = json.dumps(
            {
                "id": "evt-legacy-01",
                "source": "headhunter",
                "service": "repo",
                "status": "active",
                "event": {
                    "reason": "Legacy plan",
                    "evidence": {
                        "display_text": "GitLab MR !12",
                        "source_type": "headhunter",
                        "domain": "complicated",
                        "severity": "info",
                        "gitlab_context": {
                            "todo_id": 555,
                            "project_id": 9,
                            "project_path": "org/legacy",
                            "mr_iid": 12,
                            "mr_title": "Legacy MR",
                            "mr_description": "Legacy body",
                            "author": "bob",
                            "pipeline_status": "success",
                        },
                    },
                },
            }
        )
        doc = EventDocument.model_validate_json(legacy_json)
        assert doc.approval_requested_sha is None
        assert doc.event.evidence.gitlab_context["todo_id"] == 555
        header = build_event_header(doc)
        assert "Legacy MR" in header
        assert "Legacy body" in header

        legacy_issue_json = json.dumps(
            {
                "id": "evt-legacy-issue-01",
                "source": "headhunter",
                "service": "BlackBoard",
                "subject_type": "github_issue",
                "status": "active",
                "event": {
                    "reason": "Legacy issue plan",
                    "evidence": {
                        "display_text": "GitHub Issue #233",
                        "source_type": "headhunter",
                        "domain": "complicated",
                        "severity": "info",
                        "github_issue_context": {
                            "owner": "The-Darwin-Project",
                            "repo": "BlackBoard",
                            "issue_number": 233,
                            "title": "Legacy Issue Title",
                            "body": "Legacy issue body text",
                            "author": "octocat",
                            "html_url": "https://github.com/The-Darwin-Project/BlackBoard/issues/233",
                        },
                    },
                },
            }
        )
        issue_doc = EventDocument.model_validate_json(legacy_issue_json)
        assert issue_doc.approval_requested_sha is None
        assert issue_doc.event.evidence.github_issue_context["body"] == "Legacy issue body text"
        issue_header = build_event_header(issue_doc)
        assert "GitHub Issue: #233" in issue_header
        assert "Legacy Issue Title" in issue_header
        assert "Legacy issue body text" in issue_header
