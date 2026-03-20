# tests/test_models.py
# @ai-rules:
# 1. [Pattern]: Pydantic model validation tests. Add tests for each new model in src/models.py.
# 2. [Constraint]: Test both valid construction and schema generation for API contract stability.
import pytest
from src.models import HealthResponse


def test_health_response_valid():
    resp = HealthResponse(status="brain_online")
    assert resp.status == "brain_online"


def test_health_response_schema():
    schema = HealthResponse.model_json_schema()
    assert "status" in schema["properties"]
