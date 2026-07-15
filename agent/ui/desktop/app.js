// 麒麟OS-Agent Desktop UI - Frontend Logic

let isInitialized = false;
let isProcessing = false;
let currentMessageId = 0;
let messageQueue = [];
let pendingKnowledgeByMessageId = new Map();
let completedMessageByMessageId = new Map();
let streamingResponses = new Map();
let composerAttachments = [];
let currentSettingsSnapshot = null;
let showKnowledgeAppendix = true;
let autoAllowAll = localStorage.getItem('minibot-auto-allow-all') === 'true';
let refreshInFlight = false;
let tokenRefreshInFlight = false;
let statusRefreshInFlight = false;
let lastFocusedElement = null;
let activeConversationId = null;
let conversations = [];
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
const activePlanProgress = new Map();

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

function applyTheme(theme) {
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
            running: false,
            stopping: false,
            outputStopped: false,
            awaitingQuestion: false,
            awaitingApproval: false,
            unreadCompletion: false,
            streamContents: new Map(),
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
    const validStatuses = new Set(['pending', 'in_progress', 'completed']);
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

    const completed = planState.plan.filter(item => item.status === 'completed').length;
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
        appendStreamingResponse(streamId, content);
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
            state.running = true;
            state.stopping = Boolean(item.stopping);
            state.awaitingQuestion = Boolean(item.awaiting_question);
            state.awaitingApproval = Boolean(item.awaiting_approval);
            if (backendMessageId) state.messageId = backendMessageId;
        } else if (state.running) {
            state.running = false;
            state.stopping = false;
            state.outputStopped = false;
            state.awaitingQuestion = false;
            state.awaitingApproval = false;
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
    const targetId = String(conversationId || '');
    messageQueue = targetId
        ? messageQueue.filter(item => (
            typeof item !== 'object'
            || String(item.conversationId || '') !== targetId
        ))
        : [];
    updateQueueDisplay();
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
    const preview = getImagePreview(item);
    if (preview) {
        return `<span class="${className} is-image" aria-hidden="true"><img src="${escapeHtml(preview)}" alt=""></span>`;
    }
    if (isImageAttachment(item) || item?.parse_mode === 'vision') {
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
    container.innerHTML = composerAttachments.map(item => `
        <div class="composer-attachment ${item.status === 'error' ? 'has-error' : ''}">
            ${renderAttachmentVisual(item, 'composer-attachment-icon')}
            <span class="composer-attachment-copy">
                <strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong>
                <small>${item.status === 'parsing' ? '正在解析' : item.status === 'error' ? escapeHtml(item.error || '解析失败') : isImageAttachment(item) ? `等待发送给视觉模型 · ${formatAttachmentSize(item.size)}` : formatAttachmentSize(item.size)}</small>
            </span>
            <button type="button" class="composer-attachment-remove" onclick="removeComposerAttachment('${item.id}')" aria-label="移除 ${escapeHtml(item.name)}">×</button>
        </div>
    `).join('');
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

function hasDraggedFiles(dataTransfer) {
    return Array.from(dataTransfer?.types || []).includes('Files');
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

    if (messageQueue.length === 0) {
        queueEl.style.display = 'none';
        return;
    }

    queueEl.style.display = 'block';
    queueCount.textContent = messageQueue.length;

    queueList.innerHTML = messageQueue.map((item, idx) => {
        const message = typeof item === 'string' ? item : item.message;
        const attachmentCount = typeof item === 'string' ? 0 : (item.attachments || []).length;
        const conversationId = typeof item === 'string' ? '' : String(item.conversationId || '');
        const taskTitle = conversations.find(entry => String(entry.id) === conversationId)?.title;
        const label = `${taskTitle ? `${taskTitle} · ` : ''}${message || '解析附件'}${attachmentCount ? ` · ${attachmentCount} 个附件` : ''}`;
        return `
        <div class="queue-item">
            <span class="queue-item-number">${idx + 1}.</span>
            <span class="queue-item-text" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
            <button class="queue-item-remove" onclick="removeFromQueue(${idx})" aria-label="移除第 ${idx + 1} 个等待任务">✕</button>
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
    initializeUI();
    initializeOSAgent();
    refreshAllWorkspace();
    refreshSkills();
    updateTokenIndicator();
    updateEmbeddingStatus();
    setInterval(() => {
        if (!document.hidden) refreshAllWorkspace();
    }, 5000);
    setInterval(() => {
        if (!document.hidden) updateTokenIndicator();
    }, 4000);
    setInterval(() => {
        if (!document.hidden) updateEmbeddingStatus();
    }, 12000);
    setInterval(() => {
        if (!document.hidden && activeConversationId) {
            syncPreviewSessions(activeConversationId);
        }
    }, 4000);
    setInterval(() => {
        if (!document.hidden && !refreshInFlight) {
            refreshConversations(activeConversationId).catch(error => {
                console.error('Failed to sync task activity:', error);
            });
        }
    }, 1800);
}

document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    init();
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
    const modelBadge = document.getElementById('modelBadge');
    const inputAddButton = document.getElementById('inputAddButton');
    const attachmentInput = document.getElementById('attachmentInput');
    const clearQueueButton = document.getElementById('clearQueueButton');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const newTaskButton = document.getElementById('newTaskButton');
    const planProgress = document.getElementById('planProgress');
    const planProgressTrigger = document.getElementById('planProgressTrigger');
    const inputContainer = messageInput.closest('.input-container');
    const chatMessages = document.getElementById('chatMessages');
    const previewFrame = document.getElementById('browserPreviewFrame');
    let composerDragDepth = 0;

    applyAccessToggleState(autoAllowAll);
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
    if (modelBadge) {
        modelBadge.addEventListener('click', openSettings);
    }
    if (inputAddButton) {
        inputAddButton.addEventListener('click', () => {
            attachmentInput?.click();
        });
    }
    attachmentInput?.addEventListener('change', async () => {
        await addComposerAttachments(Array.from(attachmentInput.files || []));
        attachmentInput.value = '';
        messageInput.focus();
    });
    inputContainer?.addEventListener('dragenter', (event) => {
        if (!hasDraggedFiles(event.dataTransfer)) return;
        event.preventDefault();
        composerDragDepth += 1;
        inputContainer.classList.add('is-dragging-files');
    });
    inputContainer?.addEventListener('dragover', (event) => {
        if (!hasDraggedFiles(event.dataTransfer)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        inputContainer.classList.add('is-dragging-files');
    });
    inputContainer?.addEventListener('dragleave', (event) => {
        if (!hasDraggedFiles(event.dataTransfer)) return;
        composerDragDepth = Math.max(0, composerDragDepth - 1);
        if (composerDragDepth === 0) inputContainer.classList.remove('is-dragging-files');
    });
    inputContainer?.addEventListener('drop', async (event) => {
        if (!hasDraggedFiles(event.dataTransfer)) return;
        event.preventDefault();
        composerDragDepth = 0;
        inputContainer.classList.remove('is-dragging-files');
        await addComposerAttachments(getDroppedFiles(event.dataTransfer));
        messageInput.focus();
    });
    clearQueueButton?.addEventListener('click', clearMessageQueue);
    sidebarToggle?.addEventListener('click', () => {
        document.body.classList.toggle('sidebar-open');
        sidebarToggle.setAttribute(
            'aria-expanded',
            document.body.classList.contains('sidebar-open') ? 'true' : 'false'
        );
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
    newTaskButton?.addEventListener('click', createNewConversation);
    chatMessages?.addEventListener('click', handlePreviewLinkClick);
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
    document.querySelectorAll('.sidebar-footer .btn-settings').forEach((button) => {
        button.addEventListener('click', closeMobileSidebar);
    });

    // Stop button - also clears pending message
    const stopButton = document.getElementById('stopButton');
    stopButton.addEventListener('click', async () => {
        const state = getActiveExecutionState();
        if (!isProcessing || !state?.running) return;

        const conversationId = state.conversationId;
        const messageId = Number(state.messageId || currentMessageId || 0);
        state.running = false;
        state.stopping = false;
        state.outputStopped = false;
        state.awaitingQuestion = false;
        state.awaitingApproval = false;
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
            markPlanProgressTerminal(
                conversationId, messageId, 'stopped', '任务已停止'
            );
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
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closePlanProgress();
    });
}

function fillComposer(value) {
    const messageInput = document.getElementById('messageInput');
    messageInput.value = value;
    messageInput.dispatchEvent(new Event('input', {bubbles: true}));
    messageInput.focus();
}

function hideWelcome() {
    const welcome = document.querySelector('.welcome-message');
    const chatMessages = document.getElementById('chatMessages');
    chatMessages?.classList.remove('is-welcome');
    if (chatMessages) chatMessages.scrollTop = 0;
    if (!welcome) return;
    welcome.classList.add('is-leaving');
    setTimeout(() => welcome.remove(), 260);
}

function closeMobileSidebar() {
    document.body.classList.remove('sidebar-open');
    document.getElementById('sidebarToggle')?.setAttribute('aria-expanded', 'false');
}

function welcomeMarkup() {
    return `
        <div class="welcome-message">
            <div class="welcome-mark" aria-hidden="true">
                <img class="theme-asset-mark" src="${THEME_ASSETS[getCurrentTheme()].mark}" alt="">
                <span class="welcome-mark-glow"></span>
            </div>
            <div class="welcome-kicker">Kylin Agent Workspace</div>
            <h2>今天想完成什么？</h2>
            <p>描述目标，麒麟 OS-Agent 会规划步骤、调用工具并持续汇报进度。</p>
            <div class="quick-actions">
                <button class="quick-action" data-prompt="扫描当前项目并给出最值得优先修复的问题">
                    <span class="quick-action-copy"><strong>扫描当前项目</strong><small>发现风险与优化机会</small></span><span class="quick-action-arrow">↗</span>
                </button>
                <button class="quick-action" data-prompt="整理工作区文件并生成一份结构说明">
                    <span class="quick-action-copy"><strong>整理工作区</strong><small>归类文件并生成说明</small></span><span class="quick-action-arrow">↗</span>
                </button>
                <button class="quick-action" data-prompt="查看当前偏好、知识库和向量引擎状态">
                    <span class="quick-action-copy"><strong>查看记忆状态</strong><small>偏好、知识与向量引擎</small></span><span class="quick-action-arrow">↗</span>
                </button>
            </div>
        </div>`;
}

function bindQuickActions() {
    document.querySelectorAll('.quick-action').forEach(button => {
        button.addEventListener('click', () => fillComposer(button.dataset.prompt || ''));
    });
}

function resetConversationView() {
    closeBrowserPreview(false);
    previewSessions.clear();
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
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.classList.add('is-welcome');
    chatMessages.innerHTML = welcomeMarkup();
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
    if (!list) return;
    if (!conversations.length) {
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

    conversations.forEach((item, index) => {
        const conversationId = String(item.id || '');
        const execution = getConversationExecutionState(item.id, false);
        const running = Boolean(item.running || execution?.running);
        const unread = !running && Boolean(
            item.unread_completion || execution?.unreadCompletion
        );
        const stateLabel = running ? '正在执行' : unread ? '执行完成，尚未查看' : '';

        const row = existingRows.get(conversationId)
            || createTaskHistoryItem(conversationId);
        row.dataset.conversationId = conversationId;
        row.classList.toggle('is-active', conversationId === activeConversationId);
        row.classList.toggle('is-running', running);
        row.classList.toggle('has-unread-completion', unread);

        const main = row.querySelector('.task-history-main');
        const dot = row.querySelector('.task-history-state-dot');
        const name = row.querySelector('.task-history-name');
        const date = row.querySelector('.task-history-date');
        const title = String(item.title || '新任务');
        const dateText = formatConversationDate(item.updated_at);

        if (main.title !== title) main.title = title;
        if (name.textContent !== title) name.textContent = title;
        if (date.textContent !== dateText) date.textContent = dateText;
        if (dot.hidden === Boolean(stateLabel)) dot.hidden = !stateLabel;
        if (stateLabel) {
            if (dot.getAttribute('aria-label') !== stateLabel) {
                dot.setAttribute('aria-label', stateLabel);
            }
            if (dot.title !== stateLabel) dot.title = stateLabel;
        } else {
            dot.removeAttribute('aria-label');
            dot.removeAttribute('title');
        }

        const currentAtIndex = list.children[index];
        if (currentAtIndex !== row) {
            list.insertBefore(row, currentAtIndex || null);
        }
        existingRows.delete(conversationId);
    });

    existingRows.forEach(row => row.remove());
}

function updateActiveTaskTitle(title) {
    const element = document.getElementById('activeTaskTitle');
    if (element) element.textContent = title || '新任务';
}

async function refreshConversations(preferredId = null) {
    const generation = ++conversationRefreshGeneration;
    const result = await eel.list_conversations()();
    if (!result?.success) throw new Error(result?.error || '任务列表加载失败');
    if (generation !== conversationRefreshGeneration) return activeConversationId;
    conversations = result.conversations || [];
    syncExecutionStatesFromConversations(conversations);
    activeConversationId = preferredId || result.active_id || conversations[0]?.id || null;
    const active = conversations.find(item => item.id === activeConversationId);
    if (active) updateActiveTaskTitle(active.title);
    renderConversationList();
    conversationExecutionStates.forEach(state => {
        if (state.running && state.messageId) {
            ensureExecutionPolling(state.conversationId, state.messageId);
        }
    });
    syncActiveConversationProcessingUI();
    return activeConversationId;
}

async function createNewConversation() {
    try {
        const result = await eel.create_conversation('新任务')();
        if (!result?.success) throw new Error(result?.error || '创建失败');
        activeConversationId = result.conversation.id;
        markConversationReadLocally(activeConversationId);
        resetConversationView();
        updateActiveTaskTitle(result.conversation.title);
        await refreshConversations(activeConversationId);
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
        conversationRefreshGeneration += 1;
        const result = await eel.set_active_conversation(conversationId)();
        if (!result?.success) throw new Error(result?.error || '切换失败');
        activeConversationId = conversationId;
        markConversationReadLocally(conversationId);
        renderConversation(result.conversation);
        const execution = getConversationExecutionState(conversationId, false);
        if (execution?.running) execution.liveRenderSuppressed = false;
        await refreshConversations(conversationId);
        markConversationReadLocally(conversationId);
        renderConversationList();
        syncActiveConversationProcessingUI({showPlaceholder: true});
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
        <button type="button" data-action="delete" class="is-danger">删除任务</button>`;
    document.body.appendChild(menu);
    const rect = event.currentTarget.getBoundingClientRect();
    menu.style.left = `${Math.min(rect.left, window.innerWidth - 142)}px`;
    menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - 92)}px`;
    menu.querySelector('[data-action="rename"]').onclick = async () => {
        menu.remove();
        const title = await showInputDialog('重命名任务', item.title || '新任务');
        if (!title) return;
        const result = await eel.rename_conversation(conversationId, title)();
        if (!result?.success) return showToast(result?.error || '重命名失败', 'error');
        if (conversationId === activeConversationId) updateActiveTaskTitle(result.conversation.title);
        await refreshConversations(activeConversationId);
    };
    menu.querySelector('[data-action="delete"]').onclick = async () => {
        menu.remove();
        if (isConversationRunning(conversationId)) {
            return showToast('正在执行的任务请先停止后再删除', 'info');
        }
        const confirmed = await showConfirmDialog(`删除任务“${item.title}”？此操作不可撤销。`);
        if (!confirmed) return;
        const result = await eel.delete_conversation(conversationId)();
        if (!result?.success) return showToast(result?.error || '删除失败', 'error');
        conversationExecutionStates.delete(String(conversationId));
        clearConversationPlanProgress(conversationId);
        await refreshConversations(result.active_id);
        const loaded = await eel.load_conversation(result.active_id)();
        if (loaded?.success) renderConversation(loaded.conversation);
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
    if (!badge || !label || typeof eel === 'undefined' || statusRefreshInFlight) return;

    statusRefreshInFlight = true;
    try {
        const status = await eel.get_embedding_status()();
        const provider = status.provider || 'unknown';
        const dimension = status.dimension || 0;
        const isKylin = provider === 'kylin-coreai-embedding';
        const isFallback = provider === 'hash-fallback';

        badge.classList.toggle('sdk-active', isKylin);
        badge.classList.toggle('sdk-fallback', isFallback);
        badge.classList.toggle('sdk-error', !isKylin && !isFallback);
        label.textContent = isKylin
            ? `麒麟 SDK ${dimension || ''}D`
            : isFallback
                ? `Hash 降级 ${dimension || ''}D`
                : '向量引擎未知';
        badge.title = status.fallback_reason || status.error || `当前向量引擎：${provider}`;
    } catch (e) {
        badge.classList.add('sdk-error');
        label.textContent = '向量引擎异常';
        badge.title = e.message || '无法获取向量引擎状态';
    } finally {
        statusRefreshInFlight = false;
    }
}

async function initializeOSAgent() {
    try {
        const result = await eel.initialize()();

        if (result[0]) {
            isInitialized = true;
            const settings = await eel.load_settings()();
            showKnowledgeAppendix = String(
                settings.show_knowledge_appendix ?? 'true'
            ).toLowerCase() === 'true';
            const conversationId = await refreshConversations();
            if (conversationId) {
                const loaded = await eel.set_active_conversation(conversationId)();
                if (loaded?.success) {
                    renderConversation(loaded.conversation);
                } else {
                    const current = await eel.load_conversation(conversationId)();
                    if (current?.success) renderConversation(current.conversation);
                }
            }
            await restoreExecutionState();
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
        const messages = conversation?.messages || [];
        resetConversationView();
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
        const finalByMessageId = new Map();
        const pendingKnowledge = new Map();
        for (const event of messages) {
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
            } else if (event.type === 'tool') {
                addToolMessage(
                    event.tool || 'Tool',
                    event.content || '',
                    false,
                    Number(event.duration_ms || 0)
                );
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
                    conversation_id: event.conversation_id || conversation?.id || '',
                }, false);
            } else if (event.type === 'plan_update') {
                continue;
            } else if (event.type === 'knowledge' && showKnowledgeAppendix) {
                const anchor = finalByMessageId.get(messageId);
                if (anchor) addKnowledgePanel(event.content || '', anchor);
                else pendingKnowledge.set(messageId, event.content || '');
            }
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } finally {
        isRestoringConversation = false;
        renderConversationList();
        syncPreviewSessions(activeConversationId);
        // Historical compression cards must never leave the global activity
        // indicator in a running state after a task switch or reload.
        syncActiveConversationProcessingUI();
        if (!isProcessing && isInitialized) setAppStatus('ready', '就绪');
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

    if (!message && !attachments.length) return;
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
        });
        messageInput.value = '';
        resetComposerInput(messageInput);
        clearComposerAttachments();
        updateQueueDisplay();
        showToast(
            activeState.outputStopped
                ? '已停止输出，新消息将在后台释放后立即发送'
                : `当前任务的新消息已进入等待队列（${messageQueue.length}）`,
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
            conversationId
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
async function sendMessageWithText(message, attachments = [], conversationId = activeConversationId) {
    if (!isInitialized || (!message && !attachments.length)) return;

    // 生成新的消息ID
    const targetConversationId = String(conversationId || activeConversationId || '');
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
            targetConversationId
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

            const state = updateConversationExecutionState(executionId, {
                messageId,
                running: Boolean(status?.running),
                stopping: Boolean(status?.stopping),
                awaitingApproval: Boolean(status?.awaiting_approval),
                awaitingQuestion: Boolean(status?.awaiting_question),
            });
            updateConversationListItemState(executionId, {
                running: Boolean(status?.running),
                stopping: Boolean(status?.stopping),
                active_message_id: status?.running ? messageId : 0,
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
                if (lateResult.hadResults
                    && !lateResult.terminal
                    && !poller.terminalEventSeen) return;
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
    let terminal = false;
    let hadResults = false;
    for (let batch = 0; batch < 8 && !terminal; batch += 1) {
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
            if (isTerminalTaskEvent(result)) terminal = true;
        }
    }
    return {valid: true, terminal, hadResults};
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
        document.getElementById('messageInput').focus();
    }
    if (state) renderConversationList();
    refreshConversations(activeConversationId).catch(error => {
        console.error('Failed to refresh task history:', error);
    });

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
                queued.conversationId || activeConversationId
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
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
    requestAnimationFrame(() => {
        if (active) container.scrollIntoView({block: 'end', behavior: 'smooth'});
    });
    validateQuestionPrompt(container);
    if (active) {
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 60);
    }
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
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
        const chatMessages = document.getElementById('chatMessages');
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
    const chatMessages = document.getElementById('chatMessages');
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
    if (animate) requestAnimationFrame(() => messageDiv.classList.add('is-visible'));
    else messageDiv.classList.add('is-visible');
    if (!isRestoringConversation) chatMessages.scrollTop = chatMessages.scrollHeight;
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
    const isImage = isImageAttachment(item) || item.parse_mode === 'vision';
    const status = item.success === true
        ? isImage ? '已发送给视觉模型' : '已解析'
        : item.success === false
            ? isImage ? '图片发送失败' : '解析失败'
            : isImage ? '等待发送给视觉模型' : '正在解析';
    const statusClass = item.success === true
        ? 'is-ready'
        : item.success === false
            ? 'has-error'
            : 'is-parsing';
    const assetAttribute = item.asset_id
        ? ` data-asset-id="${escapeHtml(item.asset_id)}"`
        : '';
    return `
        <div class="message-attachment ${statusClass}" data-attachment-name="${escapeHtml(item.name)}"${assetAttribute}>
            ${renderAttachmentVisual(item, 'message-attachment-icon')}
            <span class="message-attachment-copy">
                <strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(status)} · ${formatAttachmentSize(Number(item.size || 0))}</small>
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
    const chatMessages = document.getElementById('chatMessages');
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
    state.isCommentary = true;
    if (state.frame) {
        cancelAnimationFrame(state.frame);
        state.frame = null;
        renderStreamingState(state);
    }
    completeStreamingThinking(state);
    decorateCommentaryMessage(state.element);
}

function createStreamingThinking(state) {
    state.thinkingStartedAt = Date.now();
    state.thinkingCard = addThinkingCard('', state.element, false, true, false);
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
    const chatMessages = document.getElementById('chatMessages');
    if (state.thinkingCard?.parentNode === chatMessages
        && state.element?.parentNode === chatMessages
        && state.thinkingCard.nextSibling !== state.element) {
        chatMessages.insertBefore(state.thinkingCard, state.element);
    }
}

function appendStreamingResponse(streamId, chunk) {
    const id = String(streamId || currentMessageId);
    let state = streamingResponses.get(id);
    if (!state) {
        state = {
            element: null,
            bubble: null,
            thinkingCard: null,
            thinkingBody: null,
            content: '',
            frame: null,
            streamId: id,
            thinkingCondensed: false,
            thinkingStartedAt: 0,
            thinkingDurationMs: null,
            thinkingTimer: null,
            thinkingClosed: false,
            isCommentary: false,
        };
        streamingResponses.set(id, state);
    }
    state.content += String(chunk || '');
    if (!state.thinkingCard && splitStreamingContent(state.content).hasThinking) {
        if (state.frame) {
            cancelAnimationFrame(state.frame);
            state.frame = null;
        }
        renderStreamingState(state);
        return;
    }
    scheduleStreamingRender(state);
}

function scheduleStreamingRender(state) {
    if (state.frame) return;
    state.frame = requestAnimationFrame(() => {
        state.frame = null;
        renderStreamingState(state);
    });
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

    const chatMessages = document.getElementById('chatMessages');
    const distanceFromBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
    if (distanceFromBottom < 180) chatMessages.scrollTop = chatMessages.scrollHeight;
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
    if (isCommentary && state) state.isCommentary = true;

    if (result.target === 'discard') {
        if (state?.frame) cancelAnimationFrame(state.frame);
        stopStreamingThinkingTimer(state);
        state?.element?.remove();
        state?.thinkingCard?.remove();
        streamingResponses.delete(streamId);
        return;
    }

    if (result.target === 'thinking') {
        if (state?.frame) cancelAnimationFrame(state.frame);
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
        if (state.frame) cancelAnimationFrame(state.frame);
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

    completedMessageByMessageId.set(msgId, finalMessage);
    flushPendingKnowledge(msgId, finalMessage);
    updateTokenIndicator();
}

function getVisibleModelContent(content) {
    return splitThinkingContent(content).answer.trim();
}

function removeStreamingResponses() {
    streamingResponses.forEach((state) => {
        if (state.frame) cancelAnimationFrame(state.frame);
        stopStreamingThinkingTimer(state);
        state.element?.remove();
        state.thinkingCard?.remove();
    });
    streamingResponses.clear();
}

function finalizeVisibleStreamingResponses() {
    streamingResponses.forEach((state, streamId) => {
        if (state.frame) cancelAnimationFrame(state.frame);
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
    durationMs = null
) {
    const chatMessages = document.getElementById('chatMessages');
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
    if (scrollIntoView) chatMessages.scrollTop = chatMessages.scrollHeight;
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
    const distanceFromBottom = chatMessages
        ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
        : Infinity;
    const keepBottomAnchored = distanceFromBottom < 120;

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
                chatMessages.scrollTop = chatMessages.scrollHeight;
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

function getToolProgressCopy(toolName, params = {}) {
    const name = String(toolName || '').toLowerCase();
    const path = params.filePath || params.file_path || params.path || params.filename || '';
    const fileName = path ? String(path).split(/[\\/]/).pop() : '';
    if (/write|create_file|file_write|edit/.test(name)) {
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
    if (/write|create_file|file_write|edit/.test(name)) return '正在生成写入内容';
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
    if (/^(?:error|failed|failure):/i.test(text)) return true;
    if (!text.startsWith('{')) return false;
    try {
        const parsed = JSON.parse(text);
        return parsed && typeof parsed === 'object' && parsed.success === false;
    } catch (error) {
        return false;
    }
}

function startToolExecution(result, msgId, isPreparing = false) {
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
        const summary = existing.element.querySelector('.tool-live-summary');
        if (summary) summary.textContent = existing.progressCopy;
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
    toolDiv.classList.toggle('is-preparing', isPreparing);
    toolDiv.innerHTML = `
        <div class="tool-card tool-card-running" role="status" aria-live="polite">
            <div class="tool-header tool-header-running">
                <span class="tool-progress-spinner" aria-hidden="true"><span></span></span>
                <span class="tool-name">${escapeHtml(result.tool || 'Tool')}</span>
                <span class="tool-summary tool-live-summary">${escapeHtml(progressCopy)}</span>
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
            liveSummary.textContent = `${execution.progressCopy} · ${phases[execution.phase]}`;
        }
        const distance = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
        if (distance < 160) chatMessages.scrollTop = chatMessages.scrollHeight;
    };
    updateElapsed();
    execution.interval = setInterval(updateElapsed, 1000);
    activeToolExecutions.set(key, execution);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return toolDiv;
}

function finishToolExecution(result, msgId) {
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
            Number(result.duration_ms || 0)
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
    toolDiv.classList.remove('tool-execution-running');
    toolDiv.classList.add(failed ? 'tool-execution-error' : 'tool-execution-complete');
    toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(result.tool || 'Tool')}</span>
                <span class="tool-summary">${failed ? '工具调用失败' : '工具调用完成'} · ${escapeHtml(formatToolDuration(duration))}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result.result || '').substring(0, 1600))}</div>
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
    const chatMessages = document.getElementById('chatMessages');
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
        const distance = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
        if (distance < 160) chatMessages.scrollTop = chatMessages.scrollHeight;
    };
    updateElapsed();
    state.interval = setInterval(updateElapsed, 250);
    activeCompressionActivities.set(key, state);
    chatMessages.scrollTop = chatMessages.scrollHeight;
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

function addToolMessage(toolName, result, animate = true, durationMs = 0) {
    const chatMessages = document.getElementById('chatMessages');
    const toolDiv = document.createElement('div');
    const failed = toolResultFailed(result);
    toolDiv.className = `tool-execution ${failed ? 'tool-execution-error' : ''}`;
    toolDiv.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(toolName)}</span>
                <span class="tool-summary">${failed ? '工具调用失败' : '工具调用完成'}${durationMs > 0 ? ` · ${escapeHtml(formatToolDuration(durationMs))}` : ''}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(String(result).substring(0, 1600))}</div>
        </details>
    `;
    chatMessages.appendChild(toolDiv);
    if (animate) requestAnimationFrame(() => toolDiv.classList.add('is-visible'));
    else toolDiv.classList.add('is-visible');
    if (!isRestoringConversation) chatMessages.scrollTop = chatMessages.scrollHeight;
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

function renderProjectPreviewCard(card, session) {
    const copy = getPreviewStatusCopy(session);
    const isReady = session.status === 'ready' && Boolean(session.url);
    const location = session.host || (session.port ? `localhost:${session.port}` : '本地端口');
    card.className = `project-preview-card is-${session.status}`;
    card.dataset.previewId = session.previewId;
    card.dataset.conversationId = session.conversationId;
    card.innerHTML = `
        <div class="project-preview-icon" aria-hidden="true">
            <img class="theme-asset-mark" src="${THEME_ASSETS[getCurrentTheme()].mark}" alt="">
            <span class="project-preview-status-dot"></span>
        </div>
        <div class="project-preview-copy">
            <div class="project-preview-title-row">
                <strong>${escapeHtml(session.name)}</strong>
                <span class="project-preview-status-label">${escapeHtml(copy.label)}</span>
            </div>
            <span class="project-preview-meta">网站 · ${escapeHtml(location)}</span>
            <span class="project-preview-detail">${escapeHtml(copy.detail)}</span>
        </div>
        <button class="project-preview-open" type="button"${isReady ? '' : ' disabled'}>
            <span>${escapeHtml(copy.action)}</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M9 18l6-6-6-6"/>
            </svg>
        </button>
        <span class="project-preview-progress" aria-hidden="true"><span></span></span>`;
    card.querySelector('.project-preview-open')?.addEventListener('click', () => {
        openBrowserPreview(session.previewId);
    });
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
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return null;
    let card = chatMessages.querySelector(
        `.project-preview-card[data-preview-id="${cssEscape(session.previewId)}"]`
    );
    const isNew = !card;
    if (isNew) {
        chatMessages.classList.remove('is-welcome');
        chatMessages.querySelector('.welcome-message')?.remove();
        card = document.createElement('article');
        chatMessages.appendChild(card);
    }
    renderProjectPreviewCard(card, session);
    if (isNew && animate) requestAnimationFrame(() => card.classList.add('is-visible'));
    else card.classList.add('is-visible');

    if (activePreviewId === session.previewId) updateOpenPreviewSession(session);
    if (isNew && animate && !isRestoringConversation) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    return card;
}

async function syncPreviewSessions(conversationId) {
    if (!conversationId || typeof eel === 'undefined'
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
    } catch (error) {
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
        const result = await eel.open_preview_external(previewId)();
        if (result?.success === false) throw new Error(result.error || '打开失败');
    } catch (error) {
        showToast(`外部打开失败：${error.message}`, 'error');
    }
}

async function stopBrowserPreview() {
    const previewId = String(activePreviewId || '');
    const session = previewSessions.get(previewId);
    if (!session || ['stopped', 'error'].includes(session.status)
        || typeof eel === 'undefined'
        || typeof eel.stop_project_preview !== 'function') return;
    const button = document.getElementById('browserPreviewStop');
    if (button) button.disabled = true;
    try {
        const result = await eel.stop_project_preview(previewId)();
        if (result?.success === false) throw new Error(result.error || '停止失败');
        upsertProjectPreview({
            ...result,
            preview_id: previewId,
            status: 'stopped',
            message: result?.message || result?.stop_reason || '预览服务已停止',
        });
        showToast('本地预览服务已停止', 'success');
    } catch (error) {
        if (button) button.disabled = false;
        showToast(`停止预览失败：${error.message}`, 'error');
    }
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
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
    const protectedContent = protectLatex(String(content), mathTokens);
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
    let escaped = escapeHtml(content).replace(/`([^`\n]+)`/g, (_, code) => {
        const token = `\u0000CODE${codeTokens.length}\u0000`;
        codeTokens.push(`<code>${code}</code>`);
        return token;
    });

    escaped = escaped
        .replace(/!\[([^\]]*)\]\(([^\s)]+)(?:\s+&quot;[^&]*&quot;)?\)/g, '$1')
        .replace(/\[([^\]]+)\]\(([^\s)]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_, label, url) => renderSafeLink(label, url))
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/__([^_]+)__/g, '<strong>$1</strong>')
        .replace(/~~([^~]+)~~/g, '<del>$1</del>')
        .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
        .replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>');

    return escaped.replace(/\u0000CODE(\d+)\u0000/g, (_, tokenIndex) => codeTokens[Number(tokenIndex)] || '');
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
async function refreshWorkspace(folder) {
    try {
        const items = await eel.list_workspace_files(folder)();
        const listEl = document.getElementById(folder + 'Files');

        if (!items || items.length === 0) {
            listEl.innerHTML = '<div class="sidebar-empty">暂无文件</div>';
            return;
        }

        listEl.innerHTML = items.map((item, index) => {
            const safeName = escapeHtml(item.name);
            if (item.type === 'folder') {
                return `
                    <button class="file-item folder" type="button" data-index="${index}">
                        <svg class="file-icon folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span class="file-name">${safeName}</span>
                    </button>
                `;
            } else {
                return `
                    <button class="file-item" type="button" data-index="${index}">
                        <svg class="file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span class="file-name">${safeName}</span>
                        <span class="file-size">${formatFileSize(item.size)}</span>
                    </button>
                `;
            }
        }).join('');
        listEl.querySelectorAll('.file-item').forEach((element) => {
            const item = items[Number(element.dataset.index)];
            element.addEventListener('click', () => {
                if (item.type === 'folder') {
                    openWorkspaceFolder(folder, item.name);
                } else {
                    openFile(folder, item.name);
                }
            });
        });
    } catch (e) {
        console.error('Failed to refresh workspace:', e);
    }
}

async function refreshAllWorkspace() {
    if (refreshInFlight || typeof eel === 'undefined') return;
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
        await eel.open_workspace_file(folder, fileName)();
    } catch (e) {
        console.error('Failed to open file:', e);
        showToast('打开文件失败', 'error');
    }
}

async function openWorkspaceFolder(folder, subFolder) {
    try {
        await eel.open_workspace_subfolder(folder, subFolder)();
    } catch (e) {
        console.error('Failed to open folder:', e);
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
        const settings = await eel.load_settings()();
        currentSettingsSnapshot = settings;

        document.getElementById('settingApiBaseUrl').value = settings.api_base_url || '';
        document.getElementById('settingApiKey').value = settings.api_key || '';
        document.getElementById('settingApiModel').value = settings.api_model || '';
        document.getElementById('settingTavilyKey').value = settings.tavily_api_key || '';
        document.getElementById('settingMaxSteps').value = settings.max_steps || '';
        document.getElementById('settingMaxTokens').value = settings.max_tokens || '';
        document.getElementById('settingCompressAt').value = settings.compress_at || '';
        document.getElementById('settingMaxWebSearches').value = settings.max_web_searches || '';
        document.getElementById('settingShowKnowledgeAppendix').checked = String(
            settings.show_knowledge_appendix ?? 'true'
        ).toLowerCase() === 'true';

        // 加载配置列表
        await loadConfigList();

        // 添加实时修改监听 - 当用户修改API字段时，立即重置配置选择
        const apiFields = ['settingApiBaseUrl', 'settingApiKey', 'settingApiModel'];
        apiFields.forEach(fieldId => {
            document.getElementById(fieldId).oninput = () => {
                document.getElementById('configSelect').value = '';
            };
        });

        document.getElementById('settingsModal').classList.add('active');
        document.getElementById('settingApiBaseUrl').focus();
    } catch (e) {
        console.error('Failed to load settings:', e);
        showToast(`加载设置失败：${e.message}`, 'error');
    }
}

async function loadConfigList() {
    try {
        const result = await eel.list_api_configs()();
        const select = document.getElementById('configSelect');

        select.innerHTML = '<option value="">选择已保存配置…</option>';

        if (result.available && result.available.length > 0) {
            result.available.forEach(configName => {
                const option = document.createElement('option');
                option.value = configName;
                option.textContent = configName;
                if (configName === result.active) {
                    option.selected = true;
                }
                select.appendChild(option);
            });

        }
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
        } else {
            showToast(`保存失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to save config:', e);
        showToast('保存配置失败', 'error');
    }
}

async function deleteCurrentConfig() {
    const configName = document.getElementById('configSelect').value;
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
        tavily_api_key: document.getElementById('settingTavilyKey').value.trim(),
        max_steps: document.getElementById('settingMaxSteps').value.trim() || fallback.max_steps || '20',
        max_tokens: document.getElementById('settingMaxTokens').value.trim() || fallback.max_tokens || '30000',
        compress_at: document.getElementById('settingCompressAt').value.trim() || fallback.compress_at || '',
        max_web_searches: document.getElementById('settingMaxWebSearches').value.trim() || fallback.max_web_searches || '3',
        show_knowledge_appendix: document.getElementById('settingShowKnowledgeAppendix').checked
            ? 'true'
            : 'false'
    };
}

async function saveSettings() {
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
            showKnowledgeAppendix = String(
                currentSettingsSnapshot.show_knowledge_appendix ?? 'true'
            ).toLowerCase() === 'true';
            if (!showKnowledgeAppendix) {
                pendingKnowledgeByMessageId.clear();
                document.querySelectorAll('.knowledge-panel').forEach(panel => panel.remove());
            }
            await updateModelBadge();

            closeSettingsModal();
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
    if (tokenRefreshInFlight || typeof eel === 'undefined') return;
    tokenRefreshInFlight = true;
    try {
        const requestedConversationId = String(activeConversationId || '');
        const result = await eel.get_token_count(requestedConversationId)();
        if (requestedConversationId !== String(activeConversationId || '')) return;
        const tokens = Number(result.tokens || 0);
        const maxTokens = Math.max(Number(result.compress_at ?? result.max_tokens ?? 1), 1);
        const percentage = Math.min((tokens / maxTokens) * 100, 100);

        const progressBar = document.getElementById('tokenProgressBar');
        const tokenText = document.getElementById('tokenText');

        progressBar.style.width = percentage + '%';

        // 格式化显示
        const maxK = maxTokens / 1000;
        if (tokens >= 1000) {
            tokenText.textContent = (tokens / 1000).toFixed(1) + 'k/' + maxK + 'k';
        } else {
            tokenText.textContent = tokens + '/' + maxK + 'k';
        }

        // 更新 tooltip
        const tooltip = document.getElementById('tokenTooltip');
        if (tooltip) {
            tooltip.innerHTML = `Memory usage. Auto-compress at ${maxK}k. <code>/compact</code> to compress.`;
        }

        // 颜色变化
        progressBar.classList.remove('warning', 'danger');
        if (percentage >= 90) {
            progressBar.classList.add('danger');
        } else if (percentage >= 70) {
            progressBar.classList.add('warning');
        }
    } catch (e) {
        console.error('Failed to update token indicator:', e);
    } finally {
        tokenRefreshInFlight = false;
    }
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
        const maxK = (result.compress_at ?? result.max_tokens) / 1000;

        const indicator = document.getElementById('tokenIndicator');
        tooltip = document.createElement('div');
        tooltip.id = 'tokenTooltip';
        tooltip.className = 'token-tooltip';
        tooltip.innerHTML = `Memory usage. Auto-compress at ${maxK}k. <code>/compact</code> to compress.`;

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
async function refreshSkills() {
    try {
        const skills = await eel.list_skills()();
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
    try {
        const result = await eel.select_skill_folder()();

        if (result.cancelled) {
            return;
        }

        if (result.success) {
            showToast(`技能添加成功: ${result.name}`, 'success');
            refreshSkills();
        } else {
            showToast(`添加技能失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to add skill:', e);
        showToast('添加技能失败', 'error');
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
            refreshSkills();
        } else {
            showToast(`删除技能失败: ${result.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to delete skill:', e);
        showToast('删除技能失败', 'error');
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

        titleEl.textContent = fileType === 'execution_history' ? 'execution_history.md' : 'accumulated_compression.md';
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
