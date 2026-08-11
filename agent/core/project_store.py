"""Persistent local project bindings for the desktop workspace."""

import json
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_CONTEXT_FILES = (
    "AGENTS.md",
    "README.md",
    "README.zh.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "package.json",
    ".codex/config.toml",
)


class ProjectStore:
    """Store project metadata without copying or modifying bound directories."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.root_dir / "index.json"
        self._lock = threading.RLock()
        if not self.index_file.exists():
            self._write_index({"projects": []})

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clean_name(name: str, root_path: Optional[Path] = None) -> str:
        fallback = root_path.name if root_path else "新项目"
        value = " ".join(str(name or fallback).split()).strip()
        return (value or fallback)[:80]

    @staticmethod
    def _clean_instructions(instructions: str) -> str:
        return str(instructions or "").strip()[:12000]

    @staticmethod
    def _validate_id(project_id: str) -> str:
        value = str(project_id or "")
        if not value or any(char not in "0123456789abcdef-" for char in value):
            raise ValueError("Invalid project id")
        return value

    @staticmethod
    def _validate_root(root_path: str) -> Path:
        raw_path = str(root_path or "").strip()
        if not raw_path:
            raise ValueError("项目目录不能为空")
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise ValueError("项目目录不存在")
        if not path.is_dir():
            raise ValueError("项目路径必须是目录")
        return path

    def _read_index(self) -> Dict[str, Any]:
        try:
            value = json.loads(self.index_file.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("projects"), list):
                return value
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return {"projects": []}

    def _write_index(self, value: Dict[str, Any]) -> None:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.index_file.with_name(
            f"{self.index_file.name}.{uuid.uuid4().hex}.tmp"
        )
        temp_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(self.index_file)

    @staticmethod
    def _metadata(project: Dict[str, Any]) -> Dict[str, Any]:
        root_path = str(project.get("root_path", ""))
        return {
            "id": str(project.get("id", "")),
            "name": str(project.get("name", "新项目")),
            "root_path": root_path,
            "instructions": str(project.get("instructions", "")),
            "created_at": str(project.get("created_at", "")),
            "updated_at": str(project.get("updated_at", "")),
            "available": bool(root_path and Path(root_path).is_dir()),
        }

    def list(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return all bound projects ordered by recent metadata updates."""
        with self._lock:
            projects = [
                self._metadata(item)
                for item in self._read_index().get("projects", [])
                if isinstance(item, dict) and item.get("id")
            ]
            projects.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            return {"projects": projects}

    def load(self, project_id: str) -> Dict[str, Any]:
        """Load one project binding."""
        target_id = self._validate_id(project_id)
        with self._lock:
            for project in self._read_index().get("projects", []):
                if str(project.get("id", "")) == target_id:
                    return self._metadata(project)
        raise ValueError("Project not found")

    def create(
        self, name: str, root_path: str, instructions: str = ""
    ) -> Dict[str, Any]:
        """Bind an existing local directory as a project."""
        root = self._validate_root(root_path)
        with self._lock:
            index = self._read_index()
            for item in index.get("projects", []):
                existing_root = str(item.get("root_path", "")).strip()
                if existing_root and Path(existing_root).expanduser().resolve() == root:
                    raise ValueError("该目录已经添加为项目")
            now = self._now()
            project = {
                "id": str(uuid.uuid4()),
                "name": self._clean_name(name, root),
                "root_path": str(root),
                "instructions": self._clean_instructions(instructions),
                "created_at": now,
                "updated_at": now,
            }
            index.setdefault("projects", []).append(project)
            self._write_index(index)
            return self._metadata(project)

    def update(
        self,
        project_id: str,
        *,
        name: Optional[str] = None,
        root_path: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update project metadata while preserving its task relationships."""
        target_id = self._validate_id(project_id)
        with self._lock:
            index = self._read_index()
            project = next(
                (
                    item
                    for item in index.get("projects", [])
                    if str(item.get("id", "")) == target_id
                ),
                None,
            )
            if project is None:
                raise ValueError("Project not found")

            if root_path is not None:
                root = self._validate_root(root_path)
                for item in index.get("projects", []):
                    if str(item.get("id", "")) == target_id:
                        continue
                    existing_root = str(item.get("root_path", "")).strip()
                    if existing_root and Path(existing_root).expanduser().resolve() == root:
                        raise ValueError("该目录已经添加为项目")
                project["root_path"] = str(root)
            else:
                root = Path(str(project.get("root_path", "")))
            if name is not None:
                project["name"] = self._clean_name(name, root)
            if instructions is not None:
                project["instructions"] = self._clean_instructions(instructions)
            project["updated_at"] = self._now()
            self._write_index(index)
            return self._metadata(project)

    def delete(self, project_id: str) -> Dict[str, Any]:
        """Delete only the binding; the local project directory is untouched."""
        target_id = self._validate_id(project_id)
        with self._lock:
            index = self._read_index()
            projects = [
                item
                for item in index.get("projects", [])
                if str(item.get("id", "")) != target_id
            ]
            if len(projects) == len(index.get("projects", [])):
                raise ValueError("Project not found")
            index["projects"] = projects
            self._write_index(index)
            return {"success": True}

    def inspect(self, project_id: str) -> Dict[str, Any]:
        """Return lightweight filesystem and Git state for one project."""
        project = self.load(project_id)
        root = Path(project["root_path"])
        context_files = [
            relative_path
            for relative_path in PROJECT_CONTEXT_FILES
            if (root / relative_path).is_file()
        ]
        status = self._git_status(root) if root.is_dir() else {}
        return {
            **project,
            "context_files": context_files,
            "git": status,
        }

    @staticmethod
    def _git_status(root: Path) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "status", "--short", "--branch"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return {"is_repo": False, "branch": "", "changes": 0}
        if result.returncode != 0:
            return {"is_repo": False, "branch": "", "changes": 0}
        lines = result.stdout.splitlines()
        header = lines[0][3:] if lines and lines[0].startswith("## ") else ""
        branch = header.split("...", 1)[0].split(" ", 1)[0].strip()
        return {
            "is_repo": True,
            "branch": branch or "HEAD",
            "changes": max(0, len(lines) - (1 if lines and lines[0].startswith("## ") else 0)),
            "summary": header,
        }
