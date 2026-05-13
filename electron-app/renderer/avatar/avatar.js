import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { createVRMAnimationClip, VRMAnimationLoaderPlugin } from "@pixiv/three-vrm-animation";

window.PIXI = window.PIXI || PIXI;
window.EventEmitter3.EventEmitter = EventEmitter3;

const vrmCanvas = document.getElementById("avatar-canvas");
const live2dContainer = document.getElementById("live2d-container");
const live2dCanvas = document.getElementById("live2d-canvas");
const webcamPreview = document.getElementById("webcam-preview");
const statusChip = document.getElementById("status-chip");
const renderFallback = document.getElementById("render-fallback");
const renderFallbackImage = document.getElementById("render-fallback-image");
const renderFallbackStatus = document.getElementById("render-fallback-status");
const speechBubble = document.getElementById("speech-bubble");
const voiceCaptureStatus = document.getElementById("voice-capture-status");
const voiceCaptureStatusText = document.getElementById("voice-capture-status-text");
const authGate = document.getElementById("auth-gate");
const authGateProxyUrl = document.getElementById("auth-gate-proxy-url");
const authGateUsername = document.getElementById("auth-gate-username");
const authGatePassword = document.getElementById("auth-gate-password");
const authGateLoginBtn = document.getElementById("auth-gate-login-btn");
const authGateSignupBtn = document.getElementById("auth-gate-signup-btn");
const authGateStatus = document.getElementById("auth-gate-status");
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
const hudSoulPrompt = document.getElementById("hud-soul-prompt");
const hudCompanionCurrentName = document.getElementById("hud-companion-current-name");
const hudCompanionCurrentState = document.getElementById("hud-companion-current-state");
const hudCompanionCurrentSummary = document.getElementById("hud-companion-current-summary");
const hudCompanionCurrentTags = document.getElementById("hud-companion-current-tags");
const hudCompanionName = document.getElementById("hud-companion-name");
const hudCompanionDefaultCheckbox = document.getElementById("hud-companion-default-checkbox");
const hudSaveCompanionBtn = document.getElementById("hud-save-companion-btn");
const hudRefreshCompanionsBtn = document.getElementById("hud-refresh-companions-btn");
const hudClearDefaultCompanionBtn = document.getElementById("hud-clear-default-companion-btn");
const hudCompanionList = document.getElementById("hud-companion-list");
const hudCompanionFeedback = document.getElementById("hud-companion-feedback");
const hudProxyUrl = document.getElementById("hud-proxy-url");
const hudWebUrl = document.getElementById("hud-web-url");
const hudChatEndpoint = document.getElementById("hud-chat-endpoint");
const hudChatModel = document.getElementById("hud-chat-model");
const hudChatApiKey = document.getElementById("hud-chat-api-key");
const hudTtsEndpoint = document.getElementById("hud-tts-endpoint");
const hudTtsModel = document.getElementById("hud-tts-model");
const hudTtsVoice = document.getElementById("hud-tts-voice");
const hudWindowWidth = document.getElementById("hud-window-width");
const hudWindowHeight = document.getElementById("hud-window-height");
const hudApplyWindowSizeBtn = document.getElementById("hud-apply-window-size-btn");
const hudResetWindowSizeBtn = document.getElementById("hud-reset-window-size-btn");
const hudSaveSettingsBtn = document.getElementById("hud-save-settings-btn");
const hudToggleSpeakBtn = document.getElementById("hud-toggle-speak-btn");
const hudToggleWebcamBtn = document.getElementById("hud-toggle-webcam-btn");
const hudToggleAutoCompanionBtn = document.getElementById("hud-toggle-auto-companion-btn");
const hudToggleAutoScreenBtn = document.getElementById("hud-toggle-auto-screen-btn");
const hudToggleAutoDanceBtn = document.getElementById("hud-toggle-auto-dance-btn");
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
let availableVrmAnimations = { dance: [], danceDirectory: "model_avatar/AutoDance" };
let companionListCache = [];
let companionsLoading = false;
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
let activeSpeechExpressionTriggerId = 0;
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
let speechPreviewInProgress = false;
let speechPreviewPcmStreamActive = false;
let speechPreviewPcmActiveSources = 0;
let speechPreviewPcmNextPlayTime = 0;
let speechPreviewPcmCleanupFns = [];
let speechPreviewStreamCancel = null;
let speechGeneration = 0;
let speechExpressionResetTimeout = 0;
let lookTarget = null;
let quickHudWasVisible = Boolean(currentState.quickHudVisible);
let pendingScreenSnapshot = null;
let screenContextModeEnabled = Boolean(currentState.screenContextMode);
let webcamStream = null;
let webcamStartPromise = null;
let micRecorder = null;
let micStream = null;
let micChunks = [];
let micStopTimer = 0;
let micAutoSendOnStop = false;
let micAudioContext = null;
let micAnalyserNode = null;
let micSourceNode = null;
let micAnalysisRafId = 0;
let micRecordingStartedAt = 0;
let micSpeechStarted = false;
let micLastVoiceAt = 0;
let voiceCaptureClearTimer = 0;
let autoCompanionTimer = 0;
let autoCompanionRunning = false;
let autoCompanionEmoteTimer = 0;
let autoCompanionLastActivityAt = Date.now();
let renderLoopActive = false;
let webglContextLost = false;
let fallbackImageLoading = null;
let smoothedVrmDelta = 1 / 60;

const VRM_ACTION_FADE_IN_SECONDS = 0.55;
const VRM_ACTION_FADE_OUT_SECONDS = 0.85;
const VRM_IDLE_ACTION_FADE_IN_SECONDS = 0.95;
const VRM_IDLE_ACTION_FADE_OUT_SECONDS = 0.8;
const VRM_MANUAL_IDLE_BODY_BLEND = 0.045;
const VRM_MANUAL_IDLE_LEG_BLEND = 0.052;
const VRM_MANUAL_IDLE_ARM_RELAX_BLEND = 0.07;
const VRM_MANUAL_IDLE_FINGER_CURL_BLEND = 0.22;
const VRM_MANUAL_IDLE_LEG_STANCE_BLEND = 0.045;
const VRM_MANUAL_IDLE_MOTION_BLEND = 0.038;
const VRM_MANUAL_IDLE_BLEND = 0.055;
const VRM_MANUAL_IDLE_HEAD_BLEND = 0.09;
const VRM_POSE_TO_ACTION_BLEND_MS = 420;
const VRM_IDLE_POSE_TO_ACTION_BLEND_MS = 560;
const VRM_IDLE_REFERENCE_POSE_SAMPLE_SECONDS = 0.001;
const VRM_IDLE_REFERENCE_POSE_BLEND = 0.16;
const VRM_MAX_ANIMATION_DELTA_SECONDS = 1 / 24;
const VRM_MAX_PHYSICS_DELTA_SECONDS = 1 / 45;
const VRM_DELTA_SMOOTHING = 0.18;
const VRM_PHYSICS_RESET_DELTA_SECONDS = 0.22;
const DESKTOP_MAX_TEXTURE_SIZE = 1024;
const ENABLE_DESKTOP_VRMA_PRELOAD = true;
const DESKTOP_MATERIAL_TEXTURE_KEYS = ["map", "emissiveMap", "normalMap", "roughnessMap", "metalnessMap", "alphaMap"];
const SPEECH_BUBBLE_FADE_MS = 220;
const SPEECH_SENTENCE_GAP_MS = 90;
const SPEECH_PREVIEW_PCM_INITIAL_BUFFER_SECONDS = 4.00;
const SPEECH_PREVIEW_PCM_SCHEDULE_LEAD_SECONDS = 0.45;
const SPEECH_PREVIEW_PCM_UNDERRUN_WARN_SECONDS = 0.05;
const TTS_UTTERANCE_CHUNK_MAX_CHARS = 150;
const TTS_STREAMING_UTTERANCE_CHUNK_MAX_CHARS = 360;
const TTS_UTTERANCE_FIRST_CHUNK_WORDS = 10;
const TTS_UTTERANCE_CHUNK_WORDS = 18;
const TTS_UTTERANCE_MIN_CHUNK_WORDS = 5;
const VOICE_CAPTURE_MAX_MS = 10000;
const VOICE_CAPTURE_MIN_MS = 650;
const VOICE_CAPTURE_START_GRACE_MS = 2600;
const VOICE_CAPTURE_SILENCE_MS = 850;
const VOICE_CAPTURE_RMS_THRESHOLD = 0.028;
const AUTO_COMPANION_MIN_DELAY_MS = 90000;
const AUTO_COMPANION_MAX_DELAY_MS = 240000;
const AUTO_COMPANION_USER_IDLE_GRACE_MS = 45000;
const AUTO_COMPANION_SPEECH_COOLDOWN_MS = 12000;
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
const VRM_FINGER_BONE_NAMES = [
  "leftThumbMetacarpal",
  "leftThumbProximal",
  "leftThumbDistal",
  "leftIndexProximal",
  "leftIndexIntermediate",
  "leftIndexDistal",
  "leftMiddleProximal",
  "leftMiddleIntermediate",
  "leftMiddleDistal",
  "leftRingProximal",
  "leftRingIntermediate",
  "leftRingDistal",
  "leftLittleProximal",
  "leftLittleIntermediate",
  "leftLittleDistal",
  "rightThumbMetacarpal",
  "rightThumbProximal",
  "rightThumbDistal",
  "rightIndexProximal",
  "rightIndexIntermediate",
  "rightIndexDistal",
  "rightMiddleProximal",
  "rightMiddleIntermediate",
  "rightMiddleDistal",
  "rightRingProximal",
  "rightRingIntermediate",
  "rightRingDistal",
  "rightLittleProximal",
  "rightLittleIntermediate",
  "rightLittleDistal"
];
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

function pushTtsChunk(chunks, value) {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (normalized) {
    chunks.push(normalized);
  }
}

function splitTtsWords(segment) {
  return String(segment || "").replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
}

function isPocketTtsModelName(modelName) {
  const normalized = String(modelName || "").trim().toLowerCase().replace(/_/g, "-");
  return Boolean(
    normalized === "pocket-tts" ||
    normalized === "pocket-tts-realtime" ||
    normalized.startsWith("pocket-tts") ||
    normalized.includes("kyutai/pocket-tts")
  );
}

function arrayBufferFromIpcBinary(value) {
  if (value instanceof ArrayBuffer) {
    return value;
  }
  if (ArrayBuffer.isView(value)) {
    return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
  }
  if (Array.isArray(value)) {
    return new Uint8Array(value).buffer;
  }
  if (value?.type === "Buffer" && Array.isArray(value.data)) {
    return new Uint8Array(value.data).buffer;
  }
  return null;
}

function splitLongTtsSegment(segment, maxChars, chunks) {
  const words = splitTtsWords(segment);
  let current = "";
  for (const word of words) {
    if (word.length > maxChars) {
      pushTtsChunk(chunks, current);
      current = "";
      for (let offset = 0; offset < word.length; offset += maxChars) {
        pushTtsChunk(chunks, word.slice(offset, offset + maxChars));
      }
      continue;
    }
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }
    pushTtsChunk(chunks, current);
    current = word;
  }
  pushTtsChunk(chunks, current);
}

function splitTtsUtteranceChunks(text, maxChars = TTS_UTTERANCE_CHUNK_MAX_CHARS) {
  const safeMaxChars = Math.max(80, Number(maxChars) || TTS_UTTERANCE_CHUNK_MAX_CHARS);
  const words = splitTtsWords(text);
  const chunks = [];
  let current = "";
  let currentWordCount = 0;

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    const targetWords = chunks.length === 0 ? TTS_UTTERANCE_FIRST_CHUNK_WORDS : TTS_UTTERANCE_CHUNK_WORDS;
    const endsSentence = /[.!?]["')\]]*$/.test(word);
    const shouldFlushBeforeWord = Boolean(
      current &&
      candidate.length > safeMaxChars &&
      currentWordCount >= TTS_UTTERANCE_MIN_CHUNK_WORDS
    );
    if (shouldFlushBeforeWord) {
      pushTtsChunk(chunks, current);
      current = "";
      currentWordCount = 0;
    }

    if (!current && word.length > safeMaxChars) {
      for (let offset = 0; offset < word.length; offset += safeMaxChars) {
        pushTtsChunk(chunks, word.slice(offset, offset + safeMaxChars));
      }
      continue;
    }

    current = current ? `${current} ${word}` : word;
    currentWordCount += 1;

    if (
      currentWordCount >= TTS_UTTERANCE_MIN_CHUNK_WORDS &&
      (currentWordCount >= targetWords || endsSentence || current.length >= safeMaxChars)
    ) {
      pushTtsChunk(chunks, current);
      current = "";
      currentWordCount = 0;
      continue;
    }
  }
  pushTtsChunk(chunks, current);
  return chunks.length ? chunks : splitLongTtsSegment(String(text || ""), safeMaxChars, chunks) || chunks;
}

function splitStreamingTtsUtteranceChunks(text) {
  const normalized = String(text || "").trim();
  if (!normalized) {
    return [];
  }
  const maxChars = TTS_STREAMING_UTTERANCE_CHUNK_MAX_CHARS;
  const sentences = splitSpeechIntoSentences(normalized);
  if (sentences.length <= 1 && normalized.length <= maxChars) {
    return [normalized];
  }

  const chunks = [];
  for (const sentence of sentences) {
    if (sentence.length > maxChars) {
      splitLongTtsSegment(sentence, maxChars, chunks);
      continue;
    }
    pushTtsChunk(chunks, sentence);
  }
  return chunks.length ? chunks : [normalized];
}

function estimateSpeechSegmentDurationMs(segmentText, fullText, fallbackTotalDurationMs) {
  const segmentLength = Math.max(16, String(segmentText || "").length);
  const fullLength = Math.max(segmentLength, String(fullText || "").length);
  const weightedFallback = ((Number(fallbackTotalDurationMs) || 0) * segmentLength) / fullLength;
  const readingEstimate = 550 + segmentLength * 58;
  return Math.max(650, Math.min(12000, Math.round(weightedFallback || readingEstimate)));
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

function setVoiceCaptureStatus(message, phase = "") {
  if (voiceCaptureClearTimer) {
    clearTimeout(voiceCaptureClearTimer);
    voiceCaptureClearTimer = 0;
  }
  if (voiceCaptureStatusText) {
    voiceCaptureStatusText.textContent = message;
  }
  if (voiceCaptureStatus) {
    voiceCaptureStatus.dataset.phase = phase;
  }
  document.body.classList.toggle("voice-capture-active", Boolean(message));
}

function clearVoiceCaptureStatus(delayMs = 0) {
  if (voiceCaptureClearTimer) {
    clearTimeout(voiceCaptureClearTimer);
    voiceCaptureClearTimer = 0;
  }
  const clear = () => {
    voiceCaptureClearTimer = 0;
    document.body.classList.remove("voice-capture-active");
    if (voiceCaptureStatus) {
      voiceCaptureStatus.dataset.phase = "";
    }
  };
  if (delayMs > 0) {
    voiceCaptureClearTimer = window.setTimeout(clear, delayMs);
  } else {
    clear();
  }
}

function formatQuickStatus(message) {
  const text = String(message || "").replace(/\s+/g, " ").trim();
  return text.length > 120 ? `${text.slice(0, 117)}...` : text;
}

function isWebcamStreamActive() {
  return Boolean(webcamStream?.getVideoTracks?.().some((track) => track.readyState === "live"));
}

function cleanupWebcamStream() {
  try {
    webcamStream?.getTracks?.().forEach((track) => track.stop());
  } catch (_) {
    // ignore webcam cleanup failures
  }
  webcamStream = null;
  if (webcamPreview) {
    try {
      webcamPreview.pause();
    } catch (_) {
      // ignore pause failures
    }
    webcamPreview.srcObject = null;
  }
}

function waitForWebcamFrame(timeoutMs = 2500) {
  if (!webcamPreview) {
    return Promise.reject(new Error("Webcam preview element is unavailable."));
  }
  if (webcamPreview.readyState >= 2 && webcamPreview.videoWidth > 0 && webcamPreview.videoHeight > 0) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const startedAt = performance.now();
    let rafId = 0;
    const cleanup = () => {
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      }
      webcamPreview.removeEventListener("loadedmetadata", check);
      webcamPreview.removeEventListener("canplay", check);
    };
    const check = () => {
      if (webcamPreview.readyState >= 2 && webcamPreview.videoWidth > 0 && webcamPreview.videoHeight > 0) {
        cleanup();
        resolve();
        return;
      }
      if (performance.now() - startedAt >= timeoutMs) {
        cleanup();
        reject(new Error("Webcam did not provide a frame in time."));
        return;
      }
      rafId = requestAnimationFrame(check);
    };
    webcamPreview.addEventListener("loadedmetadata", check);
    webcamPreview.addEventListener("canplay", check);
    check();
  });
}

async function ensureWebcamStream() {
  if (isWebcamStreamActive()) {
    return webcamStream;
  }
  if (webcamStartPromise) {
    return webcamStartPromise;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Webcam capture is not available in this Electron runtime.");
  }
  webcamStartPromise = (async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        width: { ideal: 960 },
        height: { ideal: 540 },
        frameRate: { ideal: 15, max: 30 }
      }
    });
    cleanupWebcamStream();
    webcamStream = stream;
    if (webcamPreview) {
      webcamPreview.muted = true;
      webcamPreview.srcObject = stream;
      try {
        await webcamPreview.play();
      } catch (_) {
        // A loaded video frame is enough for still capture.
      }
      await waitForWebcamFrame();
    }
    return stream;
  })().finally(() => {
    webcamStartPromise = null;
  });
  return webcamStartPromise;
}

async function captureWebcamSnapshot() {
  await ensureWebcamStream();
  await waitForWebcamFrame();
  const sourceWidth = Math.max(1, webcamPreview?.videoWidth || 0);
  const sourceHeight = Math.max(1, webcamPreview?.videoHeight || 0);
  const maxWidth = 960;
  const scale = Math.min(1, maxWidth / sourceWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sourceWidth * scale));
  canvas.height = Math.max(1, Math.round(sourceHeight * scale));
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) {
    throw new Error("Could not prepare webcam snapshot.");
  }
  context.drawImage(webcamPreview, 0, 0, canvas.width, canvas.height);
  return {
    dataUrl: canvas.toDataURL("image/jpeg", 0.82),
    name: "Webcam"
  };
}

async function captureWebcamSnapshotForPrompt(options = {}) {
  if (!currentState.webcamMode) {
    return null;
  }
  try {
    setQuickHudStatus("Capturing webcam snapshot...");
    if (options.source === "voice") {
      setVoiceCaptureStatus("Capturing webcam...", "sending");
    }
    const snapshot = await captureWebcamSnapshot();
    setQuickHudStatus("Webcam snapshot attached automatically.");
    return snapshot;
  } catch (error) {
    const message = formatQuickStatus(error?.message || error || "Webcam snapshot failed.");
    setQuickHudStatus(`${message} Sending without webcam.`);
    if (options.source === "voice") {
      setVoiceCaptureStatus("Webcam unavailable; sending prompt...", "sending");
    }
    return null;
  }
}

async function setWebcamMode(enabled, options = {}) {
  const shouldEnable = Boolean(enabled);
  if (shouldEnable && isAuthRequired()) {
    syncAuthGate(currentAuthStatus, { message: "Sign in before using webcam context." });
    return;
  }
  if (shouldEnable) {
    setQuickHudStatus("Starting webcam context...");
    try {
      await ensureWebcamStream();
      currentState = await window.catbotDesktop.setState({ webcamMode: true });
      renderHudState(currentState);
      updateQuickHudVisualState();
      if (options.notify !== false) {
        setQuickHudStatus("Webcam context on.");
      }
    } catch (error) {
      cleanupWebcamStream();
      currentState = await window.catbotDesktop.setState({ webcamMode: false });
      renderHudState(currentState);
      updateQuickHudVisualState();
      setQuickHudStatus(formatQuickStatus(error?.message || error || "Could not start webcam."));
    }
  } else {
    cleanupWebcamStream();
    currentState = await window.catbotDesktop.setState({ webcamMode: false });
    renderHudState(currentState);
    updateQuickHudVisualState();
    if (options.notify !== false) {
      setQuickHudStatus("Webcam context off.");
    }
  }
}

async function toggleWebcamMode() {
  await setWebcamMode(!currentState.webcamMode);
}

async function syncWebcamModeWithState(state = currentState, options = {}) {
  if (!state.webcamMode || isAuthRequired(currentAuthStatus, state)) {
    cleanupWebcamStream();
    updateQuickHudVisualState();
    return;
  }
  try {
    await ensureWebcamStream();
    if (options.notify) {
      setQuickHudStatus("Webcam context ready.");
    }
  } catch (error) {
    cleanupWebcamStream();
    if (currentState.webcamMode) {
      currentState = await window.catbotDesktop.setState({ webcamMode: false });
      renderHudState(currentState);
    }
    setQuickHudStatus(formatQuickStatus(error?.message || error || "Could not start webcam."));
  } finally {
    updateQuickHudVisualState();
  }
}

function markAutoCompanionActivity() {
  autoCompanionLastActivityAt = Date.now();
}

function getRandomAutoCompanionDelayMs() {
  const minDelay = AUTO_COMPANION_MIN_DELAY_MS;
  const maxDelay = Math.max(minDelay, AUTO_COMPANION_MAX_DELAY_MS);
  return minDelay + Math.round(Math.random() * (maxDelay - minDelay));
}

function clearAutoCompanionTimer() {
  if (autoCompanionTimer) {
    clearTimeout(autoCompanionTimer);
    autoCompanionTimer = 0;
  }
}

function clearAutoCompanionEmoteTimer() {
  if (autoCompanionEmoteTimer) {
    clearTimeout(autoCompanionEmoteTimer);
    autoCompanionEmoteTimer = 0;
  }
}

function canRunAutoCompanionAction() {
  if (!currentState.autoCompanionMode || isAuthRequired()) {
    return false;
  }
  if (!currentState.visible || currentState.moveMode || currentState.quickHudVisible || activeHudPanel) {
    return false;
  }
  if (micRecorder?.state === "recording" || quickChatSend?.hasAttribute("aria-busy")) {
    return false;
  }
  if (analyserSpeechActive || Date.now() < speechActiveUntil + AUTO_COMPANION_SPEECH_COOLDOWN_MS) {
    return false;
  }
  if (Date.now() - autoCompanionLastActivityAt < AUTO_COMPANION_USER_IDLE_GRACE_MS) {
    return false;
  }
  return true;
}

async function refreshVrmAnimationDirectory() {
  try {
    const animations = await window.catbotDesktop.listVrmaAnimations?.();
    if (animations && typeof animations === "object") {
      availableVrmAnimations = {
        dance: Array.isArray(animations.dance) ? animations.dance : [],
        danceDirectory: animations.danceDirectory || availableVrmAnimations.danceDirectory || "model_avatar/AutoDance"
      };
    }
  } catch (error) {
    console.warn("Could not scan VRMA animation directory:", error);
  }
  return availableVrmAnimations;
}

function getDanceActionKey(relativePath) {
  const normalized = String(relativePath || "").replace(/\\/g, "/").toLowerCase();
  return `dance:${normalized.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}`;
}

async function ensureDanceActionsLoaded() {
  if (!vrmModel || !vrmRuntime?.mixer || vrmRuntime.version !== "1.0") {
    return [];
  }
  const animations = await refreshVrmAnimationDirectory();
  const danceEntries = Array.isArray(animations.dance) ? animations.dance : [];
  const loadedEntries = [];
  for (const entry of danceEntries) {
    const relativePath = entry?.path || "";
    if (!relativePath) {
      continue;
    }
    const actionKey = getDanceActionKey(relativePath);
    if (!vrmRuntime.actions?.[actionKey]) {
      try {
        vrmRuntime.actions[actionKey] = await loadVrmaAction(vrmModel, vrmRuntime.mixer, actionKey, relativePath);
      } catch (error) {
        console.warn(`Failed to load dance VRMA "${relativePath}":`, error);
        continue;
      }
    }
    loadedEntries.push({
      ...entry,
      actionKey
    });
  }
  return loadedEntries;
}

async function playRandomAutoDance() {
  if (currentState.mode !== "vrm" || !currentState.autoCompanionDance || hasActiveNonIdleVrmAction()) {
    return false;
  }
  const danceEntries = await ensureDanceActionsLoaded();
  if (!danceEntries.length) {
    setQuickHudStatus(`No dance VRMA files found in ${availableVrmAnimations.danceDirectory || "model_avatar/AutoDance"}.`);
    return false;
  }
  const entry = danceEntries[Math.floor(Math.random() * danceEntries.length)];
  playVrmAction(entry.actionKey, {
    loop: THREE.LoopOnce,
    repetitions: 1,
    fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
    fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
    forceRestart: true
  });
  setQuickHudStatus(`Auto dance: ${entry.name || "VRMA"}.`);
  return true;
}

async function runAutoCompanionEmote() {
  clearAutoCompanionEmoteTimer();
  const expressions = ["happy", "love", "surprised", "think"];
  const expression = expressions[Math.floor(Math.random() * expressions.length)];
  try {
    currentState = await window.catbotDesktop.setState({
      expression,
      transientExpression: true
    });
    renderHudState(currentState);
    autoCompanionEmoteTimer = window.setTimeout(async () => {
      autoCompanionEmoteTimer = 0;
      try {
        currentState = await window.catbotDesktop.setState({
          expression: "neutral",
          transientExpression: false
        });
        renderHudState(currentState);
      } catch (_) {
        // non-critical idle expression reset
      }
    }, 5200);
    return true;
  } catch (error) {
    console.warn("Auto companion emote failed:", error);
    return false;
  }
}

async function sendAutoCompanionMessage() {
  let screenSnapshot = null;
  const useScreen = currentState.autoCompanionScreenContext !== false;
  if (useScreen) {
    try {
      setQuickHudStatus("Auto companion is looking at the desktop...");
      screenSnapshot = await window.catbotDesktop.captureScreenSnapshot();
    } catch (error) {
      console.warn("Auto companion screen snapshot failed:", error);
    }
  }

  const prompt = screenSnapshot?.dataUrl
    ? "You are CATBot acting as a desktop companion. Make one brief, friendly, non-intrusive comment about what the user appears to be doing from the attached screen image. If the screen looks private, sensitive, or unclear, keep it general. Keep it under 25 words."
    : "You are CATBot acting as a desktop companion. Initiate one brief, warm check-in or playful comment for the user. Keep it under 22 words.";

  await sendQuickChatMessage({
    message: prompt,
    source: "auto",
    clearInput: false,
    lowLatency: true,
    screenImageDataUrl: screenSnapshot?.dataUrl || "",
    historyUserText: screenSnapshot?.dataUrl ? "Auto companion screen check-in" : "Auto companion check-in"
  });
  return true;
}

async function runAutoCompanionCycle() {
  autoCompanionTimer = 0;
  if (!canRunAutoCompanionAction()) {
    syncAutoCompanionScheduler();
    return;
  }
  autoCompanionRunning = true;
  try {
    const canDance = currentState.autoCompanionDance !== false && currentState.mode === "vrm";
    const roll = Math.random();
    if (canDance && roll < 0.28 && await playRandomAutoDance()) {
      return;
    }
    if (roll < 0.5 && await runAutoCompanionEmote()) {
      return;
    }
    await sendAutoCompanionMessage();
  } catch (error) {
    console.warn("Auto companion cycle failed:", error);
    setQuickHudStatus(formatQuickStatus(error?.message || error || "Auto companion action failed."));
  } finally {
    autoCompanionRunning = false;
    markAutoCompanionActivity();
    syncAutoCompanionScheduler();
  }
}

function syncAutoCompanionScheduler() {
  if (!currentState.autoCompanionMode || isAuthRequired()) {
    clearAutoCompanionTimer();
    return;
  }
  if (autoCompanionTimer || autoCompanionRunning) {
    return;
  }
  autoCompanionTimer = window.setTimeout(() => {
    void runAutoCompanionCycle();
  }, getRandomAutoCompanionDelayMs());
}

function modelDisplayName(modelPath) {
  const normalized = String(modelPath || "").replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() || "None";
}

function addHudSelectOption(select, value, label = value) {
  const normalizedValue = String(value || "").trim();
  if (!select || !normalizedValue) {
    return;
  }
  if (Array.from(select.options).some((option) => option.value === normalizedValue)) {
    return;
  }
  const option = document.createElement("option");
  option.value = normalizedValue;
  option.textContent = String(label || normalizedValue);
  select.appendChild(option);
}

function setHudTtsVoiceValue(value) {
  const selected = String(value || "alloy").trim() || "alloy";
  addHudSelectOption(hudTtsVoice, selected);
  if (hudTtsVoice) {
    hudTtsVoice.value = selected;
  }
}

async function populateHudTtsVoiceOptions(selectedVoice = currentState.ttsVoice) {
  if (!hudTtsVoice || typeof window.catbotDesktop.listTtsVoices !== "function") {
    setHudTtsVoiceValue(selectedVoice);
    return;
  }
  const desiredVoice = String(selectedVoice || hudTtsVoice.value || currentState.ttsVoice || "alloy").trim() || "alloy";
  try {
    const catalog = await window.catbotDesktop.listTtsVoices({
      proxyBaseUrl: hudProxyUrl?.value.trim() || currentState.proxyBaseUrl,
      ttsEndpoint: hudTtsEndpoint?.value.trim() || currentState.ttsEndpoint,
      ttsModel: hudTtsModel?.value.trim() || currentState.ttsModel,
      ttsVoice: desiredVoice
    });
    const voices = Array.isArray(catalog?.voices) ? catalog.voices : [];
    hudTtsVoice.replaceChildren();
    for (const voice of voices) {
      addHudSelectOption(hudTtsVoice, voice.id, voice.name || voice.id);
    }
    const catalogSelectedVoice = String(catalog?.selectedVoice || "").trim();
    const nextVoice = desiredVoice === "alloy" && catalogSelectedVoice
      ? catalogSelectedVoice
      : (desiredVoice || catalogSelectedVoice || currentState.ttsVoice);
    setHudTtsVoiceValue(nextVoice);
    if (!hudTtsVoice.value && hudTtsVoice.options.length > 0) {
      hudTtsVoice.selectedIndex = 0;
    }
  } catch (error) {
    addHudSelectOption(hudTtsVoice, desiredVoice);
    hudTtsVoice.value = desiredVoice;
    setQuickHudStatus(`Could not refresh TTS voices: ${String(error?.message || error)}`);
  }
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
        (action === "character" && activeHudPanel === "character") ||
        (action === "controls" && activeHudPanel === "settings") ||
        (action === "screen" && screenContextModeEnabled) ||
        (action === "move" && currentState.moveMode) ||
        (action === "webcam" && currentState.webcamMode) ||
        (action === "microphone" && micRecorder?.state === "recording")
    );
  }
  if (activeHudPanel === "chat") {
    requestAnimationFrame(() => quickChatInput?.focus());
  } else if (activeHudPanel === "auth") {
    requestAnimationFrame(() => hudAuthUsername?.focus());
  } else if (activeHudPanel === "character") {
    requestAnimationFrame(() => hudCompanionName?.focus());
    void refreshHudCompanions({ silent: true });
  } else if (activeHudPanel === "status") {
    requestAnimationFrame(() => hudSpeechText?.focus());
  } else if (activeHudPanel === "settings") {
    void populateHudTtsVoiceOptions(hudTtsVoice?.value || currentState.ttsVoice);
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

function isAuthRequired(status = currentAuthStatus, state = currentState) {
  return Boolean(state?.authRequired) || Boolean(status?.required) || !Boolean(status?.authenticated);
}

function setAuthGateStatus(message, type = "info") {
  if (!authGateStatus) {
    return;
  }
  authGateStatus.textContent = message;
  authGateStatus.classList.toggle("is-error", type === "error");
  authGateStatus.classList.toggle("is-success", type === "success");
}

function syncAuthGate(status = currentAuthStatus, options = {}) {
  currentAuthStatus = status || {};
  const required = isAuthRequired(currentAuthStatus, currentState);
  document.body.classList.toggle("auth-required", required);
  authGate?.setAttribute("aria-hidden", required ? "false" : "true");
  if (required) {
    closeHudPanel();
    if (authGateProxyUrl && !authGateProxyUrl.value.trim()) {
      authGateProxyUrl.value = currentState.proxyBaseUrl || "";
    }
    setAuthGateStatus(options.message || currentAuthStatus.error || "Sign in to continue.");
    if (options.focus !== false) {
      requestAnimationFrame(() => {
        const target = authGateUsername?.value ? authGatePassword : authGateUsername;
        target?.focus();
      });
    }
  } else {
    if (authGatePassword) {
      authGatePassword.value = "";
    }
    setAuthGateStatus("Signed in.", "success");
  }
}

async function refreshStateAfterAuth() {
  const nextState = await window.catbotDesktop.getState();
  currentState = nextState;
  renderHudState(currentState);
  syncQuickHudControls(currentState);
  applyStateToScene(currentState);
  void syncWebcamModeWithState(currentState);
  return currentState;
}

async function runAuthGate(action) {
  const username = String(authGateUsername?.value || "").trim();
  const password = String(authGatePassword?.value || "");
  if (!username || !password) {
    setAuthGateStatus("Username and password are required.", "error");
    (username ? authGatePassword : authGateUsername)?.focus();
    return;
  }
  for (const button of [authGateLoginBtn, authGateSignupBtn]) {
    if (button) {
      button.disabled = true;
    }
  }
  setAuthGateStatus(action === "signup" ? "Creating account..." : "Signing in...");
  try {
    currentAuthStatus = await window.catbotDesktop.authenticate({
      action,
      username,
      password,
      proxyBaseUrl: authGateProxyUrl?.value.trim() || currentState.proxyBaseUrl
    });
    renderAuthStatus(currentAuthStatus);
    await refreshStateAfterAuth();
    syncAuthGate(currentAuthStatus);
    setQuickHudStatus(`Signed in${currentAuthStatus.username ? ` as ${currentAuthStatus.username}` : ""}.`);
    await refreshHudCompanions({ silent: true });
  } catch (error) {
    setAuthGateStatus(formatQuickStatus(error?.message || error || "Authentication failed."), "error");
  } finally {
    for (const button of [authGateLoginBtn, authGateSignupBtn]) {
      if (button) {
        button.disabled = false;
      }
    }
  }
}

function truncateCompanionLabel(value, maxLength = 26) {
  const text = String(value || "").trim();
  if (!text || text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(1, maxLength - 1))}...`;
}

function summarizeDesktopCompanionState(state = currentState) {
  const modeLabel = state.mode === "live2d" ? "Live2D" : "VRM";
  const avatarName = modelDisplayName(state.modelPath);
  const chatModel = String(state.chatModel || "").trim();
  const voiceLabel = String(state.ttsVoice || state.ttsModel || "").trim();
  const soulLength = String(state.soulPrompt || "").trim().length;
  const descriptionParts = [`${modeLabel} avatar ${avatarName}`];
  if (chatModel) {
    descriptionParts.push(`chat ${truncateCompanionLabel(chatModel)}`);
  }
  if (voiceLabel) {
    descriptionParts.push(`voice ${truncateCompanionLabel(voiceLabel, 20)}`);
  }
  const tags = [
    chatModel ? `Chat ${truncateCompanionLabel(chatModel, 20)}` : "Proxy default chat",
    voiceLabel ? `Voice ${truncateCompanionLabel(voiceLabel, 18)}` : "Voice default",
    state.speakChatReplies === false ? "Silent replies" : "Spoken replies",
    soulLength ? `Soul ${soulLength} chars` : "No soul.md"
  ];
  return {
    title: state.activeCompanionName || "CATBot",
    description: descriptionParts.join(" | "),
    tags
  };
}

function renderHudCompanionTags(container, tags = []) {
  if (!container) {
    return;
  }
  container.replaceChildren();
  for (const tag of tags.filter(Boolean)) {
    const item = document.createElement("span");
    item.className = "hud-companion-tag";
    item.textContent = tag;
    container.appendChild(item);
  }
}

function setHudCompanionFeedback(message = "", type = "info") {
  if (!hudCompanionFeedback) {
    return;
  }
  hudCompanionFeedback.textContent = message;
  hudCompanionFeedback.classList.toggle("is-error", type === "error");
  hudCompanionFeedback.classList.toggle("is-success", type === "success");
}

function renderHudCompanionDraft(state = currentState) {
  const summary = summarizeDesktopCompanionState(state);
  const isDefault = Boolean(state.activeCompanionId && state.activeCompanionId === state.defaultCompanionId);
  if (hudCompanionCurrentName) {
    hudCompanionCurrentName.textContent = summary.title;
  }
  if (hudCompanionCurrentState) {
    hudCompanionCurrentState.textContent = state.activeCompanionId
      ? isDefault ? "Default" : "Active"
      : "Not saved";
  }
  if (hudCompanionCurrentSummary) {
    hudCompanionCurrentSummary.textContent = state.activeCompanionId
      ? `${summary.description}. Saved as "${state.activeCompanionName || state.activeCompanionId}".`
      : `${summary.description}. Save this setup as a reusable character profile.`;
  }
  renderHudCompanionTags(hudCompanionCurrentTags, summary.tags);
  if (hudCompanionName && !hudCompanionName.value.trim()) {
    const modelBase = modelDisplayName(state.modelPath).replace(/\.[^.]+$/, "");
    hudCompanionName.placeholder = modelBase ? `CATBot ${modelBase}` : "CATBot profile";
  }
  if (hudCompanionDefaultCheckbox) {
    hudCompanionDefaultCheckbox.checked = Boolean(state.activeCompanionId && state.activeCompanionId === state.defaultCompanionId);
  }
}

function renderHudCompanionList(companions = companionListCache) {
  if (!hudCompanionList) {
    return;
  }
  hudCompanionList.replaceChildren();
  if (companionsLoading) {
    const loading = document.createElement("li");
    loading.className = "hud-companion-empty";
    loading.textContent = "Loading character profiles...";
    hudCompanionList.appendChild(loading);
    return;
  }
  if (!Array.isArray(companions) || !companions.length) {
    const empty = document.createElement("li");
    empty.className = "hud-companion-empty";
    empty.textContent = currentAuthStatus.authenticated
      ? "No saved profiles yet. Save the current setup to create one."
      : "Sign in to load and save character profiles.";
    hudCompanionList.appendChild(empty);
    return;
  }

  for (const companion of companions) {
    const id = String(companion.id || "").trim();
    if (!id) {
      continue;
    }
    const isActive = id === currentState.activeCompanionId;
    const isDefault = id === currentState.defaultCompanionId;
    const item = document.createElement("li");
    item.classList.toggle("is-active", isActive);
    item.classList.toggle("is-default", isDefault);

    const copy = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = companion.name || id;
    const meta = document.createElement("span");
    meta.textContent = isDefault
      ? isActive ? "Default and active"
      : "Loads when CATBot opens"
      : isActive ? "Active profile"
      : "Saved profile";
    copy.append(name, meta);

    const actions = document.createElement("div");
    actions.className = "hud-companion-list-actions";
    const loadBtn = document.createElement("button");
    loadBtn.type = "button";
    loadBtn.textContent = "Load";
    loadBtn.addEventListener("click", () => {
      void loadHudCompanion(id);
    });
    const defaultBtn = document.createElement("button");
    defaultBtn.type = "button";
    defaultBtn.classList.toggle("is-default", isDefault);
    defaultBtn.textContent = isDefault ? "Default" : "Set";
    defaultBtn.title = isDefault ? "Clear default profile" : "Load this profile when CATBot opens";
    defaultBtn.addEventListener("click", () => {
      void setHudDefaultCompanion(isDefault ? "" : id);
    });
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => {
      void deleteHudCompanion(id, companion.name || id);
    });
    actions.append(loadBtn, defaultBtn, deleteBtn);
    item.append(copy, actions);
    hudCompanionList.appendChild(item);
  }
}

async function refreshHudCompanions(options = {}) {
  if (!window.catbotDesktop.listCompanions || companionsLoading) {
    return;
  }
  companionsLoading = true;
  renderHudCompanionList();
  try {
    companionListCache = await window.catbotDesktop.listCompanions({
      proxyBaseUrl: currentState.proxyBaseUrl
    });
    setHudCompanionFeedback(options.silent ? hudCompanionFeedback?.textContent || "" : "Character profiles loaded.", "success");
  } catch (error) {
    companionListCache = [];
    const message = String(error?.message || error || "Could not load character profiles.");
    setHudCompanionFeedback(formatQuickStatus(message), "error");
  } finally {
    companionsLoading = false;
    renderHudCompanionList();
  }
}

async function saveHudCompanion() {
  const fallbackName = summarizeDesktopCompanionState(currentState).title;
  const name = String(hudCompanionName?.value || "").trim() || fallbackName;
  if (!name) {
    setHudCompanionFeedback("Profile name is required.", "error");
    return;
  }
  if (hudSaveCompanionBtn) {
    hudSaveCompanionBtn.disabled = true;
  }
  setHudCompanionFeedback("Saving character profile...");
  try {
    const result = await window.catbotDesktop.createCompanion({
      name,
      activate: true,
      setDefault: Boolean(hudCompanionDefaultCheckbox?.checked),
      proxyBaseUrl: currentState.proxyBaseUrl
    });
    if (result?.state) {
      currentState = result.state;
      applyStateToScene(currentState);
    }
    if (hudCompanionName) {
      hudCompanionName.value = "";
    }
    await refreshHudCompanions({ silent: true });
    setHudCompanionFeedback(`Saved "${result?.companion?.name || name}".`, "success");
  } catch (error) {
    setHudCompanionFeedback(formatQuickStatus(error?.message || error || "Could not save profile."), "error");
  } finally {
    if (hudSaveCompanionBtn) {
      hudSaveCompanionBtn.disabled = false;
    }
  }
}

async function loadHudCompanion(companionId) {
  setHudCompanionFeedback("Loading character profile...");
  try {
    const result = await window.catbotDesktop.loadCompanion(companionId, {
      proxyBaseUrl: currentState.proxyBaseUrl
    });
    if (result?.state) {
      currentState = result.state;
      applyStateToScene(currentState);
    }
    await refreshHudCompanions({ silent: true });
    setHudCompanionFeedback(`Loaded "${result?.companion?.name || companionId}".`, "success");
  } catch (error) {
    setHudCompanionFeedback(formatQuickStatus(error?.message || error || "Could not load profile."), "error");
  }
}

async function deleteHudCompanion(companionId, name) {
  if (!window.confirm(`Delete character profile "${name || companionId}"?`)) {
    return;
  }
  setHudCompanionFeedback("Deleting character profile...");
  try {
    const result = await window.catbotDesktop.deleteCompanion(companionId, {
      proxyBaseUrl: currentState.proxyBaseUrl
    });
    if (result?.state) {
      currentState = result.state;
      applyStateToScene(currentState);
    }
    await refreshHudCompanions({ silent: true });
    setHudCompanionFeedback(`Deleted "${name || companionId}".`, "success");
  } catch (error) {
    setHudCompanionFeedback(formatQuickStatus(error?.message || error || "Could not delete profile."), "error");
  }
}

async function setHudDefaultCompanion(companionId) {
  currentState = await window.catbotDesktop.setDefaultCompanion(companionId);
  renderHudState(currentState);
  renderHudCompanionList();
  setHudCompanionFeedback(companionId ? "Default character profile updated." : "Default character profile cleared.", "success");
}

function renderHudState(state = currentState) {
  renderHudChat(state.desktopChatHistory);
  if (hudSoulPrompt) {
    hudSoulPrompt.value = String(state.soulPrompt || "");
  }
  renderHudCompanionDraft(state);
  renderHudCompanionList();
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
    setHudTtsVoiceValue(state.ttsVoice || "alloy");
  }
  const windowBounds = state.windowBounds || {};
  const windowWidth = Math.max(240, Math.min(1600, Math.round(Number(windowBounds.width) || 480)));
  const windowHeight = Math.max(320, Math.min(1800, Math.round(Number(windowBounds.height) || 640)));
  if (hudWindowWidth) {
    hudWindowWidth.value = String(windowWidth);
  }
  if (hudWindowHeight) {
    hudWindowHeight.value = String(windowHeight);
  }
  if (hudToggleSpeakBtn) {
    hudToggleSpeakBtn.textContent = `Speak Replies: ${state.speakChatReplies === false ? "Off" : "On"}`;
  }
  if (hudToggleWebcamBtn) {
    hudToggleWebcamBtn.textContent = `Webcam Context: ${state.webcamMode ? "On" : "Off"}`;
  }
  if (hudToggleAutoCompanionBtn) {
    hudToggleAutoCompanionBtn.textContent = `Auto Companion: ${state.autoCompanionMode ? "On" : "Off"}`;
  }
  if (hudToggleAutoScreenBtn) {
    hudToggleAutoScreenBtn.textContent = `Auto Screen: ${state.autoCompanionScreenContext === false ? "Off" : "On"}`;
  }
  if (hudToggleAutoDanceBtn) {
    hudToggleAutoDanceBtn.textContent = `Auto Dance: ${state.autoCompanionDance === false ? "Off" : "On"}`;
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
          alwaysOnTop: state.alwaysOnTop,
          width: windowWidth,
          height: windowHeight
        },
        auth: {
          authenticated: Boolean(currentAuthStatus.authenticated),
          required: Boolean(state.authRequired),
          username: currentAuthStatus.username || ""
        },
        proxyBaseUrl: state.proxyBaseUrl,
        webClientUrl: state.webClientUrl,
        chatEndpoint: state.chatEndpoint || "(proxy default)",
        chatModel: state.chatModel || "(default)",
        chatApiKeyConfigured: Boolean(state.chatApiKeyConfigured),
        webcamMode: Boolean(state.webcamMode),
        webcamReady: isWebcamStreamActive(),
        autoCompanion: {
          enabled: Boolean(state.autoCompanionMode),
          screenContext: state.autoCompanionScreenContext !== false,
          dance: state.autoCompanionDance !== false,
          danceFiles: Array.isArray(availableVrmAnimations.dance) ? availableVrmAnimations.dance.length : 0
        },
        soulPromptChars: String(state.soulPrompt || "").length,
        activeCompanion: state.activeCompanionName || state.activeCompanionId || "",
        defaultCompanionId: state.defaultCompanionId || "",
        speakChatReplies: state.speakChatReplies !== false,
        screenContextMode: Boolean(state.screenContextMode),
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

function getHudWindowBoundsPatch(widthValue = hudWindowWidth?.value, heightValue = hudWindowHeight?.value) {
  const currentBounds = currentState.windowBounds || {};
  const width = Math.max(240, Math.min(1600, Math.round(Number(widthValue) || Number(currentBounds.width) || 480)));
  const height = Math.max(320, Math.min(1800, Math.round(Number(heightValue) || Number(currentBounds.height) || 640)));
  return {
    windowBounds: {
      x: Math.round(Number.isFinite(Number(currentBounds.x)) ? Number(currentBounds.x) : 80),
      y: Math.round(Number.isFinite(Number(currentBounds.y)) ? Number(currentBounds.y) : 80),
      width,
      height
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
    ttsVoice: hudTtsVoice?.value.trim() || "alloy",
    ...getHudWindowBoundsPatch()
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
    const isActive =
      (action === "microphone" && isRecording) ||
      (action === "webcam" && Boolean(currentState.webcamMode)) ||
      (action === "screen" && screenContextModeEnabled);
    button.classList.toggle("is-active", isActive);
    button.classList.toggle("is-warming", action === "webcam" && Boolean(webcamStartPromise));
    button.classList.toggle("has-attachment", action === "screen" && Boolean(pendingScreenSnapshot));
  }
}

function syncQuickHudControls(state = currentState) {
  if (!quickHud) {
    return;
  }
  screenContextModeEnabled = Boolean(state.screenContextMode);
  if (!screenContextModeEnabled) {
    pendingScreenSnapshot = null;
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
      (action === "webcam" && state.webcamMode) ||
      (action === "screen" && screenContextModeEnabled) ||
      (action === "speak" && state.speakChatReplies !== false) ||
      (action === "focus-chat" && activeHudPanel === "chat") ||
      (action === "models" && activeHudPanel === "models") ||
      (action === "character" && activeHudPanel === "character") ||
      (action === "controls" && activeHudPanel === "settings");
    button.classList.toggle("is-active", isActive);
    button.classList.toggle("is-muted", action === "speak" && state.speakChatReplies === false);
    button.classList.toggle("is-warming", action === "webcam" && Boolean(webcamStartPromise));
    button.classList.toggle("has-attachment", action === "screen" && Boolean(pendingScreenSnapshot));
  }
  if (isVisible && !quickHudWasVisible) {
    requestAnimationFrame(() => quickChatInput?.focus());
  }
  quickHudWasVisible = isVisible;
  renderHudState(state);
}

async function sendQuickChatMessage(options = {}) {
  if (isAuthRequired()) {
    syncAuthGate(currentAuthStatus, {
      message: options.source === "voice" ? "Sign in before using voice chat." : "Sign in to chat with CATBot."
    });
    return;
  }
  const messageOverride = typeof options.message === "string" ? options.message.trim() : "";
  const isVoiceFlow = options.source === "voice";
  const defaultVisualPrompt = pendingScreenSnapshot || screenContextModeEnabled
    ? "What can you see on my screen?"
    : currentState.webcamMode
      ? "What can you see from my webcam?"
      : "";
  const text = messageOverride || String(quickChatInput?.value || "").trim() || defaultVisualPrompt;
  if (!text) {
    return;
  }
  if (quickChatSend) {
    quickChatSend.disabled = true;
    quickChatSend.setAttribute("aria-busy", "true");
  }
  setQuickHudStatus("Asking CATBot...");
  if (isVoiceFlow) {
    setVoiceCaptureStatus("Sending...", "sending");
  }
  const webcamSnapshot = await captureWebcamSnapshotForPrompt(options);
  setQuickHudStatus(webcamSnapshot ? "Asking CATBot with webcam context..." : "Asking CATBot...");
  if (isVoiceFlow) {
    setVoiceCaptureStatus("Sending...", "sending");
  }
  let screenSnapshot = null;
  if (!options.screenImageDataUrl && !pendingScreenSnapshot && screenContextModeEnabled) {
    try {
      setQuickHudStatus("Capturing screen context...");
      screenSnapshot = await window.catbotDesktop.captureScreenSnapshot();
    } catch (error) {
      console.warn("Persistent screen context capture failed:", error);
      setQuickHudStatus(formatQuickStatus(error?.message || error || "Screen snapshot failed."));
    }
  }
  const screenImageDataUrl = options.screenImageDataUrl || pendingScreenSnapshot?.dataUrl || screenSnapshot?.dataUrl || "";
  const usedPendingScreenSnapshot = Boolean(!options.screenImageDataUrl && pendingScreenSnapshot);
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
      lowLatency: Boolean(options.lowLatency),
      screenImageDataUrl,
      webcamImageDataUrl: webcamSnapshot?.dataUrl || "",
      historyUserText: options.historyUserText || ""
    });
    if (quickChatInput && options.clearInput !== false) {
      quickChatInput.value = "";
    }
    if (usedPendingScreenSnapshot) {
      pendingScreenSnapshot = null;
    }
    updateQuickHudVisualState();
    if (result?.state) {
      currentState = result.state;
      applyStateToScene(currentState);
    }
    setQuickHudStatus("Reply sent to the avatar.");
    if (isVoiceFlow) {
      setVoiceCaptureStatus("Replying...", "replying");
      clearVoiceCaptureStatus(1300);
    }
  } catch (error) {
    const message = String(error?.message || error || "Desktop chat failed.");
    setQuickHudStatus(formatQuickStatus(message));
    if (isVoiceFlow) {
      setVoiceCaptureStatus(formatQuickStatus(message), "error");
      clearVoiceCaptureStatus(5000);
    }
    await window.catbotDesktop.setState({
      expression: "sad",
      transientExpression: true,
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
  if (isAuthRequired()) {
    syncAuthGate(currentAuthStatus, { message: "Sign in before attaching a screen snapshot." });
    return;
  }
  screenContextModeEnabled = !screenContextModeEnabled;
  currentState = await window.catbotDesktop.setState({ screenContextMode: screenContextModeEnabled });
  renderHudState(currentState);
  if (!screenContextModeEnabled) {
    pendingScreenSnapshot = null;
    updateQuickHudVisualState();
    setQuickHudStatus("Screen context off.");
    quickChatInput?.focus();
    return;
  }
  pendingScreenSnapshot = null;
  updateQuickHudVisualState();
  setQuickHudStatus("Screen context on. Each prompt will include a fresh screenshot.");
  quickChatInput?.focus();
  try {
    pendingScreenSnapshot = await window.catbotDesktop.captureScreenSnapshot();
    updateQuickHudVisualState();
    setQuickHudStatus("Screen context on. Snapshot ready for the next prompt.");
  } catch (error) {
    console.warn("Initial screen context snapshot failed:", error);
    setQuickHudStatus("Screen context on. A screenshot will be retried when you send.");
  }
}

function cleanupMicStream() {
  if (micStopTimer) {
    clearTimeout(micStopTimer);
    micStopTimer = 0;
  }
  if (micAnalysisRafId) {
    cancelAnimationFrame(micAnalysisRafId);
    micAnalysisRafId = 0;
  }
  try {
    micSourceNode?.disconnect();
  } catch (_) {
    // ignore source cleanup failures
  }
  try {
    micAnalyserNode?.disconnect();
  } catch (_) {
    // ignore analyser cleanup failures
  }
  try {
    micAudioContext?.close?.();
  } catch (_) {
    // ignore audio context cleanup failures
  }
  micAudioContext = null;
  micAnalyserNode = null;
  micSourceNode = null;
  micRecordingStartedAt = 0;
  micSpeechStarted = false;
  micLastVoiceAt = 0;
  try {
    micStream?.getTracks?.().forEach((track) => track.stop());
  } catch (_) {
    // ignore track cleanup failures
  }
  micStream = null;
}

async function prewarmVoiceChat() {
  try {
    await window.catbotDesktop.prewarmChat?.({
      proxyBaseUrl: currentState.proxyBaseUrl
    });
  } catch (_) {
    // Prewarm only hides setup latency; failure should not block recording.
  }
}

async function startMicSilenceDetection(stream) {
  try {
    micAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (micAudioContext.state === "suspended") {
      await micAudioContext.resume();
    }
    micSourceNode = micAudioContext.createMediaStreamSource(stream);
    micAnalyserNode = micAudioContext.createAnalyser();
    micAnalyserNode.fftSize = 1024;
    micAnalyserNode.smoothingTimeConstant = 0.25;
    micSourceNode.connect(micAnalyserNode);
  } catch (error) {
    console.warn("Could not start microphone silence detection:", error);
    return;
  }

  const buffer = new Uint8Array(micAnalyserNode.fftSize);
  micRecordingStartedAt = performance.now();
  micSpeechStarted = false;
  micLastVoiceAt = micRecordingStartedAt;

  const step = () => {
    if (!micRecorder || micRecorder.state !== "recording" || !micAnalyserNode) {
      micAnalysisRafId = 0;
      return;
    }

    micAnalyserNode.getByteTimeDomainData(buffer);
    let sum = 0;
    for (let index = 0; index < buffer.length; index += 1) {
      const normalizedSample = (buffer[index] - 128) / 128;
      sum += normalizedSample * normalizedSample;
    }
    const rms = Math.sqrt(sum / buffer.length);
    const now = performance.now();
    const elapsedMs = now - micRecordingStartedAt;

    if (rms >= VOICE_CAPTURE_RMS_THRESHOLD) {
      micSpeechStarted = true;
      micLastVoiceAt = now;
    }

    const passedMinimum = elapsedMs >= VOICE_CAPTURE_MIN_MS;
    const speechEnded = micSpeechStarted && now - micLastVoiceAt >= VOICE_CAPTURE_SILENCE_MS;
    const noSpeechTimeout = !micSpeechStarted && elapsedMs >= VOICE_CAPTURE_START_GRACE_MS;
    if (passedMinimum && (speechEnded || noSpeechTimeout)) {
      stopMicrophoneRecording();
      return;
    }

    micAnalysisRafId = requestAnimationFrame(step);
  };

  micAnalysisRafId = requestAnimationFrame(step);
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
  if (micAutoSendOnStop) {
    setVoiceCaptureStatus("Transcribing...", "transcribing");
  }
  try {
    micRecorder.requestData();
  } catch (_) {
    // Some Chromium builds do not allow requestData immediately before stop.
  }
  micRecorder.stop();
}

async function startMicrophoneRecording(options = {}) {
  if (isAuthRequired()) {
    syncAuthGate(currentAuthStatus, { message: "Sign in before using voice chat." });
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    setQuickHudStatus("Microphone STT is not available in this Electron runtime.");
    setVoiceCaptureStatus("Microphone unavailable.", "error");
    clearVoiceCaptureStatus(3500);
    return;
  }

  micAutoSendOnStop = Boolean(options.autoSend);
  setQuickHudStatus("Listening...");
  if (micAutoSendOnStop) {
    setVoiceCaptureStatus("Listening...", "recording");
    void prewarmVoiceChat();
  }
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
    void startMicSilenceDetection(micStream);
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
      const shouldAutoSend = micAutoSendOnStop;
      micAutoSendOnStop = false;
      const recordedMimeType = micRecorder?.mimeType || mimeType || "audio/webm";
      const blob = new Blob(micChunks, { type: recordedMimeType });
      micRecorder = null;
      cleanupMicStream();
      updateQuickHudVisualState();
      try {
        if (shouldAutoSend) {
          setVoiceCaptureStatus("Transcribing...", "transcribing");
        }
        const text = await transcribeMicBlob(blob);
        if (shouldAutoSend) {
          await sendQuickChatMessage({
            message: text,
            source: "voice",
            clearInput: false,
            lowLatency: true
          });
        } else if (quickChatInput) {
          quickChatInput.value = quickChatInput.value ? `${quickChatInput.value.trim()} ${text}` : text;
          setQuickHudStatus("Transcription added to the prompt.");
          quickChatInput?.focus();
        }
      } catch (error) {
        const message = String(error?.message || error || "Transcription failed.");
        setQuickHudStatus(formatQuickStatus(message));
        if (shouldAutoSend) {
          setVoiceCaptureStatus(formatQuickStatus(message), "error");
          clearVoiceCaptureStatus(5000);
        }
      }
    });
    micRecorder.start(250);
    micStopTimer = window.setTimeout(stopMicrophoneRecording, VOICE_CAPTURE_MAX_MS);
    updateQuickHudVisualState();
  } catch (error) {
    micRecorder = null;
    micAutoSendOnStop = false;
    cleanupMicStream();
    updateQuickHudVisualState();
    const message = String(error?.message || error || "Could not start microphone.");
    setQuickHudStatus(formatQuickStatus(message));
    setVoiceCaptureStatus(formatQuickStatus(message), "error");
    clearVoiceCaptureStatus(5000);
  }
}

async function toggleMicrophoneRecording(options = {}) {
  if (micRecorder?.state === "recording") {
    stopMicrophoneRecording();
    return;
  }
  await startMicrophoneRecording(options);
}

function setupQuickHud() {
  if (!quickHud) {
    return;
  }

  authGate?.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  authGateLoginBtn?.addEventListener("click", () => runAuthGate("login"));
  authGateSignupBtn?.addEventListener("click", () => runAuthGate("signup"));

  for (const input of [authGateProxyUrl, authGateUsername, authGatePassword]) {
    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runAuthGate("login");
      }
    });
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
    if (isAuthRequired() && action !== "close") {
      syncAuthGate(currentAuthStatus, { message: "Sign in to use CATBot Desktop." });
      return;
    }
    if (action === "focus-chat") {
      setHudPanel("chat");
      quickChatInput?.focus();
    } else if (action === "microphone") {
      await toggleMicrophoneRecording({ autoSend: true });
    } else if (action === "screen") {
      await attachScreenSnapshot();
    } else if (action === "webcam") {
      await toggleWebcamMode();
    } else if (action === "models") {
      setHudPanel("models");
    } else if (action === "character") {
      setHudPanel("character");
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
    companionListCache = [];
    renderAuthStatus(currentAuthStatus);
    await refreshStateAfterAuth();
    syncAuthGate(currentAuthStatus, { message: "Sign in to continue." });
    renderHudCompanionList();
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

  hudRefreshCompanionsBtn?.addEventListener("click", async () => {
    await refreshHudCompanions();
  });

  hudSaveCompanionBtn?.addEventListener("click", async () => {
    await saveHudCompanion();
  });

  hudCompanionName?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void saveHudCompanion();
    }
  });

  hudClearDefaultCompanionBtn?.addEventListener("click", async () => {
    await setHudDefaultCompanion("");
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

  for (const input of [hudProxyUrl, hudTtsEndpoint, hudTtsModel]) {
    input?.addEventListener("change", () => {
      void populateHudTtsVoiceOptions(hudTtsVoice?.value || currentState.ttsVoice);
    });
  }

  hudApplyWindowSizeBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud(getHudWindowBoundsPatch());
    setQuickHudStatus("Avatar window size applied.");
  });

  hudResetWindowSizeBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud(getHudWindowBoundsPatch(480, 640));
    setQuickHudStatus("Avatar window size reset.");
  });

  hudToggleSpeakBtn?.addEventListener("click", async () => {
    await updateDesktopStateFromHud({ speakChatReplies: currentState.speakChatReplies === false });
  });

  hudToggleWebcamBtn?.addEventListener("click", async () => {
    await toggleWebcamMode();
  });

  hudToggleAutoCompanionBtn?.addEventListener("click", async () => {
    const enabled = !currentState.autoCompanionMode;
    currentState = await window.catbotDesktop.setState({ autoCompanionMode: enabled });
    renderHudState(currentState);
    markAutoCompanionActivity();
    syncAutoCompanionScheduler();
    setQuickHudStatus(enabled ? "Auto companion mode on." : "Auto companion mode off.");
  });

  hudToggleAutoScreenBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.setState({
      autoCompanionScreenContext: currentState.autoCompanionScreenContext === false
    });
    renderHudState(currentState);
    syncAutoCompanionScheduler();
  });

  hudToggleAutoDanceBtn?.addEventListener("click", async () => {
    currentState = await window.catbotDesktop.setState({
      autoCompanionDance: currentState.autoCompanionDance === false
    });
    renderHudState(currentState);
    syncAutoCompanionScheduler();
    if (currentState.autoCompanionDance !== false) {
      void refreshVrmAnimationDirectory();
    }
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
    if (isAuthRequired()) {
      if (event.key === "Escape") {
        event.preventDefault();
        syncAuthGate(currentAuthStatus, { message: "Sign in to continue." });
      }
      return;
    }

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
      await toggleMicrophoneRecording({ autoSend: true });
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
      setHudPanel("character");
    } else if (key === "5") {
      event.preventDefault();
      setHudPanel("settings");
    } else if (key === "6") {
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
    if (isAuthRequired()) {
      syncAuthGate(currentAuthStatus, { message: "Sign in to use CATBot Desktop." });
      return;
    }
    await window.catbotDesktop.toggleQuickHud();
  });

  syncQuickHudControls(currentState);
}

window.catbotDesktop.onVoiceCaptureShortcut?.(() => {
  if (isAuthRequired()) {
    syncAuthGate(currentAuthStatus, { message: "Sign in before using voice chat." });
    return;
  }
  void toggleMicrophoneRecording({ autoSend: true });
});

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
    await refreshStateAfterAuth();
    syncAuthGate(currentAuthStatus);
    await refreshHudCompanions({ silent: true });
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
  syncAvatarOverlayPosition(currentState);
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
  const hipsBone = getHumanoidBoneNode(vrm, "hips");
  const leftShoulder = getHumanoidBoneNode(vrm, "leftShoulder");
  const rightShoulder = getHumanoidBoneNode(vrm, "rightShoulder");
  const leftUpperArm = getHumanoidBoneNode(vrm, "leftUpperArm");
  const rightUpperArm = getHumanoidBoneNode(vrm, "rightUpperArm");
  const leftLowerArm = getHumanoidBoneNode(vrm, "leftLowerArm");
  const rightLowerArm = getHumanoidBoneNode(vrm, "rightLowerArm");
  const leftHand = getHumanoidBoneNode(vrm, "leftHand");
  const rightHand = getHumanoidBoneNode(vrm, "rightHand");
  const spineBone = getHumanoidBoneNode(vrm, "spine");
  const chestBone = getHumanoidBoneNode(vrm, "chest");
  const upperChestBone = getHumanoidBoneNode(vrm, "upperChest");
  const neckBone = getHumanoidBoneNode(vrm, "neck");
  const headBone = getHumanoidBoneNode(vrm, "head");
  const leftUpperLeg = getHumanoidBoneNode(vrm, "leftUpperLeg");
  const rightUpperLeg = getHumanoidBoneNode(vrm, "rightUpperLeg");
  const leftLowerLeg = getHumanoidBoneNode(vrm, "leftLowerLeg");
  const rightLowerLeg = getHumanoidBoneNode(vrm, "rightLowerLeg");
  const leftFoot = getHumanoidBoneNode(vrm, "leftFoot");
  const rightFoot = getHumanoidBoneNode(vrm, "rightFoot");
  const fingerBones = {};
  const baseFingerRotations = {};
  for (const boneName of VRM_FINGER_BONE_NAMES) {
    const bone = getHumanoidBoneNode(vrm, boneName);
    if (!bone) {
      continue;
    }
    fingerBones[boneName] = bone;
    baseFingerRotations[boneName] = {
      x: bone.rotation.x,
      y: bone.rotation.y,
      z: bone.rotation.z
    };
  }

  vrmRuntime = {
    version: isVrm0(vrm) ? "0.0" : "1.0",
    idleStart: performance.now(),
    hipsBone,
    leftShoulder,
    rightShoulder,
    leftUpperArm,
    rightUpperArm,
    leftLowerArm,
    rightLowerArm,
    leftHand,
    rightHand,
    spineBone,
    chestBone,
    upperChestBone,
    neckBone,
    headBone,
    leftUpperLeg,
    rightUpperLeg,
    leftLowerLeg,
    rightLowerLeg,
    leftFoot,
    rightFoot,
    fingerBones,
    baseFingerRotations,
    baseLeftArmZ: leftUpperArm ? leftUpperArm.rotation.z : 0,
    baseRightArmZ: rightUpperArm ? rightUpperArm.rotation.z : 0,
    baseLeftArmY: leftUpperArm ? leftUpperArm.rotation.y : 0,
    baseRightArmY: rightUpperArm ? rightUpperArm.rotation.y : 0,
    baseLeftUpperArmX: leftUpperArm ? leftUpperArm.rotation.x : 0,
    baseRightUpperArmX: rightUpperArm ? rightUpperArm.rotation.x : 0,
    baseLeftLowerArmX: leftLowerArm ? leftLowerArm.rotation.x : 0,
    baseRightLowerArmX: rightLowerArm ? rightLowerArm.rotation.x : 0,
    baseLeftLowerArmY: leftLowerArm ? leftLowerArm.rotation.y : 0,
    baseRightLowerArmY: rightLowerArm ? rightLowerArm.rotation.y : 0,
    baseLeftLowerArmZ: leftLowerArm ? leftLowerArm.rotation.z : 0,
    baseRightLowerArmZ: rightLowerArm ? rightLowerArm.rotation.z : 0,
    baseLeftHandX: leftHand ? leftHand.rotation.x : 0,
    baseRightHandX: rightHand ? rightHand.rotation.x : 0,
    baseLeftHandY: leftHand ? leftHand.rotation.y : 0,
    baseRightHandY: rightHand ? rightHand.rotation.y : 0,
    baseLeftHandZ: leftHand ? leftHand.rotation.z : 0,
    baseRightHandZ: rightHand ? rightHand.rotation.z : 0,
    baseLeftUpperLegX: leftUpperLeg ? leftUpperLeg.rotation.x : 0,
    baseRightUpperLegX: rightUpperLeg ? rightUpperLeg.rotation.x : 0,
    baseLeftUpperLegY: leftUpperLeg ? leftUpperLeg.rotation.y : 0,
    baseRightUpperLegY: rightUpperLeg ? rightUpperLeg.rotation.y : 0,
    baseLeftUpperLegZ: leftUpperLeg ? leftUpperLeg.rotation.z : 0,
    baseRightUpperLegZ: rightUpperLeg ? rightUpperLeg.rotation.z : 0,
    baseLeftLowerLegX: leftLowerLeg ? leftLowerLeg.rotation.x : 0,
    baseRightLowerLegX: rightLowerLeg ? rightLowerLeg.rotation.x : 0,
    baseLeftLowerLegY: leftLowerLeg ? leftLowerLeg.rotation.y : 0,
    baseRightLowerLegY: rightLowerLeg ? rightLowerLeg.rotation.y : 0,
    baseLeftLowerLegZ: leftLowerLeg ? leftLowerLeg.rotation.z : 0,
    baseRightLowerLegZ: rightLowerLeg ? rightLowerLeg.rotation.z : 0,
    baseLeftFootX: leftFoot ? leftFoot.rotation.x : 0,
    baseRightFootX: rightFoot ? rightFoot.rotation.x : 0,
    baseLeftFootY: leftFoot ? leftFoot.rotation.y : 0,
    baseRightFootY: rightFoot ? rightFoot.rotation.y : 0,
    baseLeftFootZ: leftFoot ? leftFoot.rotation.z : 0,
    baseRightFootZ: rightFoot ? rightFoot.rotation.z : 0,
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
    emotionTimerId: 0,
    baseStandingPoseSnapshot: null,
    idleReferencePoseSnapshot: null,
    lastPoseSnapshot: null,
    lastFrameHadRunningAction: false,
    restorePoseOnNextManualIdle: false,
    poseBlend: null
  };
  vrmRuntime.baseStandingPoseSnapshot = createVrmPoseSnapshot(vrmRuntime);
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

function captureVrmActionPoseSnapshot(actionKey, sampleSeconds = 0) {
  if (!vrmRuntime?.mixer || !actionKey) {
    return null;
  }
  const action = vrmRuntime.actions?.[actionKey];
  if (!action) {
    return null;
  }

  const previousPose = createVrmPoseSnapshot(vrmRuntime);
  const previousMixerTime = vrmRuntime.mixer.time;
  const previousActionState = {
    enabled: action.enabled,
    paused: action.paused,
    loop: action.loop,
    repetitions: action.repetitions,
    clampWhenFinished: action.clampWhenFinished,
    time: action.time
  };

  try {
    const clipDuration = Number(action.getClip?.().duration);
    const sampleTime = Number.isFinite(clipDuration)
      ? Math.max(0, Math.min(sampleSeconds, clipDuration))
      : Math.max(0, sampleSeconds);
    action.reset();
    action.enabled = true;
    action.paused = false;
    action.loop = THREE.LoopOnce;
    action.repetitions = 1;
    action.clampWhenFinished = true;
    action.setEffectiveWeight(1);
    action.setEffectiveTimeScale(1);
    action.play();
    action.time = sampleTime;
    vrmRuntime.mixer.update(0);
    return createVrmPoseSnapshot(vrmRuntime);
  } catch (error) {
    console.warn(`Failed to capture VRMA pose for "${actionKey}":`, error);
    return null;
  } finally {
    try {
      action.stop();
      action.enabled = previousActionState.enabled;
      action.paused = previousActionState.paused;
      action.loop = previousActionState.loop;
      action.repetitions = previousActionState.repetitions;
      action.clampWhenFinished = previousActionState.clampWhenFinished;
      action.time = previousActionState.time;
      action.setEffectiveWeight(1);
      action.setEffectiveTimeScale(1);
      vrmRuntime.mixer.time = previousMixerTime;
    } catch (_) {
      // ignore pose capture cleanup failures
    }
    restoreVrmPoseSnapshot(previousPose, vrmRuntime);
  }
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
    return;
  }

  vrmRuntime.idleReferencePoseSnapshot = captureVrmActionPoseSnapshot(
    "idle",
    VRM_IDLE_REFERENCE_POSE_SAMPLE_SECONDS
  );
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

const VRM_POSE_SNAPSHOT_BONES = [
  "hipsBone",
  "leftShoulder",
  "rightShoulder",
  "leftUpperArm",
  "rightUpperArm",
  "leftLowerArm",
  "rightLowerArm",
  "leftHand",
  "rightHand",
  "spineBone",
  "chestBone",
  "upperChestBone",
  "neckBone",
  "headBone",
  "leftUpperLeg",
  "rightUpperLeg",
  "leftLowerLeg",
  "rightLowerLeg",
  "leftFoot",
  "rightFoot"
];

function getVrmPoseSnapshotBone(key, runtime = vrmRuntime) {
  if (!runtime || !key) {
    return null;
  }
  if (key.startsWith("finger:")) {
    return runtime.fingerBones?.[key.slice("finger:".length)] || null;
  }
  return runtime[key] || null;
}

function createVrmBonePoseSnapshot(bone) {
  if (!bone) {
    return null;
  }
  return {
    rotation: {
      x: bone.rotation.x,
      y: bone.rotation.y,
      z: bone.rotation.z
    },
    position: {
      x: bone.position.x,
      y: bone.position.y,
      z: bone.position.z
    }
  };
}

function createVrmPoseSnapshot(runtime = vrmRuntime) {
  if (!runtime) {
    return null;
  }
  const snapshot = {};
  for (const key of VRM_POSE_SNAPSHOT_BONES) {
    const pose = createVrmBonePoseSnapshot(runtime[key]);
    if (!pose) {
      continue;
    }
    snapshot[key] = pose;
  }
  for (const boneName of VRM_FINGER_BONE_NAMES) {
    const pose = createVrmBonePoseSnapshot(runtime.fingerBones?.[boneName]);
    if (!pose) {
      continue;
    }
    snapshot[`finger:${boneName}`] = pose;
  }
  return Object.keys(snapshot).length ? snapshot : null;
}

function restoreVrmPoseSnapshot(snapshot, runtime = vrmRuntime) {
  if (!snapshot || !runtime) {
    return;
  }
  for (const [key, pose] of Object.entries(snapshot)) {
    const bone = getVrmPoseSnapshotBone(key, runtime);
    if (!bone) {
      continue;
    }
    if (pose.rotation) {
      bone.rotation.set(pose.rotation.x, pose.rotation.y, pose.rotation.z);
    }
    if (pose.position) {
      bone.position.set(pose.position.x, pose.position.y, pose.position.z);
    }
  }
}

function lerpVrmPoseValue(fromValue, toValue, weight) {
  const from = Number.isFinite(Number(fromValue)) ? Number(fromValue) : 0;
  const to = Number.isFinite(Number(toValue)) ? Number(toValue) : from;
  return from + (to - from) * weight;
}

function lerpVrmPoseAngle(fromValue, toValue, weight) {
  const from = Number.isFinite(Number(fromValue)) ? Number(fromValue) : 0;
  const to = Number.isFinite(Number(toValue)) ? Number(toValue) : from;
  const delta = Math.atan2(Math.sin(to - from), Math.cos(to - from));
  return from + delta * weight;
}

function getVrmPoseBlendWeight(progress) {
  const t = Math.max(0, Math.min(1, Number(progress) || 0));
  return t * t * (3 - 2 * t);
}

function applyBlendedVrmPoseSnapshot(fromSnapshot, toSnapshot, weight, runtime = vrmRuntime) {
  if (!fromSnapshot || !toSnapshot || !runtime) {
    return;
  }
  const amount = Math.max(0, Math.min(1, Number(weight) || 0));
  const snapshotKeys = new Set([
    ...Object.keys(fromSnapshot),
    ...Object.keys(toSnapshot)
  ]);
  for (const key of snapshotKeys) {
    const bone = getVrmPoseSnapshotBone(key, runtime);
    const fromPose = fromSnapshot[key];
    const toPose = toSnapshot[key];
    if (!bone || !fromPose || !toPose) {
      continue;
    }
    if (fromPose.rotation && toPose.rotation) {
      bone.rotation.set(
        lerpVrmPoseAngle(fromPose.rotation.x, toPose.rotation.x, amount),
        lerpVrmPoseAngle(fromPose.rotation.y, toPose.rotation.y, amount),
        lerpVrmPoseAngle(fromPose.rotation.z, toPose.rotation.z, amount)
      );
    }
    if (fromPose.position && toPose.position) {
      bone.position.set(
        lerpVrmPoseValue(fromPose.position.x, toPose.position.x, amount),
        lerpVrmPoseValue(fromPose.position.y, toPose.position.y, amount),
        lerpVrmPoseValue(fromPose.position.z, toPose.position.z, amount)
      );
    }
  }
}

function startVrmPoseBlendToAction(actionKey, fromSnapshot, durationMs) {
  if (!vrmRuntime || !fromSnapshot) {
    return;
  }
  vrmRuntime.poseBlend = {
    actionKey,
    fromSnapshot,
    startTime: performance.now(),
    durationMs: Math.max(80, Number(durationMs) || VRM_POSE_TO_ACTION_BLEND_MS)
  };
  vrmRuntime.restorePoseOnNextManualIdle = false;
  restoreVrmPoseSnapshot(fromSnapshot, vrmRuntime);
  resetVrmPhysicsState();
  smoothedVrmDelta = 1 / 60;
}

function updateVrmPoseBlend(now = performance.now()) {
  if (!vrmRuntime?.poseBlend) {
    return false;
  }
  const blend = vrmRuntime.poseBlend;
  const action = blend.actionKey ? vrmRuntime.actions?.[blend.actionKey] : null;
  if (!blend.fromSnapshot || !action?.isRunning?.()) {
    vrmRuntime.poseBlend = null;
    return false;
  }

  const targetSnapshot = createVrmPoseSnapshot(vrmRuntime);
  if (!targetSnapshot) {
    vrmRuntime.poseBlend = null;
    return false;
  }

  const progress = (now - blend.startTime) / blend.durationMs;
  const weight = getVrmPoseBlendWeight(progress);
  applyBlendedVrmPoseSnapshot(blend.fromSnapshot, targetSnapshot, weight, vrmRuntime);

  if (progress >= 1) {
    vrmRuntime.poseBlend = null;
    resetVrmPhysicsState();
    smoothedVrmDelta = 1 / 60;
  }
  return true;
}

function stopVrmAction(action, fadeOutSeconds = VRM_ACTION_FADE_OUT_SECONDS) {
  if (!action) {
    return;
  }
  try {
    if (vrmRuntime?.poseBlend?.actionKey === action.name) {
      vrmRuntime.poseBlend = null;
    }
    if (fadeOutSeconds > 0 && action.isRunning?.()) {
      action.fadeOut(fadeOutSeconds);
      window.setTimeout(() => {
        try {
          if (!action.isRunning?.() || action.getEffectiveWeight?.() < 0.02) {
            if (vrmRuntime) {
              vrmRuntime.restorePoseOnNextManualIdle = true;
            }
            action.stop();
          }
        } catch (_) {
          // ignore delayed stop failures
        }
      }, Math.ceil(fadeOutSeconds * 1000) + 80);
    } else {
      if (vrmRuntime) {
        vrmRuntime.restorePoseOnNextManualIdle = true;
      }
      action.stop();
    }
  } catch (_) {
    // ignore action stop failures
  }
}

function stopCompletedNonIdleVrmActions() {
  if (!vrmRuntime?.actions) {
    return false;
  }

  let stoppedAny = false;
  for (const [actionKey, action] of Object.entries(vrmRuntime.actions)) {
    if (actionKey === "idle" || !action || action.isRunning?.()) {
      continue;
    }

    const clipDuration = Number(action.getClip?.().duration);
    const isAtEnd = Number.isFinite(clipDuration) && clipDuration > 0
      ? Number(action.time) >= clipDuration - 0.02
      : Boolean(action.paused);
    const shouldStop = Boolean(
      action.clampWhenFinished &&
      action.enabled &&
      (action.paused || isAtEnd || vrmRuntime.activeActionKey === actionKey)
    );
    if (!shouldStop) {
      continue;
    }

    const finishedPose = createVrmPoseSnapshot(vrmRuntime);
    try {
      action.stop();
    } catch (_) {
      // ignore action cleanup failures
    }
    if (finishedPose) {
      restoreVrmPoseSnapshot(finishedPose, vrmRuntime);
      vrmRuntime.lastPoseSnapshot = finishedPose;
      vrmRuntime.restorePoseOnNextManualIdle = true;
    }
    if (vrmRuntime.activeActionKey === actionKey) {
      vrmRuntime.activeActionKey = "";
    }
    if (vrmRuntime.requestedActionKey === actionKey) {
      vrmRuntime.requestedActionKey = "";
    }
    stoppedAny = true;
  }

  if (stoppedAny) {
    vrmRuntime.poseBlend = null;
    resetVrmPhysicsState();
    smoothedVrmDelta = 1 / 60;
  }
  return stoppedAny;
}

function isSpeechPlaybackActive() {
  return Boolean(speechPreviewInProgress || analyserSpeechActive || Date.now() < speechActiveUntil);
}

function suspendVrmIdlePlaybackForSpeech(fadeOutSeconds = 0) {
  if (!vrmRuntime?.actions?.idle) {
    return;
  }
  if (vrmRuntime.idleReplayTimerId) {
    clearTimeout(vrmRuntime.idleReplayTimerId);
    vrmRuntime.idleReplayTimerId = 0;
  }
  const idleAction = vrmRuntime.actions.idle;
  if (idleAction?.isRunning?.()) {
    stopVrmAction(idleAction, fadeOutSeconds);
  }
  if (vrmRuntime.activeActionKey === "idle") {
    vrmRuntime.activeActionKey = "";
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

function getPrimaryRunningVrmActionKey() {
  if (!vrmRuntime?.actions) {
    return "";
  }
  const activeAction = vrmRuntime.activeActionKey
    ? vrmRuntime.actions[vrmRuntime.activeActionKey]
    : null;
  if (activeAction?.isRunning?.()) {
    return vrmRuntime.activeActionKey;
  }
  const runningEntry = Object.entries(vrmRuntime.actions).find(([, action]) => action?.isRunning?.());
  return runningEntry?.[0] || "";
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

  const canFadeFromRunningAction = fadeInSeconds > 0 && hasRunningVrmAction();
  const poseBlendFromSnapshot = canFadeFromRunningAction
    ? null
    : createVrmPoseSnapshot(vrmRuntime) || vrmRuntime.lastPoseSnapshot;
  const poseBlendDurationMs = actionKey === "idle"
    ? VRM_IDLE_POSE_TO_ACTION_BLEND_MS
    : VRM_POSE_TO_ACTION_BLEND_MS;

  try {
    action.enabled = true;
    action.paused = false;
    action.loop = loop;
    action.repetitions = repetitions;
    action.clampWhenFinished = actionKey !== "idle";
    action.reset();
    action.setEffectiveWeight(1);
    action.setEffectiveTimeScale(1);
    if (canFadeFromRunningAction) {
      vrmRuntime.poseBlend = null;
      action.fadeIn(fadeInSeconds);
    }
    action.play();
    if (!canFadeFromRunningAction) {
      vrmRuntime.mixer.update(0);
      startVrmPoseBlendToAction(actionKey, poseBlendFromSnapshot, poseBlendDurationMs);
    }
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
  if (isSpeechPlaybackActive()) {
    suspendVrmIdlePlaybackForSpeech();
    return;
  }
  const defaultDelayMs = vrmRuntime.idleHasPlayedOnce
    ? 2600 + Math.round(Math.random() * 3600)
    : 0;
  const delayMs = defaultDelayMs;
  vrmRuntime.idleReplayTimerId = window.setTimeout(() => {
    vrmRuntime.idleReplayTimerId = 0;
    if (!hasActiveNonIdleVrmAction() && !isSpeechPlaybackActive()) {
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

  if (isSpeechPlaybackActive()) {
    suspendVrmIdlePlaybackForSpeech();
    return;
  }

  stopCompletedNonIdleVrmActions();

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
    if (isSpeechPlaybackActive()) {
      suspendVrmIdlePlaybackForSpeech();
      return;
    }
    scheduleNextVrmIdlePlayback();
    return;
  }

  const actionKey = vrmRuntime.actions?.[requestedActionKey] ? requestedActionKey : "";
  if (!actionKey) {
    vrmRuntime.requestedActionKey = "";
    if (isSpeechPlaybackActive()) {
      suspendVrmIdlePlaybackForSpeech();
    } else {
      scheduleNextVrmIdlePlayback();
    }
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

function smoothEulerToward(euler, targets = {}, blend = VRM_MANUAL_IDLE_BLEND) {
  if (!euler) {
    return;
  }
  const amount = Math.max(0, Math.min(1, blend));
  for (const axis of ["x", "y", "z"]) {
    if (Number.isFinite(Number(targets[axis]))) {
      euler[axis] = lerpVrmPoseAngle(euler[axis], Number(targets[axis]), amount);
    }
  }
}

function smoothPositionToward(position, targets = {}, blend = VRM_MANUAL_IDLE_BLEND) {
  if (!position) {
    return;
  }
  const amount = Math.max(0, Math.min(1, blend));
  for (const axis of ["x", "y", "z"]) {
    if (Number.isFinite(Number(targets[axis]))) {
      position[axis] += (Number(targets[axis]) - position[axis]) * amount;
    }
  }
}

const VRM_STANDING_IDLE_BODY_BONES = [
  "hipsBone",
  "leftShoulder",
  "rightShoulder",
  "spineBone",
  "chestBone",
  "upperChestBone"
];

const VRM_STANDING_IDLE_LEG_BONES = [
  "leftUpperLeg",
  "rightUpperLeg",
  "leftLowerLeg",
  "rightLowerLeg",
  "leftFoot",
  "rightFoot"
];

function createOffsetPoseTargets(values = {}, offsets = {}) {
  const targets = {};
  for (const axis of ["x", "y", "z"]) {
    if (Number.isFinite(Number(values[axis]))) {
      const offset = Number.isFinite(Number(offsets[axis])) ? Number(offsets[axis]) : 0;
      targets[axis] = Number(values[axis]) + offset;
    }
  }
  return targets;
}

function smoothVrmBoneTowardPose(key, pose, blend, rotationOffsets = {}, positionOffsets = {}) {
  const bone = vrmRuntime?.[key];
  if (!bone || !pose) {
    return;
  }
  if (pose.rotation) {
    smoothEulerToward(bone.rotation, createOffsetPoseTargets(pose.rotation, rotationOffsets), blend);
  }
  if (pose.position) {
    smoothPositionToward(bone.position, createOffsetPoseTargets(pose.position, positionOffsets), blend);
  }
}

function smoothVrmSnapshotTowardPose(snapshot, blend, runtime = vrmRuntime) {
  if (!snapshot || !runtime) {
    return false;
  }
  for (const [key, pose] of Object.entries(snapshot)) {
    const bone = getVrmPoseSnapshotBone(key, runtime);
    if (!bone || !pose) {
      continue;
    }
    if (pose.rotation) {
      smoothEulerToward(bone.rotation, pose.rotation, blend);
    }
    if (pose.position) {
      smoothPositionToward(bone.position, pose.position, blend);
    }
  }
  return true;
}

function applyVrmIdleReferencePose() {
  return smoothVrmSnapshotTowardPose(
    vrmRuntime?.idleReferencePoseSnapshot,
    VRM_IDLE_REFERENCE_POSE_BLEND,
    vrmRuntime
  );
}

function applyRelaxedVrmIdleArmPose(elapsed, blend = VRM_MANUAL_IDLE_ARM_RELAX_BLEND) {
  if (!vrmRuntime) {
    return;
  }
  const sway = Math.sin(elapsed * 1.1) * 0.018;
  const inwardSway = Math.sin(elapsed * 0.7) * 0.012;
  const elbowSway = Math.sin(elapsed * 1.7) * 0.025;
  const armLowering = 1.52;
  const armInward = 0.055;
  const elbowBend = -0.24;
  const elbowForward = -0.18;

  smoothEulerToward(vrmRuntime.leftUpperArm?.rotation, {
    x: vrmRuntime.baseLeftUpperArmX,
    y: vrmRuntime.baseLeftArmY + armInward + inwardSway,
    z: vrmRuntime.baseLeftArmZ - armLowering + sway
  }, blend);
  smoothEulerToward(vrmRuntime.rightUpperArm?.rotation, {
    x: vrmRuntime.baseRightUpperArmX,
    y: vrmRuntime.baseRightArmY - armInward - inwardSway,
    z: vrmRuntime.baseRightArmZ + armLowering - sway
  }, blend);
  smoothEulerToward(vrmRuntime.leftLowerArm?.rotation, {
    x: vrmRuntime.baseLeftLowerArmX + elbowForward,
    y: vrmRuntime.baseLeftLowerArmY,
    z: vrmRuntime.baseLeftLowerArmZ + elbowBend + elbowSway
  }, blend);
  smoothEulerToward(vrmRuntime.rightLowerArm?.rotation, {
    x: vrmRuntime.baseRightLowerArmX + elbowForward,
    y: vrmRuntime.baseRightLowerArmY,
    z: vrmRuntime.baseRightLowerArmZ + elbowBend - elbowSway
  }, blend);
  smoothEulerToward(vrmRuntime.leftHand?.rotation, {
    x: vrmRuntime.baseLeftHandX + elbowForward * 0.18,
    y: vrmRuntime.baseLeftHandY + inwardSway * 0.35,
    z: vrmRuntime.baseLeftHandZ
  }, blend);
  smoothEulerToward(vrmRuntime.rightHand?.rotation, {
    x: vrmRuntime.baseRightHandX + elbowForward * 0.18,
    y: vrmRuntime.baseRightHandY - inwardSway * 0.35,
    z: vrmRuntime.baseRightHandZ
  }, blend);
}

function getRelaxedVrmFingerCurlOffsets(boneName) {
  const isThumb = boneName.includes("Thumb");
  const isMetacarpal = boneName.includes("Metacarpal");
  const isProximal = boneName.includes("Proximal");
  const isIntermediate = boneName.includes("Intermediate");
  const isDistal = boneName.includes("Distal");
  const isRingOrLittle = boneName.includes("Ring") || boneName.includes("Little");
  const sideSign = boneName.startsWith("left") ? 1 : -1;

  if (isThumb) {
    if (isMetacarpal) {
      return { x: 0.2, y: sideSign * 0.28, z: sideSign * 0.2 };
    }
    if (isProximal) {
      return { x: 0.34, y: sideSign * 0.16, z: sideSign * 0.26 };
    }
    if (isDistal) {
      return { x: 0.28, y: 0, z: sideSign * 0.16 };
    }
  }

  if (isProximal) {
    return { x: isRingOrLittle ? 0.58 : 0.5, y: sideSign * 0.035, z: sideSign * (isRingOrLittle ? 0.18 : 0.13) };
  }
  if (isIntermediate) {
    return { x: isRingOrLittle ? 0.72 : 0.62, y: 0, z: sideSign * 0.08 };
  }
  if (isDistal) {
    return { x: isRingOrLittle ? 0.48 : 0.4, y: 0, z: sideSign * 0.05 };
  }
  return { x: 0, y: 0, z: 0 };
}

function applyRelaxedVrmFingerCurlPose(blend = VRM_MANUAL_IDLE_FINGER_CURL_BLEND) {
  if (!vrmRuntime?.fingerBones || !vrmRuntime.baseFingerRotations) {
    return;
  }
  for (const boneName of VRM_FINGER_BONE_NAMES) {
    const bone = vrmRuntime.fingerBones[boneName];
    const base = vrmRuntime.baseFingerRotations[boneName];
    if (!bone || !base) {
      continue;
    }
    const offsets = getRelaxedVrmFingerCurlOffsets(boneName);
    smoothEulerToward(bone.rotation, {
      x: base.x + offsets.x,
      y: base.y + offsets.y,
      z: base.z + offsets.z
    }, blend);
  }
}

function applyRelaxedVrmIdleLegPose(elapsed, blend = VRM_MANUAL_IDLE_LEG_STANCE_BLEND) {
  if (!vrmRuntime) {
    return;
  }
  const stanceSway = Math.sin(elapsed * 0.8) * 0.006;
  const legSpread = 0.075;
  const hipSettle = 0.02;
  const kneeBend = 0.095;
  const footBalance = 0.032;

  smoothEulerToward(vrmRuntime.leftUpperLeg?.rotation, {
    x: vrmRuntime.baseLeftUpperLegX + hipSettle,
    y: vrmRuntime.baseLeftUpperLegY,
    z: vrmRuntime.baseLeftUpperLegZ + legSpread + stanceSway
  }, blend);
  smoothEulerToward(vrmRuntime.rightUpperLeg?.rotation, {
    x: vrmRuntime.baseRightUpperLegX + hipSettle,
    y: vrmRuntime.baseRightUpperLegY,
    z: vrmRuntime.baseRightUpperLegZ - legSpread - stanceSway
  }, blend);
  smoothEulerToward(vrmRuntime.leftLowerLeg?.rotation, {
    x: vrmRuntime.baseLeftLowerLegX + kneeBend,
    y: vrmRuntime.baseLeftLowerLegY,
    z: vrmRuntime.baseLeftLowerLegZ - stanceSway * 0.5
  }, blend);
  smoothEulerToward(vrmRuntime.rightLowerLeg?.rotation, {
    x: vrmRuntime.baseRightLowerLegX + kneeBend,
    y: vrmRuntime.baseRightLowerLegY,
    z: vrmRuntime.baseRightLowerLegZ + stanceSway * 0.5
  }, blend);
  smoothEulerToward(vrmRuntime.leftFoot?.rotation, {
    x: vrmRuntime.baseLeftFootX - footBalance,
    y: vrmRuntime.baseLeftFootY,
    z: vrmRuntime.baseLeftFootZ + legSpread * 0.25
  }, blend);
  smoothEulerToward(vrmRuntime.rightFoot?.rotation, {
    x: vrmRuntime.baseRightFootX - footBalance,
    y: vrmRuntime.baseRightFootY,
    z: vrmRuntime.baseRightFootZ - legSpread * 0.25
  }, blend);
}

function applyNaturalVrmIdleMotion(elapsed, blend = VRM_MANUAL_IDLE_MOTION_BLEND) {
  if (!vrmRuntime?.baseStandingPoseSnapshot) {
    return;
  }
  const basePose = vrmRuntime.baseStandingPoseSnapshot;
  const breathe = Math.sin(elapsed * 1.55);
  const slowShift = Math.sin(elapsed * 0.48);
  const smallShift = Math.sin(elapsed * 0.9 + 1.2);
  const shoulderCounter = Math.sin(elapsed * 0.62 + 0.8);

  smoothVrmBoneTowardPose("hipsBone", basePose.hipsBone, blend, {
    x: 0.012 + breathe * 0.01,
    y: slowShift * 0.018,
    z: slowShift * 0.025
  }, {
    x: slowShift * 0.012,
    y: -0.01 + Math.max(0, -breathe) * -0.004
  });
  smoothVrmBoneTowardPose("spineBone", basePose.spineBone, blend, {
    x: -0.014 + breathe * 0.012,
    y: slowShift * -0.013,
    z: slowShift * -0.018
  }, {
    y: breathe * 0.008
  });
  smoothVrmBoneTowardPose("chestBone", basePose.chestBone, blend, {
    x: breathe * 0.018,
    y: shoulderCounter * 0.01,
    z: slowShift * -0.014
  });
  smoothVrmBoneTowardPose("upperChestBone", basePose.upperChestBone, blend, {
    x: breathe * 0.012,
    y: shoulderCounter * 0.012,
    z: slowShift * -0.012
  });
  smoothVrmBoneTowardPose("leftShoulder", basePose.leftShoulder, blend, {
    x: breathe * 0.01,
    y: smallShift * 0.008,
    z: -0.018 + shoulderCounter * 0.012
  });
  smoothVrmBoneTowardPose("rightShoulder", basePose.rightShoulder, blend, {
    x: breathe * 0.01,
    y: -smallShift * 0.008,
    z: 0.018 - shoulderCounter * 0.012
  });
}

function stabilizeVrmStandingIdlePose() {
  const basePose = vrmRuntime?.baseStandingPoseSnapshot;
  if (!basePose) {
    return;
  }
  for (const key of VRM_STANDING_IDLE_BODY_BONES) {
    smoothVrmBoneTowardPose(key, basePose[key], VRM_MANUAL_IDLE_BODY_BLEND);
  }
  for (const key of VRM_STANDING_IDLE_LEG_BONES) {
    smoothVrmBoneTowardPose(key, basePose[key], VRM_MANUAL_IDLE_LEG_BLEND);
  }
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
    spineBone,
    neckBone,
    headBone,
    baseSpineY,
    baseNeckX,
    baseNeckY,
    baseHeadX,
    baseHeadY
  } = vrmRuntime;

  const breathe = Math.sin(elapsed * 2) * 0.01;
  const usingIdleReferencePose = applyVrmIdleReferencePose();

  if (!usingIdleReferencePose) {
    stabilizeVrmStandingIdlePose();
    applyNaturalVrmIdleMotion(elapsed);
    applyRelaxedVrmIdleLegPose(elapsed);
    applyRelaxedVrmIdleArmPose(elapsed);
    applyRelaxedVrmFingerCurlPose();
    smoothPositionToward(spineBone?.position, {
      y: baseSpineY + breathe
    });
  }

  if (lookTarget && (neckBone || headBone)) {
    const camInv = new THREE.Matrix4().copy(camera.matrixWorld).invert();
    const targetInCameraSpace = new THREE.Vector3().copy(lookTarget.position).applyMatrix4(camInv);
    const yaw = Math.atan2(targetInCameraSpace.x, targetInCameraSpace.z);
    const pitch = Math.atan2(-targetInCameraSpace.y, targetInCameraSpace.z);
    const clampedYaw = Math.max(-0.35, Math.min(0.35, yaw));
    const clampedPitch = Math.max(-0.25, Math.min(0.25, pitch));
    const referencePose = usingIdleReferencePose ? vrmRuntime.idleReferencePoseSnapshot : null;
    const neckBaseX = referencePose?.neckBone?.rotation?.x ?? baseNeckX;
    const neckBaseY = referencePose?.neckBone?.rotation?.y ?? baseNeckY;
    const headBaseX = referencePose?.headBone?.rotation?.x ?? baseHeadX;
    const headBaseY = referencePose?.headBone?.rotation?.y ?? baseHeadY;
    smoothEulerToward(neckBone?.rotation, {
      x: neckBaseX + clampedPitch * 0.4,
      y: neckBaseY + clampedYaw * 0.4
    }, VRM_MANUAL_IDLE_HEAD_BLEND);
    smoothEulerToward(headBone?.rotation, {
      x: headBaseX + clampedPitch * 0.6,
      y: headBaseY + clampedYaw * 0.6
    }, VRM_MANUAL_IDLE_HEAD_BLEND);
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

function clampOverlayCoordinate(value, minValue, maxValue) {
  const min = Math.min(minValue, maxValue);
  const max = Math.max(minValue, maxValue);
  return Math.max(min, Math.min(max, value));
}

function getProjectedAvatarOverlayPoint(state = currentState) {
  const width = Math.max(window.innerWidth || 1, 1);
  const height = Math.max(window.innerHeight || 1, 1);
  const maxOverlayWidth = Math.min(320, Math.max(0, width - 36));
  const edgeInset = Math.max(18, Math.min(18 + maxOverlayWidth / 2, width / 2));
  const maxHudWidth = Math.min(420, Math.max(0, width - 16));
  const hudEdgeInset = Math.max(8, Math.min(8 + maxHudWidth / 2, width / 2));
  let projectedX = width / 2;
  let projectedY = height / 2;

  if (state?.mode === "vrm" && camera) {
    try {
      const transform = getCurrentVrmTransform(state);
      camera.updateMatrixWorld?.();
      const projected = new THREE.Vector3(transform.positionX, transform.positionY, 0).project(camera);
      const screenX = (projected.x * 0.5 + 0.5) * width;
      const screenY = (-projected.y * 0.5 + 0.5) * height;
      if (Number.isFinite(screenX)) {
        projectedX = screenX;
      }
      if (Number.isFinite(screenY)) {
        projectedY = screenY;
      }
    } catch (_) {
      projectedX = width / 2;
      projectedY = height / 2;
    }
  } else if (state?.mode === "live2d" && live2dModel) {
    const live2dX = Number(live2dModel.x);
    const live2dY = Number(live2dModel.y);
    if (Number.isFinite(live2dX)) {
      projectedX = live2dX;
    }
    if (Number.isFinite(live2dY)) {
      projectedY = live2dY;
    }
  }

  return {
    x: clampOverlayCoordinate(projectedX, edgeInset, width - edgeInset),
    hudX: clampOverlayCoordinate(projectedX, hudEdgeInset, width - hudEdgeInset),
    y: clampOverlayCoordinate(projectedY, 0, height)
  };
}

function syncAvatarOverlayPosition(state = currentState) {
  const height = Math.max(window.innerHeight || 1, 1);
  const overlayPoint = getProjectedAvatarOverlayPoint(state);
  const safeTop = 14;
  const voiceTop = clampOverlayCoordinate(
    overlayPoint.y - Math.min(118, height * 0.22),
    safeTop,
    Math.max(safeTop, height - 72)
  );
  const speechMinBottom = state?.quickHudVisible ? Math.min(188, height * 0.42) : 28;
  const speechBottom = clampOverlayCoordinate(
    height - (overlayPoint.y + Math.min(240, height * 0.38)),
    speechMinBottom,
    Math.max(speechMinBottom, height - 96)
  );

  document.body.style.setProperty("--avatar-overlay-x", `${Math.round(overlayPoint.x)}px`);
  document.body.style.setProperty("--avatar-hud-x", `${Math.round(overlayPoint.hudX)}px`);
  document.body.style.setProperty("--avatar-voice-top", `${Math.round(voiceTop)}px`);
  document.body.style.setProperty("--avatar-speech-bottom", `${Math.round(speechBottom)}px`);
}

function applyVrmTransform(state = currentState) {
  if (!vrmModel?.scene) {
    syncAvatarOverlayPosition(state);
    return;
  }
  const transform = getCurrentVrmTransform(state);
  vrmModel.scene.scale.setScalar(transform.scale);
  vrmModel.scene.position.set(transform.positionX, transform.positionY, 0);
  vrmModel.scene.rotation.y = (transform.rotation * Math.PI) / 180;
  syncAvatarOverlayPosition(state);
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
        "ih",
        "ou",
        "ee",
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
      ["Joy", "Relaxed", "Angry", "Sad", "Surprised", "Blink", "Blink_L", "Blink_R", "A", "I", "U", "E", "O"].forEach((key) => {
        try {
          vrmModel.blendShapeProxy.setValue(key, 0);
        } catch (_) {
          // ignore unsupported blend shapes
        }
      });
      vrmModel.blendShapeProxy.update?.();
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

  try {
    vrmModel.expressionManager?.update?.();
  } catch (_) {
    // ignore expression update failures
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
        vrmModel.expressionManager.update?.();
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

function forceNeutralVrmFaceForSpeech(state = currentState) {
  if (state?.mode !== "vrm" || !vrmModel) {
    return;
  }
  if (currentState.expression !== "neutral") {
    currentState = { ...currentState, expression: "neutral", transientExpression: false };
  }
  applyVrmExpression("neutral");
  syncVrmAnimationState({ ...currentState, expression: "neutral" });
  applyMouthValue(0);
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
  syncAvatarOverlayPosition(currentState);
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
  syncAvatarOverlayPosition(state);

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

function cancelSpeechPreviewStream() {
  const cancel = speechPreviewStreamCancel;
  speechPreviewStreamCancel = null;
  if (typeof cancel === "function") {
    try {
      cancel();
    } catch (_) {
      // ignore cancellation errors
    }
  }
}

function stopSpeechPreviewPcmSources() {
  speechPreviewPcmStreamActive = false;
  speechPreviewPcmActiveSources = 0;
  speechPreviewPcmNextPlayTime = 0;
  const cleanupFns = speechPreviewPcmCleanupFns;
  speechPreviewPcmCleanupFns = [];
  for (const cleanup of cleanupFns) {
    try {
      cleanup();
    } catch (_) {
      // ignore source cleanup errors
    }
  }
}

async function ensureSpeechPreviewAnalyserGraph() {
  const ctx = await ensureAudioContext();
  if (!speechPreviewAnalyserNode || speechPreviewAnalyserNode.context !== ctx) {
    try {
      speechPreviewAnalyserNode?.disconnect();
    } catch (_) {
      // ignore stale analyser cleanup
    }
    try {
      speechPreviewGainNode?.disconnect();
    } catch (_) {
      // ignore stale gain cleanup
    }
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.55;
    const gain = ctx.createGain();
    gain.gain.value = 1.0;
    analyser.connect(gain);
    gain.connect(ctx.destination);
    speechPreviewAnalyserNode = analyser;
    speechPreviewGainNode = gain;
  }
  analyserSpeechActive = true;
  return ctx;
}

function startLipSyncFromSpeechPreviewAnalyser(previewToken) {
  if (!speechPreviewAnalyserNode || speechPreviewRafId) {
    return;
  }

  const buffer = new Uint8Array(speechPreviewAnalyserNode.fftSize);
  let smoothed = 0;
  const attack = 0.6;
  const release = 0.15;

  const step = () => {
    if (previewToken !== speechGeneration) {
      speechPreviewRafId = 0;
      return;
    }
    if (!speechPreviewAnalyserNode || (!speechPreviewPcmStreamActive && speechPreviewPcmActiveSources <= 0)) {
      speechPreviewRafId = 0;
      disconnectSpeechGraph();
      applyMouthValue(0);
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
    speechPreviewRafId = requestAnimationFrame(step);
  };

  speechPreviewRafId = requestAnimationFrame(step);
}

function parseSpeechPreviewAudioContentTypeParams(contentType) {
  const params = {};
  for (const part of String(contentType || "").split(";").slice(1)) {
    const index = part.indexOf("=");
    if (index < 0) {
      continue;
    }
    const key = part.slice(0, index).trim().toLowerCase();
    const value = part.slice(index + 1).trim().replace(/^"|"$/g, "");
    if (key) {
      params[key] = value;
    }
  }
  return params;
}

function normalizeSpeechPreviewPcmFormat(format = {}) {
  const params = parseSpeechPreviewAudioContentTypeParams(format.contentType);
  const rawEncoding = String(
    format.pcmEncoding ||
    format.encoding ||
    params.encoding ||
    params.format ||
    ""
  ).trim().toLowerCase().replace(/[_\s]/g, "-");
  const rawBits = Number(format.bitsPerSample || format.bits || params.bits || params.bit_depth || params.bitdepth);
  const bitsPerSample = Number.isFinite(rawBits) && rawBits > 0
    ? Math.round(rawBits)
    : rawEncoding.includes("float")
      ? 32
      : 16;
  const encoding = rawEncoding.includes("float") || bitsPerSample === 32
    ? "float32"
    : "s16le";
  const normalizedBitsPerSample = encoding === "float32" ? 32 : 16;
  return {
    encoding,
    bitsPerSample: normalizedBitsPerSample,
    bytesPerSample: encoding === "float32" ? 4 : 2
  };
}

function getSpeechPreviewPcmFrameBytes(pcmFormat, channels) {
  const format = normalizeSpeechPreviewPcmFormat(pcmFormat);
  return Math.max(format.bytesPerSample, Math.max(1, Number(channels) || 1) * format.bytesPerSample);
}

function logSpeechPreviewPcm(level, label, payload) {
  const message = `[tts pcm] ${label} ${JSON.stringify(payload)}`;
  if (level === "warn") {
    console.warn(message);
    return;
  }
  console.debug(message);
}

function playPcmSpeechPreviewBytes(bytes, sampleRate, channels, previewToken, pcmFormat = {}) {
  if (previewToken !== speechGeneration || !speechPreviewAnalyserNode || !audioContext) {
    return 0;
  }
  const input = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || new ArrayBuffer(0));
  const safeChannels = Math.max(1, Number(channels) || 1);
  const format = normalizeSpeechPreviewPcmFormat(pcmFormat);
  const safeSampleRate = format.encoding === "float32"
    ? 24000
    : Math.max(8000, Number(sampleRate) || 24000);
  const frameBytes = safeChannels * format.bytesPerSample;
  const alignedLength = input.byteLength - (input.byteLength % frameBytes);
  if (alignedLength <= 0) {
    return input.byteLength;
  }

  const alignment = format.bytesPerSample;
  const alignedBytes = input.byteOffset % alignment === 0 && alignedLength === input.byteLength
    ? input
    : input.slice(0, alignedLength);
  const sampleCount = Math.floor(alignedLength / format.bytesPerSample);
  const framesPerChannel = Math.floor(sampleCount / safeChannels);
  if (!framesPerChannel) {
    return alignedLength;
  }

  const audioBuffer = audioContext.createBuffer(safeChannels, framesPerChannel, safeSampleRate);
  if (format.encoding === "float32") {
    const samples = new Float32Array(
      alignedBytes.buffer,
      alignedBytes.byteOffset,
      sampleCount
    );
    for (let channel = 0; channel < safeChannels; channel += 1) {
      const channelSamples = new Float32Array(framesPerChannel);
      for (let frame = 0; frame < framesPerChannel; frame += 1) {
        const sample = Number(samples[(frame * safeChannels) + channel]) || 0;
        channelSamples[frame] = Math.max(-1, Math.min(1, sample));
      }
      audioBuffer.copyToChannel(channelSamples, channel);
    }
  } else {
    const int16 = new Int16Array(
      alignedBytes.buffer,
      alignedBytes.byteOffset,
      sampleCount
    );
    for (let channel = 0; channel < safeChannels; channel += 1) {
      const channelSamples = new Float32Array(framesPerChannel);
      for (let frame = 0; frame < framesPerChannel; frame += 1) {
        channelSamples[frame] = int16[(frame * safeChannels) + channel] / 32768;
      }
      audioBuffer.copyToChannel(channelSamples, channel);
    }
  }

  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(speechPreviewAnalyserNode);
  const currentTime = audioContext.currentTime;
  const queuedUntil = Number(speechPreviewPcmNextPlayTime) || 0;
  const queueAhead = queuedUntil > 0 ? queuedUntil - currentTime : 0;
  if (queueAhead <= SPEECH_PREVIEW_PCM_UNDERRUN_WARN_SECONDS) {
    logSpeechPreviewPcm("warn", "queue underrun risk", {
      bytes: alignedLength,
      encoding: format.encoding,
      bits: format.bitsPerSample,
      rate: safeSampleRate,
      samples: sampleCount,
      duration: audioBuffer.duration,
      currentTime,
      "audioContext.currentTime": currentTime,
      nextPlayTime: queuedUntil,
      queueAhead
    });
  }
  if (!speechPreviewPcmNextPlayTime || speechPreviewPcmNextPlayTime <= currentTime) {
    speechPreviewPcmNextPlayTime = currentTime + SPEECH_PREVIEW_PCM_SCHEDULE_LEAD_SECONDS;
  }
  const startAt = speechPreviewPcmNextPlayTime;
  speechPreviewPcmNextPlayTime = startAt + audioBuffer.duration;
  logSpeechPreviewPcm("debug", "scheduled chunk", {
    bytes: alignedLength,
    encoding: format.encoding,
    bits: format.bitsPerSample,
    rate: safeSampleRate,
    samples: sampleCount,
    duration: audioBuffer.duration,
    currentTime,
    "audioContext.currentTime": currentTime,
    nextPlayTime: startAt,
    queueAhead,
    queueAheadAfter: speechPreviewPcmNextPlayTime - currentTime
  });
  speechPreviewPcmActiveSources += 1;
  speechActiveUntil = Math.max(speechActiveUntil, Date.now() + Math.ceil((speechPreviewPcmNextPlayTime - audioContext.currentTime) * 1000));

  const onEnded = () => {
    try {
      source.removeEventListener("ended", onEnded);
    } catch (_) {
      // ignore listener cleanup
    }
    speechPreviewPcmActiveSources = Math.max(0, speechPreviewPcmActiveSources - 1);
  };
  source.addEventListener("ended", onEnded, { once: true });
  speechPreviewPcmCleanupFns.push(() => {
    try {
      source.removeEventListener("ended", onEnded);
    } catch (_) {
      // ignore listener cleanup
    }
    try {
      source.stop(0);
    } catch (_) {
      // source may already be stopped
    }
    try {
      source.disconnect();
    } catch (_) {
      // ignore disconnect errors
    }
  });
  source.start(startAt);
  return alignedLength;
}

function waitForSpeechPreviewPcmPlaybackComplete(previewToken, timeoutMs = 20000) {
  const startedAt = performance.now();
  return new Promise((resolve) => {
    const check = () => {
      if (previewToken !== speechGeneration) {
        resolve(false);
        return;
      }
      if (!speechPreviewPcmStreamActive && speechPreviewPcmActiveSources <= 0) {
        resolve(true);
        return;
      }
      if (performance.now() - startedAt > timeoutMs) {
        resolve(false);
        return;
      }
      requestAnimationFrame(check);
    };
    check();
  });
}

function disconnectSpeechGraph() {
  cancelSpeechPreviewStream();
  stopSpeechPreviewPcmSources();
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

function finishSpeechPreviewPlayback() {
  speechPreviewInProgress = false;
  if (!isSpeechPlaybackActive()) {
    scheduleNextVrmIdlePlayback();
  }
}

function clearSpeechExpressionResetTimer() {
  if (speechExpressionResetTimeout) {
    clearTimeout(speechExpressionResetTimeout);
    speechExpressionResetTimeout = 0;
  }
}

async function resetTransientSpeechExpression(previewToken) {
  if (previewToken !== speechGeneration) {
    return;
  }
  if (!currentState.transientExpression || !activeSpeechExpressionTriggerId) {
    return;
  }
  if (Number(currentState.speechTriggerId) !== Number(activeSpeechExpressionTriggerId)) {
    return;
  }
  if (String(currentState.expression || "neutral").toLowerCase() === "neutral") {
    return;
  }

  try {
    const nextState = await window.catbotDesktop.setState({
      expression: "neutral",
      transientExpression: false
    });
    if (previewToken === speechGeneration) {
      currentState = nextState;
      applyStateToScene(currentState);
      renderHudState(currentState);
    }
  } catch (error) {
    console.warn("Could not reset avatar expression after speech:", error);
  }
}

function scheduleSpeechExpressionReset(delayMs, previewToken) {
  clearSpeechExpressionResetTimer();
  speechExpressionResetTimeout = window.setTimeout(() => {
    speechExpressionResetTimeout = 0;
    void resetTransientSpeechExpression(previewToken);
  }, Math.max(0, Number(delayMs) || 0));
}

function releaseSpeechPreviewAudioObject(options = {}) {
  if (speechPreviewAudio && options.pause !== false) {
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
}

function stopSpeechPreview(options = {}) {
  const { preserveBubble = false } = options;
  speechPreviewInProgress = false;
  speechActiveUntil = 0;
  clearSpeechBubbleSequence();
  clearSpeechExpressionResetTimer();
  disconnectSpeechGraph();
  releaseSpeechPreviewAudioObject();
  applyMouthValue(0);

  if (!preserveBubble) {
    hideSpeechBubble({ immediate: true });
  }
}

function startLipSyncFromAudioElement(audioEl, previewToken, options = {}) {
  const ctx = audioContext;
  if (!ctx) {
    throw new Error("Audio context is not available.");
  }
  const finalizePlayback = options.finalize !== false;

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

  return new Promise((resolve) => {
    let finished = false;
    const finish = () => {
      if (finished) {
        return;
      }
      finished = true;
      if (previewToken !== speechGeneration) {
        resolve(false);
        return;
      }
      disconnectSpeechGraph();
      applyMouthValue(0);
      if (finalizePlayback) {
        hideSpeechBubble();
        setReadyStatus();
        finishSpeechPreviewPlayback();
        void resetTransientSpeechExpression(previewToken);
      }
      resolve(true);
    };

    const step = () => {
      if (previewToken !== speechGeneration) {
        finished = true;
        speechPreviewRafId = 0;
        resolve(false);
        return;
      }
      if (!speechPreviewAnalyserNode) {
        finish();
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
    audioEl.addEventListener("error", finish, { once: true });
    audioEl.addEventListener("pause", () => {
      if (!audioEl.ended && speechPreviewAudio === audioEl) {
        finish();
      }
    }, { once: true });

    speechPreviewRafId = requestAnimationFrame(step);
  });
}

async function playBufferedSpeechResult(speechResult, chunkText, fullText, fallbackDurationMs, previewToken, state) {
  const audioBytes = arrayBufferFromIpcBinary(speechResult?.audioBuffer);
  if (!audioBytes || audioBytes.byteLength === 0) {
    throw new Error("Speech preview returned no audio data.");
  }

  const blob = new Blob([audioBytes], {
    type: speechResult?.contentType || "audio/mpeg"
  });
  const objectUrl = URL.createObjectURL(blob);
  const audio = new Audio(objectUrl);
  audio.preload = "auto";

  speechPreviewAudio = audio;
  speechPreviewObjectUrl = objectUrl;

  await ensureAudioContext();
  const audioDurationMs = await resolveAudioDurationMs(audio, fallbackDurationMs);
  if (previewToken !== speechGeneration) {
    return false;
  }
  const lipSyncFinished = startLipSyncFromAudioElement(audio, previewToken, { finalize: false });
  await audio.play();
  if (previewToken !== speechGeneration) {
    return false;
  }
  speechActiveUntil = Date.now() + audioDurationMs;
  forceNeutralVrmFaceForSpeech(state);
  scheduleSpeechBubbleSentences(chunkText, audioDurationMs, previewToken);

  const completed = await lipSyncFinished;
  releaseSpeechPreviewAudioObject({ pause: false });
  return Boolean(completed && previewToken === speechGeneration);
}

async function streamSpeechPreviewChunkToPcmQueue(chunkText, fallbackDurationMs, previewToken, state, statusText = "Streaming speech...") {
  if (typeof window.catbotDesktop.synthesizePreviewSpeechStream !== "function") {
    return { streamed: false };
  }

  let sampleRate = 24000;
  let channels = 1;
  let pcmFormat = normalizeSpeechPreviewPcmFormat({ encoding: "s16le", bitsPerSample: 16 });
  let carry = new Uint8Array(0);
  let streamedBytes = 0;
  const frameBytes = () => getSpeechPreviewPcmFrameBytes(pcmFormat, channels);
  const flushCarry = () => {
    if (carry.byteLength <= 0 || previewToken !== speechGeneration) {
      return;
    }
    const padded = new Uint8Array(carry.byteLength + (frameBytes() - (carry.byteLength % frameBytes())) % frameBytes());
    padded.set(carry);
    streamedBytes += playPcmSpeechPreviewBytes(padded, sampleRate, channels, previewToken, pcmFormat);
    carry = new Uint8Array(0);
  };
  const flushPcmBytes = (value) => {
    if (previewToken !== speechGeneration) {
      return;
    }
    const audioBuffer = arrayBufferFromIpcBinary(value?.audioBuffer);
    if (!audioBuffer) {
      return;
    }
    const incoming = new Uint8Array(audioBuffer);
    if (!incoming.byteLength) {
      return;
    }
    const joined = new Uint8Array(carry.byteLength + incoming.byteLength);
    joined.set(carry, 0);
    joined.set(incoming, carry.byteLength);
    const alignedLength = joined.byteLength - (joined.byteLength % frameBytes());
    if (alignedLength > 0) {
      const playedLength = playPcmSpeechPreviewBytes(joined.subarray(0, alignedLength), sampleRate, channels, previewToken, pcmFormat);
      streamedBytes += playedLength;
    }
    carry = joined.slice(alignedLength);
  };

  const stream = window.catbotDesktop.synthesizePreviewSpeechStream({
    text: chunkText,
    proxyBaseUrl: state.proxyBaseUrl,
    webClientUrl: state.webClientUrl,
    ttsEndpoint: state.ttsEndpoint,
    ttsModel: state.ttsModel,
    ttsVoice: state.ttsVoice
  }, {
    onStarted: (data) => {
      sampleRate = Math.max(8000, Number(data?.sampleRate) || sampleRate);
      channels = Math.max(1, Number(data?.channels) || channels);
      pcmFormat = normalizeSpeechPreviewPcmFormat({
        contentType: data?.contentType,
        pcmEncoding: data?.pcmEncoding,
        bitsPerSample: data?.bitsPerSample || data?.bits,
        bytesPerSample: data?.bytesPerSample
      });
      forceNeutralVrmFaceForSpeech(state);
      scheduleSpeechBubbleSentences(chunkText, fallbackDurationMs, previewToken);
      setStatus(statusText);
    },
    onChunk: flushPcmBytes,
    onDone: flushCarry
  });
  const cancelStream = stream.cancel;
  speechPreviewStreamCancel = cancelStream;

  try {
    const result = await stream.promise;
    if (speechPreviewStreamCancel === cancelStream) {
      speechPreviewStreamCancel = null;
    }
    if (previewToken !== speechGeneration) {
      return { streamed: false, completed: false };
    }
    flushCarry();
    if (result?.skipped) {
      return result;
    }
    if (result?.streamed) {
      return { streamed: true, completed: streamedBytes > 0, streamedBytes };
    }
    if (result?.audioBuffer) {
      return { streamed: false, completed: false, audioBuffer: result.audioBuffer, contentType: result.contentType };
    }
    return { streamed: false, completed: false };
  } catch (error) {
    if (speechPreviewStreamCancel === cancelStream) {
      speechPreviewStreamCancel = null;
    }
    throw error;
  }
}

async function playStreamingSpeechPreviewChunks(streamingChunks, fullText, fallbackDurationMs, previewToken, state) {
  if (typeof window.catbotDesktop.synthesizePreviewSpeechStream !== "function") {
    return { streamed: false };
  }

  const chunks = Array.isArray(streamingChunks)
    ? streamingChunks.map((chunk) => String(chunk || "").trim()).filter(Boolean)
    : [];
  if (!chunks.length) {
    return { streamed: false, completed: false };
  }

  const ctx = await ensureSpeechPreviewAnalyserGraph();
  speechPreviewPcmStreamActive = true;
  speechPreviewPcmActiveSources = 0;
  speechPreviewPcmNextPlayTime = ctx.currentTime + SPEECH_PREVIEW_PCM_INITIAL_BUFFER_SECONDS;
  startLipSyncFromSpeechPreviewAnalyser(previewToken);

  let streamedBytes = 0;
  let skippedOnly = true;
  try {
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex += 1) {
      const chunkText = chunks[chunkIndex];
      const chunkFallbackDurationMs = estimateSpeechSegmentDurationMs(chunkText, fullText, fallbackDurationMs);
      if (previewToken !== speechGeneration) {
        speechPreviewPcmStreamActive = false;
        return { streamed: false, completed: false };
      }
      const statusText = chunks.length > 1
        ? `Prebuffering speech ${chunkIndex + 1}/${chunks.length}...`
        : "Prebuffering speech...";
      const result = await streamSpeechPreviewChunkToPcmQueue(chunkText, chunkFallbackDurationMs, previewToken, state, statusText);
      if (previewToken !== speechGeneration) {
        speechPreviewPcmStreamActive = false;
        return { streamed: false, completed: false };
      }
      if (result?.skipped) {
        const skippedDurationMs = Math.min(chunkFallbackDurationMs, 1800);
        scheduleSpeechBubbleSentences(chunkText, skippedDurationMs, previewToken);
        speechActiveUntil = Date.now() + skippedDurationMs;
        await new Promise((resolve) => window.setTimeout(resolve, Math.min(skippedDurationMs, 700)));
        continue;
      }
      if (result?.audioBuffer) {
        if (streamedBytes > 0) {
          throw new Error("Speech preview stream changed audio mode after PCM playback started.");
        }
        speechPreviewPcmStreamActive = false;
        disconnectSpeechGraph();
        const completed = await playBufferedSpeechResult(result, chunkText, fullText, chunkFallbackDurationMs, previewToken, state);
        return { streamed: false, completed };
      }
      if (!result?.completed) {
        throw new Error("Speech preview stream did not return audio.");
      }
      streamedBytes += Math.max(0, Number(result.streamedBytes) || 0);
      skippedOnly = false;
    }

    speechPreviewPcmStreamActive = false;
    const queuedPlaybackMs = audioContext
      ? Math.max(0, (speechPreviewPcmNextPlayTime - audioContext.currentTime) * 1000)
      : 0;
    const completed = streamedBytes > 0
      ? await waitForSpeechPreviewPcmPlaybackComplete(previewToken, Math.max(3000, fallbackDurationMs + 5000, queuedPlaybackMs + 5000))
      : false;
    if (completed) {
      hideSpeechBubble();
    }
    return {
      streamed: true,
      completed,
      skipped: skippedOnly && streamedBytes <= 0
    };
  } catch (error) {
    speechPreviewPcmStreamActive = false;
    throw error;
  }
}

async function playStreamingSpeechPreviewChunk(chunkText, fullText, fallbackDurationMs, previewToken, state) {
  return playStreamingSpeechPreviewChunks([chunkText], fullText, fallbackDurationMs, previewToken, state);
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
  activeSpeechExpressionTriggerId = Number(state.speechTriggerId) || 0;
  stopSpeechPreview();
  speechPreviewInProgress = true;
  suspendVrmIdlePlaybackForSpeech();
  forceNeutralVrmFaceForSpeech(state);
  const utteranceChunks = splitTtsUtteranceChunks(text);
  setStatus(utteranceChunks.length > 1 ? `Synthesizing speech 1/${utteranceChunks.length}...` : "Synthesizing speech...");

  const synthesizeChunk = (chunkText) => window.catbotDesktop.synthesizePreviewSpeech({
    text: chunkText,
    proxyBaseUrl: state.proxyBaseUrl,
    webClientUrl: state.webClientUrl,
    ttsEndpoint: state.ttsEndpoint,
    ttsModel: state.ttsModel,
    ttsVoice: state.ttsVoice
  }).then(
    (speechResult) => ({ speechResult }),
    (error) => ({ error })
  );

  try {
    let playedAudio = false;
    const shouldUseStreamingSpeech = Boolean(
      isPocketTtsModelName(state.ttsModel) &&
      typeof window.catbotDesktop.synthesizePreviewSpeechStream === "function"
    );

    if (shouldUseStreamingSpeech) {
      const streamingChunks = splitStreamingTtsUtteranceChunks(text);
      setStatus(streamingChunks.length > 1 ? `Prebuffering speech 1/${streamingChunks.length}...` : "Prebuffering speech...");
      const result = await playStreamingSpeechPreviewChunks(streamingChunks, text, durationMs, previewToken, state);
      if (previewToken !== speechGeneration) {
        return;
      }
      if (result?.skipped) {
        // The fallback bubble timing was scheduled while handling skipped chunks.
      } else {
        if (!result?.completed) {
          throw new Error("Speech preview stream did not play audio.");
        }
        playedAudio = true;
      }
    } else {
      let nextSynthesis = synthesizeChunk(utteranceChunks[0] || text);
      for (let chunkIndex = 0; chunkIndex < utteranceChunks.length; chunkIndex += 1) {
        const chunkText = utteranceChunks[chunkIndex];
        const chunkFallbackDurationMs = estimateSpeechSegmentDurationMs(chunkText, text, durationMs);
        if (previewToken !== speechGeneration) {
          return;
        }
        setStatus(utteranceChunks.length > 1 ? `Synthesizing speech ${chunkIndex + 1}/${utteranceChunks.length}...` : "Synthesizing speech...");

        const { speechResult, error } = await nextSynthesis;
        if (error) {
          throw error;
        }
        if (previewToken !== speechGeneration) {
          return;
        }
        if (chunkIndex + 1 < utteranceChunks.length) {
          nextSynthesis = synthesizeChunk(utteranceChunks[chunkIndex + 1]);
        }

        if (speechResult?.skipped) {
          const skippedDurationMs = Math.min(chunkFallbackDurationMs, 1800);
          scheduleSpeechBubbleSentences(chunkText, skippedDurationMs, previewToken);
          speechActiveUntil = Date.now() + skippedDurationMs;
          await new Promise((resolve) => window.setTimeout(resolve, Math.min(skippedDurationMs, 700)));
          continue;
        }

        const completed = await playBufferedSpeechResult(speechResult, chunkText, text, chunkFallbackDurationMs, previewToken, state);
        if (!completed || previewToken !== speechGeneration) {
          return;
        }
        playedAudio = true;
        setStatus(utteranceChunks.length > 1 ? `Previewing speech ${chunkIndex + 1}/${utteranceChunks.length}...` : "Previewing speech...");
      }
    }

    if (previewToken !== speechGeneration) {
      return;
    }
    if (!playedAudio && Date.now() < speechActiveUntil) {
      speechPreviewInProgress = false;
      scheduleSpeechExpressionReset(Math.max(0, speechActiveUntil - Date.now()) + SPEECH_BUBBLE_FADE_MS, previewToken);
      setStatus("Speech bubble preview");
      return;
    }
    hideSpeechBubble();
    setReadyStatus();
    finishSpeechPreviewPlayback();
    void resetTransientSpeechExpression(previewToken);
  } catch (error) {
    if (previewToken !== speechGeneration) {
      return;
    }
    console.warn("Speech preview failed, using fallback mouth animation:", error);
    stopSpeechPreview({ preserveBubble: true });
    forceNeutralVrmFaceForSpeech(state);
    scheduleSpeechBubbleSentences(text, durationMs, previewToken);
    speechActiveUntil = Date.now() + durationMs;
    speechPreviewInProgress = false;
    scheduleSpeechExpressionReset(durationMs + SPEECH_BUBBLE_FADE_MS, previewToken);
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
      updateVrmPoseBlend(performance.now());
    }
    if (shouldApplyManualVrmIdleFallback()) {
      if (
        vrmRuntime?.lastPoseSnapshot &&
        (vrmRuntime.lastFrameHadRunningAction || vrmRuntime.restorePoseOnNextManualIdle)
      ) {
        restoreVrmPoseSnapshot(vrmRuntime.lastPoseSnapshot);
        vrmRuntime.restorePoseOnNextManualIdle = false;
      }
      applyVrmIdlePose(elapsed);
    }
    if (typeof vrmModel.update === "function") {
      vrmModel.update(physicsDelta);
    }
    if (vrmRuntime) {
      const runningActionKey = getPrimaryRunningVrmActionKey();
      vrmRuntime.lastPoseSnapshot = createVrmPoseSnapshot(vrmRuntime);
      vrmRuntime.lastFrameHadRunningAction = Boolean(runningActionKey);
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
window.addEventListener("pointerdown", markAutoCompanionActivity, { capture: true });
window.addEventListener("keydown", markAutoCompanionActivity, { capture: true });
window.addEventListener("blur", () => requestAnimationFrame(refreshTransparentSurface));
window.addEventListener("focus", () => requestAnimationFrame(refreshTransparentSurface));
window.addEventListener("beforeunload", cleanupWebcamStream);
document.addEventListener("visibilitychange", () => requestAnimationFrame(refreshTransparentSurface));
setupMoveModeDragging();
setupQuickHud();
syncAuthGate(currentAuthStatus, { message: "Checking sign-in..." });

try {
  availableModels = await window.catbotDesktop.listModels();
  availableVrmAnimations = await window.catbotDesktop.listVrmaAnimations?.() || availableVrmAnimations;
  currentAuthStatus = await window.catbotDesktop.verifyAuth({ proxyBaseUrl: currentState.proxyBaseUrl });
  renderAuthStatus(currentAuthStatus);
  currentState = await window.catbotDesktop.getState();
  syncQuickHudControls(currentState);
  renderHudState(currentState);
  await populateHudTtsVoiceOptions(currentState.ttsVoice);
  syncAuthGate(currentAuthStatus, {
    message: currentAuthStatus.authenticated ? "Signed in." : currentAuthStatus.error || "Sign in to continue."
  });
  if (currentAuthStatus.authenticated) {
    void syncWebcamModeWithState(currentState);
    syncAutoCompanionScheduler();
    void refreshHudCompanions({ silent: true });
  }
} catch (error) {
  console.warn("Could not initialize integrated avatar HUD:", error);
}

window.catbotDesktop.onStateChanged(async (state) => {
  currentState = state;
  applyStateToScene(state);
  if (state.authRequired && currentAuthStatus.authenticated) {
    currentAuthStatus = { ...currentAuthStatus, authenticated: false, valid: false };
    renderAuthStatus(currentAuthStatus);
  } else if (!state.authRequired && !currentAuthStatus.authenticated) {
    currentAuthStatus = { ...currentAuthStatus, authenticated: true, required: false, valid: true };
    renderAuthStatus(currentAuthStatus);
  }
  const authRequiredForState = isAuthRequired(currentAuthStatus, state);
  syncAuthGate(currentAuthStatus, { focus: false });
  void syncWebcamModeWithState(state);
  syncAutoCompanionScheduler();
  syncQuickHudControls(state);

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
    if (!authRequiredForState) {
      await playSpeechPreview(state);
    }
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
