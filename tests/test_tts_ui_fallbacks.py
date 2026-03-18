from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_JS_PATH = PROJECT_ROOT / "js" / "app.js"


def _app_js_text() -> str:
    return APP_JS_PATH.read_text(encoding="utf-8")


def test_app_js_has_env_tts_model_and_voice_fallback_helpers():
    content = _app_js_text()
    assert "function applyEnvDefaultTtsModelOnFetchFailure()" in content
    assert "function applyEnvDefaultTtsVoiceOnFetchFailure()" in content
    assert "envToolDefaults.ttsModel" in content
    assert "envToolDefaults.ttsVoice" in content


def test_app_js_applies_model_and_voice_fallbacks_when_tts_voice_fetch_fails():
    content = _app_js_text()
    assert "Failed to fetch voices from all endpoints" in content
    assert "applyEnvDefaultTtsModelOnFetchFailure();" in content
    assert "applyEnvDefaultTtsVoiceOnFetchFailure();" in content


def test_app_js_has_conversational_progress_tts_hooks():
    content = _app_js_text()
    assert "const PROGRESS_VOICE_INITIAL_DELAY_MS = 0;" in content
    assert "const PROGRESS_VOICE_REPEAT_DELAY_MS = 5000;" in content
    assert "function getConversationalProgressPrompt(stateText, announcementCount = 0)" in content
    assert "function announceConversationalProgress(force = false)" in content
    assert "textToSpeechFallback(prompt.text" in content


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
    assert "if (shouldStartProgressUpdatesForPrompt(promptText)) {" in content
    assert "startProgressUpdates('Analyzing request');" in content


def test_app_js_refreshes_model_dropdowns_for_initial_and_companion_settings():
    content = _app_js_text()
    assert "function populateModelDropdown(dropdown, models, preferredValue, fallbackValue)" in content
    assert "await fetchAvailableModels(persistedToolSettings);" in content
    assert "await fetchAvailableModels(data.settings);" in content


def test_app_js_flushes_tool_settings_on_pagehide_for_session_persistence():
    content = _app_js_text()
    assert "window.addEventListener('pagehide', () => {" in content
    assert "saveToolSettings({ skipCompanionRefresh: true });" in content
