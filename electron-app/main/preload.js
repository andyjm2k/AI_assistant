const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("catbotDesktop", {
  getState: () => ipcRenderer.invoke("desktop:get-state"),
  getAuthStatus: () => ipcRenderer.invoke("desktop:get-auth-status"),
  verifyAuth: (payload) => ipcRenderer.invoke("desktop:verify-auth", payload),
  authenticate: (payload) => ipcRenderer.invoke("desktop:authenticate", payload),
  logout: () => ipcRenderer.invoke("desktop:logout"),
  clearProviderApiKey: () => ipcRenderer.invoke("desktop:clear-provider-api-key"),
  listModels: () => ipcRenderer.invoke("desktop:list-models"),
  setState: (partialState) => ipcRenderer.invoke("desktop:set-state", partialState),
  toggleMoveMode: () => ipcRenderer.invoke("desktop:toggle-move-mode"),
  toggleClickThrough: () => ipcRenderer.invoke("desktop:toggle-click-through"),
  toggleQuickHud: () => ipcRenderer.invoke("desktop:toggle-quick-hud"),
  setQuickHudVisible: (visible) => ipcRenderer.invoke("desktop:set-quick-hud-visible", visible),
  centerAvatarWindow: () => ipcRenderer.invoke("desktop:center-avatar-window"),
  beginAvatarDrag: (point) => ipcRenderer.invoke("desktop:begin-avatar-drag", point),
  dragAvatarWindow: (point) => ipcRenderer.invoke("desktop:drag-avatar-window", point),
  endAvatarDrag: () => ipcRenderer.invoke("desktop:end-avatar-drag"),
  showControlPanel: () => ipcRenderer.invoke("desktop:show-control-panel"),
  launchWebClient: () => ipcRenderer.invoke("desktop:launch-web-client"),
  launchExternalWebClient: () => ipcRenderer.invoke("desktop:launch-external-web-client"),
  sendChatMessage: (payload) => ipcRenderer.invoke("desktop:send-chat-message", payload),
  clearChatHistory: () => ipcRenderer.invoke("desktop:clear-chat-history"),
  captureScreenSnapshot: () => ipcRenderer.invoke("desktop:capture-screen-snapshot"),
  transcribeAudio: (payload) => ipcRenderer.invoke("desktop:transcribe-audio", payload),
  resolveAssetUrl: (relativePath) => ipcRenderer.invoke("desktop:resolve-asset-url", relativePath),
  synthesizePreviewSpeech: (payload) => ipcRenderer.invoke("desktop:synthesize-preview-speech", payload),
  onStateChanged: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on("desktop:state-changed", listener);
    return () => ipcRenderer.removeListener("desktop:state-changed", listener);
  }
});
