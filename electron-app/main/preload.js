const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("catbotDesktop", {
  getState: () => ipcRenderer.invoke("desktop:get-state"),
  getAuthStatus: () => ipcRenderer.invoke("desktop:get-auth-status"),
  verifyAuth: (payload) => ipcRenderer.invoke("desktop:verify-auth", payload),
  authenticate: (payload) => ipcRenderer.invoke("desktop:authenticate", payload),
  logout: () => ipcRenderer.invoke("desktop:logout"),
  clearProviderApiKey: () => ipcRenderer.invoke("desktop:clear-provider-api-key"),
  listModels: () => ipcRenderer.invoke("desktop:list-models"),
  listVrmaAnimations: () => ipcRenderer.invoke("desktop:list-vrma-animations"),
  listTtsVoices: (payload) => ipcRenderer.invoke("desktop:list-tts-voices", payload),
  listCompanions: (payload) => ipcRenderer.invoke("desktop:list-companions", payload),
  createCompanion: (payload) => ipcRenderer.invoke("desktop:create-companion", payload),
  loadCompanion: (companionId, payload) => ipcRenderer.invoke("desktop:load-companion", companionId, payload),
  deleteCompanion: (companionId, payload) => ipcRenderer.invoke("desktop:delete-companion", companionId, payload),
  setDefaultCompanion: (companionId) => ipcRenderer.invoke("desktop:set-default-companion", companionId),
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
  prewarmChat: (payload) => ipcRenderer.invoke("desktop:prewarm-chat", payload),
  sendChatMessage: (payload) => ipcRenderer.invoke("desktop:send-chat-message", payload),
  clearChatHistory: () => ipcRenderer.invoke("desktop:clear-chat-history"),
  captureScreenSnapshot: () => ipcRenderer.invoke("desktop:capture-screen-snapshot"),
  transcribeAudio: (payload) => ipcRenderer.invoke("desktop:transcribe-audio", payload),
  resolveAssetUrl: (relativePath) => ipcRenderer.invoke("desktop:resolve-asset-url", relativePath),
  synthesizePreviewSpeech: (payload) => ipcRenderer.invoke("desktop:synthesize-preview-speech", payload),
  synthesizePreviewSpeechStream: (payload, callbacks = {}) => {
    const streamId = `speech_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const channels = {
      started: `desktop:preview-speech-stream:${streamId}:started`,
      chunk: `desktop:preview-speech-stream:${streamId}:chunk`,
      done: `desktop:preview-speech-stream:${streamId}:done`,
      error: `desktop:preview-speech-stream:${streamId}:error`
    };
    const listeners = [
      [channels.started, (_event, data) => callbacks.onStarted?.(data)],
      [channels.chunk, (_event, data) => callbacks.onChunk?.(data)],
      [channels.done, (_event, data) => callbacks.onDone?.(data)],
      [channels.error, (_event, data) => callbacks.onError?.(data)]
    ];
    for (const [channel, listener] of listeners) {
      ipcRenderer.on(channel, listener);
    }
    const cleanup = () => {
      for (const [channel, listener] of listeners) {
        ipcRenderer.removeListener(channel, listener);
      }
    };
    const promise = ipcRenderer.invoke("desktop:synthesize-preview-speech-stream", {
      ...payload,
      streamId
    }).finally(cleanup);
    return {
      streamId,
      promise,
      cancel: () => ipcRenderer.invoke("desktop:cancel-preview-speech-stream", streamId)
    };
  },
  cancelPreviewSpeechStream: (streamId) => ipcRenderer.invoke("desktop:cancel-preview-speech-stream", streamId),
  onVoiceCaptureShortcut: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("desktop:start-voice-capture", listener);
    return () => ipcRenderer.removeListener("desktop:start-voice-capture", listener);
  },
  onStateChanged: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on("desktop:state-changed", listener);
    return () => ipcRenderer.removeListener("desktop:state-changed", listener);
  }
});
