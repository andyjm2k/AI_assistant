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
  desktopCapturer
} = require("electron");

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
const BOOTSTRAP_CONFIG_FILE = path.join(ELECTRON_ROOT, "config", "default-desktop-config.json");
const ENV_FILE = path.join(ELECTRON_ROOT, ".env");
const DEFAULT_PROXY_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_CHAT_ENDPOINT = "";
const DESKTOP_CHAT_HISTORY_LIMIT = 12;
const DESKTOP_CHAT_MESSAGE_CHAR_LIMIT = 6000;
const DESKTOP_TOOL_CACHE_MS = 120000;
const DESKTOP_TOOL_LOOP_MAX_ITERATIONS = 5;
const CERT_VERIFY_RESULT_DEFAULT = -3;
const CERT_VERIFY_RESULT_OK = 0;
const AVATAR_WINDOW_TOP_CHROME_GUARD_PX = 32;

let avatarWindow = null;
let controlWindow = null;
let webClientWindow = null;
let tray = null;
let isQuitting = false;
let avatarDragState = null;
let moveModeReturnHudVisible = false;
let desktopToolingCache = {
  fetchedAt: 0,
  tools: [],
  promptLines: []
};
const hasSingleInstanceLock = app.requestSingleInstanceLock();

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
  const content = normalizeChatContent(message.content);
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
  return coerceDesktopMessageText(message?.content ?? "")
    .replace(/<think>[\s\S]*?<\/think>/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildDesktopAssistantHistoryMessage(message = {}) {
  const out = { role: message.role || "assistant" };
  for (const key of ["content", "tool_calls", "name", "function_call", "refusal", "reasoning_details"]) {
    if (Object.prototype.hasOwnProperty.call(message, key) && message[key] != null) {
      out[key] = message[key];
    }
  }
  if (!Object.prototype.hasOwnProperty.call(out, "content")) {
    out.content = "";
  }
  return out;
}

function parseDesktopLenientJsonObject(value) {
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
      const parsed = JSON.parse(candidate);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
    } catch (_) {
      // Try the next normalized candidate.
    }
  }
  return null;
}

function parseDesktopToolFallback(content) {
  const withoutCode = String(content || "").replace(/```[\s\S]*?```/g, "");
  const toolMatch = withoutCode.match(/<(?:tool|tool_call)>(.*?)<\/(?:tool|tool_call)>/i);
  const paramsMatch = withoutCode.match(/<parameters>([\s\S]*?)<\/parameters>/i);
  if (toolMatch && paramsMatch) {
    const parameters = parseDesktopLenientJsonObject(paramsMatch[1]);
    if (parameters) {
      return {
        function: {
          name: toolMatch[1].trim(),
          arguments: JSON.stringify(parameters)
        }
      };
    }
  }

  const directJson = parseDesktopLenientJsonObject(withoutCode);
  if (directJson?.name && directJson?.arguments) {
    return {
      function: {
        name: String(directJson.name).trim(),
        arguments: typeof directJson.arguments === "string"
          ? directJson.arguments
          : JSON.stringify(directJson.arguments)
      }
    };
  }
  if (directJson?.action && directJson?.contentPrompt) {
    return {
      function: {
        name: String(directJson.action).trim(),
        arguments: JSON.stringify({ contentPrompt: directJson.contentPrompt })
      }
    };
  }

  return null;
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

function coerceTranscriptionText(data) {
  if (typeof data === "string") {
    return data.trim();
  }
  const text = data?.text || data?.transcription || data?.result?.text || data?.message || "";
  return String(text || "").trim();
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

function buildDesktopUserMessage(text, screenImageDataUrl = "") {
  const cleanText = normalizeChatContent(text, 2400);
  if (!isDataImageUrl(screenImageDataUrl)) {
    return { role: "user", content: cleanText };
  }
  return {
    role: "user",
    content: [
      {
        type: "text",
        text: `${cleanText}\n\nUse the attached desktop screenshot as visual context.`
      },
      {
        type: "image_url",
        image_url: {
          url: screenImageDataUrl,
          detail: "auto"
        }
      }
    ]
  };
}

function getAssetRoot() {
  return app.isPackaged ? process.resourcesPath : DEV_PROJECT_ROOT;
}

function getLogoPath() {
  return path.join(getAssetRoot(), "CATBot_logo.png");
}

function getModelRoot() {
  return path.join(getAssetRoot(), "model_avatar");
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

function getAvailableModels() {
  const scanned = scanModelDirectory(getModelRoot());
  scanned.vrm.sort((a, b) => a.localeCompare(b));
  scanned.live2d.sort((a, b) => a.localeCompare(b));
  return scanned;
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
  }
  if (env.ELECTRON_TTS_MODEL) {
    envConfig.ttsModel = env.ELECTRON_TTS_MODEL;
  }
  if (env.ELECTRON_TTS_VOICE) {
    envConfig.ttsVoice = env.ELECTRON_TTS_VOICE;
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
      trustLocalCertificates: true,
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
state.trustLocalCertificates = state.trustLocalCertificates !== false;
state.webClientUrl = normalizeUrlString(state.webClientUrl);
state.proxyBaseUrl = normalizeUrlString(state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);

function saveState() {
  const { chatApiKey: _chatApiKey, chatApiKeyConfigured: _chatApiKeyConfigured, ...persistedState } = state;
  saveJsonFile(USER_STATE_FILE, {
    ...persistedState,
    moveMode: false,
    quickHudVisible: false
  });
}

function loadDesktopAuth() {
  const saved = loadJsonFile(USER_AUTH_FILE, {});
  return {
    accessToken: String(saved.accessToken || "").trim(),
    username: String(saved.username || "").trim(),
    chatApiKey: String(saved.chatApiKey || "").trim()
  };
}

function saveDesktopAuth() {
  saveJsonFile(USER_AUTH_FILE, {
    accessToken: desktopAuth.accessToken || "",
    username: desktopAuth.username || "",
    chatApiKey: desktopAuth.chatApiKey || ""
  });
}

function clearDesktopAuth() {
  desktopAuth = { ...desktopAuth, accessToken: "", username: "" };
  saveDesktopAuth();
  return getDesktopAuthStatus();
}

function clearProviderApiKey() {
  desktopAuth = { ...desktopAuth, chatApiKey: "" };
  saveDesktopAuth();
  broadcastState();
  return getSafeState();
}

function getDesktopAuthStatus(extra = {}) {
  return {
    authenticated: Boolean(desktopAuth.accessToken),
    username: desktopAuth.username || "",
    ...extra
  };
}

function getProxyAuthHeaders() {
  return desktopAuth.accessToken ? { "X-Auth-Token": desktopAuth.accessToken } : {};
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
    chatApiKeyConfigured: Boolean(desktopAuth?.chatApiKey)
  };
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
    accessToken: String(data.access_token || "").trim(),
    username
  };
  saveDesktopAuth();
  saveState();
  return getDesktopAuthStatus();
}

async function verifyDesktopAuth(payload = {}) {
  if (!desktopAuth.accessToken) {
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

function rectanglesIntersectEnough(bounds, area) {
  const left = Math.max(bounds.x, area.x);
  const top = Math.max(bounds.y, area.y);
  const right = Math.min(bounds.x + bounds.width, area.x + area.width);
  const bottom = Math.min(bounds.y + bounds.height, area.y + area.height);
  const visibleWidth = Math.max(0, right - left);
  const visibleHeight = Math.max(0, bottom - top);
  return visibleWidth >= Math.min(80, bounds.width) && visibleHeight >= Math.min(80, bounds.height);
}

function centerBoundsInWorkArea(bounds, workArea) {
  const width = Math.min(bounds.width, Math.max(160, workArea.width));
  const height = Math.min(bounds.height, Math.max(160, workArea.height));
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
    const displays = screen.getAllDisplays();
    if (displays.some((display) => rectanglesIntersectEnough(coerced, display.workArea))) {
      return coerced;
    }
    const primaryWorkArea = screen.getPrimaryDisplay().workArea;
    return centerBoundsInWorkArea(coerced, primaryWorkArea);
  } catch (_) {
    return coerced;
  }
}

function normalizePersistedWindowBounds() {
  state.windowBounds = normalizeBoundsForDisplays(state.windowBounds, DEFAULT_STATE.windowBounds, { width: 240, height: 320 });
  state.controlBounds = normalizeBoundsForDisplays(state.controlBounds, DEFAULT_STATE.controlBounds, { width: 420, height: 560 });
  state.webClientBounds = normalizeBoundsForDisplays(state.webClientBounds, DEFAULT_STATE.webClientBounds, { width: 720, height: 520 });
  saveState();
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
    callback(isLocalRenderer && (permission === "media" || permission === "audioCapture"));
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

function applyAvatarWindowState() {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    return;
  }
  enforceAvatarOverlayWindow();
  const hudVisible = Boolean(state.quickHudVisible);
  try {
    if (typeof avatarWindow.isFocusable !== "function" || avatarWindow.isFocusable() !== hudVisible) {
      avatarWindow.setFocusable(hudVisible);
    }
    if (!hudVisible && (typeof avatarWindow.isFocused !== "function" || avatarWindow.isFocused())) {
      avatarWindow.blur();
    }
  } catch (_) {
    // ignore focusability issues on unsupported platforms
  }
  enforceAvatarOverlayWindow();
  avatarWindow.setAlwaysOnTop(Boolean(state.alwaysOnTop), state.alwaysOnTop ? "screen-saver" : "normal");
  avatarWindow.setOpacity(Math.max(0.35, Math.min(1, Number(state.opacity) || 1)));
  avatarWindow.setIgnoreMouseEvents(Boolean(state.clickThrough) && !Boolean(state.moveMode) && !hudVisible, {
    forward: true
  });

  if (state.visible) {
    if (!avatarWindow.isVisible()) {
      avatarWindow.showInactive();
    }
    if (hudVisible) {
      avatarWindow.show();
      avatarWindow.focus();
      enforceAvatarOverlayWindow();
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
  state[windowKey] = browserWindow.getBounds();
  saveState();
}

function getAvatarWindowOptions() {
  return {
    ...normalizeBoundsForDisplays(state.windowBounds, DEFAULT_STATE.windowBounds, { width: 240, height: 320 }),
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
    if (level >= 2) {
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
    ...normalizeBoundsForDisplays(state.controlBounds, DEFAULT_STATE.controlBounds, { width: 420, height: 560 }),
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

function createWebClientWindow() {
  webClientWindow = new BrowserWindow({
    ...normalizeBoundsForDisplays(state.webClientBounds, DEFAULT_STATE.webClientBounds, { width: 720, height: 520 }),
    minWidth: 720,
    minHeight: 520,
    autoHideMenuBar: true,
    show: false,
    backgroundColor: "#0f1117",
    title: "CATBot Web Client",
    icon: getLogoPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

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
  avatarWindow.setPosition(
    Math.round(avatarDragState.bounds.x + screenX - avatarDragState.startX),
    Math.round(avatarDragState.bounds.y + screenY - avatarDragState.startY)
  );
  return true;
}

function endAvatarDrag() {
  if (!avatarDragState) {
    return getSafeState();
  }
  avatarDragState = null;
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    state.windowBounds = avatarWindow.getBounds();
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
    nextBounds = centerBoundsInWorkArea(fallbackBounds, screen.getPrimaryDisplay().workArea);
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
  if (Object.prototype.hasOwnProperty.call(patch, "chatApiKey")) {
    desktopAuth.chatApiKey = String(patch.chatApiKey || "").trim();
    saveDesktopAuth();
    delete patch.chatApiKey;
  }
  delete patch.chatApiKeyConfigured;

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
  state.trustLocalCertificates = state.trustLocalCertificates !== false;
  if (!state.vrmTransforms || typeof state.vrmTransforms !== "object" || Array.isArray(state.vrmTransforms)) {
    state.vrmTransforms = {};
  }

  applyAvatarWindowState();
  applyLaunchAtLoginSetting();
  saveState();
  broadcastState();
  return getSafeState();
}

async function fetchDesktopToolingBundle(apiOrigin, options = {}) {
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

  try {
    const response = await net.fetch(`${apiOrigin}/v1/tools/openai`, {
      method: "GET",
      headers: buildProxyRequestHeaders({ Accept: "application/json" }),
      signal: options.signal
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
  }
  return desktopToolingCache;
}

function buildDesktopToolSystemPrompt(basePrompt, toolingBundle) {
  const dynamicTools = Array.isArray(toolingBundle?.promptLines) && toolingBundle.promptLines.length
    ? `\n\nAvailable proxy tools:\n${toolingBundle.promptLines.slice(0, 80).join("\n")}`
    : "";
  const toolRules = `You are CATBot, a concise desktop companion with access to proxy-server tools.

Tool calling rules:
- Prefer native tool calls when available.
- Use tools for current information, files, weather, web access, browser automation, code changes, memory, todos, and other actions exposed by the proxy.
- Do not invent tool outputs; execute the tool and use the returned result.
- Ask a short follow-up when a required tool argument is missing.
- If native tool calls are unavailable, use this XML fallback:
<tool>tool_name</tool>
<parameters>
{ "key": "value" }
</parameters>`;
  const customPrompt = String(basePrompt || "").trim();
  return `${customPrompt ? `${customPrompt}\n\n` : ""}${toolRules}${dynamicTools}`;
}

function buildDesktopChatBody({ messages, model, tools }) {
  const body = {
    messages,
    stream: false,
    temperature: 0.7
  };
  if (model) {
    body.model = model;
  }
  if (Array.isArray(tools) && tools.length > 0) {
    body.tools = tools;
    body.tool_choice = "auto";
  }
  return body;
}

async function requestDesktopChatCompletion(proxyUrl, body, headers, signal, apiOrigin) {
  const response = await net.fetch(proxyUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
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
    if (typeof toolResult.content === "string" && toolResult.content.trim()) {
      return `${toolResult.message || "Tool result"}\n\n${toolResult.content}`;
    }
    try {
      return JSON.stringify(toolResult);
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
  if (requestedWebClientUrl) {
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

  const endpoint = normalizeEndpointString(payload.chatEndpoint || state.chatEndpoint || DEFAULT_CHAT_ENDPOINT);
  const model = String(payload.chatModel || state.chatModel || "").trim();
  const chatApiKey = String(payload.chatApiKey || desktopAuth.chatApiKey || "").trim();
  const endpointOverride = shouldAllowEndpointOverride(endpoint, chatApiKey, desktopAuth.accessToken) ? endpoint : "";
  const requestedSystemPrompt = String(payload.chatSystemPrompt || state.chatSystemPrompt || "").trim();
  const history = normalizeDesktopChatHistory(payload.history || state.desktopChatHistory);
  const proxyUrl = `${apiOrigin}/v1/proxy/chat/completions${endpointOverride ? `?endpoint=${encodeURIComponent(endpointOverride)}` : ""}`;
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 120000);
  const toolingBundle = await fetchDesktopToolingBundle(apiOrigin, { signal: controller.signal });
  const tools = Array.isArray(toolingBundle.tools) ? toolingBundle.tools : [];
  const systemPrompt = buildDesktopToolSystemPrompt(requestedSystemPrompt, toolingBundle);
  const messages = [];
  if (systemPrompt) {
    messages.push({ role: "system", content: systemPrompt });
  }
  messages.push(...history);
  messages.push(buildDesktopUserMessage(userText, payload.screenImageDataUrl));

  state.expression = "think";
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
    let data = await requestDesktopChatCompletion(
      proxyUrl,
      buildDesktopChatBody({ messages, model, tools }),
      requestHeaders,
      controller.signal,
      apiOrigin
    );
    let assistantMessage = getDesktopChatResponseMessage(data);
    let reply = getVisibleDesktopAssistantText(assistantMessage);
    let toolIterations = 0;
    let lastToolResultContent = "";

    while (toolIterations < DESKTOP_TOOL_LOOP_MAX_ITERATIONS) {
      const nativeToolCalls = Array.isArray(assistantMessage?.tool_calls) ? assistantMessage.tool_calls : [];
      const xmlToolCall = !nativeToolCalls.length ? parseDesktopToolFallback(coerceDesktopMessageText(assistantMessage?.content || "")) : null;
      if (!nativeToolCalls.length && !xmlToolCall) {
        break;
      }

      messages.push(buildDesktopAssistantHistoryMessage(assistantMessage));
      const calls = nativeToolCalls.length ? nativeToolCalls : [xmlToolCall];
      for (const toolCall of calls) {
        const toolName = getDesktopToolCallName(toolCall);
        state.expression = "think";
        saveState();
        broadcastState();
        const toolResult = await executeDesktopToolCall(
          apiOrigin,
          toolCall,
          {
            conversation_id: "desktop-avatar",
            user_id: desktopAuth.username || "desktop-avatar",
            metadata: { channel: "electron_desktop_avatar" }
          },
          controller.signal
        );
        const toolResultContent = formatDesktopToolResultForModel(toolResult);
        lastToolResultContent = toolResultContent;
        if (nativeToolCalls.length) {
          messages.push({
            role: "tool",
            content: toolResultContent,
            tool_call_id: toolCall.id || toolName
          });
        } else {
          messages.push({ role: "user", content: `Tool result from ${toolName}: ${toolResultContent}` });
        }
      }

      data = await requestDesktopChatCompletion(
        proxyUrl,
        buildDesktopChatBody({ messages, model, tools }),
        requestHeaders,
        controller.signal,
        apiOrigin
      );
      assistantMessage = getDesktopChatResponseMessage(data);
      reply = getVisibleDesktopAssistantText(assistantMessage);
      toolIterations += 1;
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

    state.desktopChatHistory = normalizeDesktopChatHistory([
      ...history,
      { role: "user", content: userText },
      { role: "assistant", content: reply }
    ]);

    const shouldSpeak = payload.speakReply == null ? state.speakChatReplies : Boolean(payload.speakReply);
    state.speakChatReplies = shouldSpeak;
    state.expression = inferDesktopAvatarExpression(reply);
    if (shouldSpeak) {
      state.speechBubbleText = reply;
      state.speechDurationMs = calculateSpeechDurationMs(reply);
      state.speechTriggerId = Date.now();
    }

    saveState();
    broadcastState();
    return {
      reply,
      state: getSafeState()
    };
  } catch (error) {
    state.expression = "sad";
    saveState();
    broadcastState();
    if (error && error.name === "AbortError") {
      throw new Error("Desktop chat request timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
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
  state.desktopChatHistory = [];
  state.speechBubbleText = "";
  state.speechDurationMs = 300;
  state.speechTriggerId = Date.now();
  state.expression = "neutral";
  saveState();
  broadcastState();
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
      label: "Open Web Client In Browser",
      enabled: Boolean(state.webClientUrl),
      click: () => shell.openExternal(state.webClientUrl)
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
    "CommandOrControl+Shift+Space": () => toggleQuickHud()
  };

  for (const [accelerator, handler] of Object.entries(shortcuts)) {
    const registered = globalShortcut.register(accelerator, handler);
    if (!registered) {
      console.warn(`Failed to register desktop shortcut: ${accelerator}`);
    }
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
  shell.openExternal(state.webClientUrl);
  return true;
});
ipcMain.handle("desktop:send-chat-message", (_event, payload) => sendDesktopChatMessage(payload));
ipcMain.handle("desktop:clear-chat-history", () => clearDesktopChatHistory());
ipcMain.handle("desktop:capture-screen-snapshot", () => capturePrimaryScreenSnapshot());
ipcMain.handle("desktop:transcribe-audio", (_event, payload) => transcribeDesktopAudio(payload));
ipcMain.handle("desktop:resolve-asset-url", (_event, relativePath) => toAssetUrl(relativePath));
ipcMain.handle("desktop:synthesize-preview-speech", async (_event, payload = {}) => {
  const inputText = String(payload.text || "").trim();
  if (!inputText) {
    throw new Error("Speech preview text is required.");
  }

  const requestedProxyBaseUrl = normalizeUrlString(payload.proxyBaseUrl || state.proxyBaseUrl || DEFAULT_STATE.proxyBaseUrl || DEFAULT_PROXY_BASE_URL);
  if (requestedProxyBaseUrl) {
    state.proxyBaseUrl = requestedProxyBaseUrl;
  }
  const apiOrigin = getProxyOriginFromPayload(payload);
  if (!apiOrigin) {
    throw new Error("CATBot API/proxy URL is not configured.");
  }

  const ttsEndpointOrigin = extractOriginFromUrlLike(payload.ttsEndpoint || state.ttsEndpoint);
  if (!ttsEndpointOrigin) {
    throw new Error("TTS endpoint is not configured.");
  }
  const providerApiKey = String(payload.chatApiKey || desktopAuth.chatApiKey || "").trim();
  if (!shouldAllowEndpointOverride(ttsEndpointOrigin, providerApiKey, desktopAuth.accessToken)) {
    throw new Error("TTS endpoint override requires a configured provider API key, signed-in HUD auth, or a trusted local endpoint.");
  }

  const proxyUrl = `${apiOrigin}/v1/proxy/tts/speech?endpoint=${encodeURIComponent(ttsEndpointOrigin)}`;
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), 60000);

  try {
    const response = await net.fetch(proxyUrl, {
      method: "POST",
      headers: buildProxyRequestHeaders({
        "Content-Type": "application/json",
        Accept: "audio/mpeg, audio/wav;q=0.9, application/octet-stream;q=0.8"
      }, { providerApiKey }),
      body: JSON.stringify({
        model: String(payload.ttsModel || state.ttsModel || "tts-1").trim() || "tts-1",
        voice: String(payload.ttsVoice || state.ttsVoice || "alloy").trim() || "alloy",
        input: inputText,
        stream: false
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const errorText = String(await response.text()).trim();
      throw new Error(formatProxyResponseError(response, errorText, "Speech preview", apiOrigin));
    }

    return {
      audioBuffer: await response.arrayBuffer(),
      contentType: response.headers.get("content-type") || "audio/mpeg"
    };
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Speech preview request timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
});

if (hasSingleInstanceLock) {
  app.on("second-instance", () => {
    showExistingInstance();
  });

  app.on("before-quit", () => {
    isQuitting = true;
    globalShortcut.unregisterAll();
  });

  app.whenReady().then(() => {
    normalizePersistedWindowBounds();
    installLocalCertificateTrust();
    installMediaPermissionHandler();
    registerAssetProtocol();
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
