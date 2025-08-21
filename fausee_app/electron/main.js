const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let pyProc = null;
let win = null;

function waitForServer(url, timeoutMs=20000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(url, res => {
        resolve();
      }).on('error', () => {
        if (Date.now() - start > timeoutMs) reject(new Error('Flask did not start'));
        else setTimeout(tick, 500);
      });
    };
    tick();
  });
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1100,
    height: 750,
    backgroundColor: '#0f1224',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  await waitForServer('http://127.0.0.1:5000/api/status').catch(()=>{});
  win.loadURL('http://127.0.0.1:5000/ui');
}

function startPython() {
  const env = Object.assign({}, process.env, { ELECTRON: '1' });
  // Launch python -m app.py (use your venv python if needed)
  const script = path.join(__dirname, '..', 'app.py');
  pyProc = spawn(process.env.PYTHON || 'python', [script], { env, cwd: path.join(__dirname, '..') });

  pyProc.stdout.on('data', (data) => { console.log(`[py] ${data}`.trim()); });
  pyProc.stderr.on('data', (data) => { console.error(`[py-err] ${data}`.trim()); });
  pyProc.on('close', (code) => { console.log(`Python process exited: ${code}`); });
}

app.whenReady().then(() => {
  startPython();
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (pyProc) { try { pyProc.kill(); } catch(e) {} }
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
