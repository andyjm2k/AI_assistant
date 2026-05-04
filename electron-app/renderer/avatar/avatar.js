import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { createVRMAnimationClip, VRMAnimationLoaderPlugin } from "@pixiv/three-vrm-animation";

window.PIXI = window.PIXI || PIXI;
window.EventEmitter3.EventEmitter = EventEmitter3;

const vrmCanvas = document.getElementById("avatar-canvas");
const live2dContainer = document.getElementById("live2d-container");
const live2dCanvas = document.getElementById("live2d-canvas");
const statusChip = document.getElementById("status-chip");
const renderFallback = document.getElementById("render-fallback");
const renderFallbackImage = document.getElementById("render-fallback-image");
const renderFallbackStatus = document.getElementById("render-fallback-status");
const speechBubble = document.getElementById("speech-bubble");
const moveOverlay = document.getElementById("move-overlay");
const quickHud = document.getElementById("quick-hud");
const quickChatForm = document.getElementById("quick-chat-form");
const quickChatInput = document.getElementById("quick-chat-input");
const quickChatSend = document.getElementById("quick-chat-send");
const quickHudStatus = document.getElementById("quick-hud-status");
const hudSheet = document.getElementById("hud-sheet");
const hudPanelButtons = Array.from(document.querySelectorAll("[data-hud-panel-button]"));
const hudPanels = Array.from(document.querySelectorAll("[data-hud-panel]"));
const hudChatLog = document.getElementById("hud-chat-log");
const hudClearChatBtn = document.getElementById("hud-clear-chat-btn");
const hudAuthChip = document.getElementById("hud-auth-chip");
const hudAuthUsername = document.getElementById("hud-auth-username");
const hudAuthPassword = document.getElementById("hud-auth-password");
const hudAuthStatus = document.getElementById("hud-auth-status");
const hudAuthLoginBtn = document.getElementById("hud-auth-login-btn");
const hudAuthSignupBtn = document.getElementById("hud-auth-signup-btn");
const hudAuthLogoutBtn = document.getElementById("hud-auth-logout-btn");
const hudAvatarMode = document.getElementById("hud-avatar-mode");
const hudAvatarModel = document.getElementById("hud-avatar-model");
const hudScaleRange = document.getElementById("hud-scale-range");
const hudScaleValue = document.getElementById("hud-scale-value");
const hudOpacityRange = document.getElementById("hud-opacity-range");
const hudOpacityValue = document.getElementById("hud-opacity-value");
const hudVrmXRange = document.getElementById("hud-vrm-x-range");
const hudVrmYRange = document.getElementById("hud-vrm-y-range");
const hudVrmRotationRange = document.getElementById("hud-vrm-rotation-range");
const hudVrmXValue = document.getElementById("hud-vrm-x-value");
const hudVrmYValue = document.getElementById("hud-vrm-y-value");
const hudVrmRotationValue = document.getElementById("hud-vrm-rotation-value");
const hudResetVrmBtn = document.getElementById("hud-reset-vrm-btn");
const hudRescanModelsBtn = document.getElementById("hud-rescan-models-btn");
const hudProxyUrl = document.getElementById("hud-proxy-url");
const hudWebUrl = document.getElementById("hud-web-url");
const hudChatEndpoint = document.getElementById("hud-chat-endpoint");
const hudChatModel = document.getElementById("hud-chat-model");
const hudChatApiKey = document.getElementById("hud-chat-api-key");
const hudTtsEndpoint = document.getElementById("hud-tts-endpoint");
const hudTtsModel = document.getElementById("hud-tts-model");
const hudTtsVoice = document.getElementById("hud-tts-voice");
const hudSaveSettingsBtn = document.getElementById("hud-save-settings-btn");
const hudToggleSpeakBtn = document.getElementById("hud-toggle-speak-btn");
const hudClearProviderKeyBtn = document.getElementById("hud-clear-provider-key-btn");
const hudOpenWebBtn = document.getElementById("hud-open-web-btn");
const hudToggleClickthroughBtn = document.getElementById("hud-toggle-clickthrough-btn");
const hudToggleTopmostBtn = document.getElementById("hud-toggle-topmost-btn");
const hudCenterAvatarBtn = document.getElementById("hud-center-avatar-btn");
const hudToggleStartTrayBtn = document.getElementById("hud-toggle-start-tray-btn");
const hudToggleLaunchLoginBtn = document.getElementById("hud-toggle-launch-login-btn");
const hudHideAvatarBtn = document.getElementById("hud-hide-avatar-btn");
const hudSpeechText = document.getElementById("hud-speech-text");
const hudPreviewSpeechBtn = document.getElementById("hud-preview-speech-btn");
const hudClearSpeechBtn = document.getElementById("hud-clear-speech-btn");
const hudOpenBrowserBtn = document.getElementById("hud-open-browser-btn");
const hudStatusOutput = document.getElementById("hud-status-output");

let currentState = await window.catbotDesktop.getState();
let currentAuthStatus = await window.catbotDesktop.getAuthStatus();
let availableModels = { vrm: [], live2d: [] };
let activeHudPanel = "";
let currentModelPath = "";
let vrmModel = null;
let vrmRuntime = null;
let live2dModel = null;
let live2dApp = null;
let live2dTickerRegistered = false;
let scene;
let camera;
let renderer;
let clock;
let currentMouthValue = 0;
let speechActiveUntil = 0;
let activeSpeechTriggerId = 0;
let bubbleHideTimeout = null;
let bubbleSequenceTimeouts = [];
let audioContext = null;
let speechPreviewAudio = null;
let speechPreviewObjectUrl = "";
let speechPreviewSourceNode = null;
let speechPreviewAnalyserNode = null;
let speechPreviewGainNode = null;
let speechPreviewRafId = 0;
let analyserSpeechActive = false;
let speechGeneration = 0;
let lookTarget = null;
let quickHudWasVisible = Boolean(currentState.quickHudVisible);
let pendingScreenSnapshot = null;
let micRecorder = null;
let micStream = null;
let micChunks = [];
let micStopTimer = 0;
let renderLoopActive = false;
let webglContextLost = false;
let fallbackImageLoading = null;
let smoothedVrmDelta = 1 / 60;

const VRM_ACTION_FADE_IN_SECONDS = 0.36;
const VRM_ACTION_FADE_OUT_SECONDS = 0.5;
const VRM_IDLE_ACTION_FADE_IN_SECONDS = 0.66;
const VRM_IDLE_ACTION_FADE_OUT_SECONDS = 0.42;
const VRM_MAX_ANIMATION_DELTA_SECONDS = 1 / 24;
const VRM_MAX_PHYSICS_DELTA_SECONDS = 1 / 45;
const VRM_DELTA_SMOOTHING = 0.18;
const VRM_PHYSICS_RESET_DELTA_SECONDS = 0.22;
const DESKTOP_MAX_TEXTURE_SIZE = 1024;
const ENABLE_DESKTOP_VRMA_PRELOAD = true;
const DESKTOP_MATERIAL_TEXTURE_KEYS = ["map", "emissiveMap", "normalMap", "roughnessMap", "metalnessMap", "alphaMap"];
const SPEECH_BUBBLE_FADE_MS = 220;
const SPEECH_SENTENCE_GAP_MS = 90;
const VRM_ANIMATION_LIBRARY = {
  idle: "model_avatar/Eva/VRMA_06.vrma",
  happy: "model_avatar/Eva/004_hello_1.vrma",
  love: "model_avatar/Eva/Kawaii Kaiwai.vrma",
  think: "model_avatar/Eva/Thinking.vrma",
  cry: "model_avatar/Eva/007_gekirei.vrma",
  angry: "model_avatar/Eva/VRMA_04.vrma",
  surprised: "model_avatar/Eva/Surprised.vrma",
  sad: "model_avatar/Eva/Relax.vrma"
};
const VRM_EXPRESSION_ACTION_MAP = {
  neutral: "idle",
  happy: "love",
  love: "love",
  think: "think",
  thinking: "think",
  sad: "cry",
  cry: "cry",
  angry: "angry",
  surprised: "surprised"
};
const VRM_ONE_SHOT_ACTION_DURATION_MS = 6000;

function setStatus(message) {
  if (renderFallbackStatus) {
    renderFallbackStatus.textContent = message;
  }
  if (!statusChip) {
    return;
  }
  statusChip.textContent = message;
}

async function ensureFallbackImage() {
  if (!renderFallbackImage || renderFallbackImage.src) {
    return;
  }
  if (!fallbackImageLoading) {
    fallbackImageLoading = window.catbotDesktop.resolveAssetUrl("CATBot_logo.png")
      .then((url) => {
        renderFallbackImage.src = url;
      })
      .catch((error) => {
        console.warn("Could not resolve avatar fallback image:", error);
      });
  }
  await fallbackImageLoading;
}

function showRenderFallback(message, error = null) {
  const fallbackMessage = message || "Avatar renderer is unavailable.";
  document.body.classList.add("render-fallback-visible");
  setStatus(fallbackMessage);
  ensureFallbackImage();
  if (error) {
    console.error(fallbackMessage, error);
  } else {
    console.error(fallbackMessage);
  }
}

function hideRenderFallback() {
  if (!webglContextLost) {
    document.body.classList.remove("render-fallback-visible");
  }
}

function formatLoadError(error) {
  const raw = String(error?.message || error || "unknown error").trim();
  return raw.length > 140 ? `${raw.slice(0, 137)}...` : raw;
}

function setReadyStatus() {
  setStatus(currentState.moveMode ? "Move mode enabled" : "Avatar ready");
}

function clearSpeechBubbleHideTimer() {
  if (bubbleHideTimeout) {
    clearTimeout(bubbleHideTimeout);
    bubbleHideTimeout = null;
  }
}

function clearSpeechBubbleSequence() {
  for (const timerId of bubbleSequenceTimeouts) {
    clearTimeout(timerId);
  }
  bubbleSequenceTimeouts = [];
}

function hideSpeechBubble(options = {}) {
  if (!speechBubble) {
    return;
  }
  const { immediate = false, clearSequence = true } = options;
  if (clearSequence) {
    clearSpeechBubbleSequence();
  }
  clearSpeechBubbleHideTimer();
  speechBubble.classList.remove("is-visible");
  if (immediate) {
    speechBubble.textContent = "";
    document.body.classList.remove("speech-active");
    return;
  }
  bubbleHideTimeout = window.setTimeout(() => {
    speechBubble.textContent = "";
    document.body.classList.remove("speech-active");
    bubbleHideTimeout = null;
  }, SPEECH_BUBBLE_FADE_MS);
}

function showSpeechBubble(text, durationMs = 0) {
  if (!speechBubble) {
    return;
  }
  clearSpeechBubbleHideTimer();

  const content = String(text || "").trim();
  if (!content) {
    hideSpeechBubble();
    return;
  }

  const wasVisible = speechBubble.classList.contains("is-visible");
  speechBubble.textContent = content;
  document.body.classList.add("speech-active");
  if (wasVisible) {
    speechBubble.classList.add("is-visible");
  } else {
    requestAnimationFrame(() => {
      if (speechBubble.textContent === content) {
        speechBubble.classList.add("is-visible");
      }
    });
  }
  if (durationMs > 0) {
    bubbleHideTimeout = window.setTimeout(() => {
      hideSpeechBubble();
    }, Math.max(400, durationMs));
  }
}

function splitSpeechIntoSentences(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return [];
  }
  const chunks = normalized.match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g) || [normalized];
  return chunks.map((chunk) => chunk.trim()).filter(Boolean);
}

function allocateSpeechSentenceDurations(sentences, totalDurationMs) {
  const totalWeight = sentences.reduce((sum, sentence) => sum + Math.max(16, sentence.length), 0) || 1;
  const usableDuration = Math.max(sentences.length * 500, Number(totalDurationMs) || 0);
  return sentences.map((sentence) => {
    const weight = Math.max(16, sentence.length);
    return Math.max(450, Math.round((usableDuration * weight) / totalWeight));
  });
}

function scheduleSpeechBubbleSentences(text, totalDurationMs, previewToken) {
  clearSpeechBubbleSequence();
  clearSpeechBubbleHideTimer();

  const sentences = splitSpeechIntoSentences(text);
  if (!sentences.length) {
    hideSpeechBubble({ immediate: true });
    return;
  }

  const durations = allocateSpeechSentenceDurations(sentences, totalDurationMs);
  let elapsedMs = 0;
  sentences.forEach((sentence, index) => {
    const sentenceDurationMs = durations[index] || 900;
    const showTimer = window.setTimeout(() => {
      if (previewToken !== speechGeneration) {
        return;
      }
      showSpeechBubble(sentence);
      const visibleDurationMs = Math.max(280, sentenceDurationMs - SPEECH_BUBBLE_FADE_MS - SPEECH_SENTENCE_GAP_MS);
      const hideTimer = window.setTimeout(() => {
        if (previewToken === speechGeneration) {
          hideSpeechBubble({ clearSequence: false });
        }
      }, visibleDurationMs);
      bubbleSequenceTimeouts.push(hideTimer);
    }, elapsedMs);
    bubbleSequenceTimeouts.push(showTimer);
    elapsedMs += sentenceDurationMs;
  });
}

async function resolveAudioDurationMs(audioEl, fallbackDurationMs, timeoutMs = 900) {
  const readDuration = () => (
    Number.isFinite(audioEl?.duration) && audioEl.duration > 0
      ? audioEl.duration * 1000
      : 0
  );
  const existingDurationMs = readDuration();
  if (existingDurationMs > 0) {
    return existingDurationMs;
  }

  audioEl?.load?.();
  await new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timeoutId);
      audioEl?.removeEventListener("loadedmetadata", finish);
      audioEl?.removeEventListener("durationchange", finish);
      audioEl?.removeEventListener("canplay", finish);
      resolve();
    };
    const timeoutId = window.setTimeout(finish, timeoutMs);
    audioEl?.addEventListener("loadedmetadata", finish, { once: true });
    audioEl?.addEventListener("durationchange", finish, { once: true });
    audioEl?.addEventListener("canplay", finish, { once: true });
  });

  return readDuration() || fallbackDurationMs;
}

function getDragPoint(event) {
  return {
    screenX: Math.round(Number(event.screenX) || 0),
    screenY: Math.round(Number(event.screenY) || 0)
  };
}

function setupMoveModeDragging() {
  if (!moveOverlay) {
    return;
  }

  let dragging = false;

  moveOverlay.addEventListener("pointerdown", async (event) => {
    if (!currentState.moveMode || event.button !== 0) {
      return;
    }
    event.preventDefault();
    dragging = true;
    try {
      moveOverlay.setPointerCapture(event.pointerId);
    } catch (_) {
      // pointer capture can fail if the pointer has already been released
    }
    const didBeginDrag = await window.catbotDesktop.beginAvatarDrag(getDragPoint(event));
    dragging = Boolean(didBeginDrag);
  });

  moveOverlay.addEventListener("pointermove", (event) => {
    if (!dragging || !currentState.moveMode) {
      return;
    }
    event.preventDefault();
    window.catbotDesktop.dragAvatarWindow(getDragPoint(event));
  });

  const endDrag = async (event) => {
    if (!dragging) {
      return;
    }
    event.preventDefault();
    dragging = false;
    try {
      moveOverlay.releasePointerCapture(event.pointerId);
    } catch (_) {
      // ignore release failures
    }
    await window.catbotDesktop.endAvatarDrag();
  };

  moveOverlay.addEventListener("pointerup", endDrag);
  moveOverlay.addEventListener("pointercancel", endDrag);
  window.addEventListener("blur", () => {
    if (dragging) {
      dragging = false;
      window.catbotDesktop.endAvatarDrag();
    }
  });
}

function setQuickHudStatus(message) {
  if (quickHudStatus) {
    quickHudStatus.textContent = message;
  }
}

function formatQuickStatus(message) {
  const text = String(message || "").replace(/\s+/g, " ").trim();
  return text.length > 120 ? `${text.slice(0, 117)}...` : text;
}

function modelDisplayName(modelPath) {
  const normalized = String(modelPath || "").replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() || "None";
}

function setHudPanel(panelName) {
  activeHudPanel = String(panelName || "");
  document.body.classList.toggle("hud-sheet-visible", Boolean(activeHudPanel));
  for (const panel of hudPanels) {
    panel.classList.toggle("is-active", panel.dataset.hudPanel === activeHudPanel);
  }
  for (const button of hudPanelButtons) {
    button.classList.toggle("is-active", button.dataset.hudPanelButton === activeHudPanel);
  }
  for (const button of quickHud?.querySelectorAll("[data-quick-action]") || []) {
    const action = button.dataset.quickAction;
    button.classList.toggle(
      "is-active",
      (action === "focus-chat" && activeHudPanel === "chat") ||
        (action === "models" && activeHudPanel === "models") ||
        (action === "controls" && activeHudPanel === "settings") ||
        (action === "screen" && activeHudPanel === "status") ||
        (action === "move" && currentState.moveMode) ||
        (action === "microphone" && micRecorder?.state === "recording")
    );
  }
  if (activeHudPanel === "chat") {
    requestAnimationFrame(() => quickChatInput?.focus());
  } else if (activeHudPanel === "auth") {
    requestAnimationFrame(() => hudAuthUsername?.focus());
  } else if (activeHudPanel === "status") {
    requestAnimationFrame(() => hudSpeechText?.focus());
  }
}

function closeHudPanel() {
  setHudPanel("");
}

function renderHudChat(history = []) {
  if (!hudChatLog) {
    return;
  }
  hudChatLog.replaceChildren();
  const messages = Array.isArray(history) ? history : [];
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "hud-chat-empty";
    empty.textContent = "No desktop chat yet. Use the prompt bar below to talk to CATBot.";
    hudChatLog.appendChild(empty);
    return;
  }
  for (const message of messages) {
    const role = message.role === "assistant" ? "assistant" : "user";
    const item = document.createElement("article");
    item.className = `hud-chat-message ${role}`;
    const label = document.createElement("strong");
    label.textContent = role === "assistant" ? "CATBot" : "You";
    const content = document.createElement("span");
    content.textContent = String(message.content || "");
    item.append(label, content);
    hudChatLog.appendChild(item);
  }
  hudChatLog.scrollTop = hudChatLog.scrollHeight;
}

function renderAuthStatus(status = currentAuthStatus) {
  currentAuthStatus = status || {};
  const signedIn = Boolean(currentAuthStatus.authenticated);
  if (hudAuthChip) {
    hudAuthChip.textContent = signedIn ? `Signed in${currentAuthStatus.username ? `: ${currentAuthStatus.username}` : ""}` : "Not signed in";
  }
  if (hudAuthStatus) {
    hudAuthStatus.textContent = signedIn
      ? "Desktop HUD requests include CATBot proxy auth."
      : "Sign in to use protected CATBot proxy features.";
  }
  if (hudAuthLogoutBtn) {
    hudAuthLogoutBtn.disabled = !signedIn;
  }
}

function renderHudState(state = currentState) {
  renderHudChat(state.desktopChatHistory);
  if (hudAvatarMode) {
    hudAvatarMode.value = state.mode === "live2d" ? "live2d" : "vrm";
  }
  populateHudModels(state.modelPath);
  const scale = Math.max(0.25, Math.min(2.5, Number(state.scale) || 1));
  const opacity = Math.max(0.35, Math.min(1, Number(state.opacity) || 1));
  if (hudScaleRange) {
    hudScaleRange.value = String(scale);
  }
  if (hudScaleValue) {
    hudScaleValue.textContent = `${scale.toFixed(2)}x`;
  }
  if (hudOpacityRange) {
    hudOpacityRange.value = String(opacity);
  }
  if (hudOpacityValue) {
    hudOpacityValue.textContent = opacity.toFixed(2);
  }
  const vrmTransform = getCurrentVrmTransform(state);
  if (hudVrmXRange) {
    hudVrmXRange.value = String(vrmTransform.positionX);
    hudVrmXRange.disabled = state.mode === "live2d";
  }
  if (hudVrmYRange) {
    hudVrmYRange.value = String(vrmTransform.positionY);
    hudVrmYRange.disabled = state.mode === "live2d";
  }
  if (hudVrmRotationRange) {
    hudVrmRotationRange.value = String(vrmTransform.rotation);
    hudVrmRotationRange.disabled = state.mode === "live2d";
  }
  if (hudVrmXValue) {
    hudVrmXValue.textContent = vrmTransform.positionX.toFixed(2);
  }
  if (hudVrmYValue) {
    hudVrmYValue.textContent = vrmTransform.positionY.toFixed(2);
  }
  if (hudVrmRotationValue) {
    hudVrmRotationValue.textContent = `${Math.round(vrmTransform.rotation)}°`;
  }
  for (const button of document.querySelectorAll("[data-hud-expression]")) {
    button.classList.toggle("is-active", button.dataset.hudExpression === String(state.expression || "neutral"));
  }
  if (hudProxyUrl) {
    hudProxyUrl.value = state.proxyBaseUrl || "";
  }
  if (hudWebUrl) {
    hudWebUrl.value = state.webClientUrl || "";
  }
  if (hudChatEndpoint) {
    hudChatEndpoint.value = state.chatEndpoint || "";
  }
  if (hudChatModel) {
    hudChatModel.value = state.chatModel || "";
  }
  if (hudChatApiKey) {
    hudChatApiKey.value = "";
    hudChatApiKey.placeholder = state.chatApiKeyConfigured
      ? "Provider key saved; leave blank to keep it"
      : "Optional for endpoint override";
  }
  if (hudTtsEndpoint) {
    hudTtsEndpoint.value = state.ttsEndpoint || "";
  }
  if (hudTtsModel) {
    hudTtsModel.value = state.ttsModel || "tts-1";
  }
  if (hudTtsVoice) {
    hudTtsVoice.value = state.ttsVoice || "alloy";
  }
  if (hudToggleSpeakBtn) {
    hudToggleSpeakBtn.textContent = `Speak Replies: ${state.speakChatReplies === false ? "Off" : "On"}`;
  }
  if (hudToggleClickthroughBtn) {
    hudToggleClickthroughBtn.textContent = `Click-Through: ${state.clickThrough ? "On" : "Off"}`;
  }
  if (hudToggleTopmostBtn) {
    hudToggleTopmostBtn.textContent = `Always On Top: ${state.alwaysOnTop ? "On" : "Off"}`;
  }
  if (hudToggleStartTrayBtn) {
    hudToggleStartTrayBtn.textContent = `Start To Tray: ${state.startToTray ? "On" : "Off"}`;
  }
  if (hudToggleLaunchLoginBtn) {
    hudToggleLaunchLoginBtn.textContent = `Launch Login: ${state.launchAtLogin ? "On" : "Off"}`;
  }
  if (hudStatusOutput) {
    hudStatusOutput.textContent = JSON.stringify(
      {
        mode: state.mode,
        model: modelDisplayName(state.modelPath),
        window: {
          visible: state.visible,
          clickThrough: state.clickThrough,
          moveMode: state.moveMode,
          alwaysOnTop: state.alwaysOnTop
        },
        auth: {
          authenticated: Boolean(currentAuthStatus.authenticated),
          username: currentAuthStatus.username || ""
        },
        proxyBaseUrl: state.proxyBaseUrl,
        webClientUrl: state.webClientUrl,
        chatEndpoint: state.chatEndpoint || "(proxy default)",
        chatModel: state.chatModel || "(default)",
        chatApiKeyConfigured: Boolean(state.chatApiKeyConfigured),
        speakChatReplies: state.speakChatReplies !== false,
        ttsEndpoint: state.ttsEndpoint || "(not set)"
      },
      null,
      2
    );
  }
}

function populateHudModels(selectedPath = currentState.modelPath) {
  if (!hudAvatarModel) {
    return;
  }
  const selectedMode = currentState.mode === "live2d" ? "live2d" : "vrm";
  const models = selectedMode === "live2d" ? availableModels.live2d || [] : availableModels.vrm || [];
  const currentOptions = Array.from(hudAvatarModel.options).map((option) => option.value).join("\n");
  if (currentOptions !== models.join("\n")) {
    hudAvatarModel.replaceChildren();
    for (const modelPath of models) {
      const option = document.createElement("option");
      option.value = modelPath;
      option.textContent = modelDisplayName(modelPath);
      hudAvatarModel.appendChild(option);
    }
  }
  hudAvatarModel.value = selectedPath || models[0] || "";
}

function getHudVrmTransformPatch() {
  if (currentState.mode !== "vrm" || !currentState.modelPath) {
    return {};
  }
  const transform = {
    ...getCurrentVrmTransform(currentState),
    scale: Number(hudScaleRange?.value || currentState.scale || 1),
    positionX: Number(hudVrmXRange?.value || 0),
    positionY: Number(hudVrmYRange?.value || 0),
    rotation: Number(hudVrmRotationRange?.value || 0)
  };
  return {
    vrmTransforms: {
      ...(currentState.vrmTransforms || {}),
      [currentState.modelPath]: transform
    }
  };
}

function getHudSettingsPatch() {
  const patch = {
    webClientUrl: hudWebUrl?.value.trim() || "",
    proxyBaseUrl: hudProxyUrl?.value.trim() || currentState.proxyBaseUrl,
    chatEndpoint: hudChatEndpoint?.value.trim() || "",
    chatModel: hudChatModel?.value.trim() || "",
    ttsEndpoint: hudTtsEndpoint?.value.trim() || "",
    ttsModel: hudTtsModel?.value.trim() || "tts-1",
    ttsVoice: hudTtsVoice?.value.trim() || "alloy"
  };
  const typedProviderKey = hudChatApiKey?.value.trim() || "";
  if (typedProviderKey) {
    patch.chatApiKey = typedProviderKey;
  }
  return patch;
}

async function updateDesktopStateFromHud(patch) {
  const nextState = await window.catbotDesktop.setState(patch);
  currentState = nextState;
  renderHudState(currentState);
  return nextState;
}

function updateQuickHudVisualState() {
  if (!quickHud) {
    return;
  }
  const isRecording = Boolean(micRecorder && micRecorder.state === "recording");
  for (const button of quickHud.querySelectorAll("[data-quick-action]")) {
    const action = button.dataset.quickAction;
    button.classList.toggle("is-active", action === "microphone" && isRecording);
    button.classList.toggle("has-attachment", action === "screen" && Boolean(pendingScreenSnapshot));
  }
}

function syncQuickHudControls(state = currentState) {
  if (!quickHud) {
    return;
  }
  const isVisible = Boolean(state.quickHudVisible);
  document.body.classList.toggle("quick-hud-visible", isVisible);
  if (!isVisible) {
    closeHudPanel();
  }
  for (const button of quickHud.querySelectorAll("[data-quick-action]")) {
    const action = button.dataset.quickAction;
    const isActive =
      (action === "click-through" && !state.clickThrough) ||
      (action === "move" && state.moveMode) ||
      (action === "microphone" && micRecorder?.state === "recording") ||
      (action === "speak" && state.speakChatReplies !== false) ||
      (action === "focus-chat" && activeHudPanel === "chat") ||
      (action === "models" && activeHudPanel === "models") ||
      (action === "controls" && activeHudPanel === "settings") ||
      (action === "screen" && activeHudPanel === "status");
    button.classList.toggle("is-active", isActive);
    button.classList.toggle("is-muted", action === "speak" && state.speakChatReplies === false);
    button.classList.toggle("has-attachment", action === "screen" && Boolean(pendingScreenSnapshot));
  }
  if (isVisible && !quickHudWasVisible) {
    requestAnimationFrame(() => quickChatInput?.focus());
  }
  quickHudWasVisible = isVisible;
  renderHudState(state);
}

async function sendQuickChatMessage() {
  const text = String(quickChatInput?.value || "").trim() || (pendingScreenSnapshot ? "What can you see on my screen?" : "");
  if (!text) {
    return;
  }
  if (quickChatSend) {
    quickChatSend.disabled = true;
    quickChatSend.setAttribute("aria-busy", "true");
  }
  setQuickHudStatus("Asking CATBot...");
  try {
    const hiddenState = await window.catbotDesktop.setQuickHudVisible(false);
    if (hiddenState) {
      currentState = hiddenState;
      applyStateToScene(currentState);
    }
  } catch (error) {
    console.warn("Could not autohide quick HUD before sending chat message:", error);
  }
  try {
    const result = await window.catbotDesktop.sendChatMessage({
      message: text,
      speakReply: currentState.speakChatReplies !== false,
      proxyBaseUrl: currentState.proxyBaseUrl,
      chatEndpoint: currentState.chatEndpoint,
      chatModel: currentState.chatModel,
      screenImageDataUrl: pendingScreenSnapshot?.dataUrl || ""
    });
    if (quickChatInput) {
      quickChatInput.value = "";
    }
    pendingScreenSnapshot = null;
    updateQuickHudVisualState();
    if (result?.state) {
      currentState = result.state;
      applyStateToScene(currentState);
    }
    setQuickHudStatus("Reply sent to the avatar.");
  } catch (error) {
    const message = String(error?.message || error || "Desktop chat failed.");
    setQuickHudStatus(formatQuickStatus(message));
    await window.catbotDesktop.setState({
      expression: "sad",
      speechBubbleText: message,
      speechDurationMs: 5000,
      speechTriggerId: Date.now()
    });
  } finally {
    if (quickChatSend) {
      quickChatSend.disabled = false;
      quickChatSend.removeAttribute("aria-busy");
    }
  }
}

async function attachScreenSnapshot() {
  setQuickHudStatus("Capturing screen snapshot...");
  try {
    pendingScreenSnapshot = await window.catbotDesktop.captureScreenSnapshot();
    updateQuickHudVisualState();
    setQuickHudStatus("Screen snapshot attached to the next prompt.");
    quickChatInput?.focus();
  } catch (error) {
    const message = String(error?.message || error || "Screen snapshot failed.");
    setQuickHudStatus(formatQuickStatus(message));
  }
}

function cleanupMicStream() {
  if (micStopTimer) {
    clearTimeout(micStopTimer);
    micStopTimer = 0;
  }
  try {
    micStream?.getTracks?.().forEach((track) => track.stop());
  } catch (_) {
    // ignore track cleanup failures
  }
  micStream = null;
}

async function transcribeMicBlob(blob) {
  if (!blob || blob.size <= 0) {
    throw new Error("No microphone audio was captured.");
  }
  const result = await window.catbotDesktop.transcribeAudio({
    audioBuffer: await blob.arrayBuffer(),
    mimeType: blob.type || "audio/webm",
    proxyBaseUrl: currentState.proxyBaseUrl
  });
  const text = String(result?.text || "").trim();
  if (!text) {
    throw new Error("Transcription returned no text.");
  }
  return text;
}

function stopMicrophoneRecording() {
  if (!micRecorder || micRecorder.state !== "recording") {
    return;
  }
  setQuickHudStatus("Transcribing...");
  try {
    micRecorder.requestData();
  } catch (_) {
    // Some Chromium builds do not allow requestData immediately before stop.
  }
  micRecorder.stop();
}

async function startMicrophoneRecording() {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    setQuickHudStatus("Microphone STT is not available in this Electron runtime.");
    return;
  }

  setQuickHudStatus("Listening...");
  micChunks = [];
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    });
    const supportedMimeTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4"
    ];
    const mimeType = supportedMimeTypes.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";
    micRecorder = mimeType ? new MediaRecorder(micStream, { mimeType }) : new MediaRecorder(micStream);
    micRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        micChunks.push(event.data);
      }
    });
    micRecorder.addEventListener("stop", async () => {
      const recordedMimeType = micRecorder?.mimeType || mimeType || "audio/webm";
      const blob = new Blob(micChunks, { type: recordedMimeType });
      micRecorder = null;
      cleanupMicStream();
      updateQuickHudVisualState();
      try {
        const text = await transcribeMicBlob(blob);
        if (quickChatInput) {
          quickChatInput.value = quickChatInput.value ? `${quickChatInput.value.trim()} ${text}` : text;
        }
        setQuickHudStatus("Transcription added to the prompt.");
        quickChatInput?.focus();
      } catch (error) {
        const message = String(error?.message || error || "Transcription failed.");
        setQuickHudStatus(formatQuickStatus(message));
      }
    });
    micRecorder.start(250);
    micStopTimer = window.setTimeout(stopMicrophoneRecording, 10000);
    updateQuickHudVisualState();
  } catch (error) {
    micRecorder = null;
    cleanupMicStream();
    updateQuickHudVisualState();
    const message = String(error?.message || error || "Could not start microphone.");
    setQuickHudStatus(formatQuickStatus(message));
  }
}

async function toggleMicrophoneRecording() {
  if (micRecorder?.state === "recording") {
    stopMicrophoneRecording();
    return;
  }
  await startMicrophoneRecording();
}

function setupQuickHud() {
  if (!quickHud) {
    return;
  }

  quickHud.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  quickHud.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-quick-action]");
    if (!button) {
      return;
    }
    event.preventDefault();
    const action = button.dataset.quickAction;
    if (action === "focus-chat") {
      setHudPanel("chat");
      quickChatInput?.focus();
    } else if (action === "microphone") {
      await toggleMicrophoneRecording();
    } else if (action === "screen") {
      await attachScreenSnapshot();
    } else if (action === "models") {
      setHudPanel("models");
    } else if (action === "move") {
      await window.catbotDesktop.toggleMoveMode();
    } else if (action === "click-through") {
      await window.catbotDesktop.toggleClickThrough();
    } else if (action === "controls") {
      setHudPanel("settings");
    } else if (action === "speak") {
      await updateDesktopStateFromHud({ speakChatReplies: currentState.speakChatReplies === false });
      setQuickHudStatus(currentState.speakChatReplies === false ? "Spoken replies off." : "Spoken replies on.");
    } else if (action === "hide") {
      await window.catbotDesktop.setState({ visible: false, quickHudVisible: false });
    } else if (action === "close") {
      await window.catbotDesktop.setQuickHudVisible(false);
    }
  });

  quickChatForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuickChatMessage();
  });

  hudSheet?.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  for (const button of hudPanelButtons) {
    button.addEventListener("click", () => setHudPanel(button.dataset.hudPanelButton));
  }

  for (const button of document.querySelectorAll("[data-hud-panel-close]")) {
    button.addEventListener("click", closeHudPanel);
  }

  hudClearChatBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.clearChatHistory();
    renderHudState(currentState);
  });

  hudAuthLoginBtn?.addEventListener("click", () => runHudAuth("login"));
  hudAuthSignupBtn?.addEventListener("click", () => runHudAuth("signup"));
  hudAuthLogoutBtn?.addEventListener("click", async () => {
    currentAuthStatus = await window.catbotDesktop.logout();
    renderAuthStatus(currentAuthStatus);
  });

  for (const input of [hudAuthUsername, hudAuthPassword]) {
    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runHudAuth("login");
      }
    });
  }

  hudAvatarMode?.addEventListener("change", async () => {
    await updateDesktopStateFromHud({ mode: hudAvatarMode.value, modelPath: "" });
  });

  hudAvatarModel?.addEventListener("change", async () => {
    await updateDesktopStateFromHud({ modelPath: hudAvatarModel.value });
  });

  hudScaleRange?.addEventListener("input", async () => {
    const scale = Number(hudScaleRange.value);
    if (hudScaleValue) {
      hudScaleValue.textContent = `${scale.toFixed(2)}x`;
    }
    await updateDesktopStateFromHud({ scale, ...getHudVrmTransformPatch() });
  });

  hudOpacityRange?.addEventListener("input", async () => {
    const opacity = Number(hudOpacityRange.value);
    if (hudOpacityValue) {
      hudOpacityValue.textContent = opacity.toFixed(2);
    }
    await updateDesktopStateFromHud({ opacity });
  });

  hudVrmXRange?.addEventListener("input", async () => {
    if (hudVrmXValue) {
      hudVrmXValue.textContent = Number(hudVrmXRange.value).toFixed(2);
    }
    await updateDesktopStateFromHud(getHudVrmTransformPatch());
  });

  hudVrmYRange?.addEventListener("input", async () => {
    if (hudVrmYValue) {
      hudVrmYValue.textContent = Number(hudVrmYRange.value).toFixed(2);
    }
    await updateDesktopStateFromHud(getHudVrmTransformPatch());
  });

  hudVrmRotationRange?.addEventListener("input", async () => {
    if (hudVrmRotationValue) {
      hudVrmRotationValue.textContent = `${Math.round(Number(hudVrmRotationRange.value))}°`;
    }
    await updateDesktopStateFromHud(getHudVrmTransformPatch());
  });

  hudResetVrmBtn?.addEventListener("click", async () => {
    if (currentState.mode !== "vrm" || !currentState.modelPath) {
      return;
    }
    await updateDesktopStateFromHud({
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

  hudRescanModelsBtn?.addEventListener("click", async () => {
    availableModels = await window.catbotDesktop.listModels();
    populateHudModels(currentState.modelPath);
    setQuickHudStatus("Model list refreshed.");
  });

  for (const button of document.querySelectorAll("[data-hud-expression]")) {
    button.addEventListener("click", async () => {
      await updateDesktopStateFromHud({ expression: button.dataset.hudExpression || "neutral" });
    });
  }

  hudSaveSettingsBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud(getHudSettingsPatch());
    setQuickHudStatus("Settings saved.");
  });

  hudToggleSpeakBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ speakChatReplies: currentState.speakChatReplies === false });
  });

  hudClearProviderKeyBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.clearProviderApiKey();
    if (hudChatApiKey) {
      hudChatApiKey.value = "";
    }
    renderHudState(currentState);
    setQuickHudStatus("Provider API key cleared.");
  });

  hudToggleClickthroughBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.toggleClickThrough();
    renderHudState(currentState);
  });

  hudToggleTopmostBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ alwaysOnTop: !currentState.alwaysOnTop });
  });

  hudCenterAvatarBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.centerAvatarWindow();
    renderHudState(currentState);
  });

  hudToggleStartTrayBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ startToTray: !currentState.startToTray });
  });

  hudToggleLaunchLoginBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ launchAtLogin: !currentState.launchAtLogin });
  });

  hudHideAvatarBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ visible: false, quickHudVisible: false });
  });

  hudOpenWebBtn?.addEventListener("click", async () => {
    await window.catbotDesktop.launchWebClient();
  });

  hudOpenBrowserBtn?.addEventListener("click", async () => {
    await window.catbotDesktop.launchExternalWebClient();
  });

  hudPreviewSpeechBtn?.addEventListener("click", async () => {
    const text = String(hudSpeechText?.value || "").trim();
    if (!text) {
      setQuickHudStatus("Speech preview text is required.");
      return;
    }
    const durationMs = Math.max(1600, Math.min(8000, text.length * 90));
    await updateDesktopStateFromHud({
      ...getHudSettingsPatch(),
      speechBubbleText: text,
      speechDurationMs: durationMs,
      speechTriggerId: Date.now()
    });
    setQuickHudStatus("Previewing speech.");
  });

  hudClearSpeechBtn?.addEventListener("click", async () => {
    if (hudSpeechText) {
      hudSpeechText.value = "";
    }
    await updateDesktopStateFromHud({
      speechBubbleText: "",
      speechDurationMs: 300,
      speechTriggerId: Date.now()
    });
    setQuickHudStatus("Speech bubble cleared.");
  });

  window.addEventListener("keydown", async (event) => {
    if (!currentState.quickHudVisible) {
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      if (activeHudPanel) {
        closeHudPanel();
      } else {
        await window.catbotDesktop.setQuickHudVisible(false);
      }
      return;
    }

    if (!event.ctrlKey || event.altKey || event.metaKey) {
      return;
    }

    const key = event.key.toLowerCase();
    if (key === "m") {
      event.preventDefault();
      await toggleMicrophoneRecording();
    } else if (key === "enter") {
      event.preventDefault();
      await sendQuickChatMessage();
    } else if (key === "l") {
      event.preventDefault();
      closeHudPanel();
      quickChatInput?.focus();
    } else if (key === "1") {
      event.preventDefault();
      setHudPanel("chat");
    } else if (key === "2") {
      event.preventDefault();
      setHudPanel("auth");
    } else if (key === "3") {
      event.preventDefault();
      setHudPanel("models");
    } else if (key === "4") {
      event.preventDefault();
      setHudPanel("settings");
    } else if (key === "5") {
      event.preventDefault();
      setHudPanel("status");
    } else if (key === "s" && event.shiftKey) {
      event.preventDefault();
      await attachScreenSnapshot();
    } else if (key === "v" && event.shiftKey) {
      event.preventDefault();
      await updateDesktopStateFromHud({ speakChatReplies: currentState.speakChatReplies === false });
      setQuickHudStatus(currentState.speakChatReplies === false ? "Spoken replies off." : "Spoken replies on.");
    }
  });

  window.addEventListener("contextmenu", async (event) => {
    if (currentState.moveMode) {
      return;
    }
    event.preventDefault();
    await window.catbotDesktop.toggleQuickHud();
  });

  syncQuickHudControls(currentState);
}

async function runHudAuth(action) {
  const username = String(hudAuthUsername?.value || "").trim();
  const password = String(hudAuthPassword?.value || "");
  if (!username || !password) {
    if (hudAuthStatus) {
      hudAuthStatus.textContent = "Username and password are required.";
    }
    return;
  }
  for (const button of [hudAuthLoginBtn, hudAuthSignupBtn]) {
    if (button) {
      button.disabled = true;
    }
  }
  if (hudAuthStatus) {
    hudAuthStatus.textContent = action === "signup" ? "Creating account..." : "Signing in...";
  }
  try {
    currentAuthStatus = await window.catbotDesktop.authenticate({
      action,
      username,
      password,
      proxyBaseUrl: hudProxyUrl?.value.trim() || currentState.proxyBaseUrl
    });
    if (hudAuthPassword) {
      hudAuthPassword.value = "";
    }
    renderAuthStatus(currentAuthStatus);
  } catch (error) {
    if (hudAuthStatus) {
      hudAuthStatus.textContent = String(error?.message || error || "Authentication failed.");
    }
  } finally {
    for (const button of [hudAuthLoginBtn, hudAuthSignupBtn]) {
      if (button) {
        button.disabled = false;
      }
    }
  }
}

function initializeScene() {
  if (THREE.ColorManagement) {
    THREE.ColorManagement.enabled = true;
  }
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
  camera.position.set(0, 0, 5);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({
    canvas: vrmCanvas,
    antialias: false,
    alpha: true,
    premultipliedAlpha: false,
    powerPreference: "low-power",
    precision: "mediump",
    failIfMajorPerformanceCaveat: false
  });
  renderer.setPixelRatio(Math.min(1.25, window.devicePixelRatio || 1));
  renderer.setClearColor(0x000000, 0);
  if ("outputColorSpace" in renderer && THREE.SRGBColorSpace) {
    renderer.outputColorSpace = THREE.SRGBColorSpace;
  }
  if ("toneMapping" in renderer) {
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.toneMappingExposure = 1;
  }

  const ambient = new THREE.AmbientLight(0x404040, 0.6);
  const directional = new THREE.DirectionalLight(0xffffff, 0.8);
  directional.position.set(1, 1, 1);
  scene.add(ambient, directional);

  clock = new THREE.Clock();
  resizeRenderer();
  renderLoopActive = true;
  animate();
}

function resizeRenderer() {
  if (!renderer || !camera) {
    return;
  }
  const width = Math.max(window.innerWidth, 1);
  const height = Math.max(window.innerHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();

  if (live2dApp) {
    live2dApp.renderer.resize(width, height);
    applyLive2dLayout();
  }
}

function refreshTransparentSurface() {
  document.documentElement.style.background = "transparent";
  document.body.style.background = "transparent";
  vrmCanvas.style.background = "transparent";
  live2dCanvas.style.background = "transparent";
  if (!renderer || !scene || !camera || webglContextLost) {
    return;
  }
  renderer.setClearColor(0x000000, 0);
  try {
    renderer.clear(true, true, true);
    renderer.render(scene, camera);
  } catch (error) {
    webglContextLost = true;
    renderLoopActive = false;
    showRenderFallback("Avatar renderer failed. Showing fallback image.", error);
  }
}

function removeCurrentVrmModel() {
  if (!vrmModel) {
    return;
  }
  if (vrmRuntime?.mixer) {
    try {
      vrmRuntime.mixer.stopAllAction();
      vrmRuntime.mixer.uncacheRoot(vrmModel.scene);
    } catch (_) {
      // ignore mixer cleanup issues
    }
  }
  clearVrmAnimationTimers(vrmRuntime);
  if (lookTarget) {
    scene.remove(lookTarget);
    lookTarget = null;
  }
  scene.remove(vrmModel.scene);
  const disposedTextures = new Set();
  vrmModel.scene.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose();
    }
    if (child.material) {
      if (Array.isArray(child.material)) {
        for (const material of child.material) {
          disposeMaterialTextures(material, disposedTextures);
          material.dispose();
        }
      } else {
        disposeMaterialTextures(child.material, disposedTextures);
        child.material.dispose();
      }
    }
  });
  vrmModel = null;
  vrmRuntime = null;
}

function removeCurrentLive2dModel() {
  if (!live2dModel) {
    return;
  }
  try {
    live2dApp?.stage?.removeChildren();
  } catch (_) {
    // ignore cleanup issues
  }
  try {
    live2dModel.destroy({ children: true, texture: true, baseTexture: true });
  } catch (_) {
    // ignore cleanup issues
  }
  live2dModel = null;
}

function extractVrm(gltf) {
  return gltf?.userData?.vrm || gltf?.parser?.userData?.vrm || gltf?.scene?.userData?.vrm || null;
}

function normalizeMaterialColorSpace(vrm) {
  if (!vrm?.scene) {
    return;
  }
  vrm.scene.traverse((child) => {
    const materials = child?.material ? (Array.isArray(child.material) ? child.material : [child.material]) : [];
    for (const material of materials) {
      if (!material) {
        continue;
      }
      for (const textureKey of ["map", "emissiveMap"]) {
        const texture = material[textureKey];
        if (texture && "colorSpace" in texture && THREE.SRGBColorSpace) {
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.needsUpdate = true;
        }
      }
      material.needsUpdate = true;
    }
  });
}

function getMaterialTexture(material, key) {
  const texture = material?.[key];
  return texture && texture.isTexture ? texture : null;
}

function getMaterialBaseColor(material) {
  const color = material?.color || material?.litFactor || material?.uniforms?.litFactor?.value;
  return color && color.isColor ? color.clone() : new THREE.Color(0xffffff);
}

function createDesktopFallbackMaterial(sourceMaterial) {
  const diffuseMap = getMaterialTexture(sourceMaterial, "map");
  const alphaMap = getMaterialTexture(sourceMaterial, "alphaMap");
  const alphaTest = Number.isFinite(Number(sourceMaterial?.alphaTest)) ? Number(sourceMaterial.alphaTest) : 0;
  const options = {
    color: getMaterialBaseColor(sourceMaterial),
    map: diffuseMap,
    alphaMap,
    transparent: Boolean(sourceMaterial?.transparent) || Number(sourceMaterial?.opacity) < 1 || Boolean(alphaMap),
    opacity: Number.isFinite(Number(sourceMaterial?.opacity)) ? Number(sourceMaterial.opacity) : 1,
    alphaTest,
    side: sourceMaterial?.side ?? THREE.FrontSide,
    depthWrite: sourceMaterial?.depthWrite ?? true,
    depthTest: sourceMaterial?.depthTest ?? true
  };
  if (sourceMaterial?.vertexColors) {
    options.vertexColors = sourceMaterial.vertexColors;
  }
  const material = new THREE.MeshBasicMaterial(options);
  material.name = sourceMaterial?.name ? `${sourceMaterial.name}-desktop-fallback` : "desktop-fallback";
  if (sourceMaterial?.blending != null) {
    material.blending = sourceMaterial.blending;
  }
  if (sourceMaterial?.blendSrc != null) {
    material.blendSrc = sourceMaterial.blendSrc;
  }
  if (sourceMaterial?.blendDst != null) {
    material.blendDst = sourceMaterial.blendDst;
  }
  if (sourceMaterial?.blendEquation != null) {
    material.blendEquation = sourceMaterial.blendEquation;
  }
  if (sourceMaterial?.userData) {
    material.userData = { ...sourceMaterial.userData };
  }
  return material;
}

function disposeMaterialTexture(texture) {
  try {
    texture?.dispose?.();
  } catch (_) {
    // ignore texture cleanup issues
  }
}

function disposeMaterialTextures(material, disposedTextures = new Set(), retainedTextures = new Set()) {
  for (const key of DESKTOP_MATERIAL_TEXTURE_KEYS) {
    const texture = getMaterialTexture(material, key);
    if (!texture || retainedTextures.has(texture) || disposedTextures.has(texture)) {
      continue;
    }
    disposedTextures.add(texture);
    disposeMaterialTexture(texture);
  }
}

function disposeSourceMaterialResources(material, disposedTextures = new Set(), retainedTextures = new Set()) {
  if (!material) {
    return;
  }
  disposeMaterialTextures(material, disposedTextures, retainedTextures);
  try {
    material.dispose?.();
  } catch (_) {
    // ignore material cleanup issues
  }
}

function downscaleTextureForDesktop(texture, maxSize = DESKTOP_MAX_TEXTURE_SIZE) {
  const image = texture?.image;
  const width = Number(image?.naturalWidth || image?.videoWidth || image?.width || 0);
  const height = Number(image?.naturalHeight || image?.videoHeight || image?.height || 0);
  if (!texture || !image || width <= maxSize && height <= maxSize) {
    return;
  }
  const scale = Math.min(maxSize / width, maxSize / height);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) {
    return;
  }
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  texture.image = canvas;
  texture.needsUpdate = true;
}

function downscaleVrmTexturesForDesktop(vrm) {
  if (!vrm?.scene) {
    return;
  }
  const seenTextures = new Set();
  vrm.scene.traverse((child) => {
    const materials = child?.material ? (Array.isArray(child.material) ? child.material : [child.material]) : [];
    for (const material of materials) {
      for (const key of DESKTOP_MATERIAL_TEXTURE_KEYS) {
        const texture = material?.[key];
        if (!texture || seenTextures.has(texture)) {
          continue;
        }
        seenTextures.add(texture);
        downscaleTextureForDesktop(texture);
      }
    }
  });
}

function applyDesktopMaterialFallback(vrm) {
  if (!vrm?.scene) {
    return;
  }
  const disposedUnusedTextures = new Set();
  const retainedTextures = new Set();
  vrm.scene.traverse((child) => {
    const materials = child?.material ? (Array.isArray(child.material) ? child.material : [child.material]) : [];
    for (const material of materials) {
      for (const key of ["map", "alphaMap"]) {
        const texture = getMaterialTexture(material, key);
        if (texture) {
          retainedTextures.add(texture);
        }
      }
    }
  });
  vrm.scene.traverse((child) => {
    if (!child?.isMesh || !child.material) {
      return;
    }
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    const fallbackMaterials = materials.map(createDesktopFallbackMaterial);
    child.material = Array.isArray(child.material) ? fallbackMaterials : fallbackMaterials[0];
    for (const material of materials) {
      disposeSourceMaterialResources(material, disposedUnusedTextures, retainedTextures);
    }
  });
}

function getVrmMetaVersion(vrm) {
  return String(vrm?.meta?.metaVersion ?? vrm?.meta?.version ?? "").trim();
}

function isVrm0(vrm) {
  return getVrmMetaVersion(vrm) === "0";
}

function getHumanoidBoneNode(vrm, boneName) {
  try {
    if (vrm?.humanoid?.getNormalizedBoneNode) {
      return vrm.humanoid.getNormalizedBoneNode(boneName);
    }
  } catch (_) {
    // ignore
  }
  try {
    if (vrm?.humanoid?.getBoneNode) {
      return vrm.humanoid.getBoneNode(boneName);
    }
  } catch (_) {
    // ignore
  }
  return null;
}

function ensureLookTarget(vrm) {
  if (lookTarget) {
    scene.remove(lookTarget);
  }
  lookTarget = new THREE.Object3D();
  lookTarget.position.set(0, 1.2, 2.3);
  scene.add(lookTarget);
  try {
    if (vrm?.lookAt) {
      vrm.lookAt.target = lookTarget;
    }
  } catch (_) {
    // ignore unsupported look-at implementations
  }
}

function setupVrmRuntime(vrm) {
  const leftShoulder = getHumanoidBoneNode(vrm, "leftShoulder");
  const rightShoulder = getHumanoidBoneNode(vrm, "rightShoulder");
  const leftUpperArm = getHumanoidBoneNode(vrm, "leftUpperArm");
  const rightUpperArm = getHumanoidBoneNode(vrm, "rightUpperArm");
  const leftLowerArm = getHumanoidBoneNode(vrm, "leftLowerArm");
  const rightLowerArm = getHumanoidBoneNode(vrm, "rightLowerArm");
  const leftHand = getHumanoidBoneNode(vrm, "leftHand");
  const rightHand = getHumanoidBoneNode(vrm, "rightHand");
  const spineBone = getHumanoidBoneNode(vrm, "spine");
  const neckBone = getHumanoidBoneNode(vrm, "neck");
  const headBone = getHumanoidBoneNode(vrm, "head");

  vrmRuntime = {
    version: isVrm0(vrm) ? "0.0" : "1.0",
    idleStart: performance.now(),
    leftShoulder,
    rightShoulder,
    leftUpperArm,
    rightUpperArm,
    leftLowerArm,
    rightLowerArm,
    leftHand,
    rightHand,
    spineBone,
    neckBone,
    headBone,
    baseLeftArmZ: leftUpperArm ? leftUpperArm.rotation.z : 0,
    baseRightArmZ: rightUpperArm ? rightUpperArm.rotation.z : 0,
    baseLeftArmY: leftUpperArm ? leftUpperArm.rotation.y : 0,
    baseRightArmY: rightUpperArm ? rightUpperArm.rotation.y : 0,
    baseLeftUpperArmX: leftUpperArm ? leftUpperArm.rotation.x : 0,
    baseRightUpperArmX: rightUpperArm ? rightUpperArm.rotation.x : 0,
    baseLeftLowerArmZ: leftLowerArm ? leftLowerArm.rotation.z : 0,
    baseRightLowerArmZ: rightLowerArm ? rightLowerArm.rotation.z : 0,
    baseLeftHandY: leftHand ? leftHand.rotation.y : 0,
    baseRightHandY: rightHand ? rightHand.rotation.y : 0,
    baseSpineY: spineBone ? spineBone.position.y : 0,
    baseNeckX: neckBone ? neckBone.rotation.x : 0,
    baseNeckY: neckBone ? neckBone.rotation.y : 0,
    baseHeadX: headBone ? headBone.rotation.x : 0,
    baseHeadY: headBone ? headBone.rotation.y : 0,
    mixer: null,
    actions: {},
    activeActionKey: "",
    requestedActionKey: "",
    idleReplayTimerId: 0,
    idleHasPlayedOnce: false,
    emotionTimerId: 0
  };
}

function extractVrmAnimation(gltf) {
  if (gltf?.userData?.vrmAnimations?.length) {
    return gltf.userData.vrmAnimations[0];
  }
  if (gltf?.extensions?.VRMC_vrm_animation) {
    return gltf.extensions.VRMC_vrm_animation;
  }
  if (gltf?.parser?.userData?.vrmAnimations?.length) {
    return gltf.parser.userData.vrmAnimations[0];
  }
  return null;
}

async function loadVrmaAction(vrm, mixer, actionKey, relativePath) {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMAnimationLoaderPlugin(parser));

  const animationUrl = await window.catbotDesktop.resolveAssetUrl(relativePath);
  const gltf = await new Promise((resolve, reject) => {
    loader.load(animationUrl, resolve, undefined, reject);
  });

  const vrmAnimation = extractVrmAnimation(gltf);
  if (!vrmAnimation) {
    throw new Error(`VRMA data not found for ${relativePath}`);
  }

  let clip = null;
  if (typeof createVRMAnimationClip === "function") {
    clip = createVRMAnimationClip(vrmAnimation, vrm);
  }

  if (!clip) {
    throw new Error(`Unable to create VRMA clip for ${relativePath}`);
  }
  if (!Array.isArray(clip.tracks) || clip.tracks.length === 0) {
    throw new Error(`VRMA clip for ${relativePath} has no playable tracks`);
  }

  const action = mixer.clipAction(clip, vrm.scene);
  action.enabled = true;
  action.clampWhenFinished = false;
  action.loop = THREE.LoopOnce;
  action.repetitions = 1;
  action.setEffectiveTimeScale(1);
  action.setEffectiveWeight(1);
  action.name = actionKey;
  return action;
}

async function preloadVrmActions(vrm) {
  if (!ENABLE_DESKTOP_VRMA_PRELOAD) {
    return;
  }
  if (!vrmRuntime || vrmRuntime.version !== "1.0") {
    return;
  }

  const mixer = new THREE.AnimationMixer(vrm.scene);
  vrmRuntime.mixer = mixer;
  vrmRuntime.actions = {};
  vrmRuntime.activeActionKey = "";

  await Promise.all(Object.entries(VRM_ANIMATION_LIBRARY).map(async ([actionKey, relativePath]) => {
    try {
      vrmRuntime.actions[actionKey] = await loadVrmaAction(vrm, mixer, actionKey, relativePath);
    } catch (error) {
      console.warn(`Failed to preload VRMA action "${actionKey}":`, error);
    }
  }));

  if (!Object.keys(vrmRuntime.actions).length) {
    vrmRuntime.mixer = null;
  }
}

function clearVrmAnimationTimers(runtime = vrmRuntime) {
  if (!runtime) {
    return;
  }
  if (runtime.idleReplayTimerId) {
    clearTimeout(runtime.idleReplayTimerId);
    runtime.idleReplayTimerId = 0;
  }
  if (runtime.emotionTimerId) {
    clearTimeout(runtime.emotionTimerId);
    runtime.emotionTimerId = 0;
  }
}

function resetVrmPhysicsState(vrm = vrmModel) {
  try {
    vrm?.springBoneManager?.reset?.();
  } catch (_) {
    // Spring bone reset is best-effort; some VRM builds do not expose it.
  }
}

function getStableVrmFrameDeltas(rawDelta) {
  const finiteDelta = Number.isFinite(rawDelta) && rawDelta > 0 ? rawDelta : 1 / 60;
  if (finiteDelta > VRM_PHYSICS_RESET_DELTA_SECONDS) {
    resetVrmPhysicsState();
    smoothedVrmDelta = 1 / 60;
  }
  const animationDelta = Math.min(finiteDelta, VRM_MAX_ANIMATION_DELTA_SECONDS);
  const targetPhysicsDelta = Math.min(finiteDelta, VRM_MAX_PHYSICS_DELTA_SECONDS);
  smoothedVrmDelta += (targetPhysicsDelta - smoothedVrmDelta) * VRM_DELTA_SMOOTHING;
  return {
    animationDelta,
    physicsDelta: Math.min(smoothedVrmDelta, VRM_MAX_PHYSICS_DELTA_SECONDS)
  };
}

function stopVrmAction(action, fadeOutSeconds = VRM_ACTION_FADE_OUT_SECONDS) {
  if (!action) {
    return;
  }
  try {
    if (fadeOutSeconds > 0 && action.isRunning?.()) {
      action.fadeOut(fadeOutSeconds);
      window.setTimeout(() => {
        try {
          if (!action.isRunning?.() || action.getEffectiveWeight?.() < 0.02) {
            action.stop();
          }
        } catch (_) {
          // ignore delayed stop failures
        }
      }, Math.ceil(fadeOutSeconds * 1000) + 80);
    } else {
      action.stop();
    }
  } catch (_) {
    // ignore action stop failures
  }
}

function stopActiveVrmAction(fadeOutSeconds = VRM_ACTION_FADE_OUT_SECONDS) {
  if (!vrmRuntime?.mixer) {
    return;
  }

  const activeAction = vrmRuntime.actions?.[vrmRuntime.activeActionKey];
  stopVrmAction(activeAction, fadeOutSeconds);
  vrmRuntime.activeActionKey = "";
  vrmRuntime.requestedActionKey = "";
}

function hasActiveNonIdleVrmAction() {
  if (!vrmRuntime?.actions) {
    return false;
  }
  return Object.entries(vrmRuntime.actions).some(([key, action]) => key !== "idle" && action?.isRunning?.());
}

function hasRunningVrmAction() {
  if (!vrmRuntime?.actions) {
    return false;
  }
  return Object.values(vrmRuntime.actions).some((action) => action?.isRunning?.());
}

function playVrmAction(actionKey, options = {}) {
  if (!vrmRuntime?.mixer || !actionKey) {
    return;
  }
  const action = vrmRuntime.actions?.[actionKey];
  if (!action) {
    return;
  }

  const {
    loop = actionKey === "think" ? THREE.LoopRepeat : THREE.LoopOnce,
    repetitions = loop === THREE.LoopRepeat ? Infinity : 1,
    fadeInSeconds = actionKey === "idle" ? VRM_IDLE_ACTION_FADE_IN_SECONDS : VRM_ACTION_FADE_IN_SECONDS,
    fadeOutSeconds = actionKey === "idle" ? VRM_IDLE_ACTION_FADE_OUT_SECONDS : VRM_ACTION_FADE_OUT_SECONDS,
    forceRestart = false
  } = options;

  if (vrmRuntime.idleReplayTimerId) {
    clearTimeout(vrmRuntime.idleReplayTimerId);
    vrmRuntime.idleReplayTimerId = 0;
  }

  const previousActionKey = vrmRuntime.activeActionKey;
  const previousAction = previousActionKey && previousActionKey !== actionKey
    ? vrmRuntime.actions?.[previousActionKey]
    : null;

  if (vrmRuntime.activeActionKey === actionKey && forceRestart) {
    stopVrmAction(action, 0);
    vrmRuntime.activeActionKey = "";
  } else if (vrmRuntime.activeActionKey && vrmRuntime.activeActionKey !== actionKey) {
    stopVrmAction(previousAction, fadeOutSeconds);
    vrmRuntime.activeActionKey = "";
  }

  if (vrmRuntime.activeActionKey === actionKey && action.isRunning?.() && !forceRestart) {
    vrmRuntime.requestedActionKey = actionKey;
    return;
  }

  try {
    action.enabled = true;
    action.paused = false;
    action.loop = loop;
    action.repetitions = repetitions;
    action.clampWhenFinished = actionKey !== "idle";
    action.reset();
    action.setEffectiveWeight(1);
    action.setEffectiveTimeScale(1);
    action.fadeIn(fadeInSeconds);
    action.play();
    vrmRuntime.activeActionKey = actionKey;
    vrmRuntime.requestedActionKey = actionKey;
  } catch (error) {
    console.warn(`Failed to start VRMA action "${actionKey}":`, error);
    vrmRuntime.activeActionKey = "";
    vrmRuntime.requestedActionKey = "";
  }
}

function scheduleNextVrmIdlePlayback() {
  if (!vrmRuntime?.actions?.idle || vrmRuntime.idleReplayTimerId || hasActiveNonIdleVrmAction()) {
    return;
  }
  const delayMs = vrmRuntime.idleHasPlayedOnce
    ? 2600 + Math.round(Math.random() * 3600)
    : 0;
  vrmRuntime.idleReplayTimerId = window.setTimeout(() => {
    vrmRuntime.idleReplayTimerId = 0;
    if (!hasActiveNonIdleVrmAction()) {
      playVrmAction("idle", {
        loop: THREE.LoopOnce,
        repetitions: 1,
        fadeInSeconds: VRM_IDLE_ACTION_FADE_IN_SECONDS,
        fadeOutSeconds: VRM_IDLE_ACTION_FADE_OUT_SECONDS,
        forceRestart: true
      });
      vrmRuntime.idleHasPlayedOnce = true;
    }
  }, delayMs);
}

function updateVrmIdlePlayback() {
  if (!vrmRuntime?.mixer || vrmRuntime.version !== "1.0" || !vrmRuntime.actions?.idle) {
    return;
  }

  if (hasActiveNonIdleVrmAction()) {
    if (vrmRuntime.actions.idle.isRunning?.()) {
      stopVrmAction(vrmRuntime.actions.idle, VRM_IDLE_ACTION_FADE_OUT_SECONDS);
    }
    return;
  }

  const activeAction = vrmRuntime.actions[vrmRuntime.activeActionKey];
  if (vrmRuntime.activeActionKey && vrmRuntime.activeActionKey !== "idle" && !activeAction?.isRunning?.()) {
    vrmRuntime.activeActionKey = "";
  }
  if (!vrmRuntime.actions.idle.isRunning?.()) {
    if (vrmRuntime.activeActionKey === "idle") {
      vrmRuntime.activeActionKey = "";
    }
    scheduleNextVrmIdlePlayback();
  }
}

function shouldApplyManualVrmIdleFallback() {
  if (!vrmRuntime) {
    return false;
  }
  if (vrmRuntime.version === "0.0") {
    return true;
  }
  return !hasRunningVrmAction();
}

function syncVrmAnimationState(state = currentState) {
  if (!vrmRuntime?.mixer || vrmRuntime.version !== "1.0") {
    return;
  }

  const normalizedExpression = String(state?.expression || "neutral").toLowerCase();
  const requestedActionKey = VRM_EXPRESSION_ACTION_MAP[normalizedExpression] || "idle";
  if (requestedActionKey === "idle") {
    if (vrmRuntime.emotionTimerId) {
      clearTimeout(vrmRuntime.emotionTimerId);
      vrmRuntime.emotionTimerId = 0;
    }
    if (vrmRuntime.activeActionKey && vrmRuntime.activeActionKey !== "idle") {
      stopActiveVrmAction();
    }
    vrmRuntime.requestedActionKey = "idle";
    scheduleNextVrmIdlePlayback();
    return;
  }

  const actionKey = vrmRuntime.actions?.[requestedActionKey] ? requestedActionKey : "";
  if (!actionKey) {
    vrmRuntime.requestedActionKey = "";
    scheduleNextVrmIdlePlayback();
    return;
  }

  const currentAction = vrmRuntime.actions?.[actionKey];
  if (
    vrmRuntime.requestedActionKey === actionKey &&
    vrmRuntime.activeActionKey === actionKey &&
    currentAction?.isRunning?.()
  ) {
    return;
  }

  if (vrmRuntime.emotionTimerId) {
    clearTimeout(vrmRuntime.emotionTimerId);
    vrmRuntime.emotionTimerId = 0;
  }

  playVrmAction(actionKey, {
    loop: actionKey === "think" ? THREE.LoopRepeat : THREE.LoopOnce,
    repetitions: actionKey === "think" ? Infinity : 1,
    fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
    fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
    forceRestart: false
  });

  if (actionKey !== "think") {
    vrmRuntime.emotionTimerId = window.setTimeout(() => {
      if (vrmRuntime?.activeActionKey === actionKey) {
        stopActiveVrmAction(0.8);
        scheduleNextVrmIdlePlayback();
      }
    }, VRM_ONE_SHOT_ACTION_DURATION_MS);
  }
}

function applyNaturalArmPoseForVrm0() {
  if (!vrmRuntime) {
    return;
  }
  const {
    leftShoulder,
    rightShoulder,
    leftUpperArm,
    rightUpperArm,
    leftLowerArm,
    rightLowerArm,
    leftHand,
    rightHand
  } = vrmRuntime;

  try {
    if (leftShoulder) {
      leftShoulder.quaternion.set(0, 0, 0, 1);
    }
    if (rightShoulder) {
      rightShoulder.quaternion.set(0, 0, 0, 1);
    }
    if (leftUpperArm) {
      leftUpperArm.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI * 0.05);
    }
    if (rightUpperArm) {
      rightUpperArm.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.PI * 0.05);
    }
    if (leftLowerArm) {
      leftLowerArm.quaternion.setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.PI * 0.02);
    }
    if (rightLowerArm) {
      rightLowerArm.quaternion.setFromAxisAngle(new THREE.Vector3(0, 0, 1), -Math.PI * 0.02);
    }
    if (leftHand) {
      leftHand.quaternion.set(0, 0, 0, 1);
    }
    if (rightHand) {
      rightHand.quaternion.set(0, 0, 0, 1);
    }
  } catch (_) {
    // ignore rig-specific failures
  }
}

function updateLookTarget(elapsed) {
  if (!lookTarget) {
    return;
  }
  const forward = new THREE.Vector3(0, 0, -1);
  const right = new THREE.Vector3(1, 0, 0);
  const up = new THREE.Vector3(0, 1, 0);
  forward.applyQuaternion(camera.quaternion).normalize();
  right.applyQuaternion(camera.quaternion).normalize();
  up.applyQuaternion(camera.quaternion).normalize();

  const dx = Math.sin(elapsed * 0.6) * 0.25 + Math.sin(elapsed * 1.1 + 1.7) * 0.08;
  const dy = Math.sin(elapsed * 0.8 + 0.5) * 0.18 + Math.sin(elapsed * 1.3 + 2.2) * 0.06;
  const base = new THREE.Vector3().copy(camera.position).add(forward.multiplyScalar(2));
  const targetPosition = new THREE.Vector3().copy(base).add(right.multiplyScalar(dx)).add(up.multiplyScalar(dy));
  lookTarget.position.lerp(targetPosition, 0.05);
}

function applyVrmIdlePose(elapsed) {
  if (!vrmModel || !vrmRuntime) {
    return;
  }

  if (vrmRuntime.version === "0.0") {
    applyNaturalArmPoseForVrm0();
    return;
  }

  if (vrmRuntime.activeActionKey && hasRunningVrmAction()) {
    return;
  }

  const {
    leftUpperArm,
    rightUpperArm,
    leftLowerArm,
    rightLowerArm,
    leftHand,
    rightHand,
    spineBone,
    neckBone,
    headBone,
    baseLeftArmZ,
    baseRightArmZ,
    baseLeftArmY,
    baseRightArmY,
    baseLeftUpperArmX,
    baseRightUpperArmX,
    baseLeftLowerArmZ,
    baseRightLowerArmZ,
    baseLeftHandY,
    baseRightHandY,
    baseSpineY,
    baseNeckX,
    baseNeckY,
    baseHeadX,
    baseHeadY
  } = vrmRuntime;

  const sway = Math.sin(elapsed * 1.1) * 0.035;
  const breathe = Math.sin(elapsed * 2) * 0.01;
  const inwardSway = Math.sin(elapsed * 0.7) * 0.03;
  const elbowSway = Math.sin(elapsed * 1.7) * 0.06;
  const armLowering = 1.25;
  const armInward = 0.18;
  const elbowBend = 0.25;

  if (leftUpperArm) {
    leftUpperArm.rotation.z = baseLeftArmZ - armLowering + sway;
    leftUpperArm.rotation.y = baseLeftArmY + armInward + inwardSway;
    leftUpperArm.rotation.x = baseLeftUpperArmX;
  }
  if (rightUpperArm) {
    rightUpperArm.rotation.z = baseRightArmZ + armLowering - sway;
    rightUpperArm.rotation.y = baseRightArmY - armInward - inwardSway;
    rightUpperArm.rotation.x = baseRightUpperArmX;
  }
  if (leftLowerArm) {
    leftLowerArm.rotation.z = baseLeftLowerArmZ + elbowBend + elbowSway;
  }
  if (rightLowerArm) {
    rightLowerArm.rotation.z = baseRightLowerArmZ + elbowBend - elbowSway;
  }
  if (leftHand) {
    leftHand.rotation.y = baseLeftHandY;
  }
  if (rightHand) {
    rightHand.rotation.y = baseRightHandY;
  }
  if (spineBone) {
    spineBone.position.y = baseSpineY + breathe;
  }

  if (lookTarget && (neckBone || headBone)) {
    const camInv = new THREE.Matrix4().copy(camera.matrixWorld).invert();
    const targetInCameraSpace = new THREE.Vector3().copy(lookTarget.position).applyMatrix4(camInv);
    const yaw = Math.atan2(targetInCameraSpace.x, targetInCameraSpace.z);
    const pitch = Math.atan2(-targetInCameraSpace.y, targetInCameraSpace.z);
    const clampedYaw = Math.max(-0.35, Math.min(0.35, yaw));
    const clampedPitch = Math.max(-0.25, Math.min(0.25, pitch));
    const smoothing = 0.12;

    if (neckBone) {
      neckBone.rotation.y += (baseNeckY + clampedYaw * 0.4 - neckBone.rotation.y) * smoothing;
      neckBone.rotation.x += (baseNeckX + clampedPitch * 0.4 - neckBone.rotation.x) * smoothing;
    }
    if (headBone) {
      headBone.rotation.y += (baseHeadY + clampedYaw * 0.6 - headBone.rotation.y) * smoothing;
      headBone.rotation.x += (baseHeadX + clampedPitch * 0.6 - headBone.rotation.x) * smoothing;
    }
  }
}

function getCurrentVrmTransform(state = currentState) {
  const modelPath = state?.modelPath || currentModelPath || "";
  const transform = state?.vrmTransforms?.[modelPath] || {};
  return {
    scale: Number.isFinite(Number(transform.scale)) ? Number(transform.scale) : Math.max(0.25, Math.min(2.5, Number(state?.scale) || 1)),
    positionX: Number.isFinite(Number(transform.positionX)) ? Number(transform.positionX) : 0,
    positionY: Number.isFinite(Number(transform.positionY)) ? Number(transform.positionY) : 0,
    rotation: Number.isFinite(Number(transform.rotation)) ? Number(transform.rotation) : 0
  };
}

function applyVrmTransform(state = currentState) {
  if (!vrmModel?.scene) {
    return;
  }
  const transform = getCurrentVrmTransform(state);
  vrmModel.scene.scale.setScalar(transform.scale);
  vrmModel.scene.position.set(transform.positionX, transform.positionY, 0);
  vrmModel.scene.rotation.y = (transform.rotation * Math.PI) / 180;
}

function resetVrmExpressions() {
  if (!vrmModel) {
    return;
  }
  try {
    if (vrmModel.expressionManager) {
      [
        "happy",
        "relaxed",
        "angry",
        "sad",
        "surprised",
        "blink",
        "blinkLeft",
        "blinkRight",
        "aa",
        "oh"
      ].forEach((key) => {
        try {
          vrmModel.expressionManager.setValue(key, 0);
        } catch (_) {
          // ignore unsupported expression keys
        }
      });
    }
    if (vrmModel.blendShapeProxy) {
      ["Joy", "Relaxed", "Angry", "Sad", "Surprised", "Blink", "A", "O"].forEach((key) => {
        try {
          vrmModel.blendShapeProxy.setValue(key, 0);
        } catch (_) {
          // ignore unsupported blend shapes
        }
      });
    }
  } catch (_) {
    // non-fatal
  }
}

function applyVrmExpression(expression) {
  if (!vrmModel) {
    return;
  }

  resetVrmExpressions();
  const normalized = String(expression || "neutral").toLowerCase();

  if (vrmModel.expressionManager) {
    const map = {
      happy: ["happy"],
      love: ["happy", "relaxed"],
      think: ["oh"],
      sad: ["sad"],
      angry: ["angry"],
      surprised: ["surprised"]
    };
    for (const key of map[normalized] || []) {
      try {
        vrmModel.expressionManager.setValue(key, key === "relaxed" ? 0.65 : 0.8);
      } catch (_) {
        // ignore unsupported expression keys
      }
    }
  }

  if (vrmModel.blendShapeProxy) {
    const map = {
      happy: ["Joy"],
      love: ["Joy", "Relaxed"],
      think: ["O"],
      sad: ["Sad"],
      angry: ["Angry"],
      surprised: ["Surprised"]
    };
    for (const key of map[normalized] || []) {
      try {
        vrmModel.blendShapeProxy.setValue(key, key === "Relaxed" ? 0.65 : 0.8);
      } catch (_) {
        // ignore unsupported blend shapes
      }
    }
  }
}

function setVrmMouth(value) {
  const clamped = Math.max(0, Math.min(1, value));
  if (!vrmModel) {
    return;
  }
  try {
    if (vrmModel.expressionManager) {
      try {
        vrmModel.expressionManager.setValue("aa", clamped);
      } catch (_) {
        // ignore unsupported expression keys
      }
    }
    if (vrmModel.blendShapeProxy) {
      try {
        vrmModel.blendShapeProxy.setValue("A", clamped);
        vrmModel.blendShapeProxy.update?.();
      } catch (_) {
        // ignore unsupported blend shapes
      }
    }
  } catch (_) {
    // non-fatal
  }
}

async function loadVrmModel(modelPath) {
  if (webglContextLost) {
    return;
  }
  if (!modelPath) {
    setStatus("No VRM model selected");
    return;
  }
  if (modelPath === currentModelPath && vrmModel) {
    applyStateToScene(currentState);
    return;
  }

  setStatus("Loading VRM model...");
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  const modelUrl = await window.catbotDesktop.resolveAssetUrl(modelPath);
  const gltf = await new Promise((resolve, reject) => {
    loader.load(modelUrl, resolve, undefined, reject);
  });

  const vrm = extractVrm(gltf);
  if (!vrm) {
    throw new Error(`VRM data not found for ${modelPath}`);
  }

  removeCurrentLive2dModel();
  removeCurrentVrmModel();
  try {
    VRMUtils.combineSkeletons(vrm.scene);
  } catch (_) {
    // best-effort optimization only
  }
  try {
    if (isVrm0(vrm) && typeof VRMUtils.rotateVRM0 === "function") {
      VRMUtils.rotateVRM0(vrm);
    }
  } catch (_) {
    // ignore rotation helper failures
  }

  normalizeMaterialColorSpace(vrm);
  downscaleVrmTexturesForDesktop(vrm);
  applyDesktopMaterialFallback(vrm);
  hideRenderFallback();
  scene.add(vrm.scene);
  vrmModel = vrm;
  setupVrmRuntime(vrm);
  ensureLookTarget(vrm);
  await preloadVrmActions(vrm);
  resetVrmPhysicsState(vrm);
  smoothedVrmDelta = 1 / 60;
  currentModelPath = modelPath;
  applyStateToScene(currentState);
  applyVrmExpression(currentState.expression);
  if (!vrmRuntime?.mixer) {
    applyVrmIdlePose(0);
  }
  setReadyStatus();
}

async function ensureLive2dRuntime() {
  if (!live2dTickerRegistered) {
    await PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);
    live2dTickerRegistered = true;
  }

  if (!live2dApp) {
    live2dApp = new PIXI.Application({
      view: live2dCanvas,
      autoStart: true,
      resizeTo: live2dContainer,
      transparent: true,
      backgroundAlpha: 0,
      antialias: true
    });
  }
}

function applyLive2dLayout() {
  if (!live2dModel || !live2dContainer || !live2dApp) {
    return;
  }

  const width = Math.max(live2dContainer.clientWidth || window.innerWidth || 1, 1);
  const height = Math.max(live2dContainer.clientHeight || window.innerHeight || 1, 1);
  live2dApp.renderer.resize(width, height);

  const bounds = live2dModel.getLocalBounds?.() || {
    width: live2dModel.width || 1,
    height: live2dModel.height || 1
  };
  const intrinsicWidth = Math.abs(bounds.width) || 1;
  const intrinsicHeight = Math.abs(bounds.height) || 1;
  const modelScale = Math.max(0.25, Math.min(2.5, Number(currentState.scale) || 1));
  const baseScale = Math.min(width / (intrinsicWidth * 1.5), height / (intrinsicHeight * 1.5)) * 2.2;

  live2dModel.scale.set(baseScale * modelScale);
  live2dModel.anchor.set(0.5, 0.4);
  live2dModel.x = width / 2;
  live2dModel.y = height / 1.35;
}

function applyLive2dExpression(expression) {
  if (!live2dModel?.internalModel?.coreModel) {
    return;
  }
  const core = live2dModel.internalModel.coreModel;
  const normalized = String(expression || "neutral").toLowerCase();
  const angleX =
    normalized === "happy" ? 6 :
    normalized === "love" ? 10 :
    normalized === "think" ? -5 :
    normalized === "angry" ? -9 :
    normalized === "surprised" ? 4 :
    normalized === "sad" ? -3 : 0;
  const angleY =
    normalized === "think" ? -8 :
    normalized === "sad" ? -5 :
    normalized === "surprised" ? 6 : 0;

  try {
    core.setParameterValueById("ParamAngleX", angleX);
  } catch (_) {
    // ignore unsupported parameters
  }
  try {
    core.setParameterValueById("ParamAngleY", angleY);
  } catch (_) {
    // ignore unsupported parameters
  }
  try {
    core.setParameterValueById("ParamAngleZ", normalized === "love" ? 4 : 0);
  } catch (_) {
    // ignore unsupported parameters
  }
}

function setLive2dMouth(value) {
  const clamped = Math.max(0, Math.min(1, value));
  try {
    live2dModel?.internalModel?.coreModel?.setParameterValueById("ParamMouthOpenY", clamped);
  } catch (_) {
    // non-fatal
  }
}

async function loadLive2dModel(modelPath) {
  if (webglContextLost) {
    return;
  }
  if (!modelPath) {
    setStatus("No Live2D model selected");
    return;
  }
  if (modelPath === currentModelPath && live2dModel) {
    applyStateToScene(currentState);
    return;
  }

  setStatus("Loading Live2D model...");
  await ensureLive2dRuntime();
  const modelUrl = await window.catbotDesktop.resolveAssetUrl(modelPath);
  const model = await PIXI.live2d.Live2DModel.from(modelUrl, {
    autoInteract: false,
    focus: false
  });

  removeCurrentVrmModel();
  removeCurrentLive2dModel();
  live2dApp.stage.removeChildren();
  live2dApp.stage.addChild(model);
  live2dModel = model;
  currentModelPath = modelPath;
  applyStateToScene(currentState);
  applyLive2dExpression(currentState.expression);
  hideRenderFallback();
  setReadyStatus();
}

function applyStateToScene(state) {
  document.body.classList.toggle("move-mode", Boolean(state.moveMode));
  syncQuickHudControls(state);
  const modelScale = Math.max(0.25, Math.min(2.5, Number(state.scale) || 1));

  if (state.mode === "live2d") {
    vrmCanvas.style.display = "none";
    live2dContainer.style.display = "block";
    if (live2dModel) {
      applyLive2dLayout();
      applyLive2dExpression(state.expression);
    }
    return;
  }

  vrmCanvas.style.display = "block";
  live2dContainer.style.display = "none";
  if (vrmModel) {
    applyVrmTransform(state);
    applyVrmExpression(state.expression);
    syncVrmAnimationState(state);
  }
}

async function ensureAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }
  return audioContext;
}

function applyMouthValue(value) {
  currentMouthValue = Math.max(0, Math.min(1, value));
  if (currentState.mode === "live2d") {
    setLive2dMouth(currentMouthValue);
  } else {
    setVrmMouth(currentMouthValue);
  }
}

function disconnectSpeechGraph() {
  if (speechPreviewRafId) {
    cancelAnimationFrame(speechPreviewRafId);
    speechPreviewRafId = 0;
  }
  try {
    speechPreviewSourceNode?.disconnect();
  } catch (_) {
    // ignore disconnect errors
  }
  try {
    speechPreviewAnalyserNode?.disconnect();
  } catch (_) {
    // ignore disconnect errors
  }
  try {
    speechPreviewGainNode?.disconnect();
  } catch (_) {
    // ignore disconnect errors
  }
  speechPreviewSourceNode = null;
  speechPreviewAnalyserNode = null;
  speechPreviewGainNode = null;
  analyserSpeechActive = false;
}

function stopSpeechPreview(options = {}) {
  const { preserveBubble = false } = options;
  speechActiveUntil = 0;
  clearSpeechBubbleSequence();
  disconnectSpeechGraph();

  if (speechPreviewAudio) {
    try {
      speechPreviewAudio.pause();
    } catch (_) {
      // ignore pause errors
    }
  }
  speechPreviewAudio = null;

  if (speechPreviewObjectUrl) {
    try {
      URL.revokeObjectURL(speechPreviewObjectUrl);
    } catch (_) {
      // ignore revoke errors
    }
  }
  speechPreviewObjectUrl = "";
  applyMouthValue(0);

  if (!preserveBubble) {
    hideSpeechBubble({ immediate: true });
  }
}

function startLipSyncFromAudioElement(audioEl, previewToken) {
  const ctx = audioContext;
  if (!ctx) {
    throw new Error("Audio context is not available.");
  }

  const source = ctx.createMediaElementSource(audioEl);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.55;
  const gain = ctx.createGain();
  gain.gain.value = 1.0;

  source.connect(analyser);
  analyser.connect(gain);
  gain.connect(ctx.destination);

  speechPreviewSourceNode = source;
  speechPreviewAnalyserNode = analyser;
  speechPreviewGainNode = gain;
  analyserSpeechActive = true;

  const buffer = new Uint8Array(analyser.fftSize);
  let smoothed = 0;
  const attack = 0.6;
  const release = 0.15;

  const finish = () => {
    if (previewToken !== speechGeneration) {
      return;
    }
    disconnectSpeechGraph();
    applyMouthValue(0);
    hideSpeechBubble();
    setReadyStatus();
  };

  const step = () => {
    if (previewToken !== speechGeneration || !speechPreviewAnalyserNode) {
      disconnectSpeechGraph();
      return;
    }

    speechPreviewAnalyserNode.getByteTimeDomainData(buffer);
    let sum = 0;
    for (let index = 0; index < buffer.length; index += 1) {
      const normalizedSample = (buffer[index] - 128) / 128;
      sum += normalizedSample * normalizedSample;
    }

    const rms = Math.sqrt(sum / buffer.length);
    if (rms > smoothed) {
      smoothed = smoothed + (rms - smoothed) * attack;
    } else {
      smoothed = smoothed + (rms - smoothed) * release;
    }

    const threshold = 0.03;
    const mouthValue = smoothed <= threshold ? 0 : Math.min(1, (smoothed - threshold) * 6);
    applyMouthValue(mouthValue);

    if (!audioEl.ended && (speechPreviewAudio === audioEl || !audioEl.paused)) {
      speechPreviewRafId = requestAnimationFrame(step);
      return;
    }

    finish();
  };

  audioEl.addEventListener("ended", finish, { once: true });
  audioEl.addEventListener("pause", () => {
    if (!audioEl.ended && speechPreviewAudio === audioEl) {
      finish();
    }
  }, { once: true });

  speechPreviewRafId = requestAnimationFrame(step);
}

async function playSpeechPreview(state) {
  const text = String(state.speechBubbleText || "").trim();
  if (!text) {
    speechGeneration += 1;
    stopSpeechPreview();
    return;
  }

  const durationMs = Math.max(600, Number(state.speechDurationMs) || 2600);
  const previewToken = ++speechGeneration;
  stopSpeechPreview();
  setStatus("Synthesizing speech...");

  try {
    const speechResult = await window.catbotDesktop.synthesizePreviewSpeech({
      text,
      proxyBaseUrl: state.proxyBaseUrl,
      webClientUrl: state.webClientUrl,
      ttsEndpoint: state.ttsEndpoint,
      ttsModel: state.ttsModel,
      ttsVoice: state.ttsVoice
    });

    if (previewToken !== speechGeneration) {
      return;
    }

    const audioBytes = speechResult?.audioBuffer;
    const normalizedAudioBytes =
      audioBytes instanceof ArrayBuffer
        ? audioBytes
        : ArrayBuffer.isView(audioBytes)
          ? audioBytes.buffer.slice(audioBytes.byteOffset, audioBytes.byteOffset + audioBytes.byteLength)
          : null;
    if (!normalizedAudioBytes || normalizedAudioBytes.byteLength === 0) {
      throw new Error("Speech preview returned no audio data.");
    }

    const blob = new Blob([normalizedAudioBytes], {
      type: speechResult?.contentType || "audio/mpeg"
    });
    const objectUrl = URL.createObjectURL(blob);
    const audio = new Audio(objectUrl);
    audio.preload = "auto";

    speechPreviewAudio = audio;
    speechPreviewObjectUrl = objectUrl;

    await ensureAudioContext();
    const audioDurationMs = await resolveAudioDurationMs(audio, durationMs);
    if (previewToken !== speechGeneration) {
      return;
    }
    await audio.play();
    if (previewToken !== speechGeneration) {
      return;
    }
    startLipSyncFromAudioElement(audio, previewToken);
    scheduleSpeechBubbleSentences(text, audioDurationMs, previewToken);
    setStatus("Previewing speech...");
  } catch (error) {
    if (previewToken !== speechGeneration) {
      return;
    }
    console.warn("Speech preview failed, using fallback mouth animation:", error);
    stopSpeechPreview({ preserveBubble: true });
    scheduleSpeechBubbleSentences(text, durationMs, previewToken);
    speechActiveUntil = Date.now() + durationMs;
    setStatus("Speech bubble preview");
  }
}

function animate() {
  if (!renderLoopActive || webglContextLost || !renderer || !scene || !camera) {
    return;
  }
  requestAnimationFrame(animate);
  const elapsed = clock.getElapsedTime();
  const rawDelta = clock.getDelta();

  if (currentState.mode === "vrm" && vrmModel) {
    const { animationDelta, physicsDelta } = getStableVrmFrameDeltas(rawDelta);
    updateLookTarget(elapsed);
    applyVrmTransform(currentState);
    if (vrmRuntime?.mixer) {
      vrmRuntime.mixer.update(animationDelta);
      updateVrmIdlePlayback();
    }
    if (shouldApplyManualVrmIdleFallback()) {
      applyVrmIdlePose(elapsed);
    }
    if (typeof vrmModel.update === "function") {
      vrmModel.update(physicsDelta);
    }
  } else if (currentState.mode === "live2d" && live2dModel && live2dContainer) {
    const driftX = Math.sin(elapsed * 0.7) * 10;
    const driftY = Math.sin(elapsed * 1.05) * 6;
    const width = Math.max(live2dContainer.clientWidth || window.innerWidth || 1, 1);
    const height = Math.max(live2dContainer.clientHeight || window.innerHeight || 1, 1);
    live2dModel.x = width / 2 + driftX;
    live2dModel.y = height / 1.35 + driftY;
  }

  if (!analyserSpeechActive) {
    if (Date.now() < speechActiveUntil) {
      const pulse = (Math.sin(elapsed * 18) + 1) / 2;
      applyMouthValue(0.15 + pulse * 0.75);
    } else if (currentMouthValue > 0) {
      applyMouthValue(currentMouthValue * 0.82);
      if (currentMouthValue < 0.01) {
        applyMouthValue(0);
      }
    }
  }

  try {
    renderer.render(scene, camera);
  } catch (error) {
    webglContextLost = true;
    renderLoopActive = false;
    showRenderFallback("Avatar renderer failed. Showing fallback image.", error);
  }
}

vrmCanvas?.addEventListener("webglcontextlost", (event) => {
  event.preventDefault();
  webglContextLost = true;
  renderLoopActive = false;
  showRenderFallback("WebGL context was lost. Showing fallback image.");
});

vrmCanvas?.addEventListener("webglcontextrestored", async () => {
  webglContextLost = false;
  hideRenderFallback();
  try {
    initializeScene();
    await loadVrmModel(currentState.modelPath);
  } catch (error) {
    showRenderFallback(`Failed to restore avatar renderer: ${formatLoadError(error)}`, error);
  }
});

window.addEventListener("resize", resizeRenderer);
window.addEventListener("blur", () => requestAnimationFrame(refreshTransparentSurface));
window.addEventListener("focus", () => requestAnimationFrame(refreshTransparentSurface));
document.addEventListener("visibilitychange", () => requestAnimationFrame(refreshTransparentSurface));
setupMoveModeDragging();
setupQuickHud();

try {
  availableModels = await window.catbotDesktop.listModels();
  currentAuthStatus = await window.catbotDesktop.verifyAuth({ proxyBaseUrl: currentState.proxyBaseUrl });
  renderAuthStatus(currentAuthStatus);
  renderHudState(currentState);
} catch (error) {
  console.warn("Could not initialize integrated avatar HUD:", error);
}

window.catbotDesktop.onStateChanged(async (state) => {
  currentState = state;
  applyStateToScene(state);

  try {
    if (state.mode === "live2d") {
      await loadLive2dModel(state.modelPath);
    } else {
      await loadVrmModel(state.modelPath);
    }
  } catch (error) {
    showRenderFallback(`Failed to load model: ${formatLoadError(error)}`, error);
    return;
  }

  if (state.speechTriggerId && state.speechTriggerId !== activeSpeechTriggerId) {
    activeSpeechTriggerId = state.speechTriggerId;
    await playSpeechPreview(state);
  } else if (!state.moveMode && !analyserSpeechActive && Date.now() >= speechActiveUntil) {
    setReadyStatus();
  }
});

try {
  initializeScene();
  if (currentState.mode === "live2d") {
    await loadLive2dModel(currentState.modelPath);
  } else {
    await loadVrmModel(currentState.modelPath);
  }
} catch (error) {
  showRenderFallback(`Failed to load model: ${formatLoadError(error)}`, error);
}
