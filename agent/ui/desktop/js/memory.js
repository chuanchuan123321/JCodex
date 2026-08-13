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
    const result = await eel.read_memory_file(fileType, activeConversationId || '')();

    if (result.error) {
      showToast(`读取内存失败: ${result.error}`, 'error');
      return;
    }

    const modal = document.getElementById('fileModal');
    const titleEl = document.getElementById('fileModalTitle');
    const contentEl = document.getElementById('fileContent');

    const memoryFileNames = {
      execution_history: 'execution_history.md',
      accumulated_compression: 'accumulated_compression.md',
      memory_context: 'memory_context.md',
    };
    titleEl.textContent = memoryFileNames[fileType] || 'memory.md';
    contentEl.textContent = result.content || '(empty)';
    modal.classList.add('active');
  } catch (e) {
    console.error('Failed to read memory file:', e);
    showToast('读取内存文件失败', 'error');
  }
}

// Static UI wiring (index.html buttons + memory file list delegation).
function bindMemoryStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('memoryRefresh', refreshMemory);
  bind('memoryFilesRefresh', refreshMemory);
  const list = document.getElementById('memoryFiles');
  if (list && !list.dataset.delegationBound) {
    list.dataset.delegationBound = 'true';
    list.addEventListener('click', (event) => {
      const item = event.target.closest('[data-memory-file]');
      if (item) openMemoryFile(item.dataset.memoryFile);
    });
  }
}
