const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const readline = require('readline');

let mainWindow;
let tray;
let pythonProcess = null;
// Set YUKI_DEV=1 environment variable to use Vite dev server (localhost:5173)
// Without it, always loads from dist/renderer (production build)
const isDev = process.env.YUKI_DEV === '1';


// ── Python Backend Spawner ────────────────────────────────────────────────────
function startPython() {
  const projectRoot = path.join(__dirname, '..');

  // Try .venv first (project venv), then system python
  const venvPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');
  const systemPython = 'python';
  
  // Script: backend/assistant.py is the real entry point
  const scriptPath = path.join(projectRoot, 'backend', 'assistant.py');

  const pythonCmd = require('fs').existsSync(venvPython) ? venvPython : systemPython;

  console.log(`[Yuki] Starting Python backend: ${pythonCmd} ${scriptPath}`);

  pythonProcess = spawn(pythonCmd, [scriptPath], {
    cwd: projectRoot,
    env: { ...process.env },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  // ── stdout → Electron IPC ──────────────────────────────────────────────────
  const rl = readline.createInterface({ input: pythonProcess.stdout });
  rl.on('line', (line) => {
    try {
      const msg = JSON.parse(line.trim());
      console.log('[Yuki Python →]', JSON.stringify(msg));
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('yuki:state', msg);
      }
    } catch (e) {
      console.log('[Python stdout]', line);
    }
  });

  // Log stderr for debugging
  pythonProcess.stderr.on('data', (data) => {
    console.error('[Python stderr]', data.toString().trim());
  });

  pythonProcess.on('exit', (code) => {
    console.log(`[Yuki] Python exited with code ${code}`);
    // Notify renderer so UI shows feedback rather than silently freezing
    if (code !== 0 && code !== null) {
      const errMsg = code === 1
        ? 'Backend crashed. Is Ollama running? Check the console for details.'
        : `Backend stopped (exit code ${code}).`;
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('yuki:state', {
          type: 'error',
          text: errMsg,
        });
      }
    }
    pythonProcess = null;
  });
}

// ── Send message to Python via stdin ─────────────────────────────────────────
function sendToPython(msg) {
  if (pythonProcess && pythonProcess.stdin && !pythonProcess.stdin.destroyed) {
    pythonProcess.stdin.write(JSON.stringify(msg) + '\n');
  }
}

// ── Window ─────────────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 300,
    minHeight: 100,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: false,
    skipTaskbar: false,
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    // Check if we were launched at startup with --hidden
    if (!process.argv.includes('--hidden')) {
      mainWindow.show();
    }
    
    // Load history
    try {
      const fs = require('fs');
      const historyPath = path.join(app.getPath('userData'), 'yuki_history.json');
      if (fs.existsSync(historyPath)) {
        const historyData = JSON.parse(fs.readFileSync(historyPath, 'utf-8'));
        mainWindow.webContents.send('yuki:load-history', historyData);
      }
    } catch (e) {
      console.error('Failed to load history:', e);
    }
  });


  if (isDev) {
    // Wait for Vite dev server to be ready before loading
    const tryLoad = (retries = 20) => {
      const http = require('http');
      const req = http.get('http://localhost:5173', (res) => {
        req.destroy();
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools({ mode: 'detach' });
      });
      req.on('error', () => {
        req.destroy();
        if (retries > 0) {
          setTimeout(() => tryLoad(retries - 1), 500);
        } else {
          console.error('[Yuki] Vite dev server not available after 10s — loading anyway');
          mainWindow.loadURL('http://localhost:5173');
        }
      });
    };
    setTimeout(() => tryLoad(), 1000); // Give Vite 1s head start
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/renderer/index.html'));
  }

  // Minimize to tray on close
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

// ── Tray ───────────────────────────────────────────────────────────────────────
function createTray() {
  // Use a small colored square as placeholder icon (works without an image file)
  const iconSize = 16;
  const { nativeImage } = require('electron');
  let icon;
  try {
    const iconPath = path.join(__dirname, '../resources/icon.png');
    icon = require('fs').existsSync(iconPath)
      ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
      : nativeImage.createEmpty();
  } catch {
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Yuki',
      click: () => { mainWindow.show(); mainWindow.focus(); },
    },
    {
      label: 'Hide Yuki',
      click: () => { mainWindow.hide(); },
    },
    { type: 'separator' },
    {
      label: 'Quick Actions',
      submenu: [
        { label: '🎵 Play Music',   click: () => sendToPython({ type: 'manual_trigger' }) },
        { label: '📸 Screenshot',   click: () => sendToPython({ type: 'manual_trigger' }) },
        { label: '🔄 Wake Yuki',    click: () => sendToPython({ type: 'manual_trigger' }) },
      ],
    },
    { type: 'separator' },
    {
      label: 'Quit Yuki',
      click: () => {
        app.isQuitting = true;
        sendToPython({ type: 'stop' });
        app.quit();
      },
    },
  ]);

  tray.setToolTip('Yuki AI — Right-click for options, click to toggle');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ── IPC Handlers from Renderer ────────────────────────────────────────────────
ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize();
});
ipcMain.on('window:close', () => mainWindow?.close());
ipcMain.on('window:hide', () => mainWindow?.hide());

ipcMain.on('window:set-mode', (event, mode) => {
  if (!mainWindow) return;
  if (mode === 'mini') {
    mainWindow.unmaximize();
    mainWindow.setSize(400, 150);
    mainWindow.setAlwaysOnTop(true);
  } else {
    mainWindow.setSize(1280, 800);
    mainWindow.setAlwaysOnTop(false);
    mainWindow.center();
  }
});

// User picked a clarify option
ipcMain.on('yuki:choice', (event, choice) => {
  console.log('[Yuki Renderer →]', 'choice:', choice);
  sendToPython({ type: 'choice', value: choice });
});

// Manual orb click — trigger Yuki
ipcMain.on('yuki:trigger', () => {
  console.log('[Yuki Renderer →]', 'manual trigger');
  sendToPython({ type: 'manual_trigger' });
});

// Text message from chat input
ipcMain.on('yuki:message', (event, text) => {
  console.log('[Yuki Renderer →]', 'message:', text);
  sendToPython({ type: 'text_input', value: text });
});

// History persistence
ipcMain.on('yuki:save-history', (event, messages) => {
  try {
    const fs = require('fs');
    const historyPath = path.join(app.getPath('userData'), 'yuki_history.json');
    fs.writeFileSync(historyPath, JSON.stringify(messages, null, 2), 'utf-8');
  } catch (e) {
    console.error('Failed to save history:', e);
  }
});

// ── App Lifecycle ──────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  // Setup auto-start at login (only applies to built app, not dev mode usually, but harmless to set)
  if (!isDev) {
    app.setLoginItemSettings({
      openAtLogin: true,
      args: ['--hidden']
    });
  }

  createWindow();
  createTray();
  startPython();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else {
    mainWindow.show();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    sendToPython({ type: 'stop' });
    setTimeout(() => {
      if (pythonProcess) pythonProcess.kill();
    }, 1000);
  }
});
