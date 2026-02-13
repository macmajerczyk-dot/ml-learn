"""Prometheus metrics for the gateway service."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "gateway_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

KAFKA_MESSAGES_PRODUCED = Counter(
    "gateway_kafka_messages_produced_total",
    "Total messages produced to Kafka",
    ["topic"],
)

KAFKA_PRODUCE_ERRORS = Counter(
    "gateway_kafka_produce_errors_total",
    "Total Kafka produce errors",
    ["topic"],
)

ACTIVE_CONNECTIONS = Gauge(
    "gateway_active_connections",
    "Number of active HTTP connections",
)

RESULTS_RECEIVED = Counter(
    "gateway_results_received_total",
    "Total prediction results consumed from Kafka",
    ["status"],
)
