function getSavedSidebarCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === 'true';
  } catch (_error) {
    return false;
  }
}

function isSidebarCollapsed() {
  return document.getElementById('sidebarShell')?.classList.contains('is-collapsed') || false;
}

function setSidebarCollapsed(collapsed, { persist = true } = {}) {
  const next = Boolean(collapsed);
  const sidebar = document.getElementById('sidebarShell');
  const button = document.getElementById('sidebarCollapseButton');
  const handle = document.getElementById('sidebarResizeHandle');
  sidebar?.classList.toggle('is-collapsed', next);
  button?.setAttribute('aria-expanded', next ? 'false' : 'true');
  button?.setAttribute('aria-label', next ? '展开工作台导航' : '收起工作台导航');
  button?.setAttribute('title', next ? '展开工作台导航' : '收起工作台导航');
  if (handle) {
    handle.tabIndex = next ? -1 : 0;
    handle.setAttribute('aria-hidden', next ? 'true' : 'false');
  }
  if (persist) {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(next));
    } catch (_error) {
      // The current layout remains usable when browser storage is unavailable.
    }
  }
  requestAnimationFrame(syncDockedLayoutWidths);
  return next;
}

function getStoredSidebarPanelWidth() {
  try {
    const value = Number(localStorage.getItem(SIDEBAR_PANEL_WIDTH_STORAGE_KEY) || 216);
    return Math.round(
      Math.min(
        SIDEBAR_PANEL_MAX_WIDTH,
        Math.max(SIDEBAR_PANEL_MIN_WIDTH, Number.isFinite(value) ? value : 216)
      )
    );
  } catch (_error) {
    return 216;
  }
}

function getCurrentSidebarTotalWidth() {
  const sidebar = document.getElementById('sidebarShell');
  const measuredWidth = sidebar?.getBoundingClientRect().width;
  if (Number.isFinite(measuredWidth) && measuredWidth > 0) return measuredWidth;
  return isSidebarCollapsed()
    ? SIDEBAR_RAIL_WIDTH
    : SIDEBAR_RAIL_WIDTH + getStoredSidebarPanelWidth();
}

function isDockedReviewLayout() {
  return window.innerWidth >= 1320;
}

function getReviewPanelWidthLimit(sidebarWidth = getCurrentSidebarTotalWidth()) {
  if (!isDockedReviewLayout()) return Math.min(760, window.innerWidth);
  return Math.max(
    CHANGE_REVIEW_MIN_WIDTH,
    Math.min(CHANGE_REVIEW_MAX_WIDTH, window.innerWidth - sidebarWidth - DOCKED_MAIN_MIN_WIDTH)
  );
}

function clampChangeReviewPanelWidth(value, sidebarWidth = getCurrentSidebarTotalWidth()) {
  const numericValue = Number(value);
  const fallback = Math.min(700, getReviewPanelWidthLimit(sidebarWidth));
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.round(
    Math.min(
      getReviewPanelWidthLimit(sidebarWidth),
      Math.max(CHANGE_REVIEW_MIN_WIDTH, numericValue)
    )
  );
}

function getSavedChangeReviewPanelWidth() {
  try {
    return clampChangeReviewPanelWidth(
      localStorage.getItem(CHANGE_REVIEW_WIDTH_STORAGE_KEY) || 700
    );
  } catch (_error) {
    return clampChangeReviewPanelWidth(700);
  }
}

function setChangeReviewPanelWidth(
  width,
  { persist = true, sidebarWidth = getCurrentSidebarTotalWidth() } = {}
) {
  const panelWidth = clampChangeReviewPanelWidth(width, sidebarWidth);
  document.documentElement.style.setProperty('--change-review-width', `${panelWidth}px`);
  const handle = document.getElementById('changeReviewResizeHandle');
  handle?.setAttribute('aria-valuenow', String(panelWidth));
  handle?.setAttribute('aria-valuemax', String(getReviewPanelWidthLimit(sidebarWidth)));
  if (persist) {
    try {
      localStorage.setItem(CHANGE_REVIEW_WIDTH_STORAGE_KEY, String(panelWidth));
    } catch (_error) {
      // Width remains usable if browser storage is unavailable.
    }
  }
  return panelWidth;
}

function clampChangeReviewFilesWidth(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return CHANGE_REVIEW_FILES_DEFAULT_WIDTH;
  return Math.round(
    Math.min(CHANGE_REVIEW_FILES_MAX_WIDTH, Math.max(CHANGE_REVIEW_FILES_MIN_WIDTH, numericValue))
  );
}

function getSavedChangeReviewFilesWidth() {
  try {
    return clampChangeReviewFilesWidth(
      localStorage.getItem(CHANGE_REVIEW_FILES_WIDTH_STORAGE_KEY) ||
        CHANGE_REVIEW_FILES_DEFAULT_WIDTH
    );
  } catch (_error) {
    return CHANGE_REVIEW_FILES_DEFAULT_WIDTH;
  }
}

function setChangeReviewFilesWidth(width, { persist = true } = {}) {
  const filesWidth = clampChangeReviewFilesWidth(width);
  document.documentElement.style.setProperty('--change-review-files-width', `${filesWidth}px`);
  const handle = document.getElementById('changeReviewFilesResizeHandle');
  handle?.setAttribute('aria-valuenow', String(filesWidth));
  if (persist) {
    try {
      localStorage.setItem(CHANGE_REVIEW_FILES_WIDTH_STORAGE_KEY, String(filesWidth));
    } catch (_error) {
      // Width remains usable if browser storage is unavailable.
    }
  }
  return filesWidth;
}

function getAgentDetailPanelWidthLimit(sidebarWidth = getCurrentSidebarTotalWidth()) {
  if (!isDockedReviewLayout()) return AGENT_DETAIL_MAX_WIDTH;
  return Math.max(
    AGENT_DETAIL_MIN_WIDTH,
    Math.min(AGENT_DETAIL_MAX_WIDTH, window.innerWidth - sidebarWidth - DOCKED_MAIN_MIN_WIDTH)
  );
}

function clampAgentDetailPanelWidth(value, sidebarWidth = getCurrentSidebarTotalWidth()) {
  const numericValue = Number(value);
  const fallback = Math.min(
    AGENT_DETAIL_DEFAULT_WIDTH,
    getAgentDetailPanelWidthLimit(sidebarWidth)
  );
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.round(
    Math.min(
      getAgentDetailPanelWidthLimit(sidebarWidth),
      Math.max(AGENT_DETAIL_MIN_WIDTH, numericValue)
    )
  );
}

function getSavedAgentDetailPanelWidth() {
  try {
    return clampAgentDetailPanelWidth(
      localStorage.getItem(AGENT_DETAIL_WIDTH_STORAGE_KEY) || AGENT_DETAIL_DEFAULT_WIDTH
    );
  } catch (_error) {
    return clampAgentDetailPanelWidth(AGENT_DETAIL_DEFAULT_WIDTH);
  }
}

function setAgentDetailPanelWidth(
  width,
  { persist = true, sidebarWidth = getCurrentSidebarTotalWidth() } = {}
) {
  const panelWidth = clampAgentDetailPanelWidth(width, sidebarWidth);
  document.documentElement.style.setProperty('--agent-detail-width', `${panelWidth}px`);
  const handle = document.getElementById('agentDetailResizeHandle');
  handle?.setAttribute('aria-valuenow', String(panelWidth));
  handle?.setAttribute('aria-valuemax', String(getAgentDetailPanelWidthLimit(sidebarWidth)));
  if (persist) {
    try {
      localStorage.setItem(AGENT_DETAIL_WIDTH_STORAGE_KEY, String(panelWidth));
    } catch (_error) {
      // Width remains usable if browser storage is unavailable.
    }
  }
  return panelWidth;
}

function clampSidebarPanelWidth(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return SIDEBAR_PANEL_MIN_WIDTH;
  const reservesDockedPanel =
    isDockedReviewLayout() &&
    !document.body.classList.contains('split-workspace-open') &&
    (document.body.classList.contains('change-review-open') ||
      document.body.classList.contains('agent-detail-open'));
  const dockedPanelWidth = document.body.classList.contains('change-review-open')
    ? CHANGE_REVIEW_MIN_WIDTH
    : AGENT_DETAIL_MIN_WIDTH;
  const viewportLimit = reservesDockedPanel
    ? Math.max(
        SIDEBAR_PANEL_MIN_WIDTH,
        window.innerWidth - SIDEBAR_RAIL_WIDTH - dockedPanelWidth - DOCKED_MAIN_MIN_WIDTH
      )
    : SIDEBAR_PANEL_MAX_WIDTH;
  return Math.round(
    Math.min(
      SIDEBAR_PANEL_MAX_WIDTH,
      viewportLimit,
      Math.max(SIDEBAR_PANEL_MIN_WIDTH, numericValue)
    )
  );
}

function getSavedSidebarPanelWidth() {
  return clampSidebarPanelWidth(getStoredSidebarPanelWidth());
}

function setSidebarPanelWidth(width, { persist = true } = {}) {
  const panelWidth = clampSidebarPanelWidth(width);
  document.documentElement.style.setProperty('--sidebar-panel-width', `${panelWidth}px`);
  const handle = document.getElementById('sidebarResizeHandle');
  handle?.setAttribute('aria-valuenow', String(panelWidth + SIDEBAR_RAIL_WIDTH));
  if (persist) {
    try {
      localStorage.setItem(SIDEBAR_PANEL_WIDTH_STORAGE_KEY, String(panelWidth));
    } catch (_error) {
      // Width remains usable if browser storage is unavailable.
    }
  }
  if (isDockedReviewLayout() && document.body.classList.contains('change-review-open')) {
    setChangeReviewPanelWidth(getSavedChangeReviewPanelWidth(), {
      persist: false,
      sidebarWidth: getCurrentSidebarTotalWidth(),
    });
  }
  if (isDockedReviewLayout() && document.body.classList.contains('agent-detail-open')) {
    setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), {
      persist: false,
      sidebarWidth: getCurrentSidebarTotalWidth(),
    });
  }
  return panelWidth;
}

function syncDockedLayoutWidths() {
  if (document.body.classList.contains('split-workspace-open')) {
    const workspace = document.getElementById('splitWorkspace');
    const current =
      parseFloat(workspace?.style.getPropertyValue('--split-pane-width')) ||
      SPLIT_PANE_DEFAULT_WIDTH;
    setSplitPaneWidth(current, { persist: false });
  }
  if (!isDockedReviewLayout()) return;
  setSidebarPanelWidth(getSavedSidebarPanelWidth(), { persist: false });
  if (document.body.classList.contains('change-review-open')) {
    setChangeReviewPanelWidth(getSavedChangeReviewPanelWidth(), {
      persist: false,
      sidebarWidth: getCurrentSidebarTotalWidth(),
    });
  }
  if (document.body.classList.contains('agent-detail-open')) {
    setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), {
      persist: false,
      sidebarWidth: getCurrentSidebarTotalWidth(),
    });
  }
}

function initializeSidebarWidth() {
  setSidebarPanelWidth(getSavedSidebarPanelWidth(), { persist: false });
  setChangeReviewPanelWidth(getSavedChangeReviewPanelWidth(), { persist: false });
  setChangeReviewFilesWidth(getSavedChangeReviewFilesWidth(), { persist: false });
  setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), { persist: false });
}

function installPointerResizeCleanup(handle, finishResize) {
  handle.addEventListener('pointerup', finishResize);
  handle.addEventListener('pointercancel', finishResize);
  handle.addEventListener('lostpointercapture', finishResize);
  window.addEventListener('pointerup', finishResize);
  window.addEventListener('pointercancel', finishResize);
  window.addEventListener('blur', finishResize);
}

function initializeSidebarResizeHandle(handle, mobileQuery) {
  if (!handle) return;
  let pointerId = null;

  const finishResize = () => {
    document.body.classList.remove('is-resizing-sidebar');
    if (pointerId === null) return;
    const capturedPointerId = pointerId;
    pointerId = null;
    try {
      if (handle.hasPointerCapture(capturedPointerId)) {
        handle.releasePointerCapture(capturedPointerId);
      }
    } catch (_error) {
      // The pointer can end outside the window before capture is released.
    }
  };
  const updateFromPointer = (event) => {
    if (pointerId === null || mobileQuery.matches) return;
    setSidebarPanelWidth(event.clientX - SIDEBAR_RAIL_WIDTH);
  };

  handle.addEventListener('pointerdown', (event) => {
    if (mobileQuery.matches || event.button !== 0) return;
    event.preventDefault();
    pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    document.body.classList.add('is-resizing-sidebar');
    updateFromPointer(event);
  });
  handle.addEventListener('pointermove', updateFromPointer);
  installPointerResizeCleanup(handle, finishResize);
  handle.addEventListener('keydown', (event) => {
    if (mobileQuery.matches) return;
    const currentWidth = getSavedSidebarPanelWidth();
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setSidebarPanelWidth(currentWidth - SIDEBAR_WIDTH_STEP);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      setSidebarPanelWidth(currentWidth + SIDEBAR_WIDTH_STEP);
    } else if (event.key === 'Home') {
      event.preventDefault();
      setSidebarPanelWidth(SIDEBAR_PANEL_MIN_WIDTH);
    } else if (event.key === 'End') {
      event.preventDefault();
      setSidebarPanelWidth(SIDEBAR_PANEL_MAX_WIDTH);
    }
  });
}

function initializeChangeReviewResizeHandle(handle) {
  if (!handle) return;
  let pointerId = null;

  const finishResize = () => {
    document.body.classList.remove('is-resizing-review');
    if (pointerId === null) return;
    const capturedPointerId = pointerId;
    pointerId = null;
    try {
      if (handle.hasPointerCapture(capturedPointerId)) {
        handle.releasePointerCapture(capturedPointerId);
      }
    } catch (_error) {
      // Capture may already be gone after a fast cross-window drag.
    }
  };
  const updateFromPointer = (event) => {
    if (pointerId === null || !isDockedReviewLayout()) return;
    setChangeReviewPanelWidth(window.innerWidth - event.clientX);
  };

  handle.addEventListener('pointerdown', (event) => {
    if (!isDockedReviewLayout() || event.button !== 0) return;
    event.preventDefault();
    pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    document.body.classList.add('is-resizing-review');
    updateFromPointer(event);
  });
  handle.addEventListener('pointermove', updateFromPointer);
  installPointerResizeCleanup(handle, finishResize);
  handle.addEventListener('keydown', (event) => {
    const currentWidth = getSavedChangeReviewPanelWidth();
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setChangeReviewPanelWidth(currentWidth + CHANGE_REVIEW_WIDTH_STEP);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      setChangeReviewPanelWidth(currentWidth - CHANGE_REVIEW_WIDTH_STEP);
    } else if (event.key === 'Home') {
      event.preventDefault();
      setChangeReviewPanelWidth(CHANGE_REVIEW_MIN_WIDTH);
    } else if (event.key === 'End') {
      event.preventDefault();
      setChangeReviewPanelWidth(getReviewPanelWidthLimit());
    }
  });
}

function initializeChangeReviewFilesResizeHandle(handle) {
  if (!handle) return;
  let pointerId = null;

  const finishResize = () => {
    document.body.classList.remove('is-resizing-review-files');
    if (pointerId === null) return;
    const capturedPointerId = pointerId;
    pointerId = null;
    try {
      if (handle.hasPointerCapture(capturedPointerId)) {
        handle.releasePointerCapture(capturedPointerId);
      }
    } catch (_error) {
      // Capture may already be gone after a fast cross-window drag.
    }
  };
  const updateFromPointer = (event) => {
    if (pointerId === null) return;
    const panelRect = document.getElementById('changeReviewPanel')?.getBoundingClientRect();
    if (!panelRect) return;
    setChangeReviewFilesWidth(panelRect.right - event.clientX);
  };

  handle.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    document.body.classList.add('is-resizing-review-files');
    updateFromPointer(event);
  });
  handle.addEventListener('pointermove', updateFromPointer);
  installPointerResizeCleanup(handle, finishResize);
}

function initializeAgentDetailResizeHandle(handle) {
  if (!handle) return;
  let pointerId = null;

  const finishResize = () => {
    document.body.classList.remove('is-resizing-agent-detail');
    if (pointerId === null) return;
    const capturedPointerId = pointerId;
    pointerId = null;
    try {
      if (handle.hasPointerCapture(capturedPointerId)) {
        handle.releasePointerCapture(capturedPointerId);
      }
    } catch (_error) {
      // Capture may already be gone after a fast cross-window drag.
    }
  };
  const updateFromPointer = (event) => {
    if (pointerId === null || !isDockedReviewLayout()) return;
    setAgentDetailPanelWidth(window.innerWidth - event.clientX);
  };

  handle.addEventListener('pointerdown', (event) => {
    if (!isDockedReviewLayout() || event.button !== 0) return;
    event.preventDefault();
    pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    document.body.classList.add('is-resizing-agent-detail');
    updateFromPointer(event);
  });
  handle.addEventListener('pointermove', updateFromPointer);
  installPointerResizeCleanup(handle, finishResize);
  handle.addEventListener('keydown', (event) => {
    if (!isDockedReviewLayout()) return;
    const currentWidth = getSavedAgentDetailPanelWidth();
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setAgentDetailPanelWidth(currentWidth + AGENT_DETAIL_WIDTH_STEP);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      setAgentDetailPanelWidth(currentWidth - AGENT_DETAIL_WIDTH_STEP);
    } else if (event.key === 'Home') {
      event.preventDefault();
      setAgentDetailPanelWidth(AGENT_DETAIL_MIN_WIDTH);
    } else if (event.key === 'End') {
      event.preventDefault();
      setAgentDetailPanelWidth(getAgentDetailPanelWidthLimit());
    }
  });
}

function getSidebarPanelButtons() {
  return Array.from(document.querySelectorAll('.sidebar-nav-item[data-sidebar-panel]'));
}

function getSavedSidebarPanel() {
  try {
    const saved = localStorage.getItem(SIDEBAR_PANEL_STORAGE_KEY);
    return SIDEBAR_PANEL_NAMES.has(saved) ? saved : 'tasks';
  } catch (_error) {
    return 'tasks';
  }
}

function setSidebarPanel(panelName, { focus = false } = {}) {
  const name = SIDEBAR_PANEL_NAMES.has(panelName) ? panelName : 'tasks';
  const panel = document.querySelector(`[data-sidebar-panel-content="${name}"]`);
  if (!panel) return;

  document.querySelectorAll('[data-sidebar-panel-content]').forEach((item) => {
    const isActive = item === panel;
    item.hidden = !isActive;
    item.classList.toggle('is-active', isActive);
  });
  getSidebarPanelButtons().forEach((button) => {
    const isActive = button.dataset.sidebarPanel === name;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
    button.tabIndex = isActive ? 0 : -1;
  });
  try {
    localStorage.setItem(SIDEBAR_PANEL_STORAGE_KEY, name);
  } catch (_error) {
    // Side panel selection remains usable when browser storage is unavailable.
  }
  if (focus) {
    document.querySelector(`[data-sidebar-panel="${name}"]`)?.focus();
  }
}
