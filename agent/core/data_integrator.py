"""数据整合模块 - 多源数据整合与预处理

统一接入以下数据：
- 工具执行结果
- 用户行为数据
- 手动配置信息

数据清洗、格式标准化、数据质量校验。
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any

_DATA_DIR_LOCKS_GUARD = RLock()
_DATA_DIR_LOCKS: dict[str, Any] = {}


def _get_data_dir_lock(data_dir: Path):
    """Return the process-wide lock for a data directory."""
    key = str(data_dir.expanduser().resolve(strict=False))
    with _DATA_DIR_LOCKS_GUARD:
        lock = _DATA_DIR_LOCKS.get(key)
        if lock is None:
            lock = RLock()
            _DATA_DIR_LOCKS[key] = lock
        return lock


class 数据源类型(Enum):
    """数据源类型"""
    工具结果 = "tool_result"
    用户行为 = "user_behavior"
    手动配置 = "manual_config"
    AI响应 = "ai_response"
    系统事件 = "system_event"


class 数据质量等级(Enum):
    """数据质量等级"""
    高 = "high"
    中 = "medium"
    低 = "low"
    无效 = "invalid"


@dataclass
class 统一数据条目:
    """单条统一数据条目"""
    id: str
    source: 数据源类型
    timestamp: datetime
    data_type: str
    content: dict[str, Any]
    quality: 数据质量等级 = 数据质量等级.中
    validated: bool = False
    raw_data: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    task_id: str | None = None  # 所属任务ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "data_type": self.data_type,
            "content": self.content,
            "quality": self.quality.value,
            "validated": self.validated,
            "tags": self.tags,
            "confidence": self.confidence,
            "task_id": self.task_id
        }


@dataclass
class 任务记录:
    """任务记录 - 分组展示用"""
    task_id: str
    start_time: datetime
    end_time: datetime | None
    user_request: str
    steps_count: int
    tools_used: list[str]
    status: str  # 进行中, 已完成
    entries: list[统一数据条目] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "user_request": self.user_request,
            "steps_count": self.steps_count,
            "tools_used": self.tools_used,
            "status": self.status,
            "entries": [e.to_dict() for e in self.entries]
        }


class 数据清洗器:
    """数据清洗和标准化工具"""

    @staticmethod
    def clean_text(text: str) -> str:
        """清洗和标准化文本数据"""
        if not text:
            return ""
        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        # 标准化空白字符
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def clean_json(data: dict[str, Any]) -> dict[str, Any]:
        """清洗JSON数据"""
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = 数据清洗器.clean_text(value)
            elif isinstance(value, dict):
                cleaned[key] = 数据清洗器.clean_json(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    数据清洗器.clean_text(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                cleaned[key] = value
        return cleaned

    @staticmethod
    def standardize_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
        """标准化工具执行结果"""
        if isinstance(result, str):
            return {
                "success": True,
                "output": 数据清洗器.clean_text(result),
                "error": None
            }
        if isinstance(result, dict):
            return {
                "success": result.get("success", True),
                "output": 数据清洗器.clean_text(str(result.get("output", result))),
                "error": result.get("error")
            }
        return {
            "success": True,
            "output": str(result),
            "error": None
        }

    @staticmethod
    def validate_data(entry: 统一数据条目) -> bool:
        """校验数据质量"""
        if not entry.content:
            entry.quality = 数据质量等级.无效
            return False

        # 根据数据源检查必填字段
        if (
            entry.source == 数据源类型.工具结果
            and "tool" not in entry.content
            and "output" not in entry.content
        ):
            entry.quality = 数据质量等级.低
            return False

        entry.validated = True
        return True


class 数据整合器:
    """数据整合器主类"""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "workspace" / "data"
        self.data_dir = Path(data_dir).expanduser().resolve(strict=False)
        self._file_lock = _get_data_dir_lock(self.data_dir)

        with self._file_lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # 数据存储文件
            self.raw_data_file = self.data_dir / "raw_data.jsonl"
            self.data_index_file = self.data_dir / "data_index.json"
            self.task_sessions_file = self.data_dir / "task_sessions.json"

            # 当前任务ID
            self._current_task_id: str | None = None
            self._current_task_start: datetime | None = None

            # 初始化索引
            self._init_index()
            self._init_task_sessions()

            self.cleaner = 数据清洗器()

    def _init_task_sessions(self):
        """初始化任务会话存储"""
        with self._file_lock:
            if not self.task_sessions_file.exists():
                self._save_task_sessions([])

    def _load_task_sessions(self) -> list[dict[str, Any]]:
        """加载任务会话"""
        with self._file_lock:
            try:
                with open(self.task_sessions_file, encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return []

    def _save_task_sessions(self, sessions: list[dict[str, Any]]):
        """保存任务会话"""
        with self._file_lock, open(self.task_sessions_file, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def start_task(self, user_request: str) -> str:
        """开始一个新任务"""
        import uuid
        with self._file_lock:
            self._current_task_id = uuid.uuid4().hex[:12]
            self._current_task_start = datetime.now()

            # 记录任务开始
            sessions = self._load_task_sessions()
            sessions.append({
                "task_id": self._current_task_id,
                "start_time": self._current_task_start.isoformat(),
                "end_time": None,
                "user_request": user_request,
                "steps_count": 0,
                "tools_used": [],
                "status": "进行中"
            })
            self._save_task_sessions(sessions)

            # 记录用户行为
            self.ingest_user_behavior(
                action="task_start",
                params={"request": user_request},
                task_id=self._current_task_id
            )

            return self._current_task_id

    def end_task(self, status: str = "已完成"):
        """结束当前任务"""
        with self._file_lock:
            if not self._current_task_id:
                return

            sessions = self._load_task_sessions()
            for session in sessions:
                if session["task_id"] == self._current_task_id:
                    session["end_time"] = datetime.now().isoformat()
                    session["status"] = status
                    break
            self._save_task_sessions(sessions)

            # 记录任务结束
            self.ingest_user_behavior(
                action="task_end",
                params={"task_id": self._current_task_id, "status": status},
                task_id=self._current_task_id
            )

            self._current_task_id = None
            self._current_task_start = None

    def get_current_task_id(self) -> str | None:
        """获取当前任务ID"""
        with self._file_lock:
            return self._current_task_id

    def get_recent_tasks(self, limit: int = 20) -> list[任务记录]:
        """获取最近的任务列表（按任务分组）"""
        with self._file_lock:
            sessions = self._load_task_sessions()[-limit:]
            tasks = []

            for session_data in reversed(sessions):
                # 获取该任务的所有条目
                entries = self.query_entries(task_id=session_data["task_id"], limit=100)

                # 统计工具使用
                tools_used = []
                steps_count = 0
                for entry in entries:
                    if entry.source == 数据源类型.工具结果:
                        tool_name = entry.content.get("tool", "unknown")
                        if tool_name not in tools_used:
                            tools_used.append(tool_name)
                        steps_count += 1

                task = 任务记录(
                    task_id=session_data["task_id"],
                    start_time=datetime.fromisoformat(session_data["start_time"]),
                    end_time=datetime.fromisoformat(session_data["end_time"]) if session_data.get("end_time") else None,
                    user_request=session_data.get("user_request", ""),
                    steps_count=steps_count,
                    tools_used=tools_used,
                    status=session_data.get("status", "进行中"),
                    entries=entries
                )
                tasks.append(task)

            return tasks

    def _init_index(self):
        """初始化数据索引"""
        with self._file_lock:
            if not self.data_index_file.exists():
                self._save_index({
                    "entries": [],
                    "last_updated": datetime.now().isoformat(),
                    "total_count": 0
                })

    def _load_index(self) -> dict[str, Any]:
        """加载数据索引"""
        with self._file_lock:
            try:
                with open(self.data_index_file, encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {"entries": [], "last_updated": datetime.now().isoformat(), "total_count": 0}

    def _save_index(self, index: dict[str, Any]):
        """保存数据索引"""
        with self._file_lock:
            index["last_updated"] = datetime.now().isoformat()
            with open(self.data_index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

    def _generate_id(self, data: dict[str, Any], source: 数据源类型) -> str:
        """生成数据条目唯一ID"""
        content_str = json.dumps(data, sort_keys=True)
        hash_str = f"{source.value}_{content_str}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_str.encode()).hexdigest()[:16]

    def ingest_tool_result(self, tool_name: str, params: dict[str, Any],
                          result: Any, context: dict[str, Any] | None = None,
                          task_id: str | None = None) -> 统一数据条目:
        """接入工具执行结果"""
        with self._file_lock:
            # 如果没指定task_id，使用当前任务
            if task_id is None:
                task_id = self._current_task_id

            standardized = self.cleaner.standardize_tool_result(tool_name, result)

            content = {
                "tool": tool_name,
                "params": self.cleaner.clean_json(params),
                "result": standardized,
                "context": context or {}
            }

            entry = 统一数据条目(
                id=self._generate_id(content, 数据源类型.工具结果),
                source=数据源类型.工具结果,
                timestamp=datetime.now(),
                data_type="tool_execution",
                content=content,
                raw_data={"original_result": result},
                task_id=task_id
            )

            self.cleaner.validate_data(entry)
            self._append_raw_entry(entry)
            return entry

    def ingest_user_behavior(self, action: str, params: dict[str, Any],
                            context: dict[str, Any] | None = None,
                            task_id: str | None = None) -> 统一数据条目:
        """接入用户行为数据"""
        with self._file_lock:
            # 如果没指定task_id，使用当前任务
            if task_id is None:
                task_id = self._current_task_id

            content = {
                "action": action,
                "params": self.cleaner.clean_json(params),
                "context": context or {}
            }

            entry = 统一数据条目(
                id=self._generate_id(content, 数据源类型.用户行为),
                source=数据源类型.用户行为,
                timestamp=datetime.now(),
                data_type="user_behavior",
                content=content,
                task_id=task_id
            )

            self.cleaner.validate_data(entry)
            self._append_raw_entry(entry)
            return entry

    def ingest_manual_config(self, config_type: str, config_data: dict[str, Any],
                             source: str = "manual") -> 统一数据条目:
        """注入手动配置"""
        with self._file_lock:
            content = {
                "config_type": config_type,
                "data": self.cleaner.clean_json(config_data),
                "source": source
            }

            entry = 统一数据条目(
                id=self._generate_id(content, 数据源类型.手动配置),
                source=数据源类型.手动配置,
                timestamp=datetime.now(),
                data_type="config",
                content=content
            )

            self.cleaner.validate_data(entry)
            self._append_raw_entry(entry)
            return entry

    def _append_raw_entry(self, entry: 统一数据条目):
        """追加数据条目到原始数据文件"""
        with self._file_lock:
            with open(self.raw_data_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')

            # 更新索引
            index = self._load_index()
            index["entries"].append({
                "id": entry.id,
                "source": entry.source.value,
                "timestamp": entry.timestamp.isoformat(),
                "data_type": entry.data_type,
                "quality": entry.quality.value,
                "task_id": entry.task_id
            })
            index["total_count"] = len(index["entries"])
            self._save_index(index)

    def get_recent_entries(self, limit: int = 50,
                          source: 数据源类型 | None = None) -> list[统一数据条目]:
        """获取最近的数据条目"""
        with self._file_lock:
            index = self._load_index()
            entries_info = index.get("entries", [])[-limit:]

            results = []
            for info in entries_info:
                if source and info["source"] != source.value:
                    continue
                # 从原始文件读取
                try:
                    with open(self.raw_data_file, encoding='utf-8') as f:
                        for line in f:
                            entry_data = json.loads(line)
                            if entry_data["id"] == info["id"]:
                                entry = self._dict_to_entry(entry_data)
                                results.append(entry)
                                break
                except Exception:
                    continue

            return results

    def _dict_to_entry(self, data: dict[str, Any]) -> 统一数据条目:
        """将字典转换为统一数据条目"""
        return 统一数据条目(
            id=data["id"],
            source=数据源类型(data["source"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data_type=data["data_type"],
            content=data["content"],
            quality=数据质量等级(data["quality"]),
            validated=data["validated"],
            tags=data.get("tags", []),
            confidence=data.get("confidence", 1.0),
            task_id=data.get("task_id")
        )

    def get_stats(self) -> dict[str, Any]:
        """获取数据统计"""
        with self._file_lock:
            index = self._load_index()
            entries = index.get("entries", [])

            stats = {
                "total_entries": index.get("total_count", 0),
                "by_source": {},
                "by_quality": {},
                "recent_count": len(entries[-100:]) if len(entries) > 100 else len(entries)
            }

            for entry_info in entries:
                source = entry_info.get("source", "unknown")
                quality = entry_info.get("quality", "unknown")
                stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
                stats["by_quality"][quality] = stats["by_quality"].get(quality, 0) + 1

            return stats

    def query_entries(self, data_type: str | None = None,
                     source: 数据源类型 | None = None,
                     start_time: datetime | None = None,
                     end_time: datetime | None = None,
                     task_id: str | None = None,
                     limit: int = 100) -> list[统一数据条目]:
        """按条件查询数据条目"""
        with self._file_lock:
            index = self._load_index()
            results = []

            for entry_info in index.get("entries", []):
                if data_type and entry_info.get("data_type") != data_type:
                    continue
                if source and entry_info.get("source") != source.value:
                    continue
                if task_id and entry_info.get("task_id") != task_id:
                    continue

                timestamp = datetime.fromisoformat(entry_info["timestamp"])
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue

                # 读取完整条目
                try:
                    with open(self.raw_data_file, encoding='utf-8') as f:
                        for line in f:
                            entry_data = json.loads(line)
                            if entry_data["id"] == entry_info["id"]:
                                results.append(self._dict_to_entry(entry_data))
                                break
                except Exception:
                    continue

                if len(results) >= limit:
                    break

            return results

    def delete_entry(self, entry_id: str) -> bool:
        """删除指定的数据条目"""
        with self._file_lock:
            try:
                # 从索引中移除
                index = self._load_index()
                original_count = len(index["entries"])
                index["entries"] = [e for e in index["entries"] if e["id"] != entry_id]
                if len(index["entries"]) == original_count:
                    return False  # 没找到
                self._save_index(index)

                # 从原始文件中移除（重建文件）
                temp_file = self.raw_data_file.with_suffix('.tmp')
                with (
                    open(self.raw_data_file, encoding='utf-8') as f_in,
                    open(temp_file, 'w', encoding='utf-8') as f_out,
                ):
                    for line in f_in:
                        entry_data = json.loads(line)
                        if entry_data["id"] != entry_id:
                            f_out.write(line)
                temp_file.replace(self.raw_data_file)
                return True
            except Exception:
                return False

    def delete_task(self, task_id: str) -> bool:
        """删除指定任务的所有数据条目"""
        with self._file_lock:
            try:
                # 从索引中移除
                index = self._load_index()
                index["entries"] = [e for e in index["entries"] if e.get("task_id") != task_id]
                index["total_count"] = len(index["entries"])
                self._save_index(index)

                # 从原始文件中移除
                temp_file = self.raw_data_file.with_suffix('.tmp')
                with (
                    open(self.raw_data_file, encoding='utf-8') as f_in,
                    open(temp_file, 'w', encoding='utf-8') as f_out,
                ):
                    for line in f_in:
                        entry_data = json.loads(line)
                        if entry_data.get("task_id") != task_id:
                            f_out.write(line)
                temp_file.replace(self.raw_data_file)

                # 从任务会话中移除
                sessions = self._load_task_sessions()
                sessions = [s for s in sessions if s["task_id"] != task_id]
                self._save_task_sessions(sessions)

                return True
            except Exception:
                return False

    def clear_all(self) -> bool:
        """清空所有数据（恢复出厂设置）"""
        with self._file_lock:
            try:
                # 清空索引
                self._save_index({"entries": [], "last_updated": datetime.now().isoformat(), "total_count": 0})

                # 清空原始数据文件
                if self.raw_data_file.exists():
                    self.raw_data_file.write_text("", encoding='utf-8')

                # 清空任务会话
                self._save_task_sessions([])

                return True
            except Exception:
                return False

    def prune_orphan_entries(self) -> int:
        """Remove entries that are no longer attached to an existing task."""
        with self._file_lock:
            sessions = self._load_task_sessions()
            active_task_ids = {
                session.get("task_id")
                for session in sessions
                if session.get("task_id")
            }
            index = self._load_index()
            entries = index.get("entries", [])
            keep_ids = {
                entry["id"]
                for entry in entries
                if entry.get("task_id") in active_task_ids
            }
            removed_count = len(entries) - len(keep_ids)
            if removed_count <= 0:
                return 0

            index["entries"] = [entry for entry in entries if entry["id"] in keep_ids]
            index["total_count"] = len(index["entries"])
            self._save_index(index)

            if self.raw_data_file.exists():
                temp_file = self.raw_data_file.with_suffix('.tmp')
                with (
                    open(self.raw_data_file, encoding='utf-8') as f_in,
                    open(temp_file, 'w', encoding='utf-8') as f_out,
                ):
                    for line in f_in:
                        try:
                            entry_data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if entry_data.get("id") in keep_ids:
                            f_out.write(line)
                temp_file.replace(self.raw_data_file)

            return removed_count

    def get_task_entries_for_analysis(self, task_id: str | None = None) -> list[dict[str, Any]]:
        """获取任务条目数据用于AI分析偏好"""
        with self._file_lock:
            if task_id:
                entries = self.query_entries(task_id=task_id, limit=500)
            else:
                # 默认只分析仍在任务列表中的数据，避免已删除任务或旧孤儿数据反复影响提取结果。
                active_task_ids = {
                    session.get("task_id")
                    for session in self._load_task_sessions()
                    if session.get("task_id")
                }
                if not active_task_ids:
                    entries = []
                else:
                    entries = []
                    for active_task_id in active_task_ids:
                        entries.extend(self.query_entries(task_id=active_task_id, limit=500))
                    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
                    entries = entries[:500]

            return [{
                "id": e.id,
                "source": e.source.value,
                "timestamp": e.timestamp.isoformat(),
                "data_type": e.data_type,
                "content": e.content,
                "task_id": e.task_id
            } for e in entries]


# 别名导出（兼容英文导入）
DataIntegrator = 数据整合器
