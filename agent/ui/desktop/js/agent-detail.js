function agentTeamKey(conversationId, messageId, teamId) {
  return `${String(conversationId || '')}:${Number(messageId || 0)}:${String(teamId || '')}`;
}

function boundedAgentPublicText(value, limit = 500) {
  return String(value || '')
    .replace(/<think\b[^>]*>[\s\S]*?<\/think>/gi, '')
    .replace(/<think\b[^>]*>[\s\S]*$/gi, '')
    .replace(/<\/?think\b[^>]*>/gi, '')
    .replace(/\u0000/g, '')
    .trim()
    .slice(0, Math.max(0, Number(limit || 0)));
}

function normalizeAgentStatus(value, fallback = 'queued') {
  const aliases = {
    pending: 'queued',
    in_progress: 'running',
    active: 'running',
    complete: 'completed',
    success: 'completed',
    error: 'failed',
    stopped: 'cancelled',
    canceled: 'cancelled',
    cancelling: 'waiting',
  };
  const status = String(value || '')
    .trim()
    .toLowerCase();
  const normalized = aliases[status] || status;
  return Object.prototype.hasOwnProperty.call(AGENT_STATUS_LABELS, normalized)
    ? normalized
    : fallback;
}

function normalizeAgentScope(scope, limit = 8) {
  const privateKeys =
    /(?:reason|analysis|chain|prompt|system|transcript|messages?|private_content)/i;
  const entries = [];
  const add = (value, prefix = '') => {
    if (entries.length >= limit) return;
    if (Array.isArray(value)) {
      value.slice(0, limit - entries.length).forEach((item) => add(item, prefix));
      return;
    }
    if (value && typeof value === 'object') {
      Object.entries(value)
        .slice(0, limit * 2)
        .forEach(([key, item]) => {
          if (entries.length >= limit || privateKeys.test(key)) return;
          const label = boundedAgentPublicText(key.replace(/[_-]+/g, ' '), 40);
          add(item, label ? `${label}：` : prefix);
        });
      return;
    }
    const text = boundedAgentPublicText(value, 180);
    if (!text) return;
    entries.push(`${prefix}${text}`.slice(0, 220));
  };
  add(scope);
  return entries;
}

function normalizeAgentActivities(rawActivities) {
  if (!Array.isArray(rawActivities)) return [];
  const bySequence = new Map();
  rawActivities.slice(-(AGENT_ACTIVITY_MAX_ITEMS * 2)).forEach((raw, index) => {
    if (!raw || typeof raw !== 'object') return;
    const kind = String(raw.kind || 'progress')
      .trim()
      .toLowerCase();
    if (!AGENT_PUBLIC_ACTIVITY_KINDS.has(kind)) return;
    const fallbackSequence = index + 1;
    const numericSequence = Number(raw.seq ?? raw.sequence);
    const seq =
      Number.isFinite(numericSequence) && numericSequence >= 0 ? numericSequence : fallbackSequence;
    const title = boundedAgentPublicText(raw.title, 120);
    const content = boundedAgentPublicText(raw.content, kind === 'stream' ? 20000 : 4000);
    const metadata = raw.metadata && typeof raw.metadata === 'object' ? raw.metadata : {};
    if (!title && !content) return;
    bySequence.set(seq, {
      seq,
      kind,
      title: title || '工作进展',
      content,
      createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
      metadata,
    });
  });
  return Array.from(bySequence.values())
    .sort((left, right) => left.seq - right.seq)
    .slice(-AGENT_ACTIVITY_MAX_ITEMS);
}

function normalizeAgentCollaboration(source, agentIds) {
  const knownAgentIds = new Set(agentIds);
  const normalizeReferences = (values) =>
    (Array.isArray(values) ? values : [])
      .map((value) => boundedAgentPublicText(value, 240))
      .filter(Boolean)
      .slice(0, 12);
  const artifacts = (Array.isArray(source.artifacts) ? source.artifacts : [])
    .slice(-40)
    .flatMap((raw) => {
      if (!raw || typeof raw !== 'object') return [];
      const senderId = boundedAgentPublicText(raw.sender_id || raw.sender_agent_id, 80);
      const recipientIds = (
        Array.isArray(raw.recipient_ids) ? raw.recipient_ids : raw.recipient_agent_ids || []
      )
        .map((value) => boundedAgentPublicText(value, 80))
        .filter((value) => knownAgentIds.has(value));
      if (!knownAgentIds.has(senderId) && senderId !== 'primary') return [];
      return [
        {
          id: boundedAgentPublicText(raw.id, 96),
          seq: Number(raw.seq ?? raw.sequence) || 0,
          createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
          senderId,
          senderName: boundedAgentPublicText(raw.sender_name, 80),
          title: boundedAgentPublicText(raw.title, 160),
          content: boundedAgentPublicText(raw.summary, 4000),
          recipientIds,
          references: normalizeReferences(raw.paths),
        },
      ];
    });
  const events = (Array.isArray(source.collaboration_events) ? source.collaboration_events : [])
    .slice(-120)
    .flatMap((raw) => {
      if (!raw || typeof raw !== 'object') return [];
      const senderId = boundedAgentPublicText(raw.sender_id || raw.sender_agent_id, 80);
      const recipientId = boundedAgentPublicText(raw.recipient_id || raw.recipient_agent_id, 80);
      if (!knownAgentIds.has(senderId) && !knownAgentIds.has(recipientId)) return [];
      return [
        {
          seq: Number(raw.seq ?? raw.sequence) || 0,
          createdAt: boundedAgentPublicText(raw.created_at || raw.timestamp, 80),
          type: boundedAgentPublicText(raw.type, 32) || 'message',
          kind: boundedAgentPublicText(raw.kind, 32) || 'message',
          senderId,
          senderName: boundedAgentPublicText(raw.sender_name, 80),
          recipientId,
          recipientName: boundedAgentPublicText(raw.recipient_name, 80),
          title: boundedAgentPublicText(raw.title, 160),
          content: boundedAgentPublicText(raw.content, 4000),
          references: normalizeReferences(raw.references),
        },
      ];
    });
  const fileClaims = (Array.isArray(source.file_claims) ? source.file_claims : [])
    .slice(0, 40)
    .flatMap((raw) => {
      if (!raw || typeof raw !== 'object') return [];
      const agentId = boundedAgentPublicText(raw.agent_id, 80);
      if (!knownAgentIds.has(agentId)) return [];
      return [
        {
          agentId,
          agentName: boundedAgentPublicText(raw.agent_name, 80),
          paths: normalizeReferences(raw.paths),
          active: Boolean(raw.active),
        },
      ];
    });
  return { artifacts, events, fileClaims };
}

function deriveAgentTeamStatus(agents, requestedStatus = '') {
  const requested = normalizeAgentStatus(requestedStatus, '');
  if (requested) return requested;
  if (agents.some((agent) => agent.status === 'running')) return 'running';
  if (agents.some((agent) => agent.status === 'waiting')) return 'waiting';
  if (agents.some((agent) => agent.status === 'failed')) return 'failed';
  if (agents.length && agents.every((agent) => AGENT_TERMINAL_STATUSES.has(agent.status))) {
    return agents.every((agent) => agent.status === 'cancelled') ? 'cancelled' : 'completed';
  }
  return 'queued';
}

function normalizeAgentTeamSnapshot(raw, conversationId = activeConversationId, messageId = 0) {
  const source = raw?.team && typeof raw.team === 'object' ? raw.team : raw;
  if (!source || !Array.isArray(source.agents)) return null;
  const normalizedConversationId = String(raw.conversation_id || conversationId || '');
  const normalizedMessageId = Number(raw.message_id || messageId || 0);
  const teamId = boundedAgentPublicText(
    source.team_id || `team-${normalizedMessageId || 'current'}`,
    80
  );
  if (!normalizedConversationId || !normalizedMessageId || !teamId) return null;

  const agentIds = new Set();
  const agents = source.agents.slice(0, AGENT_TEAM_MAX_MEMBERS).flatMap((agent, index) => {
    if (!agent || typeof agent !== 'object') return [];
    const id = boundedAgentPublicText(agent.id || agent.agent_id || `agent-${index + 1}`, 80);
    if (!id || agentIds.has(id)) return [];
    agentIds.add(id);
    const name = boundedAgentPublicText(agent.name, 48) || `子智能体 ${index + 1}`;
    return [
      {
        id,
        name,
        role: boundedAgentPublicText(agent.role, 120) || '协作任务执行',
        task: boundedAgentPublicText(agent.task, 1200) || '等待主智能体分配任务',
        status: normalizeAgentStatus(agent.status),
        currentActivity: boundedAgentPublicText(agent.current_activity, 600),
        summary: boundedAgentPublicText(agent.summary, 2000),
        result: boundedAgentPublicText(agent.result, 8000),
        error: boundedAgentPublicText(agent.error, 1600),
        startedAt: boundedAgentPublicText(agent.started_at, 80),
        endedAt: boundedAgentPublicText(agent.ended_at || agent.completed_at, 80),
        accessScope: normalizeAgentScope(
          agent.access_scope ||
            (agent.write_access ? ['可写', ...(agent.write_paths || [])] : '只读协作')
        ),
        contextScope: normalizeAgentScope(agent.context_scope || agent.context),
        dependsOn: (Array.isArray(agent.depends_on) ? agent.depends_on : [])
          .map((value) => boundedAgentPublicText(value, 80))
          .filter(Boolean)
          .slice(0, 12),
        activities: normalizeAgentActivities(agent.activities),
      },
    ];
  });
  if (!agents.length) return null;

  const numericVersion = Number(source.version || 0);
  return {
    key: agentTeamKey(normalizedConversationId, normalizedMessageId, teamId),
    conversationId: normalizedConversationId,
    messageId: normalizedMessageId,
    teamId,
    version: Number.isFinite(numericVersion) ? Math.max(0, numericVersion) : 0,
    status: deriveAgentTeamStatus(agents, source.status),
    agents,
    collaboration: normalizeAgentCollaboration(source, Array.from(agentIds)),
    element: null,
    receivedAt: Date.now(),
  };
}

function getAgentTeamSnapshot(teamKey) {
  return activeAgentTeams.get(String(teamKey || '')) || null;
}

function pruneAgentTeamSnapshots() {
  if (activeAgentTeams.size <= AGENT_TEAM_MAX_SNAPSHOTS) return;
  for (const [key, snapshot] of activeAgentTeams) {
    if (activeAgentTeams.size <= AGENT_TEAM_MAX_SNAPSHOTS) break;
    const selected = activeAgentDetail?.teamKey === key;
    const visible = snapshot.element?.isConnected;
    if (!selected && !visible && AGENT_TERMINAL_STATUSES.has(snapshot.status)) {
      activeAgentTeams.delete(key);
    }
  }
}

function agentNetworkMarkMarkup() {
  return '<span class="agent-network-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>';
}

function getAgentTeamStatusCopy(snapshot) {
  const running = snapshot.agents.filter((agent) => agent.status === 'running').length;
  const waiting = snapshot.agents.filter((agent) => agent.status === 'waiting').length;
  const completed = snapshot.agents.filter((agent) => agent.status === 'completed').length;
  if (running) return `${running} 个正在工作`;
  if (waiting) return `${waiting} 个等待协作`;
  if (completed === snapshot.agents.length) return '协作已完成';
  return AGENT_STATUS_LABELS[snapshot.status] || '等待开始';
}

function setAgentStatusClass(element, status) {
  Object.keys(AGENT_STATUS_LABELS).forEach((candidate) => {
    element.classList.toggle(`is-${candidate}`, candidate === status);
  });
}

function createAgentChip() {
  const chip = document.createElement('button');
  chip.className = 'agent-chip';
  chip.type = 'button';
  chip.setAttribute('role', 'listitem');
  chip.setAttribute('aria-controls', 'agentDetailPanel');
  chip.innerHTML = `
        ${agentNetworkMarkMarkup()}
        <span class="agent-chip-copy"><strong></strong></span>
        <span class="agent-chip-status"><span aria-hidden="true"></span></span>`;
  return chip;
}

function updateAgentChip(chip, snapshot, agent, selected) {
  const statusLabel = AGENT_STATUS_LABELS[agent.status] || agent.status;
  const activity = agent.currentActivity || agent.task;
  const titleParts = [agent.role, activity].filter(Boolean);
  chip.dataset.agentTeamKey = snapshot.key;
  chip.dataset.agentId = agent.id;
  chip.classList.toggle('is-selected', selected);
  setAgentStatusClass(chip, agent.status);
  chip.setAttribute('aria-expanded', selected ? 'true' : 'false');
  chip.setAttribute(
    'aria-label',
    [agent.name, agent.role, statusLabel, activity].filter(Boolean).join('，')
  );
  chip.title = titleParts.join(' · ');
  chip.querySelector('.agent-chip-copy strong').textContent = agent.name;
  chip.querySelector('.agent-chip-status').setAttribute('aria-label', statusLabel);
}

function renderAgentTeamCard(snapshot, animate = true) {
  if (!snapshot || snapshot.conversationId !== String(activeConversationId || '')) {
    return null;
  }
  const chatMessages = getChatRenderHost();
  if (!chatMessages) return null;
  let card = snapshot.element?.isConnected ? snapshot.element : null;
  const isNew = !card;
  if (!card) {
    card = document.createElement('section');
    card.className = 'agent-team-card';
    card.dataset.teamKey = snapshot.key;
    card.dataset.teamId = snapshot.teamId;
    card.dataset.messageId = String(snapshot.messageId);
    const chipList = document.createElement('div');
    chipList.className = 'agent-chip-list';
    chipList.setAttribute('role', 'list');
    chipList.setAttribute('aria-label', '参与协作的子智能体');
    const status = document.createElement('span');
    status.className = 'agent-team-card-status';
    status.setAttribute('aria-live', 'polite');
    card.append(chipList, status);
    const thinking = chatMessages.querySelector('#thinking');
    if (thinking) chatMessages.insertBefore(card, thinking);
    else chatMessages.appendChild(card);
    snapshot.element = card;
  }
  setAgentStatusClass(card, snapshot.status);
  const selectedAgentId =
    activeAgentDetail?.teamKey === snapshot.key ? activeAgentDetail.agentId : '';
  const chipList = card.querySelector('.agent-chip-list');
  const existingChips = new Map(
    Array.from(chipList.querySelectorAll('.agent-chip[data-agent-id]')).map((chip) => [
      chip.dataset.agentId,
      chip,
    ])
  );
  const currentAgentIds = new Set(snapshot.agents.map((agent) => agent.id));
  existingChips.forEach((chip, agentId) => {
    if (!currentAgentIds.has(agentId)) chip.remove();
  });
  snapshot.agents.forEach((agent, index) => {
    const chip = existingChips.get(agent.id) || createAgentChip();
    updateAgentChip(chip, snapshot, agent, selectedAgentId === agent.id);
    const currentAtIndex = chipList.children[index];
    if (currentAtIndex !== chip) {
      chipList.insertBefore(chip, currentAtIndex || null);
    }
  });
  card.querySelector('.agent-team-card-status').textContent = getAgentTeamStatusCopy(snapshot);
  if (isNew) {
    if (animate) requestAnimationFrame(() => card.classList.add('is-visible'));
    else card.classList.add('is-visible');
    if (!isRestoringConversation) followChatOutput(chatMessages);
  } else {
    card.classList.add('is-visible');
  }
  return card;
}

function updateAgentTeamSnapshot(
  raw,
  conversationId = activeConversationId,
  messageId = 0,
  { animate = true } = {}
) {
  const normalized = normalizeAgentTeamSnapshot(raw, conversationId, messageId);
  if (!normalized) return null;
  const previous = activeAgentTeams.get(normalized.key);
  if (previous && normalized.version <= previous.version) {
    if (
      previous.conversationId === String(activeConversationId || '') &&
      !previous.element?.isConnected
    ) {
      renderAgentTeamCard(previous, false);
    }
    return previous;
  }
  normalized.element = previous?.element || null;
  activeAgentTeams.set(normalized.key, normalized);
  pruneAgentTeamSnapshots();
  renderAgentTeamCard(normalized, animate);
  if (activeAgentDetail?.teamKey === normalized.key) {
    if (normalized.agents.some((agent) => agent.id === activeAgentDetail.agentId)) {
      renderAgentDetail(normalized, activeAgentDetail.agentId);
    } else {
      closeAgentDetail({ restoreFocus: false });
    }
  }
  return normalized;
}

function detachAgentTeamCardsForConversation(conversationId) {
  const id = String(conversationId || '');
  activeAgentTeams.forEach((snapshot) => {
    if (snapshot.conversationId === id) snapshot.element = null;
  });
}

function clearConversationAgentTeams(conversationId) {
  const id = String(conversationId || '');
  for (const [key, snapshot] of activeAgentTeams) {
    if (snapshot.conversationId === id) activeAgentTeams.delete(key);
  }
  if (activeAgentDetail) {
    const selected = getAgentTeamSnapshot(activeAgentDetail.teamKey);
    if (!selected || selected.conversationId === id) {
      closeAgentDetail({ restoreFocus: false });
    }
  }
}

function formatAgentActivityTime(value) {
  const source = String(value || '').trim();
  if (!source) return '';
  const date = new Date(source);
  if (Number.isNaN(date.getTime())) return boundedAgentPublicText(source, 24);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function createAgentOutputMessage(host, content, { commentary = false, error = false } = {}) {
  const message = document.createElement('div');
  message.className = `message ai${error ? ' error' : ''}`;
  message.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-wrapper">
            <div class="message-bubble">${renderMarkdown(content)}</div>
        </div>`;
  if (commentary) decorateCommentaryMessage(message);
  host.appendChild(message);
  message.classList.add('is-visible');
  return message;
}

function createAgentStreamState(host, streamId) {
  return {
    host,
    element: null,
    bubble: null,
    thinkingCard: null,
    thinkingBody: null,
    content: '',
    streamId,
    thinkingCondensed: false,
    thinkingStartedAt: Date.now(),
    thinkingDurationMs: null,
    thinkingTimer: null,
    thinkingClosed: false,
    isCommentary: false,
    thinkingDetectionComplete: false,
    voiceDisabled: true,
  };
}

function finalizeAgentStream(state, target, durationMs = null) {
  const content = state.content || '';
  if (target === 'discard') {
    state.element?.remove();
    state.thinkingCard?.remove();
    return;
  }
  const { thoughts, answer } = splitThinkingContent(content);
  if (target === 'thinking') {
    state.element?.remove();
    const thought = thoughts[thoughts.length - 1] || answer || content;
    if (state.thinkingCard) {
      state.thinkingBody.innerHTML = renderMarkdown(thought);
      state.thinkingDurationMs = durationMs;
      completeStreamingThinking(state);
      condenseThinkingCard(state.thinkingCard, true);
    } else if (thought.trim()) {
      addThinkingCard(thought, null, false, false, true, durationMs, state.host);
    }
    return;
  }
  if (state.thinkingCard) {
    const thought = thoughts[thoughts.length - 1] || '';
    if (thought) state.thinkingBody.innerHTML = renderMarkdown(thought);
    state.thinkingDurationMs = durationMs;
    completeStreamingThinking(state);
    condenseThinkingCard(state.thinkingCard, true);
  }
  const visible = answer.trim() || (thoughts.length ? '' : content.trim());
  if (!state.element && visible) createStreamingResponse(state.streamId, state);
  if (state.element) {
    state.element.classList.remove('streaming-response');
    state.bubble.innerHTML = visible ? renderMarkdown(visible) : '';
    if (target === 'commentary') decorateCommentaryMessage(state.element);
  }
}

function renderAgentStream(outputState, activity) {
  const metadata = activity.metadata || {};
  const streamId = String(metadata.stream_id || `activity-${activity.seq}`);
  let state = outputState.streams.get(streamId);
  if (!state) {
    state = createAgentStreamState(outputState.host, streamId);
    outputState.streams.set(streamId, state);
  }
  state.content = activity.content;
  state.thinkingDurationMs = Number.isFinite(Number(metadata.thinking_duration_ms))
    ? Number(metadata.thinking_duration_ms)
    : state.thinkingDurationMs;
  state.thinkingClosed = metadata.phase === 'end';
  renderStreamingState(state);
  if (metadata.phase === 'end') {
    finalizeAgentStream(state, String(metadata.target || 'final'), state.thinkingDurationMs);
  }
}

function renderAgentTool(outputState, activity) {
  const metadata = activity.metadata || {};
  const key = String(metadata.prepared_tool_call_id || metadata.tool_call_id || activity.seq);
  const phase = String(metadata.phase || 'end');
  let execution = outputState.tools.get(key);
  const event = {
    tool: String(metadata.tool || activity.title || 'Tool'),
    params: metadata.params || {},
    target: String(metadata.target || ''),
    result: String(metadata.result || activity.content || ''),
    duration_ms: Number(metadata.duration_ms || 0),
  };
  if (phase !== 'end') {
    if (!execution) {
      const element = document.createElement('div');
      element.className = 'tool-execution tool-execution-running';
      element.innerHTML = `
                <div class="tool-card tool-card-running" role="status" aria-live="polite">
                    <div class="tool-header tool-header-running">
                        <span class="tool-progress-spinner" aria-hidden="true"><span></span></span>
                        <span class="tool-name"></span>
                        <span class="tool-summary tool-live-summary"></span>
                        <span class="tool-elapsed">进行中</span>
                    </div>
                    <div class="tool-progress-track" aria-hidden="true"><span></span></div>
                </div>`;
      outputState.host.appendChild(element);
      element.classList.add('is-visible');
      execution = { element, event };
      outputState.tools.set(key, execution);
    }
    execution.event = event;
    execution.element.querySelector('.tool-name').textContent = event.tool;
    execution.element.querySelector('.tool-live-summary').textContent = primaryToolSummary(
      phase === 'preparing'
        ? getToolPreparingCopy(event.tool)
        : getToolProgressCopy(event.tool, event.params),
      getToolTarget(event.tool, event.params, event.target)
    );
    return;
  }
  const failed = Boolean(metadata.failed) || toolResultFailed(event.result);
  const target = getToolTarget(event.tool, event.params, event.target);
  const element = execution?.element || document.createElement('div');
  element.classList.remove(
    'tool-execution-running',
    'tool-execution-error',
    'tool-execution-complete'
  );
  element.classList.add(
    'tool-execution',
    failed ? 'tool-execution-error' : 'tool-execution-complete'
  );
  element.innerHTML = `
        <details class="tool-card">
            <summary class="tool-header">
                <span class="tool-status-icon" aria-hidden="true">${failed ? '!' : '✓'}</span>
                <span class="tool-name">${escapeHtml(event.tool)}</span>
                <span class="tool-summary">${escapeHtml(
                  primaryToolSummary(
                    `${failed ? '工具调用失败' : '工具调用完成'}${event.duration_ms > 0 ? ` · ${formatToolDuration(event.duration_ms)}` : ''}`,
                    target
                  )
                )}</span>
                <svg class="tool-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
            </summary>
            <div class="tool-result">${formatContent(event.result.substring(0, 1600))}</div>
        </details>`;
  if (!execution) {
    outputState.host.appendChild(element);
    element.classList.add('is-visible');
  }
  outputState.tools.set(key, { element, event });
}

function updateAgentActivityList(activityList, snapshot, agent) {
  const owner = `${snapshot.key}:${agent.id}`;
  if (activityList.dataset.agentOwner !== owner) {
    activityList.replaceChildren();
    activityList.dataset.agentOwner = owner;
    activityList._agentOutputState = {
      host: activityList,
      streams: new Map(),
      tools: new Map(),
      signatures: new Map(),
    };
  }
  const outputState = activityList._agentOutputState;
  if (!agent.activities.length) {
    if (!activityList.querySelector('.agent-activity-empty')) {
      const empty = document.createElement('p');
      empty.className = 'agent-activity-empty';
      empty.textContent = '等待子智能体开始输出';
      activityList.replaceChildren(empty);
    }
    return false;
  }

  activityList.querySelector('.agent-activity-empty')?.remove();
  let changed = false;
  agent.activities.forEach((activity) => {
    const seq = String(activity.seq);
    const signature = JSON.stringify([
      activity.kind,
      activity.title,
      activity.content,
      activity.createdAt,
      activity.metadata,
    ]);
    if (outputState.signatures.get(seq) === signature) return;
    outputState.signatures.set(seq, signature);
    if (activity.kind === 'stream') renderAgentStream(outputState, activity);
    else if (activity.kind === 'tool_event') renderAgentTool(outputState, activity);
    else if (activity.kind === 'error') {
      createAgentOutputMessage(activityList, activity.content, { error: true });
    } else if (activity.content) {
      createAgentOutputMessage(activityList, activity.content, { commentary: true });
    }
    changed = true;
  });
  const hasFinalStream = agent.activities.some(
    (activity) =>
      activity.kind === 'stream' &&
      activity.metadata?.phase === 'end' &&
      ['final', 'commentary'].includes(String(activity.metadata?.target || ''))
  );
  if (agent.result && !hasFinalStream) {
    const resultSignature = `result:${agent.result}`;
    if (outputState.signatures.get('__result__') !== resultSignature) {
      outputState.signatures.set('__result__', resultSignature);
      createAgentOutputMessage(activityList, agent.result);
      changed = true;
    }
  }
  return changed;
}

function syncSelectedAgentChip() {
  document.querySelectorAll('.agent-chip[data-agent-team-key][data-agent-id]').forEach((chip) => {
    const selected = Boolean(
      activeAgentDetail &&
      chip.dataset.agentTeamKey === activeAgentDetail.teamKey &&
      chip.dataset.agentId === activeAgentDetail.agentId
    );
    chip.classList.toggle('is-selected', selected);
    chip.setAttribute('aria-expanded', selected ? 'true' : 'false');
  });
}

function renderAgentCollaboration(snapshot, agent) {
  const list = document.getElementById('agentCollaborationList');
  const count = document.getElementById('agentCollaborationCount');
  if (!list || !count) return false;
  const collaboration = snapshot.collaboration || { artifacts: [], events: [], fileClaims: [] };
  const entries = [
    ...collaboration.events
      .filter((event) => event.senderId === agent.id || event.recipientId === agent.id)
      .map((event) => ({ ...event, entryType: 'message' })),
    ...collaboration.artifacts
      .filter(
        (artifact) => artifact.senderId === agent.id || artifact.recipientIds.includes(agent.id)
      )
      .map((artifact) => ({ ...artifact, entryType: 'artifact' })),
  ]
    .sort((left, right) => (left.seq || 0) - (right.seq || 0))
    .slice(-24);
  const ownClaim = collaboration.fileClaims.find((claim) => claim.agentId === agent.id);
  const signature = JSON.stringify({
    entries,
    claim: ownClaim || null,
    dependsOn: agent.dependsOn,
  });
  count.textContent = `${entries.length + (ownClaim ? 1 : 0)} 项`;
  if (list.dataset.renderSignature === signature) return false;
  list.replaceChildren();
  if (agent.dependsOn.length) {
    const dependency = document.createElement('div');
    dependency.className = 'agent-collaboration-item is-dependency';
    dependency.innerHTML = '<strong>等待依赖</strong>';
    const copy = document.createElement('p');
    copy.textContent = agent.dependsOn.join('、');
    dependency.append(copy);
    list.appendChild(dependency);
  }
  if (ownClaim?.paths.length) {
    const claim = document.createElement('div');
    claim.className = 'agent-collaboration-item is-claim';
    claim.innerHTML = `<strong>${ownClaim.active ? '已占用文件范围' : '已释放文件范围'}</strong>`;
    const copy = document.createElement('p');
    copy.textContent = ownClaim.paths.join('、');
    claim.append(copy);
    list.appendChild(claim);
  }
  entries.forEach((entry) => {
    const item = document.createElement('div');
    item.className = `agent-collaboration-item is-${entry.entryType}`;
    const isArtifact = entry.entryType === 'artifact';
    const direction = isArtifact
      ? `${entry.senderName || '协作成员'} 发布工件`
      : entry.senderId === agent.id
        ? `发送给 ${entry.recipientName || '协作成员'}`
        : `${entry.senderName || '协作成员'} 发来${entry.kind === 'handoff' ? '交接' : '消息'}`;
    const heading = document.createElement('strong');
    heading.textContent = isArtifact ? entry.title || '共享工件' : direction;
    const content = document.createElement('p');
    content.textContent = entry.content || entry.title || '协作更新';
    item.append(heading, content);
    if (entry.references?.length) {
      const references = document.createElement('span');
      references.textContent = entry.references.join('、');
      item.append(references);
    }
    list.appendChild(item);
  });
  if (!list.childElementCount) {
    const empty = document.createElement('p');
    empty.className = 'agent-activity-empty';
    empty.textContent = '暂无定向消息、交接或共享工件';
    list.appendChild(empty);
  }
  list.dataset.renderSignature = signature;
  return true;
}

function renderAgentDetail(snapshot, agentId) {
  const agent = snapshot?.agents.find((item) => item.id === String(agentId || ''));
  if (!snapshot || !agent) return false;
  const scroll = document.getElementById('agentDetailScroll');
  const previousScrollTop = Number(scroll?.scrollTop || 0);
  const distanceFromBottom = scroll
    ? scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight
    : 0;
  const status = document.getElementById('agentDetailStatus');
  status.textContent = AGENT_STATUS_LABELS[agent.status] || agent.status;
  status.className = `agent-detail-status is-${agent.status}`;
  document.getElementById('agentDetailAccess').textContent = agent.accessScope[0] || '隔离上下文';
  document.getElementById('agentDetailPanelTitle').textContent = agent.name;
  document.getElementById('agentDetailName').textContent = agent.name;
  document.getElementById('agentDetailRole').textContent = agent.currentActivity
    ? `${agent.role} · ${agent.currentActivity}`
    : agent.role;
  document.getElementById('agentDetailTask').textContent = agent.task;

  const contextScope = document.getElementById('agentDetailContextScope');
  const scopeItems = [
    ...(agent.contextScope.length
      ? agent.contextScope.map((item) => ({ label: '可见上下文', value: item }))
      : [{ label: '可见上下文', value: '主智能体分配说明与必要项目资料' }]),
    ...(agent.accessScope.length
      ? agent.accessScope.map((item) => ({ label: '工具范围', value: item }))
      : [{ label: '工具范围', value: '仅使用本任务明确授权的能力' }]),
    ...(agent.dependsOn.length ? [{ label: '任务依赖', value: agent.dependsOn.join('、') }] : []),
    { label: '隔离规则', value: '不共享主对话历史与兄弟智能体工作记忆' },
  ].slice(0, 12);
  const contextSignature = JSON.stringify(scopeItems);
  if (contextScope.dataset.renderSignature !== contextSignature) {
    contextScope.replaceChildren(
      ...scopeItems.map((scopeItem) => {
        const item = document.createElement('div');
        item.className = 'agent-context-item';
        const label = document.createElement('span');
        label.textContent = scopeItem.label;
        const value = document.createElement('strong');
        value.textContent = scopeItem.value;
        item.append(label, value);
        return item;
      })
    );
    contextScope.dataset.renderSignature = contextSignature;
  }

  const activityList = document.getElementById('agentActivityList');
  const collaborationChanged = renderAgentCollaboration(snapshot, agent);
  document.getElementById('agentDetailActivityCount').textContent = `${agent.activities.length} 条`;
  const activityChanged = updateAgentActivityList(activityList, snapshot, agent);

  const resultSection = document.getElementById('agentResultSection');
  resultSection.hidden = true;
  const resultChanged = false;
  const errorSection = document.getElementById('agentErrorSection');
  errorSection.hidden = true;

  if (scroll && (activityChanged || collaborationChanged || resultChanged)) {
    if (agentDetailScrollFrame) cancelAnimationFrame(agentDetailScrollFrame);
    agentDetailScrollFrame = requestAnimationFrame(() => {
      agentDetailScrollFrame = 0;
      if (distanceFromBottom < 48) scroll.scrollTop = scroll.scrollHeight;
      else scroll.scrollTop = previousScrollTop;
    });
  }
  return true;
}

function openAgentDetail(teamKey, agentId, trigger = null) {
  const snapshot = getAgentTeamSnapshot(teamKey);
  if (!snapshot || !snapshot.agents.some((agent) => agent.id === String(agentId || ''))) {
    return;
  }
  closeChangeReview({ restoreFocus: false });
  const panel = document.getElementById('agentDetailPanel');
  if (!panel) return;
  const chatMessages = document.getElementById('chatMessages');
  const distanceFromBottom = chatMessages
    ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
    : 0;
  const previousFocus = activeAgentDetail?.lastFocus;
  activeAgentDetail = {
    teamKey: snapshot.key,
    agentId: String(agentId),
    lastFocus: previousFocus?.isConnected ? previousFocus : trigger || document.activeElement,
  };
  renderAgentDetail(snapshot, agentId);
  syncSelectedAgentChip();
  panel.removeAttribute('aria-hidden');
  document.body.classList.add('agent-detail-open');
  notifyParentAgentDetail(true);
  setSidebarPanelWidth(getSavedSidebarPanelWidth(), { persist: false });
  setAgentDetailPanelWidth(getSavedAgentDetailPanelWidth(), { persist: false });
  requestAnimationFrame(() => panel.classList.add('is-open'));
  restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
}

function closeAgentDetail({ restoreFocus = true } = {}) {
  const panel = document.getElementById('agentDetailPanel');
  const chatMessages = document.getElementById('chatMessages');
  const distanceFromBottom = chatMessages
    ? chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight
    : 0;
  const focusTarget = activeAgentDetail?.lastFocus;
  if (agentDetailScrollFrame) cancelAnimationFrame(agentDetailScrollFrame);
  agentDetailScrollFrame = 0;
  panel?.classList.remove('is-open');
  panel?.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('agent-detail-open');
  notifyParentAgentDetail(false);
  activeAgentDetail = null;
  syncSelectedAgentChip();
  setSidebarPanelWidth(getSavedSidebarPanelWidth(), { persist: false });
  restoreChatAfterReviewLayout(chatMessages, distanceFromBottom);
  if (restoreFocus && focusTarget?.isConnected) focusTarget.focus({ preventScroll: true });
}

function handleAgentTeamClick(event) {
  const chip = event.target.closest('.agent-chip[data-agent-team-key][data-agent-id]');
  if (!chip) return false;
  openAgentDetail(chip.dataset.agentTeamKey, chip.dataset.agentId, chip);
  return true;
}

function markAgentTeamsTerminal(conversationId, messageId, status) {
  const normalizedStatus = normalizeAgentStatus(status, 'cancelled');
  if (!AGENT_TERMINAL_STATUSES.has(normalizedStatus)) return;
  const id = String(conversationId || '');
  const targetMessageId = Number(messageId || 0);
  activeAgentTeams.forEach((snapshot) => {
    if (snapshot.conversationId !== id || snapshot.messageId !== targetMessageId) return;
    snapshot.status = normalizedStatus;
    snapshot.agents = snapshot.agents.map((agent) =>
      AGENT_TERMINAL_STATUSES.has(agent.status)
        ? agent
        : {
            ...agent,
            status: normalizedStatus,
            currentActivity: normalizedStatus === 'failed' ? '协作已中断' : '任务已停止',
          }
    );
    renderAgentTeamCard(snapshot, false);
    if (activeAgentDetail?.teamKey === snapshot.key) {
      renderAgentDetail(snapshot, activeAgentDetail.agentId);
    }
  });
}

function getExecutionStateText(state) {
  if (!state) return '正在执行';
  if (state.awaitingQuestion) return '等待回答';
  if (state.awaitingApproval) return '等待确认';
  if (state.stopping) return '正在停止';
  return '正在执行';
}

function hasVisibleLiveActivity() {
  return Boolean(
    document.getElementById('thinking') ||
    document.querySelector('.streaming-response') ||
    document.querySelector('.tool-execution-running') ||
    document.querySelector('.compression-activity.is-running') ||
    document.querySelector('.approval-container') ||
    document.querySelector('.question-prompt:not(.is-submitted)')
  );
}

function restoreTrackedExecutionActivity(state) {
  if (!state || state.outputStopped) return false;
  let restored = false;
  state.streamContents.forEach((content, streamId) => {
    if (!content) return;
    const existing = streamingResponses.get(String(streamId));
    if (existing) {
      cancelStreamingRender(existing);
      stopStreamingThinkingTimer(existing);
      existing.element?.remove();
      existing.thinkingCard?.remove();
      streamingResponses.delete(String(streamId));
    }
    appendStreamingResponse(streamId, content, state.thinkingStartByStream?.get(streamId) || 0);
    restored = true;
  });
  if (state.activeToolEvent) {
    startToolExecution(
      state.activeToolEvent,
      state.messageId,
      state.activeToolEvent.type === 'tool_preparing'
    );
    restored = true;
  }
  if (state.activeCompressionEvent) {
    startCompressionActivity(state.activeCompressionEvent, state.messageId);
    restored = true;
  }
  return restored;
}

function resetTrackedExecutionActivity(state) {
  if (!state) return;
  state.streamContents.clear();
  state.thinkingStartByStream?.clear();
  state.activeToolEvent = null;
  state.activeCompressionEvent = null;
}

function trackExecutionResult(state, result) {
  if (!state || !result) return;
  const streamId = String(result.stream_id || state.messageId || '');
  if (result.type === 'stream' && streamId) {
    state.streamContents.set(
      streamId,
      `${state.streamContents.get(streamId) || ''}${String(result.content || '')}`
    );
  } else if (result.type === 'stream_end' && streamId) {
    state.streamContents.delete(streamId);
    state.thinkingStartByStream?.delete(streamId);
  } else if (result.type === 'tool_preparing' || result.type === 'tool_start') {
    state.activeToolEvent = { ...result };
  } else if (result.type === 'tool') {
    state.activeToolEvent = null;
  } else if (result.type === 'compression_start') {
    state.activeCompressionEvent = { ...result };
  } else if (result.type === 'compression_progress') {
    state.activeCompressionEvent = {
      ...(state.activeCompressionEvent || {}),
      ...result,
    };
  } else if (result.type === 'compression_end') {
    state.activeCompressionEvent = null;
  } else if (result.type === 'pending_question') {
    state.awaitingQuestion = true;
    state.awaitingApproval = false;
    state.activeToolEvent = null;
  } else if (result.type === 'pending_approval') {
    state.awaitingApproval = true;
    state.awaitingQuestion = false;
    state.activeToolEvent = null;
  } else if (result.type === 'question_answered') {
    state.awaitingQuestion = false;
  }
}
