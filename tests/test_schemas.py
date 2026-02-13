"""Tests for shared Pydantic schemas."""

import pytest
from pydantic import ValidationError

from shared.schemas import (
    HealthResponse,
    PredictionRequest,
    PredictionResult,
    TaskStatus,
)


class TestPredictionRequest:
    def test_valid_request(self):
        req = PredictionRequest(text="Hello world")
        assert req.text == "Hello world"
        assert req.request_id  # auto-generated UUID
        assert req.created_at  # auto-generated timestamp

    def test_custom_request_id(self):
        req = PredictionRequest(text="test", request_id="custom-id")
        assert req.request_id == "custom-id"

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            PredictionRequest(text="")

    def test_text_too_long_rejected(self):
        with pytest.raises(ValidationError):
            PredictionRequest(text="x" * 5001)

    def test_serialization_roundtrip(self):
        req = PredictionRequest(text="roundtrip test")
        data = req.model_dump()
        restored = PredictionRequest(**data)
        assert restored.text == req.text
        assert restored.request_id == req.request_id


class TestPredictionResult:
    def test_valid_result(self):
        result = PredictionResult(
            request_id="abc-123",
            label="POSITIVE",
            score=0.98,
            model_name="test-model",
            inference_time_ms=42.5,
        )
        assert result.status == TaskStatus.COMPLETED
        assert result.label == "POSITIVE"
        assert result.score == 0.98

    def test_failed_result(self):
        result = PredictionResult(
            request_id="abc-123",
            label="ERROR",
            score=0.0,
            model_name="test-model",
            inference_time_ms=0.0,
            status=TaskStatus.FAILED,
        )
        assert result.status == TaskStatus.FAILED


class TestHealthResponse:
    def test_healthy(self):
        resp = HealthResponse(
            service="gateway",
            status="healthy",
            version="0.1.0",
            kafka_connected=True,
        )
        assert resp.kafka_connected is True

    def test_degraded(self):
        resp = HealthResponse(
            service="gateway",
            status="degraded",
            version="0.1.0",
            kafka_connected=False,
        )
        assert resp.status == "degraded"
