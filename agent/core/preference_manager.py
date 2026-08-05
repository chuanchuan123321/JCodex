"""Preference Manager - User preference extraction and version management.

Extracts and manages user preferences including:
- Operation habits
- Output style
- Security strategies

Features:
- Version management for preferences
- Cross-scenario application
- History rollback
"""

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from agent.core.ai_engine import AIEngine


class PreferenceCategory(Enum):
    """Preference categories."""
    OPERATION_HABIT = "operation_habit"
    OUTPUT_STYLE = "output_style"
    SECURITY_STRATEGY = "security_strategy"
    AI_BEHAVIOR = "ai_behavior"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    NEWEST_WINS = "newest_wins"
    OLDEST_WINS = "oldest_wins"
    MANUAL = "manual"
    MERGE = "merge"


@dataclass
class PreferenceEntry:
    """Single preference entry with versioning."""
    id: str
    category: PreferenceCategory
    key: str
    value: Any
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source: str = "system"  # system, user, ai_inference
    confidence: float = 1.0
    tags: Set[str] = field(default_factory=set)
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "key": self.key,
            "value": self.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "source": self.source,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "history": self.history,
            "metadata": self.metadata
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PreferenceEntry':
        entry = PreferenceEntry(
            id=data["id"],
            category=PreferenceCategory(data["category"]),
            key=data["key"],
            value=data["value"],
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            source=data.get("source", "system"),
            confidence=data.get("confidence", 1.0),
            tags=set(data.get("tags", [])),
            history=data.get("history", []),
            metadata=data.get("metadata", {})
        )
        return entry


@dataclass
class PreferenceSnapshot:
    """Point-in-time snapshot of all preferences."""
    snapshot_id: str
    timestamp: datetime
    entries: List[PreferenceEntry]
    description: str = ""


class PreferenceManager:
    """Main preference manager class."""

    VERSION_FILE = "preference_versions.json"
    CURRENT_FILE = "preferences_current.json"
    SNAPSHOTS_DIR = "snapshots"

    def __init__(self, preference_dir: Optional[Path] = None):
        if preference_dir is None:
            preference_dir = Path(__file__).parent.parent.parent / "workspace" / "preferences"
        self.preference_dir = preference_dir
        self.preference_dir.mkdir(parents=True, exist_ok=True)

        # Storage files
        self.version_file = self.preference_dir / self.VERSION_FILE
        self.current_file = self.preference_dir / self.CURRENT_FILE
        self.snapshots_dir = self.preference_dir / self.SNAPSHOTS_DIR
        self.snapshots_dir.mkdir(exist_ok=True)

        # In-memory cache
        self._preferences: Dict[str, PreferenceEntry] = {}
        self._version_history: Dict[str, List[Dict[str, Any]]] = {}

        # Load existing preferences
        self._load_preferences()

    def _load_preferences(self):
        """Load preferences from disk."""
        # Clear existing preferences before loading
        self._preferences.clear()

        if self.current_file.exists():
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_data in data.get("entries", []):
                        entry = PreferenceEntry.from_dict(entry_data)
                        self._preferences[entry.id] = entry
            except (json.JSONDecodeError, KeyError):
                pass

        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 确保是dict类型，否则初始化为空dict
                    self._version_history = data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                pass

    def _save_preferences(self):
        """Save preferences to disk."""
        entries = [entry.to_dict() for entry in self._preferences.values()]
        data = {
            "entries": entries,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.current_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Save version history
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(self._version_history, f, ensure_ascii=False, indent=2)

    def _generate_id(self, category: PreferenceCategory, key: str) -> str:
        """Generate preference ID."""
        content = f"{category.value}_{key}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def set_preference(self, category: PreferenceCategory, key: str, value: Any,
                      source: str = "system", confidence: float = 1.0,
                      tags: Optional[Set[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      resolution: ConflictResolution = ConflictResolution.NEWEST_WINS) -> PreferenceEntry:
        """Set a preference value with conflict resolution."""
        # Check for existing preference
        existing = self._find_preference(category, key)

        if existing:
            return self._update_preference(existing, value, source, confidence, resolution)
        else:
            return self._create_preference(category, key, value, source, confidence, tags, metadata)

    def _find_preference(self, category: PreferenceCategory, key: str) -> Optional[PreferenceEntry]:
        """Find existing preference by category and key."""
        for entry in self._preferences.values():
            if entry.category == category and entry.key == key:
                return entry
        return None

    def _create_preference(self, category: PreferenceCategory, key: str, value: Any,
                          source: str, confidence: float,
                          tags: Optional[Set[str]], metadata: Optional[Dict[str, Any]]) -> PreferenceEntry:
        """Create new preference entry."""
        entry = PreferenceEntry(
            id=self._generate_id(category, key),
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            tags=tags or set(),
            metadata=metadata or {}
        )

        self._preferences[entry.id] = entry

        # Record in version history
        self._version_history[entry.id] = [entry.to_dict()]

        self._save_preferences()
        return entry

    def _update_preference(self, existing: PreferenceEntry, value: Any,
                          source: str, confidence: float,
                          resolution: ConflictResolution) -> PreferenceEntry:
        """Update existing preference with conflict resolution."""
        old_value = existing.value

        if resolution == ConflictResolution.NEWEST_WINS:
            # Just update to new value
            pass
        elif resolution == ConflictResolution.OLDEST_WINS:
            # Keep old value, don't update
            return existing
        elif resolution == ConflictResolution.MERGE:
            # Merge values if possible
            if isinstance(old_value, dict) and isinstance(value, dict):
                value = {**old_value, **value}
            elif isinstance(old_value, list) and isinstance(value, list):
                value = list(set(old_value + value))

        # Record history
        history_entry = {
                "version": existing.version,
                "value": old_value,
                "timestamp": existing.updated_at.isoformat(),
                "source": existing.source
            }
        existing.history.append(history_entry)

        # Update entry
        existing.value = value
        existing.version += 1
        existing.updated_at = datetime.now()
        existing.source = source
        existing.confidence = confidence

        # Update version history
        if existing.id not in self._version_history:
            self._version_history[existing.id] = []
        self._version_history[existing.id].append(existing.to_dict())

        self._save_preferences()
        return existing

    def get_preference(self, category: PreferenceCategory, key: str) -> Optional[Any]:
        """Get preference value."""
        entry = self._find_preference(category, key)
        return entry.value if entry else None

    def get_all_by_category(self, category: PreferenceCategory) -> Dict[str, Any]:
        """Get all preferences in a category."""
        return {
            entry.key: entry.value
            for entry in self._preferences.values()
            if entry.category == category
        }

    def get_operation_habits(self) -> Dict[str, Any]:
        """Get operation habit preferences."""
        return self.get_all_by_category(PreferenceCategory.OPERATION_HABIT)

    def get_output_style(self) -> Dict[str, Any]:
        """Get output style preferences."""
        return self.get_all_by_category(PreferenceCategory.OUTPUT_STYLE)

    def get_security_strategies(self) -> Dict[str, Any]:
        """Get security strategy preferences."""
        return self.get_all_by_category(PreferenceCategory.SECURITY_STRATEGY)

    def delete_preference(self, category: PreferenceCategory, key: str) -> bool:
        """Delete a preference."""
        entry = self._find_preference(category, key)
        if entry:
            del self._preferences[entry.id]
            self._save_preferences()
            return True
        return False

    def clear_all(self) -> bool:
        """Clear all preferences (factory reset)."""
        try:
            self._preferences.clear()
            self._version_history.clear()

            # 清空当前文件和版本文件
            self.current_file.write_text(
                json.dumps(
                    {"entries": [], "last_updated": datetime.now().isoformat()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding='utf-8',
            )
            self.version_file.write_text("{}", encoding='utf-8')

            # 删除所有快照
            if self.snapshots_dir.exists():
                for f in self.snapshots_dir.iterdir():
                    if f.is_file():
                        f.unlink()

            return True
        except Exception:
            return False

    def create_snapshot(self, description: str = "") -> PreferenceSnapshot:
        """Create a point-in-time snapshot of all preferences."""
        snapshot_id = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:16]
        snapshot = PreferenceSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(),
            entries=list(self._preferences.values()),
            description=description
        )

        # Save snapshot file
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump({
                "snapshot_id": snapshot.snapshot_id,
                "timestamp": snapshot.timestamp.isoformat(),
                "description": snapshot.description,
                "entries": [e.to_dict() for e in snapshot.entries]
            }, f, ensure_ascii=False, indent=2)

        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore preferences from a snapshot."""
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return False

        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Clear current preferences
            self._preferences.clear()

            # Restore entries
            for entry_data in data.get("entries", []):
                entry = PreferenceEntry.from_dict(entry_data)
                self._preferences[entry.id] = entry

            self._save_preferences()
            return True
        except Exception:
            return False

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return False

        try:
            snapshot_file.unlink()
            return True
        except Exception:
            return False

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots."""
        snapshots = []
        for f in self.snapshots_dir.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    snapshots.append({
                        "snapshot_id": data.get("snapshot_id"),
                        "timestamp": data.get("timestamp"),
                        "description": data.get("description", ""),
                        "entry_count": len(data.get("entries", []))
                    })
            except Exception:
                continue

        return sorted(snapshots, key=lambda x: x.get("timestamp", ""), reverse=True)

    def get_preference_history(self, category: PreferenceCategory, key: str) -> List[Dict[str, Any]]:
        """Get version history for a preference."""
        entry = self._find_preference(category, key)
        if not entry:
            return []

        history = entry.history.copy()
        history.append({
            "version": entry.version,
            "value": entry.value,
            "timestamp": entry.updated_at.isoformat(),
            "source": entry.source
        })

        return history

    def infer_preference_from_behavior(self, behavior_data: Dict[str, Any]) -> List[PreferenceEntry]:
        """Infer preferences from user behavior data."""
        inferred = []

        # Extract operation patterns
        if "tool_usage" in behavior_data:
            habits = behavior_data["tool_usage"]
            for tool, count in habits.items():
                if count > 5:  # Frequently used tool
                    entry = self.set_preference(
                        PreferenceCategory.OPERATION_HABIT,
                        f"frequent_tool_{tool}",
                        {"tool": tool, "count": count, "frequency": "high"},
                        source="ai_inference",
                        confidence=0.7
                    )
                    inferred.append(entry)

        # Extract output format preferences
        if "output_formats" in behavior_data:
            formats = behavior_data["output_formats"]
            entry = self.set_preference(
                PreferenceCategory.OUTPUT_STYLE,
                "preferred_formats",
                formats,
                source="ai_inference",
                confidence=0.6
            )
            inferred.append(entry)

        # Extract security patterns
        if "security_actions" in behavior_data:
            actions = behavior_data["security_actions"]
            entry = self.set_preference(
                PreferenceCategory.SECURITY_STRATEGY,
                "security_behavior",
                actions,
                source="ai_inference",
                confidence=0.8
            )
            inferred.append(entry)

        return inferred

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences grouped by category."""
        result = {}
        for category in PreferenceCategory:
            result[category.value] = self.get_all_by_category(category)
        return result

    def get_preferences_for_prompt(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get preferences with full details for prompt generation."""
        result = {}
        for category in PreferenceCategory:
            entries = [
                {
                    "key": entry.key,
                    "value": entry.value,
                    "source": entry.source,
                    "confidence": entry.confidence
                }
                for entry in self._preferences.values()
                if entry.category == category
            ]
            result[category.value] = entries
        return result

    def export_preferences(self, format: str = "json") -> str:
        """Export preferences to string."""
        if format == "json":
            return json.dumps(self.get_all_preferences(), ensure_ascii=False, indent=2)
        elif format == "env":
            lines = []
            for entry in self._preferences.values():
                key = f"PREF_{entry.category.value.upper()}_{entry.key.upper()}"
                lines.append(f"{key}={entry.value}")
            return '\n'.join(lines)
        return ""

    def import_preferences(self, data: str, format: str = "json") -> int:
        """Import preferences from string."""
        count = 0
        if format == "json":
            try:
                prefs = json.loads(data)
                for category_str, entries in prefs.items():
                    try:
                        category = PreferenceCategory(category_str)
                        if isinstance(entries, dict):
                            for key, value in entries.items():
                                self.set_preference(category, key, value, source="import")
                                count += 1
                    except ValueError:
                        continue
            except json.JSONDecodeError:
                pass
        return count

    def extract_preferences_from_data(self, data_entries: List[Dict[str, Any]],
                                       api_base_url: str = None, api_key: str = None,
                                       model: str = "deepseek-v4-pro") -> Dict[str, Any]:
        """从数据条目中AI提取偏好"""
        import traceback
        import sys
        print("[PREFERENCE_MANAGER] extract_preferences_from_data 开始执行")
        print(f"[PREFERENCE_MANAGER] 函数栈:")
        for line in traceback.format_stack()[-5:]:
            print(f"  {line.strip()}")
        print(f"[PREFERENCE_MANAGER] data_entries类型: {type(data_entries)}, 长度: {len(data_entries) if data_entries else 0}")

        if not data_entries:
            return {"success": False, "message": "没有数据可供分析", "extracted_count": 0}

        # 限制数据量
        entries_text = json.dumps(data_entries[:50], ensure_ascii=False)
        print(f"[PREFERENCE_MANAGER] entries_text长度: {len(entries_text)}, 前200字: {entries_text[:200]}")

        # 构建详细的分析prompt，让AI更好地提取偏好
        prompt = f"""分析以下用户行为数据，提取用户偏好。

数据：
{entries_text}

请分析这些数据，识别用户的行为模式、习惯偏好等。

返回格式（必须返回有效JSON）：
{{"preferences": [{{"category": "operation_habit", "key": "偏好键名", "value": "偏好值", "confidence": 0.8}}], "summary": "分析总结"}}

类别必须是以下之一：operation_habit, output_style, security_strategy, ai_behavior, workflow, custom"""

        ai_content = ""
        try:
            ai_engine = AIEngine()
            ai_engine.api_base_url = AIEngine.normalize_api_base_url(api_base_url)
            ai_engine.api_path = AIEngine.get_api_path_for_base_url(ai_engine.api_base_url)
            ai_engine.api_key = api_key
            ai_engine.model = model
            result = ai_engine.call_messages(
                [{"role": "user", "content": prompt}],
                system_prompt="你是一个专业的用户行为分析助手，直接返回JSON，不要解释。",
                max_tokens=2000,
                temperature=0.1,
            )
            ai_content = result.get("content", "") or ""

            if not ai_content:
                return {"success": False, "message": "AI返回内容为空", "extracted_count": 0}

            print(f"[PREFERENCE_MANAGER] AI原始返回长度: {len(ai_content)}, 内容前100字: {ai_content[:100]}")

            # 移除think标签内容（CoT思维链），不要提取
            import re
            ai_content_clean = re.sub(r'<think>.*?</think>', '', ai_content, flags=re.DOTALL).strip()

            # 改进的JSON提取 - 尝试多种方式
            extracted_data = None
            try:
                extracted_data = json.loads(ai_content_clean)
            except json.JSONDecodeError:
                pass

            # 方法2: 尝试用正则匹配第一个完整的JSON对象
            if extracted_data is None:
                json_match = re.search(r'\{[\s\S]*\}', ai_content_clean)
                if json_match:
                    json_str = json_match.group(0)
                    print(f"[PREFERENCE_MANAGER] 正则匹配到JSON，长度: {len(json_str)}")
                    # 尝试修复常见的JSON问题
                    try:
                        extracted_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        # 尝试修复转义问题
                        print(f"[PREFERENCE_MANAGER] JSON解析失败: {e}, 尝试修复...")
                        # 修复多余的反斜杠
                        json_str_fixed = json_str.replace('\\', '\\\\')
                        try:
                            extracted_data = json.loads(json_str_fixed)
                        except json.JSONDecodeError:
                            pass

            if extracted_data is None:
                return {"success": False, "message": f"无法解析AI返回为JSON。内容:\n{ai_content_clean[:500]}", "extracted_count": 0}

            print(f"[PREFERENCE_MANAGER] 成功解析JSON，keys: {extracted_data.keys() if isinstance(extracted_data, dict) else 'N/A'}")

            # 提取preferences
            if isinstance(extracted_data, dict):
                preferences_data = extracted_data.get("preferences", [])
                summary = extracted_data.get("summary", "")
            elif isinstance(extracted_data, list):
                preferences_data = extracted_data
                summary = ""
            else:
                return {"success": False, "message": f"无法解析AI返回: {type(extracted_data)}\n内容:\n{ai_content}", "extracted_count": 0}

            # 保存偏好
            saved_count = 0
            for pref in preferences_data:
                if not isinstance(pref, dict):
                    continue
                try:
                    cat = pref.get("category", "custom")
                    key = pref.get("key", "unknown")
                    val = pref.get("value", "")
                    conf = pref.get("confidence", 0.8)
                    self.set_preference(PreferenceCategory(cat), key, val, source="ai_inference", confidence=conf)
                    saved_count += 1
                except:
                    continue

            return {
                "success": True,
                "message": f"成功提取并保存 {saved_count} 条偏好",
                "extracted_count": saved_count,
                "summary": summary
            }

        except Exception as e:
            import traceback
            return {"success": False, "message": f"提取失败: {str(e)}\nAI返回:\n{ai_content if 'ai_content' in dir() else 'N/A'}\n堆栈:\n{traceback.format_exc()[:500]}", "extracted_count": 0}

    def generate_prompt_context(self) -> str:
        """生成偏好上下文，用于导入到prompt中

        Returns:
            格式化的偏好字符串，可以直接插入到prompt
        """
        prefs = self.get_preferences_for_prompt()

        context_parts = []
        context_parts.append("【用户偏好摘要】")

        category_names = {
            "operation_habit": "操作习惯",
            "output_style": "输出风格",
            "security_strategy": "安全策略",
            "ai_behavior": "AI行为偏好",
            "workflow": "工作流程",
            "custom": "自定义"
        }

        has_prefs = False
        for category, entries in prefs.items():
            if entries and len(entries) > 0:
                has_prefs = True
                category_cn = category_names.get(category, category)
                context_parts.append(f"\n{category_cn}：")
                for entry in entries:
                    if entry.get("source") == "ai_inference":
                        context_parts.append(f"  - {entry['key']}: {entry['value']}")

        if not has_prefs:
            context_parts.append("\n（暂无记录偏好）")

        context_parts.append("\n【注意事项】")
        context_parts.append("- 根据上述偏好调整输出风格和内容")
        context_parts.append("- 重要：优先遵循用户的明确偏好设置")

        return "\n".join(context_parts)
