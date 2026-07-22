const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("pywebview", {
  api: {
    choose_template_folder: () => ipcRenderer.invoke("choose-template-folder"),
  },
});

window.addEventListener("DOMContentLoaded", () => {
  window.dispatchEvent(new Event("pywebviewready"));
});

