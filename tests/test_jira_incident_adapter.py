# tests/test_jira_incident_adapter.py
# @ai-rules:
# 1. [Pattern]: All Jira API calls mocked via httpx_mock. No live network.
# 2. [Pattern]: Tests verify JQL construction, field mapping, auth, and error handling.
"""Unit tests for JiraIncidentAdapter."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.adapters.jira_incident import JiraIncidentAdapter, _adf_to_text


@pytest.fixture
def adapter():
    return JiraIncidentAdapter(
        base_url="https://jira.example.com",
        email="test@example.com",
        api_token="tok",
        project_key="TEST",
        platforms=["OCP", "CNV"],
    )


class TestAdfToText:
    def test_simple_text(self):
        assert _adf_to_text({"type": "text", "text": "hello"}) == "hello"

    def test_nested_doc(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "line1"}]}],
        }
        assert "line1" in _adf_to_text(adf)

    def test_empty_doc(self):
        assert _adf_to_text({}) == ""


class TestCreateIncident:
    @pytest.mark.asyncio
    async def test_field_mapping(self, adapter):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"key": "TEST-1"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await adapter.create_incident({
                "project_key": "TEST",
                "issue_type": "Incident",
                "summary": "Test incident",
                "description": "Details",
                "priority": "Major",
                "labels": ["darwin-auto"],
                "components": ["Incidents"],
                "platform": "OCP",
                "severity": "Critical",
                "severity_field_id": "customfield_10840",
            })
            assert result["issue_key"] == "TEST-1"
            assert "browse/TEST-1" in result["issue_url"]

            call_json = mock_client.post.call_args[1]["json"]
            fields = call_json["fields"]
            assert fields["project"]["key"] == "TEST"
            assert fields["issuetype"]["name"] == "Incident"
            assert fields["summary"] == "Test incident"
            assert fields["priority"]["name"] == "Major"
            assert "OCP" in fields["labels"]
            assert "darwin-auto" in fields["labels"]
            assert fields["customfield_10840"] == {"value": "Critical"}

    @pytest.mark.asyncio
    async def test_empty_project_key_raises(self, adapter):
        adapter._project_key = ""
        with pytest.raises(ValueError, match="project_key"):
            await adapter.create_incident({"summary": "test"})


class TestPlatformExtraction:
    def test_platform_intersection(self, adapter):
        issue = {
            "key": "TEST-1",
            "fields": {
                "summary": "test",
                "status": {"name": "New"},
                "priority": {"name": "Normal"},
                "labels": ["darwin-auto", "OCP", "custom-label"],
                "components": [],
                "created": "2026-01-01",
            },
        }
        result = adapter._normalize_issue(issue)
        assert result["platform"] == "OCP"

    def test_no_platform_match(self, adapter):
        issue = {
            "key": "TEST-2",
            "fields": {
                "summary": "test",
                "status": {"name": "New"},
                "priority": {"name": "Normal"},
                "labels": ["darwin-auto", "custom-label"],
                "components": [],
                "created": "2026-01-01",
            },
        }
        result = adapter._normalize_issue(issue)
        assert result["platform"] == ""


class TestSearchOpenIncidents:
    @pytest.mark.asyncio
    async def test_returns_normalized(self, adapter):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {
            "issues": [{
                "key": "TEST-5",
                "fields": {
                    "summary": "open inc",
                    "status": {"name": "New"},
                    "priority": {"name": "Major"},
                    "labels": ["darwin-auto"],
                    "components": [],
                    "created": "2026-01-01",
                },
            }],
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await adapter.search_open_incidents()
            assert len(results) == 1
            assert results[0]["issue_key"] == "TEST-5"


class TestAddComment:
    @pytest.mark.asyncio
    async def test_returns_comment_id(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "10001"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await adapter.add_comment("TEST-5", "New evidence here")
            assert result["comment_id"] == "10001"
            assert "browse/TEST-5" in result["issue_url"]


class TestAuthHeaders:
    def test_basic_auth_header(self, adapter):
        assert "Authorization" in adapter._headers
        assert adapter._headers["Authorization"].startswith("Basic ")


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_create_raises_on_4xx(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_resp.raise_for_status.side_effect = Exception("400")

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(Exception):
                await adapter.create_incident({
                    "project_key": "TEST",
                    "issue_type": "Incident",
                    "summary": "test",
                })
