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
  const computedMainMinWidth = Number.parseFloat(window.getComputedStyle(mainContent).minWidth);
  const mainMinWidth =
    Number.isFinite(computedMainMinWidth) && computedMainMinWidth > 0
      ? computedMainMinWidth
      : SPLIT_MAIN_MIN_WIDTH;
  return Math.max(SPLIT_PANE_MIN_WIDTH, sharedWidth - mainMinWidth);
}

function setSplitPaneWidth(width, { persist = true, conversationId = activeConversationId } = {}) {
  const workspace = document.getElementById('splitWorkspace');
  const handle = document.getElementById('splitResizeHandle');
  if (!workspace) return 0;
  const normalized = Math.round(
    Math.max(
      SPLIT_PANE_MIN_WIDTH,
      Math.min(Number(width) || SPLIT_PANE_DEFAULT_WIDTH, getSplitPaneWidthLimit())
    )
  );
  workspace.style.setProperty('--split-pane-width', `${normalized}px`);
  handle?.setAttribute('aria-valuenow', String(normalized));
  handle?.setAttribute('aria-valuemax', String(Math.round(getSplitPaneWidthLimit())));
  if (persist && conversationId && canCallEel()) {
    eel
      .set_split_conversation_state(conversationId, null, normalized)()
      .catch((error) => {
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
    const deletedConversationIds = Array.from(
      new Set((result.deleted_conversation_ids || []).map(String))
    );
    deletedConversationIds.forEach((deletedId) => {
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
  setSplitPaneWidth(width || SPLIT_PANE_DEFAULT_WIDTH, { persist: false });
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
  const updateFromPointer = (event) => {
    if (pointerId === null || window.innerWidth <= 780) return;
    setSplitPaneWidth(window.innerWidth - event.clientX, { persist: false });
  };

  handle.addEventListener('pointerdown', (event) => {
    if (window.innerWidth <= 780 || event.button !== 0) return;
    event.preventDefault();
    pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    document.body.classList.add('is-resizing-split');
    updateFromPointer(event);
  });
  handle.addEventListener('pointermove', updateFromPointer);
  installPointerResizeCleanup(handle, finishResize);
  handle.addEventListener('keydown', (event) => {
    const workspace = document.getElementById('splitWorkspace');
    const current =
      parseFloat(workspace?.style.getPropertyValue('--split-pane-width')) ||
      SPLIT_PANE_DEFAULT_WIDTH;
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
