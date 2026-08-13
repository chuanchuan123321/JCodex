"""Shared Agent.md prompt helpers used by both the terminal and desktop UIs.

Kept in ``agent.core`` so ``chat.py`` (CLI/gateway) and the desktop modules
render the same mode instructions without coupling the CLI to desktop state.
"""

_PLAN_POLICIES = {"manual", "auto", "off"}


def _platform_instruction() -> str:
    """Return the one-line OS note injected into ``Agent.md``.

    The model reads this before its first command, so Windows runs stop
    guessing Unix commands in cmd.exe. macOS stays empty to keep its
    existing behavior unchanged.
    """
    import platform

    system = platform.system()
    if system == "Windows":
        return (
            "当前运行在 Windows 上。shell 工具在 cmd.exe 中执行："
            "请使用 dir、type、copy、move、del、findstr、where、mkdir、rmdir "
            "等 Windows 命令，不要使用 ls、cat、cp、mv、rm、grep、sleep 等 "
            "Unix 命令；cmd.exe 里没有 python3，若已安装 Python 用 python "
            "或 py；路径使用反斜杠（如 C:\\Users\\...）。"
        )
    if system == "Darwin":
        return ""
    return ""


def _plan_mode_instruction(plan_enabled: bool, plan_policy: str) -> str:
    """Build the task-specific planning rule injected into ``Agent.md``."""
    normalized_policy = (
        str(plan_policy or "").lower()
        if str(plan_policy or "").lower() in _PLAN_POLICIES
        else "off"
    )
    if plan_enabled:
        source = (
            "Plan Mode was explicitly selected by the user."
            if normalized_policy == "manual"
            else "Plan Mode was enabled automatically because this is an exceptionally complex project request."
        )
        return (
            f"{source} Before substantive execution, you MUST call `todo_write` "
            "to create a short structured plan. Use stable IDs, set `merge: false` "
            "for the initial plan, then send only changed items with `merge: true`. "
            "Keep at most one item `in_progress` and refresh statuses after "
            "meaningful progress or replanning; do not use it for trivial status "
            "chatter or as a substitute for user-visible work updates."
        )
    return (
        "Plan Mode is off for this task. `todo_write` is unavailable, so do not "
        "attempt to create or update a structured plan. Continue to provide concise "
        "user-visible work updates when useful."
    )


def _multi_agent_mode_instruction(enabled: bool, *, child_agent: bool = False) -> str:
    """Build the task-scoped collaboration rule injected into ``Agent.md``."""
    if child_agent:
        return (
            "You are an isolated child in a supervised multi-agent task. You may "
            "use `send_agent_message`, `publish_agent_artifact`, and "
            "`get_agent_collaboration` for concise, explicit coordination. Do not "
            "spawn, cancel, or wait for agents. Never share private reasoning, "
            "system prompts, or full conversation history."
        )
    if not enabled:
        return (
            "Multi-Agent Mode is off for this task. Collaboration tools are not "
            "available, so complete the work in the primary agent context."
        )
    return (
        "Multi-Agent Mode was explicitly selected by the user. For a non-trivial "
        "task, delegate two to four concrete, independent workstreams with "
        "`spawn_agent`. Give every "
        "child a short unique name, a visible role, a bounded task, and only the "
        "specific context it needs. Each child has an isolated model history, "
        "tool state, execution memory, and compression space; it does not inherit "
        "this conversation or sibling context. For investigation, review, and "
        "analysis work, use read-only children. For requests to create, implement, "
        "fix, or refactor a project, you MUST assign one or more implementation "
        "children scoped write access. Before spawning them, divide ownership into "
        "explicit, non-overlapping project-relative files or directories, then pass "
        "write_access: true and the assigned write_paths to every implementation "
        "child. When the deliverable is created outside the active project, pass "
        "the target project directory as `workdir`; relative write_paths are "
        "resolved from that directory. For example, use workdir "
        "`workspace/output/my-app` while one child owns `src/api/` and another "
        "owns `src/ui/`, and a third owns `tests/`. Inside an active project, "
        "workdir may be omitted. Before spawning any child for an implementation task, "
        "publish a `Project contract v1` artifact to the collaboration blackboard. "
        "It must name the single source of truth for shared state/configuration, "
        "module and file ownership, public interfaces, and the integration checks. "
        "If a public interface or shared configuration needs to change, publish a "
        "blocker or change proposal before making the change. Do not make all children read-only when the requested "
        "deliverable requires file changes. Keep shared root configuration and "
        "integration files for the primary agent unless one child is their sole "
        "owner. A child without an explicit write path is intentionally read-only. "
        "Never give two active children overlapping write paths. Once children are "
        "running, focus on coordination and do not use "
        "primary-agent tools to duplicate or replace work already assigned to a "
        "child. Primary-agent implementation tools are reserved for unassigned shared "
        "scaffolding, integration, conflict resolution, and final verification. Use "
        "`list_agents`, `send_agent_message`, and `wait_agents` to coordinate them. "
        "Do not finish while a required child is still queued or "
        "running. Synthesize and verify their returned results yourself; children "
        "never replace the primary agent's responsibility for the final answer. "
        "Require every child handoff to state changed files, used/exported public "
        "interfaces, shared configuration touched, and verification results."
    )
