// Quick Commands Popup
const quickCommands = [
  { cmd: '/clear', label: 'Clear conversation', action: 'clear' },
  { cmd: '/compact', label: 'Compress memory', action: 'compact' },
];

function showQuickCommands() {
  let popup = document.getElementById('quickCommandsPopup');
  if (!popup) {
    popup = document.createElement('div');
    popup.id = 'quickCommandsPopup';
    popup.className = 'quick-commands-popup';

    const inputArea = document.querySelector('.input-area');
    inputArea.appendChild(popup);
  }

  const messageInput = document.getElementById('messageInput');
  const filter = messageInput.value.toLowerCase();

  const filtered = quickCommands.filter(
    (c) => c.cmd.startsWith(filter) || c.label.toLowerCase().includes(filter)
  );

  popup.innerHTML = filtered
    .map(
      (c, i) =>
        `<div class="quick-command-item" data-index="${i}" data-cmd="${c.cmd}" data-prompt="${c.prompt}" data-action="${c.action || ''}">
            <span class="quick-cmd">${c.cmd}</span>
            <span class="quick-label">${c.label}</span>
        </div>`
    )
    .join('');

  // Add click handlers
  popup.querySelectorAll('.quick-command-item').forEach((item) => {
    item.addEventListener('click', async () => {
      const cmd = item.dataset.cmd;
      const input = document.getElementById('messageInput');

      hideQuickCommands();
      input.value = cmd;

      // Send as user message (let AI handle it)
      sendMessage();
    });
  });

  popup.style.display = 'block';
}

function hideQuickCommands() {
  const popup = document.getElementById('quickCommandsPopup');
  if (popup) popup.style.display = 'none';
}
