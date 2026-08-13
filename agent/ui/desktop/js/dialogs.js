// Custom Input Dialog
let inputDialogResolve = null;

function showInputDialog(title, defaultValue = '') {
  return new Promise((resolve) => {
    if (inputDialogResolve) inputDialogResolve(null);
    inputDialogResolve = resolve;
    lastFocusedElement = document.activeElement;
    document.getElementById('inputDialogTitle').textContent = title;
    const input = document.getElementById('inputDialogInput');
    input.value = defaultValue;
    input.placeholder = '';
    document.getElementById('inputDialog').classList.add('active');
    input.focus();
    input.select();

    // Enter 键提交
    input.onkeypress = (e) => {
      if (e.key === 'Enter') {
        confirmInputDialog();
      }
    };
  });
}

function closeInputDialog() {
  document.getElementById('inputDialog').classList.remove('active');
  if (inputDialogResolve) {
    inputDialogResolve(null);
    inputDialogResolve = null;
  }
  lastFocusedElement?.focus?.();
}

function confirmInputDialog() {
  const value = document.getElementById('inputDialogInput').value;
  document.getElementById('inputDialog').classList.remove('active');
  if (inputDialogResolve) {
    inputDialogResolve(value || null);
    inputDialogResolve = null;
  }
  lastFocusedElement?.focus?.();
}

// Custom Confirm Dialog
let confirmDialogResolve = null;

function showConfirmDialog(message) {
  return new Promise((resolve) => {
    if (confirmDialogResolve) confirmDialogResolve(false);
    confirmDialogResolve = resolve;
    lastFocusedElement = document.activeElement;
    document.getElementById('confirmDialogMessage').textContent = message;
    document.getElementById('confirmDialog').classList.add('active');
    document.querySelector('#confirmDialog .btn-save')?.focus();
  });
}

function closeConfirmDialog() {
  document.getElementById('confirmDialog').classList.remove('active');
  if (confirmDialogResolve) {
    confirmDialogResolve(false);
    confirmDialogResolve = null;
  }
  lastFocusedElement?.focus?.();
}

function confirmConfirmDialog() {
  document.getElementById('confirmDialog').classList.remove('active');
  if (confirmDialogResolve) {
    confirmDialogResolve(true);
    confirmDialogResolve = null;
  }
  lastFocusedElement?.focus?.();
}

// Static UI wiring (index.html dialog buttons, no inline handlers).
function bindDialogStaticEvents() {
  const bind = (id, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  };
  bind('closeInputDialogButton', closeInputDialog);
  bind('inputDialogCancelButton', closeInputDialog);
  bind('inputDialogConfirmButton', confirmInputDialog);
  bind('closeConfirmDialogButton', closeConfirmDialog);
  bind('confirmDialogCancelButton', closeConfirmDialog);
  bind('confirmDialogConfirmButton', confirmConfirmDialog);
}
