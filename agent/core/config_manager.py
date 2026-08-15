"""Configuration Manager - Manage multiple API configurations"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Any


class ConfigManager:
    """管理多个 API 配置"""

    def __init__(self):
        self.config_dir = Path.home() / ".os-agent" / "configs"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "api_configs.json"
        self.active_config_file = self.config_dir / "active_config.txt"
        self.configs: Dict[str, Dict[str, str]] = self._load_configs()
        self.active_config = self._load_active_config()

    def _load_configs(self) -> Dict[str, Dict[str, str]]:
        """加载所有保存的配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_configs(self) -> None:
        """保存所有配置到文件"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.configs, f, indent=2, ensure_ascii=False)

    def _load_active_config(self) -> Optional[str]:
        """加载当前激活的配置名称"""
        if self.active_config_file.exists():
            try:
                with open(self.active_config_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return None
        return None

    def _save_active_config(self, config_name: str) -> None:
        """保存当前激活的配置"""
        with open(self.active_config_file, "w", encoding="utf-8") as f:
            f.write(config_name)

    def add_config(self, name: str, api_base_url: str, api_key: str, api_model: str, reasoning_effort: str = "high") -> bool:
        """添加新配置"""
        # 本地模型服务（如 llama.cpp）可以不填 API Key
        if not name or not api_base_url or not api_model:
            return False

        self.configs[name] = {
            "api_base_url": api_base_url,
            "api_key": api_key,
            "api_model": api_model,
            "reasoning_effort": reasoning_effort,
        }
        self._save_configs()

        # 如果这是第一个配置，自动激活它
        if self.active_config is None:
            self.set_active_config(name)

        return True

    def delete_config(self, name: str) -> bool:
        """删除配置"""
        if name not in self.configs:
            return False

        del self.configs[name]
        self._save_configs()

        # 如果删除的是当前活跃配置，切换到第一个可用的配置
        if self.active_config == name:
            if self.configs:
                first_config = next(iter(self.configs.keys()))
                self.set_active_config(first_config)
            else:
                self.active_config = None
                if self.active_config_file.exists():
                    self.active_config_file.unlink()

        return True

    def update_config(
        self, name: str, api_base_url: str, api_key: str, api_model: str, reasoning_effort: str = "high"
    ) -> bool:
        """更新配置"""
        if name not in self.configs:
            return False

        self.configs[name] = {
            "api_base_url": api_base_url,
            "api_key": api_key,
            "api_model": api_model,
            "reasoning_effort": reasoning_effort,
        }
        self._save_configs()
        return True

    def set_active_config(self, name: str) -> bool:
        """设置当前活跃配置"""
        if name not in self.configs:
            return False

        self.active_config = name
        self._save_active_config(name)
        return True

    def get_active_config(self) -> Optional[Dict[str, str]]:
        """获取当前活跃配置"""
        if self.active_config and self.active_config in self.configs:
            return self.configs[self.active_config].copy()
        return None

    def get_config(self, name: str) -> Optional[Dict[str, str]]:
        """获取指定配置"""
        if name in self.configs:
            return self.configs[name].copy()
        return None

    def list_configs(self) -> Dict[str, Any]:
        """列出所有配置"""
        return {
            "configs": self.configs,
            "active": self.active_config,
            "available": list(self.configs.keys()),
        }

    def import_from_env(self, config_name: str = "default") -> bool:
        """从环境变量导入配置"""
        api_base_url = os.getenv("API_BASE_URL")
        api_key = os.getenv("API_KEY")
        api_model = os.getenv("API_MODEL")

        if not (api_base_url and api_key and api_model):
            return False

        return self.add_config(config_name, api_base_url, api_key, api_model)

    def export_to_env(self, config_name: Optional[str] = None) -> bool:
        """将配置导出到环境变量"""
        config = self.get_active_config() if config_name is None else self.get_config(config_name)

        if not config:
            return False

        os.environ["API_BASE_URL"] = config["api_base_url"]
        os.environ["API_KEY"] = config["api_key"]
        os.environ["API_MODEL"] = config["api_model"]
        self.export_search_keys_to_env()

        return True

    def export_search_keys_to_env(self) -> None:
        """Keep web search API keys in runtime env if they already exist in .env."""
        for key in ("TAVILY_API_KEY",):
            value = os.getenv(key)
            if value:
                os.environ[key] = value

    def apply_config(self, config_name: Optional[str] = None) -> bool:
        """应用配置到环境变量"""
        if not self.set_active_config(config_name or self.active_config or ""):
            return False
        return self.export_to_env()
