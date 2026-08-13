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
    document.getElementById('settingCustomSystemPrompt').value =
      settings.custom_system_prompt || '';
    hideLocalModelMenu();
    document.getElementById('settingMaxSteps').value = settings.max_steps || '';
    document.getElementById('settingMaxTokens').value = settings.max_tokens || '';
    document.getElementById('settingContextWindow').value = contextWindowIndexFor(
      settings.context_window
    );
    updateContextWindowLabel();
    document.getElementById('settingAutoCompactPercent').value =
      settings.auto_compact_threshold_percent || '85';
    document.getElementById('settingMaxWebSearches').value = settings.max_web_searches || '';
    populateVoiceTtsSettings();

    // 加载配置列表
    await loadConfigList();

    // 添加实时修改监听 - 当用户修改API字段时，立即重置配置选择
    const apiFields = ['settingApiBaseUrl', 'settingApiKey', 'settingApiModel'];
    apiFields.forEach((fieldId) => {
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
    available.forEach((configName) => {
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
        `<span class="model-quick-switch-name">${escapeHtml(model || '未知模型')}</span>` +
        (isDeepSeek && isActive
          ? `<span class="model-quick-switch-effort" title="推理强度: ${escapeHtml(effort)}">${escapeHtml(effort)}</span>`
          : '') +
        (isDeepSeek && isActive
          ? '<svg class="model-quick-switch-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>'
          : '') +
        (isActive
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
        ['low', 'high'].forEach((value) => {
          const opt = document.createElement('button');
          opt.type = 'button';
          opt.className = 'model-reasoning-submenu-item' + (value === effort ? ' is-active' : '');
          opt.dataset.value = value;
          opt.title = `发送 reasoning_effort=${value}`;
          opt.innerHTML =
            `<span>${escapeHtml(value)}</span>` +
            (value === effort
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
                submenu.querySelectorAll('.model-reasoning-submenu-item').forEach((i) => {
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
        menu
          .querySelectorAll('.model-reasoning-submenu')
          .forEach((s) => s.classList.remove('is-open'));
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
    const targetRow = [...menu.querySelectorAll('.model-quick-switch-row')].find(
      (r) => r.dataset.config === openConfigName
    );
    const targetSubmenu = targetRow && targetRow.querySelector('.model-reasoning-submenu');
    if (targetRow && targetSubmenu) {
      menu
        .querySelectorAll('.model-reasoning-submenu')
        .forEach((s) => s.classList.remove('is-open'));
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
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
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
    tasks.forEach((task) => {
      const id = String(task.id || '');
      const interval = String(task.interval || '');
      const prompt = String(task.prompt || '');
      const convTitle = String(task.conversation_title || '');
      const nextFire = formatNextFire(task.next_fire);
      const recurring = task.recurring !== false;
      const item = document.createElement('div');
      item.className = 'scheduled-task-item';
      item.innerHTML =
        `<div class="scheduled-task-top">` +
        `<span class="scheduled-task-interval" title="${escapeHtml(interval)}">${escapeHtml(interval)}</span>` +
        (recurring ? '<span class="scheduled-task-badge">循环</span>' : '') +
        `<button class="scheduled-task-delete" type="button" title="删除定时任务" aria-label="删除定时任务">✕</button>` +
        `</div>` +
        `<div class="scheduled-task-prompt" title="${escapeHtml(prompt)}">${escapeHtml(prompt)}</div>` +
        `<div class="scheduled-task-meta">` +
        (convTitle
          ? `<span title="${escapeHtml(convTitle)}">${escapeHtml(convTitle)}</span>`
          : '') +
        (nextFire ? `<span>${escapeHtml(nextFire)}</span>` : '') +
        `</div>`;
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
    list.innerHTML =
      '<div class="data-item"><span class="data-source">定时任务加载失败</span></div>';
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

    available.forEach((configName) => {
      const config = (result.configs && result.configs[configName]) || {};
      const model = String(config.api_model || '');
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'api-config-menu-item';
      item.setAttribute('role', 'option');
      item.innerHTML =
        `<span class="api-config-menu-name">${escapeHtml(configName)}</span>` +
        (model ? `<span class="api-config-menu-model">${escapeHtml(model)}</span>` : '');
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
    models.forEach((model) => {
      const entry = model && typeof model === 'object' ? model : { id: String(model) };
      const rawId = String(entry.id || '');
      const displayName = String(entry.name || rawId || model);
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'local-model-item';
      item.textContent = displayName;
      item.title =
        rawId && rawId !== displayName
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
    max_steps:
      document.getElementById('settingMaxSteps').value.trim() || fallback.max_steps || '100',
    max_tokens:
      document.getElementById('settingMaxTokens').value.trim() || fallback.max_tokens || '50000',
    context_window: String(
      CONTEXT_WINDOW_OPTIONS[Number(document.getElementById('settingContextWindow').value)] ||
        Number(fallback.context_window || 256000)
    ),
    auto_compact_threshold_percent:
      document.getElementById('settingAutoCompactPercent').value.trim() ||
      fallback.auto_compact_threshold_percent ||
      '85',
    max_web_searches:
      document.getElementById('settingMaxWebSearches').value.trim() ||
      fallback.max_web_searches ||
      '8',
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
      document.querySelectorAll('.knowledge-panel').forEach((panel) => panel.remove());
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

// Static UI wiring (index.html buttons, no inline handlers).
function bindSettingsStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('closeSettingsButton', closeSettingsModal);
  bind('closeSettingsHeaderButton', closeSettingsModal);
  bind('saveSettingsButton', () => saveSettings());
  bind('configSelectTrigger', toggleApiConfigMenu);
  bind('saveCurrentConfigButton', saveCurrentConfig);
  bind('deleteCurrentConfigButton', deleteCurrentConfig);
  bind('localModelButton', openLocalModelPicker);
  bind('closeScheduledTasksButton', closeScheduledTasksModal);
  bind('scheduledTasksCloseButton', closeScheduledTasksModal);
  bind('scheduledTasksRefresh', loadScheduledTasks);
  const slider = document.getElementById('settingContextWindow');
  if (slider) {
    slider.addEventListener('input', () => {
      updateContextWindowLabel();
      previewContextWindow();
    });
  }
}
