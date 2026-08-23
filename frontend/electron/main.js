const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// Handle Windows installer events
if (require('electron-squirrel-startup')) {
  app.quit();
}

// Configuration
const BACKEND_PORT = 9090;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const HEALTH_CHECK_INTERVAL = 500; // ms
const HEALTH_CHECK_TIMEOUT = 30000; // ms (30 seconds max wait)

let mainWindow = null;
let loadingWindow = null;
let backendProcess = null;
let isBackendReady = false;

/**
 * Get the path to the backend executable
 */
function getBackendPath() {
  if (app.isPackaged) {
    // Production: backend is in resources/backend/
    const resourcesPath = path.join(process.resourcesPath, 'backend');
    if (process.platform === 'win32') {
      return path.join(resourcesPath, 'huaqiao-backend.exe');
    } else if (process.platform === 'darwin') {
      return path.join(resourcesPath, 'huaqiao-backend');
    } else {
      return path.join(resourcesPath, 'huaqiao-backend');
    }
  } else {
    // Development: run Python directly
    return 'python3';
  }
}

/**
 * Get backend arguments
 */
function getBackendArgs() {
  if (app.isPackaged) {
    return [];
  } else {
    // Development: run launcher.py
    return [path.join(__dirname, '../../backend/launcher.py')];
  }
}

/**
 * Get backend environment variables
 */
function getBackendEnv() {
  const env = { ...process.env };
  env.BACKEND_PORT = String(BACKEND_PORT);
  env.ENV = 'production';
  
  // Set data directory
  if (process.platform === 'win32') {
    const appdata = process.env.APPDATA || path.join(process.env.USERPROFILE, 'AppData', 'Roaming');
    env.DATA_DIR = path.join(appdata, 'HuaqiaoEligibility');
  } else if (process.platform === 'darwin') {
    env.DATA_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'HuaqiaoEligibility');
  } else {
    env.DATA_DIR = path.join(process.env.HOME, '.local', 'share', 'huaqiao-eligibility');
  }
  
  return env;
}

/**
 * Start the backend process
 */
function startBackend() {
  const backendPath = getBackendPath();
  const backendArgs = getBackendArgs();
  const backendEnv = getBackendEnv();
  
  console.log(`Starting backend: ${backendPath} ${backendArgs.join(' ')}`);
  
  try {
    backendProcess = spawn(backendPath, backendArgs, {
      env: backendEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      windowsHide: true, // Hide console window on Windows
    });
    
    backendProcess.stdout.on('data', (data) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });
    
    backendProcess.stderr.on('data', (data) => {
      console.error(`[Backend Error] ${data.toString().trim()}`);
    });
    
    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err);
      showBackendError(`后端进程启动失败: ${err.message}`);
    });
    
    backendProcess.on('exit', (code, signal) => {
      console.log(`Backend process exited with code ${code}, signal ${signal}`);
      backendProcess = null;
      if (isBackendReady && mainWindow && !mainWindow.isDestroyed()) {
        // Backend crashed unexpectedly
        dialog.showErrorBox('服务异常', '后端服务意外终止，应用将关闭。');
        app.quit();
      }
    });
  } catch (err) {
    console.error('Failed to start backend:', err);
    showBackendError(`无法启动后端服务: ${err.message}`);
  }
}

/**
 * Stop the backend process
 */
function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend process...');
    
    if (process.platform === 'win32') {
      // On Windows, use taskkill to ensure process tree is killed
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t'], {
        stdio: 'ignore',
        windowsHide: true,
      });
    } else {
      backendProcess.kill('SIGTERM');
    }
    
    // Force kill after 5 seconds
    setTimeout(() => {
      if (backendProcess) {
        console.log('Force killing backend process...');
        backendProcess.kill('SIGKILL');
        backendProcess = null;
      }
    }, 5000);
  }
}

/**
 * Check if backend is ready via health check
 */
function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

/**
 * Wait for backend to be ready
 */
async function waitForBackend() {
  const startTime = Date.now();
  
  while (Date.now() - startTime < HEALTH_CHECK_TIMEOUT) {
    const isReady = await checkBackendHealth();
    if (isReady) {
      console.log('Backend is ready!');
      return true;
    }
    
    // Update loading window
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      loadingWindow.webContents.executeJavaScript(`
        document.getElementById('status-text').textContent = '正在启动服务... (${elapsed}s)';
      `).catch(() => {});
    }
    
    await new Promise(resolve => setTimeout(resolve, HEALTH_CHECK_INTERVAL));
  }
  
  return false;
}

/**
 * Show loading window
 */
function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 400,
    height: 300,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  
  const loadingHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-radius: 16px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          color: white;
          overflow: hidden;
        }
        .logo {
          width: 80px;
          height: 80px;
          background: rgba(255,255,255,0.2);
          border-radius: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 36px;
          margin-bottom: 20px;
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.05); opacity: 0.8; }
        }
        h1 {
          font-size: 18px;
          font-weight: 500;
          margin-bottom: 10px;
        }
        #status-text {
          font-size: 14px;
          opacity: 0.8;
        }
        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-top: 20px;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      </style>
    </head>
    <body>
      <div class="logo">🎓</div>
      <h1>华侨生资格评估系统</h1>
      <p id="status-text">正在启动服务...</p>
      <div class="spinner"></div>
    </body>
    </html>
  `;
  
  loadingWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml)}`);
}

/**
 * Show backend error dialog
 */
function showBackendError(message) {
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.close();
  }
  
  dialog.showErrorBox('启动失败', `后端服务启动失败:\n\n${message}\n\n请检查系统日志或联系技术支持。`);
  app.quit();
}

/**
 * Create the main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: '华侨生国际生资格智能判定系统',
    show: false,
    backgroundColor: '#ffffff',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
    },
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    // Close loading window
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.close();
      loadingWindow = null;
    }
  });

  // Load the app - inject API base URL
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    // Load the built Vue app with API base URL injected
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Create custom menu
 */
function createMenu() {
  const template = [
    {
      label: '文件',
      submenu: [
        {
          label: '刷新',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            if (mainWindow) {
              mainWindow.reload();
            }
          }
        },
        { type: 'separator' },
        {
          label: '退出',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'forceReload', label: '强制重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '实际大小' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '切换全屏' }
      ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '关于',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '关于',
              message: '华侨生国际生资格智能判定系统',
              detail: '版本: 1.0.0\n\n基于教育部、国侨办官方政策\n\n© 2024 Huaqiao Team'
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// App lifecycle
app.whenReady().then(async () => {
  createMenu();
  
  // Show loading window
  createLoadingWindow();
  
  // Start backend
  startBackend();
  
  // Wait for backend to be ready
  const isReady = await waitForBackend();
  
  if (!isReady) {
    showBackendError('后端服务启动超时，请检查系统日志。');
    return;
  }
  
  isBackendReady = true;
  
  // Create main window
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    return { action: 'deny' };
  });
});
