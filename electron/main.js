'use strict';

const { app, BrowserWindow, dialog, Menu } = require('electron');
const { spawn, execFileSync } = require('child_process');
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

  const BACKEND = path.resolve(
    app.getAppPath(),
    '..',
    'backend',
    'jcodex-server',
    process.platform === 'win32' ? 'jcodex-server.exe' : 'jcodex-server'
  );
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
      autoHideMenuBar: true,
      icon: process.platform === 'win32'
        ? path.join(__dirname, 'build', 'icon.ico')
        : path.join(__dirname, 'build', 'icon.icns'),
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
    killStaleBackend();
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
    try {
      require('fs').writeFileSync(backendPidFile(), String(pyProc.pid));
    } catch (_e) {
      /* ignore */
    }
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

  function backendPidFile() {
    return path.join(DATA_DIR, 'desktop_backend.pid');
  }

  function backendPidIsOurs(pid) {
    try {
      if (process.platform === 'win32') {
        const out = execFileSync(
          'tasklist',
          ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'],
          { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
        );
        return /jcodex-server\.exe/i.test(String(out));
      }
      const out = execFileSync(
        'ps',
        ['-p', String(pid), '-o', 'comm='],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
      );
      return /jcodex-server/i.test(String(out));
    } catch (_e) {
      return false;
    }
  }

  function killStaleBackend() {
    // 上次异常退出（窗口关闭但后端未退出）会留下 jcodex-server 进程；
    // 两个后端同时写同一数据目录会导致对话/记忆索引竞态损坏，因此
    // 启动前先清理自己的残留后端（按 PID + 进程名双重校验，避免误杀）。
    const pidFile = backendPidFile();
    let oldPid = null;
    try {
      oldPid = parseInt(require('fs').readFileSync(pidFile, 'utf8').trim(), 10);
    } catch (_e) {
      /* no pid file yet */
    }
    if (oldPid && Number.isInteger(oldPid) && oldPid > 0 && backendPidIsOurs(oldPid)) {
      try {
        if (process.platform === 'win32') {
          execFileSync('taskkill', ['/PID', String(oldPid), '/T', '/F'], {
            stdio: 'ignore',
          });
        } else {
          process.kill(oldPid, 'SIGTERM');
        }
      } catch (_e) {
        /* process already gone */
      }
    }
    try {
      require('fs').unlinkSync(pidFile);
    } catch (_e) {
      /* ignore */
    }
  }

  app.whenReady().then(() => {
    if (!require('fs').existsSync(BACKEND)) {
      dialog.showErrorBox('JCodex 启动失败', '未找到后端组件，应用可能已损坏。');
      app.quit();
      return;
    }
    // Windows/Linux 上移除默认的 File/Edit/View 菜单栏；macOS 保留系统菜单。
    if (process.platform !== 'darwin') {
      Menu.setApplicationMenu(null);
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
    try {
      require('fs').unlinkSync(backendPidFile());
    } catch (_e) {
      /* ignore */
    }
  });
}
