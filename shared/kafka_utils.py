"""Kafka producer/consumer helpers with retry logic and health checks."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from shared.logging_config import get_logger

logger = get_logger(__name__)

TOPIC_PREDICTION_REQUESTS = "ml.prediction.requests"
TOPIC_PREDICTION_RESULTS = "ml.prediction.results"


async def create_producer(
    bootstrap_servers: str,
    max_retries: int = 10,
    retry_delay: float = 3.0,
) -> AIOKafkaProducer:
    """Create a Kafka producer with retry logic for startup resilience."""
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        enable_idempotence=True,
        max_request_size=1_048_576,
    )
    for attempt in range(1, max_retries + 1):
        try:
            await producer.start()
            logger.info("kafka_producer_connected", attempt=attempt)
            return producer
        except Exception as exc:
            logger.warning(
                "kafka_producer_retry",
                attempt=attempt,
                max_retries=max_retries,
                error=str(exc),
            )
            if attempt == max_retries:
                raise
            await asyncio.sleep(retry_delay)
    raise RuntimeError("Failed to create Kafka producer")


async def create_consumer(
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    max_retries: int = 10,
    retry_delay: float = 3.0,
) -> AIOKafkaConsumer:
    """Create a Kafka consumer with retry logic for startup resilience."""
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=10,
    )
    for attempt in range(1, max_retries + 1):
        try:
            await consumer.start()
            logger.info("kafka_consumer_connected", topic=topic, attempt=attempt)
            return consumer
        except Exception as exc:
            logger.warning(
                "kafka_consumer_retry",
                attempt=attempt,
                max_retries=max_retries,
                error=str(exc),
            )
            if attempt == max_retries:
                raise
            await asyncio.sleep(retry_delay)
    raise RuntimeError("Failed to create Kafka consumer")


async def produce_message(
    producer: AIOKafkaProducer,
    topic: str,
    key: str,
    value: dict[str, Any],
) -> None:
    """Send a message to a Kafka topic."""
    await producer.send_and_wait(topic=topic, key=key, value=value)
    logger.debug("message_produced", topic=topic, key=key)
