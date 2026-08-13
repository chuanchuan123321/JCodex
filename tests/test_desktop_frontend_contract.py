"""Static regressions for critical desktop polling contracts."""

from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parents[1] / "agent" / "ui" / "desktop"
APP_JS = DESKTOP_DIR / "app.js"
INDEX_HTML = APP_JS.with_name("index.html")
STYLES_CSS = APP_JS.with_name("styles.css")
AGENT_PROMPT = APP_JS.parents[3] / "Agent.md"


def frontend_source() -> str:
    """Concatenate app.js + js/ modules in index.html load order.

    The desktop UI is split into multiple classic scripts (see index.html),
    so contract assertions run against the combined source to stay valid
    as modules are extracted from app.js.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    parts = [APP_JS.read_text(encoding="utf-8")]
    for match in __import__("re").finditer(r'<script src="(js/[^"]+\.js)', html):
        script_path = DESKTOP_DIR / match.group(1)
        parts.append(script_path.read_text(encoding="utf-8"))
    return "\n".join(parts)



def test_context_window_slider_and_token_indicator_contract() -> None:
    source = frontend_source()
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert (
        "const CONTEXT_WINDOW_OPTIONS = [128000, 256000, 512000, 1000000];"
        in source
    )
    assert "const CONTEXT_WINDOW_LABELS = ['128K', '256K', '512K', '1M'];" in source

    index_helper = source.split("function contextWindowIndexFor(value)", 1)[1].split(
        "\nfunction updateContextWindowLabel", 1
    )[0]
    assert "Number(value || 256000)" not in index_helper

    label_helper = source.split("function updateContextWindowLabel()", 1)[1].split(
        "\nfunction setVoiceModeStatus", 1
    )[0]
    assert "Number(slider.value) || 1" not in label_helper
    assert "CONTEXT_WINDOW_LABELS[index]" in label_helper

    token_helper = source.split("async function updateTokenIndicator()", 1)[1].split(
        "\nfunction tokenTooltipMarkup", 1
    )[0]
    assert "const maxTokens = Math.max(Number(result.compress_at || 0), 1);" in token_helper
    assert "const percentage = Math.min((tokens / maxTokens) * 100, 100);" in token_helper
    assert "k/' + maxK + 'k'" in token_helper

    slider_labels_rule = css_source.split(".settings-slider-labels {", 1)[1].split(
        "}", 1
    )[0]
    assert "margin-right: calc(52px + 14px);" in slider_labels_rule

    assert "previewContextWindow" in source
    assert "eel.preview_context_window(option)" in source
    assert "slider.addEventListener('input', () => {" in source
    assert "updateContextWindowLabel();" in source


def test_api_config_dropdown_and_model_quick_switch_contract() -> None:
    source = frontend_source()
    css_source = STYLES_CSS.read_text(encoding="utf-8")
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="configSelectMenu"' in html_source
    assert 'id="configSelectTrigger"' in html_source
    assert 'id="configSelectLabel"' in html_source
    assert 'class="api-config-dropdown"' in html_source
    assert 'id="modelQuickSwitch"' in html_source
    assert 'class="model-badge-anchor"' in html_source

    assert "function toggleApiConfigMenu()" in source
    assert "function openApiConfigMenu()" in source
    assert "function setApiConfigSelection(configName)" in source
    assert "function getSelectedApiConfig()" in source
    assert "async function toggleModelQuickSwitch()" in source
    assert "function positionModelQuickSwitch()" in source
    assert "document.body.appendChild(menu)" in source
    assert "window.addEventListener('resize', positionModelQuickSwitch)" in source
    assert "eel.set_active_config(configName)" in source
    assert "badge.setAttribute('aria-expanded', 'true');" in source
    assert "badge.setAttribute('aria-expanded', 'false');" in source
    assert "item.title = `${configName} · ${model || '未知模型'}`;" in source
    assert "model-quick-switch-model" not in source
    assert "aria-haspopup=\"menu\" aria-expanded=\"false\"" in html_source
    assert "modelBadge.addEventListener('click', toggleModelQuickSwitch);" in source
    assert "modelBadge.addEventListener('click', openSettings);" not in source
    assert "document.getElementById('configSelect').value" not in source

    assert ".api-config-menu {" in css_source
    assert ".api-config-trigger {" in css_source
    assert ".model-quick-switch {" in css_source
    assert "bottom: calc(100% + 8px);" in css_source
    assert "background: var(--codex-surface-solid);" in css_source
    assert ".model-quick-switch-item {" in css_source
    assert ".model-badge[aria-expanded=\"true\"] svg" in css_source
    assert "transform: rotate(180deg);" in css_source
    assert "flex: 1 1 48%;\n    justify-content: flex-end;\n    overflow: visible;" in css_source


def test_chat_markdown_renders_address_only_images_and_videos() -> None:
    source = frontend_source()
    css_source = STYLES_CSS.read_text(encoding="utf-8")
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    prompt = AGENT_PROMPT.read_text(encoding="utf-8")

    inline_renderer = source.split("function renderInlineMarkdown(content)", 1)[1]
    inline_renderer = inline_renderer.split("\nfunction renderSafeLink", 1)[0]
    assert "renderMarkdownMedia(label, bracketedUrl || plainUrl)" in inline_renderer
    assert "function normalizeMarkdownMediaSource(" in inline_renderer
    assert "function renderMarkdownMedia(" in inline_renderer
    assert "new URLSearchParams" in inline_renderer
    assert "/__jcodex_media?" in inline_renderer
    assert "(?:data|blob|javascript):" in inline_renderer
    assert '<video src="${escapeHtml(mediaUrl)}" controls' in inline_renderer
    assert '<img src="${escapeHtml(mediaUrl)}"' in inline_renderer
    assert 'loading="lazy"' in inline_renderer
    assert "function redactEmbeddedMediaData(" in source
    assert "function openImageLightbox(" in source
    assert "function closeImageLightbox(" in source
    assert "function handleImagePreviewClick(" in source
    assert "function handleImagePreviewKeydown(" in source
    assert '.message-attachment[data-image-attachment="true"]' in source
    assert '.composer-attachment[data-image-attachment="true"]' in source

    assert ".markdown-media" in css_source
    assert ".markdown-video video" in css_source
    assert "aspect-ratio: 16 / 9;" in css_source
    assert "object-fit: contain;" in css_source
    markdown_image_rule = css_source.split(".markdown-image {", 1)[1].split("}", 1)[0]
    assert "max-width: min(100%, 640px);" in markdown_image_rule
    assert ".image-lightbox-stage img" in css_source
    assert "max-height: calc(100vh - 120px);" in css_source
    for element_id in (
        "imageLightbox",
        "imageLightboxClose",
        "imageLightboxImage",
        "imageLightboxCaption",
    ):
        assert f'id="{element_id}"' in html_source

    assert "## Media In Chat" in prompt
    assert "Render images proactively" in prompt
    assert "![说明](https://example.com/image.png)" in prompt
    assert "![video:说明](https://example.com/demo.mp4)" in prompt
    assert "Never paste Base64" in prompt
    assert "reference its absolute path instead" in prompt


def test_only_final_compression_end_is_a_terminal_event() -> None:
    source = frontend_source()

    assert "if (isTerminalTaskEvent(result))" in source
    helper = source.split("function isTerminalTaskEvent(result)", 1)[1]
    helper = helper.split("\n}", 1)[0]
    assert "result?.type === 'compression_end' && !result.task_continues" in helper
    assert "if (result.task_continues) {" in source
    assert "setAppStatus('busy', '正在继续任务');" in source
    assert "await drainLateTaskResults(msgId, generation)" in source
    assert "else if (!activeCompressionActivities.size)" in source


def test_historical_compression_does_not_set_a_running_status() -> None:
    source = frontend_source()

    assert "announceStatus = true" in source
    assert "if (announceStatus)" in source
    assert "startCompressionActivity(result, msgId, !isRestoringConversation, !isRestoringConversation);" in source
    assert "restoreStatusAfterCompression();" in source
    assert "if (!isProcessing && isInitialized) setAppStatus('ready', '就绪');" in source


def test_streaming_scroll_follows_only_while_user_is_at_bottom() -> None:
    source = frontend_source()

    assert "let chatAutoFollow = true;" in source
    assert "function updateChatAutoFollow(" in source
    assert "const CHAT_BOTTOM_THRESHOLD = 240;" in source
    assert "const CHAT_BOTTOM_VIEWPORT_RATIO = 0.25;" in source
    assert "Number(chatMessages?.clientHeight || 0) * CHAT_BOTTOM_VIEWPORT_RATIO" in source
    assert "getChatDistanceFromBottom(chatMessages) <= threshold" in source
    assert "if (event.deltaY < 0) setChatAutoFollow(false);" in source
    assert "followChatOutput();" in source

    render_helper = source.split("function renderStreamingState(state)", 1)[1]
    render_helper = render_helper.split("\nfunction splitStreamingContent", 1)[0]
    assert "followChatOutput();" in render_helper
    assert "scrollHeight - chatMessages.scrollTop" not in render_helper

    scheduler = source.split("function scheduleStreamingRender(state)", 1)[1]
    scheduler = scheduler.split("\nfunction cancelStreamingRender", 1)[0]
    assert "STREAM_RENDER_INTERVAL_MS" in scheduler
    assert "STREAM_RENDER_MAX_INTERVAL_MS" in scheduler
    assert "state.renderTimer" in scheduler


def test_voice_mode_uses_hold_to_talk_and_existing_message_pipeline() -> None:
    source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    for element_id in (
        "voiceModeButton",
        "voiceModeHint",
        "voiceModeOverlay",
        "voiceHoldButton",
        "voiceModeStatus",
        "voiceTranscript",
    ):
        assert f'id="{element_id}"' in html_source
    assert 'id="voiceModeClose"' not in html_source
    assert "const voiceModeClose" not in source
    assert "voiceModeClose?.addEventListener" not in source
    assert "getSpeechRecognitionConstructor" in source
    assert "recognition.lang = VOICE_RECOGNITION_LANGUAGE" in source
    assert "function createVoiceRecognition(sessionToken)" in source
    assert "recognition !== voiceRecognition || sessionToken !== voiceSessionToken" in source
    assert "event.code !== 'Space'" in source
    assert "startVoiceListening();" in source
    assert "stopVoiceListening();" in source
    assert "messageInput.dispatchEvent(new Event('input', { bubbles: true }))" in source  # prettier spacing
    assert "sendMessage();" in source
    assert "speechSynthesis.speak(utterance)" in source
    assert "window.speechSynthesis.getVoices()" in source
    assert "addEventListener('voiceschanged', refreshPreferredSpeechVoice)" in source
    assert "function prepareVoiceSpeechText(content)" not in source
    assert "utterance.voice = preferredVoice" in source
    assert "utterance.rate = 0.94;" in source
    assert "utterance.pitch = 1.02;" in source
    assert "voiceSpeechQueue" in source
    assert "playNextVoiceResponse" in source
    assert "function pauseVoiceResponseForConversation()" in source
    assert "function pauseActiveOutputForVoiceInput()" in source
    assert "function showVoiceModeHint()" in source
    assert "按住空格打断并说话" in source
    assert "按住空格说话" in source
    assert "voiceLastSpokenMessageId" not in source
    assert ".voice-mode-overlay" in css_source
    assert ".voice-mode-button-hint" in css_source
    assert 'id="voiceStrandsCanvas"' in html_source
    assert "drawVoiceStrands" in source
    assert "VOICE_BAR_COUNT" in source
    assert "getContext('2d'" in source
    assert "function createVoiceStrandsRenderer()" in source
    assert "function _voiceRoundRectPath(ctx" in source
    assert "function _voiceBarPalette()" in source
    assert "startVoiceAudioMeter" in source
    assert "getSmoothedVoiceAmplitude" in source
    assert "voiceStrandsPhase * 2.4" in source
    assert "rms - 0.003" in source
    assert "activeLevel * 14" in source
    assert "Math.pow(normalizedSpeech, 0.72) * 0.58" in source
    assert "target > voiceAmplitudeSmoothed ? 5.2 : 2.6" in source
    assert "voiceAnalyser.fftSize = 1024;" in source
    assert "let voiceTimeDomainBuffer = null;" in source
    assert "const data = voiceTimeDomainBuffer;" in source
    assert "autoGainControl: false" in source
    assert "noiseSuppression: true" in source
    assert "echoCancellation: true" in source
    assert "const maxDelta = (target > voiceAmplitudeSmoothed ? 1.15 : 0.62) * elapsed;" in source
    assert "const animationTime = (timestamp - renderer.timeOrigin) * 0.001;" in source
    assert "voiceStrandsPhase + 0.012 + energy * 0.018" in source
    assert "WEBGL_lose_context" not in source
    assert "const gradient = ctx.createLinearGradient(0, baseY - maxHeight, 0, baseY);" in source
    assert "const eased = barHeights[index] + (target - barHeights[index]) * 0.16;" in source
    assert "ctx.arcTo(x + width, y + height, x, y + height, r);" in source
    assert "listening" in source
    assert "palette.top" in source
    assert ".voice-strands-canvas" in css_source

    start_helper = source.split("function startVoiceListening()", 1)[1]
    start_helper = start_helper.split("\nfunction stopVoiceListening", 1)[0]
    assert start_helper.index("voiceListening = true;") < start_helper.index(
        "voiceRecognition = createVoiceRecognition(sessionToken);"
    )
    assert "classList.add('is-listening')" in start_helper
    assert "const outputPaused = pauseActiveOutputForVoiceInput();" in start_helper
    assert "pauseVoiceResponseForConversation();" in start_helper
    assert "resetVoiceAmplitude(0.31);" in start_helper
    assert "已暂停输出，正在聆听…松开空格键发送" in start_helper
    assert "正在聆听…当前环境不支持自动识别" in start_helper
    assert "const previousRecognition = voiceRecognition;" in start_helper
    assert "previousRecognition?.abort();" in start_helper
    assert "voiceRecognition = createVoiceRecognition(sessionToken);" in start_helper
    assert "voiceRecognition ||= createVoiceRecognition();" not in start_helper

    pause_helper = source.split("function pauseActiveOutputForVoiceInput()", 1)[1]
    pause_helper = pause_helper.split("\nfunction playNextVoiceResponse", 1)[0]
    assert "getActiveExecutionState()" in pause_helper
    assert "document.getElementById('stopButton')?.click();" in pause_helper

    stop_helper = source.split("function stopVoiceListening(", 1)[1]
    stop_helper = stop_helper.split("\nfunction submitVoiceTranscript", 1)[0]
    assert "voiceRecognitionRunning || voiceRecognitionStarting" in stop_helper
    assert "voiceRecognitionFinishTimer" in stop_helper
    assert "voicePendingSendToken === voiceSessionToken" not in stop_helper
    assert "pendingToken === voiceSessionToken" in stop_helper
    assert "voiceSessionToken += 1;" not in stop_helper
    assert "resetVoiceAmplitude();" in stop_helper

    assert "sessionToken !== voiceSessionToken" in source
    assert "lostpointercapture" in source
    assert "voicePointerId !== null" in source
    assert "'input, textarea, select" not in source
    assert "document.addEventListener(\n    'keydown'," in source
    assert "document.addEventListener(\n    'keyup'," in source
    finish_helper = source.split("function finishCurrentMessage(", 1)[1]
    finish_helper = finish_helper.split("\nfunction invalidatePolling", 1)[0]
    assert "if (!voiceModeActive) document.getElementById('messageInput').focus();" in finish_helper
    streaming_helper = source.split("function finalizeStreamingResponse(", 1)[1]
    streaming_helper = streaming_helper.split("\nfunction getVisibleModelContent", 1)[0]
    assert "flushVoiceStreamingResponse(state, { final: true });" in streaming_helper  # prettier spacing
    commentary_branch = streaming_helper.rsplit("if (isCommentary) {", 1)[1]
    commentary_branch = commentary_branch.split("return;", 1)[0]
    assert "speakVoiceResponse" not in commentary_branch
    assert "if (!state || !state.voiceQueuedText) speakVoiceResponse(content, msgId);" in streaming_helper
    assert "function getVoiceStreamSentenceBoundary(text)" in source
    assert "function flushVoiceStreamingResponse(state, { final = false } = {})" in source  # prettier spacing
    assert "state.isCommentary || state.voiceDisabled" in source
    assert "getVoiceStreamSentenceBoundary(pending)" in source
    assert "enqueueVoiceSpeech(" in source
    append_helper = source.split("function appendStreamingResponse(", 1)[1]
    append_helper = append_helper.split("\nfunction scheduleStreamingRender", 1)[0]
    assert "flushVoiceStreamingResponse(state);" in append_helper
    commentary_marker = source.split("function markStreamingCommentary(", 1)[1]
    commentary_marker = commentary_marker.split("\nfunction createStreamingThinking", 1)[0]
    assert "flushVoiceStreamingResponse(state, { final: true });" in commentary_marker  # prettier spacing
    assert "state.voiceDisabled = true;" in commentary_marker
    commentary_setup = streaming_helper.split("if (isCommentary && state) {", 1)[1]
    commentary_setup = commentary_setup.split("state.isCommentary = true;", 1)[0]
    assert "flushVoiceStreamingResponse(state, { final: true });" in commentary_setup
    assert "positionVoiceStrands" in source
    assert "--voice-strands-center-x" in source
    assert "window.innerHeight - inputRect.top + 10" in source
    assert "Math.max(200, Math.min(mainRect.width - 28, 240))" in source
    assert "ResizeObserver(positionVoiceStrands)" in source
    assert "voiceLayoutObserver.observe(inputContainer);" in source
    reset_view = source.split("function resetConversationView(", 1)[1]
    reset_view = reset_view.split("\nfunction formatConversationDate", 1)[0]
    assert "if (voiceModeActive) cancelVoiceSpeech();" in reset_view

    final_voice_css = css_source.rsplit(
        "/* Voice mode final presentation: only the floating strands remain visible. */",
        1,
    )[1]
    assert ".voice-mode-backdrop" in final_voice_css
    backdrop_css = final_voice_css.split(".voice-mode-backdrop {", 1)[1].split("}", 1)[0]
    assert "display: none !important;" in backdrop_css
    assert "backdrop-filter: none !important;" in backdrop_css
    canvas_css = final_voice_css.split(".voice-strands-canvas {", 1)[1].split("}", 1)[0]
    assert "background: transparent !important;" in canvas_css
    assert "filter: none !important;" in canvas_css
    assert "border-radius: 0 !important;" in final_voice_css
    assert "background: transparent !important;" in final_voice_css
    assert "bottom: var(--voice-strands-bottom, 126px) !important;" in final_voice_css
    assert "left: var(--voice-strands-center-x, 50%) !important;" in final_voice_css
    assert "width: var(--voice-strands-width, min(240px, 80vw)) !important;" in final_voice_css
    assert "height: clamp(96px, 14vw, 120px) !important;" in final_voice_css

    send_helper = source.split("async function sendMessage()", 1)[1]
    send_helper = send_helper.split("\n// 直接发送指定消息", 1)[0]
    assert "const voiceMode = voiceModeActive;" in send_helper
    assert "voiceMode," in send_helper
    queued_helper = source.split("async function sendMessageWithText(", 1)[1]
    queued_helper = queued_helper.split("\nfunction updateQueueDisplay", 1)[0]
    assert "voiceMode = voiceModeActive" in queued_helper
    assert "Boolean(voiceMode)" in queued_helper
    assert "typeof queued.voiceMode === 'boolean' ? queued.voiceMode : false" in source


def test_sidebar_rows_are_updated_in_place_during_live_polling() -> None:
    source = frontend_source()

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


def test_jcodex_welcome_has_three_action_modules() -> None:
    source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert "JCODEX WORKSPACE" in source
    assert "JCODEX WORKSPACE" in html_source
    assert "麒麟OS-Agent" not in html_source
    assert "调研与验证" in source
    assert "调研与验证" in html_source
    assert source.count('class="quick-action" data-prompt=') >= 3
    assert html_source.count('class="quick-action" data-prompt=') >= 3
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css_source


def test_sidebar_uses_persistent_two_level_navigation() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="sidebarPrimaryNav"' in html_source
    assert 'role="tablist"' in html_source
    assert html_source.count('data-sidebar-panel="') == 5
    assert html_source.count('data-sidebar-panel-content="') == 5
    assert 'id="sidebarPanelTasks"' in html_source
    assert 'id="sidebarPanelFiles"' in html_source
    assert 'id="sidebarPanelMemory"' in html_source
    assert 'id="sidebarPanelSkills"' in html_source
    assert 'id="sidebarPanelSettings"' in html_source
    for element_id in (
        "newTaskButton",
        "taskHistoryList",
        "outputFiles",
        "tempFiles",
        "memoryFiles",
        "skillsList",
        "settingsBtn",
    ):
        assert f'id="{element_id}"' in html_source

    assert "minibot-sidebar-panel" in app_source
    assert "function getSavedSidebarPanel()" in app_source
    assert "function setSidebarPanel(panelName" in app_source
    assert "item.hidden = !isActive;" in app_source
    assert "button.setAttribute('aria-selected'" in app_source
    assert "button.tabIndex = isActive ? 0 : -1;" in app_source
    assert "updateSidebarNavOrientation" in app_source
    assert "function closeMobileSidebar()" in app_source
    assert "document.body.classList.contains('sidebar-open')" in app_source
    assert ".sidebar-workbench" in css_source
    assert ".sidebar-nav-item.is-active" in css_source
    assert ".sidebar-panel[hidden]" in css_source


def test_memory_sidebar_exposes_the_exact_injected_context_file() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-memory-file="memory_context"' in html_source  # delegation, no inline onclick
    assert "memory_context.md" in html_source
    assert "memory_context: 'memory_context.md'" in app_source


def test_sidebar_skills_tree_and_resizing_contracts() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="sidebarResizeHandle"' in html_source
    assert 'role="separator"' in html_source
    assert 'aria-valuemin="258"' in html_source
    assert "const SIDEBAR_PANEL_MIN_WIDTH = 210;" in app_source
    new_task_rule = css_source.split(".new-task-button {", 1)[1].split("\n}", 1)[0]
    assert "white-space: nowrap;" in new_task_rule
    assert "minibot-sidebar-panel-width" in app_source
    assert "function initializeSidebarResizeHandle" in app_source
    assert "setPointerCapture(pointerId)" in app_source
    assert "--sidebar-panel-width" in app_source
    assert "workspaceExpandedDirectories" in app_source
    assert "function toggleWorkspaceDirectory" in app_source
    assert ".list_workspace_files(folder, path)" in app_source  # formatter-tolerant (prettier wraps eel chains)
    assert "data-workspace-toggle" in app_source
    assert "aria-expanded" in app_source
    assert "openFile(folder, fileItem.dataset.workspaceFile)" in app_source
    assert "#sidebarPanelSkills #skillsList" in css_source
    assert "#sidebarPanelSkills #skillsFolder" in css_source
    assert "max-height: none;" in css_source
    assert ".workspace-tree-children" in css_source
    assert ".sidebar-resize-handle" in css_source
    assert "body.theme-light .sidebar.sidebar-shell" in css_source
    assert "body.theme-dark .sidebar.sidebar-shell" in css_source


def test_files_panel_keeps_roots_adjacent_with_taller_tree_viewports() -> None:
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    files_panel = css_source.split("#sidebarPanelFiles .workspace-section {", 1)[1]
    files_panel = files_panel.split("\n}", 1)[0]
    file_list = css_source.split("#sidebarPanelFiles .file-list {", 1)[1]
    file_list = file_list.split("\n}", 1)[0]

    assert "display: flex;" in files_panel
    assert "flex: 0 0 auto;" in files_panel
    assert "flex-direction: column;" in files_panel
    assert "grid-template-rows" not in files_panel
    assert "max-height: clamp(320px, 48vh, 560px);" in file_list
    assert "overflow-y: auto;" in file_list
    assert "overscroll-behavior-y: auto;" in file_list
    assert "overscroll-behavior: contain;" not in file_list


def test_docked_sidebar_and_review_widths_are_clamped_to_the_viewport() -> None:
    source = frontend_source()

    review_limit = source.split("function getReviewPanelWidthLimit", 1)[1]
    review_limit = review_limit.split("\nfunction ", 1)[0]
    layout_sync = source.split("function syncDockedLayoutWidths", 1)[1]
    layout_sync = layout_sync.split("\nfunction ", 1)[0]

    assert "window.innerWidth" in review_limit
    assert "getSidebar" in review_limit or "sidebar" in review_limit.lower()
    assert "setSidebarPanelWidth" in layout_sync
    assert "setChangeReviewPanelWidth" in layout_sync
    assert "window.addEventListener('resize', syncDockedLayoutWidths)" in source


def test_panel_resize_cleanup_handles_interrupted_pointer_gestures() -> None:
    source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    cleanup = source.split("function installPointerResizeCleanup", 1)[1]
    cleanup = cleanup.split("\nfunction ", 1)[0]
    sidebar_resize = source.split("function initializeSidebarResizeHandle", 1)[1]
    sidebar_resize = sidebar_resize.split("\nfunction ", 1)[0]
    review_resize = source.split("function initializeChangeReviewResizeHandle", 1)[1]
    review_resize = review_resize.split("\nfunction ", 1)[0]
    agent_resize = source.split("function initializeAgentDetailResizeHandle", 1)[1]
    agent_resize = agent_resize.split("\nfunction ", 1)[0]

    assert "pointercancel" in cleanup
    assert "lostpointercapture" in cleanup
    assert "blur" in cleanup
    assert 'id="changeReviewResizeHandle"' in html_source
    assert 'class="change-review-resize-handle"' in html_source
    assert "installPointerResizeCleanup" in sidebar_resize
    assert 'id="agentDetailResizeHandle"' in html_source
    assert 'class="agent-detail-resize-handle"' in html_source
    assert "AGENT_DETAIL_WIDTH_STORAGE_KEY" in source
    assert "window.innerWidth - event.clientX" in agent_resize
    assert "installPointerResizeCleanup" in agent_resize
    assert "installPointerResizeCleanup" in review_resize
    assert "is-resizing-sidebar" in sidebar_resize
    assert "is-resizing-review" in review_resize


def test_frontend_stops_background_eel_calls_after_disconnect() -> None:
    source = frontend_source()

    assert "let eelConnectionLost = false;" in source
    assert "function markEelConnectionLost()" in source
    assert "function handleEelConnectionError(error)" in source
    assert "function canCallEel()" in source
    assert "Eel connection is unavailable" in source
    assert "eel._websocket?.addEventListener('close'" in source
    assert "!document.hidden && canCallEel()) refreshAllWorkspace();" in source
    assert "if (handleEelConnectionError(e)) return;" in source


def test_skill_folder_import_uses_the_browser_picker_not_tk() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="skillFolderInput"' in html_source
    assert "webkitdirectory" in html_source
    assert 'id="addSkillButton"' in html_source
    assert 'title="导入技能文件夹"' in html_source
    assert html_source.index('id="addSkillButton"') < html_source.index('id="skillsFolder"')
    assert "function importSkillFolder(files)" in app_source
    assert "file.webkitRelativePath || file.name" in app_source
    assert "eel.import_skill_folder(payload)" in app_source
    assert "eel.select_skill_folder" not in app_source


def test_skill_store_has_sidebar_entry_search_and_install_states() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    for element_id in (
        "skillStoreEntry",
        "skillStoreCount",
        "skillStoreModal",
        "skillStoreSearch",
        "skillStoreRefresh",
        "skillStoreMeta",
        "skillStoreList",
    ):
        assert f'id="{element_id}"' in html_source
    assert "技能商店" in html_source
    assert "打开商店目录" in html_source
    assert "function openSkillStore()" in app_source
    assert "function refreshSkillStore()" in app_source
    assert "function renderSkillStore(query = '')" in app_source
    assert "function installStoreSkill(skillName)" in app_source
    assert "eel.list_skill_store()" in app_source
    assert "eel.install_store_skill(skillName)" in app_source
    assert "eel.open_skill_store_folder()" in app_source
    assert "skill.installed" in app_source
    assert "skill.builtin ? '内置' : '已安装'" in app_source
    assert ".skill-store-entry" in css_source
    assert ".skill-store-list" in css_source
    assert ".skill-store-install" in css_source
    store_entry_rule = css_source.rsplit(".skill-store-entry {", 1)[1].split("}", 1)[0]
    assert "border: 0;" in store_entry_rule
    assert "background: transparent;" in store_entry_rule


def test_project_folder_picker_disables_repeated_requests_and_ignores_cancel() -> None:
    source = frontend_source()
    handler = source.split(
        "document.getElementById('projectBrowseButton')?.addEventListener", 1
    )[1].split("document.getElementById('projectDialog')", 1)[0]

    assert "button.disabled = true;" in handler
    assert "button.textContent = '正在选择…';" in handler
    assert "!result?.cancelled && result?.error" in handler
    assert "finally" in handler
    assert "button.disabled = false;" in handler


def test_project_list_uses_only_the_context_menu_for_new_project_tasks() -> None:
    source = frontend_source()
    render_helper = source.split("function renderProjectList()", 1)[1]
    render_helper = render_helper.split("\nasync function refreshProjects", 1)[0]

    assert "在项目中新建任务" not in render_helper
    assert "project-add-task" not in render_helper
    assert 'data-action="new-task"' in source


def test_composer_drop_supports_reference_folders() -> None:
    source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    assert "function getDroppedDirectoryEntries" in source
    assert "function addDroppedComposerItems" in source
    assert "kind: 'directory_reference'" in source
    assert "function getPathBaseName" in source
    assert "directoryNames.has(getPathBaseName(path))" in source
    assert "eel.get_dragged_folder_paths(" in source
    assert "await addDroppedComposerItems(event.dataTransfer);" in source
    assert "文件、图片或参考文件夹" in html_source


def test_composer_menu_can_select_a_reference_folder() -> None:
    source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-composer-action="upload-folder"' in html_source
    assert ">上传文件夹<" in html_source
    assert "async function selectComposerFolder" in source
    assert "eel.select_reference_folder()" in source
    assert "addComposerDirectoryReferences([result.path])" in source


def test_sidebar_scrollbars_auto_hide_until_interaction() -> None:
    source = frontend_source()
    styles = STYLES_CSS.read_text(encoding="utf-8")

    assert "function initializeSidebarAutoHideScrollbars" in source
    assert "is-scrollbar-active" in source
    assert "scrollbar-color: transparent transparent" in styles
    assert ".sidebar-panel::-webkit-scrollbar-thumb" in styles


def test_deleting_an_inactive_task_does_not_redraw_the_active_task() -> None:
    source = frontend_source()
    delete_handler = source.split(
        "menu.querySelector('[data-action=\"delete\"]').onclick = async () => {", 1
    )[1].split("setTimeout(() => document.addEventListener", 1)[0]

    assert "const deletedWasActive = String(conversationId) === String(activeConversationId || '');" in delete_handler
    assert "deletedWasActive ? result.active_id : activeConversationId" in delete_handler
    assert "hideSplitTaskPane();" in delete_handler
    assert "result.deleted_conversation_ids" in delete_handler
    assert "restoreSplitTaskForConversation(nextActiveId)" in delete_handler
    hide_split = source.split("function hideSplitTaskPane()", 1)[1].split("\nfunction ", 1)[0]
    assert "frame.src = 'about:blank'" in hide_split
    assert "if (!deletedWasActive) return;" in delete_handler
    assert delete_handler.index("if (!deletedWasActive) return;") < delete_handler.index(
        ".load_conversation(nextActiveId)"
    )


def test_deleting_the_active_task_finishes_at_the_latest_message() -> None:
    source = frontend_source()
    delete_handler = source.split(
        "menu.querySelector('[data-action=\"delete\"]').onclick = async () => {", 1
    )[1].split("setTimeout(() => document.addEventListener", 1)[0]

    final_pin = "pinChatToBottom(document.getElementById('chatMessages'), { force: true });"
    assert "restoreSplitTaskForConversation(nextActiveId)" in delete_handler
    assert delete_handler.index(final_pin) > delete_handler.index(
        "restoreSplitTaskForConversation(nextActiveId)"
    )


def test_split_window_initializes_its_pinned_task_id() -> None:
    source = frontend_source()
    initializer = source.split("async function initializeOSAgent()", 1)[1]
    initializer = initializer.split("\nfunction splitTaskUrl", 1)[0]

    assert "eel.initialize(" in initializer
    assert "splitPaneMode ? splitTaskIdFromUrl : ''" in initializer


def test_plan_progress_uses_single_composer_component_and_latest_snapshot() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert html_source.count('id="planProgress"') == 1
    assert html_source.index('id="planProgress"') < html_source.index(
        'class="input-container"'
    )
    assert "const activePlanProgress = new Map();" in app_source
    assert "result?.type === 'plan_update'" in app_source
    assert "if (result?.error)" in app_source
    assert "{ ...previous, error:" in app_source  # prettier spacing
    assert "plan: [{ step: '计划更新失败', status: 'pending' }]" in app_source  # prettier spacing
    assert "raw.terminal_state || raw.terminalState" in app_source
    assert "raw.terminal_message || raw.terminalMessage" in app_source
    assert "function markPlanProgressTerminal" in app_source
    assert "root.classList.toggle('is-finished', isFinished);" in app_source
    assert "root.classList.toggle('is-complete', isComplete && !isFailure);" in app_source
    assert "terminalState === 'complete'" in app_source
    assert "? finishedMessage" in app_source
    assert "function getLatestConversationPlan" in app_source
    assert "activeState?.running\n      ? null" in app_source  # prettier multiline ternary
    assert "const planMatchesActiveRun =\n      !activeExecution?.running" in app_source  # prettier wrap
    assert "latestPlan?.messageId === Number(activeExecution.messageId || 0)" in app_source
    assert "const pendingIndex = planState.plan.findIndex" in app_source
    assert "'completed', 'cancelled'" in app_source
    assert ".plan-progress-item.is-cancelled" in css_source
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


def test_composer_plan_mode_is_persistent_and_captured_at_submit() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="planModeToggle"' in html_source
    assert 'id="planModePill"' in html_source
    assert 'id="composerAddMenu"' in html_source
    assert 'aria-haspopup="menu"' in html_source
    assert 'data-composer-action="upload-attachment"' in html_source
    assert 'data-composer-action="enable-plan-mode"' in html_source
    assert 'class="plan-mode-pill-label">计划</span>' in html_source
    assert "composer-tool-divider" not in html_source
    assert "minibot-plan-mode-enabled" in app_source
    assert "function setPlanModeEnabled(enabled)" in app_source
    assert "function openComposerAddMenu(focusFirst = false)" in app_source
    assert "function closeComposerAddMenu(restoreFocus = false)" in app_source
    assert "attachmentInput?.click();" in app_source
    assert "setPlanModeEnabled(true);" in app_source
    assert "setPlanModeEnabled(false);" in app_source
    assert "const planMode = planModeEnabled;" in app_source
    assert "planMode," in app_source
    assert "Boolean(planMode)" in app_source
    assert "typeof queued.planMode === 'boolean' ? queued.planMode : planModeEnabled" in app_source
    assert ".composer-add-menu" in css_source
    assert ".plan-mode-pill" in css_source
    assert ".plan-mode-close" in css_source
    assert ".composer-tool-divider" not in css_source


def test_dark_theme_does_not_force_the_plan_mode_pill_visible() -> None:
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    plan_styles = css_source.split(".plan-mode-pill {", 1)[1]
    plan_styles = plan_styles.split("@keyframes composerAddMenuIn", 1)[0]
    assert "body.theme-dark .plan-mode-pill" not in plan_styles
    assert ".plan-mode-pill[hidden] {\n    display: none;\n}" in plan_styles
    assert "transition: padding-left 140ms ease;" in plan_styles


def test_tool_cards_show_a_safe_call_target() -> None:
    source = frontend_source()

    assert "function getToolTarget(toolName, params = {}, explicitTarget = '')" in source
    assert "['filePath', 'file_path', 'path', 'filename']" in source
    assert "values.description || values.workdir" in source
    assert "getToolTarget(result.tool, result.params || {}, result.target)" in source
    assert "${failed ? '工具调用失败' : '工具调用完成'}" in source
    assert "values.content" not in source.split("function getToolTarget", 1)[1].split(
        "\nfunction getToolProgressCopy", 1
    )[0]


def test_switching_conversations_finishes_at_the_latest_message() -> None:
    source = frontend_source()

    switch_helper = source.split("async function switchConversation(conversationId)", 1)[1]
    switch_helper = switch_helper.split("\nfunction openConversationMenu", 1)[0]
    final_pin = "pinChatToBottom(document.getElementById('chatMessages'), { force: true });"

    assert final_pin in switch_helper
    assert switch_helper.index(final_pin) > switch_helper.index(
        "syncActiveConversationProcessingUI({ showPlaceholder: true });"
    )


def test_task_end_modified_files_summary_is_dedicated_and_restorable() -> None:
    app_source = frontend_source()
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert "function addModifiedFilesSummary(result, animate = true)" in app_source
    assert "function normalizeModifiedFiles(result)" in app_source
    assert "event.type === 'modified_files'" in app_source
    assert "result.type === 'modified_files'" in app_source
    assert "addModifiedFilesSummary(event, false);" in app_source
    assert "addModifiedFilesSummary(result);" in app_source
    assert "function pinChatToBottom(" in app_source
    assert "chatMessages.style.scrollBehavior = 'auto';" in app_source
    assert "requestAnimationFrame(() => align(remainingFrames - 1));" in app_source
    assert "if (!isRestoringConversation) pinChatToBottom(chatMessages);" in app_source
    assert ".modified-files-summary" in css_source
    modified_files_css = css_source.split(".modified-files-summary {", 1)[1].split("}", 1)[0]
    assert "flex: 0 0 auto;" in modified_files_css
    assert "border-radius: 11px;" in modified_files_css
    modified_files_header_css = css_source.split(".modified-files-header {", 1)[1].split("}", 1)[0]
    assert "min-height: 48px;" in modified_files_header_css
    assert "padding: 7px 10px;" in modified_files_header_css
    modified_files_row_css = css_source.split(".modified-files-row {", 1)[1].split("}", 1)[0]
    assert "min-height: 34px;" in modified_files_row_css
    assert "新增 ${additions} 行，删除 ${deletions} 行" in app_source
    assert ".modified-files-header" in css_source
    assert ".modified-files-row" in css_source
    assert ".modified-files-added" in css_source
    assert ".modified-files-deleted" in css_source


def test_modified_files_review_opens_an_accessible_vscode_style_side_panel() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="changeReviewPanel"' in html_source
    assert 'id="changeReviewClose"' in html_source
    assert 'id="changeReviewFileList"' in html_source
    assert 'id="changeReviewDiff"' in html_source
    assert 'aria-label="关闭审核"' in html_source
    assert "function openChangeReview(result" in app_source
    assert "function closeChangeReview(" in app_source
    assert "function selectChangeReviewFile(" in app_source
    assert "openChangeReview(result" in app_source
    assert "modified-files-review" in app_source
    assert "reviewable" in app_source
    assert "hunks" in app_source
    assert "old_line" in app_source
    assert "new_line" in app_source
    assert "event.key === 'Escape'" in app_source
    assert ".change-review-panel" in css_source
    assert ".change-review-file" in css_source
    assert ".change-review-hunk" in css_source
    assert ".change-review-line-add" in css_source
    assert ".change-review-line-delete" in css_source
    assert "change-review-open" in css_source


def test_review_normalization_preserves_historical_diff_data() -> None:
    source = frontend_source()
    normalizer = source.split("function normalizeModifiedFiles(result)", 1)[1]
    normalizer = normalizer.split("\nfunction addModifiedFilesSummary", 1)[0]

    assert "reviewable" in normalizer
    assert "review_reason" in normalizer
    assert "hunks" in normalizer
    assert "structuredClone" in source or ".map((hunk)" in normalizer  # prettier wraps arrow args


def test_terminal_polling_drains_and_restores_task_end_summary() -> None:
    source = frontend_source()

    polling_helper = source.split("function startPolling(", 1)[1]
    polling_helper = polling_helper.split("\nfunction isTerminalTaskEvent", 1)[0]
    drain_helper = source.split("async function drainLateTaskResults(", 1)[1]
    drain_helper = drain_helper.split("\n// Compatibility marker", 1)[0]
    finish_helper = source.split("function finishCurrentMessage(", 1)[1]
    finish_helper = finish_helper.split("\nfunction invalidatePolling", 1)[0]

    assert "if (lateResult.hadResults && !poller.terminalEventSeen) return;" in polling_helper
    assert "batch < 8; batch += 1" in drain_helper
    assert "batch < 8 && !terminal" not in drain_helper
    assert "poller.terminalEventSeen = true;" in drain_helper
    assert ".load_conversation(id)()" in finish_helper  # prettier wraps eel chains
    assert "event?.type === 'modified_files'" in finish_helper
    assert "Number(event.message_id || 0) === messageId" in finish_helper
    assert "addModifiedFilesSummary(summary, false);" in finish_helper
    assert "renderConversation(result.conversation);" not in finish_helper


def test_terminal_polling_never_keeps_stop_button_visible_for_finalization() -> None:
    source = frontend_source()

    polling_helper = source.split("function startPolling(", 1)[1]
    polling_helper = polling_helper.split("\nfunction isTerminalTaskEvent", 1)[0]

    assert "status?.finalized === false" in polling_helper
    assert "const displayRunning = Boolean(status?.running);" in polling_helper
    assert "FINALIZATION_GRACE_MS" not in source
    assert "finalizationPendingSince" not in polling_helper
    assert polling_helper.index("if (!status?.running) {") < polling_helper.index(
        "finishCurrentMessage(executionId, messageId);"
    )


def test_stale_sidebar_snapshot_cannot_revive_a_terminal_task() -> None:
    source = frontend_source()

    state_helper = source.split("function updateConversationExecutionState", 1)[1]
    state_helper = state_helper.split("\nfunction isConversationRunning", 1)[0]
    sidebar_helper = source.split("function syncExecutionStatesFromConversations", 1)[1]
    sidebar_helper = sidebar_helper.split("\nfunction markConversationReadLocally", 1)[0]

    assert "terminalMessageId" in state_helper
    assert "incomingMessageId <= Number(state.terminalMessageId || 0)" in state_helper
    assert "backendMessageId <= Number(state.terminalMessageId || 0)" in sidebar_helper


def test_plan_terminal_state_tracks_real_execution_outcomes() -> None:
    source = frontend_source()
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
    assert "finishCurrentMessage(executionId, messageId, 'error', '桌面端与执行服务连接中断');" in polling_helper


def test_stop_renders_the_synchronously_returned_modified_files_summary() -> None:
    source = frontend_source()
    stop_handler = source.split(
        "stopButton.addEventListener('click', async () => {", 1
    )[1].split("clearChat.addEventListener", 1)[0]

    assert "const modifiedFiles = result?.modified_files;" in stop_handler
    assert "Number(modifiedFiles.message_id || messageId) === messageId" in stop_handler
    assert "addModifiedFilesSummary({" in stop_handler
    assert stop_handler.index("addModifiedFilesSummary({") < stop_handler.index(
        "conversationId, messageId, 'stopped', '任务已停止'"
    )


def test_multi_agent_mode_renders_bounded_isolated_team_snapshots() -> None:
    app_source = frontend_source()
    html_source = INDEX_HTML.read_text(encoding="utf-8")
    css_source = STYLES_CSS.read_text(encoding="utf-8")

    for element_id in (
        "multiAgentModePill",
        "multiAgentModeToggle",
        "agentDetailPanel",
        "agentDetailClose",
        "agentDetailName",
        "agentDetailTask",
        "agentDetailContextScope",
        "agentCollaborationList",
        "agentActivityList",
        "agentResultSection",
        "sidebarCollapseButton",
    ):
        assert f'id="{element_id}"' in html_source
    assert 'data-composer-action="enable-multi-agent-mode"' in html_source
    assert "不继承主对话、兄弟智能体上下文或任何私有思考" in html_source

    assert "let multiAgentModeEnabled = localStorage.getItem(" in app_source
    assert "function setMultiAgentModeEnabled(enabled)" in app_source
    assert "function normalizeAgentTeamSnapshot(" in app_source
    assert "function renderAgentTeamCard(" in app_source
    assert "function createAgentChip(" in app_source
    assert "function updateAgentChip(" in app_source
    assert "function updateAgentActivityList(" in app_source
    assert "function renderAgentDetail(" in app_source
    assert "function renderAgentCollaboration(" in app_source
    assert "function openAgentDetail(" in app_source
    assert "function closeAgentDetail(" in app_source
    assert "AGENT_TEAM_MAX_MEMBERS = 12" in app_source
    assert "AGENT_ACTIVITY_MAX_ITEMS = 80" in app_source
    assert "normalizeAgentCollaboration" in app_source
    assert "agent-collaboration-section" in css_source
    assert "SIDEBAR_COLLAPSED_STORAGE_KEY" in app_source
    assert "function setSidebarCollapsed(" in app_source
    assert "AGENT_DETAIL_MIN_WIDTH = 300" in app_source
    assert 'aria-valuemin="300"' in html_source
    assert "sidebar.sidebar-shell.is-collapsed" in css_source
    assert "body.theme-light .sidebar.sidebar-shell.is-collapsed" in css_source
    assert "body.theme-dark .sidebar.sidebar-shell.is-collapsed" in css_source
    assert "var(--sidebar-rail-width)" in css_source
    assert ".agent-detail-panel .markdown-table-wrap" in css_source
    assert "width: max-content;" in css_source
    assert "min-width: 72px;" in css_source
    assert "overscroll-behavior-x: contain;" in css_source
    assert ".agent-detail-panel .agent-activity-list .message-wrapper" in css_source
    assert ".agent-collaboration-list" in css_source
    assert "max-height: clamp(176px, 29vh, 320px);" in css_source
    assert "overflow-y: auto;" in css_source
    assert "scrollbar-gutter: stable;" in css_source
    assert "协作黑板" in html_source
    assert "splitTaskButton" in html_source
    assert 'id="splitTaskCollapse"' in html_source
    assert 'title="删除子任务"' in html_source
    assert "splitWorkspace" in html_source
    assert "splitResizeHandle" in html_source
    assert "create_split_conversation" in app_source
    assert "get_split_conversation_state" in app_source
    assert "set_split_conversation_state" in app_source
    assert "delete_split_conversation" in app_source
    assert "splitTaskCollapse?.addEventListener('click', closeSplitTask)" in app_source
    assert "splitTaskClose?.addEventListener('click', deleteSplitTask)" in app_source
    assert "function deleteSplitTask()" in app_source
    assert "独立子任务，并复制当前短期记忆快照" in app_source
    assert "result.created" in app_source
    assert "已恢复原子任务，继续使用其独立记忆" in app_source
    assert "restoreSplitTaskForConversation" in app_source
    assert "initializeSplitResizeHandle" in app_source
    assert ".split-resize-handle" in css_source
    assert "--split-pane-width" in css_source
    assert "body.theme-light .main-content > .input-area" in css_source
    assert "body.split-pane-mode .access-toggle span" in css_source
    assert "body.split-pane-mode .model-badge svg" in css_source
    assert "body.split-pane-mode #sidebarToggle" in css_source
    assert "body.split-pane-mode #tokenIndicator" in css_source
    split_hidden_rules = css_source.split("body.split-pane-mode .sidebar,", 1)[1].split("{", 1)[0]
    assert ".agent-detail-panel" not in split_hidden_rules
    assert "containerRect.right - mainRect.left" in app_source
    assert "window.getComputedStyle(mainContent).minWidth" in app_source
    assert "Narrow-pane safety" in css_source
    assert ".input-tools-left .access-toggle" in css_source
    assert "flex: 0 1 auto;" in css_source
    assert ".input-tools-right .model-badge" in css_source
    model_badge_rule = css_source.rsplit(".input-tools-right .model-badge {", 1)[1]
    model_badge_rule = model_badge_rule.split("}", 1)[0]
    assert "flex: 0 1 auto;" in model_badge_rule
    assert "width: auto;" in model_badge_rule
    assert "flex: 1 1 132px;" not in model_badge_rule
    assert "#embeddingProviderText" in css_source
    assert "overflow: visible;" in css_source
    token_indicator_rule = css_source.rsplit(
        ".header-right .token-indicator {", 1
    )[1].split("}", 1)[0]
    token_text_rule = css_source.rsplit(
        ".header-right .token-text {", 1
    )[1].split("}", 1)[0]
    assert "flex: 0 0 auto;" in token_indicator_rule
    assert "min-width: max-content;" in token_indicator_rule
    assert "max-width: none;" in token_indicator_rule
    assert "overflow: visible;" in token_text_rule
    assert "text-overflow: clip;" in token_text_rule
    assert "text-overflow: ellipsis;" not in token_text_rule
    narrow_header_rule = css_source.rsplit(".chat-header {", 1)[1].split("}", 1)[0]
    narrow_header_right_rule = css_source.rsplit(".header-right {", 1)[1].split(
        "}", 1
    )[0]
    assert "overflow: visible;" in narrow_header_rule
    assert "overflow: visible;" in narrow_header_right_rule
    token_tooltip_helper = app_source.split("function tokenTooltipMarkup(result)", 1)[1].split(
        "\nfunction formatTokenText", 1
    )[0]
    assert "系统 ${formatCompressionTokenCount(systemTokens)}" in token_tooltip_helper
    assert "压缩阈值" in token_tooltip_helper
    assert "<br>" not in token_tooltip_helper
    assert "function syncSplitTaskTheme(" in app_source
    assert "jcodex-theme-change" in app_source
    assert "jcodex-split-agent-detail" in app_source
    assert "notifyParentAgentDetail(true)" in app_source
    assert "notifyParentAgentDetail(false)" in app_source
    assert "jcodex-split-browser-preview" in app_source
    assert "notifyParentBrowserPreview(true)" in app_source
    assert "notifyParentBrowserPreview(false)" in app_source
    assert "split-child-agent-detail-open" in css_source
    assert "body.split-child-browser-preview-open .split-task-frame" in css_source
    assert "body.split-pane-mode .agent-detail-panel" in css_source
    assert "body.split-workspace-open .agent-detail-panel" in css_source
    assert "body.split-workspace-open.agent-detail-open .main-content" in css_source
    assert "!document.body.classList.contains('split-workspace-open')" in app_source
    assert "splitTaskFrame?.addEventListener('load'" in app_source
    assert "split-pane-mode" in css_source
    assert "splitPaneMode ? splitTaskIdFromUrl : ''" in app_source
    assert "!item.is_split_task" in app_source
    assert ".slice(-AGENT_ACTIVITY_MAX_ITEMS)" in app_source
    assert "normalized.version <= previous.version" in app_source
    render_helper = app_source.split("function renderAgentTeamCard(", 1)[1]
    render_helper = render_helper.split("\nfunction updateAgentTeamSnapshot", 1)[0]
    assert "card.innerHTML" not in render_helper
    assert "card.className = `agent-team-card" not in render_helper
    assert "existingChips = new Map" in render_helper
    assert "chipList.insertBefore(chip" in render_helper
    assert "updateAgentChip(chip" in render_helper
    detail_helper = app_source.split("function renderAgentDetail(", 1)[1]
    detail_helper = detail_helper.split("\nfunction openAgentDetail", 1)[0]
    assert "activityList.innerHTML" not in detail_helper
    assert "updateAgentActivityList(activityList" in detail_helper
    assert "contextScope.replaceChildren" in detail_helper
    assert "function renderAgentStream(" in app_source
    assert "function renderAgentTool(" in app_source
    assert "createAgentOutputMessage(" in app_source
    assert "state.host || document.getElementById('chatMessages')" in app_source
    agent_tool_helper = app_source.split("function renderAgentTool(", 1)[1].split(
        "\nfunction updateAgentActivityList", 1
    )[0]
    assert "element.classList.remove(" in agent_tool_helper
    assert "element.className = `tool-execution" not in agent_tool_helper
    assert "cancelAnimationFrame(agentDetailScrollFrame)" in detail_helper
    assert "AGENT_PUBLIC_ACTIVITY_KINDS.has(kind)" in app_source
    assert "replace(/<think\\b" in app_source
    assert "agent.reasoning" not in app_source
    assert "agent.chain_of_thought" not in app_source
    assert "get_subagent_detail" not in app_source
    assert "result?.type === 'agent_activity'" not in app_source

    send_helper = app_source.split("async function sendMessage()", 1)[1]
    send_helper = send_helper.split("\n// 直接发送指定消息", 1)[0]
    assert "const multiAgentMode = multiAgentModeEnabled;" in send_helper
    assert "const allowAll = autoAllowAll;" in send_helper
    assert "      voiceMode,\n      multiAgentMode," in send_helper  # prettier args
    assert "      multiAgentMode,\n      allowAll," in send_helper

    queued_helper = app_source.split("async function sendMessageWithText(", 1)[1]
    queued_helper = queued_helper.split("\nfunction updateQueueDisplay", 1)[0]
    assert "multiAgentMode = multiAgentModeEnabled" in queued_helper
    assert "allowAll = autoAllowAll" in queued_helper
    assert "      Boolean(voiceMode),\n      Boolean(multiAgentMode)," in queued_helper  # prettier args
    assert "      Boolean(multiAgentMode),\n      Boolean(allowAll)," in queued_helper  # prettier args
    assert "typeof queued.multiAgentMode === 'boolean'" in app_source
    assert "typeof queued.allowAll === 'boolean'" in app_source
    assert "function normalizeToolActor(result)" in app_source
    assert "function isPrimaryToolEvent(result)" in app_source
    assert "function primaryToolSummary(copy" in app_source
    primary_summary = app_source.split("function primaryToolSummary(copy", 1)[1].split(
        "\nfunction isQuestionToolName", 1
    )[0]
    assert "'主智能体'" not in primary_summary
    result_router = app_source.split("function handleResult(", 1)[1]
    result_router = result_router.split("\nfunction showApproval", 1)[0]
    assert "!isPrimaryToolEvent(result)" in result_router
    assert result_router.index("!isPrimaryToolEvent(result)") < result_router.index(
        "trackExecutionResult(state, result)"
    )
    start_tool = app_source.split("function startToolExecution(", 1)[1]
    start_tool = start_tool.split("\nfunction finishToolExecution", 1)[0]
    assert "isQuestionToolName(result.tool) || !isPrimaryToolEvent(result)" in start_tool
    assert "primaryToolSummary(progressCopy, target)" in start_tool
    finish_tool = app_source.split("function finishToolExecution(", 1)[1]
    finish_tool = finish_tool.split("\nfunction finishActiveToolExecutions", 1)[0]
    assert "isQuestionToolName(result.tool) || !isPrimaryToolEvent(result)" in finish_tool
    assert "primaryToolSummary(" in finish_tool
    assert "QUESTION_TOOL_NAMES = new Set(['question', 'ask_user_question'])" in app_source
    assert "function isQuestionToolName(toolName)" in app_source

    history_helper = app_source.split("function renderConversation(conversation)", 1)[1]
    history_helper = history_helper.split("\nasync function sendMessage()", 1)[0]
    assert "event.type === 'agent_team'" in history_helper
    assert "{ animate: false }" in history_helper  # prettier spacing
    assert "if (!isQuestionToolName(event.tool))" in history_helper

    result_helper = app_source.split("function handleResult(", 1)[1]
    result_helper = result_helper.split("\nfunction showApproval", 1)[0]
    assert "result?.type === 'agent_team_update'" in result_helper
    assert "updateAgentTeamSnapshot(" in result_helper

    assert "closeChangeReview({ restoreFocus: false });" in app_source
    review_helper = app_source.split("function openChangeReview(", 1)[1]
    review_helper = review_helper.split("\nfunction closeChangeReview", 1)[0]
    assert "closeAgentDetail({ restoreFocus: false });" in review_helper  # prettier spacing
    reset_helper = app_source.split("function resetConversationView(", 1)[1]
    reset_helper = reset_helper.split("\nfunction formatConversationDate", 1)[0]
    assert "closeAgentDetail({ restoreFocus: false });" in reset_helper
    assert "detachAgentTeamCardsForConversation" in reset_helper
    assert "markAgentTeamsTerminal(conversationId, messageId, 'cancelled');" in app_source

    assert ".agent-team-card" in css_source
    assert ".agent-chip" in css_source
    assert ".agent-detail-panel" in css_source
    assert "--agent-detail-width: 420px" in css_source
    assert "@media (max-width: 1319px)" in css_source
    assert "@media (max-width: 780px)" in css_source
