"""JCodex desktop UI - shared runtime state.

Single owner of the mutable process state used across the desktop modules.
``main.py`` binds ``os_agent`` after the executor class is defined; helpers
and RPC modules read everything else from here.
"""

from __future__ import annotations

import threading

from dotenv import load_dotenv

from agent.core.conversation_store import ConversationStore
from agent.core.project_store import ProjectStore
from agent.ui.desktop.constants import CONVERSATION_ROOT, DATA_ROOT, PROJECT_STORE_ROOT

# ---- shared mutable state (owned by the desktop process) ----
project_root = DATA_ROOT
load_dotenv(project_root / ".env", override=True)

_skill_import_lock = threading.Lock()
_project_folder_picker_lock = threading.Lock()
_short_term_memory_locks_guard = threading.RLock()
_short_term_memory_locks: dict[str, threading.RLock] = {}
_short_term_compression_locks: dict[str, threading.Lock] = {}

os_agent: object | None = None  # bound by main.py after the class definition
state_lock = threading.Lock()
conversation_executors: dict = {}
conversation_runs: dict = {}
conversation_generations: dict = {}
_scheduled_task_conversations: dict[str, str] = {}
_scheduled_task_owners: dict[str, object] = {}

conversation_store = ConversationStore(CONVERSATION_ROOT)
project_store = ProjectStore(PROJECT_STORE_ROOT)


def _executor_for_conversation(conversation_id: str):
    """Return the isolated executor that owns one conversation's memory."""
    from agent.ui.desktop.executor import DesktopTaskExecutor  # late import (avoids cycle)

    conversation_id = str(conversation_id or "")
    if not conversation_id:
        raise ValueError("Conversation id is required")
    with state_lock:
        executor = conversation_executors.get(conversation_id)
        if executor is not None:
            return executor
        executor = DesktopTaskExecutor(shared_from=os_agent)
        executor.initialize_conversation_runtime(conversation_id, os_agent)
        conversation_executors[conversation_id] = executor
        return executor


__all__ = [
    "_executor_for_conversation",
    "_project_folder_picker_lock",
    "_scheduled_task_conversations",
    "_scheduled_task_owners",
    "_short_term_compression_locks",
    "_short_term_memory_locks",
    "_short_term_memory_locks_guard",
    "_skill_import_lock",
    "conversation_executors",
    "conversation_generations",
    "conversation_runs",
    "conversation_store",
    "os_agent",
    "project_root",
    "project_store",
    "state_lock",
]
