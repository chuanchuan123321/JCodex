// Workspace Functions
function getWorkspaceTreeKey(folder, path = '') {
  return `${folder}:${String(path || '')}`;
}

function getWorkspaceTreeId(folder, path = '') {
  const value = `${String(folder)}:${String(path || 'root')}`;
  return `workspaceTree-${Array.from(value)
    .map((character) => character.codePointAt(0).toString(36))
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
  return `<div class="workspace-tree" id="${treeId}" role="group">${items
    .map((item) => {
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
    })
    .join('')}</div>`;
}

function bindWorkspaceTreeEvents(folder, rootElement) {
  if (!rootElement || rootElement.dataset.workspaceTreeBound === 'true') return;
  rootElement.dataset.workspaceTreeBound = 'true';
  rootElement.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-workspace-toggle]');
    const folderItem = event.target.closest('[data-workspace-folder]');
    const openFolder = event.target.closest('[data-workspace-open-folder]');
    const fileItem = event.target.closest('[data-workspace-file]');
    if (toggle || folderItem) {
      event.preventDefault();
      toggleWorkspaceDirectory(
        folder,
        (toggle || folderItem).dataset.workspaceToggle || folderItem.dataset.workspaceFolder
      );
    } else if (openFolder) {
      event.preventDefault();
      openWorkspaceFolder(folder, openFolder.dataset.workspaceOpenFolder);
    } else if (fileItem) {
      event.preventDefault();
      openFile(folder, fileItem.dataset.workspaceFile);
    }
  });
  rootElement.addEventListener('dblclick', (event) => {
    const folderItem = event.target.closest('[data-workspace-folder]');
    if (!folderItem) return;
    event.preventDefault();
    openWorkspaceFolder(folder, folderItem.dataset.workspaceFolder);
  });
  rootElement.addEventListener('dragstart', (event) => {
    const folderItem = event.target.closest('[data-workspace-folder]');
    const fileItem = event.target.closest('[data-workspace-file]');
    const sourceItem = folderItem || fileItem;
    if (!sourceItem) return;
    const itemPath = String(
      sourceItem.dataset.workspaceFolder || sourceItem.dataset.workspaceFile || ''
    );
    if (!itemPath) return;
    const name =
      String(sourceItem.querySelector('.file-name')?.textContent || '').trim() ||
      getPathBaseName(itemPath);
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('text/plain', `workspace/${folder}/${itemPath}`);
    event.dataTransfer.setData(
      WORKSPACE_DRAG_TYPE,
      JSON.stringify({
        folder,
        path: itemPath,
        name,
        isFolder: Boolean(folderItem),
      })
    );
  });
}

function updateWorkspaceTree(folder) {
  const listEl = document.getElementById(`${folder}Files`);
  if (!listEl) return;
  listEl.innerHTML = renderWorkspaceTree(folder);
  bindWorkspaceTreeEvents(folder, listEl);
}

async function loadWorkspaceDirectory(folder, path = '', { force = false } = {}) {
  const key = getWorkspaceTreeKey(folder, path);
  if (!force && workspaceDirectoryItems.has(key)) return workspaceDirectoryItems.get(key);
  if (workspaceDirectoryRequests.has(key)) return workspaceDirectoryRequests.get(key);
  if (!canCallEel()) throw new Error('Eel connection is unavailable');
  const request = eel
    .list_workspace_files(folder, path)()
    .then((items) => {
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
    .filter((key) => key.startsWith(prefix))
    .map((key) => key.slice(prefix.length));
  await Promise.all(paths.map((path) => loadWorkspaceDirectory(folder, path, { force: true })));
}

async function refreshWorkspace(folder) {
  if (!canCallEel()) return;
  try {
    await loadWorkspaceDirectory(folder, '', { force: true });
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

// Static UI wiring (index.html buttons, no inline handlers).
function bindWorkspaceStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('workspaceRefreshAll', refreshAllWorkspace);
  bind('workspaceRefreshOutput', () => refreshWorkspace('output'));
  bind('workspaceRefreshTemp', () => refreshWorkspace('temp'));
  bind('closeFileModalButton', closeFileModal);
}
