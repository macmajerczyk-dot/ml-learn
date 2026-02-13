"""Gateway service configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    service_name: str = "gateway"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_producer_retries: int = 10

    # Rate limiting
    max_requests_per_minute: int = 60

    model_config = {"env_prefix": "GW_"}


settings = GatewaySettings()
