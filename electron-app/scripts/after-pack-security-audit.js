const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const asar = require("@electron/asar");

const TEXT_EXTENSIONS = new Set([
  ".css",
  ".html",
  ".ini",
  ".js",
  ".json",
  ".md",
  ".mjs",
  ".txt",
  ".xml",
  ".yaml",
  ".yml"
]);

const FORBIDDEN_FILENAMES = new Set([
  "auth_users.json",
  "desktop-auth.json",
  "embeddings.npy",
  "metadata.json",
  "telegram_user_links.json"
]);

const FORBIDDEN_EXTENSIONS = new Set([
  ".key",
  ".log",
  ".map",
  ".p12",
  ".pem",
  ".pfx",
  ".sqlite",
  ".sqlite3",
  ".zip"
]);

const CREDENTIAL_SIGNATURES = [
  ["private-key", /-----BEGIN (?:EC |OPENSSH |RSA )?PRIVATE KEY-----/],
  ["openai-compatible-key", /\bsk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{20,}\b/],
  ["github-token", /\bgh[pousr]_[A-Za-z0-9]{20,}\b/],
  ["google-api-key", /\bAIza[A-Za-z0-9_-]{30,}\b/],
  ["telegram-bot-token", /\b\d{8,12}:[A-Za-z0-9_-]{30,}\b/]
];

function normalizeArchivePath(value) {
  return String(value || "").replaceAll("\\", "/").replace(/^\/+/, "");
}

function isForbiddenPath(value) {
  const normalized = normalizeArchivePath(value).toLowerCase();
  const segments = normalized.split("/").filter(Boolean);
  const filename = segments.at(-1) || "";
  const extension = path.posix.extname(filename);

  if (segments.some((segment) => segment === ".env" || segment.startsWith(".env."))) {
    return true;
  }
  if (segments.some((segment) => segment === "memory_data")) {
    return true;
  }
  return FORBIDDEN_FILENAMES.has(filename) || FORBIDDEN_EXTENSIONS.has(extension);
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  const entries = [];
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const separator = line.indexOf("=");
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if (
      value.length >= 2
      && ((value.startsWith("\"") && value.endsWith("\""))
        || (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1);
    }
    if (!key || !value || !/(?:API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)/i.test(key)) {
      continue;
    }
    if (value.length < 12 || /^(?:change-me|example|placeholder|test|your[-_])/i.test(value)) {
      continue;
    }
    entries.push({ key, value });
  }
  return entries;
}

function loadKnownSecrets() {
  const electronRoot = path.resolve(__dirname, "..");
  const projectRoot = path.resolve(electronRoot, "..");
  const candidates = [
    path.join(projectRoot, ".env"),
    path.join(electronRoot, ".env")
  ];
  const secrets = [];
  const seen = new Set();

  for (const candidate of candidates) {
    for (const entry of parseEnvFile(candidate)) {
      const digest = crypto.createHash("sha256").update(entry.value).digest("hex");
      if (seen.has(digest)) {
        continue;
      }
      seen.add(digest);
      secrets.push(entry);
    }
  }
  return secrets;
}

function inspectText(relativePath, buffer, knownSecrets, findings) {
  const text = buffer.toString("utf8");
  for (const [label, pattern] of CREDENTIAL_SIGNATURES) {
    if (pattern.test(text)) {
      findings.push(`${relativePath}: credential signature ${label}`);
    }
  }
  for (const secret of knownSecrets) {
    if (text.includes(secret.value)) {
      findings.push(`${relativePath}: contains configured secret ${secret.key}`);
    }
  }
}

function shouldInspectText(relativePath, size) {
  if (size > 10 * 1024 * 1024) {
    return false;
  }
  const normalized = normalizeArchivePath(relativePath);
  return TEXT_EXTENSIONS.has(path.posix.extname(normalized).toLowerCase());
}

function walkFiles(rootPath) {
  const files = [];
  const stack = [rootPath];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile()) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

function auditPackagedApp(appOutDir) {
  const resolvedOutDir = path.resolve(appOutDir);
  if (!fs.existsSync(resolvedOutDir)) {
    throw new Error(`Packaged application directory does not exist: ${resolvedOutDir}`);
  }

  const findings = [];
  const knownSecrets = loadKnownSecrets();
  const files = walkFiles(resolvedOutDir);
  const asarFiles = files.filter((filePath) => path.basename(filePath).toLowerCase() === "app.asar");

  if (asarFiles.length === 0) {
    findings.push("app.asar was not found in the packaged application");
  }

  for (const archivePath of asarFiles) {
    for (const archiveEntry of asar.listPackage(archivePath)) {
      const relativePath = normalizeArchivePath(archiveEntry);
      if (isForbiddenPath(relativePath)) {
        findings.push(`app.asar/${relativePath}: forbidden packaged path`);
        continue;
      }
      const extractionPath = String(archiveEntry || "").replace(/^[\\/]+/, "");
      const archiveStat = asar.statFile(archivePath, extractionPath);
      if (archiveStat.files || !shouldInspectText(relativePath, Number(archiveStat.size || 0))) {
        continue;
      }
      const content = asar.extractFile(archivePath, extractionPath);
      inspectText(`app.asar/${relativePath}`, content, knownSecrets, findings);
    }
  }

  for (const filePath of files) {
    if (asarFiles.includes(filePath)) {
      continue;
    }
    const relativePath = normalizeArchivePath(path.relative(resolvedOutDir, filePath));
    if (isForbiddenPath(relativePath)) {
      findings.push(`${relativePath}: forbidden packaged path`);
      continue;
    }
    const stat = fs.statSync(filePath);
    if (shouldInspectText(relativePath, stat.size)) {
      inspectText(relativePath, fs.readFileSync(filePath), knownSecrets, findings);
    }
  }

  if (findings.length) {
    throw new Error(
      `Electron package security audit failed:\n${[...new Set(findings)]
        .sort()
        .map((finding) => `- ${finding}`)
        .join("\n")}`
    );
  }

  console.log(`[electron-security] Packaged artifact audit passed: ${resolvedOutDir}`);
}

async function afterPack(context) {
  auditPackagedApp(context.appOutDir);
}

module.exports = afterPack;
module.exports.auditPackagedApp = auditPackagedApp;
module.exports.isForbiddenPath = isForbiddenPath;

if (require.main === module) {
  const target = process.argv[2];
  if (!target) {
    console.error("Usage: node scripts/after-pack-security-audit.js <packaged-app-directory>");
    process.exitCode = 2;
  } else {
    try {
      auditPackagedApp(target);
    } catch (error) {
      console.error(String(error?.message || error));
      process.exitCode = 1;
    }
  }
}
