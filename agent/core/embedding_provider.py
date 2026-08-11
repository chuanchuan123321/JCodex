"""Grok-compatible OpenAI embeddings provider for long-term memory search."""

from __future__ import annotations

import hashlib
import math
import os
import time
from typing import Any, Optional

import requests


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


class BaseEmbeddingProvider:
    """Synchronous equivalent of Grok's batch embedding provider contract."""

    name = "base"
    model = ""
    dimensions = 0
    available = True

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        vectors = self.embed_batch([text])
        if not vectors:
            raise EmbeddingError("embedding provider returned no vectors")
        return vectors[0]

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "dimension": self.dimensions,
            "available": self.available,
        }


class DisabledEmbeddingProvider(BaseEmbeddingProvider):
    """Represents Grok's default `model = None` FTS-only mode."""

    name = "disabled"
    available = False

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("memory embedding model is not configured")


class ApiEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI-compatible `/embeddings` provider with Grok's retry policy."""

    name = "api"
    max_batch_size = 32
    max_retries = 3
    initial_backoff_seconds = 1.0

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        dimensions: Optional[int] = None,
    ) -> None:
        self.api_base = self._normalize_api_base(api_base)
        self.api_key = str(api_key or "")
        self.model = str(model or "").strip()
        self.dimensions = max(1, int(dimensions)) if dimensions else 0
        self.available = bool(self.api_base and self.api_key and self.model)

    @staticmethod
    def _normalize_api_base(api_base: str) -> str:
        base = str(api_base or "").rstrip("/")
        for suffix in ("/chat/completions", "/embeddings"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return base.rstrip("/")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.available:
            raise EmbeddingError("embedding API configuration is incomplete")

        all_embeddings: list[list[float]] = []
        for offset in range(0, len(texts), self.max_batch_size):
            batch = texts[offset : offset + self.max_batch_size]
            payload = {
                "model": self.model,
                "input": batch,
            }
            if self.dimensions:
                payload["dimensions"] = self.dimensions
            last_error = ""
            for attempt in range(self.max_retries):
                if attempt:
                    time.sleep(self.initial_backoff_seconds * (2 ** (attempt - 1)))
                try:
                    response = requests.post(
                        f"{self.api_base}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=120,
                    )
                except requests.RequestException as exc:
                    last_error = str(exc)
                    continue

                if response.ok:
                    try:
                        data = response.json().get("data") or []
                        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
                        vectors = [
                            _normalize([float(value) for value in item["embedding"]])
                            for item in ordered
                        ]
                    except (KeyError, TypeError, ValueError) as exc:
                        raise EmbeddingError(f"invalid embedding response: {exc}") from exc
                    if len(vectors) != len(batch):
                        raise EmbeddingError("embedding response count does not match input")
                    if self.dimensions == 0 and vectors:
                        self.dimensions = len(vectors[0])
                    all_embeddings.extend(vectors)
                    break

                last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code != 429 and response.status_code < 500:
                    raise EmbeddingError(last_error)
            else:
                raise EmbeddingError(
                    f"embedding API failed after {self.max_retries} attempts: {last_error}"
                )
        return all_embeddings

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["api_base"] = self.api_base
        return status


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic Grok-style test provider; never selected at runtime."""

    name = "mock"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = max(1, int(dimensions))
        self.model = "mock"

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.blake2b(text.encode("utf-8"), digest_size=64).digest()
            values = [
                (digest[index % len(digest)] / 127.5) - 1.0
                for index in range(self.dimensions)
            ]
            vectors.append(_normalize(values))
        return vectors


def create_embedding_provider() -> BaseEmbeddingProvider:
    """Create the API provider, or FTS-only keyword mode when config is incomplete.

    Vector retrieval is enabled only when the embedding model, base URL and API
    key are all configured. If any of them is missing or invalid, memory search
    degrades to FTS5/BM25 keyword retrieval instead of reusing the main chat API
    configuration. Dimensions are optional: when left blank the embedding model's
    default dimension is used and detected from the first API response.
    """
    model = os.getenv("MEMORY_EMBEDDING_MODEL", "").strip()
    api_base = os.getenv("MEMORY_EMBEDDING_BASE_URL", "").strip()
    api_key = os.getenv("MEMORY_EMBEDDING_API_KEY", "").strip()
    if not model or not api_base or not api_key:
        return DisabledEmbeddingProvider()
    dimensions = os.getenv("MEMORY_EMBEDDING_DIMENSIONS", "").strip()
    dimensions_int = None
    if dimensions:
        try:
            dimensions_int = int(dimensions)
        except ValueError:
            return DisabledEmbeddingProvider()
    return ApiEmbeddingProvider(
        api_base=api_base,
        api_key=api_key,
        model=model,
        dimensions=dimensions_int,
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def l2_distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 2.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def vector_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]
