function normalizeModifiedFiles(result) {
  const merged = new Map();
  (Array.isArray(result?.files) ? result.files : []).forEach((item) => {
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
    existing.hunks = (Array.isArray(item?.hunks) ? item.hunks : []).map((hunk) => ({
      old_start: Math.max(0, Number(hunk?.old_start || 0)),
      old_count: Math.max(0, Number(hunk?.old_count || 0)),
      new_start: Math.max(0, Number(hunk?.new_start || 0)),
      new_count: Math.max(0, Number(hunk?.new_count || 0)),
      lines: (Array.isArray(hunk?.lines) ? hunk.lines : []).map((line) => ({
        type: ['context', 'add', 'delete'].includes(line?.type) ? line.type : 'context',
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
  const paths = files.map((file) => String(file.path || '').replace(/\\/g, '/')).filter(Boolean);
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
  const root = { name: '', children: new Map(), file: null };
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
        node.children.set(segment, { name: segment, children: new Map(), file: null });
      }
      node = node.children.get(segment);
    }
    const fileName = parts[parts.length - 1];
    node.children.set(fileName, { name: fileName, children: new Map(), file: { ...file, index } });
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
    html += renderChangeReviewTreeNodes(dir, depth, parentPath, selectedPath, collapsedDirs);
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
  const root = buildChangeReviewTree(activeChangeReview.files, activeChangeReview.treeRoot);
  fileList.innerHTML = renderChangeReviewTreeNodes(
    root,
    0,
    '',
    selectedPath,
    activeChangeReview.collapsedDirs
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
  const file = activeChangeReview.files[activeChangeReview.selectedIndex];
  if (!file) {
    fileHeader.textContent = '';
    diff.innerHTML = '<div class="change-review-empty">没有可审核的文件</div>';
    return;
  }
  fileHeader.innerHTML = `
        <span title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</span>
        <span class="change-review-file-counts"><b>+${file.additions}</b><em>-${file.deletions}</em></span>`;
  if (!file.reviewable || !file.hunks.length) {
    diff.innerHTML = `
            <div class="change-review-empty">
                <strong>无法显示逐行差异</strong>
                <span>${escapeHtml(file.review_reason || '此文件没有可显示的文本差异')}</span>
            </div>`;
    return;
  }
  diff.innerHTML = file.hunks
    .map(
      (hunk) => `
        <section class="change-review-hunk">
            <div class="change-review-hunk-header">@@ -${hunk.old_start},${hunk.old_count} +${hunk.new_start},${hunk.new_count} @@</div>
            <div class="change-review-lines">
                ${hunk.lines
                  .map((line) => {
                    const type = ['add', 'delete'].includes(line.type) ? line.type : 'context';
                    const marker = type === 'add' ? '+' : type === 'delete' ? '-' : ' ';
                    return `<div class="change-review-line change-review-line-${type}">
                        <span class="change-review-line-number">${line.old_line ?? ''}</span>
                        <span class="change-review-line-number">${line.new_line ?? ''}</span>
                        <span class="change-review-line-marker" aria-hidden="true">${marker}</span>
                        <code>${escapeHtml(line.content)}</code>
                    </div>`;
                  })
                  .join('')}
            </div>
        </section>`
    )
    .join('');
}

function selectChangeReviewFile(pathOrIndex) {
  if (!activeChangeReview) return;
  const nextIndex = Number.isInteger(Number(pathOrIndex))
    ? Number(pathOrIndex)
    : activeChangeReview.files.findIndex((file) => file.path === pathOrIndex);
  if (nextIndex < 0 || nextIndex >= activeChangeReview.files.length) return;
  activeChangeReview.selectedIndex = nextIndex;
  expandChangeReviewAncestors(activeChangeReview.files[nextIndex].path);
  renderChangeReviewFiles();
  renderChangeReviewDiff();
}

function restoreChatAfterReviewLayout(chatMessages, distanceFromBottom) {
  if (!chatMessages) return;
  const align = (frames) => {
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
  closeAgentDetail({ restoreFocus: false });
  const chatMessages = document.getElementById('chatMessages');
  const distanceFromBottom = chatMessages
    ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
    : 0;
  const selectedIndex = Math.max(
    0,
    files.findIndex((file) => file.path === initialPath)
  );
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

function closeChangeReview({ restoreFocus = true } = {}) {
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
  setSidebarPanelWidth(getSavedSidebarPanelWidth(), { persist: false });
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
  const reviewAvailable = files.some(
    (file) => file.reviewable || file.hunks.length || file.review_reason
  );
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
  const reviewResult = { ...result, files };
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
            ${files
              .map(
                (file, index) => `
                <button class="modified-files-row" type="button" data-review-file-index="${index}" ${reviewAvailable ? '' : 'disabled'}>
                    <code title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</code>
                    <span class="modified-files-counts" aria-label="新增 ${file.additions} 行，删除 ${file.deletions} 行" title="新增 ${file.additions} 行，删除 ${file.deletions} 行"><b class="modified-files-added">+${file.additions}</b> <b class="modified-files-deleted">-${file.deletions}</b></span>
                </button>`
              )
              .join('')}
        </div>`;
  summary.querySelector('.modified-files-review')?.addEventListener('click', () => {
    openChangeReview(reviewResult);
  });
  summary.querySelector('.modified-files-rollback')?.addEventListener('click', () => {
    rollbackTaskCard(summary);
  });
  summary.querySelectorAll('.modified-files-row').forEach((row) => {
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
    refreshTaskRollbackButtons(result.conversation_id || activeConversationId);
  }
  return summary;
}
