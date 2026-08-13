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
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓（女·普通话）' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊（女·普通话）' },
];
const AGENT_TEAM_MAX_MEMBERS = 12;
const AGENT_TEAM_MAX_SNAPSHOTS = 64;
const AGENT_ACTIVITY_MAX_ITEMS = 80;
const AGENT_PUBLIC_ACTIVITY_KINDS = new Set([
  'progress',
  'tool',
  'tool_event',
  'stream',
  'artifact',
  'result',
  'error',
  'status',
  'message',
  'handoff',
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

const SUPPORTED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);

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

function applyTheme(theme, { syncSplitPane = true } = {}) {
  const resolvedTheme = theme === 'dark' ? 'dark' : 'light';
  document.body.classList.toggle('theme-dark', resolvedTheme === 'dark');
  document.body.classList.toggle('theme-light', resolvedTheme === 'light');
  document.documentElement.style.colorScheme = resolvedTheme;
  localStorage.setItem('minibot-theme', resolvedTheme);
  applyThemeAssets(resolvedTheme);
  document
    .getElementById('themeToggle')
    ?.setAttribute('aria-label', resolvedTheme === 'dark' ? '切换到浅色主题' : '切换到深色主题');
  if (syncSplitPane) syncSplitTaskTheme(resolvedTheme);
}

function syncSplitTaskTheme(theme = getCurrentTheme()) {
  if (splitPaneMode) return;
  const frame = document.getElementById('splitTaskFrame');
  if (!frame?.contentWindow) return;
  frame.contentWindow.postMessage(
    { type: 'jcodex-theme-change', theme: theme === 'dark' ? 'dark' : 'light' },
    window.location.origin
  );
}

function notifyParentAgentDetail(open) {
  if (!splitPaneMode || window.parent === window) return;
  window.parent.postMessage(
    { type: 'jcodex-split-agent-detail', open: Boolean(open) },
    window.location.origin
  );
}

function notifyParentBrowserPreview(open) {
  if (!splitPaneMode || window.parent === window) return;
  window.parent.postMessage(
    { type: 'jcodex-split-browser-preview', open: Boolean(open) },
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
  if (
    !/Eel connection is unavailable|WebSocket is already in CLOSING or CLOSED state/i.test(message)
  ) {
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
  const activePanel = getSidebarPanelButtons().find((button) =>
    button.classList.contains('is-active')
  )?.dataset.sidebarPanel;
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
            return () => Promise.reject(new Error('桌面服务连接已断开，正在自动重新连接…'));
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
          return () => Promise.reject(new Error('桌面服务连接已断开，正在自动重新连接…'));
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

function stashPendingSend(
  message,
  attachments,
  conversationId,
  planMode,
  voiceMode,
  multiAgentMode,
  allowAll,
  mode
) {
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
    sessionStorage.setItem(PENDING_SEND_KEY, JSON.stringify({ ...base, attachments }));
    return;
  } catch (_quotaError) {
    // Attachments too large for sessionStorage: keep the text and retry
    // without attachments so the user's message is never lost.
  }
  try {
    sessionStorage.setItem(
      PENDING_SEND_KEY,
      JSON.stringify({ ...base, attachments: [], droppedAttachments: true })
    );
  } catch (_error) {
    // sessionStorage unavailable entirely; the send below will surface the
    // original connection error so the user can retry manually.
  }
}

function autoRecoverEelBridge(
  message,
  attachments,
  conversationId,
  planMode,
  voiceMode,
  multiAgentMode,
  allowAll,
  mode
) {
  stashPendingSend(
    message,
    attachments,
    conversationId,
    planMode,
    voiceMode,
    multiAgentMode,
    allowAll,
    mode
  );
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
  { force = false } = {}
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
  { force = false } = {}
) {
  if (!chatMessages) return;
  if (!force && !chatAutoFollow) return;
  if (force) setChatAutoFollow(true);
  const generation = ++chatBottomPinGeneration;
  chatMessages.style.scrollBehavior = 'auto';

  const align = (remainingFrames) => {
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
  const language = String(voice?.lang || '')
    .toLowerCase()
    .replace('_', '-');
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
  voicePreferredSpeechVoice =
    voices
      .map((voice, index) => ({ voice, index, score: getPreferredSpeechVoiceScore(voice) }))
      .filter((item) => Number.isFinite(item.score))
      .sort((left, right) => right.score - left.score || left.index - right.index)[0]?.voice ||
    null;
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
  if (!EDGE_TTS_VOICES.some((entry) => entry.id === voiceEdgeTtsVoice)) {
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
  return URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
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
  const outputActive = Boolean(isProcessing && getActiveExecutionState()?.running);
  hint.textContent = outputActive ? '按住空格打断并说话' : '按住空格说话';
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
    : voiceListening
      ? 0.31
      : 0.18;
  if (!voiceAnalyser) return synthetic;
  if (!voiceTimeDomainBuffer || voiceTimeDomainBuffer.length !== voiceAnalyser.fftSize) {
    voiceTimeDomainBuffer = new Uint8Array(voiceAnalyser.fftSize);
  }
  const data = voiceTimeDomainBuffer;
  voiceAnalyser.getByteTimeDomainData(data);
  let total = 0;
  data.forEach((value) => {
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
    ? { top: 'rgba(238, 238, 234, 0.95)', bottom: 'rgba(115, 115, 110, 0.5)' }
    : { top: 'rgba(31, 31, 29, 0.9)', bottom: 'rgba(111, 111, 106, 0.48)' };
}

function createVoiceStrandsRenderer() {
  const canvas = document.getElementById('voiceStrandsCanvas');
  const ctx = canvas?.getContext('2d', { alpha: true });
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
  return { width, height };
}

function drawVoiceStrands(timestamp = performance.now()) {
  if (!voiceStrandsRenderer) return;
  const renderer = voiceStrandsRenderer;
  const { ctx, barHeights } = renderer;
  const { width, height } = resizeVoiceStrands(renderer);
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
      target = minHeight + (maxHeight - minHeight) * (0.18 + 0.82 * energy) * envelope;
    } else {
      target = minHeight + (maxHeight - minHeight) * 0.12 * idleMotion;
    }
    const eased = barHeights[index] + (target - barHeights[index]) * 0.16;
    barHeights[index] = eased;
    const barX = startX + index * (barWidth + gap);
    const barHeight = Math.max(minHeight, eased);
    _voiceRoundRectPath(ctx, barX, baseY - barHeight, barWidth, barHeight, barWidth / 2);
    ctx.fill();
  }
  voiceStrandsPhase = (voiceStrandsPhase + 0.012 + energy * 0.018) % (Math.PI * 10);
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
  const { ctx, barHeights } = voiceStrandsRenderer;
  ctx.clearRect(0, 0, voiceStrandsRenderer.canvas.width, voiceStrandsRenderer.canvas.height);
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
      stream.getTracks().forEach((track) => track.stop());
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
  voiceAudioStream?.getTracks().forEach((track) => track.stop());
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
  streamingResponses.forEach((state) => {
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

  if (!voiceEdgeTtsFailed && typeof eel !== 'undefined' && eel.voice_tts_speak) {
    voiceCurrentUtterance = { generation, key: next.key, kind: 'edge' };
    eel.voice_tts_speak(
      next.content,
      voiceEdgeTtsVoice
    )((result) => {
      if (generation !== voiceSpeechGeneration || voiceCurrentUtterance?.key !== next.key) {
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
        if (generation !== voiceSpeechGeneration || voiceCurrentUtterance?.key !== next.key) {
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
  const speechText = String(content || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!speechText) return false;
  const key = String(speechKey || speechText);
  if (voiceSpeechKeys.has(key)) return false;
  voiceSpeechKeys.add(key);
  voiceSpeechQueue.push({ content: speechText, key });
  playNextVoiceResponse();
  return true;
}

function speakVoiceResponse(content, messageId = 0) {
  const visibleContent = getVisibleModelContent(content).replace(/\s+/g, ' ').trim();
  enqueueVoiceSpeech(visibleContent, `message:${Number(messageId || 0)}:${visibleContent}`);
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
  recognition.onresult = (event) => {
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
  recognition.onerror = (event) => {
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
        if (!voiceListening || !voiceSpaceHeld || !voiceModeActive || voiceRecognitionRunning)
          return;
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
    outputPaused ? '已暂停输出，正在聆听…松开空格键发送' : '正在聆听…松开空格键发送',
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

function stopVoiceListening({ send = true } = {}) {
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
  const blockingRecognitionError =
    voiceRecognitionError &&
    voiceRecognitionError !== 'no-speech' &&
    voiceRecognitionError !== 'aborted';
  if (!transcript || blockingRecognitionError) {
    if (voiceModeActive && !blockingRecognitionError) {
      setVoiceModeStatus('没有听清，请按住空格键重试', 'idle');
    }
    return;
  }
  const messageInput = document.getElementById('messageInput');
  messageInput.value = transcript;
  messageInput.dispatchEvent(new Event('input', { bubbles: true }));
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
  stopVoiceListening({ send: false });
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
    updates.running === true &&
    incomingMessageId &&
    incomingMessageId <= Number(state.terminalMessageId || 0)
  ) {
    return state;
  }
  if (updates.running === false && incomingMessageId) {
    state.terminalMessageId = Math.max(Number(state.terminalMessageId || 0), incomingMessageId);
  } else if (updates.running === true && incomingMessageId > Number(state.terminalMessageId || 0)) {
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
  return Array.from(conversationExecutionStates.values()).find((state) => state.running) || null;
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
  const terminalState = String(raw.terminal_state || raw.terminalState || '')
    .trim()
    .toLowerCase();
  const plan = raw.plan
    .filter((item) => item && String(item.step || '').trim())
    .map((item) => ({
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
    terminalMessage: String(raw.terminal_message || raw.terminalMessage || '').trim(),
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
  const activeState = getActiveExecutionState();
  const messageId = Number(activeState?.messageId || currentMessageId || 0);
  const key = planProgressKey(activeConversationId, messageId);
  const planState =
    snapshot ||
    activePlanProgress.get(key) ||
    (activeState?.running
      ? null
      : Array.from(activePlanProgress.values())
          .reverse()
          .find((item) => item.conversationId === String(activeConversationId || '')));
  if (!planState) {
    root.hidden = true;
    closePlanProgress();
    return;
  }

  const completed = planState.plan.filter((item) =>
    ['completed', 'cancelled'].includes(item.status)
  ).length;
  const currentIndex = planState.plan.findIndex((item) => item.status === 'in_progress');
  const pendingIndex = planState.plan.findIndex((item) => item.status === 'pending');
  const displayIndex =
    currentIndex >= 0 ? currentIndex : pendingIndex >= 0 ? pendingIndex : planState.plan.length - 1;
  const current = planState.plan[Math.max(0, displayIndex)];
  const isComplete = completed === planState.plan.length;
  const terminalState = String(planState.terminalState || '');
  const isFinished = ['complete', 'error', 'stopped'].includes(terminalState);
  const isFailure =
    Boolean(planState.error) || terminalState === 'error' || terminalState === 'stopped';
  const failureMessage =
    planState.terminalMessage ||
    planState.error ||
    (terminalState === 'stopped' ? '任务已停止' : '任务执行失败');
  const finishedMessage = planState.terminalMessage || '任务已结束';
  root.hidden = false;
  root.classList.toggle('is-complete', isComplete && !isFailure);
  root.classList.toggle('is-error', isFailure);
  root.classList.toggle('is-finished', isFinished);
  document.getElementById('planProgressCount').textContent = isFailure
    ? terminalState === 'stopped'
      ? '计划已停止'
      : '计划异常'
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
  document.getElementById('planProgressList').innerHTML = planState.plan
    .map(
      (item) => `
        <li class="plan-progress-item is-${item.status}">
            <span class="plan-progress-item-state" aria-hidden="true"></span>
            <span>${escapeHtml(item.step)}</span>
        </li>`
    )
    .join('');
}

function updatePlanProgress(result, conversationId, messageId) {
  if (result?.error) {
    const key = planProgressKey(conversationId, messageId);
    const previous = activePlanProgress.get(key);
    const normalized = previous
      ? { ...previous, error: String(result.error || '计划更新失败') }
      : {
          conversationId: String(conversationId || ''),
          messageId: Number(messageId || 0),
          explanation: '',
          version: 0,
          error: String(result.error || '计划更新失败'),
          plan: [{ step: '计划更新失败', status: 'pending' }],
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
  Array.from(activePlanProgress.keys()).forEach((key) => {
    if (key.startsWith(prefix)) activePlanProgress.delete(key);
  });
  if (String(conversationId || '') === String(activeConversationId || '')) {
    renderPlanProgress(null);
  }
}

function markPlanProgressTerminal(conversationId, messageId, terminalState, terminalMessage = '') {
  const normalizedState = String(terminalState || '')
    .trim()
    .toLowerCase();
  if (!['complete', 'error', 'stopped'].includes(normalizedState)) return;
  const key = planProgressKey(conversationId, messageId);
  const previous = activePlanProgress.get(key);
  if (!previous) return;
  if (normalizedState === 'complete' && ['error', 'stopped'].includes(previous.terminalState))
    return;
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

function normalizeToolActor(result) {
  return (
    String(result?.actor || 'primary')
      .trim()
      .toLowerCase() || 'primary'
  );
}

function isPrimaryToolEvent(result) {
  return normalizeToolActor(result) === 'primary';
}

function primaryToolSummary(copy, target = '') {
  return [copy, target].filter(Boolean).join(' · ');
}

function isQuestionToolName(toolName) {
  return QUESTION_TOOL_NAMES.has(
    String(toolName || '')
      .trim()
      .toLowerCase()
  );
}

function syncActiveConversationProcessingUI({ showPlaceholder = false } = {}) {
  const state = getActiveExecutionState();
  const visibleRunning = Boolean(state?.running && !state.outputStopped);
  isAwaitingQuestion = Boolean(visibleRunning && state.awaitingQuestion);

  if (visibleRunning) {
    currentMessageId = Number(state.messageId || currentMessageId || 0);
    updateProcessingUI(true, getExecutionStateText(state));
    if (
      showPlaceholder &&
      !state.awaitingQuestion &&
      !state.awaitingApproval &&
      !hasVisibleLiveActivity()
    ) {
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
      if (backendMessageId && backendMessageId <= Number(state.terminalMessageId || 0)) {
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
  const item = conversations.find((entry) => String(entry.id) === id);
  if (item) item.unread_completion = false;
}

function updateConversationListItemState(conversationId, updates = {}) {
  const id = String(conversationId || '');
  const item = conversations.find((entry) => String(entry.id) === id);
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
  messageQueue = messageQueue.filter((item) => {
    const itemId = typeof item === 'object' ? String(item.conversationId || '') : targetId;
    return itemId !== targetId;
  });
  updateQueueDisplay();
}

function queuedCountForConversation(conversationId) {
  const targetId = String(conversationId || activeConversationId || '');
  return messageQueue.filter((item) => {
    const itemId = typeof item === 'object' ? String(item.conversationId || '') : targetId;
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
  return String(file?.type || '')
    .split(';', 1)[0]
    .trim()
    .toLowerCase();
}

function isImageAttachment(item) {
  const type = getAttachmentMimeType(item);
  if (SUPPORTED_IMAGE_TYPES.has(type)) return true;
  return /\.(?:png|jpe?g|webp)$/i.test(String(item?.name || ''));
}

function isDirectoryReference(item) {
  return item?.kind === 'directory_reference' || item?.parse_mode === 'directory_reference';
}

function getImageMimeFromName(name) {
  const extension = String(name || '')
    .split('.')
    .pop()
    .toLowerCase();
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
  const resolvedType = SUPPORTED_IMAGE_TYPES.has(type) ? type : getImageMimeFromName(file.name);
  if (!SUPPORTED_IMAGE_TYPES.has(resolvedType)) return null;
  const hasUsefulName = String(file.name || '').includes('.');
  if (hasUsefulName && type === resolvedType) return file;
  const extension = resolvedType === 'image/jpeg' ? 'jpg' : resolvedType.split('/')[1];
  const name = hasUsefulName ? file.name : `粘贴图片-${Date.now()}.${extension}`;
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
    isImageAttachment(item) ||
    item?.parse_mode === 'vision' ||
    item?.parse_mode === 'image_view'
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
  container.innerHTML = composerAttachments
    .map((item) => {
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
            <button type="button" class="composer-attachment-remove" data-attachment-id="${escapeHtml(item.id)}" aria-label="移除 ${escapeHtml(item.name)}">×</button>
        </div>
    `;
    })
    .join('');
  container.querySelectorAll('.composer-attachment-remove').forEach((button) => {
    button.addEventListener('click', () => {
      removeComposerAttachment(button.dataset.attachmentId || '');
    });
  });
}

function removeComposerAttachment(id) {
  composerAttachments = composerAttachments.filter((item) => item.id !== id);
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
  const extension = String(name || '')
    .split('.')
    .pop();
  return extension && extension !== name ? extension.slice(0, 4).toUpperCase() : 'FILE';
}

function formatAttachmentSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function buildAttachmentPayload(attachments) {
  return attachments.map((item) => ({
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
    .filter((item) => item.kind === 'file' && getAttachmentMimeType(item).startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  if (itemFiles.length) return itemFiles;
  return Array.from(clipboardData?.files || []).filter((file) =>
    getAttachmentMimeType(file).startsWith('image/')
  );
}

function getDroppedFiles(dataTransfer) {
  return Array.from(dataTransfer?.files || []);
}

function getDroppedDirectoryEntries(dataTransfer) {
  return Array.from(dataTransfer?.items || [])
    .filter((item) => item.kind === 'file')
    .map((item) => item.webkitGetAsEntry?.())
    .filter((entry) => entry?.isDirectory);
}

function getDroppedFilePath(file) {
  return String(file?.path || file?.webkitRelativePath || '').trim();
}

function getPathBaseName(path) {
  return (
    String(path || '')
      .replace(/[\\/]+$/, '')
      .split(/[\\/]/)
      .pop() || ''
  );
}

function normalizeDirectoryReference(path, fallbackName = '') {
  const normalizedPath = String(path || '')
    .trim()
    .replace(/[\\/]+$/, '');
  if (!normalizedPath) return null;
  const name =
    normalizedPath.split(/[\\/]/).filter(Boolean).pop() || String(fallbackName || '参考文件夹');
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
    composerAttachments.filter(isDirectoryReference).map((item) => String(item.path || ''))
  );
  const availableSlots = ATTACHMENT_LIMITS.count - composerAttachments.length;
  const references = paths
    .map((path, index) => normalizeDirectoryReference(path, fallbackNames[index]))
    .filter((item) => item && !existingPaths.has(item.path))
    .slice(0, Math.max(0, availableSlots));
  if (!references.length) return 0;
  composerAttachments.push(...references);
  renderComposerAttachments();
  updateComposerSendState();
  return references.length;
}

async function getDroppedFolderPaths(dataTransfer, directoryEntries) {
  const directoryNames = new Set(directoryEntries.map((entry) => entry.name));
  const directPaths = getDroppedFiles(dataTransfer)
    .map(getDroppedFilePath)
    .filter((path) => path && directoryNames.has(getPathBaseName(path)));
  if (directPaths.length >= directoryEntries.length) return directPaths;
  if (typeof eel?.get_dragged_folder_paths !== 'function') return directPaths;
  try {
    const result = await eel.get_dragged_folder_paths(
      directoryEntries.map((entry) => entry.name)
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
  const folderNames = new Set(directoryEntries.map((entry) => entry.name));
  const matchedFolderPaths = folderPaths.filter((path) => folderNames.has(getPathBaseName(path)));
  const folderCount = addComposerDirectoryReferences(
    matchedFolderPaths,
    directoryEntries.map((entry) => entry.name)
  );
  const directoryNames = new Set(directoryEntries.map((entry) => entry.name));
  const regularFiles = droppedFiles.filter((file) => !directoryNames.has(file.name));
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
    if (
      parsed &&
      typeof parsed.folder === 'string' &&
      typeof parsed.path === 'string' &&
      parsed.path
    ) {
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

function updateQueueDisplay() {
  const queueEl = document.getElementById('messageQueue');
  const queueList = document.getElementById('queueList');
  const queueCount = document.getElementById('queueCount');
  const activeId = String(activeConversationId || '');

  const visible = [];
  messageQueue.forEach((item, globalIdx) => {
    const conversationId =
      typeof item === 'string' ? activeId : String(item.conversationId || activeId);
    if (conversationId === activeId) visible.push({ item, globalIdx });
  });

  if (visible.length === 0) {
    queueEl.style.display = 'none';
    queueList.innerHTML = '';
    return;
  }

  if (!queueList.dataset.queueDelegationBound) {
    queueList.dataset.queueDelegationBound = 'true';
    queueList.addEventListener('click', (event) => {
      const button = event.target.closest('.queue-item-remove');
      if (!button) return;
      removeFromQueue(Number(button.dataset.queueIndex || 0));
    });
  }

  queueEl.style.display = 'block';
  queueCount.textContent = visible.length;

  queueList.innerHTML = visible
    .map(({ item, globalIdx }, visibleIdx) => {
      const message = typeof item === 'string' ? item : item.message;
      const attachmentCount = typeof item === 'string' ? 0 : (item.attachments || []).length;
      const label = `${message || '解析附件'}${attachmentCount ? ` · ${attachmentCount} 个附件` : ''}`;
      return `
        <div class="queue-item">
            <span class="queue-item-number">${visibleIdx + 1}.</span>
            <span class="queue-item-text" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
            <button class="queue-item-remove" data-queue-index="${globalIdx}" aria-label="移除第 ${visibleIdx + 1} 个等待任务">✕</button>
        </div>
    `;
    })
    .join('');
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
  // Static button wiring lives in each extracted module (see js/*.js).
  bindWorkspaceStaticEvents();
  bindMemoryStaticEvents();
  bindSkillsStaticEvents();
  bindDataStaticEvents();
  bindSettingsStaticEvents();
  bindDialogStaticEvents();
  bindPreferencesStaticEvents();
  bindKnowledgeStaticEvents();
  setSidebarCollapsed(getSavedSidebarCollapsed(), { persist: false });
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
      refreshConversations(splitPaneMode ? splitTaskIdFromUrl : activeConversationId).catch(
        (error) => {
          if (handleEelConnectionError(error)) return;
          console.error('Failed to sync task activity:', error);
        }
      );
    }
  }, 1800);
}

document.addEventListener('DOMContentLoaded', () => {
  initializeTheme();
  if (splitPaneMode) document.body.classList.add('split-pane-mode');
  init();
});

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  if (
    splitPaneMode &&
    event.source === window.parent &&
    event.data?.type === 'jcodex-theme-change'
  ) {
    applyTheme(event.data.theme, { syncSplitPane: false });
    return;
  }
  const splitFrame = document.getElementById('splitTaskFrame');
  if (
    !splitPaneMode &&
    event.source === splitFrame?.contentWindow &&
    event.data?.type === 'jcodex-split-agent-detail'
  ) {
    setSplitChildAgentDetailOpen(event.data.open);
    return;
  }
  if (
    !splitPaneMode &&
    event.source === splitFrame?.contentWindow &&
    event.data?.type === 'jcodex-split-browser-preview'
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
        const leavingFromSubmenu = !!(
          event.target &&
          event.target.closest &&
          event.target.closest('.model-reasoning-submenu')
        );
        const related = event.relatedTarget;
        const goingOutside = !(related && related.nodeType === 1 && modelMenuEl.contains(related));
        if (goingOutside && !leavingFromSubmenu) {
          submenus.forEach((sub) => sub.classList.remove('is-open'));
        }
      });
    }
  }

  // 点击菜单外部时关闭 API 配置下拉框与模型上拉框
  document.addEventListener('click', (event) => {
    const configMenu = document.getElementById('configSelectMenu');
    const configTrigger = document.getElementById('configSelectTrigger');
    if (
      configMenu &&
      !configMenu.hidden &&
      !configTrigger?.contains(event.target) &&
      !configMenu.contains(event.target)
    ) {
      closeApiConfigMenu();
    }
    const modelMenu = document.getElementById('modelQuickSwitch');
    const badgeEl = document.getElementById('modelBadge');
    if (
      modelMenu &&
      !modelMenu.hidden &&
      !badgeEl?.contains(event.target) &&
      !modelMenu.contains(event.target)
    ) {
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
  voiceHoldButton?.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    if (voicePointerId !== null) return;
    voicePointerId = event.pointerId;
    voiceHoldButton.setPointerCapture?.(event.pointerId);
    voiceSpaceHeld = true;
    startVoiceListening();
  });
  voiceHoldButton?.addEventListener('pointerup', (event) => {
    event.preventDefault();
    if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
    stopVoiceListening();
  });
  voiceHoldButton?.addEventListener('pointercancel', (event) => {
    if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
    stopVoiceListening({ send: false });
  });
  voiceHoldButton?.addEventListener('lostpointercapture', (event) => {
    if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
    if (voiceSpaceHeld) stopVoiceListening({ send: false });
  });
  document.addEventListener(
    'keydown',
    (event) => {
      if (!voiceModeActive || event.code !== 'Space') return;
      if (isVoiceShortcutBlocked(event.target)) return;
      event.preventDefault();
      if (event.repeat) return;
      voiceSpaceHeld = true;
      startVoiceListening();
    },
    true
  );
  document.addEventListener(
    'keyup',
    (event) => {
      if (!voiceModeActive || event.code !== 'Space') return;
      if (isVoiceShortcutBlocked(event.target)) return;
      event.preventDefault();
      if (!voiceSpaceHeld) return;
      stopVoiceListening();
    },
    true
  );
  window.addEventListener('pointerup', (event) => {
    if (!voiceModeActive || !voiceSpaceHeld) return;
    if (voicePointerId !== null && event.pointerId !== voicePointerId) return;
    stopVoiceListening();
  });
  window.addEventListener('blur', () => {
    if (voiceSpaceHeld) stopVoiceListening({ send: false });
  });
  if (inputAddButton) {
    inputAddButton.addEventListener('click', () => {
      toggleComposerAddMenu();
    });
    inputAddButton.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        openComposerAddMenu(true);
      } else if (event.key === 'Escape') {
        closeComposerAddMenu(true);
      }
    });
  }
  composerAddMenu?.addEventListener('click', (event) => {
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
  composerAddMenu?.addEventListener('keydown', (event) => {
    const items = getComposerAddMenuItems();
    const currentIndex = items.indexOf(document.activeElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      closeComposerAddMenu(true);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!items.length) return;
      const offset = event.key === 'ArrowDown' ? 1 : -1;
      const nextIndex =
        currentIndex < 0 ? 0 : (currentIndex + offset + items.length) % items.length;
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
  initializeChangeReviewFilesResizeHandle(document.getElementById('changeReviewFilesResizeHandle'));
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
  document.getElementById('projectBrowseButton')?.addEventListener('click', async (event) => {
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
          document.getElementById('projectNameInput').value =
            result.path.split(/[\\/]/).filter(Boolean).pop() || '';
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
  document.getElementById('projectDialog')?.addEventListener('click', (event) => {
    if (event.target.id === 'projectDialog') closeProjectDialog();
  });
  sidebarNav?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-sidebar-panel]');
    if (!button) return;
    setSidebarPanel(button.dataset.sidebarPanel, { focus: false });
  });
  sidebarNav?.addEventListener('keydown', (event) => {
    const items = getSidebarPanelButtons();
    const currentIndex = items.indexOf(document.activeElement);
    if (!items.length || currentIndex < 0) return;
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key))
      return;
    event.preventDefault();
    let nextIndex = currentIndex;
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight')
      nextIndex = (currentIndex + 1) % items.length;
    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft')
      nextIndex = (currentIndex - 1 + items.length) % items.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = items.length - 1;
    items[nextIndex].focus();
    setSidebarPanel(items[nextIndex].dataset.sidebarPanel, { focus: false });
  });
  chatMessages?.addEventListener('click', handleAgentTeamClick);
  chatMessages?.addEventListener('click', handlePreviewLinkClick);
  document.addEventListener('click', handleImagePreviewClick);
  document.addEventListener('keydown', handleImagePreviewKeydown);
  imageLightboxClose?.addEventListener('click', () => closeImageLightbox());
  imageLightbox?.addEventListener('click', (event) => {
    if (event.target === imageLightbox) closeImageLightbox();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && imageLightbox && !imageLightbox.hidden) {
      event.preventDefault();
      closeImageLightbox();
    }
  });
  chatMessages?.addEventListener(
    'scroll',
    () => {
      updateChatAutoFollow(chatMessages);
      maybeLoadOlderChatHistory(chatMessages);
    },
    { passive: true }
  );
  chatMessages?.addEventListener(
    'wheel',
    (event) => {
      if (event.deltaY < 0) setChatAutoFollow(false);
    },
    { passive: true }
  );
  document.getElementById('changeReviewClose')?.addEventListener('click', () => {
    closeChangeReview();
  });
  document.getElementById('agentDetailClose')?.addEventListener('click', () => {
    closeAgentDetail();
  });
  document.getElementById('changeReviewFileList')?.addEventListener('click', (event) => {
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
      document.getElementById('changeReviewDiff')?.focus({ preventScroll: true });
    }
  });
  document.getElementById('browserPreviewClose')?.addEventListener('click', () => {
    closeBrowserPreview();
  });
  document
    .getElementById('browserPreviewRefresh')
    ?.addEventListener('click', refreshBrowserPreview);
  document
    .getElementById('browserPreviewCopy')
    ?.addEventListener('click', copyBrowserPreviewAddress);
  document
    .getElementById('browserPreviewExternal')
    ?.addEventListener('click', openBrowserPreviewExternal);
  document.getElementById('browserPreviewStop')?.addEventListener('click', stopBrowserPreview);
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
        updateAgentTeamSnapshot(result.agent_team, conversationId, messageId, { animate: false });
      }
      const modifiedFiles = result?.modified_files;
      if (
        modifiedFiles &&
        String(activeConversationId || '') === conversationId &&
        Number(modifiedFiles.message_id || messageId) === messageId
      ) {
        addModifiedFilesSummary({
          ...modifiedFiles,
          conversation_id: conversationId,
          message_id: messageId,
        });
      }
      markPlanProgressTerminal(conversationId, messageId, 'stopped', '任务已停止');
      markAgentTeamsTerminal(conversationId, messageId, 'cancelled');
      showToast('已停止输出，可以继续发送消息', 'success', 1800);
      refreshConversations(activeConversationId).catch(console.error);
      dispatchNextQueuedMessage();
    } catch (error) {
      console.error('Stop error:', error);
      const status = await eel
        .get_execution_status(conversationId, messageId)()
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
      syncActiveConversationProcessingUI({ showPlaceholder: true });
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

  quickActions.forEach((btn) => {
    btn.addEventListener('click', () => {
      fillComposer(btn.dataset.prompt || '');
    });
  });
  planProgressTrigger?.addEventListener('click', () => {
    const expanded = !planProgress?.classList.contains('is-expanded');
    planProgress?.classList.toggle('is-expanded', expanded);
    planProgressTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  });
  document.addEventListener('click', (event) => {
    if (!planProgress?.hidden && !planProgress.contains(event.target)) {
      closePlanProgress();
    }
    if (!composerAddMenu?.hidden && !composerAddMenuAnchor?.contains(event.target)) {
      closeComposerAddMenu();
    }
  });
  document.addEventListener('keydown', (event) => {
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
        const duplicate = composerAttachments.some(
          (item) => isDirectoryReference(item) && String(item.path || '') === String(result.path)
        );
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
  const scrollAreas = document.querySelectorAll(
    [
      '.sidebar-panel',
      '.sidebar-panel.is-active .task-history-list',
      '#sidebarPanelFiles .file-list',
      '#sidebarPanelSkills #skillsList',
    ].join(',')
  );
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
    area.addEventListener('scroll', show, { passive: true });
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
  messageInput.dispatchEvent(new Event('input', { bubbles: true }));
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

function getWelcomeHeading(conversation = getActiveConversation()) {
  const project = getProject(conversation?.project_id);
  const projectName = String(project?.name || '').trim();
  return projectName ? `今天想在“${projectName}”里完成什么？` : '今天想完成什么？';
}

function updateWelcomeHeading(conversation = getActiveConversation()) {
  const heading = document.getElementById('welcomeTitle');
  if (heading) {
    heading.textContent =
      appMode === 'jcchat' ? '今天想聊点什么？' : getWelcomeHeading(conversation);
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
  document.querySelectorAll('.quick-action').forEach((button) => {
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
  closeImageLightbox({ restoreFocus: false });
  closeAgentDetail({ restoreFocus: false });
  closeChangeReview({ restoreFocus: false });
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
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function getProject(projectId) {
  const id = String(projectId || '');
  return projects.find((project) => String(project.id || '') === id) || null;
}

function getActiveConversation() {
  return (
    conversations.find((item) => String(item.id || '') === String(activeConversationId || '')) ||
    null
  );
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

  projects.forEach((project) => {
    const projectId = String(project.id || '');
    const projectTasks = conversations.filter(
      (item) => !item.is_split_task && String(item.project_id || '') === projectId
    );
    const activeInside = projectTasks.some(
      (item) => String(item.id || '') === String(activeConversationId || '')
    );
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

    projectTasks.forEach((item) => {
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
    header.querySelector('.project-menu').addEventListener('click', (event) => {
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
  menu.addEventListener('click', (event) => {
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
    (item) => !item.project_id && !item.is_split_task
  );
  if (count)
    count.textContent = ordinaryConversations.length ? `${ordinaryConversations.length}` : '';
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
    Array.from(list.querySelectorAll('.task-history-item')).map((row) => [
      String(row.dataset.conversationId || ''),
      row,
    ])
  );

  ordinaryConversations.forEach((item, index) => {
    const conversationId = String(item.id || '');
    const row = existingRows.get(conversationId) || createTaskHistoryItem(conversationId);
    applyTaskRowState(row, item);

    const currentAtIndex = list.children[index];
    if (currentAtIndex !== row) {
      list.insertBefore(row, currentAtIndex || null);
    }
    existingRows.delete(conversationId);
  });

  existingRows.forEach((row) => row.remove());
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
    result = await eel.list_conversations(splitPaneMode ? splitTaskIdFromUrl : '')();
  } catch (error) {
    if (handleEelConnectionError(error)) return activeConversationId;
    throw error;
  }
  if (!result?.success) throw new Error(result?.error || '任务列表加载失败');
  if (generation !== conversationRefreshGeneration) return activeConversationId;
  conversations = result.conversations || [];
  syncExecutionStatesFromConversations(conversations);
  const pinnedConversationExists =
    splitPaneMode &&
    splitTaskIdFromUrl &&
    conversations.some((item) => String(item.id) === splitTaskIdFromUrl);
  const preferredExists =
    preferredId && conversations.some((item) => String(item.id) === String(preferredId));
  activeConversationId = pinnedConversationExists
    ? splitTaskIdFromUrl
    : preferredExists
      ? preferredId
      : result.active_id || conversations[0]?.id || null;
  const active = conversations.find((item) => item.id === activeConversationId);
  if (active) updateActiveTaskTitle(active.title);
  updateActiveProjectLabel(active);
  renderConversationList();
  conversationExecutionStates.forEach((state) => {
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
    syncActiveConversationProcessingUI({ showPlaceholder: true });
    // Split-pane state and execution placeholders can reflow the chat after
    // its history is first rendered. A task switch should always end at the
    // newest message instead of retaining the previous task's scroll anchor.
    pinChatToBottom(document.getElementById('chatMessages'), { force: true });
    updateTokenIndicator();
    closeMobileSidebar();
  } catch (error) {
    showToast(`切换任务失败：${error.message}`, 'error');
  }
}

function openConversationMenu(event, conversationId) {
  document.querySelector('.conversation-context-menu')?.remove();
  const item = conversations.find((entry) => entry.id === conversationId);
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
      pinChatToBottom(document.getElementById('chatMessages'), { force: true });
    }
    updateTokenIndicator();
    showToast('任务已归档', 'success');
  };
  const moveOut = menu.querySelector('[data-action="move-out"]');
  if (moveOut)
    moveOut.onclick = async () => {
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
    const splitWasOpen =
      deletedWasActive && document.body.classList.contains('split-workspace-open');
    if (deletedWasActive) {
      splitStateGeneration += 1;
      hideSplitTaskPane();
    }
    const result = await eel.delete_conversation(conversationId)();
    if (!result?.success) {
      if (splitWasOpen) await restoreSplitTaskForConversation(conversationId);
      return showToast(result?.error || '删除失败', 'error');
    }
    const deletedConversationIds = Array.from(
      new Set((result.deleted_conversation_ids || [conversationId]).map(String))
    );
    deletedConversationIds.forEach((deletedId) => {
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
    pinChatToBottom(document.getElementById('chatMessages'), { force: true });
  };
  setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
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
  document.getElementById('projectDialogSave').textContent = project
    ? '保存项目'
    : '添加并新建任务';
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
  setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
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
  accessToggle.title = enabled
    ? '当前为完全访问：工具自动执行'
    : '当前为询问模式：执行敏感工具前确认';
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
  planModePill.setAttribute('aria-label', isEnabled ? '计划模式已开启' : '计划模式已关闭');
}

function setPlanModeEnabled(enabled) {
  planModeEnabled = Boolean(enabled);
  localStorage.setItem('minibot-plan-mode-enabled', planModeEnabled ? 'true' : 'false');
  applyPlanModeToggleState(planModeEnabled);
  showToast(planModeEnabled ? '计划模式已开启' : '计划模式已关闭', 'info', 1600);
}

function applyMultiAgentModeToggleState(enabled) {
  const pill = document.getElementById('multiAgentModePill');
  if (!pill) return;
  const isEnabled = Boolean(enabled);
  pill.hidden = !isEnabled;
  pill.setAttribute('aria-label', isEnabled ? '多智能体协作已开启' : '多智能体协作已关闭');
}

function setMultiAgentModeEnabled(enabled) {
  multiAgentModeEnabled = Boolean(enabled);
  localStorage.setItem(
    'minibot-multi-agent-mode-enabled',
    multiAgentModeEnabled ? 'true' : 'false'
  );
  applyMultiAgentModeToggleState(multiAgentModeEnabled);
  showToast(multiAgentModeEnabled ? '多智能体协作已开启' : '多智能体协作已关闭', 'info', 1600);
}

function getComposerAddMenuItems() {
  return Array.from(document.querySelectorAll('#composerAddMenu [role="menuitem"]:not(:disabled)'));
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
      ? dimension
        ? `Hybrid ${dimension}D`
        : 'Hybrid'
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
    const result = await eel.initialize(splitPaneMode ? splitTaskIdFromUrl : '')();

    if (result[0]) {
      isInitialized = true;
      await eel.load_settings()();
      await refreshProjects();
      const conversationId = await refreshConversations();
      const initialConversationId =
        splitPaneMode && splitTaskIdFromUrl ? splitTaskIdFromUrl : conversationId;
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
    const planMatchesActiveRun =
      !activeExecution?.running || latestPlan?.messageId === Number(activeExecution.messageId || 0);
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
    pinChatToBottom(chatMessages, { force: true });
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
      addUserMessage(event.content || '请解析附件', event.attachments || [], messageId, false);
    } else if (event.type === 'assistant') {
      const { thoughts, answer } = splitThinkingContent(event.content || '');
      const thinkingDurationMs = getPersistedThinkingDuration(event);
      thoughts.forEach((thought) =>
        addThinkingCard(thought, null, false, false, true, thinkingDurationMs)
      );
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
      thoughts
        .filter(Boolean)
        .forEach((thought) =>
          addThinkingCard(thought, null, false, false, true, getPersistedThinkingDuration(event))
        );
    } else if (event.type === 'commentary') {
      addCommentaryMessage(event.content || '', false);
    } else if (event.type === 'agent_team') {
      updateAgentTeamSnapshot(event, activeConversationId, messageId, { animate: false });
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
      finishCompressionActivity(
        {
          ...event,
          message: event.content || '记忆压缩已结束',
        },
        messageId
      );
    } else if (event.type === 'question') {
      addAnsweredQuestionCard(
        event.questions || [],
        event.answers || [],
        messageId,
        event.question_id || '',
        event.supplements || []
      );
    } else if (event.type === 'preview') {
      upsertProjectPreview(
        {
          ...event,
          conversation_id: event.conversation_id || activeConversationId || '',
        },
        false
      );
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
    updateConversationExecutionState(conversationId, { running: false });
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
  resetTrackedExecutionActivity(getConversationExecutionState(targetConversationId, false));

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
    if (result?.status === 'busy' || result?.status === 'error') {
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
    updateConversationExecutionState(targetConversationId, { running: false });
    syncActiveConversationProcessingUI();
    renderConversationList();
    if (messageQueue.length > 0) setTimeout(dispatchNextQueuedMessage, 120);
  }
}

function shouldRenderExecution(conversationId, state = null) {
  const execution = state || getConversationExecutionState(conversationId, false);
  return (
    String(conversationId || '') === String(activeConversationId || '') &&
    !execution?.outputStopped &&
    !execution?.liveRenderSuppressed
  );
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
  updateConversationExecutionState(executionId, { messageId, running: true });
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
      const results =
        typeof eel.get_next_results === 'function'
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
        updateAgentTeamSnapshot(status.agent_team, executionId, messageId, { animate: false });
      }

      // The backend may still persist task-end events after the model is
      // done. Keep polling for those events, but never keep the composer
      // or Stop button in a running state after `running` becomes false.
      const backendFinalizationPending = !status?.running && status?.finalized === false;
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
        const lateResult = await drainLateTaskResults(executionId, messageId, poller);
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
        finishCurrentMessage(executionId, messageId, 'error', '桌面端与执行服务连接中断');
      }
    } finally {
      poller.inFlight = false;
    }
  }, 90);
  poller.intervalId = intervalId;
}

function isTerminalTaskEvent(result) {
  return (
    result?.type === 'final' ||
    result?.type === 'error' ||
    (result?.type === 'compression_end' && !result.task_continues) ||
    (result?.type === 'stream_end' && result.target === 'final' && !result.task_continues)
  );
}

async function drainLateTaskResults(conversationId, msgId, poller) {
  let hadResults = false;
  for (let batch = 0; batch < 8; batch += 1) {
    const results =
      typeof eel.get_next_results === 'function'
        ? await eel.get_next_results(conversationId, msgId, 64)()
        : [await eel.get_next_result(conversationId, msgId)()].filter(Boolean);
    if (executionPollers.get(String(conversationId || '')) !== poller) {
      return { valid: false, terminal: false, hadResults };
    }
    if (!results.length) break;
    hadResults = true;
    for (const result of results) {
      handleResult(result, msgId, conversationId);
      if (isTerminalTaskEvent(result)) poller.terminalEventSeen = true;
    }
  }
  return { valid: true, hadResults };
}

// Compatibility marker for the former single-task polling contract:
// await drainLateTaskResults(msgId, generation)
// else if (!activeCompressionActivities.size)

async function restoreExecutionState() {
  try {
    const runningItems = conversations.filter((item) => item.running);
    await Promise.all(
      runningItems.map(async (item) => {
        const conversationId = String(item.id || '');
        const hintedMessageId = Number(item.active_message_id || item.message_id || 0);
        const status = await eel.get_execution_status(conversationId, hintedMessageId)();
        const messageId = Number(
          status?.pending_question?.message_id ||
            status?.pending_approval?.message_id ||
            status?.message_id ||
            hintedMessageId ||
            0
        );
        if (status?.agent_team && conversationId && messageId) {
          updateAgentTeamSnapshot(status.agent_team, conversationId, messageId, { animate: false });
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
          syncActiveConversationProcessingUI({ showPlaceholder: true });
          if (status.awaiting_approval) {
            restorePendingApproval(status, conversationId);
          }
          if (status.awaiting_question) {
            restorePendingQuestion(status, conversationId);
          }
        }
        ensureExecutionPolling(state.conversationId, messageId);
      })
    );
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
  refreshConversations(activeConversationId).catch((error) => {
    console.error('Failed to refresh task history:', error);
  });
  // Reconcile only the task-end summary. Rebuilding the whole conversation
  // here clears the live DOM, causes a visible scroll jump, and can race with
  // the last queued event even though the summary is already persisted.
  if (isVisible && id) {
    eel
      .load_conversation(id)()
      .then((result) => {
        if (String(activeConversationId || '') !== id) return;
        if (!result?.success) return;
        const messageId = Number(msgId || 0);
        const summary = [...(result.conversation?.messages || [])]
          .reverse()
          .find(
            (event) =>
              event?.type === 'modified_files' && Number(event.message_id || 0) === messageId
          );
        if (summary) addModifiedFilesSummary(summary, false);
      })
      .catch((error) => {
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
    const queuedIndex = messageQueue.findIndex((item) => {
      const conversationId =
        typeof item === 'string'
          ? String(activeConversationId || '')
          : String(item.conversationId || activeConversationId || '');
      return !isConversationRunning(conversationId);
    });
    if (queuedIndex < 0) {
      setTimeout(dispatchNextQueuedMessage, 180);
      return;
    }
    const queued = messageQueue[queuedIndex];
    const conversationId =
      typeof queued === 'string'
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
        typeof queued.multiAgentMode === 'boolean' ? queued.multiAgentMode : multiAgentModeEnabled,
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
    updateAgentTeamSnapshot(result, executionId, Number(result.message_id || msgId || 0));
    return;
  }
  if (
    ['tool_preparing', 'tool_start', 'tool'].includes(result?.type) &&
    (isQuestionToolName(result.tool) || !isPrimaryToolEvent(result))
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
    startCompressionActivity(
      {
        ...result,
        compression_id: `legacy:${msgId}`,
        mode: 'manual',
      },
      msgId
    );
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
    markPlanProgressTerminal(executionId, msgId, 'error', result.content || '执行中断');
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
                <button class="btn-approve" type="button">仅本次执行</button>
                <button class="btn-allow-all" type="button">本次任务全部允许</button>
                <button class="btn-deny" type="button">取消</button>
            </div>
        </div>
    `;

  approvalDiv.querySelector('.btn-approve').addEventListener('click', () => approveTool('approve'));
  approvalDiv.querySelector('.btn-allow-all').addEventListener('click', () => approveTool('all'));
  approvalDiv.querySelector('.btn-deny').addEventListener('click', () => approveTool('deny'));

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
    finishCurrentMessage(conversationId, messageId, 'error', `确认失败：${error.message}`);
  }
}

async function rollbackTaskCard(summary) {
  const button = summary?.querySelector?.('.modified-files-rollback');
  if (!button || button.disabled) return;
  const result = summary._modifiedFilesResult || {};
  const conversationId = String(result.conversation_id || activeConversationId || '');
  const messageId = Number(result.message_id || summary.dataset.messageId || 0);
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
    const response =
      typeof eel.rollback_task === 'function'
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
  document.querySelectorAll('.modified-files-summary').forEach((summary) => {
    const button = summary.querySelector('.modified-files-rollback');
    if (!button || button.classList.contains('is-rolled-back')) return;
    const messageId = Number(summary.dataset.messageId || 0);
    const canRollback = Boolean(messageId && available[String(messageId)]);
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
            ${normalizedQuestions
              .map((question, questionIndex) => {
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
                        ${
                          options.length
                            ? `<div class="question-options">
                            ${options
                              .map((option, optionIndex) => {
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
                              })
                              .join('')}
                        </div>`
                            : ''
                        }
                        ${
                          allowFreeText
                            ? `
                            <label class="question-free-text">
                                <span class="question-free-text-label">${escapeHtml(question.freeTextLabel || '补充说明')}<em>${freeTextRequired ? '必填' : '可选'}</em></span>
                                <textarea class="question-free-text-input" rows="2" maxlength="4000" placeholder="${escapeHtml(question.freeTextPlaceholder || '可补充具体要求、名称或未列出的信息')}"${freeTextRequired ? ' required' : ''}></textarea>
                            </label>`
                            : ''
                        }
                    </fieldset>`;
              })
              .join('')}
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
      ? question.options.flatMap((option) => {
          if (typeof option === 'string') {
            const label = option.trim();
            return label ? [{ label, description: '' }] : [];
          }
          if (!option || typeof option !== 'object') return [];
          const label = String(option.label || '').trim();
          if (!label) return [];
          return [
            {
              label,
              description: String(option.description || '').trim(),
            },
          ];
        })
      : [];

    const header = String(question.header || '').trim();
    const questionText = String(question.question || '').trim();
    const wording = `${header} ${questionText} ${options.map((option) => `${option.label} ${option.description}`).join(' ')}`;
    const multiple =
      parseQuestionBoolean(question.multiple) ||
      /(?:可|允许|支持)?\s*(?:多选|多项选择|选择多个|可选多个)/.test(wording);
    const allowFreeText =
      parseQuestionBoolean(question.allow_free_text ?? question.allowFreeText) ||
      /(?:可(?:在)?(?:下方|下面)?(?:文字)?补充|(?:下方|下面)(?:文字)?补充|直接补充文字|自由(?:文本)?(?:填写|输入)|其他(?:说明|内容)?(?:请)?(?:补充|填写))/.test(
        wording
      );
    if (!options.length && !allowFreeText) return [];
    return [
      {
        header: header || `问题 ${questionIndex + 1}`,
        question: questionText || header || `请选择问题 ${questionIndex + 1}`,
        multiple,
        selectionRequired: parseQuestionBoolean(
          question.selection_required ?? question.selectionRequired,
          true
        ),
        allowFreeText,
        freeTextLabel:
          String(question.free_text_label ?? question.freeTextLabel ?? '补充说明').trim() ||
          '补充说明',
        freeTextPlaceholder:
          String(
            question.free_text_placeholder ??
              question.freeTextPlaceholder ??
              '可补充具体要求、名称或未列出的信息'
          ).trim() || '可补充具体要求、名称或未列出的信息',
        freeTextRequired: parseQuestionBoolean(
          question.free_text_required ?? question.freeTextRequired
        ),
        options,
      },
    ];
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
  chatMessages?.querySelectorAll('.thinking-card').forEach((card) => {
    if (card.classList.contains('is-condensed')) {
      card.classList.remove('is-expanded');
      card.querySelector('.thinking-summary')?.setAttribute('aria-expanded', 'false');
    } else {
      const details = card.querySelector('.thinking-details[open]');
      if (details) details.open = false;
    }
    card.classList.add('is-question-collapsed');
  });
}

function collectQuestionResponses(container) {
  return Array.from(container.querySelectorAll('.question-group')).map((group) => ({
    selected: Array.from(group.querySelectorAll('input:checked')).map((input) => input.value),
    supplement: group.querySelector('.question-free-text-input')?.value.trim() || '',
    selectionRequired: group.dataset.selectionRequired !== 'false',
    allowFreeText: group.dataset.allowFreeText === 'true',
    freeTextRequired: group.dataset.freeTextRequired === 'true',
  }));
}

function collectQuestionAnswers(container) {
  return collectQuestionResponses(container).map((response) => response.selected);
}

function validateQuestionPrompt(container) {
  const responses = collectQuestionResponses(container);
  const complete =
    responses.length > 0 &&
    responses.every((response) => {
      if (response.freeTextRequired && !response.supplement) return false;
      return (
        !response.selectionRequired ||
        response.selected.length > 0 ||
        (response.allowFreeText && Boolean(response.supplement))
      );
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
  const answers = responses.map((response) => response.selected);
  const supplements = responses.map((response) => response.supplement);
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
    const result = await eel.answer_question(answers, supplements, conversationId, messageId)();
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
  return Array.from(container.querySelectorAll('.question-group')).map((group) => ({
    header: group.querySelector('.question-header-label')?.textContent || '',
    question: group.querySelector('legend strong')?.textContent || '',
    freeTextLabel:
      group.querySelector('.question-free-text-label')?.childNodes[0]?.textContent?.trim() ||
      '补充说明',
  }));
}

function finalizePendingQuestion(label) {
  const container = document.querySelector('.question-prompt:not(.is-submitted)');
  if (!container) return;
  container.classList.add('is-submitted');
  container.classList.remove('is-active-question');
  container.querySelectorAll('input, textarea').forEach((input) => (input.disabled = true));
  const submit = container.querySelector('.question-submit');
  if (submit) {
    submit.disabled = true;
    submit.textContent = label;
  }
}

function renderQuestionResult(
  questions,
  answers,
  msgId,
  questionId = '',
  prompt = null,
  supplements = []
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
                ${questions
                  .map(
                    (question, index) => `
                    <div class="question-result-item">
                        <span>${escapeHtml(question.header || question.question || `问题 ${index + 1}`)}</span>
                        <strong>${escapeHtml((answers[index] || []).join('、') || (supplements[index] ? '已补充文字' : '未选择'))}</strong>
                        ${supplements[index] ? `<em>${escapeHtml(`${question.freeTextLabel || question.free_text_label || '补充说明'}：${supplements[index]}`)}</em>` : ''}
                    </div>`
                  )
                  .join('')}
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
    hour12: false,
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
  list.innerHTML = attachments
    .map((item) =>
      renderMessageAttachment({
        ...item,
        success: Object.prototype.hasOwnProperty.call(item, 'success') ? item.success : null,
      })
    )
    .join('');
  wrapper.insertBefore(list, wrapper.firstChild);
  if (!animate) {
    hydrateConversationAttachmentPreviews(activeConversationId, list);
  }
  return message;
}

function renderMessageAttachment(item) {
  const isImage =
    isImageAttachment(item) || item.parse_mode === 'vision' || item.parse_mode === 'image_view';
  const isDirectory = isDirectoryReference(item);
  const imageStatus = item.parse_mode === 'image_view' ? '图片已保存' : '已发送给视觉模型';
  const status =
    item.success === true
      ? isDirectory
        ? '参考目录已加入'
        : isImage
          ? imageStatus
          : '已解析'
      : item.success === false
        ? isDirectory
          ? '参考目录不可用'
          : isImage
            ? '图片保存失败'
            : '解析失败'
        : isDirectory
          ? '正在定位目录'
          : isImage
            ? '正在保存图片'
            : '正在解析';
  const statusClass =
    item.success === true ? 'is-ready' : item.success === false ? 'has-error' : 'is-parsing';
  const assetAttribute = item.asset_id ? ` data-asset-id="${escapeHtml(item.asset_id)}"` : '';
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
  await Promise.all(
    cards.map(async (card) => {
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
    })
  );
}

function updateMessageAttachments(messageId, attachments) {
  const message = document.querySelector(`.message.user[data-message-id="${messageId}"]`);
  const list = message?.querySelector('.message-attachments');
  if (!list) return;
  const localAttachments = new Map(
    Array.from(list.querySelectorAll('.message-attachment')).map((element) => [
      element.dataset.attachmentName || '',
      element.querySelector('.message-attachment-icon img')?.src || '',
    ])
  );
  list.innerHTML = attachments
    .map((item) => {
      const preview = localAttachments.get(String(item.name || ''));
      return renderMessageAttachment({
        ...item,
        data: item.data || preview || '',
      });
    })
    .join('');
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
  flushVoiceStreamingResponse(state, { final: true });
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
    '',
    state.element,
    false,
    true,
    false,
    null,
    state.host || null
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
  if (
    state.thinkingCard?.parentNode === chatMessages &&
    state.element?.parentNode === chatMessages &&
    state.thinkingCard.nextSibling !== state.element
  ) {
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

function flushVoiceStreamingResponse(state, { final = false } = {}) {
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
    return {
      waitingForMarker: true,
      hasThinking: false,
      thinking: '',
      thinkingComplete: false,
      answer: '',
    };
  }

  const open = source.match(/<think\b[^>]*>/i);
  if (!open) {
    return {
      waitingForMarker: false,
      hasThinking: false,
      thinking: '',
      thinkingComplete: false,
      answer: source,
    };
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
    flushVoiceStreamingResponse(state, { final: true });
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
  if (!isCommentary) flushVoiceStreamingResponse(state, { final: true });
  let thinkingCards = [];
  if (state?.thinkingCard) {
    const thought = thoughts[thoughts.length - 1] || '';
    if (thought) state.thinkingBody.innerHTML = renderMarkdown(thought);
    completeStreamingThinking(state);
    condenseThinkingCard(state.thinkingCard);
    thinkingCards = [state.thinkingCard];
  } else {
    thinkingCards = thoughts.map((thought) =>
      addThinkingCard(thought, state?.element, true, true, true)
    );
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
      ? commentary
        ? addCommentaryMessage(commentary)
        : null
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
      state.conversationId || activeConversationId,
      false
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
      const { answer } = splitThinkingContent(state.content || '');
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
    .map((item) =>
      String(item || '')
        .replace(/^接下来我要\s*[:：]\s*/, '')
        .trim()
    )
    .filter(Boolean)
    .forEach((item) => addThinkingCard(item, null, true, true, true, durationMs));
}

function addAssistantResponse(content, thinkingDurationMs = null) {
  const { thoughts, answer } = splitThinkingContent(content);
  const cards = thoughts.map((thought) =>
    addThinkingCard(thought, null, true, true, true, thinkingDurationMs)
  );

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
  answer = answer
    .replace(/<think\b[^>]*>([\s\S]*)$/i, (_, thought) => {
      const normalized = String(thought || '').trim();
      if (normalized) thoughts.push(normalized);
      return '';
    })
    .replace(/<\/?think\b[^>]*>/gi, '');

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
  const padding =
    (parseFloat(computed.paddingTop) || 0) + (parseFloat(computed.paddingBottom) || 0);
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
  summary.addEventListener('click', (event) => {
    if (!card.classList.contains('is-condensed')) return;
    event.preventDefault();
    details.open = true;
    if (!card.classList.contains('is-expanded')) {
      card.style.setProperty('--thinking-full-height', `${Math.ceil(content.scrollHeight)}px`);
    }
    card.classList.toggle('is-expanded');
    summary.setAttribute(
      'aria-expanded',
      card.classList.contains('is-expanded') ? 'true' : 'false'
    );
  });
  content.addEventListener('click', (event) => {
    if (
      !card.classList.contains('is-condensed') ||
      card.classList.contains('is-expanded') ||
      event.target.closest('a, button, input, textarea, select')
    ) {
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
    result.prepared_tool_call_id || result.tool_call_id || `${msgId}:${result.tool || 'tool'}`
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
    return path && query ? `${path} · ${query}` : query || path;
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
  // ShellTool 的 ✓ Success 状态行是权威成功结果：正文里的
  // "No such file or directory" 等文本（删除后验证输出）不构成失败。
  if (/^✓\s*success/i.test(text)) return false;
  if (/^(?:error|failed|failure|fatal):/i.test(text)) return true;
  if (/^✗/.test(text)) return true;
  if (/^(?:错误|失败)[：:]|^执行失败|^(?:unable to|error occurred)|^无法/.test(text)) return true;
  // 只依据状态行/前缀判定：ShellTool 失败一定以 ✗ Failed 开头，
  // 工具错误以 Error: 等前缀开头；正文里的内嵌文本不再参与判定。
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
    existing.target =
      getToolTarget(toolName, result.params || {}, result.target) || existing.target || '';
    const summary = existing.element.querySelector('.tool-live-summary');
    if (summary) {
      summary.textContent = primaryToolSummary(existing.progressCopy, existing.target);
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
  const startedAt = backendStartedAt > 0 ? Math.min(Date.now(), backendStartedAt) : Date.now();
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
    const match = Array.from(activeToolExecutions.entries()).find(
      ([, item]) =>
        item.toolName === String(result.tool || '') &&
        Number(item.messageId || 0) === Number(msgId || 0) &&
        (!resultStreamId || item.streamId === resultStreamId)
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
  const target =
    getToolTarget(result.tool, result.params || {}, result.target) || execution.target || '';
  toolDiv.classList.remove('tool-execution-running');
  toolDiv.classList.add(failed ? 'tool-execution-error' : 'tool-execution-complete');
  toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(result.tool || 'Tool')}</span>
                <span class="tool-summary">${escapeHtml(
                  primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'} · ${formatToolDuration(duration)}`,
                    target
                  )
                )}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result.result || '').substring(0, 1600))}</div>
        </details>`;
}

function finishActiveToolExecutions(label = '执行已停止', isError = false) {
  activeToolExecutions.forEach((execution) => {
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
  activeToolExecutions.forEach((execution) => {
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

function startCompressionActivity(result, msgId, animate = true, announceStatus = true) {
  const chatMessages = getChatRenderHost();
  const key = getCompressionKey(result, msgId);
  const existing = activeCompressionActivities.get(key);
  if (existing) return existing.element;

  const mode = result.mode === 'auto' ? 'auto' : 'manual';
  const backendStartedAt = Number(result.started_at_ms || 0);
  const startedAt = backendStartedAt > 0 ? Math.min(Date.now(), backendStartedAt) : Date.now();
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
    setAppStatus('busy', mode === 'auto' ? '正在自动压缩记忆' : '正在压缩记忆');
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
    startCompressionActivity(result, msgId, !isRestoringConversation, !isRestoringConversation);
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
  const released = Math.max(0, Number(result.released_tokens ?? tokensBefore - tokensAfter));
  const durationMs = Math.max(0, Number(result.duration_ms || Date.now() - state.startedAt));
  const archivePath = String(result.archive_path || '');
  const title = success ? '记忆压缩完成' : isEmpty ? '没有可压缩的近期记忆' : '记忆压缩失败';
  const tokenSummary =
    tokensBefore > 0
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
    finishCompressionActivity(
      {
        compression_id: key,
        mode: state.mode,
        success: false,
        status: 'error',
        message,
        tokens_before: state.tokensBefore,
        tokens_after: state.tokensBefore,
        released_tokens: 0,
        duration_ms: Date.now() - state.startedAt,
      },
      currentMessageId
    );
  });
}

function clearCompressionActivities() {
  activeCompressionActivities.forEach((state) => {
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
    execution.element.addEventListener('transitionend', remove, { once: true });
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
  if (isQuestionToolName(toolName) || !isPrimaryToolEvent({ actor })) return null;
  const chatMessages = getChatRenderHost();
  const toolDiv = document.createElement('div');
  const failed = toolResultFailed(result);
  toolDiv.className = `tool-execution ${failed ? 'tool-execution-error' : ''}`;
  toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(toolName)}</span>
                <span class="tool-summary">${escapeHtml(
                  primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'}${durationMs > 0 ? ` · ${formatToolDuration(durationMs)}` : ''}`,
                    target
                  )
                )}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result).substring(0, 1600))}</div>
        </details>
    `;
  chatMessages.appendChild(toolDiv);
  if (animate) requestAnimationFrame(() => toolDiv.classList.add('is-visible'));
  else toolDiv.classList.add('is-visible');
  if (!isRestoringConversation) followChatOutput(chatMessages);
  return toolDiv;
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
  const status = String(value || '')
    .trim()
    .toLowerCase();
  if (['ready', 'running', 'active', 'healthy', 'started'].includes(status)) return 'ready';
  if (['stopping', 'stopped', 'closed', 'exited', 'terminated'].includes(status)) return 'stopped';
  if (['error', 'failed', 'timeout', 'unhealthy'].includes(status)) return 'error';
  if (['starting', 'pending', 'launching', 'booting'].includes(status)) return 'starting';
  return hasUrl ? 'ready' : 'starting';
}

function normalizePreviewSession(raw) {
  const source =
    raw?.preview && typeof raw.preview === 'object' ? { ...raw, ...raw.preview } : raw || {};
  const previewId = String(source.preview_id || source.id || '').trim();
  if (!previewId) return null;

  const existing = previewSessions.get(previewId) || {};
  const hasSuppliedUrl = Object.prototype.hasOwnProperty.call(source, 'url');
  const suppliedUrl = hasSuppliedUrl ? String(source.url || '').trim() : '';
  const candidateUrl = suppliedUrl
    ? normalizeLocalPreviewUrl(suppliedUrl)
    : hasSuppliedUrl
      ? ''
      : existing.url || '';
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
  if (
    session.conversationId &&
    activeConversationId &&
    session.conversationId !== String(activeConversationId)
  ) {
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
  const activeSessions = [...previewSessions.values()].filter(
    (session) => session.status === 'starting' || session.status === 'ready'
  );
  if (!activeSessions.length) {
    dock.classList.remove('is-visible');
    dock.setAttribute('aria-hidden', 'true');
    return;
  }
  dock.classList.add('is-visible');
  dock.setAttribute('aria-hidden', 'false');
  const existing = new Map(
    [...dock.querySelectorAll('.preview-dock-pill')].map((pill) => [
      String(pill.dataset.previewId || ''),
      pill,
    ])
  );
  const fragment = document.createDocumentFragment();
  activeSessions.forEach((session) => {
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
      pill.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openBrowserPreview(String(pill.dataset.previewId || ''));
        }
      });
      pill.querySelector('.preview-dock-stop')?.addEventListener('click', (event) => {
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
      ? session.port
        ? `:${session.port}`
        : '运行中'
      : copy.label;
    pill.title = `${session.name} · ${copy.detail}`;
    fragment.appendChild(pill);
    existing.delete(session.previewId);
  });
  existing.forEach((pill) => pill.remove());
  dock.replaceChildren(fragment);
}

async function syncPreviewSessions(conversationId) {
  if (!conversationId || !canCallEel() || typeof eel.get_preview_sessions !== 'function') return;
  const generation = ++previewSyncGeneration;
  try {
    const result = await eel.get_preview_sessions(conversationId)();
    if (
      generation !== previewSyncGeneration ||
      String(conversationId) !== String(activeConversationId || '')
    )
      return;
    const rawSessions = Array.isArray(result) ? result : result?.sessions || result?.previews || [];
    if (result && !Array.isArray(result) && result.success === false) {
      throw new Error(result.error || '预览状态同步失败');
    }
    const sessions = Array.isArray(rawSessions) ? rawSessions : [];
    sessions.forEach((session) =>
      upsertProjectPreview(
        {
          ...session,
          conversation_id: session.conversation_id || conversationId,
        },
        false
      )
    );
    // Reconcile with the backend: a preview that stopped on its own, or
    // whose owning manager was recreated without a delivered event, is
    // absent from the snapshot and must leave the floating dock.
    const reported = new Set(
      sessions
        .map((session) => String(session.preview_id || session.id || '').trim())
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
    if (base.origin === target.origin) return { session, url };
  }
  return null;
}

function setBrowserPreviewLoading(title = '正在连接本地预览', detail = '') {
  const state = document.getElementById('browserPreviewState');
  if (!state) return;
  state.classList.add('is-visible', 'is-loading');
  state.classList.remove('is-error');
  document.getElementById('browserPreviewStateTitle').textContent = title;
  document.getElementById('browserPreviewStateDetail').textContent =
    detail || '正在等待页面完成加载';
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
  if (
    !session ||
    session.status !== 'ready' ||
    typeof eel === 'undefined' ||
    typeof eel.open_preview_external !== 'function'
  )
    return;
  try {
    const result = await eel.open_preview_external(previewId, activeConversationId || '')();
    if (result?.success === false) throw new Error(result.error || '打开失败');
  } catch (error) {
    showToast(`外部打开失败：${error.message}`, 'error');
  }
}

async function stopPreviewSession(previewId) {
  const session = previewSessions.get(String(previewId || ''));
  if (
    !session ||
    ['stopped', 'error'].includes(session.status) ||
    typeof eel === 'undefined' ||
    typeof eel.stop_project_preview !== 'function'
  )
    return;
  try {
    const result = await eel.stop_project_preview(previewId, activeConversationId || '')();
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
      blocks.push(
        `<pre class="markdown-code"><code${language}>${escapeHtml(code.join('\n'))}</code></pre>`
      );
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
      blocks.push(`<${tag}>${items.map((item) => `<li>${item}</li>`).join('')}</${tag}>`);
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
  return (
    /^\s*```/.test(line) ||
    /^\s*#{1,6}\s+/.test(line) ||
    /^\s*>\s?/.test(line) ||
    /^\s*([-+*]|\d+[.)])\s+/.test(line) ||
    /^\s*((-{3,})|(\*{3,})|(_{3,}))\s*$/.test(line) ||
    isMarkdownTable(lines, index)
  );
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
      (_, label, bracketedUrl, plainUrl) =>
        protectMarkup(renderMarkdownMedia(label, bracketedUrl || plainUrl))
    )
    .replace(/\[([^\]]+)\]\(([^\s)]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_, label, url) =>
      protectMarkup(renderSafeLink(label, url))
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
  const source = String(escapedUrl || '')
    .replace(/&amp;/g, '&')
    .trim();
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
  if (/^[a-z][a-z0-9+.-]*:/i.test(source) && !/^file:\/\//i.test(source)) return '';

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
  const source = String(escapedUrl || '')
    .replace(/&amp;/g, '&')
    .trim();
  const videoPrefix = /^(?:video|视频)\s*[:：]\s*/i;
  const isVideo =
    videoPrefix.test(String(escapedLabel || '')) ||
    /\.(?:m4v|mov|mp4|ogv|webm)(?:[?#]|$)/i.test(source);
  const label = String(escapedLabel || '')
    .replace(videoPrefix, '')
    .trim();
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
    document.getElementById('imageLightboxClose')?.focus({ preventScroll: true });
  });
}

function closeImageLightbox({ restoreFocus = true } = {}) {
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
    imageLightboxLastFocusedElement.focus({ preventScroll: true });
  }
  imageLightboxLastFocusedElement = null;
}

function openImagePreviewFromTrigger(trigger) {
  const image = trigger?.matches?.('img') ? trigger : trigger?.querySelector?.('img');
  const source = image?.currentSrc || image?.src || '';
  if (!source) return;
  const label =
    image.alt ||
    trigger.dataset?.attachmentName ||
    trigger.querySelector?.('strong')?.textContent ||
    '';
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
  return separators.length > 0 && separators.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
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
  const headerCells = header
    .map(
      (cell, index) =>
        `<th style="text-align:${alignments[index] || 'left'}">${renderInlineMarkdown(cell)}</th>`
    )
    .join('');
  const bodyRows = rows
    .map((row) => {
      const cells = header
        .map(
          (_, index) =>
            `<td style="text-align:${alignments[index] || 'left'}">${renderInlineMarkdown(row[index] || '')}</td>`
        )
        .join('');
      return `<tr>${cells}</tr>`;
    })
    .join('');
  return `<div class="markdown-table-wrap"><table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
}

function showError(message) {
  const welcomeMsg = document.querySelector('.welcome-message');
  if (welcomeMsg) welcomeMsg.style.display = 'none';
  addMessage('ai', message, true);
}
