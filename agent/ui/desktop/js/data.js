// JCodex Desktop UI - Data Integration Functions
// (split from app.js; classic script sharing the page's global scope)

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
    list.innerHTML = items
      .map((item) => {
        const safeTitle = escapeHtml(item.title || '新任务');
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
                        <button class="btn-small" data-archive-restore="${escapeHtml(String(item.id || ''))}">恢复</button>
                        <button class="btn-delete-task" data-archive-delete="${escapeHtml(String(item.id || ''))}" data-archive-title="${escapeHtml(item.title || '新任务')}">删除</button>
                    </div>
                </div>`;
      })
      .join('');
    if (!list.dataset.delegationBound) {
      list.dataset.delegationBound = 'true';
      list.addEventListener('click', (event) => {
        const restore = event.target.closest('[data-archive-restore]');
        if (restore) {
          restoreArchivedConversation(restore.dataset.archiveRestore);
          return;
        }
        const remove = event.target.closest('[data-archive-delete]');
        if (remove) {
          deleteArchivedConversation(
            remove.dataset.archiveDelete,
            remove.dataset.archiveTitle || ''
          );
        }
      });
    }
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
      tasks.forEach((t) => {
        if (t.entries) {
          t.entries.forEach((e) => {
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
                        <input type="checkbox" id="selectAllTasks" ${selectedTaskIds.size === tasks.length ? 'checked' : ''}>
                        <span>全选</span>
                    </label>
                    <button class="btn-delete-selected" data-action="delete-selected" ${selectedTaskIds.size === 0 ? 'disabled' : ''}>
                        🗑️ 删除选中 (${selectedTaskIds.size})
                    </button>
                </div>
            `;

      html += tasks
        .map((t) => {
          // Status color
          const statusColor =
            t.status === '已完成' ? '#4CAF50' : t.status === '进行中' ? '#2196F3' : '#FF9800';
          // Tools used text
          const toolsText =
            t.tools_used && t.tools_used.length > 0
              ? t.tools_used.slice(0, 3).join(', ') + (t.tools_used.length > 3 ? '...' : '')
              : '无';
          // Time formatting
          const startTime = formatCompactDateTime(t.start_time);
          // User request (truncated)
          const requestText =
            t.user_request && t.user_request.length > 0
              ? t.user_request.length > 36
                ? t.user_request.substring(0, 36) + '...'
                : t.user_request
              : '无描述';
          const safeRequest = escapeHtml(requestText);
          const safeRequestTitle = escapeHtml(t.user_request || '');
          const safeToolsText = escapeHtml(toolsText);
          const safeStatus = escapeHtml(t.status || '未知');
          const isSelected = selectedTaskIds.has(t.task_id);

          return `
                <div class="data-item task-item ${isSelected ? 'selected' : ''}">
                    <div class="task-checkbox">
                        <input type="checkbox" data-task-id="${escapeHtml(String(t.task_id || ''))}" ${isSelected ? 'checked' : ''}>
                    </div>
                    <div class="task-main">
                        <div class="task-header" data-task-detail="${escapeHtml(String(t.task_id || ''))}">
                            <span class="task-request" title="${safeRequestTitle}">${safeRequest}</span>
                            <span class="task-status" style="color: ${statusColor}">${safeStatus}</span>
                        </div>
                        <div class="task-details" data-task-detail="${escapeHtml(String(t.task_id || ''))}">
                            <span class="task-info">${escapeHtml(startTime)}</span>
                            <span class="task-info">${Number(t.steps_count || 0)} 步</span>
                            <span class="task-info" title="${safeToolsText}">${safeToolsText}</span>
                        </div>
                    </div>
                    <div class="task-actions">
                        <button class="btn-delete-task" data-task-delete="${escapeHtml(String(t.task_id || ''))}">删除</button>
                    </div>
                </div>
            `;
        })
        .join('');
      dataList.innerHTML = html;
      if (!dataList.dataset.delegationBound) {
        dataList.dataset.delegationBound = 'true';
        dataList.addEventListener('click', (event) => {
          const deleteSelected = event.target.closest('[data-action="delete-selected"]');
          if (deleteSelected) {
            deleteSelectedTasks();
            return;
          }
          const detail = event.target.closest('[data-task-detail]');
          if (detail) {
            showTaskDetail(detail.dataset.taskDetail);
            return;
          }
          const deleteTaskBtn = event.target.closest('[data-task-delete]');
          if (deleteTaskBtn) {
            event.stopPropagation();
            deleteTask(deleteTaskBtn.dataset.taskDelete);
          }
        });
        dataList.addEventListener('change', (event) => {
          const selectAll = event.target.closest('#selectAllTasks');
          if (selectAll) {
            toggleSelectAllTasks(selectAll);
            return;
          }
          const checkbox = event.target.closest('input[data-task-id]');
          if (checkbox) {
            toggleTaskSelection(checkbox.dataset.taskId, checkbox.checked);
          }
        });
      }
    } else {
      dataList.innerHTML =
        '<div class="data-item"><span class="data-source">暂无任务记录</span></div>';
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
  taskItems.forEach((item) => {
    const checkbox = item.querySelector('input[type="checkbox"]');
    if (checkbox && checkbox.dataset.taskId === taskId) {
      item.classList.toggle('selected', checked);
    }
  });
}

function toggleSelectAllTasks(checkbox) {
  const tasks = checkbox.closest('.data-list').querySelectorAll('.task-item:not(.task-header-row)');
  if (checkbox.checked) {
    tasks.forEach((task) => {
      const cb = task.querySelector('input[type="checkbox"]');
      if (cb) {
        selectedTaskIds.add(cb.dataset.taskId);
        task.classList.add('selected');
      }
    });
  } else {
    selectedTaskIds.clear();
    tasks.forEach((task) => task.classList.remove('selected'));
  }
  updateDeleteSelectedButton();
  // Update individual checkboxes
  tasks.forEach((task) => {
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
    const task = tasks.find((t) => t.task_id === taskId);
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
          tool_result: '工具结果',
          user_behavior: '用户行为',
          manual_config: '手动配置',
          ai_response: 'AI响应',
          system_event: '系统事件',
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
  const confirmed = await showConfirmDialog(
    '确定要清空所有数据整合记录吗？清空后 AI 提取偏好将没有数据可分析。'
  );
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

// Static UI wiring (index.html buttons, no inline handlers).
function bindDataStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('dataBtn', openDataIntegration);
  bind('archiveBtn', openArchiveModal);
  bind('scheduledBtn', openScheduledTasksModal);
  bind('closeArchiveButton', closeArchiveModal);
  bind('archiveCloseButton', closeArchiveModal);
  bind('archiveRefreshButton', refreshArchivedConversations);
  bind('closeDataButton', closeDataModal);
  bind('dataCloseButton', closeDataModal);
  bind('ingestConfigButton', ingestConfig);
  bind('clearAllDataButton', clearAllData);
  bind('refreshDataStatsButton', refreshDataStats);
}
