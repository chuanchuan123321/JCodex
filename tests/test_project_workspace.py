"""Project workspace persistence and task-root regressions."""

from pathlib import Path

from agent.core.conversation_store import ConversationStore
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.project_store import ProjectStore


def test_project_binding_does_not_copy_or_delete_local_code(tmp_path: Path) -> None:
    project_root = tmp_path / "demo-project"
    project_root.mkdir()
    source = project_root / "app.py"
    source.write_text("print('hello')\n", encoding="utf-8")
    (project_root / "AGENTS.md").write_text("Run pytest.\n", encoding="utf-8")
    store = ProjectStore(tmp_path / "project-store")

    project = store.create("Demo", str(project_root), "Keep Python 3.11 support.")
    inspected = store.inspect(project["id"])

    assert inspected["root_path"] == str(project_root.resolve())
    assert inspected["context_files"] == ["AGENTS.md"]

    store.delete(project["id"])
    assert source.read_text(encoding="utf-8") == "print('hello')\n"
    assert project_root.is_dir()


def test_conversation_project_relationship_can_be_detached(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    project_id = "12345678-1234-1234-1234-123456789abc"
    project_task = store.create("项目任务", project_id)
    ordinary_task = store.create("普通任务")

    assert store.load(project_task["id"])["project_id"] == project_id
    assert store.load(ordinary_task["id"])["project_id"] is None

    detached = store.detach_project(project_id)

    assert detached == [project_task["id"]]
    assert store.load(project_task["id"])["project_id"] is None


def test_relative_code_tools_use_bound_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "bound-project"
    workspace_root = tmp_path / "agent-workspace"
    project_root.mkdir()
    workspace_root.mkdir()
    executor = ExtendedToolExecutor(
        project_root=project_root,
        workspace_root=workspace_root,
        preview_manager=object(),
        restrict_reads_to_project=True,
    )

    assert executor.execute_file_write(
        {"path": "src/app.py", "content": "value = 1\n"}
    ).startswith("File written")
    assert (project_root / "src" / "app.py").read_text(encoding="utf-8") == (
        "value = 1\n"
    )
    assert not (workspace_root / "src" / "app.py").exists()

    grep_result = executor.execute_grep(
        {"pattern": "value", "path": "src", "include": "*.py"}
    )
    assert "app.py" in grep_result
    edit_result = executor.execute_edit(
        {
            "filePath": "src/app.py",
            "oldString": "value = 1",
            "newString": "value = 2",
        }
    )
    assert "Edit applied successfully" in edit_result
    assert (project_root / "src" / "app.py").read_text(encoding="utf-8") == (
        "value = 2\n"
    )


def test_ordinary_task_can_read_and_search_absolute_paths_outside_default_root(
    tmp_path: Path,
) -> None:
    default_root = tmp_path / "os-agent"
    external_root = tmp_path / "Desktop" / "reference-code"
    default_root.mkdir()
    external_root.mkdir(parents=True)
    target = external_root / "notes.txt"
    target.write_text("NORMAL_TASK_TOKEN\n", encoding="utf-8")
    executor = ExtendedToolExecutor(
        project_root=default_root,
        workspace_root=default_root / "workspace",
        preview_manager=object(),
        restrict_reads_to_project=False,
    )

    read_result = executor.execute_file_read({"path": str(target)})
    grep_result = executor.execute_grep(
        {"pattern": "NORMAL_TASK_TOKEN", "path": str(external_root)}
    )
    glob_result = executor.execute_glob(
        {"pattern": "*.txt", "path": str(external_root)}
    )

    assert "NORMAL_TASK_TOKEN" in read_result
    assert "notes.txt" in grep_result
    assert glob_result == "notes.txt"


def test_project_task_can_read_and_search_paths_outside_project(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    external_root = tmp_path / "external"
    project_root.mkdir()
    external_root.mkdir()
    target = external_root / "private.txt"
    target.write_text("outside\n", encoding="utf-8")
    executor = ExtendedToolExecutor(
        project_root=project_root,
        workspace_root=tmp_path / "workspace",
        preview_manager=object(),
        restrict_reads_to_project=True,
    )

    assert "outside" in executor.execute_file_read({"path": str(target)})
    assert "private.txt" in executor.execute_grep(
        {"pattern": "outside", "path": str(external_root)}
    )
    assert executor.execute_glob(
        {"pattern": "*.txt", "path": str(external_root)}
    ) == "private.txt"


def test_file_tools_protect_os_agent_source_except_output_and_temp(
    tmp_path: Path,
) -> None:
    protected_root = tmp_path / "OS-Agent"
    project_root = tmp_path / "user-project"
    external_root = tmp_path / "external"
    protected_root.mkdir()
    project_root.mkdir()
    external_root.mkdir()
    (protected_root / "workspace" / "output").mkdir(parents=True)
    (protected_root / "workspace" / "temp").mkdir(parents=True)
    protected_file = protected_root / "agent.py"
    protected_file.write_text("original\n", encoding="utf-8")
    external_file = external_root / "editable.txt"
    external_file.write_text("before\n", encoding="utf-8")
    executor = ExtendedToolExecutor(
        project_root=project_root,
        workspace_root=protected_root / "workspace",
        protected_root=protected_root,
        preview_manager=object(),
    )

    blocked_write = executor.execute_file_write(
        {"path": str(protected_root / "new.py"), "content": "new\n"}
    )
    blocked_edit = executor.execute_edit(
        {
            "filePath": str(protected_file),
            "oldString": "original",
            "newString": "changed",
        }
    )

    for result in (
        blocked_write,
        blocked_edit,
    ):
        assert "JCodex source is protected" in result
    assert protected_file.read_text(encoding="utf-8") == "original\n"
    assert not (protected_root / "new.py").exists()

    output_result = executor.execute_file_write(
        {
            "path": str(protected_root / "workspace" / "output" / "result.txt"),
            "content": "output\n",
        }
    )
    temp_result = executor.execute_file_write(
        {
            "path": str(protected_root / "workspace" / "temp" / "scratch.txt"),
            "content": "temp\n",
        }
    )
    external_result = executor.execute_edit(
        {
            "filePath": str(external_file),
            "oldString": "before",
            "newString": "after",
        }
    )

    assert output_result.startswith("File written")
    assert temp_result.startswith("File written")
    assert "Edit applied successfully" in external_result
    assert external_file.read_text(encoding="utf-8") == "after\n"


def test_file_tool_protection_blocks_symlinks_into_os_agent_source(
    tmp_path: Path,
) -> None:
    protected_root = tmp_path / "OS-Agent"
    project_root = tmp_path / "user-project"
    protected_root.mkdir()
    project_root.mkdir()
    protected_file = protected_root / "settings.py"
    protected_file.write_text("safe\n", encoding="utf-8")
    linked_file = project_root / "linked-settings.py"
    linked_file.symlink_to(protected_file)
    executor = ExtendedToolExecutor(
        project_root=project_root,
        workspace_root=protected_root / "workspace",
        protected_root=protected_root,
        preview_manager=object(),
    )

    result = executor.execute_file_write(
        {"path": str(linked_file), "content": "changed\n"}
    )

    assert "JCodex source is protected" in result
    assert protected_file.read_text(encoding="utf-8") == "safe\n"


def test_frontend_exposes_project_workspace_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "agent" / "ui" / "desktop" / "index.html").read_text(
        encoding="utf-8"
    )
    source = (root / "agent" / "ui" / "desktop" / "app.js").read_text(
        encoding="utf-8"
    )

    for element_id in (
        "newProjectButton",
        "projectList",
        "projectDialog",
        "projectNameInput",
        "projectPathInput",
        "projectInstructionsInput",
        "activeProjectName",
    ):
        assert f'id="{element_id}"' in html
    assert "async function refreshProjects()" in source
    assert "function renderProjectList()" in source
    assert "在项目中新建任务" not in source
    assert "eel.create_project(name, rootPath, instructions)" in source
    assert "eel.create_conversation('新任务', String(projectId || ''))" in source


def test_project_welcome_heading_and_first_message_transition() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "agent" / "ui" / "desktop" / "index.html").read_text(
        encoding="utf-8"
    )
    source = (root / "agent" / "ui" / "desktop" / "app.js").read_text(
        encoding="utf-8"
    )

    assert 'id="welcomeTitle"' in html
    assert "今天想在“${projectName}”里完成什么？" in source
    assert "function updateWelcomeHeading(" in source
    hide_welcome = source.split("function hideWelcome()", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "querySelector('.welcome-message')" in hide_welcome
    assert "welcome.remove()" in hide_welcome
    assert "setTimeout" not in hide_welcome
