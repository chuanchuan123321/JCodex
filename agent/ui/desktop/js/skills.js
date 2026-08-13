// Skills Functions
let skillStoreEntries = [];
const skillStoreInstallsInFlight = new Set();

function normalizeSkillStoreEntries(result) {
  if (Array.isArray(result)) return result;
  if (Array.isArray(result?.skills)) return result.skills;
  return [];
}

function updateSkillStoreSummary(result) {
  skillStoreEntries = normalizeSkillStoreEntries(result);
  const count = document.getElementById('skillStoreCount');
  if (count) count.textContent = String(skillStoreEntries.length);
}

async function refreshSkills() {
  try {
    const [skills, storeResult] = await Promise.all([
      eel.list_skills()(),
      eel.list_skill_store()(),
    ]);
    updateSkillStoreSummary(storeResult);
    const listEl = document.getElementById('skillsList');

    if (!skills || skills.length === 0) {
      listEl.innerHTML = '<div class="sidebar-empty">暂无技能</div>';
      return;
    }

    listEl.innerHTML = skills
      .map((s, index) => {
        const deleteBtn = s.builtin
          ? ''
          : `
                <button class="skill-delete" type="button" data-delete-index="${index}" title="删除技能" aria-label="删除 ${escapeHtml(s.name)}">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            `;
        const builtinBadge = s.builtin ? '<span class="builtin-badge">built-in</span>' : '';

        return `
                <div class="skill-item ${s.builtin ? 'builtin' : ''}" role="button" tabindex="0" data-skill-index="${index}" title="${escapeHtml(s.description || s.name)}">
                    <svg class="skill-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                    </svg>
                    <span class="skill-name">${escapeHtml(s.name)}</span>
                    ${builtinBadge}
                    ${deleteBtn}
                </div>
            `;
      })
      .join('');
    listEl.querySelectorAll('[data-skill-index]').forEach((element) => {
      const skill = skills[Number(element.dataset.skillIndex)];
      element.addEventListener('click', () => openSkill(skill.name));
      element.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openSkill(skill.name);
        }
      });
    });
    listEl.querySelectorAll('[data-delete-index]').forEach((element) => {
      const skill = skills[Number(element.dataset.deleteIndex)];
      element.addEventListener('click', (event) => {
        event.stopPropagation();
        deleteSkill(skill.name);
      });
    });
  } catch (e) {
    console.error('Failed to refresh skills:', e);
  }
}

async function addSkill() {
  document.getElementById('skillFolderInput')?.click();
}

async function importSkillFolder(files) {
  if (!files.length) return;
  const button = document.getElementById('addSkillButton');
  if (!canCallEel()) {
    markEelConnectionLost();
    return;
  }
  try {
    if (button) button.disabled = true;
    const payload = await Promise.all(
      files.map(async (file) => ({
        path: file.webkitRelativePath || file.name,
        data: await readFileAsDataUrl(file),
      }))
    );
    const result = await eel.import_skill_folder(payload)();
    if (!result?.success) {
      showToast(`添加技能失败: ${result?.error || '无法导入文件夹'}`, 'error');
      return;
    }
    showToast(`技能添加成功: ${result.name}`, 'success');
    await refreshSkills();
  } catch (error) {
    if (handleEelConnectionError(error)) return;
    console.error('Failed to import skill folder:', error);
    showToast(`添加技能失败: ${error.message || '无法读取文件夹'}`, 'error');
  } finally {
    if (button) button.disabled = false;
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
  const confirmed = await showConfirmDialog(`确定要删除技能 "${skillName}" 吗?`);
  if (!confirmed) return;

  try {
    const result = await eel.delete_skill(skillName)();

    if (result.success) {
      showToast(`技能已删除: ${skillName}`, 'success');
      await refreshSkills();
      if (document.getElementById('skillStoreModal')?.classList.contains('active')) {
        renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
      }
    } else {
      showToast(`删除技能失败: ${result.error}`, 'error');
    }
  } catch (e) {
    console.error('Failed to delete skill:', e);
    showToast('删除技能失败', 'error');
  }
}

async function openSkillStore() {
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById('skillStoreModal');
  const search = document.getElementById('skillStoreSearch');
  modal?.classList.add('active');
  if (search) search.value = '';
  renderSkillStore('');
  await refreshSkillStore();
  setTimeout(() => search?.focus(), 0);
}

function closeSkillStore() {
  document.getElementById('skillStoreModal')?.classList.remove('active');
  lastFocusedElement?.focus?.();
}

async function refreshSkillStore() {
  const refreshButton = document.getElementById('skillStoreRefresh');
  const meta = document.getElementById('skillStoreMeta');
  if (!canCallEel()) {
    markEelConnectionLost();
    return;
  }
  try {
    if (refreshButton) refreshButton.disabled = true;
    const result = await eel.list_skill_store()();
    if (result?.error) {
      if (meta) meta.textContent = `读取失败：${result.error}`;
      return;
    }
    updateSkillStoreSummary(result);
    renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
  } catch (error) {
    if (handleEelConnectionError(error)) return;
    if (meta) meta.textContent = '读取技能商店失败';
    console.error('Failed to refresh skill store:', error);
  } finally {
    if (refreshButton) refreshButton.disabled = false;
  }
}

function renderSkillStore(query = '') {
  const list = document.getElementById('skillStoreList');
  const meta = document.getElementById('skillStoreMeta');
  if (!list || !meta) return;
  const normalizedQuery = String(query || '')
    .trim()
    .toLocaleLowerCase();
  const visibleEntries = skillStoreEntries
    .map((skill, index) => ({ skill, index }))
    .filter(({ skill }) => {
      if (!normalizedQuery) return true;
      return `${skill.name || ''} ${skill.description || ''}`
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });
  const installableCount = skillStoreEntries.filter((skill) => !skill.installed).length;
  meta.textContent = `${skillStoreEntries.length} 个技能 · ${installableCount} 个可安装`;

  if (!visibleEntries.length) {
    list.innerHTML = `<div class="skill-store-empty">${
      skillStoreEntries.length ? '没有匹配的技能' : '商店中暂无技能'
    }</div>`;
    return;
  }

  list.innerHTML = visibleEntries
    .map(({ skill, index }) => {
      const installing = skillStoreInstallsInFlight.has(skill.name);
      let action = `
            <button class="skill-store-install" type="button" data-store-install-index="${index}" ${installing ? 'disabled' : ''}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>
                <span>${installing ? '安装中' : '安装'}</span>
            </button>`;
      if (skill.installed) {
        action = `<span class="skill-store-status ${skill.builtin ? 'is-builtin' : ''}">${skill.builtin ? '内置' : '已安装'}</span>`;
      }
      return `
            <div class="skill-store-item">
                <span class="skill-store-item-icon" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                </span>
                <span class="skill-store-item-copy">
                    <strong>${escapeHtml(skill.name)}</strong>
                    <small>${escapeHtml(skill.description || '暂无说明')}</small>
                </span>
                ${action}
            </div>`;
    })
    .join('');

  list.querySelectorAll('[data-store-install-index]').forEach((button) => {
    const skill = skillStoreEntries[Number(button.dataset.storeInstallIndex)];
    button.addEventListener('click', () => installStoreSkill(skill.name));
  });
}

async function installStoreSkill(skillName) {
  if (!skillName || skillStoreInstallsInFlight.has(skillName)) return;
  skillStoreInstallsInFlight.add(skillName);
  renderSkillStore(document.getElementById('skillStoreSearch')?.value || '');
  try {
    const result = await eel.install_store_skill(skillName)();
    if (!result?.success) {
      showToast(`安装技能失败: ${result?.error || '未知错误'}`, 'error');
      return;
    }
    showToast(`技能安装成功: ${skillName}`, 'success');
    await refreshSkills();
  } catch (error) {
    if (handleEelConnectionError(error)) return;
    console.error('Failed to install store skill:', error);
    showToast('安装技能失败', 'error');
  } finally {
    skillStoreInstallsInFlight.delete(skillName);
    await refreshSkillStore();
  }
}

async function openSkillStoreFolder() {
  try {
    const result = await eel.open_skill_store_folder()();
    if (!result?.success) {
      showToast(`打开商店目录失败: ${result?.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    if (handleEelConnectionError(error)) return;
    console.error('Failed to open skill store folder:', error);
    showToast('打开商店目录失败', 'error');
  }
}

// Static UI wiring (index.html buttons, no inline handlers).
function bindSkillsStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('addSkillButton', addSkill);
  bind('skillsRefresh', refreshSkills);
  bind('skillsFolderRefresh', refreshSkills);
  bind('skillStoreEntry', openSkillStore);
  bind('closeSkillStoreButton', closeSkillStore);
  bind('openSkillStoreFolderButton', openSkillStoreFolder);
  bind('skillStoreRefresh', refreshSkillStore);
}
