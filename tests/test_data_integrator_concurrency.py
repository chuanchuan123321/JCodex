import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from agent.core.data_integrator import DataIntegrator


def test_instances_for_same_directory_share_reentrant_lock(tmp_path):
    first = DataIntegrator(data_dir=tmp_path)
    second = DataIntegrator(data_dir=tmp_path / ".")

    assert first._file_lock is second._file_lock

    # start_task performs nested session and raw/index operations and therefore
    # also verifies that the shared lock is reentrant.
    task_id = first.start_task("nested lock check")
    first.end_task()

    assert task_id
    assert first.get_current_task_id() is None


def test_concurrent_instances_do_not_lose_sessions_or_entries(tmp_path):
    worker_count = 12
    entries_per_worker = 20
    start_barrier = Barrier(worker_count)

    def write_task(worker_id):
        integrator = DataIntegrator(data_dir=tmp_path)
        start_barrier.wait()
        task_id = integrator.start_task(f"task {worker_id}")
        for entry_number in range(entries_per_worker):
            integrator.ingest_tool_result(
                "test_tool",
                {"worker": worker_id, "entry": entry_number},
                {"success": True, "output": f"{worker_id}:{entry_number}"},
            )
        integrator.end_task()
        return task_id

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        task_ids = list(executor.map(write_task, range(worker_count)))

    verifier = DataIntegrator(data_dir=tmp_path)
    sessions = verifier._load_task_sessions()
    index = verifier._load_index()
    raw_lines = [
        json.loads(line)
        for line in verifier.raw_data_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Each task adds task_start, tool results, and task_end entries.
    expected_entry_count = worker_count * (entries_per_worker + 2)
    assert len(set(task_ids)) == worker_count
    assert len(sessions) == worker_count
    assert {session["task_id"] for session in sessions} == set(task_ids)
    assert all(session["status"] == "已完成" for session in sessions)
    assert all(session["end_time"] for session in sessions)
    assert index["total_count"] == expected_entry_count
    assert len(index["entries"]) == expected_entry_count
    assert len(raw_lines) == expected_entry_count
    assert {entry["id"] for entry in index["entries"]} == {
        entry["id"] for entry in raw_lines
    }
