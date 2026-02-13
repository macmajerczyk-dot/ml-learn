"""ML worker — consumes prediction requests from Kafka, runs inference,
and publishes results back to Kafka."""

from __future__ import annotations

import asyncio
import time

from prometheus_client import start_http_server

from services.ml_worker.config import settings
from services.ml_worker.metrics import (
    INFERENCE_COUNT,
    INFERENCE_LATENCY,
    MESSAGES_CONSUMED,
    PROCESSING_ERRORS,
    RESULTS_PRODUCED,
)
from services.ml_worker.model import SentimentModel
from shared.kafka_utils import (
    TOPIC_PREDICTION_REQUESTS,
    TOPIC_PREDICTION_RESULTS,
    create_consumer,
    create_producer,
    produce_message,
)
from shared.logging_config import get_logger, setup_logging
from shared.schemas import PredictionRequest, PredictionResult, TaskStatus

logger = get_logger(__name__)


async def run_worker() -> None:
    """Main worker loop: consume → infer → produce."""
    setup_logging(settings.service_name, settings.log_level)
    logger.info("worker_starting", version=settings.version)

    # Start Prometheus metrics server in a background thread
    start_http_server(settings.metrics_port)
    logger.info("metrics_server_started", port=settings.metrics_port)

    # Load model (synchronous, runs once)
    model = SentimentModel()
    model.load()

    # Connect to Kafka
    consumer = await create_consumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=TOPIC_PREDICTION_REQUESTS,
        group_id=settings.kafka_consumer_group,
        max_retries=settings.kafka_consumer_retries,
    )
    producer = await create_producer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        max_retries=settings.kafka_consumer_retries,
    )

    logger.info("worker_ready", model=settings.model_name)

    try:
        async for msg in consumer:
            request_id = "unknown"
            try:
                MESSAGES_CONSUMED.labels(topic=TOPIC_PREDICTION_REQUESTS).inc()
                request = PredictionRequest(**msg.value)
                request_id = request.request_id

                logger.info("processing_request", request_id=request_id)

                # Run inference (CPU-bound, but fast enough for single requests)
                start = time.perf_counter()
                prediction = model.predict(request.text)
                elapsed = time.perf_counter() - start
                INFERENCE_LATENCY.observe(elapsed)

                result = PredictionResult(
                    request_id=request_id,
                    label=prediction["label"],
                    score=prediction["score"],
                    model_name=prediction["model_name"],
                    inference_time_ms=prediction["inference_time_ms"],
                    status=TaskStatus.COMPLETED,
                )

                await produce_message(
                    producer=producer,
                    topic=TOPIC_PREDICTION_RESULTS,
                    key=request_id,
                    value=result.model_dump(),
                )
                RESULTS_PRODUCED.labels(topic=TOPIC_PREDICTION_RESULTS).inc()
                INFERENCE_COUNT.labels(status="success").inc()

                await consumer.commit()
                logger.info(
                    "request_completed",
                    request_id=request_id,
                    label=result.label,
                    score=result.score,
                    inference_ms=result.inference_time_ms,
                )

            except Exception as exc:
                INFERENCE_COUNT.labels(status="error").inc()
                PROCESSING_ERRORS.labels(error_type=type(exc).__name__).inc()
                logger.exception("processing_error", request_id=request_id)

                # Produce error result so the gateway knows it failed
                try:
                    error_result = PredictionResult(
                        request_id=request_id,
                        label="ERROR",
                        score=0.0,
                        model_name=settings.model_name,
                        inference_time_ms=0.0,
                        status=TaskStatus.FAILED,
                    )
                    await produce_message(
                        producer=producer,
                        topic=TOPIC_PREDICTION_RESULTS,
                        key=request_id,
                        value=error_result.model_dump(),
                    )
                except Exception:
                    logger.exception("error_result_produce_failed")

                await consumer.commit()

    except asyncio.CancelledError:
        logger.info("worker_cancelled")
    finally:
        logger.info("worker_shutting_down")
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
