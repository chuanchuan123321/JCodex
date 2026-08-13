"""JCodex desktop UI - data and preferences RPC."""

import os
import shutil

import eel

from agent.ui.desktop import constants, runtime


@eel.expose
def get_recent_tasks(limit: int = 20):
    """Get recent tasks (grouped)"""
    try:
        from agent.core.data_integrator import DataIntegrator

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        integrator = DataIntegrator(data_dir=workspace_path / "data")
        integrator.prune_orphan_entries()
        tasks = integrator.get_recent_tasks(limit)
        return [t.to_dict() for t in tasks]
    except Exception:
        return []


@eel.expose
def delete_task_data(task_id: str):
    """Delete all data for a task"""
    try:
        from agent.core.data_integrator import DataIntegrator

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        integrator = DataIntegrator(data_dir=workspace_path / "data")
        success = integrator.delete_task(task_id)
        integrator.prune_orphan_entries()
        runtime.os_agent.reload_data_integrator()
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def clear_all_data():
    """Clear all data (factory reset)"""
    try:
        from agent.core.data_integrator import DataIntegrator

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        integrator = DataIntegrator(data_dir=workspace_path / "data")
        success = integrator.clear_all()
        shutil.rmtree(constants.ROLLBACK_ROOT, ignore_errors=True)
        runtime.os_agent.reload_data_integrator()
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def extract_preferences_from_data(task_id: str | None = None):
    """Extract preferences from data using AI"""
    print("[DEBUG] extract_preferences_from_data 被调用")
    try:
        import traceback

        from agent.core.ai_engine import AIEngine
        from agent.core.data_integrator import DataIntegrator
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"

        print(f"[DEBUG] workspace_path: {workspace_path}")
        integrator = DataIntegrator(data_dir=workspace_path / "data")
        integrator.prune_orphan_entries()
        preference_manager = PreferenceManager(preference_dir=workspace_path / "preferences")

        # 获取数据条目
        data_entries = integrator.get_task_entries_for_analysis(task_id)
        print(
            f"[DEBUG] data_entries类型: {type(data_entries)}, 长度: {len(data_entries) if data_entries else 0}"
        )

        # 获取API配置
        api_base_url = os.getenv("API_BASE_URL")
        api_key = os.getenv("API_KEY")
        model = os.getenv("API_MODEL", "deepseek-v4-pro")
        print(f"[DEBUG] API配置: base_url={api_base_url}, model={model}")

        if not api_base_url or not api_key:
            return {"success": False, "message": "API配置不完整，请检查环境变量"}

        print(
            f"[DEBUG] 调用 preference_manager.extract_preferences_from_data, data_entries类型: {type(data_entries)}, 前50字: {str(data_entries)[:50]}"
        )

        # 调用AI提取
        result = preference_manager.extract_preferences_from_data(
            data_entries=data_entries,
            api_base_url=AIEngine.normalize_api_base_url(api_base_url) if api_base_url else None,
            api_key=api_key,
            model=model,
        )
        print(f"[DEBUG] result: {str(result)[:500]}")
        return result
    except Exception as e:
        import traceback

        error_msg = f"错误: {e!s}\n\n详情:\n{traceback.format_exc()}"
        print(f"[DEBUG] 异常: {error_msg}")
        return {"success": False, "message": error_msg}


@eel.expose
def ingest_manual_config(config_type: str, config_data: dict):
    """Ingest manual configuration"""
    try:
        from agent.core.data_integrator import DataIntegrator

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        integrator = DataIntegrator(data_dir=workspace_path / "data")
        entry = integrator.ingest_manual_config(config_type, config_data)
        return {"success": True, "entry_id": entry.id}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def get_all_preferences():
    """Get all preferences"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        return pm.get_all_preferences()
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def set_preference(category: str, key: str, value):
    """Set a preference"""
    try:
        from agent.core.preference_manager import PreferenceCategory, PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        cat = PreferenceCategory(category)
        entry = pm.set_preference(cat, key, value, source="user")
        return {"success": True, "version": entry.version}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def delete_preference(category: str, key: str):
    """Delete a preference"""
    try:
        from agent.core.preference_manager import PreferenceCategory, PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        cat = PreferenceCategory(category)
        success = pm.delete_preference(cat, key)
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def clear_all_preferences():
    """Clear all saved preferences."""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        success = pm.clear_all()
        return {"success": success}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def list_preference_snapshots():
    """List preference snapshots"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        return pm.list_snapshots()
    except Exception:
        return []


@eel.expose
def create_preference_snapshot(description: str = ""):
    """Create a preference snapshot"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        snapshot = pm.create_snapshot(description)
        return {"success": True, "snapshot_id": snapshot.snapshot_id}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def restore_preference_snapshot():
    """Restore latest preference snapshot"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        snapshots = pm.list_snapshots()
        if snapshots:
            latest = snapshots[0]["snapshot_id"]
            success = pm.restore_snapshot(latest)
            return {"success": success}
        return {"success": False, "error": "No snapshots available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def restore_preference_snapshot_by_id(snapshot_id: str):
    """Restore preference snapshot by ID"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        success = pm.restore_snapshot(snapshot_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def delete_preference_snapshot(snapshot_id: str):
    """Delete a preference snapshot"""
    try:
        from agent.core.preference_manager import PreferenceManager

        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        pm = PreferenceManager(preference_dir=workspace_path / "preferences")
        success = pm.delete_snapshot(snapshot_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = [
    "clear_all_data",
    "clear_all_preferences",
    "create_preference_snapshot",
    "delete_preference",
    "delete_preference_snapshot",
    "delete_task_data",
    "extract_preferences_from_data",
    "get_all_preferences",
    "get_recent_tasks",
    "ingest_manual_config",
    "list_preference_snapshots",
    "restore_preference_snapshot",
    "restore_preference_snapshot_by_id",
    "set_preference",
]
