"""Structured internal tool results for model-facing runtime data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolExecutionResult:
    """Keep persisted tool text separate from transient model input blocks."""

    content: str
    model_inputs: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.content
