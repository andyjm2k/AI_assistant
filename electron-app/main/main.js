const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  ipcMain,
  globalShortcut,
  nativeImage,
  protocol,
  shell,
  net,
  screen,
  session,
  safeStorage,
  desktopCapturer
} = require("electron");

const actionHarness = require("./action-harness");
const { deepMerge, loadJsonFile, saveJsonFile } = require("./window-state");

protocol.registerSchemesAsPrivileged([
  {
    scheme: "catbot-file",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true
    }
  }
]);

const ELECTRON_ROOT = path.resolve(__dirname, "..");
const DEV_PROJECT_ROOT = path.resolve(ELECTRON_ROOT, "..");
const USER_STATE_FILE = path.join(app.getPath("userData"), "desktop-state.json");
const USER_AUTH_FILE = path.join(app.getPath("userData"), "desktop-auth.json");
const USER_LOG_FILE = path.join(app.getPath("userData"), "desktop-runtime.log");
const ACTION_HARNESS_CAPTURE_DIR = path.join(app.getPath("userData"), "action-harness");
const BOOTSTRAP_CONFIG_FILE = path.join(ELECTRON_ROOT, "config", "default-desktop-config.json");
const ENV_FILE = path.join(ELECTRON_ROOT, ".env");
const PROJECT_ENV_FILE = path.join(DEV_PROJECT_ROOT, ".env");
const SOUL_PROMPT_RELATIVE_PATH = path.join("config", "soul.md");
const VRMA_DANCE_RELATIVE_DIR = path.join("model_avatar", "AutoDance");
const DEFAULT_PROXY_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_CHAT_ENDPOINT = "";
const DESKTOP_CHAT_HISTORY_LIMIT = 12;
const DESKTOP_CHAT_MESSAGE_CHAR_LIMIT = 6000;
const DESKTOP_TOOL_CACHE_MS = 120000;
const DESKTOP_CLIENT_CONFIG_CACHE_MS = 120000;
const DESKTOP_TTS_VOICE_CACHE_MS = 30000;
const DESKTOP_TOOL_FETCH_TIMEOUT_MS = 5000;
const DESKTOP_VOICE_TOOL_FETCH_TIMEOUT_MS = 3500;
const DESKTOP_TOOL_LOOP_MAX_ITERATIONS = 5;
const DESKTOP_ACTION_HARNESS_DEFAULT_LOOP_BUDGET = 80;
const DESKTOP_ACTION_HARNESS_DEFAULT_NUDGE_INTERVAL = 5;
const DESKTOP_ACTION_HARNESS_MAX_LOOP_BUDGET = 1000;
const DESKTOP_ACTION_HARNESS_MAX_NUDGE_INTERVAL = 50;
const DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT = 12000;
const DESKTOP_CHAT_REQUEST_TIMEOUT_MS = 120000;
const DESKTOP_ACTION_HARNESS_CHAT_TIMEOUT_MS = 600000;
const DESKTOP_ACTION_HARNESS_POST_ACTION_CAPTURE_DELAY_MS = 250;
const DESKTOP_ACTION_HARNESS_MAX_ACTION_DELAY_MS = 3000;
const DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS = 5000;
const DESKTOP_ACTION_HARNESS_CONTINUE_NUDGE_LIMIT = 12;
const DESKTOP_ACTION_HARNESS_CONTEXT_TAIL_MESSAGES = 4;
const DESKTOP_ACTION_HARNESS_MEMORY_MAX_ITEMS = 40;
const DESKTOP_ACTION_HARNESS_FOREGROUND_POLL_MS = 150;
const DESKTOP_ACTION_HARNESS_FOREGROUND_TIMEOUT_MS = 3500;
const DESKTOP_ACTION_HARNESS_CAPTURE_FORMAT = "jpeg";
const DESKTOP_ACTION_HARNESS_CAPTURE_EXTENSION = "jpg";
const DESKTOP_ACTION_HARNESS_CAPTURE_MAX_IMAGE_WIDTH = 800;
const DESKTOP_ACTION_HARNESS_CAPTURE_MIN_IMAGE_WIDTH = 480;
const DESKTOP_ACTION_HARNESS_CAPTURE_MAX_ALLOWED_IMAGE_WIDTH = 1600;
const DESKTOP_ACTION_HARNESS_CAPTURE_JPEG_QUALITY = 62;
const DESKTOP_ACTION_HARNESS_CAPTURE_MIN_JPEG_QUALITY = 45;
const DESKTOP_ACTION_HARNESS_CAPTURE_MAX_JPEG_QUALITY = 90;
const DESKTOP_ACTION_HARNESS_CAPTURE_CLEANUP_INTERVAL_MS = 10 * 60 * 1000;
const DESKTOP_REPLY_EMOTION_RESET_DELAY_MS = 2200;
const DESKTOP_ERROR_EMOTION_RESET_DELAY_MS = 4500;
const DESKTOP_AUTH_GREETING_TEXT = "Hi, I'm ready when you are.";
const DESKTOP_JWT_EXPIRY_LEEWAY_SECONDS = 30;
const DEFAULT_AUTH_COOKIE_NAME = "catbot_auth_token";
const CERT_VERIFY_RESULT_DEFAULT = -3;
const CERT_VERIFY_RESULT_OK = 0;
const AVATAR_WINDOW_TOP_CHROME_GUARD_PX = 32;
const ACTION_HARNESS_TOOL_NAMES = new Set([
  "desktop_action_capture_window",
  "desktop_action_mouse",
  "desktop_action_key",
  "desktop_action_type_text",
  "desktop_action_wait",
  "desktop_action_set_goal",
  "desktop_action_stop"
]);

let avatarWindow = null;
let controlWindow = null;
let webClientWindow = null;
let tray = null;
let isQuitting = false;
let avatarDragState = null;
let moveModeReturnHudVisible = false;
let desktopReplyEmotionResetTimer = null;
let desktopReplyEmotionResetToken = 0;
let desktopToolingCache = {
  fetchedAt: 0,
  tools: [],
  promptLines: []
};
let desktopClientConfigCache = {
  fetchedAt: 0,
  data: null
};
let desktopTtsVoiceCache = {
  key: "",
  fetchedAt: 0,
  voices: []
};
const actionHarnessRuntime = {
  lastCapture: null,
  playMemory: [],
  currentGoal: "",
  lastCaptureCleanupAt: 0
};
const hasSingleInstanceLock = app.requestSingleInstanceLock();

function clipActionHarnessMemoryText(value, maxChars = 360) {
  return normalizeChatContent(value, maxChars).replace(/\s+/g, " ").trim();
}

function resetActionHarnessPlayMemory() {
  actionHarnessRuntime.playMemory = [];
  actionHarnessRuntime.currentGoal = "";
}

function appendActionHarnessPlayMemory(entry = {}) {
  const normalized = {
    at: Date.now(),
    type: String(entry.type || "note").slice(0, 40),
    toolName: String(entry.toolName || "").slice(0, 80),
    args: entry.args && typeof entry.args === "object" && !Array.isArray(entry.args) ? entry.args : null,
    observation: clipActionHarnessMemoryText(entry.observation || "", 420),
    result: clipActionHarnessMemoryText(entry.result || "", 520)
  };
  if (!normalized.toolName && !normalized.observation && !normalized.result) {
    return;
  }
  actionHarnessRuntime.playMemory.push(normalized);
  if (actionHarnessRuntime.playMemory.length > DESKTOP_ACTION_HARNESS_MEMORY_MAX_ITEMS) {
    actionHarnessRuntime.playMemory.splice(0, actionHarnessRuntime.playMemory.length - DESKTOP_ACTION_HARNESS_MEMORY_MAX_ITEMS);
  }
}

function formatActionHarnessPlayMemoryForModel() {
  const recent = Array.isArray(actionHarnessRuntime.playMemory)
    ? actionHarnessRuntime.playMemory.slice(-18)
    : [];
  if (!recent.length) {
    return actionHarnessRuntime.currentGoal
      ? `Current self-goal: ${clipActionHarnessMemoryText(actionHarnessRuntime.currentGoal, 520)}`
      : "";
  }
  const lines = [
    "Play memory from this session. Use this to learn what is working, avoid repeating failed attempts, and adapt the next action."
  ];
  if (actionHarnessRuntime.currentGoal) {
    lines.push(`Current self-goal: ${clipActionHarnessMemoryText(actionHarnessRuntime.currentGoal, 520)}`);
  }
  for (const item of recent) {
    const args = item.args ? ` ${JSON.stringify(item.args)}` : "";
    const action = item.toolName ? `${item.toolName}${args}` : item.type;
    const observation = item.observation ? ` Intent/observation: ${item.observation}` : "";
    const result = item.result ? ` Result: ${item.result}` : "";
    lines.push(`- ${action}.${observation}${result}`);
  }
  return lines.join("\n");
}

function injectActionHarnessPlayMemoryMessage(messages = []) {
  const memory = formatActionHarnessPlayMemoryForModel();
  if (!memory) {
    return messages;
  }
  const output = [...messages];
  let lastUserIndex = -1;
  for (let index = output.length - 1; index >= 0; index -= 1) {
    if (output[index]?.role === "user") {
      lastUserIndex = index;
      break;
    }
  }
  if (lastUserIndex >= 0) {
    output[lastUserIndex] = appendTextToDesktopMessage(output[lastUserIndex], `\n\n${memory}`);
    return output;
  }
  output.push({ role: "user", content: memory });
  return output;
}

if (!hasSingleInstanceLock) {
  app.quit();
}

function readSimpleEnv(filePath) {
  const values = {};
  try {
    if (!fs.existsSync(filePath)) {
      return values;
    }
    const raw = fs.readFileSync(filePath, "utf8");
    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) {
        continue;
      }
      const separatorIndex = trimmed.indexOf("=");
      if (separatorIndex === -1) {
        continue;
      }
      const key = trimmed.slice(0, separatorIndex).trim();
      const value = trimmed.slice(separatorIndex + 1).trim();
      values[key] = value;
    }
  } catch (_) {
    return values;
  }
  return values;
}

function appendRuntimeLog(message) {
  try {
    fs.mkdirSync(path.dirname(USER_LOG_FILE), { recursive: true });
    fs.appendFileSync(USER_LOG_FILE, `${new Date().toISOString()} ${message}\n`, "utf8");
  } catch (_) {
    // ignore logging failures
  }
}

function normalizeUrlString(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function isSafeExternalUrl(value) {
  const normalized = normalizeUrlString(value);
  if (!normalized) {
    return false;
  }
  try {
    const parsed = new URL(normalized);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch (_) {
    return false;
  }
}

function openSafeExternalUrl(value) {
  const normalized = normalizeUrlString(value);
  if (!isSafeExternalUrl(normalized)) {
    appendRuntimeLog(`[security] blocked external URL: ${normalized || "(empty)"}`);
    return false;
  }
  shell.openExternal(normalized).catch((error) => appendRuntimeLog(`[security] openExternal failed: ${String(error?.message || error)}`));
  return true;
}

function normalizeEndpointString(value) {
  return String(value || "").trim();
}

function extractOriginFromUrlLike(value) {
  const normalized = normalizeUrlString(value);
  if (!normalized) {
    return "";
  }
  try {
    return new URL(normalized).origin;
  } catch (_) {
    const match = normalized.match(/^(https?:\/\/[^/]+)/i);
    return match ? match[1] : normalized.replace(/\/v1$/i, "");
  }
}

function areSameUrlOrigins(left, right) {
  const leftOrigin = extractOriginFromUrlLike(left);
  const rightOrigin = extractOriginFromUrlLike(right);
  return Boolean(leftOrigin && rightOrigin && leftOrigin.toLowerCase() === rightOrigin.toLowerCase());
}

function parseUrlLike(value) {
  const normalized = normalizeUrlString(value);
  if (!normalized) {
    return null;
  }
  try {
    return new URL(normalized);
  } catch (_) {
    return null;
  }
}

function normalizeHostname(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^\[/, "")
    .replace(/\]$/, "");
}

function isPrivateIpv4(hostname) {
  const parts = normalizeHostname(hostname).split(".").map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return false;
  }
  return (
    parts[0] === 10 ||
    parts[0] === 127 ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168)
  );
}

function isLocalCertificateHostname(hostname) {
  const normalized = normalizeHostname(hostname);
  return (
    normalized === "localhost" ||
    normalized === "::1" ||
    normalized.endsWith(".local") ||
    normalized.endsWith(".localhost") ||
    isPrivateIpv4(normalized)
  );
}

function getTrustedLocalCertificateHostnames() {
  const hostnames = new Set();
  for (const value of [state?.webClientUrl, state?.proxyBaseUrl, DEFAULT_STATE?.webClientUrl, DEFAULT_STATE?.proxyBaseUrl]) {
    const parsed = parseUrlLike(value);
    if (!parsed || parsed.protocol !== "https:") {
      continue;
    }
    const hostname = normalizeHostname(parsed.hostname);
    if (isLocalCertificateHostname(hostname)) {
      hostnames.add(hostname);
    }
  }
  return hostnames;
}

function isTrustedLocalCertificateUrl(urlValue) {
  if (!state?.trustLocalCertificates) {
    return false;
  }
  const parsed = parseUrlLike(urlValue);
  if (!parsed || parsed.protocol !== "https:") {
    return false;
  }
  return getTrustedLocalCertificateHostnames().has(normalizeHostname(parsed.hostname));
}

function normalizeChatContent(value, maxChars = DESKTOP_CHAT_MESSAGE_CHAR_LIMIT) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxChars ? `${text.slice(0, maxChars - 3)}...` : text;
}

function normalizeDesktopChatMessage(message = {}) {
  const role = message.role === "assistant" ? "assistant" : "user";
  const rawText = coerceDesktopMessageText(message.content);
  let content = role === "assistant"
    ? normalizeChatContent(getVisibleDesktopAssistantText(message))
    : normalizeChatContent(rawText);
  if (!content && role === "assistant") {
    try {
      content = parseDesktopToolFallbacks(rawText).length ? "Desktop action completed." : "";
    } catch (_) {
      content = "";
    }
  }
  if (!content) {
    return null;
  }
  return { role, content };
}

function normalizeDesktopChatHistory(history) {
  if (!Array.isArray(history)) {
    return [];
  }
  return history
    .map((message) => normalizeDesktopChatMessage(message))
    .filter(Boolean)
    .slice(-DESKTOP_CHAT_HISTORY_LIMIT);
}

function coerceAssistantTextFromChatResponse(data) {
  const firstChoice = Array.isArray(data?.choices) ? data.choices[0] : null;
  const message = firstChoice?.message || {};
  const content = message.content ?? firstChoice?.content ?? firstChoice?.text ?? data?.reply ?? data?.response ?? "";
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part && typeof part === "object") {
          return part.text || part.content || "";
        }
        return "";
      })
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  }
  return String(content || "").replace(/\s+/g, " ").trim();
}

function getDesktopChoiceMessage(choice = {}) {
  if (choice && typeof choice === "object" && choice.message && typeof choice.message === "object") {
    return choice.message;
  }
  if (choice && typeof choice === "object") {
    return {
      role: "assistant",
      content: choice.cleanContent ?? choice.content ?? choice.text ?? ""
    };
  }
  return { role: "assistant", content: "" };
}

function getDesktopChatResponseMessage(data) {
  const firstChoice = Array.isArray(data?.choices) ? data.choices[0] : null;
  return getDesktopChoiceMessage(firstChoice || {});
}

function coerceDesktopMessageText(value) {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part && typeof part === "object") {
          return part.text || part.content || "";
        }
        return "";
      })
      .join(" ");
  }
  return String(value || "");
}

function getVisibleDesktopAssistantText(message = {}) {
  return stripDesktopThinkBlocks(coerceDesktopMessageText(message?.content ?? ""))
    .replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, " ")
    .replace(/<tool>[\s\S]*?<\/tool>/gi, " ")
    .replace(/<parameters>[\s\S]*?<\/parameters>/gi, " ")
    .replace(/Requested tool calls:\s*(?:\r?\n\s*-\s*desktop_action_[^\r\n]+)+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatDesktopToolCallForTranscript(toolCall = {}) {
  const name = getDesktopToolCallName(toolCall);
  if (!name) {
    return "";
  }
  let args = {};
  try {
    args = getDesktopToolCallArguments(toolCall);
  } catch (_) {
    args = {};
  }
  return `${name} completed with arguments ${JSON.stringify(args)}`;
}

function buildDesktopAssistantHistoryMessage(message = {}, options = {}) {
  const contentParts = [];
  const assistantText = getVisibleDesktopAssistantText(message);
  if (assistantText) {
    contentParts.push(assistantText);
  }

  const hasToolTranscript = Array.isArray(options.toolCalls) &&
    options.toolCalls.map(formatDesktopToolCallForTranscript).filter(Boolean).length > 0;
  if (!assistantText && hasToolTranscript) {
    contentParts.push("I selected a desktop action for the harness.");
  }

  return {
    role: "assistant",
    content: contentParts.join("\n\n") || "I am calling a tool."
  };
}

function stripDesktopThinkBlocks(value) {
  return String(value || "").replace(/<think>[\s\S]*?<\/think>/gi, " ");
}

function parseDesktopLenientJsonValue(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return null;
  }
  const withoutFence = raw
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  const candidates = [
    withoutFence,
    withoutFence.replace(/,\s*([}\]])/g, "$1")
  ];
  for (const candidate of candidates) {
    try {
      return JSON.parse(candidate);
    } catch (_) {
      // Try the next normalized candidate.
    }
  }
  return null;
}

function parseDesktopLenientJsonObject(value) {
  const parsed = parseDesktopLenientJsonValue(value);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
}

function normalizeDesktopToolCall(rawCall) {
  if (!rawCall || typeof rawCall !== "object" || Array.isArray(rawCall)) {
    return null;
  }

  const functionBlock = rawCall.function && typeof rawCall.function === "object" && !Array.isArray(rawCall.function)
    ? rawCall.function
    : rawCall.function_call && typeof rawCall.function_call === "object" && !Array.isArray(rawCall.function_call)
      ? rawCall.function_call
      : null;
  const name = String(
    functionBlock?.name ||
    rawCall.name ||
    rawCall.tool_name ||
    rawCall.tool ||
    rawCall.action ||
    ""
  ).trim();
  if (!name) {
    return null;
  }

  let rawArgs = functionBlock?.arguments ?? rawCall.arguments ?? rawCall.parameters ?? rawCall.args ?? {};
  if ((!rawArgs || typeof rawArgs !== "object") && rawCall.contentPrompt) {
    rawArgs = { contentPrompt: rawCall.contentPrompt };
  }
  if (typeof rawArgs === "string") {
    const parsedArgs = parseDesktopLenientJsonObject(rawArgs);
    rawArgs = parsedArgs || rawArgs;
  }

  return {
    id: rawCall.id || `desktop_tool_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    type: rawCall.type || "function",
    function: {
      name,
      arguments: typeof rawArgs === "string"
        ? rawArgs
        : JSON.stringify(rawArgs && typeof rawArgs === "object" && !Array.isArray(rawArgs) ? rawArgs : {})
    }
  };
}

function parseDesktopToolFallbacks(content) {
  const withoutCode = stripDesktopThinkBlocks(content).replace(/```[\s\S]*?```/g, " ");
  const calls = [];

  const qwenToolRegex = /<tool_call>([\s\S]*?)<\/tool_call>/gi;
  for (const match of withoutCode.matchAll(qwenToolRegex)) {
    const parsed = parseDesktopLenientJsonValue(match[1]);
    const parsedCalls = Array.isArray(parsed) ? parsed : [parsed];
    for (const item of parsedCalls) {
      const normalized = normalizeDesktopToolCall(item);
      if (normalized) {
        calls.push(normalized);
      }
    }
  }

  const legacyToolRegex = /<tool>([\s\S]*?)<\/tool>\s*<parameters>([\s\S]*?)<\/parameters>/gi;
  for (const match of withoutCode.matchAll(legacyToolRegex)) {
    const name = String(match[1] || "").trim();
    const parameters = parseDesktopLenientJsonObject(match[2]);
    const normalized = normalizeDesktopToolCall({ name, arguments: parameters || {} });
    if (normalized) {
      calls.push(normalized);
    }
  }

  const transcriptToolRegex = /(?:^|\r?\n)\s*-\s*(desktop_action_[A-Za-z0-9_:-]+)\s+({[^\r\n]*})/gi;
  for (const match of withoutCode.matchAll(transcriptToolRegex)) {
    const name = String(match[1] || "").trim();
    const parameters = parseDesktopLenientJsonObject(match[2]);
    const normalized = normalizeDesktopToolCall({ name, arguments: parameters || {} });
    if (normalized) {
      calls.push(normalized);
    }
  }

  if (calls.length) {
    return calls;
  }

  const directJson = parseDesktopLenientJsonValue(withoutCode);
  const directCalls = Array.isArray(directJson)
    ? directJson
    : Array.isArray(directJson?.tool_calls)
      ? directJson.tool_calls
      : directJson
        ? [directJson]
        : [];
  return directCalls.map(normalizeDesktopToolCall).filter(Boolean);
}

function collectDesktopToolCalls(assistantMessage = {}) {
  const nativeCalls = Array.isArray(assistantMessage?.tool_calls)
    ? assistantMessage.tool_calls.map(normalizeDesktopToolCall).filter(Boolean)
    : [];
  if (nativeCalls.length) {
    return { calls: nativeCalls, native: true };
  }

  const functionCall = normalizeDesktopToolCall(assistantMessage?.function_call);
  if (functionCall) {
    return { calls: [functionCall], native: false };
  }

  const fallbackCalls = parseDesktopToolFallbacks(coerceDesktopMessageText(assistantMessage?.content || ""));
  return { calls: fallbackCalls, native: false };
}

function calculateSpeechDurationMs(text) {
  return Math.max(1800, Math.min(12000, String(text || "").length * 75));
}

function inferDesktopAvatarExpression(text) {
  const lowered = String(text || "").toLowerCase();
  const includesAny = (keywords) => keywords.some((keyword) => lowered.includes(keyword));
  if (includesAny(["angry", "mad", "furious", "annoyed", "irritated", "frustrated", "harsh"])) {
    return "angry";
  }
  if (includesAny(["sad", "upset", "sorry", "disappointed", "unhappy", "crying", "cry"])) {
    return "sad";
  }
  if (includesAny(["thinking", "consider", "perhaps", "maybe", "hmm", "interesting", "curious", "think", "ponder"])) {
    return "think";
  }
  if (includesAny(["surprised", "surprise", "wow", "unexpected", "amazing"])) {
    return "surprised";
  }
  if (includesAny(["happy", "joy", "glad", "excited", "wonderful", "love", "lovely", "delighted", "delight", "romantic"])) {
    return "love";
  }
  return "happy";
}

function decodeDesktopJwtPayload(token) {
  const parts = String(token || "").split(".");
  if (parts.length < 2 || !parts[1]) {
    return null;
  }
  try {
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = `${payload}${"=".repeat((4 - (payload.length % 4)) % 4)}`;
    return JSON.parse(Buffer.from(padded, "base64").toString("utf8"));
  } catch (_) {
    return null;
  }
}

function isDesktopJwtTokenUsable(token) {
  const normalized = String(token || "").trim();
  if (!normalized) {
    return false;
  }
  const payload = decodeDesktopJwtPayload(normalized);
  const expiresAtSeconds = Number(payload?.exp);
  if (!Number.isFinite(expiresAtSeconds)) {
    return false;
  }
  return expiresAtSeconds * 1000 > Date.now() + DESKTOP_JWT_EXPIRY_LEEWAY_SECONDS * 1000;
}

function coerceTranscriptionText(data) {
  if (typeof data === "string") {
    return data.trim();
  }
  const text = data?.text || data?.transcription || data?.result?.text || data?.message || "";
  return String(text || "").trim();
}

function sanitizeDesktopTtsText(text) {
  return String(text || "")
    .replace(/[\u{1F1E6}-\u{1F1FF}]{2}/gu, "")
    .replace(/[0-9#*]\uFE0F?\u20E3/gu, "")
    .replace(/\p{Extended_Pictographic}(?:[\uFE0E\uFE0F]|[\u{1F3FB}-\u{1F3FF}])*(?:\u200D\p{Extended_Pictographic}(?:[\uFE0E\uFE0F]|[\u{1F3FB}-\u{1F3FF}])*)*/gu, "")
    .replace(/[\uFE0E\uFE0F\u200D]/g, "")
    .replace(/[\u{1F3FB}-\u{1F3FF}]/gu, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .replace(/([([{])\s+/g, "$1")
    .replace(/\s+([\])}])/g, "$1")
    .trim();
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

function parseDesktopAudioContentTypeParams(contentType) {
  const params = {};
  const parts = String(contentType || "").split(";").slice(1);
  for (const part of parts) {
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

function normalizeDesktopPcmEncoding(value, bitsPerSample = 16) {
  const normalized = String(value || "").trim().toLowerCase().replace(/[_\s]/g, "-");
  if (normalized.includes("float")) {
    return "float32";
  }
  if (
    normalized.includes("s16") ||
    normalized.includes("pcm16") ||
    normalized.includes("int16") ||
    normalized.includes("signed")
  ) {
    return "s16le";
  }
  return Number(bitsPerSample) === 32 ? "float32" : "s16le";
}

function convertDesktopFloat32PcmBytesToPcm16Bytes(pcmBytes) {
  const alignedLength = pcmBytes.byteLength - (pcmBytes.byteLength % 4);
  if (alignedLength <= 0) {
    return new Uint8Array(0);
  }
  const alignedBytes = pcmBytes.byteOffset % 4 === 0 && alignedLength === pcmBytes.byteLength
    ? pcmBytes
    : pcmBytes.slice(0, alignedLength);
  const samples = new Float32Array(
    alignedBytes.buffer,
    alignedBytes.byteOffset,
    Math.floor(alignedLength / 4)
  );
  const pcm16 = new Uint8Array(samples.length * 2);
  const view = new DataView(pcm16.buffer);
  for (let index = 0; index < samples.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, Number(samples[index]) || 0));
    view.setInt16(index * 2, Math.round(clamped * 32767), true);
  }
  return pcm16;
}

function buildDesktopWavArrayBufferFromPcm(pcmArrayBuffer, sampleRate = 24000, channels = 1, pcmFormat = {}) {
  const inputBytes = new Uint8Array(pcmArrayBuffer || new ArrayBuffer(0));
  const pcmEncoding = normalizeDesktopPcmEncoding(pcmFormat.encoding || pcmFormat.pcmEncoding, pcmFormat.bitsPerSample);
  const pcmBytes = pcmEncoding === "float32"
    ? convertDesktopFloat32PcmBytesToPcm16Bytes(inputBytes)
    : inputBytes;
  const safeSampleRate = Math.max(8000, Number(sampleRate) || 24000);
  const safeChannels = Math.max(1, Number(channels) || 1);
  const bitsPerSample = 16;
  const blockAlign = safeChannels * (bitsPerSample / 8);
  const byteRate = safeSampleRate * blockAlign;
  const wavBytes = new Uint8Array(44 + pcmBytes.byteLength);
  const view = new DataView(wavBytes.buffer);
  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      wavBytes[offset + index] = value.charCodeAt(index);
    }
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + pcmBytes.byteLength, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, safeChannels, true);
  view.setUint32(24, safeSampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);
  writeAscii(36, "data");
  view.setUint32(40, pcmBytes.byteLength, true);
  wavBytes.set(pcmBytes, 44);
  return wavBytes.buffer;
}

function getDesktopAudioHeaderInfo(value) {
  const bytes = value instanceof Uint8Array
    ? value
    : new Uint8Array(value || new ArrayBuffer(0));
  if (bytes.length >= 4) {
    const tag = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
    if (tag === "RIFF") {
      return "wav";
    }
    if (tag === "OggS") {
      return "ogg";
    }
    if (bytes[0] === 0x1A && bytes[1] === 0x45 && bytes[2] === 0xDF && bytes[3] === 0xA3) {
      return "webm";
    }
  }
  if (bytes.length >= 3 && bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33) {
    return "mp3";
  }
  if (bytes.length >= 2 && bytes[0] === 0xFF && (bytes[1] & 0xE0) === 0xE0) {
    return "mp3";
  }
  return "";
}

function shouldTreatDesktopTtsBytesAsPcm(contentType, bytes, requestedPcm = false) {
  if (!requestedPcm) {
    return false;
  }
  const normalized = String(contentType || "").toLowerCase();
  if (normalized.includes("audio/pcm") || normalized.includes("audio/l16") || normalized.includes("audio/s16le")) {
    return true;
  }
  if (
    normalized.includes("audio/wav") ||
    normalized.includes("audio/wave") ||
    normalized.includes("audio/mpeg") ||
    normalized.includes("audio/mp3") ||
    normalized.includes("audio/ogg") ||
    normalized.includes("audio/webm") ||
    normalized.includes("audio/mp4")
  ) {
    return false;
  }
  const headerInfo = getDesktopAudioHeaderInfo(bytes);
  if (headerInfo) {
    return false;
  }
  return !normalized || normalized.includes("application/octet-stream");
}

function getDesktopTtsAudioFormat(contentType, bytes) {
  const normalized = String(contentType || "").toLowerCase();
  if (normalized.includes("audio/wav") || normalized.includes("audio/wave")) {
    return "wav";
  }
  if (normalized.includes("audio/mpeg") || normalized.includes("audio/mp3")) {
    return "mp3";
  }
  if (normalized.includes("audio/ogg")) {
    return "ogg";
  }
  if (normalized.includes("audio/webm")) {
    return "webm";
  }
  if (normalized.includes("audio/mp4") || normalized.includes("audio/m4a")) {
    return "mp4";
  }
  return getDesktopAudioHeaderInfo(bytes);
}

function normalizeDesktopAudioContentType(contentType, bytes) {
  const normalized = String(contentType || "").trim();
  if (/^audio\/mp3/i.test(normalized)) {
    return "audio/mpeg";
  }
  if (normalized && !/application\/octet-stream/i.test(normalized)) {
    return normalized;
  }
  const format = getDesktopTtsAudioFormat(normalized, bytes);
  if (format === "wav") {
    return "audio/wav";
  }
  if (format === "mp3") {
    return "audio/mpeg";
  }
  if (format === "ogg") {
    return "audio/ogg";
  }
  if (format === "webm") {
    return "audio/webm";
  }
  if (format === "mp4") {
    return "audio/mp4";
  }
  return normalized || "audio/mpeg";
}

function getDesktopTtsSampleRate(headers, fallback = 24000, contentType = "") {
  const params = parseDesktopAudioContentTypeParams(contentType);
  return Math.max(
    8000,
    Number(
      headers?.get?.("x-audio-sample-rate") ||
      headers?.get?.("x-sample-rate") ||
      params.rate ||
      params.samplerate ||
      params.sample_rate ||
      fallback
    ) || fallback
  );
}

function getDesktopTtsChannels(headers, fallback = 1, contentType = "") {
  const params = parseDesktopAudioContentTypeParams(contentType);
  return Math.max(
    1,
    Number(
      headers?.get?.("x-audio-channels") ||
      headers?.get?.("x-channels") ||
      params.channels ||
      fallback
    ) || fallback
  );
}

function getDesktopTtsPcmBitsPerSample(contentType = "", headers = null, encoding = "") {
  const params = parseDesktopAudioContentTypeParams(contentType);
  const rawBits =
    headers?.get?.("x-audio-bits-per-sample") ||
    headers?.get?.("x-audio-bits") ||
    headers?.get?.("x-bits-per-sample") ||
    params.bits ||
    params.bit_depth ||
    params.bitdepth;
  const parsed = Number(rawBits);
  if (Number.isFinite(parsed) && parsed > 0) {
    return Math.max(8, Math.round(parsed));
  }
  return String(encoding || "").toLowerCase().includes("float") ? 32 : 16;
}

function getDesktopTtsPcmEncoding(contentType = "", headers = null) {
  const params = parseDesktopAudioContentTypeParams(contentType);
  const rawEncoding =
    headers?.get?.("x-audio-encoding") ||
    headers?.get?.("x-pcm-encoding") ||
    params.encoding ||
    params.format ||
    "";
  return normalizeDesktopPcmEncoding(rawEncoding, getDesktopTtsPcmBitsPerSample(contentType, headers, rawEncoding));
}

function getDesktopTtsPcmFormat(contentType = "", headers = null) {
  const encoding = getDesktopTtsPcmEncoding(contentType, headers);
  const bitsPerSample = encoding === "float32" ? 32 : 16;
  return {
    encoding,
    bitsPerSample,
    bytesPerSample: encoding === "float32" ? 4 : 2
  };
}

function normalizeDesktopPcmContentType(contentType = "", sampleRate = 24000, channels = 1, pcmFormat = {}) {
  const normalized = String(contentType || "").trim();
  if (/^audio\/pcm/i.test(normalized) || /^audio\/l16/i.test(normalized) || /^audio\/s16le/i.test(normalized)) {
    return normalized;
  }
  const encoding = pcmFormat.encoding === "float32" ? "float" : "signed-integer";
  const bits = Math.max(8, Number(pcmFormat.bitsPerSample) || (encoding === "float" ? 32 : 16));
  return `audio/pcm;rate=${Math.max(8000, Number(sampleRate) || 24000)};channels=${Math.max(1, Number(channels) || 1)};encoding=${encoding};bits=${bits}`;
}

function concatDesktopUint8Chunks(chunks, totalBytes = 0) {
  const safeTotal = totalBytes || chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
  const output = new Uint8Array(safeTotal);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

function toDetachedArrayBuffer(value) {
  const bytes = value instanceof Uint8Array
    ? value
    : new Uint8Array(value || new ArrayBuffer(0));
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function stripHtmlForDiagnostic(value) {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function looksLikeHtmlResponse(contentType, text) {
  return /html/i.test(String(contentType || "")) || /^\s*<!doctype html/i.test(String(text || "")) || /^\s*<html/i.test(String(text || ""));
}

function formatProxyResponseError(response, responseText, actionLabel, apiOrigin) {
  const statusLabel = response?.status ? `HTTP ${response.status}` : "request failed";
  const contentType = response?.headers?.get("content-type") || "";
  const detailText = stripHtmlForDiagnostic(responseText);
  const shortDetail = detailText ? ` ${detailText.slice(0, 220)}` : "";

  if (looksLikeHtmlResponse(contentType, responseText)) {
    const htmlLabel = response?.status >= 400 ? "an HTML error page" : "HTML instead of JSON";
    return `${actionLabel} reached ${apiOrigin}, but that server returned ${htmlLabel} (${statusLabel}).${shortDetail} This usually means the CATBot API/proxy URL is pointing at a static web server instead of the FastAPI proxy. Set CATBot API/proxy URL to the API server, for example ${DEFAULT_PROXY_BASE_URL}.`;
  }

  return `${actionLabel} failed at ${apiOrigin} (${statusLabel}).${shortDetail}`;
}

function parseJsonOrNull(responseText) {
  try {
    return responseText ? JSON.parse(responseText) : {};
  } catch (_) {
    return null;
  }
}

function bufferFromIpcBinary(value) {
  if (Buffer.isBuffer(value)) {
    return value;
  }
  if (value instanceof ArrayBuffer) {
    return Buffer.from(value);
  }
  if (ArrayBuffer.isView(value)) {
    return Buffer.from(value.buffer, value.byteOffset, value.byteLength);
  }
  if (Array.isArray(value)) {
    return Buffer.from(value);
  }
  if (value && value.type === "Buffer" && Array.isArray(value.data)) {
    return Buffer.from(value.data);
  }
  throw new Error("Captured microphone audio was not in a supported binary format.");
}

function getProxyOriginFromPayload(payload = {}) {
  return extractOriginFromUrlLike(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || state.webClientUrl);
}

function isDataImageUrl(value) {
  return /^data:image\/(png|jpe?g|webp);base64,/i.test(String(value || ""));
}

function buildDesktopVisualAttachments(payload = {}) {
  const attachments = [];
  if (isDataImageUrl(payload.screenImageDataUrl)) {
    attachments.push({
      dataUrl: payload.screenImageDataUrl,
      label: "desktop screenshot"
    });
  }
  if (isDataImageUrl(payload.webcamImageDataUrl)) {
    attachments.push({
      dataUrl: payload.webcamImageDataUrl,
      label: "webcam snapshot"
    });
  }
  if (isDataImageUrl(payload.actionHarnessImageDataUrl)) {
    attachments.push({
      dataUrl: payload.actionHarnessImageDataUrl,
      label: "play-mode window screenshot with grid overlay"
    });
  }
  return attachments;
}

function buildDesktopUserMessage(text, visualAttachments = [], options = {}) {
  const maxChars = Number.isFinite(Number(options.maxChars))
    ? Math.max(200, Math.round(Number(options.maxChars)))
    : 2400;
  const cleanText = normalizeChatContent(text, maxChars);
  const attachments = Array.isArray(visualAttachments)
    ? visualAttachments.filter((item) => isDataImageUrl(item?.dataUrl))
    : [];
  if (!attachments.length) {
    return { role: "user", content: cleanText };
  }
  const labels = attachments.map((item) => item.label || "image").join(" and ");
  return {
    role: "user",
    content: [
      {
        type: "text",
        text: `${cleanText}\n\nUse the attached ${labels} as visual context.`
      },
      ...attachments.map((item) => ({
        type: "image_url",
        image_url: {
          url: item.dataUrl,
          detail: "auto"
        }
      }))
    ]
  };
}

function appendTextToDesktopContent(content, text) {
  const addition = String(text || "").trim();
  if (!addition) {
    return content;
  }
  if (Array.isArray(content)) {
    const next = content.map((part) => {
      if (part && typeof part === "object" && !Array.isArray(part)) {
        return { ...part };
      }
      return part;
    });
    const textPart = next.find((part) => part && typeof part === "object" && part.type === "text");
    if (textPart) {
      textPart.text = `${String(textPart.text || "").trim()}\n\n${addition}`.trim();
    } else {
      next.unshift({ type: "text", text: addition });
    }
    return next;
  }
  const base = coerceDesktopMessageText(content).trim();
  return base ? `${base}\n\n${addition}` : addition;
}

function appendTextToDesktopMessage(message = {}, text) {
  return {
    ...message,
    content: appendTextToDesktopContent(message.content, text)
  };
}

function shouldFlattenDesktopVisualContentForFallback(options = {}) {
  const model = String(options.model || "").toLowerCase();
  if (!model) {
    return false;
  }
  const isKnownVisionModel = (
    model.includes("vl") ||
    model.includes("vision") ||
    model.includes("ui-tars") ||
    model.includes("spacethinker") ||
    model.includes("gemma-3") ||
    model.includes("gemma3")
  );
  return !isKnownVisionModel && (
    model.includes("qwen") ||
    model.includes("hermes")
  );
}

function sanitizeDesktopUserContentForTextFallback(content, options = {}) {
  if (!Array.isArray(content)) {
    return normalizeChatContent(coerceDesktopMessageText(content));
  }

  const textParts = [];
  const imageParts = [];
  for (const part of content) {
    if (typeof part === "string") {
      const text = normalizeChatContent(part);
      if (text) {
        textParts.push(text);
      }
      continue;
    }
    if (!part || typeof part !== "object" || Array.isArray(part)) {
      continue;
    }
    if (part.type === "text") {
      const text = normalizeChatContent(part.text ?? part.content ?? "");
      if (text) {
        textParts.push(text);
      }
      continue;
    }
    const imageUrl = typeof part.image_url === "string"
      ? part.image_url
      : part.image_url?.url || part.url || part.image;
    if (isDataImageUrl(imageUrl)) {
      imageParts.push({
        type: "image_url",
        image_url: {
          url: imageUrl,
          detail: part.image_url?.detail || part.detail || "auto"
        }
      });
      continue;
    }
    const text = normalizeChatContent(part.text ?? part.content ?? "");
    if (text) {
      textParts.push(text);
    }
  }

  const text = normalizeChatContent(textParts.join("\n\n")) || "Continue.";
  if (shouldFlattenDesktopVisualContentForFallback(options)) {
    const imageNote = imageParts.length
      ? `\n\n${imageParts.length} image attachment${imageParts.length === 1 ? " was" : "s were"} omitted because this local text fallback template does not accept image message parts. Use the latest textual tool result and grid coordinates.`
      : "";
    return normalizeChatContent(`${text}${imageNote}`, DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT);
  }
  return [
    { type: "text", text },
    ...imageParts
  ];
}

function assistantMessageLooksLikeOnlyToolCall(message = {}) {
  if (Array.isArray(message?.tool_calls) && message.tool_calls.length) {
    return true;
  }
  const text = coerceDesktopMessageText(message?.content || "");
  try {
    return parseDesktopToolFallbacks(text).length > 0;
  } catch (_) {
    return /<tool_call>[\s\S]*?<\/tool_call>/i.test(text);
  }
}

function sanitizeDesktopMessageForTextFallback(message = {}, options = {}) {
  const rawRole = String(message?.role || "user").trim().toLowerCase();
  const role = rawRole === "system" || rawRole === "assistant" || rawRole === "user"
    ? rawRole
    : "user";

  if (role === "assistant") {
    const content = normalizeChatContent(getVisibleDesktopAssistantText(message)) ||
      (assistantMessageLooksLikeOnlyToolCall(message) ? "Desktop action completed." : "");
    return content ? { role, content } : null;
  }

  if (role === "system") {
    const content = normalizeChatContent(coerceDesktopMessageText(message?.content || ""), DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT);
    return content ? { role, content } : null;
  }

  const content = rawRole === "user"
    ? sanitizeDesktopUserContentForTextFallback(message?.content, options)
    : normalizeChatContent(coerceDesktopMessageText(message?.content || ""), DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT);
  if (Array.isArray(content)) {
    return content.length ? { role, content } : null;
  }
  return content ? { role, content } : null;
}

function mergeDesktopFallbackContent(left, right) {
  const mergedText = [coerceDesktopMessageText(left), coerceDesktopMessageText(right)]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join("\n\n");
  if (!Array.isArray(left) && !Array.isArray(right)) {
    return normalizeChatContent(mergedText, DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT);
  }
  const imageParts = [];
  for (const content of [left, right]) {
    if (!Array.isArray(content)) {
      continue;
    }
    for (const part of content) {
      const imageUrl = typeof part?.image_url === "string" ? part.image_url : part?.image_url?.url;
      if (isDataImageUrl(imageUrl)) {
        imageParts.push({
          type: "image_url",
          image_url: {
            url: imageUrl,
            detail: part?.image_url?.detail || "auto"
          }
        });
      }
    }
  }
  return [
    { type: "text", text: normalizeChatContent(mergedText, DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT) || "Continue." },
    ...imageParts
  ];
}

function isDesktopToolResponseOnlyText(content) {
  const text = coerceDesktopMessageText(content).trim();
  return /^<tool_response>[\s\S]*<\/tool_response>$/i.test(text);
}

function ensureDesktopFallbackHasUserQuery(messages = []) {
  const output = [...messages];
  if (!output.length || output[output.length - 1]?.role !== "user") {
    output.push({
      role: "user",
      content: "Continue."
    });
    return output;
  }
  const last = output[output.length - 1];
  if (isDesktopToolResponseOnlyText(last.content)) {
    output[output.length - 1] = appendTextToDesktopMessage(
      last,
      "Continue desktop play mode from this tool result and choose the next single action."
    );
  }
  return output;
}

function sanitizeDesktopMessagesForTextFallback(messages = [], options = {}) {
  const input = Array.isArray(messages) ? messages : [];
  const output = [];
  for (const message of input) {
    const sanitized = sanitizeDesktopMessageForTextFallback(message, options);
    if (!sanitized) {
      continue;
    }
    if (sanitized.role === "system" && output.length) {
      const firstSystemIndex = output.findIndex((item) => item.role === "system");
      if (firstSystemIndex >= 0) {
        output[firstSystemIndex] = {
          role: "system",
          content: mergeDesktopFallbackContent(output[firstSystemIndex].content, sanitized.content)
        };
      } else {
        output.unshift(sanitized);
      }
      continue;
    }
    const previous = output[output.length - 1];
    if (previous && previous.role === sanitized.role && sanitized.role !== "system") {
      output[output.length - 1] = {
        role: previous.role,
        content: mergeDesktopFallbackContent(previous.content, sanitized.content)
      };
      continue;
    }
    output.push(sanitized);
  }
  return ensureDesktopFallbackHasUserQuery(output);
}

function desktopContentHasImagePart(content) {
  return Array.isArray(content) && content.some((part) => {
    const imageUrl = typeof part?.image_url === "string" ? part.image_url : part?.image_url?.url;
    return isDataImageUrl(imageUrl);
  });
}

function countDesktopImagePartsInContent(content) {
  if (!Array.isArray(content)) {
    return 0;
  }
  return content.reduce((count, part) => {
    const imageUrl = typeof part?.image_url === "string" ? part.image_url : part?.image_url?.url;
    return count + (isDataImageUrl(imageUrl) ? 1 : 0);
  }, 0);
}

function countDesktopImagePartsInMessages(messages = []) {
  return (Array.isArray(messages) ? messages : []).reduce(
    (count, message) => count + countDesktopImagePartsInContent(message?.content),
    0
  );
}

function stripDesktopImagePartsFromContent(content) {
  if (!Array.isArray(content)) {
    return content;
  }
  const text = coerceDesktopMessageText(content);
  return normalizeChatContent(text, DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT) || "Earlier play-mode screenshot omitted for low-latency context.";
}

function keepLatestDesktopVisualMessageOnly(messages = []) {
  if (!Array.isArray(messages)) {
    return [];
  }
  let latestVisualIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user" && desktopContentHasImagePart(messages[index]?.content)) {
      latestVisualIndex = index;
      break;
    }
  }
  if (latestVisualIndex < 0) {
    return messages;
  }
  return messages.map((message, index) => {
    if (index === latestVisualIndex || !desktopContentHasImagePart(message?.content)) {
      return message;
    }
    return {
      ...message,
      content: stripDesktopImagePartsFromContent(message.content)
    };
  });
}

function getAssetRoot() {
  return app.isPackaged ? process.resourcesPath : DEV_PROJECT_ROOT;
}

function getSoulPromptPath() {
  return path.join(getAssetRoot(), SOUL_PROMPT_RELATIVE_PATH);
}

function getSoulPromptText() {
  try {
    const soulPath = getSoulPromptPath();
    if (!fs.existsSync(soulPath)) {
      return "";
    }
    return fs.readFileSync(soulPath, "utf8").trim();
  } catch (error) {
    appendRuntimeLog(`[soul prompt] failed to read ${SOUL_PROMPT_RELATIVE_PATH}: ${String(error?.message || error)}`);
    return "";
  }
}

function getLogoPath() {
  return path.join(getAssetRoot(), "CATBot_logo.png");
}

function getModelRoot() {
  return path.join(getAssetRoot(), "model_avatar");
}

function getVrmaDanceRoot() {
  return path.join(getAssetRoot(), VRMA_DANCE_RELATIVE_DIR);
}

function normalizeRelativeAssetPath(inputPath) {
  return String(inputPath || "")
    .replace(/\\/g, "/")
    .replace(/^\/+/, "")
    .replace(/\.\.(\/|\\)/g, "")
    .trim();
}

function isInside(parentPath, childPath) {
  const relative = path.relative(parentPath, childPath);
  return !relative.startsWith("..") && !path.isAbsolute(relative);
}

function resolveAssetPath(relativePath) {
  const normalized = normalizeRelativeAssetPath(relativePath);
  return path.resolve(getAssetRoot(), normalized);
}

function toAssetUrl(relativePath) {
  const normalized = normalizeRelativeAssetPath(relativePath);
  const encoded = normalized.split("/").map(encodeURIComponent).join("/");
  return `catbot-file:///${encoded}`;
}

function getAssetRelativePathFromRequestUrl(requestUrl) {
  const parsed = new URL(requestUrl);
  const hostPart = decodeURIComponent(parsed.host || "").replace(/^\/+/, "");
  const pathPart = decodeURIComponent(parsed.pathname || "").replace(/^\/+/, "");
  return normalizeRelativeAssetPath([hostPart, pathPart].filter(Boolean).join("/"));
}

function scanModelDirectory(rootDir, currentDir = rootDir, accumulator = { vrm: [], live2d: [] }) {
  if (!fs.existsSync(currentDir)) {
    return accumulator;
  }

  const entries = fs.readdirSync(currentDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === "models.zip") {
      continue;
    }
    const absolutePath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) {
      scanModelDirectory(rootDir, absolutePath, accumulator);
      continue;
    }

    const relativePath = path.relative(getAssetRoot(), absolutePath).replace(/\\/g, "/");
    const lower = entry.name.toLowerCase();
    if (lower.endsWith(".vrm")) {
      accumulator.vrm.push(relativePath);
    } else if (lower.endsWith(".model3.json")) {
      accumulator.live2d.push(relativePath);
    }
  }

  return accumulator;
}

function scanVrmaDirectory(rootDir, currentDir = rootDir, accumulator = []) {
  if (!fs.existsSync(currentDir)) {
    return accumulator;
  }

  const entries = fs.readdirSync(currentDir, { withFileTypes: true });
  for (const entry of entries) {
    const absolutePath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) {
      scanVrmaDirectory(rootDir, absolutePath, accumulator);
      continue;
    }
    if (!entry.name.toLowerCase().endsWith(".vrma")) {
      continue;
    }
    const relativePath = path.relative(getAssetRoot(), absolutePath).replace(/\\/g, "/");
    accumulator.push({
      name: entry.name.replace(/\.vrma$/i, ""),
      path: relativePath
    });
  }

  return accumulator;
}

function getAvailableModels() {
  const scanned = scanModelDirectory(getModelRoot());
  scanned.vrm.sort((a, b) => a.localeCompare(b));
  scanned.live2d.sort((a, b) => a.localeCompare(b));
  return scanned;
}

function getAvailableVrmaAnimations() {
  const dance = scanVrmaDirectory(getVrmaDanceRoot())
    .sort((a, b) => a.path.localeCompare(b.path));
  return {
    dance,
    danceDirectory: VRMA_DANCE_RELATIVE_DIR.replace(/\\/g, "/")
  };
}

function pickDefaultModel(mode, configValue) {
  const preferred = normalizeRelativeAssetPath(configValue);
  const resolvedPreferred = preferred ? resolveAssetPath(preferred) : "";
  if (preferred && fs.existsSync(resolvedPreferred)) {
    return preferred;
  }
  const scanned = getAvailableModels();
  if (mode === "live2d") {
    return scanned.live2d[0] || scanned.vrm[0] || "";
  }
  return scanned.vrm[0] || scanned.live2d[0] || "";
}

function readBootstrapConfig() {
  const bootstrap = loadJsonFile(BOOTSTRAP_CONFIG_FILE, {});
  const env = readSimpleEnv(ENV_FILE);
  const projectEnv = readSimpleEnv(PROJECT_ENV_FILE);

  const envConfig = {};
  if (env.ELECTRON_AVATAR_MODE) {
    envConfig.mode = env.ELECTRON_AVATAR_MODE.toLowerCase() === "live2d" ? "live2d" : "vrm";
  }
  if (env.ELECTRON_CATBOT_WEB_URL) {
    envConfig.webClientUrl = env.ELECTRON_CATBOT_WEB_URL;
  }
  if (env.ELECTRON_CATBOT_PROXY_URL) {
    envConfig.proxyBaseUrl = env.ELECTRON_CATBOT_PROXY_URL;
  }
  if (env.ELECTRON_DEFAULT_MODEL_PATH) {
    envConfig.modelPath = env.ELECTRON_DEFAULT_MODEL_PATH;
  }
  if (env.ELECTRON_START_CONTROL_PANEL) {
    envConfig.showControlPanelOnLaunch = env.ELECTRON_START_CONTROL_PANEL.toLowerCase() === "true";
  }
  if (env.ELECTRON_START_TO_TRAY) {
    envConfig.startToTray = env.ELECTRON_START_TO_TRAY.toLowerCase() === "true";
  }
  if (env.ELECTRON_LAUNCH_AT_LOGIN) {
    envConfig.launchAtLogin = env.ELECTRON_LAUNCH_AT_LOGIN.toLowerCase() === "true";
  }
  if (env.ELECTRON_START_CLICK_THROUGH) {
    envConfig.clickThrough = env.ELECTRON_START_CLICK_THROUGH.toLowerCase() === "true";
  }
  if (env.ELECTRON_ALWAYS_ON_TOP) {
    envConfig.alwaysOnTop = env.ELECTRON_ALWAYS_ON_TOP.toLowerCase() === "true";
  }
  if (env.ELECTRON_WINDOW_OPACITY) {
    envConfig.opacity = Number(env.ELECTRON_WINDOW_OPACITY);
  }
  if (env.ELECTRON_AVATAR_SCALE) {
    envConfig.scale = Number(env.ELECTRON_AVATAR_SCALE);
  }
  if (env.ELECTRON_TTS_ENDPOINT) {
    envConfig.ttsEndpoint = env.ELECTRON_TTS_ENDPOINT;
  } else if (projectEnv.TTS_ENDPOINT) {
    envConfig.ttsEndpoint = projectEnv.TTS_ENDPOINT;
  }
  if (env.ELECTRON_TTS_MODEL) {
    envConfig.ttsModel = env.ELECTRON_TTS_MODEL;
  } else if (projectEnv.TTS_MODEL) {
    envConfig.ttsModel = projectEnv.TTS_MODEL;
  }
  if (env.ELECTRON_TTS_VOICE) {
    envConfig.ttsVoice = env.ELECTRON_TTS_VOICE;
  } else if (projectEnv.TTS_VOICE) {
    envConfig.ttsVoice = projectEnv.TTS_VOICE;
  }
  if (env.ELECTRON_CHAT_ENDPOINT) {
    envConfig.chatEndpoint = env.ELECTRON_CHAT_ENDPOINT;
  }
  if (env.ELECTRON_CHAT_MODEL) {
    envConfig.chatModel = env.ELECTRON_CHAT_MODEL;
  }
  if (env.ELECTRON_CHAT_SYSTEM_PROMPT) {
    envConfig.chatSystemPrompt = env.ELECTRON_CHAT_SYSTEM_PROMPT;
  }
  if (env.ELECTRON_SPEAK_CHAT_REPLIES) {
    envConfig.speakChatReplies = env.ELECTRON_SPEAK_CHAT_REPLIES.toLowerCase() === "true";
  }
  if (env.ELECTRON_AUTO_COMPANION_MODE) {
    envConfig.autoCompanionMode = env.ELECTRON_AUTO_COMPANION_MODE.toLowerCase() === "true";
  }
  if (env.ELECTRON_AUTO_COMPANION_SCREEN) {
    envConfig.autoCompanionScreenContext = env.ELECTRON_AUTO_COMPANION_SCREEN.toLowerCase() === "true";
  }
  if (env.ELECTRON_AUTO_COMPANION_DANCE) {
    envConfig.autoCompanionDance = env.ELECTRON_AUTO_COMPANION_DANCE.toLowerCase() === "true";
  }
  if (env.ELECTRON_TRUST_LOCAL_CERTIFICATES) {
    envConfig.trustLocalCertificates = env.ELECTRON_TRUST_LOCAL_CERTIFICATES.toLowerCase() === "true";
  }

  return deepMerge(bootstrap, envConfig);
}

function isDeveloperControlPanelEnabled() {
  const env = readSimpleEnv(ENV_FILE);
  return String(env.ELECTRON_ENABLE_CONTROL_PANEL || process.env.ELECTRON_ENABLE_CONTROL_PANEL || "")
    .trim()
    .toLowerCase() === "true";
}

function getBootstrapProviderApiKey() {
  const env = readSimpleEnv(ENV_FILE);
  return String(env.ELECTRON_CHAT_API_KEY || process.env.ELECTRON_CHAT_API_KEY || "").trim();
}

function normalizeActionHarnessWindowInfo(value = {}) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const hwnd = actionHarness.normalizeHwnd(value.hwnd);
  const rect = value.rect && typeof value.rect === "object" && !Array.isArray(value.rect) ? value.rect : {};
  const width = Math.round(Number(rect.width) || 0);
  const height = Math.round(Number(rect.height) || 0);
  if (!hwnd || width <= 0 || height <= 0) {
    return null;
  }
  return {
    hwnd,
    title: String(value.title || "").trim(),
    pid: Number.isFinite(Number(value.pid)) ? Number(value.pid) : 0,
    processName: String(value.processName || value.process || "").trim(),
    rect: {
      x: Math.round(Number(rect.x) || 0),
      y: Math.round(Number(rect.y) || 0),
      width,
      height,
      right: Math.round(Number(rect.right) || Number(rect.x) + width || 0),
      bottom: Math.round(Number(rect.bottom) || Number(rect.y) + height || 0)
    }
  };
}

function normalizeActionHarnessLoopBudget(value) {
  const number = Math.round(Number(value));
  if (number === -1) {
    return -1;
  }
  if (!Number.isFinite(number)) {
    return DESKTOP_ACTION_HARNESS_DEFAULT_LOOP_BUDGET;
  }
  return Math.max(1, Math.min(DESKTOP_ACTION_HARNESS_MAX_LOOP_BUDGET, number));
}

function normalizeActionHarnessNudgeInterval(value) {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) {
    return DESKTOP_ACTION_HARNESS_DEFAULT_NUDGE_INTERVAL;
  }
  return Math.max(0, Math.min(DESKTOP_ACTION_HARNESS_MAX_NUDGE_INTERVAL, number));
}

function normalizeActionHarnessActionDelayMs(value) {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) {
    return DESKTOP_ACTION_HARNESS_POST_ACTION_CAPTURE_DELAY_MS;
  }
  return Math.max(0, Math.min(DESKTOP_ACTION_HARNESS_MAX_ACTION_DELAY_MS, number));
}

function normalizeActionHarnessCaptureMaxImageWidth(value) {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) {
    return DESKTOP_ACTION_HARNESS_CAPTURE_MAX_IMAGE_WIDTH;
  }
  return Math.max(
    DESKTOP_ACTION_HARNESS_CAPTURE_MIN_IMAGE_WIDTH,
    Math.min(DESKTOP_ACTION_HARNESS_CAPTURE_MAX_ALLOWED_IMAGE_WIDTH, number)
  );
}

function normalizeActionHarnessCaptureJpegQuality(value) {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) {
    return DESKTOP_ACTION_HARNESS_CAPTURE_JPEG_QUALITY;
  }
  return Math.max(
    DESKTOP_ACTION_HARNESS_CAPTURE_MIN_JPEG_QUALITY,
    Math.min(DESKTOP_ACTION_HARNESS_CAPTURE_MAX_JPEG_QUALITY, number)
  );
}

function normalizeActionHarnessState(value = {}) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const targetWindow = normalizeActionHarnessWindowInfo(source.targetWindow);
  const status = String(source.status || (source.playMode ? "ready" : "idle")).trim() || "idle";
  return {
    playMode: Boolean(source.playMode),
    status,
    targetWindow,
    grid: actionHarness.normalizeGrid(source.grid || {}),
    loopBudget: normalizeActionHarnessLoopBudget(source.loopBudget),
    nudgeInterval: normalizeActionHarnessNudgeInterval(source.nudgeInterval),
    actionDelayMs: normalizeActionHarnessActionDelayMs(source.actionDelayMs),
    captureMaxImageWidth: normalizeActionHarnessCaptureMaxImageWidth(source.captureMaxImageWidth),
    captureJpegQuality: normalizeActionHarnessCaptureJpegQuality(source.captureJpegQuality),
    armStartedAt: Number.isFinite(Number(source.armStartedAt)) ? Number(source.armStartedAt) : 0,
    armEndsAt: Number.isFinite(Number(source.armEndsAt)) ? Number(source.armEndsAt) : 0,
    lastCaptureAt: Number.isFinite(Number(source.lastCaptureAt)) ? Number(source.lastCaptureAt) : 0,
    lastActionAt: Number.isFinite(Number(source.lastActionAt)) ? Number(source.lastActionAt) : 0,
    lastAction: String(source.lastAction || "").slice(0, 180),
    lastError: String(source.lastError || "").slice(0, 300)
  };
}

function getDefaultActionHarnessState() {
  return normalizeActionHarnessState({
    playMode: false,
    status: "idle",
    grid: {
      columns: actionHarness.DEFAULT_GRID_COLUMNS,
      rows: actionHarness.DEFAULT_GRID_ROWS
    },
    loopBudget: DESKTOP_ACTION_HARNESS_DEFAULT_LOOP_BUDGET,
    nudgeInterval: DESKTOP_ACTION_HARNESS_DEFAULT_NUDGE_INTERVAL,
    actionDelayMs: DESKTOP_ACTION_HARNESS_POST_ACTION_CAPTURE_DELAY_MS,
    captureMaxImageWidth: DESKTOP_ACTION_HARNESS_CAPTURE_MAX_IMAGE_WIDTH,
    captureJpegQuality: DESKTOP_ACTION_HARNESS_CAPTURE_JPEG_QUALITY,
    armStartedAt: 0,
    armEndsAt: 0
  });
}

function isOutdatedActionHarnessDefaultGrid(grid = {}) {
  const columns = Number(grid.columns);
  const rows = Number(grid.rows);
  return (
    columns === 12 && rows === 9 ||
    columns === 48 && rows === 32
  );
}

const DEFAULT_STATE = (() => {
  const bootstrap = readBootstrapConfig();
  const merged = deepMerge(
    {
      mode: "vrm",
      modelPath: "model_avatar/CATBot/CATBot.vrm",
      scale: 1,
      opacity: 1,
      clickThrough: true,
      alwaysOnTop: true,
      moveMode: false,
      visible: true,
      quickHudVisible: false,
      showControlPanelOnLaunch: false,
      startToTray: false,
      launchAtLogin: false,
      expression: "neutral",
      transientExpression: false,
      speechBubbleText: "",
      speechTriggerId: 0,
      speechDurationMs: 2600,
      webClientUrl: "",
      proxyBaseUrl: DEFAULT_PROXY_BASE_URL,
      ttsEndpoint: "",
      ttsModel: "tts-1",
      ttsVoice: "alloy",
      chatEndpoint: DEFAULT_CHAT_ENDPOINT,
      chatModel: "",
      chatSystemPrompt: "You are CATBot, a concise desktop companion. Give helpful, practical answers in a few sentences unless the user asks for detail.",
      desktopChatHistory: [],
      speakChatReplies: true,
      screenContextMode: false,
      webcamMode: false,
      autoCompanionMode: false,
      autoCompanionScreenContext: true,
      autoCompanionDance: true,
      actionHarness: getDefaultActionHarnessState(),
      trustLocalCertificates: true,
      defaultCompanionId: "",
      activeCompanionId: "",
      activeCompanionName: "",
      vrmTransforms: {},
      windowBounds: {
        x: 80,
        y: 80,
        width: 480,
        height: 640
      },
      controlBounds: {
        x: 620,
        y: 120,
        width: 420,
        height: 720
      },
      webClientBounds: {
        x: 1080,
        y: 80,
        width: 1120,
        height: 820
      }
    },
    bootstrap
  );
  merged.mode = merged.mode === "live2d" ? "live2d" : "vrm";
  merged.modelPath = pickDefaultModel(merged.mode, merged.modelPath);
  return merged;
})();

let state = deepMerge(DEFAULT_STATE, loadJsonFile(USER_STATE_FILE, {}));
let desktopAuth = loadDesktopAuth();
saveDesktopAuth();
const migratedProviderApiKey = String(state.chatApiKey || "").trim() || getBootstrapProviderApiKey();
if (migratedProviderApiKey && !desktopAuth.chatApiKey) {
  desktopAuth.chatApiKey = migratedProviderApiKey;
  saveDesktopAuth();
}
delete state.chatApiKey;
state.mode = state.mode === "live2d" ? "live2d" : "vrm";
state.modelPath = pickDefaultModel(state.mode, state.modelPath);
if (state.moveMode) {
  state.moveMode = false;
  state.clickThrough = true;
}
state.quickHudVisible = false;
state.chatEndpoint = normalizeEndpointString(state.chatEndpoint || DEFAULT_CHAT_ENDPOINT);
state.chatModel = String(state.chatModel || "").trim();
state.chatSystemPrompt = String(state.chatSystemPrompt || DEFAULT_STATE.chatSystemPrompt || "").trim();
state.desktopChatHistory = normalizeDesktopChatHistory(state.desktopChatHistory);
state.speakChatReplies = state.speakChatReplies !== false;
state.screenContextMode = Boolean(state.screenContextMode);
state.webcamMode = Boolean(state.webcamMode);
state.autoCompanionMode = Boolean(state.autoCompanionMode);
state.autoCompanionScreenContext = state.autoCompanionScreenContext !== false;
state.autoCompanionDance = state.autoCompanionDance !== false;
state.actionHarness = normalizeActionHarnessState(state.actionHarness);
if (isOutdatedActionHarnessDefaultGrid(state.actionHarness.grid)) {
  state.actionHarness.grid = {
    columns: actionHarness.DEFAULT_GRID_COLUMNS,
    rows: actionHarness.DEFAULT_GRID_ROWS
  };
}
state.actionHarness.playMode = false;
state.actionHarness.status = "idle";
state.actionHarness.lastError = "";
state.trustLocalCertificates = state.trustLocalCertificates !== false;
state.defaultCompanionId = String(state.defaultCompanionId || "").trim();
state.activeCompanionId = String(state.activeCompanionId || "").trim();
state.activeCompanionName = String(state.activeCompanionName || "").trim();
state.expression = "neutral";
state.transientExpression = false;
state.speechBubbleText = "";
state.speechTriggerId = 0;
state.speechDurationMs = 2600;
state.webClientUrl = normalizeUrlString(state.webClientUrl);
if (state.webClientUrl && !isSafeExternalUrl(state.webClientUrl)) {
  appendRuntimeLog(`[security] discarded unsafe web client URL: ${state.webClientUrl}`);
  state.webClientUrl = "";
}
state.proxyBaseUrl = normalizeUrlString(state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);

function saveState() {
  const {
    chatApiKey: _chatApiKey,
    chatApiKeyConfigured: _chatApiKeyConfigured,
    transientExpression: _transientExpression,
    ...persistedState
  } = state;
  if (state.transientExpression) {
    persistedState.expression = "neutral";
  }
  persistedState.actionHarness = normalizeActionHarnessState({
    ...(persistedState.actionHarness || {}),
    playMode: false,
    status: "idle",
    lastError: ""
  });
  saveJsonFile(USER_STATE_FILE, {
    ...persistedState,
    moveMode: false,
    quickHudVisible: false
  });
}

function canEncryptDesktopSecret() {
  try {
    return Boolean(safeStorage?.isEncryptionAvailable?.());
  } catch (_) {
    return false;
  }
}

function protectDesktopSecret(value) {
  const text = String(value || "");
  if (!text) {
    return null;
  }
  if (!canEncryptDesktopSecret()) {
    if (String(process.env.ELECTRON_ALLOW_PLAINTEXT_AUTH_STORAGE || "").toLowerCase() === "true") {
      return { encoding: "plain", value: text };
    }
    appendRuntimeLog("[security] Electron safeStorage is unavailable; secret was not persisted.");
    return null;
  }
  return {
    encoding: "safeStorage",
    value: safeStorage.encryptString(text).toString("base64")
  };
}

function unprotectDesktopSecret(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  if (value.encoding === "plain") {
    return String(value.value || "").trim();
  }
  if (value.encoding === "safeStorage" && value.value && canEncryptDesktopSecret()) {
    try {
      return safeStorage.decryptString(Buffer.from(String(value.value), "base64")).trim();
    } catch (error) {
      appendRuntimeLog(`[security] failed to decrypt desktop secret: ${String(error?.message || error)}`);
      return "";
    }
  }
  return "";
}

function loadDesktopAuth() {
  const saved = loadJsonFile(USER_AUTH_FILE, {});
  const accessToken = unprotectDesktopSecret(saved.accessTokenSecret || saved.accessToken);
  const tokenUsable = isDesktopJwtTokenUsable(accessToken);
  return {
    accessToken: tokenUsable ? accessToken : "",
    username: tokenUsable ? String(saved.username || "").trim() : "",
    chatApiKey: unprotectDesktopSecret(saved.chatApiKeySecret || saved.chatApiKey)
  };
}

function saveDesktopAuth() {
  saveJsonFile(USER_AUTH_FILE, {
    version: 2,
    accessTokenSecret: protectDesktopSecret(desktopAuth.accessToken),
    username: desktopAuth.username || "",
    chatApiKeySecret: protectDesktopSecret(desktopAuth.chatApiKey)
  });
}

function getCatbotAuthCookieName() {
  const env = readSimpleEnv(ENV_FILE);
  const projectEnv = readSimpleEnv(PROJECT_ENV_FILE);
  return String(process.env.AUTH_COOKIE_NAME || projectEnv.AUTH_COOKIE_NAME || env.AUTH_COOKIE_NAME || DEFAULT_AUTH_COOKIE_NAME).trim() || DEFAULT_AUTH_COOKIE_NAME;
}

function getDesktopProxyCookieOrigin() {
  const parsed = parseUrlLike(state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (!parsed || (parsed.protocol !== "http:" && parsed.protocol !== "https:")) {
    return "";
  }
  return parsed.origin;
}

function clearDesktopProxyAuthCookie() {
  const cookieOrigin = getDesktopProxyCookieOrigin();
  const cookieName = getCatbotAuthCookieName();
  if (!cookieOrigin || !cookieName || !session?.defaultSession?.cookies?.remove) {
    return Promise.resolve(false);
  }
  return session.defaultSession.cookies.remove(cookieOrigin, cookieName)
    .then(() => true)
    .catch((error) => {
      appendRuntimeLog(`[auth] failed to clear proxy auth cookie: ${String(error?.message || error)}`);
      return false;
    });
}

function hasUsableDesktopAuthToken(options = {}) {
  if (isDesktopJwtTokenUsable(desktopAuth?.accessToken)) {
    return true;
  }
  if (desktopAuth?.accessToken || desktopAuth?.username) {
    clearDesktopAuth({
      applyWindowState: options.applyWindowState === true,
      broadcast: options.broadcast === true
    });
  }
  return false;
}

function requireDesktopAuthToken(actionLabel = "using protected proxy routes") {
  if (!hasUsableDesktopAuthToken({ applyWindowState: true, broadcast: true })) {
    throw new Error(`Sign in to the CATBot proxy before ${actionLabel}.`);
  }
  return desktopAuth.accessToken;
}

function setDesktopAuthGreeting() {
  clearDesktopReplyEmotionResetTimer();
  state.expression = "neutral";
  state.transientExpression = false;
  state.speechBubbleText = DESKTOP_AUTH_GREETING_TEXT;
  state.speechDurationMs = calculateSpeechDurationMs(DESKTOP_AUTH_GREETING_TEXT);
  state.speechTriggerId = Date.now();
}

function clearDesktopAuth(options = {}) {
  const shouldApplyWindowState = options.applyWindowState !== false;
  const shouldBroadcast = options.broadcast !== false;
  desktopAuth = { ...desktopAuth, accessToken: "", username: "" };
  saveDesktopAuth();
  clearDesktopProxyAuthCookie();
  if (shouldApplyWindowState) {
    applyAvatarWindowState();
  }
  if (shouldBroadcast) {
    broadcastState();
  }
  return getDesktopAuthStatus({ valid: false });
}

function clearProviderApiKey() {
  desktopAuth = { ...desktopAuth, chatApiKey: "" };
  saveDesktopAuth();
  broadcastState();
  return getSafeState();
}

function getDesktopAuthStatus(extra = {}) {
  const authenticated = hasUsableDesktopAuthToken({ applyWindowState: false, broadcast: false });
  return {
    authenticated,
    required: !authenticated,
    username: desktopAuth.username || "",
    ...extra
  };
}

function isDesktopAuthRequired() {
  return !hasUsableDesktopAuthToken({ applyWindowState: false, broadcast: false });
}

function getProxyAuthHeaders() {
  return hasUsableDesktopAuthToken({ applyWindowState: true, broadcast: true }) ? { "X-Auth-Token": desktopAuth.accessToken } : {};
}

function getProviderAuthorizationHeader(apiKey) {
  const normalized = String(apiKey || "").trim();
  return normalized ? { Authorization: `Bearer ${normalized}` } : {};
}

function shouldAllowEndpointOverride(endpoint, providerApiKey = "", proxyAuthToken = "") {
  const normalized = normalizeEndpointString(endpoint);
  if (!normalized) {
    return false;
  }
  if (String(providerApiKey || "").trim() || String(proxyAuthToken || "").trim()) {
    return true;
  }
  const parsed = parseUrlLike(normalized);
  return Boolean(parsed && isLocalCertificateHostname(parsed.hostname));
}

function buildProxyRequestHeaders(headers = {}, options = {}) {
  return {
    ...headers,
    ...getProxyAuthHeaders(),
    ...getProviderAuthorizationHeader(options.providerApiKey)
  };
}

function getSafeState() {
  const { chatApiKey: _chatApiKey, ...safeState } = state || {};
  return {
    ...safeState,
    soulPrompt: getSoulPromptText(),
    authRequired: isDesktopAuthRequired(),
    chatApiKeyConfigured: Boolean(desktopAuth?.chatApiKey)
  };
}

function normalizeCompanionId(value) {
  return String(value || "").trim();
}

function normalizeCompanionModelPath(value) {
  return normalizeRelativeAssetPath(value).replace(/^\.\//, "");
}

function getDesktopVrmTransform(sourceState = state) {
  const modelPath = sourceState?.modelPath || "";
  const transform = sourceState?.vrmTransforms?.[modelPath] || {};
  return {
    scale: Number.isFinite(Number(transform.scale)) ? Number(transform.scale) : Math.max(0.25, Math.min(2.5, Number(sourceState?.scale) || 1)),
    positionX: Number.isFinite(Number(transform.positionX)) ? Number(transform.positionX) : 0,
    positionY: Number.isFinite(Number(transform.positionY)) ? Number(transform.positionY) : 0,
    rotation: Number.isFinite(Number(transform.rotation)) ? Number(transform.rotation) : 0
  };
}

function getDesktopCompanionSettingsSnapshot(sourceState = state) {
  const mode = sourceState.mode === "live2d" ? "live2d" : "vrm";
  const vrmTransform = getDesktopVrmTransform(sourceState);
  const isVrm = mode === "vrm";
  return {
    assistantName: "CATBot",
    systemPrompt: String(sourceState.chatSystemPrompt || "").trim(),
    endpoint: String(sourceState.chatEndpoint || "").trim(),
    baseModel: String(sourceState.chatModel || "").trim(),
    toolModel: String(sourceState.chatModel || "").trim(),
    visionModel: "",
    ttsService: "openai",
    ttsEndpoint: String(sourceState.ttsEndpoint || "").trim(),
    ttsModel: String(sourceState.ttsModel || "tts-1").trim() || "tts-1",
    ttsVoice: String(sourceState.ttsVoice || "alloy").trim() || "alloy",
    muteMode: sourceState.speakChatReplies === false,
    avatarMode: mode,
    vrmModel: isVrm ? sourceState.modelPath || "" : "",
    live2dModel: isVrm ? "" : sourceState.modelPath || "",
    vrmScale: vrmTransform.scale,
    vrmPositionX: vrmTransform.positionX,
    vrmPositionY: vrmTransform.positionY,
    vrmRotation: vrmTransform.rotation,
    vrmPositions: sourceState.vrmTransforms || {},
    desktop: {
      mode,
      modelPath: sourceState.modelPath || "",
      scale: Number.isFinite(Number(sourceState.scale)) ? Number(sourceState.scale) : 1,
      opacity: Number.isFinite(Number(sourceState.opacity)) ? Number(sourceState.opacity) : 1,
      chatEndpoint: String(sourceState.chatEndpoint || "").trim(),
      chatModel: String(sourceState.chatModel || "").trim(),
      chatSystemPrompt: String(sourceState.chatSystemPrompt || "").trim(),
      proxyBaseUrl: String(sourceState.proxyBaseUrl || "").trim(),
      webClientUrl: String(sourceState.webClientUrl || "").trim(),
      ttsEndpoint: String(sourceState.ttsEndpoint || "").trim(),
      ttsModel: String(sourceState.ttsModel || "tts-1").trim() || "tts-1",
      ttsVoice: String(sourceState.ttsVoice || "alloy").trim() || "alloy",
      speakChatReplies: sourceState.speakChatReplies !== false,
      screenContextMode: Boolean(sourceState.screenContextMode),
      webcamMode: Boolean(sourceState.webcamMode),
      autoCompanionMode: Boolean(sourceState.autoCompanionMode),
      autoCompanionScreenContext: sourceState.autoCompanionScreenContext !== false,
      autoCompanionDance: sourceState.autoCompanionDance !== false,
      vrmTransforms: sourceState.vrmTransforms || {}
    }
  };
}

function applyCompanionSettingsToDesktopState(settings = {}) {
  const safeSettings = settings && typeof settings === "object" && !Array.isArray(settings) ? settings : {};
  const desktop = safeSettings.desktop && typeof safeSettings.desktop === "object" && !Array.isArray(safeSettings.desktop)
    ? safeSettings.desktop
    : {};
  const nextStatePatch = {};

  const systemPrompt = desktop.chatSystemPrompt ?? safeSettings.systemPrompt;
  if (typeof systemPrompt === "string") {
    nextStatePatch.chatSystemPrompt = systemPrompt.trim();
  }

  const chatEndpoint = desktop.chatEndpoint ?? safeSettings.chatEndpoint ?? safeSettings.endpoint;
  if (typeof chatEndpoint === "string") {
    nextStatePatch.chatEndpoint = normalizeEndpointString(chatEndpoint);
  }

  const chatModel = desktop.chatModel ?? safeSettings.chatModel ?? safeSettings.baseModel ?? safeSettings.toolModel;
  if (typeof chatModel === "string") {
    nextStatePatch.chatModel = chatModel.trim();
  }

  for (const [desktopKey, stateKey] of [
    ["proxyBaseUrl", "proxyBaseUrl"],
    ["webClientUrl", "webClientUrl"],
    ["ttsEndpoint", "ttsEndpoint"],
    ["ttsModel", "ttsModel"],
    ["ttsVoice", "ttsVoice"]
  ]) {
    if (typeof desktop[desktopKey] === "string") {
      nextStatePatch[stateKey] = desktop[desktopKey].trim();
    }
  }
  if (typeof safeSettings.ttsEndpoint === "string" && !nextStatePatch.ttsEndpoint) {
    nextStatePatch.ttsEndpoint = safeSettings.ttsEndpoint.trim();
  }
  if (typeof safeSettings.ttsModel === "string" && !nextStatePatch.ttsModel) {
    nextStatePatch.ttsModel = safeSettings.ttsModel.trim();
  }
  if (typeof safeSettings.ttsVoice === "string" && !nextStatePatch.ttsVoice) {
    nextStatePatch.ttsVoice = safeSettings.ttsVoice.trim();
  }

  if (typeof desktop.speakChatReplies === "boolean") {
    nextStatePatch.speakChatReplies = desktop.speakChatReplies;
  } else if (typeof safeSettings.muteMode === "boolean") {
    nextStatePatch.speakChatReplies = !safeSettings.muteMode;
  }
  if (typeof desktop.screenContextMode === "boolean") {
    nextStatePatch.screenContextMode = desktop.screenContextMode;
  }
  if (typeof desktop.webcamMode === "boolean") {
    nextStatePatch.webcamMode = desktop.webcamMode;
  }
  if (typeof desktop.autoCompanionMode === "boolean") {
    nextStatePatch.autoCompanionMode = desktop.autoCompanionMode;
  }
  if (typeof desktop.autoCompanionScreenContext === "boolean") {
    nextStatePatch.autoCompanionScreenContext = desktop.autoCompanionScreenContext;
  }
  if (typeof desktop.autoCompanionDance === "boolean") {
    nextStatePatch.autoCompanionDance = desktop.autoCompanionDance;
  }

  const mode = desktop.mode === "live2d" || safeSettings.avatarMode === "live2d" ? "live2d" : "vrm";
  nextStatePatch.mode = mode;
  const companionModelPath = normalizeCompanionModelPath(
    desktop.modelPath || (mode === "live2d" ? safeSettings.live2dModel : safeSettings.vrmModel)
  );
  if (companionModelPath) {
    nextStatePatch.modelPath = pickDefaultModel(mode, companionModelPath);
  } else if (state.mode !== mode) {
    nextStatePatch.modelPath = pickDefaultModel(mode, "");
  }

  if (Number.isFinite(Number(desktop.opacity))) {
    nextStatePatch.opacity = Number(desktop.opacity);
  }
  const companionScale = Number.isFinite(Number(desktop.scale))
    ? Number(desktop.scale)
    : Number.isFinite(Number(mode === "vrm" ? safeSettings.vrmScale : safeSettings.live2dScale))
      ? Number(mode === "vrm" ? safeSettings.vrmScale : safeSettings.live2dScale)
      : NaN;
  if (Number.isFinite(companionScale)) {
    nextStatePatch.scale = companionScale;
  }

  const nextModelPath = nextStatePatch.modelPath || state.modelPath;
  if (mode === "vrm" && nextModelPath) {
    const existingTransforms = state.vrmTransforms && typeof state.vrmTransforms === "object" && !Array.isArray(state.vrmTransforms)
      ? state.vrmTransforms
      : {};
    const companionTransforms = desktop.vrmTransforms && typeof desktop.vrmTransforms === "object" && !Array.isArray(desktop.vrmTransforms)
      ? desktop.vrmTransforms
      : safeSettings.vrmPositions && typeof safeSettings.vrmPositions === "object" && !Array.isArray(safeSettings.vrmPositions)
        ? safeSettings.vrmPositions
        : {};
    const loadedTransform = companionTransforms[nextModelPath] || companionTransforms[normalizeCompanionModelPath(nextModelPath)] || {};
    const transform = {
      ...getDesktopVrmTransform({ ...state, modelPath: nextModelPath }),
      ...(loadedTransform && typeof loadedTransform === "object" ? loadedTransform : {})
    };
    for (const [settingKey, transformKey] of [
      ["vrmScale", "scale"],
      ["vrmPositionX", "positionX"],
      ["vrmPositionY", "positionY"],
      ["vrmRotation", "rotation"]
    ]) {
      if (Number.isFinite(Number(safeSettings[settingKey]))) {
        transform[transformKey] = Number(safeSettings[settingKey]);
      }
    }
    nextStatePatch.vrmTransforms = {
      ...existingTransforms,
      [nextModelPath]: transform
    };
  }

  state = deepMerge(state, nextStatePatch);
  state.mode = state.mode === "live2d" ? "live2d" : "vrm";
  state.modelPath = pickDefaultModel(state.mode, state.modelPath);
  state.opacity = Math.max(0.35, Math.min(1, Number(state.opacity) || 1));
  state.scale = Math.max(0.25, Math.min(2.5, Number(state.scale) || 1));
  state.chatEndpoint = normalizeEndpointString(state.chatEndpoint || DEFAULT_CHAT_ENDPOINT);
  state.chatModel = String(state.chatModel || "").trim();
  state.chatSystemPrompt = String(state.chatSystemPrompt || DEFAULT_STATE.chatSystemPrompt || "").trim();
  state.proxyBaseUrl = normalizeUrlString(state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  state.webClientUrl = normalizeUrlString(state.webClientUrl);
  if (state.webClientUrl && !isSafeExternalUrl(state.webClientUrl)) {
    appendRuntimeLog(`[security] discarded unsafe web client URL: ${state.webClientUrl}`);
    state.webClientUrl = "";
  }
  state.ttsEndpoint = normalizeUrlString(state.ttsEndpoint);
  state.ttsModel = String(state.ttsModel || "tts-1").trim() || "tts-1";
  state.ttsVoice = String(state.ttsVoice || "alloy").trim() || "alloy";
  state.speakChatReplies = state.speakChatReplies !== false;
  state.webcamMode = Boolean(state.webcamMode);
  state.autoCompanionMode = Boolean(state.autoCompanionMode);
  state.autoCompanionScreenContext = state.autoCompanionScreenContext !== false;
  state.autoCompanionDance = state.autoCompanionDance !== false;
}

function getCompanionProxyOrigin(payload = {}) {
  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload({ ...payload, proxyBaseUrl: requestedProxyBaseUrl });
  if (!apiOrigin) {
    throw new Error("Configure the CATBot API/proxy URL before using character profiles.");
  }
  requireDesktopAuthToken("using character profiles");
  return apiOrigin;
}

async function requestCompanionApi(pathSuffix, options = {}) {
  const apiOrigin = getCompanionProxyOrigin(options.payload || {});
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), Math.max(1500, Number(options.timeoutMs) || 10000));
  try {
    const headers = {
      Accept: "application/json",
      ...getProxyAuthHeaders(),
      ...(options.body == null ? {} : { "Content-Type": "application/json" })
    };
    const response = await net.fetch(`${apiOrigin}${pathSuffix}`, {
      method: options.method || "GET",
      headers,
      body: options.body == null ? undefined : JSON.stringify(options.body),
      signal: controller.signal
    });
    const responseText = await response.text();
    const data = parseJsonOrNull(responseText);
    if (!response.ok) {
      const detail = data?.detail || data?.error || responseText || `HTTP ${response.status}`;
      throw new Error(String(detail));
    }
    return data ?? {};
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Character profile request timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

async function listDesktopCompanions(payload = {}) {
  const data = await requestCompanionApi("/v1/companions", { payload });
  return Array.isArray(data) ? data : [];
}

async function getDesktopCompanion(companionId, payload = {}) {
  const id = normalizeCompanionId(companionId);
  if (!id) {
    throw new Error("Character profile id is required.");
  }
  return requestCompanionApi(`/v1/companions/${encodeURIComponent(id)}`, { payload });
}

async function createDesktopCompanion(payload = {}) {
  const name = String(payload.name || "").trim();
  if (!name) {
    throw new Error("Character profile name is required.");
  }
  const settings = getDesktopCompanionSettingsSnapshot(state);
  const created = await requestCompanionApi("/v1/companions", {
    method: "POST",
    payload,
    body: { name, settings }
  });
  if (created?.id && payload.activate !== false) {
    state.activeCompanionId = String(created.id);
    state.activeCompanionName = String(created.name || name);
  }
  if (created?.id && payload.setDefault) {
    state.defaultCompanionId = String(created.id);
  }
  saveState();
  broadcastState();
  return {
    companion: created,
    state: getSafeState()
  };
}

async function loadDesktopCompanion(companionId, payload = {}) {
  const companion = await getDesktopCompanion(companionId, payload);
  if (!companion?.settings) {
    throw new Error("Character profile has no settings to load.");
  }
  applyCompanionSettingsToDesktopState(companion.settings);
  state.activeCompanionId = String(companion.id || companionId);
  state.activeCompanionName = String(companion.name || companion.id || companionId);
  applyAvatarWindowState();
  saveState();
  broadcastState();
  return {
    companion,
    state: getSafeState()
  };
}

async function deleteDesktopCompanion(companionId, payload = {}) {
  const id = normalizeCompanionId(companionId);
  if (!id) {
    throw new Error("Character profile id is required.");
  }
  const result = await requestCompanionApi(`/v1/companions/${encodeURIComponent(id)}`, {
    method: "DELETE",
    payload
  });
  if (state.activeCompanionId === id) {
    state.activeCompanionId = "";
    state.activeCompanionName = "";
  }
  if (state.defaultCompanionId === id) {
    state.defaultCompanionId = "";
  }
  saveState();
  broadcastState();
  return {
    result,
    state: getSafeState()
  };
}

function setDefaultDesktopCompanion(companionId = "") {
  state.defaultCompanionId = normalizeCompanionId(companionId);
  saveState();
  broadcastState();
  return getSafeState();
}

async function loadDefaultDesktopCompanionAfterAuth() {
  const defaultId = normalizeCompanionId(state.defaultCompanionId);
  if (!defaultId || !hasUsableDesktopAuthToken({ applyWindowState: false, broadcast: false })) {
    return;
  }
  try {
    const companion = await getDesktopCompanion(defaultId, { proxyBaseUrl: state.proxyBaseUrl });
    if (!companion?.settings) {
      return;
    }
    applyCompanionSettingsToDesktopState(companion.settings);
    state.activeCompanionId = String(companion.id || defaultId);
    state.activeCompanionName = String(companion.name || companion.id || defaultId);
    saveState();
  } catch (error) {
    appendRuntimeLog(`[companions] failed to load default "${defaultId}": ${String(error?.message || error)}`);
  }
}

async function authenticateDesktopUser(payload = {}) {
  const action = payload.action === "signup" ? "signup" : "login";
  const username = String(payload.username || "").trim();
  const password = String(payload.password || "");
  if (!username || !password) {
    throw new Error("Username and password are required.");
  }

  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    throw new Error("CATBot API/proxy URL is not configured.");
  }

  const response = await net.fetch(`${apiOrigin}/v1/auth/${action}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify({ username, password })
  });
  const responseText = await response.text();
  const data = parseJsonOrNull(responseText);
  if (!response.ok || !data?.access_token) {
    const detail = data?.detail || data?.error || responseText || "Authentication failed.";
    throw new Error(String(detail));
  }

  desktopAuth = {
    ...desktopAuth,
    accessToken: String(data.access_token || "").trim(),
    username
  };
  saveDesktopAuth();
  setDesktopAuthGreeting();
  await loadDefaultDesktopCompanionAfterAuth();
  saveState();
  applyAvatarWindowState();
  broadcastState();
  return getDesktopAuthStatus({ valid: true });
}

async function verifyDesktopAuth(payload = {}) {
  if (!hasUsableDesktopAuthToken({ applyWindowState: true, broadcast: true })) {
    return getDesktopAuthStatus({ valid: false });
  }
  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    return getDesktopAuthStatus({ valid: false, error: "CATBot API/proxy URL is not configured." });
  }

  try {
    const response = await net.fetch(`${apiOrigin}/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${desktopAuth.accessToken}`,
        Accept: "application/json"
      }
    });
    const responseText = await response.text();
    const data = parseJsonOrNull(responseText);
    if (!response.ok) {
      clearDesktopAuth();
      return getDesktopAuthStatus({ valid: false, error: data?.detail || responseText || "Session expired." });
    }
    desktopAuth.username = String(data?.username || desktopAuth.username || "").trim();
    saveDesktopAuth();
    await loadDefaultDesktopCompanionAfterAuth();
    return getDesktopAuthStatus({ valid: true });
  } catch (error) {
    return getDesktopAuthStatus({ valid: false, error: String(error?.message || error || "Auth check failed.") });
  }
}

function coerceWindowBounds(bounds = {}, fallback = {}, minimum = {}) {
  const width = Math.max(Number(minimum.width) || 120, Math.round(Number(bounds.width) || Number(fallback.width) || 480));
  const height = Math.max(Number(minimum.height) || 120, Math.round(Number(bounds.height) || Number(fallback.height) || 640));
  const x = Math.round(Number.isFinite(Number(bounds.x)) ? Number(bounds.x) : Number(fallback.x) || 80);
  const y = Math.round(Number.isFinite(Number(bounds.y)) ? Number(bounds.y) : Number(fallback.y) || 80);
  return { x, y, width, height };
}

function clampNumber(value, min, max) {
  const minimum = Math.min(min, max);
  const maximum = Math.max(min, max);
  return Math.max(minimum, Math.min(maximum, value));
}

function getRectangleOverlapArea(bounds, area) {
  const left = Math.max(bounds.x, area.x);
  const top = Math.max(bounds.y, area.y);
  const right = Math.min(bounds.x + bounds.width, area.x + area.width);
  const bottom = Math.min(bounds.y + bounds.height, area.y + area.height);
  const visibleWidth = Math.max(0, right - left);
  const visibleHeight = Math.max(0, bottom - top);
  return visibleWidth * visibleHeight;
}

function getRectangleCenter(rectangle) {
  return {
    x: rectangle.x + rectangle.width / 2,
    y: rectangle.y + rectangle.height / 2
  };
}

function getNearestDisplayWorkArea(bounds) {
  const displays = screen.getAllDisplays();
  if (!displays.length) {
    return screen.getPrimaryDisplay().workArea;
  }

  let bestDisplay = displays[0];
  let bestOverlapArea = -1;
  for (const display of displays) {
    const overlapArea = getRectangleOverlapArea(bounds, display.workArea);
    if (overlapArea > bestOverlapArea) {
      bestDisplay = display;
      bestOverlapArea = overlapArea;
    }
  }
  if (bestOverlapArea > 0) {
    return bestDisplay.workArea;
  }

  const boundsCenter = getRectangleCenter(bounds);
  let nearestDistance = Infinity;
  for (const display of displays) {
    const displayCenter = getRectangleCenter(display.workArea);
    const distance = Math.hypot(boundsCenter.x - displayCenter.x, boundsCenter.y - displayCenter.y);
    if (distance < nearestDistance) {
      bestDisplay = display;
      nearestDistance = distance;
    }
  }
  return bestDisplay.workArea;
}

function clampBoundsToWorkArea(bounds, workArea, minimum = {}) {
  const availableWidth = Math.max(1, Math.round(Number(workArea.width) || 1));
  const availableHeight = Math.max(1, Math.round(Number(workArea.height) || 1));
  const minimumWidth = Math.min(Math.max(1, Math.round(Number(minimum.width) || 120)), availableWidth);
  const minimumHeight = Math.min(Math.max(1, Math.round(Number(minimum.height) || 120)), availableHeight);
  const width = Math.min(Math.max(minimumWidth, Math.round(Number(bounds.width) || minimumWidth)), availableWidth);
  const height = Math.min(Math.max(minimumHeight, Math.round(Number(bounds.height) || minimumHeight)), availableHeight);
  const minX = Math.round(Number(workArea.x) || 0);
  const minY = Math.round(Number(workArea.y) || 0);
  const maxX = Math.round(minX + availableWidth - width);
  const maxY = Math.round(minY + availableHeight - height);
  return {
    x: Math.round(clampNumber(Math.round(Number(bounds.x) || minX), minX, maxX)),
    y: Math.round(clampNumber(Math.round(Number(bounds.y) || minY), minY, maxY)),
    width,
    height
  };
}

function boundsEqual(first = {}, second = {}) {
  return (
    Math.round(Number(first.x) || 0) === Math.round(Number(second.x) || 0) &&
    Math.round(Number(first.y) || 0) === Math.round(Number(second.y) || 0) &&
    Math.round(Number(first.width) || 0) === Math.round(Number(second.width) || 0) &&
    Math.round(Number(first.height) || 0) === Math.round(Number(second.height) || 0)
  );
}

function centerBoundsInWorkArea(bounds, workArea) {
  const width = Math.min(Math.max(1, bounds.width), Math.max(1, workArea.width));
  const height = Math.min(Math.max(1, bounds.height), Math.max(1, workArea.height));
  return {
    x: Math.round(workArea.x + (workArea.width - width) / 2),
    y: Math.round(workArea.y + (workArea.height - height) / 2),
    width,
    height
  };
}

function normalizeBoundsForDisplays(bounds, fallback, minimum = {}) {
  const coerced = coerceWindowBounds(bounds, fallback, minimum);
  try {
    return clampBoundsToWorkArea(coerced, getNearestDisplayWorkArea(coerced), minimum);
  } catch (_) {
    return coerced;
  }
}

function getWindowBoundsConfig(windowKey) {
  if (windowKey === "controlBounds") {
    return {
      fallback: DEFAULT_STATE.controlBounds,
      minimum: { width: 420, height: 560 }
    };
  }
  if (windowKey === "webClientBounds") {
    return {
      fallback: DEFAULT_STATE.webClientBounds,
      minimum: { width: 720, height: 520 }
    };
  }
  return {
    fallback: DEFAULT_STATE.windowBounds,
    minimum: { width: 240, height: 320 }
  };
}

function constrainWindowBounds(windowKey, bounds) {
  const config = getWindowBoundsConfig(windowKey);
  return normalizeBoundsForDisplays(bounds, config.fallback, config.minimum);
}

function constrainBrowserWindowToDisplays(windowKey, browserWindow, options = {}) {
  if (!browserWindow || browserWindow.isDestroyed()) {
    return null;
  }
  const normalized = constrainWindowBounds(windowKey, browserWindow.getBounds());
  if (!boundsEqual(browserWindow.getBounds(), normalized)) {
    browserWindow.setBounds(normalized);
  }
  if (options.persist !== false) {
    state[windowKey] = normalized;
  }
  if (options.save) {
    saveState();
  }
  return normalized;
}

function normalizePersistedWindowBounds() {
  state.windowBounds = constrainWindowBounds("windowBounds", state.windowBounds);
  state.controlBounds = constrainWindowBounds("controlBounds", state.controlBounds);
  state.webClientBounds = constrainWindowBounds("webClientBounds", state.webClientBounds);
  saveState();
}

function keepAllWindowsInsideDesktopBounds(options = {}) {
  state.windowBounds = constrainWindowBounds("windowBounds", state.windowBounds);
  state.controlBounds = constrainWindowBounds("controlBounds", state.controlBounds);
  state.webClientBounds = constrainWindowBounds("webClientBounds", state.webClientBounds);

  constrainBrowserWindowToDisplays("windowBounds", avatarWindow, { persist: true });
  constrainBrowserWindowToDisplays("controlBounds", controlWindow, { persist: true });
  constrainBrowserWindowToDisplays("webClientBounds", webClientWindow, { persist: true });
  applyAvatarWindowShape();

  if (options.save !== false) {
    saveState();
  }
  if (options.broadcast) {
    broadcastState();
  }
}

function registerDisplayBoundaryHandlers() {
  const handleDisplayBoundaryChange = () => {
    keepAllWindowsInsideDesktopBounds({ save: true, broadcast: true });
  };
  screen.on("display-added", handleDisplayBoundaryChange);
  screen.on("display-removed", handleDisplayBoundaryChange);
  screen.on("display-metrics-changed", handleDisplayBoundaryChange);
}

function applyLaunchAtLoginSetting() {
  if (!app.isReady()) {
    return;
  }
  if (process.platform !== "win32" && process.platform !== "darwin") {
    return;
  }
  try {
    app.setLoginItemSettings({
      openAtLogin: Boolean(state.launchAtLogin)
    });
  } catch (error) {
    console.warn("Failed to update launch-at-login setting:", error);
  }
}

function installLocalCertificateTrust() {
  session.defaultSession.setCertificateVerifyProc((request, callback) => {
    if (state?.trustLocalCertificates) {
      const trustedHostnames = getTrustedLocalCertificateHostnames();
      const requestHostname = normalizeHostname(request?.hostname);
      if (trustedHostnames.has(requestHostname)) {
        callback(CERT_VERIFY_RESULT_OK);
        return;
      }
    }
    callback(CERT_VERIFY_RESULT_DEFAULT);
  });

  app.on("certificate-error", (event, _webContents, url, _error, _certificate, callback) => {
    if (isTrustedLocalCertificateUrl(url)) {
      event.preventDefault();
      callback(true);
      return;
    }
    callback(false);
  });
}

function installMediaPermissionHandler() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const url = webContents.getURL();
    const isLocalRenderer = url.startsWith("file://") || url.startsWith("app://") || url === "";
    callback(isLocalRenderer && (permission === "media" || permission === "audioCapture" || permission === "videoCapture" || permission === "camera"));
  });
}

function broadcastState() {
  const safeState = getSafeState();
  for (const win of [avatarWindow, controlWindow, webClientWindow]) {
    if (win && !win.isDestroyed()) {
      win.webContents.send("desktop:state-changed", safeState);
    }
  }
  updateTrayMenu();
}

function clearDesktopReplyEmotionResetTimer() {
  desktopReplyEmotionResetToken += 1;
  if (desktopReplyEmotionResetTimer) {
    clearTimeout(desktopReplyEmotionResetTimer);
    desktopReplyEmotionResetTimer = null;
  }
}

function resetTransientDesktopExpression(expectedSpeechTriggerId = 0) {
  if (!state?.transientExpression) {
    return;
  }
  if (expectedSpeechTriggerId && Number(state.speechTriggerId) !== Number(expectedSpeechTriggerId)) {
    return;
  }
  state.expression = "neutral";
  state.transientExpression = false;
  saveState();
  broadcastState();
}

function scheduleDesktopReplyEmotionReset(delayMs, expectedSpeechTriggerId = 0) {
  clearDesktopReplyEmotionResetTimer();
  const token = desktopReplyEmotionResetToken;
  const timeoutMs = Math.max(0, Number(delayMs) || 0);
  desktopReplyEmotionResetTimer = setTimeout(() => {
    if (token !== desktopReplyEmotionResetToken) {
      return;
    }
    desktopReplyEmotionResetTimer = null;
    resetTransientDesktopExpression(expectedSpeechTriggerId);
  }, timeoutMs);
}

function applyAvatarWindowState() {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    return;
  }
  enforceAvatarOverlayWindow();
  constrainBrowserWindowToDisplays("windowBounds", avatarWindow, { persist: true });
  const authRequired = isDesktopAuthRequired();
  const hudVisible = Boolean(state.quickHudVisible);
  const interactiveVisible = hudVisible || authRequired;
  try {
    if (typeof avatarWindow.isFocusable !== "function" || avatarWindow.isFocusable() !== interactiveVisible) {
      avatarWindow.setFocusable(interactiveVisible);
    }
    if (!interactiveVisible && (typeof avatarWindow.isFocused !== "function" || avatarWindow.isFocused())) {
      avatarWindow.blur();
    }
  } catch (_) {
    // ignore focusability issues on unsupported platforms
  }
  enforceAvatarOverlayWindow();
  avatarWindow.setAlwaysOnTop(Boolean(state.alwaysOnTop), state.alwaysOnTop ? "screen-saver" : "normal");
  avatarWindow.setOpacity(Math.max(0.35, Math.min(1, Number(state.opacity) || 1)));
  avatarWindow.setIgnoreMouseEvents(Boolean(state.clickThrough) && !Boolean(state.moveMode) && !interactiveVisible, {
    forward: true
  });

  if (state.visible || authRequired) {
    if (interactiveVisible) {
      avatarWindow.show();
      avatarWindow.focus();
      enforceAvatarOverlayWindow();
    } else if (!avatarWindow.isVisible()) {
      avatarWindow.showInactive();
    }
  } else if (avatarWindow.isVisible()) {
    avatarWindow.hide();
  }
}

function enforceAvatarOverlayWindow() {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    return;
  }
  avatarWindow.setTitle("");
  avatarWindow.setMenu(null);
  avatarWindow.setMenuBarVisibility(false);
  avatarWindow.setSkipTaskbar(true);
  avatarWindow.setHasShadow(false);
  avatarWindow.setBackgroundColor("#00000000");
  if (typeof avatarWindow.setWindowButtonVisibility === "function") {
    avatarWindow.setWindowButtonVisibility(false);
  }
  applyAvatarWindowShape();
}

function applyAvatarWindowShape() {
  if (!avatarWindow || avatarWindow.isDestroyed() || typeof avatarWindow.setShape !== "function") {
    return;
  }
  const bounds = avatarWindow.getBounds();
  const width = Math.max(1, Math.round(bounds.width));
  const height = Math.max(1, Math.round(bounds.height - AVATAR_WINDOW_TOP_CHROME_GUARD_PX));
  avatarWindow.setShape([
    {
      x: 0,
      y: AVATAR_WINDOW_TOP_CHROME_GUARD_PX,
      width,
      height
    }
  ]);
}

function updateWindowBoundsFromInstance(windowKey, browserWindow) {
  if (!browserWindow || browserWindow.isDestroyed()) {
    return;
  }
  if (windowKey === "windowBounds" && avatarDragState) {
    return;
  }
  constrainBrowserWindowToDisplays(windowKey, browserWindow, { persist: true });
  saveState();
}

function getAvatarWindowOptions() {
  return {
    ...constrainWindowBounds("windowBounds", state.windowBounds),
    title: "",
    frame: false,
    thickFrame: false,
    focusable: false,
    acceptFirstMouse: false,
    movable: true,
    transparent: true,
    hasShadow: false,
    roundedCorners: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    backgroundColor: "#00000000",
    autoHideMenuBar: true,
    icon: getLogoPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  };
}

function createAvatarWindow() {
  avatarWindow = new BrowserWindow(getAvatarWindowOptions());
  enforceAvatarOverlayWindow();

  avatarWindow.loadFile(path.join(ELECTRON_ROOT, "renderer", "avatar", "avatar.html"));
  avatarWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  avatarWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    const text = String(message || "");
    if (level >= 2 || text.includes("[tts pcm]")) {
      appendRuntimeLog(`[avatar console:${level}] ${message} (${sourceId}:${line})`);
    }
  });
  avatarWindow.webContents.on("render-process-gone", (_event, details) => {
    appendRuntimeLog(`[avatar render-process-gone] ${JSON.stringify(details)}`);
  });
  avatarWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    appendRuntimeLog(`[avatar did-fail-load] ${errorCode} ${errorDescription} ${validatedURL}`);
  });
  avatarWindow.webContents.on("did-finish-load", () => {
    enforceAvatarOverlayWindow();
    avatarWindow.webContents.insertCSS(`
      html,
      body {
        background: transparent !important;
        background-color: rgba(0, 0, 0, 0) !important;
        overflow: hidden !important;
      }
    `).catch(() => {});
  });
  avatarWindow.on("page-title-updated", (event) => {
    event.preventDefault();
    if (!avatarWindow || avatarWindow.isDestroyed()) {
      return;
    }
    avatarWindow.setTitle("");
  });
  avatarWindow.once("ready-to-show", () => {
    enforceAvatarOverlayWindow();
    applyAvatarWindowState();
    if (state.visible) {
      avatarWindow.showInactive();
    }
  });
  avatarWindow.on("move", () => updateWindowBoundsFromInstance("windowBounds", avatarWindow));
  avatarWindow.on("resize", applyAvatarWindowShape);
  avatarWindow.on("focus", () => {
    if (isQuitting || !avatarWindow || avatarWindow.isDestroyed()) {
      return;
    }
    if (!state.quickHudVisible) {
      avatarWindow.blur();
    }
    enforceAvatarOverlayWindow();
  });
  avatarWindow.on("blur", () => {
    if (isQuitting || state.moveMode || state.quickHudVisible) {
      return;
    }
    applyAvatarWindowState();
  });
}

function createControlWindow() {
  controlWindow = new BrowserWindow({
    ...constrainWindowBounds("controlBounds", state.controlBounds),
    minWidth: 360,
    minHeight: 560,
    autoHideMenuBar: true,
    show: false,
    backgroundColor: "#0f1117",
    title: "CATBot Desktop Avatar",
    icon: getLogoPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  controlWindow.loadFile(path.join(ELECTRON_ROOT, "renderer", "control-panel", "control-panel.html"));
  if (state.showControlPanelOnLaunch && !state.startToTray) {
    controlWindow.once("ready-to-show", () => controlWindow.show());
  }
  controlWindow.on("move", () => updateWindowBoundsFromInstance("controlBounds", controlWindow));
  controlWindow.on("resize", () => updateWindowBoundsFromInstance("controlBounds", controlWindow));
  controlWindow.on("close", (event) => {
    if (isQuitting) {
      return;
    }
    event.preventDefault();
    controlWindow.hide();
  });
}

function isAllowedWebClientNavigation(targetUrl) {
  const normalizedTarget = normalizeUrlString(targetUrl);
  if (!normalizedTarget) {
    return false;
  }
  if (normalizedTarget.startsWith("data:text/html,")) {
    return !state.webClientUrl;
  }
  const configuredUrl = normalizeUrlString(state.webClientUrl);
  if (!configuredUrl) {
    return false;
  }
  try {
    const target = new URL(normalizedTarget);
    const configured = new URL(configuredUrl);
    return target.origin === configured.origin;
  } catch {
    return false;
  }
}

function installWebClientNavigationGuards(windowInstance) {
  windowInstance.webContents.setWindowOpenHandler(({ url }) => {
    if (url) {
      openSafeExternalUrl(url);
    }
    return { action: "deny" };
  });
  windowInstance.webContents.on("will-navigate", (event, url) => {
    if (isAllowedWebClientNavigation(url)) {
      return;
    }
    event.preventDefault();
    if (url) {
      openSafeExternalUrl(url);
    }
  });
}

function createWebClientWindow() {
  webClientWindow = new BrowserWindow({
    ...constrainWindowBounds("webClientBounds", state.webClientBounds),
    minWidth: 720,
    minHeight: 520,
    autoHideMenuBar: true,
    show: false,
    backgroundColor: "#0f1117",
    title: "CATBot Web Client",
    icon: getLogoPath(),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  installWebClientNavigationGuards(webClientWindow);

  if (state.webClientUrl) {
    webClientWindow.loadURL(state.webClientUrl);
  } else {
    webClientWindow.loadURL("data:text/html,<html><body style='font-family:Segoe UI;background:#0f1117;color:#eff6ff;display:grid;place-items:center;height:100vh;margin:0'>Configure a CATBot web client URL in the desktop control panel.</body></html>");
  }
  webClientWindow.on("move", () => updateWindowBoundsFromInstance("webClientBounds", webClientWindow));
  webClientWindow.on("resize", () => updateWindowBoundsFromInstance("webClientBounds", webClientWindow));
  webClientWindow.on("close", (event) => {
    if (isQuitting) {
      return;
    }
    event.preventDefault();
    webClientWindow.hide();
  });
}

function showControlPanel() {
  if (!isDeveloperControlPanelEnabled()) {
    return false;
  }
  if (!controlWindow || controlWindow.isDestroyed()) {
    createControlWindow();
  }
  constrainBrowserWindowToDisplays("controlBounds", controlWindow, { persist: true, save: true });
  controlWindow.show();
  controlWindow.focus();
  return true;
}

function showWebClientWindow() {
  if (!state.webClientUrl) {
    return false;
  }
  if (!webClientWindow || webClientWindow.isDestroyed()) {
    createWebClientWindow();
  } else if (webClientWindow.webContents.getURL() !== state.webClientUrl) {
    webClientWindow.loadURL(state.webClientUrl);
  }
  constrainBrowserWindowToDisplays("webClientBounds", webClientWindow, { persist: true, save: true });
  webClientWindow.show();
  webClientWindow.focus();
  return true;
}

function showExistingInstance() {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    createAvatarWindow();
  }
  state.visible = true;
  state.moveMode = false;
  state.clickThrough = true;
  state.quickHudVisible = true;
  applyAvatarWindowState();
  saveState();
  broadcastState();
}

function setQuickHudVisible(visible) {
  state.quickHudVisible = Boolean(visible);
  if (state.quickHudVisible) {
    state.visible = true;
    state.moveMode = false;
  }
  applyAvatarWindowState();
  saveState();
  broadcastState();
  return getSafeState();
}

function toggleQuickHud() {
  return setQuickHudVisible(!state.quickHudVisible);
}

function toggleMoveMode() {
  const enteringMoveMode = !state.moveMode;
  if (enteringMoveMode) {
    moveModeReturnHudVisible = Boolean(state.quickHudVisible);
  }
  state.moveMode = !state.moveMode;
  if (state.moveMode) {
    state.clickThrough = false;
    state.quickHudVisible = false;
  } else {
    avatarDragState = null;
    state.quickHudVisible = moveModeReturnHudVisible;
    moveModeReturnHudVisible = false;
  }
  applyAvatarWindowState();
  saveState();
  broadcastState();
  return getSafeState();
}

function toggleClickThrough() {
  state.clickThrough = !state.clickThrough;
  if (state.clickThrough) {
    state.moveMode = false;
    avatarDragState = null;
    if (!state.quickHudVisible) {
      applyAvatarWindowState();
    }
  }
  applyAvatarWindowState();
  saveState();
  broadcastState();
  return getSafeState();
}

function beginAvatarDrag(point = {}) {
  if (!state.moveMode || !avatarWindow || avatarWindow.isDestroyed()) {
    avatarDragState = null;
    return false;
  }
  const cursorPoint = screen.getCursorScreenPoint();
  avatarDragState = {
    startX: Number.isFinite(Number(point.screenX)) ? Number(point.screenX) : cursorPoint.x,
    startY: Number.isFinite(Number(point.screenY)) ? Number(point.screenY) : cursorPoint.y,
    bounds: avatarWindow.getBounds()
  };
  return true;
}

function dragAvatarWindow(point = {}) {
  if (!avatarDragState || !state.moveMode || !avatarWindow || avatarWindow.isDestroyed()) {
    return false;
  }
  const cursorPoint = screen.getCursorScreenPoint();
  const screenX = Number.isFinite(Number(point.screenX)) ? Number(point.screenX) : cursorPoint.x;
  const screenY = Number.isFinite(Number(point.screenY)) ? Number(point.screenY) : cursorPoint.y;
  const nextBounds = constrainWindowBounds("windowBounds", {
    ...avatarDragState.bounds,
    x: Math.round(avatarDragState.bounds.x + screenX - avatarDragState.startX),
    y: Math.round(avatarDragState.bounds.y + screenY - avatarDragState.startY)
  });
  avatarWindow.setBounds(nextBounds);
  return true;
}

function endAvatarDrag() {
  if (!avatarDragState) {
    return getSafeState();
  }
  avatarDragState = null;
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    state.windowBounds = constrainWindowBounds("windowBounds", avatarWindow.getBounds());
    if (!boundsEqual(avatarWindow.getBounds(), state.windowBounds)) {
      avatarWindow.setBounds(state.windowBounds);
    }
    applyAvatarWindowState();
    saveState();
    broadcastState();
  }
  return getSafeState();
}

function centerAvatarOnPrimaryDisplay() {
  const fallbackBounds = coerceWindowBounds(state.windowBounds, DEFAULT_STATE.windowBounds, { width: 240, height: 320 });
  let nextBounds = fallbackBounds;
  try {
    nextBounds = clampBoundsToWorkArea(centerBoundsInWorkArea(fallbackBounds, screen.getPrimaryDisplay().workArea), screen.getPrimaryDisplay().workArea, { width: 240, height: 320 });
  } catch (_) {
    // keep fallback bounds if display lookup fails
  }
  state.windowBounds = nextBounds;
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.setBounds(nextBounds);
  }
  applyAvatarWindowState();
  saveState();
  broadcastState();
  return getSafeState();
}

function updateState(partialState = {}) {
  const patch = partialState && typeof partialState === "object" && !Array.isArray(partialState) ? { ...partialState } : {};
  const hasExpressionPatch = Object.prototype.hasOwnProperty.call(patch, "expression");
  const hasWindowBoundsPatch = Object.prototype.hasOwnProperty.call(patch, "windowBounds");
  if (Object.prototype.hasOwnProperty.call(patch, "chatApiKey")) {
    desktopAuth.chatApiKey = String(patch.chatApiKey || "").trim();
    saveDesktopAuth();
    delete patch.chatApiKey;
  }
  delete patch.chatApiKeyConfigured;
  if (hasExpressionPatch) {
    clearDesktopReplyEmotionResetTimer();
    if (!Object.prototype.hasOwnProperty.call(patch, "transientExpression")) {
      patch.transientExpression = false;
    }
  }
  if (Object.prototype.hasOwnProperty.call(patch, "actionHarness")) {
    patch.actionHarness = normalizeActionHarnessState(deepMerge(state.actionHarness || getDefaultActionHarnessState(), patch.actionHarness));
  }

  state = deepMerge(state, patch);
  delete state.chatApiKey;
  state.mode = state.mode === "live2d" ? "live2d" : "vrm";
  state.modelPath = pickDefaultModel(state.mode, state.modelPath);

  if (typeof state.opacity !== "number" || Number.isNaN(state.opacity)) {
    state.opacity = 1;
  }
  if (typeof state.scale !== "number" || Number.isNaN(state.scale)) {
    state.scale = 1;
  }
  state.opacity = Math.max(0.35, Math.min(1, state.opacity));
  state.scale = Math.max(0.25, Math.min(2.5, state.scale));
  if (state.clickThrough) {
    state.moveMode = false;
  }
  state.quickHudVisible = Boolean(state.quickHudVisible);
  if (!state.visible) {
    state.quickHudVisible = false;
  }
  state.webClientUrl = normalizeUrlString(state.webClientUrl);
  if (state.webClientUrl && !isSafeExternalUrl(state.webClientUrl)) {
    appendRuntimeLog(`[security] discarded unsafe web client URL: ${state.webClientUrl}`);
    state.webClientUrl = "";
  }

  if (webClientWindow && !webClientWindow.isDestroyed()) {
    const currentUrl = webClientWindow.webContents.getURL();
    if (state.webClientUrl && currentUrl !== state.webClientUrl) {
      webClientWindow.loadURL(state.webClientUrl);
    }
  }

  if (typeof state.speechBubbleText !== "string") {
    state.speechBubbleText = "";
  }
  if (typeof state.expression !== "string" || !state.expression.trim()) {
    state.expression = "neutral";
  }
  state.transientExpression = Boolean(state.transientExpression);
  if (!Number.isFinite(state.speechTriggerId)) {
    state.speechTriggerId = 0;
  }
  if (!Number.isFinite(state.speechDurationMs)) {
    state.speechDurationMs = 2600;
  }
  state.launchAtLogin = Boolean(state.launchAtLogin);
  state.webClientUrl = normalizeUrlString(state.webClientUrl);
  state.proxyBaseUrl = normalizeUrlString(state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  state.ttsEndpoint = normalizeUrlString(state.ttsEndpoint);
  state.ttsModel = String(state.ttsModel || "tts-1").trim() || "tts-1";
  state.ttsVoice = String(state.ttsVoice || "alloy").trim() || "alloy";
  state.chatEndpoint = normalizeEndpointString(state.chatEndpoint || DEFAULT_CHAT_ENDPOINT);
  state.chatModel = String(state.chatModel || "").trim();
  state.chatSystemPrompt = String(state.chatSystemPrompt || "").trim();
  state.desktopChatHistory = normalizeDesktopChatHistory(state.desktopChatHistory);
  state.speakChatReplies = Boolean(state.speakChatReplies);
  state.screenContextMode = Boolean(state.screenContextMode);
  state.webcamMode = Boolean(state.webcamMode);
  state.autoCompanionMode = Boolean(state.autoCompanionMode);
  state.autoCompanionScreenContext = state.autoCompanionScreenContext !== false;
  state.autoCompanionDance = state.autoCompanionDance !== false;
  state.actionHarness = normalizeActionHarnessState(state.actionHarness);
  state.trustLocalCertificates = state.trustLocalCertificates !== false;
  state.defaultCompanionId = String(state.defaultCompanionId || "").trim();
  state.activeCompanionId = String(state.activeCompanionId || "").trim();
  state.activeCompanionName = String(state.activeCompanionName || "").trim();
  if (hasWindowBoundsPatch) {
    state.windowBounds = constrainWindowBounds("windowBounds", state.windowBounds);
    if (avatarWindow && !avatarWindow.isDestroyed()) {
      avatarWindow.setBounds(state.windowBounds);
      applyAvatarWindowShape();
    }
  }
  if (!state.vrmTransforms || typeof state.vrmTransforms !== "object" || Array.isArray(state.vrmTransforms)) {
    state.vrmTransforms = {};
  }

  applyAvatarWindowState();
  applyLaunchAtLoginSetting();
  saveState();
  broadcastState();
  return getSafeState();
}

function getActionHarnessTargetWindow() {
  return normalizeActionHarnessWindowInfo(state.actionHarness?.targetWindow);
}

function getWindowHandleString(browserWindow) {
  try {
    if (!browserWindow || browserWindow.isDestroyed()) {
      return "";
    }
    const handle = browserWindow.getNativeWindowHandle();
    if (!Buffer.isBuffer(handle) || handle.length < 4) {
      return "";
    }
    return handle.length >= 8
      ? handle.readBigUInt64LE(0).toString()
      : String(handle.readUInt32LE(0));
  } catch (_) {
    return "";
  }
}

function isOwnElectronWindowInfo(info = {}) {
  const hwnd = actionHarness.normalizeHwnd(info.hwnd);
  if (!hwnd) {
    return false;
  }
  const ownHandles = [
    getWindowHandleString(avatarWindow),
    getWindowHandleString(controlWindow),
    getWindowHandleString(webClientWindow)
  ].filter(Boolean);
  if (ownHandles.includes(hwnd)) {
    return true;
  }
  return Number(info.pid) === process.pid;
}

function getActionHarnessTargetRejectionReason(info = {}) {
  const target = normalizeActionHarnessWindowInfo(info);
  if (!target) {
    return "No usable foreground window was available.";
  }
  const title = String(target.title || "").trim();
  const processName = String(target.processName || info.processName || info.process || "").trim().toLowerCase();
  const rect = target.rect || {};
  if (isOwnElectronWindowInfo(target)) {
    return "Play mode cannot target the CATBot Electron window. Focus the game or app window and try again.";
  }
  if (Number(rect.width) < 240 || Number(rect.height) < 160) {
    return `The foreground window is too small for play mode (${rect.width}x${rect.height}). Focus the game or app window, not the taskbar or a toolbar.`;
  }
  if (!title && processName === "explorer") {
    return "The foreground target is the Windows shell/taskbar, not a playable app window. Focus the game or app window and start play mode again.";
  }
  return "";
}

function requireUsableActionHarnessTarget(info = {}) {
  const reason = getActionHarnessTargetRejectionReason(info);
  if (reason) {
    throw new Error(reason);
  }
  return normalizeActionHarnessWindowInfo(info);
}

async function getUsableForegroundActionHarnessTarget(options = {}) {
  const timeoutMs = Math.max(500, Math.round(Number(options.timeoutMs) || DESKTOP_ACTION_HARNESS_FOREGROUND_TIMEOUT_MS));
  const startedAt = Date.now();
  let lastError = null;
  do {
    try {
      return requireUsableActionHarnessTarget(await actionHarness.getForegroundWindowInfo());
    } catch (error) {
      lastError = error;
      await actionHarness.delay(DESKTOP_ACTION_HARNESS_FOREGROUND_POLL_MS);
    }
  } while (Date.now() - startedAt < timeoutMs);
  throw lastError || new Error("No usable foreground window was available.");
}

function setActionHarnessState(patch = {}) {
  state.actionHarness = normalizeActionHarnessState(deepMerge(state.actionHarness || getDefaultActionHarnessState(), patch));
}

async function withAvatarHiddenForActionCapture(work, options = {}) {
  if (options.hideAvatar !== true) {
    return work();
  }
  const shouldRestoreAvatar = Boolean(avatarWindow && !avatarWindow.isDestroyed() && avatarWindow.isVisible());
  try {
    if (shouldRestoreAvatar) {
      avatarWindow.hide();
      await actionHarness.delay(90);
    }
    return await work();
  } finally {
    if (shouldRestoreAvatar && avatarWindow && !avatarWindow.isDestroyed() && state.visible) {
      try {
        avatarWindow.showInactive();
      } catch (_) {
        // ignore restore failures
      }
      applyAvatarWindowState();
    }
  }
}

function maybeCleanupActionHarnessCaptures(force = false) {
  const now = Date.now();
  if (
    !force &&
    now - Number(actionHarnessRuntime.lastCaptureCleanupAt || 0) < DESKTOP_ACTION_HARNESS_CAPTURE_CLEANUP_INTERVAL_MS
  ) {
    return;
  }
  actionHarnessRuntime.lastCaptureCleanupAt = now;
  actionHarness.cleanupOldCaptures(ACTION_HARNESS_CAPTURE_DIR);
}

function getActionHarnessCapturePath() {
  fs.mkdirSync(ACTION_HARNESS_CAPTURE_DIR, { recursive: true });
  maybeCleanupActionHarnessCaptures();
  return path.join(ACTION_HARNESS_CAPTURE_DIR, `capture-${Date.now()}.${DESKTOP_ACTION_HARNESS_CAPTURE_EXTENSION}`);
}

function formatActionHarnessTargetLabel(targetWindow = getActionHarnessTargetWindow()) {
  if (!targetWindow) {
    return "no target window";
  }
  return targetWindow.title
    ? `"${targetWindow.title}" (${targetWindow.rect.width}x${targetWindow.rect.height})`
    : `window ${targetWindow.hwnd} (${targetWindow.rect.width}x${targetWindow.rect.height})`;
}

function ensureActionHarnessPlayMode() {
  const harnessState = normalizeActionHarnessState(state.actionHarness);
  const targetWindow = normalizeActionHarnessWindowInfo(harnessState.targetWindow);
  if (!harnessState.playMode || !targetWindow) {
    throw new Error("Desktop play mode is not active. Start play mode and designate a target window first.");
  }
  return { harnessState, targetWindow };
}

async function captureActionHarnessWindow(options = {}) {
  const { harnessState, targetWindow } = ensureActionHarnessPlayMode();
  const grid = actionHarness.normalizeGrid(options.grid || harnessState.grid);
  const outputPath = getActionHarnessCapturePath();
  const startedAt = Date.now();
  const capture = await withAvatarHiddenForActionCapture(
    () => actionHarness.captureWindowWithGrid({
      hwnd: targetWindow.hwnd,
      outputPath,
      grid,
      overlay: options.overlay !== false,
      format: options.format || DESKTOP_ACTION_HARNESS_CAPTURE_FORMAT,
      maxImageWidth: options.maxImageWidth || getActionHarnessCaptureMaxImageWidth(),
      jpegQuality: options.jpegQuality || getActionHarnessCaptureJpegQuality()
    }),
    { hideAvatar: options.hideAvatar === true }
  );
  const captureFinishedAt = Date.now();
  const normalizedTarget = normalizeActionHarnessWindowInfo(capture);
  if (!normalizedTarget) {
    throw new Error("The target window capture did not include valid window metadata.");
  }
  requireUsableActionHarnessTarget(normalizedTarget);
  actionHarnessRuntime.lastCapture = {
    ...normalizedTarget,
    grid,
    outputPath,
    capturedAt: Date.now()
  };
  setActionHarnessState({
    playMode: true,
    status: "ready",
    targetWindow: normalizedTarget,
    grid,
    lastCaptureAt: actionHarnessRuntime.lastCapture.capturedAt,
    lastError: ""
  });
  saveState();
  broadcastState();
  const dataUrlStartedAt = Date.now();
  const dataUrl = actionHarness.readCaptureDataUrl(outputPath);
  const dataUrlMs = Date.now() - dataUrlStartedAt;
  let fileBytes = 0;
  try {
    fileBytes = fs.statSync(outputPath).size;
  } catch (_) {
    fileBytes = 0;
  }
  appendRuntimeLog(`[desktop action harness] capture ready in ${Date.now() - startedAt}ms captureMs=${captureFinishedAt - startedAt} dataUrlMs=${dataUrlMs} fileBytes=${fileBytes} dataUrlChars=${dataUrl.length} image=${capture.image?.width || "?"}x${capture.image?.height || "?"} format=${capture.image?.format || "?"} quality=${capture.image?.jpegQuality || "?"}`);
  return {
    ...actionHarnessRuntime.lastCapture,
    image: capture.image || null,
    dataUrl
  };
}

async function startActionHarness(payload = {}) {
  const grid = actionHarness.normalizeGrid(payload.grid || state.actionHarness?.grid || {});
  const requestedArmDelay = Object.prototype.hasOwnProperty.call(payload, "armDelayMs")
    ? Number(payload.armDelayMs)
    : DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS;
  const armDelayMs = Math.max(0, Math.min(10000, Math.round(Number.isFinite(requestedArmDelay) ? requestedArmDelay : DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS)));
  const armStartedAt = Date.now();
  const armEndsAt = armDelayMs > 0 ? armStartedAt + armDelayMs : 0;
  resetActionHarnessPlayMemory();
  setActionHarnessState({
    playMode: false,
    status: "arming",
    targetWindow: null,
    grid,
    armStartedAt,
    armEndsAt,
    lastError: armDelayMs
      ? "Select the required active window now. Play mode will bind to the foreground window when the countdown ends."
      : ""
  });
  state.quickHudVisible = false;
  state.moveMode = false;
  state.clickThrough = true;
  state.visible = true;
  saveState();
  applyAvatarWindowState();
  broadcastState();

  try {
    if (armDelayMs) {
      await actionHarness.delay(armDelayMs);
    }
    if (state.actionHarness?.status !== "arming" || Number(state.actionHarness?.armStartedAt) !== armStartedAt) {
      appendRuntimeLog("[desktop action harness] arming cancelled before target bind.");
      return {
        state: getSafeState(),
        capture: null,
        captureError: ""
      };
    }
    appendRuntimeLog(`[desktop action harness] binding play mode target with grid ${grid.columns}x${grid.rows}`);
    const foreground = await getUsableForegroundActionHarnessTarget();
    setActionHarnessState({
      playMode: true,
      status: "ready",
      targetWindow: foreground,
      grid,
      armStartedAt: 0,
      armEndsAt: 0,
      lastCaptureAt: 0,
      lastActionAt: 0,
      lastAction: "",
      lastError: ""
    });
    saveState();
    broadcastState();
    let capture = null;
    let captureError = "";
    try {
      capture = await captureActionHarnessWindow({ grid });
    } catch (error) {
      captureError = String(error?.message || error || "Initial play-window capture failed.");
      appendRuntimeLog(`[desktop action harness] initial capture failed after target bind: ${captureError}`);
      setActionHarnessState({
        playMode: true,
        status: "ready",
        targetWindow: foreground,
        grid,
        armStartedAt: 0,
        armEndsAt: 0,
        lastError: `Play mode is on, but initial capture failed: ${captureError}`
      });
      saveState();
      broadcastState();
    }
    return {
      state: getSafeState(),
      capture,
      captureError
    };
  } catch (error) {
    appendRuntimeLog(`[desktop action harness] start failed: ${String(error?.message || error)}`);
    actionHarnessRuntime.lastCapture = null;
    setActionHarnessState({
      playMode: false,
      status: "error",
      targetWindow: null,
      grid,
      armStartedAt: 0,
      armEndsAt: 0,
      lastError: String(error?.message || error || "Could not start play mode.")
    });
    saveState();
    broadcastState();
    throw error;
  }
}

function stopActionHarness(reason = "Play mode stopped.") {
  actionHarnessRuntime.lastCapture = null;
  setActionHarnessState({
    playMode: false,
    status: "idle",
    targetWindow: null,
    armStartedAt: 0,
    armEndsAt: 0,
    lastError: "",
    lastAction: String(reason || "Play mode stopped.").slice(0, 180)
  });
  saveState();
  broadcastState();
  return getSafeState();
}

async function toggleActionHarness(payload = {}) {
  if (state.actionHarness?.playMode || state.actionHarness?.status === "arming") {
    return { state: stopActionHarness("Play mode stopped.") };
  }
  return startActionHarness(payload);
}

function getDesktopActionHarnessTooling() {
  if (!state.actionHarness?.playMode || !getActionHarnessTargetWindow()) {
    return { tools: [], promptLines: [] };
  }
  const grid = actionHarness.normalizeGrid(state.actionHarness.grid);
  const targetLabel = formatActionHarnessTargetLabel();
  return {
    tools: [
      {
        type: "function",
        function: {
          name: "desktop_action_capture_window",
          description: "Capture the designated play-mode window with an A-Z by 1-N grid overlay and return it as visual context.",
          parameters: {
            type: "object",
            properties: {
              columns: { type: "integer", minimum: 2, maximum: actionHarness.MAX_GRID_COLUMNS, description: "Optional grid column count. Default keeps the current play-mode grid." },
              rows: { type: "integer", minimum: 2, maximum: actionHarness.MAX_GRID_ROWS, description: "Optional grid row count. Default keeps the current play-mode grid." }
            },
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_mouse",
          description: "Move or click the mouse in the designated play-mode window by grid cell, or by window screenshot pixel coordinates when needed.",
          parameters: {
            type: "object",
            properties: {
              cell: { type: "string", description: "Grid cell label from the latest capture, such as A1, C4, or H7." },
              action: { type: "string", enum: ["move", "left_click", "double_click", "right_click", "middle_click"], description: "Mouse action to perform." },
              type: { type: "string", description: "Alias for action, accepted for local Qwen/Hermes fallback calls." },
              x: { type: "number", description: "Optional x coordinate from the play-mode screenshot if cell is not supplied." },
              y: { type: "number", description: "Optional y coordinate from the play-mode screenshot if cell is not supplied." },
              coordinateSpace: { type: "string", enum: ["window", "screen"], description: "Use window for screenshot-relative x/y, or screen for absolute desktop x/y." }
            },
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_key",
          description: "Press a discrete key in the designated play-mode window.",
          parameters: {
            type: "object",
            properties: {
              key: {
                type: "string",
                description: "Supported keys include up, down, left, right, space, enter, escape, tab, backspace, delete, w, a, s, d, q, e, r, f, z, x, c, v, and digits 0-9."
              },
              repeat: { type: "integer", minimum: 1, maximum: 20, description: "Number of presses." },
              holdMs: { type: "integer", minimum: 20, maximum: 5000, description: "How long each press is held." }
            },
            required: ["key"],
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_type_text",
          description: "Type short text into the designated play-mode window. Use only for text fields, not games.",
          parameters: {
            type: "object",
            properties: {
              text: { type: "string", maxLength: 1000, description: "Text to type." }
            },
            required: ["text"],
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_wait",
          description: "Wait briefly before the next capture or action.",
          parameters: {
            type: "object",
            properties: {
              ms: { type: "integer", minimum: 50, maximum: 10000, description: "Milliseconds to wait." }
            },
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_set_goal",
          description: "Update the current play-mode self-goal, strategy, and lessons learned from recent action outcomes. Use this at decision checkpoints when the environment or strategy changes.",
          parameters: {
            type: "object",
            properties: {
              goal: { type: "string", maxLength: 300, description: "Current short self-goal for the target window." },
              successAssessment: { type: "string", maxLength: 500, description: "What recent actions achieved or failed to achieve." },
              lesson: { type: "string", maxLength: 500, description: "Useful context to remember to improve future actions." },
              nextPlan: { type: "string", maxLength: 500, description: "Immediate strategy for the next one or more tool turns." }
            },
            additionalProperties: false
          }
        }
      },
      {
        type: "function",
        function: {
          name: "desktop_action_stop",
          description: "Stop desktop play mode and disable autonomous mouse/keyboard actions.",
          parameters: {
            type: "object",
            properties: {
              reason: { type: "string", maxLength: 200 }
            },
            additionalProperties: false
          }
        }
      }
    ],
    promptLines: [
      `Desktop play mode is ON for ${targetLabel}.`,
      "Desktop play mode tool format is strict. When taking a desktop action, output exactly one <tool_call> block and no other text.",
      `Use desktop_action_capture_window to inspect the target window. The overlay grid has columns A-${actionHarness.gridColumnLabel(grid.columns - 1)} and rows 1-${grid.rows}; always prefer grid cells like C4 or AA12 over raw pixels.`,
      "The grid origin is the top-left of the entire screenshot/window, including menus, score panels, sidebars, and ads. Never restart counting columns or rows at the game board or an app panel.",
      "Before clicking, verify the intended UI element is actually inside the chosen global grid cell. If the board starts at column M, a board piece cannot be in column F.",
      "Preferred mouse format: <tool_call>{\"name\":\"desktop_action_mouse\",\"arguments\":{\"cell\":\"G10\",\"action\":\"left_click\"}}</tool_call>.",
      "Allowed mouse actions are exactly: move, left_click, double_click, right_click, middle_click.",
      "Do not use x/y if a grid cell can be identified. Do not use type, button, click, screenX, or clientX in generated mouse calls.",
      "If a grid cell cannot be identified, use screenshot-relative pixels with coordinateSpace:\"window\": <tool_call>{\"name\":\"desktop_action_mouse\",\"arguments\":{\"x\":418,\"y\":424,\"coordinateSpace\":\"window\",\"action\":\"left_click\"}}</tool_call>.",
      "Keyboard format: <tool_call>{\"name\":\"desktop_action_key\",\"arguments\":{\"key\":\"space\"}}</tool_call>.",
      "Text-entry workflow: click the visible input field first, then call desktop_action_type_text with the exact string, then use Enter or a click only if the UI requires submission.",
      "Continuous play: after every tool result, inspect the latest attached screenshot and immediately output the next single <tool_call> if the goal is not complete.",
      "Use the provided play memory to learn from the session: avoid repeating moves that did not visibly help, prefer actions that changed the target, and update your next action from the latest screenshot.",
      "At decision checkpoints, judge whether recent actions succeeded. If strategy should change, call desktop_action_set_goal with the current self-goal, successAssessment, lesson, and nextPlan to enrich play memory.",
      "Do not narrate progress between play-mode actions. Use normal text only when the goal is complete, you are blocked, or the user needs to intervene.",
      "Use one desktop_action_mouse, desktop_action_key, desktop_action_type_text, desktop_action_wait, or desktop_action_set_goal per turn, then use the returned screenshot/tool result to decide the next action.",
      "Only act inside the designated play-mode window. Stop if the user asks, the target is unclear, or the action could affect the wrong app."
    ]
  };
}

function getDesktopToolResultVisualAttachments(toolResult) {
  if (!toolResult || typeof toolResult !== "object" || Array.isArray(toolResult)) {
    return [];
  }
  return Array.isArray(toolResult.visualAttachments)
    ? toolResult.visualAttachments.filter((item) => isDataImageUrl(item?.dataUrl))
    : [];
}

function isDesktopActionHarnessToolName(toolName) {
  return ACTION_HARNESS_TOOL_NAMES.has(String(toolName || "").trim());
}

function isDesktopActionHarnessInteractiveToolName(toolName) {
  return [
    "desktop_action_mouse",
    "desktop_action_key",
    "desktop_action_type_text",
    "desktop_action_wait"
  ].includes(String(toolName || "").trim());
}

function shouldNudgeDesktopActionHarnessContinue(reply) {
  const text = String(reply || "").toLowerCase();
  if (!text.trim()) {
    return true;
  }
  const explicitStopPatterns = [
    /\bplay mode complete\b/,
    /\bgoal complete\b/,
    /\btask complete\b/,
    /\bstop play mode\b/,
    /\bblocked\b/,
    /\bcannot continue\b/,
    /\bneed(?:s)? (?:user |your )?(?:direction|intervention|input)\b/,
    /\buser should\b/
  ];
  if (explicitStopPatterns.some((pattern) => pattern.test(text))) {
    return false;
  }
  return !(
    text.includes("complete and no further action") ||
    text.includes("no safe action available")
  );
}

function getActionHarnessLoopBudget() {
  return normalizeActionHarnessLoopBudget(state.actionHarness?.loopBudget);
}

function getActionHarnessNudgeInterval() {
  return normalizeActionHarnessNudgeInterval(state.actionHarness?.nudgeInterval);
}

function getActionHarnessActionDelayMs() {
  return normalizeActionHarnessActionDelayMs(state.actionHarness?.actionDelayMs);
}

function getActionHarnessCaptureMaxImageWidth() {
  return normalizeActionHarnessCaptureMaxImageWidth(state.actionHarness?.captureMaxImageWidth);
}

function getActionHarnessCaptureJpegQuality() {
  return normalizeActionHarnessCaptureJpegQuality(state.actionHarness?.captureJpegQuality);
}

function shouldRunActionHarnessLoopIteration(iteration, maxIterations) {
  return Boolean(state.actionHarness?.playMode) && (maxIterations < 0 || iteration < maxIterations);
}

function shouldInsertActionHarnessDecisionNudge(iteration, nudgeInterval) {
  return Boolean(state.actionHarness?.playMode) && nudgeInterval > 0 && iteration > 0 && iteration % nudgeInterval === 0;
}

function buildActionHarnessDecisionNudge(iteration) {
  return [
    `Play-mode decision checkpoint after ${iteration} action loop${iteration === 1 ? "" : "s"}.`,
    "Judge whether the last actions visibly helped, failed, or were inconclusive from the latest screenshot and play memory.",
    "Output exactly one desktop_action_set_goal tool call now with a concise current goal, successAssessment, lesson, and nextPlan so future actions have better context.",
    "Then continue play mode on the following turn with the next action."
  ].join(" ");
}

async function captureActionHarnessVisualAfterAction(actionLabel, delayMs = getActionHarnessActionDelayMs()) {
  if (delayMs > 0) {
    await actionHarness.delay(delayMs);
  }
  try {
    const capture = await captureActionHarnessWindow({ grid: state.actionHarness?.grid });
    const grid = actionHarness.normalizeGrid(capture.grid || state.actionHarness?.grid);
    const label = formatActionHarnessTargetLabel(capture);
    return {
      content: `Latest play-mode screenshot after ${actionLabel}: ${label}. Grid columns A-${actionHarness.gridColumnLabel(grid.columns - 1)}, rows 1-${grid.rows}. Continue with the next single tool call if the goal is not complete.`,
      visualAttachments: [
        {
          dataUrl: capture.dataUrl,
          label: "latest play-mode window screenshot with grid overlay"
        }
      ]
    };
  } catch (error) {
    const message = String(error?.message || error || "post-action capture failed");
    appendRuntimeLog(`[desktop action harness] post-action capture failed after ${actionLabel}: ${message}`);
    return {
      content: `Automatic screenshot after ${actionLabel} failed: ${message}. Call desktop_action_capture_window before choosing another action.`,
      visualAttachments: []
    };
  }
}

function normalizeDesktopActionMouseAction(args = {}) {
  const raw = String(
    args.action ||
    args.type ||
    args.mouseAction ||
    args.mouse_action ||
    args.click ||
    "left_click"
  ).trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (["move", "mousemove", "mouse_move", "hover"].includes(raw)) {
    return "move";
  }
  if (["left", "click", "leftclick", "left_click", "tap"].includes(raw)) {
    return "left_click";
  }
  if (["double", "doubleclick", "double_click", "dblclick", "dbl_click"].includes(raw)) {
    return "double_click";
  }
  if (["right", "rightclick", "right_click", "context", "context_click"].includes(raw)) {
    return "right_click";
  }
  if (["middle", "middleclick", "middle_click"].includes(raw)) {
    return "middle_click";
  }
  return "left_click";
}

async function executeDesktopActionHarnessTool(toolName, args = {}) {
  const normalizedArgs = args && typeof args === "object" && !Array.isArray(args) ? args : {};
  if (toolName === "desktop_action_stop") {
    const nextState = stopActionHarness(normalizedArgs.reason || "Play mode stopped by tool call.");
    return {
      success: true,
      message: "Desktop play mode stopped.",
      state: nextState
    };
  }
  const { targetWindow } = ensureActionHarnessPlayMode();

  if (toolName === "desktop_action_capture_window") {
    const grid = actionHarness.normalizeGrid({
      columns: normalizedArgs.columns || state.actionHarness?.grid?.columns,
      rows: normalizedArgs.rows || state.actionHarness?.grid?.rows
    });
    const capture = await captureActionHarnessWindow({ grid });
    const label = formatActionHarnessTargetLabel(capture);
    return {
      success: true,
      message: `Captured ${label} with grid A-${actionHarness.gridColumnLabel(grid.columns - 1)} by 1-${grid.rows}.`,
      content: `Use the attached play-mode screenshot to choose the next grid cell. Target window: ${label}. Grid columns A-${actionHarness.gridColumnLabel(grid.columns - 1)}, rows 1-${grid.rows}.`,
      visualAttachments: [
        {
          dataUrl: capture.dataUrl,
          label: "play-mode window screenshot with grid overlay"
        }
      ]
    };
  }

  if (toolName === "desktop_action_set_goal") {
    const goal = clipActionHarnessMemoryText(normalizedArgs.goal || "", 300);
    const successAssessment = clipActionHarnessMemoryText(normalizedArgs.successAssessment || normalizedArgs.assessment || "", 500);
    const lesson = clipActionHarnessMemoryText(normalizedArgs.lesson || normalizedArgs.memory || "", 500);
    const nextPlan = clipActionHarnessMemoryText(normalizedArgs.nextPlan || normalizedArgs.plan || "", 500);
    if (goal) {
      actionHarnessRuntime.currentGoal = goal;
    }
    appendActionHarnessPlayMemory({
      type: "self_goal",
      observation: [successAssessment, lesson].filter(Boolean).join(" "),
      result: [goal ? `Goal: ${goal}` : "", nextPlan ? `Next plan: ${nextPlan}` : ""].filter(Boolean).join(" ")
    });
    setActionHarnessState({
      playMode: true,
      status: "ready",
      lastActionAt: Date.now(),
      lastAction: "updated play memory",
      lastError: ""
    });
    saveState();
    broadcastState();
    const postActionCapture = await captureActionHarnessVisualAfterAction("play-memory update", 0);
    return {
      success: true,
      message: "Updated play-mode self-goal and memory.",
      content: `Updated play memory.${goal ? ` Current self-goal: ${goal}.` : ""}${successAssessment ? ` Success assessment: ${successAssessment}.` : ""}${lesson ? ` Lesson: ${lesson}.` : ""}${nextPlan ? ` Next plan: ${nextPlan}.` : ""}\n\n${postActionCapture.content}`,
      visualAttachments: postActionCapture.visualAttachments
    };
  }

  if (toolName === "desktop_action_mouse") {
    const capture = actionHarnessRuntime.lastCapture || await captureActionHarnessWindow({ grid: state.actionHarness?.grid });
    const point = actionHarness.mouseTargetToScreenPoint(normalizedArgs, capture);
    const requestedAction = normalizeDesktopActionMouseAction(normalizedArgs);
    const button =
      requestedAction === "right_click" ? "right" :
      requestedAction === "middle_click" ? "middle" :
      "left";
    const clicks =
      requestedAction === "move" ? 0 :
      requestedAction === "double_click" ? 2 :
      1;
    let inputResult = null;
    try {
      inputResult = await actionHarness.sendMouseInput({
        hwnd: targetWindow.hwnd,
        x: point.x,
        y: point.y,
        button,
        clicks,
        requireActive: false
      });
    } catch (error) {
      const message = String(error?.message || error || "Mouse action failed.");
      appendRuntimeLog(`[desktop action harness] mouse failed ${requestedAction} ${point.cell}: ${message}`);
      setActionHarnessState({
        playMode: true,
        status: "error",
        lastError: message,
        lastAction: `${requestedAction} ${point.cell} failed`
      });
      saveState();
      broadcastState();
      throw error;
    }
    const cursor = inputResult?.cursor || {};
    const cursorWarning = String(cursor.warning || inputResult?.warning || "").trim();
    appendRuntimeLog(`[desktop action harness] mouse ${requestedAction} ${point.cell} requested=(${point.x}, ${point.y}) cursor=(${cursor.x ?? "?"}, ${cursor.y ?? "?"}) focusMatched=${Boolean(inputResult?.focusMatched)} absoluteMoveUsed=${Boolean(cursor.absoluteMoveUsed)} verified=${cursor.verified !== false}`);
    if (cursorWarning) {
      appendRuntimeLog(`[desktop action harness] mouse warning ${requestedAction} ${point.cell}: ${cursorWarning}`);
    }
    setActionHarnessState({
      playMode: true,
      status: "ready",
      lastActionAt: Date.now(),
      lastAction: cursorWarning ? `${requestedAction} ${point.cell} (cursor warning)` : `${requestedAction} ${point.cell}`,
      lastError: ""
    });
    saveState();
    broadcastState();
    const postActionCapture = await captureActionHarnessVisualAfterAction(`${requestedAction} ${point.cell}`);
    const warningContent = cursorWarning ? `\n\nWarning: ${cursorWarning}` : "";
    return {
      success: true,
      message: clicks ? `Performed ${requestedAction} at ${point.cell}.` : `Moved mouse to ${point.cell}.`,
      content: `${requestedAction} at ${point.cell} (${point.x}, ${point.y}) in ${formatActionHarnessTargetLabel(targetWindow)}.${warningContent}\n\nIf the target did not visibly react, re-check that the chosen global grid cell is over the intended UI element; the grid covers the full screenshot, not just the game board.\n\n${postActionCapture.content}`,
      visualAttachments: postActionCapture.visualAttachments
    };
  }

  if (toolName === "desktop_action_key") {
    const key = String(normalizedArgs.key || "").trim();
    await actionHarness.sendKeyInput({
      hwnd: targetWindow.hwnd,
      key,
      repeat: normalizedArgs.repeat,
      holdMs: normalizedArgs.holdMs
    });
    setActionHarnessState({
      playMode: true,
      status: "ready",
      lastActionAt: Date.now(),
      lastAction: `key ${key}`,
      lastError: ""
    });
    saveState();
    broadcastState();
    const postActionCapture = await captureActionHarnessVisualAfterAction(`key ${key}`);
    return {
      success: true,
      message: `Pressed ${key}.`,
      content: `Pressed ${key} in ${formatActionHarnessTargetLabel(targetWindow)}.\n\n${postActionCapture.content}`,
      visualAttachments: postActionCapture.visualAttachments
    };
  }

  if (toolName === "desktop_action_type_text") {
    const text = String(normalizedArgs.text || "").slice(0, 1000);
    await actionHarness.typeTextInput({
      hwnd: targetWindow.hwnd,
      text
    });
    setActionHarnessState({
      playMode: true,
      status: "ready",
      lastActionAt: Date.now(),
      lastAction: `typed ${text.length} chars`,
      lastError: ""
    });
    saveState();
    broadcastState();
    const postActionCapture = await captureActionHarnessVisualAfterAction(`typed ${text.length} characters`);
    return {
      success: true,
      message: `Typed ${text.length} characters.`,
      content: `Typed ${text.length} characters in ${formatActionHarnessTargetLabel(targetWindow)}.\n\n${postActionCapture.content}`,
      visualAttachments: postActionCapture.visualAttachments
    };
  }

  if (toolName === "desktop_action_wait") {
    const waitMs = Math.max(50, Math.min(10000, Math.round(Number(normalizedArgs.ms) || 500)));
    await actionHarness.delay(waitMs);
    const postActionCapture = await captureActionHarnessVisualAfterAction(`waiting ${waitMs}ms`, 0);
    return {
      success: true,
      message: `Waited ${waitMs}ms.`,
      content: `Waited ${waitMs}ms.\n\n${postActionCapture.content}`,
      visualAttachments: postActionCapture.visualAttachments
    };
  }

  throw new Error(`Unknown desktop action harness tool: ${toolName}`);
}

async function fetchDesktopToolingBundle(apiOrigin, options = {}) {
  if (!hasUsableDesktopAuthToken({ applyWindowState: true, broadcast: true })) {
    return { fetchedAt: Date.now(), tools: [], promptLines: [] };
  }
  const forceRefresh = Boolean(options.forceRefresh);
  const now = Date.now();
  if (
    !forceRefresh &&
    Array.isArray(desktopToolingCache.tools) &&
    desktopToolingCache.tools.length > 0 &&
    now - desktopToolingCache.fetchedAt < DESKTOP_TOOL_CACHE_MS
  ) {
    return desktopToolingCache;
  }

  const timeoutMs = Math.max(500, Number(options.timeoutMs) || DESKTOP_TOOL_FETCH_TIMEOUT_MS);
  const fetchController = new AbortController();
  const timeoutHandle = setTimeout(() => fetchController.abort(), timeoutMs);
  const abortFetch = () => fetchController.abort();
  if (options.signal) {
    if (options.signal.aborted) {
      fetchController.abort();
    } else {
      options.signal.addEventListener("abort", abortFetch, { once: true });
    }
  }

  try {
    const response = await net.fetch(`${apiOrigin}/v1/tools/openai`, {
      method: "GET",
      headers: buildProxyRequestHeaders({ Accept: "application/json" }),
      signal: fetchController.signal
    });
    const responseText = await response.text();
    const data = parseJsonOrNull(responseText);
    if (!response.ok || !data) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }
    desktopToolingCache = {
      fetchedAt: now,
      tools: Array.isArray(data.tools) ? data.tools : [],
      promptLines: Array.isArray(data.prompt_lines) ? data.prompt_lines : []
    };
  } catch (error) {
    appendRuntimeLog(`[desktop tools] failed to fetch tool schemas: ${String(error?.message || error)}`);
    if (!Array.isArray(desktopToolingCache.tools)) {
      desktopToolingCache.tools = [];
    }
    if (!Array.isArray(desktopToolingCache.promptLines)) {
      desktopToolingCache.promptLines = [];
    }
  } finally {
    clearTimeout(timeoutHandle);
    options.signal?.removeEventListener?.("abort", abortFetch);
  }
  return desktopToolingCache;
}

async function prewarmDesktopChat(payload = {}) {
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    return { ok: false, error: "CATBot API/proxy URL is not configured." };
  }
  try {
    requireDesktopAuthToken("prewarming desktop chat");
  } catch (error) {
    return { ok: false, error: String(error?.message || error || "Sign in required.") };
  }
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 10000);
  try {
    await fetchDesktopToolingBundle(apiOrigin, { signal: controller.signal, timeoutMs: 3500 });
    return { ok: true };
  } catch (error) {
    return { ok: false, error: String(error?.message || error || "Chat prewarm failed.") };
  } finally {
    clearTimeout(timeoutHandle);
  }
}

async function getDesktopClientConfig(apiOrigin, options = {}) {
  const now = Date.now();
  if (
    !options.forceRefresh &&
    desktopClientConfigCache.data &&
    now - desktopClientConfigCache.fetchedAt < DESKTOP_CLIENT_CONFIG_CACHE_MS
  ) {
    return desktopClientConfigCache.data;
  }

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), Math.max(500, Number(options.timeoutMs) || 2500));
  try {
    const response = await net.fetch(`${apiOrigin}/v1/client-config`, {
      method: "GET",
      headers: buildProxyRequestHeaders({ Accept: "application/json" }),
      signal: controller.signal
    });
    const responseText = await response.text();
    const data = parseJsonOrNull(responseText);
    if (!response.ok || !data || typeof data !== "object") {
      throw new Error(data?.detail || responseText || `HTTP ${response.status}`);
    }
    desktopClientConfigCache = {
      fetchedAt: now,
      data: {
        ttsEndpoint: normalizeUrlString(data.ttsEndpoint || ""),
        ttsModel: String(data.ttsModel || "").trim(),
        ttsVoice: String(data.ttsVoice || "").trim()
      }
    };
  } catch (error) {
    appendRuntimeLog(`[desktop config] failed to fetch client config: ${String(error?.message || error)}`);
    desktopClientConfigCache = {
      fetchedAt: now,
      data: {}
    };
  } finally {
    clearTimeout(timeoutHandle);
  }
  return desktopClientConfigCache.data || {};
}

const DESKTOP_OPENAI_TTS_FALLBACK_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];
const DESKTOP_POCKET_TTS_FALLBACK_VOICES = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"];
const DESKTOP_KITTEN_TTS_FALLBACK_VOICES = [
  "expr-voice-2-f",
  "expr-voice-3-f",
  "expr-voice-4-m",
  "expr-voice-5-m",
  "expr-voice-2-m",
  "expr-voice-5-f"
];

function normalizeDesktopTtsVoiceEntries(responseData) {
  const candidates = Array.isArray(responseData?.data)
    ? responseData.data
    : Array.isArray(responseData?.voices)
      ? responseData.voices
      : Array.isArray(responseData)
        ? responseData
        : [];

  return candidates
    .map((voice) => {
      if (typeof voice === "string") {
        const id = voice.trim();
        return id ? { id, name: id } : null;
      }
      if (!voice || typeof voice !== "object") {
        return null;
      }
      const id = String(voice.id || voice.voice || voice.value || voice.name || "").trim();
      if (!id) {
        return null;
      }
      const name = String(voice.name || voice.label || voice.filename || id).trim() || id;
      return { ...voice, id, name };
    })
    .filter(Boolean);
}

function desktopTtsVoiceDisplayName(voiceId) {
  const value = String(voiceId || "").trim();
  if (!value) {
    return "";
  }
  const normalized = value.replace(/\\/g, "/");
  const fileName = normalized.split("/").filter(Boolean).pop() || value;
  return /\.(wav|mp3|flac|safetensors)$/i.test(fileName)
    ? fileName.replace(/\.(wav|mp3|flac|safetensors)$/i, "")
    : value;
}

function addDesktopTtsVoiceOption(voices, seen, voiceId, name = "") {
  const id = String(voiceId || "").trim();
  if (!id) {
    return;
  }
  const key = id.toLowerCase();
  if (seen.has(key)) {
    return;
  }
  seen.add(key);
  voices.push({
    id,
    name: String(name || "").trim() || desktopTtsVoiceDisplayName(id) || id
  });
}

function buildDesktopTtsFallbackVoiceEntries(modelName, selectedVoice = "") {
  const normalizedModel = String(modelName || "").trim().toLowerCase();
  const fallbackVoiceIds = normalizedModel.includes("pocket-tts")
    ? DESKTOP_POCKET_TTS_FALLBACK_VOICES
    : normalizedModel.includes("kitten")
      ? DESKTOP_KITTEN_TTS_FALLBACK_VOICES
      : DESKTOP_OPENAI_TTS_FALLBACK_VOICES;
  const voices = [];
  const seen = new Set();
  for (const voiceId of fallbackVoiceIds) {
    addDesktopTtsVoiceOption(voices, seen, voiceId);
  }
  addDesktopTtsVoiceOption(voices, seen, selectedVoice);
  return voices;
}

async function listDesktopTtsVoices(payload = {}) {
  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  const apiOrigin = getProxyOriginFromPayload({ ...payload, proxyBaseUrl: requestedProxyBaseUrl });
  const requestedTtsEndpoint = normalizeUrlString(payload.ttsEndpoint || state.ttsEndpoint || "");
  const usingProxyTtsDefaults = !requestedTtsEndpoint;
  const clientConfig = apiOrigin && usingProxyTtsDefaults
    ? await getDesktopClientConfig(apiOrigin).catch(() => ({}))
    : {};
  const requestedModel = String(payload.ttsModel || state.ttsModel || "").trim();
  const requestedVoice = String(payload.ttsVoice || state.ttsVoice || "").trim();
  const defaultTtsModel = String(DEFAULT_STATE.ttsModel || "tts-1").trim();
  const defaultTtsVoice = String(DEFAULT_STATE.ttsVoice || "alloy").trim();
  const ttsEndpoint = normalizeUrlString(requestedTtsEndpoint || clientConfig.ttsEndpoint || "");
  const ttsModel = usingProxyTtsDefaults && (!requestedModel || requestedModel === defaultTtsModel || requestedModel === "tts-1")
    ? String(clientConfig.ttsModel || defaultTtsModel || "tts-1").trim()
    : (requestedModel || defaultTtsModel || "tts-1");
  const selectedVoice = usingProxyTtsDefaults && (!requestedVoice || requestedVoice === defaultTtsVoice || requestedVoice === "alloy")
    ? String(clientConfig.ttsVoice || requestedVoice || defaultTtsVoice || "alloy").trim()
    : (requestedVoice || defaultTtsVoice || "alloy");
  const voices = buildDesktopTtsFallbackVoiceEntries(ttsModel, selectedVoice);
  const seen = new Set(voices.map((voice) => voice.id.toLowerCase()));
  const endpointOrigin = extractOriginFromUrlLike(ttsEndpoint);

  if (!apiOrigin || !endpointOrigin) {
    return {
      voices,
      selectedVoice,
      ttsEndpoint,
      ttsModel,
      source: "fallback"
    };
  }

  const cacheKey = JSON.stringify([apiOrigin, endpointOrigin, ttsModel]);
  const useEmbeddedTtsEndpoint = areSameUrlOrigins(apiOrigin, endpointOrigin);
  let fetchedVoices = [];
  if (
    desktopTtsVoiceCache.key === cacheKey &&
    Array.isArray(desktopTtsVoiceCache.voices) &&
    Date.now() - desktopTtsVoiceCache.fetchedAt < DESKTOP_TTS_VOICE_CACHE_MS
  ) {
    fetchedVoices = desktopTtsVoiceCache.voices;
  } else {
    const providerApiKey = String(payload.chatApiKey || desktopAuth.chatApiKey || "").trim();
    const proxyAuthToken = String(desktopAuth.accessToken || "").trim();
    if (shouldAllowEndpointOverride(endpointOrigin, providerApiKey, proxyAuthToken)) {
      const query = new URLSearchParams();
      if (!useEmbeddedTtsEndpoint) {
        query.set("endpoint", endpointOrigin);
      }
      if (ttsModel) {
        query.set("model", ttsModel);
      }
      const voicesPath = useEmbeddedTtsEndpoint ? "/v1/audio/voices" : "/v1/proxy/tts/voices";
      const voicesUrl = `${apiOrigin}${voicesPath}?${query.toString()}`;
      try {
        const response = await net.fetch(voicesUrl, {
          method: "GET",
          headers: buildProxyRequestHeaders({ Accept: "application/json" }, { providerApiKey })
        });
        const responseText = await response.text();
        const data = parseJsonOrNull(responseText);
        if (!response.ok || !data) {
          throw new Error(data?.detail || responseText || `HTTP ${response.status}`);
        }
        fetchedVoices = normalizeDesktopTtsVoiceEntries(data);
        desktopTtsVoiceCache = {
          key: cacheKey,
          fetchedAt: Date.now(),
          voices: fetchedVoices
        };
      } catch (error) {
        appendRuntimeLog(`[desktop tts voices] failed to fetch voices: ${String(error?.message || error)}`);
      }
    }
  }

  for (const voice of fetchedVoices) {
    addDesktopTtsVoiceOption(voices, seen, voice.id, voice.name);
  }

  return {
    voices,
    selectedVoice,
    ttsEndpoint,
    ttsModel,
    source: fetchedVoices.length ? "endpoint" : "fallback"
  };
}

function composeDesktopSystemPrompt(basePrompt) {
  const soulPrompt = getSoulPromptText();
  const customPrompt = String(basePrompt || "").trim();
  return [soulPrompt, customPrompt].filter(Boolean).join("\n\n");
}

function buildDesktopToolSystemPrompt(basePrompt, toolingBundle) {
  const dynamicTools = Array.isArray(toolingBundle?.promptLines) && toolingBundle.promptLines.length
    ? `\n\nAvailable tools:\n${toolingBundle.promptLines.slice(0, 100).join("\n")}`
    : "";
  const toolRules = `You are CATBot, a concise desktop companion with access to proxy-server tools.

Tool calling rules:
- Prefer native tool calls when available.
- Use tools for current information, files, weather, web access, browser automation, code changes, memory, todos, and other actions exposed by the proxy.
- Do not invent tool outputs; execute the tool and use the returned result.
- Ask a short follow-up when a required tool argument is missing.
- If native tool calls are unavailable, use this Qwen/Hermes text fallback:
<tool_call>
{"name":"tool_name","arguments":{"key":"value"}}
</tool_call>
- Legacy XML fallback is also accepted:
<tool>tool_name</tool>
<parameters>
{ "key": "value" }
</parameters>`;
  const customPrompt = composeDesktopSystemPrompt(basePrompt);
  return `${customPrompt ? `${customPrompt}\n\n` : ""}${toolRules}${dynamicTools}`;
}

function buildDesktopChatBody({ messages, model, tools, includeNativeTools = true }) {
  const body = {
    messages,
    stream: false,
    temperature: 0.7
  };
  if (model) {
    body.model = model;
  }
  if (includeNativeTools && Array.isArray(tools) && tools.length > 0) {
    body.tools = tools;
    body.tool_choice = "auto";
  }
  return body;
}

function serializeDesktopChatRequestBody(body) {
  const text = JSON.stringify(body);
  return {
    text,
    bytes: Buffer.byteLength(text, "utf8")
  };
}

function shouldRetryDesktopChatWithoutNativeTools(error) {
  const message = String(error?.message || error || "").toLowerCase();
  return (
    message.includes("channel") ||
    message.includes("tool_call") ||
    message.includes("tool call") ||
    message.includes("tool role") ||
    message.includes("role \"tool\"") ||
    message.includes("role 'tool'") ||
    message.includes("no user query") ||
    message.includes("jinja") ||
    message.includes("prompt template") ||
    message.includes("tool_choice") ||
    message.includes("tools") && (
      message.includes("unsupported") ||
      message.includes("not supported") ||
      message.includes("unknown") ||
      message.includes("unrecognized") ||
      message.includes("extra") ||
      message.includes("forbidden") ||
      message.includes("invalid")
    )
  );
}

function shouldUseDesktopNativeTools(options = {}) {
  if (options.actionHarnessPlayMode) {
    return false;
  }
  const model = String(options.model || "").toLowerCase();
  const endpoint = String(options.endpoint || "").toLowerCase();
  if (model.includes("qwen") || model.includes("hermes") || endpoint.includes("lmstudio")) {
    return false;
  }
  return true;
}

function compactDesktopActionHarnessMessagesForRequest(messages = []) {
  if (!Array.isArray(messages) || messages.length <= DESKTOP_ACTION_HARNESS_CONTEXT_TAIL_MESSAGES + 3) {
    return messages;
  }
  const selected = [];
  const seen = new Set();
  const addMessage = (message) => {
    if (!message || seen.has(message)) {
      return;
    }
    seen.add(message);
    selected.push(message);
  };
  if (messages[0]?.role === "system") {
    addMessage(messages[0]);
  }
  const firstUserMessage = messages.find((message) => message?.role === "user");
  addMessage(firstUserMessage);
  for (const message of messages.slice(-DESKTOP_ACTION_HARNESS_CONTEXT_TAIL_MESSAGES)) {
    addMessage(message);
  }
  return selected;
}

async function requestDesktopChatCompletion(proxyUrl, bodyText, headers, signal, apiOrigin) {
  const response = await net.fetch(proxyUrl, {
    method: "POST",
    headers,
    body: bodyText,
    signal
  });
  const responseText = await response.text();
  const data = parseJsonOrNull(responseText);

  if (!response.ok) {
    if (!data) {
      throw new Error(formatProxyResponseError(response, responseText, "Desktop chat", apiOrigin));
    }
    const detail = data?.detail || data?.error || `Chat request failed (${response.status})`;
    throw new Error(String(detail));
  }
  if (!data) {
    throw new Error(formatProxyResponseError(response, responseText, "Desktop chat", apiOrigin));
  }
  return data;
}

function getDesktopToolCallName(toolCall = {}) {
  return String(toolCall?.function?.name || toolCall?.name || "").trim();
}

function getDesktopToolCallArguments(toolCall = {}) {
  const raw = toolCall?.function?.arguments ?? toolCall?.arguments ?? {};
  if (typeof raw === "string") {
    try {
      return raw.trim() ? JSON.parse(raw) : {};
    } catch (error) {
      throw new Error(`Invalid JSON arguments for tool ${getDesktopToolCallName(toolCall) || "(unknown)"}: ${error.message}`);
    }
  }
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
}

function formatDesktopToolResultForModel(toolResult) {
  if (typeof toolResult === "string") {
    return toolResult;
  }
  if (toolResult && typeof toolResult === "object") {
    const { visualAttachments: _visualAttachments, dataUrl: _dataUrl, ...modelSafeResult } = toolResult;
    if (typeof toolResult.content === "string" && toolResult.content.trim()) {
      return `${toolResult.message || "Tool result"}\n\n${toolResult.content}`;
    }
    try {
      return JSON.stringify(modelSafeResult);
    } catch (_) {
      return String(toolResult);
    }
  }
  return String(toolResult || "");
}

async function executeDesktopToolCall(apiOrigin, toolCall, context = {}, signal = null) {
  const toolName = getDesktopToolCallName(toolCall);
  if (!toolName) {
    throw new Error("Tool call is missing a function name.");
  }
  const args = getDesktopToolCallArguments(toolCall);
  if (isDesktopActionHarnessToolName(toolName)) {
    appendRuntimeLog(`[desktop action harness] executing ${toolName} ${JSON.stringify(args).slice(0, 900)}`);
    return executeDesktopActionHarnessTool(toolName, args);
  }
  requireDesktopAuthToken(`running proxy tool ${toolName}`);
  appendRuntimeLog(`[desktop tool] executing ${toolName} ${JSON.stringify(args).slice(0, 900)}`);
  const response = await net.fetch(`${apiOrigin}/v1/tools/execute`, {
    method: "POST",
    headers: buildProxyRequestHeaders({
      "Content-Type": "application/json",
      Accept: "application/json"
    }),
    body: JSON.stringify({
      tool_name: toolName,
      arguments: args,
      context
    }),
    signal
  });
  const responseText = await response.text();
  const data = parseJsonOrNull(responseText);
  if (!response.ok) {
    const detail = data?.detail || data?.message || responseText || `HTTP ${response.status}`;
    throw new Error(`Tool ${toolName} failed: ${detail}`);
  }
  return data || { success: true, message: responseText };
}

async function sendDesktopChatMessage(payload = {}) {
  const userText = normalizeChatContent(payload.message, 2400);
  if (!userText) {
    throw new Error("Chat message is required.");
  }

  const requestedWebClientUrl = normalizeUrlString(payload.webClientUrl || state.webClientUrl);
  if (requestedWebClientUrl && isSafeExternalUrl(requestedWebClientUrl)) {
    state.webClientUrl = requestedWebClientUrl;
  }
  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    throw new Error("Configure the CATBot API/proxy URL before using desktop chat.");
  }
  const proxyAuthToken = requireDesktopAuthToken("using desktop chat");

  const endpoint = normalizeEndpointString(payload.chatEndpoint || state.chatEndpoint || DEFAULT_CHAT_ENDPOINT);
  const model = String(payload.chatModel || state.chatModel || "").trim();
  const chatApiKey = String(payload.chatApiKey || desktopAuth.chatApiKey || "").trim();
  const endpointOverride = shouldAllowEndpointOverride(endpoint, chatApiKey, proxyAuthToken) ? endpoint : "";
  const requestedSystemPrompt = String(payload.chatSystemPrompt || state.chatSystemPrompt || "").trim();
  const history = normalizeDesktopChatHistory(payload.history || state.desktopChatHistory);
  const proxyUrl = `${apiOrigin}/v1/proxy/chat/completions${endpointOverride ? `?endpoint=${encodeURIComponent(endpointOverride)}` : ""}`;
  const controller = new AbortController();
  const playModeAtRequestStart = Boolean(state.actionHarness?.playMode);
  const playModeLoopBudgetAtRequestStart = playModeAtRequestStart ? getActionHarnessLoopBudget() : 0;
  const chatTimeoutMs = playModeAtRequestStart && playModeLoopBudgetAtRequestStart < 0
    ? 0
    : playModeAtRequestStart
      ? DESKTOP_ACTION_HARNESS_CHAT_TIMEOUT_MS
      : DESKTOP_CHAT_REQUEST_TIMEOUT_MS;
  const timeoutHandle = chatTimeoutMs > 0 ? setTimeout(() => controller.abort(), chatTimeoutMs) : null;
  const lowLatency = Boolean(payload.lowLatency);
  let toolingBundle = await fetchDesktopToolingBundle(apiOrigin, {
    signal: controller.signal,
    timeoutMs: lowLatency ? DESKTOP_VOICE_TOOL_FETCH_TIMEOUT_MS : DESKTOP_TOOL_FETCH_TIMEOUT_MS
  });
  if (lowLatency && (!Array.isArray(toolingBundle.tools) || toolingBundle.tools.length === 0)) {
    toolingBundle = await fetchDesktopToolingBundle(apiOrigin, {
      signal: controller.signal,
      timeoutMs: DESKTOP_TOOL_FETCH_TIMEOUT_MS,
      forceRefresh: true
    });
  }
  const actionTooling = getDesktopActionHarnessTooling();
  const tools = [
    ...actionTooling.tools,
    ...(Array.isArray(toolingBundle.tools) ? toolingBundle.tools : [])
  ];
  const systemPrompt = buildDesktopToolSystemPrompt(requestedSystemPrompt, {
    ...toolingBundle,
    tools,
    promptLines: [
      ...actionTooling.promptLines,
      ...(Array.isArray(toolingBundle.promptLines) ? toolingBundle.promptLines : [])
    ]
  });
  const messages = [];
  if (systemPrompt) {
    messages.push({ role: "system", content: systemPrompt });
  }
  messages.push(...history);
  messages.push(buildDesktopUserMessage(userText, buildDesktopVisualAttachments(payload)));

  clearDesktopReplyEmotionResetTimer();
  state.expression = "think";
  state.transientExpression = true;
  state.chatEndpoint = endpoint;
  state.chatModel = model;
  if (payload.chatApiKey) {
    desktopAuth.chatApiKey = chatApiKey;
    saveDesktopAuth();
  }
  state.chatSystemPrompt = requestedSystemPrompt;
  saveState();
  broadcastState();

  try {
    const requestHeaders = buildProxyRequestHeaders(
      {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      { providerApiKey: chatApiKey }
    );
    const allowNativeTools = shouldUseDesktopNativeTools({
      endpoint,
      model,
      actionHarnessPlayMode: Boolean(state.actionHarness?.playMode)
    });
    if (tools.length > 0 && !allowNativeTools) {
      appendRuntimeLog("[desktop tools] using text fallback tool calls for this model/mode to avoid channel-template errors.");
    }
    let includeNativeTools = tools.length > 0 && allowNativeTools;
    const buildRequestMessagesWithCurrentToolMode = () => {
      const contextualMessagesRaw = state.actionHarness?.playMode
        ? injectActionHarnessPlayMemoryMessage(compactDesktopActionHarnessMessagesForRequest(messages))
        : messages;
      const contextualMessages = state.actionHarness?.playMode
        ? keepLatestDesktopVisualMessageOnly(contextualMessagesRaw)
        : contextualMessagesRaw;
      return includeNativeTools
        ? contextualMessages
        : sanitizeDesktopMessagesForTextFallback(contextualMessages, { endpoint, model });
    };
    const requestChatWithCurrentToolMode = async () => {
      const requestMessages = buildRequestMessagesWithCurrentToolMode();
      const requestBody = buildDesktopChatBody({ messages: requestMessages, model, tools, includeNativeTools });
      const requestStartedAt = Date.now();
      const serializeStartedAt = Date.now();
      const serializedRequestBody = serializeDesktopChatRequestBody(requestBody);
      const serializeMs = Date.now() - serializeStartedAt;
      if (state.actionHarness?.playMode) {
        appendRuntimeLog(`[desktop chat] play request start mode=${includeNativeTools ? "native" : "text"} messages=${requestMessages.length} images=${countDesktopImagePartsInMessages(requestMessages)} bytes=${serializedRequestBody.bytes} serializeMs=${serializeMs}`);
      }
      try {
        const result = await requestDesktopChatCompletion(
          proxyUrl,
          serializedRequestBody.text,
          requestHeaders,
          controller.signal,
          apiOrigin
        );
        if (state.actionHarness?.playMode) {
          appendRuntimeLog(`[desktop chat] play request completed in ${Date.now() - requestStartedAt}ms`);
        }
        return result;
      } catch (error) {
        if (!includeNativeTools || !shouldRetryDesktopChatWithoutNativeTools(error)) {
          throw error;
        }
        includeNativeTools = false;
        appendRuntimeLog(`[desktop tools] endpoint rejected native tool schema; retrying with text fallback: ${String(error?.message || error)}`);
        const fallbackMessages = buildRequestMessagesWithCurrentToolMode();
        const fallbackBody = buildDesktopChatBody({ messages: fallbackMessages, model, tools, includeNativeTools });
        const fallbackStartedAt = Date.now();
        const fallbackSerializeStartedAt = Date.now();
        const serializedFallbackBody = serializeDesktopChatRequestBody(fallbackBody);
        const fallbackSerializeMs = Date.now() - fallbackSerializeStartedAt;
        if (state.actionHarness?.playMode) {
          appendRuntimeLog(`[desktop chat] play fallback request start messages=${fallbackMessages.length} images=${countDesktopImagePartsInMessages(fallbackMessages)} bytes=${serializedFallbackBody.bytes} serializeMs=${fallbackSerializeMs}`);
        }
        const fallbackResult = await requestDesktopChatCompletion(
          proxyUrl,
          serializedFallbackBody.text,
          requestHeaders,
          controller.signal,
          apiOrigin
        );
        if (state.actionHarness?.playMode) {
          appendRuntimeLog(`[desktop chat] play fallback request completed in ${Date.now() - fallbackStartedAt}ms`);
        }
        return fallbackResult;
      }
    };
    let data = await requestChatWithCurrentToolMode();
    let assistantMessage = getDesktopChatResponseMessage(data);
    let reply = getVisibleDesktopAssistantText(assistantMessage);
    let toolIterations = 0;
    const maxToolIterations = state.actionHarness?.playMode
      ? getActionHarnessLoopBudget()
      : DESKTOP_TOOL_LOOP_MAX_ITERATIONS;
    const actionHarnessNudgeInterval = state.actionHarness?.playMode ? getActionHarnessNudgeInterval() : 0;
    let lastToolResultContent = "";
    let lastActionHarnessVisualAttachments = [];
    let actionHarnessContinueNudges = 0;
    let actionHarnessCompletedActionLoops = 0;
    const actionHarnessContinueNudgeLimit = maxToolIterations < 0
      ? Number.POSITIVE_INFINITY
      : DESKTOP_ACTION_HARNESS_CONTINUE_NUDGE_LIMIT;

    while (state.actionHarness?.playMode ? shouldRunActionHarnessLoopIteration(toolIterations, maxToolIterations) : toolIterations < maxToolIterations) {
      const { calls } = collectDesktopToolCalls(assistantMessage);
      const assistantObservation = getVisibleDesktopAssistantText(assistantMessage);
      if (!calls.length) {
        if (state.actionHarness?.playMode && assistantObservation) {
          appendActionHarnessPlayMemory({
            type: "model_note",
            observation: assistantObservation
          });
        }
        if (
          state.actionHarness?.playMode &&
          actionHarnessContinueNudges < actionHarnessContinueNudgeLimit &&
          shouldNudgeDesktopActionHarnessContinue(reply)
        ) {
          actionHarnessContinueNudges += 1;
          const nudgeLimitLabel = Number.isFinite(actionHarnessContinueNudgeLimit) ? String(actionHarnessContinueNudgeLimit) : "infinite";
          appendRuntimeLog(`[desktop action harness] nudging continuous play after non-tool reply (${actionHarnessContinueNudges}/${nudgeLimitLabel})`);
          let nudgeVisualAttachments = lastActionHarnessVisualAttachments;
          if (!nudgeVisualAttachments.length) {
            const nudgeCapture = await captureActionHarnessVisualAfterAction("non-tool response", 0);
            nudgeVisualAttachments = nudgeCapture.visualAttachments;
            if (nudgeCapture.content) {
              appendActionHarnessPlayMemory({
                type: "capture",
                result: nudgeCapture.content
              });
            }
          }
          messages.push(buildDesktopUserMessage(
            "Continue desktop play mode. Inspect the latest attached screenshot/tool result and the play memory. If the goal is not complete and you are not blocked, output exactly one next <tool_call> and no prose. If complete or blocked, answer briefly with the reason.",
            nudgeVisualAttachments,
            { maxChars: 1300 }
          ));
          data = await requestChatWithCurrentToolMode();
          assistantMessage = getDesktopChatResponseMessage(data);
          reply = getVisibleDesktopAssistantText(assistantMessage);
          continue;
        }
        break;
      }

      messages.push(buildDesktopAssistantHistoryMessage(assistantMessage, {
        toolCalls: calls
      }));
      actionHarnessContinueNudges = 0;
      let actionHarnessToolAlreadyRan = false;
      let actionHarnessActionToolRanThisStep = false;
      const toolResponseParts = [];
      const toolVisualAttachments = [];
      for (const toolCall of calls) {
        const toolName = getDesktopToolCallName(toolCall);
        let toolArgsForMemory = {};
        try {
          toolArgsForMemory = getDesktopToolCallArguments(toolCall);
        } catch (_) {
          toolArgsForMemory = {};
        }
        state.expression = "think";
        state.transientExpression = true;
        saveState();
        broadcastState();
        const isActionHarnessTool = isDesktopActionHarnessToolName(toolName);
        const toolResult = isActionHarnessTool && actionHarnessToolAlreadyRan
          ? {
              success: false,
              message: "Skipped extra desktop action.",
              content: "Only one desktop action harness tool is allowed per reasoning step. Inspect the latest result and call the next action in a later step."
            }
          : await executeDesktopToolCall(
              apiOrigin,
              toolCall,
              {
                conversation_id: "desktop-avatar",
                user_id: desktopAuth.username || "desktop-avatar",
                metadata: { channel: "electron_desktop_avatar" }
              },
              controller.signal
            );
        if (isActionHarnessTool) {
          actionHarnessToolAlreadyRan = true;
        }
        if (isDesktopActionHarnessInteractiveToolName(toolName)) {
          actionHarnessActionToolRanThisStep = true;
        }
        const toolResultContent = formatDesktopToolResultForModel(toolResult);
        lastToolResultContent = toolResultContent;
        if (isActionHarnessTool) {
          appendActionHarnessPlayMemory({
            type: "action",
            toolName,
            args: toolArgsForMemory,
            observation: assistantObservation,
            result: toolResultContent
          });
        }
        toolResponseParts.push(`Tool result from ${toolName}:\n<tool_response>\n${toolResultContent}\n</tool_response>`);
        const visualAttachments = getDesktopToolResultVisualAttachments(toolResult);
        if (visualAttachments.length) {
          toolVisualAttachments.push(...visualAttachments);
        }
      }
      if (toolVisualAttachments.length) {
        lastActionHarnessVisualAttachments = toolVisualAttachments;
      }

      if (state.actionHarness?.playMode && actionHarnessActionToolRanThisStep) {
        actionHarnessCompletedActionLoops += 1;
      }
      const nextToolIteration = toolIterations + 1;
      const shouldInsertDecisionNudge = actionHarnessActionToolRanThisStep &&
        shouldInsertActionHarnessDecisionNudge(actionHarnessCompletedActionLoops, actionHarnessNudgeInterval);

      if (toolResponseParts.length) {
        const visualInstruction = toolVisualAttachments.length
          ? "\n\nInspect the attached visual result before choosing the next play-mode action."
          : "";
        const decisionInstruction = shouldInsertDecisionNudge
          ? `\n\n${buildActionHarnessDecisionNudge(actionHarnessCompletedActionLoops)}`
          : "";
        messages.push(buildDesktopUserMessage(
          `${toolResponseParts.join("\n\n")}${visualInstruction}${decisionInstruction}`,
          toolVisualAttachments,
          { maxChars: DESKTOP_TOOL_RESULT_MESSAGE_CHAR_LIMIT }
        ));
      }

      if (playModeAtRequestStart && !state.actionHarness?.playMode) {
        break;
      }
      if (state.actionHarness?.playMode && maxToolIterations >= 0 && nextToolIteration >= maxToolIterations) {
        appendRuntimeLog(`[desktop action harness] loop budget reached (${nextToolIteration}/${maxToolIterations}).`);
        break;
      }
      data = await requestChatWithCurrentToolMode();
      assistantMessage = getDesktopChatResponseMessage(data);
      reply = getVisibleDesktopAssistantText(assistantMessage);
      toolIterations = nextToolIteration;
    }

    if (!reply) {
      if (assistantMessageLooksLikeOnlyToolCall(assistantMessage)) {
        reply = "Desktop action completed.";
      }
    }
    if (!reply) {
      reply = coerceAssistantTextFromChatResponse(data);
    }
    if (!reply && lastToolResultContent) {
      reply = `Here's what I found:\n\n${lastToolResultContent}`;
    }
    if (!reply) {
      throw new Error("CATBot returned an empty reply.");
    }

    const historyUserText = normalizeChatContent(payload.historyUserText || userText, 2400);
    state.desktopChatHistory = normalizeDesktopChatHistory([
      ...history,
      { role: "user", content: historyUserText },
      { role: "assistant", content: reply }
    ]);

    const suppressPlayModeToolSpeech = playModeAtRequestStart && assistantMessageLooksLikeOnlyToolCall(assistantMessage);
    const shouldSpeak = !suppressPlayModeToolSpeech && (payload.speakReply == null ? state.speakChatReplies : Boolean(payload.speakReply));
    state.speakChatReplies = shouldSpeak;
    state.expression = shouldSpeak ? "neutral" : inferDesktopAvatarExpression(reply);
    state.transientExpression = !shouldSpeak;
    if (shouldSpeak) {
      state.speechBubbleText = reply;
      state.speechDurationMs = calculateSpeechDurationMs(reply);
      state.speechTriggerId = Date.now();
    }

    saveState();
    broadcastState();
    if (!shouldSpeak) {
      scheduleDesktopReplyEmotionReset(DESKTOP_REPLY_EMOTION_RESET_DELAY_MS);
    }
    return {
      reply,
      state: getSafeState()
    };
  } catch (error) {
    appendRuntimeLog(`[desktop chat] request failed: ${String(error?.message || error).slice(0, 1200)}`);
    state.expression = "sad";
    state.transientExpression = true;
    saveState();
    broadcastState();
    scheduleDesktopReplyEmotionReset(DESKTOP_ERROR_EMOTION_RESET_DELAY_MS);
    if (error && error.name === "AbortError") {
      throw new Error("Desktop chat request timed out.");
    }
    throw error;
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
  }
}

async function capturePrimaryScreenSnapshot() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const scaleFactor = Math.max(1, Number(primaryDisplay.scaleFactor) || 1);
  const thumbnailSize = {
    width: Math.round(primaryDisplay.size.width * scaleFactor),
    height: Math.round(primaryDisplay.size.height * scaleFactor)
  };
  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize
  });
  const source = sources.find((item) => item.display_id === String(primaryDisplay.id)) || sources[0];
  if (!source || source.thumbnail.isEmpty()) {
    throw new Error("No screen snapshot source was available.");
  }
  return {
    dataUrl: source.thumbnail.toDataURL(),
    name: source.name || "Primary screen",
    displayId: source.display_id || String(primaryDisplay.id)
  };
}

async function transcribeDesktopAudio(payload = {}) {
  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    throw new Error("Configure the CATBot API/proxy URL before using microphone transcription.");
  }
  requireDesktopAuthToken("using microphone transcription");
  const audioBuffer = payload.audioBuffer;
  if (!audioBuffer) {
    throw new Error("No microphone audio was captured.");
  }
  const bytes = bufferFromIpcBinary(audioBuffer);
  if (!bytes.length) {
    throw new Error("Captured microphone audio was empty.");
  }

  const formData = new FormData();
  const mimeType = String(payload.mimeType || "audio/webm").trim() || "audio/webm";
  const extension =
    mimeType.includes("wav") ? "wav" :
    mimeType.includes("mpeg") || mimeType.includes("mp3") ? "mp3" :
    mimeType.includes("mp4") || mimeType.includes("m4a") ? "m4a" :
    "webm";
  const audioPayload = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  formData.append("file", new Blob([audioPayload], { type: mimeType }), `desktop-recording.${extension}`);
  formData.append("model", "whisper-1");

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await net.fetch(`${apiOrigin}/v1/audio/transcriptions`, {
      method: "POST",
      headers: buildProxyRequestHeaders(),
      body: formData,
      signal: controller.signal
    });
    const responseText = await response.text();
    const data = parseJsonOrNull(responseText);
    if (!response.ok) {
      if (!data) {
        throw new Error(formatProxyResponseError(response, responseText, "Microphone transcription", apiOrigin));
      }
      const detail = data?.detail || data?.error || `Transcription failed (${response.status})`;
      throw new Error(String(detail));
    }
    if (!data) {
      throw new Error(formatProxyResponseError(response, responseText, "Microphone transcription", apiOrigin));
    }
    const text = coerceTranscriptionText(data);
    if (!text) {
      throw new Error("Transcription returned no text.");
    }
    return { text };
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Microphone transcription timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

function clearDesktopChatHistory() {
  clearDesktopReplyEmotionResetTimer();
  state.desktopChatHistory = [];
  state.speechBubbleText = "";
  state.speechDurationMs = 300;
  state.speechTriggerId = Date.now();
  state.expression = "neutral";
  state.transientExpression = false;
  saveState();
  broadcastState();
  return getSafeState();
}

function startVoiceCaptureFromShortcut() {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    createAvatarWindow();
  }
  state.visible = true;
  state.moveMode = false;
  applyAvatarWindowState();
  saveState();
  broadcastState();

  const sendVoiceCaptureEvent = () => {
    if (avatarWindow && !avatarWindow.isDestroyed()) {
      avatarWindow.webContents.send("desktop:start-voice-capture");
    }
  };

  if (avatarWindow?.webContents?.isLoading?.()) {
    avatarWindow.webContents.once("did-finish-load", sendVoiceCaptureEvent);
  } else {
    sendVoiceCaptureEvent();
  }
  return getSafeState();
}

function updateTrayMenu() {
  if (!tray) {
    return;
  }
  const menu = Menu.buildFromTemplate([
    {
      label: state.quickHudVisible ? "Hide Avatar Actions (Ctrl+Shift+Space)" : "Show Avatar Actions (Ctrl+Shift+Space)",
      click: () => toggleQuickHud()
    },
    ...(isDeveloperControlPanelEnabled()
      ? [
          {
            label: "Open Developer Control Panel",
            click: () => showControlPanel()
          }
        ]
      : []),
    {
      label: state.startToTray ? "Disable Start To Tray" : "Enable Start To Tray",
      click: () => updateState({ startToTray: !state.startToTray })
    },
    {
      label: state.launchAtLogin ? "Disable Launch At Login" : "Enable Launch At Login",
      click: () => updateState({ launchAtLogin: !state.launchAtLogin })
    },
    {
      label: "Open CATBot Web Client (Ctrl+Shift+W)",
      enabled: Boolean(state.webClientUrl),
      click: () => showWebClientWindow()
    },
    {
      label: "Start Voice Chat (Ctrl+Alt+Space)",
      click: () => startVoiceCaptureFromShortcut()
    },
    {
      label: state.actionHarness?.playMode ? "Stop Desktop Play Mode (Ctrl+Shift+P)" : "Start Desktop Play Mode (Ctrl+Shift+P)",
      click: () => toggleActionHarness({ armDelayMs: DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS }).catch((error) => appendRuntimeLog(`[action harness] ${String(error?.message || error)}`))
    },
    {
      label: "Open Web Client In Browser",
      enabled: Boolean(state.webClientUrl),
      click: () => openSafeExternalUrl(state.webClientUrl)
    },
    {
      type: "separator"
    },
    {
      label: state.visible ? "Hide Avatar (Ctrl+Shift+A)" : "Show Avatar (Ctrl+Shift+A)",
      click: () => updateState({ visible: !state.visible })
    },
    {
      label: "Center Avatar",
      click: () => centerAvatarOnPrimaryDisplay()
    },
    {
      label: state.moveMode ? "Finish Move Mode (Ctrl+Shift+M)" : "Enable Move Mode (Ctrl+Shift+M)",
      click: () => toggleMoveMode()
    },
    {
      label: state.clickThrough ? "Disable Click-Through (Ctrl+Shift+X)" : "Enable Click-Through (Ctrl+Shift+X)",
      click: () => toggleClickThrough()
    },
    {
      type: "separator"
    },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);
  tray.setContextMenu(menu);
  tray.setToolTip("CATBot Desktop Avatar");
}

function createTray() {
  const icon = nativeImage.createFromPath(getLogoPath()).resize({ width: 16, height: 16 });
  tray = new Tray(icon);
  tray.on("click", () => toggleQuickHud());
  tray.on("double-click", () => setQuickHudVisible(true));
  updateTrayMenu();
}

function registerShortcuts() {
  const shortcuts = {
    "CommandOrControl+Shift+M": () => toggleMoveMode(),
    "CommandOrControl+Shift+C": () => setQuickHudVisible(true),
    "CommandOrControl+Shift+W": () => showWebClientWindow(),
    "CommandOrControl+Shift+A": () => updateState({ visible: !state.visible }),
    "CommandOrControl+Shift+X": () => toggleClickThrough(),
    "CommandOrControl+Alt+Space": () => startVoiceCaptureFromShortcut(),
    "CommandOrControl+Shift+Space": () => toggleQuickHud(),
    "CommandOrControl+Shift+P": () => {
      toggleActionHarness({ armDelayMs: DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS }).catch((error) => {
        appendRuntimeLog(`[action harness shortcut] ${String(error?.message || error)}`);
      });
    }
  };

  for (const [accelerator, handler] of Object.entries(shortcuts)) {
    const registered = globalShortcut.register(accelerator, handler);
    if (!registered) {
      console.warn(`Failed to register desktop shortcut: ${accelerator}`);
    }
  }
}

const activeDesktopPreviewSpeechStreams = new Map();

async function buildDesktopPreviewSpeechRequest(payload = {}) {
  const inputText = String(payload.text || "").trim();
  if (!inputText) {
    throw new Error("Speech preview text is required.");
  }
  const ttsInputText = sanitizeDesktopTtsText(inputText);
  if (!ttsInputText) {
    return {
      skipped: true,
      reason: "no-speakable-text"
    };
  }

  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    throw new Error("CATBot API/proxy URL is not configured.");
  }
  const proxyAuthToken = requireDesktopAuthToken("using speech synthesis");

  const requestedTtsEndpoint = normalizeUrlString(payload.ttsEndpoint || state.ttsEndpoint);
  const usingProxyTtsDefaults = !requestedTtsEndpoint;
  const clientConfig = usingProxyTtsDefaults ? await getDesktopClientConfig(apiOrigin) : {};
  const resolvedTtsEndpoint = normalizeUrlString(requestedTtsEndpoint || clientConfig.ttsEndpoint || "");
  const ttsEndpointOrigin = extractOriginFromUrlLike(resolvedTtsEndpoint);
  const providerApiKey = String(payload.chatApiKey || desktopAuth.chatApiKey || "").trim();
  if (ttsEndpointOrigin && !shouldAllowEndpointOverride(ttsEndpointOrigin, providerApiKey, proxyAuthToken)) {
    throw new Error("TTS endpoint override requires a configured provider API key, signed-in HUD auth, or a trusted local endpoint.");
  }
  const requestedModel = String(payload.ttsModel || state.ttsModel || "").trim();
  const requestedVoice = String(payload.ttsVoice || state.ttsVoice || "").trim();
  const defaultTtsModel = String(DEFAULT_STATE.ttsModel || "tts-1").trim();
  const defaultTtsVoice = String(DEFAULT_STATE.ttsVoice || "alloy").trim();
  const ttsModel = usingProxyTtsDefaults && (!requestedModel || requestedModel === defaultTtsModel || requestedModel === "tts-1")
    ? String(clientConfig.ttsModel || "").trim()
    : requestedModel;
  const ttsVoice = usingProxyTtsDefaults && (!requestedVoice || requestedVoice === defaultTtsVoice || requestedVoice === "alloy")
    ? String(clientConfig.ttsVoice || "").trim()
    : requestedVoice;
  const usePocketFastPath = isPocketTtsModelName(ttsModel);
  const useEmbeddedTtsEndpoint = areSameUrlOrigins(apiOrigin, ttsEndpointOrigin);
  const requestBody = {
    input: ttsInputText,
    stream: usePocketFastPath,
    response_format: usePocketFastPath ? "pcm" : "wav"
  };
  if (ttsModel) {
    requestBody.model = ttsModel;
  }
  if (ttsVoice) {
    requestBody.voice = ttsVoice;
  }
  if (usePocketFastPath) {
    requestBody.max_tokens = 256;
    requestBody.frames_after_eos = 4;
  }

  return {
    apiOrigin,
    providerApiKey,
    proxyUrl: useEmbeddedTtsEndpoint
      ? `${apiOrigin}/v1/audio/speech`
      : ttsEndpointOrigin
      ? `${apiOrigin}/v1/proxy/tts/speech?endpoint=${encodeURIComponent(ttsEndpointOrigin)}`
      : `${apiOrigin}/v1/proxy/tts/speech`,
    requestBody,
    usePocketFastPath,
    useEmbeddedTtsEndpoint
  };
}

function buildDesktopPreviewSpeechFetchHeaders(speechRequest) {
  return buildProxyRequestHeaders({
    "Content-Type": "application/json",
    Accept: speechRequest.usePocketFastPath
      ? "audio/pcm, audio/l16;q=0.95, application/octet-stream;q=0.9, audio/wav;q=0.8, audio/mpeg;q=0.6"
      : "audio/mpeg, audio/wav;q=0.9, application/octet-stream;q=0.8"
  }, { providerApiKey: speechRequest.providerApiKey });
}

function normalizeDesktopPreviewSpeechResult(audioBuffer, contentType, headers, speechRequest) {
  const bytes = new Uint8Array(audioBuffer || new ArrayBuffer(0));
  const requestedPcm = speechRequest?.requestBody?.response_format === "pcm";
  if (speechRequest?.usePocketFastPath && shouldTreatDesktopTtsBytesAsPcm(contentType, bytes, requestedPcm)) {
    return {
      audioBuffer: buildDesktopWavArrayBufferFromPcm(
        toDetachedArrayBuffer(bytes),
        getDesktopTtsSampleRate(headers, speechRequest.requestBody.sample_rate || 24000, contentType),
        getDesktopTtsChannels(headers, speechRequest.requestBody.channels || 1, contentType),
        getDesktopTtsPcmFormat(contentType, headers)
      ),
      contentType: "audio/wav"
    };
  }
  return {
    audioBuffer,
    contentType: normalizeDesktopAudioContentType(contentType, bytes)
  };
}

async function fetchDesktopPreviewSpeechBuffered(speechRequest, signal) {
  const response = await net.fetch(speechRequest.proxyUrl, {
    method: "POST",
    headers: buildDesktopPreviewSpeechFetchHeaders(speechRequest),
    body: JSON.stringify(speechRequest.requestBody),
    signal
  });

  if (!response.ok) {
    const errorText = String(await response.text()).trim();
    throw new Error(formatProxyResponseError(response, errorText, "Speech preview", speechRequest.apiOrigin));
  }

  const contentType = response.headers.get("content-type") || "";
  const audioBuffer = await response.arrayBuffer();
  return normalizeDesktopPreviewSpeechResult(audioBuffer, contentType, response.headers, speechRequest);
}

function getDesktopPreviewStreamChannel(streamId, name) {
  return `desktop:preview-speech-stream:${streamId}:${name}`;
}

function sendDesktopPreviewStreamEvent(sender, streamId, name, data = {}) {
  if (!sender || sender.isDestroyed?.()) {
    return;
  }
  try {
    sender.send(getDesktopPreviewStreamChannel(streamId, name), data);
  } catch (_) {
    // The avatar window may have been closed while the upstream stream was active.
  }
}

function registerAssetProtocol() {
  protocol.handle("catbot-file", (request) => {
    const relativePath = getAssetRelativePathFromRequestUrl(request.url);
    const resolvedPath = resolveAssetPath(relativePath);
    const assetRoot = getAssetRoot();
    if (!fs.existsSync(resolvedPath)) {
      return new Response("Not found", { status: 404 });
    }
    if (!isInside(assetRoot, resolvedPath)) {
      return new Response("Forbidden", { status: 403 });
    }
    return net.fetch(pathToFileURL(resolvedPath).toString());
  });
}

ipcMain.handle("desktop:get-state", () => getSafeState());
ipcMain.handle("desktop:get-auth-status", () => getDesktopAuthStatus());
ipcMain.handle("desktop:verify-auth", (_event, payload) => verifyDesktopAuth(payload));
ipcMain.handle("desktop:authenticate", (_event, payload) => authenticateDesktopUser(payload));
ipcMain.handle("desktop:logout", () => clearDesktopAuth());
ipcMain.handle("desktop:clear-provider-api-key", () => clearProviderApiKey());
ipcMain.handle("desktop:list-models", () => getAvailableModels());
ipcMain.handle("desktop:list-vrma-animations", () => getAvailableVrmaAnimations());
ipcMain.handle("desktop:list-tts-voices", (_event, payload) => listDesktopTtsVoices(payload));
ipcMain.handle("desktop:list-companions", (_event, payload) => listDesktopCompanions(payload));
ipcMain.handle("desktop:create-companion", (_event, payload) => createDesktopCompanion(payload));
ipcMain.handle("desktop:load-companion", (_event, companionId, payload) => loadDesktopCompanion(companionId, payload));
ipcMain.handle("desktop:delete-companion", (_event, companionId, payload) => deleteDesktopCompanion(companionId, payload));
ipcMain.handle("desktop:set-default-companion", (_event, companionId) => setDefaultDesktopCompanion(companionId));
ipcMain.handle("desktop:set-state", (_event, partialState) => updateState(partialState));
ipcMain.handle("desktop:toggle-move-mode", () => toggleMoveMode());
ipcMain.handle("desktop:toggle-click-through", () => toggleClickThrough());
ipcMain.handle("desktop:toggle-quick-hud", () => toggleQuickHud());
ipcMain.handle("desktop:set-quick-hud-visible", (_event, visible) => setQuickHudVisible(visible));
ipcMain.handle("desktop:center-avatar-window", () => centerAvatarOnPrimaryDisplay());
ipcMain.handle("desktop:begin-avatar-drag", (_event, point) => beginAvatarDrag(point));
ipcMain.handle("desktop:drag-avatar-window", (_event, point) => dragAvatarWindow(point));
ipcMain.handle("desktop:end-avatar-drag", () => endAvatarDrag());
ipcMain.handle("desktop:show-control-panel", () => {
  return showControlPanel();
});
ipcMain.handle("desktop:launch-web-client", () => showWebClientWindow());
ipcMain.handle("desktop:launch-external-web-client", () => {
  if (!state.webClientUrl) {
    return false;
  }
  return openSafeExternalUrl(state.webClientUrl);
});
ipcMain.handle("desktop:prewarm-chat", (_event, payload) => prewarmDesktopChat(payload));
ipcMain.handle("desktop:send-chat-message", (_event, payload) => sendDesktopChatMessage(payload));
ipcMain.handle("desktop:clear-chat-history", () => clearDesktopChatHistory());
ipcMain.handle("desktop:capture-screen-snapshot", () => capturePrimaryScreenSnapshot());
ipcMain.handle("desktop:start-action-harness", (_event, payload) => startActionHarness(payload));
ipcMain.handle("desktop:stop-action-harness", (_event, reason) => stopActionHarness(reason));
ipcMain.handle("desktop:toggle-action-harness", (_event, payload) => toggleActionHarness(payload));
ipcMain.handle("desktop:capture-action-harness", (_event, payload) => captureActionHarnessWindow(payload));
ipcMain.handle("desktop:transcribe-audio", (_event, payload) => transcribeDesktopAudio(payload));
ipcMain.handle("desktop:resolve-asset-url", (_event, relativePath) => toAssetUrl(relativePath));
ipcMain.handle("desktop:synthesize-preview-speech", async (_event, payload = {}) => {
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 60000);

  try {
    const speechRequest = await buildDesktopPreviewSpeechRequest(payload);
    if (speechRequest.skipped) {
      return speechRequest;
    }
    return await fetchDesktopPreviewSpeechBuffered(speechRequest, controller.signal);
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Speech preview request timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
});

ipcMain.handle("desktop:synthesize-preview-speech-stream", async (event, payload = {}) => {
  const streamId = String(payload.streamId || "").trim();
  if (!/^[a-zA-Z0-9_-]{1,96}$/.test(streamId)) {
    throw new Error("Invalid speech stream id.");
  }

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 60000);
  activeDesktopPreviewSpeechStreams.set(streamId, controller);

  try {
    const speechRequest = await buildDesktopPreviewSpeechRequest(payload);
    if (speechRequest.skipped) {
      return speechRequest;
    }

    if (!speechRequest.usePocketFastPath) {
      return {
        streamed: false,
        ...(await fetchDesktopPreviewSpeechBuffered(speechRequest, controller.signal))
      };
    }

    const response = await net.fetch(speechRequest.proxyUrl, {
      method: "POST",
      headers: buildDesktopPreviewSpeechFetchHeaders(speechRequest),
      body: JSON.stringify({
        ...speechRequest.requestBody,
        stream: true,
        response_format: "pcm"
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const errorText = String(await response.text()).trim();
      throw new Error(formatProxyResponseError(response, errorText, "Speech preview", speechRequest.apiOrigin));
    }

    const contentType = response.headers.get("content-type") || "";
    const reader = response.body?.getReader?.();
    if (!reader) {
      return {
        streamed: false,
        ...(await normalizeDesktopPreviewSpeechResult(await response.arrayBuffer(), contentType, response.headers, speechRequest))
      };
    }

    const firstRead = await reader.read();
    const firstChunk = firstRead.value ? new Uint8Array(firstRead.value) : new Uint8Array(0);
    const shouldStreamPcm = shouldTreatDesktopTtsBytesAsPcm(
      contentType,
      firstChunk,
      speechRequest.requestBody.response_format === "pcm"
    );

    if (!shouldStreamPcm) {
      const chunks = firstChunk.byteLength ? [firstChunk] : [];
      let totalBytes = firstChunk.byteLength;
      if (!firstRead.done) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }
          if (value?.byteLength) {
            const chunk = new Uint8Array(value);
            chunks.push(chunk);
            totalBytes += chunk.byteLength;
          }
        }
      }
      const bytes = concatDesktopUint8Chunks(chunks, totalBytes);
      return {
        streamed: false,
        audioBuffer: toDetachedArrayBuffer(bytes),
        contentType: normalizeDesktopAudioContentType(contentType, bytes)
      };
    }

    const sampleRate = getDesktopTtsSampleRate(response.headers, speechRequest.requestBody.sample_rate || 24000, contentType);
    const channels = getDesktopTtsChannels(response.headers, speechRequest.requestBody.channels || 1, contentType);
    const pcmFormat = getDesktopTtsPcmFormat(contentType, response.headers);
    const pcmContentType = normalizeDesktopPcmContentType(contentType, sampleRate, channels, pcmFormat);
    const minPcmChunkBytes = Math.max(
      channels * pcmFormat.bytesPerSample,
      Math.ceil(sampleRate * channels * pcmFormat.bytesPerSample * 0.1)
    );
    let totalBytes = 0;
    let chunkCount = 0;
    let upstreamChunkCount = 0;
    let pendingPcmChunks = [];
    let pendingPcmBytes = 0;
    const emitChunk = (chunk) => {
      if (!chunk?.byteLength) {
        return;
      }
      totalBytes += chunk.byteLength;
      chunkCount += 1;
      sendDesktopPreviewStreamEvent(event.sender, streamId, "chunk", {
        audioBuffer: toDetachedArrayBuffer(chunk)
      });
    };
    const flushPendingPcmChunks = (force = false) => {
      if (!pendingPcmBytes) {
        return;
      }
      if (!force && pendingPcmBytes < minPcmChunkBytes) {
        return;
      }
      const chunk = pendingPcmChunks.length === 1
        ? pendingPcmChunks[0]
        : concatDesktopUint8Chunks(pendingPcmChunks, pendingPcmBytes);
      pendingPcmChunks = [];
      pendingPcmBytes = 0;
      emitChunk(chunk);
    };
    const sendChunk = (chunk) => {
      if (!chunk?.byteLength) {
        return;
      }
      upstreamChunkCount += 1;
      if (chunk.byteLength < minPcmChunkBytes) {
        pendingPcmChunks.push(chunk);
        pendingPcmBytes += chunk.byteLength;
        flushPendingPcmChunks(false);
        return;
      }
      flushPendingPcmChunks(true);
      emitChunk(chunk);
    };

    sendDesktopPreviewStreamEvent(event.sender, streamId, "started", {
      contentType: pcmContentType,
      sampleRate,
      channels,
      pcmEncoding: pcmFormat.encoding,
      bitsPerSample: pcmFormat.bitsPerSample,
      bytesPerSample: pcmFormat.bytesPerSample,
      minChunkBytes: minPcmChunkBytes
    });
    sendChunk(firstChunk);

    if (!firstRead.done) {
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        sendChunk(value ? new Uint8Array(value) : null);
      }
    }
    flushPendingPcmChunks(true);

    const result = {
      streamed: true,
      contentType: pcmContentType,
      sampleRate,
      channels,
      pcmEncoding: pcmFormat.encoding,
      bitsPerSample: pcmFormat.bitsPerSample,
      bytesPerSample: pcmFormat.bytesPerSample,
      minChunkBytes: minPcmChunkBytes,
      byteLength: totalBytes,
      chunkCount,
      upstreamChunkCount
    };
    sendDesktopPreviewStreamEvent(event.sender, streamId, "done", result);
    return result;
  } catch (error) {
    const cancelled = controller.signal.aborted && activeDesktopPreviewSpeechStreams.get(streamId) !== controller;
    const message = cancelled
      ? "Speech preview stream cancelled."
      : error && error.name === "AbortError"
        ? "Speech preview stream timed out."
        : String(error?.message || error || "Speech preview stream failed.");
    sendDesktopPreviewStreamEvent(event.sender, streamId, "error", { message, cancelled });
    if (cancelled) {
      return { cancelled: true };
    }
    if (error && error.name === "AbortError") {
      throw new Error("Speech preview stream timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
    if (activeDesktopPreviewSpeechStreams.get(streamId) === controller) {
      activeDesktopPreviewSpeechStreams.delete(streamId);
    }
  }
});

ipcMain.handle("desktop:cancel-preview-speech-stream", (_event, streamId) => {
  const normalizedStreamId = String(streamId || "").trim();
  const controller = activeDesktopPreviewSpeechStreams.get(normalizedStreamId);
  if (controller) {
    activeDesktopPreviewSpeechStreams.delete(normalizedStreamId);
    try {
      controller.abort();
    } catch (_) {
      // ignore abort failures
    }
  }
  return true;
});

if (hasSingleInstanceLock) {
  app.on("second-instance", () => {
    showExistingInstance();
  });

  app.on("before-quit", () => {
    isQuitting = true;
    globalShortcut.unregisterAll();
  });

  app.whenReady().then(async () => {
    installLocalCertificateTrust();
    installMediaPermissionHandler();
    registerAssetProtocol();
    normalizePersistedWindowBounds();
    registerDisplayBoundaryHandlers();
    createAvatarWindow();
    createTray();
    registerShortcuts();
    applyAvatarWindowState();
    applyLaunchAtLoginSetting();
    broadcastState();
  });

  app.on("activate", () => {
    if (!avatarWindow || avatarWindow.isDestroyed()) {
      createAvatarWindow();
    }
    setQuickHudVisible(true);
  });
}
