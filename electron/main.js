const { app, BrowserWindow, dialog, ipcMain, session, shell } = require("electron");
const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const path = require("node:path");
const readline = require("node:readline");

let mainWindow = null;
let serviceProcess = null;
let serviceUrl = "";
const desktopToken = crypto.randomBytes(32).toString("hex");

function serviceCommand() {
  if (app.isPackaged) {
    return {
      executable: path.join(process.resourcesPath, "python-service", "FocusAmazonService.exe"),
      args: [],
      cwd: process.resourcesPath,
    };
  }
  const projectDir = path.resolve(__dirname, "..");
  const configuredPython = process.env.ELECTRON_PYTHON;
  const executable = configuredPython || (process.platform === "win32"
    ? path.join(projectDir, ".build-venv", "Scripts", "python.exe")
    : path.join(projectDir, ".build-venv", "bin", "python"));
  return { executable, args: [path.join(projectDir, "electron_service.py")], cwd: projectDir };
}

function startService() {
  return new Promise((resolve, reject) => {
    const command = serviceCommand();
    serviceProcess = spawn(command.executable, command.args, {
      cwd: command.cwd,
      env: {...process.env, FOCUS_DESKTOP_TOKEN: desktopToken},
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const timeout = setTimeout(() => reject(new Error("The local service did not start in time.")), 30000);
    const output = readline.createInterface({input: serviceProcess.stdout});
    output.on("line", (line) => {
      try {
        const message = JSON.parse(line);
        if (message.url && !serviceUrl) {
          serviceUrl = message.url;
          clearTimeout(timeout);
          resolve(serviceUrl);
        }
      } catch (_error) {
        // Non-protocol service output is intentionally ignored.
      }
    });
    serviceProcess.stderr.on("data", (chunk) => process.stderr.write(chunk));
    serviceProcess.once("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    serviceProcess.once("exit", (code) => {
      if (!serviceUrl) {
        clearTimeout(timeout);
        reject(new Error(`The local service stopped during startup (${code ?? "unknown"}).`));
      }
      serviceProcess = null;
    });
  });
}

async function createWindow() {
  const url = await startService();
  // Installed upgrades reuse Electron's user-data directory. Clear HTTP assets so
  // an older renderer can never survive a service/application version upgrade.
  await session.defaultSession.clearCache();
  mainWindow = new BrowserWindow({
    title: "Focus Amazon Tools",
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 650,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: "#f4f7f8",
    icon: path.resolve(__dirname, "..", "packaging", "assets", "app-icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({url: target}) => {
    shell.openExternal(target);
    return {action: "deny"};
  });
  mainWindow.webContents.on("will-navigate", (event, target) => {
    if (!target.startsWith(url)) {
      event.preventDefault();
      shell.openExternal(target);
    }
  });
  await mainWindow.loadURL(url);
  mainWindow.show();
}

ipcMain.handle("choose-template-folder", async () => {
  if (!mainWindow || !serviceUrl) return null;
  const result = await dialog.showOpenDialog(mainWindow, {properties: ["openDirectory"]});
  if (result.canceled || !result.filePaths[0]) return null;
  const response = await fetch(new URL("api/desktop/register-folder", serviceUrl), {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Focus-Desktop-Token": desktopToken},
    body: JSON.stringify({path: result.filePaths[0]}),
  });
  if (!response.ok) throw new Error("The selected folder could not be registered.");
  return response.json();
});

app.whenReady().then(createWindow).catch((error) => {
  dialog.showErrorBox("Focus Amazon Tools", `The application could not start.\n\n${error.message}`);
  app.quit();
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  if (serviceProcess && !serviceProcess.killed) serviceProcess.kill();
});
