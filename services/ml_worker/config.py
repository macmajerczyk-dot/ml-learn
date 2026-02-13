"""ML worker service configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    service_name: str = "ml-worker"
    version: str = "0.1.0"
    log_level: str = "INFO"

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "ml-worker-group"
    kafka_consumer_retries: int = 10

    # Model configuration
    model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"
    model_device: str = "cpu"  # "cpu" or "cuda"
    model_max_length: int = 512
    model_batch_size: int = 8

    # Metrics server
    metrics_port: int = 8001

    model_config = {"env_prefix": "MLW_"}


settings = WorkerSettings()
