"""Prometheus metrics for the ML worker service."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

MESSAGES_CONSUMED = Counter(
    "worker_messages_consumed_total",
    "Total messages consumed from Kafka",
    ["topic"],
)

INFERENCE_COUNT = Counter(
    "worker_inference_total",
    "Total inference requests processed",
    ["status"],
)

INFERENCE_LATENCY = Histogram(
    "worker_inference_latency_seconds",
    "Model inference latency in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

MODEL_LOAD_TIME = Gauge(
    "worker_model_load_time_seconds",
    "Time taken to load the ML model",
)

RESULTS_PRODUCED = Counter(
    "worker_results_produced_total",
    "Total results produced to Kafka",
    ["topic"],
)

PROCESSING_ERRORS = Counter(
    "worker_processing_errors_total",
    "Total processing errors",
    ["error_type"],
)
