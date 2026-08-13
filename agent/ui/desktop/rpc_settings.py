"""JCodex desktop UI - settings and model RPC."""

import contextlib
import os

import eel
import requests
from dotenv import load_dotenv

from agent.core.ai_engine import AIEngine
from agent.core.env_utils import env_int
from agent.ui.desktop import constants, helpers, runtime


@eel.expose
def load_settings():
    """Load settings from .env file"""
    try:
        project_root = constants.DATA_ROOT
        env_file = project_root / ".env"

        settings = {
            "api_base_url": "",
            "api_key": "",
            "api_model": "",
            "supports_vision": "true",
            "tavily_api_key": "",
            "custom_system_prompt": "",
            "max_steps": "100",
            "max_tokens": "50000",
            "context_window": "256000",
            "max_web_searches": "8",
            "auto_compact_threshold_percent": "85",
        }

        if env_file.exists():
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "API_BASE_URL":
                            settings["api_base_url"] = value
                        elif key == "API_KEY":
                            settings["api_key"] = value
                        elif key == "API_MODEL":
                            settings["api_model"] = value
                        elif key == "MODEL_SUPPORTS_VISION":
                            settings["supports_vision"] = value
                        elif key == "TAVILY_API_KEY":
                            settings["tavily_api_key"] = value
                        elif key == "CUSTOM_SYSTEM_PROMPT":
                            settings["custom_system_prompt"] = value.replace("\\n", "\n")
                        elif key == "MAX_STEPS":
                            settings["max_steps"] = value
                        elif key == "MAX_TOKENS":
                            settings["max_tokens"] = value
                        elif key == "CONTEXT_WINDOW":
                            settings["context_window"] = value
                        elif key == "MAX_WEB_SEARCHES":
                            settings["max_web_searches"] = value
                        elif key == "AUTO_COMPACT_THRESHOLD_PERCENT":
                            settings["auto_compact_threshold_percent"] = value

        return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {
            "api_base_url": "",
            "api_key": "",
            "api_model": "",
            "tavily_api_key": "",
            "max_steps": "100",
            "max_tokens": "50000",
            "context_window": "256000",
            "max_web_searches": "8",
            "auto_compact_threshold_percent": "85",
        }


@eel.expose
def save_settings(settings: dict):
    """Save settings to .env file, preserving other existing settings"""
    try:
        settings = helpers._validate_runtime_settings(settings)
        project_root = constants.DATA_ROOT
        env_file = project_root / ".env"

        # 写回文件，确保根目录 .env 与当前设置面板一致
        helpers._write_env_file(env_file, settings)

        # 重新加载环境变量，确保当前进程也切换到新值
        load_dotenv(env_file, override=True)

        # 更新运行时配置，直接使用用户保存的值，避免读回旧环境变量
        configured_max_steps = int(settings.get("max_steps", "100"))
        configured_max_tokens = int(settings.get("max_tokens", "50000"))
        configured_max_web_searches = int(settings.get("max_web_searches", "8"))
        configured_context_window = int(settings.get("context_window", "256000"))
        # refresh_policy 以环境变量 CONTEXT_WINDOW 为准，先同步再刷新压缩策略
        os.environ["CONTEXT_WINDOW"] = str(configured_context_window)
        os.environ["MODEL_SUPPORTS_VISION"] = str(settings.get("supports_vision", "true"))
        os.environ["CUSTOM_SYSTEM_PROMPT"] = str(settings.get("custom_system_prompt", ""))
        with runtime.state_lock:
            configured_executors = set(runtime.conversation_executors.values()) | {runtime.os_agent}
        for executor in configured_executors:
            executor.max_steps = configured_max_steps
            executor.max_tokens = configured_max_tokens
            executor.max_web_searches = configured_max_web_searches
            executor.context_window = configured_context_window
            executor.context_compactor.refresh_policy(executor.context_window, None)
            executor.compress_at = executor.context_compactor.policy.trigger_tokens
            executor.show_knowledge_appendix = False
            executor._latest_context_usage = None
        if runtime.os_agent.memory_manager:
            runtime.os_agent.accumulated_compression = (
                runtime.os_agent.memory_manager.load_accumulated_compression()
            )

        # 更新 AI Engine 的配置
        for executor in configured_executors:
            if not executor.ai_engine:
                continue
            executor.ai_engine.api_key = os.getenv("API_KEY", "")
            api_base_url = os.getenv("API_BASE_URL", "https://api.deepseek.com")

            # 清理URL中可能存在的旧API路径
            api_base = api_base_url.rstrip("/")
            for old_path in [
                "/v4/chat/completions",
                "/v1/chat/completions",
                "/v4",
                "/v1",
            ]:
                if api_base.endswith(old_path):
                    api_base = api_base[: -len(old_path)]
                    break
            executor.ai_engine.api_base_url = api_base.rstrip("/")

            # 根据URL重新选择API路径
            if "bigmodel.cn" in executor.ai_engine.api_base_url:
                executor.ai_engine.api_path = "/v4/chat/completions"
            else:
                executor.ai_engine.api_path = "/v1/chat/completions"

            executor.ai_engine.model = os.getenv("API_MODEL", "deepseek-v4-pro")
            executor.ai_engine.max_tokens = configured_max_tokens
            if not any(
                run.executor is executor and run.status in {"running", "waiting"}
                for run in runtime.conversation_runs.values()
            ):
                executor.rebuild_langgraph_runner()

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _friendly_local_model_name(model_id: str) -> str:
    """Derive a short display name from a model id (e.g. llama.cpp gguf paths)."""
    name = str(model_id or "").rstrip("/").split("/")[-1]
    for suffix in (".gguf", ".bin", ".safetensors", ".onnx"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name or str(model_id or "")


@eel.expose
def list_local_models(base_url: str = ""):
    """List models served by a local llama.cpp / OpenAI-compatible / Ollama server."""
    base = str(base_url or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        return {
            "success": False,
            "error": "请输入以 http:// 或 https:// 开头的本地地址",
        }
    models: list[dict] = []
    errors: list[str] = []
    server_type = ""
    endpoints = (
        (f"{base}/v1/models", "data", "id"),
        (f"{base}/models", "models", "name"),
        (f"{base}/api/tags", "models", "name"),
    )
    for endpoint, container_key, id_key in endpoints:
        try:
            response = requests.get(endpoint, timeout=8)
            if response.status_code != 200:
                errors.append(f"{endpoint} → HTTP {response.status_code}")
                continue
            data = response.json()
            if not server_type:
                server_type = str(response.headers.get("Server", "") or "").strip()
            for item in data.get(container_key) or []:
                raw_id = (
                    str(item.get(id_key, "") or "").strip()
                    if isinstance(item, dict)
                    else str(item or "").strip()
                )
                if not raw_id:
                    continue
                friendly = _friendly_local_model_name(raw_id)
                models.append({"id": raw_id, "name": friendly})
            if models:
                break
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{endpoint} → {exc}")
    if not models:
        detail = "；".join(errors) if errors else "地址无法访问"
        return {"success": False, "error": f"未查询到模型：{detail}"}
    unique_models: dict[str, dict] = {}
    for entry in models:
        unique_models.setdefault(str(entry["id"]), entry)
    return {
        "success": True,
        "models": sorted(unique_models.values(), key=lambda entry: str(entry["name"]).lower()),
        "server": server_type,
        "base_url": base,
    }


@eel.expose
def list_api_configs():
    """List all saved API configurations"""
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        return config_manager.list_configs()
    except Exception as e:
        return {"success": False, "error": str(e), "available": [], "active": None}


@eel.expose
def load_api_config(config_name):
    """Load and persist a specific API configuration as active."""
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        config = config_manager.get_config(config_name)
        if config and config_manager.set_active_config(config_name):
            return {"success": True, "config": config, "active": config_name}
        return {"success": False, "error": "Configuration not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def save_api_config(config_name, api_base_url, api_key, api_model, reasoning_effort="high"):
    """Save the current API configuration and make it active."""
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        if config_manager.add_config(
            config_name, api_base_url, api_key, api_model, reasoning_effort
        ) and config_manager.set_active_config(config_name):
            return {"success": True, "active": config_name}
        return {"success": False, "error": "Failed to save configuration"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def delete_api_config(config_name):
    """Delete an API configuration"""
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        if config_manager.delete_config(config_name):
            return {"success": True}
        return {"success": False, "error": "Configuration not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def set_active_config(config_name):
    """Set a configuration as active and apply it to the runtime immediately."""
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        config = config_manager.get_config(config_name)
        if not config or not config_manager.set_active_config(config_name):
            return {"success": False, "error": "Configuration not found"}
        config_manager.export_to_env(config_name)
        env_file = constants.DATA_ROOT / ".env"
        helpers._write_env_file(
            env_file,
            {
                "api_base_url": config.get("api_base_url", ""),
                "api_key": config.get("api_key", ""),
                "api_model": config.get("api_model", ""),
                "reasoning_effort": config.get("reasoning_effort", "high"),
            },
        )
        load_dotenv(env_file, override=True)
        with runtime.state_lock:
            executors = set(runtime.conversation_executors.values()) | {runtime.os_agent}
        for executor in executors:
            if not executor.ai_engine:
                continue
            executor.ai_engine.api_key = config.get("api_key", "")
            executor.ai_engine.api_base_url = AIEngine.normalize_api_base_url(
                config.get("api_base_url", "")
            )
            executor.ai_engine.api_path = AIEngine.get_api_path_for_base_url(
                executor.ai_engine.api_base_url
            )
            executor.ai_engine.model = config.get("api_model", "")
            configured_effort = str(config.get("reasoning_effort", "") or "").strip()
            executor.ai_engine.reasoning_effort = configured_effort or (
                "high" if "deepseek" in str(config.get("api_model", "")).lower() else ""
            )
            if not any(
                run.executor is executor and run.status in {"running", "waiting"}
                for run in runtime.conversation_runs.values()
            ):
                executor.rebuild_langgraph_runner()
        return {"success": True, "config": config, "active": config_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def update_config_reasoning_effort(config_name, reasoning_effort):
    """Update the reasoning effort of a saved config (DeepSeek series only)."""
    try:
        from agent.core.config_manager import ConfigManager

        effort = str(reasoning_effort or "").strip()
        if effort and effort not in ("low", "medium", "high", "max"):
            return {"success": False, "error": "Invalid reasoning effort"}

        config_manager = ConfigManager()
        config = config_manager.get_config(config_name)
        if not config:
            return {"success": False, "error": "Configuration not found"}

        if not config_manager.update_config(
            config_name,
            config.get("api_base_url", ""),
            config.get("api_key", ""),
            config.get("api_model", ""),
            effort or "high",
        ):
            return {"success": False, "error": "Failed to update configuration"}

        if config_name == config_manager.active_config:
            config_manager.export_to_env(config_name)
            env_file = constants.DATA_ROOT / ".env"
            helpers._write_env_file(env_file, {"reasoning_effort": effort or "high"})
            load_dotenv(env_file, override=True)
            with runtime.state_lock:
                executors = set(runtime.conversation_executors.values()) | {runtime.os_agent}
            for executor in executors:
                if executor.ai_engine:
                    executor.ai_engine.reasoning_effort = effort or "high"
        return {"success": True, "active": config_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def preview_context_window(context_window):
    """Live-preview a context window choice without persisting .env."""
    try:
        context_window = int(context_window or 0)
        if context_window <= 0:
            raise ValueError("context_window must be positive")
        context_window = min(2_000_000, max(8_000, context_window))
        os.environ["CONTEXT_WINDOW"] = str(context_window)
        with runtime.state_lock:
            executors = set(runtime.conversation_executors.values()) | {runtime.os_agent}
        for executor in executors:
            executor.context_window = context_window
            executor.context_compactor.refresh_policy(context_window, None)
            executor.compress_at = executor.context_compactor.policy.trigger_tokens
            executor._latest_context_usage = None
        return {
            "success": True,
            "context_window": context_window,
            "compress_at": executor.compress_at,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def get_token_count(conversation_id: str = ""):
    """Return the same full-context estimate used by automatic compaction."""
    try:
        target_id = str(conversation_id or runtime.conversation_store.active_id() or "")
        executor = runtime._executor_for_conversation(target_id)
        usage = executor.get_current_token_usage()
        return {
            **usage,
            "compress_at": int(usage.get("compress_at", executor.compress_at)),
            "auto_compact_threshold_percent": executor.context_compactor.policy.trigger_percent,
            "max_tokens": int(usage.get("context_window", executor.context_window)),
            "response_max_tokens": executor.max_tokens,
        }
    except Exception:
        return {
            "tokens": 0,
            "compress_at": int(
                env_int("CONTEXT_WINDOW", 256000)
                * env_int("AUTO_COMPACT_THRESHOLD_PERCENT", 85)
                / 100
            ),
            "auto_compact_threshold_percent": env_int("AUTO_COMPACT_THRESHOLD_PERCENT", 85),
            "max_tokens": env_int("CONTEXT_WINDOW", 256000),
            "response_max_tokens": env_int("MAX_TOKENS", 50000),
        }


@eel.expose
def get_embedding_status():
    """Return the embedding provider used by Grok-style memory search."""
    try:
        if runtime.os_agent.memory_store is None and runtime.os_agent.ai_engine is not None:
            # 初始化中途失败（例如首次启动被并发/残留后端打断）时懒恢复
            # 记忆存储，避免界面一直显示「记忆检索异常」。
            target_id = (
                runtime.os_agent.conversation_id or runtime.conversation_store.active_id() or ""
            )
            if target_id:
                with contextlib.suppress(RuntimeError, ValueError, OSError):
                    runtime.os_agent.activate_conversation(target_id)
        if runtime.os_agent.memory_store:
            return runtime.os_agent.memory_store.embedding_provider.status()
        return {"provider": "uninitialized", "available": False}
    except Exception as e:
        return {"provider": "unknown", "available": False, "error": str(e)}


__all__ = [
    "_friendly_local_model_name",
    "delete_api_config",
    "get_embedding_status",
    "get_token_count",
    "list_api_configs",
    "list_local_models",
    "load_api_config",
    "load_settings",
    "preview_context_window",
    "save_api_config",
    "save_settings",
    "set_active_config",
    "update_config_reasoning_effort",
]
