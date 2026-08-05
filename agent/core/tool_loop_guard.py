"""Execution-level protection against repeated tool-call loops."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ToolLoopGuard:
    """Reuse successful observations and block repeated state changes."""

    DEFAULT_MAX_SAME_TOOL_REPEATS = 3
    OBSERVATION_TOOLS = {
        "read",
        "file_read",
        "glob",
        "grep",
        "codesearch",
        "web_search",
        "websearch",
        "read_url",
        "view_image",
    }
    MUTATION_TOOLS = {
        "write",
        "file_write",
        "edit",
        "generate_pdf",
        "generate_docx",
        "generate_pptx",
        "generate_xlsx",
        "project_preview",
    }
    IGNORED_PARAM_KEYS = {"description", "reason", "summary"}
    ALWAYS_EXECUTE_TOOLS = {"todo_write", "update_plan", "view_image"}

    @staticmethod
    def _max_same_tool_repeats() -> int:
        """Return how many identical calls are tolerated before blocking."""
        raw = os.getenv("MAX_SAME_TOOL_REPEATS", "").strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return ToolLoopGuard.DEFAULT_MAX_SAME_TOOL_REPEATS

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._observations: Dict[str, Dict[str, Any]] = {}
        self._mutations: Dict[str, Dict[str, Any]] = {}
        self._notices = []

    def snapshot(self) -> Dict[str, Any]:
        """Return JSON-serializable state for a resumable agent run."""
        return {
            "observations": self._copy_records(self._observations),
            "mutations": self._copy_records(self._mutations),
            "notices": [str(item) for item in self._notices[-4:]],
        }

    def restore(self, snapshot: Optional[Dict[str, Any]]) -> None:
        """Restore state previously produced by :meth:`snapshot`."""
        state = snapshot if isinstance(snapshot, dict) else {}
        self._observations = self._restore_records(state.get("observations"))
        self._mutations = self._restore_records(state.get("mutations"))
        raw_notices = state.get("notices")
        self._notices = (
            [str(item) for item in raw_notices if str(item).strip()][-4:]
            if isinstance(raw_notices, list)
            else []
        )

    @staticmethod
    def _copy_records(records: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(signature): {
                "result": str(record.get("result", ""))[:12000],
                "success": bool(record.get("success", False)),
                "repeats": max(0, int(record.get("repeats", 0) or 0)),
            }
            for signature, record in records.items()
            if isinstance(record, dict)
        }

    @classmethod
    def _restore_records(cls, value: Any) -> Dict[str, Dict[str, Any]]:
        if not isinstance(value, dict):
            return {}
        return cls._copy_records(value)

    @staticmethod
    def _path(value: Any, workdir: Optional[str] = None) -> str:
        raw = str(value or ".").strip()
        path = Path(raw).expanduser()
        if not path.is_absolute() and workdir:
            path = Path(workdir).expanduser() / path
        try:
            return str(path.resolve(strict=False))
        except OSError:
            return str(path)

    def _signature(self, tool_name: str, params: Dict[str, Any]) -> tuple:
        name = str(tool_name or "").strip().lower()
        params = dict(params or {})
        if name in self.ALWAYS_EXECUTE_TOOLS:
            kind = "management"
        elif name in {"bash", "shell"}:
            kind = "observation" if self._is_read_only_command(params) else "mutation"
        elif name in self.OBSERVATION_TOOLS:
            kind = "observation"
        elif name in self.MUTATION_TOOLS:
            kind = "mutation"
        else:
            kind = "mutation"

        normalized = {
            key: value
            for key, value in params.items()
            if key not in self.IGNORED_PARAM_KEYS
        }
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
        return f"{name}:{payload}", kind

    @staticmethod
    def _is_read_only_command(params: Dict[str, Any]) -> bool:
        command = str(params.get("command", "") or "").strip().lower()
        executable = Path(command.split(maxsplit=1)[0]).name if command else ""
        return executable in {
            "ls",
            "pwd",
            "cat",
            "find",
            "grep",
            "rg",
            "head",
            "tail",
            "wc",
            "stat",
            "pytest",
            "ruff",
            "mypy",
            "eslint",
            "jest",
            "vitest",
        }

    @staticmethod
    def _succeeded(result: str) -> bool:
        raw_result = str(result or "").strip()
        lowered = raw_result.lower()
        if raw_result.startswith("{"):
            try:
                parsed = json.loads(raw_result)
                if isinstance(parsed, dict) and parsed.get("success") is False:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass
        return not lowered.startswith(("error:", "failed:", "failure:"))

    def before_call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        signature, kind = self._signature(tool_name, params)
        if str(tool_name or "").strip().lower() in self.ALWAYS_EXECUTE_TOOLS:
            return {"action": "execute", "signature": signature, "kind": kind}
        records = self._observations if kind == "observation" else self._mutations
        previous = records.get(signature)
        if not previous or not previous.get("success"):
            return {"action": "execute", "signature": signature, "kind": kind}

        previous["repeats"] = int(previous.get("repeats", 0)) + 1
        max_repeats = self._max_same_tool_repeats()
        if kind == "observation" and previous["repeats"] < max_repeats - 1:
            notice = (
                f"防循环：{tool_name} 的相同参数已经成功执行，本次直接复用已有结果。"
                "不要再次验证同一状态，请执行能推进任务的下一步。"
            )
            self._add_notice(notice)
            return {
                "action": "reuse",
                "signature": signature,
                "kind": kind,
                "result": f"{notice}\n\n已有结果：\n{previous['result']}",
            }

        if kind == "mutation" and previous["repeats"] < max_repeats - 1:
            notice = (
                f"防循环：{tool_name} 的相同变更已经成功完成，本次不会再次执行。"
                "请检查已有结果并进入下一步。"
            )
            self._add_notice(notice)
            return {
                "action": "reuse",
                "signature": signature,
                "kind": kind,
                "result": notice,
            }

        notice = (
            f"防循环已拦截重复调用：{tool_name} 的工具名与有效参数完全相同。"
            "禁止继续执行这条相同调用；请改用不同参数推进用户任务，"
            "若任务已完成则立即给出最终回答。"
        )
        self._add_notice(notice)
        return {
            "action": "block",
            "signature": signature,
            "kind": kind,
            "result": notice,
        }

    def record_result(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: str,
        signature: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> None:
        if not signature or not kind:
            signature, kind = self._signature(tool_name, params)
        if kind == "management":
            return
        success = self._succeeded(result)
        record = {
            "result": str(result)[:12000],
            "success": success,
            "repeats": 0,
        }
        if kind == "observation":
            self._observations[signature] = record
        else:
            self._mutations[signature] = record
            if success:
                # A successful mutation can invalidate all earlier filesystem checks.
                self._observations.clear()

    def _add_notice(self, notice: str) -> None:
        if notice not in self._notices:
            self._notices.append(notice)
        self._notices = self._notices[-4:]

    def context_notice(self) -> str:
        if not self._notices:
            return ""
        return "【防循环执行约束】\n- " + "\n- ".join(self._notices)
