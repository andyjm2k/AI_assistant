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
