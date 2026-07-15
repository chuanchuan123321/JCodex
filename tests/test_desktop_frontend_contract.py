"""Static regressions for critical desktop polling contracts."""

from pathlib import Path


APP_JS = (
    Path(__file__).resolve().parents[1]
    / "agent"
    / "ui"
    / "desktop"
    / "app.js"
)
INDEX_HTML = APP_JS.with_name("index.html")
STYLES_CSS = APP_JS.with_name("styles.css")


def test_only_final_compression_end_is_a_terminal_event() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "if (isTerminalTaskEvent(result))" in source
    helper = source.split("function isTerminalTaskEvent(result)", 1)[1]
    helper = helper.split("\n}", 1)[0]
    assert "result?.type === 'compression_end' && !result.task_continues" in helper
    assert "if (result.task_continues) {" in source
    assert "setAppStatus('busy', '正在继续任务');" in source
    assert "await drainLateTaskResults(msgId, generation)" in source
    assert "else if (!activeCompressionActivities.size)" in source


def test_historical_compression_does_not_set_a_running_status() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "announceStatus = true" in source
    assert "if (announceStatus)" in source
    assert "!isRestoringConversation,\n            !isRestoringConversation" in source
    assert "restoreStatusAfterCompression();" in source
    assert "if (!isProcessing && isInitialized) setAppStatus('ready', '就绪');" in source


def test_sidebar_rows_are_updated_in_place_during_live_polling() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    render_helper = source.split("function renderConversationList()", 1)[1]
    render_helper = render_helper.split(
        "\nfunction updateActiveTaskTitle", 1
    )[0]
    polling_helper = source.split("function startPolling(", 1)[1]
    polling_helper = polling_helper.split(
        "\nfunction isTerminalTaskEvent", 1
    )[0]

    assert "createTaskHistoryItem" in render_helper
    assert "existingRows = new Map" in render_helper
    assert "list.insertBefore(row" in render_helper
    assert "list.innerHTML = conversations.map" not in render_helper
    assert "renderConversationList();" not in polling_helper


def test_plan_progress_uses_single_composer_component_and_latest_snapshot() -> None:
    app_source = APP_JS.read_text(encoding="utf-8")
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert html_source.count('id="planProgress"') == 1
    assert html_source.index('id="planProgress"') < html_source.index(
        'class="input-container"'
    )
    assert "const activePlanProgress = new Map();" in app_source
    assert "result?.type === 'plan_update'" in app_source
    assert "if (result?.error)" in app_source
    assert "{...previous, error:" in app_source
    assert "plan: [{step: '计划更新失败', status: 'pending'}]" in app_source
    assert "raw.terminal_state || raw.terminalState" in app_source
    assert "raw.terminal_message || raw.terminalMessage" in app_source
    assert "function markPlanProgressTerminal" in app_source
    assert "root.classList.toggle('is-finished', isFinished);" in app_source
    assert "root.classList.toggle('is-complete', isComplete && !isFailure);" in app_source
    assert "terminalState === 'complete'" in app_source
    assert "? finishedMessage" in app_source
    assert "function getLatestConversationPlan" in app_source
    assert "activeState?.running ? null" in app_source
    assert "const planMatchesActiveRun = !activeExecution?.running" in app_source
    assert "latestPlan?.messageId === Number(activeExecution.messageId || 0)" in app_source
    assert "const pendingIndex = planState.plan.findIndex" in app_source
    assert "pendingIndex >= 0 ? pendingIndex : planState.plan.length - 1" in app_source
    assert "event?.type !== 'plan_update'" in app_source
    assert "else if (event.type === 'plan_update')" in app_source
    assert "bottom: calc(100% + 8px);" in css_source
    assert "max-height: min(60vh, 420px);" in css_source
    assert "overflow-y: auto;" in css_source
    assert ":not(.is-error):not(.is-finished) .plan-progress-state::after" in css_source
    assert ".plan-progress:not(.is-finished) .plan-progress-item.is-in_progress" in css_source
    assert "aria-expanded" in html_source
    assert "aria-controls=\"planProgressPanel\"" in html_source


def test_plan_terminal_state_tracks_real_execution_outcomes() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    stop_handler = source.split(
        "stopButton.addEventListener('click', async () => {", 1
    )[1].split("clearChat.addEventListener", 1)[0]

    assert stop_handler.index("if (!result?.success)") < stop_handler.index(
        "conversationId, messageId, 'stopped', '任务已停止'"
    )
    stop_error_path = stop_handler.split("} catch (error) {", 1)[1]
    assert "'stopped', '任务已停止'" not in stop_error_path

    finish_helper = source.split("function finishCurrentMessage(", 1)[1]
    finish_helper = finish_helper.split("\nfunction invalidatePolling", 1)[0]
    assert "terminalState = 'complete'" in finish_helper
    assert "markPlanProgressTerminal(id, msgId, terminalState, terminalMessage);" in finish_helper

    result_handler = source.split("function handleResult(", 1)[1]
    result_handler = result_handler.split("\nfunction showApproval", 1)[0]
    assert "executionId, msgId, 'error', result.content || '执行中断'" in result_handler

    polling_helper = source.split("function startPolling(", 1)[1]
    polling_helper = polling_helper.split("\nfunction isTerminalTaskEvent", 1)[0]
    assert "finishCurrentMessage(executionId, messageId);" in polling_helper
    assert "'error',\n                    '桌面端与执行服务连接中断'" in polling_helper
