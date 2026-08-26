# tests/test_maintainer_resolution.py
# @ai-rules:
# 1. [Pattern]: Minimal EventDocument/EventEvidence stubs via SimpleNamespace, matching
#    the pattern in test_brain_prompt_assembly.py. context dicts stay plain dicts (matches
#    the actual EventEvidence.ci_context/gitlab_context/github_context field types).
"""Regression coverage for shared maintainer-email resolution.

PR #210 codereview findings covered here:
- HIGH: Brain._resolve_maintainer_enum read subject_type off the evidence object
  instead of the EventDocument, so the JENKINS_OBSERVER_MAINTAINERS fallback for
  ci_gating events never fired.
- HIGH: handlers_integration._resolve_maintainer_enum was a stale duplicate with no
  ci_context branch at all -- Slack-notify fallback always used HEADHUNTER_MAINTAINERS.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.utils.maintainers import maintainer_env_key, resolve_maintainer_emails


def _make_event(subject_type="service", slack_user_id=None, **contexts):
    evidence = SimpleNamespace(
        gitlab_context=contexts.get("gitlab_context"),
        github_context=contexts.get("github_context"),
        ci_context=contexts.get("ci_context"),
    )
    inner_event = SimpleNamespace(evidence=evidence)
    return SimpleNamespace(
        subject_type=subject_type,
        slack_user_id=slack_user_id,
        event=inner_event,
    )


class TestMaintainerEnvKey:
    def test_ci_gating_selects_jenkins_observer_maintainers(self):
        assert maintainer_env_key("ci_gating") == "JENKINS_OBSERVER_MAINTAINERS"

    def test_other_subject_types_select_headhunter_maintainers(self):
        assert maintainer_env_key("service") == "HEADHUNTER_MAINTAINERS"
        assert maintainer_env_key(None) == "HEADHUNTER_MAINTAINERS"


class TestResolveMaintainerEmails:
    def test_ci_context_emails_used_when_present(self):
        event = _make_event(
            subject_type="ci_gating",
            ci_context={"maintainer": {"source": "static", "emails": ["ci@example.com"]}},
        )
        assert resolve_maintainer_emails(event) == ["ci@example.com"]

    def test_gitlab_context_takes_precedence_over_ci_context(self):
        event = _make_event(
            subject_type="ci_gating",
            gitlab_context={"maintainer": {"emails": ["gl@example.com"]}},
            ci_context={"maintainer": {"emails": ["ci@example.com"]}},
        )
        assert resolve_maintainer_emails(event) == ["gl@example.com"]

    def test_falls_back_to_jenkins_observer_maintainers_env_for_ci_gating(self, monkeypatch):
        monkeypatch.setenv("JENKINS_OBSERVER_MAINTAINERS", "jenkins-maint@example.com")
        monkeypatch.setenv("HEADHUNTER_MAINTAINERS", "headhunter-maint@example.com")
        event = _make_event(subject_type="ci_gating")
        assert resolve_maintainer_emails(event) == ["jenkins-maint@example.com"]

    def test_falls_back_to_headhunter_maintainers_env_for_other_subject_types(self, monkeypatch):
        monkeypatch.setenv("JENKINS_OBSERVER_MAINTAINERS", "jenkins-maint@example.com")
        monkeypatch.setenv("HEADHUNTER_MAINTAINERS", "headhunter-maint@example.com")
        event = _make_event(subject_type="service")
        assert resolve_maintainer_emails(event) == ["headhunter-maint@example.com"]

    def test_slack_user_id_appended_and_deduped(self, monkeypatch):
        monkeypatch.setenv("JENKINS_OBSERVER_MAINTAINERS", "")
        monkeypatch.setenv("HEADHUNTER_MAINTAINERS", "")
        event = _make_event(
            subject_type="ci_gating",
            slack_user_id="U123",
            ci_context={"maintainer": {"emails": ["ci@example.com", "U123"]}},
        )
        assert resolve_maintainer_emails(event) == ["ci@example.com", "U123"]


class TestCallSiteParity:
    """Both call sites must delegate to the same resolver (no drifted duplicates)."""

    def test_brain_resolver_matches_shared_helper(self, monkeypatch):
        monkeypatch.setenv("JENKINS_OBSERVER_MAINTAINERS", "jenkins-maint@example.com")
        event = _make_event(subject_type="ci_gating")

        from src.agents.brain import Brain

        assert Brain._resolve_maintainer_enum(event) == resolve_maintainer_emails(event)
        assert Brain._resolve_maintainer_enum(event) == ["jenkins-maint@example.com"]

    def test_handlers_integration_resolver_matches_shared_helper(self, monkeypatch):
        monkeypatch.setenv("JENKINS_OBSERVER_MAINTAINERS", "jenkins-maint@example.com")
        event = _make_event(
            subject_type="ci_gating",
            ci_context={"maintainer": {"emails": ["ci@example.com"]}},
        )

        from src.agents.handlers_integration import _resolve_maintainer_enum

        # Regression: this duplicate previously had no ci_context branch at all,
        # so it always fell through to HEADHUNTER_MAINTAINERS regardless of source data.
        assert _resolve_maintainer_enum(event) == ["ci@example.com"]
        assert _resolve_maintainer_enum(event) == resolve_maintainer_emails(event)
