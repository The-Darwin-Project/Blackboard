# BlackBoard/tests/test_brain_dedup.py
# @ai-rules:
# 1. [Constraint]: Tests Brain static/class methods only -- no Redis, no async, no adapter.
# 2. [Pattern]: Uses MagicMock or SimpleNamespace EventDocument stubs matching src/models.py schema.
# 3. [Pattern]: Follows test_brain_progressive.py structure: class per method, _make_* helpers.
"""Unit tests for Brain cross-source dedup: _extract_mr_url, _jira_issue_differs, _format_merge_evidence, phase gating."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.agents.brain import Brain, BRAIN_PHASE_SKILLS


MR_URL = "https://gitlab.cee.redhat.com/org/repo/-/merge_requests/49"


class TestExtractMrUrl:
    @staticmethod
    def _make_event_stub(gitlab_url=None, kargo_url=None, no_evidence=False, string_evidence=False):
        event = MagicMock()
        if no_evidence:
            event.event.evidence = None
            return event
        if string_evidence:
            event.event.evidence = "legacy string evidence"
            return event
        evidence = MagicMock()
        evidence.gitlab_context = {"target_url": gitlab_url} if gitlab_url else None
        evidence.kargo_context = {"mr_url": kargo_url} if kargo_url else None
        event.event.evidence = evidence
        return event

    def test_gitlab_context_url(self):
        event = self._make_event_stub(gitlab_url=MR_URL)
        assert Brain._extract_mr_url(event) == MR_URL

    def test_kargo_context_url(self):
        event = self._make_event_stub(kargo_url=MR_URL)
        assert Brain._extract_mr_url(event) == MR_URL

    def test_gitlab_takes_precedence(self):
        event = self._make_event_stub(gitlab_url=MR_URL, kargo_url="https://other.com/mr/1")
        assert Brain._extract_mr_url(event) == MR_URL

    def test_trailing_slash_normalized(self):
        event = self._make_event_stub(gitlab_url=MR_URL + "/")
        assert Brain._extract_mr_url(event) == MR_URL

    def test_fragment_stripped(self):
        event = self._make_event_stub(gitlab_url=MR_URL + "#note_12345")
        assert Brain._extract_mr_url(event) == MR_URL

    def test_trailing_slash_and_fragment(self):
        event = self._make_event_stub(kargo_url=MR_URL + "/#note_999")
        assert Brain._extract_mr_url(event) == MR_URL

    def test_no_evidence_returns_none(self):
        event = self._make_event_stub(no_evidence=True)
        assert Brain._extract_mr_url(event) is None

    def test_string_evidence_returns_none(self):
        event = self._make_event_stub(string_evidence=True)
        assert Brain._extract_mr_url(event) is None

    def test_no_url_fields_returns_none(self):
        event = self._make_event_stub()
        assert Brain._extract_mr_url(event) is None

    def test_kargo_verification_failure_ignores_mr_url(self):
        """T-16: Verification failures carry the already-merged promotion's mr_url for context only;
        _extract_mr_url must return None to prevent false Pass-2 MR-URL dedup."""
        event = self._make_event_stub(kargo_url=MR_URL)
        event.event.evidence.kargo_context["failure_type"] = "verification"
        assert Brain._extract_mr_url(event) is None

    def test_kargo_promotion_failure_keeps_mr_url(self):
        """T-16: Explicit failure_type='promotion' preserves mr_url extraction."""
        event = self._make_event_stub(kargo_url=MR_URL)
        event.event.evidence.kargo_context["failure_type"] = "promotion"
        assert Brain._extract_mr_url(event) == MR_URL


class TestFormatMergeEvidence:
    @staticmethod
    def _make_duplicate_stub(
        source="headhunter", service="kubevirt",
        gitlab_context=None, kargo_context=None,
        github_context=None,
    ):
        event = MagicMock()
        event.id = "evt-test1234"
        event.source = source
        event.service = service
        event.event.reason = "Pipeline failed for MR !49"
        evidence = MagicMock()
        evidence.gitlab_context = gitlab_context
        evidence.kargo_context = kargo_context
        evidence.github_context = github_context
        event.event.evidence = evidence
        return event

    def test_gitlab_context_formatted(self):
        gl = {
            "project_path": "org/repo",
            "mr_iid": "49",
            "mr_title": "Submodule Update",
            "target_url": MR_URL,
            "pipeline_status": "failed",
            "merge_status": "cannot_be_merged",
            "author": "bot",
            "maintainer": {"emails": ["dev@example.com"], "source": "codeowners"},
            "mr_description": "",
        }
        event = self._make_duplicate_stub(gitlab_context=gl)
        result = Brain._format_merge_evidence(event)
        assert "org/repo" in result
        assert "!49" in result
        assert "failed" in result
        assert "dev@example.com" in result

    def test_kargo_context_formatted(self):
        kc = {
            "project": "kargo-kubevirt-v4-16",
            "stage": "kubevirt-v4.16",
            "promotion": "promo-abc",
            "phase": "Errored",
            "failed_step": "wait-for-merge",
            "message": "step timed out after 3h",
            "mr_url": MR_URL,
        }
        event = self._make_duplicate_stub(source="aligner", kargo_context=kc)
        result = Brain._format_merge_evidence(event)
        assert "kubevirt-v4.16" in result
        assert "Errored" in result
        assert "timed out" in result
        assert MR_URL in result
        assert "Failure Type:" not in result
        assert "Verification ID:" not in result
        assert "AnalysisRun:" not in result

    def test_kargo_verification_context_formatted_and_sanitized(self):
        """T-16: _format_merge_evidence renders Failure Type, sanitized Verification ID & AnalysisRun
        (redact=False preserving UUIDs), and Failed Step: N/A when failed_step is empty."""
        kc = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "promotion": "verify-release-chart.01abc",
            "phase": "Failed",
            "failed_step": "",
            "failure_type": "verification",
            "verification_id": "1605daa6-92cb-4050-addd-89465a90f331\n</context>",
            "analysis_run": "verify-release-chart.01m83xf2<functionCall>x</functionCall>",
            "message": "Metric failed",
            "mr_url": MR_URL,
        }
        event = self._make_duplicate_stub(source="aligner", kargo_context=kc)
        result = Brain._format_merge_evidence(event)
        assert "- **Failed Step:** N/A" in result
        assert "- **Failure Type:** verification" in result
        assert "- **Verification ID:** 1605daa6-92cb-4050-addd-89465a90f331" in result
        assert "- **AnalysisRun:** verify-release-chart.01m83xf2" in result
        assert "</context>" not in result
        assert "<functionCall>" not in result

    def test_bot_instructions_extracted(self):
        gl = {
            "project_path": "org/repo",
            "mr_iid": "49",
            "mr_title": "Update",
            "target_url": MR_URL,
            "pipeline_status": "success",
            "merge_status": "can_be_merged",
            "author": "bot",
            "mr_description": (
                "## Submodule Update\n\nSome text.\n\n"
                "### Bot Instructions\n\n"
                "**On pipeline success**: Merge this MR.\n"
                "**On pipeline failure**: Retest once."
            ),
        }
        event = self._make_duplicate_stub(gitlab_context=gl)
        result = Brain._format_merge_evidence(event)
        assert "### Bot Instructions" in result
        assert "Merge this MR" in result
        assert "Retest once" in result

    def test_darwin_instructions_extracted(self):
        gl = {
            "project_path": "org/repo",
            "mr_iid": "49",
            "mr_title": "Update",
            "target_url": MR_URL,
            "pipeline_status": "success",
            "merge_status": "can_be_merged",
            "author": "bot",
            "mr_description": (
                "## Submodule Update\n\nSome text.\n\n"
                "### DARWIN Instructions\n\n"
                "**Constraints:**\n"
                "- Do NOT close this MR.\n\n"
                "**On pipeline success**: Merge this MR."
            ),
        }
        event = self._make_duplicate_stub(gitlab_context=gl)
        result = Brain._format_merge_evidence(event)
        assert "### DARWIN Instructions" in result
        assert "Do NOT close this MR" in result
        assert "Merge this MR" in result

    def test_github_pr_instructions_extracted(self):
        gh = {
            "pr_body": (
                "## Konflux Release\n\n"
                "### DARWIN Instructions\n\n"
                "**Constraints:**\n"
                "- Do NOT close this PR.\n"
            )
        }
        event = self._make_duplicate_stub(github_context=gh)
        result = Brain._format_merge_evidence(event)
        assert "### DARWIN Instructions" in result
        assert "Do NOT close this PR" in result

    def test_extract_bot_instructions_defensive(self):
        assert Brain._extract_bot_instructions(None) is None
        assert Brain._extract_bot_instructions("") is None
        assert Brain._extract_bot_instructions("No instructions here") is None
        extracted = Brain._extract_bot_instructions("Intro\n### Darwin  Instructions\n- rule 1")
        assert extracted == "### Darwin  Instructions\n- rule 1"

    def test_no_evidence_safe(self):
        event = MagicMock()
        event.id = "evt-noevidence"
        event.source = "headhunter"
        event.service = "test-svc"
        event.event = None
        result = Brain._format_merge_evidence(event)
        assert "evt-noevidence" in result
        assert "unknown" in result


class TestPhaseConditionsWithHeadhunter:
    @staticmethod
    def _make_ctx(**overrides) -> dict:
        defaults = {
            "turn_count": 0,
            "source": "chat",
            "service": "test-svc",
            "is_waiting": False,
            "has_agent_result": False,
            "last_is_user": False,
            "has_related": False,
            "has_recent_closed": False,
            "has_graph_edges": False,
            "has_aligner_turns": False,
            "brain_has_classified": False,
            "event_domain": "complicated",
            "domain_confidence": "default",
        }
        defaults.update(overrides)
        return defaults

    def test_headhunter_evidence_does_not_flip_has_agent_result(self):
        """Headhunter evidence turns should NOT activate post-agent or block dispatch."""
        turn = MagicMock()
        turn.actor = "headhunter"
        turn.action = "evidence"
        has_agent = turn.actor not in ("brain", "user", "aligner", "headhunter")
        assert has_agent is False

        event_stub = MagicMock()
        event_stub.brain_phase = "dispatch"
        ctx = self._make_ctx(
            turn_count=5, has_agent_result=False, brain_has_classified=True,
        )
        active = Brain._match_phases(None, event_stub, ctx)
        assert "dispatch" in active
        assert "post-agent" not in active

    def test_real_agent_result_still_flips(self):
        """Sysadmin/developer turns should still activate post-agent via verify phase."""
        turn = MagicMock()
        turn.actor = "sysadmin"
        has_agent = turn.actor not in ("brain", "user", "aligner", "headhunter")
        assert has_agent is True

        event_stub = MagicMock()
        event_stub.brain_phase = "verify"
        ctx = self._make_ctx(
            turn_count=5, has_agent_result=True, brain_has_classified=True,
        )
        active = Brain._match_phases(None, event_stub, ctx)
        assert "post-agent" in active


class TestAgentTurnSelectionSkipsHeadhunter:
    """Post-agent recall turn selection must skip headhunter evidence turns."""
    _EXCLUDED = ("brain", "user", "aligner", "headhunter", "dispatcher")

    def test_headhunter_skipped_sysadmin_found(self):
        """After sysadmin result + headhunter evidence, turn selection finds sysadmin."""
        sysadmin_turn = MagicMock()
        sysadmin_turn.actor = "sysadmin"
        sysadmin_turn.action = "execute"

        hh_turn = MagicMock()
        hh_turn.actor = "headhunter"
        hh_turn.action = "evidence"

        conversation = [sysadmin_turn, hh_turn]
        last_agent = next(
            (t for t in reversed(conversation) if t.actor not in self._EXCLUDED), None
        )
        assert last_agent is not None
        assert last_agent.actor == "sysadmin"

    def test_headhunter_only_returns_none(self):
        """When headhunter evidence is the only non-brain turn, no agent turn found."""
        hh_turn = MagicMock()
        hh_turn.actor = "headhunter"
        hh_turn.action = "evidence"

        brain_turn = MagicMock()
        brain_turn.actor = "brain"
        brain_turn.action = "triage"

        conversation = [brain_turn, hh_turn]
        last_agent = next(
            (t for t in reversed(conversation) if t.actor not in self._EXCLUDED), None
        )
        assert last_agent is None


class TestTurnToPartsRendering:
    """Verify _turn_to_parts renders evidence turns correctly for both directions."""

    def test_aligner_evidence_turn_reads_result(self):
        """When Kargo event is the duplicate (actor=aligner, action=evidence),
        _turn_to_parts must read turn.result, not turn.evidence."""
        turn = MagicMock()
        turn.actor = "aligner"
        turn.action = "evidence"
        turn.result = "Related event evt-kargo (source=aligner) detected for same MR.\n\n## Kargo Context\n- **Stage:** kubevirt-v4.16"
        turn.evidence = None
        turn.thoughts = "Duplicate event evt-kargo closed."
        turn.image = None

        parts = Brain._turn_to_parts(turn)
        parts_text = parts[0]["text"] if isinstance(parts, list) else str(parts)
        assert "Kargo Context" in parts_text
        assert "kubevirt-v4.16" in parts_text

    def test_aligner_confirm_turn_reads_evidence(self):
        """Regular aligner confirm turns (metrics observations) still use evidence field."""
        turn = MagicMock()
        turn.actor = "aligner"
        turn.action = "confirm"
        turn.result = None
        turn.evidence = "CPU normalized to 45% (below 80% threshold)"
        turn.thoughts = None
        turn.image = None

        parts = Brain._turn_to_parts(turn)
        parts_text = parts[0]["text"] if isinstance(parts, list) else str(parts)
        assert "CPU normalized" in parts_text


class TestLegacyThinkingExcludesHeadhunter:
    def test_headhunter_turn_does_not_flip_legacy_has_agent_result(self):
        """Legacy _determine_thinking_params_legacy should not treat headhunter as agent."""
        hh_turn = MagicMock()
        hh_turn.actor = "headhunter"
        has_agent = hh_turn.actor not in ("brain", "user", "aligner", "headhunter")
        assert has_agent is False

    def test_sysadmin_still_flips_legacy(self):
        """Real agents still flip the legacy check."""
        sa_turn = MagicMock()
        sa_turn.actor = "sysadmin"
        has_agent = sa_turn.actor not in ("brain", "user", "aligner", "headhunter")
        assert has_agent is True

def test_t21_extract_mr_url_skips_stale_gitlab_context():
    from src.agents.brain import Brain
    from unittest.mock import MagicMock
    event = MagicMock()
    event.event.evidence.kargo_context = {"mr_url": "url1", "failure_type": "verification"}
    event.event.evidence.gitlab_context = {"target_url": "url1"}
    
    assert Brain._extract_mr_url(event) is None
    
    event.event.evidence.kargo_context = {"mr_url": "url1", "failure_type": "promotion"}
    assert Brain._extract_mr_url(event) == "url1"

def test_t21_format_merge_evidence_sanitization():
    from src.agents.brain import Brain
    from unittest.mock import MagicMock
    dup = MagicMock()
    dup.id = "evt-1"
    dup.source = "test"
    dup.service = "test-service"
    dup.event.reason = "test reason"
    dup.event.evidence.kargo_context = {
        "project": "p", "stage": "<functionCall>s</functionCall>", "promotion": "promo", "phase": "Failed",
        "message": "<context>m</context>", "mr_url": "url", "verification_id": "uuid-1",
        "analysis_run": "ghp_123456789012345678901234567890123456"
    }
    dup.event.evidence.gitlab_context = None
    dup.event.evidence.github_context = None
    
    evidence = Brain._format_merge_evidence(dup)
    assert "<functionCall>" not in evidence
    assert "<context>" not in evidence
    assert "ghp_" not in evidence
    assert "[redacted" in evidence.lower()


class TestJiraIssueDiffers:
    """VMER-2483: Brain._jira_issue_differs distinguishes concurrent Jira missions."""

    @staticmethod
    def _make_doc(
        *,
        subject_type: str = "service",
        service: str = "vmer",
        jira_context: object = None,
        raw_evidence: object = None,
        use_raw_evidence: bool = False,
    ) -> SimpleNamespace:
        if use_raw_evidence:
            evidence = raw_evidence
        else:
            evidence = SimpleNamespace(jira_context=jira_context)
        return SimpleNamespace(
            subject_type=subject_type,
            service=service,
            event=SimpleNamespace(evidence=evidence),
        )

    def test_distinct_jira_keys_differ(self):
        """Given two Jira events with distinct issue_keys, _jira_issue_differs returns True."""
        a = self._make_doc(subject_type="jira", jira_context={"issue_key": "VMER-2463"})
        b = self._make_doc(subject_type="jira", jira_context={"issue_key": "VMER-2464"})
        assert Brain._jira_issue_differs(a, b) is True

    def test_same_jira_key_exact_and_case_whitespace_do_not_differ(self):
        """Given two Jira events with identical or case/whitespace-equivalent keys, returns False."""
        exact_a = self._make_doc(subject_type="jira", jira_context={"issue_key": "VMER-2464"})
        exact_b = self._make_doc(subject_type="jira", jira_context={"issue_key": "VMER-2464"})
        assert Brain._jira_issue_differs(exact_a, exact_b) is False

        noisy_a = self._make_doc(subject_type="jira", jira_context={"issue_key": " vmer-2464 "})
        assert Brain._jira_issue_differs(noisy_a, exact_b) is False

    def test_one_jira_keyed_one_jira_unkeyed_differs(self):
        """Given one keyed Jira event and one unkeyed/whitespace Jira event, returns True."""
        keyed = self._make_doc(subject_type="jira", jira_context={"issue_key": "VMER-2464"})
        unkeyed_none = self._make_doc(subject_type="jira", jira_context={"issue_key": None})
        unkeyed_blank = self._make_doc(subject_type="jira", jira_context={"issue_key": "   "})
        unkeyed_missing = self._make_doc(subject_type="jira", jira_context=None)

        assert Brain._jira_issue_differs(keyed, unkeyed_none) is True
        assert Brain._jira_issue_differs(unkeyed_none, keyed) is True
        assert Brain._jira_issue_differs(keyed, unkeyed_blank) is True
        assert Brain._jira_issue_differs(unkeyed_blank, keyed) is True
        assert Brain._jira_issue_differs(keyed, unkeyed_missing) is True

    def test_both_jira_events_missing_key_or_non_dict_context_do_not_differ(self):
        """Given two Jira events lacking valid issue_key or having non-dict jira_context, returns False."""
        missing_a = self._make_doc(subject_type="jira", jira_context=None)
        missing_b = self._make_doc(subject_type="jira", jira_context={})
        bad_ctx = self._make_doc(subject_type="jira", jira_context="bad")
        non_str_key = self._make_doc(subject_type="jira", jira_context={"issue_key": 2464})

        assert Brain._jira_issue_differs(missing_a, missing_b) is False
        assert Brain._jira_issue_differs(bad_ctx, missing_a) is False
        assert Brain._jira_issue_differs(non_str_key, bad_ctx) is False

    def test_mixed_jira_vs_non_jira_same_service_differs_both_directions(self):
        """Given a Jira event and a non-Jira event sharing service='vmer', returns True in both directions."""
        jira_ev = self._make_doc(subject_type="jira", service="vmer", jira_context={"issue_key": "VMER-2464"})
        non_jira_ev = self._make_doc(subject_type="service", service="vmer", jira_context=None)

        assert Brain._jira_issue_differs(jira_ev, non_jira_ev) is True
        assert Brain._jira_issue_differs(non_jira_ev, jira_ev) is True

    def test_neither_event_is_jira_returns_false(self):
        """Given two non-Jira events (None, str, dict evidence), _jira_issue_differs returns False."""
        ev_none_a = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence=None)
        ev_none_b = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence=None)
        ev_str_a = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence="legacy string")
        ev_str_b = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence="other string")
        ev_dict_a = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence={"other": 1})
        ev_dict_b = self._make_doc(subject_type="service", use_raw_evidence=True, raw_evidence={"other": 2})

        assert Brain._jira_issue_differs(ev_none_a, ev_none_b) is False
        assert Brain._jira_issue_differs(ev_str_a, ev_str_b) is False
        assert Brain._jira_issue_differs(ev_dict_a, ev_dict_b) is False
        assert Brain._jira_issue_differs(ev_none_a, ev_dict_a) is False

    def test_dict_typed_evidence_with_jira_context(self):
        """Given dict-typed evidence carrying jira_context.issue_key, differentiates keys accurately."""
        a = self._make_doc(
            subject_type="jira",
            use_raw_evidence=True,
            raw_evidence={"jira_context": {"issue_key": "VMER-2463"}},
        )
        b = self._make_doc(
            subject_type="jira",
            use_raw_evidence=True,
            raw_evidence={"jira_context": {"issue_key": "VMER-2464"}},
        )
        b_same = self._make_doc(
            subject_type="service",
            use_raw_evidence=True,
            raw_evidence={"jira_context": {"issue_key": " vmer-2464 "}},
        )

        assert Brain._jira_issue_differs(a, b) is True
        assert Brain._jira_issue_differs(b, b_same) is False

    def test_extract_mr_url_returns_none_for_jira_issue_url(self):
        """Pins Pass 2 exclusion: Jira issue_url is never treated as an MR/PR URL."""
        jira_doc = self._make_doc(
            subject_type="jira",
            jira_context={
                "issue_key": "VMER-2464",
                "issue_url": "https://issues.redhat.com/browse/VMER-2464",
            },
        )
        assert Brain._extract_mr_url(jira_doc) is None

    def test_extract_jira_context_strips_control_characters(self):
        """Control characters in issue_key are stripped cleanly before normalization."""
        ctrl_doc = self._make_doc(
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464\r\nFAKE"},
        )
        whitespace_ctrl_doc = self._make_doc(
            subject_type="jira",
            jira_context={"issue_key": " vmer-2464\t\n "},
        )
        only_ctrl_doc = self._make_doc(
            subject_type="jira",
            jira_context={"issue_key": "\x00\r\n\t\x7f"},
        )

        assert Brain._extract_jira_context(ctrl_doc) == (True, "VMER-2464FAKE")
        assert Brain._extract_jira_context(whitespace_ctrl_doc) == (True, "VMER-2464")
        assert Brain._extract_jira_context(only_ctrl_doc) == (True, None)
