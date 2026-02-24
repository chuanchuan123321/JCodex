// Minibot Desktop UI - Frontend Logic

let isInitialized = false;
let isProcessing = false;
let pollInterval = null;
let currentMessageId = 0;

function init() {
    if (typeof eel === 'undefined') {
        setTimeout(init, 100);
        return;
    }
    initializeUI();
    initializeMinibot();
    refreshAllWorkspace();
    refreshSkills();
    updateTokenIndicator();
    // 实时更新工作区文件（每3秒）
    setInterval(refreshAllWorkspace, 3000);
    // 更新token指示器（每2秒）
    setInterval(updateTokenIndicator, 2000);
}

document.addEventListener('DOMContentLoaded', init);

function initializeUI() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const clearChat = document.getElementById('clearChat');
    const quickActions = document.querySelectorAll('.quick-action');
    const settingsBtn = document.getElementById('settingsBtn');
    const tokenIndicator = document.getElementById('tokenIndicator');

    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 80) + 'px';
        
        // Show/hide quick commands popup
        if (messageInput.value.startsWith('/')) {
            showQuickCommands();
        } else {
            hideQuickCommands();
        }
        
        sendButton.disabled = !messageInput.value.trim();
    });

    messageInput.addEventListener('keydown', (e) => {
        // 检测输入法是否正在组合输入（e.isComposing）
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            if (messageInput.value.trim() && !sendButton.disabled) {
                sendMessage();
            }
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

    sendButton.addEventListener('click', sendMessage);
    clearChat.addEventListener('click', clearConversation);
    settingsBtn.addEventListener('click', openSettings);
    
    // Token indicator click
    tokenIndicator.addEventListener('click', toggleTokenTooltip);

    quickActions.forEach(btn => {
        btn.addEventListener('click', () => {
            messageInput.value = btn.dataset.prompt;
            messageInput.focus();
            sendButton.disabled = false;
        });
    });
}

async function initializeMinibot() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    try {
        const result = await eel.initialize()();
        
        if (result[0]) {
            isInitialized = true;
            statusDot.classList.remove('error');
            if (statusText) statusText.textContent = 'Ready';
            console.log('Minibot initialized:', result[1]);
        } else {
            statusDot.classList.add('error');
            if (statusText) statusText.textContent = 'Error';
            showError('Failed to initialize: ' + result[1]);
        }
    } catch (error) {
        statusDot.classList.add('error');
        if (statusText) statusText.textContent = 'Error';
        showError('Failed to initialize: ' + error.message);
    }
}

async function sendMessage() {
    if (!isInitialized) return;

    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // 停止之前的轮询
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    
    // 生成新的消息ID
    currentMessageId = Date.now();
    
    hideQuickCommands();

    isProcessing = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    document.getElementById('sendButton').disabled = true;

    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.style.display = 'none';

    addMessage('user', message);
    showThinking();

    try {
        await eel.send_message(message, currentMessageId)();
        startPolling(currentMessageId);
    } catch (error) {
        removeThinking();
        addMessage('ai', 'Error: ' + error.message, true);
        isProcessing = false;
    }
}

function startPolling(msgId) {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(async () => {
        // 检查是否是当前消息的轮询
        if (!isProcessing || msgId !== currentMessageId) {
            clearInterval(pollInterval);
            pollInterval = null;
            return;
        }
        
        try {
            const result = await eel.get_next_result()();
            if (result) {
                handleResult(result, msgId);
                
                // Stop polling on final response or error
                if (result.type === 'final' || result.type === 'error') {
                    clearInterval(pollInterval);
                    pollInterval = null;
                    isProcessing = false;
                }
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 500);
}

function handleResult(result, msgId) {
    // 忽略不是当前消息的结果
    if (msgId !== currentMessageId) {
        return;
    }
    
    // Handle different step types
    if (result.type === 'thinking') {
        removeThinking();
        addThinkingMessage(result.content);
        showThinking(); // Show loading for next step
    } else if (result.type === 'tool') {
        removeThinking();
        addToolMessage(result.tool, result.result);
        showThinking(); // Show loading for next step
        updateTokenIndicator(); // 更新token
    } else if (result.type === 'pending_approval') {
        removeThinking();
        showApproval(result.tool, result.params, result.thinking);
    } else if (result.type === 'compressing') {
        removeThinking();
        addMessage('ai', result.content);
    } else if (result.type === 'final') {
        removeThinking();
        addMessage('ai', result.content);
        updateTokenIndicator(); // 更新token
    } else if (result.type === 'error') {
        removeThinking();
        addMessage('ai', 'Error: ' + result.content, true);
    }
}

function showApproval(toolName, params, thinking) {
    const chatMessages = document.getElementById('chatMessages');
    const approvalDiv = document.createElement('div');
    approvalDiv.className = 'approval-container';
    
    let paramsText = '';
    for (const [key, value] of Object.entries(params)) {
        paramsText += `${key}: ${value}\n`;
    }
    
    approvalDiv.innerHTML = `
        <div class="approval-content">
            <div class="approval-header">
                <span class="approval-icon">⚠️</span>
                <span>Confirm Tool Execution</span>
            </div>
            <div class="approval-tool">${toolName}</div>
            <pre class="approval-params">${paramsText}</pre>
            <div class="approval-buttons">
                <button class="btn-approve" onclick="approveTool('approve')">✓ Execute</button>
                <button class="btn-allow-all" onclick="approveTool('all')">✓ All</button>
                <button class="btn-deny" onclick="approveTool('deny')">✗ Cancel</button>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(approvalDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function approveTool(action) {
    // Remove approval UI
    const approvalEl = document.querySelector('.approval-container');
    if (approvalEl) approvalEl.remove();
    
    showThinking();
    
    try {
        await eel.approve_tool(action)();
        startPolling(currentMessageId);
    } catch (error) {
        removeThinking();
        addMessage('ai', 'Error: ' + error.message, true);
        isProcessing = false;
    }
}

async function clearConversation() {
    if (!isInitialized) return;

    try {
        await eel.clear_conversation()();
        
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">M</div>
                <h2>Welcome to Minibot</h2>
                <p>Your AI automation assistant</p>
                <div class="quick-actions">
                    <button class="quick-action" data-prompt="Help me write a Python script">Write Code</button>
                    <button class="quick-action" data-prompt="Search for latest AI news">Web Search</button>
                    <button class="quick-action" data-prompt="Create a new file">Create File</button>
                </div>
            </div>
        `;

        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('messageInput').value = btn.dataset.prompt;
                document.getElementById('messageInput').focus();
                document.getElementById('sendButton').disabled = false;
            });
        });
    } catch (error) {
        console.error('Failed to clear:', error);
    }
}

function addMessage(role, content, isError = false) {
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
        <div class="message-content">
            <div class="message-bubble">${formattedContent}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addThinkingMessage(content) {
    const text = content.replace('接下来我要: ', '');
    addMessage('ai', '→ ' + text);
}

function addToolMessage(toolName, result) {
    const chatMessages = document.getElementById('chatMessages');
    const toolDiv = document.createElement('div');
    toolDiv.className = 'tool-execution';
    toolDiv.innerHTML = `
        <div class="tool-header">
            <span class="tool-name">${toolName}</span>
        </div>
        <div class="tool-result">${formatContent(String(result).substring(0, 800))}</div>
    `;
    chatMessages.appendChild(toolDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showThinking() {
    // Remove any existing thinking indicator first
    removeThinking();
    
    const chatMessages = document.getElementById('chatMessages');
    const thinkingDiv = document.createElement('div');
    thinkingDiv.id = 'thinking';
    thinkingDiv.className = 'message ai';
    thinkingDiv.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-content">
            <div class="message-loading">
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeThinking() {
    const thinking = document.getElementById('thinking');
    if (thinking) thinking.remove();
}

function formatContent(content) {
    if (!content) return '';
    
    let formatted = String(content)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, 
        '<pre><code>$2</code></pre>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
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
            listEl.innerHTML = '';
            return;
        }
        
        listEl.innerHTML = items.map(item => {
            if (item.type === 'folder') {
                return `
                    <div class="file-item folder" onclick="openWorkspaceFolder('${folder}', '${item.name}')">
                        <svg class="file-icon folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span class="file-name">${item.name}</span>
                    </div>
                `;
            } else {
                return `
                    <div class="file-item" onclick="openFile('${folder}', '${item.name}')">
                        <svg class="file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span class="file-name">${item.name}</span>
                        <span class="file-size">${formatFileSize(item.size)}</span>
                    </div>
                `;
            }
        }).join('');
    } catch (e) {
        console.error('Failed to refresh workspace:', e);
    }
}

async function refreshAllWorkspace() {
    await refreshWorkspace('output');
    await refreshWorkspace('temp');
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
        alert('Failed to open file');
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
        closeFileModal();
        closeSettingsModal();
    }
});

// Settings Functions
async function openSettings() {
    try {
        const settings = await eel.load_settings()();
        
        document.getElementById('settingApiBaseUrl').value = settings.api_base_url || '';
        document.getElementById('settingApiKey').value = settings.api_key || '';
        document.getElementById('settingApiModel').value = settings.api_model || '';
        document.getElementById('settingTavilyKey').value = settings.tavily_api_key || '';
        document.getElementById('settingMaxSteps').value = settings.max_steps || '20';
        document.getElementById('settingMaxTokens').value = settings.max_tokens || '30000';
        document.getElementById('settingCompressAt').value = settings.compress_at || '25000';
        document.getElementById('settingMaxWebSearches').value = settings.max_web_searches || '3';
        
        document.getElementById('settingsModal').classList.add('active');
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function saveSettings() {
    const settings = {
        api_base_url: document.getElementById('settingApiBaseUrl').value.trim(),
        api_key: document.getElementById('settingApiKey').value.trim(),
        api_model: document.getElementById('settingApiModel').value.trim(),
        tavily_api_key: document.getElementById('settingTavilyKey').value.trim(),
        max_steps: document.getElementById('settingMaxSteps').value.trim() || '20',
        max_tokens: document.getElementById('settingMaxTokens').value.trim() || '30000',
        compress_at: document.getElementById('settingCompressAt').value.trim() || '25000',
        max_web_searches: document.getElementById('settingMaxWebSearches').value.trim() || '3'
    };
    
    try {
        const result = await eel.save_settings(settings)();
        
        if (result.success) {
            closeSettingsModal();
            // 更新 token 显示
            updateTokenIndicator();
        } else {
            alert('Failed to save settings: ' + result.error);
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        alert('Failed to save settings');
    }
}

// Token Indicator
async function updateTokenIndicator() {
    try {
        const result = await eel.get_token_count()();
        const tokens = result.tokens;
        const maxTokens = result.max_tokens;
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
        const result = await eel.get_token_count()();
        const maxK = result.max_tokens / 1000;
        
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
            listEl.innerHTML = '';
            return;
        }
        
        listEl.innerHTML = skills.map(s => {
            const deleteBtn = s.builtin ? '' : `
                <button class="skill-delete" onclick="event.stopPropagation(); deleteSkill('${s.name}')" title="Delete">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            `;
            const builtinBadge = s.builtin ? '<span class="builtin-badge">built-in</span>' : '';
            
            return `
                <div class="skill-item ${s.builtin ? 'builtin' : ''}" onclick="openSkill('${s.name}')" title="${s.description || ''}">
                    <svg class="skill-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                    </svg>
                    <span class="skill-name">${s.name}</span>
                    ${builtinBadge}
                    ${deleteBtn}
                </div>
            `;
        }).join('');
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
            alert('Skill added successfully: ' + result.name);
            refreshSkills();
        } else {
            alert('Failed to add skill: ' + result.error);
        }
    } catch (e) {
        console.error('Failed to add skill:', e);
        alert('Failed to add skill');
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
    if (!confirm(`Delete skill "${skillName}"?`)) return;
    
    try {
        const result = await eel.delete_skill(skillName)();
        
        if (result.success) {
            refreshSkills();
        } else {
            alert('Failed to delete skill: ' + result.error);
        }
    } catch (e) {
        console.error('Failed to delete skill:', e);
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
        const result = await eel.read_memory_file(fileType)();
        
        if (result.error) {
            alert('Failed to read memory: ' + result.error);
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
        alert('Failed to read memory file');
    }
}
