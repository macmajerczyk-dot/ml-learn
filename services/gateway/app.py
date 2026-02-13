"""FastAPI gateway service — accepts prediction requests, publishes to Kafka,
consumes results, and exposes them via REST + Prometheus metrics."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from services.gateway.config import settings
from services.gateway.metrics import (
    ACTIVE_CONNECTIONS,
    KAFKA_MESSAGES_PRODUCED,
    KAFKA_PRODUCE_ERRORS,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    RESULTS_RECEIVED,
)
from shared.kafka_utils import (
    TOPIC_PREDICTION_REQUESTS,
    TOPIC_PREDICTION_RESULTS,
    create_consumer,
    create_producer,
    produce_message,
)
from shared.logging_config import get_logger, setup_logging
from shared.schemas import HealthResponse, PredictionRequest, PredictionResult, TaskStatus

logger = get_logger(__name__)

# In-memory result store (bounded LRU). In production, use Redis or a database.
MAX_RESULTS = 10_000
results_store: OrderedDict[str, dict] = OrderedDict()

producer: AIOKafkaProducer | None = None
consumer: AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None


def _store_result(request_id: str, result: dict) -> None:
    results_store[request_id] = result
    results_store.move_to_end(request_id)
    while len(results_store) > MAX_RESULTS:
        results_store.popitem(last=False)


async def _consume_results() -> None:
    """Background task that consumes prediction results from Kafka."""
    global consumer
    try:
        consumer = await create_consumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=TOPIC_PREDICTION_RESULTS,
            group_id="gateway-results-consumer",
        )
        logger.info("results_consumer_started")
        async for msg in consumer:
            try:
                result = PredictionResult(**msg.value)
                _store_result(result.request_id, result.model_dump())
                RESULTS_RECEIVED.labels(status=result.status.value).inc()
                await consumer.commit()
                logger.info(
                    "result_received",
                    request_id=result.request_id,
                    label=result.label,
                    score=result.score,
                )
            except Exception:
                logger.exception("result_processing_error")
    except asyncio.CancelledError:
        logger.info("results_consumer_cancelled")
    except Exception:
        logger.exception("results_consumer_fatal_error")
    finally:
        if consumer:
            await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup/shutdown of Kafka producer and result consumer."""
    global producer, _consumer_task

    setup_logging(settings.service_name, settings.log_level)
    logger.info("gateway_starting", version=settings.version)

    producer = await create_producer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        max_retries=settings.kafka_producer_retries,
    )
    _consumer_task = asyncio.create_task(_consume_results())

    yield

    logger.info("gateway_shutting_down")
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    if producer:
        await producer.stop()


app = FastAPI(
    title="ML Pipeline Gateway",
    version=settings.version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware: metrics + logging
# ---------------------------------------------------------------------------
@app.middleware("http")
async def metrics_middleware(request: Request, call_next) -> Response:
    ACTIVE_CONNECTIONS.inc()
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed = time.perf_counter() - start
        ACTIVE_CONNECTIONS.dec()
        REQUEST_LATENCY.labels(
            method=request.method, endpoint=request.url.path
        ).observe(elapsed)
        status = response.status_code if "response" in dir() else 500
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=status,
        ).inc()
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    kafka_ok = producer is not None
    return HealthResponse(
        service=settings.service_name,
        status="healthy" if kafka_ok else "degraded",
        version=settings.version,
        kafka_connected=kafka_ok,
    )


@app.post("/predict", status_code=202)
async def submit_prediction(request: PredictionRequest) -> dict:
    """Accept a prediction request and publish it to Kafka for async processing."""
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not available")

    try:
        await produce_message(
            producer=producer,
            topic=TOPIC_PREDICTION_REQUESTS,
            key=request.request_id,
            value=request.model_dump(),
        )
        KAFKA_MESSAGES_PRODUCED.labels(topic=TOPIC_PREDICTION_REQUESTS).inc()
    except Exception as exc:
        KAFKA_PRODUCE_ERRORS.labels(topic=TOPIC_PREDICTION_REQUESTS).inc()
        logger.error("produce_failed", request_id=request.request_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Failed to enqueue request") from exc

    logger.info("prediction_submitted", request_id=request.request_id)
    return {
        "request_id": request.request_id,
        "status": TaskStatus.PENDING.value,
        "message": "Request enqueued for processing",
    }


@app.get("/predict/{request_id}")
async def get_prediction_result(request_id: str) -> dict:
    """Poll for a prediction result by request_id."""
    result = results_store.get(request_id)
    if result is None:
        return {"request_id": request_id, "status": TaskStatus.PENDING.value}
    return result


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
