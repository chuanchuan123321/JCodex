'use strict';

const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const STARTUP_TIMEOUT_MS = 180000;

let pyProc = null;
let mainWindow = null;
let quitting = false;
let serverPort = null;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  const BACKEND = path.resolve(app.getAppPath(), '..', 'backend', 'jcodex-server', 'jcodex-server');
  const DATA_DIR = app.getPath('userData');

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function fetchToken(base) {
    return new Promise((resolve) => {
      const req = http.get(`${base}/`, (res) => {
        res.resume();
        const cookies = res.headers['set-cookie'] || [];
        for (const cookie of cookies) {
          const m = cookie.match(/jcodex_eel_session=([^;]+)/);
          if (m) {
            resolve(m[1]);
            return;
          }
        }
        resolve(null);
      });
      req.on('error', () => resolve(null));
    });
  }

  async function openWindow(port) {
    const base = `http://127.0.0.1:${port}`;
    let token = null;
    for (let i = 0; i < 40; i++) {
      token = await fetchToken(base);
      if (token) break;
      await sleep(500);
    }

    mainWindow = new BrowserWindow({
      width: 1440,
      height: 900,
      minWidth: 900,
      minHeight: 600,
      show: false,
      title: 'JCodex',
      icon: path.join(__dirname, 'build', 'icon.icns'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
      },
    });

    mainWindow.once('ready-to-show', () => {
      mainWindow.show();
    });
    mainWindow.webContents.on('did-fail-load', (_e, code, desc) => {
      console.error('[web] load failed', code, desc);
    });
    mainWindow.on('closed', () => {
      mainWindow = null;
      if (pyProc) {
        quitting = true;
        pyProc.kill();
      }
      app.quit();
    });

    const url = token ? `${base}/index.html#eel_session=${token}` : `${base}/`;
    console.log('[web] loading', base);
    await mainWindow.loadURL(url);
  }

  function startBackend() {
    const portFile = path.join(DATA_DIR, 'desktop_port.txt');
    try {
      require('fs').unlinkSync(portFile);
    } catch (_e) {
      /* ignore */
    }
    pyProc = spawn(BACKEND, [], {
      env: {
        ...process.env,
        JCODEX_DATA_DIR: DATA_DIR,
        MINIBOT_DESKTOP_MODE: 'server',
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    pyProc.stdout.on('data', (d) => {
      console.log('[py]', String(d).trim());
    });
    pyProc.stderr.on('data', (d) => console.error('[py]', String(d).trim()));
    pyProc.on('exit', (code) => {
      console.log('[py] exited with code', code);
      if (!quitting && mainWindow) {
        dialog.showErrorBox('JCodex 已退出', '本地服务意外停止，请重新打开应用。');
        app.quit();
      }
      pyProc = null;
    });
  }

  app.whenReady().then(() => {
    if (!require('fs').existsSync(BACKEND)) {
      dialog.showErrorBox('JCodex 启动失败', '未找到后端组件，应用可能已损坏。');
      app.quit();
      return;
    }
    startBackend();
    const portFile = path.join(DATA_DIR, 'desktop_port.txt');
    const startedAt = Date.now();
    const poll = setInterval(() => {
      if (serverPort) {
        clearInterval(poll);
        return;
      }
      if (Date.now() - startedAt > STARTUP_TIMEOUT_MS) {
        clearInterval(poll);
        dialog.showErrorBox('JCodex 启动失败', '后端启动超时，请重试。');
        if (pyProc) {
          quitting = true;
          pyProc.kill();
        }
        app.quit();
        return;
      }
      try {
        const p = parseInt(require('fs').readFileSync(portFile, 'utf8').trim(), 10);
        if (Number.isInteger(p) && p > 0 && p < 65536) {
          serverPort = p;
          console.log('[py] server port', serverPort);
          openWindow(serverPort);
        }
      } catch (_e) {
        /* port file not ready yet */
      }
    }, 500);
  });

  app.on('window-all-closed', () => {
    if (pyProc) {
      quitting = true;
      pyProc.kill();
    }
    app.quit();
  });

  app.on('before-quit', () => {
    if (pyProc) {
      quitting = true;
      pyProc.kill();
    }
  });
}
