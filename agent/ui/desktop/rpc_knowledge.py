"""JCodex desktop UI - knowledge base RPC."""

import json
import os
from pathlib import Path

import eel

from agent.ui.desktop import constants, helpers, runtime


@eel.expose
def get_knowledge_stats():
    """Get knowledge base statistics"""
    try:
        from agent.core.knowledge_base import KnowledgeBase

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        return kb.get_knowledge_stats()
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def list_knowledge_entries():
    """List knowledge entries"""
    try:
        from agent.core.knowledge_base import KnowledgeBase

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        entries = kb.list_entries()
        return [e.to_dict() for e in entries]
    except Exception:
        return []


@eel.expose
def search_knowledge(query: str, knowledge_type: str = ""):
    """Search knowledge base"""
    try:
        from agent.core.knowledge_base import KnowledgeBase, KnowledgeType

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        ktype = KnowledgeType(knowledge_type) if knowledge_type else None
        results = kb.search(query, knowledge_type=ktype)
        return [
            {
                "id": e.id,
                "title": e.title,
                "content": e.content,
                "knowledge_type": e.knowledge_type.value,
                "tags": list(e.tags),
                "score": score,
            }
            for e, score in results
        ]
    except Exception:
        return []


@eel.expose
def add_knowledge(knowledge_type: str, title: str, content: str, tags: list | None = None):
    """Add knowledge entry"""
    try:
        from agent.core.knowledge_base import KnowledgeBase, KnowledgeType

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        ktype = KnowledgeType(knowledge_type)
        entry = kb.add_knowledge(ktype, title, content, tags=set(tags) if tags else None)
        runtime.os_agent.reload_knowledge_base()
        return {"success": True, "entry_id": entry.id}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def extract_knowledge_from_memory(task_id: str | None = None):
    """Extract reusable knowledge from full memory using AI."""
    try:
        from agent.core.ai_engine import AIEngine
        from agent.core.data_integrator import DataIntegrator
        from agent.core.knowledge_base import KnowledgeBase

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        memory_path = runtime.os_agent.memory_manager.memory_dir

        integrator = DataIntegrator(data_dir=workspace_path / "data")
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")

        if task_id:
            entries = integrator.get_task_entries_for_analysis(task_id)
        else:
            entries = integrator.get_task_entries_for_analysis(None)

        if not entries:
            return {"success": False, "message": "没有可提取的记忆内容", "extracted_count": 0}

        memory_lines = []
        for entry in entries:
            memory_lines.append(json.dumps(entry, ensure_ascii=False))

        # 优先使用完整记忆文本，再附加累积压缩内容，保证上下文完整

        full_memory_parts = []
        execution_history = Path(memory_path) / "execution_history.md"
        accumulated = Path(memory_path) / "accumulated_compression.md"
        if execution_history.exists():
            full_memory_parts.append(execution_history.read_text(encoding="utf-8"))
        if accumulated.exists():
            full_memory_parts.append(accumulated.read_text(encoding="utf-8"))
        full_memory_parts.append("\n".join(memory_lines))

        full_memory_text = "\n\n".join([part for part in full_memory_parts if part.strip()])
        if not full_memory_text.strip():
            return {"success": False, "message": "没有可提取的记忆内容", "extracted_count": 0}

        api_base_url = os.getenv("API_BASE_URL")
        api_key = os.getenv("API_KEY")
        model = os.getenv("API_MODEL", "deepseek-v4-pro")

        result = kb.extract_knowledge_from_memory(
            memory_text=full_memory_text,
            archive_path=str(execution_history) if execution_history.exists() else "",
            task_id=task_id or "",
            api_base_url=AIEngine.normalize_api_base_url(api_base_url) if api_base_url else None,
            api_key=api_key,
            model=model,
        )
        runtime.os_agent.reload_knowledge_base()
        return result
    except Exception as e:
        return {"success": False, "message": str(e), "extracted_count": 0}


@eel.expose
def get_knowledge_conflicts():
    """Get knowledge conflicts"""
    try:
        from agent.core.knowledge_base import KnowledgeBase

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        return kb.get_conflicts()
    except Exception:
        return []


@eel.expose
def delete_knowledge_entry(entry_id: str):
    """Delete a knowledge entry"""
    try:
        from agent.core.knowledge_base import KnowledgeBase

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        kb = KnowledgeBase(knowledge_dir=workspace_path / "knowledge")
        success = kb.delete_knowledge(entry_id)
        runtime.os_agent.reload_knowledge_base()
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def open_workspace_subfolder(folder: str, subfolder: str):
    """打开workspace子文件夹"""
    try:
        import platform
        import subprocess

        folder_path = helpers._resolve_within(helpers._workspace_folder(folder), subfolder)

        if not folder_path.is_dir():
            return {"success": False, "error": "Folder not found"}

        abs_path = str(folder_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = [
    "add_knowledge",
    "delete_knowledge_entry",
    "extract_knowledge_from_memory",
    "get_knowledge_conflicts",
    "get_knowledge_stats",
    "list_knowledge_entries",
    "open_workspace_subfolder",
    "search_knowledge",
]
