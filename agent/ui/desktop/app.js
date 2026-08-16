// JCodex Desktop UI - Frontend Logic

let isInitialized = false;
let isProcessing = false;
let currentMessageId = 0;
let messageQueue = [];
let pendingKnowledgeByMessageId = new Map();
let completedMessageByMessageId = new Map();
let streamingResponses = new Map();
let composerAttachments = [];
let currentSettingsSnapshot = null;
let showKnowledgeAppendix = false;
let autoAllowAll = localStorage.getItem('minibot-auto-allow-all') === 'true';
let planModeEnabled = localStorage.getItem('minibot-plan-mode-enabled') === 'true';
let multiAgentModeEnabled = localStorage.getItem('minibot-multi-agent-mode-enabled') === 'true';
let refreshInFlight = false;
let tokenRefreshInFlight = false;
let statusRefreshInFlight = false;
let eelConnectionLost = false;
let eelConnectionNoticeShown = false;
let chatBottomPinGeneration = 0;
let chatAutoFollow = true;
let chatFollowFrame = 0;
let voiceModeActive = false;
let voiceListening = false;
let voiceSpaceHeld = false;
let voiceRecognition = null;
let voiceTranscriptFinal = '';
let voiceTranscriptInterim = '';
let voiceRecognitionError = '';
let voiceSpeechActive = false;
let voiceSpeechQueue = [];
let voiceCurrentUtterance = null;
let voiceSpeechGeneration = 0;
const voiceSpeechKeys = new Set();
let voicePreferredSpeechVoice = null;
let voiceVoicesListenerBound = false;
let voicePendingSend = false;
let voiceAudioContext = null;
let voiceAnalyser = null;
let voiceAudioSource = null;
let voiceAudioStream = null;
let voiceTimeDomainBuffer = null;
let voiceStrandsFrame = 0;
let voiceStrandsPhase = 0;
let voiceStrandsRenderer = null;
let voiceAmplitudeSmoothed = 0.18;
let voiceAmplitudeTimestamp = 0;
let voiceLayoutObserver = null;
let voiceRecognitionStarting = false;
let voiceRecognitionRunning = false;
let voiceRecognitionFinishTimer = 0;
let voiceRecognitionRestartTimer = 0;
let voiceSessionToken = 0;
let voicePendingSendToken = 0;
let voicePointerId = null;
let voiceModeHintTimer = 0;
let voiceEdgeTtsVoice = 'zh-CN-XiaoxiaoNeural';
let voiceEdgeTtsAudio = null;
let voiceEdgeTtsAudioUrl = null;
let voiceEdgeTtsFailed = false;
let lastFocusedElement = null;
let imageLightboxLastFocusedElement = null;
let activeConversationId = null;
let conversations = [];
let projects = [];
let editingProjectId = null;
const expandedProjectIds = new Set();
let conversationRefreshGeneration = 0;
const conversationExecutionStates = new Map();
const executionPollers = new Map();
const pendingStopRequests = new Map();
let isRestoringConversation = false;
let activeToolExecutions = new Map();
let activeCompressionActivities = new Map();
let isAwaitingQuestion = false;
let previewSessions = new Map();
let activePreviewId = null;
let activePreviewUrl = '';
let previewSyncGeneration = 0;
let previewLastFocusedElement = null;
let activeChangeReview = null;
const WORKSPACE_DRAG_TYPE = 'application/x-jcodex-workspace-file';
const activePlanProgress = new Map();
const activeAgentTeams = new Map();
let activeAgentDetail = null;
let agentDetailScrollFrame = 0;
const splitPaneMode = new URLSearchParams(window.location.search).get('split_child') === '1';
const splitTaskIdFromUrl = String(
    new URLSearchParams(window.location.search).get('split_task') || ''
).trim();
const SPLIT_PANE_DEFAULT_WIDTH = 560;
const SPLIT_PANE_MIN_WIDTH = 300;
const SPLIT_MAIN_MIN_WIDTH = 300;
const SPLIT_PANE_WIDTH_STEP = 24;
let splitStateGeneration = 0;
const SIDEBAR_PANEL_STORAGE_KEY = 'minibot-sidebar-panel';
const SIDEBAR_PANEL_NAMES = new Set(['tasks', 'files', 'memory', 'skills', 'settings']);
const SIDEBAR_PANEL_WIDTH_STORAGE_KEY = 'minibot-sidebar-panel-width';
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'minibot-sidebar-collapsed';
const SIDEBAR_PANEL_MIN_WIDTH = 210;
const SIDEBAR_PANEL_MAX_WIDTH = 432;
const SIDEBAR_RAIL_WIDTH = 48;
const SIDEBAR_WIDTH_STEP = 16;
const CHANGE_REVIEW_WIDTH_STORAGE_KEY = 'minibot-change-review-width';
const CHANGE_REVIEW_MIN_WIDTH = 440;
const CHANGE_REVIEW_MAX_WIDTH = 900;
const CHANGE_REVIEW_WIDTH_STEP = 24;
const CHANGE_REVIEW_FILES_WIDTH_STORAGE_KEY = 'minibot-change-review-files-width';
const CHANGE_REVIEW_FILES_DEFAULT_WIDTH = 190;
const CHANGE_REVIEW_FILES_MIN_WIDTH = 160;
const CHANGE_REVIEW_FILES_MAX_WIDTH = 460;
const DOCKED_MAIN_MIN_WIDTH = 380;
const AGENT_DETAIL_WIDTH_STORAGE_KEY = 'minibot-agent-detail-width';
const AGENT_DETAIL_DEFAULT_WIDTH = 420;
const AGENT_DETAIL_MIN_WIDTH = 300;
const AGENT_DETAIL_MAX_WIDTH = 760;
const AGENT_DETAIL_WIDTH_STEP = 24;
const workspaceExpandedDirectories = new Set();
const workspaceDirectoryItems = new Map();
const workspaceDirectoryRequests = new Map();
const CHAT_BOTTOM_THRESHOLD = 240;
const CHAT_BOTTOM_VIEWPORT_RATIO = 0.25;
const CHAT_HISTORY_INITIAL_EVENTS = 120;
const CHAT_HISTORY_LOAD_MORE_EVENTS = 120;
const CHAT_HISTORY_LOAD_MORE_THRESHOLD = 100;
let chatHistoryState = null;
let chatHistoryLoading = false;
let chatRenderTarget = null;
const STREAM_RENDER_INTERVAL_MS = 50;
const STREAM_RENDER_MAX_INTERVAL_MS = 120;
const VOICE_RECOGNITION_LANGUAGE = 'zh-CN';
const CONTEXT_WINDOW_OPTIONS = [128000, 256000, 512000, 1000000];
const CONTEXT_WINDOW_LABELS = ['128K', '256K', '512K', '1M'];
const EDGE_TTS_VOICES = [
    {id: 'zh-CN-XiaoxiaoNeural', name: '晓晓（女·普通话）'},
    {id: 'zh-CN-XiaoyiNeural', name: '晓伊（女·普通话）'},
];
const AGENT_TEAM_MAX_MEMBERS = 12;
const AGENT_TEAM_MAX_SNAPSHOTS = 64;
const AGENT_ACTIVITY_MAX_ITEMS = 80;
const AGENT_PUBLIC_ACTIVITY_KINDS = new Set([
    'progress', 'tool', 'tool_event', 'stream', 'artifact', 'result', 'error', 'status', 'message', 'handoff',
]);
const AGENT_TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const AGENT_STATUS_LABELS = Object.freeze({
    queued: '等待开始',
    running: '正在工作',
    waiting: '等待协作',
    completed: '已完成',
    failed: '执行失败',
    cancelled: '已停止',
});
const QUESTION_TOOL_NAMES = new Set(['question', 'ask_user_question']);

const THEME_ASSETS = {
    light: {
        logo: 'assets/kylin-agent-mark-light.svg',
        mark: 'assets/kylin-agent-mark-light.svg',
        hero: 'assets/kylin-blue-agent-hero.jpg',
    },
    dark: {
        logo: 'assets/kylin-agent-mark-dark.svg',
        mark: 'assets/kylin-agent-mark-dark.svg',
        hero: 'assets/kylin-red-agent-hero.jpg',
    },
};

const ATTACHMENT_LIMITS = Object.freeze({
    count: 8,
    bytesPerFile: 12 * 1024 * 1024,
    totalBytes: 30 * 1024 * 1024,
});

const SUPPORTED_IMAGE_TYPES = new Set([
    'image/png',
    'image/jpeg',
    'image/webp',
]);

const COMPOSER_MAX_HEIGHT = 220;

function resizeComposerInput(input) {
    if (!input) return;
    input.style.height = 'auto';
    const nextHeight = Math.min(input.scrollHeight, COMPOSER_MAX_HEIGHT);
    input.style.height = `${Math.max(nextHeight, 30)}px`;
    input.classList.toggle('is-scrollable', input.scrollHeight > COMPOSER_MAX_HEIGHT);
    input.closest('.input-container')?.classList.toggle('is-multiline', nextHeight > 36);
}

function resetComposerInput(input) {
    if (!input) return;
    input.style.height = '';
    input.classList.remove('is-scrollable');
    input.closest('.input-container')?.classList.remove('is-multiline');
}

function applyTheme(theme, {syncSplitPane = true} = {}) {
    const resolvedTheme = theme === 'dark' ? 'dark' : 'light';
    document.body.classList.toggle('theme-dark', resolvedTheme === 'dark');
    document.body.classList.toggle('theme-light', resolvedTheme === 'light');
    document.documentElement.style.colorScheme = resolvedTheme;
    localStorage.setItem('minibot-theme', resolvedTheme);
    applyThemeAssets(resolvedTheme);
    document.getElementById('themeToggle')?.setAttribute(
        'aria-label',
        resolvedTheme === 'dark' ? '切换到浅色主题' : '切换到深色主题'
    );
    if (syncSplitPane) syncSplitTaskTheme(resolvedTheme);
}

function syncSplitTaskTheme(theme = getCurrentTheme()) {
    if (splitPaneMode) return;
    const frame = document.getElementById('splitTaskFrame');
    if (!frame?.contentWindow) return;
    frame.contentWindow.postMessage(
        {type: 'jcodex-theme-change', theme: theme === 'dark' ? 'dark' : 'light'},
        window.location.origin
    );
}

function notifyParentAgentDetail(open) {
    if (!splitPaneMode || window.parent === window) return;
    window.parent.postMessage(
        {type: 'jcodex-split-agent-detail', open: Boolean(open)},
        window.location.origin
    );
}

function notifyParentBrowserPreview(open) {
    if (!splitPaneMode || window.parent === window) return;
    window.parent.postMessage(
        {type: 'jcodex-split-browser-preview', open: Boolean(open)},
        window.location.origin
    );
}

function setSplitChildAgentDetailOpen(open) {
    if (splitPaneMode) return;
    document.body.classList.toggle('split-child-agent-detail-open', Boolean(open));
}

function setSplitChildBrowserPreviewOpen(open) {
    if (splitPaneMode) return;
    document.body.classList.toggle('split-child-browser-preview-open', Boolean(open));
}

function applyThemeAssets(theme) {
    const assets = THEME_ASSETS[theme] || THEME_ASSETS.light;
    document.querySelectorAll('.theme-asset-logo').forEach((img) => {
        img.src = assets.logo;
    });
    document.querySelectorAll('.theme-asset-mark').forEach((img) => {
        img.src = assets.mark;
    });
    const favicon = document.getElementById('appFavicon');
    if (favicon) favicon.href = assets.mark;
    document.querySelectorAll('.theme-asset-hero').forEach((img) => {
        img.src = assets.hero;
    });
}

function getCurrentTheme() {
    return document.body.classList.contains('theme-dark') ? 'dark' : 'light';
}

function initializeTheme() {
    applyTheme(localStorage.getItem('minibot-theme') || 'light');
}

// Toast notification function
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideInUp 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function setAppStatus(state, text) {
    const indicator = document.getElementById('statusIndicator');
    const dot = indicator?.querySelector('.status-dot');
    const label = indicator?.querySelector('.status-text');
    if (!indicator || !dot || !label) return;

    indicator.dataset.state = state;
    dot.classList.toggle('error', state === 'error');
    dot.classList.toggle('busy', state === 'busy' || state === 'stopping');
    label.textContent = text;
}

function markEelConnectionLost() {
    eelConnectionLost = true;
    if (!eelConnectionNoticeShown) {
        eelConnectionNoticeShown = true;
        setAppStatus('error', '桌面服务连接已断开');
        showToast('桌面服务连接已断开；发送消息时将自动重新连接。', 'error', 5000);
    }
}

function handleEelConnectionError(error) {
    const message = String(error?.message || error || '');
    if (!/Eel connection is unavailable|WebSocket is already in CLOSING or CLOSED state/i.test(message)) {
        return false;
    }
    markEelConnectionLost();
    return true;
}

function canCallEel() {
    // Before Eel's first socket opens, its generated mock functions queue
    // startup calls. After a real disconnect, do not keep scheduling calls.
    return typeof eel !== 'undefined' && !eelConnectionLost;
}

const PENDING_SEND_KEY = 'jcodex-pending-send';
const LAST_AUTO_RELOAD_KEY = 'jcodex-last-auto-reload';
const APP_MODE_KEY = 'jcodex.appMode';
let appMode = ['jcodex', 'jcchat'].includes(localStorage.getItem(APP_MODE_KEY))
    ? localStorage.getItem(APP_MODE_KEY)
    : 'jcodex';

function setAppMode(mode) {
    if (!['jcodex', 'jcchat'].includes(mode)) return;
    appMode = mode;
    try {
        localStorage.setItem(APP_MODE_KEY, mode);
    } catch (_error) {
        /* storage may be unavailable; mode still applies for this session */
    }
    const label = document.getElementById('appModeLabel');
    if (label) label.textContent = mode === 'jcchat' ? 'JC-Chat' : 'JCodex';
    document.querySelectorAll('.app-mode-item').forEach((item) => {
        const active = item.dataset.mode === mode;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    applyAppModeUI();
    refreshWelcomeCards();
}

function applyAppModeUI() {
    const jcchat = appMode === 'jcchat';
    document.body.classList.toggle('jcchat-mode', jcchat);
    const customPromptGroup = document.getElementById('settingCustomPromptGroup');
    if (customPromptGroup) {
        customPromptGroup.style.display = jcchat ? '' : 'none';
    }
    if (!jcchat) return;
    const activePanel = getSidebarPanelButtons()
        .find((button) => button.classList.contains('is-active'))
        ?.dataset.sidebarPanel;
    if (activePanel === 'files' || activePanel === 'skills') {
        setSidebarPanel('tasks');
    }
}

function toggleAppModeMenu(open) {
    const switcher = document.getElementById('appModeSwitcher');
    const menu = document.getElementById('appModeMenu');
    if (!switcher || !menu) return;
    const isOpen = open !== undefined ? Boolean(open) : menu.hidden;
    menu.hidden = !isOpen;
    switcher.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}

function bindAppModeSwitcher() {
    const switcher = document.getElementById('appModeSwitcher');
    const menu = document.getElementById('appModeMenu');
    if (!switcher || !menu) return;
    switcher.addEventListener('click', (event) => {
        if (event.target.closest('.app-mode-menu')) return;
        event.stopPropagation();
        toggleAppModeMenu();
    });
    switcher.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggleAppModeMenu();
        } else if (event.key === 'Escape') {
            toggleAppModeMenu(false);
        }
    });
    menu.addEventListener('click', (event) => {
        const item = event.target.closest('.app-mode-item');
        if (!item) return;
        setAppMode(item.dataset.mode);
        toggleAppModeMenu(false);
    });
    document.addEventListener('click', (event) => {
        if (!switcher.contains(event.target)) toggleAppModeMenu(false);
    });
    document.addEventListener('click', (event) => {
        const menu = document.getElementById('localModelMenu');
        if (!menu || menu.hidden) return;
        if (!menu.contains(event.target) && !event.target.closest('#localModelButton')) {
            hideLocalModelMenu();
        }
    });
    setAppMode(appMode);
}

function eelBridgeReady() {
    // The bridge is usable only when the backend function is registered and
    // the websocket is actually open. After sleep the socket silently closes,
    // which makes eel.send_message fail with "is not a function" or a
    // "WebSocket is already in CLOSING or CLOSED state" error.
    if (typeof eel === 'undefined') return false;
    if (typeof eel.send_message !== 'function') return false;
    const ws = eel._websocket;
    return Boolean(ws) && ws.readyState === WebSocket.OPEN;
}

function eelBridgeDead() {
    // True once the socket has dropped or the backend restarted. During the
    // initial page load the socket is still CONNECTING and eel queues mock
    // calls, so that must not be treated as a dead bridge.
    if (typeof eel === 'undefined') return true;
    if (eelConnectionLost) return true;
    const ws = eel._websocket;
    return Boolean(ws) && ws.readyState === WebSocket.CLOSED;
}

function recoverEelBridge() {
    const lastReload = Number(sessionStorage.getItem(LAST_AUTO_RELOAD_KEY) || 0);
    if (Date.now() - lastReload < 8000) {
        showToast('桌面服务尚未恢复，请稍后重试', 'error', 3000);
        return;
    }
    sessionStorage.setItem(LAST_AUTO_RELOAD_KEY, String(Date.now()));
    setAppStatus('info', '桌面服务连接断开，正在自动重新连接…');
    location.reload();
}

function installEelGuard() {
    // Route every eel call through a connection guard so that non-message
    // actions (switching tasks, creating tasks, settings, ...) auto-reload
    // and reconnect exactly like sending a message does, instead of failing
    // with "eel.xxx(...) is not a function".
    if (!eel || eel.__jcodexGuarded) return;
    const handler = {
        get(target, prop, receiver) {
            if (typeof prop === 'symbol' || (typeof prop === 'string' && prop.startsWith('_'))) {
                return Reflect.get(target, prop, receiver);
            }
            const value = Reflect.get(target, prop, receiver);
            if (typeof value === 'function') {
                return function (...args) {
                    if (eelBridgeDead()) {
                        recoverEelBridge();
                        return () => Promise.reject(
                            new Error('桌面服务连接已断开，正在自动重新连接…')
                        );
                    }
                    return value.apply(target, args);
                };
            }
            // The function is genuinely absent. Only treat it as a dead
            // bridge when the connection is gone; otherwise keep the original
            // "not a function" semantics so typeof guards still degrade.
            if (value === undefined && eelBridgeDead()) {
                return function () {
                    recoverEelBridge();
                    return () => Promise.reject(
                        new Error('桌面服务连接已断开，正在自动重新连接…')
                    );
                };
            }
            return value;
        },
    };
    window.eel = new Proxy(eel, handler);
    try {
        eel.__jcodexGuarded = true;
    } catch (_ignore) {
        /* read-only in exotic environments */
    }
}

function stashPendingSend(message, attachments, conversationId, planMode, voiceMode, multiAgentMode, allowAll, mode) {
    const base = {
        v: 1,
        message,
        conversationId,
        planMode: Boolean(planMode),
        voiceMode: Boolean(voiceMode),
        multiAgentMode: Boolean(multiAgentMode),
        allowAll: Boolean(allowAll),
        mode: mode || 'jcodex',
        ts: Date.now(),
    };
    try {
        sessionStorage.setItem(PENDING_SEND_KEY, JSON.stringify({...base, attachments}));
        return;
    } catch (_quotaError) {
        // Attachments too large for sessionStorage: keep the text and retry
        // without attachments so the user's message is never lost.
    }
    try {
        sessionStorage.setItem(
            PENDING_SEND_KEY,
            JSON.stringify({...base, attachments: [], droppedAttachments: true})
        );
    } catch (_error) {
        // sessionStorage unavailable entirely; the send below will surface the
        // original connection error so the user can retry manually.
    }
}

function autoRecoverEelBridge(message, attachments, conversationId, planMode, voiceMode, multiAgentMode, allowAll, mode) {
    stashPendingSend(message, attachments, conversationId, planMode, voiceMode, multiAgentMode, allowAll, mode);
    recoverEelBridge();
}

async function restorePendingSend() {
    const raw = sessionStorage.getItem(PENDING_SEND_KEY);
    if (!raw) return;
    let payload;
    try {
        payload = JSON.parse(raw);
    } catch (_error) {
        sessionStorage.removeItem(PENDING_SEND_KEY);
        return;
    }
    sessionStorage.removeItem(PENDING_SEND_KEY);
    sessionStorage.removeItem(LAST_AUTO_RELOAD_KEY);
    const pendingAttachments = Array.isArray(payload.attachments) ? payload.attachments : [];
    if (!String(payload.message || '').trim() && !pendingAttachments.length) return;
    // Let the freshly restored UI settle before auto-submitting.
    setTimeout(() => {
        sendMessageWithText(
            String(payload.message || '请解析附件'),
            pendingAttachments,
            String(payload.conversationId || activeConversationId || ''),
            payload.planMode,
            payload.voiceMode,
            payload.multiAgentMode,
            payload.allowAll,
            payload.mode || 'jcodex'
        );
        if (payload.droppedAttachments) {
            showToast('附件过大未能保留，已自动重发文字消息', 'info', 4000);
        }
    }, 400);
}

function getChatDistanceFromBottom(chatMessages = document.getElementById('chatMessages')) {
    if (!chatMessages) return Infinity;
    return Math.max(
        0,
        chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
    );
}

function getChatRenderHost() {
    return chatRenderTarget || document.getElementById('chatMessages');
}

function renderConversationSliced(chatMessages, messages) {
    chatHistoryState = null;
    chatHistoryLoading = false;
    const total = messages.length;
    if (total <= CHAT_HISTORY_INITIAL_EVENTS) {
        renderConversationEvents(messages);
        return;
    }
    const firstIndex = total - CHAT_HISTORY_INITIAL_EVENTS;
    renderConversationEvents(messages.slice(firstIndex));
    chatHistoryState = {
        conversationId: String(activeConversationId || ''),
        messages,
        firstIndex,
    };
}

function maybeLoadOlderChatHistory(chatMessages) {
    const state = chatHistoryState;
    if (!state || chatHistoryLoading) return;
    if (String(state.conversationId) !== String(activeConversationId || '')) return;
    if (state.firstIndex <= 0) return;
    if (chatMessages.scrollTop > CHAT_HISTORY_LOAD_MORE_THRESHOLD) return;

    const messages = state.messages;
    if (!messages.length) return;
    const loadStart = Math.max(0, state.firstIndex - CHAT_HISTORY_LOAD_MORE_EVENTS);
    const batch = messages.slice(loadStart, state.firstIndex);
    if (!batch.length) return;

    const anchor = chatMessages.firstChild;
    if (!anchor) return;
    const anchorTop = anchor.getBoundingClientRect().top;
    const wasRestoring = isRestoringConversation;
    chatHistoryLoading = true;
    isRestoringConversation = true;
    try {
        const fragment = document.createElement('div');
        chatRenderTarget = fragment;
        renderConversationEvents(batch);
        chatRenderTarget = null;
        const nodes = Array.from(fragment.children);
        if (!nodes.length) return;
        chatMessages.prepend(...nodes);
        const delta = anchor.getBoundingClientRect().top - anchorTop;
        if (delta) chatMessages.scrollTop += delta;
        state.firstIndex = loadStart;
    } finally {
        chatRenderTarget = null;
        chatHistoryLoading = false;
        isRestoringConversation = wasRestoring;
    }
}

function setChatAutoFollow(enabled) {
    chatAutoFollow = Boolean(enabled);
    if (!chatAutoFollow && chatFollowFrame) {
        cancelAnimationFrame(chatFollowFrame);
        chatFollowFrame = 0;
    }
}

function updateChatAutoFollow(chatMessages = document.getElementById('chatMessages')) {
    const threshold = Math.max(
        CHAT_BOTTOM_THRESHOLD,
        Number(chatMessages?.clientHeight || 0) * CHAT_BOTTOM_VIEWPORT_RATIO
    );
    setChatAutoFollow(getChatDistanceFromBottom(chatMessages) <= threshold);
}

function followChatOutput(
    chatMessages = document.getElementById('chatMessages'),
    {force = false} = {}
) {
    if (!chatMessages || (!force && !chatAutoFollow)) return;
    if (chatFollowFrame) return;
    chatFollowFrame = requestAnimationFrame(() => {
        chatFollowFrame = 0;
        if (!force && !chatAutoFollow) return;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

function pinChatToBottom(
    chatMessages = document.getElementById('chatMessages'),
    {force = false} = {}
) {
    if (!chatMessages) return;
    if (!force && !chatAutoFollow) return;
    if (force) setChatAutoFollow(true);
    const generation = ++chatBottomPinGeneration;
    chatMessages.style.scrollBehavior = 'auto';

    const align = remainingFrames => {
        if (generation !== chatBottomPinGeneration) return;
        if (!chatAutoFollow) {
            chatMessages.style.removeProperty('scroll-behavior');
            return;
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
        if (remainingFrames > 0) {
            requestAnimationFrame(() => align(remainingFrames - 1));
            return;
        }
        chatMessages.style.removeProperty('scroll-behavior');
    };

    // Re-align after layout and font/markdown measurements settle.
    align(2);
}

function getSpeechRecognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function getPreferredSpeechVoiceScore(voice) {
    const language = String(voice?.lang || '').toLowerCase().replace('_', '-');
    if (!language.startsWith('zh')) return Number.NEGATIVE_INFINITY;

    const name = String(voice?.name || '').toLowerCase();
    let score = language === 'zh-cn' || language === 'zh-hans' ? 120 : 80;
    if (/natural|premium|enhanced|neural|自然|增强/.test(name)) score += 60;
    if (/xiaoxiao|yunxi|yunyang|xiaoyi|ting[- ]?ting|婷婷/.test(name)) score += 45;
    if (/mandarin|putonghua|普通话|中文/.test(name)) score += 12;
    if (voice?.localService) score += 6;
    if (voice?.default) score += 3;
    return score;
}

function refreshPreferredSpeechVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    voicePreferredSpeechVoice = voices
        .map((voice, index) => ({voice, index, score: getPreferredSpeechVoiceScore(voice)}))
        .filter(item => Number.isFinite(item.score))
        .sort((left, right) => right.score - left.score || left.index - right.index)[0]
        ?.voice || null;
    return voicePreferredSpeechVoice;
}

function initializeVoiceSpeechVoices() {
    if (!('speechSynthesis' in window)) return;
    refreshPreferredSpeechVoice();
    if (voiceVoicesListenerBound) return;
    if (typeof window.speechSynthesis.addEventListener === 'function') {
        window.speechSynthesis.addEventListener('voiceschanged', refreshPreferredSpeechVoice);
    } else {
        window.speechSynthesis.onvoiceschanged = refreshPreferredSpeechVoice;
    }
    voiceVoicesListenerBound = true;
}

function loadVoiceTtsPrefs() {
    voiceEdgeTtsVoice = localStorage.getItem('jcodex.voiceEdgeVoice') || 'zh-CN-XiaoxiaoNeural';
    if (!EDGE_TTS_VOICES.some(entry => entry.id === voiceEdgeTtsVoice)) {
        voiceEdgeTtsVoice = 'zh-CN-XiaoxiaoNeural';
    }
    voiceEdgeTtsFailed = false;
}

function saveVoiceTtsPrefs() {
    localStorage.setItem('jcodex.voiceEdgeVoice', voiceEdgeTtsVoice);
    voiceEdgeTtsFailed = false;
}

function _voiceEdgeTtsAudioUrl(audioBase64) {
    const binary = atob(String(audioBase64 || ''));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return URL.createObjectURL(new Blob([bytes], {type: 'audio/mpeg'}));
}

function populateVoiceTtsSettings() {
    const voiceSelect = document.getElementById('settingVoiceEdgeVoice');
    if (!voiceSelect) return;
    voiceSelect.innerHTML = '';
    for (const entry of EDGE_TTS_VOICES) {
        const option = document.createElement('option');
        option.value = entry.id;
        option.textContent = entry.name;
        voiceSelect.appendChild(option);
    }
    voiceSelect.value = voiceEdgeTtsVoice;
    voiceSelect.onchange = () => {
        voiceEdgeTtsVoice = voiceSelect.value;
        saveVoiceTtsPrefs();
    };
}

function contextWindowIndexFor(value) {
    const target = Number(value);
    if (!Number.isFinite(target) || target <= 0) return 1;
    let bestIndex = 1;
    let bestDistance = Infinity;
    CONTEXT_WINDOW_OPTIONS.forEach((option, index) => {
        const distance = Math.abs(option - target);
        if (distance < bestDistance) {
            bestDistance = distance;
            bestIndex = index;
        }
    });
    return bestIndex;
}

function updateContextWindowLabel() {
    const slider = document.getElementById('settingContextWindow');
    const label = document.getElementById('settingContextWindowValue');
    if (!slider || !label) return;
    const index = Number(slider.value);
    if (!Number.isInteger(index) || index < 0 || index >= CONTEXT_WINDOW_LABELS.length) return;
    label.textContent = CONTEXT_WINDOW_LABELS[index];
}

let contextWindowPreviewTimer = null;

async function previewContextWindow() {
    const slider = document.getElementById('settingContextWindow');
    if (!slider) return;
    const option = CONTEXT_WINDOW_OPTIONS[Number(slider.value)];
    if (!option) return;
    clearTimeout(contextWindowPreviewTimer);
    contextWindowPreviewTimer = window.setTimeout(async () => {
        try {
            const result = await eel.preview_context_window(option)();
            if (result && result.success) {
                await updateTokenIndicator();
            }
        } catch (e) {
            console.error('Failed to preview context window:', e);
        }
    }, 200);
}

function setVoiceModeStatus(message, state = 'idle') {
    const overlay = document.getElementById('voiceModeOverlay');
    const status = document.getElementById('voiceModeStatus');
    if (status) status.textContent = String(message || '');
    if (overlay) overlay.dataset.voiceState = state;
}

function showVoiceModeHint() {
    const hint = document.getElementById('voiceModeHint');
    if (!hint) return;
    clearTimeout(voiceModeHintTimer);
    const outputActive = Boolean(
        isProcessing && getActiveExecutionState()?.running
    );
    hint.textContent = outputActive
        ? '按住空格打断并说话'
        : '按住空格说话';
    hint.hidden = false;
    voiceModeHintTimer = window.setTimeout(() => {
        hint.hidden = true;
    }, 2600);
}

function updateVoiceTranscript() {
    const transcript = document.getElementById('voiceTranscript');
    if (!transcript) return;
    const text = `${voiceTranscriptFinal}${voiceTranscriptInterim}`.trim();
    transcript.textContent = text || '我会把识别到的内容显示在这里';
    transcript.classList.toggle('has-content', Boolean(text));
}

function getVoiceAmplitude() {
    const synthetic = voiceSpeechActive
        ? 0.5 + (0.5 + 0.5 * Math.sin(voiceStrandsPhase * 2.4)) * 0.28
        : voiceListening ? 0.31 : 0.18;
    if (!voiceAnalyser) return synthetic;
    if (!voiceTimeDomainBuffer || voiceTimeDomainBuffer.length !== voiceAnalyser.fftSize) {
        voiceTimeDomainBuffer = new Uint8Array(voiceAnalyser.fftSize);
    }
    const data = voiceTimeDomainBuffer;
    voiceAnalyser.getByteTimeDomainData(data);
    let total = 0;
    data.forEach(value => {
        const normalized = (value - 128) / 128;
        total += normalized * normalized;
    });
    const rms = Math.sqrt(total / data.length);
    // Browser AGC stays disabled so sensitivity does not drift between turns.
    // Compensate here with a compressed software gain that preserves quieter speech.
    const activeLevel = Math.max(0, rms - 0.003);
    const normalizedSpeech = Math.min(1, activeLevel * 14);
    const measured = 0.27 + Math.pow(normalizedSpeech, 0.72) * 0.58;
    return Math.min(0.88, Math.max(synthetic, measured));
}

function getSmoothedVoiceAmplitude(timestamp) {
    const target = getVoiceAmplitude();
    const elapsed = voiceAmplitudeTimestamp
        ? Math.min(0.1, Math.max(0, (timestamp - voiceAmplitudeTimestamp) / 1000))
        : 1 / 60;
    voiceAmplitudeTimestamp = timestamp;
    const response = target > voiceAmplitudeSmoothed ? 5.2 : 2.6;
    const blend = 1 - Math.exp(-response * elapsed);
    const proposedDelta = (target - voiceAmplitudeSmoothed) * blend;
    const maxDelta = (target > voiceAmplitudeSmoothed ? 1.15 : 0.62) * elapsed;
    voiceAmplitudeSmoothed += Math.max(-maxDelta, Math.min(maxDelta, proposedDelta));
    return voiceAmplitudeSmoothed;
}

function resetVoiceAmplitude(level = 0.18) {
    voiceAmplitudeSmoothed = level;
    voiceAmplitudeTimestamp = 0;
}

const VOICE_BAR_COUNT = 9;

function _voiceRoundRectPath(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
}

function _voiceBarPalette() {
    const isDark = document.body.classList.contains('theme-dark');
    return isDark
        ? {top: 'rgba(238, 238, 234, 0.95)', bottom: 'rgba(115, 115, 110, 0.5)'}
        : {top: 'rgba(31, 31, 29, 0.9)', bottom: 'rgba(111, 111, 106, 0.48)'};
}

function createVoiceStrandsRenderer() {
    const canvas = document.getElementById('voiceStrandsCanvas');
    const ctx = canvas?.getContext('2d', {alpha: true});
    if (!canvas || !ctx) return null;
    return {
        canvas,
        ctx,
        timeOrigin: null,
        barHeights: Array(VOICE_BAR_COUNT).fill(0),
    };
}

function resizeVoiceStrands(renderer) {
    const rect = renderer.canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(rect.width * ratio));
    const height = Math.max(1, Math.round(rect.height * ratio));
    if (renderer.canvas.width !== width || renderer.canvas.height !== height) {
        renderer.canvas.width = width;
        renderer.canvas.height = height;
    }
    return {width, height};
}

function drawVoiceStrands(timestamp = performance.now()) {
    if (!voiceStrandsRenderer) return;
    const renderer = voiceStrandsRenderer;
    const {ctx, barHeights} = renderer;
    const {width, height} = resizeVoiceStrands(renderer);
    const energy = getSmoothedVoiceAmplitude(timestamp);
    renderer.timeOrigin ??= timestamp;
    const animationTime = (timestamp - renderer.timeOrigin) * 0.001;
    ctx.clearRect(0, 0, width, height);

    const listening = Boolean(voiceListening || voiceRecognitionRunning);
    const barWidth = Math.max(4, Math.round(height * 0.05));
    const gap = Math.max(3, Math.round(barWidth * 0.85));
    const totalWidth = VOICE_BAR_COUNT * barWidth + (VOICE_BAR_COUNT - 1) * gap;
    const startX = (width - totalWidth) / 2;
    const baseY = height * 0.56;
    const maxHeight = height * 0.46;
    const minHeight = Math.max(2, height * 0.04);
    const centerIndex = (VOICE_BAR_COUNT - 1) / 2;
    const palette = _voiceBarPalette();
    const gradient = ctx.createLinearGradient(0, baseY - maxHeight, 0, baseY);
    gradient.addColorStop(0, palette.top);
    gradient.addColorStop(1, palette.bottom);
    ctx.fillStyle = gradient;

    for (let index = 0; index < VOICE_BAR_COUNT; index += 1) {
        const centerBias = 1 - Math.abs(index - centerIndex) / centerIndex;
        const idleMotion = 0.5 + 0.5 * Math.sin(animationTime * 2.1 + index * 0.85);
        let target;
        if (listening) {
            const envelope = 0.3 + 0.7 * centerBias;
            target =
                minHeight
                + (maxHeight - minHeight) * (0.18 + 0.82 * energy) * envelope;
        } else {
            target = minHeight + (maxHeight - minHeight) * 0.12 * idleMotion;
        }
        const eased = barHeights[index] + (target - barHeights[index]) * 0.16;
        barHeights[index] = eased;
        const barX = startX + index * (barWidth + gap);
        const barHeight = Math.max(minHeight, eased);
        _voiceRoundRectPath(
            ctx,
            barX,
            baseY - barHeight,
            barWidth,
            barHeight,
            barWidth / 2
        );
        ctx.fill();
    }
    voiceStrandsPhase = (
        voiceStrandsPhase + 0.012 + energy * 0.018
    ) % (Math.PI * 10);
    voiceStrandsFrame = requestAnimationFrame(drawVoiceStrands);
}

function positionVoiceStrands() {
    if (!voiceModeActive) return;
    const overlay = document.getElementById('voiceModeOverlay');
    const inputArea = document.querySelector('.main-content .input-area');
    const inputContainer = inputArea?.querySelector('.input-container');
    const mainContent = document.querySelector('.main-content');
    if (!overlay || !inputArea || !inputContainer || !mainContent) return;

    const inputRect = inputContainer.getBoundingClientRect();
    const mainRect = mainContent.getBoundingClientRect();
    const width = Math.max(200, Math.min(mainRect.width - 28, 240));
    const bottom = Math.max(8, window.innerHeight - inputRect.top + 10);
    overlay.style.setProperty(
        '--voice-strands-center-x',
        `${inputRect.left + inputRect.width / 2}px`
    );
    overlay.style.setProperty('--voice-strands-bottom', `${bottom}px`);
    overlay.style.setProperty('--voice-strands-width', `${width}px`);
}

function startVoiceStrands() {
    if (voiceStrandsFrame) return;
    positionVoiceStrands();
    try {
        voiceStrandsRenderer ||= createVoiceStrandsRenderer();
    } catch (error) {
        console.error('Failed to initialize voice strands:', error);
        voiceStrandsRenderer = null;
    }
    if (!voiceStrandsRenderer) return;
    voiceStrandsFrame = requestAnimationFrame(drawVoiceStrands);
}

function stopVoiceStrands() {
    if (voiceStrandsFrame) cancelAnimationFrame(voiceStrandsFrame);
    voiceStrandsFrame = 0;
    resetVoiceAmplitude();
    if (!voiceStrandsRenderer) return;
    voiceStrandsRenderer.timeOrigin = null;
    voiceStrandsPhase = 0;
    const {ctx, barHeights} = voiceStrandsRenderer;
    ctx.clearRect(
        0,
        0,
        voiceStrandsRenderer.canvas.width,
        voiceStrandsRenderer.canvas.height
    );
    barHeights.fill(0);
}

async function startVoiceAudioMeter(sessionToken = voiceSessionToken) {
    if (voiceAudioStream || !navigator.mediaDevices?.getUserMedia) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                autoGainControl: false,
                echoCancellation: true,
                noiseSuppression: true,
                channelCount: 1,
            },
        });
        if (!voiceModeActive || !voiceListening || sessionToken !== voiceSessionToken) {
            stream.getTracks().forEach(track => track.stop());
            return;
        }
        voiceAudioStream = stream;
        voiceAudioContext = new AudioContext();
        voiceAnalyser = voiceAudioContext.createAnalyser();
        voiceAnalyser.fftSize = 1024;
        voiceTimeDomainBuffer = new Uint8Array(voiceAnalyser.fftSize);
        voiceAudioSource = voiceAudioContext.createMediaStreamSource(voiceAudioStream);
        voiceAudioSource.connect(voiceAnalyser);
    } catch (error) {
        voiceAudioStream = null;
        if (String(error?.name || '') === 'NotAllowedError') {
            setVoiceModeStatus('请允许麦克风权限，仍可使用空格触发识别', 'error');
        }
    }
}

function stopVoiceAudioMeter() {
    voiceAudioStream?.getTracks().forEach(track => track.stop());
    voiceAudioSource?.disconnect?.();
    voiceAudioContext?.close?.();
    voiceAudioStream = null;
    voiceAudioSource = null;
    voiceAnalyser = null;
    voiceTimeDomainBuffer = null;
    voiceAudioContext = null;
}

function cancelVoiceSpeech() {
    voiceSpeechGeneration += 1;
    voiceSpeechQueue.length = 0;
    voiceSpeechKeys.clear();
    voiceCurrentUtterance = null;
    if (voiceEdgeTtsAudio) {
        try {
            voiceEdgeTtsAudio.pause();
        } catch (_error) {
            // The audio element may already have ended.
        }
        voiceEdgeTtsAudio = null;
    }
    if (voiceEdgeTtsAudioUrl) {
        URL.revokeObjectURL(voiceEdgeTtsAudioUrl);
        voiceEdgeTtsAudioUrl = null;
    }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    voiceSpeechActive = false;
    document.getElementById('voiceModeOverlay')?.classList.remove('is-speaking');
}

function pauseVoiceResponseForConversation() {
    // Keep the reply visible, but give an interrupted user the audio channel.
    streamingResponses.forEach(state => {
        state.voiceDisabled = true;
    });
    cancelVoiceSpeech();
}

function pauseActiveOutputForVoiceInput() {
    const state = getActiveExecutionState();
    if (!isProcessing || !state?.running) return false;

    // Use the same cancellation path as the visible stop button so a spoken
    // interruption freezes the live task before the next voice turn is sent.
    document.getElementById('stopButton')?.click();
    return true;
}

function playNextVoiceResponse() {
    if (!voiceModeActive || voiceListening || voiceCurrentUtterance) return;
    const next = voiceSpeechQueue.shift();
    if (!next) {
        voiceSpeechActive = false;
        document.getElementById('voiceModeOverlay')?.classList.remove('is-speaking');
        if (voiceModeActive && !voiceListening) {
            setVoiceModeStatus('按住空格键继续说话', 'idle');
        }
        return;
    }
    const generation = voiceSpeechGeneration;

    if (
        !voiceEdgeTtsFailed
        && typeof eel !== 'undefined'
        && eel.voice_tts_speak
    ) {
        voiceCurrentUtterance = {generation, key: next.key, kind: 'edge'};
        eel.voice_tts_speak(next.content, voiceEdgeTtsVoice)(result => {
            if (
                generation !== voiceSpeechGeneration
                || voiceCurrentUtterance?.key !== next.key
            ) {
                return;
            }
            if (!result || !result.success || !result.audio_base64) {
                voiceEdgeTtsFailed = true;
                voiceCurrentUtterance = null;
                voiceSpeechQueue.unshift(next);
                window.setTimeout(playNextVoiceResponse, 0);
                return;
            }
            if (voiceEdgeTtsAudioUrl) {
                URL.revokeObjectURL(voiceEdgeTtsAudioUrl);
                voiceEdgeTtsAudioUrl = null;
            }
            voiceEdgeTtsAudioUrl = _voiceEdgeTtsAudioUrl(result.audio_base64);
            const audio = new Audio(voiceEdgeTtsAudioUrl);
            voiceEdgeTtsAudio = audio;
            const finish = () => {
                if (voiceEdgeTtsAudio === audio) voiceEdgeTtsAudio = null;
                if (voiceEdgeTtsAudioUrl) {
                    URL.revokeObjectURL(voiceEdgeTtsAudioUrl);
                    voiceEdgeTtsAudioUrl = null;
                }
                if (
                    generation !== voiceSpeechGeneration
                    || voiceCurrentUtterance?.key !== next.key
                ) {
                    return;
                }
                voiceCurrentUtterance = null;
                if (voiceSpeechQueue.length && voiceModeActive && !voiceListening) {
                    window.setTimeout(playNextVoiceResponse, 45);
                    return;
                }
                playNextVoiceResponse();
            };
            audio.onended = finish;
            audio.onerror = finish;
            voiceSpeechActive = true;
            document.getElementById('voiceModeOverlay')?.classList.add('is-speaking');
            setVoiceModeStatus('正在为你朗读回答', 'speaking');
            audio.play().catch(finish);
        });
        return;
    }

    if (!('speechSynthesis' in window)) {
        voiceCurrentUtterance = null;
        window.setTimeout(playNextVoiceResponse, 0);
        return;
    }
    const preferredVoice = voicePreferredSpeechVoice || refreshPreferredSpeechVoice();
    const utterance = new SpeechSynthesisUtterance(next.content);
    voiceCurrentUtterance = utterance;
    if (preferredVoice) utterance.voice = preferredVoice;
    utterance.lang = preferredVoice?.lang || VOICE_RECOGNITION_LANGUAGE;
    utterance.rate = 0.94;
    utterance.pitch = 1.02;
    utterance.onstart = () => {
        if (!voiceModeActive) return;
        voiceSpeechActive = true;
        document.getElementById('voiceModeOverlay')?.classList.add('is-speaking');
        setVoiceModeStatus('正在为你朗读回答', 'speaking');
    };
    const finish = () => {
        if (generation !== voiceSpeechGeneration || voiceCurrentUtterance !== utterance) return;
        voiceCurrentUtterance = null;
        if (voiceSpeechQueue.length && voiceModeActive && !voiceListening) {
            window.setTimeout(playNextVoiceResponse, 45);
            return;
        }
        playNextVoiceResponse();
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.speak(utterance);
}

function enqueueVoiceSpeech(content, speechKey) {
    if (!voiceModeActive) return false;
    const speechText = String(content || '').replace(/\s+/g, ' ').trim();
    if (!speechText) return false;
    const key = String(speechKey || speechText);
    if (voiceSpeechKeys.has(key)) return false;
    voiceSpeechKeys.add(key);
    voiceSpeechQueue.push({content: speechText, key});
    playNextVoiceResponse();
    return true;
}

function speakVoiceResponse(content, messageId = 0) {
    const visibleContent = getVisibleModelContent(content).replace(/\s+/g, ' ').trim();
    enqueueVoiceSpeech(
        visibleContent,
        `message:${Number(messageId || 0)}:${visibleContent}`
    );
}

function createVoiceRecognition(sessionToken) {
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) return null;
    const recognition = new Recognition();
    recognition.lang = VOICE_RECOGNITION_LANGUAGE;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = () => {
        if (recognition !== voiceRecognition || sessionToken !== voiceSessionToken) return;
        voiceRecognitionStarting = false;
        voiceRecognitionRunning = true;
        if (!voiceModeActive || !voiceListening) {
            try {
                recognition.stop();
            } catch (_error) {
                // The recognition engine may already have ended.
            }
            return;
        }
        document.getElementById('voiceModeOverlay')?.classList.add('is-listening');
        setVoiceModeStatus('已暂停回答，正在聆听…松开空格键发送', 'listening');
    };
    recognition.onresult = event => {
        if (recognition !== voiceRecognition || sessionToken !== voiceSessionToken) return;
        let interim = '';
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
            const result = event.results[index];
            const value = String(result[0]?.transcript || '');
            if (result.isFinal) voiceTranscriptFinal += value;
            else interim += value;
        }
        voiceTranscriptInterim = interim;
        updateVoiceTranscript();
    };
    recognition.onerror = event => {
        if (recognition !== voiceRecognition || sessionToken !== voiceSessionToken) return;
        const error = String(event.error || 'unknown');
        voiceRecognitionError = error;
        voiceRecognitionStarting = false;
        if (error === 'not-allowed' || error === 'service-not-allowed') {
            setVoiceModeStatus('请允许麦克风权限后重试', 'error');
        } else if (error !== 'aborted' && error !== 'no-speech') {
            setVoiceModeStatus('语音识别暂时不可用，请重试', 'error');
        }
    };
    recognition.onend = () => {
        if (recognition !== voiceRecognition || sessionToken !== voiceSessionToken) return;
        voiceRecognitionStarting = false;
        voiceRecognitionRunning = false;
        if (voicePendingSend) {
            const pendingToken = voicePendingSendToken;
            voicePendingSend = false;
            voicePendingSendToken = 0;
            clearTimeout(voiceRecognitionFinishTimer);
            voiceRecognitionFinishTimer = 0;
            if (pendingToken === voiceSessionToken) submitVoiceTranscript();
            return;
        }
        if (voiceListening && voiceSpaceHeld && voiceModeActive && !voiceRecognitionError) {
            clearTimeout(voiceRecognitionRestartTimer);
            voiceRecognitionRestartTimer = window.setTimeout(() => {
                voiceRecognitionRestartTimer = 0;
                if (!voiceListening || !voiceSpaceHeld || !voiceModeActive || voiceRecognitionRunning) return;
                voiceRecognitionStarting = true;
                try {
                    recognition.start();
                } catch (_error) {
                    voiceRecognitionStarting = false;
                    setVoiceModeStatus('语音识别正在准备，请稍后重试', 'error');
                }
            }, 0);
        }
    };
    return recognition;
}

function isVoiceShortcutBlocked(target) {
    if (!target) return false;
    return Boolean(target.closest?.('.modal.active, dialog[open]'));
}

function startVoiceListening() {
    if (!voiceModeActive || voiceListening) return;
    const outputPaused = pauseActiveOutputForVoiceInput();
    pauseVoiceResponseForConversation();
    voiceSessionToken += 1;
    const sessionToken = voiceSessionToken;
    voiceListening = true;
    resetVoiceAmplitude(0.31);
    voicePendingSend = false;
    voicePendingSendToken = 0;
    clearTimeout(voiceRecognitionFinishTimer);
    clearTimeout(voiceRecognitionRestartTimer);
    voiceRecognitionFinishTimer = 0;
    voiceRecognitionRestartTimer = 0;
    document.getElementById('voiceModeOverlay')?.classList.add('is-listening');
    setVoiceModeStatus(
        outputPaused
            ? '已暂停输出，正在聆听…松开空格键发送'
            : '正在聆听…松开空格键发送',
        'listening'
    );
    startVoiceAudioMeter(sessionToken);
    voiceTranscriptFinal = '';
    voiceTranscriptInterim = '';
    voiceRecognitionError = '';
    updateVoiceTranscript();
    const previousRecognition = voiceRecognition;
    voiceRecognition = null;
    voiceRecognitionStarting = false;
    voiceRecognitionRunning = false;
    try {
        previousRecognition?.abort();
    } catch (_error) {
        // The previous recognition round may already be fully closed.
    }
    voiceRecognition = createVoiceRecognition(sessionToken);
    if (!voiceRecognition) {
        setVoiceModeStatus('正在聆听…当前环境不支持自动识别', 'listening');
        return;
    }
    voiceRecognitionStarting = true;
    try {
        voiceRecognition.start();
    } catch (_error) {
        voiceRecognitionStarting = false;
        setVoiceModeStatus('语音识别正在准备，请稍后重试', 'error');
    }
}

function stopVoiceListening({send = true} = {}) {
    if (!voiceListening && !voiceRecognitionRunning && !voiceRecognitionStarting) return;
    voiceSpaceHeld = false;
    voicePointerId = null;
    voicePendingSend = send;
    voicePendingSendToken = voiceSessionToken;
    voiceListening = false;
    resetVoiceAmplitude();
    document.getElementById('voiceModeOverlay')?.classList.remove('is-listening');
    stopVoiceAudioMeter();
    clearTimeout(voiceRecognitionRestartTimer);
    voiceRecognitionRestartTimer = 0;
    if (voiceRecognition && (voiceRecognitionRunning || voiceRecognitionStarting)) {
        let waitingForRecognitionEnd = true;
        try {
            voiceRecognition.stop();
        } catch (_error) {
            waitingForRecognitionEnd = false;
            voiceRecognitionStarting = false;
            voiceRecognitionRunning = false;
        }
        setVoiceModeStatus(send ? '正在整理识别内容…' : '已停止聆听', 'processing');
        if (!waitingForRecognitionEnd) {
            voicePendingSend = false;
            voicePendingSendToken = 0;
            if (send) submitVoiceTranscript();
            return;
        }
        clearTimeout(voiceRecognitionFinishTimer);
        voiceRecognitionFinishTimer = window.setTimeout(() => {
            voiceRecognitionFinishTimer = 0;
            if (!voicePendingSend) return;
            const pendingToken = voicePendingSendToken;
            voicePendingSend = false;
            voicePendingSendToken = 0;
            if (pendingToken === voiceSessionToken) submitVoiceTranscript();
        }, 320);
        return;
    }
    voicePendingSend = false;
    voicePendingSendToken = 0;
    if (send) submitVoiceTranscript();
}

function submitVoiceTranscript() {
    const transcript = `${voiceTranscriptFinal}${voiceTranscriptInterim}`.trim();
    const blockingRecognitionError = voiceRecognitionError
        && voiceRecognitionError !== 'no-speech'
        && voiceRecognitionError !== 'aborted';
    if (!transcript || blockingRecognitionError) {
        if (voiceModeActive && !blockingRecognitionError) {
            setVoiceModeStatus('没有听清，请按住空格键重试', 'idle');
        }
        return;
    }
    const messageInput = document.getElementById('messageInput');
    messageInput.value = transcript;
    messageInput.dispatchEvent(new Event('input', {bubbles: true}));
    setVoiceModeStatus('已识别，正在发送…', 'processing');
    sendMessage();
}

function openVoiceMode() {
    voiceModeActive = true;
    lastFocusedElement = document.activeElement;
    const overlay = document.getElementById('voiceModeOverlay');
    const button = document.getElementById('voiceModeButton');
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    button?.setAttribute('aria-pressed', 'true');
    button?.setAttribute('aria-label', '关闭语音对话模式');
    document.body.classList.add('voice-mode-active');
    showVoiceModeHint();
    setVoiceModeStatus('按住空格键开始说话', 'idle');
    positionVoiceStrands();
    requestAnimationFrame(positionVoiceStrands);
    startVoiceStrands();
    if (!getSpeechRecognitionConstructor()) {
        setVoiceModeStatus('当前环境不支持自动识别，请检查桌面麦克风设置', 'error');
    }
    document.getElementById('voiceHoldButton')?.focus();
}

function closeVoiceMode() {
    voiceModeActive = false;
    voiceSpaceHeld = false;
    voicePointerId = null;
    clearTimeout(voiceRecognitionFinishTimer);
    clearTimeout(voiceRecognitionRestartTimer);
    voiceRecognitionFinishTimer = 0;
    voiceRecognitionRestartTimer = 0;
    stopVoiceListening({send: false});
    if (voiceRecognition) voiceRecognition.abort();
    voiceRecognitionStarting = false;
    voiceRecognitionRunning = false;
    voicePendingSend = false;
    voicePendingSendToken = 0;
    cancelVoiceSpeech();
    stopVoiceAudioMeter();
    stopVoiceStrands();
    const overlay = document.getElementById('voiceModeOverlay');
    const button = document.getElementById('voiceModeButton');
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    overlay.classList.remove('is-listening', 'is-speaking');
    button?.setAttribute('aria-pressed', 'false');
    button?.setAttribute('aria-label', '打开语音对话模式');
    document.body.classList.remove('voice-mode-active');
    lastFocusedElement?.focus?.();
}

function toggleVoiceMode() {
    if (voiceModeActive) closeVoiceMode();
    else openVoiceMode();
}

function updateProcessingUI(processing, stateText = '') {
    isProcessing = Boolean(processing);
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const stopButton = document.getElementById('stopButton');
    sendButton.disabled = !messageInput.value.trim() && composerAttachments.length === 0;
    stopButton.style.display = isProcessing ? 'flex' : 'none';
    stopButton.disabled = false;
    document.body.classList.toggle('is-processing', isProcessing);
    document.querySelector('.input-container')?.classList.toggle('is-processing', isProcessing);
    if (isProcessing) {
        setAppStatus('busy', stateText || '正在执行');
    } else if (isInitialized) {
        setAppStatus('ready', '就绪');
    }
}

function getConversationExecutionState(conversationId, create = true) {
    const id = String(conversationId || '');
    if (!id) return null;
    let state = conversationExecutionStates.get(id);
    if (!state && create) {
        state = {
            conversationId: id,
            messageId: 0,
            terminalMessageId: 0,
            running: false,
            stopping: false,
            outputStopped: false,
            awaitingQuestion: false,
            awaitingApproval: false,
            unreadCompletion: false,
            streamContents: new Map(),
            thinkingStartByStream: new Map(),
            activeToolEvent: null,
            activeCompressionEvent: null,
        };
        conversationExecutionStates.set(id, state);
    }
    return state || null;
}

function updateConversationExecutionState(conversationId, updates = {}) {
    const state = getConversationExecutionState(conversationId);
    if (!state) return null;
    const incomingMessageId = Number(updates.messageId || state.messageId || 0);
    if (
        updates.running === true
        && incomingMessageId
        && incomingMessageId <= Number(state.terminalMessageId || 0)
    ) {
        return state;
    }
    if (updates.running === false && incomingMessageId) {
        state.terminalMessageId = Math.max(
            Number(state.terminalMessageId || 0), incomingMessageId
        );
    } else if (
        updates.running === true
        && incomingMessageId > Number(state.terminalMessageId || 0)
    ) {
        state.terminalMessageId = 0;
    }
    Object.assign(state, updates);
    if (Number(updates.messageId || 0) > 0) {
        state.messageId = Number(updates.messageId);
    }
    return state;
}

function isConversationRunning(conversationId) {
    return Boolean(getConversationExecutionState(conversationId, false)?.running);
}

function getRunningConversationState() {
    return Array.from(conversationExecutionStates.values()).find(state => state.running) || null;
}

function hasRunningExecution() {
    return Boolean(getRunningConversationState());
}

function getActiveExecutionState() {
    return getConversationExecutionState(activeConversationId, false);
}

function planProgressKey(conversationId, messageId) {
    return `${String(conversationId || '')}:${Number(messageId || 0)}`;
}

function normalizePlanProgress(raw, conversationId = activeConversationId, messageId = 0) {
    if (!raw || !Array.isArray(raw.plan) || !raw.plan.length) return null;
    const validStatuses = new Set(['pending', 'in_progress', 'completed', 'cancelled']);
    const validTerminalStates = new Set(['complete', 'error', 'stopped']);
    const terminalState = String(
        raw.terminal_state || raw.terminalState || ''
    ).trim().toLowerCase();
    const plan = raw.plan
        .filter(item => item && String(item.step || '').trim())
        .map(item => ({
            step: String(item.step || '').trim(),
            status: validStatuses.has(item.status) ? item.status : 'pending',
        }));
    if (!plan.length) return null;
    return {
        conversationId: String(conversationId || raw.conversation_id || ''),
        messageId: Number(messageId || raw.message_id || 0),
        explanation: String(raw.explanation || '').trim(),
        version: Number(raw.version || 0),
        error: String(raw.error || '').trim(),
        terminalState: validTerminalStates.has(terminalState) ? terminalState : '',
        terminalMessage: String(
            raw.terminal_message || raw.terminalMessage || ''
        ).trim(),
        plan,
    };
}

function getLatestConversationPlan(messages = []) {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const event = messages[index];
        if (event?.type !== 'plan_update') continue;
        const normalized = normalizePlanProgress(
            event,
            activeConversationId,
            Number(event.message_id || 0)
        );
        if (normalized) return normalized;
    }
    return null;
}

function closePlanProgress() {
    const root = document.getElementById('planProgress');
    const trigger = document.getElementById('planProgressTrigger');
    root?.classList.remove('is-expanded');
    trigger?.setAttribute('aria-expanded', 'false');
}

function renderPlanProgress(snapshot = null) {
    const root = document.getElementById('planProgress');
    if (!root) return;
    // 计划模式关闭时不显示计划进度胶囊（含轮询/事件再次触发的情况）。
    if (!planModeEnabled) {
        root.hidden = true;
        closePlanProgress();
        return;
    }
    const activeState = getActiveExecutionState();
    const messageId = Number(activeState?.messageId || currentMessageId || 0);
    const key = planProgressKey(activeConversationId, messageId);
    const planState = snapshot || activePlanProgress.get(key) || (
        activeState?.running ? null : Array.from(activePlanProgress.values())
            .reverse()
            .find(item => item.conversationId === String(activeConversationId || ''))
    );
    if (!planState) {
        root.hidden = true;
        closePlanProgress();
        return;
    }

    const completed = planState.plan.filter(
        item => ['completed', 'cancelled'].includes(item.status)
    ).length;
    const currentIndex = planState.plan.findIndex(item => item.status === 'in_progress');
    const pendingIndex = planState.plan.findIndex(item => item.status === 'pending');
    const displayIndex = currentIndex >= 0
        ? currentIndex
        : pendingIndex >= 0 ? pendingIndex : planState.plan.length - 1;
    const current = planState.plan[Math.max(0, displayIndex)];
    const isComplete = completed === planState.plan.length;
    const terminalState = String(planState.terminalState || '');
    const isFinished = ['complete', 'error', 'stopped'].includes(terminalState);
    const isFailure = Boolean(planState.error)
        || terminalState === 'error'
        || terminalState === 'stopped';
    const failureMessage = planState.terminalMessage
        || planState.error
        || (terminalState === 'stopped' ? '任务已停止' : '任务执行失败');
    const finishedMessage = planState.terminalMessage || '任务已结束';
    root.hidden = false;
    root.classList.toggle('is-complete', isComplete && !isFailure);
    root.classList.toggle('is-error', isFailure);
    root.classList.toggle('is-finished', isFinished);
    document.getElementById('planProgressCount').textContent = isFailure
        ? (terminalState === 'stopped' ? '计划已停止' : '计划异常')
        : `第 ${Math.max(1, displayIndex + 1)} / ${planState.plan.length} 步`;
    document.getElementById('planProgressCurrent').textContent = isFailure
        ? failureMessage
        : isComplete
            ? '任务计划已完成'
            : terminalState === 'complete'
                ? finishedMessage
                : current?.step || '等待开始';
    const explanation = document.getElementById('planProgressExplanation');
    explanation.textContent = planState.explanation;
    explanation.hidden = !planState.explanation;
    document.getElementById('planProgressList').innerHTML = planState.plan.map(item => `
        <li class="plan-progress-item is-${item.status}">
            <span class="plan-progress-item-state" aria-hidden="true"></span>
            <span>${escapeHtml(item.step)}</span>
        </li>`).join('');
}

function updatePlanProgress(result, conversationId, messageId) {
    if (result?.error) {
        const key = planProgressKey(conversationId, messageId);
        const previous = activePlanProgress.get(key);
        const normalized = previous
            ? {...previous, error: String(result.error || '计划更新失败')}
            : {
                conversationId: String(conversationId || ''),
                messageId: Number(messageId || 0),
                explanation: '',
                version: 0,
                error: String(result.error || '计划更新失败'),
                plan: [{step: '计划更新失败', status: 'pending'}],
            };
        activePlanProgress.set(key, normalized);
        if (normalized.conversationId === String(activeConversationId || '')) {
            renderPlanProgress(normalized);
        }
        return;
    }
    const normalized = normalizePlanProgress(result, conversationId, messageId);
    if (!normalized) return;
    activePlanProgress.set(
        planProgressKey(normalized.conversationId, normalized.messageId),
        normalized
    );
    if (normalized.conversationId === String(activeConversationId || '')) {
        renderPlanProgress(normalized);
    }
}

function clearConversationPlanProgress(conversationId) {
    const prefix = `${String(conversationId || '')}:`;
    Array.from(activePlanProgress.keys()).forEach(key => {
        if (key.startsWith(prefix)) activePlanProgress.delete(key);
    });
    if (String(conversationId || '') === String(activeConversationId || '')) {
        renderPlanProgress(null);
    }
}

function markPlanProgressTerminal(
    conversationId,
    messageId,
    terminalState,
    terminalMessage = ''
) {
    const normalizedState = String(terminalState || '').trim().toLowerCase();
    if (!['complete', 'error', 'stopped'].includes(normalizedState)) return;
    const key = planProgressKey(conversationId, messageId);
    const previous = activePlanProgress.get(key);
    if (!previous) return;
    if (normalizedState === 'complete'
        && ['error', 'stopped'].includes(previous.terminalState)) return;
    const finished = {
        ...previous,
        error: normalizedState === 'complete' ? '' : previous.error,
        terminalState: normalizedState,
        terminalMessage: String(terminalMessage || '').trim(),
    };
    activePlanProgress.set(key, finished);
    if (finished.conversationId === String(activeConversationId || '')) {
        renderPlanProgress(finished);
    }
}

function agentTeamKey(conversationId, messageId, teamId) {
    return `${String(conversationId || '')}:${Number(messageId || 0)}:${String(teamId || '')}`;
}

function boundedAgentPublicText(value, limit = 500) {
    return String(value || '')
        .replace(/<think\b[^>]*>[\s\S]*?<\/think>/gi, '')
        .replace(/<think\b[^>]*>[\s\S]*$/gi, '')
        .replace(/<\/?think\b[^>]*>/gi, '')
        .replace(/\u0000/g, '')
        .trim()
        .slice(0, Math.max(0, Number(limit || 0)));
}

function normalizeAgentStatus(value, fallback = 'queued') {
    const aliases = {
        pending: 'queued',
        in_progress: 'running',
        active: 'running',
        complete: 'completed',
        success: 'completed',
        error: 'failed',
        stopped: 'cancelled',
        canceled: 'cancelled',
        cancelling: 'waiting',
    };
    const status = String(value || '').trim().toLowerCase();
    const normalized = aliases[status] || status;
    return Object.prototype.hasOwnProperty.call(AGENT_STATUS_LABELS, normalized)
        ? normalized
        : fallback;
}

function normalizeAgentScope(scope, limit = 8) {
    const privateKeys = /(?:reason|analysis|chain|prompt|system|transcript|messages?|private_content)/i;
    const entries = [];
    const add = (value, prefix = '') => {
        if (entries.length >= limit) return;
        if (Array.isArray(value)) {
            value.slice(0, limit - entries.length).forEach(item => add(item, prefix));
            return;
        }
        if (value && typeof value === 'object') {
            Object.entries(value).slice(0, limit * 2).forEach(([key, item]) => {
                if (entries.length >= limit || privateKeys.test(key)) return;
                const label = boundedAgentPublicText(key.replace(/[_-]+/g, ' '), 40);
                add(item, label ? `${label}：` : prefix);
            });
            return;
        }
        const text = boundedAgentPublicText(value, 180);
        if (!text) return;
        entries.push(`${prefix}${text}`.slice(0, 220));
    };
    add(scope);
    return entries;
}

function normalizeAgentActivities(rawActivities) {
    if (!Array.isArray(rawActivities)) return [];
    const bySequence = new Map();
    rawActivities.slice(-(AGENT_ACTIVITY_MAX_ITEMS * 2)).forEach((raw, index) => {
        if (!raw || typeof raw !== 'object') return;
        const kind = String(raw.kind || 'progress').trim().toLowerCase();
        if (!AGENT_PUBLIC_ACTIVITY_KINDS.has(kind)) return;
        const fallbackSequence = index + 1;
        const numericSequence = Number(raw.seq ?? raw.sequence);
        const seq = Number.isFinite(numericSequence) && numericSequence >= 0
            ? numericSequence
            : fallbackSequence;
        const title = boundedAgentPublicText(raw.title, 120);
        const content = boundedAgentPublicText(raw.content, kind === 'stream' ? 20000 : 4000);
        const metadata = raw.metadata && typeof raw.metadata === 'object'
            ? raw.metadata
            : {};
        if (!title && !content) return;
        bySequence.set(seq, {
            seq,
            kind,
            title: title || '工作进展',
            content,
            createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
            metadata,
        });
    });
    return Array.from(bySequence.values())
        .sort((left, right) => left.seq - right.seq)
        .slice(-AGENT_ACTIVITY_MAX_ITEMS);
}

function normalizeAgentCollaboration(source, agentIds) {
    const knownAgentIds = new Set(agentIds);
    const normalizeReferences = values => (Array.isArray(values) ? values : [])
        .map(value => boundedAgentPublicText(value, 240))
        .filter(Boolean)
        .slice(0, 12);
    const artifacts = (Array.isArray(source.artifacts) ? source.artifacts : [])
        .slice(-40)
        .flatMap(raw => {
            if (!raw || typeof raw !== 'object') return [];
            const senderId = boundedAgentPublicText(raw.sender_id || raw.sender_agent_id, 80);
            const recipientIds = (Array.isArray(raw.recipient_ids)
                ? raw.recipient_ids
                : raw.recipient_agent_ids || [])
                .map(value => boundedAgentPublicText(value, 80))
                .filter(value => knownAgentIds.has(value));
            if (!knownAgentIds.has(senderId) && senderId !== 'primary') return [];
            return [{
                id: boundedAgentPublicText(raw.id, 96),
                seq: Number(raw.seq ?? raw.sequence) || 0,
                createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
                senderId,
                senderName: boundedAgentPublicText(raw.sender_name, 80),
                title: boundedAgentPublicText(raw.title, 160),
                content: boundedAgentPublicText(raw.summary, 4000),
                recipientIds,
                references: normalizeReferences(raw.paths),
            }];
        });
    const events = (Array.isArray(source.collaboration_events) ? source.collaboration_events : [])
        .slice(-120)
        .flatMap(raw => {
            if (!raw || typeof raw !== 'object') return [];
            const senderId = boundedAgentPublicText(raw.sender_id || raw.sender_agent_id, 80);
            const recipientId = boundedAgentPublicText(raw.recipient_id || raw.recipient_agent_id, 80);
            if (!knownAgentIds.has(senderId) && !knownAgentIds.has(recipientId)) return [];
            return [{
                seq: Number(raw.seq ?? raw.sequence) || 0,
                createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
                type: boundedAgentPublicText(raw.type, 32) || 'message',
                kind: boundedAgentPublicText(raw.kind, 32) || 'message',
                senderId,
                senderName: boundedAgentPublicText(raw.sender_name, 80),
                recipientId,
                recipientName: boundedAgentPublicText(raw.recipient_name, 80),
                title: boundedAgentPublicText(raw.title, 160),
                content: boundedAgentPublicText(raw.content, 4000),
                references: normalizeReferences(raw.references),
            }];
        });
    const fileClaims = (Array.isArray(source.file_claims) ? source.file_claims : [])
        .slice(0, 40)
        .flatMap(raw => {
            if (!raw || typeof raw !== 'object') return [];
            const agentId = boundedAgentPublicText(raw.agent_id, 80);
            if (!knownAgentIds.has(agentId)) return [];
            return [{
                agentId,
                agentName: boundedAgentPublicText(raw.agent_name, 80),
                paths: normalizeReferences(raw.paths),
                active: Boolean(raw.active),
            }];
        });
    return {artifacts, events, fileClaims};
}

function deriveAgentTeamStatus(agents, requestedStatus = '') {
    const requested = normalizeAgentStatus(requestedStatus, '');
    if (requested) return requested;
    if (agents.some(agent => agent.status === 'running')) return 'running';
    if (agents.some(agent => agent.status === 'waiting')) return 'waiting';
    if (agents.some(agent => agent.status === 'failed')) return 'failed';
    if (agents.length && agents.every(agent => AGENT_TERMINAL_STATUSES.has(agent.status))) {
        return agents.every(agent => agent.status === 'cancelled') ? 'cancelled' : 'completed';
    }
    return 'queued';
}

function normalizeAgentTeamSnapshot(
    raw,
    conversationId = activeConversationId,
    messageId = 0
) {
    const source = raw?.team && typeof raw.team === 'object' ? raw.team : raw;
    if (!source || !Array.isArray(source.agents)) return null;
    const normalizedConversationId = String(
        raw.conversation_id || conversationId || ''
    );
    const normalizedMessageId = Number(raw.message_id || messageId || 0);
    const teamId = boundedAgentPublicText(
        source.team_id || `team-${normalizedMessageId || 'current'}`,
        80
    );
    if (!normalizedConversationId || !normalizedMessageId || !teamId) return null;

    const agentIds = new Set();
    const agents = source.agents.slice(0, AGENT_TEAM_MAX_MEMBERS).flatMap((agent, index) => {
        if (!agent || typeof agent !== 'object') return [];
        const id = boundedAgentPublicText(
            agent.id || agent.agent_id || `agent-${index + 1}`,
            80
        );
        if (!id || agentIds.has(id)) return [];
        agentIds.add(id);
        const name = boundedAgentPublicText(agent.name, 48) || `子智能体 ${index + 1}`;
        return [{
            id,
            name,
            role: boundedAgentPublicText(agent.role, 120) || '协作任务执行',
            task: boundedAgentPublicText(agent.task, 1200) || '等待主智能体分配任务',
            status: normalizeAgentStatus(agent.status),
            currentActivity: boundedAgentPublicText(agent.current_activity, 600),
            summary: boundedAgentPublicText(agent.summary, 2000),
            result: boundedAgentPublicText(agent.result, 8000),
            error: boundedAgentPublicText(agent.error, 1600),
            startedAt: boundedAgentPublicText(agent.started_at, 80),
            endedAt: boundedAgentPublicText(agent.ended_at || agent.completed_at, 80),
            accessScope: normalizeAgentScope(
                agent.access_scope || (
                    agent.write_access
                        ? ['可写', ...(agent.write_paths || [])]
                        : '只读协作'
                )
            ),
            contextScope: normalizeAgentScope(agent.context_scope || agent.context),
            dependsOn: (Array.isArray(agent.depends_on) ? agent.depends_on : [])
                .map(value => boundedAgentPublicText(value, 80))
                .filter(Boolean)
                .slice(0, 12),
            activities: normalizeAgentActivities(agent.activities),
        }];
    });
    if (!agents.length) return null;

    const numericVersion = Number(source.version || 0);
    return {
        key: agentTeamKey(normalizedConversationId, normalizedMessageId, teamId),
        conversationId: normalizedConversationId,
        messageId: normalizedMessageId,
        teamId,
        version: Number.isFinite(numericVersion) ? Math.max(0, numericVersion) : 0,
        status: deriveAgentTeamStatus(agents, source.status),
        agents,
        collaboration: normalizeAgentCollaboration(source, Array.from(agentIds)),
        element: null,
        receivedAt: Date.now(),
    };
}

function getAgentTeamSnapshot(teamKey) {
    return activeAgentTeams.get(String(teamKey || '')) || null;
}

function pruneAgentTeamSnapshots() {
    if (activeAgentTeams.size <= AGENT_TEAM_MAX_SNAPSHOTS) return;
    for (const [key, snapshot] of activeAgentTeams) {
        if (activeAgentTeams.size <= AGENT_TEAM_MAX_SNAPSHOTS) break;
        const selected = activeAgentDetail?.teamKey === key;
        const visible = snapshot.element?.isConnected;
        if (!selected && !visible && AGENT_TERMINAL_STATUSES.has(snapshot.status)) {
            activeAgentTeams.delete(key);
        }
    }
}

function agentNetworkMarkMarkup() {
    return '<span class="agent-network-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>';
}

function getAgentTeamStatusCopy(snapshot) {
    const running = snapshot.agents.filter(agent => agent.status === 'running').length;
    const waiting = snapshot.agents.filter(agent => agent.status === 'waiting').length;
    const completed = snapshot.agents.filter(agent => agent.status === 'completed').length;
    if (running) return `${running} 个正在工作`;
    if (waiting) return `${waiting} 个等待协作`;
    if (completed === snapshot.agents.length) return '协作已完成';
    return AGENT_STATUS_LABELS[snapshot.status] || '等待开始';
}

function setAgentStatusClass(element, status) {
    Object.keys(AGENT_STATUS_LABELS).forEach(candidate => {
        element.classList.toggle(`is-${candidate}`, candidate === status);
    });
}

function createAgentChip() {
    const chip = document.createElement('button');
    chip.className = 'agent-chip';
    chip.type = 'button';
    chip.setAttribute('role', 'listitem');
    chip.setAttribute('aria-controls', 'agentDetailPanel');
    chip.innerHTML = `
        ${agentNetworkMarkMarkup()}
        <span class="agent-chip-copy"><strong></strong></span>
        <span class="agent-chip-status"><span aria-hidden="true"></span></span>`;
    return chip;
}

function updateAgentChip(chip, snapshot, agent, selected) {
    const statusLabel = AGENT_STATUS_LABELS[agent.status] || agent.status;
    const activity = agent.currentActivity || agent.task;
    const titleParts = [agent.role, activity].filter(Boolean);
    chip.dataset.agentTeamKey = snapshot.key;
    chip.dataset.agentId = agent.id;
    chip.classList.toggle('is-selected', selected);
    setAgentStatusClass(chip, agent.status);
    chip.setAttribute('aria-expanded', selected ? 'true' : 'false');
    chip.setAttribute(
        'aria-label',
        [agent.name, agent.role, statusLabel, activity].filter(Boolean).join('，')
    );
    chip.title = titleParts.join(' · ');
    chip.querySelector('.agent-chip-copy strong').textContent = agent.name;
    chip.querySelector('.agent-chip-status').setAttribute('aria-label', statusLabel);
}

function renderAgentTeamCard(snapshot, animate = true) {
    if (!snapshot || snapshot.conversationId !== String(activeConversationId || '')) {
        return null;
    }
    const chatMessages = getChatRenderHost();
    if (!chatMessages) return null;
    let card = snapshot.element?.isConnected ? snapshot.element : null;
    const isNew = !card;
    if (!card) {
        card = document.createElement('section');
        card.className = 'agent-team-card';
        card.dataset.teamKey = snapshot.key;
        card.dataset.teamId = snapshot.teamId;
        card.dataset.messageId = String(snapshot.messageId);
        const chipList = document.createElement('div');
        chipList.className = 'agent-chip-list';
        chipList.setAttribute('role', 'list');
        chipList.setAttribute('aria-label', '参与协作的子智能体');
        const status = document.createElement('span');
        status.className = 'agent-team-card-status';
        status.setAttribute('aria-live', 'polite');
        card.append(chipList, status);
        const thinking = chatMessages.querySelector('#thinking');
        if (thinking) chatMessages.insertBefore(card, thinking);
        else chatMessages.appendChild(card);
        snapshot.element = card;
    }
    setAgentStatusClass(card, snapshot.status);
    const selectedAgentId = activeAgentDetail?.teamKey === snapshot.key
        ? activeAgentDetail.agentId
        : '';
    const chipList = card.querySelector('.agent-chip-list');
    const existingChips = new Map(
        Array.from(chipList.querySelectorAll('.agent-chip[data-agent-id]'))
            .map(chip => [chip.dataset.agentId, chip])
    );
    const currentAgentIds = new Set(snapshot.agents.map(agent => agent.id));
    existingChips.forEach((chip, agentId) => {
        if (!currentAgentIds.has(agentId)) chip.remove();
    });
    snapshot.agents.forEach((agent, index) => {
        const chip = existingChips.get(agent.id) || createAgentChip();
        updateAgentChip(chip, snapshot, agent, selectedAgentId === agent.id);
        const currentAtIndex = chipList.children[index];
        if (currentAtIndex !== chip) {
            chipList.insertBefore(chip, currentAtIndex || null);
        }
    });
    card.querySelector('.agent-team-card-status').textContent = (
        getAgentTeamStatusCopy(snapshot)
    );
    if (isNew) {
        if (animate) requestAnimationFrame(() => card.classList.add('is-visible'));
        else card.classList.add('is-visible');
        if (!isRestoringConversation) followChatOutput(chatMessages);
    } else {
        card.classList.add('is-visible');
    }
    return card;
}

function updateAgentTeamSnapshot(
    raw,
    conversationId = activeConversationId,
    messageId = 0,
    {animate = true} = {}
) {
    const normalized = normalizeAgentTeamSnapshot(raw, conversationId, messageId);
    if (!normalized) return null;
    const previous = activeAgentTeams.get(normalized.key);
    if (previous && normalized.version <= previous.version) {
        if (
            previous.conversationId === String(activeConversationId || '')
            && !previous.element?.isConnected
        ) {
            renderAgentTeamCard(previous, false);
        }
        return previous;
    }
    normalized.element = previous?.element || null;
    activeAgentTeams.set(normalized.key, normalized);
    pruneAgentTeamSnapshots();
    renderAgentTeamCard(normalized, animate);
    if (activeAgentDetail?.teamKey === normalized.key) {
        if (normalized.agents.some(agent => agent.id === activeAgentDetail.agentId)) {
            renderAgentDetail(normalized, activeAgentDetail.agentId);
        } else {
            closeAgentDetail({restoreFocus: false});
        }
    }
    return normalized;
}

function detachAgentTeamCardsForConversation(conversationId) {
    const id = String(conversationId || '');
    activeAgentTeams.forEach(snapshot => {
        if (snapshot.conversationId === id) snapshot.element = null;
    });
}

function clearConversationAgentTeams(conversationId) {
    const id = String(conversationId || '');
    for (const [key, snapshot] of activeAgentTeams) {
        if (snapshot.conversationId === id) activeAgentTeams.delete(key);
    }
    if (activeAgentDetail) {
        const selected = getAgentTeamSnapshot(activeAgentDetail.teamKey);
        if (!selected || selected.conversationId === id) {
            closeAgentDetail({restoreFocus: false});
        }
    }
}

function formatAgentActivityTime(value) {
    const source = String(value || '').trim();
    if (!source) return '';
    const date = new Date(source);
    if (Number.isNaN(date.getTime())) return boundedAgentPublicText(source, 24);
    return date.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
}

function createAgentOutputMessage(host, content, {commentary = false, error = false} = {}) {
    const message = document.createElement('div');
    message.className = `message ai${error ? ' error' : ''}`;
    message.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-wrapper">
            <div class="message-bubble">${renderMarkdown(content)}</div>
        </div>`;
    if (commentary) decorateCommentaryMessage(message);
    host.appendChild(message);
    message.classList.add('is-visible');
    return message;
}

function createAgentStreamState(host, streamId) {
    return {
        host,
        element: null,
        bubble: null,
        thinkingCard: null,
        thinkingBody: null,
        content: '',
        streamId,
        thinkingCondensed: false,
        thinkingStartedAt: Date.now(),
        thinkingDurationMs: null,
        thinkingTimer: null,
        thinkingClosed: false,
        isCommentary: false,
        thinkingDetectionComplete: false,
        voiceDisabled: true,
    };
}

function finalizeAgentStream(state, target, durationMs = null) {
    const content = state.content || '';
    if (target === 'discard') {
        state.element?.remove();
        state.thinkingCard?.remove();
        return;
    }
    const {thoughts, answer} = splitThinkingContent(content);
    if (target === 'thinking') {
        state.element?.remove();
        const thought = thoughts[thoughts.length - 1] || answer || content;
        if (state.thinkingCard) {
            state.thinkingBody.innerHTML = renderMarkdown(thought);
            state.thinkingDurationMs = durationMs;
            completeStreamingThinking(state);
            condenseThinkingCard(state.thinkingCard, true);
        } else if (thought.trim()) {
            addThinkingCard(thought, null, false, false, true, durationMs, state.host);
        }
        return;
    }
    if (state.thinkingCard) {
        const thought = thoughts[thoughts.length - 1] || '';
        if (thought) state.thinkingBody.innerHTML = renderMarkdown(thought);
        state.thinkingDurationMs = durationMs;
        completeStreamingThinking(state);
        condenseThinkingCard(state.thinkingCard, true);
    }
    const visible = answer.trim() || (thoughts.length ? '' : content.trim());
    if (!state.element && visible) createStreamingResponse(state.streamId, state);
    if (state.element) {
        state.element.classList.remove('streaming-response');
        state.bubble.innerHTML = visible ? renderMarkdown(visible) : '';
        if (target === 'commentary') decorateCommentaryMessage(state.element);
    }
}

function renderAgentStream(outputState, activity) {
    const metadata = activity.metadata || {};
    const streamId = String(metadata.stream_id || `activity-${activity.seq}`);
    let state = outputState.streams.get(streamId);
    if (!state) {
        state = createAgentStreamState(outputState.host, streamId);
        outputState.streams.set(streamId, state);
    }
    state.content = activity.content;
    state.thinkingDurationMs = Number.isFinite(Number(metadata.thinking_duration_ms))
        ? Number(metadata.thinking_duration_ms)
        : state.thinkingDurationMs;
    state.thinkingClosed = metadata.phase === 'end';
    renderStreamingState(state);
    if (metadata.phase === 'end') {
        finalizeAgentStream(state, String(metadata.target || 'final'), state.thinkingDurationMs);
    }
}

function renderAgentTool(outputState, activity) {
    const metadata = activity.metadata || {};
    const key = String(metadata.prepared_tool_call_id || metadata.tool_call_id || activity.seq);
    const phase = String(metadata.phase || 'end');
    let execution = outputState.tools.get(key);
    const event = {
        tool: String(metadata.tool || activity.title || 'Tool'),
        params: metadata.params || {},
        target: String(metadata.target || ''),
        result: String(metadata.result || activity.content || ''),
        duration_ms: Number(metadata.duration_ms || 0),
    };
    if (phase !== 'end') {
        if (!execution) {
            const element = document.createElement('div');
            element.className = 'tool-execution tool-execution-running';
            element.innerHTML = `
                <div class="tool-card tool-card-running" role="status" aria-live="polite">
                    <div class="tool-header tool-header-running">
                        <span class="tool-progress-spinner" aria-hidden="true"><span></span></span>
                        <span class="tool-name"></span>
                        <span class="tool-summary tool-live-summary"></span>
                        <span class="tool-elapsed">进行中</span>
                    </div>
                    <div class="tool-progress-track" aria-hidden="true"><span></span></div>
                </div>`;
            outputState.host.appendChild(element);
            element.classList.add('is-visible');
            execution = {element, event};
            outputState.tools.set(key, execution);
        }
        execution.event = event;
        execution.element.querySelector('.tool-name').textContent = event.tool;
        execution.element.querySelector('.tool-live-summary').textContent = primaryToolSummary(
            phase === 'preparing' ? getToolPreparingCopy(event.tool) : getToolProgressCopy(event.tool, event.params),
            getToolTarget(event.tool, event.params, event.target)
        );
        return;
    }
    const failed = Boolean(metadata.failed) || toolResultFailed(event.result);
    const target = getToolTarget(event.tool, event.params, event.target);
    const element = execution?.element || document.createElement('div');
    element.classList.remove(
        'tool-execution-running',
        'tool-execution-error',
        'tool-execution-complete'
    );
    element.classList.add(
        'tool-execution',
        failed ? 'tool-execution-error' : 'tool-execution-complete'
    );
    element.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(event.tool)}</span>
                <span class="tool-summary">${escapeHtml(primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'}${event.duration_ms > 0 ? ` · ${formatToolDuration(event.duration_ms)}` : ''}`,
                    target
                ))}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(event.result || ''))}</div>
        </details>`;
    if (!execution) {
        outputState.host.appendChild(element);
        element.classList.add('is-visible');
    }
    outputState.tools.set(key, {element, event});
}

function updateAgentActivityList(activityList, snapshot, agent) {
    const owner = `${snapshot.key}:${agent.id}`;
    if (activityList.dataset.agentOwner !== owner) {
        activityList.replaceChildren();
        activityList.dataset.agentOwner = owner;
        activityList._agentOutputState = {
            host: activityList,
            streams: new Map(),
            tools: new Map(),
            signatures: new Map(),
        };
    }
    const outputState = activityList._agentOutputState;
    if (!agent.activities.length) {
        if (!activityList.querySelector('.agent-activity-empty')) {
            const empty = document.createElement('p');
            empty.className = 'agent-activity-empty';
            empty.textContent = '等待子智能体开始输出';
            activityList.replaceChildren(empty);
        }
        return false;
    }

    activityList.querySelector('.agent-activity-empty')?.remove();
    let changed = false;
    agent.activities.forEach(activity => {
        const seq = String(activity.seq);
        const signature = JSON.stringify([
            activity.kind,
            activity.title,
            activity.content,
            activity.createdAt,
            activity.metadata,
        ]);
        if (outputState.signatures.get(seq) === signature) return;
        outputState.signatures.set(seq, signature);
        if (activity.kind === 'stream') renderAgentStream(outputState, activity);
        else if (activity.kind === 'tool_event') renderAgentTool(outputState, activity);
        else if (activity.kind === 'error') {
            createAgentOutputMessage(activityList, activity.content, {error: true});
        } else if (activity.content) {
            createAgentOutputMessage(activityList, activity.content, {commentary: true});
        }
        changed = true;
    });
    const hasFinalStream = agent.activities.some(activity => (
        activity.kind === 'stream'
        && activity.metadata?.phase === 'end'
        && ['final', 'commentary'].includes(String(activity.metadata?.target || ''))
    ));
    if (agent.result && !hasFinalStream) {
        const resultSignature = `result:${agent.result}`;
        if (outputState.signatures.get('__result__') !== resultSignature) {
            outputState.signatures.set('__result__', resultSignature);
            createAgentOutputMessage(activityList, agent.result);
            changed = true;
        }
    }
    return changed;
}

function syncSelectedAgentChip() {
    document.querySelectorAll('.agent-chip[data-agent-team-key][data-agent-id]').forEach(chip => {
        const selected = Boolean(
            activeAgentDetail
            && chip.dataset.agentTeamKey === activeAgentDetail.teamKey
            && chip.dataset.agentId === activeAgentDetail.agentId
        );
        chip.classList.toggle('is-selected', selected);
        chip.setAttribute('aria-expanded', selected ? 'true' : 'false');
    });
}

function renderAgentCollaboration(snapshot, agent) {
    const list = document.getElementById('agentCollaborationList');
    const count = document.getElementById('agentCollaborationCount');
    if (!list || !count) return false;
    const collaboration = snapshot.collaboration || {artifacts: [], events: [], fileClaims: []};
    const entries = [
        ...collaboration.events
            .filter(event => event.senderId === agent.id || event.recipientId === agent.id)
            .map(event => ({...event, entryType: 'message'})),
        ...collaboration.artifacts
            .filter(artifact => artifact.senderId === agent.id || artifact.recipientIds.includes(agent.id))
            .map(artifact => ({...artifact, entryType: 'artifact'})),
    ].sort((left, right) => (left.seq || 0) - (right.seq || 0)).slice(-24);
    const ownClaim = collaboration.fileClaims.find(claim => claim.agentId === agent.id);
    const signature = JSON.stringify({entries, claim: ownClaim || null, dependsOn: agent.dependsOn});
    count.textContent = `${entries.length + (ownClaim ? 1 : 0)} 项`;
    if (list.dataset.renderSignature === signature) return false;
    list.replaceChildren();
    if (agent.dependsOn.length) {
        const dependency = document.createElement('div');
        dependency.className = 'agent-collaboration-item is-dependency';
        dependency.innerHTML = '<strong>等待依赖</strong>';
        const copy = document.createElement('p');
        copy.textContent = agent.dependsOn.join('、');
        dependency.append(copy);
        list.appendChild(dependency);
    }
    if (ownClaim?.paths.length) {
        const claim = document.createElement('div');
        claim.className = 'agent-collaboration-item is-claim';
        claim.innerHTML = `<strong>${ownClaim.active ? '已占用文件范围' : '已释放文件范围'}</strong>`;
        const copy = document.createElement('p');
        copy.textContent = ownClaim.paths.join('、');
        claim.append(copy);
        list.appendChild(claim);
    }
    entries.forEach(entry => {
        const item = document.createElement('div');
        item.className = `agent-collaboration-item is-${entry.entryType}`;
        const isArtifact = entry.entryType === 'artifact';
        const direction = isArtifact
            ? `${entry.senderName || '协作成员'} 发布工件`
            : entry.senderId === agent.id
                ? `发送给 ${entry.recipientName || '协作成员'}`
                : `${entry.senderName || '协作成员'} 发来${entry.kind === 'handoff' ? '交接' : '消息'}`;
        const heading = document.createElement('strong');
        heading.textContent = isArtifact ? (entry.title || '共享工件') : direction;
        const content = document.createElement('p');
        content.textContent = entry.content || entry.title || '协作更新';
        item.append(heading, content);
        if (entry.references?.length) {
            const references = document.createElement('span');
            references.textContent = entry.references.join('、');
            item.append(references);
        }
        list.appendChild(item);
    });
    if (!list.childElementCount) {
        const empty = document.createElement('p');
        empty.className = 'agent-activity-empty';
        empty.textContent = '暂无定向消息、交接或共享工件';
        list.appendChild(empty);
    }
    list.dataset.renderSignature = signature;
    return true;
}

function renderAgentDetail(snapshot, agentId) {
    const agent = snapshot?.agents.find(item => item.id === String(agentId || ''));
    if (!snapshot || !agent) return false;
    const scroll = document.getElementById('agentDetailScroll');
    const previousScrollTop = Number(scroll?.scrollTop || 0);
    const distanceFromBottom = scroll
        ? scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight
        : 0;
    const status = document.getElementById('agentDetailStatus');
    status.textContent = AGENT_STATUS_LABELS[agent.status] || agent.status;
    status.className = `agent-detail-status is-${agent.status}`;
    document.getElementById('agentDetailAccess').textContent = (
        agent.accessScope[0] || '隔离上下文'
    );
    document.getElementById('agentDetailPanelTitle').textContent = agent.name;
    document.getElementById('agentDetailName').textContent = agent.name;
    document.getElementById('agentDetailRole').textContent = agent.currentActivity
        ? `${agent.role} · ${agent.currentActivity}`
        : agent.role;
    document.getElementById('agentDetailTask').textContent = agent.task;

    const contextScope = document.getElementById('agentDetailContextScope');
    const scopeItems = [
        ...(agent.contextScope.length
            ? agent.contextScope.map(item => ({label: '可见上下文', value: item}))
            : [{label: '可见上下文', value: '主智能体分配说明与必要项目资料'}]),
        ...(agent.accessScope.length
            ? agent.accessScope.map(item => ({label: '工具范围', value: item}))
            : [{label: '工具范围', value: '仅使用本任务明确授权的能力'}]),
        ...(agent.dependsOn.length
            ? [{label: '任务依赖', value: agent.dependsOn.join('、')}]
            : []),
        {label: '隔离规则', value: '不共享主对话历史与兄弟智能体工作记忆'},
    ].slice(0, 12);
    const contextSignature = JSON.stringify(scopeItems);
    if (contextScope.dataset.renderSignature !== contextSignature) {
        contextScope.replaceChildren(...scopeItems.map(scopeItem => {
            const item = document.createElement('div');
            item.className = 'agent-context-item';
            const label = document.createElement('span');
            label.textContent = scopeItem.label;
            const value = document.createElement('strong');
            value.textContent = scopeItem.value;
            item.append(label, value);
            return item;
        }));
        contextScope.dataset.renderSignature = contextSignature;
    }

    const activityList = document.getElementById('agentActivityList');
    const collaborationChanged = renderAgentCollaboration(snapshot, agent);
    document.getElementById('agentDetailActivityCount').textContent = `${agent.activities.length} 条`;
    const activityChanged = updateAgentActivityList(activityList, snapshot, agent);

    const resultSection = document.getElementById('agentResultSection');
    resultSection.hidden = true;
    const resultChanged = false;
    const errorSection = document.getElementById('agentErrorSection');
    errorSection.hidden = true;

    if (scroll && (activityChanged || collaborationChanged || resultChanged)) {
        if (agentDetailScrollFrame) cancelAnimationFrame(agentDetailScrollFrame);
        agentDetailScrollFrame = requestAnimationFrame(() => {
            agentDetailScrollFrame = 0;
            if (distanceFromBottom < 48) scroll.scrollTop = scroll.scrollHeight;
            else scroll.scrollTop = previousScrollTop;
        });
    }
    return true;
}

function openAgentDetail(teamKey, agentId, trigger = null) {
    const snapshot = getAgentTeamSnapshot(teamKey);
    if (!snapshot || !snapshot.agents.some(agent => agent.id === String(agentId || ''))) {
        return;
    }
    closeChangeReview({restoreFocus: false});
    const panel = document.getElementById('agentDetailPanel');
    if (!panel) return;
    const chatMessages = document.getElementById('chatMessages');
    const distanceFromBottom = chatMessages
        ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        : 0;
    const previousFocus = activeAgentDetail?.lastFocus;
    activeAgentDetail = {
        teamKey: snapshot.key,
        agentId: String(agentId),
        lastFocus: previousFocus?.isConnected ? previousFocus : trigger || document.activeElement,
    };
    renderAgentDetail(snapshot, agentId);
    syncSelectedAgentChip();
    panel.removeAttribute('aria-hidden');
    document.body.classList.add('agent-detail-open');
    notifyParentAgentDetail(true);
    setSidebarPanelWidth(getSavedSidebarPanelWidth(), {persist: false});
    setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), {persist: false});
    requestAnimationFrame(() => panel.classList.add('is-open'));
    restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
}

function closeAgentDetail({restoreFocus = true} = {}) {
    const panel = document.getElementById('agentDetailPanel');
    const chatMessages = document.getElementById('chatMessages');
    const distanceFromBottom = chatMessages
        ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        : 0;
    const focusTarget = activeAgentDetail?.lastFocus;
    if (agentDetailScrollFrame) cancelAnimationFrame(agentDetailScrollFrame);
    agentDetailScrollFrame = 0;
    panel?.classList.remove('is-open');
    panel?.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('agent-detail-open');
    notifyParentAgentDetail(false);
    activeAgentDetail = null;
    syncSelectedAgentChip();
    setSidebarPanelWidth(getSavedSidebarPanelWidth(), {persist: false});
    restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
    if (restoreFocus && focusTarget?.isConnected) focusTarget.focus({preventScroll: true});
}

function handleAgentTeamClick(event) {
    const chip = event.target.closest('.agent-chip[data-agent-team-key][data-agent-id]');
    if (!chip) return false;
    openAgentDetail(chip.dataset.agentTeamKey, chip.dataset.agentId, chip);
    return true;
}

function markAgentTeamsTerminal(conversationId, messageId, status) {
    const normalizedStatus = normalizeAgentStatus(status, 'cancelled');
    if (!AGENT_TERMINAL_STATUSES.has(normalizedStatus)) return;
    const id = String(conversationId || '');
    const targetMessageId = Number(messageId || 0);
    activeAgentTeams.forEach(snapshot => {
        if (snapshot.conversationId !== id || snapshot.messageId !== targetMessageId) return;
        snapshot.status = normalizedStatus;
        snapshot.agents = snapshot.agents.map(agent => (
            AGENT_TERMINAL_STATUSES.has(agent.status)
                ? agent
                : {
                    ...agent,
                    status: normalizedStatus,
                    currentActivity: normalizedStatus === 'failed' ? '协作已中断' : '任务已停止',
                }
        ));
        renderAgentTeamCard(snapshot, false);
        if (activeAgentDetail?.teamKey === snapshot.key) {
            renderAgentDetail(snapshot, activeAgentDetail.agentId);
        }
    });
}

function getExecutionStateText(state) {
    if (!state) return '正在执行';
    if (state.awaitingQuestion) return '等待回答';
    if (state.awaitingApproval) return '等待确认';
    if (state.stopping) return '正在停止';
    return '正在执行';
}

function hasVisibleLiveActivity() {
    return Boolean(
        document.getElementById('thinking')
        || document.querySelector('.streaming-response')
        || document.querySelector('.tool-execution-running')
        || document.querySelector('.compression-activity.is-running')
        || document.querySelector('.approval-container')
        || document.querySelector('.question-prompt:not(.is-submitted)')
    );
}

function restoreTrackedExecutionActivity(state) {
    if (!state || state.outputStopped) return false;
    let restored = false;
    state.streamContents.forEach((content, streamId) => {
        if (!content) return;
        const existing = streamingResponses.get(String(streamId));
        if (existing) {
            cancelStreamingRender(existing);
            stopStreamingThinkingTimer(existing);
            existing.element?.remove();
            existing.thinkingCard?.remove();
            streamingResponses.delete(String(streamId));
        }
        appendStreamingResponse(
            streamId, content, state.thinkingStartByStream?.get(streamId) || 0
        );
        restored = true;
    });
    if (state.activeToolEvent) {
        startToolExecution(
            state.activeToolEvent,
            state.messageId,
            state.activeToolEvent.type === 'tool_preparing'
        );
        restored = true;
    }
    if (state.activeCompressionEvent) {
        startCompressionActivity(state.activeCompressionEvent, state.messageId);
        restored = true;
    }
    return restored;
}

function resetTrackedExecutionActivity(state) {
    if (!state) return;
    state.streamContents.clear();
    state.thinkingStartByStream?.clear();
    state.activeToolEvent = null;
    state.activeCompressionEvent = null;
}

function trackExecutionResult(state, result) {
    if (!state || !result) return;
    const streamId = String(result.stream_id || state.messageId || '');
    if (result.type === 'stream' && streamId) {
        state.streamContents.set(
            streamId,
            `${state.streamContents.get(streamId) || ''}${String(result.content || '')}`
        );
    } else if (result.type === 'stream_end' && streamId) {
        state.streamContents.delete(streamId);
        state.thinkingStartByStream?.delete(streamId);
    } else if (result.type === 'tool_preparing' || result.type === 'tool_start') {
        state.activeToolEvent = {...result};
    } else if (result.type === 'tool') {
        state.activeToolEvent = null;
    } else if (result.type === 'compression_start') {
        state.activeCompressionEvent = {...result};
    } else if (result.type === 'compression_progress') {
        state.activeCompressionEvent = {
            ...(state.activeCompressionEvent || {}),
            ...result,
        };
    } else if (result.type === 'compression_end') {
        state.activeCompressionEvent = null;
    } else if (result.type === 'pending_question') {
        state.awaitingQuestion = true;
        state.awaitingApproval = false;
        state.activeToolEvent = null;
    } else if (result.type === 'pending_approval') {
        state.awaitingApproval = true;
        state.awaitingQuestion = false;
        state.activeToolEvent = null;
    } else if (result.type === 'question_answered') {
        state.awaitingQuestion = false;
    }
}

function normalizeToolActor(result) {
    return String(result?.actor || 'primary').trim().toLowerCase() || 'primary';
}

function isPrimaryToolEvent(result) {
    return normalizeToolActor(result) === 'primary';
}

function primaryToolSummary(copy, target = '') {
    return [copy, target].filter(Boolean).join(' · ');
}

function isQuestionToolName(toolName) {
    return QUESTION_TOOL_NAMES.has(String(toolName || '').trim().toLowerCase());
}

function syncActiveConversationProcessingUI({showPlaceholder = false} = {}) {
    const state = getActiveExecutionState();
    const visibleRunning = Boolean(state?.running && !state.outputStopped);
    isAwaitingQuestion = Boolean(visibleRunning && state.awaitingQuestion);

    if (visibleRunning) {
        currentMessageId = Number(state.messageId || currentMessageId || 0);
        updateProcessingUI(true, getExecutionStateText(state));
        if (showPlaceholder
            && !state.awaitingQuestion
            && !state.awaitingApproval
            && !hasVisibleLiveActivity()) {
            if (!restoreTrackedExecutionActivity(state)) showThinking();
        }
    } else {
        updateProcessingUI(false);
        if (hasRunningExecution()) setAppStatus('ready', '后台任务运行中');
    }
}

function syncExecutionStatesFromConversations(items) {
    const knownIds = new Set();
    for (const item of items || []) {
        const conversationId = String(item.id || '');
        if (!conversationId) continue;
        knownIds.add(conversationId);
        const state = getConversationExecutionState(conversationId);
        const backendRunning = Boolean(item.running);
        const backendMessageId = Number(item.active_message_id || item.message_id || 0);
        state.unreadCompletion = Boolean(item.unread_completion);
        if (backendRunning) {
            if (
                backendMessageId
                && backendMessageId <= Number(state.terminalMessageId || 0)
            ) {
                continue;
            }
            updateConversationExecutionState(conversationId, {
                messageId: backendMessageId || state.messageId,
                running: true,
                stopping: Boolean(item.stopping),
                awaitingQuestion: Boolean(item.awaiting_question),
                awaitingApproval: Boolean(item.awaiting_approval),
            });
        } else if (state.running) {
            updateConversationExecutionState(conversationId, {
                messageId: state.messageId,
                running: false,
                stopping: false,
                outputStopped: false,
                awaitingQuestion: false,
                awaitingApproval: false,
            });
        }
    }
    for (const conversationId of conversationExecutionStates.keys()) {
        if (!knownIds.has(conversationId)) {
            invalidatePolling(conversationId);
            conversationExecutionStates.delete(conversationId);
        }
    }
}

function markConversationReadLocally(conversationId) {
    const id = String(conversationId || '');
    const state = getConversationExecutionState(id, false);
    if (state) state.unreadCompletion = false;
    const item = conversations.find(entry => String(entry.id) === id);
    if (item) item.unread_completion = false;
}

function updateConversationListItemState(conversationId, updates = {}) {
    const id = String(conversationId || '');
    const item = conversations.find(entry => String(entry.id) === id);
    if (!item) return false;
    let changed = false;
    Object.entries(updates).forEach(([key, value]) => {
        if (item[key] !== value) {
            item[key] = value;
            changed = true;
        }
    });
    return changed;
}

function clearMessageQueue(conversationId = '') {
    const targetId = String(conversationId || activeConversationId || '');
    messageQueue = messageQueue.filter(item => {
        const itemId = typeof item === 'object'
            ? String(item.conversationId || '')
            : targetId;
        return itemId !== targetId;
    });
    updateQueueDisplay();
}

function queuedCountForConversation(conversationId) {
    const targetId = String(conversationId || activeConversationId || '');
    return messageQueue.filter(item => {
        const itemId = typeof item === 'object'
            ? String(item.conversationId || '')
            : targetId;
        return itemId === targetId;
    }).length;
}

async function addComposerAttachments(files) {
    if (!files.length) return;
    const existingBytes = composerAttachments.reduce((sum, item) => sum + item.size, 0);
    const availableSlots = ATTACHMENT_LIMITS.count - composerAttachments.length;
    if (availableSlots <= 0) {
        showToast(`最多添加 ${ATTACHMENT_LIMITS.count} 个文件`, 'error');
        return;
    }

    const accepted = [];
    let totalBytes = existingBytes;
    for (const file of files.slice(0, availableSlots)) {
        const normalizedFile = normalizeImageFile(file);
        if (!normalizedFile) {
            showToast(`${file.name || '图片'} 格式不支持，仅支持 PNG、JPEG、WebP`, 'error');
            continue;
        }
        if (normalizedFile.size > ATTACHMENT_LIMITS.bytesPerFile) {
            showToast(`${normalizedFile.name} 超过 12 MB，已跳过`, 'error');
            continue;
        }
        if (totalBytes + normalizedFile.size > ATTACHMENT_LIMITS.totalBytes) {
            showToast('附件总大小不能超过 30 MB', 'error');
            break;
        }
        try {
            const data = await readFileAsDataUrl(normalizedFile);
            accepted.push({
                id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                name: normalizedFile.name,
                size: normalizedFile.size,
                type: normalizedFile.type || '',
                data,
                status: 'ready',
            });
            totalBytes += normalizedFile.size;
        } catch (error) {
            showToast(`${normalizedFile.name} 读取失败`, 'error');
        }
    }

    composerAttachments.push(...accepted);
    renderComposerAttachments();
    updateComposerSendState();
}

function getAttachmentMimeType(file) {
    return String(file?.type || '').split(';', 1)[0].trim().toLowerCase();
}

function isImageAttachment(item) {
    const type = getAttachmentMimeType(item);
    if (SUPPORTED_IMAGE_TYPES.has(type)) return true;
    return /\.(?:png|jpe?g|webp)$/i.test(String(item?.name || ''));
}

function isDirectoryReference(item) {
    return item?.kind === 'directory_reference'
        || item?.parse_mode === 'directory_reference';
}

function getImageMimeFromName(name) {
    const extension = String(name || '').split('.').pop().toLowerCase();
    if (extension === 'png') return 'image/png';
    if (extension === 'jpg' || extension === 'jpeg') return 'image/jpeg';
    if (extension === 'webp') return 'image/webp';
    return '';
}

function normalizeImageFile(file) {
    if (!file) return null;
    const type = getAttachmentMimeType(file);
    if (!type || !type.startsWith('image/')) {
        return /\.(?:png|jpe?g|webp)$/i.test(String(file.name || ''))
            ? new File([file], file.name, {
                type: getImageMimeFromName(file.name),
                lastModified: file.lastModified || Date.now(),
            })
            : file;
    }
    const resolvedType = SUPPORTED_IMAGE_TYPES.has(type)
        ? type
        : getImageMimeFromName(file.name);
    if (!SUPPORTED_IMAGE_TYPES.has(resolvedType)) return null;
    const hasUsefulName = String(file.name || '').includes('.');
    if (hasUsefulName && type === resolvedType) return file;
    const extension = resolvedType === 'image/jpeg' ? 'jpg' : resolvedType.split('/')[1];
    const name = hasUsefulName
        ? file.name
        : `粘贴图片-${Date.now()}.${extension}`;
    return new File([file], name, {
        type: resolvedType,
        lastModified: file.lastModified || Date.now(),
    });
}

function getImagePreview(item) {
    const data = String(item?.data || '');
    return isImageAttachment(item) && /^data:image\/(?:png|jpeg|webp);base64,/i.test(data)
        ? data
        : '';
}

function renderAttachmentVisual(item, className) {
    if (isDirectoryReference(item)) {
        return `
            <span class="${className} is-directory" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                </svg>
            </span>`;
    }
    const preview = getImagePreview(item);
    if (preview) {
        return `<span class="${className} is-image" aria-hidden="true"><img src="${escapeHtml(preview)}" alt=""></span>`;
    }
    if (
        isImageAttachment(item)
        || item?.parse_mode === 'vision'
        || item?.parse_mode === 'image_view'
    ) {
        return `
            <span class="${className} is-image-placeholder" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                    <rect x="3.5" y="4" width="17" height="16" rx="3"></rect>
                    <circle cx="9" cy="9.5" r="1.5"></circle>
                    <path d="m5.5 17 4.2-4.2 3.1 3.1 2.2-2.2 3.5 3.3"></path>
                </svg>
            </span>`;
    }
    return `<span class="${className}" aria-hidden="true">${escapeHtml(getAttachmentExtension(item.name))}</span>`;
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(reader.error || new Error('File read failed'));
        reader.readAsDataURL(file);
    });
}

function renderComposerAttachments() {
    const container = document.getElementById('composerAttachments');
    if (!container) return;
    container.classList.toggle('is-visible', composerAttachments.length > 0);
    container.innerHTML = composerAttachments.map(item => {
        const previewable = isImageAttachment(item) && Boolean(getImagePreview(item));
        const previewAttributes = previewable
            ? ` data-image-attachment="true" role="button" tabindex="0" aria-label="预览图片 ${escapeHtml(item.name)}"`
            : '';
        return `
        <div class="composer-attachment ${item.status === 'error' ? 'has-error' : ''}" data-attachment-name="${escapeHtml(item.name)}"${previewAttributes}>
            ${renderAttachmentVisual(item, 'composer-attachment-icon')}
            <span class="composer-attachment-copy">
                <strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong>
                <small>${item.status === 'parsing' ? '正在解析' : item.status === 'error' ? escapeHtml(item.error || '解析失败') : isDirectoryReference(item) ? escapeHtml(item.path || '参考文件夹') : isImageAttachment(item) ? `等待保存图片 · ${formatAttachmentSize(item.size)}` : formatAttachmentSize(item.size)}</small>
            </span>
            <button type="button" class="composer-attachment-remove" onclick="removeComposerAttachment('${item.id}')" aria-label="移除 ${escapeHtml(item.name)}">×</button>
        </div>
    `;
    }).join('');
}

function removeComposerAttachment(id) {
    composerAttachments = composerAttachments.filter(item => item.id !== id);
    renderComposerAttachments();
    updateComposerSendState();
}

function clearComposerAttachments() {
    composerAttachments = [];
    renderComposerAttachments();
    updateComposerSendState();
}

function updateComposerSendState() {
    const input = document.getElementById('messageInput');
    const button = document.getElementById('sendButton');
    if (input && button) button.disabled = !input.value.trim() && composerAttachments.length === 0;
}

function getAttachmentExtension(name) {
    const extension = String(name || '').split('.').pop();
    return extension && extension !== name ? extension.slice(0, 4).toUpperCase() : 'FILE';
}

function formatAttachmentSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function buildAttachmentPayload(attachments) {
    return attachments.map(item => ({
        name: item.name,
        size: item.size,
        type: item.type,
        data: item.data,
        path: item.path || '',
        kind: item.kind || '',
    }));
}

function getClipboardImages(clipboardData) {
    const items = Array.from(clipboardData?.items || []);
    const itemFiles = items
        .filter(item => item.kind === 'file' && getAttachmentMimeType(item).startsWith('image/'))
        .map(item => item.getAsFile())
        .filter(Boolean);
    if (itemFiles.length) return itemFiles;
    return Array.from(clipboardData?.files || [])
        .filter(file => getAttachmentMimeType(file).startsWith('image/'));
}

function getDroppedFiles(dataTransfer) {
    return Array.from(dataTransfer?.files || []);
}

function getDroppedDirectoryEntries(dataTransfer) {
    return Array.from(dataTransfer?.items || [])
        .filter(item => item.kind === 'file')
        .map(item => item.webkitGetAsEntry?.())
        .filter(entry => entry?.isDirectory);
}

function getDroppedFilePath(file) {
    return String(file?.path || file?.webkitRelativePath || '').trim();
}

function getPathBaseName(path) {
    return String(path || '').replace(/[\\/]+$/, '').split(/[\\/]/).pop() || '';
}

function normalizeDirectoryReference(path, fallbackName = '') {
    const normalizedPath = String(path || '').trim().replace(/[\\/]+$/, '');
    if (!normalizedPath) return null;
    const name = normalizedPath.split(/[\\/]/).filter(Boolean).pop()
        || String(fallbackName || '参考文件夹');
    return {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        name,
        size: 0,
        type: 'inode/directory',
        data: '',
        path: normalizedPath,
        kind: 'directory_reference',
        status: 'ready',
    };
}

function addComposerDirectoryReferences(paths, fallbackNames = []) {
    const existingPaths = new Set(
        composerAttachments
            .filter(isDirectoryReference)
            .map(item => String(item.path || ''))
    );
    const availableSlots = ATTACHMENT_LIMITS.count - composerAttachments.length;
    const references = paths
        .map((path, index) => normalizeDirectoryReference(path, fallbackNames[index]))
        .filter(item => item && !existingPaths.has(item.path))
        .slice(0, Math.max(0, availableSlots));
    if (!references.length) return 0;
    composerAttachments.push(...references);
    renderComposerAttachments();
    updateComposerSendState();
    return references.length;
}

async function getDroppedFolderPaths(dataTransfer, directoryEntries) {
    const directoryNames = new Set(directoryEntries.map(entry => entry.name));
    const directPaths = getDroppedFiles(dataTransfer)
        .map(getDroppedFilePath)
        .filter(path => path && directoryNames.has(getPathBaseName(path)));
    if (directPaths.length >= directoryEntries.length) return directPaths;
    if (typeof eel?.get_dragged_folder_paths !== 'function') return directPaths;
    try {
        const result = await eel.get_dragged_folder_paths(
            directoryEntries.map(entry => entry.name)
        )();
        if (result?.success) return Array.from(new Set([...directPaths, ...(result.paths || [])]));
    } catch (error) {
        if (!handleEelConnectionError(error)) {
            console.error('Failed to resolve dropped folder paths:', error);
        }
    }
    return directPaths;
}

async function addDroppedComposerItems(dataTransfer) {
    const directoryEntries = getDroppedDirectoryEntries(dataTransfer);
    const droppedFiles = getDroppedFiles(dataTransfer);
    const folderPaths = await getDroppedFolderPaths(dataTransfer, directoryEntries);
    const folderNames = new Set(directoryEntries.map(entry => entry.name));
    const matchedFolderPaths = folderPaths.filter(path => folderNames.has(getPathBaseName(path)));
    const folderCount = addComposerDirectoryReferences(
        matchedFolderPaths,
        directoryEntries.map(entry => entry.name)
    );
    const directoryNames = new Set(directoryEntries.map(entry => entry.name));
    const regularFiles = droppedFiles.filter(file => !directoryNames.has(file.name));
    if (regularFiles.length) await addComposerAttachments(regularFiles);
    if (directoryEntries.length && folderCount === 0) {
        showToast('无法读取该文件夹路径，请将文件夹直接从 Finder 拖入', 'error');
    }
}

function hasComposerDragItems(dataTransfer) {
    if (!dataTransfer) return false;
    const types = Array.from(dataTransfer.types || []);
    return types.includes('Files') || types.includes(WORKSPACE_DRAG_TYPE);
}

function getWorkspaceDragPayload(dataTransfer) {
    try {
        const raw = dataTransfer?.getData(WORKSPACE_DRAG_TYPE);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.folder === 'string'
            && typeof parsed.path === 'string' && parsed.path) {
            return parsed;
        }
    } catch (_error) {
        /* not a workspace file drag */
    }
    return null;
}

async function resolveWorkspacePath(folder, path) {
    if (typeof eel?.get_workspace_path !== 'function') return null;
    try {
        const result = await eel.get_workspace_path(folder, path)();
        if (result?.success) {
            return {
                path: String(result.path || ''),
                isDir: Boolean(result.is_dir),
                name: String(result.name || getPathBaseName(path) || ''),
            };
        }
    } catch (error) {
        if (!handleEelConnectionError(error)) {
            console.error('Failed to resolve workspace path:', error);
        }
    }
    return null;
}

async function readWorkspaceFile(folder, path) {
    if (typeof eel?.read_workspace_file_bytes !== 'function') return null;
    try {
        const result = await eel.read_workspace_file_bytes(folder, path)();
        if (!result?.success || !result.data) return null;
        return {
            name: String(result.name || getPathBaseName(path) || '文件'),
            size: Number(result.size || 0),
            mimeType: String(result.mime_type || 'application/octet-stream'),
            data: `data:${result.mime_type || 'application/octet-stream'};base64,${result.data}`,
        };
    } catch (error) {
        if (!handleEelConnectionError(error)) {
            console.error('Failed to read workspace file:', error);
        }
    }
    return null;
}

async function addDroppedWorkspaceFile(payload) {
    const folder = String(payload.folder || '');
    const path = String(payload.path || '');
    const fallbackName = String(payload.name || getPathBaseName(path) || '');
    const resolved = await resolveWorkspacePath(folder, path);
    if (!resolved) return;
    if (payload.isFolder || resolved.isDir) {
        addComposerDirectoryReferences([resolved.path], [resolved.name || fallbackName]);
        return;
    }
    const fileData = await readWorkspaceFile(folder, path);
    if (!fileData) {
        showToast(`${fallbackName} 读取失败`, 'error');
        return;
    }
    let bytes = null;
    try {
        const binary = atob(fileData.data.split(',')[1] || '');
        bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    } catch (_error) {
        /* invalid base64 */
    }
    if (!bytes || !bytes.length) {
        showToast(`${fileData.name} 读取失败`, 'error');
        return;
    }
    const file = new File([bytes], fileData.name, {
        type: fileData.mimeType,
        lastModified: Date.now(),
    });
    await addComposerAttachments([file]);
}

// Custom Input Dialog
let inputDialogResolve = null;

function showInputDialog(title, defaultValue = '') {
    return new Promise((resolve) => {
        if (inputDialogResolve) inputDialogResolve(null);
        inputDialogResolve = resolve;
        lastFocusedElement = document.activeElement;
        document.getElementById('inputDialogTitle').textContent = title;
        const input = document.getElementById('inputDialogInput');
        input.value = defaultValue;
        input.placeholder = '';
        document.getElementById('inputDialog').classList.add('active');
        input.focus();
        input.select();

        // Enter 键提交
        input.onkeypress = (e) => {
            if (e.key === 'Enter') {
                confirmInputDialog();
            }
        };
    });
}

function closeInputDialog() {
    document.getElementById('inputDialog').classList.remove('active');
    if (inputDialogResolve) {
        inputDialogResolve(null);
        inputDialogResolve = null;
    }
    lastFocusedElement?.focus?.();
}

function confirmInputDialog() {
    const value = document.getElementById('inputDialogInput').value;
    document.getElementById('inputDialog').classList.remove('active');
    if (inputDialogResolve) {
        inputDialogResolve(value || null);
        inputDialogResolve = null;
    }
    lastFocusedElement?.focus?.();
}

// Custom Confirm Dialog
let confirmDialogResolve = null;

function showConfirmDialog(message) {
    return new Promise((resolve) => {
        if (confirmDialogResolve) confirmDialogResolve(false);
        confirmDialogResolve = resolve;
        lastFocusedElement = document.activeElement;
        document.getElementById('confirmDialogMessage').textContent = message;
        document.getElementById('confirmDialog').classList.add('active');
        document.querySelector('#confirmDialog .btn-save')?.focus();
    });
}

function closeConfirmDialog() {
    document.getElementById('confirmDialog').classList.remove('active');
    if (confirmDialogResolve) {
        confirmDialogResolve(false);
        confirmDialogResolve = null;
    }
    lastFocusedElement?.focus?.();
}

function confirmConfirmDialog() {
    document.getElementById('confirmDialog').classList.remove('active');
    if (confirmDialogResolve) {
        confirmDialogResolve(true);
        confirmDialogResolve = null;
    }
    lastFocusedElement?.focus?.();
}

function updateQueueDisplay() {
    const queueEl = document.getElementById('messageQueue');
    const queueList = document.getElementById('queueList');
    const queueCount = document.getElementById('queueCount');
    const activeId = String(activeConversationId || '');

    const visible = [];
    messageQueue.forEach((item, globalIdx) => {
        const conversationId = typeof item === 'string'
            ? activeId
            : String(item.conversationId || activeId);
        if (conversationId === activeId) visible.push({ item, globalIdx });
    });

    if (visible.length === 0) {
        queueEl.style.display = 'none';
        queueList.innerHTML = '';
        return;
    }

    queueEl.style.display = 'block';
    queueCount.textContent = visible.length;

    queueList.innerHTML = visible.map(({ item, globalIdx }, visibleIdx) => {
        const message = typeof item === 'string' ? item : item.message;
        const attachmentCount = typeof item === 'string' ? 0 : (item.attachments || []).length;
        const label = `${message || '解析附件'}${attachmentCount ? ` · ${attachmentCount} 个附件` : ''}`;
        return `
        <div class="queue-item">
            <span class="queue-item-number">${visibleIdx + 1}.</span>
            <span class="queue-item-text" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
            <button class="queue-item-remove" onclick="removeFromQueue(${globalIdx})" aria-label="移除第 ${visibleIdx + 1} 个等待任务">✕</button>
        </div>
    `;
    }).join('');
}

function removeFromQueue(index) {
    messageQueue.splice(index, 1);
    updateQueueDisplay();
}

function init() {
    if (typeof eel === 'undefined') {
        setTimeout(init, 100);
        return;
    }
    installEelGuard();
    eel._websocket?.addEventListener('open', () => {
        eelConnectionLost = false;
        eelConnectionNoticeShown = false;
    });
    eel._websocket?.addEventListener('close', () => {
        markEelConnectionLost();
    });
    initializeUI();
    setSidebarCollapsed(getSavedSidebarCollapsed(), {persist: false});
    initializeSidebarWidth();
    setSidebarPanel(getSavedSidebarPanel());
    initializeOSAgent();
    if (!splitPaneMode) {
        refreshAllWorkspace();
        refreshSkills();
    }
    updateTokenIndicator();
    updateEmbeddingStatus();
    setInterval(() => {
        if (!splitPaneMode && !document.hidden && canCallEel()) refreshAllWorkspace();
    }, 5000);
    setInterval(() => {
        if (!document.hidden && canCallEel()) updateTokenIndicator();
    }, 4000);
    setInterval(() => {
        if (!document.hidden && canCallEel()) updateEmbeddingStatus();
    }, 12000);
    setInterval(() => {
        if (!document.hidden && activeConversationId && canCallEel()) {
            syncPreviewSessions(activeConversationId);
        }
    }, 4000);
    setInterval(() => {
        if (!document.hidden && !refreshInFlight && canCallEel()) {
            refreshConversations(
                splitPaneMode ? splitTaskIdFromUrl : activeConversationId
            ).catch(error => {
                if (handleEelConnectionError(error)) return;
                console.error('Failed to sync task activity:', error);
            });
        }
    }, 1800);
}

document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    if (splitPaneMode) document.body.classList.add('split-pane-mode');
    init();
});

window.addEventListener('message', event => {
    if (event.origin !== window.location.origin) return;
    if (
        splitPaneMode
        && event.source === window.parent
        && event.data?.type === 'jcodex-theme-change'
    ) {
        applyTheme(event.data.theme, {syncSplitPane: false});
        return;
    }
    const splitFrame = document.getElementById('splitTaskFrame');
    if (
        !splitPaneMode
        && event.source === splitFrame?.contentWindow
        && event.data?.type === 'jcodex-split-agent-detail'
    ) {
        setSplitChildAgentDetailOpen(event.data.open);
        return;
    }
    if (
        !splitPaneMode
        && event.source === splitFrame?.contentWindow
        && event.data?.type === 'jcodex-split-browser-preview'
    ) {
        setSplitChildBrowserPreviewOpen(event.data.open);
    }
});

function initializeUI() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const clearChat = document.getElementById('clearChat');
    const quickActions = document.querySelectorAll('.quick-action');
    const settingsBtn = document.getElementById('settingsBtn');
    const themeToggle = document.getElementById('themeToggle');
    const tokenIndicator = document.getElementById('tokenIndicator');
    const accessToggle = document.getElementById('accessToggle');
    const planModeToggle = document.getElementById('planModeToggle');
    const multiAgentModeToggle = document.getElementById('multiAgentModeToggle');
    const modelBadge = document.getElementById('modelBadge');
    const voiceModeButton = document.getElementById('voiceModeButton');
    const voiceHoldButton = document.getElementById('voiceHoldButton');
    const inputAddButton = document.getElementById('inputAddButton');
    const composerAddMenuAnchor = document.getElementById('composerAddMenuAnchor');
    const composerAddMenu = document.getElementById('composerAddMenu');
    const attachmentInput = document.getElementById('attachmentInput');
    const skillFolderInput = document.getElementById('skillFolderInput');
    const skillStoreSearch = document.getElementById('skillStoreSearch');
    const clearQueueButton = document.getElementById('clearQueueButton');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const sidebarCollapseButton = document.getElementById('sidebarCollapseButton');
    const sidebarResizeHandle = document.getElementById('sidebarResizeHandle');
    const newTaskButton = document.getElementById('newTaskButton');
    const newProjectButton = document.getElementById('newProjectButton');
    const splitTaskButton = document.getElementById('splitTaskButton');
    const splitTaskCollapse = document.getElementById('splitTaskCollapse');
    const splitTaskClose = document.getElementById('splitTaskClose');
    const splitResizeHandle = document.getElementById('splitResizeHandle');
    const splitTaskFrame = document.getElementById('splitTaskFrame');
    const sidebarNav = document.querySelector('.sidebar-nav');
    const planProgress = document.getElementById('planProgress');
    const planProgressTrigger = document.getElementById('planProgressTrigger');
    const inputContainer = messageInput.closest('.input-container');
    const chatMessages = document.getElementById('chatMessages');
    const imageLightbox = document.getElementById('imageLightbox');
    const imageLightboxClose = document.getElementById('imageLightboxClose');
    const previewFrame = document.getElementById('browserPreviewFrame');
    const changeReviewPanel = document.getElementById('changeReviewPanel');
    const voiceInputArea = document.querySelector('.main-content .input-area');
    const voiceMainContent = document.querySelector('.main-content');
    const changeReviewResizeHandle = document.getElementById('changeReviewResizeHandle');
    const agentDetailResizeHandle = document.getElementById('agentDetailResizeHandle');
    let composerDragDepth = 0;

    applyAccessToggleState(autoAllowAll);
    applyPlanModeToggleState(planModeEnabled);
    applyMultiAgentModeToggleState(multiAgentModeEnabled);
    initializeVoiceSpeechVoices();
    loadVoiceTtsPrefs();
    syncAutoAllowAll(autoAllowAll);
    updateModelBadge();

    messageInput.addEventListener('input', () => {
        resizeComposerInput(messageInput);

        // Show/hide quick commands popup
        if (messageInput.value.startsWith('/')) {
            showQuickCommands();
        } else {
            hideQuickCommands();
        }

        sendButton.disabled = !messageInput.value.trim() && composerAttachments.length === 0;
    });

    messageInput.addEventListener('keydown', (e) => {
        // 检测输入法是否正在组合输入（e.isComposing）
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            if ((messageInput.value.trim() || composerAttachments.length) && !sendButton.disabled) {
                sendMessage();
            }
        }

        if (e.key === 'Enter' && e.shiftKey && !e.isComposing) {
            requestAnimationFrame(() => resizeComposerInput(messageInput));
        }

        // Handle "/" shortcut
        if (e.key === '/' && messageInput.value === '' && !e.isComposing) {
            e.preventDefault();
            messageInput.value = '/';
            showQuickCommands();
        }

        // Escape to close quick commands
        if (e.key === 'Escape') {
            hideQuickCommands();
        }
    });

    messageInput.addEventListener('paste', async (event) => {
        const images = getClipboardImages(event.clipboardData);
        if (!images.length) return;
        event.preventDefault();
        await addComposerAttachments(images);
        messageInput.focus();
    });

    sendButton.addEventListener('click', sendMessage);
    if (accessToggle) {
        accessToggle.addEventListener('click', () => {
            setAutoAllowAll(!autoAllowAll);
        });
    }
    if (planModeToggle) {
        planModeToggle.addEventListener('click', () => {
            setPlanModeEnabled(false);
            inputAddButton?.focus();
        });
    }
    if (multiAgentModeToggle) {
        multiAgentModeToggle.addEventListener('click', () => {
            setMultiAgentModeEnabled(false);
            inputAddButton?.focus();
        });
    }
    if (modelBadge) {
        modelBadge.addEventListener('click', toggleModelQuickSwitch);
        window.addEventListener('resize', positionModelQuickSwitch);
        const modelMenuEl = document.getElementById('modelQuickSwitch');
        if (modelMenuEl) {
            modelMenuEl.addEventListener('mouseout', (event) => {
                const submenus = modelMenuEl.querySelectorAll('.model-reasoning-submenu');
                if (!submenus.length) return;
                // 从二级栏走出去不关闭；只有从一级面板主体走出去才关闭
                const leavingFromSubmenu = !!(event.target
                    && event.target.closest
                    && event.target.closest('.model-reasoning-submenu'));
                const related = event.relatedTarget;
                const goingOutside = !(related
                    && related.nodeType === 1
                    && modelMenuEl.contains(related));
                if (goingOutside && !leavingFromSubmenu) {
                    submenus.forEach(sub => sub.classList.remove('is-open'));
                }
            });
        }
    }

    // 点击菜单外部时关闭 API 配置下拉框与模型上拉框
    document.addEventListener('click', event => {
        const configMenu = document.getElementById('configSelectMenu');
        const configTrigger = document.getElementById('configSelectTrigger');
        if (configMenu && !configMenu.hidden
            && !configTrigger?.contains(event.target)
            && !configMenu.contains(event.target)) {
            closeApiConfigMenu();
        }
        const modelMenu = document.getElementById('modelQuickSwitch');
        const badgeEl = document.getElementById('modelBadge');
        if (modelMenu && !modelMenu.hidden
            && !badgeEl?.contains(event.target)
            && !modelMenu.contains(event.target)) {
            closeModelQuickSwitch();
        }
    });
    voiceModeButton?.addEventListener('click', toggleVoiceMode);
    window.addEventListener('resize', positionVoiceStrands);
    if ('ResizeObserver' in window && voiceInputArea && voiceMainContent) {
        voiceLayoutObserver?.disconnect();
        voiceLayoutObserver = new ResizeObserver(positionVoiceStrands);
        voiceLayoutObserver.observe(voiceInputArea);
        voiceLayoutObserver.observe(inputContainer);
        voiceLayoutObserver.observe(voiceMainContent);
    }
    voiceHoldButton?.addEventListener('pointerdown', event => {
        event.preventDefault();
        if (voicePointerId !== null) return;
        voicePointerId = event.pointerId;
        voiceHoldButton.setPointerCapture?.(event.pointerId);
        voiceSpaceHeld = true;
        startVoiceListening();
    });
    voiceHoldButton?.addEventListener('pointerup', event => {
        event.preventDefault();
        if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
        stopVoiceListening();
    });
    voiceHoldButton?.addEventListener('pointercancel', event => {
        if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
        stopVoiceListening({send: false});
    });
    voiceHoldButton?.addEventListener('lostpointercapture', event => {
        if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
        if (voiceSpaceHeld) stopVoiceListening({send: false});
    });
    document.addEventListener('keydown', event => {
        if (!voiceModeActive || event.code !== 'Space') return;
        if (isVoiceShortcutBlocked(event.target)) return;
        event.preventDefault();
        if (event.repeat) return;
        voiceSpaceHeld = true;
        startVoiceListening();
    }, true);
    document.addEventListener('keyup', event => {
        if (!voiceModeActive || event.code !== 'Space') return;
        if (isVoiceShortcutBlocked(event.target)) return;
        event.preventDefault();
        if (!voiceSpaceHeld) return;
        stopVoiceListening();
    }, true);
    window.addEventListener('pointerup', event => {
        if (!voiceModeActive || !voiceSpaceHeld) return;
        if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
        stopVoiceListening();
    });
    window.addEventListener('blur', () => {
        if (voiceSpaceHeld) stopVoiceListening({send: false});
    });
    if (inputAddButton) {
        inputAddButton.addEventListener('click', () => {
            toggleComposerAddMenu();
        });
        inputAddButton.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                openComposerAddMenu(true);
            } else if (event.key === 'Escape') {
                closeComposerAddMenu(true);
            }
        });
    }
    composerAddMenu?.addEventListener('click', event => {
        const action = event.target.closest('[data-composer-action]')?.dataset.composerAction;
        if (!action) return;
        closeComposerAddMenu();
        if (action === 'upload-attachment') {
            attachmentInput?.click();
            return;
        }
        if (action === 'upload-folder') {
            selectComposerFolder(messageInput);
            return;
        }
        if (action === 'enable-plan-mode') {
            setPlanModeEnabled(true);
            messageInput.focus();
            return;
        }
        if (action === 'enable-multi-agent-mode') {
            setMultiAgentModeEnabled(true);
            messageInput.focus();
        }
    });
    composerAddMenu?.addEventListener('keydown', event => {
        const items = getComposerAddMenuItems();
        const currentIndex = items.indexOf(document.activeElement);
        if (event.key === 'Escape') {
            event.preventDefault();
            closeComposerAddMenu(true);
        } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (!items.length) return;
            const offset = event.key === 'ArrowDown' ? 1 : -1;
            const nextIndex = currentIndex < 0
                ? 0
                : (currentIndex + offset + items.length) % items.length;
            items[nextIndex].focus();
        } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            items[event.key === 'Home' ? 0 : items.length - 1]?.focus();
        }
    });
    attachmentInput?.addEventListener('change', async () => {
        await addComposerAttachments(Array.from(attachmentInput.files || []));
        attachmentInput.value = '';
        messageInput.focus();
    });
    initializeSidebarAutoHideScrollbars();
    skillFolderInput?.addEventListener('change', async () => {
        await importSkillFolder(Array.from(skillFolderInput.files || []));
        skillFolderInput.value = '';
    });
    skillStoreSearch?.addEventListener('input', () => {
        renderSkillStore(skillStoreSearch.value);
    });
    inputContainer?.addEventListener('dragenter', (event) => {
        if (!hasComposerDragItems(event.dataTransfer)) return;
        event.preventDefault();
        composerDragDepth += 1;
        inputContainer.classList.add('is-dragging-files');
    });
    inputContainer?.addEventListener('dragover', (event) => {
        if (!hasComposerDragItems(event.dataTransfer)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        inputContainer.classList.add('is-dragging-files');
    });
    inputContainer?.addEventListener('dragleave', (event) => {
        if (!hasComposerDragItems(event.dataTransfer)) return;
        composerDragDepth = Math.max(0, composerDragDepth - 1);
        if (composerDragDepth === 0) inputContainer.classList.remove('is-dragging-files');
    });
    inputContainer?.addEventListener('drop', async (event) => {
        if (!hasComposerDragItems(event.dataTransfer)) return;
        event.preventDefault();
        composerDragDepth = 0;
        inputContainer.classList.remove('is-dragging-files');
        const workspaceDrag = getWorkspaceDragPayload(event.dataTransfer);
        if (workspaceDrag) {
            await addDroppedWorkspaceFile(workspaceDrag);
        } else {
            await addDroppedComposerItems(event.dataTransfer);
        }
        messageInput.focus();
    });
    clearQueueButton?.addEventListener('click', () => clearMessageQueue(activeConversationId));
    sidebarToggle?.addEventListener('click', () => {
        document.body.classList.toggle('sidebar-open');
        const isOpen = document.body.classList.contains('sidebar-open');
        sidebarToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        sidebarToggle.setAttribute('aria-label', isOpen ? '关闭工作台导航' : '打开工作台导航');
        if (isOpen) {
            document.querySelector('.sidebar-nav-item.is-active')?.focus();
        }
    });
    bindAppModeSwitcher();
    sidebarCollapseButton?.addEventListener('click', () => {
        setSidebarCollapsed(!isSidebarCollapsed());
    });
    sidebarBackdrop?.addEventListener('click', closeMobileSidebar);
    const mobileSidebarQuery = window.matchMedia('(max-width: 780px)');
    const handleSidebarBreakpointChange = (event) => {
        if (!event.matches) closeMobileSidebar();
    };
    if (typeof mobileSidebarQuery.addEventListener === 'function') {
        mobileSidebarQuery.addEventListener('change', handleSidebarBreakpointChange);
    } else {
        mobileSidebarQuery.addListener(handleSidebarBreakpointChange);
    }
    const updateSidebarNavOrientation = (event = mobileSidebarQuery) => {
        sidebarNav?.setAttribute('aria-orientation', event.matches ? 'horizontal' : 'vertical');
    };
    updateSidebarNavOrientation();
    if (typeof mobileSidebarQuery.addEventListener === 'function') {
        mobileSidebarQuery.addEventListener('change', updateSidebarNavOrientation);
    } else {
        mobileSidebarQuery.addListener(updateSidebarNavOrientation);
    }
    initializeSidebarResizeHandle(sidebarResizeHandle, mobileSidebarQuery);
    initializeChangeReviewResizeHandle(changeReviewResizeHandle);
    initializeChangeReviewFilesResizeHandle(
        document.getElementById('changeReviewFilesResizeHandle')
    );
    initializeAgentDetailResizeHandle(agentDetailResizeHandle);
    initializeSplitResizeHandle(splitResizeHandle);
    window.addEventListener('resize', syncDockedLayoutWidths);
    newTaskButton?.addEventListener('click', () => createNewConversation());
    splitTaskButton?.addEventListener('click', openSplitTask);
    splitTaskCollapse?.addEventListener('click', closeSplitTask);
    splitTaskClose?.addEventListener('click', deleteSplitTask);
    splitTaskFrame?.addEventListener('load', () => {
        setSplitChildAgentDetailOpen(false);
        setSplitChildBrowserPreviewOpen(false);
        syncSplitTaskTheme();
    });
    newProjectButton?.addEventListener('click', () => openProjectDialog());
    document.getElementById('projectDialogClose')?.addEventListener('click', closeProjectDialog);
    document.getElementById('projectDialogCancel')?.addEventListener('click', closeProjectDialog);
    document.getElementById('projectDialogSave')?.addEventListener('click', saveProjectDialog);
    document.getElementById('projectBrowseButton')?.addEventListener('click', async event => {
        const button = event.currentTarget;
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = '正在选择…';
        try {
            const result = await eel.select_project_folder()();
            if (result?.success && result.path) {
                const input = document.getElementById('projectPathInput');
                input.value = result.path;
                if (!document.getElementById('projectNameInput').value.trim()) {
                    document.getElementById('projectNameInput').value = result.path.split(/[\\/]/).filter(Boolean).pop() || '';
                }
            } else if (!result?.cancelled && result?.error) {
                showToast(`选择目录失败：${result.error}`, 'error');
            }
        } catch (error) {
            showToast(`选择目录失败：${error.message}`, 'error');
        } finally {
            button.disabled = false;
            button.textContent = originalLabel;
        }
    });
    document.getElementById('projectDialog')?.addEventListener('click', event => {
        if (event.target.id === 'projectDialog') closeProjectDialog();
    });
    sidebarNav?.addEventListener('click', event => {
        const button = event.target.closest('[data-sidebar-panel]');
        if (!button) return;
        setSidebarPanel(button.dataset.sidebarPanel, {focus: false});
    });
    sidebarNav?.addEventListener('keydown', event => {
        const items = getSidebarPanelButtons();
        const currentIndex = items.indexOf(document.activeElement);
        if (!items.length || currentIndex < 0) return;
        if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let nextIndex = currentIndex;
        if (event.key === 'ArrowDown' || event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % items.length;
        if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + items.length) % items.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = items.length - 1;
        items[nextIndex].focus();
        setSidebarPanel(items[nextIndex].dataset.sidebarPanel, {focus: false});
    });
    chatMessages?.addEventListener('click', handleAgentTeamClick);
    chatMessages?.addEventListener('click', handlePreviewLinkClick);
    document.addEventListener('click', handleImagePreviewClick);
    document.addEventListener('keydown', handleImagePreviewKeydown);
    imageLightboxClose?.addEventListener('click', () => closeImageLightbox());
    imageLightbox?.addEventListener('click', event => {
        if (event.target === imageLightbox) closeImageLightbox();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && imageLightbox && !imageLightbox.hidden) {
            event.preventDefault();
            closeImageLightbox();
        }
    });
    chatMessages?.addEventListener('scroll', () => {
        updateChatAutoFollow(chatMessages);
        maybeLoadOlderChatHistory(chatMessages);
    }, {passive: true});
    chatMessages?.addEventListener('wheel', event => {
        if (event.deltaY < 0) setChatAutoFollow(false);
    }, {passive: true});
    document.getElementById('changeReviewClose')?.addEventListener('click', () => {
        closeChangeReview();
    });
    document.getElementById('changeReviewFileHeader')?.addEventListener('click', (event) => {
        if (event.target.closest('.change-review-edit')) openChangeReviewEditor();
    });
    document.getElementById('agentDetailClose')?.addEventListener('click', () => {
        closeAgentDetail();
    });
    document.getElementById('changeReviewFileList')?.addEventListener('click', event => {
        const dir = event.target.closest('[data-review-dir]');
        if (dir) {
            toggleChangeReviewDir(dir.dataset.reviewDir);
            return;
        }
        const file = event.target.closest('[data-review-file-index]');
        if (file) selectChangeReviewFile(Number(file.dataset.reviewFileIndex));
    });
    changeReviewPanel?.addEventListener('transitionend', () => {
        if (changeReviewPanel.classList.contains('is-open')) {
            document.getElementById('changeReviewDiff')?.focus({preventScroll: true});
        }
    });
    document.getElementById('browserPreviewClose')?.addEventListener('click', () => {
        closeBrowserPreview();
    });
    document.getElementById('browserPreviewRefresh')?.addEventListener(
        'click', refreshBrowserPreview
    );
    document.getElementById('browserPreviewCopy')?.addEventListener(
        'click', copyBrowserPreviewAddress
    );
    document.getElementById('browserPreviewExternal')?.addEventListener(
        'click', openBrowserPreviewExternal
    );
    document.getElementById('browserPreviewStop')?.addEventListener(
        'click', stopBrowserPreview
    );
    previewFrame?.addEventListener('load', () => {
        if (activePreviewId && previewFrame.src !== 'about:blank') hideBrowserPreviewState();
    });
    document.querySelectorAll('.sidebar-workbench .sidebar-action-item').forEach((button) => {
        button.addEventListener('click', closeMobileSidebar);
    });

    // Stop button - also clears pending message
    const stopButton = document.getElementById('stopButton');
    stopButton.addEventListener('click', async () => {
        const state = getActiveExecutionState();
        if (!isProcessing || !state?.running) return;

        const conversationId = state.conversationId;
        const messageId = Number(state.messageId || currentMessageId || 0);
        updateConversationExecutionState(conversationId, {
            messageId,
            running: false,
            stopping: false,
            outputStopped: false,
            awaitingQuestion: false,
            awaitingApproval: false,
        });
        resetTrackedExecutionActivity(state);
        updateConversationListItemState(conversationId, {
            running: false,
            stopping: false,
            active_message_id: 0,
        });
        renderConversationList();

        // Freeze the visible stream immediately. Backend cancellation can finish
        // asynchronously, but the composer should be usable without waiting.
        if (String(activeConversationId || '') === conversationId) {
            invalidatePolling(conversationId);
            removeThinking();
            finalizeVisibleStreamingResponses();
            finishActiveToolExecutions('已停止');
            failActiveCompressionActivities('压缩已停止');
            if (isAwaitingQuestion) finalizePendingQuestion('任务已停止');
            isAwaitingQuestion = false;
            document.querySelector('.approval-container')?.remove();
            updateProcessingUI(false);
            document.getElementById('messageInput')?.focus();
        }

        try {
            stopButton.disabled = true;
            const request = eel.stop_execution(conversationId, messageId)();
            pendingStopRequests.set(conversationId, request);
            const result = await request;
            if (!result?.success) throw new Error(result?.error || '停止失败');
            if (result?.agent_team) {
                updateAgentTeamSnapshot(
                    result.agent_team,
                    conversationId,
                    messageId,
                    {animate: false}
                );
            }
            const modifiedFiles = result?.modified_files;
            if (
                modifiedFiles
                && String(activeConversationId || '') === conversationId
                && Number(modifiedFiles.message_id || messageId) === messageId
            ) {
                addModifiedFilesSummary({
                    ...modifiedFiles,
                    conversation_id: conversationId,
                    message_id: messageId,
                });
            }
            markPlanProgressTerminal(
                conversationId, messageId, 'stopped', '任务已停止'
            );
            markAgentTeamsTerminal(conversationId, messageId, 'cancelled');
            showToast('已停止输出，可以继续发送消息', 'success', 1800);
            refreshConversations(activeConversationId).catch(console.error);
            dispatchNextQueuedMessage();
        } catch (error) {
            console.error('Stop error:', error);
            const status = await eel.get_execution_status(conversationId, messageId)()
                .catch(() => null);
            if (status?.running) {
                updateConversationExecutionState(conversationId, {
                    messageId,
                    running: true,
                    stopping: Boolean(status.stopping),
                    awaitingQuestion: Boolean(status.awaiting_question),
                    awaitingApproval: Boolean(status.awaiting_approval),
                });
                ensureExecutionPolling(conversationId, messageId);
            }
            syncActiveConversationProcessingUI({showPlaceholder: true});
            stopButton.disabled = false;
            showToast(`停止失败：${error.message}`, 'error');
        } finally {
            pendingStopRequests.delete(conversationId);
        }
    });
    clearChat.addEventListener('click', clearConversation);
    settingsBtn.addEventListener('click', openSettings);
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const nextTheme = document.body.classList.contains('theme-dark') ? 'light' : 'dark';
            applyTheme(nextTheme);
        });
    }

    // Token indicator click
    tokenIndicator?.addEventListener('click', toggleTokenTooltip);

    quickActions.forEach(btn => {
        btn.addEventListener('click', () => {
            fillComposer(btn.dataset.prompt || '');
        });
    });
    planProgressTrigger?.addEventListener('click', () => {
        const expanded = !planProgress?.classList.contains('is-expanded');
        planProgress?.classList.toggle('is-expanded', expanded);
        planProgressTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    });
    document.addEventListener('click', event => {
        if (!planProgress?.hidden && !planProgress.contains(event.target)) {
            closePlanProgress();
        }
        if (!composerAddMenu?.hidden && !composerAddMenuAnchor?.contains(event.target)) {
            closeComposerAddMenu();
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            if (voiceModeActive) {
                closeVoiceMode();
                return;
            }
            if (activeChangeReview) {
                closeChangeReview();
                return;
            }
            if (activeAgentDetail) {
                closeAgentDetail();
                return;
            }
            closePlanProgress();
            closeComposerAddMenu(true);
            if (document.getElementById('projectDialog')?.classList.contains('active')) {
                closeProjectDialog();
            }
        }
    });
}

async function selectComposerFolder(messageInput = document.getElementById('messageInput')) {
    if (typeof eel?.select_reference_folder !== 'function') {
        showToast('当前版本无法打开文件夹选择器', 'error');
        return;
    }
    try {
        const result = await eel.select_reference_folder()();
        if (result?.success && result.path) {
            const added = addComposerDirectoryReferences([result.path]);
            if (!added) {
                const duplicate = composerAttachments.some(item => (
                    isDirectoryReference(item) && String(item.path || '') === String(result.path)
                ));
                showToast(
                    duplicate ? '该文件夹已经添加' : `最多添加 ${ATTACHMENT_LIMITS.count} 个附件`,
                    duplicate ? 'info' : 'error'
                );
            }
        } else if (!result?.cancelled && result?.error) {
            showToast(`选择文件夹失败：${result.error}`, 'error');
        }
    } catch (error) {
        if (!handleEelConnectionError(error)) {
            showToast(`选择文件夹失败：${error.message}`, 'error');
        }
    } finally {
        messageInput?.focus();
    }
}

function initializeSidebarAutoHideScrollbars() {
    const scrollAreas = document.querySelectorAll([
        '.sidebar-panel',
        '.sidebar-panel.is-active .task-history-list',
        '#sidebarPanelFiles .file-list',
        '#sidebarPanelSkills #skillsList',
    ].join(','));
    scrollAreas.forEach((area) => {
        if (area.dataset.autoHideScrollbar === 'true') return;
        area.dataset.autoHideScrollbar = 'true';
        let hideTimer = 0;
        const show = () => {
            area.classList.add('is-scrollbar-active');
            window.clearTimeout(hideTimer);
            hideTimer = window.setTimeout(() => {
                if (!area.matches(':hover') && !area.matches(':focus-within')) {
                    area.classList.remove('is-scrollbar-active');
                }
            }, 700);
        };
        area.addEventListener('scroll', show, {passive: true});
        area.addEventListener('pointerenter', show);
        area.addEventListener('pointerleave', () => {
            window.clearTimeout(hideTimer);
            hideTimer = window.setTimeout(() => {
                if (!area.matches(':focus-within')) area.classList.remove('is-scrollbar-active');
            }, 320);
        });
        area.addEventListener('focusin', show);
        area.addEventListener('focusout', () => {
            window.clearTimeout(hideTimer);
            hideTimer = window.setTimeout(() => {
                if (!area.matches(':hover') && !area.matches(':focus-within')) {
                    area.classList.remove('is-scrollbar-active');
                }
            }, 320);
        });
    });
}

function fillComposer(value) {
    const messageInput = document.getElementById('messageInput');
    messageInput.value = value;
    messageInput.dispatchEvent(new Event('input', {bubbles: true}));
    messageInput.focus();
}

function hideWelcome() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages?.classList.remove('is-welcome');
    // Remove the full-height empty state before appending the first message.
    // Keeping it in the layout during an exit animation causes two costly
    // reflows and a visible scroll jump on the first send.
    const welcome = chatMessages?.querySelector('.welcome-message');
    if (welcome) {
        setChatAutoFollow(true);
        welcome.remove();
    }
}

function closeMobileSidebar() {
    document.body.classList.remove('sidebar-open');
    const toggle = document.getElementById('sidebarToggle');
    toggle?.setAttribute('aria-expanded', 'false');
    toggle?.setAttribute('aria-label', '打开工作台导航');
}

function getSavedSidebarCollapsed() {
    try {
        return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === 'true';
    } catch (_error) {
        return false;
    }
}

function isSidebarCollapsed() {
    return document.getElementById('sidebarShell')?.classList.contains('is-collapsed') || false;
}

function setSidebarCollapsed(collapsed, {persist = true} = {}) {
    const next = Boolean(collapsed);
    const sidebar = document.getElementById('sidebarShell');
    const button = document.getElementById('sidebarCollapseButton');
    const handle = document.getElementById('sidebarResizeHandle');
    sidebar?.classList.toggle('is-collapsed', next);
    button?.setAttribute('aria-expanded', next ? 'false' : 'true');
    button?.setAttribute(
        'aria-label',
        next ? '展开工作台导航' : '收起工作台导航'
    );
    button?.setAttribute(
        'title',
        next ? '展开工作台导航' : '收起工作台导航'
    );
    if (handle) {
        handle.tabIndex = next ? -1 : 0;
        handle.setAttribute('aria-hidden', next ? 'true' : 'false');
    }
    if (persist) {
        try {
            localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(next));
        } catch (_error) {
            // The current layout remains usable when browser storage is unavailable.
        }
    }
    requestAnimationFrame(syncDockedLayoutWidths);
    return next;
}

function getStoredSidebarPanelWidth() {
    try {
        const value = Number(localStorage.getItem(SIDEBAR_PANEL_WIDTH_STORAGE_KEY) || 216);
        return Math.round(Math.min(
            SIDEBAR_PANEL_MAX_WIDTH,
            Math.max(SIDEBAR_PANEL_MIN_WIDTH, Number.isFinite(value) ? value : 216)
        ));
    } catch (_error) {
        return 216;
    }
}

function getCurrentSidebarTotalWidth() {
    const sidebar = document.getElementById('sidebarShell');
    const measuredWidth = sidebar?.getBoundingClientRect().width;
    if (Number.isFinite(measuredWidth) && measuredWidth > 0) return measuredWidth;
    return isSidebarCollapsed()
        ? SIDEBAR_RAIL_WIDTH
        : SIDEBAR_RAIL_WIDTH + getStoredSidebarPanelWidth();
}

function isDockedReviewLayout() {
    return window.innerWidth >= 1320;
}

function getReviewPanelWidthLimit(sidebarWidth = getCurrentSidebarTotalWidth()) {
    if (!isDockedReviewLayout()) return Math.min(760, window.innerWidth);
    return Math.max(
        CHANGE_REVIEW_MIN_WIDTH,
        Math.min(
            CHANGE_REVIEW_MAX_WIDTH,
            window.innerWidth - sidebarWidth - DOCKED_MAIN_MIN_WIDTH
        )
    );
}

function clampChangeReviewPanelWidth(value, sidebarWidth = getCurrentSidebarTotalWidth()) {
    const numericValue = Number(value);
    const fallback = Math.min(700, getReviewPanelWidthLimit(sidebarWidth));
    if (!Number.isFinite(numericValue)) return fallback;
    return Math.round(Math.min(
        getReviewPanelWidthLimit(sidebarWidth),
        Math.max(CHANGE_REVIEW_MIN_WIDTH, numericValue)
    ));
}

function getSavedChangeReviewPanelWidth() {
    try {
        return clampChangeReviewPanelWidth(
            localStorage.getItem(CHANGE_REVIEW_WIDTH_STORAGE_KEY) || 700
        );
    } catch (_error) {
        return clampChangeReviewPanelWidth(700);
    }
}

function setChangeReviewPanelWidth(
    width,
    {persist = true, sidebarWidth = getCurrentSidebarTotalWidth()} = {}
) {
    const panelWidth = clampChangeReviewPanelWidth(width, sidebarWidth);
    document.documentElement.style.setProperty('--change-review-width', `${panelWidth}px`);
    const handle = document.getElementById('changeReviewResizeHandle');
    handle?.setAttribute('aria-valuenow', String(panelWidth));
    handle?.setAttribute(
        'aria-valuemax',
        String(getReviewPanelWidthLimit(sidebarWidth))
    );
    if (persist) {
        try {
            localStorage.setItem(CHANGE_REVIEW_WIDTH_STORAGE_KEY, String(panelWidth));
        } catch (_error) {
            // Width remains usable if browser storage is unavailable.
        }
    }
    return panelWidth;
}

function clampChangeReviewFilesWidth(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return CHANGE_REVIEW_FILES_DEFAULT_WIDTH;
    return Math.round(Math.min(
        CHANGE_REVIEW_FILES_MAX_WIDTH,
        Math.max(CHANGE_REVIEW_FILES_MIN_WIDTH, numericValue)
    ));
}

function getSavedChangeReviewFilesWidth() {
    try {
        return clampChangeReviewFilesWidth(
            localStorage.getItem(CHANGE_REVIEW_FILES_WIDTH_STORAGE_KEY)
            || CHANGE_REVIEW_FILES_DEFAULT_WIDTH
        );
    } catch (_error) {
        return CHANGE_REVIEW_FILES_DEFAULT_WIDTH;
    }
}

function setChangeReviewFilesWidth(width, {persist = true} = {}) {
    const filesWidth = clampChangeReviewFilesWidth(width);
    document.documentElement.style.setProperty(
        '--change-review-files-width', `${filesWidth}px`
    );
    const handle = document.getElementById('changeReviewFilesResizeHandle');
    handle?.setAttribute('aria-valuenow', String(filesWidth));
    if (persist) {
        try {
            localStorage.setItem(
                CHANGE_REVIEW_FILES_WIDTH_STORAGE_KEY, String(filesWidth)
            );
        } catch (_error) {
            // Width remains usable if browser storage is unavailable.
        }
    }
    return filesWidth;
}

function getAgentDetailPanelWidthLimit(sidebarWidth = getCurrentSidebarTotalWidth()) {
    if (!isDockedReviewLayout()) return AGENT_DETAIL_MAX_WIDTH;
    return Math.max(
        AGENT_DETAIL_MIN_WIDTH,
        Math.min(
            AGENT_DETAIL_MAX_WIDTH,
            window.innerWidth - sidebarWidth - DOCKED_MAIN_MIN_WIDTH
        )
    );
}

function clampAgentDetailPanelWidth(value, sidebarWidth = getCurrentSidebarTotalWidth()) {
    const numericValue = Number(value);
    const fallback = Math.min(
        AGENT_DETAIL_DEFAULT_WIDTH,
        getAgentDetailPanelWidthLimit(sidebarWidth)
    );
    if (!Number.isFinite(numericValue)) return fallback;
    return Math.round(Math.min(
        getAgentDetailPanelWidthLimit(sidebarWidth),
        Math.max(AGENT_DETAIL_MIN_WIDTH, numericValue)
    ));
}

function getSavedAgentDetailPanelWidth() {
    try {
        return clampAgentDetailPanelWidth(
            localStorage.getItem(AGENT_DETAIL_WIDTH_STORAGE_KEY) || AGENT_DETAIL_DEFAULT_WIDTH
        );
    } catch (_error) {
        return clampAgentDetailPanelWidth(AGENT_DETAIL_DEFAULT_WIDTH);
    }
}

function setAgentDetailPanelWidth(
    width,
    {persist = true, sidebarWidth = getCurrentSidebarTotalWidth()} = {}
) {
    const panelWidth = clampAgentDetailPanelWidth(width, sidebarWidth);
    document.documentElement.style.setProperty('--agent-detail-width', `${panelWidth}px`);
    const handle = document.getElementById('agentDetailResizeHandle');
    handle?.setAttribute('aria-valuenow', String(panelWidth));
    handle?.setAttribute(
        'aria-valuemax',
        String(getAgentDetailPanelWidthLimit(sidebarWidth))
    );
    if (persist) {
        try {
            localStorage.setItem(AGENT_DETAIL_WIDTH_STORAGE_KEY, String(panelWidth));
        } catch (_error) {
            // Width remains usable if browser storage is unavailable.
        }
    }
    return panelWidth;
}

function clampSidebarPanelWidth(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return SIDEBAR_PANEL_MIN_WIDTH;
    const reservesDockedPanel = isDockedReviewLayout()
        && !document.body.classList.contains('split-workspace-open') && (
        document.body.classList.contains('change-review-open')
        || document.body.classList.contains('agent-detail-open')
    );
    const dockedPanelWidth = document.body.classList.contains('change-review-open')
        ? CHANGE_REVIEW_MIN_WIDTH
        : AGENT_DETAIL_MIN_WIDTH;
    const viewportLimit = reservesDockedPanel
        ? Math.max(
            SIDEBAR_PANEL_MIN_WIDTH,
            window.innerWidth
                - SIDEBAR_RAIL_WIDTH
                - dockedPanelWidth
                - DOCKED_MAIN_MIN_WIDTH
        )
        : SIDEBAR_PANEL_MAX_WIDTH;
    return Math.round(Math.min(
        SIDEBAR_PANEL_MAX_WIDTH,
        viewportLimit,
        Math.max(SIDEBAR_PANEL_MIN_WIDTH, numericValue)
    ));
}

function getSavedSidebarPanelWidth() {
    return clampSidebarPanelWidth(getStoredSidebarPanelWidth());
}

function setSidebarPanelWidth(width, {persist = true} = {}) {
    const panelWidth = clampSidebarPanelWidth(width);
    document.documentElement.style.setProperty('--sidebar-panel-width', `${panelWidth}px`);
    const handle = document.getElementById('sidebarResizeHandle');
    handle?.setAttribute('aria-valuenow', String(panelWidth + SIDEBAR_RAIL_WIDTH));
    if (persist) {
        try {
            localStorage.setItem(SIDEBAR_PANEL_WIDTH_STORAGE_KEY, String(panelWidth));
        } catch (_error) {
            // Width remains usable if browser storage is unavailable.
        }
    }
    if (
        isDockedReviewLayout()
        && document.body.classList.contains('change-review-open')
    ) {
        setChangeReviewPanelWidth(getSavedChangeReviewPanelWidth(), {
            persist: false,
            sidebarWidth: getCurrentSidebarTotalWidth(),
        });
    }
    if (
        isDockedReviewLayout()
        && document.body.classList.contains('agent-detail-open')
    ) {
        setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), {
            persist: false,
            sidebarWidth: getCurrentSidebarTotalWidth(),
        });
    }
    return panelWidth;
}

function syncDockedLayoutWidths() {
    if (document.body.classList.contains('split-workspace-open')) {
        const workspace = document.getElementById('splitWorkspace');
        const current = parseFloat(
            workspace?.style.getPropertyValue('--split-pane-width')
        ) || SPLIT_PANE_DEFAULT_WIDTH;
        setSplitPaneWidth(current, {persist: false});
    }
    if (!isDockedReviewLayout()) return;
    setSidebarPanelWidth(
        getSavedSidebarPanelWidth(),
        {persist: false}
    );
    if (document.body.classList.contains('change-review-open')) {
        setChangeReviewPanelWidth(
            getSavedChangeReviewPanelWidth(),
            {
                persist: false,
                sidebarWidth: getCurrentSidebarTotalWidth(),
            }
        );
    }
    if (document.body.classList.contains('agent-detail-open')) {
        setAgentDetailPanelWidth(
            getSavedAgentDetailPanelWidth(),
            {
                persist: false,
                sidebarWidth: getCurrentSidebarTotalWidth(),
            }
        );
    }
}

function initializeSidebarWidth() {
    setSidebarPanelWidth(getSavedSidebarPanelWidth(), {persist: false});
    setChangeReviewPanelWidth(getSavedChangeReviewPanelWidth(), {persist: false});
    setChangeReviewFilesWidth(getSavedChangeReviewFilesWidth(), {persist: false});
    setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), {persist: false});
}

function installPointerResizeCleanup(handle, finishResize) {
    handle.addEventListener('pointerup', finishResize);
    handle.addEventListener('pointercancel', finishResize);
    handle.addEventListener('lostpointercapture', finishResize);
    window.addEventListener('pointerup', finishResize);
    window.addEventListener('pointercancel', finishResize);
    window.addEventListener('blur', finishResize);
}

function initializeSidebarResizeHandle(handle, mobileQuery) {
    if (!handle) return;
    let pointerId = null;

    const finishResize = () => {
        document.body.classList.remove('is-resizing-sidebar');
        if (pointerId === null) return;
        const capturedPointerId = pointerId;
        pointerId = null;
        try {
            if (handle.hasPointerCapture(capturedPointerId)) {
                handle.releasePointerCapture(capturedPointerId);
            }
        } catch (_error) {
            // The pointer can end outside the window before capture is released.
        }
    };
    const updateFromPointer = event => {
        if (pointerId === null || mobileQuery.matches) return;
        setSidebarPanelWidth(event.clientX - SIDEBAR_RAIL_WIDTH);
    };

    handle.addEventListener('pointerdown', event => {
        if (mobileQuery.matches || event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        handle.setPointerCapture(pointerId);
        document.body.classList.add('is-resizing-sidebar');
        updateFromPointer(event);
    });
    handle.addEventListener('pointermove', updateFromPointer);
    installPointerResizeCleanup(handle, finishResize);
    handle.addEventListener('keydown', event => {
        if (mobileQuery.matches) return;
        const currentWidth = getSavedSidebarPanelWidth();
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setSidebarPanelWidth(currentWidth - SIDEBAR_WIDTH_STEP);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            setSidebarPanelWidth(currentWidth + SIDEBAR_WIDTH_STEP);
        } else if (event.key === 'Home') {
            event.preventDefault();
            setSidebarPanelWidth(SIDEBAR_PANEL_MIN_WIDTH);
        } else if (event.key === 'End') {
            event.preventDefault();
            setSidebarPanelWidth(SIDEBAR_PANEL_MAX_WIDTH);
        }
    });
}

function initializeChangeReviewResizeHandle(handle) {
    if (!handle) return;
    let pointerId = null;

    const finishResize = () => {
        document.body.classList.remove('is-resizing-review');
        if (pointerId === null) return;
        const capturedPointerId = pointerId;
        pointerId = null;
        try {
            if (handle.hasPointerCapture(capturedPointerId)) {
                handle.releasePointerCapture(capturedPointerId);
            }
        } catch (_error) {
            // Capture may already be gone after a fast cross-window drag.
        }
    };
    const updateFromPointer = event => {
        if (pointerId === null || !isDockedReviewLayout()) return;
        setChangeReviewPanelWidth(window.innerWidth - event.clientX);
    };

    handle.addEventListener('pointerdown', event => {
        if (!isDockedReviewLayout() || event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        handle.setPointerCapture(pointerId);
        document.body.classList.add('is-resizing-review');
        updateFromPointer(event);
    });
    handle.addEventListener('pointermove', updateFromPointer);
    installPointerResizeCleanup(handle, finishResize);
    handle.addEventListener('keydown', event => {
        const currentWidth = getSavedChangeReviewPanelWidth();
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setChangeReviewPanelWidth(currentWidth + CHANGE_REVIEW_WIDTH_STEP);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            setChangeReviewPanelWidth(currentWidth - CHANGE_REVIEW_WIDTH_STEP);
        } else if (event.key === 'Home') {
            event.preventDefault();
            setChangeReviewPanelWidth(CHANGE_REVIEW_MIN_WIDTH);
        } else if (event.key === 'End') {
            event.preventDefault();
            setChangeReviewPanelWidth(getReviewPanelWidthLimit());
        }
    });
}

function initializeChangeReviewFilesResizeHandle(handle) {
    if (!handle) return;
    let pointerId = null;

    const finishResize = () => {
        document.body.classList.remove('is-resizing-review-files');
        if (pointerId === null) return;
        const capturedPointerId = pointerId;
        pointerId = null;
        try {
            if (handle.hasPointerCapture(capturedPointerId)) {
                handle.releasePointerCapture(capturedPointerId);
            }
        } catch (_error) {
            // Capture may already be gone after a fast cross-window drag.
        }
    };
    const updateFromPointer = event => {
        if (pointerId === null) return;
        const panelRect = document.getElementById('changeReviewPanel')
            ?.getBoundingClientRect();
        if (!panelRect) return;
        setChangeReviewFilesWidth(panelRect.right - event.clientX);
    };

    handle.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        handle.setPointerCapture(pointerId);
        document.body.classList.add('is-resizing-review-files');
        updateFromPointer(event);
    });
    handle.addEventListener('pointermove', updateFromPointer);
    installPointerResizeCleanup(handle, finishResize);
}

function initializeAgentDetailResizeHandle(handle) {
    if (!handle) return;
    let pointerId = null;

    const finishResize = () => {
        document.body.classList.remove('is-resizing-agent-detail');
        if (pointerId === null) return;
        const capturedPointerId = pointerId;
        pointerId = null;
        try {
            if (handle.hasPointerCapture(capturedPointerId)) {
                handle.releasePointerCapture(capturedPointerId);
            }
        } catch (_error) {
            // Capture may already be gone after a fast cross-window drag.
        }
    };
    const updateFromPointer = event => {
        if (pointerId === null || !isDockedReviewLayout()) return;
        setAgentDetailPanelWidth(window.innerWidth - event.clientX);
    };

    handle.addEventListener('pointerdown', event => {
        if (!isDockedReviewLayout() || event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        handle.setPointerCapture(pointerId);
        document.body.classList.add('is-resizing-agent-detail');
        updateFromPointer(event);
    });
    handle.addEventListener('pointermove', updateFromPointer);
    installPointerResizeCleanup(handle, finishResize);
    handle.addEventListener('keydown', event => {
        if (!isDockedReviewLayout()) return;
        const currentWidth = getSavedAgentDetailPanelWidth();
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setAgentDetailPanelWidth(currentWidth + AGENT_DETAIL_WIDTH_STEP);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            setAgentDetailPanelWidth(currentWidth - AGENT_DETAIL_WIDTH_STEP);
        } else if (event.key === 'Home') {
            event.preventDefault();
            setAgentDetailPanelWidth(AGENT_DETAIL_MIN_WIDTH);
        } else if (event.key === 'End') {
            event.preventDefault();
            setAgentDetailPanelWidth(getAgentDetailPanelWidthLimit());
        }
    });
}

function getSidebarPanelButtons() {
    return Array.from(document.querySelectorAll('.sidebar-nav-item[data-sidebar-panel]'));
}

function getSavedSidebarPanel() {
    try {
        const saved = localStorage.getItem(SIDEBAR_PANEL_STORAGE_KEY);
        return SIDEBAR_PANEL_NAMES.has(saved) ? saved : 'tasks';
    } catch (_error) {
        return 'tasks';
    }
}

function setSidebarPanel(panelName, {focus = false} = {}) {
    const name = SIDEBAR_PANEL_NAMES.has(panelName) ? panelName : 'tasks';
    const panel = document.querySelector(`[data-sidebar-panel-content="${name}"]`);
    if (!panel) return;

    document.querySelectorAll('[data-sidebar-panel-content]').forEach(item => {
        const isActive = item === panel;
        item.hidden = !isActive;
        item.classList.toggle('is-active', isActive);
    });
    getSidebarPanelButtons().forEach(button => {
        const isActive = button.dataset.sidebarPanel === name;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        button.tabIndex = isActive ? 0 : -1;
    });
    try {
        localStorage.setItem(SIDEBAR_PANEL_STORAGE_KEY, name);
    } catch (_error) {
        // Side panel selection remains usable when browser storage is unavailable.
    }
    if (focus) {
        document.querySelector(`[data-sidebar-panel="${name}"]`)?.focus();
    }
}

function getWelcomeHeading(conversation = getActiveConversation()) {
    const project = getProject(conversation?.project_id);
    const projectName = String(project?.name || '').trim();
    return projectName
        ? `今天想在“${projectName}”里完成什么？`
        : '今天想完成什么？';
}

function updateWelcomeHeading(conversation = getActiveConversation()) {
    const heading = document.getElementById('welcomeTitle');
    if (heading) {
        heading.textContent = appMode === 'jcchat'
            ? '今天想聊点什么？'
            : getWelcomeHeading(conversation);
    }
}

function welcomeMarkup(conversation = getActiveConversation()) {
    const jcchat = appMode === 'jcchat';
    const actions = jcchat
        ? `
            <button class="quick-action" data-prompt="用通俗易懂的方式给我讲解一个概念，并举一个生活中的例子">
                <span class="quick-action-copy"><strong>学习答疑</strong><small>通俗解释、举例说明</small></span><span class="quick-action-arrow">↗</span>
            </button>
            <button class="quick-action" data-prompt="帮我写一篇短文，主题你来建议，语言简洁自然">
                <span class="quick-action-copy"><strong>写作助手</strong><small>短文、润色、翻译</small></span><span class="quick-action-arrow">↗</span>
            </button>
            <button class="quick-action" data-prompt="我们随便聊聊天吧，轻松一点">
                <span class="quick-action-copy"><strong>轻松聊天</strong><small>闲聊、倾诉、解压</small></span><span class="quick-action-arrow">↗</span>
            </button>`
        : `
            <button class="quick-action" data-prompt="扫描当前项目并给出最值得优先修复的问题">
                <span class="quick-action-copy"><strong>扫描当前项目</strong><small>发现风险与优化机会</small></span><span class="quick-action-arrow">↗</span>
            </button>
            <button class="quick-action" data-prompt="整理工作区文件并生成一份结构说明">
                <span class="quick-action-copy"><strong>整理工作区</strong><small>归类文件并生成说明</small></span><span class="quick-action-arrow">↗</span>
            </button>
            <button class="quick-action" data-prompt="调研当前任务涉及的技术方案，核对可靠来源，并运行必要测试给出结论">
                <span class="quick-action-copy"><strong>调研与验证</strong><small>检索资料并运行测试</small></span><span class="quick-action-arrow">↗</span>
            </button>`;
    return `
        <div class="welcome-message">
            <div class="welcome-mark" aria-hidden="true">
                <img class="theme-asset-mark" src="${THEME_ASSETS[getCurrentTheme()].mark}" alt="">
                <span class="welcome-mark-glow"></span>
            </div>
            <div class="welcome-kicker">${jcchat ? 'JC-CHAT' : 'JCODEX WORKSPACE'}</div>
            <h2 id="welcomeTitle">${jcchat ? '今天想聊点什么？' : escapeHtml(getWelcomeHeading(conversation))}</h2>
            <p>${jcchat ? '和 JC-Chat 随意聊聊，学习、写作、翻译、答疑都可以。' : '描述目标，JCodex 会规划步骤、调用工具并持续汇报进度。'}</p>
            <div class="quick-actions">${actions}</div>
        </div>`;
}

function bindQuickActions() {
    document.querySelectorAll('.quick-action').forEach(button => {
        button.addEventListener('click', () => fillComposer(button.dataset.prompt || ''));
    });
}

function refreshWelcomeCards() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages || !chatMessages.querySelector('.welcome-message')) return;
    chatMessages.innerHTML = welcomeMarkup(getActiveConversation());
    bindQuickActions();
}

function resetConversationView(conversation = getActiveConversation()) {
    if (voiceModeActive) cancelVoiceSpeech();
    chatHistoryState = null;
    chatHistoryLoading = false;
    closeImageLightbox({restoreFocus: false});
    closeAgentDetail({restoreFocus: false});
    closeChangeReview({restoreFocus: false});
    closeBrowserPreview(false);
    previewSessions.clear();
    renderPreviewDock(false);
    previewSyncGeneration += 1;
    isAwaitingQuestion = false;
    pendingKnowledgeByMessageId.clear();
    completedMessageByMessageId.clear();
    removeStreamingResponses();
    removeThinking();
    discardActiveToolExecutions();
    clearCompressionActivities();
    closePlanProgress();
    document.getElementById('planProgress')?.setAttribute('hidden', '');
    detachAgentTeamCardsForConversation(conversation?.id || activeConversationId);
    const chatMessages = document.getElementById('chatMessages');
    setChatAutoFollow(true);
    chatMessages.classList.add('is-welcome');
    chatMessages.innerHTML = welcomeMarkup(conversation);
    chatMessages.scrollTop = 0;
    bindQuickActions();
}

function formatConversationDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
    }
    return date.toLocaleDateString('zh-CN', {month: 'numeric', day: 'numeric'});
}

function getProject(projectId) {
    const id = String(projectId || '');
    return projects.find(project => String(project.id || '') === id) || null;
}

function getActiveConversation() {
    return conversations.find(item => String(item.id || '') === String(activeConversationId || '')) || null;
}

function updateActiveProjectLabel(conversation = getActiveConversation()) {
    const element = document.getElementById('activeProjectName');
    const project = getProject(conversation?.project_id);
    if (element) {
        element.textContent = project?.name || '普通任务';
        element.title = project?.root_path || 'JCodex 默认工作区';
    }
    updateWelcomeHeading(conversation);
}

function createProjectTaskRow(item) {
    const row = createTaskHistoryItem(item.id);
    row.classList.add('project-task-item');
    return row;
}

function applyTaskRowState(row, item) {
    const conversationId = String(item.id || '');
    const execution = getConversationExecutionState(item.id, false);
    const running = Boolean(item.running || execution?.running);
    const unread = !running && Boolean(item.unread_completion || execution?.unreadCompletion);
    const stateLabel = running ? '正在执行' : unread ? '执行完成，尚未查看' : '';
    row.dataset.conversationId = conversationId;
    row.classList.toggle('is-active', conversationId === String(activeConversationId || ''));
    row.classList.toggle('is-running', running);
    row.classList.toggle('has-unread-completion', unread);

    const main = row.querySelector('.task-history-main');
    const dot = row.querySelector('.task-history-state-dot');
    const name = row.querySelector('.task-history-name');
    const date = row.querySelector('.task-history-date');
    const title = String(item.title || '新任务');
    const dateText = formatConversationDate(item.updated_at);
    main.title = title;
    name.textContent = title;
    date.textContent = dateText;
    dot.hidden = !stateLabel;
    if (stateLabel) {
        dot.setAttribute('aria-label', stateLabel);
        dot.title = stateLabel;
    } else {
        dot.removeAttribute('aria-label');
        dot.removeAttribute('title');
    }
}

function renderProjectList() {
    const list = document.getElementById('projectList');
    const count = document.getElementById('projectCount');
    if (!list) return;
    if (count) count.textContent = projects.length ? String(projects.length) : '';
    list.replaceChildren();
    if (!projects.length) {
        const empty = document.createElement('div');
        empty.className = 'sidebar-empty';
        empty.textContent = '暂无项目';
        list.appendChild(empty);
        return;
    }

    projects.forEach(project => {
        const projectId = String(project.id || '');
        const projectTasks = conversations.filter(
            item => !item.is_split_task
                && String(item.project_id || '') === projectId
        );
        const activeInside = projectTasks.some(item => String(item.id || '') === String(activeConversationId || ''));
        if (activeInside) expandedProjectIds.add(projectId);
        const expanded = expandedProjectIds.has(projectId);
        const group = document.createElement('section');
        group.className = 'project-group';
        group.dataset.projectId = projectId;

        const header = document.createElement('div');
        header.className = 'project-row';
        header.classList.toggle('is-active', activeInside);
        header.classList.toggle('is-unavailable', !project.available);
        header.innerHTML = `
            <button class="project-toggle" type="button" aria-expanded="${expanded ? 'true' : 'false'}" title="${expanded ? '收起项目' : '展开项目'}">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
            </button>
            <button class="project-main" type="button" title="${escapeHtml(project.root_path || '')}">
                <svg class="project-folder-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                <span class="project-name">${escapeHtml(project.name || '项目')}</span>
                <span class="project-task-count">${projectTasks.length}</span>
            </button>
            <button class="project-menu" type="button" aria-label="管理项目">•••</button>`;
        const children = document.createElement('div');
        children.className = 'project-task-list';
        children.hidden = !expanded;

        projectTasks.forEach(item => {
            const row = createProjectTaskRow(item);
            applyTaskRowState(row, item);
            children.appendChild(row);
        });
        header.querySelector('.project-toggle').addEventListener('click', () => {
            if (expandedProjectIds.has(projectId)) expandedProjectIds.delete(projectId);
            else expandedProjectIds.add(projectId);
            renderProjectList();
        });
        header.querySelector('.project-main').addEventListener('click', () => {
            expandedProjectIds.add(projectId);
            if (projectTasks.length) switchConversation(projectTasks[0].id);
            else createNewConversation(projectId);
        });
        header.querySelector('.project-menu').addEventListener('click', event => {
            event.stopPropagation();
            openProjectMenu(event, projectId);
        });
        group.append(header, children);
        list.appendChild(group);
    });
}

async function refreshProjects() {
    if (!canCallEel() || typeof eel.list_projects !== 'function') return projects;
    try {
        const result = await eel.list_projects()();
        if (!result?.success) throw new Error(result?.error || '项目列表加载失败');
        projects = result.projects || [];
        renderProjectList();
        updateActiveProjectLabel();
        return projects;
    } catch (error) {
        if (handleEelConnectionError(error)) return projects;
        console.error('Failed to refresh projects:', error);
        return projects;
    }
}

function createTaskHistoryItem(conversationId) {
    const row = document.createElement('div');
    row.className = 'task-history-item';
    row.dataset.conversationId = String(conversationId || '');

    const main = document.createElement('button');
    main.className = 'task-history-main';
    main.type = 'button';
    main.addEventListener('click', () => {
        switchConversation(row.dataset.conversationId);
    });

    const dot = document.createElement('span');
    dot.className = 'task-history-state-dot';
    dot.setAttribute('role', 'status');
    dot.hidden = true;

    const name = document.createElement('span');
    name.className = 'task-history-name';
    const date = document.createElement('span');
    date.className = 'task-history-date';
    main.append(dot, name, date);

    const menu = document.createElement('button');
    menu.className = 'task-history-menu';
    menu.type = 'button';
    menu.textContent = '•••';
    menu.setAttribute('aria-label', '管理任务');
    menu.addEventListener('click', event => {
        event.stopPropagation();
        openConversationMenu(event, row.dataset.conversationId);
    });

    row.append(main, menu);
    return row;
}

function renderConversationList() {
    const list = document.getElementById('taskHistoryList');
    const count = document.getElementById('taskHistoryCount');
    if (!list) return;
    const ordinaryConversations = conversations.filter(
        item => !item.project_id && !item.is_split_task
    );
    if (count) count.textContent = ordinaryConversations.length ? `${ordinaryConversations.length}` : '';
    if (!ordinaryConversations.length) {
        if (!list.querySelector('.sidebar-empty')) {
            list.replaceChildren();
            const empty = document.createElement('div');
            empty.className = 'sidebar-empty';
            empty.textContent = '暂无任务';
            list.appendChild(empty);
        }
        return;
    }

    list.querySelector('.sidebar-empty')?.remove();
    const existingRows = new Map(
        Array.from(list.querySelectorAll('.task-history-item')).map(row => [
            String(row.dataset.conversationId || ''),
            row,
        ])
    );

    ordinaryConversations.forEach((item, index) => {
        const conversationId = String(item.id || '');
        const row = existingRows.get(conversationId)
            || createTaskHistoryItem(conversationId);
        applyTaskRowState(row, item);

        const currentAtIndex = list.children[index];
        if (currentAtIndex !== row) {
            list.insertBefore(row, currentAtIndex || null);
        }
        existingRows.delete(conversationId);
    });

    existingRows.forEach(row => row.remove());
    renderProjectList();
}

function updateActiveTaskTitle(title) {
    const element = document.getElementById('activeTaskTitle');
    if (element) element.textContent = title || '新任务';
}

async function refreshConversations(preferredId = null) {
    if (!canCallEel()) return activeConversationId;
    const generation = ++conversationRefreshGeneration;
    let result;
    try {
        result = await eel.list_conversations(
            splitPaneMode ? splitTaskIdFromUrl : ''
        )();
    } catch (error) {
        if (handleEelConnectionError(error)) return activeConversationId;
        throw error;
    }
    if (!result?.success) throw new Error(result?.error || '任务列表加载失败');
    if (generation !== conversationRefreshGeneration) return activeConversationId;
    conversations = result.conversations || [];
    syncExecutionStatesFromConversations(conversations);
    const pinnedConversationExists = splitPaneMode
        && splitTaskIdFromUrl
        && conversations.some(item => String(item.id) === splitTaskIdFromUrl);
    const preferredExists = preferredId
        && conversations.some(item => String(item.id) === String(preferredId));
    activeConversationId = pinnedConversationExists
        ? splitTaskIdFromUrl
        : preferredExists
        ? preferredId
        : result.active_id || conversations[0]?.id || null;
    const active = conversations.find(item => item.id === activeConversationId);
    if (active) updateActiveTaskTitle(active.title);
    updateActiveProjectLabel(active);
    renderConversationList();
    conversationExecutionStates.forEach(state => {
        if (state.running && state.messageId) {
            ensureExecutionPolling(state.conversationId, state.messageId);
        }
    });
    syncActiveConversationProcessingUI();
    return activeConversationId;
}

async function createNewConversation(projectId = '') {
    try {
        const result = await eel.create_conversation('新任务', String(projectId || ''))();
        if (!result?.success) throw new Error(result?.error || '创建失败');
        activeConversationId = result.conversation.id;
        markConversationReadLocally(activeConversationId);
        resetConversationView(result.conversation);
        updateQueueDisplay();
        updateActiveTaskTitle(result.conversation.title);
        await restoreSplitTaskForConversation(activeConversationId);
        if (projectId) expandedProjectIds.add(String(projectId));
        await refreshConversations(activeConversationId);
        await refreshProjects();
        syncActiveConversationProcessingUI();
        updateTokenIndicator();
        closeMobileSidebar();
        document.getElementById('messageInput')?.focus();
    } catch (error) {
        showToast(`新建任务失败：${error.message}`, 'error');
    }
}

async function switchConversation(conversationId) {
    if (!conversationId || conversationId === activeConversationId) {
        if (conversationId) {
            markConversationReadLocally(conversationId);
            renderConversationList();
            updateQueueDisplay();
            try {
                await eel.set_active_conversation(conversationId)();
            } catch (error) {
                console.error('Failed to mark task as read:', error);
            }
        }
        closeMobileSidebar();
        return;
    }
    try {
        splitStateGeneration += 1;
        hideSplitTaskPane();
        conversationRefreshGeneration += 1;
        const result = await eel.set_active_conversation(conversationId)();
        if (!result?.success) throw new Error(result?.error || '切换失败');
        activeConversationId = conversationId;
        markConversationReadLocally(conversationId);
        updateQueueDisplay();
        renderConversation(result.conversation);
        await restoreSplitTaskForConversation(conversationId);
        const execution = getConversationExecutionState(conversationId, false);
        if (execution?.running) execution.liveRenderSuppressed = false;
        await refreshConversations(conversationId);
        markConversationReadLocally(conversationId);
        renderConversationList();
        syncActiveConversationProcessingUI({showPlaceholder: true});
        // Split-pane state and execution placeholders can reflow the chat after
        // its history is first rendered. A task switch should always end at the
        // newest message instead of retaining the previous task's scroll anchor.
        pinChatToBottom(document.getElementById('chatMessages'), {force: true});
        updateTokenIndicator();
        closeMobileSidebar();
    } catch (error) {
        showToast(`切换任务失败：${error.message}`, 'error');
    }
}

function openConversationMenu(event, conversationId) {
    document.querySelector('.conversation-context-menu')?.remove();
    const item = conversations.find(entry => entry.id === conversationId);
    if (!item) return;
    const menu = document.createElement('div');
    menu.className = 'conversation-context-menu';
    menu.innerHTML = `
        <button type="button" data-action="rename">重命名</button>
        ${item.project_id ? '<button type="button" data-action="move-out">移出项目</button>' : ''}
        <button type="button" data-action="archive">归档</button>
        <button type="button" data-action="delete" class="is-danger">删除任务</button>`;
    document.body.appendChild(menu);
    const rect = event.currentTarget.getBoundingClientRect();
    menu.style.left = `${Math.min(rect.left, window.innerWidth - 142)}px`;
    menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - 124)}px`;
    menu.querySelector('[data-action="rename"]').onclick = async () => {
        menu.remove();
        const title = await showInputDialog('重命名任务', item.title || '新任务');
        if (!title) return;
        const result = await eel.rename_conversation(conversationId, title)();
        if (!result?.success) return showToast(result?.error || '重命名失败', 'error');
        if (conversationId === activeConversationId) updateActiveTaskTitle(result.conversation.title);
        await refreshConversations(activeConversationId);
    };
    menu.querySelector('[data-action="archive"]').onclick = async () => {
        menu.remove();
        if (isConversationRunning(conversationId)) {
            return showToast('正在执行的任务请先停止后再归档', 'info');
        }
        const archivedWasActive = String(conversationId) === String(activeConversationId || '');
        if (archivedWasActive) {
            splitStateGeneration += 1;
            hideSplitTaskPane();
        }
        const result = await eel.archive_conversation(conversationId)();
        if (!result?.success) {
            if (archivedWasActive) await restoreSplitTaskForConversation(conversationId);
            return showToast(result?.error || '归档失败', 'error');
        }
        const nextActiveId = await refreshConversations(activeConversationId);
        if (archivedWasActive && nextActiveId) {
            const loaded = await eel.load_conversation(nextActiveId)();
            if (loaded?.success) renderConversation(loaded.conversation);
            await restoreSplitTaskForConversation(nextActiveId);
            pinChatToBottom(document.getElementById('chatMessages'), {force: true});
        }
        updateTokenIndicator();
        showToast('任务已归档', 'success');
    };
    const moveOut = menu.querySelector('[data-action="move-out"]');
    if (moveOut) moveOut.onclick = async () => {
        menu.remove();
        if (isConversationRunning(conversationId)) {
            return showToast('正在执行的任务请先停止后再移动', 'info');
        }
        const result = await eel.move_conversation_to_project(conversationId, '')();
        if (!result?.success) return showToast(result?.error || '移动失败', 'error');
        await refreshConversations(activeConversationId);
        await refreshProjects();
        if (String(conversationId) === String(activeConversationId || '')) {
            updateActiveProjectLabel(result.conversation);
        }
        showToast('任务已移到普通任务', 'success');
    };
    menu.querySelector('[data-action="delete"]').onclick = async () => {
        menu.remove();
        if (isConversationRunning(conversationId)) {
            return showToast('正在执行的任务请先停止后再删除', 'info');
        }
        const confirmed = await showConfirmDialog(`删除任务“${item.title}”？此操作不可撤销。`);
        if (!confirmed) return;
        const deletedWasActive = String(conversationId) === String(activeConversationId || '');
        const splitWasOpen = deletedWasActive
            && document.body.classList.contains('split-workspace-open');
        if (deletedWasActive) {
            splitStateGeneration += 1;
            hideSplitTaskPane();
        }
        const result = await eel.delete_conversation(conversationId)();
        if (!result?.success) {
            if (splitWasOpen) await restoreSplitTaskForConversation(conversationId);
            return showToast(result?.error || '删除失败', 'error');
        }
        const deletedConversationIds = Array.from(new Set(
            (result.deleted_conversation_ids || [conversationId]).map(String)
        ));
        deletedConversationIds.forEach(deletedId => {
            conversationExecutionStates.delete(deletedId);
            clearConversationPlanProgress(deletedId);
            clearConversationAgentTeams(deletedId);
        });
        const nextActiveId = await refreshConversations(
            deletedWasActive ? result.active_id : activeConversationId
        );
        // Redrawing a live task clears its streaming cards, so preserve it when
        // the deleted item was only a different sidebar task.
        if (!deletedWasActive) return;
        if (!nextActiveId) return;
        const loaded = await eel.load_conversation(nextActiveId)();
        if (loaded?.success) renderConversation(loaded.conversation);
        await restoreSplitTaskForConversation(nextActiveId);
        // Restoring the split pane can reflow the chat after its history is
        // rendered, so a deleted task switch must always end at the newest
        // message instead of retaining the previous task's scroll anchor.
        pinChatToBottom(document.getElementById('chatMessages'), {force: true});
    };
    setTimeout(() => document.addEventListener('click', () => menu.remove(), {once: true}), 0);
}

function closeProjectDialog() {
    const dialog = document.getElementById('projectDialog');
    dialog?.classList.remove('active');
    dialog?.setAttribute('aria-hidden', 'true');
    editingProjectId = null;
    lastFocusedElement?.focus?.();
}

function openProjectDialog(projectId = '') {
    const project = getProject(projectId);
    editingProjectId = project ? String(project.id) : null;
    lastFocusedElement = document.activeElement;
    document.getElementById('projectDialogTitle').textContent = project ? '编辑项目' : '添加项目';
    document.getElementById('projectNameInput').value = project?.name || '';
    document.getElementById('projectPathInput').value = project?.root_path || '';
    document.getElementById('projectInstructionsInput').value = project?.instructions || '';
    document.getElementById('projectDialogSave').textContent = project ? '保存项目' : '添加并新建任务';
    const dialog = document.getElementById('projectDialog');
    dialog?.classList.add('active');
    dialog?.setAttribute('aria-hidden', 'false');
    document.getElementById(project ? 'projectNameInput' : 'projectPathInput')?.focus();
}

async function saveProjectDialog() {
    const name = document.getElementById('projectNameInput')?.value.trim() || '';
    const rootPath = document.getElementById('projectPathInput')?.value.trim() || '';
    const instructions = document.getElementById('projectInstructionsInput')?.value.trim() || '';
    if (!rootPath) {
        showToast('请输入项目本地目录', 'error');
        document.getElementById('projectPathInput')?.focus();
        return;
    }
    const button = document.getElementById('projectDialogSave');
    if (button) button.disabled = true;
    try {
        const result = editingProjectId
            ? await eel.update_project(editingProjectId, name, rootPath, instructions)()
            : await eel.create_project(name, rootPath, instructions)();
        if (!result?.success) throw new Error(result?.error || '项目保存失败');
        const createdConversationId = result.conversation?.id || null;
        const projectId = String(result.project?.id || editingProjectId || '');
        if (projectId) expandedProjectIds.add(projectId);
        closeProjectDialog();
        await refreshProjects();
        await refreshConversations(createdConversationId || activeConversationId);
        if (createdConversationId) {
            const loaded = await eel.set_active_conversation(createdConversationId)();
            if (loaded?.success) renderConversation(loaded.conversation);
        }
        showToast(result.conversation ? '项目已添加' : '项目已更新', 'success');
    } catch (error) {
        showToast(`项目保存失败：${error.message}`, 'error');
    } finally {
        if (button) button.disabled = false;
    }
}

function openProjectMenu(event, projectId) {
    document.querySelector('.conversation-context-menu')?.remove();
    const project = getProject(projectId);
    if (!project) return;
    const menu = document.createElement('div');
    menu.className = 'conversation-context-menu project-context-menu';
    menu.innerHTML = `
        <button type="button" data-action="new-task">新建项目任务</button>
        <button type="button" data-action="open-folder">打开项目目录</button>
        <button type="button" data-action="edit">编辑项目</button>
        <button type="button" data-action="delete" class="is-danger">移除项目</button>`;
    document.body.appendChild(menu);
    const rect = event.currentTarget.getBoundingClientRect();
    menu.style.left = `${Math.min(rect.left, window.innerWidth - 170)}px`;
    menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - 154)}px`;
    menu.querySelector('[data-action="new-task"]').onclick = () => {
        menu.remove();
        createNewConversation(projectId);
    };
    menu.querySelector('[data-action="open-folder"]').onclick = async () => {
        menu.remove();
        const result = await eel.open_project_folder(projectId)();
        if (!result?.success) showToast(result?.error || '无法打开项目目录', 'error');
    };
    menu.querySelector('[data-action="edit"]').onclick = () => {
        menu.remove();
        openProjectDialog(projectId);
    };
    menu.querySelector('[data-action="delete"]').onclick = async () => {
        menu.remove();
        const confirmed = await showConfirmDialog(
            `移除项目“${project.name}”？本地代码不会被删除，项目任务会移到普通任务。`
        );
        if (!confirmed) return;
        const result = await eel.delete_project(projectId)();
        if (!result?.success) return showToast(result?.error || '移除项目失败', 'error');
        expandedProjectIds.delete(String(projectId));
        await refreshConversations(activeConversationId);
        await refreshProjects();
        showToast('项目已移除，本地目录保持不变', 'success');
    };
    setTimeout(() => document.addEventListener('click', () => menu.remove(), {once: true}), 0);
}

function applyAccessToggleState(enabled) {
    const accessToggle = document.getElementById('accessToggle');
    if (!accessToggle) return;
    accessToggle.classList.toggle('active', enabled);
    accessToggle.setAttribute('aria-pressed', enabled ? 'true' : 'false');
    const label = document.getElementById('accessModeLabel');
    if (label) {
        label.textContent = enabled ? '完全访问' : '询问模式';
    }
    accessToggle.title = enabled ? '当前为完全访问：工具自动执行' : '当前为询问模式：执行敏感工具前确认';
}

async function syncAutoAllowAll(enabled) {
    try {
        await eel.set_auto_allow_all(Boolean(enabled))();
    } catch (e) {
        console.error('Failed to sync access mode:', e);
    }
}

function setAutoAllowAll(enabled) {
    autoAllowAll = Boolean(enabled);
    localStorage.setItem('minibot-auto-allow-all', autoAllowAll ? 'true' : 'false');
    applyAccessToggleState(autoAllowAll);
    syncAutoAllowAll(autoAllowAll);
    showToast(autoAllowAll ? '已切换到完全访问' : '已切换到询问模式', 'info', 1600);
}

function applyPlanModeToggleState(enabled) {
    const planModePill = document.getElementById('planModePill');
    if (!planModePill) return;
    const isEnabled = Boolean(enabled);
    planModePill.hidden = !isEnabled;
    planModePill.setAttribute(
        'aria-label',
        isEnabled ? '计划模式已开启' : '计划模式已关闭'
    );
}

function setPlanModeEnabled(enabled) {
    planModeEnabled = Boolean(enabled);
    localStorage.setItem('minibot-plan-mode-enabled', planModeEnabled ? 'true' : 'false');
    applyPlanModeToggleState(planModeEnabled);
    if (!planModeEnabled) {
        // 计划模式关闭：立即隐藏计划进度胶囊。
        const planProgress = document.getElementById('planProgress');
        if (planProgress) planProgress.hidden = true;
        closePlanProgress();
    }
    showToast(planModeEnabled ? '计划模式已开启' : '计划模式已关闭', 'info', 1600);
}

function applyMultiAgentModeToggleState(enabled) {
    const pill = document.getElementById('multiAgentModePill');
    if (!pill) return;
    const isEnabled = Boolean(enabled);
    pill.hidden = !isEnabled;
    pill.setAttribute(
        'aria-label',
        isEnabled ? '多智能体协作已开启' : '多智能体协作已关闭'
    );
}

function setMultiAgentModeEnabled(enabled) {
    multiAgentModeEnabled = Boolean(enabled);
    localStorage.setItem(
        'minibot-multi-agent-mode-enabled',
        multiAgentModeEnabled ? 'true' : 'false'
    );
    applyMultiAgentModeToggleState(multiAgentModeEnabled);
    showToast(
        multiAgentModeEnabled ? '多智能体协作已开启' : '多智能体协作已关闭',
        'info',
        1600
    );
}

function getComposerAddMenuItems() {
    return Array.from(
        document.querySelectorAll('#composerAddMenu [role="menuitem"]:not(:disabled)')
    );
}

function openComposerAddMenu(focusFirst = false) {
    const menu = document.getElementById('composerAddMenu');
    const trigger = document.getElementById('inputAddButton');
    if (!menu || !trigger) return;
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    if (focusFirst) getComposerAddMenuItems()[0]?.focus();
}

function closeComposerAddMenu(restoreFocus = false) {
    const menu = document.getElementById('composerAddMenu');
    const trigger = document.getElementById('inputAddButton');
    if (!menu || !trigger) return;
    const wasOpen = !menu.hidden;
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus && wasOpen) trigger.focus();
}

function toggleComposerAddMenu() {
    const menu = document.getElementById('composerAddMenu');
    if (!menu) return;
    if (menu.hidden) openComposerAddMenu();
    else closeComposerAddMenu();
}

async function updateModelBadge() {
    try {
        const settings = await eel.load_settings()();
        const modelName = document.getElementById('modelName');
        if (modelName) {
            modelName.textContent = settings.api_model || '模型';
        }
    } catch (e) {
        console.error('Failed to update model badge:', e);
    }
}

async function updateEmbeddingStatus() {
    const badge = document.getElementById('embeddingBadge');
    const label = document.getElementById('embeddingProviderText');
    if (!badge || !label || !canCallEel() || statusRefreshInFlight) return;

    statusRefreshInFlight = true;
    try {
        const status = await eel.get_embedding_status()();
        const provider = status.provider || 'unknown';
        const dimension = status.dimension || 0;
        const isApi = provider === 'api' && status.available;
        const isFtsOnly = provider === 'disabled';

        badge.classList.toggle('sdk-active', isApi);
        badge.classList.toggle('sdk-fallback', isFtsOnly);
        badge.classList.toggle('sdk-error', !isApi && !isFtsOnly);
        label.textContent = isApi
            ? (dimension ? `Hybrid ${dimension}D` : 'Hybrid')
            : isFtsOnly
                ? 'FTS5 / BM25'
                : '记忆检索异常';
        badge.title = isApi
            ? `OpenAI-compatible embeddings: ${status.model || provider}`
            : isFtsOnly
                ? 'Embedding 未配置，按 Grok 逻辑使用 FTS5/BM25'
                : status.error || `当前记忆检索：${provider}`;
    } catch (e) {
        if (handleEelConnectionError(e)) return;
        badge.classList.add('sdk-error');
        label.textContent = '向量引擎异常';
        badge.title = e.message || '无法获取向量引擎状态';
    } finally {
        statusRefreshInFlight = false;
    }
}

async function initializeOSAgent() {
    try {
        const result = await eel.initialize(
            splitPaneMode ? splitTaskIdFromUrl : ''
        )();

        if (result[0]) {
            isInitialized = true;
            await eel.load_settings()();
            await refreshProjects();
            const conversationId = await refreshConversations();
            const initialConversationId = splitPaneMode && splitTaskIdFromUrl
                ? splitTaskIdFromUrl
                : conversationId;
            if (!splitPaneMode && initialConversationId && initialConversationId !== conversationId) {
                await switchConversation(initialConversationId);
            }
            if (initialConversationId) {
                const loaded = splitPaneMode
                    ? await eel.load_conversation(initialConversationId)()
                    : await eel.set_active_conversation(initialConversationId)();
                if (loaded?.success) {
                    renderConversation(loaded.conversation);
                } else {
                    const current = await eel.load_conversation(initialConversationId)();
                    if (current?.success) renderConversation(current.conversation);
                }
            }
            if (!splitPaneMode && initialConversationId) {
                await restoreSplitTaskForConversation(initialConversationId);
            }
            await restoreExecutionState();
            await restorePendingSend();
            if (!isProcessing) setAppStatus('ready', '就绪');
            document.getElementById('messageInput').focus();
        } else {
            setAppStatus('error', '初始化失败');
            showError('初始化失败：' + result[1]);
        }
    } catch (error) {
        setAppStatus('error', '初始化失败');
        showError('初始化失败：' + error.message);
    }
}

function splitTaskUrl(conversationId) {
    const url = new URL(window.location.href);
    url.searchParams.set('split_child', '1');
    url.searchParams.set('split_task', String(conversationId || ''));
    return url.toString();
}

function getSplitPaneWidthLimit() {
    const workspace = document.getElementById('splitWorkspace');
    const mainContent = document.querySelector('.main-content');
    if (!workspace || !mainContent) return SPLIT_PANE_DEFAULT_WIDTH;
    const container = mainContent.parentElement;
    if (!container) return SPLIT_PANE_DEFAULT_WIDTH;
    const containerRect = container.getBoundingClientRect();
    const mainRect = mainContent.getBoundingClientRect();
    const sharedWidth = Math.max(0, containerRect.right - mainRect.left);
    const computedMainMinWidth = Number.parseFloat(
        window.getComputedStyle(mainContent).minWidth
    );
    const mainMinWidth = Number.isFinite(computedMainMinWidth) && computedMainMinWidth > 0
        ? computedMainMinWidth
        : SPLIT_MAIN_MIN_WIDTH;
    return Math.max(SPLIT_PANE_MIN_WIDTH, sharedWidth - mainMinWidth);
}

function setSplitPaneWidth(width, {persist = true, conversationId = activeConversationId} = {}) {
    const workspace = document.getElementById('splitWorkspace');
    const handle = document.getElementById('splitResizeHandle');
    if (!workspace) return 0;
    const normalized = Math.round(Math.max(
        SPLIT_PANE_MIN_WIDTH,
        Math.min(Number(width) || SPLIT_PANE_DEFAULT_WIDTH, getSplitPaneWidthLimit())
    ));
    workspace.style.setProperty('--split-pane-width', `${normalized}px`);
    handle?.setAttribute('aria-valuenow', String(normalized));
    handle?.setAttribute('aria-valuemax', String(Math.round(getSplitPaneWidthLimit())));
    if (persist && conversationId && canCallEel()) {
        eel.set_split_conversation_state(conversationId, null, normalized)().catch(error => {
            console.error('Failed to save split pane width:', error);
        });
    }
    return normalized;
}

function hideSplitTaskPane() {
    const workspace = document.getElementById('splitWorkspace');
    const frame = document.getElementById('splitTaskFrame');
    if (!workspace) return;
    setSplitChildAgentDetailOpen(false);
    setSplitChildBrowserPreviewOpen(false);
    if (frame) frame.src = 'about:blank';
    workspace.hidden = true;
    document.body.classList.remove('split-workspace-open');
}

async function closeSplitTask() {
    if (splitPaneMode) return;
    const conversationId = activeConversationId;
    hideSplitTaskPane();
    if (conversationId && canCallEel()) {
        try {
            await eel.set_split_conversation_state(conversationId, false, null)();
        } catch (error) {
            console.error('Failed to close persisted split pane:', error);
        }
    }
    document.getElementById('splitTaskButton')?.focus();
}

async function deleteSplitTask() {
    if (splitPaneMode) return;
    const sourceConversationId = activeConversationId;
    if (!sourceConversationId || !canCallEel()) return;
    const confirmed = await showConfirmDialog(
        '删除当前子任务及其全部对话和短期记忆？此操作不可撤销。'
    );
    if (!confirmed || sourceConversationId !== activeConversationId) return;

    splitStateGeneration += 1;
    hideSplitTaskPane();
    try {
        const result = await eel.delete_split_conversation(sourceConversationId)();
        if (!result?.success) {
            throw new Error(result?.error || '删除子任务失败');
        }
        const deletedConversationIds = Array.from(new Set(
            (result.deleted_conversation_ids || []).map(String)
        ));
        deletedConversationIds.forEach(deletedId => {
            conversationExecutionStates.delete(deletedId);
            clearConversationPlanProgress(deletedId);
            clearConversationAgentTeams(deletedId);
        });
        await refreshConversations(sourceConversationId);
        showToast('子任务及其独立记忆已删除', 'success');
        document.getElementById('splitTaskButton')?.focus();
    } catch (error) {
        await restoreSplitTaskForConversation(sourceConversationId);
        showToast(`删除子任务失败：${error.message}`, 'error');
    }
}

function showSplitTaskPane(conversationId, width = 0) {
    const workspace = document.getElementById('splitWorkspace');
    const frame = document.getElementById('splitTaskFrame');
    if (!workspace || !frame || !conversationId) return;
    workspace.hidden = false;
    document.body.classList.add('split-workspace-open');
    setSplitPaneWidth(width || SPLIT_PANE_DEFAULT_WIDTH, {persist: false});
    const nextUrl = splitTaskUrl(conversationId);
    if (frame.src !== nextUrl) frame.src = nextUrl;
}

async function restoreSplitTaskForConversation(conversationId) {
    if (splitPaneMode) return;
    const generation = ++splitStateGeneration;
    hideSplitTaskPane();
    if (!conversationId || !canCallEel()) return;
    try {
        const state = await eel.get_split_conversation_state(conversationId)();
        if (generation !== splitStateGeneration || conversationId !== activeConversationId) return;
        if (state?.success && state.open && state.conversation_id) {
            showSplitTaskPane(state.conversation_id, state.width);
        }
    } catch (error) {
        console.error('Failed to restore split pane:', error);
    }
}

function initializeSplitResizeHandle(handle) {
    if (!handle || splitPaneMode) return;
    let pointerId = null;

    const finishResize = () => {
        document.body.classList.remove('is-resizing-split');
        if (pointerId === null) return;
        const capturedPointerId = pointerId;
        pointerId = null;
        try {
            if (handle.hasPointerCapture(capturedPointerId)) {
                handle.releasePointerCapture(capturedPointerId);
            }
        } catch (_error) {
            // Capture may already be gone after crossing into the child frame.
        }
        const width = parseFloat(
            document.getElementById('splitWorkspace')?.style.getPropertyValue('--split-pane-width')
        );
        if (width) setSplitPaneWidth(width);
    };
    const updateFromPointer = event => {
        if (pointerId === null || window.innerWidth <= 780) return;
        setSplitPaneWidth(window.innerWidth - event.clientX, {persist: false});
    };

    handle.addEventListener('pointerdown', event => {
        if (window.innerWidth <= 780 || event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        handle.setPointerCapture(pointerId);
        document.body.classList.add('is-resizing-split');
        updateFromPointer(event);
    });
    handle.addEventListener('pointermove', updateFromPointer);
    installPointerResizeCleanup(handle, finishResize);
    handle.addEventListener('keydown', event => {
        const workspace = document.getElementById('splitWorkspace');
        const current = parseFloat(workspace?.style.getPropertyValue('--split-pane-width'))
            || SPLIT_PANE_DEFAULT_WIDTH;
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setSplitPaneWidth(current + SPLIT_PANE_WIDTH_STEP);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            setSplitPaneWidth(current - SPLIT_PANE_WIDTH_STEP);
        } else if (event.key === 'Home') {
            event.preventDefault();
            setSplitPaneWidth(SPLIT_PANE_MIN_WIDTH);
        } else if (event.key === 'End') {
            event.preventDefault();
            setSplitPaneWidth(getSplitPaneWidthLimit());
        }
    });
}

async function openSplitTask() {
    if (splitPaneMode) return;
    if (!activeConversationId || !canCallEel()) return;
    const sourceConversationId = activeConversationId;
    const button = document.getElementById('splitTaskButton');
    const workspace = document.getElementById('splitWorkspace');
    const frame = document.getElementById('splitTaskFrame');
    if (!workspace || !frame) return;
    button?.setAttribute('aria-busy', 'true');
    button && (button.disabled = true);
    try {
        const result = await eel.create_split_conversation(sourceConversationId)();
        if (!result?.success || !result.conversation?.id) {
            throw new Error(result?.error || '无法创建子任务');
        }
        if (sourceConversationId !== activeConversationId) return;
        showSplitTaskPane(
            result.conversation.id,
            result.split_state?.width || SPLIT_PANE_DEFAULT_WIDTH
        );
        await refreshConversations(sourceConversationId);
        showToast(
            result.created
                ? '已创建独立子任务，并复制当前短期记忆快照'
                : '已恢复原子任务，继续使用其独立记忆',
            'success'
        );
    } catch (error) {
        showToast(`打开子任务失败：${error.message}`, 'error');
    } finally {
        button?.removeAttribute('aria-busy');
        if (button) button.disabled = false;
    }
}

function renderConversation(conversation) {
    isRestoringConversation = true;
    try {
        activeConversationId = conversation?.id || activeConversationId;
        markConversationReadLocally(activeConversationId);
        updateActiveProjectLabel(conversation);
        const messages = conversation?.messages || [];
        resetConversationView(conversation);
        updateActiveTaskTitle(conversation?.title || '新任务');
        const latestPlan = getLatestConversationPlan(messages);
        const activeExecution = getActiveExecutionState();
        const planMatchesActiveRun = !activeExecution?.running
            || latestPlan?.messageId === Number(activeExecution.messageId || 0);
        if (latestPlan && planMatchesActiveRun) {
            activePlanProgress.set(
                planProgressKey(latestPlan.conversationId, latestPlan.messageId),
                latestPlan
            );
            renderPlanProgress(latestPlan);
        }
        if (!messages.length) return;

        const chatMessages = document.getElementById('chatMessages');
        chatMessages.classList.remove('is-welcome');
        chatMessages.innerHTML = '';
        renderConversationSliced(chatMessages, messages);
        pinChatToBottom(chatMessages, {force: true});
    } finally {
        isRestoringConversation = false;
        renderConversationList();
        syncPreviewSessions(activeConversationId);
        // Historical compression cards must never leave the global activity
        // indicator in a running state after a task switch or reload.
        syncActiveConversationProcessingUI();
        if (!isProcessing && isInitialized) setAppStatus('ready', '就绪');
        refreshTaskRollbackButtons(activeConversationId);
    }
}

function renderConversationEvents(events) {
    const finalByMessageId = new Map();
    const pendingKnowledge = new Map();
    for (const event of events) {
        const messageId = Number(event.message_id || 0);
        if (event.type === 'user') {
            addUserMessage(
                event.content || '请解析附件',
                event.attachments || [],
                messageId,
                false
            );
        } else if (event.type === 'assistant') {
            const {thoughts, answer} = splitThinkingContent(event.content || '');
            const thinkingDurationMs = getPersistedThinkingDuration(event);
            thoughts.forEach(thought => addThinkingCard(
                thought, null, false, false, true, thinkingDurationMs
            ));
            const element = addMessage(
                'ai',
                answer.trim() || event.content || '',
                Boolean(event.is_error),
                false
            );
            finalByMessageId.set(messageId, element);
            if (pendingKnowledge.has(messageId)) {
                addKnowledgePanel(pendingKnowledge.get(messageId), element);
                pendingKnowledge.delete(messageId);
            }
        } else if (event.type === 'thinking') {
            const parsed = splitThinkingContent(event.content || '');
            const thoughts = parsed.thoughts.length
                ? parsed.thoughts
                : [parsed.answer || event.content || ''];
            thoughts.filter(Boolean).forEach(thought => addThinkingCard(
                thought,
                null,
                false,
                false,
                true,
                getPersistedThinkingDuration(event)
            ));
        } else if (event.type === 'commentary') {
            addCommentaryMessage(event.content || '', false);
        } else if (event.type === 'agent_team') {
            updateAgentTeamSnapshot(
                event,
                activeConversationId,
                messageId,
                {animate: false}
            );
        } else if (event.type === 'tool') {
            if (!isQuestionToolName(event.tool)) {
                addToolMessage(
                    event.tool || 'Tool',
                    event.content || '',
                    false,
                    Number(event.duration_ms || 0),
                    event.target || '',
                    event.actor || 'primary'
                );
            }
        } else if (event.type === 'modified_files') {
            addModifiedFilesSummary(event, false);
        } else if (event.type === 'compression') {
            finishCompressionActivity({
                ...event,
                message: event.content || '记忆压缩已结束',
            }, messageId);
        } else if (event.type === 'question') {
            addAnsweredQuestionCard(
                event.questions || [],
                event.answers || [],
                messageId,
                event.question_id || '',
                event.supplements || []
            );
        } else if (event.type === 'preview') {
            upsertProjectPreview({
                ...event,
                conversation_id: event.conversation_id || activeConversationId || '',
            }, false);
        } else if (event.type === 'plan_update') {
            continue;
        } else if (event.type === 'knowledge' && showKnowledgeAppendix) {
            const anchor = finalByMessageId.get(messageId);
            if (anchor) addKnowledgePanel(event.content || '', anchor);
            else pendingKnowledge.set(messageId, event.content || '');
        }
    }
}
async function sendMessage() {
    if (!isInitialized) return;

    const activeState = getActiveExecutionState();
    if (activeState?.running && activeState.awaitingQuestion && !activeState.outputStopped) {
        showToast('请先完成当前问题选择，或停止任务', 'info');
        return;
    }

    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    const attachments = composerAttachments.slice();
    const planMode = planModeEnabled;
    const voiceMode = voiceModeActive;
    const multiAgentMode = multiAgentModeEnabled;
    const allowAll = autoAllowAll;

    if (!message && !attachments.length) return;

    if (!eelBridgeReady()) {
        autoRecoverEelBridge(
            message,
            attachments,
            String(activeConversationId || ''),
            planMode,
            voiceMode,
            multiAgentMode,
            allowAll,
            appMode
        );
        return;
    }

    const pendingStop = pendingStopRequests.get(String(activeConversationId || ''));
    if (pendingStop) {
        try {
            await pendingStop;
        } catch (_error) {
            // The normal send error path below will report any remaining busy state.
        }
    }

    // A task keeps its own execution lane. New messages for that same task wait,
    // while another task can start immediately and run independently.
    if (activeState?.running) {
        messageQueue.push({
            conversationId: String(activeConversationId || ''),
            message,
            attachments,
            planMode,
            voiceMode,
            multiAgentMode,
            allowAll,
            mode: appMode,
        });
        messageInput.value = '';
        resetComposerInput(messageInput);
        clearComposerAttachments();
        updateQueueDisplay();
        showToast(
            activeState.outputStopped
                ? '已停止输出，新消息将在后台释放后立即发送'
                : `当前任务的新消息已进入等待队列（${queuedCountForConversation(activeConversationId)}）`,
            'info',
            1800
        );
        dispatchNextQueuedMessage();
        return;
    }
    // Stop is optimistic: the backend releases this conversation immediately.
    // Do not let an in-flight sidebar refresh resurrect the cancelled run and
    // force the next message back into the queue.
    conversationRefreshGeneration += 1;

    // 生成新的消息ID
    currentMessageId = Date.now();
    const conversationId = String(activeConversationId || '');
    updateConversationExecutionState(conversationId, {
        messageId: currentMessageId,
        running: true,
        stopping: false,
        outputStopped: false,
        awaitingQuestion: false,
        awaitingApproval: false,
        unreadCompletion: false,
    });
    renderPlanProgress(null);
    resetTrackedExecutionActivity(getConversationExecutionState(conversationId, false));

    hideQuickCommands();

    messageInput.value = '';
    resetComposerInput(messageInput);
    clearComposerAttachments();
    updateProcessingUI(true);

    hideWelcome();

    addUserMessage(message || '请解析附件', attachments, currentMessageId);
    showThinking();

    try {
        const result = await eel.send_message(
            message || '请解析并说明附件内容',
            currentMessageId,
            buildAttachmentPayload(attachments),
            conversationId,
            planMode,
            voiceMode,
            multiAgentMode,
            allowAll,
            appMode
        )();
        if (result?.status === 'busy') {
            throw new Error(result.error || '已有任务正在执行');
        }
        if (result?.status === 'error') {
            throw new Error(result.error || '任务提交失败');
        }
        updateConversationListItemState(conversationId, {
            running: true,
            active_message_id: currentMessageId,
            unread_completion: false,
        });
        if (!activeState?.outputStopped) {
            refreshConversations(activeConversationId).catch(console.error);
        }
        ensureExecutionPolling(conversationId, currentMessageId);
    } catch (error) {
        if (handleEelConnectionError(error) || !eelBridgeReady()) {
            autoRecoverEelBridge(
                message,
                attachments,
                String(conversationId || ''),
                planMode,
                voiceMode,
                multiAgentMode,
                allowAll,
                appMode
            );
            return;
        }
        removeThinking();
        addMessage('ai', '任务提交失败：' + error.message, true);
        composerAttachments = attachments;
        renderComposerAttachments();
        updateComposerSendState();
        updateConversationExecutionState(conversationId, {running: false});
        syncActiveConversationProcessingUI();
        renderConversationList();
    }
}

// 直接发送指定消息（用于队列自动发送）
async function sendMessageWithText(
    message,
    attachments = [],
    conversationId = activeConversationId,
    planMode = planModeEnabled,
    voiceMode = voiceModeActive,
    multiAgentMode = multiAgentModeEnabled,
    allowAll = autoAllowAll,
    mode = appMode
) {
    if (!isInitialized || (!message && !attachments.length)) return;

    // 生成新的消息ID
    const targetConversationId = String(conversationId || activeConversationId || '');

    if (!eelBridgeReady()) {
        autoRecoverEelBridge(
            message,
            attachments,
            targetConversationId,
            planMode,
            voiceMode,
            multiAgentMode,
            allowAll,
            mode
        );
        return;
    }

    const messageId = Date.now();
    const renderTarget = targetConversationId === String(activeConversationId || '');
    if (renderTarget) currentMessageId = messageId;
    updateConversationExecutionState(targetConversationId, {
        messageId,
        running: true,
        stopping: false,
        outputStopped: false,
        awaitingQuestion: false,
        awaitingApproval: false,
        unreadCompletion: false,
    });
    if (renderTarget) renderPlanProgress(null);
    resetTrackedExecutionActivity(
        getConversationExecutionState(targetConversationId, false)
    );

    if (renderTarget) {
        updateProcessingUI(true);
        hideWelcome();
        addUserMessage(message || '请解析附件', attachments, messageId);
        showThinking();
    }
    renderConversationList();

    try {
        const result = await eel.send_message(
            message || '请解析并说明附件内容',
            messageId,
            buildAttachmentPayload(attachments),
            targetConversationId,
            Boolean(planMode),
            Boolean(voiceMode),
            Boolean(multiAgentMode),
            Boolean(allowAll),
            mode
        )();
        if (result?.status === 'busy') {
            // 暂停/停止释放竞态：后端任务尚未真正释放（_begin_execution 仍
            // 认为该对话有 running/waiting 任务）。不当作失败——移除刚显示
            // 的气泡，把消息放回等待队列，任务释放后由队列自动重发。
            if (renderTarget) removeThinking();
            const bubble = document.querySelector(`.message.user[data-message-id="${messageId}"]`);
            if (bubble) bubble.remove();
            updateConversationExecutionState(targetConversationId, {running: false});
            syncActiveConversationProcessingUI();
            messageQueue.unshift({
                conversationId: targetConversationId,
                message,
                attachments,
                planMode: Boolean(planMode),
                voiceMode: Boolean(voiceMode),
                multiAgentMode: Boolean(multiAgentMode),
                allowAll: Boolean(allowAll),
                mode,
            });
            updateQueueDisplay();
            setTimeout(dispatchNextQueuedMessage, 400);
            return;
        }
        if (result?.status === 'error') {
            throw new Error(result.error || '任务提交失败');
        }
        updateConversationListItemState(targetConversationId, {
            running: true,
            active_message_id: messageId,
            unread_completion: false,
        });
        refreshConversations(activeConversationId).catch(console.error);
        ensureExecutionPolling(targetConversationId, messageId);
    } catch (error) {
        if (handleEelConnectionError(error) || !eelBridgeReady()) {
            autoRecoverEelBridge(
                message,
                attachments,
                targetConversationId,
                planMode,
                voiceMode,
                multiAgentMode,
                allowAll,
                mode
            );
            return;
        }
        if (renderTarget) {
            removeThinking();
            addMessage('ai', '任务提交失败：' + error.message, true);
        } else {
            showToast(`后台任务提交失败：${error.message}`, 'error');
        }
        updateConversationExecutionState(targetConversationId, {running: false});
        syncActiveConversationProcessingUI();
        renderConversationList();
        if (messageQueue.length > 0) setTimeout(dispatchNextQueuedMessage, 120);
    }
}

function shouldRenderExecution(conversationId, state = null) {
    const execution = state || getConversationExecutionState(conversationId, false);
    return String(conversationId || '') === String(activeConversationId || '')
        && !execution?.outputStopped
        && !execution?.liveRenderSuppressed;
}

function ensureExecutionPolling(conversationId, msgId) {
    const id = String(conversationId || '');
    const messageId = Number(msgId || 0);
    if (!id || !messageId) return;
    const existing = executionPollers.get(id);
    if (existing?.messageId === messageId) return;
    if (existing) invalidatePolling(id);
    startPolling(id, messageId);
}

function startPolling(conversationId, msgId) {
    const executionId = String(conversationId || '');
    const messageId = Number(msgId || 0);
    updateConversationExecutionState(executionId, {messageId, running: true});
    const poller = {
        conversationId: executionId,
        messageId,
        intervalId: null,
        inFlight: false,
        terminalEventSeen: false,
        consecutiveErrors: 0,
    };
    executionPollers.set(executionId, poller);
    const intervalId = setInterval(async () => {
        if (executionPollers.get(executionId) !== poller) {
            clearInterval(intervalId);
            return;
        }
        if (poller.inFlight) return;
        poller.inFlight = true;
        try {
            const results = typeof eel.get_next_results === 'function'
                ? await eel.get_next_results(executionId, messageId, 50)()
                : [await eel.get_next_result(executionId, messageId)()].filter(Boolean);
            if (executionPollers.get(executionId) !== poller) return;
            if (results.length) {
                poller.consecutiveErrors = 0;
                for (const result of results) {
                    handleResult(result, messageId, executionId);
                    if (isTerminalTaskEvent(result)) {
                        poller.terminalEventSeen = true;
                    }
                }
            }
            const status = await eel.get_execution_status(executionId, messageId)();
            if (executionPollers.get(executionId) !== poller) return;
            if (status?.agent_team) {
                updateAgentTeamSnapshot(
                    status.agent_team,
                    executionId,
                    messageId,
                    {animate: false}
                );
            }

            // The backend may still persist task-end events after the model is
            // done. Keep polling for those events, but never keep the composer
            // or Stop button in a running state after `running` becomes false.
            const backendFinalizationPending = !status?.running
                && status?.finalized === false;
            const displayRunning = Boolean(status?.running);

            const state = updateConversationExecutionState(executionId, {
                messageId,
                running: displayRunning,
                stopping: Boolean(status?.stopping),
                awaitingApproval: Boolean(status?.awaiting_approval),
                awaitingQuestion: Boolean(status?.awaiting_question),
            });
            updateConversationListItemState(executionId, {
                running: displayRunning,
                stopping: Boolean(status?.stopping),
                active_message_id: displayRunning ? messageId : 0,
                awaiting_question: Boolean(status?.awaiting_question),
                awaiting_approval: Boolean(status?.awaiting_approval),
            });
            if (state && !state.running) state.liveRenderSuppressed = false;
            const renderLive = shouldRenderExecution(executionId, state);
            const awaitingApproval = Boolean(status?.awaiting_approval);
            const awaitingQuestion = Boolean(status?.awaiting_question);

            if (awaitingApproval || awaitingQuestion) {
                poller.terminalEventSeen = false;
                if (renderLive) {
                    if (awaitingApproval) restorePendingApproval(status, executionId);
                    if (awaitingQuestion) restorePendingQuestion(status, executionId);
                    syncActiveConversationProcessingUI();
                }
                return;
            }

            if (!status?.running) {
                const lateResult = await drainLateTaskResults(
                    executionId, messageId, poller
                );
                if (!lateResult.valid) return;
                // The final assistant event is terminal, but the backend can
                // append a task-end modified-files summary immediately after it.
                // Drain until the queue is empty before ending this poller.
                if (lateResult.hadResults && !poller.terminalEventSeen) return;
                finishCurrentMessage(executionId, messageId);
                return;
            }

            if (renderLive) syncActiveConversationProcessingUI();
        } catch (e) {
            if (executionPollers.get(executionId) !== poller) return;
            console.error('Poll error:', e);
            poller.consecutiveErrors += 1;
            if (poller.consecutiveErrors >= 5) {
                if (shouldRenderExecution(executionId)) {
                    removeThinking();
                    addMessage('ai', '桌面端与执行服务连接中断，请检查日志后重试。', true);
                }
                finishCurrentMessage(
                    executionId,
                    messageId,
                    'error',
                    '桌面端与执行服务连接中断'
                );
            }
        } finally {
            poller.inFlight = false;
        }
    }, 90);
    poller.intervalId = intervalId;
}

function isTerminalTaskEvent(result) {
    return result?.type === 'final'
        || result?.type === 'error'
        || (result?.type === 'compression_end' && !result.task_continues)
        || (result?.type === 'stream_end'
            && result.target === 'final'
            && !result.task_continues);
}

async function drainLateTaskResults(conversationId, msgId, poller) {
    let hadResults = false;
    for (let batch = 0; batch < 8; batch += 1) {
        const results = typeof eel.get_next_results === 'function'
            ? await eel.get_next_results(conversationId, msgId, 64)()
            : [await eel.get_next_result(conversationId, msgId)()].filter(Boolean);
        if (executionPollers.get(String(conversationId || '')) !== poller) {
            return {valid: false, terminal: false, hadResults};
        }
        if (!results.length) break;
        hadResults = true;
        for (const result of results) {
            handleResult(result, msgId, conversationId);
            if (isTerminalTaskEvent(result)) poller.terminalEventSeen = true;
        }
    }
    return {valid: true, hadResults};
}

// Compatibility marker for the former single-task polling contract:
// await drainLateTaskResults(msgId, generation)
// else if (!activeCompressionActivities.size)

async function restoreExecutionState() {
    try {
        const runningItems = conversations.filter(item => item.running);
        await Promise.all(runningItems.map(async item => {
            const conversationId = String(item.id || '');
            const hintedMessageId = Number(item.active_message_id || item.message_id || 0);
            const status = await eel.get_execution_status(
                conversationId, hintedMessageId
            )();
            const messageId = Number(
                status?.pending_question?.message_id
                || status?.pending_approval?.message_id
                || status?.message_id
                || hintedMessageId
                || 0
            );
            if (status?.agent_team && conversationId && messageId) {
                updateAgentTeamSnapshot(
                    status.agent_team,
                    conversationId,
                    messageId,
                    {animate: false}
                );
            }
            if (!status?.running || !conversationId || !messageId) return;

            const state = updateConversationExecutionState(conversationId, {
                messageId,
                running: true,
                stopping: Boolean(status.stopping),
                awaitingQuestion: Boolean(status.awaiting_question),
                awaitingApproval: Boolean(status.awaiting_approval),
                liveRenderSuppressed: true,
            });
            if (conversationId === String(activeConversationId || '')) {
                currentMessageId = messageId;
                state.liveRenderSuppressed = false;
                syncActiveConversationProcessingUI({showPlaceholder: true});
                if (status.awaiting_approval) {
                    restorePendingApproval(status, conversationId);
                }
                if (status.awaiting_question) {
                    restorePendingQuestion(status, conversationId);
                }
            }
            ensureExecutionPolling(state.conversationId, messageId);
        }));
        renderConversationList();
    } catch (error) {
        console.error('Failed to restore execution state:', error);
    }
}

function restorePendingApproval(status, conversationId = activeConversationId) {
    if (!status?.awaiting_approval) return false;
    if (String(conversationId || '') !== String(activeConversationId || '')) return false;

    const pending = status.pending_approval;
    if (!pending?.tool) return false;

    const messageId = Number(pending.message_id || status.message_id || currentMessageId || 0);
    const approvalId = String(
        pending.prepared_tool_call_id || pending.tool_call_id || `approval-${messageId}`
    );
    cancelSiblingPreparedToolExecutions(pending, messageId);
    const existing = document.querySelector('.approval-container');
    if (existing?.dataset.approvalId === approvalId) {
        setAppStatus('busy', '等待确认');
        return true;
    }

    removeThinking();
    if (messageId) currentMessageId = messageId;
    const chatMessages = document.getElementById('chatMessages');
    chatMessages?.classList.remove('is-welcome');
    chatMessages?.querySelector('.welcome-message')?.remove();
    showApproval(pending.tool, pending.params || {}, '', approvalId);
    setAppStatus('busy', '等待确认');
    return true;
}

function restorePendingQuestion(status, conversationId = activeConversationId) {
    if (!status?.awaiting_question) return false;
    if (String(conversationId || '') !== String(activeConversationId || '')) return false;

    const pending = status.pending_question;
    if (!pending || !Array.isArray(pending.questions)) return false;

    const messageId = Number(pending.message_id || status.message_id || currentMessageId || 0);
    const questionId = String(
        pending.prepared_tool_call_id || pending.tool_call_id || `question-${messageId}`
    );
    cancelSiblingPreparedToolExecutions(pending, messageId);
    const existing = document.querySelector('.question-prompt:not(.is-submitted)');
    if (existing?.dataset.questionId === questionId) {
        isAwaitingQuestion = true;
        setAppStatus('busy', '等待回答');
        return true;
    }

    try {
        removeThinking();
        isAwaitingQuestion = true;
        if (messageId) currentMessageId = messageId;
        const chatMessages = document.getElementById('chatMessages');
        chatMessages?.classList.remove('is-welcome');
        chatMessages?.querySelector('.welcome-message')?.remove();
        showQuestionPrompt(pending.questions, messageId, true, questionId);
        setAppStatus('busy', '等待回答');
        return true;
    } catch (error) {
        console.error('Failed to restore question prompt:', error);
        showQuestionRenderError(error.message || '问题数据格式错误');
        return false;
    }
}

function finishCurrentMessage(
    conversationId = activeConversationId,
    msgId = currentMessageId,
    terminalState = 'complete',
    terminalMessage = '任务已结束'
) {
    const id = String(conversationId || '');
    markPlanProgressTerminal(id, msgId, terminalState, terminalMessage);
    if (terminalState === 'error') markAgentTeamsTerminal(id, msgId, 'failed');
    if (terminalState === 'stopped') markAgentTeamsTerminal(id, msgId, 'cancelled');
    const state = updateConversationExecutionState(id, {
        messageId: Number(msgId || 0),
        running: false,
        stopping: false,
        outputStopped: false,
        awaitingQuestion: false,
        awaitingApproval: false,
        liveRenderSuppressed: false,
        unreadCompletion: id !== String(activeConversationId || ''),
    });
    resetTrackedExecutionActivity(state);
    updateConversationListItemState(id, {
        running: false,
        stopping: false,
        active_message_id: 0,
        unread_completion: id !== String(activeConversationId || ''),
    });
    const isVisible = id === String(activeConversationId || '');
    invalidatePolling(id);
    if (isVisible) {
        removeThinking();
        finalizeVisibleStreamingResponses();
        updateProcessingUI(false);
        if (isAwaitingQuestion) finalizePendingQuestion('任务已停止');
        isAwaitingQuestion = false;
        document.querySelector('.approval-container')?.remove();
        finishActiveToolExecutions('执行已结束');
        if (!voiceModeActive) document.getElementById('messageInput').focus();
    }
    if (state) renderConversationList();
    refreshConversations(activeConversationId).catch(error => {
        console.error('Failed to refresh task history:', error);
    });
    // Reconcile only the task-end summary. Rebuilding the whole conversation
    // here clears the live DOM, causes a visible scroll jump, and can race with
    // the last queued event even though the summary is already persisted.
    if (isVisible && id) {
        eel.load_conversation(id)().then(result => {
            if (String(activeConversationId || '') !== id) return;
            if (!result?.success) return;
            const messageId = Number(msgId || 0);
            const summary = [...(result.conversation?.messages || [])]
                .reverse()
                .find(event => event?.type === 'modified_files'
                    && Number(event.message_id || 0) === messageId);
            if (summary) addModifiedFilesSummary(summary, false);
        }).catch(error => {
            if (!handleEelConnectionError(error)) {
                console.error('Failed to restore task-end summary:', error);
            }
        });
    }

    if (messageQueue.length > 0) dispatchNextQueuedMessage();
}

function invalidatePolling(conversationId = activeConversationId) {
    const id = String(conversationId || '');
    if (!id) return;
    const poller = executionPollers.get(id);
    if (poller?.intervalId) clearInterval(poller.intervalId);
    executionPollers.delete(id);
}

async function dispatchNextQueuedMessage() {
    if (messageQueue.length === 0) return;
    try {
        const queuedIndex = messageQueue.findIndex(item => {
            const conversationId = typeof item === 'string'
                ? String(activeConversationId || '')
                : String(item.conversationId || activeConversationId || '');
            return !isConversationRunning(conversationId);
        });
        if (queuedIndex < 0) {
            setTimeout(dispatchNextQueuedMessage, 180);
            return;
        }
        const queued = messageQueue[queuedIndex];
        const conversationId = typeof queued === 'string'
            ? String(activeConversationId || '')
            : String(queued.conversationId || activeConversationId || '');
        const status = await eel.get_execution_status(conversationId, 0)();
        if (status?.running) {
            updateConversationExecutionState(conversationId, {
                messageId: Number(status.message_id || 0),
                running: true,
            });
            setTimeout(dispatchNextQueuedMessage, 180);
            return;
        }
        messageQueue.splice(queuedIndex, 1);
        updateQueueDisplay();
        if (typeof queued === 'string') {
            sendMessageWithText(queued);
        } else {
            sendMessageWithText(
                queued.message,
                queued.attachments || [],
                queued.conversationId || activeConversationId,
                typeof queued.planMode === 'boolean' ? queued.planMode : planModeEnabled,
                typeof queued.voiceMode === 'boolean' ? queued.voiceMode : false,
                typeof queued.multiAgentMode === 'boolean'
                    ? queued.multiAgentMode
                    : multiAgentModeEnabled,
                typeof queued.allowAll === 'boolean' ? queued.allowAll : autoAllowAll,
                queued.mode || appMode
            );
        }
    } catch (error) {
        console.error('Queue dispatch error:', error);
        showToast('等待任务启动失败，请手动重试', 'error');
    }
}

function handleResult(result, msgId, conversationId = activeConversationId) {
    if (result?.type === 'preview') {
        const conversationId = String(result.conversation_id || '');
        if (!conversationId || conversationId === String(activeConversationId || '')) {
            upsertProjectPreview(result);
        }
        return;
    }

    const executionId = String(
        result?.conversation_id || conversationId || activeConversationId || ''
    );
    if (result?.type === 'plan_update') {
        updatePlanProgress(result, executionId, Number(result.message_id || msgId || 0));
        return;
    }
    if (result?.type === 'agent_team_update') {
        updateAgentTeamSnapshot(
            result,
            executionId,
            Number(result.message_id || msgId || 0)
        );
        return;
    }
    if (
        ['tool_preparing', 'tool_start', 'tool'].includes(result?.type)
        && (isQuestionToolName(result.tool) || !isPrimaryToolEvent(result))
    ) {
        return;
    }
    const state = getConversationExecutionState(executionId, false);
    trackExecutionResult(state, result);
    if (!shouldRenderExecution(executionId, state)) return;
    currentMessageId = Number(msgId || currentMessageId || 0);

    // Handle different step types
    if (result.type === 'thinking') {
        removeThinking();
        addThinkingMessage(result.content);
        showThinking(); // Show loading for next step
    } else if (result.type === 'tool_preparing') {
        removeThinking();
        markStreamingCommentary(result.stream_id);
        startToolExecution(result, msgId, true);
    } else if (result.type === 'tool_start') {
        removeThinking();
        startToolExecution(result, msgId);
    } else if (result.type === 'tool') {
        removeThinking();
        finishToolExecution(result, msgId);
        showThinking(); // Show loading for next step
        updateTokenIndicator(); // 更新token
    } else if (result.type === 'modified_files') {
        removeThinking();
        addModifiedFilesSummary(result);
    } else if (result.type === 'pending_approval') {
        removeThinking();
        cancelSiblingPreparedToolExecutions(result, msgId);
        showApproval(
            result.tool,
            result.params,
            result.thinking,
            result.prepared_tool_call_id || result.tool_call_id || `approval-${msgId}`
        );
        setAppStatus('busy', '等待确认');
    } else if (result.type === 'pending_question') {
        removeThinking();
        cancelSiblingPreparedToolExecutions(result, msgId);
        try {
            isAwaitingQuestion = true;
            showQuestionPrompt(
                result.questions || [],
                msgId,
                true,
                result.prepared_tool_call_id || result.tool_call_id || ''
            );
        } catch (error) {
            console.error('Failed to render question prompt:', error);
            showQuestionRenderError(error.message || '问题数据格式错误');
        }
        setAppStatus('busy', '等待回答');
    } else if (result.type === 'question_answered') {
        isAwaitingQuestion = false;
        renderQuestionResult(
            result.questions || [],
            result.answers || [],
            msgId,
            result.question_id || '',
            document.querySelector('.question-prompt:not(.is-submitted)'),
            result.supplements || []
        );
        showThinking();
    } else if (result.type === 'compression_start') {
        removeThinking();
        startCompressionActivity(result, msgId);
    } else if (result.type === 'compression_progress') {
        updateCompressionActivity(result, msgId);
    } else if (result.type === 'compression_end') {
        removeThinking();
        const compressionElement = finishCompressionActivity(result, msgId);
        if (!result.task_continues) {
            completedMessageByMessageId.set(msgId, compressionElement);
        }
        updateTokenIndicator();
        if (result.task_continues) {
            showThinking();
            setAppStatus('busy', '正在继续任务');
        }
    } else if (result.type === 'compressing') {
        removeThinking();
        startCompressionActivity({
            ...result,
            compression_id: `legacy:${msgId}`,
            mode: 'manual',
        }, msgId);
    } else if (result.type === 'stream') {
        removeThinking();
        appendStreamingResponse(result.stream_id, result.content || '');
    } else if (result.type === 'stream_end') {
        removeThinking();
        finalizeStreamingResponse(result, msgId);
    } else if (result.type === 'attachments') {
        updateMessageAttachments(msgId, result.attachments || []);
    } else if (result.type === 'final') {
        removeThinking();
        const finalMessage = addAssistantResponse(result.content);
        speakVoiceResponse(result.content, msgId);
        completedMessageByMessageId.set(msgId, finalMessage);
        flushPendingKnowledge(msgId, finalMessage);
        updateTokenIndicator(); // 更新token
    } else if (result.type === 'knowledge') {
        if (!showKnowledgeAppendix) return;
        removeThinking();
        const finalMessage = completedMessageByMessageId.get(msgId);
        if (finalMessage) {
            addKnowledgePanel(result.content || '', finalMessage);
        } else {
            pendingKnowledgeByMessageId.set(msgId, result.content || '');
        }
    } else if (result.type === 'error') {
        removeThinking();
        removeStreamingResponses();
        finishActiveToolExecutions('执行中断', true);
        failActiveCompressionActivities(result.content || '执行中断');
        markPlanProgressTerminal(
            executionId, msgId, 'error', result.content || '执行中断'
        );
        markAgentTeamsTerminal(executionId, msgId, 'failed');
        addMessage('ai', '执行失败：' + result.content, true);
    }
}

function showApproval(toolName, params, thinking, approvalId = '') {
    const normalizedApprovalId = String(approvalId || '');
    const existing = document.querySelector('.approval-container');
    if (existing?.dataset.approvalId === normalizedApprovalId) return existing;
    existing?.remove();
    const chatMessages = document.getElementById('chatMessages');
    const approvalDiv = document.createElement('div');
    approvalDiv.className = 'approval-container';
    approvalDiv.dataset.approvalId = normalizedApprovalId;

    const paramsText = Object.entries(params || {})
        .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
        .join('\n');

    approvalDiv.innerHTML = `
        <div class="approval-content">
            <div class="approval-header">
                <span class="approval-icon">⚠️</span>
                <span>确认敏感操作</span>
            </div>
            <div class="approval-tool">${escapeHtml(toolName)}</div>
            <pre class="approval-params">${escapeHtml(paramsText)}</pre>
            <div class="approval-buttons">
                <button class="btn-approve" onclick="approveTool('approve')">仅本次执行</button>
                <button class="btn-allow-all" onclick="approveTool('all')">本次任务全部允许</button>
                <button class="btn-deny" onclick="approveTool('deny')">取消</button>
            </div>
        </div>
    `;

    chatMessages.appendChild(approvalDiv);
    requestAnimationFrame(() => approvalDiv.classList.add('is-visible'));
    followChatOutput(chatMessages);
    return approvalDiv;
}

async function approveTool(action) {
    const state = getActiveExecutionState();
    if (!state?.running) return;
    const conversationId = state.conversationId;
    const messageId = Number(state.messageId || currentMessageId || 0);
    invalidatePolling(conversationId);
    // Remove approval UI
    const approvalEl = document.querySelector('.approval-container');
    if (approvalEl) approvalEl.remove();

    showThinking();

    try {
        const result = await eel.approve_tool(action, conversationId, messageId)();
        if (!result?.success) throw new Error(result?.error || '确认失败');
        state.awaitingApproval = false;
        ensureExecutionPolling(conversationId, messageId);
    } catch (error) {
        removeThinking();
        addMessage('ai', '确认失败：' + error.message, true);
        finishCurrentMessage(
            conversationId, messageId, 'error', `确认失败：${error.message}`
        );
    }
}

async function rollbackTaskCard(summary) {
    const button = summary?.querySelector?.('.modified-files-rollback');
    if (!button || button.disabled) return;
    const result = summary._modifiedFilesResult || {};
    const conversationId = String(
        result.conversation_id || activeConversationId || ''
    );
    const messageId = Number(
        result.message_id || summary.dataset.messageId || 0
    );
    if (!conversationId || !messageId) {
        showToast('缺少任务信息，无法回退', 'error');
        return;
    }
    const fileCount = summary.querySelectorAll('.modified-files-row').length;
    const confirmed = await showConfirmDialog(
        `确定要回退该任务对 ${fileCount} 个文件的修改吗？` +
        '所有涉及文件将恢复到任务开始前的状态，且同一轮只能回退一次。'
    );
    if (!confirmed) return;
    button.disabled = true;
    button.textContent = '回退中…';
    try {
        const response = typeof eel.rollback_task === 'function'
            ? await eel.rollback_task(conversationId, messageId)()
            : null;
        if (response && response.success) {
            showToast(response.message || '回退成功', 'success');
            button.textContent = '已回退';
            button.classList.add('is-rolled-back');
            refreshTaskRollbackButtons(conversationId);
        } else {
            showToast(response?.error || '回退失败', 'error', 4000);
            button.disabled = false;
            button.textContent = '回退 ⏎';
        }
    } catch (error) {
        showToast('回退失败：' + String(error?.message || error), 'error', 4000);
        button.disabled = false;
        button.textContent = '回退 ⏎';
    }
}

let taskRollbackRefreshSeq = 0;
async function refreshTaskRollbackButtons(conversationId) {
    const convId = String(conversationId || activeConversationId || '');
    if (!convId || typeof eel.get_task_rollback_status !== 'function') return;
    const seq = ++taskRollbackRefreshSeq;
    let available = {};
    try {
        const response = await eel.get_task_rollback_status(convId)();
        if (seq !== taskRollbackRefreshSeq) return;
        if (!response?.success) return;
        available = response.available || {};
    } catch (_error) {
        return;
    }
    document.querySelectorAll('.modified-files-summary').forEach(summary => {
        const button = summary.querySelector('.modified-files-rollback');
        if (!button || button.classList.contains('is-rolled-back')) return;
        const messageId = Number(summary.dataset.messageId || 0);
        const canRollback = Boolean(
            messageId && available[String(messageId)]
        );
        if (!canRollback) {
            button.disabled = true;
            button.classList.add('is-rolled-back');
        }
    });
}

function showQuestionPrompt(questions, msgId, active = true, questionId = '') {
    document.querySelector('.question-prompt:not(.is-submitted)')?.remove();
    document.querySelector('.question-render-error')?.remove();
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) throw new Error('聊天区域尚未就绪');
    const normalizedQuestions = normalizeQuestionPromptData(questions);
    if (!normalizedQuestions.length) {
        throw new Error('提问工具没有返回可勾选的有效选项');
    }
    if (active) collapseThinkingForQuestion();
    const container = document.createElement('form');
    container.className = `question-prompt is-visible${active ? ' is-active-question' : ''}`;
    container.dataset.messageId = String(msgId);
    container.dataset.questionId = String(questionId || `question-${msgId}`);
    container.innerHTML = `
        <div class="question-prompt-header">
            <span class="question-prompt-dot" aria-hidden="true"></span>
            <span>需要你的选择</span>
        </div>
        <div class="question-prompt-list">
            ${normalizedQuestions.map((question, questionIndex) => {
                const multiple = Boolean(question.multiple);
                const inputType = multiple ? 'checkbox' : 'radio';
                const options = Array.isArray(question.options) ? question.options : [];
                const selectionRequired = question.selectionRequired !== false;
                const allowFreeText = Boolean(question.allowFreeText);
                const freeTextRequired = allowFreeText && Boolean(question.freeTextRequired);
                const inputName = `question-${msgId}-${questionIndex}`;
                return `
                    <fieldset class="question-group" data-question-index="${questionIndex}" data-multiple="${multiple}" data-selection-required="${selectionRequired}" data-allow-free-text="${allowFreeText}" data-free-text-required="${freeTextRequired}">
                        <legend>
                            <span class="question-header-label">${escapeHtml(question.header || `问题 ${questionIndex + 1}`)}</span>
                            <strong>${escapeHtml(question.question || '')}</strong>
                            <small>${multiple ? '多选' : '单选'}</small>
                        </legend>
                        ${options.length ? `<div class="question-options">
                            ${options.map((option, optionIndex) => {
                                const id = `question-${msgId}-${questionIndex}-${optionIndex}`;
                                return `
                                    <label class="question-option" for="${id}">
                                        <input id="${id}" type="${inputType}" name="${inputName}" value="${escapeHtml(option.label || '')}">
                                        <span class="question-option-control" aria-hidden="true"></span>
                                        <span class="question-option-copy">
                                            <strong>${escapeHtml(option.label || '')}</strong>
                                            <small>${escapeHtml(option.description || '')}</small>
                                        </span>
                                    </label>`;
                            }).join('')}
                        </div>` : ''}
                        ${allowFreeText ? `
                            <label class="question-free-text">
                                <span class="question-free-text-label">${escapeHtml(question.freeTextLabel || '补充说明')}<em>${freeTextRequired ? '必填' : '可选'}</em></span>
                                <textarea class="question-free-text-input" rows="2" maxlength="4000" placeholder="${escapeHtml(question.freeTextPlaceholder || '可补充具体要求、名称或未列出的信息')}"${freeTextRequired ? ' required' : ''}></textarea>
                            </label>` : ''}
                    </fieldset>`;
            }).join('')}
        </div>
        <div class="question-prompt-footer">
            <span>提交后任务会从这里继续</span>
            <button type="submit" class="btn-save question-submit">提交选择</button>
        </div>`;
    container.addEventListener('change', () => validateQuestionPrompt(container));
    container.addEventListener('input', () => validateQuestionPrompt(container));
    container.addEventListener('submit', submitQuestionPrompt);
    chatMessages.appendChild(container);
    validateQuestionPrompt(container);
    if (active) followChatOutput(chatMessages);
    return container;
}

function normalizeQuestionPromptData(questions) {
    if (!Array.isArray(questions)) return [];
    return questions.flatMap((question, questionIndex) => {
        if (!question || typeof question !== 'object') return [];
        const options = Array.isArray(question.options)
            ? question.options.flatMap(option => {
                if (typeof option === 'string') {
                    const label = option.trim();
                    return label ? [{label, description: ''}] : [];
                }
                if (!option || typeof option !== 'object') return [];
                const label = String(option.label || '').trim();
                if (!label) return [];
                return [{
                    label,
                    description: String(option.description || '').trim(),
                }];
            })
            : [];

        const header = String(question.header || '').trim();
        const questionText = String(question.question || '').trim();
        const wording = `${header} ${questionText} ${options.map(option => `${option.label} ${option.description}`).join(' ')}`;
        const multiple = parseQuestionBoolean(question.multiple)
            || /(?:可|允许|支持)?\s*(?:多选|多项选择|选择多个|可选多个)/.test(wording);
        const allowFreeText = parseQuestionBoolean(question.allow_free_text ?? question.allowFreeText)
            || /(?:可(?:在)?(?:下方|下面)?(?:文字)?补充|(?:下方|下面)(?:文字)?补充|直接补充文字|自由(?:文本)?(?:填写|输入)|其他(?:说明|内容)?(?:请)?(?:补充|填写))/.test(wording);
        if (!options.length && !allowFreeText) return [];
        return [{
            header: header || `问题 ${questionIndex + 1}`,
            question: questionText || header || `请选择问题 ${questionIndex + 1}`,
            multiple,
            selectionRequired: parseQuestionBoolean(
                question.selection_required ?? question.selectionRequired,
                true
            ),
            allowFreeText,
            freeTextLabel: String(
                question.free_text_label ?? question.freeTextLabel ?? '补充说明'
            ).trim() || '补充说明',
            freeTextPlaceholder: String(
                question.free_text_placeholder
                    ?? question.freeTextPlaceholder
                    ?? '可补充具体要求、名称或未列出的信息'
            ).trim() || '可补充具体要求、名称或未列出的信息',
            freeTextRequired: parseQuestionBoolean(
                question.free_text_required ?? question.freeTextRequired
            ),
            options,
        }];
    });
}

function parseQuestionBoolean(value, fallback = false) {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'number') return value !== 0;
    if (typeof value === 'string') {
        const normalized = value.trim().toLowerCase();
        if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
        if (['0', 'false', 'no', 'off', ''].includes(normalized)) return false;
    }
    return fallback;
}

function showQuestionRenderError(detail) {
    if (document.querySelector('.question-render-error')) return;
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    const element = document.createElement('div');
    element.className = 'question-render-error';
    element.setAttribute('role', 'alert');
    element.innerHTML = `
        <strong>问题选项暂时无法显示</strong>
        <span>${escapeHtml(detail || '请停止任务后重试')}</span>`;
    chatMessages.appendChild(element);
    followChatOutput(chatMessages);
}

function collapseThinkingForQuestion() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages?.querySelectorAll('.thinking-card').forEach(card => {
        if (card.classList.contains('is-condensed')) {
            card.classList.remove('is-expanded');
            card.querySelector('.thinking-summary')?.setAttribute(
                'aria-expanded', 'false'
            );
        } else {
            const details = card.querySelector('.thinking-details[open]');
            if (details) details.open = false;
        }
        card.classList.add('is-question-collapsed');
    });
}

function collectQuestionResponses(container) {
    return Array.from(container.querySelectorAll('.question-group')).map(group => ({
        selected: Array.from(group.querySelectorAll('input:checked')).map(input => input.value),
        supplement: group.querySelector('.question-free-text-input')?.value.trim() || '',
        selectionRequired: group.dataset.selectionRequired !== 'false',
        allowFreeText: group.dataset.allowFreeText === 'true',
        freeTextRequired: group.dataset.freeTextRequired === 'true',
    }));
}

function collectQuestionAnswers(container) {
    return collectQuestionResponses(container).map(response => response.selected);
}

function validateQuestionPrompt(container) {
    const responses = collectQuestionResponses(container);
    const complete = responses.length > 0 && responses.every(response => {
        if (response.freeTextRequired && !response.supplement) return false;
        return !response.selectionRequired
            || response.selected.length > 0
            || (response.allowFreeText && Boolean(response.supplement));
    });
    const submit = container.querySelector('.question-submit');
    if (submit) submit.disabled = !complete;
    return complete;
}

async function submitQuestionPrompt(event) {
    event.preventDefault();
    const container = event.currentTarget;
    if (!validateQuestionPrompt(container)) {
        showToast('请完成所有问题后再提交', 'info');
        return;
    }
    const responses = collectQuestionResponses(container);
    const answers = responses.map(response => response.selected);
    const supplements = responses.map(response => response.supplement);
    const questions = getQuestionPromptData(container);
    const state = getActiveExecutionState();
    const conversationId = String(state?.conversationId || activeConversationId || '');
    const messageId = Number(container.dataset.messageId || state?.messageId || currentMessageId);
    const submit = container.querySelector('.question-submit');
    if (submit) {
        submit.disabled = true;
        submit.textContent = '正在提交';
    }
    invalidatePolling(conversationId);
    try {
        const result = await eel.answer_question(
            answers, supplements, conversationId, messageId
        )();
        if (!result?.success) throw new Error(result?.error || '提交失败');
        isAwaitingQuestion = false;
        renderQuestionResult(
            questions,
            answers,
            messageId,
            container.dataset.questionId || '',
            container,
            supplements
        );
        if (state) state.awaitingQuestion = false;
        ensureExecutionPolling(conversationId, messageId);
    } catch (error) {
        if (submit) {
            submit.disabled = false;
            submit.textContent = '提交选择';
        }
        showToast(`回答提交失败：${error.message}`, 'error');
        ensureExecutionPolling(conversationId, messageId);
    }
}

function getQuestionPromptData(container) {
    return Array.from(container.querySelectorAll('.question-group')).map(group => ({
        header: group.querySelector('.question-header-label')?.textContent || '',
        question: group.querySelector('legend strong')?.textContent || '',
        freeTextLabel: group.querySelector('.question-free-text-label')?.childNodes[0]?.textContent?.trim() || '补充说明',
    }));
}

function finalizePendingQuestion(label) {
    const container = document.querySelector('.question-prompt:not(.is-submitted)');
    if (!container) return;
    container.classList.add('is-submitted');
    container.classList.remove('is-active-question');
    container.querySelectorAll('input, textarea').forEach(input => input.disabled = true);
    const submit = container.querySelector('.question-submit');
    if (submit) {
        submit.disabled = true;
        submit.textContent = label;
    }
}

function renderQuestionResult(
    questions, answers, msgId, questionId = '', prompt = null, supplements = []
) {
    const resultId = String(questionId || `question-${msgId}`);
    const selector = `.question-result[data-question-id="${cssEscape(resultId)}"]`;
    let result = document.querySelector(selector);
    if (!result) {
        result = document.createElement('div');
        result.className = 'question-result';
        result.dataset.questionId = resultId;
        const chatMessages = getChatRenderHost();
        if (prompt?.parentNode === chatMessages) {
            chatMessages.insertBefore(result, prompt);
        } else {
            chatMessages.appendChild(result);
        }
    }
    result.innerHTML = `
        <div class="question-result-icon" aria-hidden="true">✓</div>
        <div class="question-result-content">
            <div class="question-result-title">已提交回答</div>
            <div class="question-result-items">
                ${questions.map((question, index) => `
                    <div class="question-result-item">
                        <span>${escapeHtml(question.header || question.question || `问题 ${index + 1}`)}</span>
                        <strong>${escapeHtml((answers[index] || []).join('、') || (supplements[index] ? '已补充文字' : '未选择'))}</strong>
                        ${supplements[index] ? `<em>${escapeHtml(`${question.freeTextLabel || question.free_text_label || '补充说明'}：${supplements[index]}`)}</em>` : ''}
                    </div>`).join('')}
            </div>
        </div>`;
    prompt?.remove();
    requestAnimationFrame(() => result.classList.add('is-visible'));
    return result;
}

function addAnsweredQuestionCard(questions, answers, msgId, questionId = '', supplements = []) {
    return renderQuestionResult(questions, answers, msgId, questionId, null, supplements);
}

function cssEscape(value) {
    if (window.CSS?.escape) return window.CSS.escape(String(value));
    return String(value).replace(/(["\\])/g, '\\$1');
}

async function clearConversation() {
    if (!isInitialized) return;
    if (isConversationRunning(activeConversationId)) {
        showToast('当前任务正在执行，请先停止后再清空', 'info');
        return;
    }

    const confirmed = await showConfirmDialog('确定要清空会话与记忆文件吗？此操作不可撤销。');
    if (!confirmed) return;

    try {
        const result = await eel.clear_conversation(activeConversationId)();
        if (!result?.success) throw new Error(result?.error || '清空失败');

        pendingKnowledgeByMessageId.clear();
        completedMessageByMessageId.clear();
        clearMessageQueue(activeConversationId);
        conversationExecutionStates.delete(String(activeConversationId || ''));
        clearConversationPlanProgress(activeConversationId);
        clearConversationAgentTeams(activeConversationId);
        resetConversationView();
        await refreshConversations(activeConversationId);
        showToast('当前任务历史与记忆已清空', 'success');
        updateTokenIndicator();
    } catch (error) {
        console.error('Failed to clear:', error);
        showToast(`清空失败：${error.message}`, 'error');
    }
}

function addMessage(role, content, isError = false, animate = true) {
    const chatMessages = getChatRenderHost();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}${isError ? ' error' : ''}`;

    const avatar = role === 'user' ? 'U' : 'A';
    const time = new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });

    const formattedContent = formatContent(content);

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-wrapper">
            <div class="message-bubble">${formattedContent}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    // 用户消息内容超过 350px（macOS 上 ≈350pt）时折叠：底部渐变 + 右下角
    // “展开 ▾”文字，点击展开后变为“收起 ▴”，可来回切换。
    if (role === 'user' && !isError) {
        const bubble = messageDiv.querySelector('.message-bubble');
        if (bubble && bubble.scrollHeight > 350) {
            bubble.classList.add('is-collapsible');
            const expandBtn = document.createElement('button');
            expandBtn.type = 'button';
            expandBtn.className = 'message-expand-btn';
            expandBtn.textContent = '展开 ▾';
            const toggleCollapse = () => {
                const expanded = bubble.classList.toggle('is-expanded');
                expandBtn.textContent = expanded ? '收起 ▴' : '展开 ▾';
            };
            expandBtn.addEventListener('click', event => {
                event.stopPropagation();
                toggleCollapse();
            });
            bubble.appendChild(expandBtn);
            bubble.addEventListener('click', toggleCollapse);
        }
    }
    if (animate) requestAnimationFrame(() => messageDiv.classList.add('is-visible'));
    else messageDiv.classList.add('is-visible');
    if (!isRestoringConversation) followChatOutput(chatMessages);
    return messageDiv;
}

function decorateCommentaryMessage(message) {
    if (!message) return message;
    message.classList.add('commentary-message');
    message.setAttribute('aria-label', '工作说明');
    return message;
}

function addCommentaryMessage(content, animate = true) {
    return decorateCommentaryMessage(addMessage('ai', content, false, animate));
}

function addUserMessage(content, attachments, messageId, animate = true) {
    const message = addMessage('user', content, false, animate);
    message.dataset.messageId = String(messageId);
    const wrapper = message.querySelector('.message-wrapper');
    if (!wrapper || !attachments.length) return message;

    const list = document.createElement('div');
    list.className = 'message-attachments';
    list.innerHTML = attachments.map(item => renderMessageAttachment({
        ...item,
        success: Object.prototype.hasOwnProperty.call(item, 'success')
            ? item.success
            : null,
    })).join('');
    wrapper.insertBefore(list, wrapper.firstChild);
    if (!animate) {
        hydrateConversationAttachmentPreviews(activeConversationId, list);
    }
    return message;
}

function renderMessageAttachment(item) {
    const isImage = isImageAttachment(item)
        || item.parse_mode === 'vision'
        || item.parse_mode === 'image_view';
    const isDirectory = isDirectoryReference(item);
    const imageStatus = item.parse_mode === 'image_view'
        ? '图片已保存'
        : '已发送给视觉模型';
    const status = item.success === true
        ? isDirectory ? '参考目录已加入' : isImage ? imageStatus : '已解析'
        : item.success === false
            ? isDirectory ? '参考目录不可用' : isImage ? '图片保存失败' : '解析失败'
            : isDirectory ? '正在定位目录' : isImage ? '正在保存图片' : '正在解析';
    const statusClass = item.success === true
        ? 'is-ready'
        : item.success === false
            ? 'has-error'
            : 'is-parsing';
    const assetAttribute = item.asset_id
        ? ` data-asset-id="${escapeHtml(item.asset_id)}"`
        : '';
    const previewAttributes = isImage
        ? ` data-image-attachment="true" role="button" tabindex="0" aria-label="预览图片 ${escapeHtml(item.name)}"`
        : '';
    return `
        <div class="message-attachment ${statusClass}" data-attachment-name="${escapeHtml(item.name)}"${assetAttribute}${previewAttributes}>
            ${renderAttachmentVisual(item, 'message-attachment-icon')}
            <span class="message-attachment-copy">
                <strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong>
                <small title="${escapeHtml(item.path || '')}">${escapeHtml(status)}${isDirectory ? ` · ${escapeHtml(item.path || '')}` : ` · ${formatAttachmentSize(Number(item.size || 0))}`}</small>
            </span>
            <span class="message-attachment-status" aria-hidden="true">${item.success === true ? '✓' : item.success === false ? '!' : ''}</span>
        </div>
    `;
}

async function hydrateConversationAttachmentPreviews(conversationId, list) {
    if (!conversationId || !list || typeof eel === 'undefined') return;
    const cards = Array.from(list.querySelectorAll('.message-attachment[data-asset-id]'));
    await Promise.all(cards.map(async card => {
        if (card.querySelector('img') || card.dataset.previewState === 'loading') return;
        const assetId = card.dataset.assetId || '';
        if (!assetId) return;
        card.dataset.previewState = 'loading';
        try {
            const result = await eel.load_conversation_attachment(conversationId, assetId)();
            if (activeConversationId !== conversationId || !card.isConnected) return;
            if (!result?.success || !result.data) {
                card.dataset.previewState = 'unavailable';
                return;
            }
            const icon = card.querySelector('.message-attachment-icon');
            if (!icon) return;
            const preview = document.createElement('img');
            preview.src = result.data;
            preview.alt = '';
            icon.replaceChildren(preview);
            icon.classList.remove('is-image-placeholder');
            icon.classList.add('is-image');
            card.dataset.previewState = 'ready';
        } catch (error) {
            if (card.isConnected) card.dataset.previewState = 'unavailable';
            console.error('Failed to restore image preview:', error);
        }
    }));
}

function updateMessageAttachments(messageId, attachments) {
    const message = document.querySelector(`.message.user[data-message-id="${messageId}"]`);
    const list = message?.querySelector('.message-attachments');
    if (!list) return;
    const localAttachments = new Map(
        Array.from(list.querySelectorAll('.message-attachment')).map(element => [
            element.dataset.attachmentName || '',
            element.querySelector('.message-attachment-icon img')?.src || '',
        ])
    );
    list.innerHTML = attachments.map(item => {
        const preview = localAttachments.get(String(item.name || ''));
        return renderMessageAttachment({
            ...item,
            data: item.data || preview || '',
        });
    }).join('');
}

function createStreamingResponse(streamId, state) {
    const chatMessages = state.host || document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai streaming-response';
    messageDiv.dataset.streamId = streamId;
    messageDiv.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-wrapper">
            <div class="message-bubble"><span class="stream-caret" aria-hidden="true"></span></div>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    requestAnimationFrame(() => messageDiv.classList.add('is-visible'));

    state.element = messageDiv;
    state.bubble = messageDiv.querySelector('.message-bubble');
    if (state.isCommentary) decorateCommentaryMessage(messageDiv);
    return messageDiv;
}

function markStreamingCommentary(streamId) {
    const state = streamingResponses.get(String(streamId || ''));
    if (!state) return;
    state.thinkingClosed = true;
    completeStreamingThinking(state);
    flushVoiceStreamingResponse(state, {final: true});
    state.isCommentary = true;
    state.voiceDisabled = true;
    if (state.frame || state.renderTimer) {
        cancelStreamingRender(state);
        renderStreamingState(state);
    }
    completeStreamingThinking(state);
    decorateCommentaryMessage(state.element);
}

function createStreamingThinking(state) {
    if (!state.thinkingStartedAt) state.thinkingStartedAt = Date.now();
    state.thinkingCard = addThinkingCard(
        '', state.element, false, true, false, null, state.host || null
    );
    state.thinkingBody = state.thinkingCard.querySelector('.thinking-content');
    state.thinkingCard.classList.add('is-streaming');
    if (state.thinkingClosed) {
        completeStreamingThinking(state);
    } else {
        startStreamingThinkingTimer(state);
    }
}

function updateStreamingThinkingLabel(state) {
    const label = state.thinkingCard?.querySelector('.thinking-summary-label');
    if (!label) return;
    label.textContent = `正在思考 ${formatThinkingDuration(
        getThinkingDurationMs(state.thinkingStartedAt)
    )}`;
}

function startStreamingThinkingTimer(state) {
    stopStreamingThinkingTimer(state);
    updateStreamingThinkingLabel(state);
    state.thinkingTimer = setInterval(() => {
        updateStreamingThinkingLabel(state);
    }, 250);
}

function stopStreamingThinkingTimer(state) {
    if (!state?.thinkingTimer) return;
    clearInterval(state.thinkingTimer);
    state.thinkingTimer = null;
}

function completeStreamingThinking(state) {
    if (!state?.thinkingCard) return;
    if (Number.isFinite(state.thinkingDurationMs)) {
        stopStreamingThinkingTimer(state);
        return;
    }
    stopStreamingThinkingTimer(state);
    const durationMs = getThinkingDurationMs(state.thinkingStartedAt);
    state.thinkingDurationMs = durationMs;
    state.thinkingCard.classList.remove('is-streaming');
    const label = state.thinkingCard.querySelector('.thinking-summary-label');
    if (label) label.textContent = `已思考 ${formatThinkingDuration(durationMs)}`;
}

function moveThinkingBeforeAnswer(state) {
    const chatMessages = state.host || document.getElementById('chatMessages');
    if (state.thinkingCard?.parentNode === chatMessages
        && state.element?.parentNode === chatMessages
        && state.thinkingCard.nextSibling !== state.element) {
        chatMessages.insertBefore(state.thinkingCard, state.element);
    }
}

function getVoiceStreamSentenceBoundary(text) {
    const source = String(text || '');
    if (!source) return 0;
    let boundary = 0;
    const sentenceEnd = /[。！？!?；;…\n]+|\.(?=\s|$)/g;
    let match = null;
    while ((match = sentenceEnd.exec(source)) !== null) {
        boundary = match.index + match[0].length;
    }
    if (!boundary && source.length >= 72) {
        const softEnd = /[，,：:]\s*/g;
        while ((match = softEnd.exec(source)) !== null) {
            if (match.index >= 28) boundary = match.index + match[0].length;
        }
    }
    return boundary;
}

function flushVoiceStreamingResponse(state, {final = false} = {}) {
    if (!voiceModeActive || !state || state.isCommentary || state.voiceDisabled) return;
    const stream = splitStreamingContent(state.content);
    if (stream.waitingForMarker || (stream.hasThinking && !stream.thinkingComplete)) return;
    const answer = String(stream.answer || (!stream.hasThinking ? state.content : ''));
    const consumed = Math.min(Number(state.voiceConsumedLength || 0), answer.length);
    const pending = answer.slice(consumed);
    const boundary = final ? pending.length : getVoiceStreamSentenceBoundary(pending);
    if (!boundary) return;
    const speechText = pending.slice(0, boundary).replace(/\s+/g, ' ').trim();
    state.voiceConsumedLength = consumed + boundary;
    if (!speechText) return;
    state.voiceQueuedText = `${state.voiceQueuedText || ''}${speechText}`;
    enqueueVoiceSpeech(
        speechText,
        `stream:${state.streamId}:${state.voiceConsumedLength}:${speechText}`
    );
}

function appendStreamingResponse(streamId, chunk, startedAt = 0) {
    const id = String(streamId || currentMessageId);
    let state = streamingResponses.get(id);
    if (!state) {
        state = {
            conversationId: activeConversationId,
            element: null,
            bubble: null,
            thinkingCard: null,
            thinkingBody: null,
            content: '',
            frame: null,
            renderTimer: null,
            lastRenderedAt: 0,
            streamId: id,
            thinkingCondensed: false,
            thinkingStartedAt: Number(startedAt) || 0,
            thinkingDurationMs: null,
            thinkingTimer: null,
            thinkingClosed: false,
            isCommentary: false,
            thinkingDetectionComplete: false,
            voiceConsumedLength: 0,
            voiceQueuedText: '',
            voiceDisabled: false,
        };
        streamingResponses.set(id, state);
    }
    state.content += String(chunk || '');
    if (!state.thinkingCard && !state.thinkingDetectionComplete) {
        const stream = splitStreamingContent(state.content);
        if (stream.hasThinking) {
            cancelStreamingRender(state);
            renderStreamingState(state);
            return;
        }
        state.thinkingDetectionComplete = !stream.waitingForMarker;
    }
    flushVoiceStreamingResponse(state);
    scheduleStreamingRender(state);
}

function scheduleStreamingRender(state) {
    if (state.frame || state.renderTimer) return;
    const elapsed = performance.now() - Number(state.lastRenderedAt || 0);
    const interval = Math.min(
        STREAM_RENDER_MAX_INTERVAL_MS,
        STREAM_RENDER_INTERVAL_MS + state.content.length / 250
    );
    const delay = Math.max(0, interval - elapsed);
    const render = () => {
        state.renderTimer = null;
        state.frame = requestAnimationFrame(() => {
            state.frame = null;
            state.lastRenderedAt = performance.now();
            renderStreamingState(state);
        });
    };
    if (delay > 0) state.renderTimer = setTimeout(render, delay);
    else render();
}

function cancelStreamingRender(state) {
    if (!state) return;
    if (state.frame) cancelAnimationFrame(state.frame);
    if (state.renderTimer) clearTimeout(state.renderTimer);
    state.frame = null;
    state.renderTimer = null;
}

function renderStreamingState(state) {
    const stream = splitStreamingContent(state.content);
    if (stream.waitingForMarker) return;

    if (stream.hasThinking) {
        if (!state.thinkingCard) createStreamingThinking(state);
        state.thinkingBody.innerHTML = `${renderMarkdown(stream.thinking)}${stream.thinkingComplete ? '' : '<span class="stream-caret" aria-hidden="true"></span>'}`;
        if (stream.thinkingComplete && !state.thinkingCondensed) {
            state.thinkingCondensed = true;
            completeStreamingThinking(state);
            condenseThinkingCard(state.thinkingCard);
        }
    }

    if (stream.answer) {
        if (!state.element) createStreamingResponse(state.streamId, state);
        moveThinkingBeforeAnswer(state);
        state.bubble.innerHTML = `${renderMarkdown(stream.answer)}<span class="stream-caret" aria-hidden="true"></span>`;
    } else if (!stream.hasThinking) {
        if (!state.element) createStreamingResponse(state.streamId, state);
        state.bubble.innerHTML = `${renderMarkdown(state.content)}<span class="stream-caret" aria-hidden="true"></span>`;
    }

    if (!state.host) followChatOutput();
}

function splitStreamingContent(content) {
    const source = String(content || '');
    const trimmedStart = source.trimStart();
    if ('<think>'.startsWith(trimmedStart.toLowerCase()) && trimmedStart.length < 7) {
        return { waitingForMarker: true, hasThinking: false, thinking: '', thinkingComplete: false, answer: '' };
    }

    const open = source.match(/<think\b[^>]*>/i);
    if (!open) {
        return { waitingForMarker: false, hasThinking: false, thinking: '', thinkingComplete: false, answer: source };
    }

    const thoughtStart = open.index + open[0].length;
    const closePattern = /<\/think>/gi;
    closePattern.lastIndex = thoughtStart;
    const close = closePattern.exec(source);
    if (!close) {
        return {
            waitingForMarker: false,
            hasThinking: true,
            thinking: source.slice(thoughtStart),
            thinkingComplete: false,
            answer: '',
        };
    }

    return {
        waitingForMarker: false,
        hasThinking: true,
        thinking: source.slice(thoughtStart, close.index),
        thinkingComplete: true,
        answer: source.slice(close.index + close[0].length).trimStart(),
    };
}

function finalizeStreamingResponse(result, msgId) {
    const streamId = String(result.stream_id || msgId);
    const state = streamingResponses.get(streamId);
    const content = String(result.content || state?.content || '');
    const isCommentary = result.target === 'commentary';
    if (isCommentary && state) {
        flushVoiceStreamingResponse(state, {final: true});
        state.isCommentary = true;
        state.voiceDisabled = true;
    }

    if (result.target === 'discard') {
        if (state?.voiceQueuedText) cancelVoiceSpeech();
        cancelStreamingRender(state);
        stopStreamingThinkingTimer(state);
        state?.element?.remove();
        state?.thinkingCard?.remove();
        streamingResponses.delete(streamId);
        return;
    }

    if (result.target === 'thinking') {
        if (state?.voiceQueuedText) cancelVoiceSpeech();
        cancelStreamingRender(state);
        state?.element?.remove();
        if (state?.thinkingCard) {
            const { thoughts, answer } = splitThinkingContent(content);
            const thought = thoughts[thoughts.length - 1] || answer || content;
            state.thinkingBody.innerHTML = renderMarkdown(thought);
            completeStreamingThinking(state);
            condenseThinkingCard(state.thinkingCard);
        } else if (content.trim()) {
            addThinkingMessage(content);
        }
        stopStreamingThinkingTimer(state);
        streamingResponses.delete(streamId);
        return;
    }

    const { thoughts, answer } = splitThinkingContent(content);
    if (!isCommentary) flushVoiceStreamingResponse(state, {final: true});
    let thinkingCards = [];
    if (state?.thinkingCard) {
        const thought = thoughts[thoughts.length - 1] || '';
        if (thought) state.thinkingBody.innerHTML = renderMarkdown(thought);
        completeStreamingThinking(state);
        condenseThinkingCard(state.thinkingCard);
        thinkingCards = [state.thinkingCard];
    } else {
        thinkingCards = thoughts.map(thought => addThinkingCard(
            thought, state?.element, true, true, true
        ));
    }
    const visibleContent = answer.trim();
    let finalMessage = state?.element;
    if (state) {
        cancelStreamingRender(state);
        stopStreamingThinkingTimer(state);
        if (visibleContent) {
            if (!state.element) createStreamingResponse(streamId, state);
            state.bubble.innerHTML = renderMarkdown(visibleContent);
            state.element.classList.remove('streaming-response');
            if (isCommentary) decorateCommentaryMessage(state.element);
        } else if (thinkingCards.length) {
            state.element?.remove();
            finalMessage = thinkingCards[thinkingCards.length - 1];
        } else {
            if (isCommentary) {
                state.element?.remove();
                finalMessage = thinkingCards[thinkingCards.length - 1] || null;
            } else {
                if (!state.element) createStreamingResponse(streamId, state);
                state.bubble.innerHTML = renderMarkdown(content);
                state.element.classList.remove('streaming-response');
            }
        }
        streamingResponses.delete(streamId);
    } else {
        const commentary = getVisibleModelContent(content);
        finalMessage = isCommentary
            ? commentary ? addCommentaryMessage(commentary) : null
            : addAssistantResponse(content);
    }

    if (isCommentary) {
        stopStreamingThinkingTimer(state);
        streamingResponses.delete(streamId);
        return;
    }

    if (!state || !state.voiceQueuedText) speakVoiceResponse(content, msgId);
    completedMessageByMessageId.set(msgId, finalMessage);
    flushPendingKnowledge(msgId, finalMessage);
    updateTokenIndicator();
}

function getVisibleModelContent(content) {
    return splitThinkingContent(content).answer.trim();
}

function removeStreamingResponses() {
    streamingResponses.forEach((state) => {
        cancelStreamingRender(state);
        stopStreamingThinkingTimer(state);
        state.element?.remove();
        state.thinkingCard?.remove();
        const execState = getConversationExecutionState(
            state.conversationId || activeConversationId, false
        );
        const saved = execState?.thinkingStartByStream;
        if (saved && !saved.has(String(state.streamId))) {
            saved.set(String(state.streamId), Number(state.thinkingStartedAt) || 0);
        }
    });
    streamingResponses.clear();
}

function finalizeVisibleStreamingResponses() {
    streamingResponses.forEach((state, streamId) => {
        cancelStreamingRender(state);
        stopStreamingThinkingTimer(state);
        if (state.thinkingCard) {
            completeStreamingThinking(state);
            condenseThinkingCard(state.thinkingCard);
        }
        if (state.bubble && state.element) {
            const {answer} = splitThinkingContent(state.content || '');
            const visibleContent = answer.trim() || getVisibleModelContent(state.content || '');
            state.bubble.innerHTML = visibleContent
                ? renderMarkdown(visibleContent)
                : '<span class="stream-stopped-label">已停止输出</span>';
            state.element.classList.remove('streaming-response');
        }
        streamingResponses.delete(streamId);
    });
}

function addThinkingMessage(content, durationMs = null) {
    const { thoughts, answer } = splitThinkingContent(content);
    const items = thoughts.length ? thoughts : [answer || content];

    items
        .map(item => String(item || '').replace(/^接下来我要\s*[:：]\s*/, '').trim())
        .filter(Boolean)
        .forEach(item => addThinkingCard(
            item, null, true, true, true, durationMs
        ));
}

function addAssistantResponse(content, thinkingDurationMs = null) {
    const { thoughts, answer } = splitThinkingContent(content);
    const cards = thoughts.map(thought => addThinkingCard(
        thought, null, true, true, true, thinkingDurationMs
    ));

    const visibleAnswer = answer.trim();
    if (visibleAnswer) return addMessage('ai', visibleAnswer);
    if (cards.length) return cards[cards.length - 1];
    return addMessage('ai', content);
}

function splitThinkingContent(content) {
    const source = String(content || '');
    const thoughts = [];
    let answer = source.replace(/<think\b[^>]*>([\s\S]*?)<\/think>/gi, (_, thought) => {
        const normalized = String(thought || '').trim();
        if (normalized) thoughts.push(normalized);
        return '';
    });

    // Some providers occasionally omit the closing tag; never leak raw tags into the UI.
    answer = answer.replace(/<think\b[^>]*>([\s\S]*)$/i, (_, thought) => {
        const normalized = String(thought || '').trim();
        if (normalized) thoughts.push(normalized);
        return '';
    }).replace(/<\/?think\b[^>]*>/gi, '');

    if (thoughts.length && /^\s*(?:→|↳)\s*$/.test(answer)) answer = '';

    return { thoughts, answer };
}

function addThinkingCard(
    content,
    beforeElement = null,
    scrollIntoView = true,
    animate = true,
    completed = false,
    durationMs = null,
    host = null
) {
    const chatMessages = host || getChatRenderHost();
    const card = document.createElement('div');
    card.className = 'thinking-card';
    const completedLabel = Number.isFinite(durationMs)
        ? `已思考 ${formatThinkingDuration(durationMs)}`
        : '已处理';

    card.innerHTML = `
        <details class="thinking-details" open>
            <summary class="thinking-summary">
                <span class="thinking-summary-label">${completedLabel}</span>
                <svg class="thinking-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
            </summary>
            <div class="thinking-content markdown-body">${renderMarkdown(content)}</div>
        </details>
    `;

    if (beforeElement?.parentNode === chatMessages) {
        chatMessages.insertBefore(card, beforeElement);
    } else {
        chatMessages.appendChild(card);
    }
    if (animate) requestAnimationFrame(() => card.classList.add('is-visible'));
    else card.classList.add('is-visible');
    if (completed) condenseThinkingCard(card, !animate);
    if (scrollIntoView && !host) followChatOutput(chatMessages);
    return card;
}

function condenseThinkingCard(card, immediate = false) {
    if (!card || card.classList.contains('is-streaming')) return;
    const details = card.querySelector('.thinking-details');
    const content = card.querySelector('.thinking-content');
    const summary = card.querySelector('.thinking-summary');
    if (!details || !content || !summary) return;

    const alreadyCondensed = card.classList.contains('is-condensed');
    details.open = true;
    if (!alreadyCondensed) {
        card.classList.remove('is-expanded');
        card.style.removeProperty('--thinking-preview-height');
        card.style.removeProperty('--thinking-full-height');
    }

    const computed = getComputedStyle(content);
    const lineHeight = parseFloat(computed.lineHeight) || 22;
    const padding = (parseFloat(computed.paddingTop) || 0)
        + (parseFloat(computed.paddingBottom) || 0);
    const previewHeight = Math.ceil(lineHeight * 10 + padding);
    const fullHeight = Math.ceil(content.scrollHeight);
    if (fullHeight <= previewHeight + 2) {
        card.classList.remove('is-condensed', 'is-expanded');
        summary.removeAttribute('aria-expanded');
        return;
    }

    const chatMessages = document.getElementById('chatMessages');
    const keepBottomAnchored = chatAutoFollow;

    card.style.setProperty('--thinking-preview-height', `${previewHeight}px`);
    card.style.setProperty('--thinking-full-height', `${fullHeight}px`);
    if (alreadyCondensed) {
        summary.setAttribute(
            'aria-expanded',
            card.classList.contains('is-expanded') ? 'true' : 'false'
        );
        return;
    }
    card.classList.add('is-condensed', 'is-expanded');
    void content.offsetHeight;

    const collapse = () => {
        card.classList.remove('is-expanded');
        summary.setAttribute('aria-expanded', 'false');
        if (keepBottomAnchored && chatMessages) {
            requestAnimationFrame(() => {
                followChatOutput(chatMessages);
            });
        }
    };
    if (immediate) collapse();
    else requestAnimationFrame(collapse);

    if (summary.dataset.thinkingToggleBound === 'true') return;
    summary.dataset.thinkingToggleBound = 'true';
    summary.addEventListener('click', event => {
        if (!card.classList.contains('is-condensed')) return;
        event.preventDefault();
        details.open = true;
        if (!card.classList.contains('is-expanded')) {
            card.style.setProperty(
                '--thinking-full-height',
                `${Math.ceil(content.scrollHeight)}px`
            );
        }
        card.classList.toggle('is-expanded');
        summary.setAttribute(
            'aria-expanded',
            card.classList.contains('is-expanded') ? 'true' : 'false'
        );
    });
    content.addEventListener('click', event => {
        if (!card.classList.contains('is-condensed')
            || card.classList.contains('is-expanded')
            || event.target.closest('a, button, input, textarea, select')) {
            return;
        }
        summary.click();
    });
    summary.setAttribute('aria-expanded', 'false');
}

function getThinkingDurationMs(startedAt, endedAt = Date.now()) {
    const start = Number(startedAt || 0);
    const end = Number(endedAt || Date.now());
    if (!Number.isFinite(start) || start <= 0 || !Number.isFinite(end)) return null;
    return Math.max(0, end - start);
}

function formatThinkingDuration(durationMs) {
    const totalSeconds = Math.max(0, Math.floor(Number(durationMs || 0) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes ? `${minutes} 分 ${seconds} 秒` : `${seconds} 秒`;
}

function getPersistedThinkingDuration(event) {
    const value = event?.thinking_duration_ms ?? event?.duration_ms;
    if (value === undefined || value === null || value === '') return null;
    const duration = Number(value);
    return Number.isFinite(duration) && duration >= 0 ? duration : null;
}

function getToolExecutionKey(result, msgId) {
    return String(
        result.prepared_tool_call_id
        || result.tool_call_id
        || `${msgId}:${result.tool || 'tool'}`
    );
}

function getPreparedToolStreamId(result) {
    const explicitStreamId = String(result.stream_id || '').trim();
    if (explicitStreamId) return explicitStreamId;
    const preparedId = String(result.prepared_tool_call_id || '').trim();
    const separatorIndex = preparedId.lastIndexOf(':');
    return separatorIndex > 0 ? preparedId.slice(0, separatorIndex) : '';
}

function getToolTarget(toolName, params = {}, explicitTarget = '') {
    const target = String(explicitTarget || '').trim();
    if (target) return target;
    const values = params && typeof params === 'object' ? params : {};
    const source = String(values.source || '').trim();
    const destination = String(values.destination || '').trim();
    if (source && destination) return `${source} -> ${destination}`;
    for (const key of ['filePath', 'file_path', 'path', 'filename']) {
        const value = String(values[key] || '').trim();
        if (value) return value;
    }
    const name = String(toolName || '').toLowerCase();
    if (/bash|shell/.test(name)) {
        return String(values.description || values.workdir || '').trim();
    }
    if (name === 'read_url') return String(values.url || '').trim();
    if (/websearch|web_search|codesearch/.test(name)) {
        const query = String(values.query || values.pattern || '').trim();
        const path = String(values.path || '').trim();
        return path && query ? `${path} · ${query}` : (query || path);
    }
    if (name === 'project_preview') {
        return String(values.name || values.workdir || values.entry_path || '').trim();
    }
    if (name === 'load_skill') return String(values.skill_name || '').trim();
    return '';
}

function getToolProgressCopy(toolName, params = {}) {
    const name = String(toolName || '').toLowerCase();
    const path = params.filePath || params.file_path || params.path || params.filename || '';
    const fileName = path ? String(path).split(/[\\/]/).pop() : '';
    if (/write|edit/.test(name)) {
        return fileName ? `正在写入 ${fileName}` : '正在写入文件';
    }
    if (/bash|shell/.test(name)) return '正在运行命令';
    if (/docx|pdf|ppt|xlsx|generate/.test(name)) return '正在生成文件';
    if (/read/.test(name)) return fileName ? `正在读取 ${fileName}` : '正在读取文件';
    if (/search|glob|grep/.test(name)) return '正在搜索内容';
    return '正在执行工具';
}

function getToolPreparingCopy(toolName) {
    const name = String(toolName || '').toLowerCase();
    if (/write|edit/.test(name)) return '正在生成写入内容';
    if (/bash|shell/.test(name)) return '正在生成命令参数';
    if (/read/.test(name)) return '正在准备读取参数';
    if (/search|glob|grep/.test(name)) return '正在准备搜索参数';
    if (/docx|pdf|ppt|xlsx|generate/.test(name)) return '正在准备生成内容';
    return '正在生成工具参数';
}

function formatToolDuration(milliseconds) {
    const seconds = Math.max(0, Number(milliseconds || 0) / 1000);
    if (seconds < 10) return `${Math.max(0.1, seconds).toFixed(1)} 秒`;
    if (seconds < 60) return `${Math.floor(seconds)} 秒`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes} 分 ${Math.floor(seconds % 60)} 秒`;
}

function toolResultFailed(value) {
    const text = String(value || '').trim();
    const lowered = text.toLowerCase();
    if (text.startsWith('{')) {
        try {
            const parsed = JSON.parse(text);
            if (parsed && typeof parsed === 'object' && parsed.success === false) return true;
        } catch (error) {
            /* fall through to text heuristics */
        }
    }
    // 旧渲染器的 ✓ Success 状态行是权威成功结果（防御性保留）；正文里的
    // "No such file or directory" 等文本（删除后验证输出）不构成失败。
    if (/^✓\s*success/i.test(text)) return false;
    if (/^(?:error|failed|failure|fatal):/i.test(text)) return true;
    if (/^✗/.test(text)) return true;
    if (/^(?:错误|失败)[：:]|^执行失败|^(?:unable to|error occurred)|^无法/.test(text)) return true;
    // 标记契约：非零退出是报告不是错误，但对该卡片而言仍是失败态
    // （不当作成功复用）；只有精确的标记行参与判定，正文内嵌文本不参与。
    if (text.includes('[cancelled]')) return true;
    if (text.includes('[timed out after') || text.includes('[timed out]')) return true;
    if (text.includes('[killed by signal')) return true;
    const exitMarker = text.lastIndexOf('[exit code: ');
    if (exitMarker >= 0) {
        const end = text.indexOf(']', exitMarker);
        const code = text.slice(exitMarker + '[exit code: '.length, end).trim();
        if (/^[1-9]\d*$/.test(code)) return true;
    }
    return false;
}

function startToolExecution(result, msgId, isPreparing = false) {
    if (isQuestionToolName(result.tool) || !isPrimaryToolEvent(result)) return null;
    const chatMessages = document.getElementById('chatMessages');
    const key = getToolExecutionKey(result, msgId);
    const existing = activeToolExecutions.get(key);
    if (existing) {
        const toolName = String(result.tool || existing.toolName || 'Tool');
        const toolNameElement = existing.element.querySelector('.tool-name');
        if (toolNameElement) toolNameElement.textContent = toolName;
        existing.toolName = toolName;
        existing.messageId = Number(msgId || existing.messageId || 0);
        existing.streamId = getPreparedToolStreamId(result) || existing.streamId || '';
        existing.isPreparing = Boolean(isPreparing);
        existing.progressCopy = isPreparing
            ? getToolPreparingCopy(toolName)
            : getToolProgressCopy(toolName, result.params || {});
        existing.target = getToolTarget(toolName, result.params || {}, result.target) || existing.target || '';
        const summary = existing.element.querySelector('.tool-live-summary');
        if (summary) {
            summary.textContent = primaryToolSummary(
                existing.progressCopy,
                existing.target
            );
        }
        const backendStartedAt = Number(result.started_at_ms || 0);
        if (backendStartedAt > 0) {
            existing.startedAt = Math.min(existing.startedAt, backendStartedAt);
        }
        existing.element.classList.toggle('is-preparing', isPreparing);
        return existing.element;
    }

    const toolDiv = document.createElement('div');
    toolDiv.className = 'tool-execution tool-execution-running';
    toolDiv.dataset.toolExecutionKey = key;
    const progressCopy = isPreparing
        ? getToolPreparingCopy(result.tool)
        : getToolProgressCopy(result.tool, result.params || {});
    const target = getToolTarget(result.tool, result.params || {}, result.target);
    toolDiv.classList.toggle('is-preparing', isPreparing);
    toolDiv.innerHTML = `
        <div class="tool-card tool-card-running" role="status" aria-live="polite">
            <div class="tool-header tool-header-running">
                <span class="tool-progress-spinner" aria-hidden="true"><span></span></span>
                <span class="tool-name">${escapeHtml(result.tool || 'Tool')}</span>
                <span class="tool-summary tool-live-summary">${escapeHtml(primaryToolSummary(progressCopy, target))}</span>
                <span class="tool-elapsed">0 秒</span>
            </div>
            <div class="tool-progress-track" aria-hidden="true"><span></span></div>
        </div>`;
    chatMessages.appendChild(toolDiv);
    requestAnimationFrame(() => toolDiv.classList.add('is-visible'));

    const backendStartedAt = Number(result.started_at_ms || 0);
    const startedAt = backendStartedAt > 0
        ? Math.min(Date.now(), backendStartedAt)
        : Date.now();
    const execution = {
        element: toolDiv,
        interval: null,
        startedAt,
        toolName: String(result.tool || ''),
        messageId: Number(msgId || 0),
        streamId: getPreparedToolStreamId(result),
        progressCopy,
        target,
        isPreparing: Boolean(isPreparing),
        phase: 0,
        conversationId: String(activeConversationId || ''),
    };
    const phases = ['处理中', '仍在进行', '正在完成'];
    const updateElapsed = () => {
        const seconds = Math.max(1, Math.floor((Date.now() - execution.startedAt) / 1000));
        const elapsed = execution.element.querySelector('.tool-elapsed');
        const liveSummary = execution.element.querySelector('.tool-live-summary');
        if (elapsed) elapsed.textContent = `${seconds} 秒`;
        if (liveSummary && seconds > 8 && seconds % 6 === 0) {
            execution.phase = (execution.phase + 1) % phases.length;
            const status = `${execution.progressCopy} · ${phases[execution.phase]}`;
            liveSummary.textContent = primaryToolSummary(status, execution.target);
        }
        followChatOutput(chatMessages);
    };
    updateElapsed();
    execution.interval = setInterval(updateElapsed, 1000);
    activeToolExecutions.set(key, execution);
    followChatOutput(chatMessages);
    return toolDiv;
}

function finishToolExecution(result, msgId) {
    if (isQuestionToolName(result.tool) || !isPrimaryToolEvent(result)) return null;
    const key = getToolExecutionKey(result, msgId);
    let execution = activeToolExecutions.get(key);
    let executionKey = key;
    if (!execution && !result.tool_call_id) {
        const resultStreamId = getPreparedToolStreamId(result);
        const match = Array.from(activeToolExecutions.entries()).find(([, item]) =>
            item.toolName === String(result.tool || '')
            && Number(item.messageId || 0) === Number(msgId || 0)
            && (!resultStreamId || item.streamId === resultStreamId)
        );
        executionKey = match?.[0] || key;
        execution = match?.[1];
    }
    if (!execution) {
        addToolMessage(
            result.tool,
            result.result,
            true,
            Number(result.duration_ms || 0),
            getToolTarget(result.tool, result.params || {}, result.target)
        );
        return;
    }

    clearInterval(execution.interval);
    activeToolExecutions.delete(executionKey);
    const toolDiv = execution.element;
    // Measure from the first streamed tool marker, including long argument/content generation.
    const frontendDuration = Math.max(0, Date.now() - execution.startedAt);
    const backendDuration = Math.max(0, Number(result.duration_ms || 0));
    const duration = Math.max(frontendDuration, backendDuration);
    const failed = toolResultFailed(result.result);
    const target = getToolTarget(result.tool, result.params || {}, result.target) || execution.target || '';
    toolDiv.classList.remove('tool-execution-running');
    toolDiv.classList.add(failed ? 'tool-execution-error' : 'tool-execution-complete');
    toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(result.tool || 'Tool')}</span>
                <span class="tool-summary">${escapeHtml(primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'} · ${formatToolDuration(duration)}`,
                    target
                ))}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result.result || ''))}</div>
        </details>`;
}

function finishActiveToolExecutions(label = '执行已停止', isError = false) {
    activeToolExecutions.forEach(execution => {
        clearInterval(execution.interval);
        execution.element.classList.remove('tool-execution-running');
        execution.element.classList.add(isError ? 'tool-execution-error' : 'tool-execution-complete');
        const summary = execution.element.querySelector('.tool-live-summary');
        if (summary) summary.textContent = label;
        const spinner = execution.element.querySelector('.tool-progress-spinner');
        if (spinner) spinner.textContent = isError ? '!' : '■';
        execution.element.querySelector('.tool-progress-track')?.remove();
    });
    activeToolExecutions.clear();
}

function discardActiveToolExecutions() {
    activeToolExecutions.forEach(execution => {
        clearInterval(execution.interval);
        execution.element.remove();
    });
    activeToolExecutions.clear();
}

function getCompressionKey(result, msgId) {
    return String(result.compression_id || `compression:${msgId}`);
}

function formatCompressionTokenCount(tokens) {
    const value = Math.max(0, Number(tokens || 0));
    if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 1 : 2)}k`;
    return String(Math.round(value));
}

function formatCompressionElapsed(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes ? `${minutes} 分 ${seconds} 秒` : `${seconds} 秒`;
}

function getCompressionModeLabel(mode) {
    return mode === 'auto' ? '自动压缩' : '手动压缩';
}

function startCompressionActivity(
    result, msgId, animate = true, announceStatus = true
) {
    const chatMessages = getChatRenderHost();
    const key = getCompressionKey(result, msgId);
    const existing = activeCompressionActivities.get(key);
    if (existing) return existing.element;

    const mode = result.mode === 'auto' ? 'auto' : 'manual';
    const backendStartedAt = Number(result.started_at_ms || 0);
    const startedAt = backendStartedAt > 0
        ? Math.min(Date.now(), backendStartedAt)
        : Date.now();
    const tokensBefore = Math.max(0, Number(result.tokens_before || 0));
    const stepCount = Math.max(0, Number(result.step_count || 0));
    const activity = document.createElement('div');
    activity.className = `compression-activity is-running is-${mode}`;
    activity.dataset.compressionId = key;
    activity.innerHTML = `
        <div class="compression-card" role="status" aria-live="polite">
            <div class="compression-header">
                <span class="compression-spinner" aria-hidden="true"><span></span></span>
                <span class="compression-title">正在压缩近期记忆</span>
                <span class="compression-mode">${getCompressionModeLabel(mode)}</span>
                <span class="compression-elapsed">0 秒</span>
            </div>
            <div class="compression-copy">
                <strong class="compression-stage">正在整理近期对话与执行记录</strong>
                <span class="compression-meta">${stepCount ? `${stepCount} 条记录 · ` : ''}${formatCompressionTokenCount(tokensBefore)} Token</span>
            </div>
            <div class="compression-progress-track" aria-hidden="true"><span></span></div>
        </div>`;
    chatMessages.appendChild(activity);
    if (animate) requestAnimationFrame(() => activity.classList.add('is-visible'));
    else activity.classList.add('is-visible');

    const state = {
        element: activity,
        interval: null,
        startedAt,
        mode,
        tokensBefore,
        stepCount,
    };
    const updateElapsed = () => {
        const elapsed = activity.querySelector('.compression-elapsed');
        if (elapsed) elapsed.textContent = formatCompressionElapsed(Date.now() - startedAt);
        followChatOutput(chatMessages);
    };
    updateElapsed();
    state.interval = setInterval(updateElapsed, 250);
    activeCompressionActivities.set(key, state);
    followChatOutput(chatMessages);
    if (announceStatus) {
        setAppStatus(
            'busy',
            mode === 'auto' ? '正在自动压缩记忆' : '正在压缩记忆'
        );
    }
    return activity;
}

function updateCompressionActivity(result, msgId) {
    const key = getCompressionKey(result, msgId);
    let state = activeCompressionActivities.get(key);
    if (!state) {
        startCompressionActivity(result, msgId);
        state = activeCompressionActivities.get(key);
    }
    const stage = state?.element.querySelector('.compression-stage');
    if (stage) stage.textContent = result.content || '正在持续整理近期记忆';
}

function finishCompressionActivity(result, msgId) {
    const key = getCompressionKey(result, msgId);
    let state = activeCompressionActivities.get(key);
    if (!state) {
        // Completed history is rendered as a completed card, not as a new job.
        startCompressionActivity(
            result,
            msgId,
            !isRestoringConversation,
            !isRestoringConversation
        );
        state = activeCompressionActivities.get(key);
    }
    if (!state) return null;

    clearInterval(state.interval);
    activeCompressionActivities.delete(key);
    const activity = state.element;
    const status = String(result.status || (result.success ? 'success' : 'error'));
    const success = Boolean(result.success);
    const isEmpty = status === 'empty';
    const tokensBefore = Math.max(0, Number(result.tokens_before ?? state.tokensBefore));
    const tokensAfter = Math.max(0, Number(result.tokens_after || 0));
    const released = Math.max(0, Number(result.released_tokens ?? (tokensBefore - tokensAfter)));
    const durationMs = Math.max(0, Number(result.duration_ms || (Date.now() - state.startedAt)));
    const archivePath = String(result.archive_path || '');
    const title = success
        ? '记忆压缩完成'
        : isEmpty
            ? '没有可压缩的近期记忆'
            : '记忆压缩失败';
    const tokenSummary = tokensBefore > 0
        ? `${formatCompressionTokenCount(tokensBefore)} → ${formatCompressionTokenCount(tokensAfter)} Token · 释放 ${formatCompressionTokenCount(released)} Token`
        : '近期记忆已整理';
    const summary = success
        ? `${tokenSummary} · ${formatToolDuration(durationMs)}`
        : `${result.message || '压缩未完成'} · ${formatToolDuration(durationMs)}`;

    activity.classList.remove('is-running');
    activity.classList.add(success ? 'is-complete' : isEmpty ? 'is-empty' : 'is-error');
    activity.innerHTML = `
        <details class="compression-card compression-card-complete"${archivePath ? '' : ' open'}>
            <summary class="compression-header">
                <span class="compression-status-icon" aria-hidden="true">${success ? '✓' : isEmpty ? '—' : '!'}</span>
                <span class="compression-title">${title}</span>
                <span class="compression-mode">${getCompressionModeLabel(result.mode || state.mode)}</span>
                <svg class="compression-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="compression-result">
                <strong>${escapeHtml(summary)}</strong>
                <p>${escapeHtml(result.message || title)}</p>
                ${archivePath ? `<code>${escapeHtml(archivePath)}</code>` : ''}
            </div>
        </details>`;
    if (isRestoringConversation) activity.classList.add('did-finish');
    else requestAnimationFrame(() => activity.classList.add('did-finish'));
    restoreStatusAfterCompression();
    return activity;
}

function restoreStatusAfterCompression() {
    if (isRestoringConversation || activeCompressionActivities.size) return;
    if (isProcessing) {
        // The backend releases execution just after it publishes compression_end.
        // Keep the state accurate during that small hand-off instead of retaining
        // a stale "正在自动压缩记忆" label.
        setAppStatus('busy', '正在完成任务');
    } else if (isInitialized) {
        setAppStatus('ready', '就绪');
    }
}

function failActiveCompressionActivities(message = '压缩已中断') {
    activeCompressionActivities.forEach((state, key) => {
        finishCompressionActivity({
            compression_id: key,
            mode: state.mode,
            success: false,
            status: 'error',
            message,
            tokens_before: state.tokensBefore,
            tokens_after: state.tokensBefore,
            released_tokens: 0,
            duration_ms: Date.now() - state.startedAt,
        }, currentMessageId);
    });
}

function clearCompressionActivities() {
    activeCompressionActivities.forEach(state => {
        clearInterval(state.interval);
        state.element.remove();
    });
    activeCompressionActivities.clear();
}

function cancelSiblingPreparedToolExecutions(result, msgId) {
    const pendingKey = getToolExecutionKey(result, msgId);
    const pendingStreamId = getPreparedToolStreamId(result);
    const pendingExecution = activeToolExecutions.get(pendingKey);
    const resolvedStreamId = pendingStreamId || pendingExecution?.streamId || '';
    const removals = [];

    activeToolExecutions.forEach((execution, key) => {
        if (Number(execution.messageId || 0) !== Number(msgId || 0)) return;
        if (resolvedStreamId && execution.streamId !== resolvedStreamId) return;
        if (!resolvedStreamId && key !== pendingKey) return;
        if (execution.isPreparing || key === pendingKey) removals.push([key, execution]);
    });

    removals.forEach(([key, execution]) => {
        clearInterval(execution.interval);
        execution.element.classList.add('is-cancelled');
        activeToolExecutions.delete(key);
        const remove = () => execution.element.remove();
        execution.element.addEventListener('transitionend', remove, {once: true});
        setTimeout(remove, 240);
    });
}

function addToolMessage(
    toolName,
    result,
    animate = true,
    durationMs = 0,
    target = '',
    actor = 'primary'
) {
    if (isQuestionToolName(toolName) || !isPrimaryToolEvent({actor})) return null;
    const chatMessages = getChatRenderHost();
    const toolDiv = document.createElement('div');
    const failed = toolResultFailed(result);
    toolDiv.className = `tool-execution ${failed ? 'tool-execution-error' : ''}`;
    toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(toolName)}</span>
                <span class="tool-summary">${escapeHtml(primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'}${durationMs > 0 ? ` · ${formatToolDuration(durationMs)}` : ''}`,
                    target
                ))}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result))}</div>
        </details>
    `;
    chatMessages.appendChild(toolDiv);
    if (animate) requestAnimationFrame(() => toolDiv.classList.add('is-visible'));
    else toolDiv.classList.add('is-visible');
    if (!isRestoringConversation) followChatOutput(chatMessages);
    return toolDiv;
}

function normalizeModifiedFiles(result) {
    const merged = new Map();
    (Array.isArray(result?.files) ? result.files : []).forEach(item => {
        const path = String(item?.path || '').trim();
        if (!path) return;
        const existing = merged.get(path) || {
            path,
            additions: 0,
            deletions: 0,
            reviewable: false,
            review_reason: '',
            hunks: [],
        };
        existing.additions += Math.max(0, Number(item?.additions || 0));
        existing.deletions += Math.max(0, Number(item?.deletions || 0));
        existing.reviewable = Boolean(item?.reviewable);
        existing.review_reason = String(item?.review_reason || '');
        existing.hunks = (Array.isArray(item?.hunks) ? item.hunks : []).map(hunk => ({
            old_start: Math.max(0, Number(hunk?.old_start || 0)),
            old_count: Math.max(0, Number(hunk?.old_count || 0)),
            new_start: Math.max(0, Number(hunk?.new_start || 0)),
            new_count: Math.max(0, Number(hunk?.new_count || 0)),
            lines: (Array.isArray(hunk?.lines) ? hunk.lines : []).map(line => ({
                type: ['context', 'add', 'delete'].includes(line?.type)
                    ? line.type
                    : 'context',
                old_line: line?.old_line == null ? null : Number(line.old_line),
                new_line: line?.new_line == null ? null : Number(line.new_line),
                content: String(line?.content || ''),
            })),
        }));
        merged.set(path, existing);
    });
    return Array.from(merged.values());
}

function changeReviewDirKey(parentPath, name) {
    return parentPath ? `${parentPath}/${name}` : name;
}

function changeReviewCommonRoot(files) {
    const paths = files
        .map(file => String(file.path || '').replace(/\\/g, '/'))
        .filter(Boolean);
    if (!paths.length) return '';
    let common = paths[0].split('/').slice(0, -1);
    for (const path of paths.slice(1)) {
        const parts = path.split('/').slice(0, -1);
        let i = 0;
        while (i < common.length && i < parts.length && common[i] === parts[i]) {
            i += 1;
        }
        common = common.slice(0, i);
        if (!common.length) break;
    }
    return common.join('/');
}

function buildChangeReviewTree(files, stripPrefix) {
    const root = {name: '', children: new Map(), file: null};
    files.forEach((file, index) => {
        let path = String(file.path || '').replace(/\\/g, '/');
        if (stripPrefix && path.startsWith(`${stripPrefix}/`)) {
            path = path.slice(stripPrefix.length + 1);
        }
        const parts = path.split('/').filter(Boolean);
        if (!parts.length) return;
        let node = root;
        for (let i = 0; i < parts.length - 1; i++) {
            const segment = parts[i];
            if (!node.children.has(segment)) {
                node.children.set(segment, {name: segment, children: new Map(), file: null});
            }
            node = node.children.get(segment);
        }
        const fileName = parts[parts.length - 1];
        node.children.set(fileName, {name: fileName, children: new Map(), file: {...file, index}});
    });
    if (stripPrefix) {
        return {
            name: stripPrefix.split('/').pop() || stripPrefix,
            children: root.children,
            file: null,
        };
    }
    return root;
}

function renderChangeReviewTreeNodes(node, depth, parentPath, selectedPath, collapsedDirs) {
    let html = '';
    if (node.name) {
        const dirKey = changeReviewDirKey(parentPath, node.name);
        const collapsed = collapsedDirs.has(dirKey);
        html += `
            <button class="change-review-tree-row" type="button" data-review-dir="${escapeHtml(dirKey)}" aria-expanded="${!collapsed}" style="padding-left:${8 + depth * 14}px" title="${escapeHtml(dirKey)}">
                <span class="change-review-dir-arrow" aria-hidden="true">${collapsed ? '▸' : '▾'}</span>
                <span class="change-review-dir-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>
                </span>
                <span class="change-review-dir-name">${escapeHtml(node.name)}</span>
            </button>`;
        if (collapsed) return html;
        depth += 1;
        parentPath = dirKey;
    }
    const dirs = [];
    const leaves = [];
    for (const child of node.children.values()) {
        (child.file ? leaves : dirs).push(child);
    }
    dirs.sort((a, b) => a.name.localeCompare(b.name));
    leaves.sort((a, b) => a.name.localeCompare(b.name));
    for (const dir of dirs) {
        html += renderChangeReviewTreeNodes(
            dir, depth, parentPath, selectedPath, collapsedDirs
        );
    }
    for (const leaf of leaves) {
        const file = leaf.file;
        const active = file.path === selectedPath;
        html += `
            <button class="change-review-file${active ? ' is-active' : ''}" type="button" data-review-file-index="${file.index}" style="padding-left:${11 + depth * 14}px" title="${escapeHtml(file.path)}">
                <span class="change-review-file-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5"/></svg>
                </span>
                <span class="change-review-file-name">${escapeHtml(leaf.name)}</span>
                <span class="change-review-file-counts"><b>+${file.additions}</b><em>-${file.deletions}</em></span>
            </button>`;
    }
    return html;
}

function renderChangeReviewFiles() {
    const fileList = document.getElementById('changeReviewFileList');
    if (!fileList || !activeChangeReview) return;
    const selectedPath = activeChangeReview.files[activeChangeReview.selectedIndex]?.path;
    const root = buildChangeReviewTree(
        activeChangeReview.files, activeChangeReview.treeRoot
    );
    fileList.innerHTML = renderChangeReviewTreeNodes(
        root, 0, '', selectedPath, activeChangeReview.collapsedDirs
    );
}

function toggleChangeReviewDir(dirKey) {
    if (!activeChangeReview) return;
    if (activeChangeReview.collapsedDirs.has(dirKey)) {
        activeChangeReview.collapsedDirs.delete(dirKey);
    } else {
        activeChangeReview.collapsedDirs.add(dirKey);
    }
    renderChangeReviewFiles();
}

function expandChangeReviewAncestors(path) {
    if (!activeChangeReview) return;
    let normalized = String(path || '').replace(/\\/g, '/');
    const strip = activeChangeReview.treeRoot;
    if (strip && normalized.startsWith(`${strip}/`)) {
        normalized = normalized.slice(strip.length + 1);
    }
    if (strip) {
        activeChangeReview.collapsedDirs.delete(strip.split('/').pop());
    }
    const parts = normalized.split('/').filter(Boolean);
    parts.pop();
    let prefix = '';
    for (const part of parts) {
        prefix = prefix ? `${prefix}/${part}` : part;
        activeChangeReview.collapsedDirs.delete(prefix);
    }
}

function renderChangeReviewDiff() {
    const fileHeader = document.getElementById('changeReviewFileHeader');
    const diff = document.getElementById('changeReviewDiff');
    if (!fileHeader || !diff || !activeChangeReview) return;
    diff.classList.remove('change-review-editing');
    const file = activeChangeReview.files[activeChangeReview.selectedIndex];
    if (!file) {
        fileHeader.textContent = '';
        diff.innerHTML = '<div class="change-review-empty">没有可审核的文件</div>';
        return;
    }
    fileHeader.innerHTML = `
        <span title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</span>
        <span class="change-review-file-counts"><b>+${file.additions}</b><em>-${file.deletions}</em></span>
        <button class="change-review-edit" type="button" title="编辑此文件（基于磁盘上的最新内容）">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            <span>编辑</span>
        </button>`;
    if (!file.reviewable || !file.hunks.length) {
        diff.innerHTML = `
            <div class="change-review-empty">
                <strong>无法显示逐行差异</strong>
                <span>${escapeHtml(file.review_reason || '此文件没有可显示的文本差异')}</span>
            </div>`;
        return;
    }
    diff.innerHTML = file.hunks.map(hunk => `
        <section class="change-review-hunk">
            <div class="change-review-hunk-header">@@ -${hunk.old_start},${hunk.old_count} +${hunk.new_start},${hunk.new_count} @@</div>
            <div class="change-review-lines">
                ${hunk.lines.map(line => {
                    const type = ['add', 'delete'].includes(line.type) ? line.type : 'context';
                    const marker = type === 'add' ? '+' : type === 'delete' ? '-' : ' ';
                    return `<div class="change-review-line change-review-line-${type}">
                        <span class="change-review-line-number">${line.old_line ?? ''}</span>
                        <span class="change-review-line-number">${line.new_line ?? ''}</span>
                        <span class="change-review-line-marker" aria-hidden="true">${marker}</span>
                        <code>${escapeHtml(line.content)}</code>
                    </div>`;
                }).join('')}
            </div>
        </section>`).join('');
}

function selectChangeReviewFile(pathOrIndex) {
    if (!activeChangeReview) return;
    const nextIndex = Number.isInteger(Number(pathOrIndex))
        ? Number(pathOrIndex)
        : activeChangeReview.files.findIndex(file => file.path === pathOrIndex);
    if (nextIndex < 0 || nextIndex >= activeChangeReview.files.length) return;
    activeChangeReview.selectedIndex = nextIndex;
    expandChangeReviewAncestors(activeChangeReview.files[nextIndex].path);
    renderChangeReviewFiles();
    renderChangeReviewDiff();
}

let changeReviewEditState = null;

async function openChangeReviewEditor() {
    const fileHeader = document.getElementById('changeReviewFileHeader');
    const diff = document.getElementById('changeReviewDiff');
    if (!fileHeader || !diff || !activeChangeReview) return;
    const file = activeChangeReview.files[activeChangeReview.selectedIndex];
    if (!file) return;
    try {
        const result = await eel.read_review_file(file.path)();
        if (!result || !result.success) {
            showToast(result?.error || '无法读取文件', 'error');
            return;
        }
        changeReviewEditState = {
            path: file.path,
            fingerprint: result.fingerprint,
        };
        const content = String(result.content || '');
        fileHeader.innerHTML = `
            <span title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</span>
            <span class="change-review-file-counts"><b>+${file.additions}</b><em>-${file.deletions}</em></span>
            <button class="change-review-edit-action change-review-edit-save" type="button" title="保存修改">保存</button>
            <button class="change-review-edit-action change-review-edit-cancel" type="button" title="取消编辑">取消</button>`;
        diff.innerHTML = `
            <div class="change-review-inline-editor">
                <div class="change-review-editor-gutter" aria-hidden="true"></div>
                <textarea class="change-review-editor-input" spellcheck="false"></textarea>
            </div>`;
        diff.classList.add('change-review-editing');
        const textarea = diff.querySelector('.change-review-editor-input');
        const gutter = diff.querySelector('.change-review-editor-gutter');
        textarea.value = content;
        refreshReviewEditorGutter(diff);
        textarea.addEventListener('input', () => refreshReviewEditorGutter(diff));
        textarea.addEventListener('scroll', () => {
            const gutter = diff.querySelector('.change-review-editor-gutter');
            if (gutter) gutter.scrollTop = textarea.scrollTop;
        });
        fileHeader.querySelector('.change-review-edit-save').addEventListener('click', saveChangeReviewFile);
        fileHeader.querySelector('.change-review-edit-cancel').addEventListener('click', closeChangeReviewEditor);
        textarea.focus();
        textarea.setSelectionRange(0, 0);
        // focus/setSelectionRange 之后浏览器可能重新滚动（长文件时容易
        // 停在底部），这里强制回顶，并用下一帧兜底（布局完成后
        // scrollHeight 才稳定，直接赋值 scrollTop 才可靠）。
        textarea.scrollTop = 0;
        textarea.scrollLeft = 0;
        if (gutter) gutter.scrollTop = 0;
        requestAnimationFrame(() => {
            textarea.scrollTop = 0;
            textarea.scrollLeft = 0;
            if (gutter) gutter.scrollTop = 0;
        });
    } catch (error) {
        showToast(`读取失败：${error.message || error}`, 'error');
    }
}

function refreshReviewEditorGutter(diff) {
    const gutter = diff.querySelector('.change-review-editor-gutter');
    const textarea = diff.querySelector('.change-review-editor-input');
    if (!gutter || !textarea) return;
    const count = Math.max(1, textarea.value.split('\n').length);
    const fragment = [];
    for (let index = 1; index <= count; index += 1) {
        fragment.push(`<span>${index}</span>`);
    }
    gutter.innerHTML = fragment.join('');
}

async function saveChangeReviewFile() {
    const fileHeader = document.getElementById('changeReviewFileHeader');
    const diff = document.getElementById('changeReviewDiff');
    if (!fileHeader || !diff || !changeReviewEditState) return;
    const textarea = diff.querySelector('.change-review-editor-input');
    if (!textarea) return;
    const button = fileHeader.querySelector('.change-review-edit-save');
    if (button) button.disabled = true;
    try {
        const result = await eel.save_review_file(
            changeReviewEditState.path,
            textarea.value,
            changeReviewEditState.fingerprint || ''
        )();
        if (!result || !result.success) {
            showToast(result?.error || '保存失败', 'error', result?.stale ? 6000 : 3000);
            return;
        }
        showToast(result.unchanged ? '内容未变化，未写入' : '已保存', 'success');
        changeReviewEditState = null;
        renderChangeReviewDiff();
    } catch (error) {
        showToast(`保存失败：${error.message || error}`, 'error');
    } finally {
        if (button) button.disabled = false;
    }
}

function closeChangeReviewEditor() {
    changeReviewEditState = null;
    renderChangeReviewDiff();
}

function restoreChatAfterReviewLayout(chatMessages, distanceFromBottom) {
    if (!chatMessages) return;
    const align = frames => {
        if (distanceFromBottom < 72) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            chatMessages.scrollTop = Math.max(
                0,
                chatMessages.scrollHeight - chatMessages.clientHeight - distanceFromBottom
            );
        }
        if (frames > 0) requestAnimationFrame(() => align(frames - 1));
    };
    requestAnimationFrame(() => align(2));
}

function openChangeReview(result, initialPath = '') {
    const panel = document.getElementById('changeReviewPanel');
    const files = normalizeModifiedFiles(result);
    if (!panel || !files.length) return;
    closeAgentDetail({restoreFocus: false});
    const chatMessages = document.getElementById('chatMessages');
    const distanceFromBottom = chatMessages
        ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        : 0;
    const selectedIndex = Math.max(0, files.findIndex(file => file.path === initialPath));
    activeChangeReview = {
        conversationId: String(result?.conversation_id || activeConversationId || ''),
        messageId: Number(result?.message_id || 0),
        files,
        selectedIndex,
        collapsedDirs: new Set(),
        treeRoot: changeReviewCommonRoot(files),
        lastFocus: document.activeElement,
    };
    expandChangeReviewAncestors(files[selectedIndex]?.path || '');
    document.getElementById('changeReviewTotals').innerHTML = `
        <b>+${files.reduce((total, file) => total + file.additions, 0)}</b>
        <em>-${files.reduce((total, file) => total + file.deletions, 0)}</em>`;
    panel.removeAttribute('aria-hidden');
    document.body.classList.add('change-review-open');
    syncDockedLayoutWidths();
    renderChangeReviewFiles();
    renderChangeReviewDiff();
    requestAnimationFrame(() => panel.classList.add('is-open'));
    restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
}

function closeChangeReview({restoreFocus = true} = {}) {
    const panel = document.getElementById('changeReviewPanel');
    if (!panel) return;
    const chatMessages = document.getElementById('chatMessages');
    const distanceFromBottom = chatMessages
        ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        : 0;
    const focusTarget = activeChangeReview?.lastFocus;
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('change-review-open');
    activeChangeReview = null;
    setSidebarPanelWidth(getSavedSidebarPanelWidth(), {persist: false});
    restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
    if (restoreFocus && focusTarget?.isConnected) focusTarget.focus();
}

function addModifiedFilesSummary(result, animate = true) {
    const chatMessages = getChatRenderHost();
    if (!chatMessages) return null;
    const files = normalizeModifiedFiles(result);
    if (!files.length) return null;

    const additions = files.reduce((total, item) => total + item.additions, 0);
    const deletions = files.reduce((total, item) => total + item.deletions, 0);
    const reviewAvailable = files.some(file => (
        file.reviewable || file.hunks.length || file.review_reason
    ));
    const messageId = Number(result?.message_id || 0);
    const existing = messageId
        ? chatMessages.querySelector(`.modified-files-summary[data-message-id="${messageId}"]`)
        : null;
    if (existing) {
        if (!isRestoringConversation) pinChatToBottom(chatMessages);
        return existing;
    }

    const summary = document.createElement('section');
    summary.className = 'modified-files-summary';
    if (messageId) summary.dataset.messageId = String(messageId);
    const reviewResult = {...result, files};
    summary._modifiedFilesResult = reviewResult;
    summary.innerHTML = `
        <div class="modified-files-header">
            <span class="modified-files-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 3h8l4 4v11a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3h1Z"/><path d="M14 3v5h5M12 10v6m-3-3h6"/></svg>
            </span>
            <div class="modified-files-title-block">
                <strong>已编辑 ${files.length} 个文件</strong>
                <span class="modified-files-total" aria-label="新增 ${additions} 行，删除 ${deletions} 行" title="新增 ${additions} 行，删除 ${deletions} 行"><b class="modified-files-added">+${additions}</b> <b class="modified-files-deleted">-${deletions}</b></span>
            </div>
            ${reviewAvailable ? '<button class="modified-files-review" type="button">审核</button>' : ''}
            ${result.rollback_available ? '<button class="modified-files-rollback" type="button" title="撤销这个任务对文件的全部修改，恢复到任务开始前的状态">回退 ⏎</button>' : ''}
        </div>
        <div class="modified-files-list">
            ${files.map((file, index) => `
                <button class="modified-files-row" type="button" data-review-file-index="${index}" ${reviewAvailable ? '' : 'disabled'}>
                    <code title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</code>
                    <span class="modified-files-counts" aria-label="新增 ${file.additions} 行，删除 ${file.deletions} 行" title="新增 ${file.additions} 行，删除 ${file.deletions} 行"><b class="modified-files-added">+${file.additions}</b> <b class="modified-files-deleted">-${file.deletions}</b></span>
                </button>`).join('')}
        </div>`;
    summary.querySelector('.modified-files-review')?.addEventListener('click', () => {
        openChangeReview(reviewResult);
    });
    summary.querySelector('.modified-files-rollback')?.addEventListener('click', () => {
        rollbackTaskCard(summary);
    });
    summary.querySelectorAll('.modified-files-row').forEach(row => {
        row.addEventListener('click', () => {
            const index = Number(row.dataset.reviewFileIndex || 0);
            openChangeReview(reviewResult, files[index]?.path || '');
        });
    });
    chatMessages.appendChild(summary);
    if (animate) requestAnimationFrame(() => summary.classList.add('is-visible'));
    else summary.classList.add('is-visible');
    if (!isRestoringConversation) {
        pinChatToBottom(chatMessages);
        refreshTaskRollbackButtons(
            result.conversation_id || activeConversationId
        );
    }
    return summary;
}

function normalizeLocalPreviewUrl(value) {
    try {
        const parsed = new URL(String(value || '').trim());
        const allowedHosts = new Set(['127.0.0.1', '[::1]', '::1']);
    if (parsed.protocol !== 'http:') return '';
        if (parsed.username || parsed.password || parsed.hash) return '';
        if (!allowedHosts.has(String(parsed.hostname || '').toLowerCase())) return '';
        if (!parsed.port || parsed.port === '0') return '';
        return parsed.href;
    } catch (error) {
        return '';
    }
}

function normalizePreviewStatus(value, hasUrl = false) {
    const status = String(value || '').trim().toLowerCase();
    if (['ready', 'running', 'active', 'healthy', 'started'].includes(status)) return 'ready';
    if (['stopping', 'stopped', 'closed', 'exited', 'terminated'].includes(status)) return 'stopped';
    if (['error', 'failed', 'timeout', 'unhealthy'].includes(status)) return 'error';
    if (['starting', 'pending', 'launching', 'booting'].includes(status)) return 'starting';
    return hasUrl ? 'ready' : 'starting';
}

function normalizePreviewSession(raw) {
    const source = raw?.preview && typeof raw.preview === 'object'
        ? {...raw, ...raw.preview}
        : (raw || {});
    const previewId = String(source.preview_id || source.id || '').trim();
    if (!previewId) return null;

    const existing = previewSessions.get(previewId) || {};
    const hasSuppliedUrl = Object.prototype.hasOwnProperty.call(source, 'url');
    const suppliedUrl = hasSuppliedUrl ? String(source.url || '').trim() : '';
    const candidateUrl = suppliedUrl
        ? normalizeLocalPreviewUrl(suppliedUrl)
        : (hasSuppliedUrl ? '' : existing.url || '');
    const rejectedUrl = Boolean(suppliedUrl) && !candidateUrl;
    const status = normalizePreviewStatus(source.status, Boolean(candidateUrl));
    let host = '';
    let detectedPort = '';
    if (candidateUrl) {
        const parsed = new URL(candidateUrl);
        host = parsed.host;
        detectedPort = parsed.port;
    }

    return {
        ...existing,
        previewId,
        status: rejectedUrl ? 'error' : status,
        url: candidateUrl,
        name: String(source.name || existing.name || '项目预览').trim() || '项目预览',
        port: String(source.port || detectedPort || existing.port || '').trim(),
        host: host || existing.host || '',
        message: rejectedUrl
            ? '预览地址未通过本机安全校验'
            : String(source.message || source.content || source.error || existing.message || '').trim(),
        conversationId: String(
            source.conversation_id || existing.conversationId || activeConversationId || ''
        ),
    };
}

function getPreviewStatusCopy(session) {
    if (session.status === 'ready') {
        return {
            label: '运行中',
            detail: session.message || '网站已在本地浏览器沙盒中运行',
            action: '打开预览',
        };
    }
    if (session.status === 'stopped') {
        return {
            label: '已停止',
            detail: session.message || '本地预览服务已停止',
            action: '预览已停止',
        };
    }
    if (session.status === 'error') {
        return {
            label: '启动失败',
            detail: session.message || '预览服务未能正常启动，请检查运行日志',
            action: '无法打开',
        };
    }
    return {
        label: '正在启动',
        detail: session.message || '正在启动项目并等待本地端口就绪',
        action: '准备中',
    };
}

function upsertProjectPreview(raw, animate = true) {
    const session = normalizePreviewSession(raw);
    if (!session) return null;
    if (session.conversationId
        && activeConversationId
        && session.conversationId !== String(activeConversationId)) {
        return null;
    }

    previewSessions.set(session.previewId, session);
    if (activePreviewId === session.previewId) updateOpenPreviewSession(session);
    renderPreviewDock(animate);
    return null;
}

function renderPreviewDock(animate = true) {
    const dock = document.getElementById('previewDock');
    if (!dock) return;
    const activeSessions = [...previewSessions.values()].filter(session =>
        session.status === 'starting' || session.status === 'ready'
    );
    if (!activeSessions.length) {
        dock.classList.remove('is-visible');
        dock.setAttribute('aria-hidden', 'true');
        return;
    }
    dock.classList.add('is-visible');
    dock.setAttribute('aria-hidden', 'false');
    const existing = new Map(
        [...dock.querySelectorAll('.preview-dock-pill')].map(pill => [
            String(pill.dataset.previewId || ''), pill
        ])
    );
    const fragment = document.createDocumentFragment();
    activeSessions.forEach(session => {
        let pill = existing.get(session.previewId);
        if (!pill) {
            pill = document.createElement('div');
            pill.className = 'preview-dock-pill';
            pill.dataset.previewId = session.previewId;
            pill.setAttribute('role', 'button');
            pill.setAttribute('tabindex', '0');
            pill.innerHTML = `
                <span class="preview-dock-dot" aria-hidden="true"></span>
                <span class="preview-dock-name"></span>
                <span class="preview-dock-status"></span>
                <button class="preview-dock-stop" type="button" title="停止预览" aria-label="停止预览">
                    <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>
                </button>`;
            pill.addEventListener('click', () => {
                openBrowserPreview(String(pill.dataset.previewId || ''));
            });
            pill.addEventListener('keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openBrowserPreview(String(pill.dataset.previewId || ''));
                }
            });
            pill.querySelector('.preview-dock-stop')?.addEventListener('click', event => {
                event.stopPropagation();
                event.preventDefault();
                stopPreviewSession(String(pill.dataset.previewId || ''));
            });
        }
        const copy = getPreviewStatusCopy(session);
        const isReady = session.status === 'ready';
        pill.classList.toggle('is-ready', isReady);
        pill.classList.toggle('is-starting', session.status === 'starting');
        pill.querySelector('.preview-dock-name').textContent = session.name;
        pill.querySelector('.preview-dock-status').textContent = isReady
            ? (session.port ? `:${session.port}` : '运行中')
            : copy.label;
        pill.title = `${session.name} · ${copy.detail}`;
        fragment.appendChild(pill);
        existing.delete(session.previewId);
    });
    existing.forEach(pill => pill.remove());
    dock.replaceChildren(fragment);
}

async function syncPreviewSessions(conversationId) {
    if (!conversationId || !canCallEel()
        || typeof eel.get_preview_sessions !== 'function') return;
    const generation = ++previewSyncGeneration;
    try {
        const result = await eel.get_preview_sessions(conversationId)();
        if (generation !== previewSyncGeneration
            || String(conversationId) !== String(activeConversationId || '')) return;
        const rawSessions = Array.isArray(result)
            ? result
            : (result?.sessions || result?.previews || []);
        if (result && !Array.isArray(result) && result.success === false) {
            throw new Error(result.error || '预览状态同步失败');
        }
        const sessions = Array.isArray(rawSessions) ? rawSessions : [];
        sessions.forEach(session => upsertProjectPreview({
            ...session,
            conversation_id: session.conversation_id || conversationId,
        }, false));
        // Reconcile with the backend: a preview that stopped on its own, or
        // whose owning manager was recreated without a delivered event, is
        // absent from the snapshot and must leave the floating dock.
        const reported = new Set(
            sessions
                .map(session => String(session.preview_id || session.id || '').trim())
                .filter(Boolean)
        );
        let changed = false;
        for (const [previewId, session] of previewSessions) {
            if (String(session.conversationId || '') !== String(conversationId)) continue;
            if (reported.has(previewId)) continue;
            previewSessions.delete(previewId);
            changed = true;
        }
        if (changed) {
            if (activePreviewId && !previewSessions.has(activePreviewId)) {
                closeBrowserPreview(false);
            }
            renderPreviewDock(false);
        }
    } catch (error) {
        if (handleEelConnectionError(error)) return;
        console.error('Failed to sync preview sessions:', error);
    }
}

function findRegisteredPreviewForUrl(value) {
    const url = normalizeLocalPreviewUrl(value);
    if (!url) return null;
    const target = new URL(url);
    for (const session of previewSessions.values()) {
        if (session.status !== 'ready' || !session.url) continue;
        const base = new URL(session.url);
        if (base.origin === target.origin) return {session, url};
    }
    return null;
}

function setBrowserPreviewLoading(title = '正在连接本地预览', detail = '') {
    const state = document.getElementById('browserPreviewState');
    if (!state) return;
    state.classList.add('is-visible', 'is-loading');
    state.classList.remove('is-error');
    document.getElementById('browserPreviewStateTitle').textContent = title;
    document.getElementById('browserPreviewStateDetail').textContent = detail
        || '正在等待页面完成加载';
}

function showBrowserPreviewUnavailable(title, detail) {
    const state = document.getElementById('browserPreviewState');
    if (!state) return;
    state.classList.add('is-visible', 'is-error');
    state.classList.remove('is-loading');
    document.getElementById('browserPreviewStateTitle').textContent = title;
    document.getElementById('browserPreviewStateDetail').textContent = detail;
}

function hideBrowserPreviewState() {
    const state = document.getElementById('browserPreviewState');
    state?.classList.remove('is-visible', 'is-loading', 'is-error');
}

function updateOpenPreviewSession(session) {
    const modal = document.getElementById('browserPreviewModal');
    if (!modal?.classList.contains('active')) return;
    document.getElementById('browserPreviewTitle').textContent = session.name;
    document.getElementById('browserPreviewStatus').textContent = getPreviewStatusCopy(session).label;
    const stopButton = document.getElementById('browserPreviewStop');
    const externalButton = document.getElementById('browserPreviewExternal');
    const refreshButton = document.getElementById('browserPreviewRefresh');
    const canOpen = session.status === 'ready' && Boolean(session.url);
    if (stopButton) stopButton.disabled = ['stopped', 'error'].includes(session.status);
    if (externalButton) externalButton.disabled = !canOpen;
    if (refreshButton) refreshButton.disabled = !canOpen;

    if (canOpen) return;
    activePreviewUrl = '';
    const frame = document.getElementById('browserPreviewFrame');
    if (frame) frame.src = 'about:blank';
    const copy = getPreviewStatusCopy(session);
    showBrowserPreviewUnavailable(copy.label, copy.detail);
}

function loadBrowserPreviewUrl(value) {
    const url = normalizeLocalPreviewUrl(value);
    const frame = document.getElementById('browserPreviewFrame');
    if (!url || !frame) return false;
    activePreviewUrl = url;
    document.getElementById('browserPreviewAddress').value = url;
    setBrowserPreviewLoading();
    frame.src = url;
    return true;
}

function openBrowserPreview(previewId, requestedUrl = '') {
    const session = previewSessions.get(String(previewId || ''));
    if (!session || session.status !== 'ready' || !session.url) {
        showToast('该项目的本地预览尚未就绪', 'info');
        return;
    }
    const targetUrl = normalizeLocalPreviewUrl(requestedUrl || session.url);
    const targetOrigin = targetUrl ? new URL(targetUrl).origin : '';
    if (!targetUrl || targetOrigin !== new URL(session.url).origin) {
        showToast('预览地址不属于已登记的本地服务', 'error');
        return;
    }

    const modal = document.getElementById('browserPreviewModal');
    previewLastFocusedElement = document.activeElement;
    activePreviewId = session.previewId;
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('browser-preview-open');
    notifyParentBrowserPreview(true);
    updateOpenPreviewSession(session);
    loadBrowserPreviewUrl(targetUrl);
    document.getElementById('browserPreviewClose')?.focus();
}

function closeBrowserPreview(restoreFocus = true) {
    const modal = document.getElementById('browserPreviewModal');
    const frame = document.getElementById('browserPreviewFrame');
    if (frame) frame.src = 'about:blank';
    if (modal) {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
    }
    hideBrowserPreviewState();
    document.body.classList.remove('browser-preview-open');
    notifyParentBrowserPreview(false);
    activePreviewId = null;
    activePreviewUrl = '';
    if (restoreFocus) previewLastFocusedElement?.focus?.();
    previewLastFocusedElement = null;
}

function refreshBrowserPreview() {
    const session = previewSessions.get(String(activePreviewId || ''));
    const url = normalizeLocalPreviewUrl(activePreviewUrl || session?.url || '');
    const frame = document.getElementById('browserPreviewFrame');
    if (!session || session.status !== 'ready' || !url || !frame) return;
    setBrowserPreviewLoading('正在刷新预览', '正在重新加载本地页面');
    frame.src = url;
}

async function copyBrowserPreviewAddress() {
    const url = normalizeLocalPreviewUrl(activePreviewUrl);
    if (!url) return;
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(url);
        } else {
            const input = document.getElementById('browserPreviewAddress');
            input.focus();
            input.select();
            document.execCommand('copy');
            document.getElementById('browserPreviewClose')?.focus();
        }
        showToast('预览地址已复制', 'success');
    } catch (error) {
        showToast('复制地址失败', 'error');
    }
}

async function openBrowserPreviewExternal() {
    const previewId = String(activePreviewId || '');
    const session = previewSessions.get(previewId);
    if (!session || session.status !== 'ready'
        || typeof eel === 'undefined'
        || typeof eel.open_preview_external !== 'function') return;
    try {
        const result = await eel.open_preview_external(
            previewId, activeConversationId || ''
        )();
        if (result?.success === false) throw new Error(result.error || '打开失败');
    } catch (error) {
        showToast(`外部打开失败：${error.message}`, 'error');
    }
}

async function stopPreviewSession(previewId) {
    const session = previewSessions.get(String(previewId || ''));
    if (!session || ['stopped', 'error'].includes(session.status)
        || typeof eel === 'undefined'
        || typeof eel.stop_project_preview !== 'function') return;
    try {
        const result = await eel.stop_project_preview(
            previewId, activeConversationId || ''
        )();
        if (result?.success === false) throw new Error(result.error || '停止失败');
        upsertProjectPreview({
            ...result,
            preview_id: previewId,
            status: 'stopped',
            message: result?.message || result?.stop_reason || '预览服务已停止',
        });
        showToast('本地预览服务已停止', 'success');
    } catch (error) {
        showToast(`停止预览失败：${error.message}`, 'error');
    }
}

async function stopBrowserPreview() {
    const previewId = String(activePreviewId || '');
    const session = previewSessions.get(previewId);
    if (!session || ['stopped', 'error'].includes(session.status)) return;
    const button = document.getElementById('browserPreviewStop');
    if (button) button.disabled = true;
    await stopPreviewSession(previewId);
}

function handlePreviewLinkClick(event) {
    const link = event.target.closest('a[data-local-preview-url]');
    if (!link) return;
    event.preventDefault();
    const match = findRegisteredPreviewForUrl(link.dataset.localPreviewUrl || '');
    if (!match) {
        showToast('该本地地址没有可用的项目预览会话', 'info');
        return;
    }
    openBrowserPreview(match.session.previewId, match.url);
}

function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function flushPendingKnowledge(msgId, afterElement) {
    const content = pendingKnowledgeByMessageId.get(msgId);
    if (!content) return;
    addKnowledgePanel(content, afterElement);
    pendingKnowledgeByMessageId.delete(msgId);
}

function addKnowledgePanel(content, anchorElement = null) {
    if (!anchorElement) return;

    const wrapper = anchorElement.querySelector('.message-wrapper');
    if (!wrapper) return;
    const existing = wrapper.querySelector('.knowledge-panel');
    if (existing) existing.remove();

    const raw = String(content || '');
    const lines = raw.split('\n').filter(Boolean);
    const header = lines[0] || '知识附录';
    const countLine = lines[1] || '0 条片段';
    const body = lines.slice(2).join('\n').trim() || '（本轮未命中知识）';

    const panel = document.createElement('details');
    panel.className = 'knowledge-panel';

    panel.innerHTML = `
        <summary class="knowledge-panel-header">
            <span class="knowledge-panel-title">${escapeHtml(header.replace(/^【|】$/g, ''))}</span>
            <span class="knowledge-panel-count">${escapeHtml(countLine)}</span>
        </summary>
        <pre class="knowledge-panel-body">${escapeHtml(body)}</pre>
    `;

    wrapper.appendChild(panel);
    const chatMessages = document.getElementById('chatMessages');
    followChatOutput(chatMessages);
}

function showThinking() {
    removeThinking();

    const chatMessages = document.getElementById('chatMessages');
    const thinkingDiv = document.createElement('div');
    thinkingDiv.id = 'thinking';
    thinkingDiv.className = 'message ai';
    thinkingDiv.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-wrapper">
            <div class="message-loading">
                <span class="thinking-orb" aria-hidden="true"></span>
                <span class="thinking-label">正在思考</span>
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(thinkingDiv);
    requestAnimationFrame(() => thinkingDiv.classList.add('is-visible'));
    followChatOutput(chatMessages);
}

function removeThinking() {
    const thinking = document.getElementById('thinking');
    if (!thinking) return;
    if (thinking._thinkingTimer) clearInterval(thinking._thinkingTimer);
    thinking.remove();
}

function formatContent(content) {
    return renderMarkdown(content);
}

function renderMarkdown(content) {
    if (!content) return '';

    const mathTokens = [];
    const protectedContent = protectLatex(redactEmbeddedMediaData(String(content)), mathTokens);
    const lines = protectedContent.replace(/\r\n?/g, '\n').split('\n');
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
        const line = lines[index];
        if (!line.trim()) {
            index += 1;
            continue;
        }

        const fence = line.match(/^\s*```([\w.+-]*)\s*$/);
        if (fence) {
            const code = [];
            index += 1;
            while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
                code.push(lines[index]);
                index += 1;
            }
            if (index < lines.length) index += 1;
            const language = fence[1] ? ` data-language="${escapeHtml(fence[1])}"` : '';
            blocks.push(`<pre class="markdown-code"><code${language}>${escapeHtml(code.join('\n'))}</code></pre>`);
            continue;
        }

        const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
        if (heading) {
            const level = heading[1].length;
            blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
            index += 1;
            continue;
        }

        if (/^\s*((-{3,})|(\*{3,})|(_{3,}))\s*$/.test(line)) {
            blocks.push('<hr>');
            index += 1;
            continue;
        }

        if (isMarkdownTable(lines, index)) {
            const header = splitTableRow(lines[index]);
            const alignments = splitTableRow(lines[index + 1]).map(getTableAlignment);
            const rows = [];
            index += 2;
            while (index < lines.length && isTableRow(lines[index])) {
                rows.push(splitTableRow(lines[index]));
                index += 1;
            }
            blocks.push(renderMarkdownTable(header, alignments, rows));
            continue;
        }

        if (/^\s*>\s?/.test(line)) {
            const quote = [];
            while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
                quote.push(lines[index].replace(/^\s*>\s?/, ''));
                index += 1;
            }
            blocks.push(`<blockquote>${renderMarkdown(quote.join('\n'))}</blockquote>`);
            continue;
        }

        const listMatch = line.match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
        if (listMatch) {
            const ordered = /^\d/.test(listMatch[1]);
            const items = [];
            while (index < lines.length) {
                const item = lines[index].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
                if (!item || /^\d/.test(item[1]) !== ordered) break;
                items.push(renderListItem(item[2]));
                index += 1;
            }
            const tag = ordered ? 'ol' : 'ul';
            blocks.push(`<${tag}>${items.map(item => `<li>${item}</li>`).join('')}</${tag}>`);
            continue;
        }

        const paragraph = [line.trim()];
        index += 1;
        while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines, index)) {
            paragraph.push(lines[index].trim());
            index += 1;
        }
        blocks.push(`<p>${paragraph.map(renderInlineMarkdown).join('<br>')}</p>`);
    }

    return restoreLatex(blocks.join(''), mathTokens);
}

function protectLatex(content, tokens) {
    const codeTokens = [];
    let protectedText = content.replace(/```[\s\S]*?(?:```|$)/g, (code) => {
        const token = `\u0000LATEXCODE${codeTokens.length}\u0000`;
        codeTokens.push(code);
        return token;
    });
    protectedText = protectedText.replace(/`[^`\n]*`/g, (code) => {
        const token = `\u0000LATEXCODE${codeTokens.length}\u0000`;
        codeTokens.push(code);
        return token;
    });
    protectedText = protectedText.replace(/\\\[([\s\S]*?)\\\]/g, (_, expression) => {
        return createLatexToken(expression, true, tokens);
    });
    protectedText = protectedText.replace(/\$\$([\s\S]*?)\$\$/g, (_, expression) => {
        return createLatexToken(expression, true, tokens);
    });
    protectedText = protectedText.replace(/\\\(([^\n]*?)\\\)/g, (_, expression) => {
        return createLatexToken(expression, false, tokens);
    });
    protectedText = protectedText.replace(/(^|[^\\$])\$([^$\n]+?)\$/g, (_, prefix, expression) => {
        return `${prefix}${createLatexToken(expression, false, tokens)}`;
    });
    return protectedText.replace(/\u0000LATEXCODE(\d+)\u0000/g, (_, index) => {
        return codeTokens[Number(index)] || '';
    });
}

function createLatexToken(expression, displayMode, tokens) {
    const token = `\u0000MATH${tokens.length}\u0000`;
    tokens.push(renderLatex(expression.trim(), displayMode));
    return token;
}

function restoreLatex(html, tokens) {
    return html.replace(/\u0000MATH(\d+)\u0000/g, (_, index) => tokens[Number(index)] || '');
}

function renderLatex(expression, displayMode) {
    if (!expression) return '';
    if (typeof katex === 'undefined') {
        const delimiter = displayMode ? '$$' : '$';
        return `<code class="latex-fallback">${delimiter}${escapeHtml(expression)}${delimiter}</code>`;
    }

    try {
        const rendered = katex.renderToString(expression, {
            displayMode,
            throwOnError: false,
            strict: 'ignore',
            trust: false,
            output: 'html',
        });
        return displayMode
            ? `<div class="latex-display">${rendered}</div>`
            : `<span class="latex-inline">${rendered}</span>`;
    } catch (error) {
        return `<code class="latex-fallback">${escapeHtml(expression)}</code>`;
    }
}

function isMarkdownBlockStart(lines, index) {
    const line = lines[index] || '';
    return /^\s*```/.test(line)
        || /^\s*#{1,6}\s+/.test(line)
        || /^\s*>\s?/.test(line)
        || /^\s*([-+*]|\d+[.)])\s+/.test(line)
        || /^\s*((-{3,})|(\*{3,})|(_{3,}))\s*$/.test(line)
        || isMarkdownTable(lines, index);
}

function renderInlineMarkdown(content) {
    const codeTokens = [];
    const markupTokens = [];
    let escaped = escapeHtml(content).replace(/`([^`\n]+)`/g, (_, code) => {
        const token = `\u0000CODE${codeTokens.length}\u0000`;
        codeTokens.push(`<code>${code}</code>`);
        return token;
    });

    const protectMarkup = (html) => {
        const token = `\u0000MARKUP${markupTokens.length}\u0000`;
        markupTokens.push(html);
        return token;
    };

    escaped = escaped
        .replace(
            /!\[([^\]]*)\]\((?:&lt;((?:(?!&gt;).)+)&gt;|([^\s)]+))(?:\s+&quot;[^&]*&quot;)?\)/g,
            (_, label, bracketedUrl, plainUrl) => protectMarkup(
                renderMarkdownMedia(label, bracketedUrl || plainUrl)
            )
        )
        .replace(
            /\[([^\]]+)\]\(([^\s)]+)(?:\s+&quot;[^&]*&quot;)?\)/g,
            (_, label, url) => protectMarkup(renderSafeLink(label, url))
        )
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/__([^_]+)__/g, '<strong>$1</strong>')
        .replace(/~~([^~]+)~~/g, '<del>$1</del>')
        .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
        .replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>');

    return escaped
        .replace(/\u0000CODE(\d+)\u0000/g, (_, tokenIndex) => codeTokens[Number(tokenIndex)] || '')
        .replace(/\u0000MARKUP(\d+)\u0000/g, (_, tokenIndex) => markupTokens[Number(tokenIndex)] || '');
}

function redactEmbeddedMediaData(content) {
    return String(content || '').replace(
        /data:(?:image|video)\/[a-z0-9.+-]+;base64,[a-z0-9+/=_-]{256,}/gi,
        '[已省略 Base64 媒体数据，请改用文件路径或 HTTP(S) 地址]'
    );
}

function normalizeMarkdownMediaSource(escapedUrl) {
    const source = String(escapedUrl || '').replace(/&amp;/g, '&').trim();
    if (!source || /[\u0000-\u001f\u007f]/.test(source)) return '';
    if (/^https?:\/\//i.test(source)) {
        try {
            const parsed = new URL(source);
            return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '';
        } catch (_error) {
            return '';
        }
    }
    if (/^(?:data|blob|javascript):/i.test(source)) return '';
    if (
        /^[a-z][a-z0-9+.-]*:/i.test(source)
        && !/^file:\/\//i.test(source)
        // Windows 盘符（C:\...）是本地路径，不是协议
        && !/^[a-zA-Z]:[\\/]/.test(source)
    ) return '';

    const session = sessionStorage.getItem('minibot_eel_session') || '';
    if (!session) return '';
    const params = new URLSearchParams({
        path: source,
        conversation_id: String(activeConversationId || ''),
        session,
    });
    return `/__jcodex_media?${params.toString()}`;
}

function renderMarkdownMedia(escapedLabel, escapedUrl) {
    const source = String(escapedUrl || '').replace(/&amp;/g, '&').trim();
    const videoPrefix = /^(?:video|视频)\s*[:：]\s*/i;
    const isVideo = videoPrefix.test(String(escapedLabel || ''))
        || /\.(?:m4v|mov|mp4|ogv|webm)(?:[?#]|$)/i.test(source);
    const label = String(escapedLabel || '').replace(videoPrefix, '').trim();
    const mediaUrl = normalizeMarkdownMediaSource(escapedUrl);
    if (!mediaUrl) {
        return `<span class="markdown-media-blocked">${label || (isVideo ? '视频' : '图片')}（媒体地址不可用）</span>`;
    }
    if (isVideo) {
        return `<span class="markdown-media markdown-video"><video src="${escapeHtml(mediaUrl)}" controls preload="metadata" playsinline aria-label="${label || '视频'}"></video>${label ? `<span class="markdown-media-caption">${label}</span>` : ''}</span>`;
    }
    return `<button type="button" class="markdown-media markdown-image" aria-label="预览图片${label ? ` ${label}` : ''}"><img src="${escapeHtml(mediaUrl)}" alt="${label}" loading="lazy" decoding="async" referrerpolicy="no-referrer">${label ? `<span class="markdown-media-caption">${label}</span>` : ''}</button>`;
}

const IMAGE_PREVIEW_TRIGGER_SELECTOR = [
    '.markdown-image',
    '.message-attachment[data-image-attachment="true"]',
    '.composer-attachment[data-image-attachment="true"]',
].join(', ');

function openImageLightbox(source, label = '') {
    const lightbox = document.getElementById('imageLightbox');
    const image = document.getElementById('imageLightboxImage');
    const caption = document.getElementById('imageLightboxCaption');
    if (!lightbox || !image || !caption || !source) return;

    imageLightboxLastFocusedElement = document.activeElement;
    image.src = source;
    image.alt = label || '图片预览';
    caption.textContent = label;
    caption.hidden = !label;
    lightbox.hidden = false;
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.classList.add('image-lightbox-open');
    requestAnimationFrame(() => {
        lightbox.classList.add('is-open');
        document.getElementById('imageLightboxClose')?.focus({preventScroll: true});
    });
}

function closeImageLightbox({restoreFocus = true} = {}) {
    const lightbox = document.getElementById('imageLightbox');
    if (!lightbox || lightbox.hidden) return;
    lightbox.classList.remove('is-open');
    lightbox.hidden = true;
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('image-lightbox-open');
    const image = document.getElementById('imageLightboxImage');
    if (image) {
        image.removeAttribute('src');
        image.alt = '';
    }
    if (restoreFocus && imageLightboxLastFocusedElement?.isConnected) {
        imageLightboxLastFocusedElement.focus({preventScroll: true});
    }
    imageLightboxLastFocusedElement = null;
}

function openImagePreviewFromTrigger(trigger) {
    const image = trigger?.matches?.('img') ? trigger : trigger?.querySelector?.('img');
    const source = image?.currentSrc || image?.src || '';
    if (!source) return;
    const label = image.alt
        || trigger.dataset?.attachmentName
        || trigger.querySelector?.('strong')?.textContent
        || '';
    openImageLightbox(source, String(label || '').trim());
}

function handleImagePreviewClick(event) {
    if (event.target.closest('.composer-attachment-remove')) return;
    const trigger = event.target.closest(IMAGE_PREVIEW_TRIGGER_SELECTOR);
    if (trigger) openImagePreviewFromTrigger(trigger);
}

function handleImagePreviewKeydown(event) {
    if (!['Enter', ' '].includes(event.key)) return;
    if (event.target.matches('button, a, input, textarea, select')) return;
    const trigger = event.target.closest(IMAGE_PREVIEW_TRIGGER_SELECTOR);
    if (!trigger) return;
    event.preventDefault();
    openImagePreviewFromTrigger(trigger);
}

function renderSafeLink(label, escapedUrl) {
    const url = String(escapedUrl || '').replace(/&amp;/g, '&');
    if (!/^(https?:\/\/|mailto:)/i.test(url)) return `${label} (${escapeHtml(url)})`;
    const localPreviewUrl = normalizeLocalPreviewUrl(url);
    if (localPreviewUrl) {
        return `<a href="${escapeHtml(localPreviewUrl)}" data-local-preview-url="${escapeHtml(localPreviewUrl)}">${label}</a>`;
    }
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
}

function renderListItem(content) {
    const task = String(content).match(/^\[([ xX])\]\s+(.+)$/);
    if (!task) return renderInlineMarkdown(content);
    const checked = task[1].toLowerCase() === 'x';
    return `<span class="markdown-task"><input type="checkbox" disabled${checked ? ' checked' : ''}>${renderInlineMarkdown(task[2])}</span>`;
}

function isMarkdownTable(lines, index) {
    if (index + 1 >= lines.length || !isTableRow(lines[index])) return false;
    const separators = splitTableRow(lines[index + 1]);
    return separators.length > 0 && separators.every(cell => /^:?-{3,}:?$/.test(cell.trim()));
}

function isTableRow(line) {
    const trimmed = String(line || '').trim();
    return trimmed.includes('|') && !/^\s*```/.test(trimmed);
}

function splitTableRow(line) {
    const source = String(line || '')
        .trim()
        .replace(/^\|/, '')
        .replace(/\|$/, '');
    const cells = [];
    let cell = '';
    let escaped = false;

    for (const char of source) {
        if (escaped) {
            cell += char === '|' ? '|' : `\\${char}`;
            escaped = false;
        } else if (char === '\\') {
            escaped = true;
        } else if (char === '|') {
            cells.push(cell.trim());
            cell = '';
        } else {
            cell += char;
        }
    }

    if (escaped) cell += '\\';
    cells.push(cell.trim());
    return cells;
}

function getTableAlignment(separator) {
    const value = separator.trim();
    if (value.startsWith(':') && value.endsWith(':')) return 'center';
    if (value.endsWith(':')) return 'right';
    return 'left';
}

function renderMarkdownTable(header, alignments, rows) {
    const headerCells = header.map((cell, index) => `<th style="text-align:${alignments[index] || 'left'}">${renderInlineMarkdown(cell)}</th>`).join('');
    const bodyRows = rows.map(row => {
        const cells = header.map((_, index) => `<td style="text-align:${alignments[index] || 'left'}">${renderInlineMarkdown(row[index] || '')}</td>`).join('');
        return `<tr>${cells}</tr>`;
    }).join('');
    return `<div class="markdown-table-wrap"><table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
}

function showError(message) {
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.style.display = 'none';
    addMessage('ai', message, true);
}

// Quick Commands Popup
const quickCommands = [
    { cmd: '/clear', label: 'Clear conversation', action: 'clear' },
    { cmd: '/compact', label: 'Compress memory', action: 'compact' },
];

function showQuickCommands() {
    let popup = document.getElementById('quickCommandsPopup');
    if (!popup) {
        popup = document.createElement('div');
        popup.id = 'quickCommandsPopup';
        popup.className = 'quick-commands-popup';

        const inputArea = document.querySelector('.input-area');
        inputArea.appendChild(popup);
    }

    const messageInput = document.getElementById('messageInput');
    const filter = messageInput.value.toLowerCase();

    const filtered = quickCommands.filter(c =>
        c.cmd.startsWith(filter) || c.label.toLowerCase().includes(filter)
    );

    popup.innerHTML = filtered.map((c, i) =>
        `<div class="quick-command-item" data-index="${i}" data-cmd="${c.cmd}" data-prompt="${c.prompt}" data-action="${c.action || ''}">
            <span class="quick-cmd">${c.cmd}</span>
            <span class="quick-label">${c.label}</span>
        </div>`
    ).join('');

    // Add click handlers
    popup.querySelectorAll('.quick-command-item').forEach(item => {
        item.addEventListener('click', async () => {
            const cmd = item.dataset.cmd;
            const input = document.getElementById('messageInput');

            hideQuickCommands();
            input.value = cmd;

            // Send as user message (let AI handle it)
            sendMessage();
        });
    });

    popup.style.display = 'block';
}

function hideQuickCommands() {
    const popup = document.getElementById('quickCommandsPopup');
    if (popup) popup.style.display = 'none';
}

// Workspace Functions
function getWorkspaceTreeKey(folder, path = '') {
    return `${folder}:${String(path || '')}`;
}

function getWorkspaceTreeId(folder, path = '') {
    const value = `${String(folder)}:${String(path || 'root')}`;
    return `workspaceTree-${Array.from(value)
        .map(character => character.codePointAt(0).toString(36))
        .join('-')}`;
}

function workspaceFolderIconMarkup() {
    return `
        <svg class="file-icon folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
    `;
}

function workspaceFileIconMarkup() {
    return `
        <svg class="file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
        </svg>
    `;
}

function renderWorkspaceTree(folder, path = '') {
    const key = getWorkspaceTreeKey(folder, path);
    const items = workspaceDirectoryItems.get(key);
    const treeId = getWorkspaceTreeId(folder, path);
    if (!items) {
        return `<div class="workspace-tree-loading" id="${treeId}" role="status">加载中...</div>`;
    }
    if (!items.length) {
        return path
            ? `<div class="workspace-tree-empty" id="${treeId}" role="status">空文件夹</div>`
            : `<div class="sidebar-empty" id="${treeId}" role="status">暂无文件</div>`;
    }
    return `<div class="workspace-tree" id="${treeId}" role="group">${items.map(item => {
        const safeName = escapeHtml(item.name);
        const itemPath = String(item.path || item.name || '');
        if (item.type === 'folder') {
            const itemKey = getWorkspaceTreeKey(folder, itemPath);
            const isExpanded = workspaceExpandedDirectories.has(itemKey);
            const childId = getWorkspaceTreeId(folder, itemPath);
            return `
                <div class="workspace-tree-node is-folder">
                    <div class="workspace-tree-row">
                        <button class="workspace-tree-toggle" type="button" data-workspace-toggle="${escapeHtml(itemPath)}" aria-label="${isExpanded ? '收起' : '展开'} ${safeName}" aria-expanded="${isExpanded ? 'true' : 'false'}" aria-controls="${childId}">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
                        </button>
                        <button class="workspace-tree-item" type="button" draggable="true" data-workspace-folder="${escapeHtml(itemPath)}" title="${safeName}">
                            ${workspaceFolderIconMarkup()}
                            <span class="file-name">${safeName}</span>
                        </button>
                        <button class="workspace-tree-open" type="button" data-workspace-open-folder="${escapeHtml(itemPath)}" title="在文件管理器中打开 ${safeName}" aria-label="在文件管理器中打开 ${safeName}">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/></svg>
                        </button>
                    </div>
                    <div class="workspace-tree-children" id="${childId}" ${isExpanded ? '' : 'hidden'}>${isExpanded ? renderWorkspaceTree(folder, itemPath) : ''}</div>
                </div>
            `;
        }
        return `
            <div class="workspace-tree-row is-file">
                <button class="workspace-tree-item" type="button" draggable="true" data-workspace-file="${escapeHtml(itemPath)}" title="${safeName}">
                    ${workspaceFileIconMarkup()}
                    <span class="file-name">${safeName}</span>
                    <span class="file-size">${formatFileSize(item.size)}</span>
                </button>
            </div>
        `;
    }).join('')}</div>`;
}

function bindWorkspaceTreeEvents(folder, rootElement) {
    if (!rootElement || rootElement.dataset.workspaceTreeBound === 'true') return;
    rootElement.dataset.workspaceTreeBound = 'true';
    rootElement.addEventListener('click', event => {
        const toggle = event.target.closest('[data-workspace-toggle]');
        const folderItem = event.target.closest('[data-workspace-folder]');
        const openFolder = event.target.closest('[data-workspace-open-folder]');
        const fileItem = event.target.closest('[data-workspace-file]');
        if (toggle || folderItem) {
            event.preventDefault();
            toggleWorkspaceDirectory(folder, (toggle || folderItem).dataset.workspaceToggle || folderItem.dataset.workspaceFolder);
        } else if (openFolder) {
            event.preventDefault();
            openWorkspaceFolder(folder, openFolder.dataset.workspaceOpenFolder);
        } else if (fileItem) {
            event.preventDefault();
            openFile(folder, fileItem.dataset.workspaceFile);
        }
    });
    rootElement.addEventListener('dblclick', event => {
        const folderItem = event.target.closest('[data-workspace-folder]');
        if (!folderItem) return;
        event.preventDefault();
        openWorkspaceFolder(folder, folderItem.dataset.workspaceFolder);
    });
    rootElement.addEventListener('dragstart', event => {
        const folderItem = event.target.closest('[data-workspace-folder]');
        const fileItem = event.target.closest('[data-workspace-file]');
        const sourceItem = folderItem || fileItem;
        if (!sourceItem) return;
        const itemPath = String(
            sourceItem.dataset.workspaceFolder || sourceItem.dataset.workspaceFile || ''
        );
        if (!itemPath) return;
        const name = String(sourceItem.querySelector('.file-name')?.textContent || '')
            .trim() || getPathBaseName(itemPath);
        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData('text/plain', `workspace/${folder}/${itemPath}`);
        event.dataTransfer.setData(WORKSPACE_DRAG_TYPE, JSON.stringify({
            folder,
            path: itemPath,
            name,
            isFolder: Boolean(folderItem),
        }));
    });
}

function updateWorkspaceTree(folder) {
    const listEl = document.getElementById(`${folder}Files`);
    if (!listEl) return;
    listEl.innerHTML = renderWorkspaceTree(folder);
    bindWorkspaceTreeEvents(folder, listEl);
}

async function loadWorkspaceDirectory(folder, path = '', {force = false} = {}) {
    const key = getWorkspaceTreeKey(folder, path);
    if (!force && workspaceDirectoryItems.has(key)) return workspaceDirectoryItems.get(key);
    if (workspaceDirectoryRequests.has(key)) return workspaceDirectoryRequests.get(key);
    if (!canCallEel()) throw new Error('Eel connection is unavailable');
    const request = eel.list_workspace_files(folder, path)()
        .then(items => {
            workspaceDirectoryItems.set(key, Array.isArray(items) ? items : []);
            return workspaceDirectoryItems.get(key);
        })
        .finally(() => workspaceDirectoryRequests.delete(key));
    workspaceDirectoryRequests.set(key, request);
    return request;
}

async function refreshExpandedWorkspaceDirectories(folder) {
    const prefix = `${folder}:`;
    const paths = Array.from(workspaceExpandedDirectories)
        .filter(key => key.startsWith(prefix))
        .map(key => key.slice(prefix.length));
    await Promise.all(paths.map(path => loadWorkspaceDirectory(folder, path, {force: true})));
}

async function refreshWorkspace(folder) {
    if (!canCallEel()) return;
    try {
        await loadWorkspaceDirectory(folder, '', {force: true});
        await refreshExpandedWorkspaceDirectories(folder);
        updateWorkspaceTree(folder);
    } catch (e) {
        if (handleEelConnectionError(e)) return;
        console.error('Failed to refresh workspace:', e);
        const listEl = document.getElementById(`${folder}Files`);
        if (listEl) listEl.innerHTML = '<div class="sidebar-empty">无法读取文件</div>';
    }
}

async function toggleWorkspaceDirectory(folder, path) {
    const normalizedPath = String(path || '');
    if (!normalizedPath) return;
    const key = getWorkspaceTreeKey(folder, normalizedPath);
    if (workspaceExpandedDirectories.has(key)) {
        workspaceExpandedDirectories.delete(key);
        updateWorkspaceTree(folder);
        return;
    }
    workspaceExpandedDirectories.add(key);
    updateWorkspaceTree(folder);
    try {
        await loadWorkspaceDirectory(folder, normalizedPath);
    } catch (error) {
        workspaceExpandedDirectories.delete(key);
        showToast('无法展开文件夹', 'error');
        console.error('Failed to load workspace directory:', error);
    }
    updateWorkspaceTree(folder);
}

async function refreshAllWorkspace() {
    if (refreshInFlight || !canCallEel()) return;
    refreshInFlight = true;
    try {
        await Promise.all([refreshWorkspace('output'), refreshWorkspace('temp')]);
    } finally {
        refreshInFlight = false;
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function openFile(folder, fileName) {
    try {
        const result = await eel.open_workspace_file(folder, fileName)();
        if (!result?.success) {
            showToast(result?.error || '打开文件失败', 'error');
        }
    } catch (e) {
        console.error('Failed to open file:', e);
        showToast('打开文件失败', 'error');
    }
}

async function openWorkspaceFolder(folder, subFolder) {
    try {
        const result = await eel.open_workspace_subfolder(folder, subFolder)();
        if (!result?.success) {
            showToast(result?.error || '打开文件夹失败', 'error');
        }
    } catch (e) {
        console.error('Failed to open folder:', e);
        showToast('打开文件夹失败', 'error');
    }
}

function closeFileModal() {
    const modal = document.getElementById('fileModal');
    modal.classList.remove('active');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (document.getElementById('browserPreviewModal').classList.contains('active')) {
            closeBrowserPreview();
        } else if (document.getElementById('inputDialog').classList.contains('active')) {
            closeInputDialog();
        } else if (document.getElementById('confirmDialog').classList.contains('active')) {
            closeConfirmDialog();
        } else if (document.body.classList.contains('sidebar-open')) {
            closeMobileSidebar();
            document.getElementById('sidebarToggle')?.focus();
        } else {
            closeActiveModal();
        }
    }
});

function closeActiveModal() {
    const activeModal = document.querySelector(
        '.browser-preview-modal.active, .file-modal.active, .settings-modal.active'
    );
    if (!activeModal) return;
    if (activeModal.id === 'browserPreviewModal') {
        closeBrowserPreview();
        return;
    }
    activeModal.classList.remove('active');
    if (activeModal.id === 'dataModal') selectedTaskIds.clear();
    if (activeModal.id === 'prefModal') selectedPrefKeys.clear();
    if (activeModal.id === 'knowledgeModal') selectedKbIds.clear();
    lastFocusedElement?.focus?.();
}

// Settings Functions
async function openSettings() {
    try {
        lastFocusedElement = document.activeElement;
        applyAppModeUI();
        const settings = await eel.load_settings()();
        currentSettingsSnapshot = settings;

        document.getElementById('settingApiBaseUrl').value = settings.api_base_url || '';
        document.getElementById('settingApiKey').value = settings.api_key || '';
        document.getElementById('settingApiModel').value = settings.api_model || '';
        document.getElementById('settingSupportsVision').checked = settings.supports_vision !== 'false';
        document.getElementById('settingTavilyKey').value = settings.tavily_api_key || '';
        document.getElementById('settingCustomSystemPrompt').value = settings.custom_system_prompt || '';
        hideLocalModelMenu();
        document.getElementById('settingMaxSteps').value = settings.max_steps || '';
        document.getElementById('settingMaxTokens').value = settings.max_tokens || '';
        document.getElementById('settingContextWindow').value = contextWindowIndexFor(
            settings.context_window
        );
        updateContextWindowLabel();
        document.getElementById('settingAutoCompactPercent').value = settings.auto_compact_threshold_percent || '85';
        document.getElementById('settingMaxWebSearches').value = settings.max_web_searches || '';
        populateVoiceTtsSettings();

        // 加载配置列表
        await loadConfigList();

        // 添加实时修改监听 - 当用户修改API字段时，立即重置配置选择
        const apiFields = ['settingApiBaseUrl', 'settingApiKey', 'settingApiModel'];
        apiFields.forEach(fieldId => {
            document.getElementById(fieldId).oninput = () => {
                clearApiConfigSelection();
            };
        });

        document.getElementById('settingsModal').classList.add('active');
        document.getElementById('settingApiBaseUrl').focus();
    } catch (e) {
        console.error('Failed to load settings:', e);
        showToast(`加载设置失败：${e.message}`, 'error');
    }
}

let apiConfigMenuSelection = '';

function getSelectedApiConfig() {
    return apiConfigMenuSelection;
}

function setApiConfigSelection(configName) {
    apiConfigMenuSelection = configName || '';
    const label = document.getElementById('configSelectLabel');
    if (label) {
        label.textContent = apiConfigMenuSelection || '选择已保存配置…';
    }
}

function clearApiConfigSelection() {
    setApiConfigSelection('');
}

function closeApiConfigMenu() {
    const menu = document.getElementById('configSelectMenu');
    const trigger = document.getElementById('configSelectTrigger');
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
}

function openApiConfigMenu() {
    const menu = document.getElementById('configSelectMenu');
    const trigger = document.getElementById('configSelectTrigger');
    if (!menu) return;
    menu.hidden = false;
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
}

function toggleApiConfigMenu() {
    const menu = document.getElementById('configSelectMenu');
    if (!menu) return;
    if (menu.hidden) openApiConfigMenu();
    else closeApiConfigMenu();
}

function normalizeEffort(value) {
    return String(value || '').toLowerCase() === 'low' ? 'low' : 'high';
}

function positionReasoningSubmenu(submenu, row) {
    if (!submenu || !row) return;
    const rect = row.getBoundingClientRect();
    submenu.style.position = 'fixed';
    submenu.style.visibility = 'hidden';
    const sw = submenu.offsetWidth;
    const sh = submenu.offsetHeight;
    let left = rect.right;
    if (left + sw > window.innerWidth - 8) {
        left = Math.max(8, rect.left - sw);
    }
    let top = rect.top - 4;
    if (top + sh > window.innerHeight - 8) {
        top = Math.max(8, window.innerHeight - sh - 8);
    }
    submenu.style.left = left + 'px';
    submenu.style.top = top + 'px';
    submenu.style.visibility = '';
}

function closeModelQuickSwitch() {
    const menu = document.getElementById('modelQuickSwitch');
    if (menu) menu.hidden = true;
    const badge = document.getElementById('modelBadge');
    if (badge) badge.setAttribute('aria-expanded', 'false');
}

function positionModelQuickSwitch() {
    const menu = document.getElementById('modelQuickSwitch');
    const badge = document.getElementById('modelBadge');
    if (!menu || !badge || menu.hidden) return;
    const badgeRect = badge.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.right = 'auto';
    menu.style.bottom = 'auto';
    menu.style.visibility = 'hidden';
    const width = menu.offsetWidth;
    menu.style.left = Math.max(8, badgeRect.right - width) + 'px';
    menu.style.visibility = '';
    const height = menu.offsetHeight;
    menu.style.top = Math.max(8, badgeRect.top - height - 8) + 'px';
}

async function renderModelQuickSwitch(openConfigName) {
    const menu = document.getElementById('modelQuickSwitch');
    if (!menu) return;
    const result = await eel.list_api_configs()();
    const available = Array.isArray(result.available) ? result.available : [];
    menu.innerHTML = '';

    if (available.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'model-quick-switch-empty';
        empty.textContent = '暂无已保存的模型配置';
        menu.appendChild(empty);
    } else {
        available.forEach(configName => {
            const config = (result.configs && result.configs[configName]) || {};
            const model = String(config.api_model || '');
            const isDeepSeek = model.toLowerCase().includes('deepseek');
            const effort = isDeepSeek ? normalizeEffort(config.reasoning_effort) : '';
            const row = document.createElement('div');
            row.className = 'model-quick-switch-row';
            row.dataset.config = configName;

            const isActive = configName === result.active;
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'model-quick-switch-item';
            if (isActive) item.classList.add('is-active');
            item.title = `${configName} · ${model || '未知模型'}`;
            item.innerHTML =
                `<span class="model-quick-switch-name">${escapeHtml(model || '未知模型')}</span>`
                + (isDeepSeek && isActive
                    ? `<span class="model-quick-switch-effort" title="推理强度: ${escapeHtml(effort)}">${escapeHtml(effort)}</span>`
                    : '')
                + (isDeepSeek && isActive
                    ? '<svg class="model-quick-switch-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>'
                    : '')
                + (isActive
                    ? '<svg class="model-quick-switch-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 6L9 17l-5-5"/></svg>'
                    : '');
            item.addEventListener('click', async () => {
                closeModelQuickSwitch();
                try {
                    const switchResult = await eel.set_active_config(configName)();
                    if (switchResult && switchResult.success) {
                        showToast(`已切换到 ${configName}`, 'success');
                        await updateModelBadge();
                    } else {
                        showToast(`切换失败: ${switchResult?.error || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    console.error('Failed to switch model:', e);
                    showToast('切换模型失败', 'error');
                }
            });
            row.appendChild(item);

            if (isDeepSeek && isActive) {
                const submenu = document.createElement('div');
                submenu.className = 'model-reasoning-submenu';
                const title = document.createElement('div');
                title.className = 'model-reasoning-submenu-title';
                title.textContent = '推理强度';
                submenu.appendChild(title);
                ['low', 'high'].forEach(value => {
                    const opt = document.createElement('button');
                    opt.type = 'button';
                    opt.className = 'model-reasoning-submenu-item'
                        + (value === effort ? ' is-active' : '');
                    opt.dataset.value = value;
                    opt.title = `发送 reasoning_effort=${value}`;
                    opt.innerHTML =
                        `<span>${escapeHtml(value)}</span>`
                        + (value === effort
                            ? '<svg class="model-reasoning-submenu-check" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 6L9 17l-5-5"/></svg>'
                            : '');
                    opt.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        try {
                            const res = await eel.update_config_reasoning_effort(configName, value)();
                            if (res && res.success) {
                                showToast(`已设置 ${model} 推理强度: ${value}`, 'success');
                                const effortEl = row.querySelector('.model-quick-switch-effort');
                                if (effortEl) {
                                    effortEl.textContent = value;
                                    effortEl.title = `推理强度: ${value}`;
                                }
                                // 原地移动勾选标记，不重绘菜单，避免模型栏闪没
                                const check = submenu.querySelector('.model-reasoning-submenu-check');
                                submenu.querySelectorAll('.model-reasoning-submenu-item')
                                    .forEach(i => {
                                        const isSelected = i.dataset.value === value;
                                        i.classList.toggle('is-active', isSelected);
                                        if (isSelected && check && !i.contains(check)) {
                                            i.appendChild(check);
                                        }
                                    });
                                if (configName === result.active) await updateModelBadge();
                            } else {
                                showToast(`设置失败: ${res?.error || '未知错误'}`, 'error');
                            }
                        } catch (err) {
                            console.error('Failed to update reasoning effort:', err);
                            showToast('设置推理强度失败', 'error');
                        }
                    });
                    submenu.appendChild(opt);
                });
                row.appendChild(submenu);
            }

            row.addEventListener('mouseenter', () => {
                menu.querySelectorAll('.model-reasoning-submenu')
                    .forEach(s => s.classList.remove('is-open'));
                if (isActive) {
                    const sub = row.querySelector('.model-reasoning-submenu');
                    if (sub) {
                        sub.classList.add('is-open');
                        positionReasoningSubmenu(sub, row);
                    }
                }
            });
            menu.appendChild(row);
        });
    }

    const footer = document.createElement('button');
    footer.type = 'button';
    footer.className = 'model-quick-switch-footer';
    footer.textContent = '打开运行设置…';
    footer.addEventListener('click', () => {
        closeModelQuickSwitch();
        openSettings();
    });
    menu.appendChild(footer);

    document.body.appendChild(menu);
    menu.hidden = false;
    const badge = document.getElementById('modelBadge');
    if (badge) badge.setAttribute('aria-expanded', 'true');
    positionModelQuickSwitch();

    if (openConfigName) {
        const targetRow = [...menu.querySelectorAll('.model-quick-switch-row')]
            .find(r => r.dataset.config === openConfigName);
        const targetSubmenu = targetRow && targetRow.querySelector('.model-reasoning-submenu');
        if (targetRow && targetSubmenu) {
            menu.querySelectorAll('.model-reasoning-submenu')
                .forEach(s => s.classList.remove('is-open'));
            targetSubmenu.classList.add('is-open');
            positionReasoningSubmenu(targetSubmenu, targetRow);
        }
    }
}

async function toggleModelQuickSwitch() {
    const menu = document.getElementById('modelQuickSwitch');
    if (!menu) return;
    if (!menu.hidden) {
        closeModelQuickSwitch();
        return;
    }
    try {
        await renderModelQuickSwitch();
    } catch (e) {
        console.error('Failed to load model list:', e);
    }
}

function formatNextFire(value) {
    if (!value) return '';
    const ts = Number(value);
    if (!Number.isFinite(ts) || ts <= 0) return '';
    try {
        const now = Date.now();
        const diff = ts * 1000 - now;
        if (diff > 0 && diff < 60 * 60 * 1000) {
            const mins = Math.max(1, Math.round(diff / 60000));
            return `${mins} 分钟后`;
        }
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
    } catch (e) {
        return '';
    }
}

async function loadScheduledTasks() {
    const list = document.getElementById('scheduledTasksModalList');
    if (!list || !canCallEel()) return;
    try {
        const result = await eel.list_scheduled_tasks()();
        if (!result || !result.success) throw new Error(result?.error || '加载失败');
        const tasks = Array.isArray(result.tasks) ? result.tasks : [];
        if (!tasks.length) {
            list.innerHTML = '<div class="data-item"><span class="data-source">暂无定时任务</span></div>';
            return;
        }
        list.innerHTML = '';
        tasks.forEach(task => {
            const id = String(task.id || '');
            const interval = String(task.interval || '');
            const prompt = String(task.prompt || '');
            const convTitle = String(task.conversation_title || '');
            const nextFire = formatNextFire(task.next_fire);
            const recurring = task.recurring !== false;
            const item = document.createElement('div');
            item.className = 'scheduled-task-item';
            item.innerHTML =
                `<div class="scheduled-task-top">`
                + `<span class="scheduled-task-interval" title="${escapeHtml(interval)}">${escapeHtml(interval)}</span>`
                + (recurring ? '<span class="scheduled-task-badge">循环</span>' : '')
                + `<button class="scheduled-task-delete" type="button" title="删除定时任务" aria-label="删除定时任务">✕</button>`
                + `</div>`
                + `<div class="scheduled-task-prompt" title="${escapeHtml(prompt)}">${escapeHtml(prompt)}</div>`
                + `<div class="scheduled-task-meta">`
                + (convTitle ? `<span title="${escapeHtml(convTitle)}">${escapeHtml(convTitle)}</span>` : '')
                + (nextFire ? `<span>${escapeHtml(nextFire)}</span>` : '')
                + `</div>`;
            item.querySelector('.scheduled-task-delete').addEventListener('click', async () => {
                const confirmed = await showConfirmDialog('确定删除这个定时任务吗？');
                if (!confirmed) return;
                try {
                    const res = await eel.delete_scheduled_task(id)();
                    if (res && res.success) {
                        showToast('定时任务已删除', 'success');
                        loadScheduledTasks();
                    } else {
                        showToast(`删除失败: ${res?.error || '未知错误'}`, 'error');
                    }
                } catch (err) {
                    console.error('Failed to delete scheduled task:', err);
                    showToast('删除定时任务失败', 'error');
                }
            });
            list.appendChild(item);
        });
    } catch (e) {
        console.error('Failed to load scheduled tasks:', e);
        list.innerHTML = '<div class="data-item"><span class="data-source">定时任务加载失败</span></div>';
    }
}

async function loadConfigList() {
    try {
        const result = await eel.list_api_configs()();
        const menu = document.getElementById('configSelectMenu');
        if (!menu) return;
        menu.innerHTML = '';
        const available = Array.isArray(result.available) ? result.available : [];

        if (available.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'api-config-menu-empty';
            empty.textContent = '暂无已保存的配置';
            menu.appendChild(empty);
            setApiConfigSelection('');
            return;
        }

        available.forEach(configName => {
            const config = (result.configs && result.configs[configName]) || {};
            const model = String(config.api_model || '');
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'api-config-menu-item';
            item.setAttribute('role', 'option');
            item.innerHTML =
                `<span class="api-config-menu-name">${escapeHtml(configName)}</span>`
                + (model
                    ? `<span class="api-config-menu-model">${escapeHtml(model)}</span>`
                    : '');
            if (configName === result.active) {
                item.classList.add('is-active');
                setApiConfigSelection(configName);
            }
            item.addEventListener('click', () => {
                setApiConfigSelection(configName);
                closeApiConfigMenu();
                loadConfig(configName);
            });
            menu.appendChild(item);
        });
    } catch (e) {
        console.error('Failed to load config list:', e);
    }
}

async function loadConfig(configName, showNotification = true) {
    if (!configName) return;

    try {
        const result = await eel.load_api_config(configName)();

        if (result.success) {
            document.getElementById('settingApiBaseUrl').value = result.config.api_base_url || '';
            document.getElementById('settingApiKey').value = result.config.api_key || '';
            document.getElementById('settingApiModel').value = result.config.api_model || '';
            setApiConfigSelection(result.active || configName);

            if (showNotification) {
                showToast(`已加载配置: ${configName}`, 'success');
            }
        } else {
            if (showNotification) {
                showToast(`加载配置失败: ${result.error}`, 'error');
            }
        }
    } catch (e) {
        console.error('Failed to load config:', e);
        if (showNotification) {
            showToast('加载配置失败', 'error');
        }
    }
}

function hideLocalModelMenu() {
    const menu = document.getElementById('localModelMenu');
    if (menu) {
        menu.hidden = true;
        menu.innerHTML = '';
    }
}

async function openLocalModelPicker() {
    const baseInput = document.getElementById('settingApiBaseUrl');
    const defaultValue = (baseInput?.value || '').trim() || 'http://127.0.0.1:8080';
    const baseUrl = await showInputDialog('输入本地模型服务地址', defaultValue);
    if (!baseUrl) return;
    const address = baseUrl.trim();
    if (!/^https?:\/\//i.test(address)) {
        showToast('地址必须以 http:// 或 https:// 开头', 'error');
        return;
    }
    const menu = document.getElementById('localModelMenu');
    if (!menu) return;
    hideLocalModelMenu();
    menu.hidden = false;
    menu.innerHTML = '<div class="local-model-status">正在查询本地模型…</div>';
    try {
        const result = await eel.list_local_models(address)();
        if (!result || !result.success) {
            const message = result?.error || '未查询到模型';
            menu.innerHTML = `<div class="local-model-status">${escapeHtml(message)}</div>`;
            showToast(message, 'error');
            return;
        }
        const models = Array.isArray(result.models) ? result.models : [];
        if (models.length === 0) {
            menu.innerHTML = '<div class="local-model-status">该地址没有返回可用模型</div>';
            showToast('该地址没有返回可用模型', 'error');
            return;
        }
        const applyLocalModel = async (entry) => {
            const rawId = String(entry.id || '');
            const displayName = String(entry.name || rawId || '');
            document.getElementById('settingApiModel').value = displayName || rawId;
            if (baseInput) {
                baseInput.value = result.base_url || address;
            }
            document.getElementById('settingApiKey').value = '';
            clearApiConfigSelection();
            hideLocalModelMenu();
            await saveSettings(false);
        };
        if (models.length === 1) {
            await applyLocalModel(models[0]);
            return;
        }
        menu.innerHTML = '';
        const serverLabel = String(result.server || '').trim();
        const header = document.createElement('div');
        header.className = 'local-model-status';
        header.textContent = serverLabel
            ? `${serverLabel} · 共 ${models.length} 个模型`
            : `共 ${models.length} 个模型`;
        menu.appendChild(header);
        models.forEach(model => {
            const entry = (model && typeof model === 'object') ? model : {id: String(model)};
            const rawId = String(entry.id || '');
            const displayName = String(entry.name || rawId || model);
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'local-model-item';
            item.textContent = displayName;
            item.title = rawId && rawId !== displayName
                ? `${rawId} · 点击选择 ${displayName}`
                : `点击选择 ${displayName}`;
            item.addEventListener('click', () => applyLocalModel(entry));
            menu.appendChild(item);
        });
    } catch (e) {
        if (handleEelConnectionError(e)) return;
        const message = e.message || '查询失败';
        menu.innerHTML = `<div class="local-model-status">${escapeHtml(message)}</div>`;
        showToast(message, 'error');
    }
}

async function saveCurrentConfig() {
    const configName = await showInputDialog('请输入配置名称:');
    if (!configName) return;

    try {
        const result = await eel.save_api_config(
            configName,
            document.getElementById('settingApiBaseUrl').value,
            document.getElementById('settingApiKey').value,
            document.getElementById('settingApiModel').value
        )();

        if (result.success) {
            showToast(`配置已保存: ${configName}`, 'success');
            await loadConfigList();
            setApiConfigSelection(result.active || configName);
        } else {
            showToast(`保存失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to save config:', e);
        showToast('保存配置失败', 'error');
    }
}

async function deleteCurrentConfig() {
    const configName = getSelectedApiConfig();
    if (!configName) {
        showToast('请先选择一个配置', 'info');
        return;
    }

    const confirmed = await showConfirmDialog(`确定要删除配置 "${configName}" 吗?`);
    if (!confirmed) return;

    try {
        const result = await eel.delete_api_config(configName)();

        if (result.success) {
            showToast('配置已删除', 'success');
            await loadConfigList();
        } else {
            showToast(`删除失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to delete config:', e);
        showToast('删除配置失败', 'error');
    }
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
    lastFocusedElement?.focus?.();
}

function collectSettingsFromForm(fallback = {}) {
    return {
        api_base_url: document.getElementById('settingApiBaseUrl').value.trim(),
        api_key: document.getElementById('settingApiKey').value.trim(),
        api_model: document.getElementById('settingApiModel').value.trim(),
        supports_vision: document.getElementById('settingSupportsVision').checked ? 'true' : 'false',
        tavily_api_key: document.getElementById('settingTavilyKey').value.trim(),
        custom_system_prompt: document.getElementById('settingCustomSystemPrompt').value,
        max_steps: document.getElementById('settingMaxSteps').value.trim() || fallback.max_steps || '100',
        max_tokens: document.getElementById('settingMaxTokens').value.trim() || fallback.max_tokens || '50000',
        context_window: String(
            CONTEXT_WINDOW_OPTIONS[Number(document.getElementById('settingContextWindow').value)]
            || Number(fallback.context_window || 256000)
        ),
        auto_compact_threshold_percent: document.getElementById('settingAutoCompactPercent').value.trim()
            || fallback.auto_compact_threshold_percent
            || '85',
        max_web_searches: document.getElementById('settingMaxWebSearches').value.trim() || fallback.max_web_searches || '8'
    };
}

async function saveSettings(closeModal = true) {
    const settings = collectSettingsFromForm(currentSettingsSnapshot || {});
    const saveButton = document.getElementById('saveSettingsButton');

    if (!/^https?:\/\//i.test(settings.api_base_url)) {
        showToast('API Base URL 必须以 http:// 或 https:// 开头', 'error');
        document.getElementById('settingApiBaseUrl').focus();
        return;
    }
    if (!settings.api_model) {
        showToast('请输入模型名称', 'error');
        document.getElementById('settingApiModel').focus();
        return;
    }
    try {
        saveButton.disabled = true;
        saveButton.textContent = '保存中…';
        const result = await eel.save_settings(settings)();

        if (result.success) {
            currentSettingsSnapshot = await eel.load_settings()();
            pendingKnowledgeByMessageId.clear();
            document.querySelectorAll('.knowledge-panel').forEach(panel => panel.remove());
            await updateModelBadge();

            if (closeModal) closeSettingsModal();
            await updateTokenIndicator();
            showToast('设置已保存并立即生效', 'success');
        } else {
            showToast(`保存设置失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        showToast('保存设置失败', 'error');
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = '保存';
    }
}

// Token Indicator
async function updateTokenIndicator() {
    if (tokenRefreshInFlight || !canCallEel()) return;
    tokenRefreshInFlight = true;
    try {
        const requestedConversationId = String(activeConversationId || '');
        const result = await eel.get_token_count(requestedConversationId)();
        if (requestedConversationId !== String(activeConversationId || '')) return;
        const tokens = Number(result.tokens || 0);
        const maxTokens = Math.max(Number(result.compress_at || 0), 1);
        const percentage = Math.min((tokens / maxTokens) * 100, 100);

        const progressBar = document.getElementById('tokenProgressBar');
        const tokenText = document.getElementById('tokenText');

        progressBar.style.width = percentage + '%';

        // 格式化显示：以自动压缩阈值为上限（例如 512K 上下文 → 435.2K）
        const maxK = maxTokens / 1000;
        if (tokens >= 1000) {
            tokenText.textContent = (tokens / 1000).toFixed(1) + 'k/' + maxK + 'k';
        } else {
            tokenText.textContent = tokens + '/' + maxK + 'k';
        }

        // 更新 tooltip
        const tooltip = document.getElementById('tokenTooltip');
        if (tooltip) {
            tooltip.innerHTML = tokenTooltipMarkup(result);
        }

        // 颜色变化
        progressBar.classList.remove('warning', 'danger');
        if (percentage >= 90) {
            progressBar.classList.add('danger');
        } else if (percentage >= 70) {
            progressBar.classList.add('warning');
        }
    } catch (e) {
        if (handleEelConnectionError(e)) return;
        console.error('Failed to update token indicator:', e);
    } finally {
        tokenRefreshInFlight = false;
    }
}

function tokenTooltipMarkup(result) {
    const systemTokens = Number(result.system_tokens || 0);
    const messageTokens = Number(result.message_tokens || 0);
    const toolTokens = Number(result.tool_tokens || 0);
    const compressAt = Number(result.compress_at || 0);
    const triggerPercent = Number(result.auto_compact_threshold_percent || 85);
    return [
        `压缩阈值 ${formatCompressionTokenCount(compressAt)}（${triggerPercent}%）`,
        `系统 ${formatCompressionTokenCount(systemTokens)}`,
        `消息 ${formatCompressionTokenCount(messageTokens)}`,
        `工具 ${formatCompressionTokenCount(toolTokens)}`,
    ].join(' · ');
}

function formatTokenText(tokens, maxTokens) {
    const maxK = maxTokens / 1000;
    if (tokens >= 1000) {
        return (tokens / 1000).toFixed(1) + 'k/' + maxK + 'k';
    }
    return tokens + '/' + maxK + 'k';
}

async function toggleTokenTooltip() {
    let tooltip = document.getElementById('tokenTooltip');

    if (tooltip) {
        tooltip.remove();
        return;
    }

    try {
        const result = await eel.get_token_count(activeConversationId || '')();

        const indicator = document.getElementById('tokenIndicator');
        tooltip = document.createElement('div');
        tooltip.id = 'tokenTooltip';
        tooltip.className = 'token-tooltip';
        tooltip.innerHTML = tokenTooltipMarkup(result);

        indicator.style.position = 'relative';
        indicator.appendChild(tooltip);

        // 点击其他地方关闭
        setTimeout(() => {
            document.addEventListener('click', closeTokenTooltip);
        }, 10);
    } catch (e) {
        console.error('Failed to get token info:', e);
    }
}

function closeTokenTooltip(e) {
    const tooltip = document.getElementById('tokenTooltip');
    if (tooltip && !e.target.closest('#tokenIndicator')) {
        tooltip.remove();
        document.removeEventListener('click', closeTokenTooltip);
    }
}

// Skills Functions
let skillStoreEntries = [];
const skillStoreInstallsInFlight = new Set();

function normalizeSkillStoreEntries(result) {
    if (Array.isArray(result)) return result;
    if (Array.isArray(result?.skills)) return result.skills;
    return [];
}

function updateSkillStoreSummary(result) {
    skillStoreEntries = normalizeSkillStoreEntries(result);
    const count = document.getElementById('skillStoreCount');
    if (count) count.textContent = String(skillStoreEntries.length);
}

async function refreshSkills() {
    try {
        const [skills, storeResult] = await Promise.all([
            eel.list_skills()(),
            eel.list_skill_store()(),
        ]);
        updateSkillStoreSummary(storeResult);
        const listEl = document.getElementById('skillsList');

        if (!skills || skills.length === 0) {
            listEl.innerHTML = '<div class="sidebar-empty">暂无技能</div>';
            return;
        }

        listEl.innerHTML = skills.map((s, index) => {
            const deleteBtn = s.builtin ? '' : `
                <button class="skill-delete" type="button" data-delete-index="${index}" title="删除技能" aria-label="删除 ${escapeHtml(s.name)}">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            `;
            const builtinBadge = s.builtin ? '<span class="builtin-badge">built-in</span>' : '';

            return `
                <div class="skill-item ${s.builtin ? 'builtin' : ''}" role="button" tabindex="0" data-skill-index="${index}" title="${escapeHtml(s.description || s.name)}">
                    <svg class="skill-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                    </svg>
                    <span class="skill-name">${escapeHtml(s.name)}</span>
                    ${builtinBadge}
                    ${deleteBtn}
                </div>
            `;
        }).join('');
        listEl.querySelectorAll('[data-skill-index]').forEach((element) => {
            const skill = skills[Number(element.dataset.skillIndex)];
            element.addEventListener('click', () => openSkill(skill.name));
            element.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openSkill(skill.name);
                }
            });
        });
        listEl.querySelectorAll('[data-delete-index]').forEach((element) => {
            const skill = skills[Number(element.dataset.deleteIndex)];
            element.addEventListener('click', (event) => {
                event.stopPropagation();
                deleteSkill(skill.name);
            });
        });
    } catch (e) {
        console.error('Failed to refresh skills:', e);
    }
}

async function addSkill() {
    document.getElementById('skillFolderInput')?.click();
}

async function importSkillFolder(files) {
    if (!files.length) return;
    const button = document.getElementById('addSkillButton');
    if (!canCallEel()) {
        markEelConnectionLost();
        return;
    }
    try {
        if (button) button.disabled = true;
        const payload = await Promise.all(files.map(async file => ({
            path: file.webkitRelativePath || file.name,
            data: await readFileAsDataUrl(file),
        })));
        const result = await eel.import_skill_folder(payload)();
        if (!result?.success) {
            showToast(`添加技能失败: ${result?.error || '无法导入文件夹'}`, 'error');
            return;
        }
        showToast(`技能添加成功: ${result.name}`, 'success');
        await refreshSkills();
    } catch (error) {
        if (handleEelConnectionError(error)) return;
        console.error('Failed to import skill folder:', error);
        showToast(`添加技能失败: ${error.message || '无法读取文件夹'}`, 'error');
    } finally {
        if (button) button.disabled = false;
    }
}

async function openSkill(skillName) {
    try {
        await eel.open_skill_folder(skillName)();
    } catch (e) {
        console.error('Failed to open skill:', e);
    }
}

async function deleteSkill(skillName) {
    const confirmed = await showConfirmDialog(`确定要删除技能 "${skillName}" 吗?`);
    if (!confirmed) return;

    try {
        const result = await eel.delete_skill(skillName)();

        if (result.success) {
            showToast(`技能已删除: ${skillName}`, 'success');
            await refreshSkills();
            if (document.getElementById('skillStoreModal')?.classList.contains('active')) {
                renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
            }
        } else {
            showToast(`删除技能失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to delete skill:', e);
        showToast('删除技能失败', 'error');
    }
}

async function openSkillStore() {
    lastFocusedElement = document.activeElement;
    const modal = document.getElementById('skillStoreModal');
    const search = document.getElementById('skillStoreSearch');
    modal?.classList.add('active');
    if (search) search.value = '';
    renderSkillStore('');
    await refreshSkillStore();
    setTimeout(() => search?.focus(), 0);
}

function closeSkillStore() {
    document.getElementById('skillStoreModal')?.classList.remove('active');
    lastFocusedElement?.focus?.();
}

async function refreshSkillStore() {
    const refreshButton = document.getElementById('skillStoreRefresh');
    const meta = document.getElementById('skillStoreMeta');
    if (!canCallEel()) {
        markEelConnectionLost();
        return;
    }
    try {
        if (refreshButton) refreshButton.disabled = true;
        const result = await eel.list_skill_store()();
        if (result?.error) {
            if (meta) meta.textContent = `读取失败：${result.error}`;
            return;
        }
        updateSkillStoreSummary(result);
        renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
    } catch (error) {
        if (handleEelConnectionError(error)) return;
        if (meta) meta.textContent = '读取技能商店失败';
        console.error('Failed to refresh skill store:', error);
    } finally {
        if (refreshButton) refreshButton.disabled = false;
    }
}

function renderSkillStore(query = '') {
    const list = document.getElementById('skillStoreList');
    const meta = document.getElementById('skillStoreMeta');
    if (!list || !meta) return;
    const normalizedQuery = String(query || '').trim().toLocaleLowerCase();
    const visibleEntries = skillStoreEntries
        .map((skill, index) => ({skill, index}))
        .filter(({skill}) => {
            if (!normalizedQuery) return true;
            return `${skill.name || ''} ${skill.description || ''}`
                .toLocaleLowerCase()
                .includes(normalizedQuery);
        });
    const installableCount = skillStoreEntries.filter(skill => !skill.installed).length;
    meta.textContent = `${skillStoreEntries.length} 个技能 · ${installableCount} 个可安装`;

    if (!visibleEntries.length) {
        list.innerHTML = `<div class="skill-store-empty">${
            skillStoreEntries.length ? '没有匹配的技能' : '商店中暂无技能'
        }</div>`;
        return;
    }

    list.innerHTML = visibleEntries.map(({skill, index}) => {
        const installing = skillStoreInstallsInFlight.has(skill.name);
        let action = `
            <button class="skill-store-install" type="button" data-store-install-index="${index}" ${installing ? 'disabled' : ''}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>
                <span>${installing ? '安装中' : '安装'}</span>
            </button>`;
        if (skill.installed) {
            action = `<span class="skill-store-status ${skill.builtin ? 'is-builtin' : ''}">${skill.builtin ? '内置' : '已安装'}</span>`;
        }
        return `
            <div class="skill-store-item">
                <span class="skill-store-item-icon" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                </span>
                <span class="skill-store-item-copy">
                    <strong>${escapeHtml(skill.name)}</strong>
                    <small>${escapeHtml(skill.description || '暂无说明')}</small>
                </span>
                ${action}
            </div>`;
    }).join('');

    list.querySelectorAll('[data-store-install-index]').forEach(button => {
        const skill = skillStoreEntries[Number(button.dataset.storeInstallIndex)];
        button.addEventListener('click', () => installStoreSkill(skill.name));
    });
}

async function installStoreSkill(skillName) {
    if (!skillName || skillStoreInstallsInFlight.has(skillName)) return;
    skillStoreInstallsInFlight.add(skillName);
    renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
    try {
        const result = await eel.install_store_skill(skillName)();
        if (!result?.success) {
            showToast(`安装技能失败: ${result?.error || '未知错误'}`, 'error');
            return;
        }
        showToast(`技能安装成功: ${skillName}`, 'success');
        await refreshSkills();
    } catch (error) {
        if (handleEelConnectionError(error)) return;
        console.error('Failed to install store skill:', error);
        showToast('安装技能失败', 'error');
    } finally {
        skillStoreInstallsInFlight.delete(skillName);
        await refreshSkillStore();
    }
}

async function openSkillStoreFolder() {
    try {
        const result = await eel.open_skill_store_folder()();
        if (!result?.success) {
            showToast(`打开商店目录失败: ${result?.error || '未知错误'}`, 'error');
        }
    } catch (error) {
        if (handleEelConnectionError(error)) return;
        console.error('Failed to open skill store folder:', error);
        showToast('打开商店目录失败', 'error');
    }
}

// Memory Functions
async function refreshMemory() {
    // Memory files are always the same, just visual feedback
    const memoryFiles = document.getElementById('memoryFiles');
    memoryFiles.style.opacity = '0.5';
    setTimeout(() => {
        memoryFiles.style.opacity = '1';
    }, 200);
}

function toggleMemorySection() {
    const memoryFiles = document.getElementById('memoryFiles');
    if (memoryFiles.style.display === 'none') {
        memoryFiles.style.display = 'block';
    } else {
        memoryFiles.style.display = 'block'; // Always show
    }
}

async function openMemoryFile(fileType) {
    try {
        const result = await eel.read_memory_file(
            fileType, activeConversationId || ''
        )();

        if (result.error) {
            showToast(`读取内存失败: ${result.error}`, 'error');
            return;
        }

        const modal = document.getElementById('fileModal');
        const titleEl = document.getElementById('fileModalTitle');
        const contentEl = document.getElementById('fileContent');

        const memoryFileNames = {
            execution_history: 'execution_history.md',
            accumulated_compression: 'accumulated_compression.md',
            memory_context: 'memory_context.md',
        };
        titleEl.textContent = memoryFileNames[fileType] || 'memory.md';
        contentEl.textContent = result.content || '(empty)';
        modal.classList.add('active');
    } catch (e) {
        console.error('Failed to read memory file:', e);
        showToast('读取内存文件失败', 'error');
    }
}

// ==================== Data Integration Functions ====================

let selectedTaskIds = new Set();

function formatCompactDateTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${month}/${day} ${hours}:${minutes}`;
}

function openDataIntegration() {
    const modal = document.getElementById('dataModal');
    modal.classList.add('active');
    refreshDataStats();
}

function closeDataModal() {
    document.getElementById('dataModal').classList.remove('active');
    selectedTaskIds.clear();
    updateTaskSelectAllCheckbox();
}

function openArchiveModal() {
    document.getElementById('archiveModal').classList.add('active');
    refreshArchivedConversations();
}

function closeArchiveModal() {
    document.getElementById('archiveModal').classList.remove('active');
}

function openScheduledTasksModal() {
    document.getElementById('scheduledTasksModal').classList.add('active');
    loadScheduledTasks();
}

function closeScheduledTasksModal() {
    document.getElementById('scheduledTasksModal').classList.remove('active');
}

async function refreshArchivedConversations() {
    const list = document.getElementById('archivedConversationList');
    if (!list) return;
    try {
        const result = await eel.list_archived_conversations()();
        if (!result?.success) throw new Error(result?.error || '加载归档任务失败');
        const items = result.conversations || [];
        if (!items.length) {
            list.innerHTML = '<div class="data-item"><span class="data-source">暂无归档任务</span></div>';
            return;
        }
        list.innerHTML = items.map(item => {
            const safeId = encodeURIComponent(String(item.id || ''));
            const safeTitle = escapeHtml(item.title || '新任务');
            const safeTitleEncoded = encodeURIComponent(item.title || '新任务');
            const time = formatCompactDateTime(
                item.last_user_message_at || item.updated_at || item.created_at || ''
            );
            const count = Number(item.message_count || 0);
            return `
                <div class="data-item archive-item">
                    <div class="task-main">
                        <div class="task-header">
                            <span class="task-request" title="${safeTitle}">${safeTitle}</span>
                        </div>
                        <div class="task-details">
                            <span class="task-info">${escapeHtml(time)}</span>
                            <span class="task-info">${count} 条消息</span>
                        </div>
                    </div>
                    <div class="task-actions">
                        <button class="btn-small" onclick="restoreArchivedConversation(decodeURIComponent('${safeId}'))">恢复</button>
                        <button class="btn-delete-task" onclick="deleteArchivedConversation(decodeURIComponent('${safeId}'), decodeURIComponent('${safeTitleEncoded}'))">删除</button>
                    </div>
                </div>`;
        }).join('');
    } catch (error) {
        list.innerHTML = `<div class="data-item"><span class="data-source">加载失败：${escapeHtml(error.message)}</span></div>`;
    }
}

async function restoreArchivedConversation(conversationId) {
    try {
        const result = await eel.restore_conversation(conversationId)();
        if (!result?.success) return showToast(result?.error || '恢复失败', 'error');
        await refreshArchivedConversations();
        await refreshConversations(activeConversationId);
        showToast('任务已恢复到对话栏', 'success');
    } catch (error) {
        showToast(`恢复失败：${error.message}`, 'error');
    }
}

async function deleteArchivedConversation(conversationId, title) {
    try {
        const confirmed = await showConfirmDialog(
            `删除归档任务“${title || '该任务'}”？此操作不可撤销，将删除其全部对话和记忆。`
        );
        if (!confirmed) return;
        const result = await eel.delete_conversation(conversationId)();
        if (!result?.success) return showToast(result?.error || '删除失败', 'error');
        await refreshArchivedConversations();
        showToast('归档任务已删除', 'success');
    } catch (error) {
        showToast(`删除失败：${error.message}`, 'error');
    }
}

async function refreshDataStats() {
    try {
        // 获取任务列表（包含所有条目信息）
        const tasks = await eel.get_recent_tasks(20)();

        // 计算统计数据（基于任务条目）
        let totalEntries = 0;
        let toolCount = 0;
        let userCount = 0;
        let configCount = 0;

        if (tasks && tasks.length > 0) {
            tasks.forEach(t => {
                if (t.entries) {
                    t.entries.forEach(e => {
                        totalEntries++;
                        if (e.source === 'tool_result') toolCount++;
                        else if (e.source === 'user_behavior') userCount++;
                        else if (e.source === 'manual_config') configCount++;
                    });
                }
            });
        }

        // 更新统计显示
        document.getElementById('statTotal').textContent = totalEntries;
        document.getElementById('statTool').textContent = toolCount;
        document.getElementById('statUser').textContent = userCount;
        document.getElementById('statConfig').textContent = configCount;

        // Update data list with tasks (grouped)
        const dataList = document.getElementById('dataList');
        if (tasks && tasks.length > 0) {
            // Add select all header
            let html = `
                <div class="data-item task-header-row">
                    <label class="select-all-label">
                        <input type="checkbox" id="selectAllTasks" onchange="toggleSelectAllTasks(this)" ${selectedTaskIds.size === tasks.length ? 'checked' : ''}>
                        <span>全选</span>
                    </label>
                    <button class="btn-delete-selected" onclick="deleteSelectedTasks()" ${selectedTaskIds.size === 0 ? 'disabled' : ''}>
                        🗑️ 删除选中 (${selectedTaskIds.size})
                    </button>
                </div>
            `;

            html += tasks.map(t => {
                // Status color
                const statusColor = t.status === '已完成' ? '#4CAF50' : t.status === '进行中' ? '#2196F3' : '#FF9800';
                // Tools used text
                const toolsText = t.tools_used && t.tools_used.length > 0
                    ? t.tools_used.slice(0, 3).join(', ') + (t.tools_used.length > 3 ? '...' : '')
                    : '无';
                // Time formatting
                const startTime = formatCompactDateTime(t.start_time);
                // User request (truncated)
                const requestText = t.user_request && t.user_request.length > 0
                    ? (t.user_request.length > 36 ? t.user_request.substring(0, 36) + '...' : t.user_request)
                    : '无描述';
                const safeRequest = escapeHtml(requestText);
                const safeRequestTitle = escapeHtml(t.user_request || '');
                const safeToolsText = escapeHtml(toolsText);
                const safeTaskId = encodeURIComponent(String(t.task_id || ''));
                const safeStatus = escapeHtml(t.status || '未知');
                const isSelected = selectedTaskIds.has(t.task_id);

                return `
                <div class="data-item task-item ${isSelected ? 'selected' : ''}">
                    <div class="task-checkbox">
                        <input type="checkbox" data-task-id="${escapeHtml(String(t.task_id || ''))}" onclick="event.stopPropagation();" onchange="toggleTaskSelection(decodeURIComponent('${safeTaskId}'), this.checked)" ${isSelected ? 'checked' : ''}>
                    </div>
                    <div class="task-main">
                        <div class="task-header" onclick="event.stopPropagation(); showTaskDetail(decodeURIComponent('${safeTaskId}'))">
                            <span class="task-request" title="${safeRequestTitle}">${safeRequest}</span>
                            <span class="task-status" style="color: ${statusColor}">${safeStatus}</span>
                        </div>
                        <div class="task-details" onclick="event.stopPropagation(); showTaskDetail(decodeURIComponent('${safeTaskId}'))">
                            <span class="task-info">${escapeHtml(startTime)}</span>
                            <span class="task-info">${Number(t.steps_count || 0)} 步</span>
                            <span class="task-info" title="${safeToolsText}">${safeToolsText}</span>
                        </div>
                    </div>
                    <div class="task-actions">
                        <button class="btn-delete-task" onclick="event.stopPropagation(); deleteTask(decodeURIComponent('${safeTaskId}'))">删除</button>
                    </div>
                </div>
            `}).join('');
            dataList.innerHTML = html;
        } else {
            dataList.innerHTML = '<div class="data-item"><span class="data-source">暂无任务记录</span></div>';
        }
    } catch (e) {
        console.error('Failed to refresh data stats:', e);
    }
}

function toggleTaskSelection(taskId, checked) {
    if (checked) {
        selectedTaskIds.add(taskId);
    } else {
        selectedTaskIds.delete(taskId);
    }
    updateTaskSelectAllCheckbox();
    updateDeleteSelectedButton();
    // Update visual selection state
    const taskItems = document.querySelectorAll('.task-item:not(.task-header-row)');
    taskItems.forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (checkbox && checkbox.dataset.taskId === taskId) {
            item.classList.toggle('selected', checked);
        }
    });
}

function toggleSelectAllTasks(checkbox) {
    const tasks = checkbox.closest('.data-list').querySelectorAll('.task-item:not(.task-header-row)');
    if (checkbox.checked) {
        tasks.forEach(task => {
            const cb = task.querySelector('input[type="checkbox"]');
            if (cb) {
                selectedTaskIds.add(cb.dataset.taskId);
                task.classList.add('selected');
            }
        });
    } else {
        selectedTaskIds.clear();
        tasks.forEach(task => task.classList.remove('selected'));
    }
    updateDeleteSelectedButton();
    // Update individual checkboxes
    tasks.forEach(task => {
        const cb = task.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = checkbox.checked;
    });
}

function updateTaskSelectAllCheckbox() {
    const selectAll = document.getElementById('selectAllTasks');
    if (selectAll) {
        const tasks = document.querySelectorAll('.task-item:not(.task-header-row)');
        selectAll.checked = tasks.length > 0 && selectedTaskIds.size === tasks.length;
    }
}

function updateDeleteSelectedButton() {
    const btn = document.querySelector('.btn-delete-selected');
    if (btn) {
        btn.disabled = selectedTaskIds.size === 0;
        btn.textContent = `🗑️ 删除选中 (${selectedTaskIds.size})`;
    }
}

async function deleteSelectedTasks() {
    if (selectedTaskIds.size === 0) return;

    const confirmed = await showConfirmDialog(`确定要删除选中的 ${selectedTaskIds.size} 个任务吗？`);
    if (!confirmed) return;

    try {
        let successCount = 0;
        for (const taskId of selectedTaskIds) {
            const result = await eel.delete_task_data(taskId)();
            if (result && result.success) {
                successCount++;
            }
        }
        showToast(`已删除 ${successCount} 个任务`, 'success');
        selectedTaskIds.clear();
        refreshDataStats();
    } catch (e) {
        console.error('Failed to delete tasks:', e);
        showToast('删除失败', 'error');
    }
}

async function showTaskDetail(taskId) {
    try {
        const tasks = await eel.get_recent_tasks(100)();
        const task = tasks.find(t => t.task_id === taskId);
        if (!task) {
            showToast('未找到任务详情', 'error');
            return;
        }

        // Build detail content
        let content = `任务ID: ${task.task_id}\n`;
        content += `状态: ${task.status}\n`;
        content += `开始时间: ${new Date(task.start_time).toLocaleString()}\n`;
        if (task.end_time) {
            content += `结束时间: ${new Date(task.end_time).toLocaleString()}\n`;
        }
        content += `用户请求: ${task.user_request || '无'}\n`;
        content += `执行步数: ${task.steps_count}\n`;
        content += `使用工具: ${task.tools_used ? task.tools_used.join(', ') : '无'}\n\n`;
        content += `--- 详细记录 ---\n`;

        if (task.entries && task.entries.length > 0) {
            task.entries.forEach((e, i) => {
                const sourceMap = {
                    'tool_result': '工具结果',
                    'user_behavior': '用户行为',
                    'manual_config': '手动配置',
                    'ai_response': 'AI响应',
                    'system_event': '系统事件'
                };
                const sourceText = sourceMap[e.source] || e.source || e.data_type;
                content += `\n[${i + 1}] ${sourceText} - ${new Date(e.timestamp).toLocaleString()}\n`;
                if (e.data_type === 'tool_execution') {
                    content += `工具: ${e.content?.tool || 'unknown'}\n`;
                } else if (e.data_type === 'user_behavior') {
                    content += `行为: ${e.content?.action || 'unknown'}\n`;
                }
            });
        }

        const modal = document.getElementById('fileModal');
        const titleEl = document.getElementById('fileModalTitle');
        const contentEl = document.getElementById('fileContent');

        titleEl.textContent = `任务详情 (${task.task_id})`;
        contentEl.textContent = content;
        modal.classList.add('active');
    } catch (e) {
        console.error('Failed to show task detail:', e);
        showToast('获取任务详情失败', 'error');
    }
}

async function deleteTask(taskId) {
    const confirmed = await showConfirmDialog('确定要删除这个任务的所有数据吗？');
    if (!confirmed) return;
    try {
        const result = await eel.delete_task_data(taskId)();
        if (result && result.success) {
            showToast('任务数据已删除', 'success');
            refreshDataStats();
        } else {
            showToast('删除失败', 'error');
        }
    } catch (e) {
        console.error('Failed to delete task:', e);
        showToast('删除失败', 'error');
    }
}

async function clearAllData() {
    const confirmed = await showConfirmDialog('确定要清空所有数据整合记录吗？清空后 AI 提取偏好将没有数据可分析。');
    if (!confirmed) return;

    try {
        const result = await eel.clear_all_data()();
        if (result && result.success) {
            selectedTaskIds.clear();
            showToast('数据已清空', 'success');
            refreshDataStats();
        } else {
            showToast(result?.error || '清空数据失败', 'error');
        }
    } catch (e) {
        console.error('Failed to clear data:', e);
        showToast('清空数据失败', 'error');
    }
}

async function extractPreferences(button = null) {
    const btn = button || document.getElementById('extractPreferencesButton');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const result = await eel.extract_preferences_from_data()();
        if (result && result.success) {
            showToast(result.message || '偏好提取成功', 'success');

            // 关闭数据整合弹窗
            closeDataModal();

            // 打开偏好模块显示提取结果
            openPreferences();

            // 显示分析总结（用toast如果短，否则用弹窗）
            if (result.summary) {
                setTimeout(() => {
                    showToast('分析总结: ' + result.summary, 'info');
                }, 500);
            }
        } else {
            showToast(result.message || '提取失败', 'error');
        }
    } catch (e) {
        console.error('Failed to extract preferences:', e);
        showToast('提取失败', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 AI提取偏好';
    }
}

async function ingestConfig() {
    const configType = document.getElementById('configTypeInput').value;
    const configData = document.getElementById('configDataInput').value;

    if (!configType) {
        showToast('请输入配置类型', 'error');
        return;
    }

    let parsedData = {};
    if (configData) {
        try {
            parsedData = JSON.parse(configData);
        } catch (e) {
            parsedData = { value: configData };
        }
    }

    try {
        const result = await eel.ingest_manual_config(configType, parsedData)();
        if (result && !result.error) {
            showToast('配置已注入', 'success');
            document.getElementById('configTypeInput').value = '';
            document.getElementById('configDataInput').value = '';
            refreshDataStats();
        } else {
            showToast('注入失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to ingest config:', e);
        showToast('注入配置失败', 'error');
    }
}

// ==================== Preferences Functions ====================

let currentPrefCategory = 'operation_habit';
let selectedPrefKeys = new Set();

function openPreferences() {
    const modal = document.getElementById('prefModal');
    modal.classList.add('active');
    refreshPreferences();
    showPrefCategory('operation_habit');
}

function closePrefModal() {
    document.getElementById('prefModal').classList.remove('active');
    selectedPrefKeys.clear();
}

function showPrefCategory(category) {
    currentPrefCategory = category;

    // Update tab states
    document.querySelectorAll('.pref-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.pref-tab[onclick*="'${category}'"]`)?.classList?.add('active');

    refreshPreferences();
}

async function refreshPreferences() {
    try {
        const result = await eel.get_all_preferences()();
        if (result && !result.error) {
            const categoryPrefs = result[currentPrefCategory] || {};
            const prefList = document.getElementById('prefList');

            if (Object.keys(categoryPrefs).length > 0) {
                // Add select all header
                let html = `
                    <div class="pref-item pref-header-row">
                        <label class="select-all-label">
                            <input type="checkbox" id="selectAllPrefs" onchange="toggleSelectAllPrefs(this)" ${selectedPrefKeys.size === Object.keys(categoryPrefs).length ? 'checked' : ''}>
                            <span>全选</span>
                        </label>
                        <button class="btn-delete-pref" onclick="deleteSelectedPrefs()" ${selectedPrefKeys.size === 0 ? 'disabled' : ''}>
                            🗑️ 删除选中 (${selectedPrefKeys.size})
                        </button>
                    </div>
                `;

                html += Object.entries(categoryPrefs).map(([key, value]) => {
                    const isSelected = selectedPrefKeys.has(key);
                    const safeKey = escapeHtml(key);
                    const encodedKey = encodeURIComponent(key);
                    const safeValue = escapeHtml(
                        typeof value === 'object' ? JSON.stringify(value) : value
                    );
                    return `
                    <div class="pref-item ${isSelected ? 'selected' : ''}">
                        <div class="pref-checkbox">
                            <input type="checkbox" data-key="${escapeHtml(key)}" onchange="togglePrefSelection(decodeURIComponent('${encodedKey}'), this.checked)" ${isSelected ? 'checked' : ''}>
                        </div>
                        <div class="pref-content">
                            <span class="pref-key">${safeKey}</span>
                            <span class="pref-value">${safeValue}</span>
                        </div>
                        <button class="btn-delete-pref" onclick="event.stopPropagation(); deletePref(decodeURIComponent('${encodedKey}'))">删除</button>
                    </div>
                `}).join('');
                prefList.innerHTML = html;
            } else {
                prefList.innerHTML = '<div class="pref-item"><span class="pref-key">该分类暂无偏好</span></div>';
            }
        }

        // Refresh snapshots
        const snapshots = await eel.list_preference_snapshots()();
        const snapshotList = document.getElementById('prefSnapshots');
        if (snapshots && snapshots.length > 0) {
            snapshotList.innerHTML = snapshots.map(s => {
                const encodedId = encodeURIComponent(String(s.snapshot_id || ''));
                return `
                <div class="pref-snapshot-item">
                    <div class="snapshot-info" onclick="restoreSnapshotById(decodeURIComponent('${encodedId}'))">
                        <span class="snapshot-time">${escapeHtml(new Date(s.timestamp).toLocaleString())}</span>
                        <span class="snapshot-desc">${escapeHtml(s.description || '手动快照')} (${Number(s.entry_count || 0)} 条目)</span>
                    </div>
                    <div class="snapshot-actions">
                        <button class="btn-restore" onclick="event.stopPropagation(); restoreSnapshotById(decodeURIComponent('${encodedId}'))">回溯</button>
                        <button class="btn-delete-snapshot" onclick="event.stopPropagation(); deleteSnapshotById(decodeURIComponent('${encodedId}'))">删除</button>
                    </div>
                </div>
            `}).join('');
        } else {
            snapshotList.innerHTML = '<div class="pref-snapshot-item">暂无可用快照</div>';
        }
    } catch (e) {
        console.error('Failed to refresh preferences:', e);
    }
}

function togglePrefSelection(key, checked) {
    if (checked) {
        selectedPrefKeys.add(key);
    } else {
        selectedPrefKeys.delete(key);
    }
    updatePrefSelectAllCheckbox();
    updateDeletePrefSelectedButton();
    // Update visual selection state
    const prefItems = document.querySelectorAll('.pref-item:not(.pref-header-row)');
    prefItems.forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (checkbox && checkbox.dataset.key === key) {
            item.classList.toggle('selected', checked);
        }
    });
}

function toggleSelectAllPrefs(checkbox) {
    const prefs = document.querySelectorAll('.pref-item:not(.pref-header-row)');
    if (checkbox.checked) {
        prefs.forEach(pref => {
            const cb = pref.querySelector('input[type="checkbox"]');
            if (cb) {
                selectedPrefKeys.add(cb.dataset.key);
                pref.classList.add('selected');
            }
        });
    } else {
        selectedPrefKeys.clear();
        prefs.forEach(pref => pref.classList.remove('selected'));
    }
    updateDeletePrefSelectedButton();
    // Update individual checkboxes
    prefs.forEach(pref => {
        const cb = pref.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = checkbox.checked;
    });
}

function updatePrefSelectAllCheckbox() {
    const selectAll = document.getElementById('selectAllPrefs');
    if (selectAll) {
        const prefs = document.querySelectorAll('.pref-item:not(.pref-header-row)');
        selectAll.checked = prefs.length > 0 && selectedPrefKeys.size === prefs.length;
    }
}

function updateDeletePrefSelectedButton() {
    const btn = document.querySelector('.pref-header-row .btn-delete-pref');
    if (btn) {
        btn.disabled = selectedPrefKeys.size === 0;
        btn.textContent = `🗑️ 删除选中 (${selectedPrefKeys.size})`;
    }
}

async function deleteSelectedPrefs() {
    if (selectedPrefKeys.size === 0) return;

    const confirmed = await showConfirmDialog(`确定要删除选中的 ${selectedPrefKeys.size} 个偏好吗？`);
    if (!confirmed) return;

    try {
        let successCount = 0;
        for (const key of selectedPrefKeys) {
            const result = await eel.delete_preference(currentPrefCategory, key)();
            if (result && result.success) {
                successCount++;
            }
        }
        showToast(`已删除 ${successCount} 个偏好`, 'success');
        selectedPrefKeys.clear();
        refreshPreferences();
    } catch (e) {
        console.error('Failed to delete preferences:', e);
        showToast('删除失败', 'error');
    }
}

async function deletePref(key) {
    const confirmed = await showConfirmDialog(`确定要删除偏好「${key}」吗？`);
    if (!confirmed) return;

    try {
        const result = await eel.delete_preference(currentPrefCategory, key)();
        if (result && result.success) {
            showToast('偏好已删除', 'success');
            refreshPreferences();
        } else {
            showToast('删除失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to delete preference:', e);
        showToast('删除失败', 'error');
    }
}

async function clearAllPreferences() {
    const confirmed = await showConfirmDialog('确定要清空所有已保存偏好吗？这不会删除数据整合记录。');
    if (!confirmed) return;

    try {
        const result = await eel.clear_all_preferences()();
        if (result && result.success) {
            selectedPrefKeys.clear();
            showToast('偏好已清空', 'success');
            refreshPreferences();
        } else {
            showToast(result?.error || '清空偏好失败', 'error');
        }
    } catch (e) {
        console.error('Failed to clear preferences:', e);
        showToast('清空偏好失败', 'error');
    }
}

async function restoreSnapshotById(snapshotId) {
    const confirmed = await showConfirmDialog('确定要回溯到这个偏好快照吗？当前偏好将被覆盖。');
    if (!confirmed) return;

    try {
        const result = await eel.restore_preference_snapshot_by_id(snapshotId)();
        if (result && result.success) {
            showToast('已回溯到指定快照', 'success');
            refreshPreferences();
        } else {
            showToast('回溯失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to restore snapshot:', e);
        showToast('回溯失败', 'error');
    }
}

async function deleteSnapshotById(snapshotId) {
    const confirmed = await showConfirmDialog('确定要删除这个偏好快照吗？');
    if (!confirmed) return;

    try {
        const result = await eel.delete_preference_snapshot(snapshotId)();
        if (result && result.success) {
            showToast('快照已删除', 'success');
            refreshPreferences();
        } else {
            showToast('删除失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to delete snapshot:', e);
        showToast('删除失败', 'error');
    }
}

async function addPreference() {
    const category = document.getElementById('prefCategorySelect').value;
    const key = document.getElementById('prefKeyInput').value;
    const value = document.getElementById('prefValueInput').value;

    if (!key) {
        showToast('请输入偏好键', 'error');
        return;
    }

    let parsedValue = value;
    try {
        parsedValue = JSON.parse(value);
    } catch (e) {
        // Keep as string
    }

    try {
        const result = await eel.set_preference(category, key, parsedValue)();
        if (result && !result.error) {
            showToast('偏好已添加/更新', 'success');
            document.getElementById('prefKeyInput').value = '';
            document.getElementById('prefValueInput').value = '';
            refreshPreferences();
        } else {
            showToast('添加失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to add preference:', e);
        showToast('添加偏好失败', 'error');
    }
}

async function createPrefSnapshot() {
    try {
        const result = await eel.create_preference_snapshot('手动快照')();
        if (result && !result.error) {
            showToast('快照已创建', 'success');
            refreshPreferences();
        }
    } catch (e) {
        console.error('Failed to create snapshot:', e);
        showToast('创建快照失败', 'error');
    }
}

async function restoreLatestSnapshot() {
    const confirmed = await showConfirmDialog('确定要恢复最新的偏好快照吗？当前偏好将被覆盖。');
    if (!confirmed) return;

    try {
        const result = await eel.restore_preference_snapshot()();
        if (result && result.success) {
            showToast('快照已恢复', 'success');
            refreshPreferences();
        } else {
            showToast('恢复失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to restore snapshot:', e);
        showToast('恢复快照失败', 'error');
    }
}

// ==================== Knowledge Base Functions ====================

let selectedKbIds = new Set();

function openKnowledgeBase() {
    const modal = document.getElementById('knowledgeModal');
    modal.classList.add('active');
    refreshKnowledgeBase();
}

function closeKnowledgeModal() {
    document.getElementById('knowledgeModal').classList.remove('active');
    selectedKbIds.clear();
}

async function refreshKnowledgeBase() {
    try {
        const result = await eel.get_knowledge_stats()();
        if (result && !result.error) {
            document.getElementById('kbTotal').textContent = result.total_entries || 0;
            document.getElementById('kbWorkflows').textContent = result.by_type?.workflow || 0;
            document.getElementById('kbCases').textContent = result.by_type?.success_case || 0;
            document.getElementById('kbConflicts').textContent = result.unresolved_conflicts || 0;
        }

        // Load knowledge list
        const entries = await eel.list_knowledge_entries()();
        const kbList = document.getElementById('kbList');
        if (entries && entries.length > 0) {
            const typeMap = {
                'workflow': '工作流',
                'success_case': '成功案例',
                'template': '模板',
                'fact': '事实',
                'rule': '规则',
                'custom': '自定义'
            };

            // Add select all header
            let html = `
                <div class="kb-item kb-header-row">
                    <label class="select-all-label">
                        <input type="checkbox" id="selectAllKb" onchange="toggleSelectAllKb(this)" ${selectedKbIds.size === entries.length ? 'checked' : ''}>
                        <span>全选</span>
                    </label>
                    <button class="btn-delete-kb" onclick="deleteSelectedKb()" ${selectedKbIds.size === 0 ? 'disabled' : ''}>
                        🗑️ 删除选中 (${selectedKbIds.size})
                    </button>
                </div>
            `;

            html += entries.map(e => {
                const typeText = typeMap[e.knowledge_type] || e.knowledge_type;
                const isSelected = selectedKbIds.has(e.id);
                const encodedId = encodeURIComponent(String(e.id || ''));
                return `
                <div class="kb-item ${isSelected ? 'selected' : ''}">
                    <div class="kb-checkbox">
                        <input type="checkbox" data-id="${escapeHtml(String(e.id || ''))}" onchange="toggleKbSelection(decodeURIComponent('${encodedId}'), this.checked)" ${isSelected ? 'checked' : ''}>
                    </div>
                    <div class="kb-main">
                        <div class="kb-title">${escapeHtml(e.title)}</div>
                        <div class="kb-meta">${escapeHtml(typeText)} | v${escapeHtml(e.version)} | 使用 ${Number(e.usage_count || 0)} 次</div>
                    </div>
                </div>
            `}).join('');
            kbList.innerHTML = html;
        } else {
            kbList.innerHTML = `
                <div class="kb-empty-state">
                    <span>暂无知识条目</span>
                </div>
            `;
        }

        // Load conflicts
        const conflicts = await eel.get_knowledge_conflicts()();
        const conflictList = document.getElementById('conflictList');
        if (conflicts && conflicts.length > 0) {
            conflictList.innerHTML = conflicts.map(c => `
                <div class="conflict-item">
                    <span class="conflict-title">${escapeHtml(c.entry_a_title)} vs ${escapeHtml(c.entry_b_title)}</span>
                    <span class="conflict-badge">未解决</span>
                    <div class="conflict-detail">字段: ${escapeHtml(c.conflict_field)}</div>
                </div>
            `).join('');
        } else {
            conflictList.innerHTML = '<div class="conflict-item">暂无冲突</div>';
        }
    } catch (e) {
        console.error('Failed to refresh knowledge base:', e);
    }
}

function toggleKbSelection(id, checked) {
    if (checked) {
        selectedKbIds.add(id);
    } else {
        selectedKbIds.delete(id);
    }
    updateKbSelectAllCheckbox();
    updateDeleteKbSelectedButton();
}

function toggleSelectAllKb(checkbox) {
    const entries = document.querySelectorAll('.kb-item:not(.kb-header-row)');
    if (checkbox.checked) {
        entries.forEach(entry => {
            const cb = entry.querySelector('input[type="checkbox"]');
            if (cb) {
                selectedKbIds.add(cb.dataset.id);
                entry.classList.add('selected');
            }
        });
    } else {
        selectedKbIds.clear();
        entries.forEach(entry => entry.classList.remove('selected'));
    }
    updateDeleteKbSelectedButton();
    // Update individual checkboxes
    entries.forEach(entry => {
        const cb = entry.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = checkbox.checked;
    });
}

function updateKbSelectAllCheckbox() {
    const selectAll = document.getElementById('selectAllKb');
    if (selectAll) {
        const entries = document.querySelectorAll('.kb-item:not(.kb-header-row)');
        selectAll.checked = entries.length > 0 && selectedKbIds.size === entries.length;
    }
}

function updateDeleteKbSelectedButton() {
    const btn = document.querySelector('.kb-header-row .btn-delete-kb');
    if (btn) {
        btn.disabled = selectedKbIds.size === 0;
        btn.textContent = `🗑️ 删除选中 (${selectedKbIds.size})`;
    }
}

async function deleteSelectedKb() {
    if (selectedKbIds.size === 0) return;

    const confirmed = await showConfirmDialog(`确定要删除选中的 ${selectedKbIds.size} 个知识条目吗？`);
    if (!confirmed) return;

    try {
        let successCount = 0;
        for (const id of selectedKbIds) {
            const result = await eel.delete_knowledge_entry(id)();
            if (result && result.success) {
                successCount++;
            }
        }
        showToast(`已删除 ${successCount} 个知识条目`, 'success');
        selectedKbIds.clear();
        refreshKnowledgeBase();
    } catch (e) {
        console.error('Failed to delete knowledge entries:', e);
        showToast('删除失败', 'error');
    }
}

async function searchKnowledge() {
    const query = document.getElementById('kbSearchInput').value;
    const type = document.getElementById('kbTypeSelect').value;

    if (!query) {
        showToast('请输入搜索关键词', 'error');
        return;
    }

    try {
        const results = await eel.search_knowledge(query, type)();
        const kbResults = document.getElementById('kbResults');

        if (results && results.length > 0) {
            kbResults.innerHTML = results.map(r => {
                // Map English type names to Chinese
                const typeMap = {
                    'workflow': '工作流',
                    'success_case': '成功案例',
                    'template': '模板',
                    'fact': '事实',
                    'rule': '规则',
                    'custom': '自定义'
                };
                const typeText = typeMap[r.knowledge_type] || r.knowledge_type;
                return `
                <div class="kb-item">
                    <div class="kb-title">${escapeHtml(r.title)}</div>
                    <div class="kb-meta">${escapeHtml(typeText)} | 匹配度: ${Number(r.score || 0).toFixed(2)}</div>
                    <div class="kb-content">${escapeHtml(String(r.content || '').substring(0, 150))}...</div>
                    <div class="kb-tags">
                        ${(r.tags || []).map(t => `<span class="kb-tag">${escapeHtml(t)}</span>`).join('')}
                    </div>
                </div>
            `}).join('');
        } else {
            kbResults.innerHTML = '<div class="kb-item">未找到结果</div>';
        }
    } catch (e) {
        console.error('Failed to search knowledge:', e);
        showToast('搜索失败', 'error');
    }
}

async function addKnowledgeEntry() {
    const type = document.getElementById('kbNewTypeSelect').value;
    const title = document.getElementById('kbNewTitle').value;
    const content = document.getElementById('kbNewContent').value;
    const tagsStr = document.getElementById('kbNewTags').value;

    if (!title || !content) {
        showToast('请输入标题和内容', 'error');
        return;
    }

    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()) : [];

    try {
        const result = await eel.add_knowledge(type, title, content, tags)();
        if (result && !result.error) {
            showToast('知识已添加', 'success');
            document.getElementById('kbNewTitle').value = '';
            document.getElementById('kbNewContent').value = '';
            document.getElementById('kbNewTags').value = '';
            refreshKnowledgeBase();
        } else {
            showToast('添加失败: ' + (result?.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Failed to add knowledge:', e);
        showToast('添加知识失败', 'error');
    }
}

async function extractKnowledgeFromMemory(button = null) {
    const btn = button || document.getElementById('extractKnowledgeButton');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '提取中...';

    try {
        const result = await eel.extract_knowledge_from_memory()();
        const extractResult = document.getElementById('kbExtractResult');
        if (result && result.success) {
            showToast(result.message || `成功提取 ${result.extracted_count || 0} 条知识`, 'success');
            extractResult.innerHTML = `
                <div class="kb-item">
                    <div class="kb-title">提取完成</div>
                    <div class="kb-meta">已提取 ${result.extracted_count || 0} 条知识</div>
                    <div class="kb-content">${escapeHtml((result.message || '').substring(0, 200))}</div>
                </div>
            `;
            refreshKnowledgeBase();
        } else {
            const message = result?.message || '提取失败';
            showToast(message, 'error');
            extractResult.innerHTML = `<div class="kb-item">${escapeHtml(message)}</div>`;
        }
    } catch (e) {
        console.error('Failed to extract knowledge:', e);
        showToast('提取知识失败', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'AI提取记忆知识';
    }
}

function showKnowledgeDetail(entryId) {
    // For now just show a toast - could open a detail modal
    showToast('知识条目: ' + entryId, 'info');
}
