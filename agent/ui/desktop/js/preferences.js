// JCodex Desktop UI - Preferences Functions
// (split from app.js; classic script sharing the page's global scope)

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
  document.querySelectorAll('.pref-tab').forEach((tab) => {
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
                            <input type="checkbox" id="selectAllPrefs" ${selectedPrefKeys.size === Object.keys(categoryPrefs).length ? 'checked' : ''}>
                            <span>全选</span>
                        </label>
                        <button class="btn-delete-pref" data-action="delete-selected" ${selectedPrefKeys.size === 0 ? 'disabled' : ''}>
                            🗑️ 删除选中 (${selectedPrefKeys.size})
                        </button>
                    </div>
                `;

        html += Object.entries(categoryPrefs)
          .map(([key, value]) => {
            const isSelected = selectedPrefKeys.has(key);
            const safeKey = escapeHtml(key);
            const safeValue = escapeHtml(typeof value === 'object' ? JSON.stringify(value) : value);
            return `
                    <div class="pref-item ${isSelected ? 'selected' : ''}">
                        <div class="pref-checkbox">
                            <input type="checkbox" data-key="${escapeHtml(key)}" ${isSelected ? 'checked' : ''}>
                        </div>
                        <div class="pref-content">
                            <span class="pref-key">${safeKey}</span>
                            <span class="pref-value">${safeValue}</span>
                        </div>
                        <button class="btn-delete-pref" data-pref-delete="${escapeHtml(key)}">删除</button>
                    </div>
                `;
          })
          .join('');
        prefList.innerHTML = html;
        if (!prefList.dataset.delegationBound) {
          prefList.dataset.delegationBound = 'true';
          prefList.addEventListener('click', (event) => {
            const deleteSelected = event.target.closest('[data-action="delete-selected"]');
            if (deleteSelected) {
              deleteSelectedPrefs();
              return;
            }
            const deleteBtn = event.target.closest('[data-pref-delete]');
            if (deleteBtn) {
              event.stopPropagation();
              deletePref(deleteBtn.dataset.prefDelete);
            }
          });
          prefList.addEventListener('change', (event) => {
            const selectAll = event.target.closest('#selectAllPrefs');
            if (selectAll) {
              toggleSelectAllPrefs(selectAll);
              return;
            }
            const checkbox = event.target.closest('input[data-key]');
            if (checkbox) {
              togglePrefSelection(checkbox.dataset.key, checkbox.checked);
            }
          });
        }
      } else {
        prefList.innerHTML =
          '<div class="pref-item"><span class="pref-key">该分类暂无偏好</span></div>';
      }
    }

    // Refresh snapshots
    const snapshots = await eel.list_preference_snapshots()();
    const snapshotList = document.getElementById('prefSnapshots');
    if (snapshots && snapshots.length > 0) {
      snapshotList.innerHTML = snapshots
        .map((s) => {
          const safeSnapshotId = escapeHtml(String(s.snapshot_id || ''));
          return `
                <div class="pref-snapshot-item">
                    <div class="snapshot-info" data-snapshot-restore="${safeSnapshotId}">
                        <span class="snapshot-time">${escapeHtml(new Date(s.timestamp).toLocaleString())}</span>
                        <span class="snapshot-desc">${escapeHtml(s.description || '手动快照')} (${Number(s.entry_count || 0)} 条目)</span>
                    </div>
                    <div class="snapshot-actions">
                        <button class="btn-restore" data-snapshot-restore="${safeSnapshotId}">回溯</button>
                        <button class="btn-delete-snapshot" data-snapshot-delete="${safeSnapshotId}">删除</button>
                    </div>
                </div>
            `;
        })
        .join('');
      if (!snapshotList.dataset.delegationBound) {
        snapshotList.dataset.delegationBound = 'true';
        snapshotList.addEventListener('click', (event) => {
          const restore = event.target.closest('[data-snapshot-restore]');
          if (restore) {
            event.stopPropagation();
            restoreSnapshotById(restore.dataset.snapshotRestore);
            return;
          }
          const remove = event.target.closest('[data-snapshot-delete]');
          if (remove) {
            event.stopPropagation();
            deleteSnapshotById(remove.dataset.snapshotDelete);
          }
        });
      }
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
  prefItems.forEach((item) => {
    const checkbox = item.querySelector('input[type="checkbox"]');
    if (checkbox && checkbox.dataset.key === key) {
      item.classList.toggle('selected', checked);
    }
  });
}

function toggleSelectAllPrefs(checkbox) {
  const prefs = document.querySelectorAll('.pref-item:not(.pref-header-row)');
  if (checkbox.checked) {
    prefs.forEach((pref) => {
      const cb = pref.querySelector('input[type="checkbox"]');
      if (cb) {
        selectedPrefKeys.add(cb.dataset.key);
        pref.classList.add('selected');
      }
    });
  } else {
    selectedPrefKeys.clear();
    prefs.forEach((pref) => pref.classList.remove('selected'));
  }
  updateDeletePrefSelectedButton();
  // Update individual checkboxes
  prefs.forEach((pref) => {
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

// Static UI wiring (index.html buttons, no inline handlers).
function bindPreferencesStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('closePrefButton', closePrefModal);
  bind('prefCloseButton', closePrefModal);
  bind('clearAllPreferencesButton', clearAllPreferences);
  bind('refreshPreferencesButton', refreshPreferences);
  bind('addPreferenceButton', addPreference);
  bind('createPrefSnapshotButton', createPrefSnapshot);
  document.querySelectorAll('[data-pref-category]').forEach((button) => {
    button.addEventListener('click', () => showPrefCategory(button.dataset.prefCategory));
  });
}
