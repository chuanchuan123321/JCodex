// JCodex Desktop UI - Knowledge Base Functions
// (split from app.js; classic script sharing the page's global scope)

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
        workflow: '工作流',
        success_case: '成功案例',
        template: '模板',
        fact: '事实',
        rule: '规则',
        custom: '自定义',
      };

      // Add select all header
      let html = `
                <div class="kb-item kb-header-row">
                    <label class="select-all-label">
                        <input type="checkbox" id="selectAllKb" ${selectedKbIds.size === entries.length ? 'checked' : ''}>
                        <span>全选</span>
                    </label>
                    <button class="btn-delete-kb" data-action="delete-selected" ${selectedKbIds.size === 0 ? 'disabled' : ''}>
                        🗑️ 删除选中 (${selectedKbIds.size})
                    </button>
                </div>
            `;

      html += entries
        .map((e) => {
          const typeText = typeMap[e.knowledge_type] || e.knowledge_type;
          const isSelected = selectedKbIds.has(e.id);
          return `
                <div class="kb-item ${isSelected ? 'selected' : ''}">
                    <div class="kb-checkbox">
                        <input type="checkbox" data-id="${escapeHtml(String(e.id || ''))}" ${isSelected ? 'checked' : ''}>
                    </div>
                    <div class="kb-main">
                        <div class="kb-title">${escapeHtml(e.title)}</div>
                        <div class="kb-meta">${escapeHtml(typeText)} | v${escapeHtml(e.version)} | 使用 ${Number(e.usage_count || 0)} 次</div>
                    </div>
                </div>
            `;
        })
        .join('');
      kbList.innerHTML = html;
      if (!kbList.dataset.delegationBound) {
        kbList.dataset.delegationBound = 'true';
        kbList.addEventListener('click', (event) => {
          const deleteSelected = event.target.closest('[data-action="delete-selected"]');
          if (deleteSelected) deleteSelectedKb();
        });
        kbList.addEventListener('change', (event) => {
          const selectAll = event.target.closest('#selectAllKb');
          if (selectAll) {
            toggleSelectAllKb(selectAll);
            return;
          }
          const checkbox = event.target.closest('input[data-id]');
          if (checkbox) {
            toggleKbSelection(checkbox.dataset.id, checkbox.checked);
          }
        });
      }
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
      conflictList.innerHTML = conflicts
        .map(
          (c) => `
                <div class="conflict-item">
                    <span class="conflict-title">${escapeHtml(c.entry_a_title)} vs ${escapeHtml(c.entry_b_title)}</span>
                    <span class="conflict-badge">未解决</span>
                    <div class="conflict-detail">字段: ${escapeHtml(c.conflict_field)}</div>
                </div>
            `
        )
        .join('');
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
    entries.forEach((entry) => {
      const cb = entry.querySelector('input[type="checkbox"]');
      if (cb) {
        selectedKbIds.add(cb.dataset.id);
        entry.classList.add('selected');
      }
    });
  } else {
    selectedKbIds.clear();
    entries.forEach((entry) => entry.classList.remove('selected'));
  }
  updateDeleteKbSelectedButton();
  // Update individual checkboxes
  entries.forEach((entry) => {
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

  const confirmed = await showConfirmDialog(
    `确定要删除选中的 ${selectedKbIds.size} 个知识条目吗？`
  );
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
      kbResults.innerHTML = results
        .map((r) => {
          // Map English type names to Chinese
          const typeMap = {
            workflow: '工作流',
            success_case: '成功案例',
            template: '模板',
            fact: '事实',
            rule: '规则',
            custom: '自定义',
          };
          const typeText = typeMap[r.knowledge_type] || r.knowledge_type;
          return `
                <div class="kb-item">
                    <div class="kb-title">${escapeHtml(r.title)}</div>
                    <div class="kb-meta">${escapeHtml(typeText)} | 匹配度: ${Number(r.score || 0).toFixed(2)}</div>
                    <div class="kb-content">${escapeHtml(String(r.content || '').substring(0, 150))}...</div>
                    <div class="kb-tags">
                        ${(r.tags || []).map((t) => `<span class="kb-tag">${escapeHtml(t)}</span>`).join('')}
                    </div>
                </div>
            `;
        })
        .join('');
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

  const tags = tagsStr ? tagsStr.split(',').map((t) => t.trim()) : [];

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

// Static UI wiring (index.html buttons, no inline handlers).
function bindKnowledgeStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('closeKnowledgeButton', closeKnowledgeModal);
  bind('knowledgeCloseButton', closeKnowledgeModal);
  bind('refreshKnowledgeButton', refreshKnowledgeBase);
  bind('searchKnowledgeButton', searchKnowledge);
  bind('extractKnowledgeButton', (event) => extractKnowledgeFromMemory(event.currentTarget));
}
