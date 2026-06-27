        // At the start of your script section, add these lines:
        window.PIXI = PIXI;
        window.EventEmitter3.EventEmitter = EventEmitter3;

        const startRecordBtn = document.getElementById('start-record-btn');
        const sendBtn = document.getElementById('send-btn');
        const philosopherModeBtn = document.getElementById('philosopher-mode-btn');
        const userInput = document.getElementById('user-input');
        // Shared send handler (assigned later) - used by mobile send button so iOS Safari doesn't need programmatic click
        window.submitUserMessage = null;
        const responseOutput = document.getElementById('response-output');
        const messageHistory = document.getElementById('message-history'); // New message history container

        // Mobile UI handlers
        const hamburgerBtn = document.getElementById('hamburger-btn');
        const settingsOverlay = document.getElementById('settings-overlay');
        const settingsMenu = document.getElementById('settings-menu');
        const closeSettingsBtn = document.getElementById('close-settings-btn');
        const newChatBtnMobile = document.getElementById('new-chat-btn-mobile');
        const hideChatBtn = document.getElementById('hide-chat-btn');
        const hideChatIcon = document.getElementById('hide-chat-icon');
        const attachBtn = document.getElementById('attach-btn');
        const attachmentInput = document.getElementById('attachment-input');
        const attachmentPreview = document.getElementById('attachment-preview');
        const attachmentPreviewList = document.getElementById('attachment-preview-list');
        const attachmentClearBtn = document.getElementById('attachment-clear-btn');
        const thinkBtn = document.getElementById('think-btn');
        const MAX_PENDING_ATTACHMENTS = 6;
        const MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024;
        let pendingAttachmentFiles = [];

        // Settings menu toggle
        if (hamburgerBtn && settingsOverlay && settingsMenu) {
            hamburgerBtn.addEventListener('click', function() {
                settingsOverlay.classList.add('active');
                settingsMenu.classList.add('active');
                if (typeof renderCompanionList === 'function') renderCompanionList();
            });

            closeSettingsBtn.addEventListener('click', function() {
                settingsOverlay.classList.remove('active');
                settingsMenu.classList.remove('active');
            });

            settingsOverlay.addEventListener('click', function() {
                settingsOverlay.classList.remove('active');
                settingsMenu.classList.remove('active');
            });
        }

        // Hide chat button - toggle chat visibility
        if (hideChatBtn) {
            hideChatBtn.addEventListener('click', function() {
                const container = document.querySelector('.container');
                const isHidden = container.classList.contains('chat-hidden');
                
                if (isHidden) {
                    // Show chat
                    container.classList.remove('chat-hidden');
                    if (hideChatIcon) {
                        hideChatIcon.className = 'fas fa-chevron-down';
                    }
                    hideChatBtn.title = 'Hide Chat';
                } else {
                    // Hide chat
                    container.classList.add('chat-hidden');
                    if (hideChatIcon) {
                        hideChatIcon.className = 'fas fa-chevron-up';
                    }
                    hideChatBtn.title = 'Show Chat';
                }
                
                // Trigger resize event to update avatar canvas size
                // Use setTimeout to ensure CSS transition completes before resize
                setTimeout(() => {
                    window.dispatchEvent(new Event('resize'));
                }, 100);
            });
        }

        // Conversation history panel toggle
        const conversationOverlay = document.getElementById('conversation-overlay');
        const conversationPanel = document.getElementById('conversation-history-panel');
        const closeConversationBtn = document.getElementById('close-conversation-btn');
        const newConversationBtnMobile = document.getElementById('new-conversation-btn-mobile');
        
        // Ensure conversation overlay is hidden by default on page load - trigger close action
        if (conversationOverlay && conversationPanel) {
            conversationOverlay.classList.remove('active');
            conversationPanel.classList.remove('active');
        }

        if (newChatBtnMobile && conversationOverlay && conversationPanel) {
            // Toggle conversation history panel when burger button is clicked
            newChatBtnMobile.addEventListener('click', function() {
                conversationOverlay.classList.add('active');
                conversationPanel.classList.add('active');
                // Render conversation list when panel opens
                renderConversationList();
            });

            // Close panel when close button is clicked
            if (closeConversationBtn) {
                closeConversationBtn.addEventListener('click', function() {
                    conversationOverlay.classList.remove('active');
                    conversationPanel.classList.remove('active');
                });
                
                // Trigger close action on page load to ensure overlay is hidden by default
                closeConversationBtn.click();
            }

            // Close panel when overlay is clicked
            conversationOverlay.addEventListener('click', function() {
                conversationOverlay.classList.remove('active');
                conversationPanel.classList.remove('active');
            });
        }

        // New conversation button in mobile panel
        if (newConversationBtnMobile) {
            newConversationBtnMobile.addEventListener('click', function() {
                const newConv = createNewConversation('New Conversation');
                switchToConversation(newConv.id);
                // Close the panel after creating new conversation
                if (conversationOverlay && conversationPanel) {
                    conversationOverlay.classList.remove('active');
                    conversationPanel.classList.remove('active');
                }
            });
        }


        // Auto-resize textarea
        const USER_INPUT_MAX_HEIGHT = 120;
        let userInputBaseHeight = null;

        function getUserInputBaseHeight(minHeight) {
            if (!userInput) return minHeight;
            if (userInputBaseHeight !== null) return userInputBaseHeight;

            const previousHeight = userInput.style.height;
            userInput.style.height = 'auto';
            userInputBaseHeight = Math.max(minHeight, userInput.scrollHeight);
            userInput.style.height = previousHeight;
            return userInputBaseHeight;
        }

        function resizeUserInput() {
            if (!userInput) return;

            const minHeight = parseFloat(window.getComputedStyle(userInput).minHeight) || 0;
            const baseHeight = getUserInputBaseHeight(minHeight);

            if (userInput.value.length === 0) {
                userInput.style.height = `${baseHeight}px`;
                userInput.scrollTop = 0;
                return;
            }

            userInput.style.height = '0px';
            userInput.style.height = Math.max(baseHeight, Math.min(userInput.scrollHeight, USER_INPUT_MAX_HEIGHT)) + 'px';
        }

        function syncUserInputUi() {
            if (!userInput) return;

            resizeUserInput();

            if (userInput.value.length === 0) {
                window.requestAnimationFrame(() => {
                    if (userInput && userInput.value.length === 0) {
                        resizeUserInput();
                    }
                });
            }

            if (sendBtnMobile) {
                const hasText = userInput.value.trim().length > 0;
                const hasAttachments = pendingAttachmentFiles.length > 0;
                sendBtnMobile.style.display = (hasText || hasAttachments) ? 'flex' : 'none';
                if (startRecordBtn) startRecordBtn.style.display = (hasText || hasAttachments) ? 'none' : 'flex';
            }
        }

        function formatAttachmentSize(bytes = 0) {
            if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
            if (bytes < 1024) return `${bytes} B`;
            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        }

        function clearPendingAttachments() {
            pendingAttachmentFiles = [];
            if (attachmentInput) attachmentInput.value = '';
            renderAttachmentPreview();
            syncUserInputUi();
        }

        function renderAttachmentPreview() {
            if (!attachmentPreview || !attachmentPreviewList) return;

            if (!pendingAttachmentFiles.length) {
                attachmentPreview.style.display = 'none';
                attachmentPreviewList.innerHTML = '';
                return;
            }

            attachmentPreview.style.display = 'block';
            attachmentPreviewList.innerHTML = '';

            pendingAttachmentFiles.forEach((file, index) => {
                const chip = document.createElement('div');
                chip.className = 'attachment-chip';

                const name = document.createElement('span');
                name.className = 'attachment-chip-name';
                name.title = file.name || '';
                name.textContent = file.name || 'attachment';

                const size = document.createElement('span');
                size.className = 'attachment-chip-size';
                size.textContent = formatAttachmentSize(file.size);

                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'attachment-chip-remove';
                button.setAttribute('data-attachment-index', String(index));
                button.setAttribute('aria-label', 'Remove attachment');
                button.textContent = 'x';
                button.addEventListener('click', () => {
                    const index = Number(button.getAttribute('data-attachment-index'));
                    if (Number.isInteger(index) && index >= 0) {
                        pendingAttachmentFiles.splice(index, 1);
                        renderAttachmentPreview();
                        syncUserInputUi();
                    }
                });

                chip.append(name, size, button);
                attachmentPreviewList.appendChild(chip);
            });
        }

        function addPendingAttachments(fileList) {
            const incomingFiles = Array.from(fileList || []);
            if (!incomingFiles.length) return;

            const nextFiles = [...pendingAttachmentFiles];
            const rejectedNames = [];
            for (const file of incomingFiles) {
                if (nextFiles.length >= MAX_PENDING_ATTACHMENTS) {
                    rejectedNames.push(file.name);
                    continue;
                }
                if (file.size > MAX_ATTACHMENT_SIZE_BYTES) {
                    rejectedNames.push(file.name);
                    continue;
                }
                nextFiles.push(file);
            }

            pendingAttachmentFiles = nextFiles;
            renderAttachmentPreview();
            syncUserInputUi();

            if (rejectedNames.length) {
                console.warn('Rejected attachment(s):', rejectedNames);
            }
        }

        if (userInput) {
            userInput.addEventListener('input', syncUserInputUi);
        }

        if (attachBtn) {
            attachBtn.addEventListener('click', function() {
                if (attachmentInput) attachmentInput.click();
            });
        }

        if (attachmentInput) {
            attachmentInput.addEventListener('change', function(event) {
                addPendingAttachments(event.target.files);
                attachmentInput.value = '';
            });
        }

        if (attachmentClearBtn) {
            attachmentClearBtn.addEventListener('click', function() {
                clearPendingAttachments();
            });
        }

        // Think button - toggles philosopher mode
        if (thinkBtn) {
            thinkBtn.addEventListener('click', async function() {
                // Toggle philosopher mode on/off
                await togglePhilosopherMode();
            });
        }

        // iOS Safari viewport height fix
        function setViewportHeight() {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        }
        setViewportHeight();
        window.addEventListener('resize', setViewportHeight);
        window.addEventListener('orientationchange', setViewportHeight);

        // Send button mobile - show/hide based on input
        const sendBtnMobile = document.getElementById('send-btn-mobile');
        if (userInput && sendBtnMobile) {
            // Handle blur event - switch back to microphone button when input loses focus
            userInput.addEventListener('blur', function() {
                syncUserInputUi();
            });

            // Handle focus event - show send button if there's text when input regains focus
            userInput.addEventListener('focus', function() {
                syncUserInputUi();
            });

            // Send on button click - call shared handler directly (iOS Safari ignores programmatic sendBtn.click() on display:none)
            sendBtnMobile.addEventListener('click', function() {
                if ((userInput.value.trim().length > 0 || pendingAttachmentFiles.length > 0) && window.submitUserMessage) {
                    window.submitUserMessage();
                }
            });
            // iOS Safari: touchend fires reliably; click can be delayed or lost when keyboard is open
            sendBtnMobile.addEventListener('touchend', function(e) {
                if ((userInput.value.trim().length > 0 || pendingAttachmentFiles.length > 0) && window.submitUserMessage) {
                    e.preventDefault();
                    window.submitUserMessage();
                }
            }, { passive: false });
        }
        syncUserInputUi();
        const userNameInput = document.getElementById('user-name'); // User name input
        const assistantNameInput = document.getElementById('assistant-name'); // Assistant name input
        const status = document.getElementById('status');
        const endpointInput = document.getElementById('endpoint-url');
        const apiKeyInput = document.getElementById('api-key');
        const newsApiKeyInput = document.getElementById('news-api-key');
        const systemPromptInput = document.getElementById('system-prompt');
        const soulPromptDisplay = document.getElementById('soul-prompt-display');
        const voiceDropdown = document.getElementById('voice-dropdown');
        const ttsServiceMicrosoft = document.getElementById('tts-service-microsoft'); // Microsoft TTS service radio
        const ttsServiceOpenAI = document.getElementById('tts-service-openai'); // OpenAI-compatible TTS service radio
        const ttsEndpointInput = document.getElementById('tts-endpoint-url'); // TTS endpoint input
        const ttsModelDropdown = document.getElementById('tts-model-dropdown'); // TTS model dropdown
        const ttsVoiceDropdown = document.getElementById('tts-voice-dropdown'); // TTS voice dropdown
        const refreshTtsVoicesBtn = document.getElementById('refresh-tts-voices-btn'); // Refresh TTS voices button
        const SELECTED_VOICE_STORAGE_KEY = 'selectedVoiceURI'; // Persist selected voice across browser sessions
        
        // Server configuration for remote access
        // Detect server IP from URL parameter, current hostname, or default to localhost
        function getServerBase() {
            // Check for server parameter in URL (e.g., ?server=192.168.1.100)
            const urlParams = new URLSearchParams(window.location.search);
            const serverParam = urlParams.get('server');
            if (serverParam) {
                return serverParam; // Return IP from URL parameter
            }
            // If accessed via IP address (not localhost), use current hostname
            const currentHost = window.location.hostname;
            if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
                return currentHost; // Use the IP/hostname from which the page was accessed
            }
            // Default to localhost for local access
            return 'localhost';
        }
        
        // Get the server base (IP or hostname)
        const SERVER_BASE = getServerBase();
        // Get the current protocol (http or https) - use https for secure connections
        const PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const PROXY_BASE_PORT = '8002';
        const PROXY_BASE_URL_STORAGE_KEY = 'catbotProxyBaseUrl';
        // Opening index.html directly uses the file: protocol. The proxy still runs on HTTPS.
        const INITIAL_PROXY_PROTOCOL = window.location.protocol === 'http:' ? 'http:' : 'https:';
        // Construct base URLs using the detected server with HTTPS
        let PROXY_BASE_URL = `${INITIAL_PROXY_PROTOCOL}//${SERVER_BASE}:${PROXY_BASE_PORT}`;
        const MCP_BROWSER_BASE_URL = `${PROTOCOL}//${SERVER_BASE}:5001`;
        
        // Make PROXY_BASE_URL available globally for ai-autogen-call.js
        window.PROXY_BASE_URL = PROXY_BASE_URL;
        
        // Helper function to resolve relative model paths to absolute URLs for remote access
        function resolveModelPath(relativePath) {
            // If path is already absolute (starts with http:// or https://), return as-is
            if (relativePath.startsWith('http://') || relativePath.startsWith('https://')) {
                return relativePath;
            }
            // Convert relative path to absolute URL using current origin
            const baseUrl = `${PROTOCOL}//${window.location.hostname}:${window.location.port || (PROTOCOL === 'https:' ? '8000' : '8000')}`;
            // Remove leading ./ if present
            const cleanPath = relativePath.startsWith('./') ? relativePath.substring(2) : relativePath;
            // Ensure path starts with /
            const normalizedPath = cleanPath.startsWith('/') ? cleanPath : '/' + cleanPath;
            return baseUrl + normalizedPath;
        }
        const AUTH_TOKEN_STORAGE_KEY = 'jwtAuthToken';

        function safeLocalStorageGet(key) {
            try {
                return window.localStorage?.getItem(key) || '';
            } catch (error) {
                console.warn(`Could not read ${key} from localStorage:`, error);
                return '';
            }
        }

        function safeLocalStorageSet(key, value) {
            try {
                window.localStorage?.setItem(key, value);
            } catch (error) {
                console.warn(`Could not persist ${key} to localStorage:`, error);
            }
        }

        function safeLocalStorageRemove(key) {
            try {
                window.localStorage?.removeItem(key);
            } catch (error) {
                console.warn(`Could not remove ${key} from localStorage:`, error);
            }
        }

        function safeSessionStorageGet(key) {
            try {
                return window.sessionStorage?.getItem(key) || '';
            } catch (error) {
                console.warn(`Could not read ${key} from sessionStorage:`, error);
                return '';
            }
        }

        function safeSessionStorageSet(key, value) {
            try {
                window.sessionStorage?.setItem(key, value);
            } catch (error) {
                console.warn(`Could not persist ${key} to sessionStorage:`, error);
            }
        }

        function safeSessionStorageRemove(key) {
            try {
                window.sessionStorage?.removeItem(key);
            } catch (error) {
                console.warn(`Could not remove ${key} from sessionStorage:`, error);
            }
        }

        const legacyAuthToken = safeLocalStorageGet(AUTH_TOKEN_STORAGE_KEY);
        if (legacyAuthToken) {
            safeSessionStorageSet(AUTH_TOKEN_STORAGE_KEY, legacyAuthToken);
            safeLocalStorageRemove(AUTH_TOKEN_STORAGE_KEY);
        }
        let authToken = safeSessionStorageGet(AUTH_TOKEN_STORAGE_KEY) || '';

        const authOverlay = document.getElementById('auth-overlay');
        const authUsernameInput = document.getElementById('auth-username');
        const authPasswordInput = document.getElementById('auth-password');
        const authStatus = document.getElementById('auth-status');
        const authLoginBtn = document.getElementById('auth-login-btn');
        const authSignupBtn = document.getElementById('auth-signup-btn');
        const authLogoutBtn = document.getElementById('auth-logout-btn');
        // Guard so post-auth initialization runs only once (e.g. from DOMContentLoaded or after login)
        let appInitialized = false;
        let envToolDefaults = null;

        function showAuthOverlay(message = '') {
            if (authOverlay) authOverlay.style.display = 'flex';
            if (authStatus) authStatus.textContent = message;
        }

        function hideAuthOverlay() {
            if (authOverlay) authOverlay.style.display = 'none';
            if (authStatus) authStatus.textContent = '';
        }

        function setAuthToken(token) {
            authToken = token || '';
            safeLocalStorageRemove(AUTH_TOKEN_STORAGE_KEY);
            if (authToken) safeSessionStorageSet(AUTH_TOKEN_STORAGE_KEY, authToken);
            else safeSessionStorageRemove(AUTH_TOKEN_STORAGE_KEY);
        }

        function normalizeProxyBaseUrl(baseUrl) {
            const value = String(baseUrl || '').trim();
            if (!value) return '';
            if (!/^https?:\/\//i.test(value)) {
                const host = normalizeProxyHost(value);
                return host ? `https://${host}:${PROXY_BASE_PORT}` : '';
            }
            try {
                const parsed = new URL(value);
                return `${parsed.protocol}//${parsed.host}`;
            } catch {
                return value.replace(/\/+$/, '');
            }
        }

        function setProxyBaseUrl(baseUrl) {
            const normalized = normalizeProxyBaseUrl(baseUrl);
            if (!normalized) return;
            PROXY_BASE_URL = normalized;
            window.PROXY_BASE_URL = normalized;
            safeLocalStorageSet(PROXY_BASE_URL_STORAGE_KEY, normalized);
        }

        function addUniqueProxyBase(candidates, seen, baseUrl) {
            const normalized = normalizeProxyBaseUrl(baseUrl);
            if (!normalized || seen.has(normalized)) return;
            seen.add(normalized);
            candidates.push(normalized);
        }

        function normalizeProxyHost(host) {
            const cleaned = String(host || '')
                .trim()
                .replace(/^https?:\/\//i, '')
                .replace(/\/.*$/, '');
            if (!cleaned) return '';
            const withoutPort = cleaned.replace(/:\d+$/, '');
            return withoutPort || cleaned;
        }

        function getConfiguredProxyBaseFromPage() {
            const urlParams = new URLSearchParams(window.location.search);
            const queryProxyBase = urlParams.get('proxyBaseUrl') || urlParams.get('proxy');
            if (queryProxyBase) return queryProxyBase;
            return document.querySelector('meta[name="catbot-proxy-base-url"]')?.content || '';
        }

        function getProxyBaseCandidates() {
            const candidates = [];
            const seen = new Set();
            const storedProxyBase = safeLocalStorageGet(PROXY_BASE_URL_STORAGE_KEY);
            const configuredProxyBase = getConfiguredProxyBaseFromPage();

            addUniqueProxyBase(candidates, seen, storedProxyBase);
            addUniqueProxyBase(candidates, seen, configuredProxyBase);
            if (PROXY_BASE_URL.startsWith('https://')) {
                addUniqueProxyBase(candidates, seen, PROXY_BASE_URL);
            }

            const configuredHttpsHost = normalizeProxyHost(
                document.querySelector('meta[name="catbot-https-hostname"]')?.content
            );
            const hosts = [
                configuredHttpsHost,
                normalizeProxyHost(SERVER_BASE),
                normalizeProxyHost(window.location.hostname),
                'localhost',
                '127.0.0.1'
            ].filter(Boolean);

            for (const host of hosts) {
                addUniqueProxyBase(candidates, seen, `https://${host}:${PROXY_BASE_PORT}`);
            }
            addUniqueProxyBase(candidates, seen, PROXY_BASE_URL);
            for (const host of hosts) {
                addUniqueProxyBase(candidates, seen, `http://${host}:${PROXY_BASE_PORT}`);
            }

            return candidates;
        }

        async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
            try {
                return await originalFetch(url, { ...options, signal: controller.signal });
            } finally {
                window.clearTimeout(timeoutId);
            }
        }

        async function fetchProxyEndpoint(path, options = {}) {
            let lastError = null;
            const headers = new Headers(options.headers || {});
            if (authToken && !headers.has('X-Auth-Token')) {
                headers.set('X-Auth-Token', authToken);
            }
            const authenticatedOptions = { ...options, headers };
            for (const baseUrl of getProxyBaseCandidates()) {
                try {
                    const response = await fetchWithTimeout(`${baseUrl}${path}`, authenticatedOptions);
                    setProxyBaseUrl(baseUrl);
                    return response;
                } catch (error) {
                    lastError = error;
                    console.warn(`Could not reach CATBot proxy at ${baseUrl}:`, error);
                }
            }
            throw lastError || new Error('Unable to reach CATBot proxy');
        }

        function proxyConnectionErrorMessage(error) {
            if (error?.name === 'AbortError') {
                return 'Could not reach CATBot proxy before the login request timed out.';
            }
            return 'Could not reach CATBot proxy. Check that the CATBot services are running, then try again.';
        }

        function getRequestPathname(requestUrl = '') {
            try {
                return new URL(String(requestUrl || ''), window.location.href).pathname;
            } catch (_) {
                return String(requestUrl || '').split('?')[0] || '';
            }
        }

        function isProxyRouteWithProviderAuthSemantics(requestUrl = '') {
            const pathname = getRequestPathname(requestUrl);
            return (
                pathname === '/v1/proxy/chat/completions' ||
                pathname === '/v1/proxy/models' ||
                pathname.startsWith('/v1/proxy/tts/') ||
                pathname === '/v1/audio/transcriptions'
            );
        }

        const originalFetch = window.fetch.bind(window);
        window.fetch = async function(input, init = {}) {
            const requestUrl = typeof input === 'string' ? input : input?.url || '';
            const isProxyRequest = requestUrl.startsWith(PROXY_BASE_URL) || requestUrl.startsWith('/v1/');
            const isAuthRoute = requestUrl.includes('/v1/auth/login') || requestUrl.includes('/v1/auth/signup');

            if (isProxyRequest && authToken && !isAuthRoute) {
                const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined) || {});
                if (!headers.has('X-Auth-Token')) headers.set('X-Auth-Token', authToken);
                init = { ...init, headers };
            }

            const response = await originalFetch(input, init);
            if (
                isProxyRequest &&
                response.status === 401 &&
                !isAuthRoute &&
                !isProxyRouteWithProviderAuthSemantics(requestUrl)
            ) {
                showAuthOverlay('Session expired. Please log in again.');
                setAuthToken('');
            }
            return response;
        };

        async function performAuth(action) {
            const username = (authUsernameInput?.value || '').trim();
            const password = authPasswordInput?.value || '';
            if (!username || !password) {
                showAuthOverlay('Username and password are required.');
                return false;
            }

            if (authStatus) authStatus.textContent = 'Authenticating...';
            let response;
            try {
                response = await fetchProxyEndpoint(`/v1/auth/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
            } catch (error) {
                console.error('Authentication request failed:', error);
                showAuthOverlay(proxyConnectionErrorMessage(error));
                return false;
            }

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                showAuthOverlay(data.detail || 'Authentication failed.');
                return false;
            }

            try {
                setAuthToken(data.access_token);
                hideAuthOverlay();
                await runAppInitialization();
                await fetchTodoListFromServer();
            } catch (error) {
                console.error('Authentication completed but app setup failed:', error);
                showAuthOverlay('Signed in, but the app could not finish setup. Refresh the page and try again.');
                return false;
            }
            return true;
        }

        async function verifyExistingAuth() {
            if (!authToken) {
                showAuthOverlay('Please log in to continue.');
                return false;
            }

            let response;
            try {
                response = await fetchProxyEndpoint('/v1/auth/me', {
                    headers: { Authorization: `Bearer ${authToken}` }
                });
            } catch (error) {
                console.error('Session verification failed:', error);
                showAuthOverlay(proxyConnectionErrorMessage(error));
                return false;
            }

            if (!response.ok) {
                setAuthToken('');
                showAuthOverlay('Please log in to continue.');
                return false;
            }

            hideAuthOverlay();
            return true;
        }

        // Post-auth app initialization: VRM, mic, avatar, webcam, conversations, etc. Run once from DOMContentLoaded (when already authenticated) or after performAuth() (when user just logged in). On failure we set appInitialized = false so retry (e.g. login again) can run init again.
        async function runAppInitialization() {
            if (appInitialized) return;
            appInitialized = true;
            try {
                // Initialize variables: todo from backend when authenticated, else localStorage fallback; memory from localStorage
                try {
                    await fetchTodoListFromServer();
                    memoryCache = JSON.parse(localStorage.getItem('memoryCache') || storage.getItem('memoryCache')) || [];
                } catch (storageError) {
                    console.warn('Could not load initial state:', storageError);
                    todoList = [];
                    memoryCache = [];
                }

                envToolDefaults = await fetchClientToolDefaults();
                renderSoulPromptPreview(envToolDefaults ? envToolDefaults.soulPrompt : '');
                // Load persisted tool settings (User Name, Assistant Name, etc.)
                const persistedToolSettings = (() => {
                    try {
                        const rawSettings = localStorage.getItem('toolSettings');
                        return rawSettings ? JSON.parse(rawSettings) : null;
                    } catch (error) {
                        console.warn('Could not read persisted tool settings during initialization:', error);
                        return null;
                    }
                })();
                let initialToolSettings = persistedToolSettings;
                if (defaultCompanionId) {
                    try {
                        const defaultCompanion = await fetchCompanionRecord(defaultCompanionId);
                        if (defaultCompanion && defaultCompanion.settings) {
                            initialToolSettings = defaultCompanion.settings;
                            activeCompanionId = defaultCompanionId;
                            activeCompanionName = defaultCompanion.name || defaultCompanionId;
                            latestSavedCompanionId = defaultCompanionId;
                            latestSavedCompanionName = activeCompanionName;
                            companionHasUnsavedChanges = false;
                        }
                    } catch (error) {
                        console.warn('Could not load default companion during initialization:', error);
                        if (/not found|404/i.test(String(error && error.message || ''))) {
                            setDefaultCompanion(null, { render: false, refreshDraft: false });
                        }
                    }
                }
                loadToolSettings(initialToolSettings);
                // Ensure VRM version is initialized (default to 1.0 if not set)
                const vrmVersionDropdown = document.getElementById('vrm-version-dropdown');
                if (vrmVersionDropdown && !vrmVersion) {
                    vrmVersion = vrmVersionDropdown.value || '1.0';
                }

                // Initialize core features
                loadVoices();
                if (typeof speechSynthesis !== 'undefined' && speechSynthesis.onvoiceschanged !== undefined) {
                    speechSynthesis.onvoiceschanged = loadVoices;
                }

                // Fetch available models based on current tool settings (also sets VRM list and currentVRMModelPath)
                await fetchAvailableModels(initialToolSettings);
                await scanAndMergeModelAvatarLists({ silent: true });
                if (activeCompanionId) {
                    activeCompanionSignature = getSettingsSignature(getToolSettingsFromDOM());
                    latestSavedCompanionSignature = activeCompanionSignature;
                    saveToolSettings({ syncDirtyState: false });
                }
                await initAudioRecording();
                // Initialize avatar based on mode preference (default to Live2D)
                const avatarMode = localStorage.getItem('avatarMode') || 'live2d';
                if (avatarMode === 'vrm') {
                    document.getElementById('vrm-mode').checked = true;
                    await switchToVRM();
                } else {
                    document.getElementById('live2d-mode').checked = true;
                    await switchToLive2D();
                }
                await initWebcam();

                // Initialize collapsible sections
                const collapsibleBtn = document.querySelector('.collapsible-btn');
                const collapsibleContent = document.querySelector('.collapsible-content');
                if (collapsibleBtn && collapsibleContent) {
                    collapsibleBtn.addEventListener('click', function() {
                        this.classList.toggle('active');
                        collapsibleContent.classList.toggle('active');
                        const isExpanded = this.classList.contains('active');
                        this.setAttribute('aria-expanded', isExpanded);
                        if (isExpanded) setActiveToolSettingsPanel(activeToolSettingsPanelId, { scrollIntoView: false });
                    });
                }

                setupToolSettingsBuilderUI();

                // Add event listeners to save tool settings when they change
                setupToolSettingsPersistence();

                // Companions UI: list, add modal, load/delete
                setupCompanionsUI();

                // Initialize conversation management system
                loadConversations();

                // Load sidebar state
                loadSidebarState();

                // Ensure conversation overlay is hidden on page load - trigger close action
                setTimeout(function() {
                    const conversationOverlay = document.getElementById('conversation-overlay');
                    const conversationPanel = document.getElementById('conversation-history-panel');
                    if (conversationOverlay && conversationPanel) {
                        conversationOverlay.classList.remove('active');
                        conversationPanel.classList.remove('active');
                    }
                }, 0);

                // Initialize clipboard monitoring if Clipboard Vision Mode is already enabled
                if (clipboardToggle && clipboardToggle.checked) {
                    clipboardVisionEnabled = true;
                    startClipboardMonitoring();
                }

                // New conversation button handler
                const newConversationBtn = document.getElementById('new-conversation-btn');
                if (newConversationBtn) {
                    newConversationBtn.addEventListener('click', () => {
                        const newConv = createNewConversation('New Conversation');
                        switchToConversation(newConv.id);
                    });
                }

                // Sidebar toggle button handler
                const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
                if (sidebarToggleBtn) {
                    sidebarToggleBtn.addEventListener('click', () => {
                        toggleSidebar();
                    });
                }

                // Right panel toggle button handler
                const rightPanelToggleBtn = document.getElementById('right-panel-toggle-btn');
                if (rightPanelToggleBtn) {
                    rightPanelToggleBtn.addEventListener('click', () => {
                        toggleRightPanel();
                    });
                }

                // Load right panel state
                loadRightPanelState();
            } catch (error) {
                console.error('Error during initialization:', error);
                appInitialized = false; // Allow retry (e.g. after login again or refresh)
            }
        }

        let voices = [];
        let audioContextResumed = false; // True after at least one successful gesture-based audio unlock
        let audioUnlockListenersInstalled = false; // Prevent duplicate global unlock listeners
        const userAgent = navigator.userAgent || '';
        const isIOSDevice = /iPad|iPhone|iPod/.test(userAgent) ||
            (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        // Safari/iOS may need a tiny rendered buffer after resume for stable playback/lip sync.
        function primeAudioContext(context) {
            try {
                if (!context) return;
                const buffer = context.createBuffer(1, 1, context.sampleRate || 44100);
                const source = context.createBufferSource();
                source.buffer = buffer;
                source.connect(context.destination);
                source.start(0);
                source.stop(0);
                source.disconnect();
            } catch (_) {}
        }

        // Resume known audio contexts from a user gesture. Safe to call repeatedly.
        async function resumeAudioContextOnce() {
            let resumedAny = false;
            try {
                // Opus decoder context (used by streamed PCM path).
                if (window.__opus?.audioCtx) {
                    if (window.__opus.audioCtx.state === 'suspended' && typeof window.__opus.resume === 'function') {
                        await window.__opus.resume();
                    }
                    if (window.__opus.audioCtx.state === 'running') {
                        primeAudioContext(window.__opus.audioCtx);
                        resumedAny = true;
                    }
                }

                // Main WebAudio context used by recorder/lip sync paths.
                if (audioContext && audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                if (audioContext && audioContext.state === 'running') {
                    primeAudioContext(audioContext);
                    resumedAny = true;
                }
            } catch (e) {
                console.warn('Audio unlock attempt failed:', e);
            }

            if (resumedAny) {
                audioContextResumed = true;
                removeGlobalAudioUnlockListeners();
            }
        }

        async function handleGlobalAudioUnlock() {
            await resumeAudioContextOnce();
        }

        function installGlobalAudioUnlockListeners() {
            if (audioUnlockListenersInstalled) return;
            audioUnlockListenersInstalled = true;
            const opts = { capture: true, passive: true };
            document.addEventListener('pointerdown', handleGlobalAudioUnlock, opts);
            document.addEventListener('touchstart', handleGlobalAudioUnlock, opts);
            document.addEventListener('click', handleGlobalAudioUnlock, opts);
            document.addEventListener('keydown', handleGlobalAudioUnlock, opts);
        }

        function removeGlobalAudioUnlockListeners() {
            if (!audioUnlockListenersInstalled) return;
            audioUnlockListenersInstalled = false;
            const opts = { capture: true };
            document.removeEventListener('pointerdown', handleGlobalAudioUnlock, opts);
            document.removeEventListener('touchstart', handleGlobalAudioUnlock, opts);
            document.removeEventListener('click', handleGlobalAudioUnlock, opts);
            document.removeEventListener('keydown', handleGlobalAudioUnlock, opts);
        }

        // Install early so first tap/click/key can unlock audio on iOS Safari.
        installGlobalAudioUnlockListeners();
        
        // Message history management
        let displayedMessages = []; // Array to store displayed messages (last 25)
        let philosopherModeActive = false; // Philosopher mode state
        let philosopherModeStarting = false; // Flag to prevent race condition on start
        let philosopherModeContemplating = false; // Whether a contemplation is in progress
        let philosopherModeInterval = null; // Interval for contemplation loop

        // Progress status updates (server-persisted, polled every 60s)
        let statusPollTimer = null;
        let statusRequestId = null;
        let statusConversationId = null;
        let statusSinceSeq = 0;
        const PROGRESS_VOICE_INITIAL_DELAY_MS = 0;
        const PROGRESS_VOICE_REPEAT_DELAY_MS = 5000;
        const PROGRESS_VOICE_STATE_COOLDOWN_MS = 5000;
        const PROGRESS_VOICE_MAX_ANNOUNCEMENTS = 4;
        let progressVoiceTimer = null;
        let progressVoiceRepeatTimer = null;
        let progressVoiceSessionId = 0;
        let progressVoiceStartedAt = 0;
        let progressVoiceCurrentState = '';
        let progressVoiceLastAnnouncementAt = 0;
        let progressVoiceAnnouncementCount = 0;
        let progressVoiceLastStateKey = '';

        function generateRequestId() {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                return window.crypto.randomUUID();
            }
            return `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
        }

        function clearProgressVoiceTimers() {
            if (progressVoiceTimer) {
                clearTimeout(progressVoiceTimer);
                progressVoiceTimer = null;
            }
            if (progressVoiceRepeatTimer) {
                clearTimeout(progressVoiceRepeatTimer);
                progressVoiceRepeatTimer = null;
            }
        }

        function humanizeToolName(toolName) {
            return String(toolName || 'tool')
                .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
                .replace(/[_-]+/g, ' ')
                .trim()
                .toLowerCase();
        }

        function getConversationalProgressPrompt(stateText, announcementCount = 0) {
            const rawState = String(stateText || '').trim();
            const lowerState = rawState.toLowerCase();
            const safeIndex = Math.max(0, announcementCount);

            if (lowerState.startsWith('executing tool:')) {
                const rawToolName = rawState.split(':').slice(1).join(':').trim();
                const normalizedToolName = rawToolName.replace(/[^a-z0-9]/gi, '').toLowerCase();
                const spokenToolName = humanizeToolName(rawToolName);
                const toolPromptMap = {
                    websearch: [
                        "I'm on it, looking that up now.",
                        "I'm on it, still checking the web for that.",
                        "I'm on it, finishing that search now."
                    ],
                    scrapewebsite: [
                        "I'm on it, checking that page now.",
                        "I'm on it, still reading through that page.",
                        "I'm on it, wrapping up that page check now."
                    ],
                    readfile: [
                        "I'm on it, reading through the file now.",
                        "I'm on it, still going through the file.",
                        "I'm on it, almost done reviewing the file."
                    ],
                    writefile: [
                        "I'm on it, putting that file together now.",
                        "I'm on it, still writing that up.",
                        "I'm on it, just finishing that file now."
                    ],
                    runcodexcli: [
                        "I'm on it, making that code change now.",
                        "I'm on it, still working through the code update.",
                        "I'm on it, just cleaning up the code change."
                    ],
                    fetchnews: [
                        "I'm on it, pulling the latest articles now.",
                        "I'm on it, still gathering the latest coverage.",
                        "I'm on it, finishing that news pass now."
                    ],
                    uploadtogoogledrive: [
                        "I'm on it, uploading that now.",
                        "I'm on it, still sending that file over.",
                        "I'm on it, just waiting for the upload to finish."
                    ],
                    managetodolist: [
                        "I'm on it, updating that task now.",
                        "I'm on it, still sorting out the task list.",
                        "I'm on it, just finishing the task update."
                    ]
                };
                const mappedPrompts = toolPromptMap[normalizedToolName];
                if (mappedPrompts && mappedPrompts.length > 0) {
                    return {
                        key: `tool:${normalizedToolName}`,
                        text: mappedPrompts[Math.min(safeIndex, mappedPrompts.length - 1)]
                    };
                }
                const genericToolPrompts = [
                    `I'm on it, using ${spokenToolName || 'a tool'} for that now.`,
                    `I'm on it, still working through ${spokenToolName || 'that tool'} right now.`,
                    `I'm on it, almost done with ${spokenToolName || 'that tool'}.`
                ];
                return {
                    key: `tool:${normalizedToolName || 'generic'}`,
                    text: genericToolPrompts[Math.min(safeIndex, genericToolPrompts.length - 1)]
                };
            }

            const promptGroups = [
                {
                    match: () => lowerState.includes('analyzing request'),
                    key: 'analyzing-request',
                    prompts: [
                        "Let me think.",
                        "Meow, let me think.",
                        "Let me think, almost there."
                    ]
                },
                {
                    match: () => lowerState.includes('planning tool chain'),
                    key: 'planning-tool-chain',
                    prompts: [
                        "I'm on it, lining up the steps now.",
                        "I'm on it, still organizing the best path through this.",
                        "I'm on it, nearly got the plan set."
                    ]
                },
                {
                    match: () => lowerState.includes('executing tool chain'),
                    key: 'executing-tool-chain',
                    prompts: [
                        "I'm on it, working through the steps now.",
                        "I'm on it, still moving through that tool chain.",
                        "I'm on it, wrapping up the last step now."
                    ]
                },
                {
                    match: () => lowerState.includes('contacting model'),
                    key: 'contacting-model',
                    prompts: [
                        "Let me think.",
                        "Meow, still thinking.",
                        "Let me think, I nearly have it."
                    ]
                },
                {
                    match: () => lowerState.includes('requesting final response'),
                    key: 'requesting-final-response',
                    prompts: [
                        "Let me think, putting the answer together.",
                        "Meow, still polishing the response.",
                        "Let me think, about to send it."
                    ]
                }
            ];

            const matchedGroup = promptGroups.find(group => group.match());
            if (matchedGroup) {
                return {
                    key: matchedGroup.key,
                    text: matchedGroup.prompts[Math.min(safeIndex, matchedGroup.prompts.length - 1)]
                };
            }

            const genericPrompts = [
                "Let me think.",
                "Meow, still thinking.",
                "Let me think, nearly done."
            ];
            return {
                key: lowerState || 'generic-progress',
                text: genericPrompts[Math.min(safeIndex, genericPrompts.length - 1)]
            };
        }

        function announceConversationalProgress(force = false) {
            if (!statusRequestId || !statusConversationId) return;
            if (!progressVoiceStartedAt || !progressVoiceCurrentState) return;
            if (isMuted) return;
            if (!force && (Date.now() - progressVoiceStartedAt) < PROGRESS_VOICE_INITIAL_DELAY_MS) return;
            if (progressVoiceAnnouncementCount >= PROGRESS_VOICE_MAX_ANNOUNCEMENTS) return;
            if (!force && progressVoiceLastAnnouncementAt && (Date.now() - progressVoiceLastAnnouncementAt) < PROGRESS_VOICE_STATE_COOLDOWN_MS) return;

            const prompt = getConversationalProgressPrompt(progressVoiceCurrentState, progressVoiceAnnouncementCount);
            if (!prompt || !prompt.text) return;

            progressVoiceLastAnnouncementAt = Date.now();
            progressVoiceAnnouncementCount += 1;
            progressVoiceLastStateKey = prompt.key || '';
            textToSpeech(prompt.text, { preserveThinkingPose: true });
        }

        function scheduleProgressVoiceAnnouncement(delayMs, sessionId = progressVoiceSessionId) {
            if (!statusRequestId || !statusConversationId) return;
            if (progressVoiceAnnouncementCount >= PROGRESS_VOICE_MAX_ANNOUNCEMENTS) return;
            if (progressVoiceTimer) {
                clearTimeout(progressVoiceTimer);
            }
            progressVoiceTimer = setTimeout(() => {
                if (sessionId !== progressVoiceSessionId) return;
                progressVoiceTimer = null;
                announceConversationalProgress(false);
            }, Math.max(0, delayMs));
        }

        function scheduleProgressVoiceRepeat(sessionId = progressVoiceSessionId) {
            if (!statusRequestId || !statusConversationId) return;
            if (progressVoiceAnnouncementCount >= PROGRESS_VOICE_MAX_ANNOUNCEMENTS) return;
            if (progressVoiceRepeatTimer) {
                clearTimeout(progressVoiceRepeatTimer);
            }
            progressVoiceRepeatTimer = setTimeout(() => {
                if (sessionId !== progressVoiceSessionId) return;
                progressVoiceRepeatTimer = null;
                announceConversationalProgress(false);
                scheduleProgressVoiceRepeat(sessionId);
            }, PROGRESS_VOICE_REPEAT_DELAY_MS);
        }

        async function postStatusStart(stateText) {
            if (!statusRequestId || !statusConversationId) return;
            const payload = {
                conversation_id: statusConversationId,
                request_id: statusRequestId,
                channel: 'web',
                state: (stateText || 'Working: processing your request...').trim()
            };
            try {
                await fetch(`${PROXY_BASE_URL}/v1/status/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } catch (_) {}
        }

        async function postStatusUpdate(stateText) {
            if (!statusRequestId || !statusConversationId) return;
            if (!stateText || typeof stateText !== 'string') return;
            const payload = {
                conversation_id: statusConversationId,
                request_id: statusRequestId,
                state: stateText.trim()
            };
            try {
                await fetch(`${PROXY_BASE_URL}/v1/status/update`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } catch (_) {}
        }

        async function postStatusFinish(finalState) {
            if (!statusRequestId || !statusConversationId) return;
            const payload = {
                conversation_id: statusConversationId,
                request_id: statusRequestId,
                final_state: finalState ? finalState.trim() : undefined
            };
            try {
                await fetch(`${PROXY_BASE_URL}/v1/status/finish`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } catch (_) {}
        }

        async function pollStatusEvents() {
            if (!statusRequestId || !statusConversationId) return;
            const params = new URLSearchParams({
                conversation_id: statusConversationId,
                request_id: statusRequestId,
                since_seq: String(statusSinceSeq)
            });
            try {
                const resp = await fetch(`${PROXY_BASE_URL}/v1/status/events?${params.toString()}`);
                if (!resp.ok) return;
                const data = await resp.json();
                const events = Array.isArray(data.events) ? data.events : [];
                events.forEach(ev => {
                    const state = (ev.state || '').trim();
                    if (state) {
                        addMessageToHistory('system', `[status] ${state}`);
                    }
                });
                if (typeof data.latest_seq === 'number') {
                    statusSinceSeq = Math.max(statusSinceSeq, data.latest_seq);
                }
            } catch (_) {}
        }

        const SMALL_TALK_PROMPT_PATTERNS = [
            /^(?:hi|hello|hey|hiya|yo|howdy)(?:\s+(?:cat|catbot|there))?[!.?]*$/i,
            /^(?:hi|hello|hey)[,!\s]*(?:how are you|how's it going|how are things|what's up)[?.!\s]*$/i,
            /^(?:how are you|how's it going|how are things|what's up)[?.!\s]*$/i,
            /^(?:thanks|thank you|cheers|cool|awesome|great|nice|sounds good|got it|ok|okay|alright)[!.?\s]*$/i,
            /^(?:bye|goodbye|see ya|see you|cya|ttyl|talk to you later|good night)[!.?\s]*$/i
        ];

        function isSmallTalkPrompt(promptText = '') {
            const normalized = String(promptText || '').replace(/\s+/g, ' ').trim();
            if (!normalized) return false;
            if (normalized.length > 120) return false;
            return SMALL_TALK_PROMPT_PATTERNS.some(pattern => pattern.test(normalized));
        }

        function shouldStartProgressUpdatesForPrompt(promptText = '') {
            return !isSmallTalkPrompt(promptText);
        }

        function startProgressUpdates(stateText) {
            stopProgressUpdates();
            statusRequestId = generateRequestId();
            statusConversationId = activeConversationId || 'default';
            statusSinceSeq = 0;
            progressVoiceSessionId += 1;
            progressVoiceStartedAt = Date.now();
            progressVoiceCurrentState = typeof stateText === 'string' ? stateText.trim() : '';
            progressVoiceLastAnnouncementAt = 0;
            progressVoiceAnnouncementCount = 0;
            progressVoiceLastStateKey = '';
            postStatusStart(stateText);
            pollStatusEvents();
            statusPollTimer = setInterval(pollStatusEvents, 60000);
            announceConversationalProgress(true);
            scheduleProgressVoiceAnnouncement(PROGRESS_VOICE_INITIAL_DELAY_MS, progressVoiceSessionId);
            scheduleProgressVoiceRepeat(progressVoiceSessionId);
        }

        function updateProgressState(stateText) {
            if (typeof stateText === 'string' && stateText.trim()) {
                const trimmedState = stateText.trim();
                const nextPrompt = getConversationalProgressPrompt(trimmedState, progressVoiceAnnouncementCount);
                const nextStateKey = nextPrompt?.key || trimmedState.toLowerCase();
                const previousStateKey = progressVoiceLastStateKey || getConversationalProgressPrompt(progressVoiceCurrentState, Math.max(0, progressVoiceAnnouncementCount - 1))?.key || '';
                progressVoiceCurrentState = trimmedState;
                postStatusUpdate(trimmedState);

                if (progressVoiceAnnouncementCount >= PROGRESS_VOICE_MAX_ANNOUNCEMENTS) {
                    return;
                }

                const elapsedMs = progressVoiceStartedAt ? (Date.now() - progressVoiceStartedAt) : 0;
                if (elapsedMs < PROGRESS_VOICE_INITIAL_DELAY_MS) {
                    scheduleProgressVoiceAnnouncement(PROGRESS_VOICE_INITIAL_DELAY_MS - elapsedMs, progressVoiceSessionId);
                    return;
                }

                if (nextStateKey && nextStateKey !== previousStateKey) {
                    const msSinceLastAnnouncement = progressVoiceLastAnnouncementAt ? (Date.now() - progressVoiceLastAnnouncementAt) : Number.POSITIVE_INFINITY;
                    const delayMs = msSinceLastAnnouncement >= PROGRESS_VOICE_STATE_COOLDOWN_MS
                        ? 1200
                        : (PROGRESS_VOICE_STATE_COOLDOWN_MS - msSinceLastAnnouncement) + 200;
                    scheduleProgressVoiceAnnouncement(delayMs, progressVoiceSessionId);
                }
            }
        }

        function stopProgressUpdates() {
            if (statusPollTimer) {
                clearInterval(statusPollTimer);
                statusPollTimer = null;
            }
            clearProgressVoiceTimers();
            postStatusFinish('Done: response delivered');
            statusRequestId = null;
            statusConversationId = null;
            statusSinceSeq = 0;
            progressVoiceCurrentState = '';
            progressVoiceStartedAt = 0;
            progressVoiceLastAnnouncementAt = 0;
            progressVoiceAnnouncementCount = 0;
            progressVoiceLastStateKey = '';
        }
        
        // Function to add a message to the history display
        function addMessageToHistory(role, content) {
            // Validate inputs - now supports 'user', 'assistant', 'philosopher', and 'system'
            if (!role || (role !== 'user' && role !== 'assistant' && role !== 'philosopher' && role !== 'system')) {
                console.error('addMessageToHistory called with invalid role:', role);
                return;
            }
            
            // Validate content is a string and not empty
            if (typeof content !== 'string') {
                console.error('addMessageToHistory called with invalid content type:', typeof content, content);
                return;
            }
            
            // Trim content but don't reject empty strings (assistant might send empty responses)
            content = content.trim();
            
            console.log('addMessageToHistory called - role:', role, 'content:', content); // Debug log
            
            // Get the configured names or use defaults
            const userName = userNameInput.value.trim() || 'User';
            const assistantName = assistantNameInput.value.trim() || 'EVA';
            const philosopherName = assistantNameInput.value.trim() || 'EVA'; // Use assistant name for philosopher
            const systemName = 'Status';
            
            // Create message object - ensure content is set correctly (not sender name)
            const message = {
                role: role, // 'user', 'assistant', or 'philosopher'
                content: content, // The actual message content, not the sender name
                sender: role === 'user'
                    ? userName
                    : (role === 'philosopher'
                        ? philosopherName + ' (Contemplating)'
                        : (role === 'system' ? systemName : assistantName)),
                timestamp: new Date()
            };
            
            console.log('Message object created:', { role: message.role, sender: message.sender, content: message.content }); // Debug log
            
            // Add to displayedMessages array and limit to 25 messages
            displayedMessages.push(message);
            if (displayedMessages.length > 25) {
                displayedMessages.shift(); // Remove oldest message
            }
            
            // Also add to chatHistory for API calls and persistence (skip system/status updates)
            if (role !== 'system') {
                // Create a simplified message object for chatHistory (without sender/timestamp for API compatibility)
                const chatMessage = {
                    role: role,
                    content: content
                };
                chatHistory.push(chatMessage);
            }
            
            // Update the display
            renderMessageHistory();
            
            // Auto-scroll to bottom
            messageHistory.scrollTop = messageHistory.scrollHeight;
            
            // Save to active conversation
            updateActiveConversationMessages();
        }
        
        // Function to render the entire message history
        function renderMessageHistory() {
            // Clear the container
            messageHistory.innerHTML = '';
            
            // Render each message
            displayedMessages.forEach((msg, index) => {
                // Debug log to verify message content before rendering
                console.log(`Rendering message ${index}:`, { 
                    role: msg.role, 
                    sender: msg.sender, 
                    content: msg.content,
                    contentLength: msg.content ? msg.content.length : 0
                });
                
                const messageDiv = document.createElement('div');
                // Support 'philosopher' role in addition to 'user' and 'assistant'
                messageDiv.className = `message ${msg.role}`;
                
                const senderDiv = document.createElement('div');
                senderDiv.className = 'message-sender';
                senderDiv.textContent = msg.sender;
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                // Ensure we're setting the actual content, not the sender name
                if (msg.content && typeof msg.content === 'string') {
                    contentDiv.textContent = msg.content;
                } else {
                    console.warn(`Message ${index} has invalid content:`, msg.content);
                    contentDiv.textContent = '[No content]';
                }
                
                messageDiv.appendChild(senderDiv);
                messageDiv.appendChild(contentDiv);
                messageHistory.appendChild(messageDiv);
            });
        }
        
        // Function to clear message history
        function clearMessageHistory() {
            displayedMessages = [];
            chatHistory = [];
            messageHistory.innerHTML = '';
            // Save to active conversation
            updateActiveConversationMessages();
        }

        // ============================================================================
        // PHILOSOPHER MODE FUNCTIONS
        // ============================================================================

        // Check if message contains philosopher mode trigger
        function detectPhilosopherModeTrigger(message) {
            const triggerPhrases = [
                'philosopher mode',
                'enable philosopher mode',
                'start philosopher mode',
                'enter philosopher mode',
                'philosopher',
            ];
            const messageLower = message.toLowerCase().trim();
            return triggerPhrases.some(phrase => messageLower.includes(phrase));
        }

        // Start philosopher mode
        async function startPhilosopherMode() {
            // Prevent race condition: check if already active or starting
            if (philosopherModeActive || philosopherModeStarting) {
                return; // Already active or starting
            }

            // Set starting flag immediately to prevent concurrent calls
            philosopherModeStarting = true;

            try {
                const response = await fetch(`${PROXY_BASE_URL}/v1/philosopher/start`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: activeConversationId || 'default',
                        user_id: activeConversationId || 'default',
                    }),
                });

                // Check if response is not ok (status >= 400)
                if (!response.ok) {
                    let errorMessage = 'Unknown error';
                    try {
                        const errorData = await response.json();
                        // FastAPI HTTPException returns {"detail": "..."}
                        errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                    } catch (e) {
                        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    }
                    console.error('Failed to start philosopher mode:', errorMessage);
                    status.textContent = `Failed to start philosopher mode: ${errorMessage}`;
                    return;
                }

                const data = await response.json();
                // Check if start was cancelled (philosopherModeStarting was cleared by stopPhilosopherMode)
                if (!philosopherModeStarting) {
                    // Start was cancelled, don't activate
                    return;
                }

                // Check data.success explicitly - require it to be true
                if (data.success === true) {
                    // Check starting flag wasn't cleared during API call or after response parsing
                    if (!philosopherModeStarting) {
                        // Start was cancelled, don't activate
                        return;
                    }
                    // Critical section: Check one more time right before activation
                    // This prevents race condition where stopPhilosopherMode is called between checks
                    if (!philosopherModeStarting) {
                        return; // Start was cancelled
                    }
                    // Set active state - but verify starting flag is still true after setting
                    philosopherModeActive = true;
                    // Final verification: if starting flag was cleared, revert the activation
                    if (!philosopherModeStarting) {
                        philosopherModeActive = false; // Revert activation if cancelled
                        return;
                    }
                    // Only proceed with UI updates if we successfully activated
                    if (philosopherModeBtn) {
                        philosopherModeBtn.innerHTML = '<i class="fas fa-brain"></i>';
                        philosopherModeBtn.style.backgroundColor = '#ff9800';
                    }
                    // Update Think button visual state when philosopher mode is active
                    if (thinkBtn) {
                        thinkBtn.style.backgroundColor = '#ff9800';
                        thinkBtn.style.opacity = '1';
                    }
                    addMessageToHistory('assistant', 'Philosopher Mode activated. I will now contemplate questions and share my thoughts.');
                    // Start contemplation loop
                    startPhilosopherContemplationLoop();
                } else {
                    console.error('Failed to start philosopher mode:', data.message);
                    status.textContent = `Failed to start philosopher mode: ${data.message || 'Unknown error'}`;
                }
            } catch (error) {
                console.error('Error starting philosopher mode:', error);
                status.textContent = `Error starting philosopher mode: ${error.message}`;
            } finally {
                // Always clear the starting flag, whether success or failure
                philosopherModeStarting = false;
            }
        }

        // Stop philosopher mode
        async function stopPhilosopherMode(skipMessage = false) {
            // If not active and not starting, there's nothing to stop
            if (!philosopherModeActive && !philosopherModeStarting) {
                return; // Already stopped and not starting
            }

            try {
                // Clear contemplation interval and reset state immediately
                philosopherModeActive = false; // Set to false first to stop loop
                if (philosopherModeInterval) {
                    clearInterval(philosopherModeInterval);
                    philosopherModeInterval = null;
                }

                // If starting, cancel the start operation by clearing the starting flag
                // This will prevent startPhilosopherMode from activating when it completes
                const wasStarting = philosopherModeStarting;
                if (philosopherModeStarting) {
                    philosopherModeStarting = false;
                }

                // Always call the backend API to stop, even if we think it was just starting
                // This handles the race condition where backend might already be active
                // The backend will handle the case where it's not active gracefully
                const response = await fetch(`${PROXY_BASE_URL}/v1/philosopher/stop`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: activeConversationId || 'default',
                        user_id: activeConversationId || 'default',
                    }),
                });

                const data = await response.json();
                philosopherModeActive = false;
                philosopherModeContemplating = false;
                if (philosopherModeBtn) {
                    philosopherModeBtn.innerHTML = '<i class="fas fa-brain"></i>';
                    philosopherModeBtn.style.backgroundColor = '';
                }
                // Reset Think button visual state when philosopher mode is deactivated
                if (thinkBtn) {
                    thinkBtn.style.backgroundColor = '';
                    thinkBtn.style.opacity = '';
                }
                
                // Show appropriate message based on whether it was starting or already active
                // Skip message display if skipMessage is true (used during interruption to maintain message order)
                if (!skipMessage) {
                    if (wasStarting) {
                        addMessageToHistory('assistant', 'Philosopher Mode activation cancelled.');
                    } else {
                        addMessageToHistory('assistant', 'Philosopher Mode deactivated.');
                    }
                }
                if (!data.choices || data.choices.length === 0) {
                    console.warn('LLM returned no choices');
                    const lastToolMsg = messages.slice().reverse().find(m => m.role === 'tool')?.content;
                    if (lastToolMsg) {
                        let fallbackText = '';
                        try {
                            const parsed = typeof lastToolMsg === 'string' ? JSON.parse(lastToolMsg) : lastToolMsg;
                            fallbackText = parsed?.message || '';
                        } catch (_) {
                            fallbackText = typeof lastToolMsg === 'string' ? lastToolMsg : '';
                        }
                        if (fallbackText) {
                            responseOutput.value = fallbackText;
                            addMessageToHistory('assistant', fallbackText); // Add to message history (also updates chatHistory)
                            extractMemoriesFromConversation().catch(err => {
                                console.warn('Memory extraction failed:', err);
                            });
                            if (uploadedAttachments.length) {
                                clearPendingAttachments();
                            }
                            textToSpeech(fallbackText);
                        }
                    }
                }
            } catch (error) {
                console.error('Error stopping philosopher mode:', error);
                // Still deactivate locally even if API call fails
                philosopherModeActive = false;
                philosopherModeContemplating = false;
                philosopherModeStarting = false; // Also clear starting flag on error
                if (philosopherModeBtn) {
                    philosopherModeBtn.innerHTML = '<i class="fas fa-brain"></i>';
                    philosopherModeBtn.style.backgroundColor = '';
                }
                // Reset Think button visual state on error
                if (thinkBtn) {
                    thinkBtn.style.backgroundColor = '';
                    thinkBtn.style.opacity = '';
                }
            }
        }

        // Execute a single contemplation cycle
        async function executeContemplation() {
            if (!philosopherModeActive || philosopherModeContemplating) {
                return; // Not active or already contemplating
            }

            philosopherModeContemplating = true;

            try {
                const response = await fetch(`${PROXY_BASE_URL}/v1/philosopher/contemplate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: activeConversationId || 'default',
                        user_id: activeConversationId || 'default',
                    }),
                });

                // Check if response is not ok (status >= 400)
                if (!response.ok) {
                    let errorMessage = 'Unknown error';
                    try {
                        const errorData = await response.json();
                        // FastAPI HTTPException returns {"detail": "..."}
                        errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                    } catch (e) {
                        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    }
                    console.error('Contemplation failed:', errorMessage);
                    // Display error to user in chat
                    if (philosopherModeActive) {
                        addMessageToHistory('assistant', `⚠️ Contemplation error: ${errorMessage}`);
                    }
                    return;
                }

                const data = await response.json();
                // Check if philosopher mode is still active after async fetch completes
                // This prevents displaying contemplation results if mode was stopped during the fetch
                if (!philosopherModeActive) {
                    // Mode was stopped, don't display results
                    return;
                }
                
                if (data.success && data.data) {
                    // Double-check mode is still active before displaying
                    if (!philosopherModeActive) {
                        return; // Mode was stopped, don't display results
                    }
                    // Display question
                    if (data.data.question) {
                        addMessageToHistory('philosopher', `🤔 Question: ${data.data.question}`);
                    }
                    // Check again before displaying conclusion
                    if (!philosopherModeActive) {
                        return; // Mode was stopped, don't display conclusion
                    }
                    // Display conclusion
                    if (data.data.conclusion) {
                        addMessageToHistory('philosopher', `💭 Conclusion: ${data.data.conclusion}`);
                    }
                } else {
                    const errorMsg = data.message || 'Unknown error';
                    console.error('Contemplation failed:', errorMsg);
                    // Display error to user in chat
                    if (philosopherModeActive) {
                        addMessageToHistory('assistant', `⚠️ Contemplation failed: ${errorMsg}`);
                    }
                }
            } catch (error) {
                console.error('Error during contemplation:', error);
                // Display error to user in chat
                if (philosopherModeActive) {
                    addMessageToHistory('assistant', `⚠️ Contemplation error: ${error.message || 'Network or connection error'}`);
                }
            } finally {
                philosopherModeContemplating = false;
            }
        }

        // Start contemplation loop
        function startPhilosopherContemplationLoop() {
            // Clear any existing interval
            if (philosopherModeInterval) {
                clearInterval(philosopherModeInterval);
            }

            // Execute first contemplation immediately
            executeContemplation();

            // Then set up interval for subsequent contemplations (every 30 seconds)
            philosopherModeInterval = setInterval(() => {
                if (philosopherModeActive && !philosopherModeContemplating) {
                    executeContemplation();
                }
            }, 30000); // 30 seconds between contemplations
        }

        // Toggle philosopher mode
        async function togglePhilosopherMode() {
            if (philosopherModeActive) {
                await stopPhilosopherMode();
            } else {
                await startPhilosopherMode();
            }
        }

        // Add event listener for philosopher mode button
        if (philosopherModeBtn) {
            philosopherModeBtn.addEventListener('click', togglePhilosopherMode);
        }

        // Persist voice selection when the user changes the dropdown
        if (voiceDropdown) {
            voiceDropdown.addEventListener('change', function() {
                const selectedVoiceIndex = parseInt(voiceDropdown.value);
                if (!isNaN(selectedVoiceIndex) && voices[selectedVoiceIndex]) {
                    try {
                        localStorage.setItem(SELECTED_VOICE_STORAGE_KEY, voices[selectedVoiceIndex].voiceURI);
                        saveToolSettings(); // Also save in unified settings
                    } catch (persistError) {
                        console.warn('Could not persist selected voice in localStorage:', persistError);
                    }
                }
            });
        }
        let audioContext;
        let mediaStreamSource;
        let recorderNode;
        let audioData = [];
        let live2dModel;
        let live2dApp = null;
        let live2dTickerRegistered = false; // Ensures we only register the Live2D ticker once
        let live2dOffsets = {}; // Persisted map of modelPath -> vertical offset in px
        let live2dScales = {}; // Persisted map of modelPath -> size multiplier
        let live2dResizeHandler = null;
        let live2dLoadGeneration = 0;
        let live2dActiveModelPath = '';
        // Live2D model configuration (selector-driven)
        let modelPath = '';

        // VRM model variables
        let vrmModel;
        let vrmScene;
        let vrmCamera;
        let vrmRenderer;
        let vrmResizeHandler = null;
        let vrmMixer;
        let vrmClock;
        let vrmLipSyncMorphTarget;
        let vrmLoadGeneration = 0;
        let vrmActiveModelPath = '';
        let vrmAnimationFrameId = 0;
        let vrmBlinkTimeout; // Timer id used to schedule periodic blinking
        let vrmBlinkCloseTimeout = null; // Timer id used to reopen eyes after a blink
        let vrmLovePoseActive = false; // Whether the love pose is active
        let lovePoseTimeoutId = null; // Auto-release timer for love pose
        let isSpeaking = false; // Global speaking state for lip sync/expressions
        let lovePoseWeight = 0; // Current blend weight [0..1] toward love pose
        let targetLovePoseWeight = 0; // Target blend weight we ease toward
        let vrmThinkPoseActive = false; // Whether the thinking pose is active
        let thinkPoseTimeoutId = null; // Auto-release timer for thinking pose
        let thinkPoseWeight = 0; // Current blend for thinking pose
        let vrmVersion = '1.0'; // Selected VRM version ('1.0' or '0.0')
        let targetThinkPoseWeight = 0; // Target blend for thinking pose
        let vrmCryPoseActive = false; // Whether the cry pose is active
        let cryPoseTimeoutId = null; // Auto-release timer for cry pose
        let cryPoseWeight = 0; // Current blend for cry pose
        let targetCryPoseWeight = 0; // Target blend for cry pose
        let vrmAngryPoseActive = false; // Whether the angry pose is active
        let angryPoseTimeoutId = null; // Auto-release timer for angry pose
        let angryPoseWeight = 0; // Current blend for angry pose
        let targetAngryPoseWeight = 0; // Target blend for angry pose
        let vrmPositions = {}; // Persisted map of modelPath -> {scale, positionX, positionY, rotation}
        let currentVRMModelPath = '';
        // Removed fallback VRM; enforce valid user-provided .vrm only


        // Add these variables at the top of your script section
        let clipboardData = null;
        let clipboardType = null;
        let clipboardMonitorInterval = null; // Interval ID for clipboard monitoring
        let webcamStream = null;
        let isProcessing = false;
        let webcamInterval = null;
        // Global lip sync controller state
        let ttsLipSyncIntervalId = null; // Interval used by SpeechSynthesis fallback
        let ttsRafId = 0; // requestAnimationFrame id used by audio analyser loop
        let ttsCleanupFns = []; // Set of cleanup callbacks for active audio graph/listeners
        let ttsAnalyserNode = null; // Shared analyser used for PCM16 streaming lip sync
        let ttsAnalyserGainNode = null; // Gain node feeding analyser output to speakers
        let ttsAnalyserDataArray = null; // Reusable byte buffer for analyser samples
        let ttsAnalyserLoopActive = false; // Tracks whether analyser-driven lip sync loop is running
        let ttsStreamActive = false; // Flag indicating an active Chatterbox PCM stream
        let ttsPcmActiveSources = 0; // Count of PCM buffer sources currently playing
        let ttsAnalyserStopTimer = null; // Timer used to delay cleanup after audio ends
		let ttsAbortController = null; // AbortController for active Chatterbox TTS fetch/stream
		let ttsGeneration = 0; // Monotonic token to discard stale TTS callbacks
		// Microsoft TTS lip sync variables (smooth amplitude-based approach, same as Chatterbox)
		let microsoftTtsRafId = 0; // requestAnimationFrame id for Microsoft TTS lip sync loop
		let microsoftTtsTargetAmplitude = 0; // Target amplitude for smooth lip sync (0-1)
		let microsoftTtsSmoothedAmplitude = 0; // Current smoothed amplitude value
		let microsoftTtsLastBoundaryTs = 0; // Timestamp of last boundary event
		let microsoftTtsIsActive = false; // Flag to track if Microsoft TTS lip sync is active
        let browserSpeechGeneration = 0; // Monotonic token used to ignore stale speechSynthesis callbacks after interruption

        // Global VRMA actions
        let vrmLoveVrmaAction = null; // Prepared AnimationAction for love VRMA
        let vrmThinkVrmaAction = null; // Prepared AnimationAction for thinking VRMA
        let vrmCryVrmaAction = null; // Prepared AnimationAction for cry VRMA
        let vrmAngryVrmaAction = null; // Prepared AnimationAction for angry VRMA
        let vrmIdleVrmaAction = null; // Prepared AnimationAction for idle VRMA
        let vrmProcessingThinkLoopActive = false; // Whether the request-processing thinking loop is active
        let vrmAwaitingTtsStart = false; // Whether we are holding the processing loop until speech playback begins
        let vrmAwaitingTtsStartTimerId = null; // Safety timer so processing loop cannot get stuck forever
        let vrmTtsStartHandled = false; // One-shot guard for the first playback event of a TTS session
        let vrmIdleReplayTimerId = null; // Timer for delayed idle replays
        let vrmIdleHasPlayedOnce = false; // Tracks whether the initial idle pass has already happened
        let smoothedVrmDelta = 1 / 60; // Smoothed physics delta to keep browser VRM motion close to Electron
        let vrmPoseSnapshotBones = {}; // Humanoid bones used to preserve visible pose across VRMA transitions
        let vrmBaseStandingPoseSnapshot = null; // Initial relaxed pose snapshot for the active model
        let vrmLastPoseSnapshot = null; // Last visible animated/manual pose before an action releases bindings
        let vrmLastFrameHadRunningAction = false; // Whether the previous frame had any VRMA action owning the rig
        let vrmRestorePoseOnNextManualIdle = false; // Guard to bridge stopped actions back into manual idle
        let vrmPoseBlend = null; // Active bridge from current visible pose into a newly-started VRMA action

        // Pose configuration (tweak these numbers to adjust poses)
        const POSE_CONFIG = {
            blendSmoothing: 0.12, // Easing toward target pose weights per frame
            love: {
                durationMs: 6000, // How long to hold the love pose
                expressionsOnly: true, // Do not apply manual limb rotations; VRMA drives motion
                vrmaPath: './model_avatar/Eva/Kawaii Kaiwai.vrma', // VRMA animation path for love pose
                useVrma: true, // Prefer VRMA over JSON pose
                upperArmRollFactor: 0.15, // Reduce side roll by this fraction of armLowering
                upperArmPitchForward: 0.9, // How much to pitch both upper arms forward (negative X)
                upperArmYawIn: 0.9, // How much to yaw both upper arms inward (Y)
                forearmBend: 1.4, // How much to bend both elbows (forearm Z)
                handYawIn: 1.1, // How much to yaw both hands inward (Y)
                smileGain: 0.85, // Smile amplitude scale during pose
                smileBias: 0.2, // Extra bias so smile starts visible
                loveEyesGain: 0.75, // Love eyes (relaxed) amplitude scale during pose
                loveEyesBias: 0.15, // Extra bias so love eyes start visible
                affectFace: false, // If true, also set smile/eye shapes (disabled per user request)
                poseJsonPath: 'model_avatar/Eva/Eva0.vrm.json', // Optional pose JSON path with target quaternions (ignored when useVrma is true)
                poseName: 'Heart', // Pose name in the JSON file
                convertUnityQuat: false // Do not flip axes; VRM Poser quaternions align with three-vrm normalized bones
            },
            think: {
                durationMs: 6000, // How long to hold the thinking pose
                expressionsOnly: true, // If true, only drive facial expressions; skip limb rotations
                vrmaPath: './model_avatar/Eva/Thinking.vrma', // VRMA animation path for thinking pose
                useVrma: true, // Prefer VRMA over manual pose
                upperArmPitchForward: 0.6, // Additional forward pitch for right upper arm
                upperArmYawIn: 0.65, // Additional inward yaw for right upper arm
                upperArmRollZ: 0.2, // Additional roll for right upper arm
                forearmBendExtra: 1.6, // Extra elbow bend for right forearm
                handYawInExtra: 0.8, // Extra inward yaw on right hand
                oMouthGain: 0.75, // O mouth amplitude scale
                oMouthBias: 0.2, // O mouth bias
                browRaiseGain: 0.6 // Brow raise amplitude scale
            },
            cry: {
                durationMs: 6000, // How long to hold the cry pose
                expressionsOnly: true, // Only drive facial expressions; skip limb rotations
                vrmaPath: './model_avatar/Eva/007_gekirei.vrma', // VRMA animation path for cry pose
                useVrma: true, // Prefer VRMA over manual pose
                sadMouthGain: 0.75, // Sad mouth amplitude scale
                sadMouthBias: 0.2, // Sad mouth bias
                tearGain: 0.8 // Tear/crying expression amplitude
            },
            angry: {
                durationMs: 6000, // How long to hold the angry pose
                expressionsOnly: true, // Only drive facial expressions; skip limb rotations
                vrmaPath: './model_avatar/Eva/VRMA_04.vrma', // VRMA animation path for angry pose
                useVrma: true, // Prefer VRMA over manual pose
                angryExpressionGain: 1.0, // Angry expression amplitude scale
                browDownGain: 0.8 // Brow down amplitude for angry look
            }
        };

        const VRM_ACTION_FADE_IN_SECONDS = 0.55;
        const VRM_ACTION_FADE_OUT_SECONDS = 0.85;
        const VRM_IDLE_ACTION_FADE_IN_SECONDS = 0.95;
        const VRM_IDLE_ACTION_FADE_OUT_SECONDS = 0.8;
        const VRM_MAX_ANIMATION_DELTA_SECONDS = 1 / 24;
        const VRM_MAX_PHYSICS_DELTA_SECONDS = 1 / 45;
        const VRM_DELTA_SMOOTHING = 0.18;
        const VRM_PHYSICS_RESET_DELTA_SECONDS = 0.22;
        const VRM_BROWSER_TARGET_FPS = 60;
        const VRM_BROWSER_PIXEL_RATIO_CAP = 1.25;
        const VRM_POSE_TO_ACTION_BLEND_MS = 420;
        const VRM_IDLE_POSE_TO_ACTION_BLEND_MS = 560;
        const VRM_POSE_SNAPSHOT_BONE_NAMES = [
            'hips',
            'spine',
            'chest',
            'upperChest',
            'neck',
            'head',
            'leftShoulder',
            'rightShoulder',
            'leftUpperArm',
            'rightUpperArm',
            'leftLowerArm',
            'rightLowerArm',
            'leftHand',
            'rightHand',
            'leftUpperLeg',
            'rightUpperLeg',
            'leftLowerLeg',
            'rightLowerLeg',
            'leftFoot',
            'rightFoot',
            'leftToes',
            'rightToes'
        ];

        function isCurrentVrmLoad(loadGeneration, modelPathSnapshot, modelInstance = vrmModel) {
            return Boolean(
                loadGeneration === vrmLoadGeneration &&
                modelPathSnapshot === currentVRMModelPath &&
                modelInstance &&
                modelInstance === vrmModel &&
                document.getElementById('vrm-mode')?.checked
            );
        }

        function clearVrmBlinkTimers() {
            if (vrmBlinkTimeout) { try { clearTimeout(vrmBlinkTimeout); } catch (_) {} vrmBlinkTimeout = null; }
            if (vrmBlinkCloseTimeout) { try { clearTimeout(vrmBlinkCloseTimeout); } catch (_) {} vrmBlinkCloseTimeout = null; }
        }

        function flushVrmExpressions(targetVrm = vrmModel) {
            try { targetVrm?.expressionManager?.update?.(); } catch (_) {}
            try { targetVrm?.blendShapeProxy?.update?.(); } catch (_) {}
        }

        function resetVrmPhysicsState(targetVrm = vrmModel) {
            try { targetVrm?.springBoneManager?.reset?.(); } catch (_) {}
        }

        function getStableVrmFrameDeltas(rawDelta) {
            const finiteDelta = Number.isFinite(rawDelta) && rawDelta > 0 ? rawDelta : 1 / 60;
            if (finiteDelta > VRM_PHYSICS_RESET_DELTA_SECONDS) {
                resetVrmPhysicsState();
                smoothedVrmDelta = 1 / 60;
            }
            const animationDelta = Math.min(finiteDelta, VRM_MAX_ANIMATION_DELTA_SECONDS);
            const physicsMax = VRM_BROWSER_TARGET_FPS <= 30 ? 1 / 30 : VRM_MAX_PHYSICS_DELTA_SECONDS;
            const targetPhysicsDelta = Math.min(finiteDelta, physicsMax);
            smoothedVrmDelta += (targetPhysicsDelta - smoothedVrmDelta) * VRM_DELTA_SMOOTHING;
            return {
                animationDelta,
                physicsDelta: Math.min(smoothedVrmDelta, physicsMax)
            };
        }

        function configureVrmRenderer(rendererInstance) {
            if (!rendererInstance) return;
            try {
                rendererInstance.setPixelRatio(Math.min(VRM_BROWSER_PIXEL_RATIO_CAP, window.devicePixelRatio || 1));
            } catch (_) {}
            try {
                if ('outputColorSpace' in rendererInstance && window.THREE?.SRGBColorSpace) {
                    rendererInstance.outputColorSpace = window.THREE.SRGBColorSpace;
                }
            } catch (_) {}
            try {
                if ('toneMapping' in rendererInstance && window.THREE?.NoToneMapping !== undefined) {
                    rendererInstance.toneMapping = window.THREE.NoToneMapping;
                    rendererInstance.toneMappingExposure = 1;
                }
            } catch (_) {}
        }

        function getVrmPoseSnapshotBone(key) {
            return vrmPoseSnapshotBones?.[key] || null;
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

        function createVrmPoseSnapshot() {
            const snapshot = {};
            for (const boneName of VRM_POSE_SNAPSHOT_BONE_NAMES) {
                const pose = createVrmBonePoseSnapshot(getVrmPoseSnapshotBone(boneName));
                if (pose) {
                    snapshot[boneName] = pose;
                }
            }
            return Object.keys(snapshot).length ? snapshot : null;
        }

        function restoreVrmPoseSnapshot(snapshot) {
            if (!snapshot) {
                return;
            }
            for (const [boneName, pose] of Object.entries(snapshot)) {
                const bone = getVrmPoseSnapshotBone(boneName);
                if (!bone) {
                    continue;
                }
                if (pose.rotation) {
                    bone.rotation.set(pose.rotation.x, pose.rotation.y, pose.rotation.z);
                }
                if (pose.position) {
                    bone.position.set(pose.position.x, pose.position.y, pose.position.z);
                }
                try { bone.updateMatrixWorld?.(true); } catch (_) {}
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

        function applyBlendedVrmPoseSnapshot(fromSnapshot, toSnapshot, weight) {
            if (!fromSnapshot || !toSnapshot) {
                return;
            }
            const amount = Math.max(0, Math.min(1, Number(weight) || 0));
            const snapshotKeys = new Set([
                ...Object.keys(fromSnapshot),
                ...Object.keys(toSnapshot)
            ]);
            for (const boneName of snapshotKeys) {
                const bone = getVrmPoseSnapshotBone(boneName);
                const fromPose = fromSnapshot[boneName];
                const toPose = toSnapshot[boneName];
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
                try { bone.updateMatrixWorld?.(true); } catch (_) {}
            }
        }

        function getVrmActionList() {
            return [
                vrmLoveVrmaAction,
                vrmThinkVrmaAction,
                vrmCryVrmaAction,
                vrmAngryVrmaAction,
                vrmIdleVrmaAction
            ].filter(Boolean);
        }

        function isVrmActionRunning(action) {
            return Boolean(action && typeof action.isRunning === 'function' && action.isRunning());
        }

        function hasRunningVrmAction() {
            return getVrmActionList().some(isVrmActionRunning);
        }

        function markVrmPoseForManualRestore() {
            const snapshot = createVrmPoseSnapshot();
            if (snapshot) {
                vrmLastPoseSnapshot = snapshot;
                vrmRestorePoseOnNextManualIdle = true;
            }
        }

        function startVrmPoseBlendToAction(action, fromSnapshot, durationMs) {
            if (!action || !fromSnapshot) {
                vrmPoseBlend = null;
                return;
            }
            vrmPoseBlend = {
                action,
                fromSnapshot,
                startTime: performance.now(),
                durationMs: Math.max(80, Number(durationMs) || VRM_POSE_TO_ACTION_BLEND_MS)
            };
            vrmRestorePoseOnNextManualIdle = false;
            restoreVrmPoseSnapshot(fromSnapshot);
            resetVrmPhysicsState();
            smoothedVrmDelta = 1 / 60;
        }

        function updateVrmPoseBlend(now = performance.now()) {
            if (!vrmPoseBlend) {
                return false;
            }
            const { action, fromSnapshot, startTime, durationMs } = vrmPoseBlend;
            if (!fromSnapshot || !isVrmActionRunning(action)) {
                vrmPoseBlend = null;
                return false;
            }

            const targetSnapshot = createVrmPoseSnapshot();
            if (!targetSnapshot) {
                vrmPoseBlend = null;
                return false;
            }

            const progress = (now - startTime) / durationMs;
            const weight = getVrmPoseBlendWeight(progress);
            applyBlendedVrmPoseSnapshot(fromSnapshot, targetSnapshot, weight);

            if (progress >= 1) {
                vrmPoseBlend = null;
                resetVrmPhysicsState();
                smoothedVrmDelta = 1 / 60;
            }
            return true;
        }

        function disposeThreeSceneResources(root) {
            if (!root?.traverse) return;
            root.traverse((child) => {
                if (child.geometry) {
                    try { child.geometry.dispose(); } catch (_) {}
                }
                if (child.material) {
                    const materials = Array.isArray(child.material) ? child.material : [child.material];
                    materials.forEach((material) => {
                        try { material.dispose(); } catch (_) {}
                    });
                }
            });
        }

        function disposeStaleVrmLoadResources(scene, renderer, mixer, vrmInstance, gltfScene = null) {
            try {
                if (mixer && vrmInstance?.scene) {
                    mixer.stopAllAction();
                    mixer.uncacheRoot(vrmInstance.scene);
                }
            } catch (_) {}
            disposeThreeSceneResources(scene);
            if (gltfScene && gltfScene !== scene) {
                disposeThreeSceneResources(gltfScene);
            }
            try { renderer?.dispose?.(); } catch (_) {}
        }

        function clearVrmAwaitingTtsStart() {
            vrmAwaitingTtsStart = false;
            if (vrmAwaitingTtsStartTimerId) {
                try { clearTimeout(vrmAwaitingTtsStartTimerId); } catch (_) {}
                vrmAwaitingTtsStartTimerId = null;
            }
        }

        function resetVrmPoseState() {
            if (lovePoseTimeoutId) { try { clearTimeout(lovePoseTimeoutId); } catch (_) {} lovePoseTimeoutId = null; }
            if (thinkPoseTimeoutId) { try { clearTimeout(thinkPoseTimeoutId); } catch (_) {} thinkPoseTimeoutId = null; }
            if (cryPoseTimeoutId) { try { clearTimeout(cryPoseTimeoutId); } catch (_) {} cryPoseTimeoutId = null; }
            if (angryPoseTimeoutId) { try { clearTimeout(angryPoseTimeoutId); } catch (_) {} angryPoseTimeoutId = null; }

            vrmLovePoseActive = false;
            vrmThinkPoseActive = false;
            vrmCryPoseActive = false;
            vrmAngryPoseActive = false;
            lovePoseWeight = 0;
            thinkPoseWeight = 0;
            cryPoseWeight = 0;
            angryPoseWeight = 0;
            targetLovePoseWeight = 0;
            targetThinkPoseWeight = 0;
            targetCryPoseWeight = 0;
            targetAngryPoseWeight = 0;

            try {
                if (vrmModel?.expressionManager) {
                    ['smile','happy','joy','fun','relaxed','heart','love','oh','browUp','browUpLeft','browUpRight','surprised','sad','cry','sorrow','angry']
                        .forEach(k => { try { vrmModel.expressionManager.setValue(k, 0.0); } catch (_) {} });
                }
                if (vrmModel?.blendShapeProxy) {
                    ['Smile','Joy','Fun','MouthSmile','Relaxed','Heart','Love','O','BrowUp','BrowUp_L','BrowUp_R','Surprised','Sad','Cry','Sorrow','Angry']
                        .forEach(k => { try { vrmModel.blendShapeProxy.setValue(k, 0.0); } catch (_) {} });
                }
                flushVrmExpressions(vrmModel);
            } catch (_) {}
        }

        function clearVrmActionStopTimer(action) {
            if (!action || !action.__vrmStopTimerId) return;
            try { clearTimeout(action.__vrmStopTimerId); } catch (_) {}
            action.__vrmStopTimerId = null;
        }

        function scheduleVrmActionStop(action, fadeSeconds = VRM_ACTION_FADE_OUT_SECONDS) {
            if (!action) return;
            clearVrmActionStopTimer(action);
            action.__vrmStopTimerId = setTimeout(() => {
                action.__vrmStopTimerId = null;
                try {
                    markVrmPoseForManualRestore();
                    action.stop();
                } catch (_) {}
            }, Math.max(0, Math.round(fadeSeconds * 1000) + 80));
        }

        function stopVrmAction(action, fadeSeconds = VRM_ACTION_FADE_OUT_SECONDS) {
            if (!action) return;
            try {
                if (vrmPoseBlend?.action === action) {
                    vrmPoseBlend = null;
                }
                const effectiveWeight = typeof action.getEffectiveWeight === 'function' ? action.getEffectiveWeight() : 0;
                const isActive = (typeof action.isRunning === 'function' && action.isRunning()) || effectiveWeight > 0.001;
                if (!isActive || fadeSeconds <= 0) {
                    clearVrmActionStopTimer(action);
                    markVrmPoseForManualRestore();
                    action.stop();
                    return;
                }

                action.enabled = true;
                action.clampWhenFinished = true;
                action.fadeOut(fadeSeconds);
                scheduleVrmActionStop(action, fadeSeconds);
            } catch (_) {}
        }

        function transitionToVrmAction(nextAction, {
            loop = window.THREE.LoopOnce,
            repetitions = 1,
            fadeInSeconds = VRM_ACTION_FADE_IN_SECONDS,
            fadeOutSeconds = VRM_ACTION_FADE_OUT_SECONDS,
            forceRestart = true
        } = {}) {
            if (!nextAction) {
                return false;
            }

            const actionsToFade = [
                vrmLoveVrmaAction,
                vrmThinkVrmaAction,
                vrmCryVrmaAction,
                vrmAngryVrmaAction,
                vrmIdleVrmaAction
            ];
            const canFadeFromRunningAction = fadeInSeconds > 0 && actionsToFade.some(action => (
                action &&
                action !== nextAction &&
                isVrmActionRunning(action)
            ));
            const poseBlendFromSnapshot = canFadeFromRunningAction
                ? null
                : createVrmPoseSnapshot() || vrmLastPoseSnapshot || vrmBaseStandingPoseSnapshot;
            const poseBlendDurationMs = nextAction === vrmIdleVrmaAction
                ? VRM_IDLE_POSE_TO_ACTION_BLEND_MS
                : VRM_POSE_TO_ACTION_BLEND_MS;

            actionsToFade.forEach(action => {
                if (!action || action === nextAction) return;
                const fadeSeconds = action === vrmIdleVrmaAction ? VRM_IDLE_ACTION_FADE_OUT_SECONDS : fadeOutSeconds;
                stopVrmAction(action, fadeSeconds);
            });

            try {
                clearVrmActionStopTimer(nextAction);
                if (forceRestart || !nextAction.isRunning()) {
                    nextAction.reset();
                }
                nextAction.clampWhenFinished = loop !== window.THREE.LoopRepeat;
                nextAction.loop = loop;
                if (loop !== window.THREE.LoopRepeat) {
                    nextAction.repetitions = repetitions;
                }
                nextAction.setEffectiveWeight(1.0);
                nextAction.setEffectiveTimeScale(1.0);
                nextAction.enabled = true;
                if (canFadeFromRunningAction) {
                    vrmPoseBlend = null;
                    nextAction.fadeIn(fadeInSeconds);
                }
                nextAction.play();
                if (!canFadeFromRunningAction && poseBlendFromSnapshot) {
                    try { vrmMixer?.update?.(0); } catch (_) {}
                    startVrmPoseBlendToAction(nextAction, poseBlendFromSnapshot, poseBlendDurationMs);
                }
                return true;
            } catch (e) {
                console.warn('Failed to transition VRM action smoothly:', e);
                return false;
            }
        }

        function clearVrmIdleReplayTimer() {
            if (vrmIdleReplayTimerId) {
                try { clearTimeout(vrmIdleReplayTimerId); } catch (_) {}
                vrmIdleReplayTimerId = null;
            }
        }

        function scheduleNextVrmIdlePlayback() {
            const vrmModeToggle = document.getElementById('vrm-mode');
            if (!vrmIdleVrmaAction || !vrmModeToggle?.checked || vrmIdleReplayTimerId) {
                return;
            }
            if (vrmProcessingThinkLoopActive || vrmAwaitingTtsStart) {
                return;
            }

            const hasActiveAnimation =
                (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) ||
                (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) ||
                (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) ||
                (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning());

            if (hasActiveAnimation) {
                return;
            }

            const delayMs = 10000 + Math.floor(Math.random() * 10001);
            vrmIdleReplayTimerId = setTimeout(() => {
                vrmIdleReplayTimerId = null;
                playVrmIdleAction();
            }, delayMs);
        }

        function playVrmIdleAction({ force = false } = {}) {
            const vrmModeToggle = document.getElementById('vrm-mode');
            if (!vrmIdleVrmaAction || !vrmModeToggle?.checked) {
                return;
            }
            if (!force && (vrmProcessingThinkLoopActive || vrmAwaitingTtsStart)) {
                return;
            }

            const hasActiveAnimation =
                (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) ||
                (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) ||
                (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) ||
                (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning());

            if (!force && hasActiveAnimation) {
                return;
            }

            try {
                clearVrmIdleReplayTimer();
                if (!force && vrmIdleVrmaAction.isRunning()) {
                    return;
                }
                const didStart = transitionToVrmAction(vrmIdleVrmaAction, {
                    loop: window.THREE.LoopOnce,
                    repetitions: 1,
                    fadeInSeconds: VRM_IDLE_ACTION_FADE_IN_SECONDS,
                    fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                    forceRestart: force || !vrmIdleVrmaAction.isRunning()
                });
                if (didStart) {
                    vrmIdleHasPlayedOnce = true;
                }
            } catch (_) {}
        }

        function markVrmAwaitingTtsStart() {
            vrmTtsStartHandled = false;
            vrmAwaitingTtsStart = true;
            if (vrmAwaitingTtsStartTimerId) {
                try { clearTimeout(vrmAwaitingTtsStartTimerId); } catch (_) {}
            }
            vrmAwaitingTtsStartTimerId = setTimeout(() => {
                vrmAwaitingTtsStartTimerId = null;
                vrmAwaitingTtsStart = false;
                stopVrmProcessingThinkingLoop({ resumeIdle: true });
            }, 8000);
        }

        function startVrmProcessingThinkingLoop() {
            const vrmModeToggle = document.getElementById('vrm-mode');
            clearVrmAwaitingTtsStart();
            vrmTtsStartHandled = false;

            if (!vrmThinkVrmaAction || !vrmModeToggle?.checked) {
                vrmProcessingThinkLoopActive = false;
                return;
            }

            vrmProcessingThinkLoopActive = true;
            clearVrmIdleReplayTimer();
            resetVrmPoseState();

            try {
                transitionToVrmAction(vrmThinkVrmaAction, {
                    loop: window.THREE.LoopRepeat,
                    fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                    fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                    forceRestart: !vrmThinkVrmaAction.isRunning()
                });
            } catch (e) {
                console.warn('Failed to start processing thinking VRMA loop:', e);
                vrmProcessingThinkLoopActive = false;
            }
        }

        function stopVrmProcessingThinkingLoop({ resumeIdle = false } = {}) {
            clearVrmAwaitingTtsStart();
            const wasProcessingLoopActive = vrmProcessingThinkLoopActive;
            vrmProcessingThinkLoopActive = false;

            if (vrmThinkVrmaAction) {
                try {
                    vrmThinkVrmaAction.clampWhenFinished = true;
                    vrmThinkVrmaAction.loop = window.THREE.LoopOnce;
                    if (wasProcessingLoopActive && vrmThinkVrmaAction.isRunning()) {
                        stopVrmAction(vrmThinkVrmaAction, VRM_ACTION_FADE_OUT_SECONDS);
                    }
                } catch (_) {}
            }

            if (resumeIdle) {
                playVrmIdleAction({ force: true });
            }
        }

        function handleVrmTtsPlaybackStarted() {
            if (vrmTtsStartHandled) {
                return;
            }

            vrmTtsStartHandled = true;
            clearVrmAwaitingTtsStart();
            vrmProcessingThinkLoopActive = false;
            clearVrmIdleReplayTimer();
            resetVrmPoseState();
            stopVrmAction(vrmLoveVrmaAction, VRM_ACTION_FADE_OUT_SECONDS);
            stopVrmAction(vrmThinkVrmaAction, VRM_ACTION_FADE_OUT_SECONDS);
            stopVrmAction(vrmCryVrmaAction, VRM_ACTION_FADE_OUT_SECONDS);
            stopVrmAction(vrmAngryVrmaAction, VRM_ACTION_FADE_OUT_SECONDS);

            if (vrmThinkVrmaAction) {
                try {
                    vrmThinkVrmaAction.clampWhenFinished = true;
                    vrmThinkVrmaAction.loop = window.THREE.LoopOnce;
                } catch (_) {}
            }

            playVrmIdleAction({ force: true });
        }

        function maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose = false) {
            if (preserveThinkingPose) {
                return;
            }
            handleVrmTtsPlaybackStarted();
        }



        // Add these variables at the top of your script section
        let webcamEnabled = false;
        const webcamToggle = document.getElementById('webcam-toggle');
        const currentModelSpan = document.getElementById('current-model');
        // Storage keys for Live2D selection persistence
        const L2D_SELECTED_KEY = 'live2dSelectedModelPath';
        const L2D_OFFSETS_KEY = 'live2dVerticalOffsets'; // Map modelPath -> offset px
        const L2D_SCALES_KEY = 'live2dSizeMultipliers'; // Map modelPath -> size multiplier

        // Storage keys for VRM selection persistence
        const VRM_SELECTED_KEY = 'vrmSelectedModelPath';
        const VRM_POSITIONS_KEY = 'vrmPositions'; // Map modelPath -> {scale, positionX, positionY, rotation}



        // Add these variables at the top of your script section
        let clipboardVisionEnabled = false;
        const clipboardToggle = document.getElementById('clipboard-toggle');

        // Add these variables near the top of your script section
        let isRecording = false;
        let spacebarPressed = false;



        // Add these variables at the top of your script section
        let availableModels = [];

        // Base chat model selection
        const baseModelDropdown = document.getElementById('base-model-dropdown');
        let baseModel = 'qwen/qwen3-4b';   // Default base model
        let defaultBaseModel = 'qwen/qwen3-4b';



        // Tool processing model selection
        const toolModelDropdown = document.getElementById('tool-model-dropdown');
        let toolModel = 'qwen/qwen3-4b'; // Default tool model
        let defaultToolModel = 'qwen/qwen3-4b'; // Store default model

        // Vision model selection (used for clipboard image mode and webcam mode)
        const visionModelDropdown = document.getElementById('vision-model-dropdown');
        let visionModel = 'qwen/qwen2.5-vl-7b'; // Default vision model
        let defaultVisionModel = 'qwen/qwen2.5-vl-7b';
        // Set the default value for the dropdown
                if (baseModelDropdown) {
            baseModelDropdown.value = defaultBaseModel;
            baseModel = defaultBaseModel;

            // Update base model when user selects a new one
            baseModelDropdown.addEventListener('change', function() {
                baseModel = this.value;
                defaultBaseModel = this.value;
                saveToolSettings();
                if (currentModelSpan) {
                    currentModelSpan.textContent = `Current Model: ${getCurrentModel()}`;
                }
            });
        }

        if (toolModelDropdown) {
            toolModelDropdown.value = defaultToolModel;
            toolModel = defaultToolModel;

            // Update tool model when user selects a new one
            toolModelDropdown.addEventListener('change', function() {
                toolModel = this.value;
                defaultToolModel = this.value;
                saveToolSettings();
                if (currentModelSpan) {
                    currentModelSpan.textContent = `Current Model: ${getCurrentModel()}`;
                }
            });
        }

        if (visionModelDropdown) {
            visionModelDropdown.value = defaultVisionModel;
            visionModel = defaultVisionModel;

            // Update vision model when user selects a new one
            visionModelDropdown.addEventListener('change', function() {
                visionModel = this.value;
                defaultVisionModel = this.value;
                saveToolSettings();
                if (currentModelSpan) {
                    currentModelSpan.textContent = `Current Model: ${getCurrentModel()}`;
                }
            });
        }

        function buildOptionalAuthorizationHeaders(apiKey = '') {
            const normalizedApiKey = String(apiKey || '').trim();
            return normalizedApiKey ? { 'Authorization': `Bearer ${normalizedApiKey}` } : {};
        }

        function normalizeOpenAiCompatibleEndpointPath(endpoint = '', targetPath = 'chat/completions') {
            const rawEndpoint = String(endpoint || '').trim();
            if (!rawEndpoint) return '';
            try {
                const parsed = new URL(rawEndpoint, window.location.href);
                const trimmedPath = parsed.pathname.replace(/\/+$/g, '').replace(/\/(chat\/completions|models)$/i, '');
                parsed.pathname = `${trimmedPath}/${targetPath}`.replace(/\/{2,}/g, '/');
                parsed.search = '';
                parsed.hash = '';
                return parsed.toString().replace(/\/$/, '');
            } catch (_) {
                const trimmedEndpoint = rawEndpoint.replace(/\/+$/g, '').replace(/\/(chat\/completions|models)$/i, '');
                return `${trimmedEndpoint}/${targetPath}`.replace(/\/{2,}/g, '/');
            }
        }

        function normalizeAvailableModelsResponse(responseData) {
            const candidates = Array.isArray(responseData?.data)
                ? responseData.data
                : Array.isArray(responseData?.models)
                    ? responseData.models
                    : Array.isArray(responseData)
                        ? responseData
                        : [];

            return candidates
                .map((model) => {
                    if (typeof model === 'string') {
                        const trimmedId = model.trim();
                        return trimmedId ? { id: trimmedId } : null;
                    }
                    if (!model || typeof model !== 'object') return null;
                    const resolvedId = [model.id, model.model, model.name]
                        .map((value) => (typeof value === 'string' ? value.trim() : ''))
                        .find(Boolean);
                    return resolvedId ? { ...model, id: resolvedId } : null;
                })
                .filter(Boolean);
        }

        function formatApiErrorDetail(detail) {
            if (!detail) return '';
            if (Array.isArray(detail)) {
                const firstItem = detail[0];
                if (typeof firstItem === 'string') return firstItem;
                if (firstItem && typeof firstItem === 'object') {
                    return firstItem.msg || firstItem.message || firstItem.loc?.join('.') || JSON.stringify(firstItem);
                }
            }
            if (typeof detail === 'object') {
                return detail.message || detail.error || JSON.stringify(detail);
            }
            return String(detail).trim();
        }

        function extractApiErrorMessage(payload, rawText = '') {
            if (payload && typeof payload === 'object') {
                const nestedError = payload.error;
                if (typeof nestedError === 'string' && nestedError.trim()) return nestedError.trim();
                if (nestedError && typeof nestedError === 'object') {
                    const nestedMessage = formatApiErrorDetail(nestedError.message || nestedError.detail || nestedError.error);
                    if (nestedMessage) return nestedMessage;
                }

                const topLevelMessage = formatApiErrorDetail(payload.detail || payload.message || payload.error_description);
                if (topLevelMessage) return topLevelMessage;
            }
            return String(rawText || '').trim();
        }

        function inferLlmSettingsHint(detail = '', statusCode = 0) {
            const normalizedDetail = String(detail || '').toLowerCase();
            if (
                /private\/local model endpoint|private or local model endpoint|resolves to a private or local address|points to a local address/.test(normalizedDetail)
            ) {
                return 'This is a local/private model URL. Add its exact base URL to OPENAI_PROXY_TRUSTED_BASE_URLS, or enable OPENAI_PROXY_ALLOW_PRIVATE on the CATBot server and restart it.';
            }
            if (statusCode === 401 || statusCode === 403 || /unauthori[sz]ed|forbidden|api key|authentication|invalid key/.test(normalizedDetail)) {
                return 'Check the API key or provider credentials in Tool Settings.';
            }
            if (/model/.test(normalizedDetail) && /not found|does not exist|unknown|invalid|unsupported/.test(normalizedDetail)) {
                return 'The selected model does not look valid for this endpoint.';
            }
            if (statusCode === 404 || /not found|unknown path|no route|unsupported path/.test(normalizedDetail)) {
                return 'Check the endpoint URL. Some OpenAI-compatible providers do not expose every standard path.';
            }
            if (statusCode === 400 || statusCode === 422 || /validation|parameter|temperature|top_p|max_tokens|tool_choice|messages/.test(normalizedDetail)) {
                return 'One of the request settings is invalid for this provider.';
            }
            return 'Check the endpoint URL, selected model, and provider-specific settings in Tool Settings.';
        }

        function buildLlmEndpointErrorMessage(response, payload, rawText = '', context = {}) {
            const statusCode = Number(response?.status || 0);
            const statusLabel = statusCode
                ? `${statusCode}${response?.statusText ? ` ${response.statusText}` : ''}`
                : 'request failed';
            const detail = extractApiErrorMessage(payload, rawText) || response?.statusText || 'The endpoint did not return a usable error message.';
            const hint = inferLlmSettingsHint(detail, statusCode);
            const requestedModel = typeof context?.model === 'string' ? context.model.trim() : '';
            const modelSuffix = requestedModel ? ` Model: ${requestedModel}.` : '';
            const actionLabel = context?.action === 'models'
                ? 'The model list could not be refreshed.'
                : 'The assistant could not get a response from the model endpoint.';
            return `${actionLabel} ${statusLabel}.${modelSuffix} ${hint} Details: ${detail}`;
        }

        async function parseJsonResponseWithErrors(response, context = {}) {
            const rawText = await response.text().catch(() => '');
            let payload = {};
            if (rawText) {
                try {
                    payload = JSON.parse(rawText);
                } catch (parseError) {
                    if (!response.ok) {
                        throw new Error(buildLlmEndpointErrorMessage(response, null, rawText, context));
                    }
                    throw new Error('The model endpoint returned an invalid JSON response. Check the endpoint URL in Tool Settings.');
                }
            }

            if (!response.ok) {
                throw new Error(buildLlmEndpointErrorMessage(response, payload, rawText, context));
            }

            return payload;
        }

        // Refresh available models when API key or endpoint changes
        apiKeyInput.addEventListener('change', fetchAvailableModels);
        endpointInput.addEventListener('change', fetchAvailableModels);
        let fetchAvailableModelsDebounceId = null;
        const queueAvailableModelsRefresh = () => {
            if (fetchAvailableModelsDebounceId) {
                window.clearTimeout(fetchAvailableModelsDebounceId);
            }
            fetchAvailableModelsDebounceId = window.setTimeout(() => {
                fetchAvailableModels().catch((error) => {
                    console.warn('Debounced model refresh failed:', error);
                });
            }, 350);
        };
        apiKeyInput.addEventListener('input', queueAvailableModelsRefresh);
        endpointInput.addEventListener('input', queueAvailableModelsRefresh);

        // Add this function to fetch available models
        async function fetchAvailableModels(preferredSettings = null) {
            const originalEndpoint = endpointInput.value.trim();
            if (!originalEndpoint) {
                return;
            }
            const apiKey = apiKeyInput.value.trim();
            const desiredBaseModel = hasMeaningfulValue(preferredSettings?.baseModel)
                ? preferredSettings.baseModel
                : (baseModelDropdown ? baseModelDropdown.value : (baseModel || defaultBaseModel));
            const desiredToolModel = hasMeaningfulValue(preferredSettings?.toolModel)
                ? preferredSettings.toolModel
                : (toolModelDropdown ? toolModelDropdown.value : (toolModel || defaultToolModel));
            const desiredVisionModel = hasMeaningfulValue(preferredSettings?.visionModel)
                ? preferredSettings.visionModel
                : (visionModelDropdown ? visionModelDropdown.value : (visionModel || defaultVisionModel));
            
            // Route through proxy server to avoid mixed content issues with HTTPS
            const endpoint = `${PROXY_BASE_URL}/v1/proxy/models?endpoint=${encodeURIComponent(originalEndpoint)}`;

            try {
                // Ensure VRM ES modules have loaded and THREE globals are present
                if (!window.__vrmModulesReady || !window.THREE || !window.GLTFLoader || !window.VRMLoaderPlugin) {
                    await new Promise((resolve) => {
                        const start = Date.now();
                        const timer = setInterval(() => {
                            if (window.__vrmModulesReady && window.THREE && window.GLTFLoader && window.VRMLoaderPlugin) {
                                clearInterval(timer);
                                resolve();
                            } else if (Date.now() - start > 5000) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 50);
                    });
                }
                const response = await fetch(endpoint, {
                    method: 'GET',
                    headers: buildOptionalAuthorizationHeaders(apiKey)
                });

                const data = await parseJsonResponseWithErrors(response, {
                    action: 'models',
                    endpoint: normalizeOpenAiCompatibleEndpointPath(originalEndpoint, 'models')
                });
                const normalizedModels = normalizeAvailableModelsResponse(data);
                if (!normalizedModels.length) {
                    throw new Error(
                        `The model list could not be refreshed. No models were returned by ${normalizeOpenAiCompatibleEndpointPath(originalEndpoint, 'models') || 'the configured endpoint'}. Check the endpoint URL and provider settings in Tool Settings.`
                    );
                }
                availableModels = normalizedModels;
                if (typeof data.warning === 'string' && data.warning.trim()) {
                    status.textContent = data.warning.trim();
                }
                
                // Update tool model dropdown
                if (toolModelDropdown) {
                    toolModel = populateModelDropdown(
                        toolModelDropdown,
                        availableModels,
                        desiredToolModel,
                        defaultToolModel
                    ) || defaultToolModel;
                    defaultToolModel = toolModel;
                }

                // Update base model dropdown
                if (baseModelDropdown) {
                    baseModel = populateModelDropdown(
                        baseModelDropdown,
                        availableModels,
                        desiredBaseModel,
                        defaultBaseModel
                    ) || defaultBaseModel;
                    defaultBaseModel = baseModel;
                }

                // Populate Live2D model controls from scanned textarea data plus persisted selection
                const live2dList = document.getElementById('live2d-model-list');
                const live2dDropdown = document.getElementById('live2d-model-dropdown');
                const live2dOffsetRange = document.getElementById('live2d-offset-range');
                const live2dOffsetValue = document.getElementById('live2d-offset-value');
                const live2dScaleRange = document.getElementById('live2d-scale-range');
                const live2dScaleValue = document.getElementById('live2d-scale-value');
                if (live2dList && live2dDropdown) {
                    // Load persisted selection and offsets; list contents are scan-driven
                    try {
                        const savedSelected = localStorage.getItem(L2D_SELECTED_KEY);
                        if (savedSelected) {
                            modelPath = savedSelected;
                        }
                        const savedOffsets = localStorage.getItem(L2D_OFFSETS_KEY);
                        if (savedOffsets) {
                            live2dOffsets = JSON.parse(savedOffsets);
                        }
                        const savedScales = localStorage.getItem(L2D_SCALES_KEY);
                        if (savedScales) {
                            live2dScales = JSON.parse(savedScales);
                        }
                    } catch (e) {
                        console.warn('Unable to read persisted Live2D model list/selection:', e);
                    }
                    syncLive2DModelControls();

                    // Update modelPath when user selects a new one and persist selection
                    live2dDropdown.onchange = async () => {
                        modelPath = live2dDropdown.value;
                        try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
                        // Set the offset UI to stored value (default 0)
                        const currentOffset = getLive2DOffset(modelPath);
                        const currentScale = getLive2DScale(modelPath);
                        if (live2dOffsetRange && live2dOffsetValue) {
                            live2dOffsetRange.value = String(currentOffset);
                            live2dOffsetValue.textContent = String(currentOffset);
                        }
                        if (live2dScaleRange && live2dScaleValue) {
                            live2dScaleRange.value = String(currentScale);
                            live2dScaleValue.textContent = formatLive2DScale(currentScale);
                        }
                        saveToolSettings();
                        if (document.getElementById('live2d-mode')?.checked) {
                            try {
                                cleanupLive2D();
                            } catch (e) {
                                console.warn('Error destroying previous Live2D model (safe to ignore):', e);
                            }
                            await initLive2D();
                        }
                    };

                    // Rebuild dropdown if the scanned list changes programmatically
                    live2dList.addEventListener('input', async () => {
                        const previousModelPath = modelPath;
                        syncLive2DModelControls();

                        if (modelPath !== previousModelPath) {
                            try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
                            saveToolSettings();
                            if (document.getElementById('live2d-mode')?.checked) {
                                try {
                                    cleanupLive2D();
                                } catch (e) {
                                    console.warn('Error destroying previous Live2D model (safe to ignore):', e);
                                }
                                await initLive2D();
                            }
                        }
                    });

                    // Offset and size changes -> update persisted values and apply immediately
                    if (live2dOffsetRange && live2dOffsetValue && live2dScaleRange && live2dScaleValue) {
                        // Initialize UI with current offset
                        const initialOffset = getLive2DOffset(modelPath);
                        const initialScale = getLive2DScale(modelPath);
                        live2dOffsetRange.value = String(initialOffset);
                        live2dOffsetValue.textContent = String(initialOffset);
                        live2dScaleRange.value = String(initialScale);
                        live2dScaleValue.textContent = formatLive2DScale(initialScale);
                        live2dOffsetRange.addEventListener('input', () => {
                            if (!modelPath) return;
                            const newOffset = parseInt(live2dOffsetRange.value, 10) || 0;
                            live2dOffsetValue.textContent = String(newOffset);
                            live2dOffsets[modelPath] = newOffset;
                            try { localStorage.setItem(L2D_OFFSETS_KEY, JSON.stringify(live2dOffsets)); } catch {}
                            applyCurrentLive2DLayout();
                            saveToolSettings();
                        });
                        live2dScaleRange.addEventListener('input', () => {
                            if (!modelPath) return;
                            const newScale = Math.min(3.0, Math.max(0.4, parseFloat(live2dScaleRange.value) || 1.0));
                            live2dScaleValue.textContent = formatLive2DScale(newScale);
                            live2dScales[modelPath] = newScale;
                            try { localStorage.setItem(L2D_SCALES_KEY, JSON.stringify(live2dScales)); } catch {}
                            applyCurrentLive2DLayout();
                            saveToolSettings();
                        });
                    }
                }

                // Initialize VRM model list and controls
                const vrmList = document.getElementById('vrm-model-list');
                const vrmDropdown = document.getElementById('vrm-model-dropdown');
                if (vrmList && vrmDropdown) {
                    // Load persisted selection and transforms; list contents are scan-driven
                    try {
                        const savedSelected = localStorage.getItem(VRM_SELECTED_KEY);
                        if (savedSelected) {
                            currentVRMModelPath = savedSelected;
                        }
                        const savedPositions = localStorage.getItem(VRM_POSITIONS_KEY);
                        if (savedPositions) {
                            vrmPositions = JSON.parse(savedPositions);
                        }
                    } catch (e) {
                        console.warn('Unable to read persisted VRM model list/selection:', e);
                    }
                    syncVRMModelControls();

                    vrmDropdown.onchange = async () => {
                        currentVRMModelPath = vrmDropdown.value;
                        try { localStorage.setItem(VRM_SELECTED_KEY, currentVRMModelPath); } catch {}
                        // Optionally reinitialize VRM with the new model
                        if (document.getElementById('vrm-mode').checked) {
                            cleanupVRM();
                            await initVRM();
                        }
                    };

                    vrmList.addEventListener('input', async () => {
                        const previousModelPath = currentVRMModelPath;
                        syncVRMModelControls();

                        if (currentVRMModelPath !== previousModelPath) {
                            try { localStorage.setItem(VRM_SELECTED_KEY, currentVRMModelPath); } catch {}
                            if (document.getElementById('vrm-mode').checked) {
                                cleanupVRM();
                                await initVRM();
                            }
                        }
                    });
                }

                // VRM position controls
                const vrmScaleRange = document.getElementById('vrm-scale-range');
                const vrmScaleValue = document.getElementById('vrm-scale-value');
                const vrmPositionXRange = document.getElementById('vrm-position-x-range');
                const vrmPositionXValue = document.getElementById('vrm-position-x-value');
                const vrmPositionYRange = document.getElementById('vrm-position-y-range');
                const vrmPositionYValue = document.getElementById('vrm-position-y-value');
                const vrmRotationRange = document.getElementById('vrm-rotation-range');
                const vrmRotationValue = document.getElementById('vrm-rotation-value');

                if (vrmScaleRange && vrmScaleValue) {
                    // Load persisted positions for current model
                    const currentPositions = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
                    vrmScaleRange.value = currentPositions.scale;
                    vrmScaleValue.textContent = String(currentPositions.scale);
                    vrmPositionXRange.value = currentPositions.positionX;
                    vrmPositionXValue.textContent = String(currentPositions.positionX);
                    vrmPositionYRange.value = currentPositions.positionY;
                    vrmPositionYValue.textContent = String(currentPositions.positionY);
                    vrmRotationRange.value = currentPositions.rotation;
                    vrmRotationValue.textContent = String(currentPositions.rotation);

                    // Scale control
                    vrmScaleRange.addEventListener('input', () => {
                        const newScale = parseFloat(vrmScaleRange.value) || 1.0;
                        vrmScaleValue.textContent = String(newScale);
                        const existing = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
                        vrmPositions[currentVRMModelPath] = { ...existing, scale: newScale };
                        updateVRMTransform();
                    });

                    // Position X control
                    vrmPositionXRange.addEventListener('input', () => {
                        const newX = parseFloat(vrmPositionXRange.value) || 0;
                        vrmPositionXValue.textContent = String(newX);
                        const existing = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
                        vrmPositions[currentVRMModelPath] = { ...existing, positionX: newX };
                        updateVRMTransform();
                    });

                    // Position Y control
                    vrmPositionYRange.addEventListener('input', () => {
                        const newY = parseFloat(vrmPositionYRange.value) || 0;
                        vrmPositionYValue.textContent = String(newY);
                        const existing = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
                        vrmPositions[currentVRMModelPath] = { ...existing, positionY: newY };
                        updateVRMTransform();
                    });

                    // Rotation control
                    vrmRotationRange.addEventListener('input', () => {
                        const newRotation = parseInt(vrmRotationRange.value, 10) || 0;
                        vrmRotationValue.textContent = String(newRotation);
                        const existing = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
                        vrmPositions[currentVRMModelPath] = { ...existing, rotation: newRotation };
                        updateVRMTransform();
                    });
                }

                // Avatar mode toggle
                const live2dModeRadio = document.getElementById('live2d-mode');
                const vrmModeRadio = document.getElementById('vrm-mode');

                if (live2dModeRadio && vrmModeRadio) {
                    live2dModeRadio.addEventListener('change', async () => {
                        if (live2dModeRadio.checked) {
                            await switchToLive2D();
                            saveToolSettings();
                        }
                    });

                    vrmModeRadio.addEventListener('change', async () => {
                        if (vrmModeRadio.checked) {
                            await switchToVRM();
                            saveToolSettings();
                        }
                    });
                }

                // Update vision model dropdown (filter to models that look multimodal if desired)
                if (visionModelDropdown) {
                    visionModel = populateModelDropdown(
                        visionModelDropdown,
                        availableModels,
                        desiredVisionModel,
                        defaultVisionModel
                    ) || defaultVisionModel;
                    defaultVisionModel = visionModel;
                }
            } catch (error) {
                console.warn('Model list refresh failed:', error?.message || error);
                status.textContent = error.message || 'The model list could not be refreshed. Check Tool Settings.';
                if (toolModelDropdown) {
                    toolModel = populateModelDropdown(
                        toolModelDropdown,
                        [],
                        desiredToolModel,
                        defaultToolModel
                    ) || defaultToolModel;
                    defaultToolModel = toolModel;
                }
                if (baseModelDropdown) {
                    baseModel = populateModelDropdown(
                        baseModelDropdown,
                        [],
                        desiredBaseModel,
                        defaultBaseModel
                    ) || defaultBaseModel;
                    defaultBaseModel = baseModel;
                }
                if (visionModelDropdown) {
                    visionModel = populateModelDropdown(
                        visionModelDropdown,
                        [],
                        desiredVisionModel,
                        defaultVisionModel
                    ) || defaultVisionModel;
                    defaultVisionModel = visionModel;
                }
            }
        }

        // Add this event listener after your other initialization code
        clipboardToggle.addEventListener('change', function() {
            clipboardVisionEnabled = this.checked;
            // Guard against missing span element
            if (currentModelSpan) {
                currentModelSpan.textContent = `Current Model: ${getCurrentModel()}`;
            }
            
            // Start or stop clipboard monitoring based on toggle state
            if (clipboardVisionEnabled) {
                startClipboardMonitoring();
            } else {
                stopClipboardMonitoring();
                clearClipboardPreview(); // Clear clipboard data when mode is disabled
            }
        });

        // Update the webcam toggle event listener
        webcamToggle.addEventListener('change', function() {
            webcamEnabled = this.checked;
            // Guard against missing span element
            if (currentModelSpan) {
                currentModelSpan.textContent = `Current Model: ${getCurrentModel()}`;
            }
            
            // Show/hide webcam preview
            const previewContainer = document.getElementById('webcam-preview-container');
            previewContainer.style.display = webcamEnabled ? 'block' : 'none';
            
            if (webcamEnabled) {
                initWebcam();
                startPeriodicCapture();
            } else {
                if (webcamInterval) {
                    clearInterval(webcamInterval);
                }
                if (webcamStream) {
                    webcamStream.getTracks().forEach(track => track.stop());
                    webcamStream = null;
                }
            }
        });

        // Update the getCurrentModel function to handle tool requests separately
        function getCurrentModel(isToolRequest = false) {
            if (isToolRequest) {
                return toolModelDropdown.value || toolModel;
            }
            const hasPendingImageAttachments = pendingAttachmentFiles.some((file) => isVisionImageFile(file));
            // If webcam or clipboard vision is enabled, use the corresponding model
            if (webcamEnabled) {
                return visionModel || 'qwen/qwen2.5-vl-7b';
            }
            if (clipboardVisionEnabled && clipboardType === 'image') {
                return visionModel || 'qwen/qwen2.5-vl-7b';
            }
            if (hasPendingImageAttachments) {
                return visionModel || 'qwen/qwen2.5-vl-7b';
            }
            if (clipboardVisionEnabled && clipboardType === 'text') {
                return toolModel;
            }
            
            // Reset endpoint URL for other cases if it was changed
            const currentEndpoint = endpointInput.value;
            if (currentEndpoint.includes('api.openai.com')) {
                endpointInput.value = 'http://localhost:1234/v1/chat/completions';
            }
            return baseModel;
        }

        function populateModelDropdown(dropdown, models, preferredValue, fallbackValue) {
            if (!dropdown) return '';

            const normalizedPreferred = hasMeaningfulValue(preferredValue) ? String(preferredValue).trim() : '';
            const normalizedFallback = hasMeaningfulValue(fallbackValue) ? String(fallbackValue).trim() : '';
            const seenValues = new Set();
            dropdown.innerHTML = '';

            if (Array.isArray(models)) {
                models.forEach(model => {
                    const modelId = typeof model?.id === 'string' ? model.id.trim() : '';
                    if (!modelId || seenValues.has(modelId)) return;
                    seenValues.add(modelId);
                    const option = document.createElement('option');
                    option.value = modelId;
                    option.textContent = modelId;
                    dropdown.appendChild(option);
                });
            }

            [normalizedPreferred, normalizedFallback].forEach(value => {
                if (!value || seenValues.has(value)) return;
                seenValues.add(value);
                const option = document.createElement('option');
                option.value = value;
                option.textContent = value;
                dropdown.appendChild(option);
            });

            const desiredValue = normalizedPreferred || normalizedFallback;
            if (desiredValue) {
                dropdown.value = desiredValue;
            }

            if (!dropdown.value && dropdown.options.length > 0) {
                dropdown.selectedIndex = 0;
            }

            return dropdown.value || desiredValue || '';
        }

        function applyEnvDefaultTtsVoiceOnFetchFailure() {
            const envVoice = (envToolDefaults && typeof envToolDefaults.ttsVoice === 'string')
                ? envToolDefaults.ttsVoice.trim()
                : '';
            if (!envVoice || !ttsVoiceDropdown) return false;

            if (!Array.from(ttsVoiceDropdown.options).some(option => option.value === envVoice)) {
                const option = document.createElement('option');
                option.value = envVoice;
                option.textContent = envVoice;
                ttsVoiceDropdown.appendChild(option);
            }

            ttsVoiceDropdown.value = envVoice;
            saveToolSettings();
            console.warn('TTS voices fetch failed; applied .env default voice to tool settings:', envVoice);
            return true;
        }

        function applyEnvDefaultTtsModelOnFetchFailure() {
            const envModel = (envToolDefaults && typeof envToolDefaults.ttsModel === 'string')
                ? envToolDefaults.ttsModel.trim()
                : '';
            if (!envModel || !ttsModelDropdown) return false;

            if (!Array.from(ttsModelDropdown.options).some(option => option.value === envModel)) {
                const option = document.createElement('option');
                option.value = envModel;
                option.textContent = envModel;
                ttsModelDropdown.appendChild(option);
            }

            ttsModelDropdown.value = envModel;
            saveToolSettings();
            console.warn('TTS voices fetch failed; applied .env default model to tool settings:', envModel);
            return true;
        }

        function normalizeTtsVoiceEntries(responseData) {
            if (Array.isArray(responseData)) {
                return responseData;
            }
            if (responseData && typeof responseData === 'object') {
                if (Array.isArray(responseData.voices)) {
                    return responseData.voices;
                }
                if (Array.isArray(responseData.data)) {
                    return responseData.data;
                }
            }
            return [];
        }

        // Fetch TTS voices from OpenAI-compatible endpoint (e.g., Chatterbox)
        async function fetchTtsVoices() {
            try {
                // Get the TTS endpoint and normalize it (remove trailing slash)
                const endpoint = (ttsEndpointInput && ttsEndpointInput.value && ttsEndpointInput.value.trim()) 
                    ? ttsEndpointInput.value.trim().replace(/\/$/, '') 
                    : 'http://localhost:4123/v1';
                const selectedModel = (ttsModelDropdown && ttsModelDropdown.value && ttsModelDropdown.value.trim())
                    ? ttsModelDropdown.value.trim()
                    : '';
                
                // Extract base URL (origin: protocol + host + port) to pass to proxy
                // The proxy will try /voices first, then /v1/audio/voices
                let baseUrl;
                try {
                    // Parse the endpoint URL to extract the origin (protocol + host + port)
                    const endpointUrl = new URL(endpoint);
                    baseUrl = endpointUrl.origin; // Gets protocol + host + port, without any path
                } catch (e) {
                    // Fallback to simple string replacement if URL parsing fails
                    // Remove /v1 if it's at the end, or extract origin manually
                    const match = endpoint.match(/^(https?:\/\/[^\/]+)/);
                    baseUrl = match ? match[1] : endpoint.replace(/\/v1$/, '');
                }
                
                console.log('Fetching voices through proxy from TTS endpoint:', baseUrl);
                
                // Try to fetch voices from the configured endpoint through proxy
                // The proxy will automatically try /voices first, then /v1/audio/voices
                let response = null;
                let responseData = null;
                
                try {
                    const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/tts/voices?endpoint=${encodeURIComponent(baseUrl)}${selectedModel ? `&model=${encodeURIComponent(selectedModel)}` : ''}`;
                    console.log('Fetching voices through proxy:', proxyUrl);
                    response = await fetch(proxyUrl, {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    if (response.ok) {
                        responseData = await response.json();
                    }
                } catch (e) {
                    console.warn('Primary fetch failed:', e);
                    response = null;
                }
                
                // If primary fetch fails, try OpenAI-compatible fallback endpoint
                // (different server, so we try it separately)
                if (!response || !response.ok) {
                    console.warn('Primary fetch failed, trying OpenAI-compatible fallback endpoint');
                    const openAiFallbackUrl = 'http://localhost:8880';
                    try {
                        const openAiFallbackProxyUrl = `${PROXY_BASE_URL}/v1/proxy/tts/voices?endpoint=${encodeURIComponent(openAiFallbackUrl)}${selectedModel ? `&model=${encodeURIComponent(selectedModel)}` : ''}`;
                        console.log('Fetching voices from OpenAI-compatible fallback through proxy:', openAiFallbackProxyUrl);
                        response = await fetch(openAiFallbackProxyUrl, {
                            method: 'GET',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        });
                        
                        if (response.ok) {
                            responseData = await response.json();
                        }
                    } catch (e) {
                        console.warn('OpenAI fallback failed:', e);
                        response = null;
                    }
                }
                
                // If all attempts failed, log error and return
                if (!response || !response.ok || !responseData) {
                    console.error('Failed to fetch voices from all endpoints');
                    applyEnvDefaultTtsModelOnFetchFailure();
                    applyEnvDefaultTtsVoiceOnFetchFailure();
                    return;
                }
                
                console.log('Fetched voices:', responseData);
                
                const voicesData = normalizeTtsVoiceEntries(responseData);
                if (!Array.isArray(voicesData)) {
                    console.warn('Unexpected voices response format:', responseData);
                }
                
                const storedVoice = (() => {
                    try {
                        const savedSettings = localStorage.getItem('toolSettings');
                        if (!savedSettings) return '';
                        const settings = JSON.parse(savedSettings);
                        return settings.ttsVoice || '';
                    } catch (error) {
                        console.warn('Could not read stored TTS voice:', error);
                        return '';
                    }
                })();
                const fallbackVoice = ttsVoiceDropdown.value || storedVoice;

                // Clear existing options
                ttsVoiceDropdown.innerHTML = '';
                
                // Add a model-aware fallback voice before appending fetched voices.
                const defaultVoices = selectedModel.toLowerCase().includes('pocket-tts') ? ['alba'] : ['Empress'];
                defaultVoices.forEach(voice => {
                    if (Array.from(ttsVoiceDropdown.options).some(option => option.value === voice)) return;
                    const option = document.createElement('option');
                    option.value = voice;
                    option.textContent = voice;
                    ttsVoiceDropdown.appendChild(option);
                });
                
                // Add fetched voices from Chatterbox
                if (Array.isArray(voicesData)) {
                    console.log(`Adding ${voicesData.length} voices from Chatterbox`);
                    voicesData.forEach(voice => {
                        const voiceValue = voice.id || voice.name;
                        if (!voiceValue) return;
                        if (Array.from(ttsVoiceDropdown.options).some(option => option.value === voiceValue)) return;
                        const option = document.createElement('option');
                        option.value = voiceValue;
                        // Show filename if metadata is not available
                        const displayName = (voice.name || voiceValue) + (voice.metadata?.language ? ` (${voice.metadata.language})` : 
                            (voice.filename ? ` - ${voice.filename}` : ''));
                        option.textContent = displayName;
                        ttsVoiceDropdown.appendChild(option);
                    });
                } else {
                    console.warn('Voices data is not an array:', voicesData);
                }
                
                const availableVoiceValues = Array.from(ttsVoiceDropdown.options).map(option => option.value);
                const desiredVoice = availableVoiceValues.includes(storedVoice) ? storedVoice : fallbackVoice;
                if (desiredVoice && availableVoiceValues.includes(desiredVoice)) {
                    ttsVoiceDropdown.value = desiredVoice;
                }

                console.log('TTS voices updated successfully');
                saveToolSettings(); // Save the updated voice list state
            } catch (error) {
                console.error('Error fetching TTS voices:', error);
                applyEnvDefaultTtsModelOnFetchFailure();
                applyEnvDefaultTtsVoiceOnFetchFailure();
            }
        }

        // Populate voice list for Text-to-Speech
        function loadVoices() {
            // Fetch available voices and rebuild the dropdown without losing the user's selection
            voices = speechSynthesis.getVoices();
            voiceDropdown.innerHTML = '';

            let defaultVoiceIndex = 0; // Fallback default

            if (voices.length === 0) {
                console.warn('No voices available yet, waiting for voices to load');
                return;
            }

            // Read any previously selected voice from persistent storage
            let storedVoiceURI = null;
            try {
                storedVoiceURI = localStorage.getItem(SELECTED_VOICE_STORAGE_KEY);
            } catch (readError) {
                console.warn('Could not read selected voice from localStorage:', readError);
            }

            voices.forEach((voice, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `${voice.name} (${voice.lang})`;
                voiceDropdown.appendChild(option);

                // Prefer Microsoft Ana Online; otherwise choose first English voice as a reasonable default
                if (voice.name === 'Microsoft Ana Online (Natural) - English (United States)') {
                    defaultVoiceIndex = index;
                } else if (voice.lang.includes('en-') && defaultVoiceIndex === 0) {
                    defaultVoiceIndex = index;
                }
            });

            // Determine which voice should be selected after re-populating the list
            let selectedIndex = defaultVoiceIndex;
            if (storedVoiceURI) {
                const idx = voices.findIndex(v => v.voiceURI === storedVoiceURI);
                if (idx !== -1) {
                    selectedIndex = idx;
                }
            }

            voiceDropdown.value = String(selectedIndex);

            // Ensure the chosen voice is persisted for future sessions
            try {
                if (!storedVoiceURI && voices[selectedIndex]) {
                    localStorage.setItem(SELECTED_VOICE_STORAGE_KEY, voices[selectedIndex].voiceURI);
                }
            } catch (persistError) {
                console.warn('Could not persist selected voice in localStorage:', persistError);
            }

            console.log('Voices loaded:', voices.length, 'Selected voice:', voices[selectedIndex]?.name);
        }

        // Initial load of voices
        loadVoices();
        
        // Handle voice changes
        if (typeof speechSynthesis !== 'undefined') {
            speechSynthesis.onvoiceschanged = function() {
                loadVoices();
            };
        }

        // Function to generate random movement within a range
        function randomInRange(min, max) {
            const result = Math.random() * (max - min) + min;
            console.log(`randomInRange: min=${min}, max=${max}, result=${result}`);
            return result;
        }
	
	// ─── Helper ───
	// Removes everything between <think> … </think> (case-insensitive, multiline)
	function stripThinkTags(text = '') {
    		return text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
	}

        function coerceMessageText(content) {
            if (content == null) return '';
            if (typeof content === 'string') return content;
            if (Array.isArray(content)) {
                return content.map(item => {
                    if (typeof item === 'string') return item.trim();
                    if (!item || typeof item !== 'object') return '';
                    let candidate = item.text;
                    if (candidate && typeof candidate === 'object') {
                        candidate = candidate.value || candidate.content;
                    }
                    if (typeof candidate !== 'string') {
                        candidate = item.content || item.output_text || '';
                    }
                    return typeof candidate === 'string' ? candidate.trim() : '';
                }).filter(Boolean).join('\n').trim();
            }
            if (typeof content === 'object') {
                let candidate = content.text;
                if (candidate && typeof candidate === 'object') {
                    candidate = candidate.value || candidate.content;
                }
                if (typeof candidate !== 'string') {
                    candidate = content.content || content.output_text || '';
                }
                return typeof candidate === 'string' ? candidate.trim() : '';
            }
            return String(content).trim();
        }

        function isMinimaxCompatibleRequest(endpoint = '', model = '') {
            let hostname = '';
            try {
                const parsed = new URL(endpoint, window.location.href);
                const proxiedEndpoint = parsed.searchParams.get('endpoint');
                const resolved = proxiedEndpoint ? new URL(proxiedEndpoint) : parsed;
                hostname = resolved.hostname.toLowerCase();
            } catch (_) {
                hostname = '';
            }
            return hostname.endsWith('minimax.io') || hostname.endsWith('minimaxi.com') || /\bminimax\b|^MiniMax-/i.test(String(model || '').trim());
        }

        function normalizeMinimaxTemperature(value) {
            const parsed = Number(value);
            if (!Number.isFinite(parsed)) return value;
            if (parsed <= 0) return 0.01;
            if (parsed > 1) return 1;
            return parsed;
        }

        function buildCompatibleChatBody(endpoint, payload = {}) {
            const body = { ...payload };
            if (isMinimaxCompatibleRequest(endpoint, body.model)) {
                if (Object.prototype.hasOwnProperty.call(body, 'temperature')) {
                    body.temperature = normalizeMinimaxTemperature(body.temperature);
                }
                body.extra_body = {
                    ...(body.extra_body || {}),
                    reasoning_split: true
                };
            }
            return body;
        }

        function isVisionImageMimeType(mimeType = '') {
            const normalized = String(mimeType || '').trim().toLowerCase();
            return normalized === 'image/png' || normalized === 'image/jpeg' || normalized === 'image/jpg';
        }

        function isVisionImageFile(file) {
            if (!file) return false;
            if (isVisionImageMimeType(file.type)) return true;
            const name = String(file.name || '').toLowerCase();
            return name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg');
        }

        function fileToDataUrl(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result || ''));
                reader.onerror = () => reject(reader.error || new Error('Failed to read file.'));
                reader.readAsDataURL(file);
            });
        }

        async function buildVisionImagePartsFromFiles(files = []) {
            const imageFiles = Array.isArray(files)
                ? files.filter((file) => isVisionImageFile(file))
                : [];
            if (!imageFiles.length) return [];

            const parts = [];
            for (const file of imageFiles) {
                const dataUrl = await fileToDataUrl(file);
                if (!dataUrl) continue;
                parts.push({
                    type: 'image_url',
                    image_url: {
                        url: dataUrl,
                        detail: 'auto'
                    }
                });
            }
            return parts;
        }

        function stringifyPayloadForLog(payload) {
            return JSON.stringify(payload, (key, value) => {
                if (typeof value === 'string' && value.startsWith('data:image/')) {
                    return `[image-data-url:${value.length} chars]`;
                }
                return value;
            }, 2);
        }

        function buildAssistantHistoryMessage(message = {}) {
            const out = { role: message.role || 'assistant' };
            ['content', 'tool_calls', 'name', 'function_call', 'refusal', 'reasoning_details'].forEach((key) => {
                if (message && Object.prototype.hasOwnProperty.call(message, key) && message[key] != null) {
                    out[key] = message[key];
                }
            });
            return out;
        }

        function getChoiceMessage(choice = {}) {
            if (choice && typeof choice === 'object' && choice.message && typeof choice.message === 'object') {
                return choice.message;
            }
            if (choice && typeof choice === 'object') {
                return {
                    role: 'assistant',
                    content: choice.cleanContent ?? choice.content ?? choice.text ?? ''
                };
            }
            return { role: 'assistant', content: '' };
        }

        function extractChoiceRawText(choice = {}) {
            const message = getChoiceMessage(choice);
            const content = coerceMessageText(message?.content ?? '');
            if (content) return content;
            if (choice && typeof choice === 'object') {
                return coerceMessageText(choice.cleanContent ?? choice.content ?? choice.text ?? '');
            }
            return '';
        }

        function extractChoiceVisibleText(choice = {}) {
            return stripThinkTags(extractChoiceRawText(choice));
        }

        function getVisibleAssistantText(message = {}) {
            return stripThinkTags(coerceMessageText(message?.content || ''));
        }

        function renderAssistantErrorResponse(message = '') {
            const normalizedMessage = String(message || '').trim();
            if (!normalizedMessage) return;
            responseOutput.value = normalizedMessage;
            addMessageToHistory('assistant', normalizedMessage);
        }
	
        // Function to create smooth head movement
        async function animateHeadMovement(model, duration) {
            const targetX = randomInRange(-15, 15);
            const targetY = randomInRange(-10, 10);
            const targetZ = randomInRange(-5, 5);
            
            const steps = 60; // Number of animation frames
            const startX = model.internalModel.coreModel.getParameterValueById('ParamAngleX');
            const startY = model.internalModel.coreModel.getParameterValueById('ParamAngleY');
            const startZ = model.internalModel.coreModel.getParameterValueById('ParamAngleZ');
            
            for (let i = 0; i <= steps; i++) {
                const progress = i / steps;
                // Easing function for smooth movement
                const ease = progress * (2 - progress);
                
                const currentX = startX + (targetX - startX) * ease;
                const currentY = startY + (targetY - startY) * ease;
                const currentZ = startZ + (targetZ - startZ) * ease;
                
                model.internalModel.coreModel.setParameterValueById('ParamAngleX', currentX);
                model.internalModel.coreModel.setParameterValueById('ParamAngleY', currentY);
                model.internalModel.coreModel.setParameterValueById('ParamAngleZ', currentZ);
                
                await new Promise(resolve => setTimeout(resolve, duration / steps));
            }
        }

        // Helper function to remove emojis from text before TTS processing
        function removeEmojis(text) {
            // Comprehensive regex pattern to match various emoji ranges
            // Includes standard emojis, symbols, emoticons, pictographs, etc.
            const emojiRegex = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2300}-\u{23FF}\u{2B50}\u{2B55}\u{231A}\u{231B}\u{2328}\u{23CF}\u{23E9}-\u{23FF}\u{24C2}\u{25AA}-\u{25AB}\u{25B6}\u{25C0}\u{25FB}-\u{25FE}\u{2934}-\u{2935}\u{2B05}-\u{2B07}\u{2B1B}-\u{2B1C}\u{3030}\u{303D}\u{3297}\u{3299}\u{FE0F}\u{200D}]/gu;
            return text.replace(emojiRegex, ''); // Remove all emojis and return clean text
        }

        // Helper function to strip any bracketed content including nested pairs
        function stripBracketedContent(text) { // Remove text inside (), [], {}, <> recursively
            const patterns = [ /\([^()]*\)/g, /\[[^\[\]]*\]/g, /\{[^{}]*\}/g, /<[^<>]*>/g ]; // One-level patterns for each bracket type
            let prev = null; // Track previous value to detect stabilization
            let curr = String(text); // Work on a copy of the input
            while (curr !== prev) { // Iterate until no further removals occur
                prev = curr; // Save current state for comparison
                for (const re of patterns) { curr = curr.replace(re, ''); } // Remove one nesting level for each pattern
            }
            return curr; // Return text with bracketed content removed
        }

        // Canonical sanitizer for all TTS inputs (browser and Chatterbox)
        function sanitizeTTS(text) { // Normalize TTS text by removing emojis, bracketed content, asterisks, and special symbols
            if (!text) return text; // Guard against falsy input
            let t = String(text); // Ensure string type for processing
            t = removeEmojis(t); // Drop emojis which TTS may speak oddly
            t = stripBracketedContent(t); // Remove stage directions or asides in brackets
            t = t.replace(/\*/g, ''); // Remove asterisks used for emphasis or actions
            t = t.replace(/[^\w\s\.,!\?;:'"\-]/g, ''); // Remove remaining special symbols, keep common punctuation
            t = t.replace(/\s+/g, ' ').trim(); // Collapse whitespace and trim ends
            return t; // Provide sanitized text
        }

        // Split long TTS text into sentence-aware chunks for browser speech engines.
        function splitTtsTextChunks(text, maxChars = 280) {
            const cleaned = (text || '').trim();
            if (!cleaned) return [];
            if (cleaned.length <= maxChars) return [cleaned];

            const segments = cleaned.split(/(?<=[.!?])\s+/).filter(Boolean);
            const chunks = [];
            let current = '';

            const appendPiece = (piece) => {
                const safePiece = (piece || '').trim();
                if (!safePiece) return;
                if (!current) {
                    current = safePiece;
                    return;
                }
                const candidate = `${current} ${safePiece}`;
                if (candidate.length <= maxChars) {
                    current = candidate;
                } else {
                    chunks.push(current);
                    current = safePiece;
                }
            };

            for (const segment of segments) {
                if (segment.length <= maxChars) {
                    appendPiece(segment);
                    continue;
                }
                const words = segment.split(/\s+/).filter(Boolean);
                let wordBuffer = '';
                for (const word of words) {
                    const candidate = wordBuffer ? `${wordBuffer} ${word}` : word;
                    if (candidate.length <= maxChars) {
                        wordBuffer = candidate;
                        continue;
                    }
                    if (wordBuffer) appendPiece(wordBuffer);
                    wordBuffer = '';
                    if (word.length <= maxChars) {
                        wordBuffer = word;
                    } else {
                        for (let i = 0; i < word.length; i += maxChars) {
                            appendPiece(word.slice(i, i + maxChars));
                        }
                    }
                }
                if (wordBuffer) appendPiece(wordBuffer);
            }

            if (current) chunks.push(current);
            return chunks.length > 0 ? chunks : [cleaned];
        }

        function getSelectedBrowserVoice() {
            const selectedVoiceIndex = parseInt(voiceDropdown.value, 10);
            if (voices.length > 0 && !Number.isNaN(selectedVoiceIndex) && voices[selectedVoiceIndex]) {
                return voices[selectedVoiceIndex];
            }
            return null;
        }

        function resetBrowserSpeechMouthState() {
            const mouthOpenY = 'ParamMouthOpenY';
            if (live2dModel) {
                live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, 0);
            }
            const vrmModeToggle = document.getElementById('vrm-mode');
            if (vrmModel && vrmModeToggle && vrmModeToggle.checked) {
                animateVRMLipSync(0);
            }
        }

        function startBrowserSpeechLipSyncLoop() {
            const mouthOpenY = 'ParamMouthOpenY';
            if (microsoftTtsRafId) return;

            microsoftTtsIsActive = true;
            microsoftTtsSmoothedAmplitude = 0;
            microsoftTtsTargetAmplitude = 0.3;
            microsoftTtsLastBoundaryTs = performance.now();

            const attack = 0.6;
            const release = 0.15;
            const threshold = 0.05;
            const boundaryDecayRate = 0.08;
            const boundaryDecayDelay = 50;

            const step = () => {
                if (!microsoftTtsIsActive || !isSpeaking) {
                    microsoftTtsRafId = 0;
                    microsoftTtsSmoothedAmplitude = 0;
                    resetBrowserSpeechMouthState();
                    return;
                }

                const now = performance.now();
                const timeSinceBoundary = now - microsoftTtsLastBoundaryTs;

                if (timeSinceBoundary > boundaryDecayDelay) {
                    const decayFactor = Math.min(1.0, (timeSinceBoundary - boundaryDecayDelay) / 200);
                    microsoftTtsTargetAmplitude = Math.max(0, microsoftTtsTargetAmplitude - (boundaryDecayRate * decayFactor));
                }

                if (microsoftTtsTargetAmplitude > microsoftTtsSmoothedAmplitude) {
                    microsoftTtsSmoothedAmplitude += (microsoftTtsTargetAmplitude - microsoftTtsSmoothedAmplitude) * attack;
                } else {
                    microsoftTtsSmoothedAmplitude += (microsoftTtsTargetAmplitude - microsoftTtsSmoothedAmplitude) * release;
                }

                const scaled = microsoftTtsSmoothedAmplitude <= threshold ? 0 : Math.min(1, (microsoftTtsSmoothedAmplitude - threshold) * 5.5);

                if (live2dModel) {
                    live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, scaled);
                }

                const vrmModeToggle = document.getElementById('vrm-mode');
                if (vrmModel && vrmModeToggle && vrmModeToggle.checked) {
                    animateVRMLipSync(scaled);
                }

                if (isSpeaking && microsoftTtsIsActive) {
                    microsoftTtsRafId = requestAnimationFrame(step);
                } else {
                    microsoftTtsRafId = 0;
                }
            };

            step();
        }

        function registerBrowserSpeechBoundary() {
            const now = performance.now();
            const timeSinceLastBoundary = now - microsoftTtsLastBoundaryTs;
            microsoftTtsLastBoundaryTs = now;
            const amplitudeBoost = Math.min(0.35, 0.15 + (timeSinceLastBoundary / 1000) * 0.08);
            microsoftTtsTargetAmplitude = Math.min(0.85, microsoftTtsTargetAmplitude + amplitudeBoost);
        }

        function stopBrowserSpeechLipSync() {
            isSpeaking = false;
            microsoftTtsIsActive = false;
            if (microsoftTtsRafId) {
                try { cancelAnimationFrame(microsoftTtsRafId); } catch(_) {}
                microsoftTtsRafId = 0;
            }
            if (ttsLipSyncIntervalId) {
                try { clearInterval(ttsLipSyncIntervalId); } catch(_) {}
                ttsLipSyncIntervalId = null;
            }
            if (ttsRafId) {
                try { cancelAnimationFrame(ttsRafId); } catch(_) {}
                ttsRafId = 0;
            }
            try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
            ttsCleanupFns = [];
            resetBrowserSpeechMouthState();
        }

        // Update the textToSpeech function
        function textToSpeech(text, { preserveThinkingPose = false } = {}) {
            if (!text) {
                console.warn('No text provided for speech');
                if (!preserveThinkingPose) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
                return;
            }

            // Check if muted
            if (isMuted) {
                console.log('TTS is muted, skipping speech');
                if (!preserveThinkingPose) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
                return;
            }

            // Sanitize text to remove emojis, bracketed sections, asterisks, and special symbols
            text = sanitizeTTS(text);
            if (!text) {
                if (!preserveThinkingPose) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
                return;
            }
            if (!preserveThinkingPose) {
                markVrmAwaitingTtsStart();
            }
            const browserSpeechSessionId = ++browserSpeechGeneration;

			// Cancel any ongoing speech and active lip-sync loops/graphs
            try { speechSynthesis.cancel(); } catch (_) {}
            try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch (_) {}
            try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch (_) {}
			try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); ttsCleanupFns = []; } catch (_) {}
			try { stopChatterboxLipSync(true); } catch (_) {}
			try { if (ttsAbortController) { ttsAbortController.abort(); ttsAbortController = null; } } catch (_) {}
			// Stop Microsoft TTS lip sync if active
			try { 
				microsoftTtsIsActive = false; // Stop Microsoft TTS lip sync loop
				if (microsoftTtsRafId) { 
					cancelAnimationFrame(microsoftTtsRafId); 
					microsoftTtsRafId = 0; 
				} // Cancel Microsoft TTS RAF
			} catch (_) {}

            // Check TTS service selection - use OpenAI-compatible TTS when selected or when API key is present
            const useOpenAITTS = (ttsServiceOpenAI && ttsServiceOpenAI.checked) || 
                                 (typeof apiKey === 'string' && apiKey.trim().length > 0 && !ttsServiceMicrosoft.checked); // Use OpenAI TTS if OpenAI-compatible is selected or API key is present and Microsoft is not explicitly selected
            
            if (useOpenAITTS) { // If OpenAI-compatible TTS should be used
                speakWithOpenAITTS(text, { preserveThinkingPose }); // Use OpenAI TTS which returns audio bytes we can analyze
                return; // Do not proceed with browser SpeechSynthesis path
            }

            const utterance = new SpeechSynthesisUtterance(text); // Use sanitized text for browser SpeechSynthesis
            const selectedVoiceIndex = parseInt(voiceDropdown.value);
            
            // Ensure we have voices and a valid selection
            if (voices.length > 0 && !isNaN(selectedVoiceIndex) && voices[selectedVoiceIndex]) {
                utterance.voice = voices[selectedVoiceIndex];
                console.log('Using voice:', voices[selectedVoiceIndex].name);
            } else {
                console.warn('No valid voice selected, using default system voice');
            }

            const mouthOpenY = "ParamMouthOpenY"; // Live2D mouth open parameter id
            let headMovementInterval; // Interval id for gentle head movement
            
            utterance.onstart = function() { // When speech begins
                if (browserSpeechSessionId !== browserSpeechGeneration) return;
                console.log('Speech started'); // Log start of speech
                maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
                isSpeaking = true; // Set global speaking flag
                if (live2dModel) { // If Live2D model is active
                    headMovementInterval = setInterval(() => { // Start periodic head movement
                        animateHeadMovement(live2dModel, 1000); // Trigger head animation routine
                    }, 3000); // Run every 3 seconds
                } // End Live2D head movement setup

                microsoftTtsLastBoundaryTs = performance.now(); // Initialize boundary timestamp
                
                // Start smooth amplitude-based lip sync (same approach as Chatterbox)
                startBrowserSpeechLipSyncLoop(); // Start smooth lip sync loop

                // Kick mouth slightly open at start so it does not appear stuck
                if (vrmModel && document.getElementById('vrm-mode').checked) { // If VRM active
                    animateVRMLipSync(0.8); // Open mouth initially
                } // End VRM initial kick
            }; // End onstart handler

            utterance.onboundary = function(event) { // Called on word or sentence boundaries
                if (browserSpeechSessionId !== browserSpeechGeneration) return;
                registerBrowserSpeechBoundary();
            }; // End onboundary handler

            utterance.onend = function() { // When speech ends
                if (browserSpeechSessionId !== browserSpeechGeneration) return;
                console.log('Speech ended'); // Log end of speech
                if (headMovementInterval) { // If head movement was running
                    clearInterval(headMovementInterval); // Stop head movement interval
                } // End head movement cleanup
                stopBrowserSpeechLipSync();

                if (live2dModel) { // If Live2D active
                    live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, 0); // Ensure mouth is closed
                    animateHeadMovement(live2dModel, 1000).then(() => { // Run gentle head settle animation
                        live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleX', 0); // Reset X angle
                        live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleY', 0); // Reset Y angle
                        live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleZ', 0); // Reset Z angle
                    }); // End settle sequence
                } // End Live2D reset

                // VRM lip sync end animation
                if (vrmModel && document.getElementById('vrm-mode').checked) { // If VRM active
                    animateVRMLipSync(0.0); // Ensure mouth returns closed at end
                } // End VRM reset
            }; // End onend handler

            utterance.onerror = function(event) {
                if (browserSpeechSessionId !== browserSpeechGeneration) return;
                console.error('Speech synthesis error:', event);
                if (headMovementInterval) {
                    clearInterval(headMovementInterval);
                }
                stopBrowserSpeechLipSync();
            };

            utterance.rate = 1.0;
            utterance.pitch = 1.0;

            try {
            speechSynthesis.speak(utterance);
            } catch (error) {
                console.error('Speech synthesis error:', error);
                if (!preserveThinkingPose) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
            }
        }

        // Robust SSE reader that handles keep-alives, multi-line data, CRLF
        async function streamSSE(response, { onInit, onDelta, onDone, onError, onInfo }) { // Function to parse Server-Sent Events stream
            const reader = response.body.getReader(); // Get stream reader
            const decoder = new TextDecoder(); // Create text decoder that tolerates chunk splits
            let buf = ''; // Buffer for incomplete SSE events
            
            try { // Guard SSE parsing
                while (true) { // Loop until stream ends
                    const { value, done } = await reader.read(); // Read next chunk
                    if (done) break; // Exit when stream completes
                    buf += decoder.decode(value, { stream: true }); // Decode partial chunk and add to buffer
                    
                    // SSE events end with a blank line (\n\n)
                    let idx; // Index of double newline
                    while ((idx = buf.indexOf('\n\n')) !== -1) { // Find complete SSE event
                        const rawEvent = buf.slice(0, idx); // Extract complete event
                        buf = buf.slice(idx + 2); // Remove processed event from buffer
                        
                        // Ignore comments/heartbeats starting with ":" lines
                        const lines = rawEvent.split(/\r?\n/).filter(l => !l.startsWith(':')); // Split by newline and filter comments
                        
                        // Concatenate multiple data: lines (valid SSE format)
                        let eventName = null; // Event type from event: line
                        const dataParts = []; // Array to collect data: lines
                        for (const line of lines) { // Process each line of the event
                            if (line.startsWith('event:')) { // Check for event type declaration
                                eventName = line.slice(6).trim(); // Extract event name
                            } else if (line.startsWith('data:')) { // Check for data line
                                dataParts.push(line.slice(5).trim()); // Extract data (remove 'data:' prefix)
                            } // End data line check
                        } // End line processing loop
                        
                        if (dataParts.length === 0) continue; // Skip events with no data
                        const dataStr = dataParts.join('\n'); // Join multiple data lines
                        if (dataStr === '[DONE]') { // Check for OpenAI-style completion
                            onDone?.(); // Call completion handler
                            return; // Exit parser
                        } // End [DONE] check
                        
                        // Expect JSON object per Chatterbox docs
                        let evt; // Parsed event object
                        try { // Guard JSON parsing
                            evt = JSON.parse(dataStr); // Parse JSON from data string
                        } catch { // Catch JSON parse errors
                            continue; // Skip invalid JSON events
                        } // End JSON parse try/catch
                        
                        // OpenAI-compatible naming from Chatterbox docs:
                        //   speech.audio.info   (metadata: sample_rate, channels, bits_per_sample)
                        //   speech.audio.init   (base64 WebM init segment)
                        //   speech.audio.delta  (base64 in evt.audio)
                        //   speech.audio.done
                        // Log all event types for debugging
                        console.log('🎵 SSE event received, type:', evt?.type, 'has audio:', !!evt?.audio); // Debug log
                        
                        if (evt?.type === 'speech.audio.info') { // Check for metadata/info event
                            console.log('🎵 Received audio info:', evt); // Log metadata (sample_rate, channels, etc.)
                            onInfo?.(evt); // Pass metadata (sample_rate, channels, etc.) to handler
                        } else if (evt?.type === 'speech.audio.init' && evt?.audio) { // Check for init segment event
                            console.log('🎵 Received init event, size:', evt.audio.length); // Log init event
                            onInit?.(evt.audio); // Pass base64 init segment to handler
                        } else if (evt?.type === 'speech.audio.delta' && evt?.audio) { // Check for audio delta event
                            onDelta?.(evt.audio); // Pass base64 string to handler
                        } else if (evt?.type === 'speech.audio.done') { // Check for completion event
                            console.log('🎵 Received done event'); // Log completion
                            onDone?.(evt.usage); // Call completion handler with usage info
                            return; // Exit parser
                        } else { // Unknown event type
                            console.warn('🎵 Unknown SSE event type:', evt?.type, 'Full event:', evt); // Log unknown event
                        } // End event type check
                    } // End event parsing loop
                } // End stream reading loop
                onDone?.(); // Call completion handler when stream ends
            } catch (e) { // Catch SSE parsing errors
                onError?.(e); // Call error handler
            } // End try/catch
        } // End streamSSE
        
        // MSE appender for WebM/Opus (or MP3)
        function makeMSEPlayer(mimeType = 'audio/webm;codecs=opus') { // Function to create MediaSource player
            if (!window.MediaSource || !MediaSource.isTypeSupported(mimeType)) { // Check if MSE is supported
                return null; // Return null if unsupported (caller will fall back to blob/AudioContext path)
            } // End MSE support check
            
            const audio = new Audio(); // Create audio element
            const mediaSource = new MediaSource(); // Create MediaSource for streaming
            audio.src = URL.createObjectURL(mediaSource); // Set source to object URL
            audio.preload = 'auto'; // Enable preload
            audio.crossOrigin = 'anonymous'; // Allow WebAudio connection
            
            let sourceBuffer; // SourceBuffer for appending chunks
            let initAppended = false; // Track if init segment has been appended
            let started = false; // Track if playback has started
            
            mediaSource.addEventListener('sourceopen', () => { // When MediaSource opens
                sourceBuffer = mediaSource.addSourceBuffer(mimeType); // Create source buffer with specified MIME type
                sourceBuffer.mode = 'sequence'; // Set mode to prevent timestamp gaps
            }); // End sourceopen handler
            
            // Function to append init segment (must be called first)
            const appendInit = (u8) => { // Function to append initialization segment
                return new Promise((resolve) => { // Return promise that resolves when init is appended
                    const doAppend = () => { // Inner function to perform append
                        if (!sourceBuffer) { // If source buffer not yet created
                            setTimeout(doAppend, 10); // Wait a bit and retry
                            return; // Exit function
                        } // End sourceBuffer check
                        
                        if (sourceBuffer.updating) { // If buffer is currently updating
                            sourceBuffer.addEventListener('updateend', doAppend, { once: true }); // Wait for update to complete
                            return; // Exit function
                        } // End updating check
                        
                        try { // Guard append operation
                            sourceBuffer.appendBuffer(u8); // Append init segment to buffer
                            console.log('🎵 Init segment appended, size:', u8.length); // Log init append
                            initAppended = true; // Mark init as appended
                            // Wait for append to complete before resolving
                            sourceBuffer.addEventListener('updateend', () => { // When append completes
                                console.log('🎵 Init segment append complete'); // Log completion
                                resolve(); // Resolve promise to signal init is ready
                            }, { once: true }); // One-time listener
                        } catch (e) { // Catch append errors
                            console.warn('Init append error, will retry:', e); // Log warning
                            setTimeout(doAppend, 10); // Retry append after short delay
                        } // End append try/catch
                    }; // End doAppend function
                    
                    doAppend(); // Start append process
                }); // End Promise constructor
            }; // End appendInit function
            
            // Function to append delta chunks (audio frames)
            const append = (u8) => { // Function to append audio chunk
                const doAppend = () => { // Inner function to perform append
                    if (!sourceBuffer) { // If source buffer not yet created
                        setTimeout(doAppend, 10); // Wait a bit and retry
                        return; // Exit function
                    } // End sourceBuffer check
                    
                    if (!initAppended) { // If init hasn't been appended yet
                        console.warn('⚠️ Attempted to append delta before init segment, waiting...'); // Log warning
                        setTimeout(doAppend, 10); // Wait and retry
                        return; // Exit function
                    } // End init check
                    
                    if (sourceBuffer.updating) { // If buffer is currently updating
                        sourceBuffer.addEventListener('updateend', doAppend, { once: true }); // Wait for update to complete
                        return; // Exit function
                    } // End updating check
                    
                    try { // Guard append operation
                        sourceBuffer.appendBuffer(u8); // Append chunk to buffer
                        
                        // Start playback after first delta chunk (init + first delta = ready)
                        if (!started && initAppended) { // If playback hasn't started and init is ready
                            started = true; // Mark as started
                            sourceBuffer.addEventListener('updateend', () => { // When buffer update completes
                                audio.play().then(() => { // Start audio playback
                                    console.log('🎵 Audio playback started (MSE)'); // Log playback start
                                    handleVrmTtsPlaybackStarted();
                                    startLipSyncFromAudioElement(audio); // Hook up lip sync
                                }).catch((e) => { // Catch play errors
                                    console.warn('Audio play error (may be autoplay restriction):', e); // Log warning
                                }); // End play promise chain
                            }, { once: true }); // One-time listener
                        } // End playback start check
                    } catch (e) { // Catch append errors
                        console.warn('Append error, will retry:', e); // Log warning
                        setTimeout(doAppend, 10); // Retry append after short delay
                    } // End append try/catch
                }; // End doAppend function
                
                doAppend(); // Start append process
            }; // End append function
            
            const end = () => { // Function to end stream
                try { // Guard endOfStream call
                    if (mediaSource.readyState === 'open') { // Check if source is still open
                        mediaSource.endOfStream(); // Signal end of stream
                    } // End readyState check
                } catch {} // Ignore errors
            }; // End end function
            
            // Handle cleanup when audio ends
            audio.addEventListener('ended', () => { // When playback finishes
                URL.revokeObjectURL(audio.src); // Release object URL
                // Cleanup MediaSource
                try { if (mediaSource.readyState === 'open') mediaSource.endOfStream(); } catch(_){}
                // Cleanup lip sync intervals
                try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                ttsCleanupFns = []; // Clear cleanup functions
                // Reset avatar mouth
                if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
            }); // End ended handler
            
            // Register cleanup for external cancellations
            ttsCleanupFns.push(() => {
                try { audio.pause(); } catch(_){}
                try { if (mediaSource.readyState === 'open') mediaSource.endOfStream(); } catch(_){}
                try { mediaSource.removeEventListener('error', () => {}); } catch(_){}
                try { URL.revokeObjectURL(audio.src); } catch(_){}
            }); // End cleanup registration
            
            return { audio, appendInit, append, end }; // Return player interface with init handler
        } // End makeMSEPlayer
        
        // Minimal MSE player (WebM/Opus) for SSE init/delta
        function createWebMOpusMSE() { // Function to create MediaSource player for WebM/Opus streaming
            if (!('MediaSource' in window)) return null; // Return null if MediaSource is not supported
            
            const audio = new Audio(); // Create audio element for playback
            audio.preload = 'auto'; // Enable preload
            audio.crossOrigin = 'anonymous'; // Allow CORS for audio analysis (lip sync)
            const ms = new MediaSource(); // Create MediaSource instance
            audio.src = URL.createObjectURL(ms); // Set source to object URL
            
            const q = []; // ArrayBuffers waiting to append
            let sb, started = false, ended = false; // SourceBuffer, playback state, and end flag
            
            const appendNext = () => { // Function to append next chunk from queue
                if (!sb || sb.updating) return; // Exit if no source buffer or already updating
                if (!q.length) { // If queue is empty
                    if (ended && ms.readyState === 'open') ms.endOfStream(); // End stream if done
                    return; // Exit if queue empty
                } // End empty queue check
                sb.appendBuffer(q.shift()); // Append next chunk from queue
            }; // End appendNext function
            
            ms.addEventListener('sourceopen', () => { // When MediaSource opens
                sb = ms.addSourceBuffer('audio/webm;codecs=opus'); // Create source buffer for WebM/Opus
                sb.mode = 'sequence'; // Set mode to sequence for monotonic timestamps
                sb.addEventListener('updateend', appendNext); // Queue next chunk when update completes
            }); // End sourceopen handler
            
            const b64ToU8 = (b64) => { // Helper function to decode base64 to Uint8Array
                const bin = atob(b64); // Decode base64 to binary string
                const u8 = new Uint8Array(bin.length); // Create byte array
                for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); // Convert character code to byte
                return u8; // Return decoded bytes
            }; // End b64ToU8 function
            
            return {
                audio, // Return audio element for external access (lip-sync, etc.)
                appendInit(b64) { // Function to append init segment
                    q.push(b64ToU8(b64).buffer); // Decode and add init segment to queue
                    appendNext(); // Try to append if source buffer is ready
                    if (!started) { // If playback hasn't started
                        started = true; // Mark as started
                        audio.play().catch(() => { // Start audio playback
                            console.warn('Autoplay blocked — start after user gesture.'); // Log autoplay block warning
                        }); // End play promise catch
                    } // End started check
                }, // End appendInit method
                appendDelta(b64) { // Function to append delta chunks
                    q.push(b64ToU8(b64).buffer); // Decode and add chunk to queue
                    appendNext(); // Try to append if source buffer is ready
                }, // End appendDelta method
                end() { // Function to end stream
                    ended = true; // Mark stream as ended
                    appendNext(); // Final append attempt
                } // End end method
            }; // End return object
        } // End createWebMOpusMSE
        
        function ensureChatterboxLipSyncGraph() { // Ensure analyser graph exists for PCM16 playback
            if (!window.__opus) { window.__opus = {}; } // Initialize opus container if missing
            let ctx = window.__opus.audioCtx; // Reuse existing audio context when available
            if (!ctx) { // Create context if we do not already have one
                ctx = new (window.AudioContext || window.webkitAudioContext)(); // Create audio context
                window.__opus.audioCtx = ctx; // Persist context for reuse
                window.__opus.playhead = 0; // Initialize playhead tracking
            }

            if (!ttsAnalyserNode || ttsAnalyserNode.context !== ctx) { // Rebuild analyser chain when context changes
                try { if (ttsAnalyserNode) ttsAnalyserNode.disconnect(); } catch (_) {} // Detach old analyser if present
                try { if (ttsAnalyserGainNode) ttsAnalyserGainNode.disconnect(); } catch (_) {} // Detach old gain node
                ttsAnalyserNode = ctx.createAnalyser(); // Create analyser node for amplitude tracking
                ttsAnalyserNode.fftSize = 1024; // Match analyser resolution with audio-element path
                ttsAnalyserNode.smoothingTimeConstant = 0.7; // Apply smoothing to reduce jitter
                ttsAnalyserGainNode = ctx.createGain(); // Gain node to feed analyser output to speakers
                ttsAnalyserGainNode.gain.value = 1.0; // Unity gain to preserve original volume
                ttsAnalyserNode.connect(ttsAnalyserGainNode); // Route analyser output through gain
                ttsAnalyserGainNode.connect(ctx.destination); // Connect gain to destination so audio is audible
            }

            if (!ttsAnalyserDataArray || ttsAnalyserDataArray.length !== ttsAnalyserNode.fftSize) { // Ensure buffer matches analyser size
                ttsAnalyserDataArray = new Uint8Array(ttsAnalyserNode.fftSize); // Allocate reusable buffer
            }

            if (ttsAnalyserStopTimer) { // Clear pending stop timers when new audio is starting
                clearTimeout(ttsAnalyserStopTimer);
                ttsAnalyserStopTimer = null;
            }

            return window.__opus.audioCtx; // Return prepared audio context
        } // End ensureChatterboxLipSyncGraph

        function startLipSyncFromAnalyserNode() { // Start analyser-driven lip sync loop
            try {
                if (!ttsAnalyserNode) return; // Guard when analyser is unavailable

                if (!ttsAnalyserDataArray || ttsAnalyserDataArray.length !== ttsAnalyserNode.fftSize) { // Ensure buffer exists
                    ttsAnalyserDataArray = new Uint8Array(ttsAnalyserNode.fftSize); // Allocate buffer for analyser samples
                }

                if (ttsAnalyserLoopActive) return; // Avoid spawning duplicate RAF loops

                let smoothed = 0; // Smoothed RMS envelope
                const attack = 0.6; // Attack coefficient for rising amplitude
                const release = 0.15; // Release coefficient for falling amplitude
                const threshold = 0.03; // Minimum RMS required before opening the mouth

                const step = () => { // Per-frame analyser sampling callback
                    if (!ttsAnalyserNode) { // Abort if analyser was disposed
                        ttsAnalyserLoopActive = false;
                        ttsRafId = 0;
                        return;
                    }

                    ttsAnalyserNode.getByteTimeDomainData(ttsAnalyserDataArray); // Sample current waveform
                    let sum = 0; // Accumulator for RMS energy
                    for (let i = 0; i < ttsAnalyserDataArray.length; i++) { // Iterate over analyser buffer
                        const v = (ttsAnalyserDataArray[i] - 128) / 128; // Convert byte sample to [-1, 1]
                        sum += v * v; // Accumulate squared amplitude
                    }

                    const rms = Math.sqrt(sum / ttsAnalyserDataArray.length); // Compute RMS amplitude
                    if (rms > smoothed) { // Attack branch
                        smoothed += (rms - smoothed) * attack;
                    } else { // Release branch
                        smoothed += (rms - smoothed) * release;
                    }

                    const scaled = smoothed <= threshold ? 0 : Math.min(1, (smoothed - threshold) * 6.0); // Map to [0,1]

                    if (live2dModel) { // Apply to Live2D mouth
                        live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', scaled);
                    }

                    const vrmModeToggle = document.getElementById('vrm-mode'); // Cache VRM toggle reference
                    if (vrmModel && vrmModeToggle && vrmModeToggle.checked) { // Apply to VRM mouth when active
                        animateVRMLipSync(scaled);
                    }

                    if (ttsStreamActive || ttsPcmActiveSources > 0 || smoothed > 0.0005) { // Keep looping while audio is active
                        ttsRafId = requestAnimationFrame(step);
                    } else { // Otherwise stop and reset mouth
                        ttsRafId = 0;
                        ttsAnalyserLoopActive = false;
                        if (live2dModel) {
                            live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
                        }
                        if (vrmModel && vrmModeToggle && vrmModeToggle.checked) {
                            animateVRMLipSync(0);
                        }
                    }
                }; // End step function

                ttsAnalyserLoopActive = true; // Mark loop active so we do not start duplicates
                step(); // Kick off analyser sampling immediately
            } catch (e) {
                console.warn('startLipSyncFromAnalyserNode failed:', e); // Log analyser errors but do not crash
            }
        } // End startLipSyncFromAnalyserNode

        function stopChatterboxLipSync(immediate = false) { // Stop analyser-based lip sync with optional delay
            if (immediate) {
                ttsStreamActive = false; // Clear stream-active flag immediately
                ttsPcmActiveSources = 0; // Reset active source count
				try { if (window.__opus && typeof window.__opus.playhead !== 'undefined') { window.__opus.playhead = 0; } } catch(_) {}
                if (ttsAnalyserStopTimer) { // Clear pending delayed stops
                    clearTimeout(ttsAnalyserStopTimer);
                    ttsAnalyserStopTimer = null;
                }
                if (ttsRafId) { // Cancel any pending animation frame
                    try { cancelAnimationFrame(ttsRafId); } catch (_) {}
                    ttsRafId = 0;
                }
                ttsAnalyserLoopActive = false; // Mark loop inactive
                if (live2dModel) { // Close Live2D mouth
                    live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
                }
                const vrmModeToggle = document.getElementById('vrm-mode');
                if (vrmModel && vrmModeToggle && vrmModeToggle.checked) { // Close VRM mouth
                    animateVRMLipSync(0);
                }
                return; // Exit after immediate cleanup
            }

            if (ttsAnalyserStopTimer) { // Clear existing timer before scheduling new one
                clearTimeout(ttsAnalyserStopTimer);
            }

            ttsAnalyserStopTimer = setTimeout(() => { // Delay cleanup slightly to allow tail audio to finish
                if (ttsStreamActive || ttsPcmActiveSources > 0) { // Abort if audio resumed
                    return;
                }
                stopChatterboxLipSync(true); // Otherwise perform immediate cleanup
            }, 250);
        } // End stopChatterboxLipSync

        // Play PCM16 delta chunk using Web Audio API (mirrors existing schedule pattern)
        function playPcm16Delta(base64, sampleRate = 24000, channels = 1, { preserveThinkingPose = false } = {}) { // Function to decode and play PCM16 audio chunk
            const bin = atob(base64); // Decode base64 to binary string
            const totalSamples = bin.length / 2; // Calculate total number of int16 samples across all channels (2 bytes/sample)
            if (!Number.isFinite(totalSamples) || totalSamples <= 0) {
                console.warn('⚠️ Received empty PCM16 chunk');
                return;
            }

            const i16 = new Int16Array(totalSamples); // Create Int16Array for signed 16-bit samples
            
            // Convert little-endian bytes to int16 samples
            for (let i = 0, o = 0; i < totalSamples; i++, o += 2) { // Loop through samples (2 bytes each)
                // little-endian 16-bit signed conversion
                i16[i] = (bin.charCodeAt(o) | (bin.charCodeAt(o + 1) << 8)); // Combine bytes (little-endian)
            } // End byte conversion loop

            // Convert Int16 to Float32 [-1, 1] range
            const f32 = new Float32Array(totalSamples); // Create Float32Array for normalized samples
            for (let i = 0; i < totalSamples; i++) { // Loop through samples
                f32[i] = Math.max(-1, Math.min(1, i16[i] / 32768)); // Normalize to [-1, 1] range and clamp
            } // End normalization loop

            // Reuse existing AudioContext and playhead scheduling pattern
            const ctx = ensureChatterboxLipSyncGraph(); // Prepare shared audio context and analyser chain
            if (ctx.state === 'suspended') { // Resume context if autoplay policies suspended it
                try { ctx.resume(); } catch (_) {} // Ignore resume errors (will resume on user gesture)
            }

            const safeChannels = Math.max(1, channels | 0); // Ensure channel count is a positive integer
            const framesPerChannel = Math.floor(totalSamples / safeChannels); // Sample frames available for each channel
            if (framesPerChannel <= 0) {
                console.warn('⚠️ PCM16 chunk shorter than declared channel count, skipping playback');
                return;
            }
            const trailingSamples = totalSamples - framesPerChannel * safeChannels;
            if (trailingSamples !== 0) {
                console.warn('⚠️ Dropping', trailingSamples, 'sample(s) that do not fit evenly across', safeChannels, 'channels');
            }
            const buf = ctx.createBuffer(safeChannels, framesPerChannel, sampleRate); // Create audio buffer with specified channels, length, and sample rate

            // Set channel data from decoded PCM
            if (safeChannels === 1) { // If mono channel
                const channelData = buf.getChannelData(0);
                channelData.set(f32.subarray(0, framesPerChannel)); // Set single channel data
            } else { // If multi-channel (stereo or more)
                // Split interleaved samples into channel arrays
                for (let ch = 0; ch < safeChannels; ch++) { // Loop through each channel
                    const channelData = buf.getChannelData(ch); // Reference channel buffer directly
                    for (let i = 0; i < framesPerChannel; i++) { // Loop through samples in channel
                        channelData[i] = f32[i * safeChannels + ch]; // Extract interleaved sample for this channel
                    } // End sample extraction loop
                } // End channel loop
            } // End channel data assignment

            // Create and schedule audio source (same pattern as existing schedule function)
            const src = ctx.createBufferSource(); // Create buffer source node
            src.buffer = buf; // Set decoded buffer
            const playback = connectScheduledPcmSource(ctx, src, buf.duration);

            ttsPcmActiveSources += 1; // Track active sources so we know when playback has finished
            const handleEnded = () => { // Cleanup when buffer playback completes
                if (src) {
                    try { src.removeEventListener('ended', handleEnded); } catch (_) {}
                }
                if (ttsPcmActiveSources > 0) {
                    ttsPcmActiveSources -= 1;
                }
                if (ttsPcmActiveSources === 0) { // Schedule mouth close once final buffer finishes
                    stopChatterboxLipSync(false);
                }
            };
			src.addEventListener('ended', handleEnded, { once: true }); // Ensure cleanup runs only once

			// Ensure we can immediately stop scheduled sources on interruption
			ttsCleanupFns.push(() => {
				try { src.removeEventListener('ended', handleEnded); } catch(_) {}
				try { src.stop(0); } catch(_) {}
				try { src.disconnect(); } catch(_) {}
				try { playback.gainNode.disconnect(); } catch(_) {}
			});

            src.start(playback.startTime); // Schedule playback without chunk overlap
            maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
            window.__opus.playhead = playback.startTime + buf.duration;
            
            console.log('🔊 Scheduled PCM16 chunk:', framesPerChannel, 'frames per channel (', totalSamples, 'total samples ),', sampleRate, 'Hz,', safeChannels, 'channels, duration:', buf.duration.toFixed(3), 's'); // Log playback info
        } // End playPcm16Delta

        const PCM16_CHUNK_EDGE_FADE_SECONDS = 0.002;

        function connectScheduledPcmSource(ctx, src, durationSeconds) {
            const gainNode = ctx.createGain();
            const startTime = Math.max(ctx.currentTime, window.__opus.playhead || 0);
            const fadeSeconds = Math.min(
                PCM16_CHUNK_EDGE_FADE_SECONDS,
                Math.max(0.0005, durationSeconds / 16)
            );
            const fadeOutStart = Math.max(startTime + fadeSeconds, startTime + durationSeconds - fadeSeconds);

            gainNode.gain.cancelScheduledValues(startTime);
            gainNode.gain.setValueAtTime(0, startTime);
            gainNode.gain.linearRampToValueAtTime(1, startTime + fadeSeconds);
            gainNode.gain.setValueAtTime(1, fadeOutStart);
            gainNode.gain.linearRampToValueAtTime(0, startTime + durationSeconds);

            src.connect(gainNode);
            if (ttsAnalyserNode) gainNode.connect(ttsAnalyserNode);
            else gainNode.connect(ctx.destination);

            return { gainNode, startTime };
        }

        // Play raw PCM16 bytes (little-endian) using the same scheduler as playPcm16Delta
        function playPcm16Bytes(u8, sampleRate = 24000, channels = 1, { preserveThinkingPose = false } = {}) {
            if (!(u8 instanceof Uint8Array) || u8.length < 2) {
                return;
            }
            const sampleCount = Math.floor(u8.length / 2);
            if (sampleCount <= 0) return;
            const i16 = new Int16Array(sampleCount);
            for (let i = 0, o = 0; i < sampleCount; i++, o += 2) {
                const lo = u8[o];
                const hi = u8[o + 1];
                const val = (hi << 8) | lo;
                i16[i] = (val & 0x8000) ? (val - 0x10000) : val;
            }
            const f32 = new Float32Array(sampleCount);
            for (let i = 0; i < sampleCount; i++) {
                f32[i] = Math.max(-1, Math.min(1, i16[i] / 32768));
            }

            const ctx = ensureChatterboxLipSyncGraph();
            if (ctx.state === 'suspended') {
                try { ctx.resume(); } catch (_) {}
            }

            const safeChannels = Math.max(1, channels | 0);
            const framesPerChannel = Math.floor(sampleCount / safeChannels);
            if (framesPerChannel <= 0) return;
            const buf = ctx.createBuffer(safeChannels, framesPerChannel, sampleRate);
            if (safeChannels === 1) {
                buf.getChannelData(0).set(f32.subarray(0, framesPerChannel));
            } else {
                for (let ch = 0; ch < safeChannels; ch++) {
                    const channelData = buf.getChannelData(ch);
                    for (let i = 0; i < framesPerChannel; i++) {
                        channelData[i] = f32[i * safeChannels + ch];
                    }
                }
            }

            const src = ctx.createBufferSource();
            src.buffer = buf;
            const playback = connectScheduledPcmSource(ctx, src, buf.duration);

            ttsPcmActiveSources += 1;
            const handleEnded = () => {
                try { src.removeEventListener('ended', handleEnded); } catch (_) {}
                if (ttsPcmActiveSources > 0) ttsPcmActiveSources -= 1;
                if (ttsPcmActiveSources === 0) stopChatterboxLipSync(false);
            };
            src.addEventListener('ended', handleEnded, { once: true });
            ttsCleanupFns.push(() => {
                try { src.removeEventListener('ended', handleEnded); } catch (_) {}
                try { src.stop(0); } catch (_) {}
                try { src.disconnect(); } catch (_) {}
                try { playback.gainNode.disconnect(); } catch (_) {}
            });
            src.start(playback.startTime);
            maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
            window.__opus.playhead = playback.startTime + buf.duration;
        }
        
        // Speak using Chatterbox TTS endpoint with streaming PCM16 decoding
		async function speakWithOpenAITTS(text, { preserveThinkingPose = false } = {}) { // Asynchronous function to fetch and play TTS audio via Chatterbox
            // Declare localGen and localController outside try block so they're accessible in catch block
            let localGen = 0; // Generation token for this TTS request (initialized before try block)
            let localController = null; // Local reference to this request's abort controller
            try { // Begin error handling scope
                if (!text) return; // Guard for missing input
                
                // Sanitize text before sending to TTS API (remove emojis/brackets/asterisks/specials)
                text = sanitizeTTS(text);
                const isSuperseded = () => localGen > 0 && localGen !== ttsGeneration;
                const isIntentionalAbort = (error = null) => {
                    if (error && (error.name === 'AbortError' || error.message?.includes('aborted'))) {
                        return true;
                    }
                    return !!(localController && localController.signal.aborted);
                };
                const shouldSkipFallback = (error = null) => isSuperseded() || isIntentionalAbort(error);
                const runBrowserTtsFallback = (error = null) => {
                    if (shouldSkipFallback(error)) {
                        console.log('Skipping browser TTS fallback for cancelled or superseded request');
                        return false;
                    }
                    textToSpeechFallback(text, { preserveThinkingPose });
                    return true;
                };
                
                // Get TTS settings from UI elements - require Chatterbox endpoint
                if (!ttsEndpointInput || !ttsEndpointInput.value || !ttsEndpointInput.value.trim()) { // Check if endpoint is configured
                    console.error('❌ Chatterbox TTS endpoint not configured'); // Log error
                    runBrowserTtsFallback(); // Fall back to browser TTS
                    return; // Exit early
                } // End endpoint check
                
                // Get TTS endpoint base URL and extract origin for proxy
                const ttsEndpointBase = ttsEndpointInput.value.trim().replace(/\/$/, '');
                let baseUrl;
                try {
                    // Parse the endpoint URL to extract the origin (protocol + host + port)
                    const endpointUrl = new URL(ttsEndpointBase);
                    baseUrl = endpointUrl.origin; // Gets protocol + host + port, without any path
                } catch (e) {
                    // Fallback to simple string replacement if URL parsing fails
                    const match = ttsEndpointBase.match(/^(https?:\/\/[^\/]+)/);
                    baseUrl = match ? match[1] : ttsEndpointBase.replace(/\/v1$/, '');
                }
                
                // Use proxy endpoint to handle CORS.
                const endpoint = `${PROXY_BASE_URL}/v1/proxy/tts/speech?endpoint=${encodeURIComponent(baseUrl)}`; // Use proxy endpoint for TTS speech
                const modelId = (ttsModelDropdown && ttsModelDropdown.value) ? ttsModelDropdown.value : 'tts-1'; // Get model from dropdown or default
                const voiceId = (ttsVoiceDropdown && ttsVoiceDropdown.value) ? ttsVoiceDropdown.value : 'alloy'; // Get voice from dropdown or default

                const reqBody = { // Build request payload for OpenAI-compatible binary audio
                    model: modelId, // TTS model (optional for Chatterbox)
                    voice: voiceId, // Voice preset
                    input: text, // The text to speak (emojis already removed)
                    stream: false // Request a single binary audio response for broad browser compatibility
                }; // End payload

                // Prefer PCM streaming for local/self-hosted TTS endpoints to reduce time-to-first-audio.
                // Keep remote/unknown providers on binary MP3 defaults for compatibility.
                const shouldPreferPcmStreaming = (() => {
                    if (isIOSDevice) return true;
                    try {
                        const host = (new URL(baseUrl)).hostname.toLowerCase();
                        const pageHost = (window.location.hostname || '').toLowerCase();
                        const isLoopback = host === 'localhost' || host === '127.0.0.1' || host === '::1';
                        const isLocalDomain = host.endsWith('.local');
                        const sameHost = !!pageHost && host === pageHost;
                        const hasWebAudio = !!(window.AudioContext || window.webkitAudioContext);
                        return hasWebAudio && (isLoopback || isLocalDomain || sameHost);
                    } catch (_) {
                        return false;
                    }
                })();

                if (shouldPreferPcmStreaming) {
                    reqBody.response_format = 'pcm';
                    reqBody.sample_rate = 24000; // honored by some servers; ignored by others
                    reqBody.stream = true;
                }

                // Request binary audio by default; response parser still supports SSE when returned.
                const wantsPcmResponse = reqBody.response_format === 'pcm';
                const headers = {
                    'Content-Type': 'application/json', // JSON body content type
                    'Accept': wantsPcmResponse
                        ? 'audio/pcm, application/octet-stream, audio/wav;q=0.9, audio/mpeg;q=0.7'
                        : 'audio/mpeg'
                }; // End headers

				// Prepare abort + generation token so interruptions cancel immediately and stale callbacks are ignored
				try { if (ttsAbortController) { ttsAbortController.abort(); } } catch (_) {}
				localController = new AbortController(); // Create controller for this specific request
				ttsAbortController = localController; // Store in global variable
				localGen = (++ttsGeneration); // Assign generation token for this request

				// Request TTS audio through proxy using a browser-compatible contract.
				const res = await fetch(endpoint, { // Issue HTTP request for speech through proxy
                    method: 'POST', // Use POST method per API spec
                    headers: headers, // Set request headers
					body: JSON.stringify(reqBody), // Attach serialized JSON body
					signal: localController.signal // Allow immediate cancellation on interrupt (use local reference)
                }); // End fetch

                // Check if request was aborted before processing response (check local controller first)
                if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) {
                    console.log('🛑 Chatterbox TTS request cancelled before response, skipping fallback'); // Log cancellation
                    stopChatterboxLipSync(true); // Immediately stop lip sync
                    return; // Exit without fallback
                }
                
                if (!res.ok) { // If response indicates failure
                    const errText = await res.text().catch(() => ''); // Attempt to read error body
                    console.error('❌ Chatterbox TTS error:', res.status, errText); // Log details for diagnostics
                    // Fallback to browser speech if available
                    stopChatterboxLipSync(true); // Ensure any analyser-driven lip sync is reset
                    runBrowserTtsFallback(); // Use backup speaker for continuity
                    return; // Exit early
                } // End error response branch
                
                // Detect response format: SSE (Chatterbox/PCM) or binary audio (VibeVoice/OpenAI-compatible)
                const ct = (res.headers.get('content-type') || '').toLowerCase(); // Get content type from headers
                const isSSE = ct.includes('text/event-stream'); // Check if response is SSE format (Chatterbox)
                const isBinaryAudio = ct.includes('audio/') || ct.includes('application/octet-stream'); // Check if response is binary audio (VibeVoice/OpenAI-compatible)
                
                // Check if request was aborted before processing format (check local controller first)
                if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) {
                    console.log('🛑 TTS request cancelled during format check, skipping fallback'); // Log cancellation
                    stopChatterboxLipSync(true); // Immediately stop lip sync
                    return; // Exit without fallback
                }
                
                // Handle binary audio format (VibeVoice/OpenAI-compatible TTS) with low-latency streaming
                if (!isSSE && isBinaryAudio) { // If binary audio format (not SSE)
                    console.log('📦 Received binary audio format:', ct, '- streaming for low latency'); // Log format detection
                    stopChatterboxLipSync(true); // Reset lip sync state
                    
                    // Handle binary audio response (MP3, WAV, etc. from OpenAI-compatible TTS) with streaming
                    try {
                        // Determine MIME type from content-type header
                        let mimeType = 'audio/mpeg'; // Default to MP3
                        if (ct.includes('audio/pcm') || ct.includes('audio/l16')) {
                            mimeType = 'audio/pcm';
                        } else if (ct.includes('audio/wav') || ct.includes('audio/wave')) {
                            mimeType = 'audio/wav';
                        } else if (ct.includes('audio/webm')) {
                            mimeType = 'audio/webm';
                        } else if (ct.includes('audio/ogg')) {
                            mimeType = 'audio/ogg';
                        } else if (ct.includes('audio/mp4') || ct.includes('audio/m4a')) {
                            mimeType = 'audio/mp4';
                        } else if (ct.includes('audio/mp3') || ct.includes('audio/mpeg')) {
                            // Normalize MP3 MIME for Safari/iOS compatibility.
                            mimeType = 'audio/mpeg';
                        }
                        
                        // Prefer WebAudio PCM playback on iOS for maximum compatibility and lip sync fidelity.
                        const wantsPcm = reqBody.response_format === 'pcm';
                        const looksLikePcm = mimeType === 'audio/pcm' || ct.includes('octet-stream');
                        if (wantsPcm && looksLikePcm && reqBody.stream && res.body) {
                            console.log('🎵 Using streaming WebAudio PCM16 path');
                            stopChatterboxLipSync(true);
                            const pcmCtx = ensureChatterboxLipSyncGraph();
                            if (pcmCtx.state === 'suspended') {
                                await pcmCtx.resume();
                            }
                            window.__opus.playhead = pcmCtx.currentTime;
                            ttsStreamActive = true;
                            startLipSyncFromAnalyserNode();

                            const channels = Math.max(1, Number(res.headers.get('x-audio-channels') || res.headers.get('x-channels') || reqBody.channels || 1));
                            const sampleRate = Math.max(8000, Number(res.headers.get('x-audio-sample-rate') || res.headers.get('x-sample-rate') || reqBody.sample_rate || 24000));
                            const frameBytes = Math.max(2, channels * 2);
                            let carry = new Uint8Array(0);
                            const reader = res.body.getReader();
                            while (true) {
                                const { value, done } = await reader.read();
                                if (done) break;
                                if (!value || value.length === 0) continue;
                                const joined = new Uint8Array(carry.length + value.length);
                                joined.set(carry, 0);
                                joined.set(value, carry.length);
                                const alignedLen = joined.length - (joined.length % frameBytes);
                                if (alignedLen > 0) {
                                    playPcm16Bytes(joined.subarray(0, alignedLen), sampleRate, channels, { preserveThinkingPose });
                                }
                                carry = joined.subarray(alignedLen);
                            }
                            ttsStreamActive = false;
                            stopChatterboxLipSync(false);
                            return;
                        }

                        if (wantsPcm && looksLikePcm) {
                            console.log('🎵 Using WebAudio PCM16 playback path for iOS compatibility');
                            const pcmBytes = await res.arrayBuffer();
                            const header = new Uint8Array(pcmBytes.slice(0, 4));
                            const looksLikeMp3 = (header[0] === 0x49 && header[1] === 0x44 && header[2] === 0x33) || (header[0] === 0xFF && (header[1] & 0xE0) === 0xE0);
                            if (looksLikeMp3) {
                                console.warn('⚠️ Upstream returned MP3 bytes while PCM was requested; falling back to blob playback');
                                const mp3Blob = new Blob([pcmBytes], { type: 'audio/mpeg' });
                                const audioUrl = URL.createObjectURL(mp3Blob);
                                const audio = new Audio(audioUrl);
                                audio.preload = 'auto';
                                audio.crossOrigin = 'anonymous';
                                audio.onended = () => {
                                    URL.revokeObjectURL(audioUrl);
                                    try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                                    try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                                    try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                                    ttsCleanupFns = [];
                                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                                };
                                startLipSyncFromAudioElement(audio);
                                await audio.play();
                                maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
                                return;
                            }
                            const channels = Math.max(1, Number(res.headers.get('x-audio-channels') || res.headers.get('x-channels') || reqBody.channels || 1));
                            const sampleRate = Math.max(8000, Number(res.headers.get('x-audio-sample-rate') || res.headers.get('x-sample-rate') || reqBody.sample_rate || 24000));
                            const int16 = new Int16Array(pcmBytes);
                            const framesPerChannel = Math.floor(int16.length / channels);
                            if (!framesPerChannel) {
                                throw new Error('PCM response did not include decodable audio frames');
                            }

                            stopChatterboxLipSync(true); // Reset any old state before starting PCM playback
                            const pcmCtx = ensureChatterboxLipSyncGraph();
                            if (pcmCtx.state === 'suspended') {
                                await pcmCtx.resume();
                            }
                            startLipSyncFromAnalyserNode();

                            const audioBuffer = pcmCtx.createBuffer(channels, framesPerChannel, sampleRate);
                            for (let ch = 0; ch < channels; ch++) {
                                const channelData = audioBuffer.getChannelData(ch);
                                for (let i = 0; i < framesPerChannel; i++) {
                                    channelData[i] = int16[(i * channels) + ch] / 32768;
                                }
                            }

                            const src = pcmCtx.createBufferSource();
                            src.buffer = audioBuffer;
                            if (ttsAnalyserNode) {
                                src.connect(ttsAnalyserNode);
                            } else {
                                src.connect(pcmCtx.destination);
                            }

                            ttsPcmActiveSources += 1;
                            const handleEnded = () => {
                                try { src.removeEventListener('ended', handleEnded); } catch (_) {}
                                if (ttsPcmActiveSources > 0) ttsPcmActiveSources -= 1;
                                if (ttsPcmActiveSources === 0) stopChatterboxLipSync(false);
                            };
                            src.addEventListener('ended', handleEnded, { once: true });

                            ttsCleanupFns.push(() => {
                                try { src.removeEventListener('ended', handleEnded); } catch (_) {}
                                try { src.stop(0); } catch (_) {}
                                try { src.disconnect(); } catch (_) {}
                            });

                            src.start();
                            maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
                            console.log('🎵 PCM16 playback started:', sampleRate, 'Hz, channels:', channels, 'frames:', framesPerChannel);
                            return;
                        }

                        // Check if MediaSource supports this format for streaming
                        // Note: MP3 is not well-supported by MediaSource API in most browsers
                        // For MP3, we'll use blob mode instead
                        const useMediaSource = window.MediaSource && 
                                               MediaSource.isTypeSupported(mimeType) && 
                                               !mimeType.includes('mpeg'); // Don't use MediaSource for MP3
                        
                        if (useMediaSource) {
                            // Use MediaSource API for low-latency streaming playback
                            console.log('🎵 Using MediaSource API for low-latency streaming:', mimeType); // Log streaming method
                            
                            // Create audio element and MediaSource
                            const audio = new Audio(); // Create audio element
                            const mediaSource = new MediaSource(); // Create MediaSource for streaming
                            audio.src = URL.createObjectURL(mediaSource); // Set source to object URL
                            audio.preload = 'auto'; // Enable preload
                            audio.crossOrigin = 'anonymous'; // Allow WebAudio connection
                            
                            // Collect audio chunks as they arrive
                            const audioChunks = []; // Array to store audio chunks
                            let sourceBuffer = null; // Source buffer for MediaSource
                            let audioStarted = false; // Track if audio has started playing
                            
                            // Wait for MediaSource to be ready
                            mediaSource.addEventListener('sourceopen', () => { // When MediaSource opens
                                try {
                                    sourceBuffer = mediaSource.addSourceBuffer(mimeType); // Create source buffer
                                    sourceBuffer.mode = 'sequence'; // Set mode to prevent timestamp gaps
                                    
                                    // Function to append chunks as they arrive
                                    const appendChunk = (chunk) => { // Function to append a chunk
                                        if (sourceBuffer && sourceBuffer.updating === false && mediaSource.readyState === 'open') {
                                            try {
                                                sourceBuffer.appendBuffer(chunk); // Append chunk to buffer
                                                
                                                // Start audio playback after first chunk for low latency
                                                if (!audioStarted && audioChunks.length >= 1) {
                                                    audioStarted = true; // Mark as started
                                                    audio.play().then(() => { // When audio starts playing
                                                        console.log('🎵 Audio playback started (streaming, low latency)'); // Log playback start
                                                        // Start lip sync for binary audio path
                                                        maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
                                                        startLipSyncFromAudioElement(audio); // Hook up lip sync to this audio element
                                                    }).catch(e => { // Catch play errors
                                                        console.error('Audio play error:', e); // Log error
                                                    }); // End play promise chain
                                                } // End audio start check
                                            } catch (e) {
                                                console.error('Error appending chunk:', e); // Log error
                                            }
                                        } else {
                                            // Buffer is updating, queue the chunk
                                            if (sourceBuffer) {
                                                sourceBuffer.addEventListener('updateend', () => appendChunk(chunk), { once: true }); // Queue chunk
                                            }
                                        }
                                    }; // End appendChunk function
                                    
                                    // Read response stream and collect chunks
                                    const reader = res.body.getReader(); // Get stream reader
                                    const pump = async () => { // Async function to pump chunks
                                        try {
                                            while (true) { // Loop until stream ends
                                                const { done, value } = await reader.read(); // Read next chunk
                                                if (done) { // If stream is done
                                                    console.log('🎵 Stream complete, ending MediaSource'); // Log completion
                                                    // Wait for buffer to finish updating, then end stream
                                                    if (sourceBuffer && sourceBuffer.updating) {
                                                        sourceBuffer.addEventListener('updateend', () => {
                                                            if (mediaSource.readyState === 'open') {
                                                                mediaSource.endOfStream(); // Signal end of stream
                                                            }
                                                        }, { once: true }); // End stream after last chunk
                                                    } else {
                                                        if (mediaSource.readyState === 'open') {
                                                            mediaSource.endOfStream(); // Signal end of stream
                                                        }
                                                    }
                                                    break; // Exit loop
                                                }
                                                
                                                if (value) { // If chunk has data
                                                    audioChunks.push(value); // Store chunk in array
                                                    appendChunk(value); // Append chunk to MediaSource buffer
                                                }
                                            }
                                        } catch (e) {
                                            console.error('Error in stream pump:', e); // Log error
                                            if (mediaSource.readyState === 'open') {
                                                mediaSource.endOfStream(); // Signal end on error
                                            }
                                        }
                                    }; // End pump function
                                    
                                    pump(); // Start pumping chunks
                                } catch (e) {
                                    console.error('MediaSource setup error:', e); // Log error
                                    mediaSource.endOfStream(); // Signal end on error
                                }
                            }); // End sourceopen event
                            
                            // Handle cleanup when audio ends
                            audio.onended = () => { // When playback finishes
                                URL.revokeObjectURL(audio.src); // Release object URL
                                // Cleanup lip sync intervals
                                try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                                try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                                try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                                ttsCleanupFns = []; // Clear cleanup functions
                                // Reset avatar mouth
                                if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                                if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                            }; // End onended handler
                            
                            // Store audio reference for cleanup
                            ttsCleanupFns.push(() => { // Ensure cleanup when speech is cancelled
                                try { if (audio) { audio.pause(); audio.src = ''; } } catch(_) {}
                                try { if (mediaSource && mediaSource.readyState === 'open') { mediaSource.endOfStream(); } } catch(_) {}
                            }); // End cleanup function
                            
                            return; // Exit successfully
                        } else {
                            // MediaSource not supported for this format, fall back to blob playback
                            console.warn('⚠️ MediaSource not supported for', mimeType, '- using blob playback'); // Log fallback
                            const audioBlob = await res.blob(); // Get audio data as blob
                            // Re-wrap with normalized MIME because some TTS services return audio/mp3
                            // which is less reliable on iOS Safari than audio/mpeg.
                            const normalizedBlob = (audioBlob.type && audioBlob.type !== mimeType)
                                ? new Blob([audioBlob], { type: mimeType })
                                : audioBlob;
                            const audioUrl = URL.createObjectURL(normalizedBlob); // Create object URL for blob
                            
                            // Create audio element and play
                            const audio = new Audio(audioUrl); // Create audio element
                            audio.preload = 'auto'; // Enable preload
                            audio.crossOrigin = 'anonymous'; // Allow WebAudio connection
                            
                            // Handle cleanup when audio ends
                            audio.onended = () => { // When playback finishes
                                URL.revokeObjectURL(audioUrl); // Release object URL
                                // Cleanup lip sync intervals
                                try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                                try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                                try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                                ttsCleanupFns = []; // Clear cleanup functions
                                // Reset avatar mouth
                                if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                                if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                            }; // End onended handler
                            
                            // Start lip sync for binary audio path
                            startLipSyncFromAudioElement(audio); // Hook up lip sync to this audio element
                            
                            // Play the audio
                            await audio.play(); // Start playback
                            maybeHandleVrmTtsPlaybackStarted(preserveThinkingPose);
                            console.log('🎵 Playing binary audio from TTS service (blob mode)'); // Log playback start
                            
                            return; // Exit successfully
                        }
                    } catch (audioError) {
                        console.error('❌ Error playing binary audio:', audioError); // Log error
                        stopChatterboxLipSync(true); // Reset lip sync state
                        if (shouldSkipFallback(audioError)) {
                            console.log('Skipping browser TTS fallback after interrupted binary audio playback');
                            return; // Exit without fallback on intentional interruption
                        }
                        runBrowserTtsFallback(audioError); // Fall back to browser TTS on error
                        return; // Exit early
                    }
                } // End binary audio handling
                
                // Handle SSE format (Chatterbox/PCM streaming)
                // This path is for Chatterbox which returns SSE with base64-encoded PCM16 chunks
                if (isSSE) {
                    console.log('📡 Received SSE format (Chatterbox/PCM) - processing stream'); // Log format detection
                    
                    // Prepare analyser-driven lip sync graph for PCM streaming
                    stopChatterboxLipSync(true); // Reset any previous PCM lip sync loop before starting a new stream
                    const pcmCtx = ensureChatterboxLipSyncGraph(); // Ensure audio context and analyser exist
                    if (pcmCtx.state === 'suspended') { // Resume context if required by autoplay policies
                        try { pcmCtx.resume(); } catch (_) {} // Swallow resume errors; user interaction will resume if needed
                    }
                    ttsStreamActive = true; // Mark stream active so analyser loop stays alive between chunks
                    startLipSyncFromAnalyserNode(); // Start analyser-driven lip sync updates
				ttsCleanupFns.push(() => { // Ensure cleanup when speech is cancelled elsewhere
					try { stopChatterboxLipSync(true); } catch(_) {}
					try { if (localController) { localController.abort(); } } catch(_) {}
				});

                if (window.__opus.playhead === undefined) { // Check if playhead exists
                    window.__opus.playhead = 0; // Initialize playhead to 0
                } // End playhead initialization
                
                // Capture sample_rate and channels from speech.audio.info event
                let ttsSampleRate = 24000; // Default sample rate (fallback)
                let ttsChannels = 1; // Default channels (mono, fallback)
                
                // Wire SSE events to PCM16 decoder
				await streamSSE(res, { // Start SSE parsing with callbacks
					onInfo: (evt) => { // Handle metadata/info event
						if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) { return; }
                        ttsSampleRate = evt.sample_rate || evt.sampleRate || 24000; // Capture sample rate from metadata
                        ttsChannels = evt.channels || 1; // Capture channel count from metadata
                        console.log('🎵 PCM16 audio info - sample_rate:', ttsSampleRate, 'channels:', ttsChannels); // Log audio info
                    }, // End onInfo handler
					onInit: (b64) => { // Handle init event (if any - PCM16 may not need init)
						if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) { return; }
                        console.log('🎵 Received init event (PCM16 may not require init)'); // Log init event
                        // PCM16 typically doesn't need init segment, but handle if provided
                    }, // End onInit handler
					onDelta: (b64) => { // Decode and play each PCM16 delta chunk
						if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) { return; }
						playPcm16Delta(b64, ttsSampleRate, ttsChannels, { preserveThinkingPose });
					},
                    onDone: () => { // Handle stream completion
						if (localGen !== ttsGeneration || (localController && localController.signal.aborted)) { return; }
						console.log('🎵 SSE stream complete (PCM16)'); // Log completion
                        ttsStreamActive = false; // Mark stream inactive so lip sync can wind down
                        stopChatterboxLipSync(false); // Allow mouth to close after buffers finish
                        // Reset playhead for next stream (optional)
                        // window.__opus.playhead = 0; // Uncomment if you want to reset between streams
                    }, // End onDone handler
                    onError: (e) => { // Handle parsing errors
                        // Skip fallback if this was an intentional abort (cancellation) or if generation token is stale
                        if (localGen !== ttsGeneration || (e && e.name === 'AbortError') || (localController && localController.signal.aborted)) {
                            console.log('🛑 SSE stream cancelled (intentional abort), skipping fallback'); // Log cancellation
                            ttsStreamActive = false; // Mark stream inactive on abort
                            stopChatterboxLipSync(true); // Immediately stop lip sync
                            return; // Exit without fallback
                        }
                        console.error('❌ SSE parsing error:', e); // Log error
                        ttsStreamActive = false; // Mark stream inactive on error
                        stopChatterboxLipSync(false); // Schedule cleanup for analyser-driven lip sync
                        runBrowserTtsFallback(e); // Fall back to browser TTS if error occurs
                    } // End onError handler
                }); // End streamSSE call
                } else {
                    // Unknown format - neither SSE nor binary audio
                    console.warn('⚠️ Unknown TTS response format:', ct, '- falling back to browser TTS'); // Log format mismatch
                    stopChatterboxLipSync(true); // Reset lip sync state before fallback
                    runBrowserTtsFallback(); // Fall back to browser TTS
                    return; // Exit early
                } // End SSE format handling
            } catch (e) { // Catch any runtime errors
                // FIRST: Check if this error is from a stale request (new utterance already started) - this must be checked first
                if (localGen !== ttsGeneration) {
                    console.log('🛑 Chatterbox TTS request superseded by new utterance, skipping fallback'); // Log superseded request
                    ttsStreamActive = false; // Ensure stream-active flag is cleared
                    stopChatterboxLipSync(true); // Immediately stop lip sync
                    return; // Exit without fallback
                }
                // SECOND: Check if this was an intentional abort (cancellation) - check error name first and use local controller reference
                const isAbortError = (e && (e.name === 'AbortError' || e.message?.includes('aborted'))) || 
                                    (localController && localController.signal && localController.signal.aborted && localGen === ttsGeneration);
                if (isAbortError) {
                    console.log('🛑 Chatterbox TTS cancelled (intentional abort), skipping fallback'); // Log cancellation
                    ttsStreamActive = false; // Ensure stream-active flag is cleared on abort
                    stopChatterboxLipSync(true); // Immediately stop lip sync
                    return; // Exit without fallback
                }
                // Only fallback for real errors (network failures, server errors, etc.)
                console.error('❌ Chatterbox TTS failed:', e); // Log the error cause
                ttsStreamActive = false; // Ensure stream-active flag is cleared on failure
                stopChatterboxLipSync(false); // Schedule analyser cleanup so mouth closes gracefully
                // Fallback to browser speech if available (only for real errors, not cancellations)
                runBrowserTtsFallback(e); // Ensure speech still happens
            } // End try/catch
        } // End speakWithOpenAITTS (Chatterbox streaming TTS)

        // Play streaming audio using MediaSource API for real-time playback
        async function playStreamingAudioStream(audioChunks, mimeType = 'audio/webm;codecs=opus') { // Function to play streamed audio chunks in real-time
            try { // Begin error handling scope
                // Create audio element and MediaSource
                const audio = new Audio(); // Create audio element
                const mediaSource = new MediaSource(); // Create MediaSource for streaming
                audio.src = URL.createObjectURL(mediaSource); // Set source to object URL
                audio.preload = 'auto'; // Enable preload
                audio.crossOrigin = 'anonymous'; // Allow WebAudio connection
                
                console.log('🎵 Starting MediaSource audio stream...'); // Log streaming start
                
                // Wait for MediaSource to be ready
                mediaSource.addEventListener('sourceopen', () => { // When MediaSource opens
                    try { // Guard scope
                        const sourceBuffer = mediaSource.addSourceBuffer(mimeType); // Create source buffer
                        sourceBuffer.mode = 'sequence'; // Set mode to prevent timestamp gaps on Chrome builds
                        
                        // Flag to track if audio has started playing
                        let audioStarted = false; // Track if playback has started
                        let chunkIndex = 0; // Track current chunk index
                        
                        // Define the pump function to append chunks from array
                        const pump = async () => { // Async function to pump chunks
                            try { // Guard scope
                                if (chunkIndex < audioChunks.length) { // If more chunks are available
                                    const chunk = audioChunks[chunkIndex]; // Get next chunk from array
                                    sourceBuffer.appendBuffer(chunk); // Append chunk to buffer
                                    console.log('🎵 Chunk appended, size:', chunk.length, `(${chunkIndex + 1}/${audioChunks.length})`); // Log chunk size and progress
                                    
                                    // Start audio playback after first chunk to avoid autoplay guard
                                    if (!audioStarted) { // If audio hasn't started yet
                                        audioStarted = true; // Mark as started
                                        audio.play().then(() => { // When audio starts playing
                                            console.log('🎵 Audio playback started (streaming)'); // Log playback start
                                            handleVrmTtsPlaybackStarted();
                                            startLipSyncFromAudioElement(audio); // Hook up lip sync
                                        }).catch(e => { // Catch play errors
                                            console.error('Audio play error:', e); // Log error
                                        }); // End play promise chain
                                    } // End audio start check
                                    
                                    chunkIndex++; // Move to next chunk
                                    
                                    // Wait for buffer update before next append
                                    sourceBuffer.addEventListener('updateend', pump, { once: true }); // Schedule next chunk
                                } else { // If all chunks have been appended
                                    console.log('🎵 Stream complete, ending MediaSource'); // Log completion
                                    mediaSource.endOfStream(); // Signal end of stream
                                } // End chunks check
                            } catch (e) { // Catch errors in pump
                                console.error('Error in pump loop:', e); // Log error
                                mediaSource.endOfStream(); // Signal end on error
                            } // End try/catch in pump
                        }; // End pump function
                        
                        pump(); // Start the pump process
                    } catch (e) { // Catch MediaSource errors
                        console.error('MediaSource setup error:', e); // Log error
                    } // End try/catch
                }); // End sourceopen event listener
                
                // Handle cleanup when audio ends
                audio.onended = () => { // When playback finishes
                    URL.revokeObjectURL(audio.src); // Release object URL
                    // Cleanup MediaSource
                    try { if (mediaSource.readyState === 'open') mediaSource.endOfStream(); } catch(_){}
                    // Cleanup lip sync intervals
                    try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                    try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                    try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                    ttsCleanupFns = []; // Clear cleanup functions
                    // Reset avatar mouth
                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                }; // End onended handler
                
                // Handle media source errors
                mediaSource.addEventListener('error', (e) => { // When MediaSource errors occur
                    console.error('MediaSource error:', e); // Log the error
                }); // End error handler
                
                // Register cleanup for external cancellations
                ttsCleanupFns.push(() => {
                    try { audio.pause(); } catch(_){}
                    try { if (mediaSource.readyState === 'open') mediaSource.endOfStream(); } catch(_){}
                    try { mediaSource.removeEventListener('error', () => {}); } catch(_){}
                    try { URL.revokeObjectURL(audio.src); } catch(_){}
                }); // End cleanup registration
                
            } catch (error) { // Catch setup errors
                console.error('Error setting up streaming audio:', error); // Log error
                throw error; // Re-throw to trigger fallback
            } // End try/catch
        } // End playStreamingAudioStream

        // Play streaming audio chunks as blob (fallback for Safari)
        async function playStreamingAudio(combinedAudio, mimeType) { // Function to play streamed audio from combined array
            try {
                // Create blob from combined audio data
                const blob = new Blob([combinedAudio], { type: mimeType }); // Create blob with provided MIME type
                const url = URL.createObjectURL(blob); // Create object URL
                
                const audio = new Audio(); // Create audio element
                audio.src = url; // Set source URL
                audio.preload = 'auto'; // Enable preload
                audio.crossOrigin = 'anonymous'; // Allow WebAudio connection
                
                // Handle cleanup when audio ends
                audio.onended = () => { // When playback finishes
                    URL.revokeObjectURL(url); // Release object URL
                    // Cleanup lip sync intervals
                    try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                    try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                    try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                    ttsCleanupFns = []; // Clear cleanup functions
                    // Reset avatar mouth
                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                }; // End onended handler
                
                // Start lip sync using audio amplitude
                startLipSyncFromAudioElement(audio); // Hook up lip sync
                
                // Start playback
                await audio.play(); // Begin playing audio
                handleVrmTtsPlaybackStarted();
                console.log('🎵 Audio playback started'); // Log playback start
            } catch (error) {
                console.error('Error playing streaming audio:', error); // Log error
            } // End try/catch
        } // End playStreamingAudio
        
        // Browser speech fallback wrapper used when server TTS fails
        function textToSpeechFallback(text, { preserveThinkingPose = false } = {}) { // Function to call original SpeechSynthesis path
            try { // Begin guard
                // Sanitize text before creating utterance
                text = sanitizeTTS(text); // Clean text for browser fallback speech
                if (!text) return;
                const browserSpeechSessionId = ++browserSpeechGeneration;
                const selectedVoice = getSelectedBrowserVoice();
                const chunkLimit = isIOSDevice ? 160 : 280;
                const chunks = splitTtsTextChunks(text, chunkLimit);
                let idx = 0;
                let cancelled = false;
                ttsCleanupFns.push(() => { cancelled = true; });

                const finalize = () => {
                    if (cancelled) return;
                    try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                    try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                    try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); ttsCleanupFns = []; } catch(_){}
                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                };

                const speakNextChunk = () => {
                    if (cancelled || browserSpeechSessionId !== browserSpeechGeneration) return;
                    if (idx >= chunks.length) {
                        finalize();
                        return;
                    }
                    const chunk = chunks[idx++];
                    const utter = new SpeechSynthesisUtterance(chunk);
                    if (selectedVoice) utter.voice = selectedVoice;
                    utter.rate = 1.0;
                    utter.pitch = 1.0;
                    utter.onstart = () => {
                        if (cancelled || browserSpeechSessionId !== browserSpeechGeneration) return;
                        if (!preserveThinkingPose) {
                            handleVrmTtsPlaybackStarted();
                        }
                        isSpeaking = true;
                        microsoftTtsLastBoundaryTs = performance.now();
                        startBrowserSpeechLipSyncLoop();
                    };
                    utter.onboundary = () => {
                        if (cancelled || browserSpeechSessionId !== browserSpeechGeneration) return;
                        registerBrowserSpeechBoundary();
                    };
                    utter.onend = () => {
                        if (cancelled || browserSpeechSessionId !== browserSpeechGeneration) return;
                        if (idx < chunks.length) {
                            speakNextChunk();
                        } else {
                            stopBrowserSpeechLipSync();
                            finalize();
                        }
                    };
                    utter.onerror = (event) => {
                        if (cancelled || browserSpeechSessionId !== browserSpeechGeneration) return;
                        console.warn('Browser TTS fallback chunk error:', event);
                        if (idx < chunks.length) {
                            speakNextChunk();
                        } else {
                            stopBrowserSpeechLipSync();
                            finalize();
                        }
                    };
                    speechSynthesis.speak(utter); // Speak using browser engine
                };

                try { speechSynthesis.cancel(); } catch(_) {}
                speakNextChunk();
            } catch (e) { // Catch runtime issues
                console.warn('Browser TTS fallback failed:', e); // Log warning for diagnostics
                if (!preserveThinkingPose) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
            } // End try/catch
        } // End textToSpeechFallback

        // Connect an HTMLAudioElement to Web Audio and drive mouth using real-time amplitude
        function startLipSyncFromAudioElement(audioEl) { // Function to build analyzer pipeline for lip sync
            try { // Begin guard scope
                // Ensure an AudioContext exists and is resumed (required by autoplay policies)
                if (!audioContext) { // If no global audio context is present
                    audioContext = new (window.AudioContext || window.webkitAudioContext)(); // Create new context instance
                } // End audio context creation
                if (audioContext.state === 'suspended') { // If audio is suspended by policy
                    audioContext.resume().catch(() => {}); // Attempt to resume context
                } // End resume branch

                const source = audioContext.createMediaElementSource(audioEl); // Wrap element as MediaElementSourceNode
                const analyser = audioContext.createAnalyser(); // Create AnalyserNode to read waveform
                analyser.fftSize = 1024; // Set FFT size for time domain buffer length
                analyser.smoothingTimeConstant = 0.7; // Add smoothing to reduce jitter
                const gain = audioContext.createGain(); // Create gain node
                gain.gain.value = 1.0; // Ensure full volume to destination

                source.connect(analyser); // Connect source to analyser for measurement
                analyser.connect(gain); // Pass through gain to output
                gain.connect(audioContext.destination); // Route audio to speakers

                const buffer = new Uint8Array(analyser.fftSize); // Allocate byte buffer for time domain samples
                let rafId = 0; // Store the requestAnimationFrame id for cleanup
                let smoothed = 0; // Keep a smoothed envelope value
                const attack = 0.6; // Attack coefficient for rising amplitude
                const release = 0.15; // Release coefficient for falling amplitude

                const update = () => { // Define per-frame update callback
                    analyser.getByteTimeDomainData(buffer); // Fill buffer with time-domain samples
                    // Compute normalized RMS amplitude [0,1]
                    let sum = 0; // Accumulator for RMS
                    for (let i = 0; i < buffer.length; i++) { // Iterate over samples
                        const v = (buffer[i] - 128) / 128; // Convert byte sample to [-1,1]
                        sum += v * v; // Accumulate squared amplitude
                    } // End sample loop
                    const rms = Math.sqrt(sum / buffer.length); // Compute root-mean-square amplitude
                    // Envelope follower with attack/release
                    if (rms > smoothed) { // If amplitude is rising
                        smoothed = smoothed + (rms - smoothed) * attack; // Apply attack smoothing
                    } else { // If amplitude is falling
                        smoothed = smoothed + (rms - smoothed) * release; // Apply release smoothing
                    } // End envelope update

                    // Map amplitude to mouth open value with thresholding
                    const threshold = 0.03; // Minimum RMS to consider as speech
                    const scaled = smoothed <= threshold ? 0 : Math.min(1, (smoothed - threshold) * 6.0); // Scale to [0,1]

                    // Apply to Live2D if present
                    if (live2dModel) { // If Live2D model active
                        live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', scaled); // Set mouth parameter by amplitude
                    } // End Live2D application

                    // Apply to VRM if present
                    if (vrmModel && document.getElementById('vrm-mode').checked) { // If VRM active
                        animateVRMLipSync(scaled); // Set expression value based on amplitude
                    } // End VRM application

                    if (!audioEl.paused && !audioEl.ended) { // If audio is still playing
                        rafId = requestAnimationFrame(update); // Schedule next frame update
                        ttsRafId = rafId; // Track globally so we can cancel on utterance end elsewhere
                    } // End continuation check
                }; // End update function

                const startLoop = () => { // Start analyser loop only once per playback
                    if (rafId) return; // Avoid duplicate RAF loops
                    update(); // Kick off mouth animation updates
                };

                const onPlay = () => { // Ensure loop starts even when hook is created before play()
                    if (audioContext && audioContext.state === 'suspended') {
                        audioContext.resume().catch(() => {});
                    }
                    startLoop();
                };

                const onEnded = () => { // Define cleanup on audio end
                    if (rafId) cancelAnimationFrame(rafId); // Cancel RAF loop
                    ttsRafId = 0; // Clear global raf id
                    // Ensure mouth returns to closed state
                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); } // Close Live2D mouth
                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); } // Close VRM mouth
                    // Disconnect nodes to avoid leaks
                    try { source.disconnect(); } catch (_) {} // Detach source from graph
                    try { analyser.disconnect(); } catch (_) {} // Detach analyser from graph
                    try { gain.disconnect(); } catch (_) {} // Detach gain from graph
                    try { URL.revokeObjectURL(audioEl.src); } catch (_) {} // Revoke object URL
                    audioEl.removeEventListener('play', onPlay); // Remove play handler
                    audioEl.removeEventListener('ended', onEnded); // Remove event handler
                }; // End onEnded

                audioEl.addEventListener('play', onPlay); // Start analyser loop when playback begins
                audioEl.addEventListener('ended', onEnded); // Wire cleanup on end
                // Register cleanup for external cancellations
                ttsCleanupFns.push(() => {
                    try { audioEl.pause(); } catch(_){}
                    try { audioEl.removeEventListener('play', onPlay); } catch(_){}
                    try { audioEl.removeEventListener('ended', onEnded); } catch(_){}
                    try { source.disconnect(); } catch(_){}
                    try { analyser.disconnect(); } catch(_){}
                    try { gain.disconnect(); } catch(_){}
                    try { if (rafId) cancelAnimationFrame(rafId); } catch(_){}
                    try { URL.revokeObjectURL(audioEl.src); } catch(_){}
                });
                if (!audioEl.paused && !audioEl.ended) { // Start immediately when already playing
                    startLoop();
                }
            } catch (e) { // Catch runtime issues constructing graph
                console.warn('startLipSyncFromAudioElement failed:', e); // Log warning to console
            } // End try/catch
        } // End startLipSyncFromAudioElement

        // Add this helper function to create smoother mouth movements
        function animateMouth() {
            if (!live2dModel) return;
            
            const mouthOpenY = "ParamMouthOpenY";
            const now = Date.now();
            const value = (Math.sin(now * 0.01) + 1) * 0.5; // Creates a smooth 0-1 oscillation
            
            live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, value);
            requestAnimationFrame(animateMouth);
        }

        function getLive2DOffset(path = modelPath) {
            const value = Number(live2dOffsets?.[path]);
            return Number.isFinite(value) ? value : 0;
        }

        function getLive2DScale(path = modelPath) {
            const value = Number(live2dScales?.[path]);
            if (!Number.isFinite(value)) return 1.0;
            return Math.min(3.0, Math.max(0.4, value));
        }

        function formatLive2DScale(value) {
            const numericValue = Math.min(3.0, Math.max(0.4, Number(value) || 1.0));
            return `${numericValue.toFixed(2)}x`;
        }

        function clearLive2DResizeHandler() {
            if (live2dResizeHandler) {
                window.removeEventListener('resize', live2dResizeHandler);
                live2dResizeHandler = null;
            }
        }

        function destroyLive2DModelInstance(model) {
            if (!model) return;
            try { model.removeAllListeners?.(); } catch (_) {}
            try {
                if (model.parent) {
                    model.parent.removeChild(model);
                }
            } catch (_) {}
            try {
                if (typeof model.destroy === 'function') {
                    model.destroy({ children: true, texture: true, baseTexture: true });
                }
            } catch (_) {}
        }

        function ensureLive2DApp(container, canvas) {
            const width = Math.max(container?.clientWidth || 0, 1);
            const height = Math.max(container?.clientHeight || 0, 1);
            if (!live2dApp) {
                live2dApp = new PIXI.Application({
                    view: canvas,
                    transparent: true,
                    autoStart: true,
                    width,
                    height
                });
            } else {
                live2dApp.renderer.resize(width, height);
            }
            return live2dApp;
        }

        function getLive2DIntrinsicSize(model) {
            try {
                const bounds = model.getLocalBounds?.();
                const width = Math.abs(bounds?.width || 0);
                const height = Math.abs(bounds?.height || 0);
                if (width > 0 && height > 0) {
                    return { width, height };
                }
            } catch (_) {}

            const scaleX = Math.abs(model?.scale?.x || 1) || 1;
            const scaleY = Math.abs(model?.scale?.y || 1) || 1;
            const width = Math.abs((model?.width || 0) / scaleX);
            const height = Math.abs((model?.height || 0) / scaleY);
            return {
                width: width > 0 ? width : 1,
                height: height > 0 ? height : 1
            };
        }

        function applyCurrentLive2DLayout(targetModel = live2dModel, path = live2dActiveModelPath || modelPath) {
            const container = document.getElementById('live2d-container');
            if (!container || !targetModel || !live2dApp) return;

            const width = Math.max(container.clientWidth || 0, 1);
            const height = Math.max(container.clientHeight || 0, 1);
            live2dApp.renderer.resize(width, height);

            const intrinsic = getLive2DIntrinsicSize(targetModel);
            const baseScale = Math.min(
                width / (intrinsic.width * 1.5),
                height / (intrinsic.height * 1.5)
            ) * 2.5;
            const scale = baseScale * getLive2DScale(path);

            targetModel.scale.set(scale);
            targetModel.x = width / 2;
            targetModel.y = (height / 1.4) + getLive2DOffset(path);
        }

        function disposeLive2DModel() {
            clearLive2DResizeHandler();
            if (live2dApp?.stage) {
                try { live2dApp.stage.removeChildren(); } catch (_) {}
                try { live2dApp.renderer.render(live2dApp.stage); } catch (_) {}
            }
            destroyLive2DModelInstance(live2dModel);
            live2dModel = null;
            live2dActiveModelPath = '';
        }

        function attachLive2DResizeHandler(path) {
            clearLive2DResizeHandler();
            let rafId = 0;
            live2dResizeHandler = () => {
                if (rafId) cancelAnimationFrame(rafId);
                rafId = requestAnimationFrame(() => {
                    rafId = 0;
                    applyCurrentLive2DLayout(live2dModel, path);
                });
            };
            window.addEventListener('resize', live2dResizeHandler);
        }

        function clearVRMResizeHandler() {
            if (vrmResizeHandler) {
                window.removeEventListener('resize', vrmResizeHandler);
                vrmResizeHandler = null;
            }
        }

        function resizeVRMViewport() {
            const container = document.getElementById('vrm-container');
            if (!container || !vrmRenderer || !vrmCamera) return;

            const width = Math.max(container.clientWidth || 0, 1);
            const height = Math.max(container.clientHeight || 0, 1);

            vrmRenderer.setSize(width, height, false);
            vrmCamera.aspect = width / height;
            vrmCamera.updateProjectionMatrix();

            if (vrmScene) {
                try { vrmRenderer.render(vrmScene, vrmCamera); } catch (_) {}
            }
        }

        function attachVRMResizeHandler() {
            clearVRMResizeHandler();
            let rafId = 0;
            vrmResizeHandler = () => {
                if (rafId) cancelAnimationFrame(rafId);
                rafId = requestAnimationFrame(() => {
                    rafId = 0;
                    resizeVRMViewport();
                });
            };
            window.addEventListener('resize', vrmResizeHandler);
        }

        // Build full tool settings object from DOM (single source of truth for companion snapshot and localStorage)
        function getToolSettingsFromDOM() {
            const vrmVersionDropdown = document.getElementById('vrm-version-dropdown');
            const voiceDropdown = document.getElementById('voice-dropdown');
            const live2dDropdown = document.getElementById('live2d-model-dropdown');
            const live2dList = document.getElementById('live2d-model-list');
            const live2dOffsetRange = document.getElementById('live2d-offset-range');
            const live2dScaleRange = document.getElementById('live2d-scale-range');
            const vrmDropdown = document.getElementById('vrm-model-dropdown');
            const vrmList = document.getElementById('vrm-model-list');
            const vrmScaleRange = document.getElementById('vrm-scale-range');
            const vrmPositionXRange = document.getElementById('vrm-position-x-range');
            const vrmPositionYRange = document.getElementById('vrm-position-y-range');
            const vrmRotationRange = document.getElementById('vrm-rotation-range');
            const vrmModeEl = document.getElementById('vrm-mode');
            const avatarMode = (vrmModeEl && vrmModeEl.checked) ? 'vrm' : 'live2d';
            return {
                userName: userNameInput.value,
                assistantName: assistantNameInput.value,
                apiKey: apiKeyInput.value,
                endpoint: endpointInput.value,
                newsApiKey: newsApiKeyInput ? newsApiKeyInput.value : '',
                systemPrompt: systemPromptInput.value,
                webcamMode: document.getElementById('webcam-toggle').checked,
                clipboardMode: document.getElementById('clipboard-toggle').checked,
                muteMode: document.getElementById('mute-toggle').checked,
                baseModel: baseModelDropdown ? baseModelDropdown.value : baseModel,
                toolModel: toolModelDropdown ? toolModelDropdown.value : toolModel,
                visionModel: visionModelDropdown ? visionModelDropdown.value : visionModel,
                ttsService: ttsServiceOpenAI.checked ? 'openai' : 'microsoft',
                ttsEndpoint: ttsEndpointInput.value,
                ttsModel: ttsModelDropdown ? ttsModelDropdown.value : '',
                ttsVoice: ttsVoiceDropdown ? ttsVoiceDropdown.value : '',
                browserVoiceURI: voiceDropdown && voices[voiceDropdown.value] ? voices[voiceDropdown.value].voiceURI : null,
                vrmVersion: vrmVersionDropdown ? vrmVersionDropdown.value : '1.0',
                avatarMode: avatarMode,
                live2dModel: live2dDropdown ? live2dDropdown.value : '',
                live2dModelList: live2dList ? live2dList.value : '',
                live2dOffset: live2dOffsetRange ? parseFloat(live2dOffsetRange.value) || 0 : 0,
                live2dScale: live2dScaleRange ? parseFloat(live2dScaleRange.value) || 1.0 : 1.0,
                vrmModel: vrmDropdown ? vrmDropdown.value : '',
                vrmModelList: vrmList ? vrmList.value : '',
                vrmScale: vrmScaleRange ? parseFloat(vrmScaleRange.value) || 1.0 : 1.0,
                vrmPositionX: vrmPositionXRange ? parseFloat(vrmPositionXRange.value) || 0 : 0,
                vrmPositionY: vrmPositionYRange ? parseFloat(vrmPositionYRange.value) || 0 : 0,
                vrmRotation: vrmRotationRange ? parseInt(vrmRotationRange.value, 10) || 0 : 0,
                live2dOffsets: live2dOffsets || {},
                live2dScales: live2dScales || {},
                vrmPositions: vrmPositions || {}
            };
        }

        // Function to save tool settings to localStorage (uses getToolSettingsFromDOM as single source)
        function saveToolSettings(options = {}) {
            try {
                const settings = getToolSettingsFromDOM();
                localStorage.setItem('toolSettings', JSON.stringify(settings));
                if (!options.skipCompanionRefresh) {
                    updateCompanionDraftUI(settings, { syncDirtyState: options.syncDirtyState !== false });
                }
            } catch (error) {
                console.warn('Error saving tool settings:', error);
            }
        }

        function hasMeaningfulValue(value) {
            if (value == null) return false;
            if (typeof value === 'string') return value.trim().length > 0;
            return true;
        }

        function mergeClientDefaults(settings, defaults) {
            if (!defaults || typeof defaults !== 'object') return { settings, applied: false };
            const merged = (settings && typeof settings === 'object') ? { ...settings } : {};
            let applied = false;
            if (!hasMeaningfulValue(merged.endpoint) && hasMeaningfulValue(defaults.llmEndpoint)) {
                merged.endpoint = defaults.llmEndpoint;
                applied = true;
            }
            if (!hasMeaningfulValue(merged.ttsEndpoint) && hasMeaningfulValue(defaults.ttsEndpoint)) {
                merged.ttsEndpoint = defaults.ttsEndpoint;
                applied = true;
            }
            if (!hasMeaningfulValue(merged.ttsModel) && hasMeaningfulValue(defaults.ttsModel)) {
                merged.ttsModel = defaults.ttsModel;
                applied = true;
            }
            if (!hasMeaningfulValue(merged.ttsVoice) && hasMeaningfulValue(defaults.ttsVoice)) {
                merged.ttsVoice = defaults.ttsVoice;
                applied = true;
            }
            return { settings: merged, applied };
        }

        function renderSoulPromptPreview(soulPrompt = '') {
            if (!soulPromptDisplay) return;
            soulPromptDisplay.value = typeof soulPrompt === 'string' ? soulPrompt : '';
        }

        async function fetchClientToolDefaults() {
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/client-config`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                if (!res.ok) return null;
                const data = await res.json();
                if (!data || typeof data !== 'object') return null;
                const defaults = {
                    soulPrompt: data.soulPrompt || '',
                    llmEndpoint: data.llmEndpoint || '',
                    llmPrivateNetworksAllowed: data.llmPrivateNetworksAllowed === true,
                    ttsEndpoint: data.ttsEndpoint || '',
                    ttsModel: data.ttsModel || '',
                    ttsVoice: data.ttsVoice || ''
                };
                return defaults;
            } catch (error) {
                console.warn('Error fetching client config:', error);
                return null;
            }
        }

        // Apply a settings object to DOM and globals; optionally re-initialize avatar if mode/model changed
        function applyToolSettingsToDOM(settings) {
            if (!settings || typeof settings !== 'object') return;
            // User and API
            if (settings.userName !== undefined) userNameInput.value = settings.userName;
            if (settings.assistantName !== undefined) assistantNameInput.value = settings.assistantName;
            if (settings.apiKey !== undefined) apiKeyInput.value = settings.apiKey;
            if (settings.endpoint !== undefined) endpointInput.value = settings.endpoint;
            if (newsApiKeyInput && settings.newsApiKey !== undefined) newsApiKeyInput.value = settings.newsApiKey;
            if (settings.systemPrompt !== undefined) systemPromptInput.value = settings.systemPrompt;
            if (settings.webcamMode !== undefined) document.getElementById('webcam-toggle').checked = settings.webcamMode;
            if (settings.clipboardMode !== undefined) document.getElementById('clipboard-toggle').checked = settings.clipboardMode;
            if (settings.muteMode !== undefined) {
                document.getElementById('mute-toggle').checked = settings.muteMode;
                isMuted = settings.muteMode;
            }
            // Models
            if (settings.baseModel !== undefined) {
                defaultBaseModel = settings.baseModel;
                baseModel = settings.baseModel;
                if (baseModelDropdown) baseModelDropdown.value = settings.baseModel;
            }
            if (settings.toolModel !== undefined) {
                defaultToolModel = settings.toolModel;
                toolModel = settings.toolModel;
                if (toolModelDropdown) toolModelDropdown.value = settings.toolModel;
            }
            if (settings.visionModel !== undefined) {
                defaultVisionModel = settings.visionModel;
                visionModel = settings.visionModel;
                if (visionModelDropdown) visionModelDropdown.value = settings.visionModel;
            }
            // TTS
            if (settings.ttsService !== undefined) {
                if (settings.ttsService === 'openai') ttsServiceOpenAI.checked = true;
                else ttsServiceMicrosoft.checked = true;
            }
            if (settings.ttsEndpoint !== undefined && ttsEndpointInput) ttsEndpointInput.value = settings.ttsEndpoint;
            if (settings.ttsModel !== undefined && ttsModelDropdown) {
                if (settings.ttsModel && !Array.from(ttsModelDropdown.options).some(o => o.value === settings.ttsModel)) {
                    const opt = document.createElement('option');
                    opt.value = settings.ttsModel;
                    opt.textContent = settings.ttsModel;
                    ttsModelDropdown.appendChild(opt);
                }
                ttsModelDropdown.value = settings.ttsModel;
            }
            if (settings.ttsVoice !== undefined && ttsVoiceDropdown) ttsVoiceDropdown.value = settings.ttsVoice;
            const vrmVersionDropdown = document.getElementById('vrm-version-dropdown');
            if (settings.vrmVersion !== undefined && vrmVersionDropdown) {
                vrmVersionDropdown.value = settings.vrmVersion;
                vrmVersion = settings.vrmVersion;
            }
            if (settings.browserVoiceURI !== undefined) {
                try { localStorage.setItem(SELECTED_VOICE_STORAGE_KEY, settings.browserVoiceURI); } catch (e) {}
                if (typeof loadVoices === 'function') loadVoices();
            }
            if (settings.ttsService === 'openai' && ttsServiceOpenAI) {
                setTimeout(() => fetchTtsVoices(), 500);
            } else if (settings.ttsVoice !== undefined && ttsVoiceDropdown) {
                if (Array.from(ttsVoiceDropdown.options).some(o => o.value === settings.ttsVoice)) {
                    ttsVoiceDropdown.value = settings.ttsVoice;
                }
            }
            // Avatar: Live2D list and selection
            const live2dListEl = document.getElementById('live2d-model-list');
            const live2dDropdownEl = document.getElementById('live2d-model-dropdown');
            if (settings.live2dModelList !== undefined && live2dListEl) live2dListEl.value = settings.live2dModelList;
            if (settings.live2dModel !== undefined) modelPath = settings.live2dModel;
            if (settings.live2dOffsets !== undefined && typeof settings.live2dOffsets === 'object') live2dOffsets = settings.live2dOffsets;
            if (settings.live2dScales !== undefined && typeof settings.live2dScales === 'object') live2dScales = settings.live2dScales;
            if (live2dListEl && live2dDropdownEl) {
                const lines = (live2dListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));
                setModelDropdownOptions(live2dDropdownEl, lines, modelPath);
                if (modelPath && lines.indexOf(modelPath) === -1) {
                    const opt = document.createElement('option');
                    opt.value = modelPath;
                    opt.textContent = modelPath.split('/').pop();
                    opt.selected = true;
                    live2dDropdownEl.appendChild(opt);
                } else if (modelPath) live2dDropdownEl.value = modelPath;
            }
            const live2dOffsetRangeEl = document.getElementById('live2d-offset-range');
            const live2dOffsetValueEl = document.getElementById('live2d-offset-value');
            const live2dScaleRangeEl = document.getElementById('live2d-scale-range');
            const live2dScaleValueEl = document.getElementById('live2d-scale-value');
            if (settings.live2dOffset !== undefined && modelPath) {
                live2dOffsets[modelPath] = Number(settings.live2dOffset) || 0;
            }
            if (settings.live2dScale !== undefined && modelPath) {
                live2dScales[modelPath] = Math.min(3.0, Math.max(0.4, Number(settings.live2dScale) || 1.0));
            }
            const offsetVal = settings.live2dOffset !== undefined ? (Number(settings.live2dOffset) || 0) : getLive2DOffset(modelPath);
            const scaleVal = settings.live2dScale !== undefined
                ? Math.min(3.0, Math.max(0.4, Number(settings.live2dScale) || 1.0))
                : getLive2DScale(modelPath);
            if (live2dOffsetRangeEl) live2dOffsetRangeEl.value = String(offsetVal);
            if (live2dOffsetValueEl) live2dOffsetValueEl.textContent = String(offsetVal);
            if (live2dScaleRangeEl) live2dScaleRangeEl.value = String(scaleVal);
            if (live2dScaleValueEl) live2dScaleValueEl.textContent = formatLive2DScale(scaleVal);
            // Avatar: VRM list and selection
            const vrmListEl = document.getElementById('vrm-model-list');
            const vrmDropdownEl = document.getElementById('vrm-model-dropdown');
            if (settings.vrmModelList !== undefined && vrmListEl) vrmListEl.value = settings.vrmModelList;
            if (settings.vrmModel !== undefined) currentVRMModelPath = settings.vrmModel;
            if (settings.vrmPositions !== undefined && typeof settings.vrmPositions === 'object') vrmPositions = settings.vrmPositions;
            if (vrmListEl && vrmDropdownEl) {
                const vrmLines = (vrmListEl.value || '').split('\n').map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));
                setModelDropdownOptions(vrmDropdownEl, vrmLines, currentVRMModelPath);
                if (currentVRMModelPath) {
                    if (vrmLines.indexOf(currentVRMModelPath) !== -1) vrmDropdownEl.value = currentVRMModelPath;
                    else {
                        const opt = document.createElement('option');
                        opt.value = currentVRMModelPath;
                        opt.textContent = currentVRMModelPath.split('/').pop();
                        opt.selected = true;
                        vrmDropdownEl.appendChild(opt);
                        vrmDropdownEl.value = currentVRMModelPath;
                    }
                }
            }
            const vrmScaleRangeEl = document.getElementById('vrm-scale-range');
            const vrmScaleValueEl = document.getElementById('vrm-scale-value');
            const vrmPosXEl = document.getElementById('vrm-position-x-range');
            const vrmPosXValEl = document.getElementById('vrm-position-x-value');
            const vrmPosYEl = document.getElementById('vrm-position-y-range');
            const vrmPosYValEl = document.getElementById('vrm-position-y-value');
            const vrmRotEl = document.getElementById('vrm-rotation-range');
            const vrmRotValEl = document.getElementById('vrm-rotation-value');
            const pos = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };
            const scale = settings.vrmScale !== undefined ? Number(settings.vrmScale) : pos.scale;
            const posX = settings.vrmPositionX !== undefined ? Number(settings.vrmPositionX) : pos.positionX;
            const posY = settings.vrmPositionY !== undefined ? Number(settings.vrmPositionY) : pos.positionY;
            const rot = settings.vrmRotation !== undefined ? Number(settings.vrmRotation) : pos.rotation;
            if (vrmScaleRangeEl) vrmScaleRangeEl.value = scale;
            if (vrmScaleValueEl) vrmScaleValueEl.textContent = String(scale);
            if (vrmPosXEl) vrmPosXEl.value = posX;
            if (vrmPosXValEl) vrmPosXValEl.textContent = String(posX);
            if (vrmPosYEl) vrmPosYEl.value = posY;
            if (vrmPosYValEl) vrmPosYValEl.textContent = String(posY);
            if (vrmRotEl) vrmRotEl.value = rot;
            if (vrmRotValEl) vrmRotValEl.textContent = String(rot);
            vrmPositions[currentVRMModelPath] = { scale, positionX: posX, positionY: posY, rotation: rot };
            // Avatar mode radio and re-init
            const live2dModeEl = document.getElementById('live2d-mode');
            const vrmModeEl = document.getElementById('vrm-mode');
            const newMode = (settings.avatarMode === 'vrm') ? 'vrm' : 'live2d';
            if (live2dModeEl && vrmModeEl) {
                if (newMode === 'vrm') vrmModeEl.checked = true;
                else live2dModeEl.checked = true;
            }
            try { localStorage.setItem('avatarMode', newMode); } catch {}
            if (modelPath) {
                try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
            }
            if (currentVRMModelPath) {
                try { localStorage.setItem(VRM_SELECTED_KEY, currentVRMModelPath); } catch {}
            }
            // Re-initialize avatar so the companion's model loads (always cleanup and init so model path change takes effect)
            setTimeout(async () => {
                try {
                    const live2dContainer = document.getElementById('live2d-container');
                    const vrmContainer = document.getElementById('vrm-container');
                    if (newMode === 'vrm') {
                        if (vrmContainer) vrmContainer.style.display = 'block';
                        if (live2dContainer) live2dContainer.style.display = 'none';
                        if (typeof cleanupVRM === 'function') cleanupVRM();
                        if (typeof cleanupLive2D === 'function') cleanupLive2D();
                        if (typeof initVRM === 'function') await initVRM();
                    } else {
                        if (live2dContainer) live2dContainer.style.display = 'block';
                        if (vrmContainer) vrmContainer.style.display = 'none';
                        if (typeof cleanupLive2D === 'function') cleanupLive2D();
                        if (typeof cleanupVRM === 'function') cleanupVRM();
                        if (typeof initLive2D === 'function') await initLive2D();
                    }
                } catch (e) { console.warn('Companion avatar re-init:', e); }
            }, 100);
        }

        // Function to load tool settings from localStorage or from a provided settings object (e.g. companion)
        function loadToolSettings(optionalSettings) {
            try {
                let settings = optionalSettings != null
                    ? optionalSettings
                    : (() => { const s = localStorage.getItem('toolSettings'); return s ? JSON.parse(s) : null; })();
                let appliedDefaults = false;
                if (optionalSettings == null) {
                    const merged = mergeClientDefaults(settings, envToolDefaults);
                    settings = merged.settings;
                    appliedDefaults = merged.applied;
                }
                if (settings) {
                    applyToolSettingsToDOM(settings);
                    if (appliedDefaults) saveToolSettings();
                    if (optionalSettings == null) console.log('Tool settings loaded from localStorage');
                } else if (optionalSettings == null && envToolDefaults) {
                    const merged = mergeClientDefaults(null, envToolDefaults);
                    if (merged.settings) {
                        applyToolSettingsToDOM(merged.settings);
                        if (merged.applied) saveToolSettings();
                    }
                }
            } catch (error) {
                console.warn('Error loading tool settings:', error);
            }
        }

        // Normalize path for dedupe: strip leading ./ and trailing slash so "./model_avatar/X" matches "model_avatar/X"
        function normalizeModelPath(p) {
            return (p || '').trim().replace(/^\.\//, '').replace(/\/$/, '');
        }

        function parseModelList(value, extension) {
            return (value || '')
                .split(/\r?\n/)
                .map(line => line.trim())
                .filter(line => line.length > 0 && line.toLowerCase().endsWith(extension));
        }

        function setModelDropdownOptions(dropdown, paths, selectedPath = '') {
            if (!dropdown) return;
            dropdown.textContent = '';
            paths.forEach((path) => {
                const option = document.createElement('option');
                option.value = path;
                option.textContent = path.split('/').pop() || path;
                option.selected = path === selectedPath;
                dropdown.appendChild(option);
            });
        }

        function setModelListValue(textarea, paths) {
            if (!textarea) return;
            textarea.value = paths.join('\n');
        }

        function syncLive2DModelControls() {
            const live2dListEl = document.getElementById('live2d-model-list');
            const live2dDropdownEl = document.getElementById('live2d-model-dropdown');
            const live2dOffsetRangeEl = document.getElementById('live2d-offset-range');
            const live2dOffsetValueEl = document.getElementById('live2d-offset-value');
            const live2dScaleRangeEl = document.getElementById('live2d-scale-range');
            const live2dScaleValueEl = document.getElementById('live2d-scale-value');
            if (!live2dListEl || !live2dDropdownEl) return [];

            const lines = parseModelList(live2dListEl.value, '.model3.json');
            if (!lines.includes(modelPath)) {
                modelPath = lines[0] || '';
                try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
            }

            setModelDropdownOptions(live2dDropdownEl, lines, modelPath);

            if (modelPath) {
                live2dDropdownEl.value = modelPath;
            }

            const currentOffset = modelPath ? getLive2DOffset(modelPath) : 0;
            const currentScale = modelPath ? getLive2DScale(modelPath) : 1.0;
            if (live2dOffsetRangeEl) live2dOffsetRangeEl.value = String(currentOffset);
            if (live2dOffsetValueEl) live2dOffsetValueEl.textContent = String(currentOffset);
            if (live2dScaleRangeEl) live2dScaleRangeEl.value = String(currentScale);
            if (live2dScaleValueEl) live2dScaleValueEl.textContent = formatLive2DScale(currentScale);
            return lines;
        }

        function syncVRMModelControls() {
            const vrmListEl = document.getElementById('vrm-model-list');
            const vrmDropdownEl = document.getElementById('vrm-model-dropdown');
            if (!vrmListEl || !vrmDropdownEl) return [];

            const lines = parseModelList(vrmListEl.value, '.vrm');
            if (!lines.includes(currentVRMModelPath)) {
                currentVRMModelPath = lines[0] || '';
                try { localStorage.setItem(VRM_SELECTED_KEY, currentVRMModelPath); } catch {}
            }

            setModelDropdownOptions(vrmDropdownEl, lines, currentVRMModelPath);

            if (currentVRMModelPath) {
                vrmDropdownEl.value = currentVRMModelPath;
            }
            return lines;
        }

        // Call scan endpoint and refresh discovered Live2D/VRM paths from model_avatar/
        async function scanAndMergeModelAvatarLists(options = {}) {
            const { silent = false } = options;
            const live2dListEl = document.getElementById('live2d-model-list');
            const vrmListEl = document.getElementById('vrm-model-list');
            if (!live2dListEl || !vrmListEl) return;
            const scanBtn = document.getElementById('scan-model-avatar-btn');
            if (scanBtn) {
                scanBtn.disabled = true;
                scanBtn.textContent = 'Scanning…';
            }
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/model-avatar/scan`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                if (!res.ok) {
                    const msg = res.status === 401
                        ? 'Scan failed. Sign in or start the server.'
                        : (res.statusText || 'Scan failed. Is the server running?');
                    if (!silent && typeof showToast === 'function') showToast(msg); else console.warn(msg);
                    return;
                }
                const data = await res.json();
                const scannedLive2d = Array.isArray(data.live2d) ? data.live2d : [];
                const scannedVrm = Array.isArray(data.vrm) ? data.vrm : [];
                const uniqueLive2d = [];
                const live2dSeen = new Set();
                scannedLive2d.forEach(path => {
                    const normalized = normalizeModelPath(path);
                    if (!normalized || live2dSeen.has(normalized)) return;
                    live2dSeen.add(normalized);
                    uniqueLive2d.push(path);
                });
                const uniqueVrm = [];
                const vrmSeen = new Set();
                scannedVrm.forEach(path => {
                    const normalized = normalizeModelPath(path);
                    if (!normalized || vrmSeen.has(normalized)) return;
                    vrmSeen.add(normalized);
                    uniqueVrm.push(path);
                });

                setModelListValue(live2dListEl, uniqueLive2d);
                setModelListValue(vrmListEl, uniqueVrm);
                syncLive2DModelControls();
                syncVRMModelControls();
                saveToolSettings();
                const feedback = (uniqueLive2d.length || uniqueVrm.length)
                    ? `Found ${uniqueLive2d.length} Live2D and ${uniqueVrm.length} VRM model(s).`
                    : 'No avatar models found in model_avatar.';
                if (!silent && typeof showToast === 'function') showToast(feedback); else console.log(feedback);
            } catch (err) {
                const msg = 'Scan failed. Is the server running?';
                if (!silent && typeof showToast === 'function') showToast(msg); else console.warn(msg, err);
            } finally {
                if (scanBtn) {
                    scanBtn.disabled = false;
                    scanBtn.textContent = 'Scan for new models';
                }
            }
        }

        // --- Companions UI: list from server, add modal, load/delete ---
        async function fetchCompanionsList() {
            const url = `${PROXY_BASE_URL}/v1/companions`;
            const res = await fetch(url, { headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) throw new Error(res.statusText || 'Failed to fetch companions');
            return res.json();
        }

        const DEFAULT_COMPANION_STORAGE_KEY = 'defaultCompanionId';

        function getStoredDefaultCompanionId() {
            try {
                const value = localStorage.getItem(DEFAULT_COMPANION_STORAGE_KEY);
                return value && value.trim() ? value.trim() : null;
            } catch (error) {
                console.warn('Could not read default companion from localStorage:', error);
                return null;
            }
        }

        function persistDefaultCompanionId(id) {
            try {
                if (id && String(id).trim()) localStorage.setItem(DEFAULT_COMPANION_STORAGE_KEY, String(id).trim());
                else localStorage.removeItem(DEFAULT_COMPANION_STORAGE_KEY);
            } catch (error) {
                console.warn('Could not persist default companion in localStorage:', error);
            }
        }

        let defaultCompanionId = getStoredDefaultCompanionId();
        let activeCompanionId = null;
        let activeCompanionName = '';
        let activeCompanionSignature = '';
        let companionHasUnsavedChanges = false;
        let latestSavedCompanionId = null;
        let latestSavedCompanionName = '';
        let latestSavedCompanionSignature = '';
        let activeToolSettingsPanelId = 'connection-settings-panel';

        function setDefaultCompanion(id, options = {}) {
            defaultCompanionId = id && String(id).trim() ? String(id).trim() : null;
            persistDefaultCompanionId(defaultCompanionId);
            if (options.render !== false) renderCompanionList();
            if (options.refreshDraft !== false) updateCompanionDraftUI(undefined, { syncDirtyState: false });
        }

        async function fetchCompanionRecord(id) {
            const url = `${PROXY_BASE_URL}/v1/companions/${encodeURIComponent(id)}`;
            const res = await fetch(url, { headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) {
                const detail = await res.text().catch(() => '');
                throw new Error(detail || res.statusText || 'Companion not found');
            }
            return res.json();
        }

        function setActiveToolSettingsPanel(panelId, options = {}) {
            const panels = Array.from(document.querySelectorAll('[data-tool-settings-panel]'));
            if (!panels.length) return;

            const nextPanel = panels.find((panel) => panel.id === panelId) || panels[0];
            activeToolSettingsPanelId = nextPanel.id;

            panels.forEach((panel) => {
                panel.classList.toggle('tool-settings-screen-active', panel.id === activeToolSettingsPanelId);
            });

            document.querySelectorAll('[data-tool-settings-target]').forEach((control) => {
                const isActive = control.getAttribute('data-tool-settings-target') === activeToolSettingsPanelId;
                control.classList.toggle('is-active', isActive);
                control.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });

            if (options.scrollIntoView) {
                nextPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        function showToolSettingsBuilderPanel(panelId = activeToolSettingsPanelId, options = {}) {
            const collapsible = document.querySelector('.collapsible');
            const content = collapsible && collapsible.querySelector('.collapsible-content');
            const btn = collapsible && collapsible.querySelector('.collapsible-btn');

            if (content && btn) {
                content.classList.add('active');
                btn.classList.add('active');
                btn.setAttribute('aria-expanded', 'true');
                if (options.expandScrollIntoView !== false) {
                    content.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }

            setActiveToolSettingsPanel(panelId, { scrollIntoView: options.scrollIntoView === true });
        }

        function setupToolSettingsBuilderUI() {
            const controls = Array.from(document.querySelectorAll('[data-tool-settings-target]'));
            if (!controls.length) return;

            controls.forEach((control) => {
                control.addEventListener('click', () => {
                    setActiveToolSettingsPanel(control.getAttribute('data-tool-settings-target'), { scrollIntoView: false });
                });
            });

            setActiveToolSettingsPanel(activeToolSettingsPanelId, { scrollIntoView: false });
        }

        function escapeHtml(value) {
            return String(value == null ? '' : value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function getSettingsSignature(settings) {
            try {
                return JSON.stringify(settings || {});
            } catch (error) {
                console.warn('Settings signature error:', error);
                return '';
            }
        }

        function getBasenameFromPath(path) {
            const normalized = String(path || '').trim().replace(/\\/g, '/');
            if (!normalized) return '';
            const segments = normalized.split('/').filter(Boolean);
            return segments.length ? segments[segments.length - 1] : normalized;
        }

        function truncateLabel(value, maxLength = 28) {
            const text = String(value || '').trim();
            if (!text || text.length <= maxLength) return text;
            return `${text.slice(0, maxLength - 1)}...`;
        }

        function getEndpointLabel(endpoint) {
            const raw = String(endpoint || '').trim();
            if (!raw) return '';
            try {
                const parsed = new URL(raw);
                if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') return 'Local endpoint';
                return truncateLabel(parsed.hostname, 24);
            } catch (error) {
                return truncateLabel(raw.replace(/^https?:\/\//i, ''), 24);
            }
        }

        function summarizeCompanionSettings(settings) {
            const safeSettings = (settings && typeof settings === 'object') ? settings : {};
            const assistant = String(safeSettings.assistantName || '').trim() || 'Assistant';
            const avatarMode = safeSettings.avatarMode === 'vrm' ? 'VRM' : 'Live2D';
            const avatarFile = getBasenameFromPath(
                safeSettings.avatarMode === 'vrm' ? safeSettings.vrmModel : safeSettings.live2dModel
            );
            const primaryModel = safeSettings.baseModel || safeSettings.toolModel || safeSettings.visionModel || '';
            const voiceLabel = safeSettings.ttsService === 'openai'
                ? (safeSettings.ttsVoice || safeSettings.ttsModel || 'OpenAI-compatible TTS')
                : 'Browser voice';
            const endpointLabel = getEndpointLabel(safeSettings.endpoint);
            const activeModes = [];
            if (safeSettings.webcamMode) activeModes.push('Webcam');
            if (safeSettings.clipboardMode) activeModes.push('Clipboard vision');
            if (safeSettings.muteMode) activeModes.push('Muted');

            const descriptionParts = [`${assistant} using ${avatarMode}`];
            if (avatarFile) descriptionParts.push(`avatar ${avatarFile}`);
            if (primaryModel) descriptionParts.push(`chat model ${truncateLabel(primaryModel, 24)}`);

            const tags = [];
            if (primaryModel) tags.push(`Chat ${truncateLabel(primaryModel, 24)}`);
            if (voiceLabel) tags.push(`Voice ${truncateLabel(voiceLabel, 22)}`);
            if (endpointLabel) tags.push(endpointLabel);
            tags.push(activeModes.length ? activeModes.join(' + ') : 'Standard chat');

            return {
                title: assistant,
                description: descriptionParts.join(' | '),
                tags
            };
        }

        function suggestCompanionName(settings) {
            const summary = summarizeCompanionSettings(settings);
            const primaryModel = String(settings?.baseModel || settings?.toolModel || settings?.visionModel || '').trim();
            const endpointLabel = getEndpointLabel(settings?.endpoint);
            const avatarFile = getBasenameFromPath(
                settings?.avatarMode === 'vrm' ? settings?.vrmModel : settings?.live2dModel
            ).replace(/\.[^.]+$/g, '');
            const detail = truncateLabel(primaryModel || endpointLabel || avatarFile || '', 22);
            return detail ? `${summary.title} ${detail}` : summary.title;
        }

        function renderCompanionTags(container, tags) {
            if (!container) return;
            const safeTags = Array.isArray(tags) ? tags.filter(Boolean) : [];
            container.innerHTML = safeTags
                .map((tag) => `<span class="companion-tag">${escapeHtml(tag)}</span>`)
                .join('');
        }

        function setCompanionFeedback(message = '', type = 'info') {
            const feedbackEl = document.getElementById('companion-feedback');
            if (!feedbackEl) return;
            feedbackEl.textContent = message;
            feedbackEl.classList.remove('is-error', 'is-success');
            if (type === 'error') feedbackEl.classList.add('is-error');
            if (type === 'success') feedbackEl.classList.add('is-success');
        }

        function updateCompanionDraftUI(optionalSettings, options = {}) {
            const settings = (optionalSettings && typeof optionalSettings === 'object')
                ? optionalSettings
                : getToolSettingsFromDOM();
            const summary = summarizeCompanionSettings(settings);
            const currentSignature = getSettingsSignature(settings);
            const previousDirtyState = companionHasUnsavedChanges;
            const isDefaultActiveCompanion = Boolean(activeCompanionId && activeCompanionId === defaultCompanionId);

            if (options.syncDirtyState !== false && activeCompanionId && activeCompanionSignature) {
                companionHasUnsavedChanges = currentSignature !== activeCompanionSignature;
            }

            const nameEl = document.getElementById('companion-current-name');
            const stateEl = document.getElementById('companion-current-state');
            const summaryEl = document.getElementById('companion-current-summary');
            const tagsEl = document.getElementById('companion-current-tags');
            const modalPreviewText = document.getElementById('companion-modal-preview-text');
            const modalTagsEl = document.getElementById('companion-modal-tags');

            if (nameEl) nameEl.textContent = summary.title;

            let stateLabel = 'Not saved';
            let summaryText = summary.description;

            if (activeCompanionId) {
                if (companionHasUnsavedChanges) {
                    stateLabel = isDefaultActiveCompanion ? 'Default with changes' : 'Unsaved changes';
                    summaryText = `${summary.description}. This no longer matches "${activeCompanionName || 'the active companion'}".`;
                    if (isDefaultActiveCompanion) {
                        summaryText += ' The saved default profile will still load when CATBot opens.';
                    }
                } else {
                    stateLabel = isDefaultActiveCompanion ? 'Default companion' : 'Active companion';
                    summaryText = `${summary.description}. Saved as "${activeCompanionName || summary.title}".`;
                    if (isDefaultActiveCompanion) {
                        summaryText += ' This profile loads automatically when CATBot opens.';
                    }
                }
            } else if (latestSavedCompanionSignature && currentSignature === latestSavedCompanionSignature) {
                stateLabel = 'Saved snapshot';
                summaryText = `${summary.description}. Saved as "${latestSavedCompanionName || summary.title}".`;
            }

            if (stateEl) stateEl.textContent = stateLabel;
            if (summaryEl) summaryEl.textContent = summaryText;
            renderCompanionTags(tagsEl, summary.tags);

            if (modalPreviewText) modalPreviewText.textContent = summary.description;
            renderCompanionTags(modalTagsEl, summary.tags);

            if (previousDirtyState !== companionHasUnsavedChanges && activeCompanionId) {
                renderCompanionList();
            }
        }

        function renderCompanionList() {
            const listEl = document.getElementById('companion-list');
            if (!listEl) return;
            listEl.innerHTML = '';
            fetchCompanionsList().then(companions => {
                if (!Array.isArray(companions) || companions.length === 0) {
                    listEl.innerHTML = '<li class="companion-empty-state">No saved companions yet. Save the current setup to reuse it later.</li>';
                    return;
                }
                const currentSignature = getSettingsSignature(getToolSettingsFromDOM());
                companions.forEach(c => {
                    const li = document.createElement('li');
                    li.setAttribute('data-companion-id', c.id);
                    const isActive = c.id === activeCompanionId;
                    const isDefault = c.id === defaultCompanionId;
                    if (isActive) li.classList.add('companion-active');
                    if (isActive && companionHasUnsavedChanges) li.classList.add('companion-active-dirty');
                    if (isDefault) li.classList.add('companion-default');

                    const copy = document.createElement('div');
                    copy.className = 'companion-list-copy';

                    const nameSpan = document.createElement('span');
                    nameSpan.textContent = c.name || c.id;
                    nameSpan.className = 'companion-name';
                    copy.appendChild(nameSpan);

                    const subtitle = document.createElement('span');
                    subtitle.className = 'companion-subtitle';
                    if (isDefault && isActive && companionHasUnsavedChanges) subtitle.textContent = 'Default companion with unsaved changes';
                    else if (isDefault && isActive) subtitle.textContent = 'Default companion';
                    else if (isDefault) subtitle.textContent = 'Loads automatically when CATBot opens';
                    else if (isActive && companionHasUnsavedChanges) subtitle.textContent = 'Active companion with unsaved changes';
                    else if (isActive) subtitle.textContent = 'Active companion';
                    else if (!activeCompanionId && c.id === latestSavedCompanionId && currentSignature === latestSavedCompanionSignature) subtitle.textContent = 'Matches the current setup';
                    else subtitle.textContent = 'Click to load this setup';
                    copy.appendChild(subtitle);

                    li.appendChild(copy);
                    const actions = document.createElement('div');
                    actions.className = 'companion-list-actions';

                    const defaultBtn = document.createElement('button');
                    defaultBtn.type = 'button';
                    defaultBtn.className = 'companion-default-btn';
                    defaultBtn.setAttribute('aria-label', isDefault ? 'Clear default companion' : 'Set as default companion');
                    defaultBtn.title = isDefault
                        ? `Clear "${c.name || c.id}" as the default companion`
                        : `Set "${c.name || c.id}" as the default companion`;
                    if (isDefault) defaultBtn.classList.add('is-default');
                    defaultBtn.innerHTML = isDefault
                        ? '<i class="fas fa-star"></i><span>Default</span>'
                        : '<i class="far fa-star"></i><span>Set default</span>';
                    defaultBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (isDefault) {
                            setDefaultCompanion(null);
                            setCompanionFeedback(`Cleared "${c.name || c.id}" as the default companion.`, 'success');
                        } else {
                            setDefaultCompanion(c.id);
                            setCompanionFeedback(`"${c.name || c.id}" will load automatically when CATBot opens.`, 'success');
                        }
                    });
                    actions.appendChild(defaultBtn);

                    const delBtn = document.createElement('button');
                    delBtn.type = 'button';
                    delBtn.className = 'companion-delete-btn';
                    delBtn.setAttribute('aria-label', 'Delete companion');
                    delBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
                    delBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteCompanion(c.id, c.name || c.id).catch((error) => {
                            console.warn('Delete companion failed:', error);
                            setCompanionFeedback(`Failed to delete companion: ${error.message}`, 'error');
                        });
                    });
                    actions.appendChild(delBtn);
                    li.appendChild(actions);
                    listEl.appendChild(li);
                });
            }).catch(err => {
                console.warn('Companions list failed:', err);
                listEl.innerHTML = '<li class="companion-empty-state">Unable to load companions</li>';
            });
        }

        async function loadCompanion(id) {
            const data = await fetchCompanionRecord(id);
            if (data.settings) {
                applyToolSettingsToDOM(data.settings);
                await fetchAvailableModels(data.settings);
                activeCompanionId = id;
                activeCompanionName = data.name || id;
                activeCompanionSignature = getSettingsSignature(getToolSettingsFromDOM());
                companionHasUnsavedChanges = false;
                latestSavedCompanionId = id;
                latestSavedCompanionName = data.name || id;
                latestSavedCompanionSignature = activeCompanionSignature;
                saveToolSettings({ syncDirtyState: false });
                updateCompanionDraftUI(data.settings, { syncDirtyState: false });
                renderCompanionList();
                setCompanionFeedback(`Loaded companion "${activeCompanionName}".`, 'success');
            }
        }

        async function deleteCompanion(id, name) {
            if (!window.confirm(`Delete companion "${name || id}"?`)) return;
            const url = `${PROXY_BASE_URL}/v1/companions/${encodeURIComponent(id)}`;
            const res = await fetch(url, { method: 'DELETE', headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) throw new Error(res.statusText || 'Delete failed');
            if (activeCompanionId === id) {
                activeCompanionId = null;
                activeCompanionName = '';
                activeCompanionSignature = '';
                companionHasUnsavedChanges = false;
            }
            if (latestSavedCompanionId === id) {
                latestSavedCompanionId = null;
                latestSavedCompanionName = '';
                latestSavedCompanionSignature = '';
            }
            if (defaultCompanionId === id) {
                setDefaultCompanion(null, { render: false, refreshDraft: false });
            }
            renderCompanionList();
            updateCompanionDraftUI(undefined, { syncDirtyState: false });
            setCompanionFeedback(`Deleted companion "${name || id}".`, 'success');
        }

        function setupCompanionsUI() {
            const listEl = document.getElementById('companion-list');
            const addBtn = document.getElementById('companion-add-btn');
            const modalOverlay = document.getElementById('companion-modal-overlay');
            const nameInput = document.getElementById('companion-name-input');
            const saveBtn = document.getElementById('companion-modal-save');
            const cancelBtn = document.getElementById('companion-modal-cancel');
            const activateCheckbox = document.getElementById('companion-activate-checkbox');
            const modalError = document.getElementById('companion-modal-error');
            if (!listEl || !addBtn || !modalOverlay || !saveBtn || !cancelBtn) return;

            function openToolSettingsPanel(targetPanelId = activeToolSettingsPanelId, options = {}) {
                showToolSettingsBuilderPanel(targetPanelId, options);
            }

            function setModalError(message) {
                if (!modalError) return;
                modalError.textContent = message || '';
            }

            function updateSaveState() {
                if (!saveBtn) return;
                saveBtn.disabled = !nameInput || !nameInput.value.trim();
            }

            // Click on list item (excluding delete button): load companion
            listEl.addEventListener('click', (e) => {
                const t = e.target && e.target.nodeType === 1 ? e.target : e.target && e.target.parentNode;
                const li = t && t.closest ? t.closest('li[data-companion-id]') : null;
                if (!li || (t && t.closest && t.closest('.companion-delete-btn'))) return;
                const id = li.getAttribute('data-companion-id');
                if (id) {
                    loadCompanion(id).catch(err => {
                        console.warn('Load companion failed:', err);
                        setCompanionFeedback(`Failed to load companion: ${err.message}`, 'error');
                    });
                }
            });

            addBtn.addEventListener('click', () => {
                const settings = getToolSettingsFromDOM();
                openToolSettingsPanel(activeToolSettingsPanelId, { expandScrollIntoView: false });
                if (nameInput) nameInput.value = suggestCompanionName(settings);
                if (activateCheckbox) activateCheckbox.checked = true;
                setModalError('');
                updateCompanionDraftUI(settings, { syncDirtyState: false });
                updateSaveState();
                modalOverlay.style.display = 'flex';
                modalOverlay.setAttribute('aria-hidden', 'false');
                if (nameInput) nameInput.focus();
            });

            function closeCompanionModal() {
                modalOverlay.style.display = 'none';
                modalOverlay.setAttribute('aria-hidden', 'true');
                setModalError('');
            }

            cancelBtn.addEventListener('click', closeCompanionModal);
            modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeCompanionModal(); });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && modalOverlay.style.display !== 'none') closeCompanionModal();
            });

            if (nameInput) {
                nameInput.addEventListener('input', () => {
                    updateSaveState();
                    setModalError('');
                });
                nameInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !saveBtn.disabled) {
                        e.preventDefault();
                        saveBtn.click();
                    }
                });
            }

            const editSettingsLink = document.getElementById('companion-edit-settings-link');
            if (editSettingsLink) {
                editSettingsLink.addEventListener('click', () => {
                    closeCompanionModal();
                    openToolSettingsPanel(activeToolSettingsPanelId, { scrollIntoView: true });
                });
            }

            saveBtn.addEventListener('click', async () => {
                const name = (nameInput && nameInput.value || '').trim();
                if (!name) {
                    setModalError('Give this companion a name before saving.');
                    return;
                }
                const settings = getToolSettingsFromDOM();
                saveBtn.disabled = true;
                setModalError('');
                try {
                    const res = await fetch(`${PROXY_BASE_URL}/v1/companions`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${authToken}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ name, settings })
                    });
                    if (!res.ok) throw new Error(await res.text() || 'Save failed');
                    const created = await res.json();
                    latestSavedCompanionId = created.id;
                    latestSavedCompanionName = created.name || name;
                    latestSavedCompanionSignature = getSettingsSignature(settings);
                    if (!activateCheckbox || activateCheckbox.checked) {
                        activeCompanionId = created.id;
                        activeCompanionName = created.name || name;
                        activeCompanionSignature = latestSavedCompanionSignature;
                        companionHasUnsavedChanges = false;
                    }
                    saveToolSettings({ syncDirtyState: false });
                    updateCompanionDraftUI(settings, { syncDirtyState: false });
                    closeCompanionModal();
                    renderCompanionList();
                    setCompanionFeedback(
                        !activateCheckbox || activateCheckbox.checked
                            ? `Saved and activated companion "${created.name || name}".`
                            : `Saved companion "${created.name || name}".`,
                        'success'
                    );
                } catch (err) {
                    console.warn('Save companion failed:', err);
                    setModalError(err.message || 'Could not save the companion.');
                    setCompanionFeedback(`Failed to save companion: ${err.message}`, 'error');
                } finally {
                    updateSaveState();
                }
            });

            renderCompanionList();
            updateCompanionDraftUI(undefined, { syncDirtyState: false });
            updateSaveState();
        }

        // Function to setup event listeners for persisting tool settings
        function setupToolSettingsPersistence() {
            // Add change event listeners to User Name and Assistant Name inputs
            userNameInput.addEventListener('input', saveToolSettings);
            assistantNameInput.addEventListener('input', saveToolSettings);
            
            // Add change event listeners to other tool settings
            apiKeyInput.addEventListener('input', saveToolSettings);
            if (newsApiKeyInput) {
                newsApiKeyInput.addEventListener('input', saveToolSettings);
            }
            endpointInput.addEventListener('input', saveToolSettings);
            systemPromptInput.addEventListener('input', saveToolSettings);
            document.getElementById('webcam-toggle').addEventListener('change', saveToolSettings);
            document.getElementById('clipboard-toggle').addEventListener('change', saveToolSettings);
            document.getElementById('mute-toggle').addEventListener('change', saveToolSettings);
            
            // Add event listeners for TTS settings
            if (ttsServiceMicrosoft) {
                ttsServiceMicrosoft.addEventListener('change', () => {
                    saveToolSettings();
                    if (ttsServiceOpenAI.checked) fetchTtsVoices(); // Auto-fetch when switching to OpenAI-compatible
                });
            }
            if (ttsServiceOpenAI) {
                ttsServiceOpenAI.addEventListener('change', () => {
                    saveToolSettings();
                    if (ttsServiceOpenAI.checked) fetchTtsVoices(); // Auto-fetch when selecting OpenAI-compatible
                });
            }
            if (ttsEndpointInput) {
                ttsEndpointInput.addEventListener('input', saveToolSettings);
                ttsEndpointInput.addEventListener('change', () => {
                    if (ttsServiceOpenAI && ttsServiceOpenAI.checked) fetchTtsVoices(); // Auto-fetch when endpoint changes
                });
            }
            if (ttsModelDropdown) {
                ttsModelDropdown.addEventListener('change', () => {
                    saveToolSettings();
                    if (ttsServiceOpenAI && ttsServiceOpenAI.checked) fetchTtsVoices();
                });
            }
            if (ttsVoiceDropdown) ttsVoiceDropdown.addEventListener('change', saveToolSettings);
            
            // Add event listener for VRM version dropdown
            const vrmVersionDropdown = document.getElementById('vrm-version-dropdown');
            if (vrmVersionDropdown) {
                vrmVersionDropdown.addEventListener('change', async () => {
                    vrmVersion = vrmVersionDropdown.value; // Update global variable
                    saveToolSettings(); // Save the setting
                    // Reinitialize VRM if currently active
                    if (document.getElementById('vrm-mode') && document.getElementById('vrm-mode').checked && vrmModel) {
                        cleanupVRM();
                        await initVRM();
                    }
                });
            }
            
            // Add event listener for refresh button
            if (refreshTtsVoicesBtn) {
                refreshTtsVoicesBtn.addEventListener('click', fetchTtsVoices);
            }
            // Add event listener for scan model avatar button (discovers new Live2D/VRM under model_avatar/)
            const scanModelAvatarBtn = document.getElementById('scan-model-avatar-btn');
            if (scanModelAvatarBtn) {
                scanModelAvatarBtn.addEventListener('click', () => scanAndMergeModelAvatarLists());
            }

            window.addEventListener('pagehide', () => {
                saveToolSettings({ skipCompanionRefresh: true });
            });
            
            console.log('Tool settings persistence enabled');
        }

        function handleAuthInputKeydown(event) {
            if (event.key !== 'Enter' || event.isComposing) {
                return;
            }

            event.preventDefault();
            performAuth('login');
        }

        authUsernameInput?.addEventListener('keydown', handleAuthInputKeydown);
        authPasswordInput?.addEventListener('keydown', handleAuthInputKeydown);
        authLoginBtn?.addEventListener('click', () => performAuth('login'));
        authSignupBtn?.addEventListener('click', () => performAuth('signup'));
        authLogoutBtn?.addEventListener('click', async () => {
            try {
                await fetchProxyEndpoint('/v1/auth/logout', { method: 'POST' });
            } catch (error) {
                console.warn('Logout cookie clear request failed:', error);
            }
            setAuthToken('');
            showAuthOverlay('Logged out.');
        });

        // Replace the document load event listener
        document.addEventListener('DOMContentLoaded', async function() {
            try {
                const isAuthenticated = await verifyExistingAuth();
                if (!isAuthenticated) {
                    return;
                }

                await runAppInitialization();
            } catch (error) {
                console.error('Error during initialization:', error);
            }

        });








        // Debounce function to limit server sync frequency
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }















        // Initialize audio recording using Web Audio API and AudioWorkletNode
        async function initAudioRecording() {
            try {
                // Get getUserMedia function with fallback for legacy browsers
                let getUserMedia;
                if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    // Use standard modern API
                    getUserMedia = (constraints) => navigator.mediaDevices.getUserMedia(constraints);
                } else {
                    // Check for legacy getUserMedia support
                    const legacyGetUserMedia = navigator.getUserMedia || 
                                              navigator.webkitGetUserMedia || 
                                              navigator.mozGetUserMedia || 
                                              navigator.msGetUserMedia;
                    
                    if (!legacyGetUserMedia) {
                        throw new Error('getUserMedia is not supported in this browser. Please use a modern browser with microphone access support.');
                    }
                    
                    // Wrap legacy API in Promise
                    getUserMedia = (constraints) => {
                        return new Promise((resolve, reject) => {
                            legacyGetUserMedia.call(navigator, constraints, resolve, reject);
                        });
                    };
                }
                
                // Request microphone access
                const stream = await getUserMedia({ audio: true });
                
                // Create audio context
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                mediaStreamSource = audioContext.createMediaStreamSource(stream);

                // Load the audio worklet module
                await audioContext.audioWorklet.addModule('recorder-worklet-processor.js');

                // Create recorder node
                recorderNode = new AudioWorkletNode(audioContext, 'recorder-worklet');
                recorderNode.port.onmessage = (event) => {
                    const inputData = event.data;
                    // Log audio chunk info (but limit frequency to avoid console spam)
                    if (audioData.length % 100 === 0) {
                        console.log('Received audio data chunk:', inputData.length, 'samples (total chunks:', audioData.length + 1, ')');
                    }
                    // Store the audio data chunk
                    audioData.push(new Float32Array(inputData));
                };

                // Initialize the record button state
                startRecordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
                startRecordBtn.title = "Start Recording";
                console.log('Audio recording initialized successfully');
            } catch (error) {
                console.error('Unable to access microphone:', error);
                // Only show alert if the error is not about unsupported browser
                if (!error.message.includes('not supported')) {
                    alert('Unable to access microphone: ' + error.message);
                } else {
                    console.warn('Microphone access not available. Recording feature will be disabled.');
                }
            }
        }

        // Update these two event listeners
        startRecordBtn.addEventListener('click', async function() { // Handle record button click
            await resumeAudioContextOnce(); // Resume audio context on first user action (for autoplay and lip sync)
            toggleRecording(); // Toggle recording state
        }); // End record button click handler

        document.addEventListener('keydown', async (e) => { // Handle keyboard shortcuts
            if (e.key === ';' && !e.repeat && !isRecording) { // Check for semicolon key (recording shortcut)
                e.preventDefault(); // Prevent semicolon from being typed
                await resumeAudioContextOnce(); // Resume audio context on first user action (for autoplay and lip sync)
                toggleRecording(); // Toggle recording state
            } // End semicolon key check
        });

        document.addEventListener('keyup', (e) => {
            if (e.key === ';' && isRecording) {
                e.preventDefault(); // Prevent semicolon from being typed
                toggleRecording();
            }
        });

        // Add this simple toggle function
        function toggleRecording() {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        }

        // Update the startRecording function
        function startRecording() {
            if (!isRecording && recorderNode && audioContext) {
                // Cancel any ongoing speech
                speechSynthesis.cancel();
                
                // Reset Live2D model expression
                if (live2dModel) {
                    live2dModel.expression(null);
                    // Reset head position
                    live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleX', 0);
                    live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleY', 0);
                    live2dModel.internalModel.coreModel.setParameterValueById('ParamAngleZ', 0);
                    live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
                }

                // Clear previous recordings
                audioData = [];
                
                // Clear the text areas (keep message history intact)
                userInput.value = '';
                syncUserInputUi();
                responseOutput.value = '';
                // clearMessageHistory(); // Commented out to preserve chat history when using STT

                // Connect the nodes and start recording
                // Connect mediaStreamSource to recorderNode to capture audio
                mediaStreamSource.connect(recorderNode);
                // Note: recorderNode is NOT connected to destination to avoid audio feedback loop
                // The audio is only captured, not played back through speakers
                
                // Update UI
                startRecordBtn.innerHTML = '<i class="fas fa-stop"></i>';
                startRecordBtn.title = "Stop Recording";
                status.textContent = "Recording...";
                isRecording = true;
                console.log("Recording started");
            }
        }

        // Update the stopRecording function
        function stopRecording() {
            // Check if we're actually recording and have required nodes
            if (!isRecording || !recorderNode || !audioContext) {
                // Not recording or missing required nodes, reset state and exit
                isRecording = false;
                startRecordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
                startRecordBtn.title = "Start Recording";
                return; // Exit early if not in valid recording state
            }
            
            // Safely disconnect audio nodes with error handling
            try {
                // Disconnect mediaStreamSource if it exists and is connected
                if (mediaStreamSource) {
                    try {
                        mediaStreamSource.disconnect();
                    } catch (disconnectError) {
                        // Node may already be disconnected, log but continue
                        console.warn('MediaStreamSource disconnect warning:', disconnectError.message);
                    }
                }
                
                // Disconnect recorderNode if it exists and is connected
                if (recorderNode) {
                    try {
                        recorderNode.disconnect();
                    } catch (disconnectError) {
                        // Node may already be disconnected, log but continue
                        console.warn('RecorderNode disconnect warning:', disconnectError.message);
                    }
                }
            } catch (error) {
                // Log any unexpected errors during disconnection
                console.error('Error during audio node disconnection:', error);
            }
            
            // Update UI
            startRecordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
            startRecordBtn.title = "Start Recording";
            status.textContent = "Processing recording...";
            
            // Set recording state to false BEFORE processing the audio
            isRecording = false;
            
            // Process the recorded audio if we have data
            if (audioData.length > 0) {
                processAudioData();
            } else {
                status.textContent = "No audio recorded";
            }
        }

        function processAudioData() {
            // Validate audioContext exists before processing
            if (!audioContext || !audioContext.sampleRate) {
                // Audio context is missing or invalid, show error and exit
                console.error('Audio context is not available for processing');
                status.textContent = "Processing failed: Audio context unavailable. Please try recording again.";
                audioData = []; // Clear audio data
                return; // Exit early if audio context is invalid
            }
            
            // Flatten the audio data
            let flatData = flattenArray(audioData);
            
            // Validate that we have meaningful audio data
            console.log('Audio data chunks:', audioData.length);
            console.log('Total samples:', flatData.length);
            console.log('Sample rate:', audioContext.sampleRate);
            const durationSeconds = flatData.length / audioContext.sampleRate;
            console.log('Recording duration:', durationSeconds.toFixed(2), 'seconds');
            
            // Check if recording is too short (less than 0.5 seconds)
            if (durationSeconds < 0.5) {
                console.error('Recording is too short:', durationSeconds, 'seconds');
                status.textContent = "Recording too short. Please speak for at least 0.5 seconds.";
                audioData = []; // Clear audio data
                return; // Exit early if recording is too short
            }
            
            // Check if audio is mostly silence (very low amplitude)
            let maxAmplitude = 0;
            let sumAmplitude = 0;
            for (let i = 0; i < flatData.length; i++) {
                const absValue = Math.abs(flatData[i]);
                maxAmplitude = Math.max(maxAmplitude, absValue);
                sumAmplitude += absValue;
            }
            const avgAmplitude = sumAmplitude / flatData.length;
            console.log('Max amplitude:', maxAmplitude.toFixed(4));
            console.log('Average amplitude:', avgAmplitude.toFixed(4));
            
            // If audio is too quiet (max amplitude less than 0.01), warn the user
            if (maxAmplitude < 0.01) {
                console.warn('Audio appears to be very quiet or silent');
                status.textContent = "Audio too quiet. Please speak louder or check your microphone.";
                audioData = []; // Clear audio data
                return; // Exit early if audio is too quiet
            }

            // Encode the data into WAV format using validated sample rate
            let wavBlob = encodeWAV(flatData, audioContext.sampleRate);
            
            // Log the blob size for debugging
            console.log('WAV blob size:', wavBlob.size, 'bytes');
            
            // Save the WAV file for testing/debugging (helps verify audio quality)
            // Uncomment the next line to enable automatic WAV file downloads for debugging
            // saveWAVFile(wavBlob);

            // Clear audioData for next recording
            audioData = [];

            // Send to Whisper
            sendAudioToWhisper(wavBlob);
        }
/*
function saveWAVFile(wavBlob) {
    const url = URL.createObjectURL(wavBlob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = 'test_recording.wav';
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
}
*/

        function encodeWAV(samples, sampleRate) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);

            /* RIFF identifier */
            writeString(view, 0, 'RIFF');
            /* file length */
            view.setUint32(4, 36 + samples.length * 2, true);
            /* RIFF type */
            writeString(view, 8, 'WAVE');
            /* format chunk identifier */
            writeString(view, 12, 'fmt ');
            /* format chunk length */
            view.setUint32(16, 16, true);
            /* sample format (PCM) */
            view.setUint16(20, 1, true);
            /* channel count */
            view.setUint16(22, 1, true);
            /* sample rate */
            view.setUint32(24, sampleRate, true);
            /* byte rate (sampleRate * blockAlign) */
            view.setUint32(28, sampleRate * 2, true);
            /* block align (channels * bytesPerSample) */
            view.setUint16(32, 2, true);
            /* bits per sample */
            view.setUint16(34, 16, true);
            /* data chunk identifier */
            writeString(view, 36, 'data');
            /* data chunk length */
            view.setUint32(40, samples.length * 2, true);

            // Convert Float32Array samples to 16-bit PCM
            floatTo16BitPCM(view, 44, samples);

            return new Blob([view], { type: 'audio/wav' });
        }

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        function floatTo16BitPCM(output, offset, input) {
            for (let i = 0; i < input.length; i++, offset += 2) {
                let s = Math.max(-1, Math.min(1, input[i]));
                output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            }
        }

        function flattenArray(channelData) {
            let length = channelData.reduce((acc, val) => acc + val.length, 0);
            let result = new Float32Array(length);
            let offset = 0;
            for (let data of channelData) {
                result.set(data, offset);
                offset += data.length;
            }
            return result;
        }

        async function sendAudioToWhisper(audioBlob) {
            // Use the proxy server endpoint which has CORS configured
            const whisperEndpoint = `${PROXY_BASE_URL}/v1/audio/transcriptions`;

            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');
            formData.append('model', 'whisper-1');

            try {
                console.log('Sending audio to Whisper...');
                const response = await fetch(whisperEndpoint, {
                    method: 'POST',
                    body: formData
                });
                
                // Check if response is successful before parsing JSON
                if (!response.ok) {
                    // Response is not OK, try to get error details
                    let errorMessage = `Transcription failed: Server returned ${response.status} ${response.statusText}`;
                    try {
                        // Try to parse error response for more details
                        const errorData = await response.json();
                        if (errorData.error && errorData.error.message) {
                            errorMessage = `Transcription failed: ${errorData.error.message}`;
                        } else if (errorData.message) {
                            errorMessage = `Transcription failed: ${errorData.message}`;
                        }
                    } catch (parseError) {
                        // If error response is not JSON, use status-based message
                        if (response.status === 401) {
                            errorMessage = "Transcription failed: sign in again or check the proxy transcription configuration.";
                        } else if (response.status === 404) {
                            errorMessage = "Transcription failed: Endpoint not found. Please check the server configuration.";
                        } else if (response.status >= 500) {
                            errorMessage = "Transcription failed: Server error. Please try again later.";
                        }
                    }
                    console.error('Whisper API error:', errorMessage);
                    status.textContent = errorMessage;
                    return; // Exit early on error
                }
                
                // Response is OK, parse JSON
                // Read response as text first so we can log it if JSON parsing fails
                let responseText;
                let data;
                try {
                    // Read the response body as text first (can only be read once)
                    responseText = await response.text();
                    // Try to parse the text as JSON
                    data = JSON.parse(responseText);
                } catch (jsonError) {
                    // JSON parsing failed - log the raw response text for debugging
                    console.error('Failed to parse Whisper response as JSON:', jsonError);
                    console.error('Raw response text:', responseText || 'Unable to read response');
                    status.textContent = "Transcription failed: Invalid server response format. Please try again.";
                    return;
                }
                
                console.log('Whisper response:', data);
                
                // Check for different possible response formats
                let transcribedText = null;
                if (data.text) {
                    // Standard format: { text: "transcribed text" }
                    transcribedText = data.text;
                } else if (data.transcription) {
                    // Alternative format: { transcription: "transcribed text" }
                    transcribedText = data.transcription;
                } else if (typeof data === 'string') {
                    // Response might be a plain string
                    transcribedText = data;
                } else if (data.result && data.result.text) {
                    // Nested format: { result: { text: "transcribed text" } }
                    transcribedText = data.result.text;
                }
                
                if (transcribedText) {
                    // Trim the transcribed text
                    transcribedText = transcribedText.trim();
                    console.log('Transcribed text extracted:', transcribedText); // Debug log to see what was transcribed
                    
                    // Validate that we have actual transcribed text (not empty or just whitespace)
                    if (!transcribedText || transcribedText.length === 0) {
                        console.error('Transcribed text is empty after trimming');
                        status.textContent = "Transcription failed: No text was transcribed. Please try again.";
                        return;
                    }
                    
                    // Set the input field with the transcribed text
                    userInput.value = transcribedText + ' ';
                    status.textContent = "Transcription successful.";
                    
                    // Send the transcribed text to OpenAI
                    // Note: fetchOpenAIResponse will add the message to chat history
                    console.log('Calling fetchOpenAIResponse with transcribed text:', transcribedText); // Debug log
                    fetchOpenAIResponse(transcribedText);
                    userInput.value = ''; // Clear input field after submission
                    syncUserInputUi();
                } else {
                    // Response format is unexpected - log the full response for debugging
                    console.error('Unexpected response format - no text field found:', data);
                    console.error('Response keys:', Object.keys(data));
                    status.textContent = "Transcription failed: Unexpected response format. Please check console for details.";
                }
            } catch (error) {
                // Handle network errors and other exceptions
                let errorMessage = "Transcription failed. Please try again.";
                if (error instanceof TypeError && error.message.includes('fetch')) {
                    // Network error (e.g., server unreachable)
                    errorMessage = "Transcription failed: Unable to connect to server. Please check your connection and server status.";
                } else if (error instanceof SyntaxError) {
                    // JSON parsing error
                    errorMessage = "Transcription failed: Invalid server response. Please try again.";
                } else {
                    // Other errors
                    errorMessage = `Transcription failed: ${error.message || 'Unknown error'}. Please try again.`;
                }
                console.error('Error with OpenAI Whisper request:', error);
                status.textContent = errorMessage;
            }
        }

        // Replace the existing expressionKeywords object with:
        const expressionKeywords = {
            'Love eye': ['happy', 'joy', 'glad', 'excited', 'wonderful', 'love', 'lovely', 'delighted', 'delight', 'romantic'],
            'cry': ['sad', 'upset', 'sorry', 'disappointed', 'unhappy', 'crying', 'cry'],
            'black face': ['surprised', 'surprise', 'shocked', 'shock', 'amazed', 'wow', 'whoa', 'unexpected', 'harsh', 'angry', 'mad', 'upset', 'furious', 'annoyed'],
            'Milk Tea': ['thinking', 'consider', 'perhaps', 'maybe', 'hmm', 'interesting', 'curious', 'thinking', 'think', 'think about', 'thinking about it', 'think about it']
        };

        // Update the detectExpressionFromText function:
        function detectExpressionFromText(text) {
            const lowercaseText = text.toLowerCase();
            console.log('Analyzing text for expressions:', lowercaseText);
            
            for (const [expression, keywords] of Object.entries(expressionKeywords)) {
                console.log(`Checking keywords for ${expression}:`, keywords);
                if (keywords.some(keyword => {
                    const found = lowercaseText.includes(keyword);
                    if (found) console.log(`Found keyword: ${keyword}`);
                    return found;
                })) {
                    console.log(`Expression match found: ${expression}`);
                    // Match the exact expression file names from the model
                    switch(expression) {
                        case 'Love eye':
                            return 'love';  // Use the Name from model3.json
                        case 'cry':
                            return 'cry';   // Use the Name from model3.json
                        case 'black face':
                            return 'black_face';  // Use the Name from model3.json
                        case 'Milk Tea':
                            return 'milk_tea';    // Use the Name from model3.json
                    }
                }
            }
            
            console.log('No expression match found, returning null to reset to default');
            return null;  // Explicitly return null when no expression is found
        }

        // Add this before the tools declaration
        // Storage wrapper
        const storage = {
            data: new Map(),
            isAvailable: false,
            
            init() {
                try {
                    localStorage.setItem('test', 'test');
                    localStorage.removeItem('test');
                    this.isAvailable = true;
                } catch (e) {
                    console.warn('localStorage not available, using in-memory storage');
                    this.isAvailable = false;
                }
            },

            setItem(key, value) {
                if (this.isAvailable) {
                    try {
                        localStorage.setItem(key, value);
                    } catch (e) {
                        console.warn('Error saving to localStorage:', e);
                        this.data.set(key, value);
                    }
                } else {
                    this.data.set(key, value);
                }
            },

            getItem(key) {
                if (this.isAvailable) {
                    try {
                        return localStorage.getItem(key);
                    } catch (e) {
                        console.warn('Error reading from localStorage:', e);
                        return this.data.get(key) || null;
                    }
                }
                return this.data.get(key) || null;
            }
        };

        // Initialize storage
        storage.init();

        // Storage helper functions (saveTodoList used only when not using backend todo API)
        function saveTodoList() {
            storage.setItem('todoList', JSON.stringify(todoList));
        }

        // Fetch todo list from backend when authenticated; otherwise keep empty or localStorage fallback
        async function fetchTodoListFromServer() {
            if (!authToken) {
                try {
                    const saved = storage.getItem('todoList');
                    if (saved) todoList = JSON.parse(saved);
                    else todoList = [];
                } catch (e) {
                    todoList = [];
                }
                todoTaskItems = [];
                return;
            }
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/todo`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    todoList = Array.isArray(data.tasks) ? data.tasks : [];
                    todoTaskItems = Array.isArray(data.taskItems) ? data.taskItems : [];
                } else {
                    todoList = [];
                    todoTaskItems = [];
                }
            } catch (err) {
                console.warn('Failed to fetch todo list from server:', err);
                todoList = [];
                todoTaskItems = [];
            }
        }

        function saveMemory() {
            storage.setItem('memoryCache', JSON.stringify(memoryCache));
        }

        // Initialize variables
        let todoList = [];
        let todoTaskItems = [];
        let memoryCache = [];
        let isToolRequest = false;
        let chatHistory = [];  // Single declaration of chatHistory
        const MODEL_HISTORY_MAX_MESSAGES = 14;
        const MODEL_HISTORY_MAX_CHARS = 12000;
        const MODEL_MESSAGE_MAX_CHARS = 2500;
        const CHAT_REQUEST_TIMEOUT_MS = 1800000;
        let activeChatRequest = null;

        function buildModelHistoryWindow() {
            if (!Array.isArray(chatHistory) || chatHistory.length === 0) {
                return [];
            }

            const bounded = [];
            let totalChars = 0;
            for (let i = chatHistory.length - 1; i >= 0; i -= 1) {
                if (bounded.length >= MODEL_HISTORY_MAX_MESSAGES) break;

                const msg = chatHistory[i];
                if (!msg || (msg.role !== 'user' && msg.role !== 'assistant')) continue;

                let content = typeof msg.content === 'string' ? msg.content.trim() : '';
                if (!content) continue;
                if (content.length > MODEL_MESSAGE_MAX_CHARS) {
                    content = `${content.slice(0, MODEL_MESSAGE_MAX_CHARS)}\n[message truncated]`;
                }

                if ((totalChars + content.length > MODEL_HISTORY_MAX_CHARS) && bounded.length > 0) {
                    break;
                }

                totalChars += content.length;
                bounded.push({ role: msg.role, content: content });
            }

            return bounded.reverse();
        }

        function setChatRequestUiLocked(locked) {
            if (sendBtn) sendBtn.disabled = locked;
            if (sendBtnMobile) sendBtnMobile.disabled = locked;
        }

        // Conversation Management System
        let conversations = []; // Array to store all conversations
        let activeConversationId = null; // ID of the currently active conversation
        const CONVERSATIONS_STORAGE_KEY = 'conversations'; // Key for localStorage
        const ACTIVE_CONVERSATION_STORAGE_KEY = 'activeConversationId'; // Key for active conversation ID

        // Function to generate unique conversation ID
        function generateConversationId() {
            return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }

        // Function to create a new conversation
        function createNewConversation(title = null) {
            const newConversation = {
                id: generateConversationId(),
                title: title || 'New Conversation',
                messages: [], // Store the chat history for this conversation
                displayedMessages: [], // Store displayed messages for this conversation
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString()
            };
            conversations.push(newConversation);
            saveConversations();
            return newConversation;
        }

        // Function to save conversations to localStorage
        function saveConversations() {
            try {
                storage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations));
                storage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, activeConversationId);
                console.log('Conversations saved to localStorage:', {
                    conversationCount: conversations.length,
                    activeConversationId: activeConversationId,
                    activeConversationMessageCount: getActiveConversation()?.messages?.length || 0
                });
            } catch (error) {
                console.warn('Error saving conversations:', error);
            }
        }

        // Function to load conversations from localStorage
        function loadConversations() {
            try {
                const savedConversations = storage.getItem(CONVERSATIONS_STORAGE_KEY);
                const savedActiveId = storage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY);
                
                if (savedConversations) {
                    conversations = JSON.parse(savedConversations);
                }
                
                // If no conversations exist, create a default one
                if (conversations.length === 0) {
                    const firstConversation = createNewConversation('Welcome Chat');
                    activeConversationId = firstConversation.id;
                } else if (savedActiveId && conversations.find(c => c.id === savedActiveId)) {
                    activeConversationId = savedActiveId;
                } else {
                    activeConversationId = conversations[0].id;
                }
                
                // Skip timestamp update when loading from storage to preserve original timestamps
                switchToConversation(activeConversationId, true);
                renderConversationList();
            } catch (error) {
                console.warn('Error loading conversations:', error);
                const firstConversation = createNewConversation('Welcome Chat');
                activeConversationId = firstConversation.id;
                renderConversationList();
            }
        }

        // Function to get active conversation
        function getActiveConversation() {
            return conversations.find(c => c.id === activeConversationId);
        }

        // Function to switch to a different conversation
        function switchToConversation(conversationId, skipTimestampUpdate = false) {
            // Save current conversation's state before switching
            const currentConv = getActiveConversation();
            if (currentConv) {
                // Only update timestamp if messages actually changed and we're not skipping updates
                const messagesChanged = JSON.stringify(currentConv.messages) !== JSON.stringify(chatHistory) ||
                                      JSON.stringify(currentConv.displayedMessages) !== JSON.stringify(displayedMessages);
                
                currentConv.messages = [...chatHistory];
                currentConv.displayedMessages = [...displayedMessages];
                
                // Only update timestamp if messages actually changed and we're not skipping updates
                if (!skipTimestampUpdate && messagesChanged) {
                    currentConv.updatedAt = new Date().toISOString();
                }
            }
            
            // Switch to new conversation
            activeConversationId = conversationId;
            const newConv = getActiveConversation();
            
            if (newConv) {
                // Load the new conversation's history
                chatHistory = [...newConv.messages];
                displayedMessages = [...newConv.displayedMessages];
                
                // Update the UI using the existing render function
                renderMessageHistory();
                
                // Scroll to bottom
                messageHistory.scrollTop = messageHistory.scrollHeight;
            }
            
            saveConversations();
            renderConversationList();
        }

        // Function to delete a conversation
        function deleteConversation(conversationId) {
            const index = conversations.findIndex(c => c.id === conversationId);
            if (index !== -1) {
                conversations.splice(index, 1);
                
                // If we deleted the active conversation, switch to another one
                if (conversationId === activeConversationId) {
                    if (conversations.length === 0) {
                        const newConv = createNewConversation('New Chat');
                        activeConversationId = newConv.id;
                    } else {
                        activeConversationId = conversations[0].id;
                    }
                    switchToConversation(activeConversationId);
                }
                
                saveConversations();
                renderConversationList();
            }
        }

        // Function to rename a conversation
        function renameConversation(conversationId, newTitle) {
            const conv = conversations.find(c => c.id === conversationId);
            if (conv) {
                conv.title = newTitle || 'Untitled';
                conv.updatedAt = new Date().toISOString();
                saveConversations();
                renderConversationList();
            }
        }

        // Function to render the conversation list in the sidebar
        function renderConversationList() {
            // Get both desktop and mobile conversation lists
            const conversationList = document.getElementById('conversation-list');
            const conversationListMobile = document.getElementById('conversation-list-mobile');
            
            // Helper function to render to a specific list element
            const renderToElement = (listElement) => {
                if (!listElement) return;
                
                listElement.innerHTML = '';
                
                // Sort conversations by updated date (most recent first)
                const sortedConversations = [...conversations].sort((a, b) => 
                    new Date(b.updatedAt) - new Date(a.updatedAt)
                );
                
                sortedConversations.forEach(conv => {
                    const convItem = document.createElement('div');
                    convItem.className = 'conversation-item' + (conv.id === activeConversationId ? ' active' : '');
                    convItem.dataset.conversationId = conv.id;
                    
                    // Create title element
                    const titleDiv = document.createElement('div');
                    titleDiv.className = 'conversation-title';
                    titleDiv.textContent = conv.title;
                    
                    // Create date element
                    const dateDiv = document.createElement('div');
                    dateDiv.className = 'conversation-date';
                    const date = new Date(conv.updatedAt);
                    dateDiv.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    // Create actions container
                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'conversation-actions';
                    
                    // Rename button
                    const renameBtn = document.createElement('button');
                    renameBtn.className = 'rename-btn';
                    renameBtn.innerHTML = '<i class="fas fa-edit"></i> Rename';
                    renameBtn.onclick = (e) => {
                        e.stopPropagation();
                        const newTitle = prompt('Enter new title:', conv.title);
                        if (newTitle && newTitle.trim()) {
                            renameConversation(conv.id, newTitle.trim());
                        }
                    };
                    
                    // Delete button
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'delete-btn';
                    deleteBtn.innerHTML = '<i class="fas fa-trash"></i> Delete';
                    deleteBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (confirm('Are you sure you want to delete this conversation?')) {
                            deleteConversation(conv.id);
                        }
                    };
                    
                    // Add buttons to actions container
                    actionsDiv.appendChild(renameBtn);
                    actionsDiv.appendChild(deleteBtn);
                    
                    // Add click handler to switch conversation
                    convItem.addEventListener('click', function() {
                        switchToConversation(conv.id);
                        // Close mobile panel after switching
                        const overlay = document.getElementById('conversation-overlay');
                        const panel = document.getElementById('conversation-history-panel');
                        if (overlay && panel) {
                            overlay.classList.remove('active');
                            panel.classList.remove('active');
                        }
                    });
                    
                    // Append elements to conversation item
                    convItem.appendChild(titleDiv);
                    convItem.appendChild(dateDiv);
                    convItem.appendChild(actionsDiv);
                    
                    // Append conversation item to list
                    listElement.appendChild(convItem);
                });
            };
            
            // Render to both desktop and mobile lists if they exist
            renderToElement(conversationList);
            renderToElement(conversationListMobile);
            
            // Return early if neither list exists
            if (!conversationList && !conversationListMobile) {
                return;
            }
        }

        // Function to update active conversation when messages change
        function updateActiveConversationMessages() {
            // Ensure we have an active conversation - create one if it doesn't exist
            let activeConv = getActiveConversation();
            if (!activeConv) {
                console.log('No active conversation found, creating new one');
                // If no active conversation exists, create a new one
                if (activeConversationId === null || conversations.length === 0) {
                    activeConv = createNewConversation('New Conversation');
                    activeConversationId = activeConv.id;
                } else {
                    // Try to use the first conversation if activeConversationId is invalid
                    activeConversationId = conversations[0].id;
                    activeConv = getActiveConversation();
                }
            }
            
            if (activeConv) {
                // Update the conversation with current message state
                activeConv.messages = [...chatHistory];
                activeConv.displayedMessages = [...displayedMessages];
                activeConv.updatedAt = new Date().toISOString();
                
                console.log('Updating active conversation:', {
                    conversationId: activeConv.id,
                    messageCount: chatHistory.length,
                    displayedMessageCount: displayedMessages.length
                });
                
                // Auto-generate title from first user message if still "New Conversation"
                if (activeConv.title === 'New Conversation' && chatHistory.length > 0) {
                    const firstUserMsg = chatHistory.find(msg => msg.role === 'user');
                    if (firstUserMsg && firstUserMsg.content) {
                        const title = firstUserMsg.content.substring(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '');
                        activeConv.title = title;
                    }
                }
                
                // Save to localStorage
                saveConversations();
                renderConversationList();
            } else {
                console.warn('Could not create or find active conversation for message persistence');
            }
        }

        // Sidebar toggle functionality
        const SIDEBAR_STATE_KEY = 'conversationSidebarCollapsed';
        let sidebarCollapsed = false;

        // Function to toggle sidebar
        function toggleSidebar() {
            const sidebar = document.getElementById('conversation-sidebar');
            const toggleBtn = document.getElementById('sidebar-toggle-btn');
            // Return early if sidebar elements don't exist (e.g., in mobile version)
            if (!sidebar || !toggleBtn) {
                return;
            }
            const toggleIcon = toggleBtn.querySelector('i');
            
            sidebarCollapsed = !sidebarCollapsed;
            
            if (sidebarCollapsed) {
                sidebar.classList.add('collapsed');
                toggleBtn.classList.remove('sidebar-open');
                if (toggleIcon) {
                    toggleIcon.className = 'fas fa-chevron-right';
                }
            } else {
                sidebar.classList.remove('collapsed');
                toggleBtn.classList.add('sidebar-open');
                if (toggleIcon) {
                    toggleIcon.className = 'fas fa-chevron-left';
                }
            }
            
            // Save state to localStorage
            try {
                storage.setItem(SIDEBAR_STATE_KEY, sidebarCollapsed.toString());
            } catch (error) {
                console.warn('Error saving sidebar state:', error);
            }
        }

        // Function to load sidebar state
        function loadSidebarState() {
            try {
                const savedState = storage.getItem(SIDEBAR_STATE_KEY);
                if (savedState === 'true') {
                    sidebarCollapsed = false; // Set to false first so toggle works correctly
                    toggleSidebar(); // This will set it to true and apply the collapsed state
                }
            } catch (error) {
                console.warn('Error loading sidebar state:', error);
            }
        }

        // Right panel toggle functionality
        const RIGHT_PANEL_STATE_KEY = 'rightPanelCollapsed';
        let rightPanelCollapsed = false; // Default to open (accessible)

        // Function to toggle right panel
        function toggleRightPanel() {
            const rightColumn = document.getElementById('right-column');
            const toggleBtn = document.getElementById('right-panel-toggle-btn');
            const toggleIcon = toggleBtn.querySelector('i');
            
            rightPanelCollapsed = !rightPanelCollapsed;
            
            if (rightPanelCollapsed) {
                rightColumn.classList.add('collapsed');
                toggleBtn.classList.add('panel-closed');
                toggleIcon.className = 'fas fa-chevron-left'; // Point left to indicate it will expand from right
            } else {
                rightColumn.classList.remove('collapsed');
                toggleBtn.classList.remove('panel-closed');
                toggleIcon.className = 'fas fa-chevron-right'; // Point right to indicate it will collapse to right
            }
            
            // Save state to localStorage
            try {
                storage.setItem(RIGHT_PANEL_STATE_KEY, rightPanelCollapsed.toString());
            } catch (error) {
                console.warn('Error saving right panel state:', error);
            }
        }

        // Function to load right panel state
        function loadRightPanelState() {
            try {
                const savedState = storage.getItem(RIGHT_PANEL_STATE_KEY);
                // If there's a saved state and it's 'true' (panel should be collapsed), collapse it
                if (savedState === 'true') {
                    rightPanelCollapsed = false; // Set to false first so toggle works correctly
                    toggleRightPanel(); // This will set it to true and collapse the panel
                }
                // If no saved state or saved state is 'false', panel remains open (default)
            } catch (error) {
                console.warn('Error loading right panel state:', error);
            }
        }

        // Note: loadConversations() and event listeners are set up in DOMContentLoaded event

        try {
            const savedMemoryCache = storage.getItem('memoryCache');
            if (savedMemoryCache) {
                memoryCache = JSON.parse(savedMemoryCache);
            }
        } catch (error) {
            console.warn('Error loading from storage:', error);
        }
        // Todo list is loaded from backend (or localStorage fallback) in fetchTodoListFromServer when runAppInitialization runs

        // Replace the ToolManager with OpenAI-style tool definitions
        const baseTools = [
                {
                    type: "function",
                    function: {
                        name: "manageTodoList",
                        description: "Manages a persistent todo list with scheduling and repeating-task support (list, due, add, update, complete, delete, clear).",
                        parameters: {
                            type: "object",
                            properties: {
                                action: {
                                    type: "string",
                                    enum: ["list", "due", "add", "update", "complete", "delete", "clear"],
                                    description: "The action to perform on the todo list"
                                },
                                taskId: {
                                    type: "number",
                                    description: "The stable task ID (required for update, complete, and delete actions)"
                                },
                                taskDescription: {
                                    type: "string",
                                    description: "The description of the task (required for add and update actions)"
                                },
                                scheduledFor: {
                                    type: "string",
                                    description: "Optional scheduled datetime in ISO-8601 format (e.g. 2026-03-01T09:00:00-05:00)"
                                },
                                recurrence: {
                                    type: "object",
                                    description: "Optional recurrence rule for repeating tasks",
                                    properties: {
                                        frequency: {
                                            type: "string",
                                            enum: ["hourly", "daily", "weekly", "monthly", "yearly"]
                                        },
                                        interval: {
                                            type: "number",
                                            description: "Repeat every N frequency units (default 1)"
                                        }
                                    }
                                },
                                repeatFrequency: {
                                    type: "string",
                                    enum: ["hourly", "daily", "weekly", "monthly", "yearly"],
                                    description: "Alias for recurrence.frequency"
                                },
                                repeatInterval: {
                                    type: "number",
                                    description: "Alias for recurrence.interval"
                                },
                                clearSchedule: {
                                    type: "boolean",
                                    description: "When true (update action), remove existing schedule."
                                },
                                clearRecurrence: {
                                    type: "boolean",
                                    description: "When true (update action), remove recurrence."
                                }
                            },
                            required: ["action"]
                        }
                    }
                },
            {
                type: "function",
                function: {
                    name: "executeTodoTask",
                    description: "Start execution of a todo task by task ID. The backend runs a bounded LLM+tools loop (search, files, etc.) and supports multiple tasks in parallel. You MUST call this with taskId set to the task ID the user requested. If status is paused_awaiting_feedback, use resumeTodoExecution with the user's reply (and taskId when available). If status is awaiting_confirmation, use completeTodoTask to mark it done when the user confirms.",
                    parameters: {
                        type: "object",
                        properties: {
                            taskId: { type: "number", description: "Stable task ID (required)" },
                            promptOverride: { type: "string", description: "Optional goal for this run (e.g. 'research and compile a report on X')" }
                        },
                        required: ["taskId"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "resumeTodoExecution",
                    description: "Resume a paused task execution after the user has provided feedback. Call when executeTodoTask returned status 'paused_awaiting_feedback' and the user has replied with their input. Include taskId when more than one task may be paused.",
                    parameters: {
                        type: "object",
                        properties: {
                            userMessage: { type: "string", description: "The user's feedback or answer to continue the task" },
                            taskId: { type: "number", description: "Optional task ID to resume when multiple paused tasks exist" }
                        },
                        required: ["userMessage"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "completeTodoTask",
                    description: "Mark a todo task as complete (human-in-the-loop). One-time tasks are removed; repeating tasks are rescheduled. Call when executeTodoTask returned status 'awaiting_confirmation' and the user confirms they want to mark the task done.",
                    parameters: {
                        type: "object",
                        properties: {
                            taskId: { type: "number", description: "Stable task ID to mark complete (use the taskId from the execute response or todo list)" }
                        },
                        required: ["taskId"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "cancelTodoExecution",
                    description: "Cancel a running task execution. The task stays on the list. Provide taskId when multiple tasks are running in parallel.",
                    parameters: {
                        type: "object",
                        properties: {
                            taskId: { type: "number", description: "Optional task ID to cancel. Required when multiple tasks are running." }
                        },
                        required: []
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "uploadToGoogleDrive",
                    description: "Uploads a file from the scratch directory to Google Drive using service account authentication. The file must be in the scratch directory; use the filename relative to scratch (e.g. report.docx).",
                    parameters: {
                        type: "object",
                        properties: {
                            filePath: {
                                type: "string",
                                description: "Filename relative to the scratch directory (e.g. report.docx, climate_updates.csv). Do not use absolute paths or paths outside scratch."
                            },
                            fileName: {
                                type: "string",
                                description: "Optional custom name for the file in Drive (defaults to local filename)"
                            }
                        },
                        required: ["filePath"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "scrapeWebsite",
                    description: "Fetches and summarizes content from a website. Pass one url or multiple urls to try in order until one succeeds (scrape-with-retry). Supports JavaScript rendering for dynamic pages via render_js.",
                    parameters: {
                        type: "object",
                        properties: {
                            url: {
                                type: "string",
                                description: "Single URL to scrape (must include http:// or https://)"
                            },
                            urls: {
                                type: "array",
                                items: { type: "string" },
                                description: "Optional list of URLs to try in order; first successful fetch is returned (use after webSearch to retry on failure)"
                            },
                            render_js: {
                                type: "boolean",
                                description: "Optional. Enable JavaScript rendering for dynamic pages (Playwright/Selenium on proxy)."
                            },
                            render_engine: {
                                type: "string",
                                description: "Optional renderer: auto, playwright, or selenium."
                            },
                            wait_for_selector: {
                                type: "string",
                                description: "Optional CSS selector to wait for before extracting content."
                            },
                            js_wait_ms: {
                                type: "number",
                                description: "Optional extra wait time in milliseconds after page load for dynamic content."
                            }
                        }
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "fetchNews",
                    description: "Fetches news articles matching given keywords and saves them to a CSV file",
                    parameters: {
                        type: "object",
                        properties: {
                            searchTerm: {
                                type: "string",
                                description: "Keywords to search the news for (e.g., 'economy', 'climate change')"
                            },
                            filename: {
                                type: "string",
                                description: "CSV filename to save the articles to (e.g., 'news.csv')"
                            }
                        },
                        required: ["searchTerm", "filename"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "pdfToPowerPoint",
                    description: "Use this tool only when the user explicitly wants to convert a PDF or Markdown document into a PowerPoint or slide presentation. Do not use it for reviewing, summarizing, or extracting text from an attached file; use the filesystem read tool for that. Call it with title and filename; use source for structured inputs, or sourceUrl/pdfUrl for simple URL/path inputs. If the user did not provide a source, omit source, sourceUrl, and pdfUrl and the user will be prompted to upload a PDF or Markdown file.",
                    parameters: {
                        type: "object",
                        properties: {
                            source: {
                                type: "object",
                                description: "Optional structured source descriptor. Supports URL, scratch-relative path, uploaded attachment metadata, inline Markdown text, or base64 file content.",
                                properties: {
                                    type: {
                                        type: "string",
                                        enum: ["url", "path", "attachment", "inline", "file"],
                                        description: "Optional source locator kind."
                                    },
                                    value: {
                                        type: "string",
                                        description: "Generic source value. Use for a URL, scratch-relative path, or inline Markdown content."
                                    },
                                    url: {
                                        type: "string",
                                        description: "Optional source URL."
                                    },
                                    path: {
                                        type: "string",
                                        description: "Optional scratch-relative path."
                                    },
                                    relativePath: {
                                        type: "string",
                                        description: "Optional scratch-relative path for uploaded attachments."
                                    },
                                    content: {
                                        type: "string",
                                        description: "Optional inline Markdown content."
                                    },
                                    contentBase64: {
                                        type: "string",
                                        description: "Optional base64-encoded PDF or Markdown file content."
                                    },
                                    mimeType: {
                                        type: "string",
                                        description: "Optional MIME type for inline or base64 content."
                                    },
                                    filename: {
                                        type: "string",
                                        description: "Optional filename used for source-type detection."
                                    }
                                }
                            },
                            sourceUrl: {
                                type: "string",
                                description: "Optional. URL or scratch-relative path to the source document. Supports PDF and Markdown files."
                            },
                            sourceType: {
                                type: "string",
                                enum: ["pdf", "markdown"],
                                description: "Optional. Source document type. Use 'markdown' for .md/.markdown files. Omit to auto-detect when possible."
                            },
                            pdfUrl: {
                                type: "string",
                                description: "Optional legacy alias for a PDF URL or scratch-relative path. Prefer sourceUrl for new calls."
                            },
                            title: {
                                type: "string",
                                description: "Presentation title for the title slide (e.g. 'Quarterly Report')"
                            },
                            author: {
                                type: "string",
                                description: "Optional author name to show on the title slide"
                            },
                            maxSlides: {
                                type: "number",
                                description: "Optional maximum number of content slides (default: 15)"
                            },
                            filename: {
                                type: "string",
                                description: "Output .pptx filename (e.g. 'presentation.pptx')"
                            }
                        },
                        required: ["title", "filename"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "manageWorkingContext",
                    description: "Manages a persistent memory cache with various operations",
                    parameters: {
                        type: "object",
                        properties: {
                            action: {
                                type: "string",
                                enum: ["list", "add", "update", "delete", "clear"],
                                description: "The action to perform on the memory cache"
                            },
                            memId: {
                                type: "number",
                                description: "The ID of the memory cache item"
                            },
                            memDescription: {
                                type: "string",
                                description: "The description of the memory cache item"
                            }
                        },
                        required: ["action"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "storeMemory",
                    description: "Store important information about the user (preferences, habits, facts, needs, relationships) in the persistent embeddings-based memory system for future conversations",
                    parameters: {
                        type: "object",
                        properties: {
                            text: {
                                type: "string",
                                description: "The information to remember about the user"
                            },
                            category: {
                                type: "string",
                                enum: ["preference", "habit", "fact", "need", "relationship", "general"],
                                description: "Category of the memory (preference, habit, fact, need, relationship, or general)"
                            }
                        },
                        required: ["text"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "searchMemories",
                    description: "Search for relevant memories from previous conversations. Use this tool when the user asks you to recall, remember, or tell them what you know about something. Examples: 'what core insights have you made?', 'tell me what you know about the concept of consciousness', 'recall what you've contemplated recently'. Always use this tool before saying you don't have information. These are your own memories, not the user's.",
                    parameters: {
                        type: "object",
                        properties: {
                            query: {
                                type: "string",
                                description: "Search query to find relevant memories. Use topic keywords from the user's question (e.g., 'Laura', 'preferences', 'age', etc.)"
                            },
                            limit: {
                                type: "number",
                                description: "Maximum number of memories to retrieve (default: 5)"
                            }
                        },
                        required: ["query"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "listMemories",
                    description: "List recent memories stored in the embeddings-based memory system",
                    parameters: {
                        type: "object",
                        properties: {
                            limit: {
                                type: "number",
                                description: "Maximum number of memories to list (default: 10)"
                            }
                        }
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "deleteMemory",
                    description: "Delete a specific memory by its ID from the embeddings-based memory system",
                    parameters: {
                        type: "object",
                        properties: {
                            memory_id: {
                                type: "string",
                                description: "The ID of the memory to delete"
                            }
                        },
                        required: ["memory_id"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "navigateToUrl",
                    description: "Opens a URL in a new browser tab",
                    parameters: {
                        type: "object",
                        properties: {
                            url: {
                                type: "string",
                                description: "The URL to navigate to (must include https:// or http://)"
                            }
                        },
                        required: ["url"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "openChatToUser",
                    description: "Opens a Teams chat with specified user",
                    parameters: {
                        type: "object",
                        properties: {
                            url: {
                                type: "string",
                                description: "The Teams URL to open"
                            }
                        },
                        required: ["url"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "calculate",
                    description: "Performs basic mathematical calculations",
                    parameters: {
                        type: "object",
                        properties: {
                            expression: {
                                type: "string",
                                description: "The mathematical expression to evaluate",
                                pattern: "^[0-9+\\-*/\\s.()]+$"
                            }
                        },
                        required: ["expression"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "runWorkflow",
                    description: "Executes a workflow based on the provided prompt",
                    parameters: {
                        type: "object",
                        properties: {
                            contentPrompt: {
                                type: "string",
                                description: "The workflow prompt to execute"
                            }
                        },
                        required: ["contentPrompt"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "runCodexCli",
                    description: "Runs Codex CLI non-interactively to make CATBot code changes or add new tool capabilities. Provide a clear, self-contained prompt with the user's request, error text, and instructions to inspect the repository. Output is saved to a scratch summary file.",
                    parameters: {
                        type: "object",
                        properties: {
                            prompt: {
                                type: "string",
                                description: "Self-contained instructions for Codex to execute in the CATBot project (e.g. 'Fix this runcodexcli error: ... Search the repo, patch the bug, and run focused tests.')"
                            },
                            timeoutSeconds: {
                                type: "number",
                                description: "Optional timeout in seconds (default 1800, max 7200)"
                            }
                        },
                        required: ["prompt"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "restartProxyServer",
                    description: "Restarts the CATBot proxy server so newly added/updated tools become available. Use this after code/tool changes. Requires explicit confirmation.",
                    parameters: {
                        type: "object",
                        properties: {
                            confirm: {
                                type: "boolean",
                                description: "Must be true to confirm restart."
                            },
                            reason: {
                                type: "string",
                                description: "Optional short reason for restart (for logs)."
                            }
                        },
                        required: ["confirm"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "webSearch",
                    description: "Searches the web for information about a topic and returns relevant results",
                    parameters: {
                        type: "object",
                        properties: {
                            query: {
                                type: "string",
                                description: "The search query or keywords to look for"
                            }
                        },
                        required: ["query"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "weatherInfo",
                    description: "Gets weather information for a location from Open-Meteo. Use for current conditions, forecast, rain chance, and general weather summaries. If location is omitted, backend may use saved memory location.",
                    parameters: {
                        type: "object",
                        properties: {
                            location: {
                                type: "string",
                                description: "City/suburb/postcode (optional if user location is already known)"
                            },
                            requestType: {
                                type: "string",
                                enum: ["summary", "current", "forecast"],
                                description: "Type of weather response to retrieve"
                            }
                        }
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "runBrowserAgent",
                    description: "Executes browser automation tasks using natural language. Can navigate websites, fill forms, click buttons, extract information, and perform complex multi-step web interactions.",
                    parameters: {
                        type: "object",
                        properties: {
                            task: {
                                type: "string",
                                description: "Natural language description of the browser task to perform (e.g., 'Go to amazon.com and search for wireless headphones', 'Navigate to github.com and find the trending repositories')"
                            }
                        },
                        required: ["task"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "runDeepResearch",
                    description: "Performs comprehensive multi-step web research on a topic, gathering information from multiple sources and generating a detailed research report with citations and findings.",
                    parameters: {
                        type: "object",
                        properties: {
                            researchTask: {
                                type: "string",
                                description: "The research topic or question to investigate (e.g., 'What are the latest developments in quantum computing?', 'Compare the best electric vehicles available in 2024')"
                            },
                            maxParallelBrowsers: {
                                type: "number",
                                description: "Optional: Maximum number of parallel browser instances to use for faster research (default: 3, max: 5)"
                            }
                        },
                        required: ["researchTask"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "health_check",
                    description: "Checks browser-use server health and running background tasks. Use for status/progress/update questions about browser automation or deep research (e.g. still running, completed, current state).",
                    parameters: {
                        type: "object",
                        properties: {},
                        required: []
                    }
                }
            }
        ];

        const SKILL_TOOL_ALIAS_PREFIX = 'skill__';
        const SKILL_TOOL_CACHE_MS = 120000;
        const skillToolAliasToQualifiedName = new Map();
        let cachedSkillToolsForLlm = [];
        let cachedSkillPromptLines = [];
        let lastSkillToolFetchAt = 0;
        let skillToolsRefreshPromise = null;

        function createSkillToolAlias(qualifiedName, usedNames) {
            const safeCore = String(qualifiedName || '')
                .trim()
                .replace(/[^a-zA-Z0-9_-]/g, '_')
                .replace(/_+/g, '_')
                .replace(/^_+|_+$/g, '')
                .slice(0, 48) || 'tool';
            let alias = `${SKILL_TOOL_ALIAS_PREFIX}${safeCore}`.slice(0, 64);
            let suffix = 2;
            while (usedNames.has(alias)) {
                const candidate = `${SKILL_TOOL_ALIAS_PREFIX}${safeCore}_${suffix}`;
                alias = candidate.slice(0, 64);
                suffix += 1;
            }
            return alias;
        }

        function resolveSkillToolName(name) {
            if (!name || typeof name !== 'string') return name;
            return skillToolAliasToQualifiedName.get(name) || name;
        }

        async function refreshDynamicSkillToolsCache(signal) {
            const usedNames = new Set(
                baseTools
                    .map((tool) => tool?.function?.name)
                    .filter((name) => typeof name === 'string' && name.trim())
            );
            const nextAliasMap = new Map();

            const response = await fetch(`${PROXY_BASE_URL}/v1/skills/tools/openai?qualified_names=true`, {
                method: 'GET',
                signal
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const payload = await response.json();
            const tools = Array.isArray(payload?.tools) ? payload.tools : [];

            const llmTools = [];
            const promptLines = [];
            for (const tool of tools) {
                const fn = tool?.function;
                const qualifiedName = typeof fn?.name === 'string' ? fn.name.trim() : '';
                if (!qualifiedName) continue;
                const alias = createSkillToolAlias(qualifiedName, usedNames);
                usedNames.add(alias);
                nextAliasMap.set(alias, qualifiedName);

                const schema = (fn && typeof fn.parameters === 'object' && fn.parameters)
                    ? fn.parameters
                    : { type: 'object', properties: {} };
                llmTools.push({
                    type: 'function',
                    function: {
                        name: alias,
                        description: fn?.description || `Skill framework tool: ${qualifiedName}`,
                        parameters: schema
                    }
                });
                promptLines.push(
                    `- ${alias} (maps to ${qualifiedName}): ${fn?.description || 'No description.'}`
                );
            }

            skillToolAliasToQualifiedName.clear();
            nextAliasMap.forEach((qualifiedName, alias) => {
                skillToolAliasToQualifiedName.set(alias, qualifiedName);
            });
            cachedSkillToolsForLlm = llmTools;
            cachedSkillPromptLines = promptLines;
            lastSkillToolFetchAt = Date.now();
            return { tools: cachedSkillToolsForLlm, promptLines: cachedSkillPromptLines };
        }

        async function fetchDynamicSkillTools(forceRefresh = false, options = {}) {
            const signal = options?.signal;
            const now = Date.now();
            const cacheAge = now - lastSkillToolFetchAt;
            const hasCache = cachedSkillToolsForLlm.length > 0 || cachedSkillPromptLines.length > 0;

            if (!forceRefresh && hasCache) {
                if (cacheAge < SKILL_TOOL_CACHE_MS) {
                    return { tools: cachedSkillToolsForLlm, promptLines: cachedSkillPromptLines };
                }
                if (!skillToolsRefreshPromise) {
                    skillToolsRefreshPromise = refreshDynamicSkillToolsCache(undefined)
                        .catch((error) => {
                            console.warn('Background refresh of dynamic skill tools failed:', error);
                        })
                        .finally(() => {
                            skillToolsRefreshPromise = null;
                        });
                }
                return { tools: cachedSkillToolsForLlm, promptLines: cachedSkillPromptLines };
            }

            try {
                if (skillToolsRefreshPromise) {
                    await skillToolsRefreshPromise;
                    return { tools: cachedSkillToolsForLlm, promptLines: cachedSkillPromptLines };
                }
                const fresh = await refreshDynamicSkillToolsCache(signal);
                return fresh;
            } catch (error) {
                if (!hasCache) {
                    lastSkillToolFetchAt = now;
                }
                if (error?.name === 'AbortError') {
                    throw error;
                }
                console.warn('Could not load dynamic skill tools from proxy:', error);
                if (!hasCache) {
                    cachedSkillToolsForLlm = [];
                    cachedSkillPromptLines = [];
                }
                return { tools: cachedSkillToolsForLlm, promptLines: cachedSkillPromptLines };
            }
        }

        async function buildToolingBundle(forceRefresh = false, options = {}) {
            const dynamic = await fetchDynamicSkillTools(forceRefresh, options);
            return {
                tools: [...baseTools, ...dynamic.tools],
                skillPromptLines: dynamic.promptLines
            };
        }

        // Handler for reading files from the scratch directory
        async function handleReadFile(args = {}) {
            const path = String(args?.filename || args?.path || args?.file || '').trim();
            return await handleSkillFrameworkTool('filesystem.read_text', {
                path,
                start_line: args?.start_line,
                end_line: args?.end_line,
                max_chars: args?.max_chars,
                include_line_numbers: args?.include_line_numbers
            });
        }

        // Handler for writing files to the scratch directory
        async function handleWriteFile({ filename, content, format }) {
            let path = String(filename || '').trim();
            if (path && !/[\\/]/.test(path) && !/\.[^.\\/]+$/.test(path) && format) {
                path = `${path}.${String(format).trim().toLowerCase()}`;
            }
            return await handleSkillFrameworkTool('filesystem.write_text', {
                path,
                content: content ?? ''
            });
        }

        // Handler for listing files in the scratch directory
        async function handleListFiles({ path = '', recursive = false, offset = 0, max_entries = undefined } = {}) {
            return await handleSkillFrameworkTool('filesystem.list_files', {
                path,
                recursive,
                offset,
                max_entries
            });
        }

        async function handleSkillFrameworkTool(toolName, args) {
            try {
                const payload = {
                    tool_name: toolName,
                    arguments: (args && typeof args === 'object') ? args : {},
                    context: {
                        conversation_id: activeConversationId || 'default',
                        user_id: activeConversationId || 'default',
                        scratch_dir: 'scratch',
                        metadata: { channel: 'html_ui' }
                    }
                };
                const response = await fetch(`${PROXY_BASE_URL}/v1/skills/tools/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok) {
                    const detail = result?.detail || result?.message || `HTTP ${response.status}`;
                    return { success: false, message: `Skill tool error: ${detail}` };
                }
                const normalizedToolName = result.tool_name || toolName;
                const data = (result && typeof result.data === 'object' && result.data)
                    ? result.data
                    : null;
                if (normalizedToolName === 'filesystem.read_text' && data) {
                    return {
                        success: result.success !== false,
                        message: result.message || `Read ${data.path || args?.path || args?.filename || 'file'}.`,
                        content: typeof data.content === 'string' ? data.content : '',
                        type: typeof data.type === 'string' ? data.type : 'text',
                        data,
                        tool_name: normalizedToolName
                    };
                }
                if (normalizedToolName === 'filesystem.write_text' && data) {
                    return {
                        success: result.success !== false,
                        message: result.message || `Wrote ${data.path || args?.path || args?.filename || 'file'}.`,
                        filepath: data.path,
                        size: data.size_bytes,
                        data,
                        tool_name: normalizedToolName
                    };
                }
                if (normalizedToolName === 'filesystem.list_files' && data) {
                    const items = Array.isArray(data.items) ? data.items : [];
                    const files = items.map((item) => ({
                        name: item?.relative_path || item?.name || '',
                        size: item?.size_bytes,
                        type: item?.type || ''
                    }));
                    const offsetValue = Number.isFinite(Number(data.offset)) ? Number(data.offset) : 0;
                    const renderedLines = files.length > 0
                        ? files.map((file, index) => {
                            const isDir = String(file?.type || '').toLowerCase() === 'directory';
                            return isDir
                                ? `${offsetValue + index + 1}. ${file.name}/ [dir]`
                                : `${offsetValue + index + 1}. ${file.name} (${file.size ?? 0} bytes)`;
                        }).join('\n')
                        : 'No files found in the scratch directory.';
                    const continuationLine = data.has_more && typeof data.next_offset === 'number'
                        ? `\nMore files available. Call skill__filesystem_list_files with offset=${data.next_offset}.`
                        : '';
                    return {
                        success: result.success !== false,
                        message: result.message || `Found ${data.total_count ?? files.length} file${(data.total_count ?? files.length) === 1 ? '' : 's'}.`,
                        files,
                        count: data.total_count ?? files.length,
                        returned_count: data.returned_count ?? files.length,
                        total_count: data.total_count ?? files.length,
                        scratch_dir: data.root,
                        content: `${renderedLines}${continuationLine}`,
                        data,
                        tool_name: normalizedToolName
                    };
                }
                if (normalizedToolName === 'filesystem.search_files' && data) {
                    const items = Array.isArray(data.items) ? data.items : [];
                    const offsetValue = Number.isFinite(Number(data.offset)) ? Number(data.offset) : 0;
                    const renderedLines = items.length > 0
                        ? items.map((item, index) => {
                            const relPath = item?.relative_path || item?.name || '?';
                            const matchTypes = Array.isArray(item?.match_types) && item.match_types.length
                                ? item.match_types.join(',')
                                : 'unknown';
                            const lineSuffix = Number.isFinite(Number(item?.line_number)) && Number(item.line_number) > 0
                                ? ` line ${item.line_number}`
                                : '';
                            const excerpt = String(item?.excerpt || '').trim();
                            return excerpt
                                ? `${offsetValue + index + 1}. ${relPath} [${matchTypes}]${lineSuffix}: ${excerpt}`
                                : `${offsetValue + index + 1}. ${relPath} [${matchTypes}]`;
                        }).join('\n')
                        : `No matching files found for "${data.query || args?.query || ''}".`;
                    const continuationLine = data.has_more && typeof data.next_offset === 'number'
                        ? `\nMore results available. Call skill__filesystem_search_files with offset=${data.next_offset}.`
                        : '';
                    return {
                        success: result.success !== false,
                        message: result.message || `Found ${data.total_matches ?? items.length} matching file result${(data.total_matches ?? items.length) === 1 ? '' : 's'}.`,
                        matches: items,
                        total_matches: data.total_matches ?? items.length,
                        content: `${renderedLines}${continuationLine}`,
                        data,
                        tool_name: normalizedToolName
                    };
                }
                return {
                    success: result.success !== false,
                    message: result.message || `Skill tool '${toolName}' executed.`,
                    data: result.data,
                    error_code: result.error_code,
                    tool_name: normalizedToolName
                };
            } catch (error) {
                console.error('Skill framework tool error:', error);
                return {
                    success: false,
                    message: `Error executing skill tool '${toolName}': ${error.message}`
                };
            }
        }

        async function reportToolInvocationToProxy(name, args) {
            try {
                const payload = {
                    source: 'html_ui',
                    name: name,
                    arguments: (args && typeof args === 'object') ? args : {}
                };
                const headers = { 'Content-Type': 'application/json' };
                if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
                await fetch(`${PROXY_BASE_URL}/v1/tools/log`, {
                    method: 'POST',
                    headers,
                    keepalive: true,
                    body: JSON.stringify(payload)
                });
            } catch (error) {
                // Logging failures should never block tool execution.
                console.warn('Tool invocation logging failed:', error);
            }
        }

        // Update executeToolCall to include the new handler
        async function executeToolCall(toolCall, context) {
            console.log('executeToolCall - Input:', { toolCall, context });
            
            let name, argsString;
            
            // Handle both direct tool call format and function format
            if (toolCall.function) {
                ({ name, arguments: argsString } = toolCall.function);
            } else if (toolCall.name) {
                // Handle direct format
                name = toolCall.name;
                argsString = toolCall.arguments;
            } else {
                console.error('executeToolCall - Invalid toolCall format:', toolCall);
                throw new Error('Invalid tool call format');
            }
            
            if (!name || !argsString) {
                console.error('executeToolCall - Missing required properties:', { name, argsString });
                throw new Error('Invalid tool call format: missing name or arguments');
            }

            console.log('executeToolCall - Extracted values:', { name, argsString });

            try {
                const args = typeof argsString === 'string' ? JSON.parse(argsString) : argsString;
                console.log('executeToolCall - Parsed arguments:', args);
                const resolvedName = resolveSkillToolName(name);
                if (resolvedName !== name) {
                    console.log('executeToolCall - Resolved dynamic skill alias:', { alias: name, qualified: resolvedName });
                }
                void reportToolInvocationToProxy(resolvedName, args);

                let result;
                switch (resolvedName) {
                    case "manageTodoList":
                        result = await handleTodoList(args);
                        break;
                    case "executeTodoTask":
                        result = await handleExecuteTodoTask(args);
                        break;
                    case "resumeTodoExecution":
                        result = await handleResumeTodoExecution(args);
                        break;
                    case "completeTodoTask":
                        result = await handleCompleteTodoTask(args);
                        break;
                    case "cancelTodoExecution":
                        result = await handleCancelTodoExecution(args);
                        break;
                    case "scrapeWebsite":
                        result = await handleWebScraping(args);
                        break;
                    case "webSearch":
                        result = await handleWebSearch(args);
                        break;
                    case "weatherInfo":
                        result = await handleWeatherInfo(args);
                        break;
                    case "manageWorkingContext":
                        result = await handleMemoryCache(args);
                        break;
                    case "navigateToUrl":
                        result = await handleNavigation(args);
                        break;
                    case "openChatToUser":
                        result = await handleTeamsChat(args);
                        break;
                    case "calculate":
                        result = await handleCalculation(args, context);
                        break;
                    case "runWorkflow":
                        // Ensure hostname and protocol are included to avoid localhost default
                        result = await handleWorkflow({
                            ...args,
                            hostname: args.hostname || window.location.hostname,
                            protocol: args.protocol || window.location.protocol
                        });
                        break;
                    case "runCodexCli":
                        result = await handleCodexCli(args);
                        break;
                    case "restartProxyServer":
                        result = await handleRestartProxyServer(args);
                        break;
                    case "llmQuery":
                        result = await handleLLMQuery(args, context);
                        break;
                    case "saveToFile":
                        result = await handleWriteFile({
                            filename: args?.filename,
                            content: args?.content,
                            format: args?.format || "txt",
                        });
                        break;
                    case "fetchNews":
                        result = await handleNews(args);
                        break;
                    // Backward compatibility: route legacy name to the new handler
                    case "fetchRoboticsNews":
                        result = await handleNews(args);
                        break;
                    case "pdfToPowerPoint":
                        result = await handlePdfToPowerPoint(args);
                        break;
                    case "uploadToGoogleDrive":
                        result = await handleGoogleDriveUpload(args);
                        break;
                    case "storeMemory":
                        result = await handleStoreMemory(args);
                        break;
                    case "searchMemories":
                        result = await handleSearchMemories(args);
                        break;
                    case "listMemories":
                        result = await handleListMemories(args);
                        break;
                    case "deleteMemory":
                        result = await handleDeleteMemory(args);
                        break;
                    case "runBrowserAgent":
                        result = await handleBrowserAgent(args);
                        break;
                    case "runDeepResearch":
                        result = await handleDeepResearch(args);
                        break;
                    case "health_check":
                        result = await handleBrowserHealthCheck(args);
                        break;
                    case "readFile":
                        result = await handleReadFile(args);
                        break;
                    case "writeFile":
                        result = await handleWriteFile(args);
                        break;
                    case "listFiles":
                        result = await handleListFiles(args);
                        break;
                    default:
                        result = await handleSkillFrameworkTool(resolvedName, args);
                        if (!result || result.success === false) {
                            result = result || {};
                            result.success = false;
                            result.message = result.message || `Unknown tool: ${resolvedName}`;
                        }
                        break;
                }
                console.log('executeToolCall - Result:', result);
                return result;
            } catch (error) {
                console.error('executeToolCall - Error:', error);
                throw error;
            }
        }

        function formatToolResultForModel(toolResult) {
            if (typeof toolResult === 'string') {
                return toolResult;
            }
            if (toolResult && typeof toolResult === 'object' && toolResult.content) {
                return `${toolResult.message}\n\nContent:\n${toolResult.content}`;
            }
            try {
                return JSON.stringify(toolResult);
            } catch (_) {
                return String(toolResult);
            }
        }

        function extractToolResultSummary(toolResult) {
            if (typeof toolResult === 'string') {
                return toolResult;
            }
            if (toolResult && typeof toolResult === 'object' && typeof toolResult.message === 'string' && toolResult.message.trim()) {
                return toolResult.message.trim();
            }
            return formatToolResultForModel(toolResult);
        }


        // Individual tool handlers (todo uses REST API when authenticated, else local + localStorage)
        function normalizeTodoRecurrenceInput({ recurrence, repeatFrequency, repeatInterval }) {
            if (recurrence && typeof recurrence === 'object') {
                const freq = String(recurrence.frequency || '').trim().toLowerCase();
                const intervalRaw = recurrence.interval ?? 1;
                const interval = Number(intervalRaw);
                if (!freq) return null;
                return { frequency: freq, interval: Number.isFinite(interval) && interval > 0 ? Math.floor(interval) : 1 };
            }
            const freqAlias = String(repeatFrequency || '').trim().toLowerCase();
            if (!freqAlias) return null;
            const intervalAlias = Number(repeatInterval ?? 1);
            return {
                frequency: freqAlias,
                interval: Number.isFinite(intervalAlias) && intervalAlias > 0 ? Math.floor(intervalAlias) : 1
            };
        }

        function formatTodoTaskLine(task, index) {
            if (typeof task === 'string') return `${index + 1}. ${task}`;
            const description = task?.taskDescription || task?.description || '(No description)';
            const parsedTaskId = Number(task?.taskId);
            const lineNumber = Number.isFinite(parsedTaskId) && parsedTaskId > 0 ? Math.floor(parsedTaskId) : (index + 1);
            const suffix = [];
            const nextRun = task?.nextRunAt || task?.next_run_at || task?.scheduledFor || task?.scheduled_for;
            if (nextRun) {
                suffix.push(`next: ${nextRun}${task?.isDue ? ', due now' : ''}`);
            }
            const recurrence = task?.recurrence;
            if (recurrence && recurrence.frequency) {
                const interval = Number(recurrence.interval ?? 1);
                const safeInterval = Number.isFinite(interval) && interval > 0 ? Math.floor(interval) : 1;
                const freq = String(recurrence.frequency).toLowerCase();
                const unit = safeInterval === 1 ? freq : `${freq}s`;
                suffix.push(`repeats every ${safeInterval} ${unit}`);
            }
            return suffix.length
                ? `${lineNumber}. ${description} (${suffix.join('; ')})`
                : `${lineNumber}. ${description}`;
        }

        async function handleTodoList({ action, taskId, taskDescription, scheduledFor, recurrence, repeatFrequency, repeatInterval, clearSchedule, clearRecurrence }) {
            const headers = { 'Content-Type': 'application/json' };
            if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
            const normalizedAction = String(action || '').trim().toLowerCase();
            const resolvedAction = (normalizedAction === 'list_due' || normalizedAction === 'listdue') ? 'due' : normalizedAction;
            try {
                if (authToken) {
                    const recurrencePayload = normalizeTodoRecurrenceInput({ recurrence, repeatFrequency, repeatInterval });
                    switch (resolvedAction) {
                        case "list":
                            await fetchTodoListFromServer();
                            if (todoList.length === 0) return { success: true, message: "Your todo list is empty." };
                            const sourceItems = (Array.isArray(todoTaskItems) && todoTaskItems.length > 0)
                                ? todoTaskItems
                                : todoList;
                            const taskList = sourceItems.map((task, index) => formatTodoTaskLine(task, index)).join('\n');
                            return { success: true, message: "Here are your current tasks:\n" + taskList };
                        case "due":
                            const dueRes = await fetch(`${PROXY_BASE_URL}/v1/todo/due`, { method: 'GET', headers });
                            if (!dueRes.ok) {
                                const err = await dueRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || dueRes.statusText };
                            }
                            const dueData = await dueRes.json();
                            const dueTasks = Array.isArray(dueData.tasks) ? dueData.tasks : [];
                            const dueTaskItems = Array.isArray(dueData.taskItems) ? dueData.taskItems : [];
                            if (dueTasks.length === 0) {
                                return { success: true, message: "You have no due scheduled tasks right now." };
                            }
                            const dueSourceItems = dueTaskItems.length > 0 ? dueTaskItems : dueTasks;
                            const dueTaskList = dueSourceItems.map((task, index) => formatTodoTaskLine(task, index)).join('\n');
                            return { success: true, message: "Here are your due tasks:\n" + dueTaskList, tasks: dueTasks, taskItems: dueTaskItems };
                        case "add":
                            if (!taskDescription) return { success: false, message: "Task description is required." };
                            const addPayload = { taskDescription: taskDescription.trim() };
                            const scheduledText = typeof scheduledFor === 'string' ? scheduledFor.trim() : '';
                            if (scheduledText) addPayload.scheduledFor = scheduledText;
                            if (recurrencePayload) addPayload.recurrence = recurrencePayload;
                            const addRes = await fetch(`${PROXY_BASE_URL}/v1/todo`, {
                                method: 'POST', headers,
                                body: JSON.stringify(addPayload)
                            });
                            if (!addRes.ok) {
                                const err = await addRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || addRes.statusText };
                            }
                            const addData = await addRes.json();
                            todoList = addData.tasks || [];
                            todoTaskItems = addData.taskItems || [];
                            return { success: true, message: `Added task: ${taskDescription}` };
                        case "update":
                            if (!taskId) return { success: false, message: "Task ID is required." };
                            const updatePayload = {};
                            if (taskDescription !== undefined && taskDescription !== null) {
                                const nextDesc = String(taskDescription).trim();
                                if (!nextDesc) return { success: false, message: "taskDescription cannot be empty." };
                                updatePayload.taskDescription = nextDesc;
                            }
                            const updateScheduledText = typeof scheduledFor === 'string' ? scheduledFor.trim() : '';
                            if (updateScheduledText) updatePayload.scheduledFor = updateScheduledText;
                            if (recurrencePayload) updatePayload.recurrence = recurrencePayload;
                            if (clearSchedule) updatePayload.clearSchedule = true;
                            if (clearRecurrence) updatePayload.clearRecurrence = true;
                            if (Object.keys(updatePayload).length === 0) {
                                return { success: false, message: "Provide at least one field to update." };
                            }
                            const updRes = await fetch(`${PROXY_BASE_URL}/v1/todo/${taskId}`, {
                                method: 'PATCH', headers,
                                body: JSON.stringify(updatePayload)
                            });
                            if (!updRes.ok) {
                                const err = await updRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || updRes.statusText };
                            }
                            const updData = await updRes.json();
                            todoList = updData.tasks || [];
                            todoTaskItems = updData.taskItems || [];
                            return { success: true, message: `Updated task ${taskId}.` };
                        case "complete":
                            if (!taskId) return { success: false, message: "Task ID is required." };
                            const completeRes = await fetch(`${PROXY_BASE_URL}/v1/todo/${taskId}/complete`, {
                                method: 'POST', headers
                            });
                            if (!completeRes.ok) {
                                const err = await completeRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || completeRes.statusText };
                            }
                            const completeData = await completeRes.json();
                            todoList = completeData.tasks || [];
                            todoTaskItems = completeData.taskItems || [];
                            return { success: true, message: `Completed task ${taskId}.` };
                        case "delete":
                            if (!taskId) return { success: false, message: "Task ID is required." };
                            const delRes = await fetch(`${PROXY_BASE_URL}/v1/todo/${taskId}`, { method: 'DELETE', headers });
                            if (!delRes.ok) {
                                const err = await delRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || delRes.statusText };
                            }
                            const delData = await delRes.json();
                            todoList = delData.tasks || [];
                            todoTaskItems = delData.taskItems || [];
                            return { success: true, message: "Task deleted." };
                        case "clear":
                            const clearRes = await fetch(`${PROXY_BASE_URL}/v1/todo`, { method: 'DELETE', headers });
                            if (!clearRes.ok) {
                                const err = await clearRes.json().catch(() => ({}));
                                return { success: false, message: err.detail || clearRes.statusText };
                            }
                            todoList = [];
                            todoTaskItems = [];
                            return { success: true, message: "Todo list has been cleared." };
                        default:
                            return { success: false, message: "Invalid action." };
                    }
                }
                // Not authenticated: old localStorage path disabled; require sign-in for persistent todo
                return { success: false, message: "Please sign in to use the todo list. Your tasks are stored when you're signed in." };
            } catch (error) {
                console.error('Todo list operation error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        async function handleExecuteTodoTask(args) {
            // Normalize camelCase and snake_case (LLM may send either)
            const taskId = args.taskId ?? args.task_id;
            const promptOverride = (args.promptOverride ?? args.prompt_override ?? '').toString().trim() || null;
            if (!authToken) return { success: false, message: "Please sign in to run task execution." };
            if (taskId === undefined || taskId === null) return { success: false, message: "Task ID is required." };
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/todo/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ taskId: Number(taskId), promptOverride: promptOverride || null })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    // FastAPI validation returns detail as array; format readably
                    const detail = data.detail;
                    const message = Array.isArray(detail) && detail.length
                        ? (detail[0].msg || detail[0].loc?.join('.') || JSON.stringify(detail[0]))
                        : (typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : res.statusText));
                    return { success: false, message: message };
                }
                return { success: true, message: data.message || "Execution started.", status: data.status, taskId: data.taskId };
            } catch (err) {
                return { success: false, message: err.message || "Task execution failed." };
            }
        }

        async function handleResumeTodoExecution(args) {
            const userMessage = (args.userMessage ?? args.user_message ?? '').toString().trim();
            const taskIdRaw = args.taskId ?? args.task_id;
            const taskId = (taskIdRaw === undefined || taskIdRaw === null) ? null : Number(taskIdRaw);
            if (!authToken) return { success: false, message: "Please sign in to resume task execution." };
            if (!userMessage) return { success: false, message: "userMessage is required to resume." };
            if (taskIdRaw !== undefined && taskIdRaw !== null && !Number.isFinite(taskId)) {
                return { success: false, message: "taskId must be a number." };
            }
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/todo/execute/resume`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ userMessage, taskId: taskId ?? null })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const detail = data.detail;
                    const message = Array.isArray(detail) && detail.length
                        ? (detail[0].msg || detail[0].loc?.join('.') || JSON.stringify(detail[0]))
                        : (typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : res.statusText));
                    return { success: false, message: message };
                }
                return { success: true, message: data.message || "Resumed.", status: data.status, taskId: data.taskId };
            } catch (err) {
                return { success: false, message: err.message || "Resume failed." };
            }
        }

        async function handleCompleteTodoTask(args) {
            const taskId = args.taskId ?? args.task_id;
            if (!authToken) return { success: false, message: "Please sign in to mark a task complete." };
            if (taskId === undefined || taskId === null) return { success: false, message: "taskId is required." };
            try {
                const res = await fetch(`${PROXY_BASE_URL}/v1/todo/${Number(taskId)}/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const detail = data.detail;
                    const message = Array.isArray(detail) && detail.length
                        ? (detail[0].msg || detail[0].loc?.join('.') || JSON.stringify(detail[0]))
                        : (typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : res.statusText));
                    return { success: false, message: message };
                }
                todoList = Array.isArray(data.tasks) ? data.tasks : [];
                todoTaskItems = Array.isArray(data.taskItems) ? data.taskItems : [];
                return { success: true, message: "Task completion recorded.", tasks: todoList };
            } catch (err) {
                return { success: false, message: err.message || "Complete failed." };
            }
        }

        async function handleCancelTodoExecution(args = {}) {
            const taskIdRaw = args.taskId ?? args.task_id;
            const taskId = (taskIdRaw === undefined || taskIdRaw === null) ? null : Number(taskIdRaw);
            if (!authToken) return { success: false, message: "Please sign in to cancel task execution." };
            if (taskIdRaw !== undefined && taskIdRaw !== null && !Number.isFinite(taskId)) {
                return { success: false, message: "taskId must be a number." };
            }
            try {
                const url = taskId !== null
                    ? `${PROXY_BASE_URL}/v1/todo/execute/cancel?taskId=${encodeURIComponent(String(taskId))}`
                    : `${PROXY_BASE_URL}/v1/todo/execute/cancel`;
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const detail = data.detail;
                    const message = Array.isArray(detail) && detail.length
                        ? (detail[0].msg || detail[0].loc?.join('.') || JSON.stringify(detail[0]))
                        : (typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : res.statusText));
                    return { success: false, message: message };
                }
                return { success: true, message: data.message || "Execution cancelled." };
            } catch (err) {
                return { success: false, message: err.message || "Cancel failed." };
            }
        }

        async function handleMemoryCache({ action, memId, memDescription }) {
                    try {
                        switch (action) {
                            case "list":
                                if (memoryCache.length === 0) {
                            return { success: true, message: "Your memory cache is empty." };
                        }
                        const memList = memoryCache.map((mem, index) => `${index + 1}. ${mem}`).join('\n');
                        return { success: true, message: "Here are your memories:\n" + memList };

                            case "add":
                                if (!memDescription) {
                            return { success: false, message: "Memory description is required." };
                                }
                                memoryCache.push(memDescription);
                        saveMemory();
                        return { success: true, message: `Added memory: ${memDescription}` };

                            case "update":
                                if (!memId || !memDescription) {
                            return { success: false, message: "Both memory ID and new description are required." };
                                }
                                if (memId < 1 || memId > memoryCache.length) {
                            return { success: false, message: "Invalid memory ID." };
                                }
                                const oldMem = memoryCache[memId - 1];
                                memoryCache[memId - 1] = memDescription;
                        saveMemory();
                        return { success: true, message: `Updated memory ${memId} from "${oldMem}" to "${memDescription}"` };

                            case "delete":
                                if (!memId) {
                            return { success: false, message: "Memory ID is required." };
                                }
                                if (memId < 1 || memId > memoryCache.length) {
                            return { success: false, message: "Invalid memory ID." };
                                }
                                const deletedMem = memoryCache.splice(memId - 1, 1)[0];
                        saveMemory();
                        return { success: true, message: `Deleted memory: ${deletedMem}` };

                            case "clear":
                                memoryCache = [];
                        saveMemory();
                        return { success: true, message: "Memory cache has been cleared." };

                            default:
                        return { success: false, message: "Invalid action." };
                        }
                    } catch (error) {
                        console.error('Memory cache operation error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        async function handleStoreMemory({ text, category }) {
            try {
                const response = await fetchProxyEndpoint('/v1/memory/store', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        category: category || "profile_fact",
                        source: "explicit"
                    })
                });
                const data = await response.json();
                if (data.success) {
                    return { success: true, message: `Memory stored: ${text}` };
                } else {
                    return { success: false, message: data.message || "Failed to store memory" };
                }
            } catch (error) {
                return { success: false, message: `Error storing memory: ${error.message}` };
            }
        }

        async function handleSearchMemories({ query, limit, similarity_threshold }) {
            try {
                const threshold = (typeof similarity_threshold === 'number') ? similarity_threshold : 0.6;
                const response = await fetchProxyEndpoint('/v1/memory/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        limit: limit || 5,
                        similarity_threshold: threshold
                    })
                });
                const data = await response.json();
                if (data.success && data.data.memories) {
                    const memories = data.data.memories;
                    if (memories.length === 0) {
                        return { success: true, message: "No relevant memories found.", data: { memories: [] } };
                    }
                    const memoryList = memories.map((mem, i) => 
                        `${i + 1}. ${mem.text} (similarity: ${(mem.similarity * 100).toFixed(1)}%)`
                    ).join('\n');
                    return { success: true, message: `Found ${memories.length} relevant memories:\n${memoryList}`, data: { memories } };
                } else {
                    return { success: false, message: data.message || "Failed to search memories" };
                }
            } catch (error) {
                return { success: false, message: `Error searching memories: ${error.message}` };
            }
        }

        // Retrieve prompt-safe context through the shared server-side policy.
        async function fetchConversationMemoryContext(prompt) {
            if (philosopherModeActive) {
                return null;
            }
            try {
                const response = await fetchProxyEndpoint('/v1/memory/context', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: prompt,
                        purpose: 'conversation',
                        conversation_id: activeConversationId || 'default',
                        max_items: 4,
                        max_tokens: 500
                    })
                });
                const result = await response.json();
                return result?.success ? (result?.data?.context || null) : null;
            } catch (error) {
                console.warn('Auto memory search failed:', error);
                return null;
            }
        }

        async function handleListMemories({ limit }) {
            try {
                const limitParam = limit ? `?limit=${limit}` : '';
                const response = await fetchProxyEndpoint(`/v1/memory/list${limitParam}`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.success && data.data.memories) {
                    const memories = data.data.memories;
                    if (memories.length === 0) {
                        return { success: true, message: "No memories stored yet." };
                    }
                    const memoryList = memories.map((mem, i) => 
                        `${i + 1}. [${mem.category}] ${mem.text} (ID: ${mem.id})`
                    ).join('\n');
                    return { success: true, message: `Stored memories (${data.data.total} total):\n${memoryList}` };
                } else {
                    return { success: false, message: data.message || "Failed to list memories" };
                }
            } catch (error) {
                return { success: false, message: `Error listing memories: ${error.message}` };
            }
        }

        async function handleDeleteMemory({ memory_id }) {
            try {
                const response = await fetchProxyEndpoint(`/v1/memory/${encodeURIComponent(memory_id)}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.success) {
                    return { success: true, message: `Memory ${memory_id} deleted successfully.` };
                } else {
                    return { success: false, message: data.message || "Failed to delete memory" };
                }
            } catch (error) {
                return { success: false, message: `Error deleting memory: ${error.message}` };
            }
        }

        // Automatically extract memories from conversation
        async function extractMemoriesFromConversation() {
            try {
                // Get recent messages from chatHistory (last 4 messages: user + assistant pairs)
                const recentMessages = chatHistory.slice(-4).map(msg => ({
                    role: msg.role,
                    content: msg.content || msg.content || ''
                })).filter(msg => msg.content.trim()); // Filter out empty messages
                
                if (recentMessages.length === 0) {
                    return; // No messages to extract from
                }
                
                // Call the backend to extract and store memories
                const response = await fetchProxyEndpoint('/v1/memory/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: recentMessages,
                        max_memories: 3,
                        conversation_id: activeConversationId || 'default'
                    })
                });
                
                const data = await response.json();
                if (data.success && data.data.extracted > 0) {
                    console.log(`Automatically extracted ${data.data.extracted} memories from conversation`);
                }
            } catch (error) {
                // Silently fail - don't interrupt user experience
                console.warn('Failed to extract memories automatically:', error);
            }
        }

        function normalizeSafeExternalToolUrl(rawUrl, allowedProtocols = ['http:', 'https:']) {
            const value = String(rawUrl || '').trim();
            if (!value) return '';
            try {
                const parsed = new URL(value);
                return allowedProtocols.includes(parsed.protocol) ? parsed.href : '';
            } catch (_) {
                return '';
            }
        }

        function openExternalToolUrl(rawUrl, allowedProtocols = ['http:', 'https:']) {
            const safeUrl = normalizeSafeExternalToolUrl(rawUrl, allowedProtocols);
            if (!safeUrl) return false;
            const opened = window.open(safeUrl, '_blank', 'noopener,noreferrer');
            if (opened) opened.opener = null;
            return true;
        }

        async function handleNavigation({ url }) {
            try {
                const safeUrl = normalizeSafeExternalToolUrl(url, ['http:', 'https:']);
                if (!safeUrl) {
                    return { success: false, message: "Only http:// and https:// URLs can be opened." };
                }
                if (confirm(`Would you like to open ${safeUrl}?`)) {
                    if (!openExternalToolUrl(safeUrl, ['http:', 'https:'])) {
                        return { success: false, message: "Website opening was blocked." };
                    }
                    return { success: true, message: "The website has been opened in a new tab." };
                }
                return { success: false, message: "Website opening was cancelled." };
            } catch (error) {
                console.error('Navigation error:', error);
                return { success: false, message: "Invalid URL provided" };
            }
        }

        async function handleTeamsChat({ url }) {
            try {
                const safeUrl = normalizeSafeExternalToolUrl(url, ['https:', 'msteams:']);
                if (!safeUrl) {
                    return { success: false, message: "Only HTTPS or Microsoft Teams URLs can be opened." };
                }
                if (confirm(`Would you like to open Teams chat?`)) {
                    if (!openExternalToolUrl(safeUrl, ['https:', 'msteams:'])) {
                        return { success: false, message: "Teams chat opening was blocked." };
                    }
                    return { success: true, message: "Teams chat has been opened" };
                }
                return { success: false, message: "Teams chat opening was cancelled." };
            } catch (error) {
                console.error('Teams chat error:', error);
                return { success: false, message: "Invalid Teams URL" };
            }
        }

        function evaluateMathExpression(expression) {
            const input = String(expression || '');
            let index = 0;

            function peek() {
                return input[index] || '';
            }

            function consume(char) {
                if (peek() === char) {
                    index += 1;
                    return true;
                }
                return false;
            }

            function parseNumber() {
                const start = index;
                while (/[0-9.]/.test(peek())) index += 1;
                if (start === index) throw new Error('Expected number');
                const raw = input.slice(start, index);
                if ((raw.match(/\./g) || []).length > 1) throw new Error('Invalid number');
                return Number(raw);
            }

            function parseFactor() {
                if (consume('+')) return parseFactor();
                if (consume('-')) return -parseFactor();
                if (consume('(')) {
                    const value = parseExpression();
                    if (!consume(')')) throw new Error('Missing closing parenthesis');
                    return value;
                }
                return parseNumber();
            }

            function parseTerm() {
                let value = parseFactor();
                while (peek() === '*' || peek() === '/') {
                    const operator = peek();
                    index += 1;
                    const rhs = parseFactor();
                    value = operator === '*' ? value * rhs : value / rhs;
                }
                return value;
            }

            function parseExpression() {
                let value = parseTerm();
                while (peek() === '+' || peek() === '-') {
                    const operator = peek();
                    index += 1;
                    const rhs = parseTerm();
                    value = operator === '+' ? value + rhs : value - rhs;
                }
                return value;
            }

            const result = parseExpression();
            if (index !== input.length) throw new Error('Unexpected input');
            return result;
        }

        async function handleCalculation({ expression }, context) {
            try {
                console.log('Handling calculation:', expression);
                console.log('Calculation context:', context);
                
                // Check if expression is empty or undefined
                if (!expression) {
                    console.error('Empty or undefined expression');
                    return { success: false, message: "No mathematical expression provided" };
                }

                // Resolve RESULT placeholder if present
                let resolvedExpression = expression;
                if (expression.includes('RESULT')) {
                    const prevResult = context?.variables?.get('lastCalculation');
                    console.log('Previous calculation result:', prevResult);
                    
                    if (prevResult === undefined || prevResult === null) {
                        console.error('No previous result found for calculation');
                        return { success: false, message: "No previous calculation result available" };
                    }
                    
                    resolvedExpression = expression.replace('RESULT', prevResult.toString());
                    console.log('Resolved expression:', resolvedExpression);
                }

                // Clean the resolved expression
                const cleanExpression = resolvedExpression.toString().replace(/\s+/g, '');
                console.log('Cleaned expression:', cleanExpression);
                
                // Validate the cleaned expression
                if (!cleanExpression || !/^[0-9][0-9+\-*/().]*$/.test(cleanExpression)) {
                    console.error('Invalid expression after cleaning:', cleanExpression);
                    return { success: false, message: "Invalid mathematical expression" };
                }
                
                // Evaluate the expression without using eval.
                const result = evaluateMathExpression(cleanExpression);
                console.log('Calculation result:', result);
                
                if (typeof result !== 'number' || isNaN(result)) {
                    return { success: false, message: "Invalid calculation result" };
                }
                
                // Store the result in the context for future reference
                if (context && context.variables instanceof Map) {
                    context.variables.set('lastCalculation', result);
                    console.log('Stored calculation result in context:', result);
                } else {
                    console.warn('Context not available for storing calculation result');
                }
                
                return { success: true, message: `${cleanExpression} = ${result}` };
            } catch (error) {
                console.error('Calculation error:', error);
                return { success: false, message: `Invalid calculation: ${error.message}` };
            }
        }

        async function handleWorkflow({ contentPrompt, hostname, protocol }) {
            try {
                // Pass the calling page's hostname and protocol to runWorkflow
                // Use provided values or fallback to window.location to avoid localhost default
                const result = await window.runWorkflow(contentPrompt, {
                    hostname: hostname || window.location.hostname,
                    protocol: protocol || window.location.protocol,
                    fullPayload: true
                });
                const now = new Date();
                const pad2 = (value) => value.toString().padStart(2, '0');
                const timestamp = [
                    pad2(now.getDate()),
                    pad2(now.getMonth() + 1),
                    now.getFullYear(),
                    pad2(now.getHours()),
                    pad2(now.getMinutes()),
                    pad2(now.getSeconds())
                ].join('-');
                const filename = result?.logFile || `${timestamp}_autogen_response.txt`;
                const transcript = result?.transcript || result?.response || result?.output || '';

                const writeResult = await handleWriteFile({
                    filename,
                    content: transcript,
                    format: 'txt'
                });

                if (!writeResult.success) {
                    console.warn('Failed to persist AutoGen response:', writeResult.message);
                }

                return { success: true, message: `The workflow has completed. Full team transcript saved to ${filename}.` };
            } catch (error) {
                console.error('Workflow error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        async function handleCodexCli({ prompt, timeoutSeconds }) {
            try {
                const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/codex`;
                const response = await fetch(proxyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({
                        prompt,
                        timeoutSeconds
                    })
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`Codex CLI failed: ${response.status} ${response.statusText}${errText ? ' - ' + errText.slice(0, 120) : ''}`);
                }

                const data = await response.json();
                const summaryFile = data.summaryFile ? `Summary file: ${data.summaryFile}` : 'Summary file not provided.';
                const eventsFile = data.eventsFile ? `Events file: ${data.eventsFile}` : 'Events file not provided.';
                const lastMessageFile = data.lastMessageFile ? `Last message file: ${data.lastMessageFile}` : 'Last message file not provided.';
                const exitCode = data.exitCode !== undefined ? `exit_code=${data.exitCode}` : 'exit_code=unknown';
                const timedOut = data.timedOut ? 'timed_out=true' : 'timed_out=false';
                const statusWord = data.success === false ? 'failed' : 'finished';
                const stderrPreview = data.success === false && data.stderr ? ` Error: ${String(data.stderr).slice(0, 500)}` : '';
                return {
                    success: data.success !== false,
                    message: `Codex CLI ${statusWord} (${exitCode}, ${timedOut}). ${summaryFile} ${eventsFile} ${lastMessageFile}${stderrPreview}`
                };
            } catch (error) {
                console.error('Codex CLI error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        async function handleRestartProxyServer({ confirm, reason }) {
            try {
                if (confirm !== true) {
                    return { success: false, message: "Restart not confirmed. Set confirm=true to restart the proxy server." };
                }
                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/restart`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`Proxy restart failed: ${response.status} ${response.statusText}${errText ? ' - ' + errText.slice(0, 160) : ''}`);
                }
                const data = await response.json();
                const note = reason ? ` Reason: ${reason}` : '';
                return {
                    success: data.success !== false,
                    message: `${data.message || 'Proxy restart requested.'}${note}`
                };
            } catch (error) {
                console.error('Proxy restart error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        // Add this new handler function for web scraping (supports single url or urls[] for retry)
        async function handleWebScraping({ url, urls, render_js, render_engine, wait_for_selector, js_wait_ms }) {
            try {
                // Build list: single url or urls array; filter invalid
                const urlList = [];
                if (url && url !== 'pending' && typeof url === 'string' && url.startsWith('http')) {
                    urlList.push(url);
                }
                if (Array.isArray(urls)) {
                    urls.forEach(u => {
                        if (u && typeof u === 'string' && u.startsWith('http') && u !== 'pending') {
                            urlList.push(u);
                        }
                    });
                }
                // Dedupe while preserving order
                const toTry = [...new Set(urlList)];
                if (toTry.length === 0) {
                    return {
                        success: false,
                        message: 'No URL available from previous step. Run a web search first, or specify a URL (or urls array) to scrape.'
                    };
                }

                const renderJs = Boolean(render_js);
                const renderEngine = typeof render_engine === 'string' ? render_engine.trim().toLowerCase() : 'auto';
                const waitForSelector = typeof wait_for_selector === 'string' ? wait_for_selector.trim() : '';
                const parsedWait = Number.parseInt(js_wait_ms, 10);
                const jsWaitMs = Number.isFinite(parsedWait) ? Math.max(0, Math.min(parsedWait, 20000)) : 2200;

                // Use POST for proxy fetch; proxy tries each URL until one succeeds when urls[] is sent
                const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/fetch`;
                const body = toTry.length === 1 ? { url: toTry[0] } : { urls: toTry };
                if (renderJs) {
                    body.render_js = true;
                    body.render_engine = ['playwright', 'selenium'].includes(renderEngine) ? renderEngine : 'auto';
                    body.js_wait_ms = jsWaitMs;
                    if (waitForSelector) {
                        body.wait_for_selector = waitForSelector;
                    }
                }
                const response = await fetch(proxyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify(body)
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`Failed to fetch content: ${response.status} ${response.statusText}${errText ? ' - ' + errText.slice(0, 100) : ''}`);
                }

                const data = await response.json();
                if (!data.content) {
                    throw new Error('No content received from proxy');
                }

                // Create a temporary element to parse the HTML
                const parser = new DOMParser();
                const doc = parser.parseFromString(data.content, 'text/html');
                // Remove script and style elements
                doc.querySelectorAll('script, style').forEach(el => el.remove());
                // Safely get body text (iOS Safari: doc.body can be null for malformed HTML)
                const bodyEl = doc.body;
                const textContent = (bodyEl && bodyEl.textContent ? bodyEl.textContent : doc.documentElement ? doc.documentElement.textContent : '')
                    .replace(/\s+/g, ' ')
                    .trim();
                
                // Use the LLM to summarize the content via proxy to avoid mixed content (HTTPS page calling HTTP endpoint)
                const summaryEndpoint = `${PROXY_BASE_URL}/v1/proxy/chat/completions?endpoint=${encodeURIComponent(endpointInput.value)}`;
                const summaryResponse = await fetch(summaryEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKeyInput.value}`
                    },
                    body: JSON.stringify(buildCompatibleChatBody(summaryEndpoint, {
                        model: getCurrentModel(),
                        messages: [
                            {
                                role: 'system',
                                content: 'You are a helpful assistant that provides clear and concise summaries of web content.'
                            },
                            {
                                role: 'user',
                                content: `Please provide a concise summary of this webpage content:\n\n${textContent.substring(0, 4000)}`
                            }
                        ],
                        max_tokens: 500,
                        temperature: 0.7
                    }))
                });

                const summaryData = await summaryResponse.json();
                if (summaryData.choices && summaryData.choices.length > 0) {
                    const summary = summaryData.choices[0].message.content;
                    const urlLabel = toTry.length === 1 ? toTry[0] : toTry[0] + (toTry.length > 1 ? ` (first of ${toTry.length} URLs)` : '');
                    return {
                        success: true,
                        message: `Summary of ${urlLabel}:\n\n${summary}`
                    };
                } else {
                    throw new Error('Failed to generate summary');
                        }
            } catch (error) {
                console.error('Web scraping error:', error);
                        return { 
                            success: false, 
                    message: `Error scraping website: ${error.message}` 
                };
            }
        }

        // Add this new handler function for web searching
        async function handleWebSearch({ query }) {
            try {
                // Use the proxy endpoint for searching
                const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/search?query=${encodeURIComponent(query)}`;
                
                // Use authToken for authentication (the global fetch interceptor will also add it, but be explicit)
                const response = await fetch(proxyUrl, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });

                if (!response.ok) {
                    throw new Error(`Failed to search: ${response.statusText}`);
                }

                const data = await response.json();
                if (!data.results || data.results.length === 0) {
                    const noResultsMessage = `No results found for "${query}".`;
                    // Add to chat history
                    chatHistory.push({
                        role: 'assistant',
                        content: noResultsMessage
                    });
                            return { 
                                success: true, 
                        message: noResultsMessage
                    };
                }

                // Format the results into a readable message
                const resultText = data.results.map((result, index) => 
                    `${index + 1}. ${result.title}\nURL: ${result.url}\n${result.snippet}\n`
                ).join('\n');

                const searchResultMessage = `Search results for "${query}":\n\n${resultText}`;
                
                // Add to chat history
                chatHistory.push({
                    role: 'assistant',
                    content: searchResultMessage
                });

                        return { 
                    success: true, 
                    message: searchResultMessage
                };
            } catch (error) {
                console.error('Web search error:', error);
                const errorMessage = `Error performing web search: ${error.message}`;
                // Add error to chat history
                chatHistory.push({
                    role: 'assistant',
                    content: errorMessage
                });
                        return { 
                            success: false, 
                    message: errorMessage
                };
            }
        }

        function normalizeToolParametersText(rawText) {
            const text = typeof rawText === 'string' ? rawText.trim() : String(rawText || '').trim();
            const cdataText = text.startsWith('<![CDATA[') && text.endsWith(']]>')
                ? text.slice(9, -3).trim()
                : text;
            return cdataText
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'")
                .replace(/[“”]/g, '"')
                .replace(/[‘’]/g, "'");
        }

        function extractBalancedJsonCandidate(text) {
            if (typeof text !== 'string' || !text) return null;
            const startIndex = text.search(/[\[{]/);
            if (startIndex === -1) return null;
            const opening = text[startIndex];
            const closing = opening === '{' ? '}' : ']';
            let depth = 0;
            let inString = false;
            let escapeNext = false;

            for (let i = startIndex; i < text.length; i += 1) {
                const ch = text[i];
                if (inString) {
                    if (escapeNext) {
                        escapeNext = false;
                        continue;
                    }
                    if (ch === '\\') {
                        escapeNext = true;
                        continue;
                    }
                    if (ch === '"') {
                        inString = false;
                    }
                    continue;
                }
                if (ch === '"') {
                    inString = true;
                    continue;
                }
                if (ch === opening) {
                    depth += 1;
                    continue;
                }
                if (ch === closing) {
                    depth -= 1;
                    if (depth === 0) {
                        return text.slice(startIndex, i + 1);
                    }
                }
            }
            return null;
        }

        function parseLenientJsonObject(rawText) {
            const normalized = normalizeToolParametersText(rawText);
            if (!normalized) return null;
            const candidates = [normalized];
            const balanced = extractBalancedJsonCandidate(normalized);
            if (balanced && !candidates.includes(balanced)) {
                candidates.push(balanced);
            }

            for (const candidate of candidates) {
                try {
                    return JSON.parse(candidate);
                } catch (error) {
                    // Try simpler recovery passes below.
                }
            }

            for (const candidate of candidates) {
                try {
                    const repaired = candidate
                        .replace(/([{,]\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)/g, '$1"$2"$3')
                        .replace(/([{,]\s*)'([^']+?)'\s*:/g, '$1"$2":')
                        .replace(/:\s*'([^'\\]*(?:\\.[^'\\]*)*)'/g, ': "$1"');
                    return JSON.parse(repaired);
                } catch (error) {
                    // Keep trying.
                }
            }

            try {
                const xmlMatches = Array.from(normalized.matchAll(/<([A-Za-z_][A-Za-z0-9_-]*)>([\s\S]*?)<\/\1>/g));
                if (xmlMatches.length > 0) {
                    const parsed = {};
                    for (const [, key, value] of xmlMatches) {
                        const nested = parseLenientJsonObject(value.trim());
                        parsed[key] = nested !== null ? nested : value.trim();
                    }
                    return parsed;
                }
            } catch (error) {
                console.error('Error parsing XML parameter map:', error);
            }

            return null;
        }

        // Add this function to parse both XML-style and JSON tool responses
        function parseToolResponse(content) {
            console.log('Parsing tool response:', content);

            // Ignore any <tool> tags that occur inside fenced code blocks
            // This prevents example snippets from being executed as real tool calls
            const contentWithoutCode = typeof content === 'string'
                ? content.replace(/```[\s\S]*?```/g, '')
                : content;

            // Try XML format first, but only if tags appear at top-level content
            // Support both <tool> and <tool_call> tags (handle malformed XML where opening/closing tags differ)
            const toolMatch = contentWithoutCode.match(/<(?:tool|tool_call)>(.*?)<\/(?:tool|tool_call)>/);
            const paramsMatch = contentWithoutCode.match(/<parameters>([\s\S]*?)<\/parameters>/);
            
            if (toolMatch && paramsMatch) {
                const toolName = toolMatch[1].trim();
                const parameters = parseLenientJsonObject(paramsMatch[1]);
                if (parameters !== null) {
                    console.log('Successfully parsed XML format:', { toolName, parameters });
                    return {
                        function: {
                            name: toolName,
                            arguments: JSON.stringify(parameters)
                        }
                    };
                }
                console.error('Error parsing XML tool response:', paramsMatch[1]);
            }

            // Try parsing as direct JSON, but only if the content looks like JSON
            if (typeof content === 'string') {
                const trimmed = content.trim();
                if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                    try {
                        const jsonContent = JSON.parse(trimmed);
                        console.log('Parsed JSON content:', jsonContent);

                        // Handle Qwen-style format with action and contentPrompt
                        if (jsonContent.action && jsonContent.contentPrompt) {
                            console.log('Found Qwen format with action and contentPrompt');
                            return {
                                function: {
                                    name: jsonContent.action,
                                    arguments: JSON.stringify({
                                        contentPrompt: jsonContent.contentPrompt
                                    })
                                }
                            };
                        }

                        // Handle OpenAI-style function calling format
                        if (jsonContent.name && jsonContent.arguments) {
                            console.log('Found OpenAI function calling format');
                            return {
                                function: {
                                    name: jsonContent.name,
                                    arguments: typeof jsonContent.arguments === 'string'
                                        ? jsonContent.arguments
                                        : JSON.stringify(jsonContent.arguments)
                                }
                            };
                        }
                    } catch (error) {
                        // Silently ignore if content is not valid JSON
                        console.debug('Ignoring non-JSON tool response');
                    }
                } else if (trimmed.includes('contentPrompt')) {
                    // Handle case where the entire response is the parameters for a known tool name
                    console.log('Found direct contentPrompt format');
                    return {
                        function: {
                            name: 'runWorkflow',
                            arguments: trimmed
                        }
                    };
                }
            } else if (content && typeof content === 'object') {
                const jsonContent = content;
                // Handle Qwen-style format with action and contentPrompt
                if (jsonContent.action && jsonContent.contentPrompt) {
                    return {
                        function: {
                            name: jsonContent.action,
                            arguments: JSON.stringify({ contentPrompt: jsonContent.contentPrompt })
                        }
                    };
                }
                if (jsonContent.name && jsonContent.arguments) {
                    return {
                        function: {
                            name: jsonContent.name,
                            arguments: typeof jsonContent.arguments === 'string' ? jsonContent.arguments : JSON.stringify(jsonContent.arguments)
                        }
                    };
                }
            }

            console.log('No valid tool response format found');
            return null;
        }

        // Define tool patterns for task extraction
        const TOOL_PATTERNS = {
            runWorkflow: {
                patterns: [
                    /^workflow\.\s*(.+)$/i,
                    /^run workflow[:\s]+(.+)$/i,
                    /^execute workflow[:\s]+(.+)$/i,
                    /^workflow[:\s]+(.+)$/i
                ],
                extractArgs: (match) => ({ contentPrompt: match[1].trim() })
            },
            webSearch: {
                patterns: [
                    // "websearch for X" / "web search for X" so "and then" doesn't end up in query
                    /(?:web\s*search|websearch)\s+for\s+(.+?)(?:\s+and)?\s*$/i,
                    /(search|look up|find|get information|information about|tell me about) (.*?)(?=\s*(?:then|,|$))/i,
                    /search (?:for )?["'](.+?)["']/i
                ],
                extractArgs: (match) => ({ query: (match[2] || match[1] || match[0]).trim() })
            },
            scrapeWebsite: {
                patterns: [
                    /(scrape|read|summarize|get content from|look at) (?:the )?(first|1st|second|2nd|third|3rd|url|website|link|result|content at|page at|site|from) ?(?:from )?(?:the )?(?:url )?(?:at )?(?:address )?(?:["'])?([^"'\s]*)(?:["'])?/i,
                    /(?:go to|visit|open) (?:the )?(?:url|website|link|page) (?:at )?(?:["'])?([^"'\s]*)(?:["'])?/i
                ],
                extractArgs: (match, context) => {
                    const urlArg = match[3] || match[1];
                    // If it's a direct URL, use it; otherwise mark as pending
                    return { url: urlArg?.includes('http') ? urlArg : 'pending' };
                }
            },
            manageTodoList: {
                patterns: [
                    /(add|create|make|new) (?:a )?(?:new )?(?:todo|task|item|reminder|note)(?: (?:to|in|into) (?:the )?(?:todo )?list)?(?: saying| with)? ["']?([^"']+)["']?/i,
                    /(update|change|modify|edit) (?:the )?(?:todo|task|item|reminder|note) (?:number )?(\d+)(?: (?:to|with) ["']?([^"']+)["']?)?/i,
                    /(complete|done|finish|mark complete|check off) (?:the )?(?:todo|task|item|reminder|note) (?:number )?(\d+)/i,
                    /(delete|remove|clear) (?:the )?(?:todo|task|item|reminder|note)(?: number )?(\d+)?/i,
                    /(show|list|get|display) (?:my )?(?:due|overdue|scheduled due) (?:todo|task|item|reminder|note)s?/i,
                    /(show|list|display|get) (?:all )?(?:my )?(?:todo|task|item|reminder|note)s?(?:list)?/i
                ],
                extractArgs: (match) => {
                    const rawText = String(match[0] || '').toLowerCase();
                    if (/\bdue\b|\boverdue\b/.test(rawText)) {
                        return { action: 'due' };
                    }
                    const action = match[1].toLowerCase();
                    if (action.match(/add|create|make|new/i)) {
                        return { 
                            action: 'add',
                            taskDescription: match[2] || ''
                        };
                    } else if (action.match(/update|change|modify|edit/i)) {
                        return { 
                            action: 'update',
                            taskId: parseInt(match[2]),
                            taskDescription: match[3] || ''
                        };
                    } else if (action.match(/complete|done|finish|mark complete|check off/i)) {
                        return {
                            action: 'complete',
                            taskId: parseInt(match[2])
                        };
                    } else if (action.match(/delete|remove/i)) {
                        return {
                            action: 'delete',
                            taskId: parseInt(match[2])
                        };
                    } else if (action === 'clear') {
                        return { action: 'clear' };
                    } else {
                        return { action: 'list' };
                    }
                }
            },
            manageWorkingContext: {
                patterns: [
                    /(?:remember|memorize|note)(?: that| this)? ["']?([^"']+)["']?/i,
                    /(?:update|change|modify|edit)(?: the)? memory (?:item )?(?:number )?(\d+)(?: (?:to|with) ["']?([^"']+)["']?)?/i,
                    /(?:delete|remove|forget|clear)(?: the)? memory(?: item)?(?: number )?(\d+)?/i,
                    /(?:show|list|display|get|recall|what is in|what's in)(?: all)?(?: my)? memory(?:cache)?(?:list)?/i
                ],
                extractArgs: (match) => {
                    const action = match[1]?.toLowerCase();
                    if (action?.match(/remember|memorize|note/i)) {
                        return {
                            action: 'add',
                            memDescription: match[2] || match[1] || ''
                        };
                    } else if (action?.match(/update|change|modify|edit/i)) {
                        return {
                            action: 'update',
                            memId: parseInt(match[2]),
                            memDescription: match[3] || ''
                        };
                    } else if (action?.match(/delete|remove|forget/i)) {
                        return {
                            action: 'delete',
                            memId: parseInt(match[2])
                        };
                    } else if (action === 'clear') {
                        return { action: 'clear' };
                    } else {
                        return { action: 'list' };
                    }
                }
            },
            calculate: {
                patterns: [
                    /(?:calculate|compute|evaluate|solve|what is) (?:the )?(?:expression )?(\d+(?:[+\-*/]\d+)+)/i,
                    /(?:calculate|compute|evaluate|solve|what is) (?:the )?(?:result|answer|previous result|previous answer|last result|last answer) ?([+\-*/]) ?(\d+)/i,
                    /(?:calculate|compute|evaluate|solve|what is) (?:the )?(?:expression )?result ?([+\-*/]) ?(\d+)/i,
                    /(\d+(?:[+\-*/]\d+)+)/i  // Direct calculation pattern
                ],
                extractArgs: (match, context) => {
                    console.log('Calculate match:', match);
                    
                    // Check if this is a calculation using previous result
                    if (match[2] && match[3] || (match[1] && match[2])) {
                        const operator = match[1] || match[2];
                        const value = match[2] || match[3];
                        // Use placeholder for result that will be resolved at execution time
                        const expression = `RESULT${operator}${value}`;
                        console.log('Generated expression with placeholder:', expression);
                        return { expression };
                    }
                    
                    // Direct calculation
                    const expression = match[1] || match[0];
                    console.log('Direct expression:', expression);
                    return { expression: expression.replace(/[^0-9+\-*/\s.()]/g, '').trim() };
                }
            },
            llmQuery: {
                patterns: [
                    /^(?!workflow)(?!run workflow)(?!execute workflow)(what|who|where|when|why|how|tell me|explain|describe|list|give me|show me|can you|please|find|search) .+?(?=\s*(?:then|,|$))/i,
                    /^(?!workflow)(?!run workflow)(?!execute workflow)([^,.]+?(?:is|are|was|were|do|does|did|has|have|had|can|could|will|would|should|may|might)\s+.+?)(?=\s*(?:then|,|$))/i
                ],
                extractArgs: (match) => ({
                    query: match[1] || match[0]
                })
            },
            writeFile: {
                patterns: [
                    /(?:save|write|store|output|export)(?: the)?(?: result| response| content| data)? to (?:file |filename |filepath )?["']?([^"'\s]+\.(?:txt|csv|json))["']?/i,
                    /(?:create|generate|make)(?: a)? (?:new )?file (?:called |named )?["']?([^"'\s]+\.(?:txt|csv|json))["']? (?:with|containing)(?: the)?(?: result| response| content| data)?/i,
                    /(?:save|write) (?:to|into)(?: a)? file (?:called |named )?["']?([^"'\s]+\.(?:txt|csv|json))["']?/i
                ],
                extractArgs: async (match, context) => {
                    const filename = match[1];
                    // Get the last result from context if available
                    let content = '';
                    if (context && context.previousResults && context.previousResults.length > 0) {
                        const lastResult = context.previousResults[context.previousResults.length - 1];
                        if (lastResult.result.message === "Sure, I'd be happy to help! What do you want to know?") {
                            // Generate content about Pompeii using LLM
                            const response = await fetch(endpointInput.value, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': `Bearer ${apiKeyInput.value}`
                                },
                                body: JSON.stringify(buildCompatibleChatBody(endpointInput.value, {
                                    model: getCurrentModel(),
                                    messages: [
                                        {
                                            role: 'system',
                                            content: 'You are a knowledgeable historian. Provide a comprehensive but concise overview of the history of Pompeii, including its destruction by Mount Vesuvius and its archaeological significance.'
                                        },
                                        {
                                            role: 'user',
                                            content: 'What happened to Pompeii?'
                                        }
                                    ]
                                }))
                            });
                            const data = await response.json();
                            content = extractChoiceVisibleText(data?.choices?.[0] || {});
                        } else {
                            content = lastResult.result.message || '';
                        }
                    }
                    return {
                        filename: filename,
                        content: content
                    };
                }
            }
        };

        // Update preprocessTask to handle async operations
        async function preprocessTask(task, context) {
            task.originalArguments = task.function.arguments;
            const args = JSON.parse(task.function.arguments);
            
            switch (task.function.name) {
                case 'scrapeWebsite':
                    if (args.url === 'pending' && (context.searchResults.length > 0 || (context.urls && context.urls.length > 0))) {
                        // Prefer URL from parsed urls list, then from search result lines
                        let url = context.urls && context.urls.length > 0 ? context.urls[0] : null;
                        if (!url) {
                            const urlLine = context.searchResults.find(line => line.includes('URL:'));
                            if (urlLine) {
                                const idx = urlLine.indexOf('URL:');
                                url = idx >= 0 ? urlLine.slice(idx + 4).trim() : null;
                            }
                        }
                        if (url) {
                            task.function.arguments = JSON.stringify({ url });
                            responseOutput.value += `→ Found URL to scrape: ${url}\n`;
                        }
                    }
                    break;
                case 'writeFile':
                    // Re-extract args with async support
                    for (const pattern of TOOL_PATTERNS.writeFile.patterns) {
                        const match = task.originalText.match(pattern);
                        if (match) {
                            const newArgs = await TOOL_PATTERNS.writeFile.extractArgs(match, context);
                            task.function.arguments = JSON.stringify(newArgs);
                            break;
                        }
                    }
                    break;
            }
        }

        // Update extractTasks function to handle async operations
        async function extractTasks(prompt) {
            console.log('extractTasks - Starting with prompt:', prompt);
            const tasks = [];
            const segments = prompt.split(/\s*(?:then|next|after that|afterwards|finally)\s*/i);
            console.log('extractTasks - Split segments:', segments);
            
            // Initialize context with variables Map
            const context = {
                variables: new Map(),
                searchResults: [],
                urls: [],
                previousResults: []
            };
            console.log('extractTasks - Initialized context:', context);
            
            for (const segment of segments) {
                let taskFound = false;
                const trimmedSegment = segment.trim();
                console.log('extractTasks - Processing segment:', trimmedSegment);
                
                // Try each tool's patterns
                for (const [toolName, tool] of Object.entries(TOOL_PATTERNS)) {
                    if (taskFound) break;
                    
                    for (const pattern of tool.patterns) {
                        const match = trimmedSegment.match(pattern);
                        if (match) {
                            console.log(`extractTasks - Found match for ${toolName}:`, match);
                            const args = tool.extractArgs.constructor.name === 'AsyncFunction' 
                                ? await tool.extractArgs(match, context)
                                : tool.extractArgs(match, context);
                            console.log('extractTasks - Extracted args:', args);
                            
                            if (args && Object.keys(args).length > 0) {
                                const task = {
                                    function: {
                                        name: toolName,
                                        arguments: JSON.stringify(args)
                                    },
                                    originalText: trimmedSegment,
                                    context: context
                                };
                                console.log('extractTasks - Created task:', task);
                                tasks.push(task);
                                taskFound = true;
                                break;
                            }
                        }
                    }
                }

                // If no tool pattern matched and the segment isn't empty
                if (!taskFound && trimmedSegment) {
                    console.log('extractTasks - No tool match found, treating as LLM query:', trimmedSegment);
                    const task = {
                        function: {
                            name: 'llmQuery',
                            arguments: JSON.stringify({ query: trimmedSegment })
                        },
                        originalText: trimmedSegment,
                        context: context
                    };
                    console.log('extractTasks - Created LLM query task:', task);
                    tasks.push(task);
                }
            }

            console.log('extractTasks - Final tasks:', tasks);
            return tasks;
        }

        // Update the processToolChain function
        async function processToolChain(tasks) {
            console.log('processToolChain - Starting with tasks:', tasks);
            let results = [];
            let context = {
                searchResults: [],
                urls: [],
                variables: new Map(),
                previousResults: []
            };
            console.log('processToolChain - Initialized context:', context);

            // Build task list for display (do not add to history yet; one message at end)
            let responseContent = `Detected ${tasks.length} tasks in the chain:\n`;
            tasks.forEach((task, index) => {
                console.log(`processToolChain - Task ${index + 1}:`, task);
                responseContent += `${index + 1}. ${task.originalText}\n`;
            });
            responseContent += '\nExecuting tasks...\n\n';
            responseOutput.value = responseContent;

            for (let i = 0; i < tasks.length; i++) {
                const task = tasks[i];
                console.log(`processToolChain - Processing task ${i + 1}/${tasks.length}:`, task);
                
                // Update progress in response box
                responseOutput.value += `Processing task ${i + 1}/${tasks.length}: ${task.originalText}\n`;
                
                try {
                    // Ensure task has access to current context
                    task.context = context;
                    
                    // Pre-process task based on context
                    console.log('processToolChain - Pre-processing task:', task);
                    await preprocessTask(task, context);
                    console.log('processToolChain - After pre-processing:', task);
                    
                    // Execute the task with context
                    console.log('processToolChain - Executing task with context:', context);
                    const result = await executeToolCall(task.function, context);
                    console.log('processToolChain - Task execution result:', result);
                    
                    // Only add successful results
                    if (result && result.success) {
                        // Post-process result and update context
                        console.log('processToolChain - Post-processing result:', result);
                        await postprocessResult(result, task, context);
                        console.log('processToolChain - Updated context:', context);

                        // Store the result
                        context.previousResults.push({
                            task: task.originalText,
                            result: result
                        });

                        results.push({
                            task: task.originalText,
                            result: result
                        });

                        // Show interim result
                        responseOutput.value += `✓ Task completed: ${result.message}\n\n`;
                    } else {
                        console.warn('processToolChain - Task failed:', result);
                        responseOutput.value += `✗ Task failed: ${result?.message || 'Unknown error'}\n\n`;
                    }

                } catch (error) {
                    console.error(`processToolChain - Error in task ${i + 1}:`, error);
                    responseOutput.value += `✗ Task failed: ${error.message}\n\n`;
                }
            }

            // Format final results
            console.log('processToolChain - All results:', results);
            let finalOutput;
            if (results.length > 0) {
                finalOutput = results
                    .map((r, index) => `Step ${index + 1} (${r.task}):\n${r.result.message}`)
                    .join('\n\n---\n\n');
                
                // Only read out the last step using TTS
                const lastResult = results[results.length - 1];
                if (lastResult) {
                    const lastStepOutput = `Final result: ${lastResult.result.message}`;
                    textToSpeech(lastStepOutput);
                }
            } else {
                finalOutput = 'Task chain completed, but no successful results were obtained.';
                textToSpeech(finalOutput);
            }

            // Single combined message: task list + results (avoids repeating Step 1 in history)
            const combinedOutput = responseContent + finalOutput;
            responseOutput.value = combinedOutput;
            // Caller adds to history once with returned value
            console.log('processToolChain - Final output:', finalOutput);

            return combinedOutput;
        }

        // Helper function to postprocess result and update context
        async function postprocessResult(result, task, context) {
            if (!result.success) return;

            switch (task.function.name) {
                case 'webSearch':
                    if (result.success && result.message) {
                        // Parse search results defensively so chain can continue to next step
                        const parts = result.message.split('\n\n');
                        const resultsBlock = parts.length > 1 ? parts[1] : parts[0];
                        const searchResults = (resultsBlock || result.message)
                            .split('\n')
                            .filter(line => line.trim());
                        context.searchResults = searchResults;
                        // Extract URLs for next step (e.g. "scrape the first URL")
                        const urls = searchResults
                            .filter(line => line.includes('URL:'))
                            .map(line => {
                                const idx = line.indexOf('URL:');
                                return idx >= 0 ? line.slice(idx + 4).trim() : null;
                            })
                            .filter(Boolean);
                        context.urls = urls;
                    }
                    break;
                case 'manageTodoList':
                    // Store the current todo list state in context
                    if (result.success && todoList) {
                        context.currentTodoList = [...todoList];
                    }
                    break;
                case 'manageWorkingContext':
                    // Store the current memory cache state in context
                    if (result.success && memoryCache) {
                        context.currentMemoryCache = [...memoryCache];
                    }
                    break;
                case 'calculate':
                    if (result.success) {
                        const match = result.message.match(/=\s*(-?\d+\.?\d*)/);
                        if (match) {
                            const calculationResult = parseFloat(match[1]);
                            context.variables.set('lastCalculation', calculationResult);
                            console.log('Stored calculation result:', calculationResult);
                        }
                    }
                    break;
                // Add more postprocessing cases for other tools as needed
            }
        }

        // Update the fetchOpenAIResponse function to handle context properly
        async function uploadPendingAttachmentsForChat() {
            if (!pendingAttachmentFiles.length) return [];

            const formData = new FormData();
            pendingAttachmentFiles.forEach((file) => {
                formData.append('files', file, file.name);
            });
            formData.append('conversation_id', activeConversationId || 'default');

            const response = await fetch(`${PROXY_BASE_URL}/v1/files/attachments`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                throw new Error(data.detail || data.message || 'Failed to upload attachments.');
            }

            return Array.isArray(data.attachments) ? data.attachments : [];
        }

        function buildAttachmentPromptText(promptText, attachments) {
            const attachmentList = Array.isArray(attachments) ? attachments : [];
            if (!attachmentList.length) return promptText;

            const basePrompt = (promptText || '').trim() || 'Please review the attached file(s).';
            const manifestLines = attachmentList.map((attachment) => {
                const relPath = attachment.relative_path || attachment.relativePath || attachment.filename || 'attachment';
                const original = attachment.original_filename || attachment.originalFilename || attachment.filename || relPath;
                const mimeType = attachment.mime_type || attachment.mimeType || 'application/octet-stream';
                const sizeBytes = Number(attachment.size_bytes || attachment.sizeBytes || 0);
                return `- ${relPath} (original: ${original}, type: ${mimeType}, size: ${sizeBytes} bytes)`;
            });

            return `${basePrompt}\n\nAttached files saved in scratch:\n${manifestLines.join('\n')}\nUse the filesystem read skill tool shown in the dynamic skill list, usually skill__filesystem_read_text, with these scratch-relative paths to inspect attachments before answering.\nFor attached PDFs, DOCX, XLSX, text files, Markdown files, and images, inspect the attachment first instead of guessing.\nDo not call pdfToPowerPoint unless the user explicitly asks to convert a PDF or Markdown document into a PowerPoint or slide deck.`;
        }

        async function fetchOpenAIResponse(promptText) {
            // Validate promptText parameter
            if (typeof promptText !== 'string') {
                console.error('fetchOpenAIResponse called with invalid promptText:', promptText);
                status.textContent = "Error: Invalid input text. Please try again.";
                return;
            }
            
            // Trim and validate the prompt text
            promptText = promptText.trim();
            const hasPendingAttachments = pendingAttachmentFiles.length > 0;
            if (promptText.length === 0 && !hasPendingAttachments) {
                console.error('fetchOpenAIResponse called with empty promptText and no attachments');
                status.textContent = "Error: Empty input text. Please try again.";
                return;
            }
            
            console.log('fetchOpenAIResponse called with promptText:', promptText); // Debug log

            if (activeChatRequest) {
                status.textContent = 'A response is already in progress. Please wait.';
                return;
            }

            const chatRequestController = new AbortController();
            const chatRequestTimeoutId = window.setTimeout(() => {
                try {
                    chatRequestController.abort();
                } catch (_) {}
            }, CHAT_REQUEST_TIMEOUT_MS);
            const chatRequestSignal = chatRequestController.signal;
            activeChatRequest = { controller: chatRequestController, startedAt: Date.now() };
            setChatRequestUiLocked(true);
            startVrmProcessingThinkingLoop();

            try {
            let endpoint = endpointInput.value;
            const apiKey = apiKeyInput.value.trim();
            let uploadedAttachments = [];
            let promptTextForModel = promptText;

            if (hasPendingAttachments) {
                updateProgressState('Uploading attachments');
                uploadedAttachments = await uploadPendingAttachmentsForChat();
                promptTextForModel = buildAttachmentPromptText(promptText, uploadedAttachments);
            }
            
            // Store the original endpoint for proxy routing
            const originalEndpoint = endpoint;

            // Initialize context object for both single and chained tool calls
            const context = {
                searchResults: [],
                urls: [],
                variables: new Map(),
                previousResults: []
            };

            // Start periodic progress updates only for request-like turns, not small talk.
            if (shouldStartProgressUpdatesForPrompt(promptTextForModel)) {
                startProgressUpdates('Analyzing request');
            }

            // Check for tool chaining before proceeding with normal processing
            const hasChaining = promptTextForModel.toLowerCase().includes('then') || 
                               promptTextForModel.match(/first.*second|1st.*2nd|step.*step/i);

            if (hasChaining) {
                console.log('Detected task chaining in prompt');
                updateProgressState('Planning tool chain');
                const tasks = await extractTasks(promptTextForModel);
                
                if (tasks.length > 1) {
                    console.log('Executing task chain:', tasks);
                    updateProgressState('Executing tool chain');
                    const chainResult = await processToolChain(tasks);
                    
                    chatHistory.push({
                        role: 'assistant',
                        content: chainResult
                    });
                    
                    responseOutput.value = chainResult;
                    addMessageToHistory('assistant', chainResult); // Add to message history
                    textToSpeech(chainResult);
                    if (uploadedAttachments.length) {
                        clearPendingAttachments();
                    }
                    stopProgressUpdates();
                    return;
                }
            }
    
            // Determine if we need to use OpenAI's endpoint
            if (clipboardVisionEnabled && clipboardType === 'image') {
                endpoint = 'http://localhost:1234/v1/chat/completions';
            }
                endpointInput.value = endpoint;
            
            // Route through proxy server to avoid mixed content issues with HTTPS
            // Use the proxy endpoint and pass the original endpoint as a query parameter
            const proxyEndpoint = `${PROXY_BASE_URL}/v1/proxy/chat/completions?endpoint=${encodeURIComponent(endpoint)}`;
            endpoint = proxyEndpoint;

            const systemPrompt = `You are EVA, a useful AI assistant that can use various tools to help users.

When tool calling is available, prefer native function/tool calls from the API.
If the model cannot emit native tool calls, use this XML fallback format:
<tool>tool_name</tool>
<parameters>
{
    "parameter1": "value1",
    "parameter2": "value2"
}
</parameters>

IMPORTANT: Prefer native tool calls. Use the XML fallback only when native tool calls are unavailable.

Available tools:

1. manageTodoList
Description: Manages a todo list with scheduler support
Parameters:
{
    "action": "list|due|add|update|complete|delete|clear",
    "taskId": "number (for update/complete/delete)",
    "taskDescription": "string (for add/update)",
    "scheduledFor": "string (optional ISO-8601 datetime)",
    "recurrence": {"frequency": "hourly|daily|weekly|monthly|yearly", "interval": "number >= 1"},
    "clearSchedule": "boolean (update only)",
    "clearRecurrence": "boolean (update only)"
}

2. manageWorkingContext
Description: Manages memory storage
Parameters:
{
    "action": "list|add|update|delete|clear",
    "memId": "number (for update/delete)",
    "memDescription": "string (for add/update)"
}

3. navigateToUrl
Description: Opens a website
Parameters:
{
    "url": "string (must include http:// or https://)"
}

4. openChatToUser
Description: Opens Teams chat
Parameters:
{
    "url": "string (Teams URL)"
}

5. calculate
Description: Performs calculations
Parameters:
{
    "expression": "string (e.g., '2 + 2')"
}

6. runWorkflow
Description: Executes workflows for code generation and automation tasks
Parameters:
{
    "contentPrompt": "string (the task to execute)"
}

7. runCodexCli
Description: Runs Codex CLI non-interactively to make CATBot code changes or add new tool capabilities. Use this when the user asks to modify the CATBot codebase or implement new tools. The prompt must be self-contained with the user's request, relevant error text, and instructions to inspect/search the repository before editing.
Parameters:
{
    "prompt": "string (self-contained instructions for Codex to execute)",
    "timeoutSeconds": "number (optional; default 1800, max 7200)"
}

8. restartProxyServer
Description: Restarts the CATBot proxy server so new/updated tools are loaded. Use this after tool or code changes. Requires explicit confirmation.
Parameters:
{
    "confirm": "boolean (must be true)",
    "reason": "string (optional reason)"
}

9. scrapeWebsite
Description: Fetches and summarizes content from a website
Parameters:
{
    "url": "string (single URL; must include http:// or https://)",
    "urls": "array of strings (optional retry list; first successful URL is used)",
    "render_js": "boolean (optional; true for JavaScript-rendered websites)",
    "render_engine": "string (optional: auto|playwright|selenium)",
    "wait_for_selector": "string (optional CSS selector to wait for before extraction)",
    "js_wait_ms": "number (optional extra wait in milliseconds for dynamic content)"
}

10. webSearch
Description: Searches the web for information about a topic and returns relevant results
Parameters:
{
    "query": "string (the search query or keywords to look for)"
}

11. fetchNews
Description: Fetches news articles matching given keywords and saves them to a CSV file
Parameters:
{
    "searchTerm": "string (keywords to search the news for)",
    "filename": "string (CSV filename to save to)"
}

12. pdfToPowerPoint
Description: Use this tool only when the user explicitly wants to convert a PDF or Markdown document to PowerPoint, turn one into a presentation, or create slides from one. Do not use it for reviewing, summarizing, or reading an attached source file. For structured inputs such as uploaded attachments, inline Markdown, or base64 content, use source. For simple PDF/Markdown URLs or scratch-relative paths, use sourceUrl and sourceType when helpful; for legacy PDF calls, pdfUrl is still accepted. If they do not provide a source, omit source, sourceUrl, and pdfUrl and the user will be prompted to upload a file. Required: title, filename.
Parameters:
{
    "source": {
        "type": "object (optional structured source descriptor)",
        "value": "string (optional URL, scratch-relative path, or inline Markdown content)",
        "url": "string (optional source URL)",
        "path": "string (optional scratch-relative path)",
        "relativePath": "string (optional scratch-relative path for an uploaded attachment)",
        "content": "string (optional inline Markdown content)",
        "contentBase64": "string (optional base64-encoded PDF/Markdown file content)",
        "mimeType": "string (optional MIME type for inline/base64 content)",
        "filename": "string (optional filename used for type detection)"
    },
    "sourceUrl": "string (optional; URL or scratch-relative path to a PDF or Markdown source file)",
    "sourceType": "string (optional; 'pdf' or 'markdown')",
    "pdfUrl": "string (optional legacy alias for PDF source URL/path)",
    "title": "string (required; presentation title)",
    "author": "string (optional)",
    "maxSlides": "number (optional; default 15)",
    "filename": "string (required; e.g. 'presentation.pptx')"
}

13. uploadToGoogleDrive
Description: Uploads a file from the scratch directory to Google Drive using service account authentication. Use the filename relative to the scratch directory.
Parameters:
{
    "filePath": "string (filename relative to scratch directory, e.g. report.docx or climate_updates.csv)",
    "fileName": "string (optional custom name for the file in Drive)"
}

14. Dynamic filesystem skill tools
Description: File operations are provided by dynamic skill aliases such as 'skill__filesystem_read_text', 'skill__filesystem_list_files', 'skill__filesystem_write_text', and 'skill__filesystem_search_files'. Use the exact alias listed in the dynamic skill section for reading, listing, writing, and searching scratch files.
Parameters:
{
    "Refer to the dynamic skill schema for the specific alias": "filesystem read/list/write/search tools are loaded at runtime"
}

Examples:
User: "Remember to buy milk"
Assistant: <tool>manageWorkingContext</tool>
<parameters>
{
    "action": "add",
    "memDescription": "Buy milk"
}
</parameters>

User: "Add a task to call John"
Assistant: <tool>manageTodoList</tool>
<parameters>
{
    "action": "add",
    "taskDescription": "Call John"
}
</parameters>

User: "Open google.com"
Assistant: <tool>navigateToUrl</tool>
<parameters>
{
    "url": "https://google.com"
}
</parameters>

User: "Calculate 2 + 2"
Assistant: <tool>calculate</tool>
<parameters>
{
    "expression": "2 + 2"
}
</parameters>

User: "Summarize the content from example.com"
Assistant: <tool>scrapeWebsite</tool>
<parameters>
{
    "url": "https://example.com"
}
</parameters>

User: "Search for information about artificial intelligence"
Assistant: <tool>webSearch</tool>
<parameters>
{
    "query": "artificial intelligence"
}
</parameters>

User: "Get the latest news about climate policy and save it to climate_updates.csv"
Assistant: <tool>fetchNews</tool>
<parameters>
{
    "searchTerm": "climate policy",
    "filename": "climate_updates.csv"
}
</parameters>

User: "Read the content from report.txt"
Assistant: <tool>skill__filesystem_read_text</tool>
<parameters>
{
    "path": "report.txt"
}
</parameters>

User: "List the files in the scratch directory"
Assistant: <tool>skill__filesystem_list_files</tool>
<parameters>
{
}
</parameters>

User: "Write a summary to summary.docx"
Assistant: <tool>skill__filesystem_write_text</tool>
<parameters>
{
    "path": "summary.docx",
    "content": "This is a comprehensive summary of the report..."
}
</parameters>

User: "Turn this PDF into a PowerPoint: https://example.com/report.pdf. Title it 'Quarterly Report' and save as report.pptx"
Assistant: <tool>pdfToPowerPoint</tool>
<parameters>
{
    "sourceUrl": "https://example.com/report.pdf",
    "sourceType": "pdf",
    "title": "Quarterly Report",
    "filename": "report.pptx"
}
</parameters>

User: "Convert my PDF to a PowerPoint and save it as my_preso.pptx"
Assistant: <tool>pdfToPowerPoint</tool>
<parameters>
{
    "title": "My Presentation",
    "filename": "my_preso.pptx"
}
</parameters>

User: "Create a PowerPoint from scratch/notes/quarterly-update.md and save it as quarterly-update.pptx"
Assistant: <tool>pdfToPowerPoint</tool>
<parameters>
{
    "sourceUrl": "scratch/notes/quarterly-update.md",
    "sourceType": "markdown",
    "title": "Quarterly Update",
    "filename": "quarterly-update.pptx"
}
</parameters>

User: "Turn the uploaded attachment attachments/web/demo/brief.md into a deck called brief.pptx"
Assistant: <tool>pdfToPowerPoint</tool>
<parameters>
{
    "source": {
        "type": "attachment",
        "relativePath": "attachments/web/demo/brief.md",
        "filename": "brief.md",
        "mimeType": "text/markdown"
    },
    "sourceType": "markdown",
    "title": "Brief",
    "filename": "brief.pptx"
}
</parameters>

User: "Upload the climate_updates.csv file to Google Drive"
Assistant: <tool>uploadToGoogleDrive</tool>
<parameters>
{
    "filePath": "climate_updates.csv",
    "fileName": "Latest Climate News"
}
</parameters>

User: "workflow. code a snake game in python"
Assistant: <tool>runWorkflow</tool>
<parameters>
{
    "contentPrompt": "code a snake game in python"
}
</parameters>

User: "workflow. build a javascript todo app"
Assistant: <tool>runWorkflow</tool>
<parameters>
{
    "contentPrompt": "build a javascript todo application that runs without error in a browser. It should use local storage to save the tasks."
}
</parameters>

User: "workflow. create a react component"
Assistant: <tool>runWorkflow</tool>
<parameters>
{
    "contentPrompt": "create a react component"
}
</parameters>

IMPORTANT REMINDER: Use native tool calls when possible. Use <tool> and <parameters> XML only as a fallback.

Current memory cache contents:
${memoryCache.map((item, index) => `${index + 1}. ${item}`).join('\n')}`;

            const toolingBundle = await buildToolingBundle(false, { signal: chatRequestSignal });
            const tools = toolingBundle.tools;
            const dynamicSkillPrompt = toolingBundle.skillPromptLines.length
                ? `\n\nAdditional Skill Framework tools (dynamic):\n${toolingBundle.skillPromptLines.join('\n')}\nUse the alias exactly as listed for native tool calls; it maps to the qualified skill tool on the server.`
                : '';
            const compactMemoryLines = memoryCache.length
                ? memoryCache.map((item, index) => `${index + 1}. ${item}`).join('\n')
                : '(empty)';
            const compactSystemPrompt = `You are EVA, a helpful AI assistant with access to tools.

Tool calling rules:
- Prefer native tool calls when available.
- If native tool calls are unavailable, use XML fallback:
<tool>tool_name</tool>
<parameters>
{ "key": "value" }
</parameters>
- Ask follow-up questions when required inputs are missing.
- Do not invent tool outputs; rely on real tool results.

Task-specific rules:
- For attached files, inspect them with the filesystem read tool before answering.
- Use pdfToPowerPoint only when the user explicitly asks to convert a PDF or Markdown document into PowerPoint/slides.
- For CATBot code/tool changes, use runCodexCli with a self-contained prompt that includes the user's actual request, error text, and instructions to inspect/search the repository before editing.
- Call restartProxyServer only with explicit user confirmation.
- For scratch files, use relative filenames and preserve requested output names.

            Current memory cache contents:
${compactMemoryLines}`;

            // Preserve existing system prompt by default; user input overrides it
            let effectiveSystemPrompt = systemPromptInput.value.trim() || compactSystemPrompt;
            const soulPrompt = (envToolDefaults && typeof envToolDefaults.soulPrompt === 'string')
                ? envToolDefaults.soulPrompt.trim()
                : '';
            if (dynamicSkillPrompt) {
                effectiveSystemPrompt = `${effectiveSystemPrompt}\n${dynamicSkillPrompt}`;
            }
            if (soulPrompt) {
                effectiveSystemPrompt = `${soulPrompt}\n\n${effectiveSystemPrompt}`;
            }
            
            // Prepend context: timezone, knowledge-gap awareness, and todo execution rules (always applies)
            const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            const contextBlock = `Context: You are running in timezone ${userTimezone}. Use this when interpreting dates/times unless the user specifies otherwise.
Knowledge awareness: Your training has a cutoff. Acknowledge your knowledge gap; do not assume the current year or recent events. When the user provides current facts, corrections, or information that differs from your training (e.g., "it's 2025 now", "that API changed"), accept them as authoritative and do not contradict them.
Todo execution: Task IDs are stable and are not list indexes. When the user asks to execute a task, use executeTodoTask with the requested taskId (from the current todo list). Multiple task executions may run in parallel. If the result has status "paused_awaiting_feedback", ask the user for input and call resumeTodoExecution (include taskId if multiple paused tasks exist). If the result has status "awaiting_confirmation", tell the user the task is done and call completeTodoTask with the returned taskId when they confirm. For cancel requests while multiple tasks are active, call cancelTodoExecution with taskId.

`;
            effectiveSystemPrompt = contextBlock + effectiveSystemPrompt;
            
            // Get user name from tool settings and add to system prompt
            // This works whether using custom prompt or default prompt
            const userName = userNameInput.value.trim() || 'User';
            if (userName && userName !== 'User') {
                // Prepend user name info to the system prompt (works with both custom and default)
                effectiveSystemPrompt = `The user you are talking to is named ${userName}.\n\n${effectiveSystemPrompt}`;
            }
            
            // Retrieve shared, server-ranked conversation memory context.
            let memoryContext = null;
            if (!philosopherModeActive) {
                memoryContext = await fetchConversationMemoryContext(promptTextForModel);
                if (memoryContext) {
                    effectiveSystemPrompt += `\n\n${memoryContext}`;
                }
            }
            
            const modelHistory = isToolRequest ? [] : buildModelHistoryWindow();
            const messages = [
                { 
                    role: 'system', 
                    content: effectiveSystemPrompt
                },
                ...modelHistory,
                {
                    role: 'user',
                    content: promptTextForModel
                }
            ];

            // Track if clipboard content was used (store in a way that persists through async operations)
            const hadClipboardContent = clipboardData && clipboardVisionEnabled;
            const clipboardContentType = clipboardType; // Store type before potential clearing

            // Add text content if present (prepend to user message)
            if (clipboardData && clipboardType === 'text' && clipboardVisionEnabled) {
                const originalPrompt = messages[messages.length - 1].content;
                messages[messages.length - 1].content = `[Clipboard content: ${clipboardData}]\n\n${originalPrompt}`;
            }

            const visionParts = [];
            if (clipboardData && clipboardType === 'image' && clipboardVisionEnabled) {
                const clipboardDataUrl = await fileToDataUrl(clipboardData);
                if (clipboardDataUrl) {
                    visionParts.push({
                        type: 'image_url',
                        image_url: {
                            url: clipboardDataUrl,
                            detail: 'auto'
                        }
                    });
                }
            }

            const attachmentVisionParts = await buildVisionImagePartsFromFiles(pendingAttachmentFiles);
            if (attachmentVisionParts.length) {
                visionParts.push(...attachmentVisionParts);
            }

            if (visionParts.length) {
                const currentPromptText = coerceMessageText(messages[messages.length - 1].content || '').trim();
                const contentParts = [];
                if (currentPromptText) {
                    contentParts.push({
                        type: 'text',
                        text: currentPromptText
                    });
                }
                messages[messages.length - 1].content = [...contentParts, ...visionParts];
            }

            const body = buildCompatibleChatBody(endpoint, {
                model: getCurrentModel(),
                messages: messages,
                max_tokens: 4096,
                temperature: 0.7,
                stream: false,
                // Provide tools per LM Studio tool-use docs
                tools: tools,
                tool_choice: 'auto'
            });

            // Add user message to history before sending
            console.log('Adding user message to history with content:', promptTextForModel); // Debug log
            addMessageToHistory('user', promptTextForModel);
            
            try {
                // Add pulsing effect to indicate we are waiting for the API
                responseOutput.classList.add('responding');
                messageHistory.classList.add('responding'); // Add pulsing effect to message history
                updateProgressState('Contacting model');
                console.log('Sending request:', {
                    endpoint,
                    model: getCurrentModel(),
                    prompt: promptTextForModel
                });
                console.log('Full request:', stringifyPayloadForLog(body));
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...buildOptionalAuthorizationHeaders(apiKey)
                    },
                    signal: chatRequestSignal,
                    body: JSON.stringify(body)
                });

                const data = await parseJsonResponseWithErrors(response, {
                    action: 'chat',
                    endpoint: originalEndpoint,
                    model: getCurrentModel()
                });
                console.log('Response from LLM:', JSON.stringify(data, null, 2));

                if (data.choices && data.choices.length > 0) {
                    const firstChoice = data.choices[0] || {};
                    const message = getChoiceMessage(firstChoice);
                    console.log('Processing message:', message);
                    const initialAssistantMessage = buildAssistantHistoryMessage(message);

                    // Handle LM Studio/OpenAI function/tool calling first
                    if (message.tool_calls && Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
                        try {
                            // Add the assistant's tool call turn to messages
                            messages.push(initialAssistantMessage);

                            let lastToolSummary = '';

                            // Execute each tool call and push results
                            for (const tc of message.tool_calls) {
                                const toolName = tc?.function?.name || tc?.name || 'tool';
                                updateProgressState(`Executing tool: ${toolName}`);
                                const toolResult = await executeToolCall(tc, context);
                                const toolResultContent = formatToolResultForModel(toolResult);
                                lastToolSummary = extractToolResultSummary(toolResult);
                                
                                messages.push({
                                    role: 'tool',
                                    content: toolResultContent,
                                    tool_call_id: tc.id
                                });
                            }

                            // Follow-up request to get the final assistant response after tool execution
                            updateProgressState('Requesting final response');
                            const followupResponse = await fetch(endpoint, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    ...buildOptionalAuthorizationHeaders(apiKey)
                                },
                                signal: chatRequestSignal,
                                body: JSON.stringify(buildCompatibleChatBody(endpoint, {
                                    model: getCurrentModel(),
                                    messages: messages,
                                    max_tokens: 4096,
                                    temperature: 0.7,
                                    tools: tools,
                                    tool_choice: 'auto'
                                }))
                            });
                            const followupData = await parseJsonResponseWithErrors(followupResponse, {
                                action: 'chat',
                                endpoint: originalEndpoint,
                                model: getCurrentModel()
                            });
                            let finalMessage = followupData?.choices?.[0]?.message || {};
                            let finalContent = getVisibleAssistantText(finalMessage);
                            let followupToolIterations = 0;

                            while (followupToolIterations < 4) {
                                const nativeFollowupCalls = Array.isArray(finalMessage?.tool_calls)
                                    ? finalMessage.tool_calls
                                    : [];
                                const finalRawContent = coerceMessageText(finalMessage?.content || '');
                                const xmlFollowupCall = (!nativeFollowupCalls.length && finalRawContent)
                                    ? parseToolResponse(finalRawContent)
                                    : null;

                                if (!nativeFollowupCalls.length && !xmlFollowupCall) {
                                    break;
                                }

                                if (nativeFollowupCalls.length) {
                                    messages.push(buildAssistantHistoryMessage(finalMessage));
                                    for (const tc of nativeFollowupCalls) {
                                        const toolName = tc?.function?.name || tc?.name || 'tool';
                                        updateProgressState(`Executing tool: ${toolName}`);
                                        const toolResult = await executeToolCall(tc, context);
                                        const toolResultContent = formatToolResultForModel(toolResult);
                                        lastToolSummary = extractToolResultSummary(toolResult);
                                        messages.push({
                                            role: 'tool',
                                            content: toolResultContent,
                                            tool_call_id: tc.id
                                        });
                                    }
                                } else if (xmlFollowupCall) {
                                    const xmlToolName = xmlFollowupCall?.function?.name || xmlFollowupCall?.name || 'tool';
                                    updateProgressState(`Executing tool: ${xmlToolName}`);
                                    const xmlToolResult = await executeToolCall(xmlFollowupCall, context);
                                    const xmlToolResultContent = formatToolResultForModel(xmlToolResult);
                                    lastToolSummary = extractToolResultSummary(xmlToolResult);

                                    messages.push(buildAssistantHistoryMessage(finalMessage));
                                    messages.push({ role: 'user', content: `Tool result: ${xmlToolResultContent}` });
                                }

                                updateProgressState('Requesting final response');
                                const chainedFollowupResponse = await fetch(endpoint, {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        ...buildOptionalAuthorizationHeaders(apiKey)
                                    },
                                    signal: chatRequestSignal,
                                    body: JSON.stringify(buildCompatibleChatBody(endpoint, {
                                        model: getCurrentModel(),
                                        messages: messages,
                                        max_tokens: 4096,
                                        temperature: 0.7,
                                        tools: tools,
                                        tool_choice: 'auto'
                                    }))
                                });
                                const chainedFollowupData = await parseJsonResponseWithErrors(chainedFollowupResponse, {
                                    action: 'chat',
                                    endpoint: originalEndpoint,
                                    model: getCurrentModel()
                                });
                                finalMessage = chainedFollowupData?.choices?.[0]?.message || {};
                                finalContent = getVisibleAssistantText(finalMessage);
                                followupToolIterations += 1;
                            }

                            if (finalContent) {
                                responseOutput.value = finalContent;
                                addMessageToHistory('assistant', finalContent); // Add to message history (also updates chatHistory)
                                
                                // Automatically extract memories from conversation (async, non-blocking)
                                extractMemoriesFromConversation().catch(err => {
                                    console.warn('Memory extraction failed:', err);
                                });
                                
                                // Clear clipboard content after successful followup response
                                if (hadClipboardContent) {
                                    clearClipboardPreview();
                                    console.log('Clipboard content cleared after followup response');
                                }
                                if (uploadedAttachments.length) {
                                    clearPendingAttachments();
                                }
                                
                                textToSpeech(finalContent);
                        const expressionFile = detectExpressionFromText(finalContent);
                        if (expressionFile && live2dModel) {
                            await live2dModel.expression(expressionFile);
                        }
                        // Trigger VRM love pose when Love eye is detected
                        try {
                            const lowered = (finalContent || '').toLowerCase();
                            const loveHit = ['happy','joy','glad','excited','wonderful','love','lovely','delighted','delight','romantic'].some(k => lowered.includes(k));
                            const thinkHit = ['thinking','consider','perhaps','maybe','hmm','interesting','curious','think','think about','ponder'].some(k => lowered.includes(k));
                            const cryHit = ['sad','upset','sorry','disappointed','unhappy','crying','cry'].some(k => lowered.includes(k));
                            const angryHit = ['angry','mad','furious','annoyed','irritated','frustrated','harsh'].some(k => lowered.includes(k));
                            if (loveHit) {
                                vrmLovePoseActive = true; targetLovePoseWeight = 1; targetThinkPoseWeight = 0; vrmThinkPoseActive = false;
                                if (lovePoseTimeoutId) { clearTimeout(lovePoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmLoveVrmaAction) {
                                    try {
                                        console.log('Playing VRMA love action');
                                        transitionToVrmAction(vrmLoveVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA action state:', {
                                            isRunning: vrmLoveVrmaAction.isRunning(),
                                            isScheduled: vrmLoveVrmaAction.isScheduled(),
                                            paused: vrmLoveVrmaAction.paused,
                                            enabled: vrmLoveVrmaAction.enabled,
                                            time: vrmLoveVrmaAction.time,
                                            weight: vrmLoveVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA action:', e);
                                    }
                                }
                                lovePoseTimeoutId = setTimeout(() => {
                                    vrmLovePoseActive = false; targetLovePoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmLoveVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA:', e);
                                        }
                                    }
                                    // Ensure smile/eyes reset after timeout
                                    try {
                                        if (!POSE_CONFIG.love.expressionsOnly) { try { restoreHumanoidQuats(vrm, lovePoseRestore); } catch(_) {} }
                                        lovePoseRestore = null;
                                        if (vrm.expressionManager) {
                                            ['smile','happy','joy','fun'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch (_) {} });
                                            // Clear love eyes expressions
                                            ['relaxed','heart','love'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch (_) {} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            ['Smile','Joy','Fun','MouthSmile'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch (_) {} });
                                            // Clear love eyes expressions for VRM 0.x
                                            ['Relaxed','Heart','Love'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch (_) {} });
                                        }
                                    } catch (_) {}
                                }, POSE_CONFIG.love.durationMs);
                            } else if (thinkHit) {
                                vrmThinkPoseActive = true; targetThinkPoseWeight = 1; targetLovePoseWeight = 0; vrmLovePoseActive = false;
                                if (thinkPoseTimeoutId) { clearTimeout(thinkPoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmThinkVrmaAction) {
                                    try {
                                        console.log('Playing VRMA thinking action');
                                        transitionToVrmAction(vrmThinkVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA thinking action state:', {
                                            isRunning: vrmThinkVrmaAction.isRunning(),
                                            isScheduled: vrmThinkVrmaAction.isScheduled(),
                                            paused: vrmThinkVrmaAction.paused,
                                            enabled: vrmThinkVrmaAction.enabled,
                                            time: vrmThinkVrmaAction.time,
                                            weight: vrmThinkVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA thinking action:', e);
                                    }
                                }
                                thinkPoseTimeoutId = setTimeout(() => {
                                    vrmThinkPoseActive = false; targetThinkPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmThinkVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA thinking animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA thinking:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            try { vrm.expressionManager.setValue('oh', 0.0); } catch(_){}
                                            ['browUp','browUpLeft','browUpRight','surprised'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch(_){} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            try { vrm.blendShapeProxy.setValue('O', 0.0); } catch(_){}
                                            ['BrowUp','BrowUp_L','BrowUp_R','Surprised'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch(_){} });
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.think.durationMs);
                            } else if (cryHit) {
                                vrmCryPoseActive = true; targetCryPoseWeight = 1; targetLovePoseWeight = 0; targetThinkPoseWeight = 0; vrmLovePoseActive = false; vrmThinkPoseActive = false;
                                if (cryPoseTimeoutId) { clearTimeout(cryPoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmCryVrmaAction) {
                                    try {
                                        console.log('Playing VRMA cry action');
                                        transitionToVrmAction(vrmCryVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA cry action state:', {
                                            isRunning: vrmCryVrmaAction.isRunning(),
                                            isScheduled: vrmCryVrmaAction.isScheduled(),
                                            paused: vrmCryVrmaAction.paused,
                                            enabled: vrmCryVrmaAction.enabled,
                                            time: vrmCryVrmaAction.time,
                                            weight: vrmCryVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA cry action:', e);
                                    }
                                }
                                cryPoseTimeoutId = setTimeout(() => {
                                    vrmCryPoseActive = false; targetCryPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmCryVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA cry animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA cry:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            // Clear sad/cry expressions
                                            ['sad','cry','sorrow'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch(_){} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            // Clear sad/cry expressions for VRM 0.x
                                            ['Sad','Cry','Sorrow'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch(_){} });
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.cry.durationMs);
                            } else if (angryHit) {
                                vrmAngryPoseActive = true; targetAngryPoseWeight = 1; targetLovePoseWeight = 0; targetThinkPoseWeight = 0; targetCryPoseWeight = 0; vrmLovePoseActive = false; vrmThinkPoseActive = false; vrmCryPoseActive = false;
                                if (angryPoseTimeoutId) { clearTimeout(angryPoseTimeoutId); }
                                // Set angry expression on the model
                                try {
                                    if (vrm.expressionManager) {
                                        // Set angry expression to full intensity
                                        try { vrm.expressionManager.setValue('angry', 1.0); } catch(_){}
                                    }
                                    if (vrm.blendShapeProxy) {
                                        // Set angry expression for VRM 0.x
                                        try { vrm.blendShapeProxy.setValue('Angry', 1.0); } catch(_){}
                                    }
                                } catch(_){}
                                // Prefer VRMA animation if available
                                if (vrmAngryVrmaAction) {
                                    try {
                                        console.log('Playing VRMA angry action');
                                        transitionToVrmAction(vrmAngryVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA angry action state:', {
                                            isRunning: vrmAngryVrmaAction.isRunning(),
                                            isScheduled: vrmAngryVrmaAction.isScheduled(),
                                            paused: vrmAngryVrmaAction.paused,
                                            enabled: vrmAngryVrmaAction.enabled,
                                            time: vrmAngryVrmaAction.time,
                                            weight: vrmAngryVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA angry action:', e);
                                    }
                                }
                                angryPoseTimeoutId = setTimeout(() => {
                                    vrmAngryPoseActive = false; targetAngryPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmAngryVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA angry animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA angry:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            // Clear angry expressions
                                            try { vrm.expressionManager.setValue('angry', 0.0); } catch(_){}
                                        }
                                        if (vrm.blendShapeProxy) {
                                            // Clear angry expressions for VRM 0.x
                                            try { vrm.blendShapeProxy.setValue('Angry', 0.0); } catch(_){}
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.angry.durationMs);
                            }
                        } catch (_) {}
                            } else {
                                // Fallback: if the model returned no content after tool calls,
                                // synthesize a simple confirmation from the last tool result
                                let confirmText = lastToolSummary;
                                if (!confirmText) {
                                    const lastToolMsg = messages.slice().reverse().find(m => m.role === 'tool')?.content;
                                    try {
                                        const parsed = typeof lastToolMsg === 'string' ? JSON.parse(lastToolMsg) : lastToolMsg;
                                        confirmText = parsed?.message || '';
                                    } catch (_) {
                                        confirmText = typeof lastToolMsg === 'string' ? lastToolMsg : '';
                                    }
                                }
                                if (confirmText) {
                                    responseOutput.value = confirmText;
                                    addMessageToHistory('assistant', confirmText); // Add to message history (also updates chatHistory)
                                    
                                    // Automatically extract memories from conversation (async, non-blocking)
                                    extractMemoriesFromConversation().catch(err => {
                                        console.warn('Memory extraction failed:', err);
                                    });
                                    
                                    textToSpeech(confirmText);
                                }
                            }
                            // Remove pulsing effect after receiving the final response
                            responseOutput.classList.remove('responding');
                            messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
                            stopProgressUpdates();
                            return;
                        } catch (toolErr) {
                            console.error('Error handling tool calls via LM Studio/OpenAI format:', toolErr);
                            // Fall back to legacy handling below
                        }
                    }

                    const rawContent = extractChoiceRawText(firstChoice);
                    const cleanContent = stripThinkTags(rawContent);
                    if (cleanContent) {
                        // Check for tool calls in Qwen's XML format
                        const toolCall = parseToolResponse(rawContent);
                        if (toolCall) {
                            console.log('Tool call detected:', toolCall);
                            try {
                                const toolName = toolCall.function?.name || toolCall.name || 'tool';
                                updateProgressState(`Executing tool: ${toolName}`);
                                const result = await executeToolCall(toolCall, context);  // Pass the context here
                                console.log('Tool execution result:', result);
                                
                                // Add the assistant's message to chat history
                                chatHistory.push({
                                    role: 'assistant',
                                    content: cleanContent
                                });
                                
                                if (result.success) {
                                    // For file read operations, include the content in the context for the LLM to use
                                    if (result.content) {
                                        // Get the tool name from the tool call
                                        const toolName = toolCall.function?.name || toolCall.name;
                                        
                                        // Create a follow-up message that includes the file content for the LLM to process
                                        const contentMessage = `File content from the file operation:\n\n${result.content}\n\nBased on this content, please respond to the user's request.`;
                                        
                                        // Add tool result to chat history
                                        chatHistory.push({
                                            role: 'user',
                                            content: contentMessage
                                        });
                                        
                                        // Make a follow-up call to let the LLM respond based on the file content
                                        try {
                                            updateProgressState('Requesting final response');
                                            const followupResponse = await fetch(endpoint, {
                                                method: 'POST',
                                                headers: {
                                                    'Content-Type': 'application/json',
                                                    'Authorization': `Bearer ${apiKey}`
                                                },
                                                signal: chatRequestSignal,
                                                body: JSON.stringify(buildCompatibleChatBody(endpoint, {
                                                    model: getCurrentModel(),
                                                    messages: buildModelHistoryWindow(),
                                                    temperature: 0.7
                                                }))
                                            });
                                            
                                            const followupData = await followupResponse.json();
                                            if (followupData.choices && followupData.choices.length > 0) {
                                                const followupMessage = followupData.choices[0].message;
                                                const followupContent = getVisibleAssistantText(followupMessage);
                                                
                                                if (followupContent) {
                                                    responseOutput.value = followupContent;
                                                    addMessageToHistory('assistant', followupContent);
                                                    textToSpeech(followupContent);
                                                    
                                                    chatHistory.push({
                                                        role: 'assistant',
                                                        content: followupContent
                                                    });
                                                }
                                            }
                                        } catch (followupError) {
                                            console.error('Follow-up request failed:', followupError);
                                            responseOutput.value = result.message;
                                            addMessageToHistory('assistant', result.message);
                                            textToSpeech(result.message);
                                        }
                                    } else {
                                        // For operations without content (like write), just show the result message
                                        responseOutput.value = result.message;
                                        addMessageToHistory('assistant', result.message);
                                        textToSpeech(result.message);
                                    }
                                }
                                
                                // Clear clipboard content after successful tool execution
                                if (hadClipboardContent) {
                                    clearClipboardPreview();
                                    console.log('Clipboard content cleared after tool execution');
                                }
                                if (uploadedAttachments.length) {
                                    clearPendingAttachments();
                                }
                                
                                // Remove pulsing effect after tool execution
                                responseOutput.classList.remove('responding');
                                messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
                            } catch (error) {
                                console.error('Tool execution error:', error);
                                responseOutput.value = `Error executing tool: ${error.message}`;
                                addMessageToHistory('assistant', `Error executing tool: ${error.message}`); // Add to message history
                                responseOutput.classList.remove('responding');
                                messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
                            }
                        } else {
                            // Handle regular message response
                        responseOutput.value = cleanContent;
                        addMessageToHistory('assistant', cleanContent); // Add to message history (also updates chatHistory)
                            // If user asked to convert a PDF/Markdown document to PowerPoint but the LLM replied in text, show upload widget in chat
                            if (isPdfToPowerPointRequest(promptText)) {
                                appendPdfUploadWidgetToChat(promptText);
                            }
                            // Automatically extract memories from conversation (async, non-blocking)
                            extractMemoriesFromConversation().catch(err => {
                                console.warn('Memory extraction failed:', err);
                            });
                            
                            // Clear clipboard content after successful message send
                            if (hadClipboardContent) {
                                clearClipboardPreview();
                                console.log('Clipboard content cleared after message sent');
                            }
                            if (uploadedAttachments.length) {
                                clearPendingAttachments();
                            }
                            
                            textToSpeech(cleanContent);
                        
                            // Update Live2D expression
                        const expressionFile = detectExpressionFromText(cleanContent);
                        if (expressionFile && live2dModel) {
                            await live2dModel.expression(expressionFile);
                        }
                        // Trigger VRM love pose when Love eye is detected
                        try {
                            const lowered = (cleanContent || '').toLowerCase();
                            const loveHit = ['happy','joy','glad','excited','wonderful','love','lovely','delighted','delight','romantic'].some(k => lowered.includes(k));
                            const thinkHit = ['thinking','consider','perhaps','maybe','hmm','interesting','curious','think','think about','ponder'].some(k => lowered.includes(k));
                            const cryHit = ['sad','upset','sorry','disappointed','unhappy','crying','cry'].some(k => lowered.includes(k));
                            const angryHit = ['angry','mad','furious','annoyed','irritated','frustrated','harsh'].some(k => lowered.includes(k));
                            if (loveHit) {
                                vrmLovePoseActive = true; targetLovePoseWeight = 1; targetThinkPoseWeight = 0; vrmThinkPoseActive = false;
                                if (lovePoseTimeoutId) { clearTimeout(lovePoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmLoveVrmaAction) {
                                    try {
                                        console.log('Playing VRMA love action');
                                        transitionToVrmAction(vrmLoveVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA action state:', {
                                            isRunning: vrmLoveVrmaAction.isRunning(),
                                            isScheduled: vrmLoveVrmaAction.isScheduled(),
                                            paused: vrmLoveVrmaAction.paused,
                                            enabled: vrmLoveVrmaAction.enabled,
                                            time: vrmLoveVrmaAction.time,
                                            weight: vrmLoveVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA action:', e);
                                    }
                                }
                                lovePoseTimeoutId = setTimeout(() => {
                                    vrmLovePoseActive = false; targetLovePoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmLoveVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA:', e);
                                        }
                                    }
                                    try {
                                        if (!POSE_CONFIG.love.expressionsOnly) { try { restoreHumanoidQuats(vrm, lovePoseRestore); } catch(_) {} }
                                        lovePoseRestore = null;
                                        if (vrm.expressionManager) {
                                            ['smile','happy','joy','fun'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch (_) {} });
                                            // Clear love eyes expressions
                                            ['relaxed','heart','love'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch (_) {} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            ['Smile','Joy','Fun','MouthSmile'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch (_) {} });
                                            // Clear love eyes expressions for VRM 0.x
                                            ['Relaxed','Heart','Love'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch (_) {} });
                                        }
                                    } catch (_) {}
                                }, 6000);
                            } else if (thinkHit) {
                                vrmThinkPoseActive = true; targetThinkPoseWeight = 1; targetLovePoseWeight = 0; vrmLovePoseActive = false;
                                if (thinkPoseTimeoutId) { clearTimeout(thinkPoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmThinkVrmaAction) {
                                    try {
                                        console.log('Playing VRMA thinking action');
                                        transitionToVrmAction(vrmThinkVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA thinking action state:', {
                                            isRunning: vrmThinkVrmaAction.isRunning(),
                                            isScheduled: vrmThinkVrmaAction.isScheduled(),
                                            paused: vrmThinkVrmaAction.paused,
                                            enabled: vrmThinkVrmaAction.enabled,
                                            time: vrmThinkVrmaAction.time,
                                            weight: vrmThinkVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA thinking action:', e);
                                    }
                                }
                                thinkPoseTimeoutId = setTimeout(() => {
                                    vrmThinkPoseActive = false; targetThinkPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmThinkVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA thinking animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA thinking:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            try { vrm.expressionManager.setValue('oh', 0.0); } catch(_){}
                                            ['browUp','browUpLeft','browUpRight','surprised'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch(_){} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            try { vrm.blendShapeProxy.setValue('O', 0.0); } catch(_){}
                                            ['BrowUp','BrowUp_L','BrowUp_R','Surprised'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch(_){} });
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.think.durationMs);
                            } else if (cryHit) {
                                vrmCryPoseActive = true; targetCryPoseWeight = 1; targetLovePoseWeight = 0; targetThinkPoseWeight = 0; vrmLovePoseActive = false; vrmThinkPoseActive = false;
                                if (cryPoseTimeoutId) { clearTimeout(cryPoseTimeoutId); }
                                // Prefer VRMA animation if available
                                if (vrmCryVrmaAction) {
                                    try {
                                        console.log('Playing VRMA cry action');
                                        transitionToVrmAction(vrmCryVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA cry action state:', {
                                            isRunning: vrmCryVrmaAction.isRunning(),
                                            isScheduled: vrmCryVrmaAction.isScheduled(),
                                            paused: vrmCryVrmaAction.paused,
                                            enabled: vrmCryVrmaAction.enabled,
                                            time: vrmCryVrmaAction.time,
                                            weight: vrmCryVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA cry action:', e);
                                    }
                                }
                                cryPoseTimeoutId = setTimeout(() => {
                                    vrmCryPoseActive = false; targetCryPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmCryVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA cry animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA cry:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            // Clear sad/cry expressions
                                            ['sad','cry','sorrow'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch(_){} });
                                        }
                                        if (vrm.blendShapeProxy) {
                                            // Clear sad/cry expressions for VRM 0.x
                                            ['Sad','Cry','Sorrow'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch(_){} });
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.cry.durationMs);
                            } else if (angryHit) {
                                vrmAngryPoseActive = true; targetAngryPoseWeight = 1; targetLovePoseWeight = 0; targetThinkPoseWeight = 0; targetCryPoseWeight = 0; vrmLovePoseActive = false; vrmThinkPoseActive = false; vrmCryPoseActive = false;
                                if (angryPoseTimeoutId) { clearTimeout(angryPoseTimeoutId); }
                                // Set angry expression on the model
                                try {
                                    if (vrm.expressionManager) {
                                        // Set angry expression to full intensity
                                        try { vrm.expressionManager.setValue('angry', 1.0); } catch(_){}
                                    }
                                    if (vrm.blendShapeProxy) {
                                        // Set angry expression for VRM 0.x
                                        try { vrm.blendShapeProxy.setValue('Angry', 1.0); } catch(_){}
                                    }
                                } catch(_){}
                                // Prefer VRMA animation if available
                                if (vrmAngryVrmaAction) {
                                    try {
                                        console.log('Playing VRMA angry action');
                                        transitionToVrmAction(vrmAngryVrmaAction, {
                                            loop: window.THREE.LoopOnce,
                                            repetitions: 1,
                                            fadeInSeconds: VRM_ACTION_FADE_IN_SECONDS,
                                            fadeOutSeconds: VRM_ACTION_FADE_OUT_SECONDS,
                                            forceRestart: true
                                        });
                                        console.log('VRMA angry action state:', {
                                            isRunning: vrmAngryVrmaAction.isRunning(),
                                            isScheduled: vrmAngryVrmaAction.isScheduled(),
                                            paused: vrmAngryVrmaAction.paused,
                                            enabled: vrmAngryVrmaAction.enabled,
                                            time: vrmAngryVrmaAction.time,
                                            weight: vrmAngryVrmaAction.getEffectiveWeight()
                                        });
                                    } catch(e) {
                                        console.warn('Error playing VRMA angry action:', e);
                                    }
                                }
                                angryPoseTimeoutId = setTimeout(() => {
                                    vrmAngryPoseActive = false; targetAngryPoseWeight = 0;
                                    // Smoothly fade out VRMA animation before stopping
                                    if (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning()) {
                                        try {
                                            stopVrmAction(vrmAngryVrmaAction, 0.8); // Fade out over 0.8 seconds
                                            console.log('Fading out VRMA angry animation');
                                        } catch(e) {
                                            console.warn('Error fading out VRMA angry:', e);
                                        }
                                    }
                                    try {
                                        if (vrm.expressionManager) {
                                            // Clear angry expressions
                                            try { vrm.expressionManager.setValue('angry', 0.0); } catch(_){}
                                        }
                                        if (vrm.blendShapeProxy) {
                                            // Clear angry expressions for VRM 0.x
                                            try { vrm.blendShapeProxy.setValue('Angry', 0.0); } catch(_){}
                                        }
                                    } catch(_){}
                                }, POSE_CONFIG.angry.durationMs);
                            }
                        } catch (_) {}
                        responseOutput.classList.remove('responding');
                        messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
                    }
                }
                }
            } catch (error) {
                console.error('Error:', error);
                const isTimeoutAbort = error?.name === 'AbortError';
                const userErrorMessage = isTimeoutAbort
                    ? `Error: Request timed out after ${Math.round(CHAT_REQUEST_TIMEOUT_MS / 1000)} seconds. Please try again.`
                    : `${error.message}`;
                status.textContent = userErrorMessage;
                renderAssistantErrorResponse(userErrorMessage);
            } finally {
                responseOutput.classList.remove('responding');
                messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
                stopProgressUpdates();
            }
            } catch (outerError) {
                console.error('Error before chat request completion:', outerError);
                const isTimeoutAbort = outerError?.name === 'AbortError';
                const userErrorMessage = isTimeoutAbort
                    ? `Error: Request timed out after ${Math.round(CHAT_REQUEST_TIMEOUT_MS / 1000)} seconds. Please try again.`
                    : `${outerError.message}`;
                status.textContent = userErrorMessage;
                renderAssistantErrorResponse(userErrorMessage);
                responseOutput.classList.remove('responding');
                messageHistory.classList.remove('responding');
                stopProgressUpdates();
            } finally {
                try {
                    window.clearTimeout(chatRequestTimeoutId);
                } catch (_) {}
                if (!vrmAwaitingTtsStart) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
                if (activeChatRequest && activeChatRequest.controller === chatRequestController) {
                    activeChatRequest = null;
                }
                setChatRequestUiLocked(false);
            }
        }

        // Shared send logic so mobile paper-airplane button can call it directly (fixes iOS Safari programmatic click)
        window.submitUserMessage = async function () {
            // Check for philosopher mode trigger phrase
            const promptText = userInput.value.trim();
            if (promptText && detectPhilosopherModeTrigger(promptText)) {
                await startPhilosopherMode();
                userInput.value = ''; // Clear input
                syncUserInputUi();
                return; // Don't send as regular message
            }

            // If philosopher mode is active or starting, and user sends a message, stop philosopher mode (interruption)
            const shouldStopPhilosopher = (philosopherModeActive || philosopherModeStarting) && promptText;
            if (shouldStopPhilosopher) {
                // Stop philosopher mode but skip message display - we'll add it after the user message
                await stopPhilosopherMode(true); // Pass true to skip message display
            }
            await resumeAudioContextOnce(); // Resume audio context on first user action (for autoplay and lip sync)
            const userText = userInput.value; // Get user input text
            if (userText.trim() === '' && pendingAttachmentFiles.length === 0) { // Check if input is empty
                alert('Please enter some text or record your voice.'); // Show alert if empty
                return; // Exit early
            } // End empty check
            if (activeChatRequest) {
                status.textContent = 'A response is already in progress. Please wait.';
                return;
            }

            // Note: fetchOpenAIResponse will add the user message to history, so we don't add it here
            fetchOpenAIResponse(userText); // Send message to OpenAI API (this will add user message to history)

            // Add deactivation message after user message if we stopped philosopher mode
            // This appears after the user message since fetchOpenAIResponse adds it synchronously at the start
            if (shouldStopPhilosopher) {
                addMessageToHistory('assistant', 'Philosopher Mode deactivated.');
            }
            userInput.value = ''; // Clear input field
            syncUserInputUi();
        };
        sendBtn.addEventListener('click', function () { // Handle send button click
            if (window.submitUserMessage) window.submitUserMessage();
        }); // End send button click handler

        // Handle Enter key submission and Shift+Enter for newlines
        userInput.addEventListener('keydown', async function (event) { // Handle keyboard input
            // Handle semicolon key for STT shortcut (even when input is focused) - start recording
            if (event.key === ';' && !event.repeat && !isRecording) {
                event.preventDefault(); // Prevent semicolon from being typed
                await resumeAudioContextOnce(); // Resume audio context on first user action (for autoplay and lip sync)
                toggleRecording(); // Start recording
                return; // Exit early to prevent other handlers
            }
            if (event.key === 'Enter' && !event.shiftKey) { // Check if Enter key pressed (not Shift+Enter)
                event.preventDefault(); // Prevent default newline behavior
                await resumeAudioContextOnce(); // Resume audio context on first user action (for autoplay and lip sync)
                const userText = userInput.value; // Get user input text
                
                // Check for philosopher mode trigger phrase
                if (userText.trim() && detectPhilosopherModeTrigger(userText)) {
                    await startPhilosopherMode();
                    userInput.value = ''; // Clear input
                    syncUserInputUi();
                    return; // Don't send as regular message
                }

                // If philosopher mode is active or starting, and user sends a message, stop philosopher mode (interruption)
                const shouldStopPhilosopher = (philosopherModeActive || philosopherModeStarting) && userText.trim();
                if (shouldStopPhilosopher) {
                    // Stop philosopher mode but skip message display - we'll add it after the user message
                    await stopPhilosopherMode(true); // Pass true to skip message display
                }
                
                if (userText.trim() !== '' || pendingAttachmentFiles.length > 0) { // Check if input is not empty
                    if (activeChatRequest) {
                        status.textContent = 'A response is already in progress. Please wait.';
                        return;
                    }
                    // Note: fetchOpenAIResponse will add the user message to history, so we don't add it here
                    fetchOpenAIResponse(userText); // Send message to OpenAI API (this will add user message to history)
                    
                    // Add deactivation message after user message if we stopped philosopher mode
                    // This appears after the user message since fetchOpenAIResponse adds it synchronously at the start
                    if (shouldStopPhilosopher) {
                        addMessageToHistory('assistant', 'Philosopher Mode deactivated.');
                    }
                    
                    userInput.value = ''; // Clear input field
                    syncUserInputUi();
                } else { // If input is empty
                    alert('Please enter some text or record your voice.'); // Show alert
                } // End empty check
            } // End Enter key check
            // Shift+Enter allows normal newline behavior (default)
        }); // End keyboard input handler

        // Handle semicolon keyup for STT shortcut (when input is focused)
        userInput.addEventListener('keyup', (e) => {
            if (e.key === ';' && isRecording) {
                e.preventDefault(); // Prevent semicolon from being typed
                toggleRecording(); // Stop recording
            }
        });

        // Update the initLive2D function
        async function initLive2D() {
            const requestedGeneration = ++live2dLoadGeneration;
            const requestedModelPath = modelPath;
            try {
                // Wait for the document to be fully loaded
                if (document.readyState !== 'complete') {
                    await new Promise(resolve => window.addEventListener('load', resolve));
                }

                const container = document.getElementById('live2d-container');
                const canvas = document.getElementById('live2d-canvas');
                if (!container || !canvas) {
                    console.warn('Live2D container/canvas not found. Skipping init.');
                    return;
                }

                if (!requestedModelPath || !requestedModelPath.toLowerCase().endsWith('.model3.json')) {
                    console.warn('No Live2D model is currently available from the scanned model list.');
                    return;
                }

                // Initialize Live2D
                // Register ticker only once to avoid duplicate RAF workloads
                if (!live2dTickerRegistered) {
                    await PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);
                    live2dTickerRegistered = true;
                }

                const app = ensureLive2DApp(container, canvas);
                disposeLive2DModel();

                // Resolve model path to absolute URL for remote access
                const resolvedModelPath = resolveModelPath(requestedModelPath);
                console.log(`Loading Live2D model from: ${resolvedModelPath} (original: ${requestedModelPath})`);
                
                // Load model
                const model = await PIXI.live2d.Live2DModel.from(resolvedModelPath, {
                    autoInteract: false,
                    focus: false
                });

                if (
                    requestedGeneration !== live2dLoadGeneration ||
                    requestedModelPath !== modelPath ||
                    document.getElementById('vrm-mode')?.checked
                ) {
                    destroyLive2DModelInstance(model);
                    return;
                }
                
                // Clear stage and add the fresh model to stage
                app.stage.removeChildren();
                app.stage.addChild(model);

                // Center the model
                model.anchor.set(0.5, 0.4);

                // Rest of your model setup...
                model.draggable = false;
                model.following = false;
                model.interactive = false;
                model.tracking = false;
                model.removeAllListeners();
                
                if (model.internalModel) {
                    model.internalModel.coreModel.setParameterValueById('ParamAngleX', 0);
                    model.internalModel.coreModel.setParameterValueById('ParamAngleY', 0);
                    model.internalModel.coreModel.setParameterValueById('ParamAngleZ', 0);
                    model.internalModel.coreModel.setParameterValueById('ParamEyeBallX', 0);
                    model.internalModel.coreModel.setParameterValueById('ParamEyeBallY', 0);
                }

                live2dModel = model;
                live2dActiveModelPath = requestedModelPath;
                attachLive2DResizeHandler(requestedModelPath);
                applyCurrentLive2DLayout(model, requestedModelPath);
                console.log('Live2D model loaded successfully');
                
                // Prime expression metadata without running a slow expression test loop on every swap
                await initializeLive2DExpressions(model);

            } catch (error) {
                if (requestedGeneration === live2dLoadGeneration) {
                    console.error('Failed to load Live2D model:', error);
                }
            }
        }

        // Helper to safely cleanup existing Live2D resources before switching models
        function cleanupLive2D() {
            try {
                live2dLoadGeneration += 1;
                disposeLive2DModel();
            } catch (err) {
                console.warn('cleanupLive2D encountered an issue:', err);
            }
        }

        // VRM Functions
        function cleanupVRM() {
            try {
                vrmLoadGeneration += 1;
                clearVRMResizeHandler();
                clearVrmAwaitingTtsStart();
                clearVrmIdleReplayTimer();
                clearVrmBlinkTimers();
                if (vrmAnimationFrameId) {
                    try { cancelAnimationFrame(vrmAnimationFrameId); } catch (_) {}
                    vrmAnimationFrameId = 0;
                }
                [
                    vrmLoveVrmaAction,
                    vrmThinkVrmaAction,
                    vrmCryVrmaAction,
                    vrmAngryVrmaAction,
                    vrmIdleVrmaAction
                ].forEach(clearVrmActionStopTimer);
                vrmProcessingThinkLoopActive = false;
                vrmTtsStartHandled = false;
                vrmIdleHasPlayedOnce = false;
                resetVrmPoseState();
                vrmPoseSnapshotBones = {};
                vrmBaseStandingPoseSnapshot = null;
                vrmLastPoseSnapshot = null;
                vrmLastFrameHadRunningAction = false;
                vrmRestorePoseOnNextManualIdle = false;
                vrmPoseBlend = null;

            // Stop and uncache animation bindings
            try {
                if (vrmMixer && vrmModel && vrmModel.scene) {
                    vrmMixer.stopAllAction();
                    vrmMixer.uncacheRoot(vrmModel.scene);
                }
            } catch (_) {}

            if (vrmScene) {
                disposeThreeSceneResources(vrmScene);
            }

            if (vrmRenderer) {
                vrmRenderer.dispose();
            }

            vrmModel = null;
            vrmScene = null;
            vrmCamera = null;
            vrmRenderer = null;
            vrmMixer = null;
            vrmClock = null;
            vrmLipSyncMorphTarget = null;
            vrmLoveVrmaAction = null;
            vrmThinkVrmaAction = null;
            vrmCryVrmaAction = null;
            vrmAngryVrmaAction = null;
            vrmIdleVrmaAction = null;
            vrmActiveModelPath = '';
            if (lovePoseTimeoutId) { try { clearTimeout(lovePoseTimeoutId); } catch (_) {} lovePoseTimeoutId = null; }
            if (thinkPoseTimeoutId) { try { clearTimeout(thinkPoseTimeoutId); } catch (_) {} thinkPoseTimeoutId = null; }
            if (cryPoseTimeoutId) { try { clearTimeout(cryPoseTimeoutId); } catch (_) {} cryPoseTimeoutId = null; }
            if (angryPoseTimeoutId) { try { clearTimeout(angryPoseTimeoutId); } catch (_) {} angryPoseTimeoutId = null; }

            // Detach mouse move handler if present
            const canvas = document.getElementById('vrm-canvas'); // Retrieve canvas to remove handler
            if (canvas && canvas.__vrmMouseMoveHandler) { // If a handler was attached
                try { canvas.removeEventListener('mousemove', canvas.__vrmMouseMoveHandler); } catch {} // Remove handler
                canvas.__vrmMouseMoveHandler = null; // Clear reference
            }

        } catch (error) {
            console.warn('Error cleaning up VRM:', error);
        }
        }

        async function initVRM() {
            const requestedGeneration = ++vrmLoadGeneration;
            const requestedModelPath = currentVRMModelPath;
            let scene = null;
            let camera = null;
            let renderer = null;
            let mixer = null;
            let gltf = null;
            let vrm = null;
            try {
                const container = document.getElementById('vrm-container');
                const canvas = document.getElementById('vrm-canvas');
                if (!container || !canvas) {
                    console.warn('VRM container/canvas not found. Skipping init.');
                    return;
                }

                // Ensure a valid .vrm path is selected
                if (!requestedModelPath || !requestedModelPath.toLowerCase().endsWith('.vrm')) {
                    console.warn('Selected model path is not a .vrm file. Please provide a valid VRM file.');
                    return;
                }

                // Wait for THREE.js and VRM modules to be ready
                if (!window.__vrmModulesReady || !window.THREE || !window.GLTFLoader) {
                    console.log('Waiting for VRM modules to load...');
                    await new Promise((resolve, reject) => {
                        const start = Date.now();
                        const timer = setInterval(() => {
                            if (window.__vrmModulesReady && window.THREE && window.GLTFLoader && window.VRMLoaderPlugin) {
                                clearInterval(timer);
                                resolve();
                            } else if (Date.now() - start > 10000) {
                                clearInterval(timer);
                                reject(new Error('VRM modules failed to load within 10 seconds'));
                            }
                        }, 50);
                    });
                }

                if (requestedGeneration !== vrmLoadGeneration || requestedModelPath !== currentVRMModelPath || !document.getElementById('vrm-mode')?.checked) {
                    return;
                }

                // Verify THREE.js is available
                if (!window.THREE) {
                    if (window.__vrmModulesError) {
                        throw new Error('VRM modules failed to load: ' + window.__vrmModulesError.message);
                    }
                    throw new Error('THREE.js is not loaded. Please refresh the page and check the console for errors.');
                }
                if (!window.THREE.Scene) {
                    throw new Error('THREE.js Scene is not available. THREE.js may not have loaded correctly.');
                }

                // Initialize Three.js scene
                const viewportWidth = Math.max(container.clientWidth || canvas.clientWidth || 0, 1);
                const viewportHeight = Math.max(container.clientHeight || canvas.clientHeight || 0, 1);
                scene = new window.THREE.Scene();
                camera = new window.THREE.PerspectiveCamera(45, viewportWidth / viewportHeight, 0.1, 1000);
                renderer = new window.THREE.WebGLRenderer({
                    canvas: canvas,
                    antialias: true,
                    alpha: true,
                    premultipliedAlpha: false,
                    powerPreference: 'default',
                    precision: 'highp',
                    failIfMajorPerformanceCaveat: false
                });
                configureVrmRenderer(renderer);
                renderer.setSize(viewportWidth, viewportHeight);
                renderer.setClearColor(0x000000, 0);

                // Add lighting
                const ambientLight = new window.THREE.AmbientLight(0x404040, 0.6);
                scene.add(ambientLight);
                const directionalLight = new window.THREE.DirectionalLight(0xffffff, 0.8);
                directionalLight.position.set(1, 1, 1);
                scene.add(directionalLight);

                // Load VRM model
                const loader = new window.GLTFLoader();
                // Register VRM plugin (same plugin works for both VRM 0.0 and 1.0)
                if (window.VRMLoaderPlugin) {
                    loader.register(parser => new window.VRMLoaderPlugin(parser));
                }
                // Register VRMA plugin for VRM 1.0 animations (only works with VRM 1.0)
                if (vrmVersion === '1.0' && window.VRMAnimationLoaderPlugin) {
                    loader.register(parser => new window.VRMAnimationLoaderPlugin(parser));
                }

                // Resolve model path to absolute URL for remote access
                const resolvedVRMPath = resolveModelPath(requestedModelPath);
                console.log(`Loading VRM model from: ${resolvedVRMPath} (original: ${requestedModelPath})`);
                
                gltf = await new Promise((resolve, reject) => {
                    loader.load(
                        resolvedVRMPath,
                        resolve,
                        undefined,
                        reject
                    );
                });

                if (requestedGeneration !== vrmLoadGeneration || requestedModelPath !== currentVRMModelPath || !document.getElementById('vrm-mode')?.checked) {
                    disposeStaleVrmLoadResources(scene, renderer, mixer, null, gltf?.scene);
                    return;
                }

                // Extract VRM instance from GLTFLoader plugin output
                // VRM data can be in userData.vrm or extensions.VRM
                if (gltf && gltf.userData && gltf.userData.vrm) {
                    vrm = gltf.userData.vrm;
                } else if (gltf && gltf.parser && gltf.parser.userData && gltf.parser.userData.vrm) {
                    vrm = gltf.parser.userData.vrm;
                } else if (gltf && gltf.scene && gltf.scene.userData && gltf.scene.userData.vrm) {
                    vrm = gltf.scene.userData.vrm;
                }
                
                if (!vrm) {
                    console.error('GLTF structure:', {
                        hasUserData: !!gltf?.userData,
                        hasParser: !!gltf?.parser,
                        hasScene: !!gltf?.scene,
                        userDataKeys: gltf?.userData ? Object.keys(gltf.userData) : [],
                        parserUserDataKeys: gltf?.parser?.userData ? Object.keys(gltf.parser.userData) : []
                    });
                    disposeStaleVrmLoadResources(scene, renderer, mixer, null, gltf?.scene);
                    throw new Error('Loaded GLTF does not contain VRM data. Ensure the file is a valid .vrm model and the VRM version setting matches the model version.');
                }

                // Optimize skeleton for performance (updated per deprecation notice)
                if (window.VRMUtils && vrm && vrm.scene) {
                    try { window.VRMUtils.combineSkeletons(vrm.scene); } catch (_) {}
                }
                
                // Handle VRM 0.0 orientation if needed (VRM 0.0 models face Z- instead of Z+)
                if (vrmVersion === '0.0' && window.VRMUtils && vrm) {
                    try {
                        // Check if this is actually a VRM 0.0 model by checking meta
                        if (vrm.meta && vrm.meta.metaVersion === '0') {
                            // Rotate VRM 0.0 model to correct orientation
                            window.VRMUtils.rotateVRM0(vrm);
                        }
                    } catch (e) {
                        console.warn('Could not rotate VRM 0.0 model:', e);
                    }
                }

                // Setup VRM model
                vrm.scene.traverse((child) => {
                    if (child.isMesh && child.material) {
                        child.material.needsUpdate = true;
                    }
                });

                scene.add(vrm.scene);
                
                // Reset VRM 0.0 arm bones to natural rest pose AFTER scene is added
                // This ensures the bones are properly initialized before we reset them
                if (vrmVersion === '0.0' && vrm && vrm.meta && vrm.meta.metaVersion === '0' && vrm.humanoid) {
                    try {
                        // Function to set arm bones to natural rest pose (arms hanging naturally by sides)
                        const setNaturalArmPose = () => {
                            // Get arm bones
                            const leftShoulder = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
                            const rightShoulder = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
                            const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
                            const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
                            const leftLowerArm = vrm.humanoid.getNormalizedBoneNode('leftLowerArm');
                            const rightLowerArm = vrm.humanoid.getNormalizedBoneNode('rightLowerArm');
                            const leftHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
                            const rightHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
                            
                            // Set shoulders to neutral
                            if (leftShoulder) leftShoulder.quaternion.set(0, 0, 0, 1);
                            if (rightShoulder) rightShoulder.quaternion.set(0, 0, 0, 1);
                            
                            // Set upper arms with slight inward rotation for natural hang
                            if (leftUpperArm) {
                                leftUpperArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 1, 0), 
                                    Math.PI * 0.05 // ~9 degrees inward
                                );
                            }
                            if (rightUpperArm) {
                                rightUpperArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 1, 0), 
                                    -Math.PI * 0.05 // ~9 degrees inward
                                );
                            }
                            
                            // Set lower arms with slight forward rotation
                            if (leftLowerArm) {
                                leftLowerArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 0, 1), 
                                    Math.PI * 0.02 // ~3.6 degrees forward
                                );
                            }
                            if (rightLowerArm) {
                                rightLowerArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 0, 1), 
                                    -Math.PI * 0.02 // ~3.6 degrees forward
                                );
                            }
                            
                            // Set hands to neutral
                            if (leftHand) leftHand.quaternion.set(0, 0, 0, 1);
                            if (rightHand) rightHand.quaternion.set(0, 0, 0, 1);
                            
                            // Update the skeleton hierarchy to propagate changes
                            if (vrm.scene) {
                                vrm.scene.updateMatrixWorld(true);
                            }
                        };
                        
                        // Set pose immediately
                        setNaturalArmPose();
                        
                        // Also set after a short delay to ensure everything is initialized
                        setTimeout(setNaturalArmPose, 100);
                    } catch (e) {
                        // Silently handle errors to avoid console spam
                    }
                }

                // Find lip sync morph target (supports VRM 0.x and VRM 1.0)
                try {
                    if (vrm.expressionManager) {
                        // VRM 1.0: use vowel expression key 'aa' if available, fallback to common names
                        vrmLipSyncMorphTarget = 'aa';
                    } else if (vrm.blendShapeProxy) {
                        // VRM 0.x: use preset 'A' if available, fallback by name
                        const groups = vrm.blendShapeProxy.getBlendShapeGroupList ? vrm.blendShapeProxy.getBlendShapeGroupList() : [];
                        const findByPreset = (preset) => groups.find(g => String(g.presetName || '').toUpperCase() === String(preset).toUpperCase());
                        const findByName = (regex) => groups.find(g => regex.test(String(g.name || '')));
                        const aPreset = findByPreset('A');
                        if (aPreset) {
                            vrmLipSyncMorphTarget = 'A';
                        } else {
                            const mouthOpen = findByName(/MouthOpen/i);
                            const anyMouth = mouthOpen || findByName(/Mouth/i) || findByName(/Lip/i);
                            vrmLipSyncMorphTarget = anyMouth ? anyMouth.name : null;
                        }
                    } else {
                        vrmLipSyncMorphTarget = null;
                    }
                } catch (e) {
                    console.warn('Failed to resolve VRM lip sync target:', e);
                    vrmLipSyncMorphTarget = null;
                }

                // Position camera
                camera.position.set(0, 0, 5);
                camera.lookAt(0, 0, 0);

                // Animation mixer
                mixer = new window.THREE.AnimationMixer(vrm.scene);
                // Optional: preload VRMA animation clip for love pose (only for VRM 1.0)
                let loveVrmaAction = null;
                try {
                    // VRMA animations only work with VRM 1.0, skip for VRM 0.0
                    if (vrmVersion === '1.0' && POSE_CONFIG?.love?.useVrma && POSE_CONFIG?.love?.vrmaPath) {
                        const vrmaUrl = encodeURI(POSE_CONFIG.love.vrmaPath);
                        console.log('Loading VRMA from', vrmaUrl);
                        const vrmaGltf = await new Promise((resolve, reject) => {
                            loader.load(vrmaUrl, resolve, undefined, reject);
                        });
                        // Prefer VRMAnimation (vrma) from userData if provided by plugin
                        let clip = null;
                        // Check multiple possible locations for VRMA data
                        let vrma = null;

                        // Try userData first
                        if (vrmaGltf?.userData?.vrmAnimations && Array.isArray(vrmaGltf.userData.vrmAnimations) && vrmaGltf.userData.vrmAnimations.length > 0) {
                            vrma = vrmaGltf.userData.vrmAnimations[0];
                        }
                        // Try extensions
                        else if (vrmaGltf?.extensions?.VRMC_vrm_animation) {
                            vrma = vrmaGltf.extensions.VRMC_vrm_animation;
                        }
                        // Try parser userData
                        else if (vrmaGltf?.parser?.userData?.vrmAnimations) {
                            vrma = vrmaGltf.parser.userData.vrmAnimations[0];
                        }

                        if (vrma) {
                            console.log('Found VRMA data');
                            console.log('VRMA object:', vrma);
                            console.log('VRMA constructor:', vrma.constructor?.name);
                            console.log('VRMA object keys:', Object.keys(vrma || {}));
                            console.log('VRMA humanoidTracks type:', typeof vrma.humanoidTracks);
                            console.log('VRMA humanoidTracks length:', vrma.humanoidTracks ? (Array.isArray(vrma.humanoidTracks) ? vrma.humanoidTracks.length : 'not array') : 'undefined');

                            // Debug the VRMA structure more deeply
                            if (vrma.humanoidTracks) {
                                console.log('HumanoidTracks raw:', vrma.humanoidTracks);
                                
                                // Check if it's a Map
                                if (vrma.humanoidTracks instanceof Map) {
                                    console.log('HumanoidTracks is a Map, size:', vrma.humanoidTracks.size);
                                    const mapKeys = Array.from(vrma.humanoidTracks.keys());
                                    console.log('HumanoidTracks Map keys:', mapKeys);
                                    if (mapKeys.length > 0) {
                                        const firstKey = mapKeys[0];
                                        console.log('First track key:', firstKey);
                                        console.log('First track value:', vrma.humanoidTracks.get(firstKey));
                                    }
                                } else if (typeof vrma.humanoidTracks === 'object') {
                                    // Check Object.keys vs Object.values
                                    const keys = Object.keys(vrma.humanoidTracks);
                                    const values = Object.values(vrma.humanoidTracks);
                                    console.log('HumanoidTracks Object.keys():', keys);
                                    console.log('HumanoidTracks Object.values() length:', values.length);
                                    
                                    // Check if it has enumerable properties
                                    console.log('HumanoidTracks own property names:', Object.getOwnPropertyNames(vrma.humanoidTracks));
                                    
                                    // Try to iterate
                                    if (values.length > 0) {
                                        console.log('First track in values:', values[0]);
                                    }
                                }
                                
                                console.log('HumanoidTracks content preview:', vrma.humanoidTracks.slice ? vrma.humanoidTracks.slice(0, 2) : 'not sliceable');
                                if (Array.isArray(vrma.humanoidTracks) && vrma.humanoidTracks.length > 0) {
                                    console.log('First track structure:', Object.keys(vrma.humanoidTracks[0] || {}));
                                }
                            }

                            // Also check for alternative track structures
                            if (vrma.humanoidAnimationTracks) {
                                console.log('Found humanoidAnimationTracks instead');
                            }
                            if (vrma.tracks) {
                                console.log('Found tracks property');
                            }
                            
                            // Check if vrma has the createAnimationClip method
                            console.log('Has createAnimationClip method:', typeof vrma.createAnimationClip);
                        } else {
                            console.warn('No VRMA data found in any expected location');
                            console.log('Available locations checked:', {
                                userData: !!vrmaGltf?.userData,
                                extensions: !!vrmaGltf?.extensions,
                                parser: !!vrmaGltf?.parser
                            });
                        }

                        // Prefer instance method on VRMAnimation to retarget to this VRM
                        if (!clip && vrma && typeof vrma.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying vrma.createAnimationClip(vrm)...');
                                clip = vrma.createAnimationClip(vrm); 
                                if (clip) {
                                    console.log('Successfully created clip via vrma.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('vrma.createAnimationClip failed:', e);
                                console.warn('Error stack:', e.stack);
                            }
                        }
                        // Static helper fallback if available
                        if (!clip && window.VRMAnimation && typeof window.VRMAnimation.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying VRMAnimation.createAnimationClip(vrma, vrm)...');
                                clip = window.VRMAnimation.createAnimationClip(vrma, vrm); 
                                if (clip) {
                                    console.log('Successfully created clip via VRMAnimation.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('VRMAnimation.createAnimationClip failed:', e);
                                console.warn('Error stack:', e.stack);
                            }
                        }
                        // Direct clip property or getter fallbacks
                        if (!clip && vrma && vrma.clip) { 
                            try { 
                                clip = vrma.clip;
                                console.log('Got clip from vrma.clip property');
                            } catch(_) {} 
                        }
                        if (!clip && vrma && typeof vrma.getClip === 'function') { 
                            try { 
                                clip = vrma.getClip();
                                console.log('Got clip from vrma.getClip() method');
                            } catch(_) {} 
                        }
                        // Synthesise THREE.AnimationClip if tracks array present
                        if (!clip) {
                            console.log('Trying to build clip manually from VRMA object...');
                            const built = buildClipFromVRMAObject(vrma, vrm);
                            if (built) { 
                                clip = built;
                                console.log('Successfully built clip manually');
                            }
                        }

                        if (clip) {
                            // Retarget track names to VRM bone UUIDs if needed
                            const boundClip = retargetClipToVRM(clip, vrm) || clip;
                            loveVrmaAction = mixer.clipAction(boundClip, vrm.scene);
                            loveVrmaAction.clampWhenFinished = true;
                            loveVrmaAction.setEffectiveWeight(1.0);
                            loveVrmaAction.setEffectiveTimeScale(1.0);
                            loveVrmaAction.loop = window.THREE.LoopOnce;
                            console.log('VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                            if (Array.isArray(boundClip.tracks) && boundClip.tracks.length > 0) {
                                console.log('Sample track names:', boundClip.tracks.slice(0, 3).map(t => t.name));
                                
                                // Verify bone exists for first few tracks
                                console.log('Verifying bones exist for tracks:');
                                for (let i = 0; i < Math.min(5, boundClip.tracks.length); i++) {
                                    const track = boundClip.tracks[i];
                                    const trackUUID = track.name.split('.')[0];
                                    const bone = vrm.scene.getObjectByProperty('uuid', trackUUID);
                                    console.log(`Track ${i}: UUID=${trackUUID}, bone found=${!!bone}, boneName=${bone?.name || 'N/A'}`);
                                }
                            }
                        } else {
                            console.warn('No animation clip found in VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload VRMA animation:', e);
                }
                
                // Optional: preload VRMA animation clip for thinking pose (only for VRM 1.0)
                let thinkVrmaAction = null;
                try {
                    // VRMA animations only work with VRM 1.0, skip for VRM 0.0
                    if (vrmVersion === '1.0' && POSE_CONFIG?.think?.useVrma && POSE_CONFIG?.think?.vrmaPath) {
                        const vrmaUrl = encodeURI(POSE_CONFIG.think.vrmaPath);
                        console.log('Loading Thinking VRMA from', vrmaUrl);
                        const vrmaGltf = await new Promise((resolve, reject) => {
                            loader.load(vrmaUrl, resolve, undefined, reject);
                        });
                        // Check multiple possible locations for VRMA data
                        let vrma = null;

                        // Try userData first
                        if (vrmaGltf?.userData?.vrmAnimations && Array.isArray(vrmaGltf.userData.vrmAnimations) && vrmaGltf.userData.vrmAnimations.length > 0) {
                            vrma = vrmaGltf.userData.vrmAnimations[0];
                        }
                        // Try extensions
                        else if (vrmaGltf?.extensions?.VRMC_vrm_animation) {
                            vrma = vrmaGltf.extensions.VRMC_vrm_animation;
                        }
                        // Try parser userData
                        else if (vrmaGltf?.parser?.userData?.vrmAnimations) {
                            vrma = vrmaGltf.parser.userData.vrmAnimations[0];
                        }

                        let clip = null;
                        
                        // Try instance method on VRMAnimation to retarget to this VRM
                        if (!clip && vrma && typeof vrma.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying vrma.createAnimationClip(vrm) for thinking...');
                                clip = vrma.createAnimationClip(vrm); 
                                if (clip) {
                                    console.log('Successfully created thinking clip via vrma.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('vrma.createAnimationClip failed for thinking:', e);
                            }
                        }
                        // Static helper fallback if available
                        if (!clip && window.VRMAnimation && typeof window.VRMAnimation.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying VRMAnimation.createAnimationClip(vrma, vrm) for thinking...');
                                clip = window.VRMAnimation.createAnimationClip(vrma, vrm); 
                                if (clip) {
                                    console.log('Successfully created thinking clip via VRMAnimation.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('VRMAnimation.createAnimationClip failed for thinking:', e);
                            }
                        }
                        // Synthesise THREE.AnimationClip if tracks array present
                        if (!clip) {
                            console.log('Trying to build thinking clip manually from VRMA object...');
                            const built = buildClipFromVRMAObject(vrma, vrm);
                            if (built) { 
                                clip = built;
                                console.log('Successfully built thinking clip manually');
                            }
                        }

                        if (clip) {
                            const boundClip = retargetClipToVRM(clip, vrm) || clip;
                            thinkVrmaAction = mixer.clipAction(boundClip, vrm.scene);
                            thinkVrmaAction.clampWhenFinished = true;
                            thinkVrmaAction.setEffectiveWeight(1.0);
                            thinkVrmaAction.setEffectiveTimeScale(1.0);
                            thinkVrmaAction.loop = window.THREE.LoopOnce;
                            console.log('Thinking VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                        } else {
                            console.warn('No animation clip found in Thinking VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload Thinking VRMA animation:', e);
                }
                
                // Optional: preload VRMA animation clip for cry pose (only for VRM 1.0)
                let cryVrmaAction = null;
                try {
                    // VRMA animations only work with VRM 1.0, skip for VRM 0.0
                    if (vrmVersion === '1.0' && POSE_CONFIG?.cry?.useVrma && POSE_CONFIG?.cry?.vrmaPath) {
                        const vrmaUrl = encodeURI(POSE_CONFIG.cry.vrmaPath);
                        console.log('Loading Cry VRMA from', vrmaUrl);
                        const vrmaGltf = await new Promise((resolve, reject) => {
                            loader.load(vrmaUrl, resolve, undefined, reject);
                        });
                        // Check multiple possible locations for VRMA data
                        let vrma = null;

                        // Try userData first
                        if (vrmaGltf?.userData?.vrmAnimations && Array.isArray(vrmaGltf.userData.vrmAnimations) && vrmaGltf.userData.vrmAnimations.length > 0) {
                            vrma = vrmaGltf.userData.vrmAnimations[0];
                        }
                        // Try extensions
                        else if (vrmaGltf?.extensions?.VRMC_vrm_animation) {
                            vrma = vrmaGltf.extensions.VRMC_vrm_animation;
                        }
                        // Try parser userData
                        else if (vrmaGltf?.parser?.userData?.vrmAnimations) {
                            vrma = vrmaGltf.parser.userData.vrmAnimations[0];
                        }

                        let clip = null;
                        
                        // Try instance method on VRMAnimation to retarget to this VRM
                        if (!clip && vrma && typeof vrma.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying vrma.createAnimationClip(vrm) for cry...');
                                clip = vrma.createAnimationClip(vrm); 
                                if (clip) {
                                    console.log('Successfully created cry clip via vrma.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('vrma.createAnimationClip failed for cry:', e);
                            }
                        }
                        // Static helper fallback if available
                        if (!clip && window.VRMAnimation && typeof window.VRMAnimation.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying VRMAnimation.createAnimationClip(vrma, vrm) for cry...');
                                clip = window.VRMAnimation.createAnimationClip(vrma, vrm); 
                                if (clip) {
                                    console.log('Successfully created cry clip via VRMAnimation.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('VRMAnimation.createAnimationClip failed for cry:', e);
                            }
                        }
                        // Synthesise THREE.AnimationClip if tracks array present
                        if (!clip) {
                            console.log('Trying to build cry clip manually from VRMA object...');
                            const built = buildClipFromVRMAObject(vrma, vrm);
                            if (built) { 
                                clip = built;
                                console.log('Successfully built cry clip manually');
                            }
                        }

                        if (clip) {
                            const boundClip = retargetClipToVRM(clip, vrm) || clip;
                            cryVrmaAction = mixer.clipAction(boundClip, vrm.scene);
                            cryVrmaAction.clampWhenFinished = true;
                            cryVrmaAction.setEffectiveWeight(1.0);
                            cryVrmaAction.setEffectiveTimeScale(1.0);
                            cryVrmaAction.loop = window.THREE.LoopOnce;
                            console.log('Cry VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                        } else {
                            console.warn('No animation clip found in Cry VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload Cry VRMA animation:', e);
                }
                
                // Optional: preload VRMA animation clip for angry pose (only for VRM 1.0)
                let angryVrmaAction = null;
                try {
                    // VRMA animations only work with VRM 1.0, skip for VRM 0.0
                    if (vrmVersion === '1.0' && POSE_CONFIG?.angry?.useVrma && POSE_CONFIG?.angry?.vrmaPath) {
                        const vrmaUrl = encodeURI(POSE_CONFIG.angry.vrmaPath);
                        console.log('Loading Angry VRMA from', vrmaUrl);
                        const vrmaGltf = await new Promise((resolve, reject) => {
                            loader.load(vrmaUrl, resolve, undefined, reject);
                        });
                        // Check multiple possible locations for VRMA data
                        let vrma = null;

                        // Try userData first
                        if (vrmaGltf?.userData?.vrmAnimations && Array.isArray(vrmaGltf.userData.vrmAnimations) && vrmaGltf.userData.vrmAnimations.length > 0) {
                            vrma = vrmaGltf.userData.vrmAnimations[0];
                        }
                        // Try extensions
                        else if (vrmaGltf?.extensions?.VRMC_vrm_animation) {
                            vrma = vrmaGltf.extensions.VRMC_vrm_animation;
                        }
                        // Try parser userData
                        else if (vrmaGltf?.parser?.userData?.vrmAnimations) {
                            vrma = vrmaGltf.parser.userData.vrmAnimations[0];
                        }

                        let clip = null;
                        
                        // Try instance method on VRMAnimation to retarget to this VRM
                        if (!clip && vrma && typeof vrma.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying vrma.createAnimationClip(vrm) for angry...');
                                clip = vrma.createAnimationClip(vrm); 
                                if (clip) {
                                    console.log('Successfully created angry clip via vrma.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('vrma.createAnimationClip failed for angry:', e);
                            }
                        }
                        // Static helper fallback if available
                        if (!clip && window.VRMAnimation && typeof window.VRMAnimation.createAnimationClip === 'function') {
                            try { 
                                console.log('Trying VRMAnimation.createAnimationClip(vrma, vrm) for angry...');
                                clip = window.VRMAnimation.createAnimationClip(vrma, vrm); 
                                if (clip) {
                                    console.log('Successfully created angry clip via VRMAnimation.createAnimationClip');
                                }
                            } catch(e) { 
                                console.warn('VRMAnimation.createAnimationClip failed for angry:', e);
                            }
                        }
                        // Synthesise THREE.AnimationClip if tracks array present
                        if (!clip) {
                            console.log('Trying to build angry clip manually from VRMA object...');
                            const built = buildClipFromVRMAObject(vrma, vrm);
                            if (built) { 
                                clip = built;
                                console.log('Successfully built angry clip manually');
                            }
                        }

                        if (clip) {
                            const boundClip = retargetClipToVRM(clip, vrm) || clip;
                            angryVrmaAction = mixer.clipAction(boundClip, vrm.scene);
                            angryVrmaAction.clampWhenFinished = true;
                            angryVrmaAction.setEffectiveWeight(1.0);
                            angryVrmaAction.setEffectiveTimeScale(1.0);
                            angryVrmaAction.loop = window.THREE.LoopOnce;
                            console.log('Angry VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                        } else {
                            console.warn('No animation clip found in Angry VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload Angry VRMA animation:', e);
                }
                
                // Optional: preload VRMA animation clip for idle animation (only for VRM 1.0)
                let idleVrmaAction = null;
                try {
                    // VRMA animations only work with VRM 1.0, skip for VRM 0.0
                    if (vrmVersion === '1.0') {
                        const vrmaUrl = encodeURI('./model_avatar/Eva/VRMA_06.vrma');
                        console.log('Loading Idle VRMA from', vrmaUrl);
                        const vrmaGltf = await new Promise((resolve, reject) => {
                            loader.load(vrmaUrl, resolve, undefined, reject);
                        });
                        // Check multiple possible locations for VRMA data
                        let vrma = null;

                        // Try userData first
                        if (vrmaGltf?.userData?.vrmAnimations && Array.isArray(vrmaGltf.userData.vrmAnimations) && vrmaGltf.userData.vrmAnimations.length > 0) {
                            vrma = vrmaGltf.userData.vrmAnimations[0];
                        }
                        // Try extensions
                        else if (vrmaGltf?.extensions?.VRMC_vrm_animation) {
                            vrma = vrmaGltf.extensions.VRMC_vrm_animation;
                        }
                        // Try parser userData
                        else if (vrmaGltf?.parser?.userData?.vrmAnimations) {
                            vrma = vrmaGltf.parser.userData.vrmAnimations[0];
                        }

                        let clip = null;
                        
                        // Try instance method on VRMAnimation to retarget to this VRM
                        if (!clip && vrma && typeof vrma.createAnimationClip === 'function') {
                            try { 
                                clip = vrma.createAnimationClip(vrm); 
                            } catch(e) { 
                                console.warn('vrma.createAnimationClip failed for idle:', e);
                            }
                        }
                        // Static helper fallback if available
                        if (!clip && window.VRMAnimation && typeof window.VRMAnimation.createAnimationClip === 'function') {
                            try { 
                                clip = window.VRMAnimation.createAnimationClip(vrma, vrm); 
                            } catch(e) { 
                                console.warn('VRMAnimation.createAnimationClip failed for idle:', e);
                            }
                        }
                        // Synthesise THREE.AnimationClip if tracks array present
                        if (!clip) {
                            const built = buildClipFromVRMAObject(vrma, vrm);
                            if (built) { 
                                clip = built;
                            }
                        }

                        if (clip) {
                            const boundClip = retargetClipToVRM(clip, vrm) || clip;
                            idleVrmaAction = mixer.clipAction(boundClip, vrm.scene);
                            idleVrmaAction.clampWhenFinished = false; // Return to base pose between delayed replays
                            idleVrmaAction.setEffectiveWeight(1.0);
                            idleVrmaAction.setEffectiveTimeScale(1.0);
                            idleVrmaAction.loop = window.THREE.LoopOnce; // Replay is scheduled manually with a random delay
                            idleVrmaAction.repetitions = 1;
                            console.log('Idle VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                        } else {
                            console.warn('No animation clip found in Idle VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload Idle VRMA animation:', e);
                }

                if (requestedGeneration !== vrmLoadGeneration || requestedModelPath !== currentVRMModelPath || !document.getElementById('vrm-mode')?.checked) {
                    disposeStaleVrmLoadResources(scene, renderer, mixer, vrm, gltf?.scene);
                    return;
                }
                
                const clock = new window.THREE.Clock();

                // Store references
                vrmModel = vrm;
                vrmScene = scene;
                vrmCamera = camera;
                vrmRenderer = renderer;
                vrmMixer = mixer;
                vrmClock = clock;
                vrmLoveVrmaAction = loveVrmaAction;
                vrmThinkVrmaAction = thinkVrmaAction;
                vrmCryVrmaAction = cryVrmaAction;
                vrmAngryVrmaAction = angryVrmaAction;
                vrmIdleVrmaAction = idleVrmaAction;
                vrmActiveModelPath = requestedModelPath;
                smoothedVrmDelta = 1 / 60;
                resetVrmPhysicsState(vrm);
                clearVrmIdleReplayTimer();
                vrmIdleHasPlayedOnce = false;
                attachVRMResizeHandler();
                resizeVRMViewport();

                // Apply initial transforms
                updateVRMTransform();

                // Create a look-at target and hook mouse movement so the avatar tracks the pointer
                const lookTarget = new window.THREE.Object3D(); // 3D object used as look target
                scene.add(lookTarget); // Add target into scene
                if (vrm.lookAt) { // If VRM has a lookAt component
                    vrm.lookAt.target = lookTarget; // Set target so head/eyes follow
                }
                let lastMouseMoveTs = performance.now(); // Timestamp of the most recent mouse move
                const onMouseMove = (event) => { // Mouse move handler to convert screen to world position
                    const rect = canvas.getBoundingClientRect(); // Canvas bounds for NDC conversion
                    const ndcX = ((event.clientX - rect.left) / rect.width) * 2 - 1; // Normalized X in clip space
                    const ndcY = -(((event.clientY - rect.top) / rect.height) * 2 - 1); // Normalized Y in clip space
                    const vec = new window.THREE.Vector3(ndcX, ndcY, 0.5); // Point in clip space depth 0.5
                    vec.unproject(camera); // Convert to world space
                    const dir = vec.sub(camera.position).normalize(); // Ray direction from camera
                    const distance = 2.0; // Distance in front of camera to place target
                    lookTarget.position.copy(camera.position).add(dir.multiplyScalar(distance)); // Update target position
                    lastMouseMoveTs = performance.now(); // Record the time of this mouse movement
                };
                canvas.addEventListener('mousemove', onMouseMove); // Attach mouse tracking
                canvas.__vrmMouseMoveHandler = onMouseMove; // Save handler for cleanup

                // Prepare simple idle animation to avoid T-pose (gentle arm and spine motion)
                const getBone = (name) => { // Helper to access humanoid bones using non-deprecated APIs
                    if (vrm.humanoid && typeof vrm.humanoid.getNormalizedBoneNode === 'function') { return vrm.humanoid.getNormalizedBoneNode(name); } // Prefer normalized bone
                    if (vrm.humanoid && typeof vrm.humanoid.getRawBoneNode === 'function') { return vrm.humanoid.getRawBoneNode(name); } // Fallback to raw bone
                    if (vrm.humanoid && typeof vrm.humanoid.getBoneNode === 'function') { return vrm.humanoid.getBoneNode(name); } // Legacy fallback
                    return null; // Not available
                }; // End bone helper
                const leftUpperArm = getBone('leftUpperArm'); // Left upper arm bone
                const rightUpperArm = getBone('rightUpperArm'); // Right upper arm bone
                const leftLowerArm = getBone('leftLowerArm'); // Left lower arm bone
                const rightLowerArm = getBone('rightLowerArm'); // Right lower arm bone
                const spineBone = getBone('spine'); // Spine bone
                const hipsBone = getBone('hips'); // Hips bone
                const chestBone = getBone('chest'); // Chest bone
                const upperChestBone = getBone('upperChest'); // Upper chest bone
                const neckBone = getBone('neck'); // Neck bone for head rotation blending
                const headBone = getBone('head'); // Head bone for direct head rotation
                const leftShoulder = getBone('leftShoulder'); // Left shoulder bone
                const rightShoulder = getBone('rightShoulder'); // Right shoulder bone
                const leftHand = getBone('leftHand'); // Left hand bone for love pose
                const rightHand = getBone('rightHand'); // Right hand bone for love pose
                const leftUpperLeg = getBone('leftUpperLeg'); // Left upper leg bone
                const rightUpperLeg = getBone('rightUpperLeg'); // Right upper leg bone
                const leftLowerLeg = getBone('leftLowerLeg'); // Left lower leg bone
                const rightLowerLeg = getBone('rightLowerLeg'); // Right lower leg bone
                const leftFoot = getBone('leftFoot'); // Left foot bone
                const rightFoot = getBone('rightFoot'); // Right foot bone
                const leftToes = getBone('leftToes'); // Left toe bone
                const rightToes = getBone('rightToes'); // Right toe bone
                const rightForeArm = getBone('rightLowerArm') || rightLowerArm; // Alias
                vrmPoseSnapshotBones = {
                    hips: hipsBone,
                    spine: spineBone,
                    chest: chestBone,
                    upperChest: upperChestBone,
                    neck: neckBone,
                    head: headBone,
                    leftShoulder,
                    rightShoulder,
                    leftUpperArm,
                    rightUpperArm,
                    leftLowerArm,
                    rightLowerArm,
                    leftHand,
                    rightHand,
                    leftUpperLeg,
                    rightUpperLeg,
                    leftLowerLeg,
                    rightLowerLeg,
                    leftFoot,
                    rightFoot,
                    leftToes,
                    rightToes
                };
                vrmBaseStandingPoseSnapshot = createVrmPoseSnapshot();
                vrmLastPoseSnapshot = vrmBaseStandingPoseSnapshot;
                vrmLastFrameHadRunningAction = false;
                vrmRestorePoseOnNextManualIdle = false;
                vrmPoseBlend = null;
                // Optional: load target arm/hand rotations from VRM pose JSON (skip when VRMA is used)
                let jsonPoseTargets = null;
                if (!POSE_CONFIG?.love?.useVrma) {
                    try {
                        jsonPoseTargets = await (await fetch(POSE_CONFIG.love.poseJsonPath)).json();
                    } catch (_) {}
                }
                // Map VRoid node names -> VRM humanoid canonical names (for pose retargeting)
                function mapVroidToHumanoid(name) { const M = { 'J_Bip_C_Hips': 'hips', 'J_Bip_C_Spine': 'spine', 'J_Bip_C_Chest': 'chest', 'J_Bip_C_UpperChest': 'upperChest', 'J_Bip_C_Neck': 'neck', 'J_Bip_C_Head': 'head', 'J_Bip_L_Shoulder': 'leftShoulder', 'J_Bip_L_UpperArm': 'leftUpperArm', 'J_Bip_L_LowerArm': 'leftLowerArm', 'J_Bip_L_Hand': 'leftHand', 'J_Bip_R_Shoulder': 'rightShoulder', 'J_Bip_R_UpperArm': 'rightUpperArm', 'J_Bip_R_LowerArm': 'rightLowerArm', 'J_Bip_R_Hand': 'rightHand', 'J_Bip_L_UpperLeg': 'leftUpperLeg', 'J_Bip_L_LowerLeg': 'leftLowerLeg', 'J_Bip_L_Foot': 'leftFoot', 'J_Bip_L_ToeBase': 'leftToes', 'J_Bip_R_UpperLeg': 'rightUpperLeg', 'J_Bip_R_LowerLeg': 'rightLowerLeg', 'J_Bip_R_Foot': 'rightFoot', 'J_Bip_R_ToeBase': 'rightToes', 'J_Bip_L_Thumb1': 'leftThumbProximal', 'J_Bip_L_Thumb2': 'leftThumbIntermediate', 'J_Bip_L_Thumb3': 'leftThumbDistal', 'J_Bip_L_Index1': 'leftIndexProximal', 'J_Bip_L_Index2': 'leftIndexIntermediate', 'J_Bip_L_Index3': 'leftIndexDistal', 'J_Bip_L_Middle1': 'leftMiddleProximal', 'J_Bip_L_Middle2': 'leftMiddleIntermediate', 'J_Bip_L_Middle3': 'leftMiddleDistal', 'J_Bip_L_Ring1': 'leftRingProximal', 'J_Bip_L_Ring2': 'leftRingIntermediate', 'J_Bip_L_Ring3': 'leftRingDistal', 'J_Bip_L_Little1': 'leftLittleProximal', 'J_Bip_L_Little2': 'leftLittleIntermediate', 'J_Bip_L_Little3': 'leftLittleDistal', 'J_Bip_R_Thumb1': 'rightThumbProximal', 'J_Bip_R_Thumb2': 'rightThumbIntermediate', 'J_Bip_R_Thumb3': 'rightThumbDistal', 'J_Bip_R_Index1': 'rightIndexProximal', 'J_Bip_R_Index2': 'rightIndexIntermediate', 'J_Bip_R_Index3': 'rightIndexDistal', 'J_Bip_R_Middle1': 'rightMiddleProximal', 'J_Bip_R_Middle2': 'rightMiddleIntermediate', 'J_Bip_R_Middle3': 'rightMiddleDistal', 'J_Bip_R_Ring1': 'rightRingProximal', 'J_Bip_R_Ring2': 'rightRingIntermediate', 'J_Bip_R_Ring3': 'rightRingDistal', 'J_Bip_R_Little1': 'rightLittleProximal', 'J_Bip_R_Little2': 'rightLittleIntermediate', 'J_Bip_R_Little3': 'rightLittleDistal' }; return M[name] || null; }
                // Convert the VRM Poser pose object -> { humanoid: {boneName:{rotation:[x,y,z,w]}} }
                function toHumanoidPoseFromVrmPoser(poseObj) { const out = { version: '1.0', humanoid: {} }; for (const b of poseObj?.bones || []) { const hName = mapVroidToHumanoid(b.boneName); if (!hName || !b.localRotation || b.localRotation.length !== 4) continue; const r = b.localRotation; out.humanoid[hName] = { rotation: [r[0], r[1], r[2], r[3]] }; } return out; }
                // Apply the converted pose to a VRM using normalized bones (works for 0.x and 1.0)
                function applyHumanoidPose(vrmInstance, humanoidPose) { const human = vrmInstance?.humanoid; if (!human) return; for (const [name, data] of Object.entries(humanoidPose.humanoid)) { const node = human.getNormalizedBoneNode(name); if (!node || !data?.rotation) continue; const q = data.rotation; node.quaternion.set(q[0], q[1], q[2], q[3]); node.updateMatrixWorld(true); } }
                // Utility to find a pose by name
                function findPoseEntry(poserJsonArray, poseName) { if (!Array.isArray(poserJsonArray)) return null; return poserJsonArray.find(p => p.poseName === poseName) || poserJsonArray[0] || null; }
                // Capture and restore helpers for quaternions
                function captureHumanoidQuats(vrmInstance, boneNames) { const human = vrmInstance?.humanoid; const out = {}; if (!human) return out; for (const n of boneNames) { const node = human.getNormalizedBoneNode(n); if (node) out[n] = node.quaternion.clone(); } return out; }
                function restoreHumanoidQuats(vrmInstance, captured) { const human = vrmInstance?.humanoid; if (!human || !captured) return; for (const [n, q] of Object.entries(captured)) { const node = human.getNormalizedBoneNode(n); if (node && q) { node.quaternion.copy(q); node.updateMatrixWorld(true); } } }
                let lovePoseRestore = null; // Captured quaternions for restoring after love pose

                // Retarget a THREE.AnimationClip (from VRMA/Mixamo names) to this VRM's bones by UUID
                function retargetClipToVRM(sourceClip, vrmInstance) {
                    try {
                        if (!sourceClip || !Array.isArray(sourceClip.tracks)) return sourceClip;
                        const human = vrmInstance?.humanoid; if (!human) return sourceClip;
                        const mixamoToHumanoid = {
                            'Hips': 'hips', 'Spine': 'spine', 'Chest': 'chest', 'UpperChest': 'upperChest', 'Neck': 'neck', 'Head': 'head',
                            'LeftShoulder': 'leftShoulder', 'LeftArm': 'leftUpperArm', 'LeftForeArm': 'leftLowerArm', 'LeftHand': 'leftHand',
                            'RightShoulder': 'rightShoulder', 'RightArm': 'rightUpperArm', 'RightForeArm': 'rightLowerArm', 'RightHand': 'rightHand',
                            'LeftUpLeg': 'leftUpperLeg', 'LeftLeg': 'leftLowerLeg', 'LeftFoot': 'leftFoot', 'LeftToeBase': 'leftToes',
                            'RightUpLeg': 'rightUpperLeg', 'RightLeg': 'rightLowerLeg', 'RightFoot': 'rightFoot', 'RightToeBase': 'rightToes',
                            'LeftHandThumb1': 'leftThumbProximal', 'LeftHandThumb2': 'leftThumbIntermediate', 'LeftHandThumb3': 'leftThumbDistal',
                            'LeftHandIndex1': 'leftIndexProximal', 'LeftHandIndex2': 'leftIndexIntermediate', 'LeftHandIndex3': 'leftIndexDistal',
                            'LeftHandMiddle1': 'leftMiddleProximal', 'LeftHandMiddle2': 'leftMiddleIntermediate', 'LeftHandMiddle3': 'leftMiddleDistal',
                            'LeftHandRing1': 'leftRingProximal', 'LeftHandRing2': 'leftRingIntermediate', 'LeftHandRing3': 'leftRingDistal',
                            'LeftHandPinky1': 'leftLittleProximal', 'LeftHandPinky2': 'leftLittleIntermediate', 'LeftHandPinky3': 'leftLittleDistal',
                            'RightHandThumb1': 'rightThumbProximal', 'RightHandThumb2': 'rightThumbIntermediate', 'RightHandThumb3': 'rightThumbDistal',
                            'RightHandIndex1': 'rightIndexProximal', 'RightHandIndex2': 'rightIndexIntermediate', 'RightHandIndex3': 'rightIndexDistal',
                            'RightHandMiddle1': 'rightMiddleProximal', 'RightHandMiddle2': 'rightMiddleIntermediate', 'RightHandMiddle3': 'rightMiddleDistal',
                            'RightHandRing1': 'rightRingProximal', 'RightHandRing2': 'rightRingIntermediate', 'RightHandRing3': 'rightRingDistal',
                            'RightHandPinky1': 'rightLittleProximal', 'RightHandPinky2': 'rightLittleIntermediate', 'RightHandPinky3': 'rightLittleDistal'
                        };
                        const retargetedTracks = [];
                        for (const t of sourceClip.tracks) {
                            const parts = String(t.name || '').split('.');
                            if (parts.length < 2) continue;
                            const srcNode = parts[0];
                            const prop = parts.slice(1).join('.');
                            // Only retarget rotations; skip position/scale to avoid moving the rig off-screen
                            if (!/^quaternion(\.|$)/i.test(prop)) continue;
                            const humanoidName = mixamoToHumanoid[srcNode];
                            if (!humanoidName) continue;
                            // Bind to raw bone node to ensure stable bindings for animation
                            const node = (typeof human.getRawBoneNode === 'function') ? human.getRawBoneNode(humanoidName) : human.getNormalizedBoneNode(humanoidName);
                            if (!node) continue;
                            const newName = `${node.uuid}.${prop}`;
                            // Recreate the track with the same constructor and values but different name
                            const Cls = t.constructor; // e.g., THREE.QuaternionKeyframeTrack
                            const newTrack = new Cls(newName, t.times.slice(), t.values.slice(), t.interpolation);
                            retargetedTracks.push(newTrack);
                        }
                        if (retargetedTracks.length === 0) return sourceClip;
                        const THREE_NS = window.THREE;
                        const out = new THREE_NS.AnimationClip(sourceClip.name || 'retargeted', sourceClip.duration, retargetedTracks);
                        return out;
                    } catch (_) { return sourceClip; }
                }

                // Build a THREE.AnimationClip directly from a VRMAnimation object when helper APIs are unavailable
                function buildClipFromVRMAObject(vrmaObj, vrmInstance) {
                    try {
                        if (!vrmaObj) return null;
                        const human = vrmInstance?.humanoid; if (!human) return null;
                        const THREE_NS = window.THREE;
                        const outTracks = [];
                        const isTyped = (x) => x && typeof x === 'object' && typeof x.BYTES_PER_ELEMENT === 'number';
                        const asFloatArray = (x) => {
                            if (!x) return null;
                            if (Array.isArray(x)) return Float32Array.from(x);
                            if (isTyped(x)) return new Float32Array(x);
                            return null;
                        };
                        // Try multiple possible locations for tracks
                        let tracksContainer = vrmaObj.humanoidTracks;

                        // Fallback to alternative track structures
                        if (!tracksContainer || (Array.isArray(tracksContainer) && tracksContainer.length === 0)) {
                            if (vrmaObj.humanoidAnimationTracks) {
                                tracksContainer = vrmaObj.humanoidAnimationTracks;
                                console.log('Using humanoidAnimationTracks as fallback');
                            } else if (vrmaObj.tracks) {
                                tracksContainer = vrmaObj.tracks;
                                console.log('Using tracks as fallback');
                            } else if (vrmaObj.animations && Array.isArray(vrmaObj.animations)) {
                                tracksContainer = vrmaObj.animations;
                                console.log('Using animations as fallback');
                            }
                        }

                        // Handle VRMA 1.0 structure: { translation: Map, rotation: Map }
                        if (tracksContainer && typeof tracksContainer === 'object' && !Array.isArray(tracksContainer) && 
                            (tracksContainer.translation instanceof Map || tracksContainer.rotation instanceof Map)) {
                            console.log('Detected VRMA 1.0 structure with translation/rotation Maps');
                            
                            // Process rotation tracks
                            if (tracksContainer.rotation instanceof Map) {
                                console.log('Processing rotation tracks, count:', tracksContainer.rotation.size);
                                for (const [boneName, trackData] of tracksContainer.rotation) {
                                    try {
                                        const node = (typeof human.getRawBoneNode === 'function') 
                                            ? human.getRawBoneNode(boneName) 
                                            : human.getNormalizedBoneNode(boneName);
                                        if (!node) {
                                            console.warn('VRMA build: bone not found for', boneName);
                                            continue;
                                        }
                                        
                                        let times = trackData.times;
                                        let values = trackData.values;
                                        
                                        times = asFloatArray(times) || (Array.isArray(times) ? Float32Array.from(times) : null);
                                        values = asFloatArray(values) || (Array.isArray(values) ? Float32Array.from(values) : null);
                                        
                                        if (!times || !values || times.length === 0 || values.length === 0) {
                                            console.warn('VRMA build: invalid times/values for', boneName);
                                            continue;
                                        }
                                        
                                        const trackName = node.uuid + '.quaternion';
                                        const track = new THREE_NS.QuaternionKeyframeTrack(trackName, times, values);
                                        outTracks.push(track);
                                    } catch (e) {
                                        console.warn('Error processing rotation track for', boneName, ':', e);
                                    }
                                }
                            }
                            
                            // Process translation tracks (usually just hips)
                            // DISABLED: Skip translation tracks to prevent model position changes
                            // This keeps the model at its configured position in the viewing window
                            if (false && tracksContainer.translation instanceof Map) {
                                console.log('Processing translation tracks, count:', tracksContainer.translation.size);
                                for (const [boneName, trackData] of tracksContainer.translation) {
                                    try {
                                        const node = (typeof human.getRawBoneNode === 'function') 
                                            ? human.getRawBoneNode(boneName) 
                                            : human.getNormalizedBoneNode(boneName);
                                        if (!node) {
                                            console.warn('VRMA build: bone not found for translation', boneName);
                                            continue;
                                        }
                                        
                                        let times = trackData.times;
                                        let values = trackData.values;
                                        
                                        times = asFloatArray(times) || (Array.isArray(times) ? Float32Array.from(times) : null);
                                        values = asFloatArray(values) || (Array.isArray(values) ? Float32Array.from(values) : null);
                                        
                                        if (!times || !values || times.length === 0 || values.length === 0) continue;
                                        
                                        const trackName = node.uuid + '.position';
                                        const track = new THREE_NS.VectorKeyframeTrack(trackName, times, values);
                                        outTracks.push(track);
                                    } catch (e) {
                                        console.warn('Error processing translation track for', boneName, ':', e);
                                    }
                                }
                            } else {
                                console.log('Translation tracks skipped to preserve model position');
                            }
                        }
                        
                        // Convert tracksContainer to array, handling Map, Array, and Object (for other formats)
                        let list = [];
                        if (Array.isArray(tracksContainer)) {
                            list = tracksContainer;
                        } else if (tracksContainer instanceof Map) {
                            list = Array.from(tracksContainer.values());
                            console.log('Converted Map to array, length:', list.length);
                        } else if (tracksContainer && typeof tracksContainer === 'object' && 
                                   !(tracksContainer.translation instanceof Map || tracksContainer.rotation instanceof Map)) {
                            list = Object.values(tracksContainer);
                        }
                        
                        if (list && list.length > 0) {
                            try { console.log('First humanoidTrack keys:', Object.keys(list[0] || {})); } catch (_) {}
                        } else if (tracksContainer && typeof tracksContainer === 'object') {
                            try { 
                                if (tracksContainer instanceof Map) {
                                    const firstKey = Array.from(tracksContainer.keys())[0];
                                    console.log('First humanoidTrack Map key:', firstKey);
                                } else {
                                    const firstKey = Object.keys(tracksContainer)[0]; 
                                    console.log('First humanoidTrack obj key:', firstKey);
                                }
                            } catch(_) {}
                        }
                        for (let i = 0; i < list.length; i++) {
                            const ht = list[i];
                            if (!ht) continue;
                            const hName = ht.humanoidName || ht.name || ht.bone || ht.node || (ht.target && (ht.target.humanoidName || ht.target.name));
                            if (!hName) continue;
                            const node = (typeof human.getRawBoneNode === 'function') ? human.getRawBoneNode(hName) : human.getNormalizedBoneNode(hName);
                            if (!node) { try { if (i === 0) console.warn('VRMA build: bone not found for', hName); } catch(_) {} continue; }
                            // Collect times
                            let times = ht.times || ht.timeSamples || ht.timestamps || ht.time || (Array.isArray(ht.keyframes) ? ht.keyframes.map(k => k.time) : null);
                            times = asFloatArray(times) || (Array.isArray(times) ? Float32Array.from(times) : null);
                            // Collect values (quaternions): flatten if nested or map from keyframes with x,y,z,w
                            let values = ht.values || ht.rotations || ht.quaternions || (ht.data && (ht.data.values || ht.data.rotations || ht.data.quaternions)) || null;
                            if (!values && Array.isArray(ht.keyframes)) {
                                const qArr = [];
                                for (const kf of ht.keyframes) {
                                    const r = (kf.rotation || kf.quaternion || kf.value || kf);
                                    if (Array.isArray(r)) { qArr.push(r[0], r[1], r[2], r[3]); }
                                    else if (r && typeof r === 'object' && 'x' in r && 'y' in r && 'z' in r && 'w' in r) { qArr.push(r.x, r.y, r.z, r.w); }
                                }
                                values = qArr;
                            }
                            // If nested arrays, flatten
                            if (Array.isArray(values) && values.length > 0 && Array.isArray(values[0])) { values = values.flat(); }
                            values = asFloatArray(values) || (Array.isArray(values) ? Float32Array.from(values) : null);
                            // If no times but we have values and duration, synthesize evenly spaced times
                            if ((!times || times.length === 0) && values && values.length >= 4 && typeof vrmaObj.duration === 'number' && vrmaObj.duration > 0) {
                                const numKeys = Math.floor(values.length / 4);
                                const out = new Float32Array(numKeys);
                                for (let k = 0; k < numKeys; k++) out[k] = (vrmaObj.duration * k) / Math.max(1, numKeys - 1);
                                times = out;
                            }
                            if (!times || times.length === 0) { try { if (i === 0) console.warn('VRMA build: missing times for', hName); } catch(_) {} continue; }
                            if (!values || values.length < times.length * 4) { try { if (i === 0) console.warn('VRMA build: values length mismatch for', hName, 'times', times.length, 'values', values ? values.length : 0); } catch(_) {} continue; }
                            // Collect values (quaternions): flatten if nested or map from keyframes with x,y,z,w
                            const trackName = `${node.uuid}.quaternion`;
                            const track = new THREE_NS.QuaternionKeyframeTrack(trackName, times, values);
                            outTracks.push(track);
                        }
                        // Process expression tracks (morph targets / blend shapes)
                        if (vrmaObj.expressionTracks) {
                            const expressionManager = vrmInstance?.expressionManager;
                            if (expressionManager && vrmaObj.expressionTracks instanceof Map) {
                                console.log('Processing expression tracks, count:', vrmaObj.expressionTracks.size);
                                for (const [expressionName, trackData] of vrmaObj.expressionTracks) {
                                    try {
                                        const expression = expressionManager.getExpression(expressionName);
                                        if (!expression) {
                                            console.warn('VRMA build: expression not found:', expressionName);
                                            continue;
                                        }
                                        
                                        let times = trackData.times;
                                        let values = trackData.values;
                                        
                                        times = asFloatArray(times) || (Array.isArray(times) ? Float32Array.from(times) : null);
                                        values = asFloatArray(values) || (Array.isArray(values) ? Float32Array.from(values) : null);
                                        
                                        if (!times || !values || times.length === 0 || values.length === 0) continue;
                                        
                                        // VRM expressions need to be controlled via expressionManager.setValue()
                                        // For now, we'll skip these in the manual builder as they need special handling
                                        console.log('Note: Expression track', expressionName, 'requires VRMAnimation API for proper playback');
                                    } catch (e) {
                                        console.warn('Error processing expression track for', expressionName, ':', e);
                                    }
                                }
                            }
                        }
                        
                        if (outTracks.length === 0) return null;
                        const duration = (typeof vrmaObj.duration === 'number' && vrmaObj.duration > 0) ? vrmaObj.duration : -1;
                        console.log('Built animation clip with', outTracks.length, 'tracks, duration:', duration);
                        return new THREE_NS.AnimationClip(vrmaObj.name || 'vrma-built', duration, outTracks);
                    } catch (e) { console.warn('buildClipFromVRMAObject failed:', e); return null; }
                }
                const convertUnityToThree = (q) => {
                    // JSON localRotation order is [x, y, z, w]. We treat it as a Unity quaternion.
                    // If conversion is enabled, flip X and Z to account for handedness differences.
                    if (POSE_CONFIG.love.convertUnityQuat) {
                        return new window.THREE.Quaternion(-q.x, q.y, -q.z, q.w).normalize();
                    }
                    return new window.THREE.Quaternion(q.x, q.y, q.z, q.w).normalize();
                };
                const readQuatForPose = (poseName, name) => {
                    if (!jsonPoseTargets) return null;
                    const pose = jsonPoseTargets.find(p => p.poseName === poseName);
                    if (!pose) return null;
                    const bone = pose.bones.find(b => b.boneName === name);
                    if (!bone || !bone.localRotation) return null;
                    const q = bone.localRotation; // [x,y,z,w] in Unity space order
                    const unityQ = new window.THREE.Quaternion(q[0], q[1], q[2], q[3]);
                    return convertUnityToThree(unityQ);
                };
                const qLUpper = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_L_UpperArm');
                const qRUpper = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_R_UpperArm');
                const qLLower = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_L_LowerArm');
                const qRLower = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_R_LowerArm');
                const qLHand  = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_L_Hand');
                const qRHand  = readQuatForPose(POSE_CONFIG.love.poseName, 'J_Bip_R_Hand');
                const bLUpper = readQuatForPose('Base', 'J_Bip_L_UpperArm');
                const bRUpper = readQuatForPose('Base', 'J_Bip_R_UpperArm');
                const bLLower = readQuatForPose('Base', 'J_Bip_L_LowerArm');
                const bRLower = readQuatForPose('Base', 'J_Bip_R_LowerArm');
                const bLHand  = readQuatForPose('Base', 'J_Bip_L_Hand');
                const bRHand  = readQuatForPose('Base', 'J_Bip_R_Hand');

                // Capture the model's neutral (current) bind orientation as a reference
                const neutral = {
                    LUpper: leftUpperArm ? leftUpperArm.quaternion.clone() : null,
                    RUpper: rightUpperArm ? rightUpperArm.quaternion.clone() : null,
                    LLower: leftLowerArm ? leftLowerArm.quaternion.clone() : null,
                    RLower: rightLowerArm ? rightLowerArm.quaternion.clone() : null,
                    LHand: leftHand ? leftHand.quaternion.clone() : null,
                    RHand: rightHand ? rightHand.quaternion.clone() : null
                };

                // Compute deltas Heart relative to Base so we respect the rig's bind orientation
                const deltaOr = (baseQ, heartQ) => {
                    if (!heartQ) return null;
                    if (!baseQ) return heartQ.clone();
                    const invBase = baseQ.clone().invert();
                    return invBase.multiply(heartQ).normalize();
                };
                const dLUpper = deltaOr(bLUpper, qLUpper);
                const dRUpper = deltaOr(bRUpper, qRUpper);
                const dLLower = deltaOr(bLLower, qLLower);
                const dRLower = deltaOr(bRLower, qRLower);
                const dLHand  = deltaOr(bLHand,  qLHand);
                const dRHand  = deltaOr(bRHand,  qRHand);
                const baseLeftArmZ = leftUpperArm ? leftUpperArm.rotation.z : 0; // Capture base left arm Z rotation
                const baseRightArmZ = rightUpperArm ? rightUpperArm.rotation.z : 0; // Capture base right arm Z rotation
                const baseLeftArmY = leftUpperArm ? leftUpperArm.rotation.y : 0; // Capture base left arm Y rotation
                const baseRightArmY = rightUpperArm ? rightUpperArm.rotation.y : 0; // Capture base right arm Y rotation
                const baseLeftUpperArmX = leftUpperArm ? leftUpperArm.rotation.x : 0; // Base left upper arm forward
                const baseLeftLowerArmZ = leftLowerArm ? leftLowerArm.rotation.z : 0; // Capture base left elbow hinge (Z)
                const baseRightLowerArmZ = rightLowerArm ? rightLowerArm.rotation.z : 0; // Capture base right elbow hinge (Z)
                const baseSpineY = spineBone ? spineBone.position.y : 0; // Capture base spine Y position
                const baseNeckX = neckBone ? neckBone.rotation.x : 0; // Capture base neck X rotation (pitch)
                const baseNeckY = neckBone ? neckBone.rotation.y : 0; // Capture base neck Y rotation (yaw)
                const baseHeadX = headBone ? headBone.rotation.x : 0; // Capture base head X rotation (pitch)
                const baseHeadY = headBone ? headBone.rotation.y : 0; // Capture base head Y rotation (yaw)
                const baseLeftHandY = leftHand ? leftHand.rotation.y : 0; // Base left hand yaw
                const baseRightHandY = rightHand ? rightHand.rotation.y : 0; // Base right hand yaw
                const baseRightUpperArmX = rightUpperArm ? rightUpperArm.rotation.x : 0; // Base right upper arm pitch
                const baseRightUpperArmY = rightUpperArm ? rightUpperArm.rotation.y : 0; // Base right upper arm yaw
                const baseRightUpperArmZ = rightUpperArm ? rightUpperArm.rotation.z : 0; // Base right upper arm roll
                const baseRightForeArmX = rightForeArm ? rightForeArm.rotation.x : 0; // Base right forearm bend
                const baseHeadZ = headBone ? headBone.rotation.z : 0; // Base head roll
                const armLowering = 1.25; // Baseline to lower arms naturally alongside torso
                const armInward = 0.18; // Baseline to rotate arms slightly inward towards body
                const elbowBend = 0.25; // Baseline elbow bend so arms are relaxed
                const idleStart = performance.now(); // Idle start time reference

                // Start render loop
                function animate() {
                    if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm)) {
                        return;
                    }
                    vrmAnimationFrameId = requestAnimationFrame(animate);

                    if (vrmClock) {
                        const rawDelta = vrmClock.getDelta();
                        const { animationDelta, physicsDelta } = getStableVrmFrameDeltas(rawDelta);
                        // Update mixer with a capped animation delta so action transitions do not jump after browser stalls.
                        if (vrmMixer) {
                            vrmMixer.update(animationDelta);
                            updateVrmPoseBlend(performance.now());
                            
                            // Check if any other animation is running
                            const hasActiveAnimation = 
                                (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) ||
                                (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) ||
                                (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) ||
                                (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning());
                            
                            // Play idle animation if no other animation is running
                            if (vrmIdleVrmaAction && !hasActiveAnimation) {
                                if (!vrmIdleVrmaAction.isRunning()) {
                                    if (!vrmIdleHasPlayedOnce) {
                                        playVrmIdleAction();
                                    } else {
                                        scheduleNextVrmIdlePlayback();
                                    }
                                }
                            } else if (vrmIdleVrmaAction && hasActiveAnimation) {
                                // Stop idle animation when other animations are playing
                                if (vrmIdleVrmaAction.isRunning()) {
                                    stopVrmAction(vrmIdleVrmaAction, VRM_IDLE_ACTION_FADE_OUT_SECONDS);
                                }
                            }
                            
                            // Debug animation state periodically
                            if (window.debugAnimationFrames === undefined) window.debugAnimationFrames = 0;
                            window.debugAnimationFrames++;
                            if (window.debugAnimationFrames % 60 === 0) {
                                if (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) {
                                    const actionState = {
                                        type: 'Love',
                                        isRunning: vrmLoveVrmaAction.isRunning(),
                                        isScheduled: vrmLoveVrmaAction.isScheduled(),
                                        time: vrmLoveVrmaAction.time.toFixed(2),
                                        weight: vrmLoveVrmaAction.getEffectiveWeight()
                                    };
                                    console.log('Love Animation running:', actionState, '- Manual pose control DISABLED');
                                }
                                if (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) {
                                    const actionState = {
                                        type: 'Think',
                                        isRunning: vrmThinkVrmaAction.isRunning(),
                                        isScheduled: vrmThinkVrmaAction.isScheduled(),
                                        time: vrmThinkVrmaAction.time.toFixed(2),
                                        weight: vrmThinkVrmaAction.getEffectiveWeight()
                                    };
                                    console.log('Think Animation running:', actionState, '- Manual pose control DISABLED');
                                }
                                if (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) {
                                    const actionState = {
                                        type: 'Cry',
                                        isRunning: vrmCryVrmaAction.isRunning(),
                                        isScheduled: vrmCryVrmaAction.isScheduled(),
                                        time: vrmCryVrmaAction.time.toFixed(2),
                                        weight: vrmCryVrmaAction.getEffectiveWeight()
                                    };
                                    console.log('Cry Animation running:', actionState, '- Manual pose control DISABLED');
                                }
                                if (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning()) {
                                    const actionState = {
                                        type: 'Angry',
                                        isRunning: vrmAngryVrmaAction.isRunning(),
                                        isScheduled: vrmAngryVrmaAction.isScheduled(),
                                        time: vrmAngryVrmaAction.time.toFixed(2),
                                        weight: vrmAngryVrmaAction.getEffectiveWeight()
                                    };
                                    console.log('Angry Animation running:', actionState, '- Manual pose control DISABLED');
                                }
                            }
                        }
                        // Idle head/eye movement by drifting the look target when mouse is idle
                        if (lookTarget && vrmCamera) { // Ensure target and camera exist
                            const idleFor = performance.now() - lastMouseMoveTs; // Duration since last mouse move
                            if (idleFor > 1500) { // Only apply drift after 1.5s of inactivity
                                const forward = new window.THREE.Vector3(); // Camera forward vector container
                                vrmCamera.getWorldDirection(forward).normalize(); // Compute normalized forward
                                const worldUp = new window.THREE.Vector3(0, 1, 0); // World up axis vector
                                const right = new window.THREE.Vector3().crossVectors(forward, worldUp).normalize(); // Camera right vector
                                const up = new window.THREE.Vector3().crossVectors(right, forward).normalize(); // Camera up vector
                                const t = performance.now() * 0.001; // Time in seconds for oscillation
                                const dx = Math.sin(t * 0.6) * 0.25 + Math.sin(t * 1.1 + 1.7) * 0.08; // Horizontal drift offset
                                const dy = Math.sin(t * 0.8 + 0.5) * 0.18 + Math.sin(t * 1.3 + 2.2) * 0.06; // Vertical drift offset
                                const base = new window.THREE.Vector3().copy(vrmCamera.position).add(forward.multiplyScalar(2.0)); // Base point in front of camera
                                const targetPos = new window.THREE.Vector3().copy(base).add(right.multiplyScalar(dx)).add(up.multiplyScalar(dy)); // New target position
                                lookTarget.position.lerp(targetPos, 0.05); // Smoothly approach new position
                            }
                        }
                        // Blend weights toward targets for poses
                        lovePoseWeight += (targetLovePoseWeight - lovePoseWeight) * POSE_CONFIG.blendSmoothing; // Ease-in/out
                        thinkPoseWeight += (targetThinkPoseWeight - thinkPoseWeight) * POSE_CONFIG.blendSmoothing; // Ease-in/out

                // Apply lightweight idle motion each frame (with love/think pose handling)
                        const t = (performance.now() - idleStart) / 1000; // Seconds since start
                        const sway = Math.sin(t * 1.1) * 0.035; // Small sway factor
                        const breathe = Math.sin(t * 2.0) * 0.01; // Small breathing factor
                        const inwardSway = Math.sin(t * 0.7) * 0.03; // Tiny inward/outward sway
                        const elbowSway = Math.sin(t * 1.7) * 0.06; // Small elbow motion for naturalness
                // Strict Love pose (disabled when using VRMA)
                if (vrmLovePoseActive && !POSE_CONFIG.love.expressionsOnly && !POSE_CONFIG.love.useVrma && (dLUpper || dRUpper || dLLower || dRLower || dLHand || dRHand)) {
                    try { if (leftUpperArm && dLUpper && neutral.LUpper) { leftUpperArm.quaternion.copy(neutral.LUpper.clone().multiply(dLUpper)); } } catch(_){}
                    try { if (rightUpperArm && dRUpper && neutral.RUpper) { rightUpperArm.quaternion.copy(neutral.RUpper.clone().multiply(dRUpper)); } } catch(_){}
                    try { if (leftLowerArm && dLLower && neutral.LLower) { leftLowerArm.quaternion.copy(neutral.LLower.clone().multiply(dLLower)); } } catch(_){}
                    try { if (rightLowerArm && dRLower && neutral.RLower) { rightLowerArm.quaternion.copy(neutral.RLower.clone().multiply(dRLower)); } } catch(_){}
                    try { if (leftHand && dLHand && neutral.LHand) { leftHand.quaternion.copy(neutral.LHand.clone().multiply(dLHand)); } } catch(_){}
                    try { if (rightHand && dRHand && neutral.RHand) { rightHand.quaternion.copy(neutral.RHand.clone().multiply(dRHand)); } } catch(_){}
                } else if (!hasRunningVrmAction()) {
                    // Only apply manual pose control if VRMA animations are NOT running
                    if (vrmLastPoseSnapshot && (vrmLastFrameHadRunningAction || vrmRestorePoseOnNextManualIdle)) {
                        restoreVrmPoseSnapshot(vrmLastPoseSnapshot);
                        vrmRestorePoseOnNextManualIdle = false;
                    }
                    // For VRM 0.0, set arms to natural rest pose (slightly rotated inward, hanging naturally)
                    if (vrmVersion === '0.0' && vrm && vrm.meta && vrm.meta.metaVersion === '0') {
                        try {
                            // Set arms to natural rest pose (hanging by sides with slight inward rotation)
                            // Left arm: slight inward rotation (positive Y rotation)
                            if (leftUpperArm) {
                                leftUpperArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 1, 0), 
                                    Math.PI * 0.05 // ~9 degrees inward
                                );
                            }
                            // Right arm: slight inward rotation (negative Y rotation)
                            if (rightUpperArm) {
                                rightUpperArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 1, 0), 
                                    -Math.PI * 0.05 // ~9 degrees inward
                                );
                            }
                            // Lower arms: slight forward rotation for natural hang
                            if (leftLowerArm) {
                                leftLowerArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 0, 1), 
                                    Math.PI * 0.02 // ~3.6 degrees forward
                                );
                            }
                            if (rightLowerArm) {
                                rightLowerArm.quaternion.setFromAxisAngle(
                                    new window.THREE.Vector3(0, 0, 1), 
                                    -Math.PI * 0.02 // ~3.6 degrees forward
                                );
                            }
                            // Hands: keep neutral
                            if (leftHand) leftHand.quaternion.set(0, 0, 0, 1);
                            if (rightHand) rightHand.quaternion.set(0, 0, 0, 1);
                            // Shoulders: keep neutral
                            if (leftShoulder) leftShoulder.quaternion.set(0, 0, 0, 1);
                            if (rightShoulder) rightShoulder.quaternion.set(0, 0, 0, 1);
                        } catch (e) {
                            // Silently handle any errors to avoid console spam
                        }
                    } else {
                        // Normal idle animation for VRM 1.0
                        const w = lovePoseWeight; // Shorthand for love pose
                        const wt = thinkPoseWeight; // Shorthand for think pose
                        const applyLimbs = !POSE_CONFIG.love.expressionsOnly; // Skip love limb offsets when expressions-only is enabled
                        const wL = applyLimbs ? w : 0; // Use 0 weight for limbs when expressions-only, to keep idle only
                        // Compute defaults (relaxed idle) and targets (love pose), then blend
                        if (leftUpperArm) {
                            const defZ = baseLeftArmZ - armLowering + sway; // relaxed lowered
                            const tgtZ = baseLeftArmZ - armLowering * POSE_CONFIG.love.upperArmRollFactor; // minimal side roll to reduce flare
                            leftUpperArm.rotation.z = defZ * (1 - wL) + tgtZ * wL;
                            const defY = baseLeftArmY + armInward + inwardSway; // slight inward
                            const tgtY = baseLeftArmY + POSE_CONFIG.love.upperArmYawIn; // inward toward chest
                            leftUpperArm.rotation.y = defY * (1 - wL) + tgtY * wL;
                            const defX = baseLeftUpperArmX; // minimal forward
                            const tgtX = baseLeftUpperArmX - POSE_CONFIG.love.upperArmPitchForward; // forward pitch (negative)
                            leftUpperArm.rotation.x = defX * (1 - wL) + tgtX * wL;
                            // If JSON pose targets provided, blend toward them too
                            if (applyLimbs && qLUpper) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(leftUpperArm.rotation);
                                const blended = curQ.clone().slerp(qLUpper, Math.min(1, wL * 0.85));
                                leftUpperArm.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (rightUpperArm) {
                            const defZ = baseRightArmZ + armLowering - sway; // relaxed lowered
                            const tgtZ = baseRightArmZ + armLowering * POSE_CONFIG.love.upperArmRollFactor; // minimal side roll to reduce flare
                            let outZ = defZ * (1 - wL) + tgtZ * wL; // Start from love blend (or idle only)
                            const defY = baseRightArmY - armInward - inwardSway; // slight inward
                            const tgtY = baseRightArmY - POSE_CONFIG.love.upperArmYawIn; // inward toward chest
                            let outY = defY * (1 - wL) + tgtY * wL;
                            const defX = baseRightUpperArmX; // minimal forward
                            const tgtX = baseRightUpperArmX - POSE_CONFIG.love.upperArmPitchForward; // forward pitch (negative)
                            let outX = defX * (1 - wL) + tgtX * wL;
                            // Thinking pose adjustment: bring right hand to chin (raise and yaw inward more)
                            if (wt > 0 && !POSE_CONFIG.think.expressionsOnly) {
                                const tRaise = baseRightUpperArmX - POSE_CONFIG.think.upperArmPitchForward; // raise further forward
                                const tYawIn = baseRightUpperArmY - POSE_CONFIG.think.upperArmYawIn; // yaw inward more
                                const tRoll = baseRightUpperArmZ + POSE_CONFIG.think.upperArmRollZ; // slight roll to align palm
                                outX = outX * (1 - wt) + tRaise * wt;
                                outY = outY * (1 - wt) + tYawIn * wt;
                                outZ = outZ * (1 - wt) + tRoll * wt;
                            }
                            rightUpperArm.rotation.x = outX;
                            rightUpperArm.rotation.y = outY;
                            rightUpperArm.rotation.z = outZ;
                            if (applyLimbs && qRUpper) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(rightUpperArm.rotation);
                                const blended = curQ.clone().slerp(qRUpper, Math.min(1, wL * 0.85));
                                rightUpperArm.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (leftLowerArm) {
                            const def = baseLeftLowerArmZ + elbowBend + elbowSway; // relaxed elbow on Z hinge
                            const tgt = baseLeftLowerArmZ + POSE_CONFIG.love.forearmBend; // stronger bend toward chest
                            let outL = def * (1 - wL) + tgt * wL;
                            leftLowerArm.rotation.z = outL;
                            if (applyLimbs && qLLower) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(leftLowerArm.rotation);
                                const blended = curQ.clone().slerp(qLLower, Math.min(1, wL * 0.9));
                                leftLowerArm.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (rightLowerArm) {
                            const def = baseRightLowerArmZ + elbowBend - elbowSway; // relaxed elbow on Z hinge
                            const tgt = baseRightLowerArmZ + POSE_CONFIG.love.forearmBend; // stronger bend toward chest
                            let out = def * (1 - wL) + tgt * wL;
                            if (wt > 0 && !POSE_CONFIG.think.expressionsOnly) {
                                const tFore = baseRightLowerArmZ + POSE_CONFIG.think.forearmBendExtra; // stronger bend to reach chin
                                out = out * (1 - wt) + tFore * wt;
                            }
                            rightLowerArm.rotation.z = out;
                            if (applyLimbs && qRLower) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(rightLowerArm.rotation);
                                const blended = curQ.clone().slerp(qRLower, Math.min(1, wL * 0.9));
                                rightLowerArm.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (leftHand) {
                            const def = baseLeftHandY; // relaxed
                            const tgt = baseLeftHandY + POSE_CONFIG.love.handYawIn; // strong inward to chest
                            leftHand.rotation.y = def * (1 - wL) + tgt * wL;
                            if (applyLimbs && qLHand) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(leftHand.rotation);
                                const blended = curQ.clone().slerp(qLHand, Math.min(1, wL));
                                leftHand.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (rightHand) {
                            const def = baseRightHandY; // relaxed
                            const tgt = baseRightHandY - POSE_CONFIG.love.handYawIn; // strong inward to chest (mirror)
                            let out = def * (1 - wL) + tgt * wL;
                            if (wt > 0 && !POSE_CONFIG.think.expressionsOnly) {
                                const tHandYaw = baseRightHandY - POSE_CONFIG.think.handYawInExtra; // more inward for chin touch
                                out = out * (1 - wt) + tHandYaw * wt;
                            }
                            rightHand.rotation.y = out;
                            if (applyLimbs && qRHand) {
                                const curQ = new window.THREE.Quaternion().setFromEuler(rightHand.rotation);
                                const blended = curQ.clone().slerp(qRHand, Math.min(1, wL));
                                rightHand.rotation.setFromQuaternion(blended);
                            }
                        }
                        if (spineBone) { spineBone.position.y = baseSpineY + breathe; } // Subtle spine bob for breathing

                        // Compute desired head yaw/pitch to look towards the drifting/mouse-driven look target
                        if (vrmCamera && (neckBone || headBone)) { // Ensure camera and bones exist
                            const camInv = new window.THREE.Matrix4().copy(vrmCamera.matrixWorld).invert(); // Inverse of camera world matrix
                            const tgtCam = new window.THREE.Vector3().copy(lookTarget.position).applyMatrix4(camInv); // Target position in camera space
                            const yaw = Math.atan2(tgtCam.x, tgtCam.z); // Yaw angle from camera X/Z
                            const pitch = Math.atan2(-tgtCam.y, tgtCam.z); // Pitch angle from camera Y/Z
                            const maxYaw = 0.35; // Maximum yaw in radians (~20 degrees)
                            const maxPitch = 0.25; // Maximum pitch in radians (~14 degrees)
                            const clampedYaw = Math.max(-maxYaw, Math.min(maxYaw, yaw)); // Clamp yaw to safe range
                            const clampedPitch = Math.max(-maxPitch, Math.min(maxPitch, pitch)); // Clamp pitch to safe range
                            const neckWeight = 0.4; // Proportion of rotation applied to neck
                            const headWeight = 0.6; // Proportion of rotation applied to head
                            const smoothing = 0.12; // Lerp factor for smooth motion
                            if (neckBone) { // If neck bone is available
                                const targetNeckY = baseNeckY + clampedYaw * neckWeight; // Desired neck yaw
                                const targetNeckX = baseNeckX + clampedPitch * neckWeight; // Desired neck pitch
                                neckBone.rotation.y += (targetNeckY - neckBone.rotation.y) * smoothing; // Smoothly apply neck yaw
                                neckBone.rotation.x += (targetNeckX - neckBone.rotation.x) * smoothing; // Smoothly apply neck pitch
                            } // End neck application
                            if (headBone) { // If head bone is available
                                const targetHeadY = baseHeadY + clampedYaw * headWeight; // Desired head yaw
                                const targetHeadX = baseHeadX + clampedPitch * headWeight; // Desired head pitch
                                headBone.rotation.y += (targetHeadY - headBone.rotation.y) * smoothing; // Smoothly apply head yaw
                                headBone.rotation.x += (targetHeadX - headBone.rotation.x) * smoothing; // Smoothly apply head pitch
                            } // End head application
                        } // End head rotation block
                } // end strict love pose else-branch

                        // When love pose is active and not speaking, hold a closed smile and love eyes (scaled by weight)
                        if (lovePoseWeight > 0.1 && !isSpeaking) {
                            try {
                                const smileVal = POSE_CONFIG.love.smileGain * Math.min(1, lovePoseWeight + POSE_CONFIG.love.smileBias) * 0.5; // Reduced to 50%
                                const loveEyesVal = POSE_CONFIG.love.loveEyesGain * Math.min(1, lovePoseWeight + POSE_CONFIG.love.loveEyesBias);
                                if (vrm.expressionManager) {
                                    // Set smile expressions
                                    const smileKeys = ['smile', 'happy', 'joy', 'fun'];
                                    for (const k of smileKeys) { try { vrm.expressionManager.setValue(k, smileVal); } catch (_) {} }
                                    // Keep vowels closed only when not speaking
                                    const vowels = ['aa','ih','ou','ee','oh'];
                                    for (const v of vowels) { try { vrm.expressionManager.setValue(v, 0.0); } catch (_) {} }
                                    // Set love eyes (relaxed expression creates soft half-closed eyes)
                                    try { vrm.expressionManager.setValue('relaxed', loveEyesVal); } catch (_) {} // VRM 1.0 standard relaxed key
                                    try { vrm.expressionManager.setValue('heart', loveEyesVal); } catch (_) {} // Optional custom heart eyes
                                    try { vrm.expressionManager.setValue('love', loveEyesVal); } catch (_) {} // Optional custom love eyes
                                    // Clear conflicting eye expressions
                                    const clearEyeKeys = ['neutral', 'look','lookLeft','lookRight'];
                                    for (const eKey of clearEyeKeys) { try { vrm.expressionManager.setValue(eKey, 0.0); } catch (_) {} }
                                }
                                if (vrm.blendShapeProxy) {
                                    // VRM 0.x: Set smile expressions (already reduced to 50% via smileVal)
                                    const smile0 = ['Smile','Joy','Fun','MouthSmile'];
                                    for (const k of smile0) { try { vrm.blendShapeProxy.setValue(k, smileVal); } catch (_) {} }
                                    const vowels0 = ['A','I','U','E','O'];
                                    for (const v of vowels0) { try { vrm.blendShapeProxy.setValue(v, 0.0); } catch (_) {} }
                                    // VRM 0.x: Set love eyes expressions
                                    try { vrm.blendShapeProxy.setValue('Relaxed', loveEyesVal); } catch (_) {} // VRM 0.x relaxed key
                                    try { vrm.blendShapeProxy.setValue('Heart', loveEyesVal); } catch (_) {} // Optional custom heart eyes
                                    try { vrm.blendShapeProxy.setValue('Love', loveEyesVal); } catch (_) {} // Optional custom love eyes
                                }
                                flushVrmExpressions(vrm);
                            } catch (_) {}
                        } else if (!isSpeaking && lovePoseWeight <= 0.1) {
                            // Fully release smile/eye shapes when pose finished
                            try {
                                if (vrm.expressionManager) {
                                    const smileKeys = ['smile', 'happy', 'joy', 'fun'];
                                    for (const k of smileKeys) { try { vrm.expressionManager.setValue(k, 0.0); } catch (_) {} }
                                    // Clear love eyes expressions
                                    try { vrm.expressionManager.setValue('relaxed', 0.0); } catch (_) {}
                                    try { vrm.expressionManager.setValue('heart', 0.0); } catch (_) {}
                                    try { vrm.expressionManager.setValue('love', 0.0); } catch (_) {}
                                }
                                if (vrm.blendShapeProxy) {
                                    const smile0 = ['Smile','Joy','Fun','MouthSmile'];
                                    for (const k of smile0) { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch (_) {} }
                                    // Clear love eyes expressions for VRM 0.x
                                    try { vrm.blendShapeProxy.setValue('Relaxed', 0.0); } catch (_) {}
                                    try { vrm.blendShapeProxy.setValue('Heart', 0.0); } catch (_) {}
                                    try { vrm.blendShapeProxy.setValue('Love', 0.0); } catch (_) {}
                                }
                                flushVrmExpressions(vrm);
                            } catch (_) {}
                        }

                        // Thinking pose facial cues when active and not speaking
                        if (thinkPoseWeight > 0.1 && !isSpeaking) {
                            try {
                                const oVal = Math.min(1, POSE_CONFIG.think.oMouthGain * thinkPoseWeight + POSE_CONFIG.think.oMouthBias) * 0.5; // Reduced to 50%
                                if (vrm.expressionManager) {
                                    // Prefer 'oh' vowel for O mouth
                                    try { vrm.expressionManager.setValue('oh', oVal); } catch(_){}
                                    // Raise brows if keys exist
                                    const browUpKeys = ['browUp','browUpLeft','browUpRight','surprised'];
                                    for (const b of browUpKeys) { try { vrm.expressionManager.setValue(b, POSE_CONFIG.think.browRaiseGain * thinkPoseWeight); } catch(_){} }
                                }
                                if (vrm.blendShapeProxy) {
                                    // VRM 0.x: use 'O' if available (already reduced to 50% via oVal)
                                    try { vrm.blendShapeProxy.setValue('O', oVal); } catch(_){}
                                    const brow0 = ['BrowUp','BrowUp_L','BrowUp_R','Surprised'];
                                    for (const b of brow0) { try { vrm.blendShapeProxy.setValue(b, POSE_CONFIG.think.browRaiseGain * thinkPoseWeight); } catch(_){} }
                                }
                                flushVrmExpressions(vrm);
                            } catch(_){}
                        } else if (!isSpeaking && thinkPoseWeight <= 0.1) {
                            // Release O mouth and brow keys when done
                            try {
                                if (vrm.expressionManager) {
                                    try { vrm.expressionManager.setValue('oh', 0.0); } catch(_){}
                                    ['browUp','browUpLeft','browUpRight','surprised'].forEach(k => { try { vrm.expressionManager.setValue(k, 0.0); } catch(_){} });
                                }
                                if (vrm.blendShapeProxy) {
                                    try { vrm.blendShapeProxy.setValue('O', 0.0); } catch(_){}
                                    ['BrowUp','BrowUp_L','BrowUp_R','Surprised'].forEach(k => { try { vrm.blendShapeProxy.setValue(k, 0.0); } catch(_){} });
                                }
                                flushVrmExpressions(vrm);
                            } catch(_){}
                        }
                    }
                    } // End else block for VRM 1.0 idle animation

                    // Update VRM after mixer/manual pose writes so look-at and spring physics use a stable delta.
                    if (vrmModel && typeof vrmModel.update === 'function') {
                        try { vrmModel.update(physicsDelta); } catch (_) {}
                    }
                    const runningVrmActionThisFrame = hasRunningVrmAction();
                    if (runningVrmActionThisFrame || vrmLastFrameHadRunningAction || vrmRestorePoseOnNextManualIdle || vrmPoseBlend) {
                        vrmLastPoseSnapshot = createVrmPoseSnapshot() || vrmLastPoseSnapshot;
                    }
                    vrmLastFrameHadRunningAction = runningVrmActionThisFrame;

                    if (vrmRenderer && vrmScene && vrmCamera) {
                        vrmRenderer.render(vrmScene, vrmCamera);
                    }
                }
                animate();

                // Start periodic blinking after VRM is ready
                const setBlink = (value) => { // Helper to set blink expression value
                    if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm)) return; // Skip stale blink callbacks
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blink', value); } } catch (_) {} // VRM 1.0 blink key
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blinkLeft', value); } } catch (_) {} // Optional left eye key
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blinkRight', value); } } catch (_) {} // Optional right eye key
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink', value); } } catch (_) {} // VRM 0.x combined blink
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink_L', value); } } catch (_) {} // VRM 0.x left blink
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink_R', value); } } catch (_) {} // VRM 0.x right blink
                    flushVrmExpressions(vrm);
                }; // End setBlink helper

                const scheduleBlink = () => { // Function to schedule the next blink
                    if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm)) return; // Skip if VRM has been cleaned up or swapped
                    const waitMs = 2200 + Math.random() * 2600; // Random delay between blinks (2.2s - 4.8s)
                    vrmBlinkTimeout = setTimeout(() => { // Set timer for blink
                        vrmBlinkTimeout = null;
                        if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm)) return; // Skip stale blink close/open cycle
                        setBlink(1.0); // Close eyelids
                        vrmBlinkCloseTimeout = setTimeout(() => { // Short delay to reopen eyes
                            vrmBlinkCloseTimeout = null;
                            if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm)) return; // Skip stale blink reopen
                            setBlink(0.0); // Open eyelids
                            scheduleBlink(); // Schedule subsequent blink
                        }, 120 + Math.random() * 80); // Keep eyes closed 120-200ms
                    }, waitMs); // After the random wait
                }; // End scheduleBlink
                scheduleBlink(); // Kick off blinking loop

                console.log('VRM model loaded successfully');

            } catch (error) {
                if (requestedGeneration === vrmLoadGeneration) {
                    if (vrmModel !== vrm) {
                        disposeStaleVrmLoadResources(scene, renderer, mixer, vrm, gltf?.scene);
                    }
                    console.error('Failed to load VRM model:', error);
                }
            }
        }

        function updateVRMTransform() {
            if (!vrmModel || !vrmModel.scene) return;

            const currentPositions = vrmPositions[currentVRMModelPath] || { scale: 1.0, positionX: 0, positionY: 0, rotation: 0 };

            // Apply scale
            vrmModel.scene.scale.setScalar(currentPositions.scale);

            // Apply position
            vrmModel.scene.position.set(currentPositions.positionX, currentPositions.positionY, 0);

            // Apply rotation
            vrmModel.scene.rotation.y = (currentPositions.rotation * Math.PI) / 180;

            // Persist the positions
            vrmPositions[currentVRMModelPath] = currentPositions;
            try { localStorage.setItem(VRM_POSITIONS_KEY, JSON.stringify(vrmPositions)); } catch {}
            // If renderer exists, render a frame to reflect changes immediately
            if (vrmRenderer && vrmScene && vrmCamera) {
                try { vrmRenderer.render(vrmScene, vrmCamera); } catch (_) {}
            }
        }

        function animateVRMLipSync(value) {
            // Ensure VRM model exists and we have a target key
            if (!vrmModel || !vrmLipSyncMorphTarget) return;

            // Normalize key; allow both VRM 0.x ('A') and VRM 1.0 ('aa') conventions
            let key = vrmLipSyncMorphTarget;
            if (typeof key !== 'string') {
                key = (key && (key.presetName || key.name)) || '';
            }
            if (!key) return;

            const clamped = Math.max(0, Math.min(1, value));

            // Try VRM 1.0 first if available
            try {
                if (vrmModel.expressionManager) {
                    // For VRM 1.0, vowel keys are typically lowercase: 'aa','ih','ou','ee','oh'
                    const exprKey = key.toLowerCase() === 'a' ? 'aa' : key.toLowerCase();
                    vrmModel.expressionManager.setValue(exprKey, clamped);
                    flushVrmExpressions(vrmModel);
                    return;
                }
            } catch (e) {
                // fall through to VRM 0.x
            }

            // Fallback: VRM 0.x blendShapeProxy uses presets like 'A','I','U','E','O' or custom names
            try {
                if (vrmModel.blendShapeProxy) {
                    const proxyKey = key.length === 2 && key === key.toLowerCase() ? key.toUpperCase().charAt(0) : key; // map 'aa'->'A'
                    vrmModel.blendShapeProxy.setValue(proxyKey, clamped);
                    flushVrmExpressions(vrmModel);
                }
            } catch (error) {
                console.warn('Error animating VRM lip sync:', error);
            }
        }

        async function switchToLive2D() {
            // Hide VRM container
            const vrmContainer = document.getElementById('vrm-container');
            if (vrmContainer) vrmContainer.style.display = 'none';

            // Show Live2D container
            const live2dContainer = document.getElementById('live2d-container');
            if (live2dContainer) live2dContainer.style.display = 'block';

            // Cleanup VRM if active
            cleanupVRM();

            // Initialize Live2D if needed
            if (!live2dModel || live2dActiveModelPath !== modelPath) {
                await initLive2D();
            }

            // Persist avatar mode preference
            try { localStorage.setItem('avatarMode', 'live2d'); } catch {}
        }

        async function switchToVRM() {
            // Hide Live2D container
            const live2dContainer = document.getElementById('live2d-container');
            if (live2dContainer) live2dContainer.style.display = 'none';

            // Show VRM container
            const vrmContainer = document.getElementById('vrm-container');
            if (vrmContainer) vrmContainer.style.display = 'block';

            // Cleanup Live2D if active
            cleanupLive2D();

            // Initialize VRM if needed
            if (!vrmModel || vrmActiveModelPath !== currentVRMModelPath) {
                if (vrmModel) {
                    cleanupVRM();
                }
                await initVRM();
            }

            // Persist avatar mode preference
            try { localStorage.setItem('avatarMode', 'vrm'); } catch {}
        }

        // Add this after your existing button event listeners
        document.getElementById('paste-btn').addEventListener('click', async () => {
            try {
                const items = await navigator.clipboard.read();
                const previewContainer = document.getElementById('clipboard-preview');
                const previewImage = document.getElementById('clipboard-image');
                const previewText = document.getElementById('clipboard-text');

                // Reset previous clipboard data
                clipboardData = null;
                clipboardType = null;
                previewImage.style.display = 'none';
                previewText.style.display = 'none';
                
                for (const item of items) {
                    // Handle images
                    if (item.types.includes('image/png') || item.types.includes('image/jpeg')) {
                        const blob = await item.getType(item.types.find(type => type.startsWith('image/')));
                        const imageUrl = URL.createObjectURL(blob);
                        
                        clipboardData = blob;
                        clipboardType = 'image';
                        
                        previewImage.src = imageUrl;
                        previewImage.style.display = 'block';
                        previewContainer.style.display = 'block';
                        break;
                    }
                    // Handle text
                    else if (item.types.includes('text/plain')) {
                        const text = await (await item.getType('text/plain')).text();
                        
                        clipboardData = text;
                        clipboardType = 'text';
                        
                        previewText.textContent = text;
                        previewText.style.display = 'block';
                        previewContainer.style.display = 'block';
                        break;
                    }
                }
            } catch (err) {
                console.error('Failed to read clipboard:', err);
                // Fallback to older clipboard API for text
                try {
                    const text = await navigator.clipboard.readText();
                    clipboardData = text;
                    clipboardType = 'text';
                    
                    const previewText = document.getElementById('clipboard-text');
                    previewText.textContent = text;
                    previewText.style.display = 'block';
                    document.getElementById('clipboard-preview').style.display = 'block';
                } catch (err) {
                    alert('Unable to access clipboard: ' + err.message);
                }
            }
        });

        // Add this new helper function
        function clearClipboardPreview() {
            // Clear the clipboard data variables
            clipboardData = null;
            clipboardType = null;
            
            // Clear the preview elements
            const previewContainer = document.getElementById('clipboard-preview');
            const previewImage = document.getElementById('clipboard-image');
            const previewText = document.getElementById('clipboard-text');
            const statusElement = document.getElementById('clipboard-status');
            
            previewContainer.style.display = 'none';
            previewImage.style.display = 'none';
            previewImage.src = '';
            previewText.style.display = 'none';
            previewText.textContent = '';
            if (statusElement) {
                statusElement.textContent = '';
            }
        }

        // Automatic clipboard monitoring function
        async function monitorClipboard() {
            // Only monitor if Clipboard Vision Mode is enabled
            if (!clipboardVisionEnabled) {
                return;
            }

            try {
                // Attempt to read clipboard contents
                const items = await navigator.clipboard.read();
                const previewContainer = document.getElementById('clipboard-preview');
                const previewImage = document.getElementById('clipboard-image');
                const previewText = document.getElementById('clipboard-text');

                // Check each clipboard item
                for (const item of items) {
                    // Handle images (PNG, JPEG)
                    if (item.types.includes('image/png') || item.types.includes('image/jpeg')) {
                        const blob = await item.getType(item.types.find(type => type.startsWith('image/')));
                        const imageUrl = URL.createObjectURL(blob);
                        
                        // Only update if this is new content (avoid unnecessary updates)
                        if (clipboardType !== 'image' || clipboardData !== blob) {
                            clipboardData = blob;
                            clipboardType = 'image';
                            
                            previewImage.src = imageUrl;
                            previewImage.style.display = 'block';
                            previewText.style.display = 'none';
                            previewContainer.style.display = 'block';
                            
                            // Show visual feedback with timestamp
                            const statusElement = document.getElementById('clipboard-status');
                            if (statusElement) {
                                const timestamp = new Date().toLocaleTimeString();
                                statusElement.textContent = `✓ Clipboard image detected automatically at ${timestamp} - will be included with next message`;
                                statusElement.style.color = '#4CAF50'; // Green color for success
                            }
                            
                            console.log('Clipboard image detected and ready');
                        }
                        return; // Exit after processing first image
                    }
                    // Handle text
                    else if (item.types.includes('text/plain')) {
                        const text = await (await item.getType('text/plain')).text();
                        
                        // Only update if this is new content (avoid unnecessary updates)
                        if (clipboardType !== 'text' || clipboardData !== text) {
                            clipboardData = text;
                            clipboardType = 'text';
                            
                            previewText.textContent = text;
                            previewText.style.display = 'block';
                            previewImage.style.display = 'none';
                            previewContainer.style.display = 'block';
                            
                            // Show visual feedback with timestamp
                            const statusElement = document.getElementById('clipboard-status');
                            if (statusElement) {
                                const timestamp = new Date().toLocaleTimeString();
                                statusElement.textContent = `✓ Clipboard text detected automatically at ${timestamp} - will be included with next message`;
                                statusElement.style.color = '#4CAF50'; // Green color for success
                            }
                            
                            console.log('Clipboard text detected and ready');
                        }
                        return; // Exit after processing first text
                    }
                }
            } catch (err) {
                // Handle permission errors and other clipboard access issues gracefully
                if (err.name === 'NotAllowedError' || err.name === 'SecurityError') {
                    // Permission denied - only log once to avoid spam
                    if (!clipboardMonitorInterval || clipboardData === null) {
                        console.warn('Clipboard access denied. Please grant clipboard permissions.');
                    }
                } else if (err.name !== 'NotFoundError') {
                    // NotFoundError is normal when clipboard is empty, don't log it
                    // But log other errors
                    console.warn('Error reading clipboard:', err.message);
                }
            }
        }

        // Start clipboard monitoring when Clipboard Vision Mode is enabled
        function startClipboardMonitoring() {
            // Clear any existing interval first
            if (clipboardMonitorInterval) {
                clearInterval(clipboardMonitorInterval);
            }
            
            // Remove any existing focus event listener to prevent duplicates
            // This ensures we don't accumulate multiple listeners if startClipboardMonitoring is called multiple times
            window.removeEventListener('focus', monitorClipboard);
            
            // Check clipboard immediately
            monitorClipboard();
            
            // Set up periodic monitoring (every 1.5 seconds)
            clipboardMonitorInterval = setInterval(monitorClipboard, 1500);
            
            // Also check clipboard on window focus (useful when user switches back to the tab)
            window.addEventListener('focus', monitorClipboard);
            
            console.log('Clipboard monitoring started');
        }

        // Stop clipboard monitoring when Clipboard Vision Mode is disabled
        function stopClipboardMonitoring() {
            // Clear the monitoring interval
            if (clipboardMonitorInterval) {
                clearInterval(clipboardMonitorInterval);
                clipboardMonitorInterval = null;
            }
            
            // Remove focus event listener
            window.removeEventListener('focus', monitorClipboard);
            
            console.log('Clipboard monitoring stopped');
        }

        // Update the initWebcam function
        async function initWebcam() {
            if (!webcamEnabled) return;
            
            try {
                const video = document.getElementById('webcam-video');
                const preview = document.getElementById('webcam-preview');
                webcamStream = await navigator.mediaDevices.getUserMedia({ 
                    video: {
                        width: { ideal: 640 },
                        height: { ideal: 480 }
                    }
                });
                
                // Set both video elements to use the same stream
                video.srcObject = webcamStream;
                preview.srcObject = webcamStream;
                
                await video.play();
                await preview.play();
                
                console.log('Webcam initialized successfully');
                startPeriodicCapture();
            } catch (error) {
                console.error('Error accessing webcam:', error);
                // If webcam fails to initialize, turn off webcam mode
                webcamToggle.checked = false;
                webcamEnabled = false;
                if (currentModelSpan) {
                    currentModelSpan.textContent = 'Current Model: qwen2.5-coder-3b-instruct';
                }
                document.getElementById('webcam-preview-container').style.display = 'none';
                alert('Failed to initialize webcam. Webcam mode has been disabled.');
            }
        }

        // Function to capture and process webcam image
        async function captureAndProcessWebcam() {
            if (isProcessing || !webcamStream) return;

            const video = document.createElement('video');
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            
            try {
                video.srcObject = webcamStream;
                await video.play();

                // Set canvas size to match video dimensions
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                
                // Draw current video frame to canvas
                context.drawImage(video, 0, 0);
                
                // Convert canvas to blob
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg'));
                
                // Process the image with the model
                isProcessing = true;
                await processWebcamImage(blob);
                
            } catch (error) {
                console.error('Error capturing webcam image:', error);
            } finally {
                video.srcObject = null;
                isProcessing = false;
            }
        }

        // Function to process webcam image with OpenAI
        async function processWebcamImage(imageBlob) {
            const apiKey = apiKeyInput.value.trim();
            const endpoint = endpointInput.value || 'http://localhost:1234/v1/chat/completions';
            const model = getCurrentModel(); // Dynamically get the current model

            try {
                startVrmProcessingThinkingLoop();
                const base64Image = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(imageBlob);
                });

                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        model: model,
                        message:
                                {
                                "role": "user",
                                "content": promptText,
                                "images": [`data:image/jpeg;base64,${base64Image}`],
                                "temperature": 0.7,
                                "max_tokens": 4096
                            }
                    })
                });

                const data = await response.json();
                if (data.choices && data.choices.length > 0) {
                    const message = extractChoiceVisibleText(data.choices[0] || {});
                    if (!message) {
                        throw new Error('Model returned no visible text for webcam analysis.');
                    }
                    
                    // Update response output
                    responseOutput.value = message;
                    addMessageToHistory('assistant', message); // Add to message history
                    
                    // Trigger text-to-speech
                    textToSpeech(message);
                    
                    // Extract emotion from message and update expression
                    const emotions = ['happy', 'sad', 'surprised', 'neutral', 'thinking'];
                    const emotion = emotions.find(e => message.toLowerCase().includes(e)) || 'neutral';
                    updateLive2DExpression(emotion);
                    
                    // Add to chat history
                    chatHistory.push({ role: 'assistant', content: message });
                    
                    // Automatically extract memories from conversation (async, non-blocking)
                    extractMemoriesFromConversation().catch(err => {
                        console.warn('Memory extraction failed:', err);
                    });
                }
            } catch (error) {
                console.error('Error processing webcam image:', error);
                status.textContent = "Failed to process webcam image. Please try again.";
            } finally {
                if (!vrmAwaitingTtsStart) {
                    stopVrmProcessingThinkingLoop({ resumeIdle: true });
                }
            }
        }

        // Function to update Live2D expression
        function updateLive2DExpression(emotion) {
            if (!live2dModel) return;
            
            let expressionFile = null;
            
            // Map emotions to available expressions
            switch(emotion) {
                case 'happy':
                    expressionFile = 'Love eye.exp3.json';
                    break;
                case 'sad':
                    expressionFile = 'cry.exp3.json';
                    break;
                case 'surprised':
                    expressionFile = 'black face.exp3.json';
                    break;
                case 'thinking':
                    expressionFile = 'Milk Tea.exp3.json';
                    break;
            }
            
            const resetLive2DExpression = () => {
                try {
                    const resetResult = live2dModel.expression(null);
                    if (resetResult && typeof resetResult.catch === 'function') {
                        resetResult.catch(() => {});
                    }
                } catch (_) {}
            };

            try {
                const expressionResult = expressionFile
                    ? live2dModel.expression(expressionFile)
                    : live2dModel.expression(null);
                if (expressionResult && typeof expressionResult.catch === 'function') {
                    expressionResult.catch((error) => {
                        console.warn('Could not apply Live2D expression:', error);
                        resetLive2DExpression();
                    });
                }
            } catch (error) {
                console.warn('Could not apply Live2D expression:', error);
                resetLive2DExpression();
            }
        }

        // Function to start periodic capture
        function startPeriodicCapture() {
            if (webcamInterval) {
                clearInterval(webcamInterval);
            }
            webcamInterval = setInterval(() => {
                // Only process if not already processing and not speaking
                if (!isProcessing && !speechSynthesis.speaking && chatHistory.length === 0) {
                    captureAndProcessWebcam();
                }
            }, 30000); // 30 seconds
        }

        // Add cleanup function for when the page is closed
        window.addEventListener('beforeunload', () => {
            if (webcamInterval) {
                clearInterval(webcamInterval);
            }
            if (webcamStream) {
                webcamStream.getTracks().forEach(track => track.stop());
            }
        });

        // Add this function to initialize expressions when the model loads
        async function initializeLive2DExpressions(model) {
            try {
                const expressions = await model.expressions;
                if (Array.isArray(expressions) && expressions.length > 0) {
                    console.log('Available expressions:', expressions);
                }
                try {
                    await model.expression(null);
                } catch (_) {
                    // Some models do not expose expressions or reject reset calls; that is non-fatal.
                }
            } catch (error) {
                console.error('Error initializing expressions:', error);
            }
        }

        // Add this new function to handle direct LLM queries
        async function handleLLMQuery({ query }, context) {
            try {
                const endpoint = endpointInput.value;
                const apiKey = apiKeyInput.value.trim();
                const toolingBundle = await buildToolingBundle();
                const tools = toolingBundle.tools;

                // Format previous results in a clear, structured way
                let enhancedQuery = query;
                if (context.previousResults.length > 0) {
                    const contextString = context.previousResults
                        .map((r, i) => {
                            if (r.task.toLowerCase().includes('calculate')) {
                                const match = r.result.message.match(/=\s*(-?\d+\.?\d*)/);
                                return `Step ${i + 1}: ${r.task} → Result: ${match ? match[1] : r.result.message}`;
                            }
                            return `Step ${i + 1}: ${r.task} → Result: ${r.result.message}`;
                        })
                        .join('\n');

                    enhancedQuery = `Given the following previous steps and their results:\n\n${contextString}\n\nNow, ${query}`;
                    
                    if (query.toLowerCase().includes('that') || query.toLowerCase().includes('it') || query.toLowerCase().includes('the result')) {
                        enhancedQuery += "\n\nPlease use the previous results to provide your answer.";
                    }
                }

                console.log('Enhanced query with context:', enhancedQuery);

                // Build initial messages for this sub-request
                const subMessages = [
                    {
                        role: 'system',
                        content: 'You are a helpful assistant. When responding to queries that reference previous results, use that context to provide accurate answers. If the query references calculations or numeric results, incorporate those numbers in your response.'
                    },
                    {
                        role: 'user',
                        content: enhancedQuery
                    }
                ];

                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify(buildCompatibleChatBody(endpoint, {
                        model: getCurrentModel(),
                        messages: subMessages,
                        temperature: 0.7,
                        // Provide tools so the model can decide to call them here as well
                        tools: tools,
                        tool_choice: 'auto'
                    }))
                });

                const data = await response.json();
                if (data.choices && data.choices.length > 0) {
                    const msg = data.choices[0].message;
                    // Handle potential tool calls using LM Studio/OpenAI format
                    if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
                        try {
                            let lastToolSummary = '';
                            // Add assistant tool calls
                            subMessages.push(buildAssistantHistoryMessage(msg));
                            // Execute and add tool results
                            for (const tc of msg.tool_calls) {
                                const toolResult = await executeToolCall(tc, context);
                                const toolResultContent = formatToolResultForModel(toolResult);
                                lastToolSummary = extractToolResultSummary(toolResult);
                                
                                subMessages.push({
                                    role: 'tool',
                                    content: toolResultContent,
                                    tool_call_id: tc.id
                                });
                            }
                            // Finalize with follow-up calls until no more native/XML tool calls are returned.
                            let finalMessage = null;
                            let loopCount = 0;
                            while (loopCount < 4) {
                                const follow = await fetch(endpoint, {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'Authorization': `Bearer ${apiKey}`
                                    },
                                    body: JSON.stringify(buildCompatibleChatBody(endpoint, {
                                        model: getCurrentModel(),
                                        messages: subMessages,
                                        temperature: 0.7,
                                        tools: tools,
                                        tool_choice: 'auto'
                                    }))
                                });
                                const followJson = await follow.json();
                                finalMessage = followJson?.choices?.[0]?.message || {};
                                const nativeCalls = Array.isArray(finalMessage.tool_calls) ? finalMessage.tool_calls : [];
                                const finalRawText = coerceMessageText(finalMessage.content || '').trim();
                                const finalText = stripThinkTags(finalRawText).trim();
                                const xmlCall = (!nativeCalls.length && finalRawText) ? parseToolResponse(finalRawText) : null;

                                if (!nativeCalls.length && !xmlCall) {
                                    return { success: true, message: finalText || lastToolSummary };
                                }

                                if (nativeCalls.length) {
                                    subMessages.push(buildAssistantHistoryMessage(finalMessage));
                                    for (const tc of nativeCalls) {
                                        const toolResult = await executeToolCall(tc, context);
                                        const toolResultContent = formatToolResultForModel(toolResult);
                                        lastToolSummary = extractToolResultSummary(toolResult);
                                        subMessages.push({
                                            role: 'tool',
                                            content: toolResultContent,
                                            tool_call_id: tc.id
                                        });
                                    }
                                } else if (xmlCall) {
                                    const xmlResult = await executeToolCall(xmlCall, context);
                                    const xmlResultContent = formatToolResultForModel(xmlResult);
                                    lastToolSummary = extractToolResultSummary(xmlResult);
                                    subMessages.push(buildAssistantHistoryMessage(finalMessage));
                                    subMessages.push({ role: 'user', content: `Tool result: ${xmlResultContent}` });
                                }
                                loopCount += 1;
                            }
                            return { success: true, message: lastToolSummary };
                        } catch (innerErr) {
                            console.error('Error handling tool calls in handleLLMQuery:', innerErr);
                            // Fall back to plain content if present
                        }
                    }

                    const rawPlain = coerceMessageText(msg.content || '').trim();
                    const plain = stripThinkTags(rawPlain).trim();
                    const xmlToolCall = rawPlain ? parseToolResponse(rawPlain) : null;
                    if (xmlToolCall) {
                        const xmlResult = await executeToolCall(xmlToolCall, context);
                        return {
                            success: true,
                            message: extractToolResultSummary(xmlResult)
                        };
                    }
                    console.log('LLM Response:', plain);
                    return {
                        success: true,
                        message: plain
                    };
                } else {
                    throw new Error('No response from LLM');
                }
            } catch (error) {
                console.error('LLM query error:', error);
                return {
                    success: false,
                    message: `Error getting response: ${error.message}`
                };
            }
        }



        async function handleWeatherInfo({ location, requestType, detail }) {
            try {
                const selectedDetail = (requestType || detail || 'summary').toString().trim().toLowerCase();
                const params = new URLSearchParams();
                if (location && location.trim()) params.set('location', location.trim());
                params.set('detail', selectedDetail || 'summary');
                const headers = {};
                if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/weather?${params.toString()}`, {
                    method: 'GET',
                    headers
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    return { success: false, message: err.detail || `Failed to fetch weather (${response.status})` };
                }

                const data = await response.json();
                return {
                    success: true,
                    message: data.summary || `Weather data retrieved for ${data.resolved_location || (location || 'requested location')}.`,
                    data
                };
            } catch (error) {
                console.error('Weather tool error:', error);
                return { success: false, message: `Error fetching weather: ${error.message}` };
            }
        }

        // Add these variables at the top of your script section
        let isMuted = false;
        const muteToggle = document.getElementById('mute-toggle');

        // Add this event listener after your other initialization code
        muteToggle.addEventListener('change', function() {
            isMuted = this.checked;
            if (isMuted) {
                speechSynthesis.cancel(); // Stop any ongoing speech
            }
        });

        async function handleNews({ searchTerm, filename }) {
            try {
                const url = `${PROXY_BASE_URL}/v1/proxy/news?query=${encodeURIComponent(searchTerm)}`;
                const response = await fetch(url);
                
                if (!response.ok) {
                    const errorPayload = await response.json().catch(() => ({}));
                    throw new Error(errorPayload.detail || `Failed to fetch news: ${response.statusText}`);
                }
                
                const data = await response.json();
                const articles = data.articles || [];
                
                if (articles.length === 0) {
                    return {
                        success: false,
                        message: `No articles found for search term "${searchTerm}"`
                    };
                }
                
                // Create CSV content
                const csvContent = ['Title,URL\n'];
                articles.forEach(article => {
                    const title = article.title.replace(/,/g, ' ');  // Remove commas from titles
                    csvContent.push(`"${title}","${article.url}"\n`);
                });
                
                // Create a Blob with the CSV content
                const blob = new Blob(csvContent, { type: 'text/csv' });
                
                // Create a download link and trigger it
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(a.href);
                
                return {
                    success: true,
                    message: `Successfully saved ${articles.length} news articles to ${filename}`
                };
                
            } catch (error) {
                console.error('News fetch error:', error);
                return {
                    success: false,
                    message: `Error fetching news: ${error.message}. Configure NEWS_API_KEY on the CATBot proxy.`
                };
            }
        }

        // Extract images from a PDF page using PDF.js
        async function extractImagesFromPage(page, operators, pageIndex) {
            const images = [];
            const viewport = page.getViewport({ scale: 1.0 });
            
            try {
                // Look for image operations in the PDF
                const ops = operators.fnArray;
                const args = operators.argsArray;
                
                for (let i = 0; i < ops.length; i++) {
                    // Check for image painting operations (Op.paintImageXObject)
                    if (ops[i] === window.pdfjsLib.OPS.paintImageXObject) {
                        try {
                            const objId = args[i][0];
                            
                            // Get the image object
                            const imgData = await page.objs.get(objId);
                            
                            if (imgData && (imgData.data || imgData.bitmap)) {
                                // Create canvas to extract image data
                                const canvas = document.createElement('canvas');
                                const ctx = canvas.getContext('2d');
                                
                                if (imgData.bitmap) {
                                    // Handle ImageBitmap
                                    canvas.width = imgData.bitmap.width;
                                    canvas.height = imgData.bitmap.height;
                                    ctx.drawImage(imgData.bitmap, 0, 0);
                                } else if (imgData.data) {
                                    // Handle raw image data
                                    canvas.width = imgData.width || 100;
                                    canvas.height = imgData.height || 100;
                                    
                                    const imageData = ctx.createImageData(canvas.width, canvas.height);
                                    const data = imgData.data;
                                    
                                    // Convert data to RGBA if needed
                                    for (let j = 0; j < data.length; j += 3) {
                                        const idx = (j / 3) * 4;
                                        if (idx + 3 < imageData.data.length) {
                                            imageData.data[idx] = data[j];     // R
                                            imageData.data[idx + 1] = data[j + 1]; // G
                                            imageData.data[idx + 2] = data[j + 2]; // B
                                            imageData.data[idx + 3] = 255;    // A
                                        }
                                    }
                                    ctx.putImageData(imageData, 0, 0);
                                }
                                
                                // Convert to data URL
                                const dataUrl = canvas.toDataURL('image/png');
                                
                                // Only include reasonably sized images
                                if (canvas.width >= 50 && canvas.height >= 50) {
                                    images.push({
                                        id: `img_page${pageIndex}_${i}`,
                                        dataUrl: dataUrl,
                                        width: canvas.width,
                                        height: canvas.height,
                                        pageNumber: pageIndex,
                                        description: `Image from page ${pageIndex}`
                                    });
                                    
                                    console.log(`Extracted image ${images.length} from page ${pageIndex} (${canvas.width}x${canvas.height})`);
                                }
                            }
                        } catch (imgError) {
                            console.warn(`Could not extract image ${i} from page ${pageIndex}:`, imgError);
                        }
                    }
                }
            } catch (error) {
                console.warn(`Error processing page ${pageIndex} for images:`, error);
            }
            
            return images;
        }

        // Converts a PDF or Markdown source into an intelligent PowerPoint presentation.
        // Enhanced approach:
        // 1) Load the source document and extract text content
        // 2) For PDFs, also extract images with PDF.js
        // 3) Send text to OpenAI LLM for intelligent summarization and structuring
        // 4) Create structured slides based on LLM output (intro, key points, details, conclusion)
        // 5) Save the enhanced PPTX file
        async function handlePdfToPowerPoint({ pdfUrl, source, sourceUrl, sourceType, sourceFile = null, promptUpload = false, title, author = "", maxSlides = 15, filename }) {
            let sourceLabel = 'source';
            try {
                if (!window.PptxGenJS) {
                    throw new Error('PptxGenJS not loaded');
                }
                let fullText = '';
                let extractedImages = [];
                const legacyPdfSource = !sourceUrl && !!pdfUrl;
                let resolvedSource = sourceFile || source || sourceUrl || pdfUrl;

                if (!resolvedSource) {
                    const file = await promptForLocalPdf();
                    if (!file) {
                        return { success: false, message: 'No source file selected.' };
                    }
                    resolvedSource = file;
                }

                const normalizedSource = normalizePresentationSourceInput(
                    resolvedSource,
                    sourceType || (legacyPdfSource ? 'pdf' : '')
                );
                const resolvedSourceType = normalizedSource.sourceType;
                sourceLabel = resolvedSourceType === 'markdown' ? 'Markdown' : 'PDF';

                if (resolvedSourceType === 'pdf') {
                    if (!window.pdfjsLib) {
                        throw new Error('PDF.js not loaded');
                    }
                    if (window.pdfjsLib.GlobalWorkerOptions) {
                        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
                    }

                    const resolvedPdfSource = normalizedSource.sourceBlob
                        ? await readFileAsDataUrl(normalizedSource.sourceBlob)
                        : await resolvePdfInputToDocumentSource(normalizedSource.locator);

                    const loadingTask = window.pdfjsLib.getDocument({ url: resolvedPdfSource, withCredentials: false });
                    const pdf = await loadingTask.promise;

                    for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex++) {
                        const page = await pdf.getPage(pageIndex);

                        const textContent = await page.getTextContent();
                        const pageText = textContent.items.map(it => it.str).join(' ').replace(/\s+/g, ' ').trim();
                        fullText += pageText + ' ';

                        try {
                            const operators = await page.getOperatorList();
                            const pageImages = await extractImagesFromPage(page, operators, pageIndex);
                            extractedImages = extractedImages.concat(pageImages);
                        } catch (imageError) {
                            console.warn(`Could not extract images from page ${pageIndex}:`, imageError);
                        }
                    }

                    fullText = fullText.trim().replace(/\s+/g, ' ');

                    if (!fullText || fullText.length < 50) {
                        throw new Error('Could not extract sufficient text content from PDF');
                    }

                    console.log(`Extracted ${extractedImages.length} images from PDF`);
                } else {
                    fullText = normalizedSource.inlineText != null
                        ? normalizedSource.inlineText
                        : normalizedSource.sourceBlob
                            ? await readFileAsText(normalizedSource.sourceBlob)
                            : await resolveMarkdownInputToTextSource(normalizedSource.locator);
                    fullText = normalizeMarkdownForPresentation(fullText);

                    if (!fullText || fullText.length < 50) {
                        throw new Error('Could not extract sufficient text content from Markdown source');
                    }

                    console.log(`Loaded ${fullText.length} characters from Markdown source`);
                }

                // Determine which model to use for the presentation generation
                const modelUsed = extractedImages.length > 0 ? 
                    (visionModelDropdown.value || visionModel || 'qwen/qwen2.5-vl-7b') : 
                    getCurrentModel();

                // Process images in batches to avoid overwhelming local models
                let imageAnalysis = [];
                if (extractedImages.length > 0) {
                    // Limit image processing if there are too many to avoid excessive processing time
                    const imagesToProcess = extractedImages.length > 150 ? 
                        extractedImages.filter((img, index) => index % 2 === 0) : // Process every other image if > 150
                        extractedImages;
                    
                    console.log(`Processing ${imagesToProcess.length} of ${extractedImages.length} images in batches to avoid overwhelming local models...`);
                    imageAnalysis = await processImagesInBatches(imagesToProcess, modelUsed);
                }

                // Use OpenAI to intelligently structure the content including image placement
                const structuredContent = await generateStructuredPresentation(
                    fullText,
                    title,
                    maxSlides,
                    extractedImages,
                    imageAnalysis,
                    resolvedSourceType
                );
                
                if (!structuredContent) {
                    throw new Error(`Failed to generate structured content from ${sourceLabel}`);
                }

                // Helper function to find image by ID
                const findImageById = (imageId) => {
                    if (!imageId) return null;
                    const found = extractedImages.find(img => img.id === imageId);
                    console.log(`Looking for image ${imageId}:`, found ? 'FOUND' : 'NOT FOUND');
                    return found;
                };

                // Create PowerPoint with structured content
                const pptx = new window.PptxGenJS();
                pptx.layout = 'LAYOUT_16x9';

                // Title slide
                {
                    const slide = pptx.addSlide();
                    slide.addText(title, { x: 0.5, y: 1.2, w: 9, h: 1, fontSize: 36, bold: true });
                    if (author) {
                        slide.addText(author, { x: 0.5, y: 2.1, w: 9, h: 0.6, fontSize: 18, color: '666666' });
                    }
                    // Add a subtitle if available
                    if (structuredContent.subtitle) {
                        slide.addText(structuredContent.subtitle, { 
                            x: 0.5, y: 2.8, w: 9, h: 0.5, fontSize: 16, color: '888888', italic: true 
                        });
                    }
                }

                // Introduction slide
                if (structuredContent.introduction) {
                    const slide = pptx.addSlide();
                    slide.addText('Introduction', { x: 0.5, y: 0.5, w: 9, h: 0.6, fontSize: 28, bold: true, color: '2B5AA0' });
                    
                    // Check if there's an intro image
                    const introImage = structuredContent.introImage ? findImageById(structuredContent.introImage) : null;
                    console.log(`Introduction slide - Image requested: ${structuredContent.introImage}, Found: ${introImage ? 'YES' : 'NO'}`);
                    
                    if (introImage) {
                        // Layout with image on the right
                        slide.addText(structuredContent.introduction, {
                            x: 0.5,
                            y: 1.3,
                            w: 5.5,
                            h: 4.0,
                            fontSize: 16,
                            lineSpacing: 28
                        });
                        // Add image on the right
                        slide.addImage({ 
                            data: introImage.dataUrl, 
                            x: 6.2, 
                            y: 1.0, 
                            w: 3.0, 
                            h: 4.5 
                        });
                    } else {
                        // Full width text without image
                        slide.addText(structuredContent.introduction, {
                            x: 0.5,
                            y: 1.3,
                            w: 9,
                            h: 4.0,
                            fontSize: 16,
                            lineSpacing: 28
                        });
                    }
                }

                // Content slides
                if (structuredContent.slides && structuredContent.slides.length > 0) {
                    for (let i = 0; i < structuredContent.slides.length; i++) {
                        const slideContent = structuredContent.slides[i];
                        const slide = pptx.addSlide();
                        
                        // Slide title
                        slide.addText(slideContent.title, { 
                            x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 24, bold: true, color: '2B5AA0' 
                        });
                        
                        // Check if there's an image for this slide
                        const slideImage = slideContent.image ? findImageById(slideContent.image) : null;
                        console.log(`Slide ${i + 1} - Image requested: ${slideContent.image}, Found: ${slideImage ? 'YES' : 'NO'}`);
                        
                        if (slideImage) {
                            console.log(`Adding image ${slideContent.image} to slide ${i + 1}: "${slideContent.title}"`);
                            
                            // Layout with image on the right
                            let textY = 0.9;
                            
                            // Key point (main concept)
                            slide.addText(`Key Point: ${slideContent.keyPoint}`, {
                                x: 0.5,
                                y: textY,
                                w: 5.5,
                                h: 0.4,
                                fontSize: 16,
                                bold: true,
                                color: '333333'
                            });
                            textY += 0.5;
                            
                            // Explanation
                            if (slideContent.explanation) {
                                slide.addText(slideContent.explanation, {
                                    x: 0.5,
                                    y: textY,
                                    w: 5.5,
                                    h: 1.2,
                                    fontSize: 14,
                                    lineSpacing: 20
                                });
                                textY += 1.3;
                            }
                            
                            // Supporting details as bullets
                            if (slideContent.details && slideContent.details.length > 0) {
                                const bulletText = slideContent.details.map(detail => `• ${detail}`).join('\n');
                                slide.addText(bulletText, {
                                    x: 0.5,
                                    y: textY,
                                    w: 5.5,
                                    h: 2.5,
                                    fontSize: 13,
                                    lineSpacing: 24
                                });
                            }
                            
                            // Add image on the right
                            slide.addImage({ 
                                data: slideImage.dataUrl, 
                                x: 6.2, 
                                y: 0.8, 
                                w: 3.0, 
                                h: 4.5 
                            });
                        } else {
                            // Full width layout without image
                            let textY = 0.9;
                            
                            // Key point (main concept)
                            slide.addText(`Key Point: ${slideContent.keyPoint}`, {
                                x: 0.5,
                                y: textY,
                                w: 9,
                                h: 0.4,
                                fontSize: 16,
                                bold: true,
                                color: '333333'
                            });
                            textY += 0.5;
                            
                            // Explanation
                            if (slideContent.explanation) {
                                slide.addText(slideContent.explanation, {
                                    x: 0.5,
                                    y: textY,
                                    w: 9,
                                    h: 1.2,
                                    fontSize: 14,
                                    lineSpacing: 20
                                });
                                textY += 1.3;
                            }
                            
                            // Supporting details as bullets
                            if (slideContent.details && slideContent.details.length > 0) {
                                const bulletText = slideContent.details.map(detail => `• ${detail}`).join('\n');
                                slide.addText(bulletText, {
                                    x: 0.5,
                                    y: textY,
                                    w: 9,
                                    h: 3.0,
                                    fontSize: 13,
                                    lineSpacing: 24
                                });
                            }
                        }
                    }
                }

                // Conclusion slide
                if (structuredContent.conclusion) {
                    const slide = pptx.addSlide();
                    slide.addText('Conclusion', { x: 0.5, y: 0.5, w: 9, h: 0.6, fontSize: 28, bold: true, color: '2B5AA0' });
                    
                    // Check if there's a conclusion image
                    const conclusionImage = structuredContent.conclusionImage ? findImageById(structuredContent.conclusionImage) : null;
                    console.log(`Conclusion slide - Image requested: ${structuredContent.conclusionImage}, Found: ${conclusionImage ? 'YES' : 'NO'}`);
                    
                    if (conclusionImage) {
                        console.log(`Adding image ${structuredContent.conclusionImage} to conclusion slide`);
                        // Layout with image on the right
                        slide.addText(structuredContent.conclusion, {
                            x: 0.5,
                            y: 1.3,
                            w: 5.5,
                            h: 4.0,
                            fontSize: 16,
                            lineSpacing: 28
                        });
                        // Add image on the right
                        slide.addImage({ 
                            data: conclusionImage.dataUrl, 
                            x: 6.2, 
                            y: 1.0, 
                            w: 3.0, 
                            h: 4.5 
                        });
                    } else {
                        // Full width text without image
                        slide.addText(structuredContent.conclusion, {
                            x: 0.5,
                            y: 1.3,
                            w: 9,
                            h: 4.0,
                            fontSize: 16,
                            lineSpacing: 28
                        });
                    }
                }

                await pptx.writeFile({ fileName: filename });
                
                // Count how many images were actually embedded
                let imagesEmbedded = 0;
                if (structuredContent.introImage && findImageById(structuredContent.introImage)) imagesEmbedded++;
                if (structuredContent.conclusionImage && findImageById(structuredContent.conclusionImage)) imagesEmbedded++;
                structuredContent.slides?.forEach(slide => {
                    if (slide.image && findImageById(slide.image)) imagesEmbedded++;
                });
                
                console.log(`✅ FINAL RESULT: ${imagesEmbedded} images successfully embedded in presentation`);
                
                if (resolvedSourceType === 'markdown') {
                    return {
                        success: true,
                        message: `Successfully created presentation from Markdown with ${structuredContent.slides?.length || 0} content slides. Saved to ${filename}`
                    };
                }

                return {
                    success: true,
                    message: `Successfully created intelligent presentation with ${structuredContent.slides?.length || 0} content slides and ${imagesEmbedded}/${extractedImages.length} images embedded using ${modelUsed.includes('vl') ? 'vision model' : 'standard model'}. Saved to ${filename}`
                };
            } catch (error) {
                console.error('Document to PPTX error:', error);
                return { success: false, message: `Error converting ${sourceLabel}: ${error.message}` };
            }
        }

        // Detects if the user message is asking to convert a PDF or Markdown document to PowerPoint
        // so we can show upload UI when the LLM replies in text instead of calling the tool.
        function isPdfToPowerPointRequest(text) {
            if (!text || typeof text !== 'string') return false;
            const lower = text.toLowerCase();
            const hasSourceType = /\bpdf\b|\bmarkdown\b|\.md\b|\.markdown\b/i.test(text);
            const hasPowerPoint = /\bpowerpoint\b|\bpptx\b|\bpresentation\b|\bslides?\b|\.pptx\b/i.test(text) || lower.includes('power point');
            const hasConvert = /\bconvert\b|\bturn\b|\btransform\b|\bcreate\b|\bmake\b|\bupload\b/i.test(text);
            return hasSourceType && (hasPowerPoint || hasConvert);
        }

        // Parses optional filename (e.g. my_preso.pptx) and title from the user message for PDF-to-PowerPoint.
        function parsePdfToPowerPointParams(userMessage) {
            const filenameMatch = userMessage.match(/(\w[\w.-]*\.pptx)/i) || userMessage.match(/\b(?:call it|named?|save as|as)\s+['"]?(\w[\w.-]*\.pptx)['"]?/i);
            const filename = filenameMatch ? filenameMatch[1] : 'presentation.pptx';
            const titleMatch = userMessage.match(/(?:call the presentation|title it|named?)\s+['"]?([^'"]+)['"]?/i);
            const title = titleMatch ? titleMatch[1].trim().replace(/\.pptx$/i, '') : 'Presentation';
            return { title, filename };
        }

        // When the LLM replied in text instead of calling the tool, show the upload widget in chat
        // and run conversion when the user selects a PDF or Markdown file.
        function appendPdfUploadWidgetToChat(userMessage) {
            const messageHistory = document.getElementById('message-history');
            if (!messageHistory) return;
            const { title, filename } = parsePdfToPowerPointParams(userMessage);

            const wrapper = document.createElement('div');
            wrapper.id = 'pdf-upload-prompt';
            wrapper.setAttribute('aria-label', 'Presentation source upload');
            wrapper.style.margin = '16px 0';
            wrapper.style.padding = '16px';
            wrapper.style.background = 'rgba(42, 42, 42, 0.95)';
            wrapper.style.border = '1px solid #3a3a3a';
            wrapper.style.borderRadius = '12px';
            wrapper.style.fontFamily = 'Segoe UI, Roboto, sans-serif';
            wrapper.style.color = '#ffffff';

            const text = document.createElement('div');
            text.textContent = 'Select a PDF or Markdown file to convert to PowerPoint';
            text.style.marginBottom = '12px';
            text.style.fontSize = '15px';
            text.style.fontWeight = '600';

            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.pdf,.md,.markdown,application/pdf,text/markdown,text/plain';
            input.style.position = 'absolute';
            input.style.width = '1px';
            input.style.height = '1px';
            input.style.opacity = '0';
            input.style.pointerEvents = 'none';

            const selectBtn = document.createElement('button');
            selectBtn.textContent = 'Select source file';
            selectBtn.type = 'button';
            selectBtn.style.padding = '12px 20px';
            selectBtn.style.marginRight = '10px';
            selectBtn.style.fontSize = '14px';
            selectBtn.style.cursor = 'pointer';
            selectBtn.style.background = '#2563eb';
            selectBtn.style.color = '#fff';
            selectBtn.style.border = 'none';
            selectBtn.style.borderRadius = '8px';
            selectBtn.onclick = () => { input.click(); };

            const cancel = document.createElement('button');
            cancel.textContent = 'Cancel';
            cancel.type = 'button';
            cancel.style.padding = '12px 20px';
            cancel.style.cursor = 'pointer';
            cancel.style.background = '#3a3a3a';
            cancel.style.color = '#ffffff';
            cancel.style.border = '1px solid #4a4a4a';
            cancel.style.borderRadius = '8px';
            cancel.onclick = () => { if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper); };

            input.onchange = async () => {
                const file = input.files && input.files[0] ? input.files[0] : null;
                if (!file || !wrapper.parentNode) return;
                selectBtn.disabled = true;
                text.textContent = 'Converting…';
                try {
                    const result = await handlePdfToPowerPoint({ sourceFile: file, title, filename });
                    if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
                    addMessageToHistory('assistant', result.message);
                    responseOutput.value = result.message;
                    if (typeof textToSpeech === 'function') textToSpeech(result.message);
                } catch (err) {
                    text.textContent = `Error: ${err.message}`;
                    selectBtn.disabled = false;
                }
            };

            wrapper.appendChild(text);
            wrapper.appendChild(input);
            wrapper.appendChild(selectBtn);
            wrapper.appendChild(cancel);
            messageHistory.appendChild(wrapper);
            messageHistory.scrollTop = messageHistory.scrollHeight;
        }

        // Shows source document upload UI inline in the message history so it is always visible
        // (no popup/modal—avoids issues with iframes, z-index, and security blocking dialogs).
        // Button triggers file input so the OS file dialog opens on user gesture.
        function promptForLocalPdf() {
            return new Promise(resolve => {
                const messageHistory = document.getElementById('message-history');
                const wrapper = document.createElement('div');
                wrapper.id = 'pdf-upload-prompt';
                wrapper.setAttribute('aria-label', 'Presentation source upload');
                wrapper.style.margin = '16px 0';
                wrapper.style.padding = '16px';
                wrapper.style.background = 'rgba(42, 42, 42, 0.95)';
                wrapper.style.border = '1px solid #3a3a3a';
                wrapper.style.borderRadius = '12px';
                wrapper.style.fontFamily = 'Segoe UI, Roboto, sans-serif';
                wrapper.style.color = '#ffffff';

                const text = document.createElement('div');
                text.textContent = 'Select a PDF or Markdown file to convert to PowerPoint';
                text.style.marginBottom = '12px';
                text.style.fontSize = '15px';
                text.style.fontWeight = '600';

                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.pdf,.md,.markdown,application/pdf,text/markdown,text/plain';
                input.style.position = 'absolute';
                input.style.width = '1px';
                input.style.height = '1px';
                input.style.opacity = '0';
                input.style.pointerEvents = 'none';

                const selectBtn = document.createElement('button');
                selectBtn.textContent = 'Select source file';
                selectBtn.type = 'button';
                selectBtn.style.padding = '12px 20px';
                selectBtn.style.marginRight = '10px';
                selectBtn.style.fontSize = '14px';
                selectBtn.style.cursor = 'pointer';
                selectBtn.style.background = '#2563eb';
                selectBtn.style.color = '#fff';
                selectBtn.style.border = 'none';
                selectBtn.style.borderRadius = '8px';
                selectBtn.onclick = () => { input.click(); };

                const cancel = document.createElement('button');
                cancel.textContent = 'Cancel';
                cancel.type = 'button';
                cancel.style.padding = '12px 20px';
                cancel.style.cursor = 'pointer';
                cancel.style.background = '#3a3a3a';
                cancel.style.color = '#ffffff';
                cancel.style.border = '1px solid #4a4a4a';
                cancel.style.borderRadius = '8px';
                cancel.onclick = () => {
                    if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
                    resolve(null);
                };

                input.onchange = () => {
                    const file = input.files && input.files[0] ? input.files[0] : null;
                    if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
                    resolve(file);
                };

                wrapper.appendChild(text);
                wrapper.appendChild(input);
                wrapper.appendChild(selectBtn);
                wrapper.appendChild(cancel);

                if (messageHistory) {
                    messageHistory.appendChild(wrapper);
                    messageHistory.scrollTop = messageHistory.scrollHeight;
                } else {
                    document.body.appendChild(wrapper);
                }
            });
        }

        async function resolvePdfInputToDocumentSource(pdfUrl) {
            const source = String(pdfUrl || '').trim();
            if (!source) {
                throw new Error('Missing PDF');
            }
            if (source.startsWith('data:') || source.startsWith('blob:') || /^https?:\/\//i.test(source)) {
                return source;
            }

            const response = await fetch(`${PROXY_BASE_URL}/v1/files/content?path=${encodeURIComponent(source)}`, {
                method: 'GET',
                cache: 'no-store'
            });
            if (!response.ok) {
                const message = await response.text().catch(() => '');
                throw new Error(message || `Missing PDF: ${source}`);
            }
            const blob = await response.blob();
            return await readFileAsDataUrl(blob);
        }

        function normalizePresentationSourceInput(sourceInput, explicitType = '') {
            const sourceType = inferPresentationSourceType(sourceInput, explicitType);

            if (isPresentationFileLike(sourceInput)) {
                return {
                    sourceType,
                    sourceBlob: sourceInput,
                    inlineText: null,
                    locator: ''
                };
            }

            if (typeof sourceInput === 'string') {
                const locator = sourceInput.trim();
                if (!locator) {
                    throw new Error('Missing source document');
                }
                return {
                    sourceType,
                    sourceBlob: null,
                    inlineText: null,
                    locator
                };
            }

            if (!sourceInput || typeof sourceInput !== 'object') {
                throw new Error('Unsupported source input');
            }

            const descriptorType = String(sourceInput.type || sourceInput.kind || sourceInput.sourceKind || '').trim().toLowerCase();
            const blobSource = sourceInput.file || sourceInput.blob || sourceInput.sourceFile;
            if (isPresentationFileLike(blobSource)) {
                return {
                    sourceType,
                    sourceBlob: blobSource,
                    inlineText: null,
                    locator: ''
                };
            }

            const mimeType = firstDefinedString(
                sourceInput.mimeType,
                sourceInput.mime_type,
                sourceInput.contentType,
                sourceInput.content_type
            );
            const fileName = firstDefinedString(
                sourceInput.filename,
                sourceInput.fileName,
                sourceInput.name,
                sourceInput.original_filename,
                sourceInput.originalFilename
            );
            const locator = firstDefinedString(
                sourceInput.sourceUrl,
                sourceInput.url,
                sourceInput.href,
                sourceInput.uri,
                sourceInput.src,
                sourceInput.pdfUrl,
                sourceInput.path,
                sourceInput.filePath,
                sourceInput.relative_path,
                sourceInput.relativePath,
                descriptorType === 'url' || descriptorType === 'path' || descriptorType === 'attachment' || descriptorType === 'file'
                    ? sourceInput.value
                    : '',
                descriptorType === 'attachment' ? sourceInput.name : ''
            );
            const inlineText = firstDefinedString(
                sourceInput.markdown,
                sourceInput.text,
                descriptorType === 'inline' || descriptorType === 'markdown' || descriptorType === 'text'
                    ? sourceInput.value
                    : '',
                sourceInput.content
            );
            const encodedContent = firstDefinedString(
                sourceInput.contentBase64,
                sourceInput.content_base64,
                sourceInput.base64
            );

            if (
                sourceType === 'markdown' &&
                inlineText &&
                (descriptorType === 'inline' || descriptorType === 'markdown' || descriptorType === 'text' || !locator)
            ) {
                return {
                    sourceType,
                    sourceBlob: null,
                    inlineText,
                    locator: ''
                };
            }

            if (encodedContent) {
                if (/^data:/i.test(encodedContent)) {
                    return {
                        sourceType,
                        sourceBlob: null,
                        inlineText: null,
                        locator: encodedContent
                    };
                }
                return {
                    sourceType,
                    sourceBlob: decodeBase64SourceToBlob(
                        encodedContent,
                        mimeType || (sourceType === 'markdown' ? 'text/markdown' : 'application/pdf')
                    ),
                    inlineText: null,
                    locator: ''
                };
            }

            if (locator) {
                return {
                    sourceType: inferPresentationSourceType(
                        {
                            name: fileName,
                            type: mimeType,
                            sourceUrl: locator
                        },
                        explicitType || sourceType
                    ),
                    sourceBlob: null,
                    inlineText: null,
                    locator
                };
            }

            throw new Error('Unsupported source input. Use a URL, scratch-relative path, attachment, uploaded file, inline Markdown, or base64 content.');
        }

        function isPresentationFileLike(value) {
            return typeof Blob !== 'undefined' && value instanceof Blob;
        }

        function firstDefinedString(...values) {
            for (const value of values) {
                if (typeof value === 'string' && value.trim()) {
                    return value.trim();
                }
            }
            return '';
        }

        function decodeBase64SourceToBlob(encodedContent, mimeType) {
            const normalized = String(encodedContent || '').trim();
            if (!normalized) {
                throw new Error('Missing base64 source content');
            }
            const binary = atob(normalized);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            return new Blob([bytes], { type: mimeType || 'application/octet-stream' });
        }

        function inferPresentationSourceType(sourceInput, explicitType = '') {
            const normalizedType = String(explicitType || '').trim().toLowerCase();
            if (normalizedType === 'md') return 'markdown';
            if (normalizedType === 'pdf' || normalizedType === 'markdown') {
                return normalizedType;
            }
            if (normalizedType) {
                throw new Error(`Unsupported source type: ${explicitType}`);
            }

            const descriptorType = sourceInput && typeof sourceInput === 'object'
                ? String(
                    (typeof sourceInput.type === 'string' && !sourceInput.type.includes('/') ? sourceInput.type : '') ||
                    sourceInput.kind ||
                    sourceInput.sourceKind ||
                    ''
                ).toLowerCase()
                : '';
            const fileName = sourceInput && typeof sourceInput === 'object'
                ? firstDefinedString(
                    sourceInput.name,
                    sourceInput.filename,
                    sourceInput.fileName,
                    sourceInput.original_filename,
                    sourceInput.originalFilename
                ).toLowerCase()
                : '';
            const mimeType = sourceInput && typeof sourceInput === 'object'
                ? firstDefinedString(
                    sourceInput.mimeType,
                    sourceInput.mime_type,
                    sourceInput.contentType,
                    sourceInput.content_type,
                    typeof sourceInput.type === 'string' && sourceInput.type.includes('/') ? sourceInput.type : ''
                ).toLowerCase()
                : '';
            const source = typeof sourceInput === 'string'
                ? sourceInput.trim().toLowerCase()
                : sourceInput && typeof sourceInput === 'object'
                    ? firstDefinedString(
                        sourceInput.sourceUrl,
                        sourceInput.url,
                        sourceInput.href,
                        sourceInput.uri,
                        sourceInput.src,
                        sourceInput.pdfUrl,
                        sourceInput.path,
                        sourceInput.filePath,
                        sourceInput.relative_path,
                        sourceInput.relativePath,
                        descriptorType === 'url' || descriptorType === 'path' || descriptorType === 'attachment' || descriptorType === 'file'
                            ? sourceInput.value
                            : '',
                        sourceInput.filename,
                        sourceInput.fileName,
                        sourceInput.original_filename,
                        sourceInput.originalFilename
                    ).toLowerCase()
                    : '';
            const inlineText = sourceInput && typeof sourceInput === 'object'
                ? firstDefinedString(
                    sourceInput.markdown,
                    sourceInput.text,
                    descriptorType === 'inline' || descriptorType === 'markdown' || descriptorType === 'text'
                        ? sourceInput.value
                        : '',
                    sourceInput.content
                )
                : '';

            if (mimeType === 'application/pdf' || fileName.endsWith('.pdf') || /^data:application\/pdf[;,]/i.test(source)) {
                return 'pdf';
            }
            if (
                (descriptorType === 'inline' || descriptorType === 'markdown' || descriptorType === 'text') && inlineText ||
                mimeType === 'text/markdown' ||
                mimeType === 'text/x-markdown' ||
                (mimeType === 'text/plain' && (fileName.endsWith('.md') || fileName.endsWith('.markdown'))) ||
                fileName.endsWith('.md') ||
                fileName.endsWith('.markdown') ||
                /\.md(?:[?#].*)?$/i.test(source) ||
                /\.markdown(?:[?#].*)?$/i.test(source) ||
                /^data:text\/markdown[;,]/i.test(source)
            ) {
                return 'markdown';
            }

            if (typeof sourceInput === 'string' && sourceInput.trim()) {
                return 'pdf';
            }

            throw new Error('Unable to determine source type. Use sourceType with "pdf" or "markdown".');
        }

        async function resolveMarkdownInputToTextSource(sourceUrl) {
            const source = String(sourceUrl || '').trim();
            if (!source) {
                throw new Error('Missing Markdown source');
            }

            let response;
            if (source.startsWith('data:') || source.startsWith('blob:') || /^https?:\/\//i.test(source)) {
                response = await fetch(source, {
                    method: 'GET',
                    cache: 'no-store'
                });
            } else {
                response = await fetch(`${PROXY_BASE_URL}/v1/files/content?path=${encodeURIComponent(source)}`, {
                    method: 'GET',
                    cache: 'no-store'
                });
            }

            if (!response.ok) {
                const message = await response.text().catch(() => '');
                throw new Error(message || `Missing Markdown source: ${source}`);
            }
            return await response.text();
        }

        // Reads a File or Blob as a data URL
        function readFileAsDataUrl(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.onload = () => resolve(reader.result);
                reader.readAsDataURL(file);
            });
        }

        function readFileAsText(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.onload = () => resolve(reader.result);
                reader.readAsText(file);
            });
        }

        function normalizeMarkdownForPresentation(markdownText) {
            return String(markdownText || '')
                .replace(/^---[\r\n]+[\s\S]*?[\r\n]+---[\r\n]*/m, '')
                .replace(/<!--[\s\S]*?-->/g, ' ')
                .replace(/\r\n/g, '\n')
                .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '$1 ')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/^#{1,6}\s+/gm, '')
                .replace(/^\s*[-*+]\s+/gm, '- ')
                .replace(/^\s*\d+\.\s+/gm, '- ')
                .replace(/^\s*>\s?/gm, '')
                .trim();
        }

        // Process images in batches to avoid overwhelming local models
        async function processImagesInBatches(images, modelToUse, batchSize = 3) {
            const imageAnalysis = [];
            // Route through proxy to avoid mixed content (HTTPS page calling HTTP LLM)
            const originalEndpoint = endpointInput.value;
            const endpoint = `${PROXY_BASE_URL}/v1/proxy/chat/completions?endpoint=${encodeURIComponent(originalEndpoint)}`;
            const apiKey = apiKeyInput.value.trim();
            
            // Only process with vision models
            if (!modelToUse.includes('vl')) {
                console.log('Non-vision model detected, skipping batch image analysis');
                return [];
            }
            
            // Process images in batches
            for (let i = 0; i < images.length; i += batchSize) {
                const batch = images.slice(i, i + batchSize);
                const batchNumber = Math.floor(i / batchSize) + 1;
                const totalBatches = Math.ceil(images.length / batchSize);
                
                console.log(`Processing image batch ${batchNumber}/${totalBatches} (${batch.length} images)`);
                
                try {
                    const batchAnalysis = await analyzeImageBatch(batch, endpoint, apiKey, modelToUse);
                    imageAnalysis.push(...batchAnalysis);
                    
                    // Small delay between batches to be gentle on local models
                    if (i + batchSize < images.length) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                } catch (error) {
                    console.warn(`Failed to analyze batch ${batchNumber}:`, error);
                    // Add placeholder analysis for failed batches
                    batch.forEach(img => {
                        imageAnalysis.push({
                            id: img.id,
                            description: 'Image analysis failed',
                            relevantTopics: [],
                            imageType: 'unknown'
                        });
                    });
                }
            }
            
            console.log(`Completed analysis of ${imageAnalysis.length} images`);
            return imageAnalysis;
        }

        // Analyze a single batch of images
        async function analyzeImageBatch(imageBatch, endpoint, apiKey, modelToUse) {
            const userContent = [
                { 
                    type: 'text', 
                    text: `Analyze these ${imageBatch.length} images and for each one provide:
1. Brief description of what the image shows
2. Relevant topics/keywords it relates to
3. Image type (chart, diagram, photo, screenshot, etc.)

Respond in JSON format:
{
  "analyses": [
    {
      "id": "img_pageX_Y",
      "description": "Brief description",
      "relevantTopics": ["topic1", "topic2"],
      "imageType": "chart|diagram|photo|screenshot|other"
    }
  ]
}

IMPORTANT: Respond with ONLY the JSON object.` 
                }
            ];
            
            // Add images to the batch
            imageBatch.forEach(img => {
                userContent.push({
                    type: 'image_url',
                    image_url: {
                        url: img.dataUrl,
                        detail: 'low'
                    }
                });
            });
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${apiKey}`
                },
                body: JSON.stringify({
                    model: modelToUse,
                    messages: [{ role: 'user', content: userContent }],
                    max_tokens: 1024,
                    temperature: 0.3,
                    stream: false
                })
            });
            
            if (!response.ok) {
                throw new Error(`Batch analysis failed: ${response.status}`);
            }
            
            const data = await response.json();
            const content = extractChoiceVisibleText(data?.choices?.[0] || {});
            
            try {
                const jsonMatch = content.match(/\{[\s\S]*\}/);
                const jsonStr = jsonMatch ? jsonMatch[0] : content;
                const result = JSON.parse(jsonStr);
                return result.analyses || [];
            } catch (parseError) {
                console.warn('Failed to parse batch analysis, creating fallback');
                return imageBatch.map(img => ({
                    id: img.id,
                    description: 'Analysis parsing failed',
                    relevantTopics: [],
                    imageType: 'unknown'
                }));
            }
        }

        // Generate structured presentation content using OpenAI LLM
        async function generateStructuredPresentation(fullText, title, maxSlides = 15, availableImages = [], imageAnalysis = [], sourceType = 'pdf') {
            try {
                // Route through proxy to avoid mixed content (HTTPS page calling HTTP LLM)
                const originalEndpoint = endpointInput.value;
                const endpoint = `${PROXY_BASE_URL}/v1/proxy/chat/completions?endpoint=${encodeURIComponent(originalEndpoint)}`;
                const apiKey = apiKeyInput.value.trim();

                if (!apiKey) {
                    throw new Error('API key is required for content generation');
                }

                // Use vision model if images are available for better image analysis
                const modelToUse = availableImages.length > 0 ? 
                    (visionModelDropdown.value || visionModel || 'qwen/qwen2.5-vl-7b') : 
                    getCurrentModel();
                
                console.log(`Using ${availableImages.length > 0 ? 'vision' : 'standard'} model for presentation generation:`, modelToUse);

                // Create CONCISE image information for the prompt using pre-analyzed data
                const sourceLabel = sourceType === 'markdown' ? 'Markdown document' : 'PDF';
                let imageInfo = '';
                if (availableImages.length > 0) {
                    // Group images by type and summarize to keep prompt manageable
                    const imagesByType = {};
                    const keyImages = [];
                    
                    availableImages.forEach(img => {
                        const analysis = imageAnalysis.find(a => a.id === img.id);
                        if (analysis) {
                            const type = analysis.imageType || 'other';
                            if (!imagesByType[type]) imagesByType[type] = [];
                            imagesByType[type].push({...img, analysis});
                            
                            // Keep track of potentially important images (larger ones or with key topics)
                            if (img.width > 300 || img.height > 300 || 
                                analysis.relevantTopics.some(topic => 
                                    ['chart', 'graph', 'diagram', 'workflow', 'architecture', 'data', 'performance'].includes(topic.toLowerCase())
                                )) {
                                keyImages.push({...img, analysis});
                            }
                        }
                    });
                    
                    // Create a concise summary
                    imageInfo = `\n\nImage Summary (${availableImages.length} total images):\n`;
                    
                    // Summarize by type
                    Object.keys(imagesByType).forEach(type => {
                        const count = imagesByType[type].length;
                        imageInfo += `- ${count} ${type}(s)\n`;
                    });
                    
                    // Include more detailed image information (max 25 for better selection)
                    const importantImages = keyImages.slice(0, 25);
                    if (importantImages.length > 0) {
                        imageInfo += `\nDETAILED IMAGE CATALOG FOR SELECTION:\n`;
                        imageInfo += `Please choose from these analyzed images by their exact ID:\n\n`;
                        
                        importantImages.forEach((img, index) => {
                            const topics = img.analysis.relevantTopics.join(', ');
                            const description = img.analysis.description.replace(/\n/g, ' ');
                            imageInfo += `${index + 1}. ID: ${img.id}\n`;
                            imageInfo += `   Type: ${img.analysis.imageType}\n`;
                            imageInfo += `   Content: ${description}\n`;
                            imageInfo += `   Topics: ${topics}\n`;
                            imageInfo += `   Size: ${img.width}x${img.height}px\n\n`;
                        });
                        
                        imageInfo += `SELECTION INSTRUCTIONS:\n`;
                        imageInfo += `- Use exact IDs (e.g., "${importantImages[0].id}")\n`;
                        imageInfo += `- Match image content to slide topics\n`;
                        imageInfo += `- Charts for data slides, diagrams for processes, screenshots for technical content\n`;
                        imageInfo += `- PLEASE SELECT AT LEAST 3-5 RELEVANT IMAGES\n\n`;
                    }
                    
                    // Add fallback image list
                    if (availableImages.length > importantImages.length) {
                        const additionalImages = availableImages.slice(importantImages.length, importantImages.length + 15);
                        imageInfo += `Additional Available Images: `;
                        imageInfo += additionalImages.map(img => img.id).join(', ') + '\n';
                    }
                    
                    imageInfo += `\nNote: Additional ${availableImages.length - importantImages.length} images available for placement.`;
                } else {
                    imageInfo = '\n\nNo images were found in the source document.';
                }

                // Create a comprehensive prompt for OpenAI to structure the content
                const systemPrompt = `You are an expert presentation designer. Your task is to analyze the provided ${sourceLabel} content and create a well-structured PowerPoint presentation outline${availableImages.length > 0 ? ', including intelligent placement of extracted images' : ''}. 

${availableImages.length > 0 ? 'Each image has been pre-analyzed by a vision model to understand its content, type, and relevant topics. Use this analysis information to make smart placement decisions.' : ''}

Structure your response as a JSON object with the following format:
{
    "subtitle": "A brief subtitle for the presentation (optional)",
    "introduction": "A clear, engaging introduction that sets the context and previews main points (2-3 sentences)",
    ${availableImages.length > 0 ? '"introImage": "img_pageX_Y (optional: ID of image that would work well with intro, or null)",\n    ' : ''}"slides": [
        {
            "title": "Clear, compelling slide title",
            "keyPoint": "Main concept or idea for this slide",
            "explanation": "Detailed explanation of the key point (2-4 sentences that elaborate on the concept)",
            "details": ["Supporting bullet point 1", "Supporting bullet point 2", "Supporting bullet point 3"]${availableImages.length > 0 ? ',\n            "image": "img_pageX_Y (optional: ID of most relevant image for this slide, or null)"' : ''}
        }
    ],
    "conclusion": "A strong conclusion that summarizes key takeaways and provides closure (2-3 sentences)"${availableImages.length > 0 ? ',\n    "conclusionImage": "img_pageX_Y (optional: ID of image that would work well with conclusion, or null)"' : ''}
}

Guidelines:
- Create ${Math.min(maxSlides - 2, 18)} content slides maximum (excluding intro/conclusion) - UP TO 20 TOTAL SLIDES
- Each slide should focus on ONE main key point with detailed explanation
- Include 2-4 sentence explanations that elaborate on each key point
- Add 2-4 supporting bullet points that provide specific details or examples
- Focus on the most important and actionable information
- Use clear, professional language suitable for a business presentation
- Ensure logical flow between slides
- Make explanations comprehensive but concise
- If the content is technical, explain concepts in accessible terms${availableImages.length > 0 ? '\n- For image placement: Use the DETAILED IMAGE CATALOG provided above\n- CRITICAL: Choose images using their EXACT IDs from the catalog (e.g., "img_page1_0")\n- Match image content and topics to slide content - charts for data, diagrams for processes, screenshots for technical content\n- PLEASE SELECT AT LEAST 5-8 RELEVANT IMAGES from the detailed catalog\n- Read the image descriptions carefully and match them to appropriate slide content\n- Consider image type and topics when making selections\n- Prefer images with clear relevant topics that match your slide content' : ''}

IMPORTANT: Respond with ONLY the JSON object, no additional text or formatting.`;

                // Adjust text length based on number of images to manage token limits
                const maxTextLength = availableImages.length > 100 ? 8000 : 
                                     availableImages.length > 50 ? 10000 : 12000;
                
                const userPrompt = `Please analyze the following ${sourceLabel} content and create a structured presentation outline for a presentation titled "${title}":

${sourceLabel} Content:
${fullText.length > maxTextLength ? fullText.substring(0, maxTextLength) + '...' : fullText}${imageInfo}`;

                // Use text-only messages since images have been pre-analyzed
                const messages = [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: userPrompt }
                ];
                
                console.log('Using pre-analyzed image data for intelligent placement decisions');
                console.log(`Prompt length: ~${(systemPrompt + userPrompt).length} characters`);
                
                // Debug: Log the image info being sent to LLM
                if (availableImages.length > 0) {
                    console.log('Image info being sent to LLM:');
                    console.log(imageInfo.substring(0, 500) + (imageInfo.length > 500 ? '...' : ''));
                }

                console.log('Generating structured presentation content...');
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        model: modelToUse,
                        messages: messages,
                        max_tokens: 2048,
                        temperature: 0.7,
                        stream: false
                    })
                });

                if (!response.ok) {
                    // If it's a 400 error (likely token limit), try with minimal image data
                    if (response.status === 400 && availableImages.length > 0) {
                        console.warn('Main request failed (likely token limit), retrying with minimal image data...');
                        
                        // Create ultra-minimal image info
                        const minimalImageInfo = `\n\nImages Available: ${availableImages.length} total (types: chart, diagram, screenshot, photo, other)`;
                        
                        const minimalUserPrompt = `Please analyze the following ${sourceLabel} content and create a structured presentation outline for a presentation titled "${title}":

${sourceLabel} Content:
${fullText.substring(0, 6000)}...${minimalImageInfo}`;

                        const retryResponse = await fetch(endpoint, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${apiKey}`
                            },
                            body: JSON.stringify({
                                model: modelToUse,
                                messages: [
                                    { role: 'system', content: systemPrompt.substring(0, 2000) + '\n\nIMPORTANT: Respond with ONLY the JSON object, no additional text or formatting.' },
                                    { role: 'user', content: minimalUserPrompt }
                                ],
                                max_tokens: 2048,
                                temperature: 0.7,
                                stream: false
                            })
                        });
                        
                        if (!retryResponse.ok) {
                            throw new Error(`API request failed even with minimal data: ${retryResponse.status} ${retryResponse.statusText}`);
                        }
                        
                        console.log('Retry with minimal data successful');
                        const retryData = await retryResponse.json();
                        
                        if (!retryData.choices || !retryData.choices[0] || !retryData.choices[0].message) {
                            throw new Error('Invalid response format from retry API call');
                        }
                        
                        const retryContent = extractChoiceVisibleText(retryData?.choices?.[0] || {});
                        console.log('Raw LLM response (minimal retry):', retryContent.substring(0, 200) + '...');
                        
                        // Parse the retry response
                        let structuredContent;
                        try {
                            const jsonMatch = retryContent.match(/\{[\s\S]*\}/);
                            const jsonStr = jsonMatch ? jsonMatch[0] : retryContent;
                            structuredContent = JSON.parse(jsonStr);
                        } catch (parseError) {
                            console.error('Failed to parse minimal retry JSON response:', parseError);
                            structuredContent = createFallbackStructure(fullText, maxSlides, availableImages, imageAnalysis);
                        }
                        
                        // Validate the retry response
                        if (!structuredContent.slides || !Array.isArray(structuredContent.slides)) {
                            structuredContent.slides = [];
                        }
                        
                        structuredContent.slides = structuredContent.slides.map(slide => ({
                            title: slide.title || 'Slide Title',
                            keyPoint: slide.keyPoint || 'Main concept',
                            explanation: slide.explanation || 'Detailed explanation of the concept.',
                            details: Array.isArray(slide.details) ? slide.details : ['Supporting detail'],
                            image: slide.image || null
                        }));
                        
                        console.log('Generated structured content (minimal retry):', structuredContent);
                        
                        // Apply the same fallback logic for minimal retry
                        if (availableImages.length > 0) {
                            const hasAnyImageSelected = structuredContent.introImage || 
                                                     structuredContent.conclusionImage ||
                                                     (structuredContent.slides && structuredContent.slides.some(slide => slide.image));
                            
                            if (!hasAnyImageSelected) {
                                console.log('Minimal retry: Applying fallback image assignment...');
                                console.log(`Available images for minimal retry fallback: ${availableImages.length}`);
                                
                                const usableImages = availableImages.slice(0, 5); // Use first few images
                                console.log(`Using first ${usableImages.length} images for minimal retry fallback`);
                                
                                if (usableImages.length > 0) {
                                    structuredContent.introImage = usableImages[0].id;
                                    console.log('Minimal retry fallback: Assigned intro image:', usableImages[0].id);
                                    
                                    if (structuredContent.slides) {
                                        structuredContent.slides.forEach((slide, index) => {
                                            if (index < usableImages.length - 1 && index < 3) {
                                                slide.image = usableImages[index + 1].id;
                                                console.log(`Minimal retry fallback: Assigned image ${usableImages[index + 1].id} to slide ${index + 1}`);
                                            }
                                        });
                                    }
                                    
                                    // Add conclusion image if available
                                    if (usableImages.length > 4) {
                                        structuredContent.conclusionImage = usableImages[4].id;
                                        console.log('Minimal retry fallback: Assigned conclusion image:', usableImages[4].id);
                                    }
                                } else {
                                    console.warn('No images available for minimal retry fallback');
                                }
                            }
                        }
                        
                        return structuredContent;
                    } else {
                        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
                    }
                }

                const data = await response.json();
                
                if (!data.choices || !data.choices[0] || !data.choices[0].message) {
                    throw new Error('Invalid response format from API');
                }

                const content = extractChoiceVisibleText(data?.choices?.[0] || {});
                console.log('Raw LLM response:', content);

                // Parse the JSON response
                let structuredContent;
                try {
                    // Extract JSON from response (in case there's extra text)
                    const jsonMatch = content.match(/\{[\s\S]*\}/);
                    const jsonStr = jsonMatch ? jsonMatch[0] : content;
                    structuredContent = JSON.parse(jsonStr);
                } catch (parseError) {
                    console.error('Failed to parse JSON response:', parseError);
                    // Fallback to simple structure if parsing fails
                    structuredContent = createFallbackStructure(fullText, maxSlides, availableImages, imageAnalysis);
                }

                // Validate and ensure required structure
                if (!structuredContent.slides || !Array.isArray(structuredContent.slides)) {
                    structuredContent.slides = [];
                }

                // Ensure each slide has required fields and add fallback image selection
                structuredContent.slides = structuredContent.slides.map((slide, index) => ({
                    title: slide.title || 'Slide Title',
                    keyPoint: slide.keyPoint || 'Main concept',
                    explanation: slide.explanation || 'Detailed explanation of the concept.',
                    details: Array.isArray(slide.details) ? slide.details : ['Supporting detail'],
                    image: slide.image || null // Keep original image selection
                }));
                
                // Fallback: If no images were selected by LLM, automatically assign some
                if (availableImages.length > 0) {
                    const hasAnyImageSelected = structuredContent.introImage || 
                                             structuredContent.conclusionImage ||
                                             structuredContent.slides.some(slide => slide.image);
                    
                    if (!hasAnyImageSelected) {
                        console.log('LLM did not select any images, applying fallback image assignment...');
                        console.log(`Available images total: ${availableImages.length}`);
                        console.log(`Image analysis total: ${imageAnalysis.length}`);
                        
                        // Try to assign images based on available analysis, but be more lenient
                        let usableImages = availableImages.filter(img => {
                            const analysis = imageAnalysis.find(a => a.id === img.id);
                            const isUsable = analysis && analysis.imageType !== 'unknown';
                            console.log(`Image ${img.id}: has analysis: ${!!analysis}, type: ${analysis?.imageType}, usable: ${isUsable}`);
                            return isUsable;
                        });
                        
                        // If no usable images with good analysis, just use the first few available images
                        if (usableImages.length === 0) {
                            console.log('No images with good analysis found, using first available images as fallback');
                            usableImages = availableImages.slice(0, 5);
                        }
                        
                        console.log(`Usable images for fallback: ${usableImages.length}`);
                        
                        if (usableImages.length > 0) {
                            // Assign first suitable image to introduction
                            if (usableImages[0]) {
                                structuredContent.introImage = usableImages[0].id;
                                console.log('Fallback: Assigned intro image:', usableImages[0].id);
                            }
                            
                            // Assign images to first few slides
                            structuredContent.slides.forEach((slide, index) => {
                                if (index < usableImages.length - 1 && index < 4) {
                                    slide.image = usableImages[index + 1].id;
                                    console.log(`Fallback: Assigned image ${usableImages[index + 1].id} to slide ${index + 1}`);
                                }
                            });
                            
                            // Assign conclusion image if we have enough
                            if (usableImages.length > structuredContent.slides.length + 1) {
                                structuredContent.conclusionImage = usableImages[usableImages.length - 1].id;
                                console.log('Fallback: Assigned conclusion image:', usableImages[usableImages.length - 1].id);
                            }
                        } else {
                            console.warn('No usable images found for fallback assignment');
                        }
                    }
                }

                // Debug: Check what images were selected by the LLM
                console.log('Generated structured content:', structuredContent);
                if (availableImages.length > 0) {
                    console.log('Image selections by LLM:');
                    console.log('- Intro image:', structuredContent.introImage);
                    console.log('- Conclusion image:', structuredContent.conclusionImage);
                    if (structuredContent.slides) {
                        structuredContent.slides.forEach((slide, index) => {
                            console.log(`- Slide ${index + 1} image:`, slide.image);
                        });
                    }
                }
                return structuredContent;

            } catch (error) {
                console.error('Error generating structured presentation:', error);
                // Return fallback structure on error
                return createFallbackStructure(fullText, maxSlides, availableImages, imageAnalysis);
            }
        }

                        // Fallback function to create basic structure when OpenAI fails
        function createFallbackStructure(fullText, maxSlides, availableImages = [], imageAnalysis = []) {
            console.log('Using fallback structure generation');
            console.log(`Fallback structure: ${availableImages.length} images available`);
            
            // Simple text processing as fallback
            const sentences = fullText
                .split(/(?<=[.!?])\s+/)
                .map(s => s.trim())
                .filter(s => s.length > 20 && /[a-zA-Z]/.test(s));

            const numSlides = Math.min(Math.max(3, maxSlides - 2), 18);
            const sentencesPerSlide = Math.ceil(sentences.length / numSlides);

            const slides = [];
            for (let i = 0; i < numSlides && i * sentencesPerSlide < sentences.length; i++) {
                const startIdx = i * sentencesPerSlide;
                const endIdx = Math.min((i + 1) * sentencesPerSlide, sentences.length);
                const slideSentences = sentences.slice(startIdx, endIdx);
                
                // Assign images to slides in fallback
                const imageId = availableImages[i + 1] ? availableImages[i + 1].id : null;
                if (imageId) {
                    console.log(`Fallback structure: Assigned image ${imageId} to slide ${i + 1}`);
                }
                
                slides.push({
                    title: `Content Slide ${i + 1}`,
                    keyPoint: slideSentences[0] || 'Main concept',
                    explanation: slideSentences.length > 1 ? slideSentences.slice(1, 3).join(' ') : 'Detailed explanation of the concept.',
                    details: slideSentences.slice(1, 4).map(s => s.length > 120 ? s.substring(0, 117) + '...' : s),
                    image: imageId
                });
            }

            // Assign intro and conclusion images in fallback
            const introImageId = availableImages[0] ? availableImages[0].id : null;
            const conclusionImageId = availableImages[availableImages.length - 1] ? availableImages[availableImages.length - 1].id : null;
            
            if (introImageId) {
                console.log(`Fallback structure: Assigned intro image ${introImageId}`);
            }
            if (conclusionImageId && conclusionImageId !== introImageId) {
                console.log(`Fallback structure: Assigned conclusion image ${conclusionImageId}`);
            }

            return {
                subtitle: 'Document Summary',
                introduction: sentences.length > 0 ? sentences[0] : 'Introduction to the document content.',
                introImage: introImageId,
                slides: slides,
                conclusion: sentences.length > 1 ? sentences[sentences.length - 1] : 'Summary of key points discussed.',
                conclusionImage: conclusionImageId !== introImageId ? conclusionImageId : null
            };
        }

        async function handleGoogleDriveUpload({ filePath, fileName }) {
            // Credentials are read from .env file by the proxy server for security
            // No credentials are sent from the frontend

            try {
                // Verify file exists
                if (!filePath) {
                    throw new Error('File path is required');
                }

                // Make request to proxy endpoint for Google Drive upload
                // Note: All credentials and folder ID are read from .env file by the proxy server for security
                const formData = new FormData();
                formData.append('filePath', filePath);
                if (fileName) {
                    formData.append('fileName', fileName);
                }

                // Use authToken for proxy authentication (the global fetch interceptor will also add it, but be explicit)
                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/upload-to-drive`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Upload failed: ${response.statusText}`);
                }

                const data = await response.json();
                
                if (data.fileId) {
                    return {
                        success: true,
                        message: `File successfully uploaded to Google Drive with ID: ${data.fileId}`
                    };
                } else {
                    throw new Error('No file ID received from upload');
                }
            } catch (error) {
                console.error('Google Drive upload error:', error);
                return {
                    success: false,
                    message: `Failed to upload file to Google Drive: ${error.message}`
                };
            }
        }

        // MCP Browser-Use Integration Handlers
        async function handleBrowserAgent({ task }) {
            try {
                console.log('handleBrowserAgent - Task:', task);
                
                // Validate task parameter
                if (!task || typeof task !== 'string' || task.trim() === '') {
                    return {
                        success: false,
                        message: 'Task description is required and must be a non-empty string.'
                    };
                }
                
                // Route through proxy server to avoid mixed content issues with HTTPS
                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/browser-agent`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ task: task })
                });
                
                // Check if request was successful
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: response.statusText }));
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                }
                
                // Parse response data
                const data = await response.json();
                
                // Return formatted result
                if (data.success) {
                    console.log('Browser agent completed successfully');
                    return {
                        success: true,
                        message: `Browser Agent Result:\n\n${data.result}`
                    };
                } else {
                    throw new Error(data.error || 'Unknown error occurred');
                }
                
            } catch (error) {
                console.error('Browser agent error:', error);
                return {
                    success: false,
                    message: `Browser automation failed: ${error.message}\n\nPlease ensure:\n1. The browser-use HTTP server is running (in mcp-browser-use directory: uv run mcp-server-browser-use server)\n2. The MCP Browser HTTP bridge is running (python start_mcp_browser_server.py) if using the Flask API\n3. Environment variables are configured correctly (MCP_BROWSER_USE_HTTP_URL defaults to http://127.0.0.1:8383/mcp)`
                };
            }
        }

        async function handleDeepResearch({ researchTask, maxParallelBrowsers }) {
            try {
                console.log('handleDeepResearch - Task:', researchTask);
                
                // Validate research task parameter
                if (!researchTask || typeof researchTask !== 'string' || researchTask.trim() === '') {
                    return {
                        success: false,
                        message: 'Research task description is required and must be a non-empty string.'
                    };
                }
                
                // Prepare request body with optional parameters
                const requestBody = {
                    research_task: researchTask
                };
                
                // Add optional max parallel browsers parameter if provided
                if (maxParallelBrowsers !== undefined && maxParallelBrowsers !== null) {
                    // Validate and constrain the value
                    const browsers = parseInt(maxParallelBrowsers);
                    if (isNaN(browsers) || browsers < 1) {
                        return {
                            success: false,
                            message: 'maxParallelBrowsers must be a positive number'
                        };
                    }
                    // Cap at 5 to prevent resource exhaustion
                    requestBody.max_parallel_browsers = Math.min(browsers, 5);
                }
                
                // Route through proxy server to avoid mixed content issues with HTTPS
                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/deep-research`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                });
                
                // Check if request was successful
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: response.statusText }));
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                }
                
                // Parse response data
                const data = await response.json();
                
                // Return formatted result
                if (data.success) {
                    console.log('Deep research completed successfully');
                    return {
                        success: true,
                        message: `Deep Research Report:\n\n${data.result}`
                    };
                } else {
                    throw new Error(data.error || 'Unknown error occurred');
                }
                
            } catch (error) {
                console.error('Deep research error:', error);
                return {
                    success: false,
                    message: `Deep research failed: ${error.message}\n\nPlease ensure:\n1. The browser-use HTTP server is running (in mcp-browser-use: uv run mcp-server-browser-use server)\n2. The MCP Browser HTTP bridge is running (python start_mcp_browser_server.py) if using the Flask API\n3. MCP_RESEARCH_TOOL_SAVE_DIR is configured in environment\n4. The browser-use MCP server is accessible (MCP_BROWSER_USE_HTTP_URL)\n5. You have sufficient system resources for parallel browsers`
                };
            }
        }

        async function handleBrowserHealthCheck(_) {
            try {
                const response = await fetch(`${PROXY_BASE_URL}/v1/proxy/browser-health`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({})
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: response.statusText }));
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                if (!data.success) {
                    throw new Error(data.message || 'Unknown error occurred');
                }

                const resultPayload = data.result !== undefined ? data.result : data;
                const pretty = (typeof resultPayload === 'string')
                    ? resultPayload
                    : JSON.stringify(resultPayload, null, 2);
                const summary = data.message ? `${data.message}\n\n` : '';
                return {
                    success: true,
                    message: `Browser Health Check:\n\n${summary}${pretty}`
                };
            } catch (error) {
                console.error('Browser health check error:', error);
                return {
                    success: false,
                    message: `Browser health check failed: ${error.message}`
                };
            }
        }
