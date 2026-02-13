"""ML model wrapper for sentiment analysis inference."""

from __future__ import annotations

import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

from services.ml_worker.config import settings
from services.ml_worker.metrics import MODEL_LOAD_TIME
from shared.logging_config import get_logger

logger = get_logger(__name__)


class SentimentModel:
    """Wraps a HuggingFace sentiment analysis pipeline with metrics."""

    def __init__(self) -> None:
        self._pipeline = None
        self._model_name = settings.model_name
        self._device = settings.model_device
        self._max_length = settings.model_max_length

    def load(self) -> None:
        """Load the model and tokenizer. Call once at startup."""
        logger.info(
            "model_loading",
            model_name=self._model_name,
            device=self._device,
        )
        start = time.perf_counter()

        device_index = 0 if self._device == "cuda" and torch.cuda.is_available() else -1

        tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        model = AutoModelForSequenceClassification.from_pretrained(self._model_name)

        self._pipeline = pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            device=device_index,
            truncation=True,
            max_length=self._max_length,
        )

        elapsed = time.perf_counter() - start
        MODEL_LOAD_TIME.set(elapsed)
        logger.info(
            "model_loaded",
            model_name=self._model_name,
            load_time_s=round(elapsed, 3),
            device="cuda" if device_index >= 0 else "cpu",
        )

    def predict(self, text: str) -> dict:
        """Run inference on a single text input.

        Returns:
            dict with keys: label, score, model_name, inference_time_ms
        """
        if self._pipeline is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        start = time.perf_counter()
        result = self._pipeline(text)[0]
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "label": result["label"],
            "score": round(result["score"], 6),
            "model_name": self._model_name,
            "inference_time_ms": round(elapsed_ms, 2),
        }

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None
