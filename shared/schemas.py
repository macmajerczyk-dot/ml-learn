"""Shared Pydantic schemas used across services for event serialization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PredictionRequest(BaseModel):
    """Inbound request submitted via the gateway API."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(..., min_length=1, max_length=5000)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PredictionResult(BaseModel):
    """Result produced by the ML worker after inference."""

    request_id: str
    label: str
    score: float
    model_name: str
    inference_time_ms: float
    status: TaskStatus = TaskStatus.COMPLETED
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HealthResponse(BaseModel):
    service: str
    status: str
    version: str
    kafka_connected: bool
