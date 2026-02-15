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
        const thinkBtn = document.getElementById('think-btn');

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
        if (userInput) {
            userInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            });
        }

        // Attach button (placeholder - can be extended)
        if (attachBtn) {
            attachBtn.addEventListener('click', function() {
                // Placeholder for attachment functionality
                console.log('Attach clicked');
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
            // Handle input event - show send button when text is entered
            userInput.addEventListener('input', function() {
                if (this.value.trim().length > 0) {
                    sendBtnMobile.style.display = 'flex';
                    if (startRecordBtn) startRecordBtn.style.display = 'none';
                } else {
                    sendBtnMobile.style.display = 'none';
                    if (startRecordBtn) startRecordBtn.style.display = 'flex';
                }
            });

            // Handle blur event - switch back to microphone button when input loses focus
            userInput.addEventListener('blur', function() {
                sendBtnMobile.style.display = 'none';
                if (startRecordBtn) startRecordBtn.style.display = 'flex';
            });

            // Handle focus event - show send button if there's text when input regains focus
            userInput.addEventListener('focus', function() {
                if (this.value.trim().length > 0) {
                    sendBtnMobile.style.display = 'flex';
                    if (startRecordBtn) startRecordBtn.style.display = 'none';
                } else {
                    sendBtnMobile.style.display = 'none';
                    if (startRecordBtn) startRecordBtn.style.display = 'flex';
                }
            });

            // Send on button click - call shared handler directly (iOS Safari ignores programmatic sendBtn.click() on display:none)
            sendBtnMobile.addEventListener('click', function() {
                if (userInput.value.trim().length > 0 && window.submitUserMessage) {
                    window.submitUserMessage();
                }
            });
            // iOS Safari: touchend fires reliably; click can be delayed or lost when keyboard is open
            sendBtnMobile.addEventListener('touchend', function(e) {
                if (userInput.value.trim().length > 0 && window.submitUserMessage) {
                    e.preventDefault();
                    window.submitUserMessage();
                }
            }, { passive: false });
        }
        const userNameInput = document.getElementById('user-name'); // User name input
        const assistantNameInput = document.getElementById('assistant-name'); // Assistant name input
        const status = document.getElementById('status');
        const endpointInput = document.getElementById('endpoint-url');
        const apiKeyInput = document.getElementById('api-key');
        const newsApiKeyInput = document.getElementById('news-api-key');
        const systemPromptInput = document.getElementById('system-prompt');
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
        // Construct base URLs using the detected server with HTTPS
        const PROXY_BASE_URL = `${PROTOCOL}//${SERVER_BASE}:8002`;
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
        let authToken = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || '';

        const authOverlay = document.getElementById('auth-overlay');
        const authUsernameInput = document.getElementById('auth-username');
        const authPasswordInput = document.getElementById('auth-password');
        const authStatus = document.getElementById('auth-status');
        const authLoginBtn = document.getElementById('auth-login-btn');
        const authSignupBtn = document.getElementById('auth-signup-btn');
        const authLogoutBtn = document.getElementById('auth-logout-btn');
        // Guard so post-auth initialization runs only once (e.g. from DOMContentLoaded or after login)
        let appInitialized = false;

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
            if (authToken) localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, authToken);
            else localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        }

        const originalFetch = window.fetch.bind(window);
        window.fetch = async function(input, init = {}) {
            const requestUrl = typeof input === 'string' ? input : input?.url || '';
            const isProxyRequest = requestUrl.startsWith(PROXY_BASE_URL) || requestUrl.startsWith('/v1/');
            const isAuthRoute = requestUrl.includes('/v1/auth/login') || requestUrl.includes('/v1/auth/signup');

            if (isProxyRequest && authToken && !isAuthRoute) {
                const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined) || {});
                if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${authToken}`);
                init = { ...init, headers };
            }

            const response = await originalFetch(input, init);
            if (isProxyRequest && response.status === 401 && !isAuthRoute) {
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

            authStatus.textContent = 'Authenticating...';
            const response = await originalFetch(`${PROXY_BASE_URL}/v1/auth/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                showAuthOverlay(data.detail || 'Authentication failed.');
                return false;
            }

            setAuthToken(data.access_token);
            hideAuthOverlay();
            await runAppInitialization();
            return true;
        }

        async function verifyExistingAuth() {
            if (!authToken) {
                showAuthOverlay('Please log in to continue.');
                return false;
            }

            const response = await originalFetch(`${PROXY_BASE_URL}/v1/auth/me`, {
                headers: { Authorization: `Bearer ${authToken}` }
            });

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
                // Initialize variables from localStorage if available
                try {
                    todoList = JSON.parse(localStorage.getItem('todoList')) || [];
                    memoryCache = JSON.parse(localStorage.getItem('memoryCache')) || [];
                } catch (storageError) {
                    console.warn('Could not access localStorage:', storageError);
                    todoList = [];
                    memoryCache = [];
                }

                // Load persisted tool settings (User Name, Assistant Name, etc.)
                loadToolSettings();
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
                await fetchAvailableModels();
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
                    });
                }

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
        let audioContextResumed = false; // Flag to track if audio context has been resumed after first user action
        
        // Resume audio context on first user action (required for autoplay policy and lip sync)
        async function resumeAudioContextOnce() { // Function to resume audio context once after first user gesture
            if (audioContextResumed) return; // Exit early if already resumed
            audioContextResumed = true; // Mark as resumed
            
            try { // Guard resume operations
                // Resume Opus decoder audio context if available
                if (window.__opus?.audioCtx && window.__opus.audioCtx.state === 'suspended') { // Check if Opus decoder context is suspended
                    await window.__opus.resume(); // Resume audio context to satisfy autoplay policy
                    console.log('✅ Audio context resumed (Opus decoder)'); // Log successful resume
                } // End Opus decoder resume check
                
                // Resume any other audio contexts that might be created for lip sync
                // This ensures audio can play automatically after user gesture
            } catch (e) { // Catch resume errors
                console.warn('⚠️ Failed to resume audio context:', e); // Log resume failure (non-critical)
            } // End resume try/catch
        } // End resumeAudioContextOnce
        
        // Message history management
        let displayedMessages = []; // Array to store displayed messages (last 25)
        let philosopherModeActive = false; // Philosopher mode state
        let philosopherModeStarting = false; // Flag to prevent race condition on start
        let philosopherModeContemplating = false; // Whether a contemplation is in progress
        let philosopherModeInterval = null; // Interval for contemplation loop
        
        // Function to add a message to the history display
        function addMessageToHistory(role, content) {
            // Validate inputs - now supports 'user', 'assistant', and 'philosopher'
            if (!role || (role !== 'user' && role !== 'assistant' && role !== 'philosopher')) {
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
            
            // Create message object - ensure content is set correctly (not sender name)
            const message = {
                role: role, // 'user', 'assistant', or 'philosopher'
                content: content, // The actual message content, not the sender name
                sender: role === 'user' ? userName : (role === 'philosopher' ? philosopherName + ' (Contemplating)' : assistantName),
                timestamp: new Date()
            };
            
            console.log('Message object created:', { role: message.role, sender: message.sender, content: message.content }); // Debug log
            
            // Add to displayedMessages array and limit to 25 messages
            displayedMessages.push(message);
            if (displayedMessages.length > 25) {
                displayedMessages.shift(); // Remove oldest message
            }
            
            // Also add to chatHistory for API calls and persistence
            // Create a simplified message object for chatHistory (without sender/timestamp for API compatibility)
            const chatMessage = {
                role: role,
                content: content
            };
            chatHistory.push(chatMessage);
            
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
        let live2dTickerRegistered = false; // Ensures we only register the Live2D ticker once
        let live2dOffsets = {}; // Persisted map of modelPath -> vertical offset in px
        // Live2D model configuration (selector-driven)
        let modelPath = './model_avatar/RACOON01/RACOON01.model3.json';

        // VRM model variables
        let vrmModel;
        let vrmScene;
        let vrmCamera;
        let vrmRenderer;
        let vrmMixer;
        let vrmClock;
        let vrmLipSyncMorphTarget;
        let vrmBlinkTimeout; // Timer id used to schedule periodic blinking
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

        // Global VRMA actions
        let vrmLoveVrmaAction = null; // Prepared AnimationAction for love VRMA
        let vrmThinkVrmaAction = null; // Prepared AnimationAction for thinking VRMA
        let vrmCryVrmaAction = null; // Prepared AnimationAction for cry VRMA
        let vrmAngryVrmaAction = null; // Prepared AnimationAction for angry VRMA
        let vrmIdleVrmaAction = null; // Prepared AnimationAction for idle VRMA

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
                vrmaPath: './model_avatar/Eva/VRMA_06.vrma', // VRMA animation path for thinking pose
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

        // Add these variables at the top of your script section
        let webcamEnabled = false;
        const webcamToggle = document.getElementById('webcam-toggle');
        const currentModelSpan = document.getElementById('current-model');
        // Storage keys for Live2D model list and selection persistence
        const L2D_LIST_KEY = 'live2dModelList';
        const L2D_SELECTED_KEY = 'live2dSelectedModelPath';
        const L2D_OFFSETS_KEY = 'live2dVerticalOffsets'; // Map modelPath -> offset px

        // Storage keys for VRM model list and selection persistence
        const VRM_LIST_KEY = 'vrmModelList';
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

        // Refresh available models when API key or endpoint changes
        apiKeyInput.addEventListener('change', fetchAvailableModels);
        endpointInput.addEventListener('change', fetchAvailableModels);

        // Add this function to fetch available models
        async function fetchAvailableModels() {
            const originalEndpoint = endpointInput.value.replace('/chat/completions', '/models');
            const apiKey = apiKeyInput.value.trim();
            
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
                    headers: {
                        'Authorization': `Bearer ${apiKey}`
                    }
                });

                const data = await response.json();
                availableModels = data.data || [];
                
                // Update tool model dropdown
                if (toolModelDropdown) {
                    toolModelDropdown.innerHTML = availableModels
                        .map(model => `<option value="${model.id}" ${model.id === defaultToolModel ? 'selected' : ''}>${model.id}</option>`)
                        .join('');
                    if (!toolModelDropdown.value) {
                        toolModelDropdown.value = defaultToolModel;
                    }
                    toolModel = toolModelDropdown.value || defaultToolModel;
                }

                // Update base model dropdown
                if (baseModelDropdown) {
                    baseModelDropdown.innerHTML = availableModels
                        .map(model => `<option value="${model.id}" ${model.id === defaultBaseModel ? 'selected' : ''}>${model.id}</option>`)
                        .join('');
                    if (!baseModelDropdown.value) {
                        baseModelDropdown.value = defaultBaseModel;
                    }
                    baseModel = baseModelDropdown.value || defaultBaseModel;
                }

                // Populate Live2D model list dropdown from persisted storage or textarea
                const live2dList = document.getElementById('live2d-model-list');
                const live2dDropdown = document.getElementById('live2d-model-dropdown');
                const live2dOffsetRange = document.getElementById('live2d-offset-range');
                const live2dOffsetValue = document.getElementById('live2d-offset-value');
                if (live2dList && live2dDropdown) {
                    // Load any persisted list
                    try {
                        const savedList = localStorage.getItem(L2D_LIST_KEY);
                        if (savedList) {
                            live2dList.value = JSON.parse(savedList).join('\n');
                        }
                        const savedSelected = localStorage.getItem(L2D_SELECTED_KEY);
                        if (savedSelected) {
                            modelPath = savedSelected;
                        }
                        const savedOffsets = localStorage.getItem(L2D_OFFSETS_KEY);
                        if (savedOffsets) {
                            live2dOffsets = JSON.parse(savedOffsets);
                        }
                    } catch (e) {
                        console.warn('Unable to read persisted Live2D model list/selection:', e);
                    }

                    const lines = live2dList.value
                        .split(/\r?\n/)
                        .map(l => l.trim())
                        .filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));

                    // Build dropdown options showing only the file name
                    live2dDropdown.innerHTML = lines
                        .map(path => {
                            const fileName = path.split('/').pop();
                            const selected = path === modelPath ? 'selected' : '';
                            return `<option value="${path}" ${selected}>${fileName}</option>`;
                        })
                        .join('');

                    // If current modelPath is not in list, append it
                    if (lines.indexOf(modelPath) === -1) {
                        const fileName = modelPath.split('/').pop();
                        const opt = document.createElement('option');
                        opt.value = modelPath;
                        opt.textContent = fileName;
                        opt.selected = true;
                        live2dDropdown.appendChild(opt);
                    }

                    // Update modelPath when user selects a new one and persist selection
                    live2dDropdown.onchange = async () => {
                        modelPath = live2dDropdown.value;
                        try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
                        // Set the offset UI to stored value (default 0)
                        const currentOffset = live2dOffsets[modelPath] ?? 0;
                        if (live2dOffsetRange && live2dOffsetValue) {
                            live2dOffsetRange.value = currentOffset;
                            live2dOffsetValue.textContent = String(currentOffset);
                        }
                        // Optionally reinitialize Live2D with the new model
                        try {
                            cleanupLive2D();
                        } catch (e) {
                            console.warn('Error destroying previous Live2D model (safe to ignore):', e);
                        }
                        await initLive2D();
                    };

                    // Rebuild dropdown when the list changes (user adds new lines) and persist list
                    live2dList.addEventListener('input', () => {
                        const updated = live2dList.value
                            .split(/\r?\n/)
                            .map(l => l.trim())
                            .filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));
                        try { localStorage.setItem(L2D_LIST_KEY, JSON.stringify(updated)); } catch {}

                        // Keep current selection if still present, otherwise select the last added entry
                        const selectedPath = updated.includes(modelPath)
                            ? modelPath
                            : (updated.length > 0 ? updated[updated.length - 1] : '');

                        live2dDropdown.innerHTML = updated
                            .map(path => {
                                const fileName = path.split('/').pop();
                                const selected = path === selectedPath ? 'selected' : '';
                                return `<option value="${path}" ${selected}>${fileName}</option>`;
                            })
                            .join('');

                        if (selectedPath && selectedPath !== modelPath) {
                            modelPath = selectedPath;
                            live2dDropdown.value = modelPath;
                            try { localStorage.setItem(L2D_SELECTED_KEY, modelPath); } catch {}
                            // Update offset UI to new model's stored offset
                            const currentOffset = live2dOffsets[modelPath] ?? 0;
                            if (live2dOffsetRange && live2dOffsetValue) {
                                live2dOffsetRange.value = currentOffset;
                                live2dOffsetValue.textContent = String(currentOffset);
                            }
                            // Reinitialize the model with the new selection
                            try {
                                cleanupLive2D();
                            } catch (e) {
                                console.warn('Error destroying previous Live2D model (safe to ignore):', e);
                            }
                            initLive2D();
                        }
                    });

                    // Offset range change -> update persisted offset and apply immediately
                    if (live2dOffsetRange && live2dOffsetValue) {
                        const applyOffset = (offsetPx) => {
                            if (live2dModel) {
                                // Apply vertical offset to current model
                                live2dModel.y += offsetPx - (live2dOffsets[modelPath] ?? 0);
                            }
                        };
                        // Initialize UI with current offset
                        const initialOffset = live2dOffsets[modelPath] ?? 0;
                        live2dOffsetRange.value = initialOffset;
                        live2dOffsetValue.textContent = String(initialOffset);
                        live2dOffsetRange.addEventListener('input', () => {
                            const newOffset = parseInt(live2dOffsetRange.value, 10) || 0;
                            live2dOffsetValue.textContent = String(newOffset);
                            // Apply delta offset
                            applyOffset(newOffset);
                            // Persist offset map
                            live2dOffsets[modelPath] = newOffset;
                            try { localStorage.setItem(L2D_OFFSETS_KEY, JSON.stringify(live2dOffsets)); } catch {}
                        });
                    }
                }

                // Initialize VRM model list and controls
                const vrmList = document.getElementById('vrm-model-list');
                const vrmDropdown = document.getElementById('vrm-model-dropdown');
                if (vrmList && vrmDropdown) {
                    // Load any persisted list
                    try {
                        const savedList = localStorage.getItem(VRM_LIST_KEY);
                        if (savedList) {
                            vrmList.value = JSON.parse(savedList).join('\n');
                        }
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

                    let lines = vrmList.value
                        .split('\n')
                        .map(l => l.trim())
                        .filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));
                    // If no VRM entries are provided, keep list empty and wait for user input

                    // Populate dropdown with model paths
                    vrmDropdown.innerHTML = '';
                    lines.forEach(line => {
                        const opt = document.createElement('option');
                        opt.value = line;
                        opt.textContent = line.split('/').pop();
                        vrmDropdown.appendChild(opt);
                    });

                    // Set initial selection
                    if (lines.includes(currentVRMModelPath)) {
                        vrmDropdown.value = currentVRMModelPath;
                    } else if (lines.length > 0) {
                        currentVRMModelPath = lines[0];
                        vrmDropdown.value = currentVRMModelPath;
                    }

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
                        const updated = vrmList.value
                            .split('\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));

                        try { localStorage.setItem(VRM_LIST_KEY, JSON.stringify(updated)); } catch {}

                        // Keep current selection if still present, otherwise select the last added entry
                        vrmDropdown.innerHTML = '';
                        updated.forEach(line => {
                            const opt = document.createElement('option');
                            opt.value = line;
                            opt.textContent = line.split('/').pop();
                            vrmDropdown.appendChild(opt);
                        });

                        let selectedPath = currentVRMModelPath;
                        if (!updated.includes(currentVRMModelPath)) {
                            selectedPath = updated[updated.length - 1] || '';
                        }

                        if (selectedPath) {
                            currentVRMModelPath = selectedPath;
                            vrmDropdown.value = currentVRMModelPath;
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
                        }
                    });

                    vrmModeRadio.addEventListener('change', async () => {
                        if (vrmModeRadio.checked) {
                            await switchToVRM();
                        }
                    });
                }

                // Update vision model dropdown (filter to models that look multimodal if desired)
                if (visionModelDropdown) {
                    visionModelDropdown.innerHTML = availableModels
                        .map(model => `<option value="${model.id}" ${model.id === defaultVisionModel ? 'selected' : ''}>${model.id}</option>`)
                        .join('');
                    if (!visionModelDropdown.value) {
                        visionModelDropdown.value = defaultVisionModel;
                    }
                    visionModel = visionModelDropdown.value || defaultVisionModel;
                }
            } catch (error) {
                console.error('Error fetching models:', error);
                if (toolModelDropdown) {
                    toolModelDropdown.innerHTML = `<option value="${defaultToolModel}" selected>${defaultToolModel}</option>`;
                    toolModel = defaultToolModel;
                }
                if (baseModelDropdown) {
                    baseModelDropdown.innerHTML = `<option value="${defaultBaseModel}" selected>${defaultBaseModel}</option>`;
                    baseModel = defaultBaseModel;
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
            // If webcam or clipboard vision is enabled, use the corresponding model
            if (webcamEnabled) {
                return visionModel || 'qwen/qwen2.5-vl-7b';
            }
            if (clipboardVisionEnabled && clipboardType === 'image') {
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

        // Fetch TTS voices from OpenAI-compatible endpoint (e.g., Chatterbox)
        async function fetchTtsVoices() {
            try {
                // Get the TTS endpoint and normalize it (remove trailing slash)
                const endpoint = (ttsEndpointInput && ttsEndpointInput.value && ttsEndpointInput.value.trim()) 
                    ? ttsEndpointInput.value.trim().replace(/\/$/, '') 
                    : 'http://localhost:4123/v1';
                
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
                    const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/tts/voices?endpoint=${encodeURIComponent(baseUrl)}`;
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
                        const openAiFallbackProxyUrl = `${PROXY_BASE_URL}/v1/proxy/tts/voices?endpoint=${encodeURIComponent(openAiFallbackUrl)}`;
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
                    return;
                }
                
                console.log('Fetched voices:', responseData);
                
                // Extract voices array from the response (handle both array and object formats)
                let voicesData = responseData;
                if (responseData && typeof responseData === 'object' && responseData.voices) {
                    // Response is an object with a 'voices' property
                    voicesData = responseData.voices;
                } else if (!Array.isArray(responseData)) {
                    // Response is neither an array nor an object with voices property
                    console.warn('Unexpected voices response format:', responseData);
                    voicesData = [];
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
                
                // Add default OpenAI voices first
                const defaultVoices = ['Empress'];
                defaultVoices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice;
                    option.textContent = voice;
                    ttsVoiceDropdown.appendChild(option);
                });
                
                // Add fetched voices from Chatterbox
                if (Array.isArray(voicesData)) {
                    console.log(`Adding ${voicesData.length} voices from Chatterbox`);
                    voicesData.forEach(voice => {
                        const option = document.createElement('option');
                        option.value = voice.name;
                        // Show filename if metadata is not available
                        const displayName = voice.name + (voice.metadata?.language ? ` (${voice.metadata.language})` : 
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

        // Update the textToSpeech function
        function textToSpeech(text) {
            if (!text) {
                console.warn('No text provided for speech');
                return;
            }

            // Check if muted
            if (isMuted) {
                console.log('TTS is muted, skipping speech');
                return;
            }

            // Sanitize text to remove emojis, bracketed sections, asterisks, and special symbols
            text = sanitizeTTS(text);

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
                speakWithOpenAITTS(text); // Use OpenAI TTS which returns audio bytes we can analyze
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
            
            // Start smooth amplitude-based lip sync for Microsoft TTS (similar to Chatterbox analyser approach)
            function startMicrosoftTtsLipSync() { // Start smooth lip sync loop for Microsoft TTS
                if (microsoftTtsRafId) return; // Avoid spawning duplicate loops
                
                microsoftTtsIsActive = true; // Mark lip sync as active
                microsoftTtsSmoothedAmplitude = 0; // Initialize smoothed amplitude
                microsoftTtsTargetAmplitude = 0.3; // Start with lower mouth opening to allow natural closing
                microsoftTtsLastBoundaryTs = performance.now(); // Initialize boundary timestamp
                
                const attack = 0.6; // Attack coefficient for rising amplitude (same as Chatterbox)
                const release = 0.15; // Release coefficient for falling amplitude (same as Chatterbox)
                const threshold = 0.05; // Minimum amplitude threshold (increased to make mouth close more between words)
                const boundaryDecayRate = 0.08; // Rate at which amplitude decays between boundaries (increased for faster closing)
                const boundaryDecayDelay = 50; // Delay before decay starts (reduced from 100ms for more responsive closing)
                
                const step = () => { // Per-frame lip sync update callback
                    if (!microsoftTtsIsActive || !isSpeaking) { // Stop if speech ended or deactivated
                        microsoftTtsRafId = 0; // Clear RAF id
                        microsoftTtsSmoothedAmplitude = 0; // Reset amplitude
                        // Close mouth when speech ends
                        if (live2dModel) {
                            live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, 0);
                        }
                        const vrmModeToggle = document.getElementById('vrm-mode');
                        if (vrmModel && vrmModeToggle && vrmModeToggle.checked) {
                            animateVRMLipSync(0);
                        }
                        return; // Exit loop
                    }
                    
                    const now = performance.now(); // Get current timestamp
                    const timeSinceBoundary = now - microsoftTtsLastBoundaryTs; // Calculate time since last boundary
                    
                    // Decay target amplitude over time if no recent boundary (simulates natural speech rhythm)
                    // Use exponential decay for more natural closing between words
                    if (timeSinceBoundary > boundaryDecayDelay) { // If no boundary for >50ms, start decaying
                        const decayFactor = Math.min(1.0, (timeSinceBoundary - boundaryDecayDelay) / 200); // Faster decay over 200ms
                        microsoftTtsTargetAmplitude = Math.max(0, microsoftTtsTargetAmplitude - (boundaryDecayRate * decayFactor));
                    }
                    
                    // Apply attack/release smoothing (same algorithm as Chatterbox analyser)
                    if (microsoftTtsTargetAmplitude > microsoftTtsSmoothedAmplitude) { // Attack branch
                        microsoftTtsSmoothedAmplitude += (microsoftTtsTargetAmplitude - microsoftTtsSmoothedAmplitude) * attack;
                    } else { // Release branch
                        microsoftTtsSmoothedAmplitude += (microsoftTtsTargetAmplitude - microsoftTtsSmoothedAmplitude) * release;
                    }
                    
                    // Scale amplitude with adjusted threshold for better mouth closing between words
                    const scaled = microsoftTtsSmoothedAmplitude <= threshold ? 0 : Math.min(1, (microsoftTtsSmoothedAmplitude - threshold) * 5.5);
                    
                    // Apply to Live2D model
                    if (live2dModel) {
                        live2dModel.internalModel.coreModel.setParameterValueById(mouthOpenY, scaled);
                    }
                    
                    // Apply to VRM model
                    const vrmModeToggle = document.getElementById('vrm-mode');
                    if (vrmModel && vrmModeToggle && vrmModeToggle.checked) {
                        animateVRMLipSync(scaled);
                    }
                    
                    // Continue loop while speech is active
                    if (isSpeaking && microsoftTtsIsActive) {
                        microsoftTtsRafId = requestAnimationFrame(step);
                    } else {
                        microsoftTtsRafId = 0; // Clear RAF id when done
                    }
                }; // End step function
                
                step(); // Start the lip sync loop immediately
            } // End startMicrosoftTtsLipSync
            
            utterance.onstart = function() { // When speech begins
                console.log('Speech started'); // Log start of speech
                isSpeaking = true; // Set global speaking flag
                if (live2dModel) { // If Live2D model is active
                    headMovementInterval = setInterval(() => { // Start periodic head movement
                        animateHeadMovement(live2dModel, 1000); // Trigger head animation routine
                    }, 3000); // Run every 3 seconds
                } // End Live2D head movement setup

                microsoftTtsLastBoundaryTs = performance.now(); // Initialize boundary timestamp
                
                // Start smooth amplitude-based lip sync (same approach as Chatterbox)
                startMicrosoftTtsLipSync(); // Start smooth lip sync loop

                // Kick mouth slightly open at start so it does not appear stuck
                if (vrmModel && document.getElementById('vrm-mode').checked) { // If VRM active
                    animateVRMLipSync(0.8); // Open mouth initially
                } // End VRM initial kick
            }; // End onstart handler

            utterance.onboundary = function(event) { // Called on word or sentence boundaries
                const now = performance.now(); // Get current timestamp
                const timeSinceLastBoundary = now - microsoftTtsLastBoundaryTs; // Calculate time since last boundary
                microsoftTtsLastBoundaryTs = now; // Update boundary timestamp
                // Trigger amplitude increase on boundary (simulates speech activity)
                // Use smaller, more frequent boosts to allow mouth to close between words
                const amplitudeBoost = Math.min(0.35, 0.15 + (timeSinceLastBoundary / 1000) * 0.08); // Reduced boost for more natural closing
                microsoftTtsTargetAmplitude = Math.min(0.85, microsoftTtsTargetAmplitude + amplitudeBoost); // Cap at 0.85 to allow closing
            }; // End onboundary handler

            utterance.onend = function() { // When speech ends
                console.log('Speech ended'); // Log end of speech
                isSpeaking = false; // Clear speaking flag
                microsoftTtsIsActive = false; // Stop Microsoft TTS lip sync loop
                if (headMovementInterval) { // If head movement was running
                    clearInterval(headMovementInterval); // Stop head movement interval
                } // End head movement cleanup
                if (microsoftTtsRafId) { // If Microsoft TTS lip sync RAF is running
                    try { cancelAnimationFrame(microsoftTtsRafId); } catch(_){} // Cancel animation frame
                    microsoftTtsRafId = 0; // Clear RAF id
                } // End Microsoft TTS lip sync cleanup
                if (ttsLipSyncIntervalId) { try { clearInterval(ttsLipSyncIntervalId); } catch(_){} ttsLipSyncIntervalId = null; }
                if (ttsRafId) { try { cancelAnimationFrame(ttsRafId); } catch(_){} ttsRafId = 0; }
                try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); } catch(_){}
                ttsCleanupFns = [];

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
                console.error('Speech synthesis error:', event);
            };

            utterance.rate = 1.0;
            utterance.pitch = 1.0;

            try {
            speechSynthesis.speak(utterance);
            } catch (error) {
                console.error('Speech synthesis error:', error);
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
        function playPcm16Delta(base64, sampleRate = 24000, channels = 1) { // Function to decode and play PCM16 audio chunk
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
            if (ttsAnalyserNode) { // Route through analyser when available for lip sync
                src.connect(ttsAnalyserNode);
            } else {
                src.connect(ctx.destination); // Fallback directly to destination if analyser missing
            }

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
			});

            // Keep the same playhead logic (reuse from existing scheduler)
            window.__opus.playhead = Math.max(ctx.currentTime, window.__opus.playhead || 0); // Calculate start time with playhead overlap
            src.start(window.__opus.playhead); // Schedule playback at playhead position
            window.__opus.playhead += buf.duration - 0.02; // Update playhead with 20ms overlap to hide seams
            
            console.log('🔊 Scheduled PCM16 chunk:', framesPerChannel, 'frames per channel (', totalSamples, 'total samples ),', sampleRate, 'Hz,', safeChannels, 'channels, duration:', buf.duration.toFixed(3), 's'); // Log playback info
        } // End playPcm16Delta
        
        // Speak using Chatterbox TTS endpoint with streaming PCM16 decoding
		async function speakWithOpenAITTS(text) { // Asynchronous function to fetch and play TTS audio via Chatterbox
            // Declare localGen and localController outside try block so they're accessible in catch block
            let localGen = 0; // Generation token for this TTS request (initialized before try block)
            let localController = null; // Local reference to this request's abort controller
            try { // Begin error handling scope
                if (!text) return; // Guard for missing input
                
                // Sanitize text before sending to TTS API (remove emojis/brackets/asterisks/specials)
                text = sanitizeTTS(text);
                
                // Get TTS settings from UI elements - require Chatterbox endpoint
                if (!ttsEndpointInput || !ttsEndpointInput.value || !ttsEndpointInput.value.trim()) { // Check if endpoint is configured
                    console.error('❌ Chatterbox TTS endpoint not configured'); // Log error
                    textToSpeechFallback(text); // Fall back to browser TTS
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
                
                // Use proxy endpoint to handle CORS
                const endpoint = `${PROXY_BASE_URL}/v1/proxy/tts/speech?endpoint=${encodeURIComponent(baseUrl)}`; // Use proxy endpoint for TTS speech
                const modelId = (ttsModelDropdown && ttsModelDropdown.value) ? ttsModelDropdown.value : 'tts-1'; // Get model from dropdown or default
                const voiceId = (ttsVoiceDropdown && ttsVoiceDropdown.value) ? ttsVoiceDropdown.value : 'alloy'; // Get voice from dropdown or default

                const reqBody = { // Build request payload for Chatterbox SSE streaming with PCM16
                    model: modelId, // TTS model (optional for Chatterbox)
                    voice: voiceId, // Voice preset
                    input: text, // The text to speak (emojis already removed)
                    stream: true, // Enable streaming
                    stream_format: 'sse', // Use SSE format for browser-friendly streaming
                    streaming_chunk_size: 150, // Request 10 byte chunks
                    streaming_strategy: 'word', // Request word-based streaming strategy
                    streaming_quality: 'fast', // Request fast quality streaming
                    container: 'raw', // Request raw PCM format
                    codec: 'pcm16' // Request PCM16 codec format
                }; // End payload

                // Build headers for Chatterbox SSE streaming (no Authorization needed for local Chatterbox)
                const headers = { // Set content headers for SSE streaming
                    'Content-Type': 'application/json', // JSON body content type
                    'Accept': 'text/event-stream' // Request SSE format response
                }; // End headers

				// Prepare abort + generation token so interruptions cancel immediately and stale callbacks are ignored
				try { if (ttsAbortController) { ttsAbortController.abort(); } } catch (_) {}
				localController = new AbortController(); // Create controller for this specific request
				ttsAbortController = localController; // Store in global variable
				localGen = (++ttsGeneration); // Assign generation token for this request

				// Use SSE streaming approach for lower latency through proxy
				const res = await fetch(endpoint, { // Issue HTTP request for speech through proxy
                    method: 'POST', // Use POST method per API spec
                    headers: headers, // Set headers for SSE streaming
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
                    textToSpeechFallback(text); // Use backup speaker for continuity
                    return; // Exit early
                } // End error response branch
                
                // Detect response format: SSE (Chatterbox/PCM) or binary audio (VibeVoice/OpenAI-compatible)
                const ct = (res.headers.get('content-type') || '').toLowerCase(); // Get content type from headers
                const isSSE = ct.includes('text/event-stream'); // Check if response is SSE format (Chatterbox)
                const isBinaryAudio = ct.includes('audio/'); // Check if response is binary audio (VibeVoice/OpenAI-compatible)
                
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
                        if (ct.includes('audio/wav') || ct.includes('audio/wave')) {
                            mimeType = 'audio/wav';
                        } else if (ct.includes('audio/webm')) {
                            mimeType = 'audio/webm';
                        } else if (ct.includes('audio/ogg')) {
                            mimeType = 'audio/ogg';
                        } else if (ct.includes('audio/mp4') || ct.includes('audio/m4a')) {
                            mimeType = 'audio/mp4';
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
                                                        // Start lip sync using audio element
                                                        const audioContext = new (window.AudioContext || window.webkitAudioContext)(); // Create audio context
                                                        const source = audioContext.createMediaElementSource(audio); // Create source from audio element
                                                        const analyser = audioContext.createAnalyser(); // Create analyser for lip sync
                                                        analyser.fftSize = 256; // Set FFT size for analysis
                                                        source.connect(analyser); // Connect source to analyser
                                                        analyser.connect(audioContext.destination); // Connect analyser to output
                                                        startLipSyncFromAnalyserNode(); // Start analyser-driven lip sync updates
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
                            const audioUrl = URL.createObjectURL(audioBlob); // Create object URL for blob
                            
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
                            
                            // Start basic lip sync using audio amplitude
                            const audioContext = new (window.AudioContext || window.webkitAudioContext)(); // Create audio context
                            const source = audioContext.createMediaElementSource(audio); // Create source from audio element
                            const analyser = audioContext.createAnalyser(); // Create analyser for lip sync
                            analyser.fftSize = 256; // Set FFT size for analysis
                            source.connect(analyser); // Connect source to analyser
                            analyser.connect(audioContext.destination); // Connect analyser to output
                            
                            // Start lip sync animation
                            startLipSyncFromAnalyserNode(); // Start analyser-driven lip sync updates
                            
                            // Play the audio
                            await audio.play(); // Start playback
                            console.log('🎵 Playing binary audio from TTS service (blob mode)'); // Log playback start
                            
                            return; // Exit successfully
                        }
                    } catch (audioError) {
                        console.error('❌ Error playing binary audio:', audioError); // Log error
                        stopChatterboxLipSync(true); // Reset lip sync state
                        textToSpeechFallback(text); // Fall back to browser TTS on error
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
						playPcm16Delta(b64, ttsSampleRate, ttsChannels);
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
                        textToSpeechFallback(text); // Fall back to browser TTS if error occurs
                    } // End onError handler
                }); // End streamSSE call
                } else {
                    // Unknown format - neither SSE nor binary audio
                    console.warn('⚠️ Unknown TTS response format:', ct, '- falling back to browser TTS'); // Log format mismatch
                    stopChatterboxLipSync(true); // Reset lip sync state before fallback
                    textToSpeechFallback(text); // Fall back to browser TTS
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
                textToSpeechFallback(text); // Ensure speech still happens
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
                console.log('🎵 Audio playback started'); // Log playback start
            } catch (error) {
                console.error('Error playing streaming audio:', error); // Log error
            } // End try/catch
        } // End playStreamingAudio
        
        // Browser speech fallback wrapper used when server TTS fails
        function textToSpeechFallback(text) { // Function to call original SpeechSynthesis path
            try { // Begin guard
                // Sanitize text before creating utterance
                text = sanitizeTTS(text); // Clean text for browser fallback speech
                const utter = new SpeechSynthesisUtterance(text); // Build utterance instance
                utter.onend = () => { // Ensure cleanup on browser TTS end
                    try { if (ttsLipSyncIntervalId) { clearInterval(ttsLipSyncIntervalId); ttsLipSyncIntervalId = null; } } catch(_){}
                    try { if (ttsRafId) { cancelAnimationFrame(ttsRafId); ttsRafId = 0; } } catch(_){}
                    try { ttsCleanupFns.forEach(fn => { try { fn(); } catch(_){} }); ttsCleanupFns = []; } catch(_){}
                    if (live2dModel) { live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0); }
                    if (vrmModel && document.getElementById('vrm-mode').checked) { animateVRMLipSync(0); }
                };
                speechSynthesis.speak(utter); // Speak using browser engine
            } catch (e) { // Catch runtime issues
                console.warn('Browser TTS fallback failed:', e); // Log warning for diagnostics
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
                    audioEl.removeEventListener('ended', onEnded); // Remove event handler
                }; // End onEnded

                audioEl.addEventListener('ended', onEnded); // Wire cleanup on end
                // Register cleanup for external cancellations
                ttsCleanupFns.push(() => {
                    try { audioEl.pause(); } catch(_){}
                    try { audioEl.removeEventListener('ended', onEnded); } catch(_){}
                    try { source.disconnect(); } catch(_){}
                    try { analyser.disconnect(); } catch(_){}
                    try { gain.disconnect(); } catch(_){}
                    try { if (rafId) cancelAnimationFrame(rafId); } catch(_){}
                    try { URL.revokeObjectURL(audioEl.src); } catch(_){}
                });
                update(); // Kick off the animation loop
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

        // Build full tool settings object from DOM (single source of truth for companion snapshot and localStorage)
        function getToolSettingsFromDOM() {
            const vrmVersionDropdown = document.getElementById('vrm-version-dropdown');
            const voiceDropdown = document.getElementById('voice-dropdown');
            const live2dDropdown = document.getElementById('live2d-model-dropdown');
            const live2dList = document.getElementById('live2d-model-list');
            const live2dOffsetRange = document.getElementById('live2d-offset-range');
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
                vrmModel: vrmDropdown ? vrmDropdown.value : '',
                vrmModelList: vrmList ? vrmList.value : '',
                vrmScale: vrmScaleRange ? parseFloat(vrmScaleRange.value) || 1.0 : 1.0,
                vrmPositionX: vrmPositionXRange ? parseFloat(vrmPositionXRange.value) || 0 : 0,
                vrmPositionY: vrmPositionYRange ? parseFloat(vrmPositionYRange.value) || 0 : 0,
                vrmRotation: vrmRotationRange ? parseInt(vrmRotationRange.value, 10) || 0 : 0,
                live2dOffsets: live2dOffsets || {},
                vrmPositions: vrmPositions || {}
            };
        }

        // Function to save tool settings to localStorage (uses getToolSettingsFromDOM as single source)
        function saveToolSettings() {
            try {
                const settings = getToolSettingsFromDOM();
                localStorage.setItem('toolSettings', JSON.stringify(settings));
            } catch (error) {
                console.warn('Error saving tool settings:', error);
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
            if (settings.ttsModel !== undefined && ttsModelDropdown) ttsModelDropdown.value = settings.ttsModel;
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
            if (live2dListEl && live2dDropdownEl) {
                const lines = (live2dListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));
                live2dDropdownEl.innerHTML = lines.map(path => {
                    const fileName = path.split('/').pop();
                    const selected = path === modelPath ? ' selected' : '';
                    return `<option value="${path}"${selected}>${fileName}</option>`;
                }).join('');
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
            const offsetVal = settings.live2dOffset !== undefined ? Number(settings.live2dOffset) : (live2dOffsets[modelPath] ?? 0);
            if (live2dOffsetRangeEl) live2dOffsetRangeEl.value = offsetVal;
            if (live2dOffsetValueEl) live2dOffsetValueEl.textContent = String(offsetVal);
            // Avatar: VRM list and selection
            const vrmListEl = document.getElementById('vrm-model-list');
            const vrmDropdownEl = document.getElementById('vrm-model-dropdown');
            if (settings.vrmModelList !== undefined && vrmListEl) vrmListEl.value = settings.vrmModelList;
            if (settings.vrmModel !== undefined) currentVRMModelPath = settings.vrmModel;
            if (settings.vrmPositions !== undefined && typeof settings.vrmPositions === 'object') vrmPositions = settings.vrmPositions;
            if (vrmListEl && vrmDropdownEl) {
                const vrmLines = (vrmListEl.value || '').split('\n').map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));
                vrmDropdownEl.innerHTML = vrmLines.map(path => `<option value="${path}">${path.split('/').pop()}</option>`).join('');
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
                const settings = optionalSettings != null
                    ? optionalSettings
                    : (() => { const s = localStorage.getItem('toolSettings'); return s ? JSON.parse(s) : null; })();
                if (settings) {
                    applyToolSettingsToDOM(settings);
                    if (optionalSettings == null) console.log('Tool settings loaded from localStorage');
                }
            } catch (error) {
                console.warn('Error loading tool settings:', error);
            }
        }

        // Normalize path for dedupe: strip leading ./ and trailing slash so "./model_avatar/X" matches "model_avatar/X"
        function normalizeModelPath(p) {
            return (p || '').trim().replace(/^\.\//, '').replace(/\/$/, '');
        }

        // Call scan endpoint, merge discovered paths into Live2D/VRM lists, rebuild dropdowns, persist
        async function scanAndMergeModelAvatarLists() {
            const live2dListEl = document.getElementById('live2d-model-list');
            const live2dDropdownEl = document.getElementById('live2d-model-dropdown');
            const vrmListEl = document.getElementById('vrm-model-list');
            const vrmDropdownEl = document.getElementById('vrm-model-dropdown');
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
                    if (typeof showToast === 'function') showToast(msg); else console.warn(msg);
                    return;
                }
                const data = await res.json();
                const scannedLive2d = Array.isArray(data.live2d) ? data.live2d : [];
                const scannedVrm = Array.isArray(data.vrm) ? data.vrm : [];
                // Merge Live2D: existing lines first (dedupe by normalized path), then append new from scan
                const live2dLines = (live2dListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));
                const live2dNorm = new Set(live2dLines.map(normalizeModelPath));
                const origLive2dCount = live2dLines.length;
                scannedLive2d.forEach(path => {
                    if (!live2dNorm.has(normalizeModelPath(path))) {
                        live2dLines.push(path);
                        live2dNorm.add(normalizeModelPath(path));
                    }
                });
                live2dListEl.value = live2dLines.join('\n');
                // Merge VRM: same
                const vrmLines = (vrmListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));
                const vrmNorm = new Set(vrmLines.map(normalizeModelPath));
                const origVrmCount = vrmLines.length;
                scannedVrm.forEach(path => {
                    if (!vrmNorm.has(normalizeModelPath(path))) {
                        vrmLines.push(path);
                        vrmNorm.add(normalizeModelPath(path));
                    }
                });
                vrmListEl.value = vrmLines.join('\n');
                // Rebuild Live2D dropdown from merged list
                if (live2dDropdownEl) {
                    const lines = (live2dListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.model3.json'));
                    live2dDropdownEl.innerHTML = lines.map(path => {
                        const fileName = path.split('/').pop();
                        const selected = path === modelPath ? ' selected' : '';
                        return `<option value="${path}"${selected}>${fileName}</option>`;
                    }).join('');
                    if (modelPath && lines.indexOf(modelPath) === -1) {
                        const opt = document.createElement('option');
                        opt.value = modelPath;
                        opt.textContent = modelPath.split('/').pop();
                        opt.selected = true;
                        live2dDropdownEl.appendChild(opt);
                    } else if (modelPath) live2dDropdownEl.value = modelPath;
                }
                // Rebuild VRM dropdown from merged list
                if (vrmDropdownEl) {
                    const vrmLinesFinal = (vrmListEl.value || '').split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0 && l.toLowerCase().endsWith('.vrm'));
                    vrmDropdownEl.innerHTML = vrmLinesFinal.map(path => `<option value="${path}">${path.split('/').pop()}</option>`).join('');
                    if (currentVRMModelPath) {
                        if (vrmLinesFinal.indexOf(currentVRMModelPath) !== -1) vrmDropdownEl.value = currentVRMModelPath;
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
                saveToolSettings();
                const addedLive2d = live2dLines.length - origLive2dCount;
                const addedVrmCount = vrmLines.length - origVrmCount;
                const feedback = (addedLive2d || addedVrmCount) ? `Added ${addedLive2d} Live2D, ${addedVrmCount} VRM model(s).` : 'No new models found.';
                if (typeof showToast === 'function') showToast(feedback); else console.log(feedback);
            } catch (err) {
                const msg = 'Scan failed. Is the server running?';
                if (typeof showToast === 'function') showToast(msg); else console.warn(msg, err);
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

        let activeCompanionId = null;

        function renderCompanionList() {
            const listEl = document.getElementById('companion-list');
            if (!listEl) return;
            listEl.innerHTML = '';
            fetchCompanionsList().then(companions => {
                if (!Array.isArray(companions)) return;
                companions.forEach(c => {
                    const li = document.createElement('li');
                    li.setAttribute('data-companion-id', c.id);
                    if (c.id === activeCompanionId) li.classList.add('companion-active');
                    const nameSpan = document.createElement('span');
                    nameSpan.textContent = c.name || c.id;
                    nameSpan.className = 'companion-name';
                    li.appendChild(nameSpan);
                    const delBtn = document.createElement('button');
                    delBtn.type = 'button';
                    delBtn.className = 'companion-delete-btn';
                    delBtn.setAttribute('aria-label', 'Delete companion');
                    delBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
                    delBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteCompanion(c.id); });
                    li.appendChild(delBtn);
                    listEl.appendChild(li);
                });
            }).catch(err => {
                console.warn('Companions list failed:', err);
                listEl.innerHTML = '<li style="color:#888;">Unable to load companions</li>';
            });
        }

        async function loadCompanion(id) {
            const url = `${PROXY_BASE_URL}/v1/companions/${encodeURIComponent(id)}`;
            const res = await fetch(url, { headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) throw new Error(res.statusText || 'Companion not found');
            const data = await res.json();
            if (data.settings) {
                applyToolSettingsToDOM(data.settings);
                saveToolSettings();
                activeCompanionId = id;
                renderCompanionList();
            }
        }

        async function deleteCompanion(id) {
            const url = `${PROXY_BASE_URL}/v1/companions/${encodeURIComponent(id)}`;
            const res = await fetch(url, { method: 'DELETE', headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) throw new Error(res.statusText || 'Delete failed');
            if (activeCompanionId === id) activeCompanionId = null;
            renderCompanionList();
        }

        function setupCompanionsUI() {
            const listEl = document.getElementById('companion-list');
            const addBtn = document.getElementById('companion-add-btn');
            const modalOverlay = document.getElementById('companion-modal-overlay');
            const modal = document.getElementById('companion-modal');
            const nameInput = document.getElementById('companion-name-input');
            const saveBtn = document.getElementById('companion-modal-save');
            const cancelBtn = document.getElementById('companion-modal-cancel');
            if (!listEl || !addBtn || !modalOverlay || !saveBtn || !cancelBtn) return;

            // Click on list item (excluding delete button): load companion
            listEl.addEventListener('click', (e) => {
                const t = e.target && e.target.nodeType === 1 ? e.target : e.target && e.target.parentNode;
                const li = t && t.closest ? t.closest('li[data-companion-id]') : null;
                if (!li || (t && t.closest && t.closest('.companion-delete-btn'))) return;
                const id = li.getAttribute('data-companion-id');
                if (id) loadCompanion(id).catch(err => console.warn('Load companion failed:', err));
            });

            addBtn.addEventListener('click', () => {
                if (nameInput) nameInput.value = '';
                modalOverlay.style.display = 'flex';
                modalOverlay.setAttribute('aria-hidden', 'false');
                if (nameInput) nameInput.focus();
                renderCompanionList();
            });

            function closeCompanionModal() {
                modalOverlay.style.display = 'none';
                modalOverlay.setAttribute('aria-hidden', 'true');
            }

            cancelBtn.addEventListener('click', closeCompanionModal);
            modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeCompanionModal(); });

            const editSettingsLink = document.getElementById('companion-edit-settings-link');
            if (editSettingsLink) {
                editSettingsLink.addEventListener('click', () => {
                    closeCompanionModal();
                    const collapsible = document.querySelector('.collapsible');
                    const content = collapsible && collapsible.querySelector('.collapsible-content');
                    const btn = collapsible && collapsible.querySelector('.collapsible-btn');
                    if (content && btn) {
                        content.classList.add('active');
                        btn.classList.add('active');
                        btn.setAttribute('aria-expanded', 'true');
                        content.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                });
            }

            saveBtn.addEventListener('click', async () => {
                const name = (nameInput && nameInput.value || '').trim();
                if (!name) return;
                const settings = getToolSettingsFromDOM();
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
                    closeCompanionModal();
                    renderCompanionList();
                } catch (err) {
                    console.warn('Save companion failed:', err);
                }
            });
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
            if (ttsModelDropdown) ttsModelDropdown.addEventListener('change', saveToolSettings);
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
            
            console.log('Tool settings persistence enabled');
        }

        authLoginBtn?.addEventListener('click', () => performAuth('login'));
        authSignupBtn?.addEventListener('click', () => performAuth('signup'));
        authLogoutBtn?.addEventListener('click', () => {
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
            // Validate API key before making request
            const apiKey = apiKeyInput.value.trim();
            if (!apiKey || apiKey.length === 0) {
                // API key is missing, show error and exit
                console.error('API key is required for transcription');
                status.textContent = "Transcription failed: API key is missing. Please enter your API key.";
                return; // Exit early if API key is missing
            }
            
            // Use the proxy server endpoint which has CORS configured
            const whisperEndpoint = `${PROXY_BASE_URL}/v1/audio/transcriptions`;

            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');
            formData.append('model', 'whisper-1');

            try {
                console.log('Sending audio to Whisper...');
                const response = await fetch(whisperEndpoint, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${apiKey}`
                    },
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
                            errorMessage = "Transcription failed: Invalid or missing API key. Please check your API key.";
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

        // Storage helper functions
        function saveTodoList() {
            storage.setItem('todoList', JSON.stringify(todoList));
        }

        function saveMemory() {
            storage.setItem('memoryCache', JSON.stringify(memoryCache));
        }

        // Initialize variables
        let todoList = [];
        let memoryCache = [];
        let isToolRequest = false;
        let chatHistory = [];  // Single declaration of chatHistory

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
            const savedTodoList = storage.getItem('todoList');
            const savedMemoryCache = storage.getItem('memoryCache');
            
            if (savedTodoList) {
                todoList = JSON.parse(savedTodoList);
            }
            if (savedMemoryCache) {
                memoryCache = JSON.parse(savedMemoryCache);
            }
        } catch (error) {
            console.warn('Error loading from storage:', error);
        }

        // Replace the ToolManager with OpenAI-style tool definitions
        const tools = [
                {
                    type: "function",
                    function: {
                        name: "manageTodoList",
                        description: "Manages a persistent todo list with various operations (list, add, update, delete tasks)",
                        parameters: {
                            type: "object",
                            properties: {
                                action: {
                                    type: "string",
                                    enum: ["list", "add", "update", "delete", "clear"],
                                    description: "The action to perform on the todo list"
                                },
                                taskId: {
                                    type: "number",
                                    description: "The ID of the task (required for update and delete actions)"
                                },
                                taskDescription: {
                                    type: "string",
                                    description: "The description of the task (required for add and update actions)"
                                }
                            },
                            required: ["action"]
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
                    description: "Fetches and summarizes content from a website",
                    parameters: {
                        type: "object",
                        properties: {
                            url: {
                                type: "string",
                                description: "The URL of the website to scrape (must include http:// or https://)"
                            }
                        },
                        required: ["url"]
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
                    description: "Use this tool whenever the user wants to convert a PDF to PowerPoint, turn a PDF into a presentation, or create slides from a PDF. Call it with title and filename; if the user did not provide a PDF URL, omit pdfUrl and the user will be prompted to upload a PDF file. Do not reply in text—always invoke this tool for PDF-to-PowerPoint requests.",
                    parameters: {
                        type: "object",
                        properties: {
                            pdfUrl: {
                                type: "string",
                                description: "Optional. URL of the PDF (http/https). Omit when the user has not provided a URL—they will be prompted to upload a file."
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
                    name: "manageMemoryCache",
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
                    name: "saveToFile",
                    description: "Saves content to a file in the specified directory",
                    parameters: {
                        type: "object",
                        properties: {
                            filename: {
                                type: "string",
                                description: "The name of the file to save (e.g., 'latest_news.txt', 'data.csv')"
                            },
                            content: {
                                type: "string",
                                description: "The content to save to the file"
                            }
                        },
                        required: ["filename", "content"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "readFile",
                    description: "Reads content from a file",
                    parameters: {
                        type: "object",
                        properties: {
                            filename: {
                                type: "string",
                                description: "The name of the file to read"
                            }
                        },
                        required: ["filename"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "writeFile",
                    description: "Writes content to a file with an optional format",
                    parameters: {
                        type: "object",
                        properties: {
                            filename: {
                                type: "string",
                                description: "The name of the file to write"
                            },
                            content: {
                                type: "string",
                                description: "The content to write to the file"
                            },
                            format: {
                                type: "string",
                                description: "Optional format of the content (e.g., 'text', 'json')"
                            }
                        },
                        required: ["filename", "content"]
                    }
                }
            },
            {
                type: "function",
                function: {
                    name: "listFiles",
                    description: "Lists files in the scratch directory",
                    parameters: {
                        type: "object",
                        properties: {},
                        required: []
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
            }
        ];

        // Add the new handler function before executeToolCall
        async function handleSaveToFile({ filename, content }) {
            try {
                // Construct the full path
                // const savePath = `C:\\Users\\andyjm\\scratch\\${filename}`;
                
                // Create a Blob with the content
                const blob = new Blob([content], { type: 'text/plain' });
                
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
                    message: `Content has been saved to ${filename}` 
                };
            } catch (error) {
                console.error('Save to file error:', error);
                return { 
                    success: false, 
                    message: `Error saving file: ${error.message}` 
                };
            }
        }

        // Handler for reading files from the scratch directory
        async function handleReadFile({ filename }) {
            try {
                // Call the proxy server to read the file
                const response = await fetch(`${PROXY_BASE_URL}/v1/files/read`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ filename })
                });

                // Parse the response
                const result = await response.json();

                // Return the result
                if (result.success) {
                    return {
                        success: true,
                        message: result.message,
                        content: result.data.content,
                        type: result.data.type
                    };
                } else {
                    return {
                        success: false,
                        message: result.message
                    };
                }
            } catch (error) {
                // Handle network or parsing errors
                console.error('Read file error:', error);
                return {
                    success: false,
                    message: `Error reading file: ${error.message}. Make sure the proxy server is running on port 8002.`
                };
            }
        }

        // Handler for writing files to the scratch directory
        async function handleWriteFile({ filename, content, format }) {
            try {
                // Default format to txt if not specified
                if (!format) {
                    format = 'txt';
                }

                // Call the proxy server to write the file
                const response = await fetch(`${PROXY_BASE_URL}/v1/files/write`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ filename, content, format })
                });

                // Parse the response
                const result = await response.json();

                // Return the result
                if (result.success) {
                    return {
                        success: true,
                        message: result.message,
                        filepath: result.data?.filepath,
                        size: result.data?.size
                    };
                } else {
                    return {
                        success: false,
                        message: result.message
                    };
                }
            } catch (error) {
                // Handle network or parsing errors
                console.error('Write file error:', error);
                return {
                    success: false,
                    message: `Error writing file: ${error.message}. Make sure the proxy server is running on port 8002.`
                };
            }
        }

        // Handler for listing files in the scratch directory
        async function handleListFiles() {
            try {
                // Call the proxy server to list files
                const response = await fetch(`${PROXY_BASE_URL}/v1/files/list`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                // Parse the response
                const result = await response.json();

                // Return the result
                if (result.success) {
                    const files = result.files || [];
                    const count = typeof result.count === 'number' ? result.count : files.length;
                    const scratchDir = result.scratch_dir;
                    const content = files.length > 0
                        ? files
                            .map((file, index) => `${index + 1}. ${file.name} (${file.size} bytes)`)
                            .join('\n')
                        : 'No files found in the scratch directory.';

                    return {
                        success: true,
                        message: `Found ${count} file${count === 1 ? '' : 's'} in the scratch directory.`,
                        files,
                        count,
                        scratch_dir: scratchDir,
                        content
                    };
                }

                return {
                    success: false,
                    message: result.message
                };
            } catch (error) {
                // Handle network or parsing errors
                console.error('List files error:', error);
                return {
                    success: false,
                    message: `Error listing files: ${error.message}. Make sure the proxy server is running on port 8002.`
                };
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

                let result;
                switch (name) {
                    case "manageTodoList":
                        result = await handleTodoList(args);
                        break;
                    case "scrapeWebsite":
                        result = await handleWebScraping(args);
                        break;
                    case "webSearch":
                        result = await handleWebSearch(args);
                        break;
                    case "manageMemoryCache":
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
                    case "llmQuery":
                        result = await handleLLMQuery(args, context);
                        break;
                    case "saveToFile":
                        result = await handleSaveToFile(args);
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
                        // Tool not found
                        result = {
                            success: false,
                            message: `Unknown tool: ${name}`
                        };
                        break;
                }
                console.log('executeToolCall - Result:', result);
                return result;
            } catch (error) {
                console.error('executeToolCall - Error:', error);
                throw error;
            }
        }


        // Individual tool handlers
        async function handleTodoList({ action, taskId, taskDescription }) {
                    try {
                        switch (action) {
                            case "list":
                                if (todoList.length === 0) {
                            return { success: true, message: "Your todo list is empty." };
                        }
                        const taskList = todoList.map((task, index) => `${index + 1}. ${task}`).join('\n');
                        return { success: true, message: "Here are your current tasks:\n" + taskList };

                            case "add":
                                if (!taskDescription) {
                            return { success: false, message: "Task description is required." };
                                }
                                todoList.push(taskDescription);
                        saveTodoList();
                        return { success: true, message: `Added task: ${taskDescription}` };

                            case "update":
                                if (!taskId || !taskDescription) {
                            return { success: false, message: "Both task ID and new description are required." };
                                }
                                if (taskId < 1 || taskId > todoList.length) {
                            return { success: false, message: "Invalid task ID." };
                                }
                                const oldTask = todoList[taskId - 1];
                                todoList[taskId - 1] = taskDescription;
                        saveTodoList();
                        return { success: true, message: `Updated task ${taskId} from "${oldTask}" to "${taskDescription}"` };

                            case "delete":
                                if (!taskId) {
                            return { success: false, message: "Task ID is required." };
                                }
                                if (taskId < 1 || taskId > todoList.length) {
                            return { success: false, message: "Invalid task ID." };
                                }
                                const deletedTask = todoList.splice(taskId - 1, 1)[0];
                        saveTodoList();
                        return { success: true, message: `Deleted task: ${deletedTask}` };

                            case "clear":
                                todoList = [];
                        saveTodoList();
                        return { success: true, message: "Todo list has been cleared." };

                            default:
                        return { success: false, message: "Invalid action." };
                        }
                    } catch (error) {
                        console.error('Todo list operation error:', error);
                return { success: false, message: `Error: ${error.message}` };
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
                const response = await fetch(`${PROXY_BASE_URL}/v1/memory/store`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        category: category || "general",
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

        async function handleSearchMemories({ query, limit }) {
            try {
                const response = await fetch(`${PROXY_BASE_URL}/v1/memory/search`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        limit: limit || 5,
                        similarity_threshold: 0.5  // Lower threshold for better recall
                    })
                });
                const data = await response.json();
                if (data.success && data.data.memories) {
                    const memories = data.data.memories;
                    if (memories.length === 0) {
                        return { success: true, message: "No relevant memories found." };
                    }
                    const memoryList = memories.map((mem, i) => 
                        `${i + 1}. ${mem.text} (similarity: ${(mem.similarity * 100).toFixed(1)}%)`
                    ).join('\n');
                    return { success: true, message: `Found ${memories.length} relevant memories:\n${memoryList}` };
                } else {
                    return { success: false, message: data.message || "Failed to search memories" };
                }
            } catch (error) {
                return { success: false, message: `Error searching memories: ${error.message}` };
            }
        }

        // Detect if a question is asking for opinion/knowledge vs an action
        function isOpinionOrKnowledgeQuestion(prompt) {
            // Convert to lowercase for case-insensitive matching
            const lowerPrompt = prompt.toLowerCase().trim();
            
            // Patterns that indicate opinion/knowledge questions
            const opinionKnowledgePatterns = [
                /what\s+(do\s+you\s+)?think\s+(about|of)/i,
                /what'?s\s+(your\s+)?(opinion|view|perspective|take|thoughts?)\s+(on|about|of|regarding)/i,
                /what\s+(do\s+you\s+)?know\s+(about|of)/i,
                /what\s+(are\s+your\s+)?(thoughts?|views?|beliefs?|ideas?)\s+(on|about|of|regarding)/i,
                /how\s+do\s+you\s+(feel|see|view|perceive)\s+(about|on|regarding)/i,
                /tell\s+me\s+(what\s+you\s+)?(think|know|believe|feel)\s+(about|of|on)/i,
                /what\s+(is|are)\s+your\s+(thoughts?|views?|opinions?|beliefs?|ideas?|insights?)\s+(on|about|of|regarding)/i,
                /share\s+(your\s+)?(thoughts?|views?|opinions?|perspective)/i,
                /what\s+(do\s+you\s+)?(believe|understand|consider)\s+(about|of|regarding)/i,
                /what\s+(are\s+your\s+)?(insights?|reflections?|contemplations?)\s+(on|about|of|regarding)/i
            ];
            
            // Patterns that indicate action-oriented questions (skip memory search)
            const actionPatterns = [
                /(search|find|look\s+up|get|fetch|retrieve)\s+(for|information\s+about|details\s+about)/i,
                /how\s+much\s+(does|do|is|are|cost)/i,
                /what'?s\s+the\s+(weather|price|cost|temperature|time)/i,
                /(show|display|list|give\s+me)\s+(me\s+)?(information|data|details|results)/i,
                /(calculate|compute|determine|find\s+out)\s+(the\s+)?(cost|price|value|amount|total)/i,
                /(navigate|go\s+to|visit|open|browse)/i,
                /(read|write|save|load|upload|download)\s+(the\s+)?(file|document|data)/i,
                /(create|make|build|generate|produce)\s+(a|an|the)/i,
                /(run|execute|perform|do)\s+(a|an|the)/i
            ];
            
            // Check for action patterns first (higher priority)
            for (const pattern of actionPatterns) {
                if (pattern.test(lowerPrompt)) {
                    return false; // This is an action question, not opinion/knowledge
                }
            }
            
            // Check for opinion/knowledge patterns
            for (const pattern of opinionKnowledgePatterns) {
                if (pattern.test(lowerPrompt)) {
                    return true; // This is an opinion/knowledge question
                }
            }
            
            // Default: if it starts with "what do you" or "what's your", treat as opinion/knowledge
            if (/^what\s+(do\s+you|'?s\s+your)/i.test(lowerPrompt)) {
                return true;
            }
            
            // Default to false (action-oriented) if no patterns match
            return false;
        }

        // Automatically search memories for opinion/knowledge questions (when not in philosopher mode)
        async function autoSearchMemoriesForQuestion(prompt) {
            // Only auto-search if not in philosopher mode
            if (philosopherModeActive) {
                return null; // Skip auto-search in philosopher mode
            }
            
            // Check if this is an opinion/knowledge question
            if (!isOpinionOrKnowledgeQuestion(prompt)) {
                return null; // Skip auto-search for action questions
            }
            
            try {
                // Extract topic from the question for better search
                // Try to extract the main topic after common question patterns
                let searchQuery = prompt;
                const topicMatch = prompt.match(/(?:think|opinion|view|know|thoughts?|beliefs?|feel|see|perceive|understand|consider|insights?|reflections?|contemplations?)\s+(?:about|of|on|regarding)\s+(.+?)(?:\?|$)/i);
                if (topicMatch && topicMatch[1]) {
                    searchQuery = topicMatch[1].trim();
                }
                
                // Search memories
                const result = await handleSearchMemories({ query: searchQuery, limit: 5 });
                
                if (result.success && result.message && result.message !== "No relevant memories found.") {
                    // Return the memory context string
                    return result.message;
                }
                
                return null; // No memories found or error
            } catch (error) {
                console.warn('Auto memory search failed:', error);
                return null; // Fail silently, don't block the request
            }
        }

        async function handleListMemories({ limit }) {
            try {
                const limitParam = limit ? `?limit=${limit}` : '';
                const response = await fetch(`${PROXY_BASE_URL}/v1/memory/list${limitParam}`, {
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
                const response = await fetch(`${PROXY_BASE_URL}/v1/memory/${memory_id}`, {
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
                const response = await fetch(`${PROXY_BASE_URL}/v1/memory/extract`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: recentMessages,
                        max_memories: 3
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

        async function handleNavigation({ url }) {
            try {
                const urlObj = new URL(url);
                if (confirm(`Would you like to open ${url}?`)) {
                    window.open(url, '_blank');
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
                if (confirm(`Would you like to open Teams chat?`)) {
                            window.open(url, '_blank');
                    return { success: true, message: "Teams chat has been opened" };
                }
                return { success: false, message: "Teams chat opening was cancelled." };
            } catch (error) {
                console.error('Teams chat error:', error);
                return { success: false, message: "Invalid Teams URL" };
            }
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
                
                // Evaluate the expression
                const result = eval(cleanExpression);
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
                    protocol: protocol || window.location.protocol
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
                const filename = `${timestamp}_autogen_response.txt`;

                const writeResult = await handleWriteFile({
                    filename,
                    content: result,
                    format: 'txt'
                });

                if (!writeResult.success) {
                    console.warn('Failed to persist AutoGen response:', writeResult.message);
                }

                return { success: true, message: "The workflow has completed. Please review the output." };
            } catch (error) {
                console.error('Workflow error:', error);
                return { success: false, message: `Error: ${error.message}` };
            }
        }

        // Add this new handler function for web scraping
        async function handleWebScraping({ url }) {
            try {
                // Reject 'pending' or invalid URLs so chain step fails clearly instead of throwing
                if (!url || url === 'pending' || !url.startsWith('http')) {
                    return {
                        success: false,
                        message: 'No URL available from previous step. Run a web search first, or specify a URL to scrape.'
                    };
                }
                const urlObj = new URL(url);
                // Use POST for proxy fetch to avoid URL length limits on iOS Safari and improve reliability
                const proxyUrl = `${PROXY_BASE_URL}/v1/proxy/fetch`;
                const response = await fetch(proxyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ url: url })
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
                    body: JSON.stringify({
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
                    })
                });

                const summaryData = await summaryResponse.json();
                if (summaryData.choices && summaryData.choices.length > 0) {
                    const summary = summaryData.choices[0].message.content;
                            return { 
                                success: true, 
                        message: `Summary of ${url}:\n\n${summary}` 
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

        // Add this function to parse both XML-style and JSON tool responses
        function parseToolResponse(content) {
            console.log('Parsing tool response:', content);

            // Ignore any <tool> tags that occur inside fenced code blocks
            // This prevents example snippets from being executed as real tool calls
            const contentWithoutCode = typeof content === 'string'
                ? content.replace(/```[\s\S]*?```/g, '')
                : content;

            // Try XML format first, but only if tags appear at top-level content
            const toolMatch = contentWithoutCode.match(/<tool>(.*?)<\/tool>/);
            const paramsMatch = contentWithoutCode.match(/<parameters>([\s\S]*?)<\/parameters>/);
            
            if (toolMatch && paramsMatch) {
                try {
                    const toolName = toolMatch[1].trim();
                    const parameters = JSON.parse(paramsMatch[1].trim());
                    console.log('Successfully parsed XML format:', { toolName, parameters });
                    return {
                        function: {
                            name: toolName,
                            arguments: JSON.stringify(parameters)
                        }
                    };
                } catch (error) {
                    console.error('Error parsing XML tool response:', error);
                }
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
                    /(delete|remove|clear) (?:the )?(?:todo|task|item|reminder|note)(?: number )?(\d+)?/i,
                    /(show|list|display|get) (?:all )?(?:my )?(?:todo|task|item|reminder|note)s?(?:list)?/i
                ],
                extractArgs: (match) => {
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
            manageMemoryCache: {
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
            saveToFile: {
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
                                body: JSON.stringify({
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
                                })
                            });
                            const data = await response.json();
                            content = data.choices[0].message.content;
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
                case 'saveToFile':
                    // Re-extract args with async support
                    for (const pattern of TOOL_PATTERNS.saveToFile.patterns) {
                        const match = task.originalText.match(pattern);
                        if (match) {
                            const newArgs = await TOOL_PATTERNS.saveToFile.extractArgs(match, context);
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
                case 'manageMemoryCache':
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
        async function fetchOpenAIResponse(promptText) {
            // Validate promptText parameter
            if (!promptText || typeof promptText !== 'string') {
                console.error('fetchOpenAIResponse called with invalid promptText:', promptText);
                status.textContent = "Error: Invalid input text. Please try again.";
                return;
            }
            
            // Trim and validate the prompt text
            promptText = promptText.trim();
            if (promptText.length === 0) {
                console.error('fetchOpenAIResponse called with empty promptText');
                status.textContent = "Error: Empty input text. Please try again.";
                return;
            }
            
            console.log('fetchOpenAIResponse called with promptText:', promptText); // Debug log
            
            let endpoint = endpointInput.value;
            const apiKey = apiKeyInput.value.trim();
            
            // Store the original endpoint for proxy routing
            const originalEndpoint = endpoint;

            // Initialize context object for both single and chained tool calls
            const context = {
                searchResults: [],
                urls: [],
                variables: new Map(),
                previousResults: []
            };

            // Check for tool chaining before proceeding with normal processing
            const hasChaining = promptText.toLowerCase().includes('then') || 
                               promptText.match(/first.*second|1st.*2nd|step.*step/i);

            if (hasChaining) {
                console.log('Detected task chaining in prompt');
                const tasks = await extractTasks(promptText);
                
                if (tasks.length > 1) {
                    console.log('Executing task chain:', tasks);
                    const chainResult = await processToolChain(tasks);
                    
                    chatHistory.push({
                        role: 'assistant',
                        content: chainResult
                    });
                    
                    responseOutput.value = chainResult;
                    addMessageToHistory('assistant', chainResult); // Add to message history
                    textToSpeech(chainResult);
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

To use a tool, you MUST ALWAYS respond in this EXACT format:
<tool>tool_name</tool>
<parameters>
{
    "parameter1": "value1",
    "parameter2": "value2"
}
</parameters>

IMPORTANT: Always use the XML-style format shown above. Never return raw JSON or other formats.

Available tools:

1. manageTodoList
Description: Manages a todo list
Parameters:
{
    "action": "list|add|update|delete|clear",
    "taskId": "number (for update/delete)",
    "taskDescription": "string (for add/update)"
}

2. manageMemoryCache
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

7. scrapeWebsite
Description: Fetches and summarizes content from a website
Parameters:
{
    "url": "string (must include http:// or https://)"
}

8. webSearch
Description: Searches the web for information about a topic and returns relevant results
Parameters:
{
    "query": "string (the search query or keywords to look for)"
}

9. fetchNews
Description: Fetches news articles matching given keywords and saves them to a CSV file
Parameters:
{
    "searchTerm": "string (keywords to search the news for)",
    "filename": "string (CSV filename to save to)"
}

10. pdfToPowerPoint
Description: Use this tool whenever the user wants to convert a PDF to PowerPoint, turn a PDF into a presentation, or create slides from a PDF. Always call the tool—do not reply in text. If the user provides a PDF URL, include pdfUrl; if they do not, omit pdfUrl and the user will be prompted to upload a file. Required: title, filename.
Parameters:
{
    "pdfUrl": "string (optional; include only when user provides a URL; if omitted, user is prompted to upload)",
    "title": "string (required; presentation title)",
    "author": "string (optional)",
    "maxSlides": "number (optional; default 15)",
    "filename": "string (required; e.g. 'presentation.pptx')"
}

11. uploadToGoogleDrive
Description: Uploads a file from the scratch directory to Google Drive using service account authentication. Use the filename relative to the scratch directory.
Parameters:
{
    "filePath": "string (filename relative to scratch directory, e.g. report.docx or climate_updates.csv)",
    "fileName": "string (optional custom name for the file in Drive)"
}

12. readFile
Description: Reads a file from the scratch directory. Supports txt, docx, xlsx, pdf, and png formats.
Parameters:
{
    "filename": "string (name of the file to read from the scratch directory)"
}

13. listFiles
Description: Lists all files currently available in the scratch directory. No parameters are required.
Parameters:
{
}

14. writeFile
Description: Writes content to a file in the scratch directory. Supports txt, docx, xlsx, and pdf formats.
Parameters:
{
    "filename": "string (name of the file to write)",
    "content": "string (content to write to the file)",
    "format": "string (optional: txt|docx|xlsx|pdf, defaults to txt)"
}

Examples:
User: "Remember to buy milk"
Assistant: <tool>manageMemoryCache</tool>
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
Assistant: <tool>readFile</tool>
<parameters>
{
    "filename": "report.txt"
}
</parameters>

User: "List the files in the scratch directory"
Assistant: <tool>listFiles</tool>
<parameters>
{
}
</parameters>

User: "Write a summary to summary.docx"
Assistant: <tool>writeFile</tool>
<parameters>
{
    "filename": "summary.docx",
    "content": "This is a comprehensive summary of the report...",
    "format": "docx"
}
</parameters>

User: "Turn this PDF into a PowerPoint: https://example.com/report.pdf. Title it 'Quarterly Report' and save as report.pptx"
Assistant: <tool>pdfToPowerPoint</tool>
<parameters>
{
    "pdfUrl": "https://example.com/report.pdf",
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

IMPORTANT REMINDER: Always wrap your tool responses in <tool> and <parameters> tags as shown in the examples above. Never return raw JSON.

Current memory cache contents:
${memoryCache.map((item, index) => `${index + 1}. ${item}`).join('\n')}`;
            
            // Preserve existing system prompt by default; user input overrides it
            let effectiveSystemPrompt = systemPromptInput.value.trim() || systemPrompt;
            
            // Prepend context: timezone and knowledge-gap awareness (always applies)
            const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            const contextBlock = `Context: You are running in timezone ${userTimezone}. Use this when interpreting dates/times unless the user specifies otherwise.
Knowledge awareness: Your training has a cutoff. Acknowledge your knowledge gap; do not assume the current year or recent events. When the user provides current facts, corrections, or information that differs from your training (e.g., "it's 2025 now", "that API changed"), accept them as authoritative and do not contradict them.

`;
            effectiveSystemPrompt = contextBlock + effectiveSystemPrompt;
            
            // Get user name from tool settings and add to system prompt
            // This works whether using custom prompt or default prompt
            const userName = userNameInput.value.trim() || 'User';
            if (userName && userName !== 'User') {
                // Prepend user name info to the system prompt (works with both custom and default)
                effectiveSystemPrompt = `The user you are talking to is named ${userName}.\n\n${effectiveSystemPrompt}`;
            }
            
            // Automatically search memories for opinion/knowledge questions (when not in philosopher mode)
            let memoryContext = null;
            if (!philosopherModeActive) {
                memoryContext = await autoSearchMemoriesForQuestion(promptText);
                if (memoryContext) {
                    // Add memory context to system prompt
                    effectiveSystemPrompt += `\n\nRelevant context from previous conversations:\n${memoryContext}\n\nUse this context to provide more personalized and relevant responses based on what you've discussed before.`;
                }
            }
            
            const messages = [
                { 
                    role: 'system', 
                    content: effectiveSystemPrompt
                },
                ...(isToolRequest ? [] : chatHistory),
                {
                    role: 'user',
                    content: promptText
                }
            ];

            // Track if clipboard content was used (store in a way that persists through async operations)
            const hadClipboardContent = clipboardData && clipboardVisionEnabled;
            const clipboardContentType = clipboardType; // Store type before potential clearing
            
            // Add image content if present
            if (clipboardData && clipboardType === 'image' && clipboardVisionEnabled) {
                const base64Image = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(clipboardData);
                });
                
                messages.push({
                    role: 'user',
                    content: [
                        {
                            type: 'image_url',
                            image_url: {
                                url: `data:image/jpeg;base64,${base64Image}`,
                                detail: 'auto'
                            }
                        }
                    ]
                });
            }
            // Add text content if present (prepend to user message)
            else if (clipboardData && clipboardType === 'text' && clipboardVisionEnabled) {
                // Prepend clipboard text to the user's message
                const originalPrompt = messages[messages.length - 1].content;
                messages[messages.length - 1].content = `[Clipboard content: ${clipboardData}]\n\n${originalPrompt}`;
            }

            const body = {
                model: getCurrentModel(),
                messages: messages,
                max_tokens: 4096,
                temperature: 0.7,
                stream: false,
                // Provide tools per LM Studio tool-use docs
                tools: tools,
                tool_choice: 'auto'
            };

            // Add user message to history before sending
            console.log('Adding user message to history with content:', promptText); // Debug log
            addMessageToHistory('user', promptText);
            
            try {
                // Add pulsing effect to indicate we are waiting for the API
                responseOutput.classList.add('responding');
                messageHistory.classList.add('responding'); // Add pulsing effect to message history
                console.log('Sending request:', {
                    endpoint,
                    model: getCurrentModel(),
                    prompt: promptText
                });
                console.log('Full request:', JSON.stringify(body, null, 2));
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify(body)
                });

                const data = await response.json();
                console.log('Response from LLM:', JSON.stringify(data, null, 2));

                if (data.choices && data.choices.length > 0) {
                    const message = data.choices[0].message;
                    console.log('Processing message:', message);

                    // Handle LM Studio/OpenAI function/tool calling first
                    if (message.tool_calls && Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
                        try {
                            // Add the assistant's tool call turn to messages
                            messages.push({ role: 'assistant', tool_calls: message.tool_calls });

                            // Execute each tool call and push results
                            for (const tc of message.tool_calls) {
                                const toolResult = await executeToolCall(tc, context);
                                
                                // Format the tool result content properly
                                let toolResultContent;
                                if (typeof toolResult === 'string') {
                                    toolResultContent = toolResult;
                                } else if (toolResult.content) {
                                    // If the tool result has content (like from readFile), include it in a readable format
                                    toolResultContent = `${toolResult.message}\n\nContent:\n${toolResult.content}`;
                                } else {
                                    // Otherwise, just stringify the result
                                    toolResultContent = JSON.stringify(toolResult);
                                }
                                
                                messages.push({
                                    role: 'tool',
                                    content: toolResultContent,
                                    tool_call_id: tc.id
                                });
                            }

                            // Follow-up request to get the final assistant response after tool execution
                            const followupResponse = await fetch(endpoint, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': `Bearer ${apiKey}`
                                },
                                body: JSON.stringify({
                                    model: getCurrentModel(),
                                    messages: messages,
                                    max_tokens: 4096,
                                    temperature: 0.7,
                                    tools: tools,
                                    tool_choice: 'auto'
                                })
                            });
                            const followupData = await followupResponse.json();
                            const finalMsg = followupData?.choices?.[0]?.message?.content || '';
                            const finalContent = stripThinkTags(finalMsg);
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmLoveVrmaAction.stop();
                                        vrmLoveVrmaAction.reset();
                                        vrmLoveVrmaAction.setEffectiveWeight(1.0);
                                        vrmLoveVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmLoveVrmaAction.enabled = true;
                                        vrmLoveVrmaAction.play();
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
                                            vrmLoveVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmThinkVrmaAction.stop();
                                        vrmThinkVrmaAction.reset();
                                        vrmThinkVrmaAction.setEffectiveWeight(1.0);
                                        vrmThinkVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmThinkVrmaAction.enabled = true;
                                        vrmThinkVrmaAction.play();
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
                                            vrmThinkVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmCryVrmaAction.stop();
                                        vrmCryVrmaAction.reset();
                                        vrmCryVrmaAction.setEffectiveWeight(1.0);
                                        vrmCryVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmCryVrmaAction.enabled = true;
                                        vrmCryVrmaAction.play();
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
                                            vrmCryVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmAngryVrmaAction.stop();
                                        vrmAngryVrmaAction.reset();
                                        vrmAngryVrmaAction.setEffectiveWeight(1.0);
                                        vrmAngryVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmAngryVrmaAction.enabled = true;
                                        vrmAngryVrmaAction.play();
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
                                            vrmAngryVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                const lastToolMsg = messages.slice().reverse().find(m => m.role === 'tool')?.content;
                                let confirmText = '';
                                try {
                                    const parsed = typeof lastToolMsg === 'string' ? JSON.parse(lastToolMsg) : lastToolMsg;
                                    confirmText = parsed?.message || '';
                                } catch (_) {
                                    confirmText = typeof lastToolMsg === 'string' ? lastToolMsg : '';
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
                            return;
                        } catch (toolErr) {
                            console.error('Error handling tool calls via LM Studio/OpenAI format:', toolErr);
                            // Fall back to legacy handling below
                        }
                    }

                    const rawContent = message.content || '';
                    const cleanContent = stripThinkTags(rawContent);
                    if (cleanContent) {
                        // Check for tool calls in Qwen's XML format
                        const toolCall = parseToolResponse(cleanContent);
                        if (toolCall) {
                            console.log('Tool call detected:', toolCall);
                            try {
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
                                        const contentMessage = `File content from ${toolName === 'readFile' ? 'reading the file' : 'the operation'}:\n\n${result.content}\n\nBased on this content, please respond to the user's request.`;
                                        
                                        // Add tool result to chat history
                                        chatHistory.push({
                                            role: 'user',
                                            content: contentMessage
                                        });
                                        
                                        // Make a follow-up call to let the LLM respond based on the file content
                                        try {
                                            const followupResponse = await fetch(endpoint, {
                                                method: 'POST',
                                                headers: {
                                                    'Content-Type': 'application/json',
                                                    'Authorization': `Bearer ${apiKey}`
                                                },
                                                body: JSON.stringify({
                                                    model: getCurrentModel(),
                                                    messages: chatHistory,
                                                    temperature: 0.7
                                                })
                                            });
                                            
                                            const followupData = await followupResponse.json();
                                            if (followupData.choices && followupData.choices.length > 0) {
                                                const followupMessage = followupData.choices[0].message;
                                                const followupContent = stripThinkTags(followupMessage.content || '');
                                                
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
                            // If user asked to convert PDF to PowerPoint but the LLM replied in text, show upload widget in chat
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmLoveVrmaAction.stop();
                                        vrmLoveVrmaAction.reset();
                                        vrmLoveVrmaAction.setEffectiveWeight(1.0);
                                        vrmLoveVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmLoveVrmaAction.enabled = true;
                                        vrmLoveVrmaAction.play();
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
                                            vrmLoveVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmThinkVrmaAction.stop();
                                        vrmThinkVrmaAction.reset();
                                        vrmThinkVrmaAction.setEffectiveWeight(1.0);
                                        vrmThinkVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmThinkVrmaAction.enabled = true;
                                        vrmThinkVrmaAction.play();
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
                                            vrmThinkVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmCryVrmaAction.stop();
                                        vrmCryVrmaAction.reset();
                                        vrmCryVrmaAction.setEffectiveWeight(1.0);
                                        vrmCryVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmCryVrmaAction.enabled = true;
                                        vrmCryVrmaAction.play();
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
                                            vrmCryVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                                        // Stop idle animation if playing
                                        if (vrmIdleVrmaAction && vrmIdleVrmaAction.isRunning()) {
                                            vrmIdleVrmaAction.stop();
                                        }
                                        vrmAngryVrmaAction.stop();
                                        vrmAngryVrmaAction.reset();
                                        vrmAngryVrmaAction.setEffectiveWeight(1.0);
                                        vrmAngryVrmaAction.setEffectiveTimeScale(1.0);
                                        vrmAngryVrmaAction.enabled = true;
                                        vrmAngryVrmaAction.play();
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
                                            vrmAngryVrmaAction.fadeOut(0.8); // Fade out over 0.8 seconds
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
                } else {
                    // No choices returned; ensure UI is not left waiting
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
                            
                            // Automatically extract memories from conversation (async, non-blocking)
                            extractMemoriesFromConversation().catch(err => {
                                console.warn('Memory extraction failed:', err);
                            });
                            
                            textToSpeech(fallbackText);
                        }
                    }
                }
            } catch (error) {
                console.error('Error:', error);
                responseOutput.value = `Error: ${error.message}. Please try again.`;
                addMessageToHistory('assistant', `Error: ${error.message}. Please try again.`); // Add to message history
            } finally {
                responseOutput.classList.remove('responding');
                messageHistory.classList.remove('responding'); // Remove pulsing effect from message history
            }
        }

        // Shared send logic so mobile paper-airplane button can call it directly (fixes iOS Safari programmatic click)
        window.submitUserMessage = async function () {
            // Check for philosopher mode trigger phrase
            const promptText = userInput.value.trim();
            if (promptText && detectPhilosopherModeTrigger(promptText)) {
                await startPhilosopherMode();
                userInput.value = ''; // Clear input
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
            if (userText.trim() === '') { // Check if input is empty
                alert('Please enter some text or record your voice.'); // Show alert if empty
                return; // Exit early
            } // End empty check

            // Note: fetchOpenAIResponse will add the user message to history, so we don't add it here
            fetchOpenAIResponse(userText); // Send message to OpenAI API (this will add user message to history)

            // Add deactivation message after user message if we stopped philosopher mode
            // This appears after the user message since fetchOpenAIResponse adds it synchronously at the start
            if (shouldStopPhilosopher) {
                addMessageToHistory('assistant', 'Philosopher Mode deactivated.');
            }
            userInput.value = ''; // Clear input field
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
                    return; // Don't send as regular message
                }

                // If philosopher mode is active or starting, and user sends a message, stop philosopher mode (interruption)
                const shouldStopPhilosopher = (philosopherModeActive || philosopherModeStarting) && userText.trim();
                if (shouldStopPhilosopher) {
                    // Stop philosopher mode but skip message display - we'll add it after the user message
                    await stopPhilosopherMode(true); // Pass true to skip message display
                }
                
                if (userText.trim() !== '') { // Check if input is not empty
                    // Note: fetchOpenAIResponse will add the user message to history, so we don't add it here
                    fetchOpenAIResponse(userText); // Send message to OpenAI API (this will add user message to history)
                    
                    // Add deactivation message after user message if we stopped philosopher mode
                    // This appears after the user message since fetchOpenAIResponse adds it synchronously at the start
                    if (shouldStopPhilosopher) {
                        addMessageToHistory('assistant', 'Philosopher Mode deactivated.');
                    }
                    
                    userInput.value = ''; // Clear input field
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
                
                // Ensure the canvas stays in DOM; create PIXI Application with responsive dimensions
                const app = new PIXI.Application({
                    view: canvas,
                    transparent: true,
                    autoStart: true,
                    width: container.clientWidth,
                    height: container.clientHeight
                });

                // Initialize Live2D
                // Register ticker only once to avoid duplicate RAF workloads
                if (!live2dTickerRegistered) {
                    await PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);
                    live2dTickerRegistered = true;
                }

                // Resolve model path to absolute URL for remote access
                const resolvedModelPath = resolveModelPath(modelPath);
                console.log(`Loading Live2D model from: ${resolvedModelPath} (original: ${modelPath})`);
                
                // Load model
                const model = await PIXI.live2d.Live2DModel.from(resolvedModelPath, {
                    autoInteract: false,
                    focus: false
                });
                
                // Clear stage and add the fresh model to stage
                app.stage.removeChildren();
                app.stage.addChild(model);

                // Function to resize model
                const resizeModel = () => {
                    app.renderer.resize(container.clientWidth, container.clientHeight);
                    
                    // Increase scale for a closer view
                    const scale = Math.min(
                        container.clientWidth / (model.width * 1.5),  // Changed from 1.2 to 0.8
                        container.clientHeight / (model.height * 1.5)  // Changed from 1.2 to 0.8
                    ) * 2.5;  // Multiply by 1.5 to make it 50% larger
                    
                    model.scale.set(scale);
                    model.x = container.clientWidth / 2;
                    // Base vertical placement (upper body focus), then apply per-model offset (px)
                    const baseY = container.clientHeight / 1.4;
                    const offsetPx = live2dOffsets[modelPath] ?? 0;
                    model.y = baseY + offsetPx;
                };

                // Center the model
                model.anchor.set(0.5, 0.4);
                
                // Initial resize
                resizeModel();

                // Add resize handler (debounced) and store app on model instance for cleanup
                const debouncedResize = (() => {
                    let raf = null;
                    return () => {
                        if (raf) cancelAnimationFrame(raf);
                        raf = requestAnimationFrame(resizeModel);
                    };
                })();
                window.addEventListener('resize', debouncedResize);
                // Store references for proper cleanup when switching models
                model.__app = app;
                model.__resizeHandler = debouncedResize;

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
                console.log('Live2D model loaded successfully');
                
                // Initialize and test expressions
                await initializeLive2DExpressions(model);

            } catch (error) {
                console.error('Failed to load Live2D model:', error);
            }
        }

        // Helper to safely cleanup existing Live2D resources before switching models
        function cleanupLive2D() {
            try {
                if (!live2dModel) return;
                // Remove resize listener if present
                if (live2dModel.__resizeHandler) {
                    window.removeEventListener('resize', live2dModel.__resizeHandler);
                }
                // Destroy PIXI application if stored
                if (live2dModel.__app) {
                    // Guard against undefined destroy options inside PIXI
                    try {
                        // Do NOT remove the canvas view from the DOM; keep removeView=false
                        live2dModel.__app.destroy(false, { children: true, texture: true, baseTexture: true });
                    } catch {}
                }
                // Destroy Live2D model if possible
                if (typeof live2dModel.destroy === 'function') {
                    try {
                        live2dModel.destroy({ children: true, texture: true, baseTexture: true });
                    } catch {}
                }
            } catch (err) {
                console.warn('cleanupLive2D encountered an issue:', err);
            } finally {
                live2dModel = null;
            }
        }

        // VRM Functions
        function cleanupVRM() {
            try {
                if (!vrmModel) return;

            // Stop and uncache animation bindings
            try {
                if (vrmMixer && vrmModel && vrmModel.scene) {
                    vrmMixer.stopAllAction();
                    vrmMixer.uncacheRoot(vrmModel.scene);
                }
            } catch (_) {}

            if (vrmScene) {
                vrmScene.traverse((child) => {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(material => material.dispose());
                        } else {
                            child.material.dispose();
                        }
                    }
                });
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
            if (vrmBlinkTimeout) { try { clearTimeout(vrmBlinkTimeout); } catch (_) {} vrmBlinkTimeout = null; }
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
            try {
                const container = document.getElementById('vrm-container');
                const canvas = document.getElementById('vrm-canvas');
                if (!container || !canvas) {
                    console.warn('VRM container/canvas not found. Skipping init.');
                    return;
                }

                // Ensure a valid .vrm path is selected
                if (!currentVRMModelPath || !currentVRMModelPath.toLowerCase().endsWith('.vrm')) {
                    throw new Error('Selected model path is not a .vrm file. Please provide a valid VRM file.');
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
                const scene = new window.THREE.Scene();
                const camera = new window.THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
                const renderer = new window.THREE.WebGLRenderer({ canvas: canvas, antialias: true });
                renderer.setSize(canvas.clientWidth, canvas.clientHeight);
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
                const resolvedVRMPath = resolveModelPath(currentVRMModelPath);
                console.log(`Loading VRM model from: ${resolvedVRMPath} (original: ${currentVRMModelPath})`);
                
                const gltf = await new Promise((resolve, reject) => {
                    loader.load(
                        resolvedVRMPath,
                        resolve,
                        undefined,
                        reject
                    );
                });

                // Extract VRM instance from GLTFLoader plugin output
                // VRM data can be in userData.vrm or extensions.VRM
                let vrm = null;
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
                const mixer = new window.THREE.AnimationMixer(vrm.scene);
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
                            idleVrmaAction.clampWhenFinished = false; // Allow looping
                            idleVrmaAction.setEffectiveWeight(1.0);
                            idleVrmaAction.setEffectiveTimeScale(1.0);
                            idleVrmaAction.loop = window.THREE.LoopRepeat; // Loop continuously
                            console.log('Idle VRMA clip prepared. Tracks:', Array.isArray(boundClip.tracks) ? boundClip.tracks.length : 'unknown');
                        } else {
                            console.warn('No animation clip found in Idle VRMA');
                        }
                    }
                } catch (e) {
                    console.warn('Failed to preload Idle VRMA animation:', e);
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
                const neckBone = getBone('neck'); // Neck bone for head rotation blending
                const headBone = getBone('head'); // Head bone for direct head rotation
                const leftHand = getBone('leftHand'); // Left hand bone for love pose
                const rightHand = getBone('rightHand'); // Right hand bone for love pose
                const rightForeArm = getBone('rightLowerArm') || rightLowerArm; // Alias
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
                    requestAnimationFrame(animate);

                    if (vrmClock) {
                        const delta = vrmClock.getDelta();
                        // Update VRM BEFORE mixer so it doesn't override animation
                        // VRM update handles expressions, look-at, and physics
                        if (vrmModel && typeof vrmModel.update === 'function') {
                            try { vrmModel.update(delta); } catch (_) {}
                        }
                        // Update mixer AFTER VRM so animation has final control over bones
                        if (vrmMixer) {
                            vrmMixer.update(delta);
                            
                            // Check if any other animation is running
                            const hasActiveAnimation = 
                                (vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) ||
                                (vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) ||
                                (vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) ||
                                (vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning());
                            
                            // Play idle animation if no other animation is running
                            if (vrmIdleVrmaAction && !hasActiveAnimation) {
                                if (!vrmIdleVrmaAction.isRunning()) {
                                    vrmIdleVrmaAction.reset();
                                    vrmIdleVrmaAction.setEffectiveWeight(1.0);
                                    vrmIdleVrmaAction.setEffectiveTimeScale(1.0);
                                    vrmIdleVrmaAction.enabled = true;
                                    vrmIdleVrmaAction.play();
                                }
                            } else if (vrmIdleVrmaAction && hasActiveAnimation) {
                                // Stop idle animation when other animations are playing
                                if (vrmIdleVrmaAction.isRunning()) {
                                    vrmIdleVrmaAction.stop();
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
                } else if (!(vrmLoveVrmaAction && vrmLoveVrmaAction.isRunning()) && !(vrmThinkVrmaAction && vrmThinkVrmaAction.isRunning()) && !(vrmCryVrmaAction && vrmCryVrmaAction.isRunning()) && !(vrmAngryVrmaAction && vrmAngryVrmaAction.isRunning())) {
                    // Only apply manual pose control if VRMA animations are NOT running
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
                            } catch(_){}
                        }
                    }
                    } // End else block for VRM 1.0 idle animation

                    if (vrmRenderer && vrmScene && vrmCamera) {
                        vrmRenderer.render(vrmScene, vrmCamera);
                    }
                }
                animate();

                // Start periodic blinking after VRM is ready
                const setBlink = (value) => { // Helper to set blink expression value
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blink', value); } } catch (_) {} // VRM 1.0 blink key
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blinkLeft', value); } } catch (_) {} // Optional left eye key
                    try { if (vrm.expressionManager) { vrm.expressionManager.setValue('blinkRight', value); } } catch (_) {} // Optional right eye key
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink', value); } } catch (_) {} // VRM 0.x combined blink
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink_L', value); } } catch (_) {} // VRM 0.x left blink
                    try { if (vrm.blendShapeProxy) { vrm.blendShapeProxy.setValue('Blink_R', value); } } catch (_) {} // VRM 0.x right blink
                }; // End setBlink helper

                const scheduleBlink = () => { // Function to schedule the next blink
                    if (!vrmModel) return; // Skip if VRM has been cleaned up
                    const waitMs = 2200 + Math.random() * 2600; // Random delay between blinks (2.2s - 4.8s)
                    vrmBlinkTimeout = setTimeout(() => { // Set timer for blink
                        setBlink(1.0); // Close eyelids
                        setTimeout(() => { // Short delay to reopen eyes
                            setBlink(0.0); // Open eyelids
                            scheduleBlink(); // Schedule subsequent blink
                        }, 120 + Math.random() * 80); // Keep eyes closed 120-200ms
                    }, waitMs); // After the random wait
                }; // End scheduleBlink
                scheduleBlink(); // Kick off blinking loop

                console.log('VRM model loaded successfully');

            } catch (error) {
                console.error('Failed to load VRM model:', error);
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
            if (!live2dModel) {
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
            if (!vrmModel) {
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
                    const message = data.choices[0].cleanContent.trim();
                    
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
            
            if (expressionFile) {
                live2dModel.expression(expressionFile);
            } else {
                // Reset to default expression
                live2dModel.expression(null);
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
                // Log available expressions
                const expressions = await model.expressions;
                console.log('Available expressions:', expressions);
                
                // Test each expression
                if (expressions) {
                    for (const exp of expressions) {
                        console.log(`Testing expression: ${exp}`);
                        try {
                            await model.expression(exp);
                            console.log(`Successfully set expression: ${exp}`);
                        } catch (error) {
                            console.error(`Error setting expression ${exp}:`, error);
                        }
                        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second between expressions
                    }
                    // Reset to default
                    await model.expression(null);
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
                    body: JSON.stringify({
                        model: getCurrentModel(),
                        messages: subMessages,
                        temperature: 0.7,
                        // Provide tools so the model can decide to call them here as well
                        tools: tools,
                        tool_choice: 'auto'
                    })
                });

                const data = await response.json();
                if (data.choices && data.choices.length > 0) {
                    const msg = data.choices[0].message;
                    // Handle potential tool calls using LM Studio/OpenAI format
                    if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
                        try {
                            // Add assistant tool calls
                            subMessages.push({ role: 'assistant', tool_calls: msg.tool_calls });
                            // Execute and add tool results
                            for (const tc of msg.tool_calls) {
                                const toolResult = await executeToolCall(tc, context);
                                
                                // Format the tool result content properly
                                let toolResultContent;
                                if (typeof toolResult === 'string') {
                                    toolResultContent = toolResult;
                                } else if (toolResult.content) {
                                    // If the tool result has content (like from readFile), include it in a readable format
                                    toolResultContent = `${toolResult.message}\n\nContent:\n${toolResult.content}`;
                                } else {
                                    // Otherwise, just stringify the result
                                    toolResultContent = JSON.stringify(toolResult);
                                }
                                
                                subMessages.push({
                                    role: 'tool',
                                    content: toolResultContent,
                                    tool_call_id: tc.id
                                });
                            }
                            // Finalize with a follow-up call
                            const follow = await fetch(endpoint, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': `Bearer ${apiKey}`
                                },
                                body: JSON.stringify({
                                    model: getCurrentModel(),
                                    messages: subMessages,
                                    temperature: 0.7,
                                    tools: tools,
                                    tool_choice: 'auto'
                                })
                            });
                            const followJson = await follow.json();
                            const finalText = followJson?.choices?.[0]?.message?.content?.trim() || '';
                            return { success: true, message: finalText };
                        } catch (innerErr) {
                            console.error('Error handling tool calls in handleLLMQuery:', innerErr);
                            // Fall back to plain content if present
                        }
                    }

                    const plain = (msg.content || '').trim();
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
            // Get News API key from localStorage or input field
            let API_KEY = '';
            try {
                const savedSettings = localStorage.getItem('toolSettings');
                if (savedSettings) {
                    const settings = JSON.parse(savedSettings);
                    API_KEY = settings.newsApiKey || '';
                }
            } catch (e) {
                console.warn('Error loading news API key from settings:', e);
            }
            
            // Fallback to input field if not in settings
            if (!API_KEY && newsApiKeyInput) {
                API_KEY = newsApiKeyInput.value.trim();
            }
            
            if (!API_KEY) {
                return {
                    success: false,
                    message: 'News API key is not configured. Please enter your News API key in the settings.'
                };
            }
            
            try {
                // Fetch news from the API
                const url = `https://newsapi.org/v2/everything?q=${encodeURIComponent(searchTerm)}&apiKey=${API_KEY}`;
                const response = await fetch(url);
                
                if (!response.ok) {
                    throw new Error(`Failed to fetch news: ${response.statusText}`);
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
                    message: `Error fetching news: ${error.message}`
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

        // Converts a PDF (by URL or data URL) into an intelligent PowerPoint presentation.
        // Enhanced approach:
        // 1) Load PDF with PDF.js and extract ALL text content
        // 2) Send text to OpenAI LLM for intelligent summarization and structuring
        // 3) Create structured slides based on LLM output (intro, key points, details, conclusion)
        // 4) Save the enhanced PPTX file
        async function handlePdfToPowerPoint({ pdfUrl, promptUpload = false, title, author = "", maxSlides = 15, filename }) {
            try {
                if (!window.pdfjsLib) {
                    throw new Error('PDF.js not loaded');
                }
                if (!window.PptxGenJS) {
                    throw new Error('PptxGenJS not loaded');
                }

                // Configure PDF.js worker if available
                if (window.pdfjsLib.GlobalWorkerOptions) {
                    window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
                }

                // When no PDF URL is supplied, always prompt the user to upload a PDF
                if (!pdfUrl) {
                    const file = await promptForLocalPdf();
                    if (!file) {
                        return { success: false, message: 'No PDF selected.' };
                    }
                    // Use data URL for local files to avoid CORS issues
                    pdfUrl = await readFileAsDataUrl(file);
                }

                const loadingTask = window.pdfjsLib.getDocument({ url: pdfUrl, withCredentials: false });
                const pdf = await loadingTask.promise;

                // Extract ALL text content and images from the PDF
                let fullText = '';
                let extractedImages = [];
                
                for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex++) {
                    const page = await pdf.getPage(pageIndex);
                    
                    // Extract text content
                    const textContent = await page.getTextContent();
                    const pageText = textContent.items.map(it => it.str).join(' ').replace(/\s+/g, ' ').trim();
                    fullText += pageText + ' ';
                    
                    // Extract images from this page
                    try {
                        const operators = await page.getOperatorList();
                        const pageImages = await extractImagesFromPage(page, operators, pageIndex);
                        extractedImages = extractedImages.concat(pageImages);
                    } catch (imageError) {
                        console.warn(`Could not extract images from page ${pageIndex}:`, imageError);
                    }
                }

                // Clean up the extracted text
                fullText = fullText.trim().replace(/\s+/g, ' ');
                
                if (!fullText || fullText.length < 50) {
                    throw new Error('Could not extract sufficient text content from PDF');
                }
                
                console.log(`Extracted ${extractedImages.length} images from PDF`);

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
                const structuredContent = await generateStructuredPresentation(fullText, title, maxSlides, extractedImages, imageAnalysis);
                
                if (!structuredContent) {
                    throw new Error('Failed to generate structured content from PDF text');
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
                
                return { 
                    success: true, 
                    message: `Successfully created intelligent presentation with ${structuredContent.slides?.length || 0} content slides and ${imagesEmbedded}/${extractedImages.length} images embedded using ${modelUsed.includes('vl') ? 'vision model' : 'standard model'}. Saved to ${filename}` 
                };
            } catch (error) {
                console.error('PDF to PPTX error:', error);
                return { success: false, message: `Error converting PDF: ${error.message}` };
            }
        }

        // Detects if the user message is asking to convert a PDF to PowerPoint (so we can show upload UI when the LLM replies in text instead of calling the tool).
        function isPdfToPowerPointRequest(text) {
            if (!text || typeof text !== 'string') return false;
            const lower = text.toLowerCase();
            const hasPdf = /\bpdf\b/i.test(text);
            const hasPowerPoint = /\bpowerpoint\b|\bpptx\b|\bpresentation\b|\.pptx\b/i.test(text) || lower.includes('power point');
            const hasConvert = /\bconvert\b|\bturn\b|\btransform\b|\bcreate\b|\bmake\b|\bupload\b/i.test(text);
            return hasPdf && (hasPowerPoint || hasConvert);
        }

        // Parses optional filename (e.g. my_preso.pptx) and title from the user message for PDF-to-PowerPoint.
        function parsePdfToPowerPointParams(userMessage) {
            const filenameMatch = userMessage.match(/(\w[\w.-]*\.pptx)/i) || userMessage.match(/\b(?:call it|named?|save as|as)\s+['"]?(\w[\w.-]*\.pptx)['"]?/i);
            const filename = filenameMatch ? filenameMatch[1] : 'presentation.pptx';
            const titleMatch = userMessage.match(/(?:call the presentation|title it|named?)\s+['"]?([^'"]+)['"]?/i);
            const title = titleMatch ? titleMatch[1].trim().replace(/\.pptx$/i, '') : 'Presentation';
            return { title, filename };
        }

        // When the LLM replied in text instead of calling the tool, show the upload widget in chat and run conversion when the user selects a file.
        function appendPdfUploadWidgetToChat(userMessage) {
            const messageHistory = document.getElementById('message-history');
            if (!messageHistory) return;
            const { title, filename } = parsePdfToPowerPointParams(userMessage);

            const wrapper = document.createElement('div');
            wrapper.id = 'pdf-upload-prompt';
            wrapper.setAttribute('aria-label', 'PDF upload');
            wrapper.style.margin = '16px 0';
            wrapper.style.padding = '16px';
            wrapper.style.background = 'rgba(42, 42, 42, 0.95)';
            wrapper.style.border = '1px solid #3a3a3a';
            wrapper.style.borderRadius = '12px';
            wrapper.style.fontFamily = 'Segoe UI, Roboto, sans-serif';
            wrapper.style.color = '#ffffff';

            const text = document.createElement('div');
            text.textContent = 'Select a PDF to convert to PowerPoint';
            text.style.marginBottom = '12px';
            text.style.fontSize = '15px';
            text.style.fontWeight = '600';

            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'application/pdf';
            input.style.position = 'absolute';
            input.style.width = '1px';
            input.style.height = '1px';
            input.style.opacity = '0';
            input.style.pointerEvents = 'none';

            const selectBtn = document.createElement('button');
            selectBtn.textContent = 'Select PDF file';
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
                    const pdfUrl = await readFileAsDataUrl(file);
                    const result = await handlePdfToPowerPoint({ pdfUrl, title, filename });
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

        // Shows PDF upload UI inline in the message history so it is always visible
        // (no popup/modal—avoids issues with iframes, z-index, and security blocking dialogs).
        // Button triggers file input so the OS file dialog opens on user gesture.
        function promptForLocalPdf() {
            return new Promise(resolve => {
                const messageHistory = document.getElementById('message-history');
                const wrapper = document.createElement('div');
                wrapper.id = 'pdf-upload-prompt';
                wrapper.setAttribute('aria-label', 'PDF upload');
                wrapper.style.margin = '16px 0';
                wrapper.style.padding = '16px';
                wrapper.style.background = 'rgba(42, 42, 42, 0.95)';
                wrapper.style.border = '1px solid #3a3a3a';
                wrapper.style.borderRadius = '12px';
                wrapper.style.fontFamily = 'Segoe UI, Roboto, sans-serif';
                wrapper.style.color = '#ffffff';

                const text = document.createElement('div');
                text.textContent = 'Select a PDF to convert to PowerPoint';
                text.style.marginBottom = '12px';
                text.style.fontSize = '15px';
                text.style.fontWeight = '600';

                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'application/pdf';
                input.style.position = 'absolute';
                input.style.width = '1px';
                input.style.height = '1px';
                input.style.opacity = '0';
                input.style.pointerEvents = 'none';

                const selectBtn = document.createElement('button');
                selectBtn.textContent = 'Select PDF file';
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

        // Reads a File as a data URL
        function readFileAsDataUrl(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.onload = () => resolve(reader.result);
                reader.readAsDataURL(file);
            });
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
            const content = data.choices[0].message.content.trim();
            
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
        async function generateStructuredPresentation(fullText, title, maxSlides = 15, availableImages = [], imageAnalysis = []) {
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
                    imageInfo = '\n\nNo images were found in the PDF.';
                }

                // Create a comprehensive prompt for OpenAI to structure the content
                const systemPrompt = `You are an expert presentation designer. Your task is to analyze the provided PDF content and create a well-structured PowerPoint presentation outline${availableImages.length > 0 ? ', including intelligent placement of extracted images' : ''}. 

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
                
                const userPrompt = `Please analyze the following PDF content and create a structured presentation outline for a presentation titled "${title}":

PDF Content:
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
                        
                        const minimalUserPrompt = `Please analyze the following PDF content and create a structured presentation outline for a presentation titled "${title}":

PDF Content:
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
                        
                        const retryContent = retryData.choices[0].message.content.trim();
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

                const content = data.choices[0].message.content.trim();
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
