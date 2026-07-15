"""Structured task-plan state for model-driven progress updates."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Any, Dict, List, Optional


PLAN_STATUSES = {"pending", "in_progress", "completed"}


def get_plan_tool_definition() -> Dict[str, Any]:
    """Return the OpenAI function schema for replacing the current task plan."""
    return {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": (
                "Create or replace the complete structured plan for a multi-step "
                "task. Call this after meaningful progress or when replanning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": "Optional concise reason for this plan snapshot",
                    },
                    "plan": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "step": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "Short, concrete task step",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": sorted(PLAN_STATUSES),
                                },
                            },
                            "required": ["step", "status"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["plan"],
                "additionalProperties": False,
            },
        },
    }


class PlanTool:
    """Validate and atomically replace one task's latest plan snapshot."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot: Optional[Dict[str, Any]] = None
        self._version = 0

    def update(self, params: Dict[str, Any]) -> str:
        """Replace the plan and return a machine-readable progress summary."""
        try:
            snapshot = self._validate(params)
        except ValueError as exc:
            return f"Error: {exc}"

        with self._lock:
            self._version += 1
            snapshot["version"] = self._version
            self._snapshot = snapshot
            result = self._summary(snapshot)
        return json.dumps(result, ensure_ascii=False)

    def snapshot(self) -> Optional[Dict[str, Any]]:
        """Return an isolated copy of the latest valid plan."""
        with self._lock:
            return deepcopy(self._snapshot)

    @staticmethod
    def _validate(params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise ValueError("update_plan parameters must be an object")
        unexpected = set(params) - {"explanation", "plan"}
        if unexpected:
            fields = ", ".join(sorted(str(field) for field in unexpected))
            raise ValueError(f"unexpected update_plan fields: {fields}")
        explanation = params.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError("explanation must be a string")
        raw_plan = params.get("plan")
        if not isinstance(raw_plan, list) or not raw_plan:
            raise ValueError("plan must contain at least one step")

        plan: List[Dict[str, str]] = []
        in_progress_count = 0
        for index, item in enumerate(raw_plan):
            if not isinstance(item, dict):
                raise ValueError(f"plan[{index}] must be an object")
            unexpected = set(item) - {"step", "status"}
            if unexpected:
                fields = ", ".join(sorted(str(field) for field in unexpected))
                raise ValueError(f"unexpected plan[{index}] fields: {fields}")
            raw_step = item.get("step")
            raw_status = item.get("status")
            if not isinstance(raw_step, str):
                raise ValueError(f"plan[{index}].step must be a string")
            if not isinstance(raw_status, str):
                raise ValueError(f"plan[{index}].status must be a string")
            step = raw_step.strip()
            status = raw_status.strip()
            if not step:
                raise ValueError(f"plan[{index}].step is required")
            if status not in PLAN_STATUSES:
                allowed = ", ".join(sorted(PLAN_STATUSES))
                raise ValueError(f"plan[{index}].status must be one of: {allowed}")
            if status == "in_progress":
                in_progress_count += 1
            plan.append({"step": step, "status": status})

        if in_progress_count > 1:
            raise ValueError("only one plan step may be in_progress")

        return {
            "explanation": explanation.strip(),
            "plan": plan,
        }

    @staticmethod
    def _summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        plan = snapshot["plan"]
        completed = sum(item["status"] == "completed" for item in plan)
        current = next(
            (item["step"] for item in plan if item["status"] == "in_progress"),
            "",
        )
        return {
            "success": True,
            "version": snapshot["version"],
            "completed": completed,
            "total": len(plan),
            "current_step": current,
            "explanation": snapshot["explanation"],
            "plan": deepcopy(plan),
        }
