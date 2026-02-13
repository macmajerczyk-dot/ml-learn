"""Tests for the gateway API endpoints (mocked Kafka)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked Kafka producer."""
    with patch("services.gateway.app.create_producer") as mock_create_prod, \
         patch("services.gateway.app.create_consumer") as mock_create_cons:

        mock_producer = AsyncMock()
        mock_create_prod.return_value = mock_producer

        # Prevent the consumer background task from actually running
        mock_consumer = AsyncMock()
        mock_consumer.__aiter__ = AsyncMock(return_value=iter([]))
        mock_create_cons.return_value = mock_consumer

        import services.gateway.app as gateway_module
        from services.gateway.app import app, results_store

        # Inject mock producer
        gateway_module.producer = mock_producer

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_producer, results_store

        # Cleanup
        results_store.clear()
        gateway_module.producer = None


class TestHealthEndpoint:
    def test_health_with_producer(self, client):
        c, mock_producer, _ = client
        import services.gateway.app as gw
        gw.producer = mock_producer
        response = c.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "gateway"
        assert data["kafka_connected"] is True

    def test_health_without_producer(self, client):
        c, _, _ = client
        import services.gateway.app as gw
        gw.producer = None
        response = c.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["kafka_connected"] is False


class TestPredictEndpoint:
    def test_submit_prediction_success(self, client):
        c, mock_producer, _ = client
        mock_producer.send_and_wait = AsyncMock()
        response = c.post("/predict", json={"text": "This is great!"})
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert "request_id" in data

    def test_submit_prediction_empty_text(self, client):
        c, _, _ = client
        response = c.post("/predict", json={"text": ""})
        assert response.status_code == 422

    def test_get_result_pending(self, client):
        c, _, _ = client
        response = c.get("/predict/nonexistent-id")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    def test_get_result_completed(self, client):
        c, _, results_store = client
        results_store["test-id"] = {
            "request_id": "test-id",
            "label": "POSITIVE",
            "score": 0.95,
            "model_name": "test",
            "inference_time_ms": 10.0,
            "status": "completed",
        }
        response = c.get("/predict/test-id")
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "POSITIVE"
        assert data["score"] == 0.95


class TestMetricsEndpoint:
    def test_metrics_returns_prometheus_format(self, client):
        c, _, _ = client
        response = c.get("/metrics")
        assert response.status_code == 200
        assert "gateway_requests_total" in response.text
