"""Knowledge Base - Structured knowledge storage and retrieval.

Features:
- Structured storage of workflows, cases, templates
- Conflict detection and resolution
- Intelligent retrieval with ranking
- Knowledge provenance tracking
"""

import hashlib
import json
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from agent.core.ai_engine import AIEngine
from agent.core.embedding_provider import (
    cosine_similarity,
    create_embedding_provider,
    vector_hash,
)


class KnowledgeType(Enum):
    """Knowledge types."""
    WORKFLOW = "workflow"
    SUCCESS_CASE = "success_case"
    TEMPLATE = "template"
    FACT = "fact"
    RULE = "rule"
    CUSTOM = "custom"

class ConflictStrategy(Enum):
    """Conflict resolution strategies."""
    KEEP_BOTH = "keep_both"
    NEWEST = "newest"
    OLDEST = "oldest"
    HIGHEST_CONFIDENCE = "highest_confidence"
    MERGE = "merge"
    MANUAL = "manual"

@dataclass
class KnowledgeEntry:
    """Single knowledge entry."""
    id: str
    knowledge_type: KnowledgeType
    title: str
    content: str
    tags: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    provenance: str = ""  # Source of this knowledge
    confidence: float = 1.0
    usage_count: int = 0
    last_used: datetime | None = None
    related_entries: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    status: str = "active"  # active, deprecated, merged
    previous_versions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "content": self.content,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "provenance": self.provenance,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "related_entries": list(self.related_entries),
            "metadata": self.metadata,
            "version": self.version,
            "status": self.status,
            "previous_versions": self.previous_versions
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> 'KnowledgeEntry':
        return KnowledgeEntry(
            id=data["id"],
            knowledge_type=KnowledgeType(data["knowledge_type"]),
            title=data["title"],
            content=data["content"],
            tags=set(data.get("tags", [])),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            provenance=data.get("provenance", ""),
            confidence=data.get("confidence", 1.0),
            usage_count=data.get("usage_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            related_entries=set(data.get("related_entries", [])),
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
            status=data.get("status", "active"),
            previous_versions=data.get("previous_versions", [])
        )

@dataclass
class ConflictRecord:
    """Record of a knowledge conflict."""
    id: str
    entry_a_id: str
    entry_b_id: str
    conflict_field: str
    value_a: Any
    value_b: Any
    detected_at: datetime
    resolution: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str = "system"  # system, user, ai

class KnowledgeBase:
    """Main knowledge base class."""

    KNOWLEDGE_FILE = "knowledge_base.json"
    CONFLICTS_FILE = "knowledge_conflicts.json"
    INDEX_FILE = "knowledge_index.json"
    VECTORS_FILE = "knowledge_vectors.json"

    def __init__(self, knowledge_dir: Path | None = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent.parent / "workspace" / "knowledge"
        self.knowledge_dir = knowledge_dir
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        # Storage files
        self.knowledge_file = self.knowledge_dir / self.KNOWLEDGE_FILE
        self.conflicts_file = self.knowledge_dir / self.CONFLICTS_FILE
        self.index_file = self.knowledge_dir / self.INDEX_FILE
        self.vectors_file = self.knowledge_dir / self.VECTORS_FILE

        # In-memory storage
        self._entries: dict[str, KnowledgeEntry] = {}
        self._conflicts: list[ConflictRecord] = []
        self._index: dict[str, list[str]] = {}  # tag -> entry_ids
        self._vectors: dict[str, dict[str, Any]] = {}
        self._last_retrieved: list[tuple[KnowledgeEntry, float]] = []
        self.embedding_provider = create_embedding_provider()

        # Load existing data
        self._load_knowledge()
        self._load_conflicts()
        self._load_index()
        self._load_vectors()
        self._ensure_vectors()

    def _load_knowledge(self):
        """Load knowledge from disk."""
        if self.knowledge_file.exists():
            try:
                with open(self.knowledge_file, encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_data in data.get("entries", []):
                        entry = KnowledgeEntry.from_dict(entry_data)
                        self._entries[entry.id] = entry
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_conflicts(self):
        """Load conflict records."""
        if self.conflicts_file.exists():
            try:
                with open(self.conflicts_file, encoding='utf-8') as f:
                    data = json.load(f)
                    for conflict_data in data.get("conflicts", []):
                        self._conflicts.append(ConflictRecord(
                            id=conflict_data["id"],
                            entry_a_id=conflict_data["entry_a_id"],
                            entry_b_id=conflict_data["entry_b_id"],
                            conflict_field=conflict_data["conflict_field"],
                            value_a=conflict_data["value_a"],
                            value_b=conflict_data["value_b"],
                            detected_at=datetime.fromisoformat(conflict_data["detected_at"]),
                            resolution=conflict_data.get("resolution"),
                            resolved_at=datetime.fromisoformat(conflict_data["resolved_at"]) if conflict_data.get("resolved_at") else None,
                            resolved_by=conflict_data.get("resolved_by", "system")
                        ))
            except json.JSONDecodeError:
                pass

    def _load_index(self):
        """Load search index."""
        if self.index_file.exists():
            try:
                with open(self.index_file, encoding='utf-8') as f:
                    self._index = json.load(f)
            except json.JSONDecodeError:
                self._index = {}
        else:
            self._rebuild_index()

    def _rebuild_index(self):
        """Rebuild search index from entries."""
        self._index = {}
        for entry_id, entry in self._entries.items():
            # Index by tags
            for tag in entry.tags:
                if tag not in self._index:
                    self._index[tag] = []
                if entry_id not in self._index[tag]:
                    self._index[tag].append(entry_id)

            # Index by knowledge type
            ktype = entry.knowledge_type.value
            if ktype not in self._index:
                self._index[ktype] = []
            if entry_id not in self._index[ktype]:
                self._index[ktype].append(entry_id)

            # Index by title words
            words = re.findall(r'\w+', entry.title.lower())
            for word in words:
                if word not in self._index:
                    self._index[word] = []
                if entry_id not in self._index[word]:
                    self._index[word].append(entry_id)

    def _save_knowledge(self):
        """Save knowledge to disk."""
        data = {
            "entries": [entry.to_dict() for entry in self._entries.values()],
            "last_updated": datetime.now().isoformat()
        }
        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_conflicts(self):
        """Save conflict records."""
        data = {
            "conflicts": [
                {
                    "id": c.id,
                    "entry_a_id": c.entry_a_id,
                    "entry_b_id": c.entry_b_id,
                    "conflict_field": c.conflict_field,
                    "value_a": c.value_a,
                    "value_b": c.value_b,
                    "detected_at": c.detected_at.isoformat(),
                    "resolution": c.resolution,
                    "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                    "resolved_by": c.resolved_by
                }
                for c in self._conflicts
            ]
        }
        with open(self.conflicts_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_index(self):
        """Save search index."""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f)

    def _load_vectors(self):
        """Load vector index from disk."""
        if self.vectors_file.exists():
            try:
                with open(self.vectors_file, encoding='utf-8') as f:
                    data = json.load(f)
                    vectors = data.get("vectors", {})
                    if isinstance(vectors, dict):
                        self._vectors = vectors
            except json.JSONDecodeError:
                self._vectors = {}

    def _save_vectors(self):
        """Save vector index to disk."""
        data = {
            "provider": self.embedding_provider.status(),
            "last_updated": datetime.now().isoformat(),
            "vectors": self._vectors,
        }
        with open(self.vectors_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def _vector_text(self, entry: KnowledgeEntry) -> str:
        """Build the text used for vectorization."""
        tags = " ".join(sorted(entry.tags))
        return (
            f"{entry.knowledge_type.value}\n"
            f"{entry.title}\n"
            f"{tags}\n"
            f"{entry.content}"
        )

    def _upsert_vector(self, entry: KnowledgeEntry) -> None:
        """Create or refresh a vector for a knowledge entry."""
        if entry.status == "deprecated":
            self._vectors.pop(entry.id, None)
            return

        text = self._vector_text(entry)
        text_hash = vector_hash(text)
        existing = self._vectors.get(entry.id)
        provider_status = self.embedding_provider.status()
        provider_name = str(provider_status.get("provider", "unknown"))
        dimension = int(provider_status.get("dimension") or 0)

        if (
            existing
            and existing.get("text_hash") == text_hash
            and existing.get("provider") == provider_name
        ):
            return

        vector = self.embedding_provider.embed(text)
        self._vectors[entry.id] = {
            "vector": vector,
            "text_hash": text_hash,
            "provider": provider_name,
            "dimension": dimension or len(vector),
            "updated_at": datetime.now().isoformat(),
        }

    def _ensure_vectors(self) -> None:
        """Backfill vectors for active entries when possible."""
        changed = False
        for entry in self._entries.values():
            if entry.status != "active":
                continue
            try:
                before = self._vectors.get(entry.id)
                self._upsert_vector(entry)
                if self._vectors.get(entry.id) != before:
                    changed = True
            except Exception:
                continue
        if changed:
            self._save_vectors()

    def get_vector_status(self) -> dict[str, Any]:
        """Return vector index diagnostics for UI and evaluation reports."""
        provider_status = self.embedding_provider.status()
        active_ids = {entry.id for entry in self._entries.values() if entry.status == "active"}
        indexed_ids = set(self._vectors.keys())
        return {
            "provider": provider_status,
            "active_entries": len(active_ids),
            "indexed_entries": len(active_ids & indexed_ids),
            "missing_entries": len(active_ids - indexed_ids),
            "vector_file": str(self.vectors_file),
        }

    def _generate_id(self, title: str, ktype: KnowledgeType) -> str:
        """Generate unique knowledge ID."""
        content = f"{ktype.value}_{title}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _stable_id(self, prefix: str, key: str) -> str:
        """Generate a stable ID for imported memory fragments."""
        content = f"{prefix}:{key}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _detect_conflicts(self, entry: KnowledgeEntry, existing: KnowledgeEntry | None = None) -> list[ConflictRecord]:
        """Detect conflicts with existing entries."""
        conflicts = []

        candidates = [existing] if existing is not None else list(self._entries.values())
        for other in candidates:
            if not other or other.id == entry.id:
                continue
            if self._calculate_similarity(entry.title, other.title) > 0.8:
                conflict = ConflictRecord(
                    id=hashlib.md5(f"{entry.id}_{other.id}".encode()).hexdigest()[:16],
                    entry_a_id=entry.id,
                    entry_b_id=other.id,
                    conflict_field="title",
                    value_a=entry.title,
                    value_b=other.title,
                    detected_at=datetime.now()
                )
                conflicts.append(conflict)

            # Check for same tags with different content
            if entry.tags & other.tags and entry.content != other.content:
                conflict = ConflictRecord(
                    id=hashlib.md5(f"{entry.id}_{other.id}_content".encode()).hexdigest()[:16],
                    entry_a_id=entry.id,
                    entry_b_id=other.id,
                    conflict_field="content",
                    value_a=entry.content[:100],
                    value_b=other.content[:100],
                    detected_at=datetime.now()
                )
                conflicts.append(conflict)

        return conflicts

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (simple word overlap)."""
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def add_knowledge(self, knowledge_type: KnowledgeType, title: str, content: str,
                    tags: set[str] | None = None,
                    provenance: str = "",
                    confidence: float = 1.0,
                    metadata: dict[str, Any] | None = None,
                    conflict_strategy: ConflictStrategy = ConflictStrategy.HIGHEST_CONFIDENCE) -> KnowledgeEntry:
        """Add new knowledge entry."""
        entry = KnowledgeEntry(
            id=self._generate_id(title, knowledge_type),
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            tags=tags or set(),
            provenance=provenance,
            confidence=confidence,
            metadata=metadata or {}
        )

        # Check for conflicts
        existing = self._find_similar_entry(title, knowledge_type)
        if existing:
            conflicts = self._detect_conflicts(entry, existing)
            if conflicts:
                self._handle_conflicts(entry, existing, conflicts, conflict_strategy)
                return entry

        # Add entry
        self._entries[entry.id] = entry

        # Update index
        self._update_entry_index(entry)
        self._upsert_vector(entry)

        self._save_knowledge()
        self._save_vectors()
        return entry

    def upsert_knowledge(
        self,
        entry_id: str,
        knowledge_type: KnowledgeType,
        title: str,
        content: str,
        tags: set[str] | None = None,
        provenance: str = "",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEntry:
        """Insert or update a knowledge entry with a stable ID.

        This is mainly used by memory synchronization so the same archive does
        not create duplicate entries every time it is refreshed.
        """
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            entry.knowledge_type = knowledge_type
            entry.title = title
            entry.content = content
            entry.tags = tags or set()
            entry.updated_at = datetime.now()
            entry.provenance = provenance
            entry.confidence = confidence
            if metadata:
                entry.metadata.update(metadata)
        else:
            entry = KnowledgeEntry(
                id=entry_id,
                knowledge_type=knowledge_type,
                title=title,
                content=content,
                tags=tags or set(),
                provenance=provenance,
                confidence=confidence,
                metadata=metadata or {},
            )
            self._entries[entry.id] = entry

        self._update_entry_index(entry)
        self._upsert_vector(entry)
        self._save_knowledge()
        self._save_vectors()
        return entry

    def _find_similar_entry(self, title: str, ktype: KnowledgeType) -> KnowledgeEntry | None:
        """Find similar entry by title and type."""
        for entry in self._entries.values():
            if (
                entry.knowledge_type == ktype
                and self._calculate_similarity(title, entry.title) > 0.7
            ):
                return entry
        return None

    def _handle_conflicts(self, new_entry: KnowledgeEntry, existing: KnowledgeEntry,
                         conflicts: list[ConflictRecord], strategy: ConflictStrategy):
        """Handle detected conflicts."""
        # Record conflicts
        self._conflicts.extend(conflicts)

        if strategy == ConflictStrategy.KEEP_BOTH:
            # Just record conflicts, keep both entries
            pass

        elif strategy == ConflictStrategy.NEWEST:
            # Replace old with new
            existing.status = "deprecated"
            existing.previous_versions.append(existing.to_dict())
            self._entries[new_entry.id] = new_entry

        elif strategy == ConflictStrategy.OLDEST:
            # Keep old, discard new
            new_entry.status = "deprecated"

        elif strategy == ConflictStrategy.HIGHEST_CONFIDENCE:
            if new_entry.confidence > existing.confidence:
                existing.status = "deprecated"
                existing.previous_versions.append(existing.to_dict())
                self._entries[new_entry.id] = new_entry
            else:
                new_entry.status = "deprecated"

        elif strategy == ConflictStrategy.MERGE:
            # Merge content
            new_entry.content = f"{existing.content}\n---\n{new_entry.content}"
            new_entry.related_entries.add(existing.id)
            existing.related_entries.add(new_entry.id)
            self._entries[new_entry.id] = new_entry

        self._rebuild_index()
        for item in (existing, new_entry):
            try:
                self._upsert_vector(item)
            except Exception:
                continue
        self._save_knowledge()
        self._save_conflicts()
        self._save_vectors()

    def _update_entry_index(self, entry: KnowledgeEntry):
        """Update search index for an entry."""
        for tag in entry.tags:
            if tag not in self._index:
                self._index[tag] = []
            if entry.id not in self._index[tag]:
                self._index[tag].append(entry.id)

        ktype = entry.knowledge_type.value
        if ktype not in self._index:
            self._index[ktype] = []
        if entry.id not in self._index[ktype]:
            self._index[ktype].append(entry.id)

        self._save_index()

    def delete_knowledge(self, entry_id: str) -> bool:
        """Delete knowledge entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._vectors.pop(entry_id, None)
            self._last_retrieved = [
                item for item in self._last_retrieved if item[0].id != entry_id
            ]
            self._rebuild_index()
            self._save_knowledge()
            self._save_index()
            self._save_vectors()
            return True
        return False

    def _keyword_score(self, entry: KnowledgeEntry, query_words: set[str]) -> float:
        """Calculate lexical relevance score."""
        title_text = entry.title.lower()
        content_text = entry.content.lower()
        title_words = set(re.findall(r'\w+', title_text))
        content_words = set(re.findall(r'\w+', content_text))

        title_match = len(query_words & title_words)
        content_match = len(query_words & content_words)
        substring_bonus = 0.0
        for word in query_words:
            if word and word in title_text:
                substring_bonus += 2.0
            if word and word in content_text:
                substring_bonus += 1.0

        query_cjk = set("".join(re.findall(r"[\u4e00-\u9fff]", " ".join(query_words))))
        if query_cjk:
            title_cjk = set(re.findall(r"[\u4e00-\u9fff]", title_text))
            content_cjk = set(re.findall(r"[\u4e00-\u9fff]", content_text))
            substring_bonus += len(query_cjk & title_cjk) * 0.5
            substring_bonus += len(query_cjk & content_cjk) * 0.25

        # Tag bonus
        tag_bonus = len([t for t in entry.tags if t.lower() in query_words]) * 0.5
        return (
            (title_match * 2.0)
            + content_match
            + substring_bonus
            + tag_bonus
            + (entry.confidence * 0.5)
        )

    def search(self, query: str, knowledge_type: KnowledgeType | None = None,
              tags: list[str] | None = None, limit: int = 10) -> list[tuple[KnowledgeEntry, float]]:
        """Search knowledge with vector-first hybrid relevance ranking."""
        query_words = set(re.findall(r'\w+', query.lower()))
        results = []
        query_vector = None
        try:
            query_vector = self.embedding_provider.embed(query)
        except Exception:
            query_vector = None

        for entry in self._entries.values():
            if entry.status == "deprecated":
                continue

            if knowledge_type and entry.knowledge_type != knowledge_type:
                continue

            if tags and not any(tag in entry.tags for tag in tags):
                continue

            keyword_score = self._keyword_score(entry, query_words)
            vector_score = 0.0

            if query_vector is not None:
                vector_record = self._vectors.get(entry.id)
                if vector_record is None:
                    try:
                        self._upsert_vector(entry)
                        vector_record = self._vectors.get(entry.id)
                        self._save_vectors()
                    except Exception:
                        vector_record = None

                if vector_record:
                    vector_score = cosine_similarity(
                        query_vector, vector_record.get("vector", [])
                    )

            score = (vector_score * 10.0) + keyword_score
            if score > 0:
                results.append((entry, score))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        if not results:
            fallback_entries = [
                entry
                for entry in self._entries.values()
                if entry.status == "active"
                and (not knowledge_type or entry.knowledge_type == knowledge_type)
                and (not tags or any(tag in entry.tags for tag in tags))
            ]
            fallback_entries.sort(key=lambda entry: entry.updated_at, reverse=True)
            results = [(entry, 0.001) for entry in fallback_entries[:limit]]
        self._last_retrieved = results[:limit]
        return self._last_retrieved

    def generate_prompt_context(self, query: str, limit: int = 5) -> str:
        """Generate compact knowledge context for the agent prompt."""
        results = self.search(query, limit=limit)
        if not results:
            return "（暂无相关知识）"

        lines = ["【相关知识记忆】"]
        for entry, score in results:
            content = entry.content.strip().replace("\n", " ")
            if len(content) > 500:
                content = content[:500] + "..."
            tags = ", ".join(sorted(entry.tags)) if entry.tags else "none"
            lines.append(
                f"- [{entry.knowledge_type.value}] {entry.title} "
                f"(score={score:.3f}, tags={tags}): {content}"
            )
        return "\n".join(lines)

    def _prepare_memory_extract_text(self, memory_text: str, max_chars: int = 12000) -> str:
        """Trim noisy runtime records before sending memory to the extraction model."""
        text = re.sub(r"<think>[\s\S]*?</think>", "", memory_text)
        text = re.sub(r"<minimax:tool_call>[\s\S]*?</minimax:tool_call>", "", text)
        text = re.sub(r"<invoke[\s\S]*?</invoke>", "", text)
        text = re.sub(r"<content>[\s\S]{1200,}</content>", "", text)

        lines = []
        current_len = 0
        skip_patterns = (
            "workspace/skills/",
            "node_modules/",
            "<parameter name=\"filePath\">",
            "执行工具:",
            "错误详情",
        )
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(pattern in line for pattern in skip_patterns):
                continue
            if len(line) > 800:
                line = line[:800] + "..."
            lines.append(line)
            current_len += len(line) + 1
            if current_len >= max_chars:
                break
        return "\n".join(lines).strip()

    def _parse_ai_json(self, ai_content: str) -> dict[str, Any] | None:
        """Parse model JSON output using the same tolerant strategy as preferences."""
        content = re.sub(r"<think>[\s\S]*?</think>", "", ai_content, flags=re.DOTALL).strip()
        content = re.sub(r"<minimax:tool_call>[\s\S]*?</minimax:tool_call>", "", content, flags=re.DOTALL).strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"\s*```$", "", content).strip()

        parsed: Any | None = None
        with suppress(json.JSONDecodeError):
            parsed = json.loads(content)

        if parsed is None:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                json_str = match.group(0)
                try:
                    parsed = json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        parsed = json.loads(json_str.replace("\\", "\\\\"))
                    except json.JSONDecodeError:
                        parsed = None

        if parsed is None:
            match = re.search(r"\[[\s\S]*\]", content)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = None

        if isinstance(parsed, list):
            return {"items": parsed, "summary": ""}
        if isinstance(parsed, dict):
            return parsed
        return None

    def extract_knowledge_from_memory(
        self,
        memory_text: str,
        archive_path: str = "",
        task_id: str = "",
        api_base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Use AI to extract reusable knowledge from full memory text.

        This is the main path for the competition requirement: automatically
        derive knowledge items from accumulated memory, instead of manual entry.
        """
        api_base_url = api_base_url or os.getenv("API_BASE_URL")
        api_key = api_key or os.getenv("API_KEY")
        model = model or os.getenv("API_MODEL", "deepseek-v4-pro")

        if not api_base_url or not api_key:
            return {"success": False, "message": "API配置不完整", "extracted_count": 0}

        source_text = memory_text.strip()
        if not source_text:
            return {"success": False, "message": "没有可提取的记忆内容", "extracted_count": 0}

        source_text = self._prepare_memory_extract_text(source_text)
        if not source_text:
            return {"success": False, "message": "记忆内容清理后为空，无法提取知识", "extracted_count": 0}

        ai_engine = AIEngine()
        ai_engine.api_base_url = AIEngine.normalize_api_base_url(api_base_url)
        ai_engine.api_path = AIEngine.get_api_path_for_base_url(ai_engine.api_base_url)
        ai_engine.api_key = api_key
        ai_engine.model = model
        entries_text = json.dumps(
            {"memory": source_text, "archive_path": archive_path, "task_id": task_id},
            ensure_ascii=False,
        )
        prompt = f"""分析以下用户完整记忆，提取可复用知识。

数据：
{entries_text}

要求：
1. 只抽取可复用知识，不要逐字搬运全部记忆。
2. 优先抽取工作流、成功案例、模板、规则、事实。
3. 忽略工具调用语法、文件路径、报错堆栈、源码片段。
4. 不要调用任何工具，不要输出 <minimax:tool_call>。

返回格式（必须返回有效JSON）：
{{"items": [{{"knowledge_type": "workflow", "title": "标题", "content": "知识内容", "tags": ["tag1"], "confidence": 0.8}}], "summary": "提取总结"}}

knowledge_type 必须是以下之一：workflow, success_case, template, fact, rule, custom"""

        try:
            system_prompt = (
                "你是一个专业的知识抽取助手。直接返回JSON，不要解释，"
                "不要调用工具，不要输出XML或<minimax:tool_call>。"
            )
            content = ""
            extracted = None
            for attempt in range(2):
                result = ai_engine.call_messages(
                    [{"role": "user", "content": prompt}],
                    system_prompt=system_prompt,
                    max_tokens=3000,
                    temperature=0.1,
                )

                if result.get("finish_reason") == "error":
                    return {
                        "success": False,
                        "message": result.get("content", "API调用失败"),
                        "extracted_count": 0,
                    }

                content = result.get("content", "") or ""
                if not content:
                    return {"success": False, "message": "AI返回为空", "extracted_count": 0}
                extracted = self._parse_ai_json(content)
                if extracted is not None:
                    break
                if "<minimax:tool_call>" not in content or attempt == 1:
                    break
                prompt = (
                    "上一次输出包含工具调用标签，这是错误的。请只基于下面数据重新提取知识，"
                    "本次只能输出JSON对象，不能调用工具，不能输出XML。\n\n"
                    f"数据：\n{entries_text}\n\n"
                    '返回格式：{"items": [{"knowledge_type": "custom", "title": "标题", '
                    '"content": "知识内容", "tags": ["tag1"], "confidence": 0.8}], '
                    '"summary": "提取总结"}'
                )

            if extracted is None:
                return {
                    "success": False,
                    "message": f"无法解析AI返回JSON。内容前500字:\n{content[:500]}",
                    "extracted_count": 0,
                }

            items = extracted.get("items", [])
            saved = 0
            for idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                ktype = item.get("knowledge_type", "custom")
                title = item.get("title", "").strip()
                content_text = item.get("content", "").strip()
                if not title or not content_text:
                    continue

                try:
                    knowledge_type = KnowledgeType(ktype)
                except Exception:
                    knowledge_type = KnowledgeType.CUSTOM

                tags = set(item.get("tags", []))
                tags.update({"auto_extracted", "memory"})
                metadata = {
                    "source": "memory_ai_extract",
                    "archive_path": archive_path,
                    "task_id": task_id,
                    "item_index": idx,
                }

                stable_id = self._stable_id(
                    f"ai-memory-{knowledge_type.value}",
                    f"{archive_path}:{title}:{idx}",
                )
                self.upsert_knowledge(
                    entry_id=stable_id,
                    knowledge_type=knowledge_type,
                    title=title,
                    content=content_text,
                    tags=tags,
                    provenance=archive_path,
                    confidence=float(item.get("confidence", 0.8)),
                    metadata=metadata,
                )
                saved += 1

            return {
                "success": True,
                "message": extracted.get("summary", f"成功提取 {saved} 条知识"),
                "extracted_count": saved,
            }

        except Exception as e:
            return {"success": False, "message": f"提取失败: {e}", "extracted_count": 0}

    def get_knowledge_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        by_type = {}
        for entry in self._entries.values():
            ktype = entry.knowledge_type.value
            by_type[ktype] = by_type.get(ktype, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_type": by_type,
            "active_count": sum(1 for e in self._entries.values() if e.status == "active"),
            "deprecated_count": sum(1 for e in self._entries.values() if e.status == "deprecated"),
            "total_usage": sum(e.usage_count for e in self._entries.values()),
            "conflict_count": len(self._conflicts),
            "unresolved_conflicts": sum(1 for c in self._conflicts if c.resolution is None),
            "vector_status": self.get_vector_status()
        }

    def list_entries(self, knowledge_type: KnowledgeType | None = None,
                    status: str = "active", limit: int = 50) -> list[KnowledgeEntry]:
        """List knowledge entries with filters."""
        entries = list(self._entries.values())

        if knowledge_type:
            entries = [e for e in entries if e.knowledge_type == knowledge_type]

        if status:
            entries = [e for e in entries if e.status == status]

        return sorted(entries, key=lambda x: x.updated_at, reverse=True)[:limit]

    def get_conflicts(self, unresolved_only: bool = True) -> list[dict[str, Any]]:
        """Get conflict records."""
        conflicts = []
        for c in self._conflicts:
            if unresolved_only and c.resolution is not None:
                continue
            conflicts.append({
                "id": c.id,
                "entry_a_id": c.entry_a_id,
                "entry_b_id": c.entry_b_id,
                "entry_a_title": self._entries.get(c.entry_a_id, KnowledgeEntry("", KnowledgeType.CUSTOM, "")).title if c.entry_a_id in self._entries else "Unknown",
                "entry_b_title": self._entries.get(c.entry_b_id, KnowledgeEntry("", KnowledgeType.CUSTOM, "")).title if c.entry_b_id in self._entries else "Unknown",
                "conflict_field": c.conflict_field,
                "value_a": c.value_a,
                "value_b": c.value_b,
                "detected_at": c.detected_at.isoformat(),
                "resolution": c.resolution,
                "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None
            })
        return conflicts

