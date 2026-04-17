from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_JS_PATH = PROJECT_ROOT / "js" / "app.js"


def _app_js_text() -> str:
    return APP_JS_PATH.read_text(encoding="utf-8")


def test_app_js_has_env_tts_model_and_voice_fallback_helpers():
    content = _app_js_text()
    assert "function applyEnvDefaultTtsModelOnFetchFailure()" in content
    assert "function applyEnvDefaultTtsVoiceOnFetchFailure()" in content
    assert "function normalizeTtsVoiceEntries(responseData)" in content
    assert "envToolDefaults.ttsModel" in content
    assert "envToolDefaults.ttsVoice" in content


def test_app_js_applies_model_and_voice_fallbacks_when_tts_voice_fetch_fails():
    content = _app_js_text()
    assert "Failed to fetch voices from all endpoints" in content
    assert "applyEnvDefaultTtsModelOnFetchFailure();" in content
    assert "applyEnvDefaultTtsVoiceOnFetchFailure();" in content
    assert "responseData.data" in content
    assert "&model=${encodeURIComponent(selectedModel)}" in content


def test_app_js_has_conversational_progress_tts_hooks():
    content = _app_js_text()
    assert "const PROGRESS_VOICE_INITIAL_DELAY_MS = 0;" in content
    assert "const PROGRESS_VOICE_REPEAT_DELAY_MS = 5000;" in content
    assert "function getConversationalProgressPrompt(stateText, announcementCount = 0)" in content
    assert "function announceConversationalProgress(force = false)" in content
    assert "textToSpeech(prompt.text, { preserveThinkingPose: true });" in content


def test_app_js_uses_thinking_fillers_for_non_tool_progress_and_specific_tool_prompts():
    content = _app_js_text()
    assert '"Let me think."' in content
    assert '"Meow, let me think."' in content
    assert '"I\'m on it, looking that up now."' in content


def test_app_js_has_small_talk_progress_suppression_helpers():
    content = _app_js_text()
    assert "const SMALL_TALK_PROMPT_PATTERNS = [" in content
    assert "function isSmallTalkPrompt(promptText = '')" in content
    assert "function shouldStartProgressUpdatesForPrompt(promptText = '')" in content


def test_app_js_only_starts_progress_updates_for_request_like_prompts():
    content = _app_js_text()
    assert "if (shouldStartProgressUpdatesForPrompt(promptTextForModel)) {" in content
    assert "startProgressUpdates('Analyzing request');" in content


def test_app_js_refreshes_model_dropdowns_for_initial_and_companion_settings():
    content = _app_js_text()
    assert "function populateModelDropdown(dropdown, models, preferredValue, fallbackValue)" in content
    assert "await fetchAvailableModels(initialToolSettings);" in content
    assert "await fetchAvailableModels(data.settings);" in content


def test_app_js_fetches_and_prepends_soul_prompt_for_chat_requests():
    content = _app_js_text()
    assert "soulPrompt: data.soulPrompt || ''" in content
    assert "typeof envToolDefaults.soulPrompt === 'string'" in content
    assert "effectiveSystemPrompt = `${soulPrompt}\\n\\n${effectiveSystemPrompt}`;" in content


def test_app_js_renders_soul_prompt_preview_in_identity_panel():
    content = _app_js_text()
    assert "const soulPromptDisplay = document.getElementById('soul-prompt-display');" in content
    assert "function renderSoulPromptPreview(soulPrompt = '')" in content
    assert "soulPromptDisplay.value = typeof soulPrompt === 'string' ? soulPrompt : '';" in content
    assert "renderSoulPromptPreview(envToolDefaults ? envToolDefaults.soulPrompt : '');" in content


def test_app_js_flushes_tool_settings_on_pagehide_for_session_persistence():
    content = _app_js_text()
    assert "window.addEventListener('pagehide', () => {" in content
    assert "saveToolSettings({ skipCompanionRefresh: true });" in content


def test_app_js_refreshes_tts_voices_when_model_changes():
    content = _app_js_text()
    assert "ttsModelDropdown.addEventListener('change', () => {" in content
    assert "if (ttsServiceOpenAI && ttsServiceOpenAI.checked) fetchTtsVoices();" in content


def test_app_js_normalizes_non_string_choice_content_before_rendering():
    content = _app_js_text()
    assert "function getChoiceMessage(choice = {})" in content
    assert "function extractChoiceRawText(choice = {})" in content
    assert "function extractChoiceVisibleText(choice = {})" in content
    assert "const message = getChoiceMessage(firstChoice);" in content
    assert "const rawContent = extractChoiceRawText(firstChoice);" in content


def test_app_js_reuses_choice_visible_text_helper_in_auxiliary_flows():
    content = _app_js_text()
    assert "content = extractChoiceVisibleText(data?.choices?.[0] || {});" in content
    assert "const message = extractChoiceVisibleText(data.choices[0] || {});" in content
    assert "const content = extractChoiceVisibleText(data?.choices?.[0] || {});" in content
    assert "data.choices[0].cleanContent.trim()" not in content
    assert "data.choices[0].message.content.trim()" not in content


def test_app_js_surfaces_llm_endpoint_errors_and_model_refresh_failures():
    content = _app_js_text()
    assert "function buildOptionalAuthorizationHeaders(apiKey = '')" in content
    assert "function parseJsonResponseWithErrors(response, context = {})" in content
    assert "function buildLlmEndpointErrorMessage(response, payload, rawText = '', context = {})" in content
    assert "function renderAssistantErrorResponse(message = '')" in content
    assert "The assistant could not get a response from the model endpoint." in content
    assert "The model list could not be refreshed." in content
    assert "status.textContent = error.message || 'The model list could not be refreshed. Check Tool Settings.';" in content
    assert "renderAssistantErrorResponse(userErrorMessage);" in content


def test_app_js_debounces_model_refresh_and_normalizes_model_payloads():
    content = _app_js_text()
    assert "let fetchAvailableModelsDebounceId = null;" in content
    assert "const queueAvailableModelsRefresh = () => {" in content
    assert "apiKeyInput.addEventListener('input', queueAvailableModelsRefresh);" in content
    assert "endpointInput.addEventListener('input', queueAvailableModelsRefresh);" in content
    assert "function normalizeAvailableModelsResponse(responseData)" in content
    assert "const normalizedModels = normalizeAvailableModelsResponse(data);" in content
