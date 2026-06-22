const modeSelect = document.getElementById("avatar-mode-select");
const modelSelect = document.getElementById("avatar-model-select");
const vrmQualitySelect = document.getElementById("vrm-quality-select");
const vrmQualityStatus = document.getElementById("vrm-quality-status");
const scaleRange = document.getElementById("scale-range");
const opacityRange = document.getElementById("opacity-range");
const scaleValue = document.getElementById("scale-value");
const opacityValue = document.getElementById("opacity-value");
const vrmTransformPanel = document.getElementById("vrm-transform-panel");
const vrmPositionXRange = document.getElementById("vrm-position-x-range");
const vrmPositionYRange = document.getElementById("vrm-position-y-range");
const vrmRotationRange = document.getElementById("vrm-rotation-range");
const vrmPositionXValue = document.getElementById("vrm-position-x-value");
const vrmPositionYValue = document.getElementById("vrm-position-y-value");
const vrmRotationValue = document.getElementById("vrm-rotation-value");
const toggleMoveBtn = document.getElementById("toggle-move-btn");
const toggleClickThroughBtn = document.getElementById("toggle-clickthrough-btn");
const toggleVisibilityBtn = document.getElementById("toggle-visibility-btn");
const toggleTopMostBtn = document.getElementById("toggle-topmost-btn");
const centerAvatarBtn = document.getElementById("center-avatar-btn");
const toggleQuickHudBtn = document.getElementById("toggle-quick-hud-btn");
const expressionSelect = document.getElementById("expression-select");
const expressionButtons = Array.from(document.querySelectorAll("[data-expression]"));
const speechTextInput = document.getElementById("speech-text-input");
const desktopChatLog = document.getElementById("desktop-chat-log");
const chatPromptInput = document.getElementById("chat-prompt-input");
const sendChatBtn = document.getElementById("send-chat-btn");
const clearChatBtn = document.getElementById("clear-chat-btn");
const speakChatRepliesToggle = document.getElementById("speak-chat-replies-toggle");
const startToTrayToggle = document.getElementById("start-to-tray-toggle");
const launchAtLoginToggle = document.getElementById("launch-at-login-toggle");
const webUrlInput = document.getElementById("web-url-input");
const proxyUrlInput = document.getElementById("proxy-url-input");
const chatEndpointInput = document.getElementById("chat-endpoint-input");
const chatModelInput = document.getElementById("chat-model-input");
const chatApiKeyInput = document.getElementById("chat-api-key-input");
const ttsEndpointInput = document.getElementById("tts-endpoint-input");
const ttsModelInput = document.getElementById("tts-model-input");
const ttsVoiceInput = document.getElementById("tts-voice-input");
const refreshTtsVoicesBtn = document.getElementById("refresh-tts-voices-btn");
const statusOutput = document.getElementById("status-output");
const runtimeModeChip = document.getElementById("runtime-mode-chip");
const runtimeModelChip = document.getElementById("runtime-model-chip");
const runtimeWindowChip = document.getElementById("runtime-window-chip");
const runtimeTtsChip = document.getElementById("runtime-tts-chip");
const authUsernameInput = document.getElementById("auth-username-input");
const authPasswordInput = document.getElementById("auth-password-input");
const authStatusChip = document.getElementById("auth-status-chip");
const authStatusText = document.getElementById("auth-status-text");
const authLoginBtn = document.getElementById("auth-login-btn");
const authSignupBtn = document.getElementById("auth-signup-btn");
const authLogoutBtn = document.getElementById("auth-logout-btn");
const clearProviderKeyBtn = document.getElementById("clear-provider-key-btn");

let currentState = await window.catbotDesktop.getState();
let currentAuthStatus = await window.catbotDesktop.getAuthStatus();
let graphicsDiagnostics = {};

function clampNumber(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

function modelDisplayName(modelPath) {
  const normalized = String(modelPath || "").replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() || "None";
}

function getCurrentVrmTransform(state = currentState) {
  const modelPath = state?.modelPath || "";
  const transform = state?.vrmTransforms?.[modelPath] || {};
  return {
    scale: Number.isFinite(Number(transform.scale)) ? Number(transform.scale) : Number(state?.scale ?? 1),
    positionX: Number.isFinite(Number(transform.positionX)) ? Number(transform.positionX) : 0,
    positionY: Number.isFinite(Number(transform.positionY)) ? Number(transform.positionY) : 0,
    rotation: Number.isFinite(Number(transform.rotation)) ? Number(transform.rotation) : 0
  };
}

function getVrmTransformPatch() {
  if (currentState.mode !== "vrm" || !currentState.modelPath) {
    return {};
  }
  const nextTransform = {
    ...getCurrentVrmTransform(),
    positionX: Number(vrmPositionXRange.value),
    positionY: Number(vrmPositionYRange.value),
    rotation: Number(vrmRotationRange.value),
    scale: Number(scaleRange.value)
  };
  return {
    vrmTransforms: {
      ...(currentState.vrmTransforms || {}),
      [currentState.modelPath]: nextTransform
    }
  };
}

function getConnectionSettingsPatch() {
  const patch = {
    webClientUrl: webUrlInput.value.trim(),
    proxyBaseUrl: proxyUrlInput.value.trim(),
    chatEndpoint: chatEndpointInput.value.trim(),
    chatModel: chatModelInput.value.trim(),
    ttsEndpoint: ttsEndpointInput.value.trim(),
    ttsModel: ttsModelInput.value.trim() || "tts-1",
    ttsVoice: ttsVoiceInput.value.trim() || "alloy",
    speakChatReplies: currentState.speakChatReplies !== false,
    vrmGraphicsQuality: vrmQualitySelect?.value || currentState.vrmGraphicsQuality || "medium"
  };
  const typedProviderKey = chatApiKeyInput.value.trim();
  if (typedProviderKey) {
    patch.chatApiKey = typedProviderKey;
  }
  return patch;
}

async function updateDesktopState(patch) {
  const nextState = await window.catbotDesktop.setState(patch);
  renderState(nextState);
  return nextState;
}

function setButtonActive(button, active) {
  button.classList.toggle("is-active", Boolean(active));
}

function renderStatusRail(state) {
  runtimeModeChip.textContent = state.mode === "live2d" ? "Live2D" : "VRM";
  runtimeModelChip.textContent = modelDisplayName(state.modelPath);
  runtimeWindowChip.textContent = state.visible
    ? state.quickHudVisible
      ? "Actions"
      : state.moveMode
      ? "Move Mode"
      : state.clickThrough
        ? "Click-Through"
        : "Interactive"
    : "Hidden";
  runtimeTtsChip.textContent = state.ttsEndpoint ? state.ttsVoice || "Ready" : "Not Set";
}

function renderStatus(state) {
  statusOutput.textContent = JSON.stringify(
    {
      mode: state.mode,
      modelPath: state.modelPath,
      scale: state.scale,
      opacity: state.opacity,
      clickThrough: state.clickThrough,
      alwaysOnTop: state.alwaysOnTop,
      moveMode: state.moveMode,
      quickHudVisible: state.quickHudVisible,
      visible: state.visible,
      startToTray: state.startToTray,
      launchAtLogin: state.launchAtLogin,
      expression: state.expression,
      vrmGraphicsQuality: state.vrmGraphicsQuality || "medium",
      graphics: graphicsDiagnostics,
      vrmTransform: getCurrentVrmTransform(state),
      webClientUrl: state.webClientUrl,
      proxyBaseUrl: state.proxyBaseUrl,
      chatEndpoint: state.chatEndpoint,
      chatModel: state.chatModel,
      chatApiKeyConfigured: Boolean(state.chatApiKeyConfigured),
      desktopChatMessages: Array.isArray(state.desktopChatHistory) ? state.desktopChatHistory.length : 0,
      speakChatReplies: state.speakChatReplies !== false,
      ttsEndpoint: state.ttsEndpoint,
      ttsModel: state.ttsModel,
      ttsVoice: state.ttsVoice
    },
    null,
    2
  );
}

async function populateModels(selectedPath) {
  const models = await window.catbotDesktop.listModels();
  const selectedMode = currentState.mode === "live2d" ? "live2d" : "vrm";
  const availableModels = selectedMode === "live2d" ? (models.live2d || []) : (models.vrm || []);

  modelSelect.replaceChildren();
  for (const modelPath of availableModels) {
    const option = document.createElement("option");
    option.value = modelPath;
    option.textContent = modelDisplayName(modelPath);
    option.selected = modelPath === selectedPath;
    modelSelect.appendChild(option);
  }
}

function addSelectOption(select, value, label = value) {
  const normalizedValue = String(value || "").trim();
  if (!select || !normalizedValue) {
    return;
  }
  const exists = Array.from(select.options).some((option) => option.value === normalizedValue);
  if (exists) {
    return;
  }
  const option = document.createElement("option");
  option.value = normalizedValue;
  option.textContent = String(label || normalizedValue);
  select.appendChild(option);
}

function setTtsVoiceInputValue(value) {
  const selected = String(value || "alloy").trim() || "alloy";
  addSelectOption(ttsVoiceInput, selected);
  ttsVoiceInput.value = selected;
}

async function populateTtsVoiceOptions(selectedVoice = currentState.ttsVoice) {
  if (!ttsVoiceInput || typeof window.catbotDesktop.listTtsVoices !== "function") {
    setTtsVoiceInputValue(selectedVoice);
    return;
  }
  const desiredVoice = String(selectedVoice || ttsVoiceInput.value || currentState.ttsVoice || "alloy").trim() || "alloy";
  try {
    const catalog = await window.catbotDesktop.listTtsVoices({
      proxyBaseUrl: proxyUrlInput.value.trim() || currentState.proxyBaseUrl,
      ttsEndpoint: ttsEndpointInput.value.trim() || currentState.ttsEndpoint,
      ttsModel: ttsModelInput.value.trim() || currentState.ttsModel,
      ttsVoice: desiredVoice
    });
    const voices = Array.isArray(catalog?.voices) ? catalog.voices : [];
    ttsVoiceInput.replaceChildren();
    for (const voice of voices) {
      addSelectOption(ttsVoiceInput, voice.id, voice.name || voice.id);
    }
    const catalogSelectedVoice = String(catalog?.selectedVoice || "").trim();
    const nextVoice = desiredVoice === "alloy" && catalogSelectedVoice
      ? catalogSelectedVoice
      : (desiredVoice || catalogSelectedVoice || currentState.ttsVoice);
    setTtsVoiceInputValue(nextVoice);
    if (!ttsVoiceInput.value && ttsVoiceInput.options.length > 0) {
      ttsVoiceInput.selectedIndex = 0;
    }
  } catch (error) {
    addSelectOption(ttsVoiceInput, desiredVoice);
    ttsVoiceInput.value = desiredVoice;
    statusOutput.textContent = `Could not refresh TTS voices: ${String(error?.message || error)}`;
  }
}

function renderExpressionButtons(expression) {
  const normalized = String(expression || "neutral").toLowerCase();
  expressionSelect.value = normalized;
  for (const button of expressionButtons) {
    setButtonActive(button, button.dataset.expression === normalized);
  }
}

function renderDesktopChat(history = []) {
  desktopChatLog.replaceChildren();
  const messages = Array.isArray(history) ? history : [];
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "chat-empty";
    empty.textContent = "No desktop chat yet. Ask a short question and the reply can animate the avatar.";
    desktopChatLog.appendChild(empty);
    return;
  }

  for (const message of messages) {
    const role = message.role === "assistant" ? "assistant" : "user";
    const item = document.createElement("article");
    item.className = `chat-message ${role}`;
    const label = document.createElement("strong");
    label.textContent = role === "assistant" ? "CATBot" : "You";
    const content = document.createElement("span");
    content.textContent = String(message.content || "");
    item.append(label, content);
    desktopChatLog.appendChild(item);
  }
  desktopChatLog.scrollTop = desktopChatLog.scrollHeight;
}

function renderState(state) {
  currentState = state;
  const isVrm = state.mode !== "live2d";
  const scale = clampNumber(state.scale, 0.25, 2.5, 1);
  const opacity = clampNumber(state.opacity, 0.35, 1, 1);
  const vrmTransform = getCurrentVrmTransform(state);

  modeSelect.value = isVrm ? "vrm" : "live2d";
  if (vrmQualitySelect) {
    vrmQualitySelect.value = state.vrmGraphicsQuality || "medium";
    vrmQualitySelect.disabled = !isVrm;
  }
  scaleRange.value = String(scale);
  opacityRange.value = String(opacity);
  scaleValue.textContent = `${scale.toFixed(2)}x`;
  opacityValue.textContent = opacity.toFixed(2);
  webUrlInput.value = state.webClientUrl || "";
  proxyUrlInput.value = state.proxyBaseUrl || "";
  chatEndpointInput.value = state.chatEndpoint || "";
  chatModelInput.value = state.chatModel || "";
  chatApiKeyInput.value = "";
  chatApiKeyInput.placeholder = state.chatApiKeyConfigured
    ? "Provider key saved; leave blank to keep it"
    : "Optional; server credentials are used when trusted";
  ttsEndpointInput.value = state.ttsEndpoint || "";
  ttsModelInput.value = state.ttsModel || "tts-1";
  setTtsVoiceInputValue(state.ttsVoice || "alloy");
  vrmPositionXRange.value = String(vrmTransform.positionX);
  vrmPositionYRange.value = String(vrmTransform.positionY);
  vrmRotationRange.value = String(vrmTransform.rotation);
  vrmPositionXValue.textContent = vrmTransform.positionX.toFixed(2);
  vrmPositionYValue.textContent = vrmTransform.positionY.toFixed(2);
  vrmRotationValue.textContent = `${Math.round(vrmTransform.rotation)}\u00B0`;

  toggleMoveBtn.textContent = state.moveMode ? "Finish Move Mode" : "Enable Move Mode";
  toggleClickThroughBtn.textContent = state.clickThrough ? "Disable Click-Through" : "Enable Click-Through";
  toggleVisibilityBtn.textContent = state.visible ? "Hide Avatar" : "Show Avatar";
  toggleTopMostBtn.textContent = state.alwaysOnTop ? "Disable Always On Top" : "Enable Always On Top";
  toggleQuickHudBtn.textContent = state.quickHudVisible ? "Hide Avatar Actions" : "Show Avatar Actions";
  startToTrayToggle.textContent = `Start To Tray: ${state.startToTray ? "On" : "Off"}`;
  launchAtLoginToggle.textContent = `Launch At Login: ${state.launchAtLogin ? "On" : "Off"}`;
  speakChatRepliesToggle.textContent = `Speak Replies: ${state.speakChatReplies === false ? "Off" : "On"}`;

  setButtonActive(toggleMoveBtn, state.moveMode);
  setButtonActive(toggleClickThroughBtn, !state.clickThrough);
  setButtonActive(toggleVisibilityBtn, state.visible);
  setButtonActive(toggleTopMostBtn, state.alwaysOnTop);
  setButtonActive(toggleQuickHudBtn, state.quickHudVisible);
  setButtonActive(startToTrayToggle, state.startToTray);
  setButtonActive(launchAtLoginToggle, state.launchAtLogin);
  setButtonActive(speakChatRepliesToggle, state.speakChatReplies !== false);
  renderExpressionButtons(state.expression);
  renderDesktopChat(state.desktopChatHistory);

  vrmTransformPanel.classList.toggle("is-disabled", !isVrm);
  for (const input of [vrmPositionXRange, vrmPositionYRange, vrmRotationRange]) {
    input.disabled = !isVrm;
  }
  renderGraphicsQualityStatus();

  if (modelSelect.value !== state.modelPath || modeSelect.value !== state.mode) {
    populateModels(state.modelPath);
  }
  renderStatusRail(state);
  renderStatus(state);
}

function renderGraphicsQualityStatus() {
  if (!vrmQualityStatus) {
    return;
  }
  const renderer = graphicsDiagnostics?.renderer || {};
  const requested = renderer.requestedQuality || currentState.vrmGraphicsQuality || "medium";
  const effective = renderer.effectiveQuality || requested;
  const fps = Number(renderer.fps);
  const gpu = graphicsDiagnostics?.gpuInfo?.auxAttributes?.glRenderer || "";
  const details = [
    `${requested[0].toUpperCase()}${requested.slice(1)} requested`,
    `${effective[0].toUpperCase()}${effective.slice(1)} active`,
    Number.isFinite(fps) && fps > 0 ? `${fps.toFixed(0)} FPS` : "",
    gpu
  ].filter(Boolean);
  vrmQualityStatus.textContent = details.join(" · ") || "Changing quality reloads the VRM renderer.";
}

async function refreshGraphicsDiagnostics() {
  if (typeof window.catbotDesktop.getGraphicsDiagnostics !== "function") {
    return;
  }
  try {
    graphicsDiagnostics = await window.catbotDesktop.getGraphicsDiagnostics() || {};
    renderGraphicsQualityStatus();
    renderStatus(currentState);
  } catch (_) {
    // Diagnostics are optional and must not block avatar controls.
  }
}

function renderAuthStatus(status = currentAuthStatus) {
  currentAuthStatus = status || {};
  const signedIn = Boolean(currentAuthStatus.authenticated);
  authStatusChip.textContent = signedIn ? `Signed in${currentAuthStatus.username ? `: ${currentAuthStatus.username}` : ""}` : "Not signed in";
  authStatusChip.classList.toggle("is-active", signedIn);
  authStatusText.textContent = signedIn
    ? "Desktop HUD requests will include CATBot proxy auth."
    : "Sign in so desktop HUD requests can use protected CATBot proxy routes.";
  authLogoutBtn.disabled = !signedIn;
}

async function runAuthAction(action) {
  const username = authUsernameInput.value.trim();
  const password = authPasswordInput.value;
  if (!username || !password) {
    authStatusText.textContent = "Username and password are required.";
    return;
  }

  for (const button of [authLoginBtn, authSignupBtn]) {
    button.disabled = true;
  }
  authStatusText.textContent = action === "signup" ? "Creating account..." : "Signing in...";
  try {
    const status = await window.catbotDesktop.authenticate({
      action,
      username,
      password,
      proxyBaseUrl: proxyUrlInput.value.trim() || currentState.proxyBaseUrl
    });
    authPasswordInput.value = "";
    renderAuthStatus(status);
  } catch (error) {
    authStatusText.textContent = String(error?.message || error || "Authentication failed.");
  } finally {
    for (const button of [authLoginBtn, authSignupBtn]) {
      button.disabled = false;
    }
  }
}

window.catbotDesktop.onStateChanged((state) => renderState(state));

document.getElementById("rescan-models-btn").addEventListener("click", async () => {
  await populateModels(currentState.modelPath);
});

modeSelect.addEventListener("change", async () => {
  await updateDesktopState({ mode: modeSelect.value, modelPath: "" });
});

modelSelect.addEventListener("change", async () => {
  await updateDesktopState({ modelPath: modelSelect.value });
});

vrmQualitySelect?.addEventListener("change", async () => {
  await updateDesktopState({ vrmGraphicsQuality: vrmQualitySelect.value });
});

scaleRange.addEventListener("input", async () => {
  const scale = Number(scaleRange.value);
  scaleValue.textContent = `${scale.toFixed(2)}x`;
  await updateDesktopState({
    scale,
    ...getVrmTransformPatch()
  });
});

opacityRange.addEventListener("input", async () => {
  const opacity = Number(opacityRange.value);
  opacityValue.textContent = opacity.toFixed(2);
  await updateDesktopState({ opacity });
});

toggleMoveBtn.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.toggleMoveMode();
  renderState(nextState);
});

toggleClickThroughBtn.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.toggleClickThrough();
  renderState(nextState);
});

toggleVisibilityBtn.addEventListener("click", async () => {
  await updateDesktopState({ visible: !currentState.visible });
});

toggleTopMostBtn.addEventListener("click", async () => {
  await updateDesktopState({ alwaysOnTop: !currentState.alwaysOnTop });
});

centerAvatarBtn.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.centerAvatarWindow();
  renderState(nextState);
});

toggleQuickHudBtn.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.toggleQuickHud();
  renderState(nextState);
});

expressionSelect.addEventListener("change", async () => {
  await updateDesktopState({ expression: expressionSelect.value });
});

for (const button of expressionButtons) {
  button.addEventListener("click", async () => {
    await updateDesktopState({ expression: button.dataset.expression || "neutral" });
  });
}

vrmPositionXRange.addEventListener("input", async () => {
  vrmPositionXValue.textContent = Number(vrmPositionXRange.value).toFixed(2);
  await updateDesktopState(getVrmTransformPatch());
});

vrmPositionYRange.addEventListener("input", async () => {
  vrmPositionYValue.textContent = Number(vrmPositionYRange.value).toFixed(2);
  await updateDesktopState(getVrmTransformPatch());
});

vrmRotationRange.addEventListener("input", async () => {
  vrmRotationValue.textContent = `${Math.round(Number(vrmRotationRange.value))}\u00B0`;
  await updateDesktopState(getVrmTransformPatch());
});

document.getElementById("reset-vrm-transform-btn").addEventListener("click", async () => {
  if (currentState.mode !== "vrm" || !currentState.modelPath) {
    return;
  }
  await updateDesktopState({
    scale: 1,
    vrmTransforms: {
      ...(currentState.vrmTransforms || {}),
      [currentState.modelPath]: {
        scale: 1,
        positionX: 0,
        positionY: 0,
        rotation: 0
      }
    }
  });
});

document.getElementById("preview-speech-btn").addEventListener("click", async () => {
  const text = speechTextInput.value.trim();
  if (!text) {
    return;
  }
  const durationMs = Math.max(1600, Math.min(8000, text.length * 90));
  await updateDesktopState({
    ...getConnectionSettingsPatch(),
    speechBubbleText: text,
    speechDurationMs: durationMs,
    speechTriggerId: Date.now()
  });
});

document.getElementById("clear-speech-btn").addEventListener("click", async () => {
  speechTextInput.value = "";
  await updateDesktopState({
    speechBubbleText: "",
    speechDurationMs: 300,
    speechTriggerId: Date.now()
  });
});

speakChatRepliesToggle.addEventListener("click", async () => {
  await updateDesktopState({ speakChatReplies: currentState.speakChatReplies === false });
});

sendChatBtn.addEventListener("click", async () => {
  const message = chatPromptInput.value.trim();
  if (!message) {
    return;
  }

  sendChatBtn.disabled = true;
  sendChatBtn.textContent = "Asking...";
  try {
    const result = await window.catbotDesktop.sendChatMessage({
      ...getConnectionSettingsPatch(),
      message,
      speakReply: currentState.speakChatReplies !== false
    });
    chatPromptInput.value = "";
    renderState(result.state);
  } catch (error) {
    await updateDesktopState({
      expression: "sad",
      speechBubbleText: String(error?.message || error || "Desktop chat failed."),
      speechDurationMs: 5000,
      speechTriggerId: Date.now()
    });
  } finally {
    sendChatBtn.disabled = false;
    sendChatBtn.textContent = "Send To CATBot";
  }
});

chatPromptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    sendChatBtn.click();
  }
});

clearChatBtn.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.clearChatHistory();
  renderState(nextState);
});

startToTrayToggle.addEventListener("click", async () => {
  await updateDesktopState({ startToTray: !currentState.startToTray });
});

launchAtLoginToggle.addEventListener("click", async () => {
  await updateDesktopState({ launchAtLogin: !currentState.launchAtLogin });
});

document.getElementById("save-web-url-btn").addEventListener("click", async () => {
  await updateDesktopState(getConnectionSettingsPatch());
});

refreshTtsVoicesBtn?.addEventListener("click", async () => {
  await populateTtsVoiceOptions(ttsVoiceInput.value || currentState.ttsVoice);
});

for (const input of [proxyUrlInput, ttsEndpointInput, ttsModelInput]) {
  input?.addEventListener("change", async () => {
    await populateTtsVoiceOptions(ttsVoiceInput.value || currentState.ttsVoice);
  });
}

clearProviderKeyBtn?.addEventListener("click", async () => {
  const nextState = await window.catbotDesktop.clearProviderApiKey();
  chatApiKeyInput.value = "";
  renderState(nextState);
});

authLoginBtn.addEventListener("click", async () => {
  await runAuthAction("login");
});

authSignupBtn.addEventListener("click", async () => {
  await runAuthAction("signup");
});

authLogoutBtn.addEventListener("click", async () => {
  const status = await window.catbotDesktop.logout();
  renderAuthStatus(status);
});

for (const input of [authUsernameInput, authPasswordInput]) {
  input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      await runAuthAction("login");
    }
  });
}

document.getElementById("open-web-client-btn").addEventListener("click", async () => {
  await window.catbotDesktop.launchWebClient();
});

document.getElementById("open-external-web-client-btn").addEventListener("click", async () => {
  await window.catbotDesktop.launchExternalWebClient();
});

await populateModels(currentState.modelPath);
renderState(currentState);
await populateTtsVoiceOptions(currentState.ttsVoice);
renderAuthStatus(await window.catbotDesktop.verifyAuth({ proxyBaseUrl: currentState.proxyBaseUrl }));
await refreshGraphicsDiagnostics();
window.setInterval(refreshGraphicsDiagnostics, 2500);
