from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_JS = PROJECT_ROOT / "js" / "app.js"
INDEX_HTML = PROJECT_ROOT / "index.html"
HTTPS_SERVER = PROJECT_ROOT / "src" / "servers" / "https_server.py"


def _app_js_text() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _index_html_text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _https_server_text() -> str:
    return HTTPS_SERVER.read_text(encoding="utf-8")


def test_proxy_auth_interceptor_uses_x_auth_token_not_provider_authorization():
    content = _app_js_text()

    assert "headers.set('X-Auth-Token', authToken)" in content
    assert "headers.set('Authorization', `Bearer ${authToken}`)" not in content
    assert "safeSessionStorageSet(AUTH_TOKEN_STORAGE_KEY, authToken)" in content


def test_provider_auth_proxy_401_does_not_clear_login_session():
    content = _app_js_text()

    assert "function isProxyRouteWithProviderAuthSemantics" in content
    assert "pathname === '/v1/proxy/chat/completions'" in content
    assert "!isProxyRouteWithProviderAuthSemantics(requestUrl)" in content


def test_attachment_preview_renders_file_names_with_dom_text_nodes():
    content = _app_js_text()

    assert "pendingAttachmentFiles.map((file, index) => `" not in content
    assert "name.textContent = file.name || 'attachment';" in content
    assert "name.title = file.name || '';" in content


def test_whisper_transcription_does_not_require_chat_api_key():
    content = _app_js_text()
    start = content.index("async function sendAudioToWhisper")
    end = content.index("// Check if response is successful before parsing JSON", start)
    section = content[start:end]

    assert "API key is required for transcription" not in section
    assert "'Authorization': `Bearer ${apiKey}`" not in section


def test_calculator_does_not_use_eval():
    content = _app_js_text()

    assert "function evaluateMathExpression" in content
    assert "eval(cleanExpression)" not in content


def test_news_tool_uses_proxy_not_browser_api_key_url():
    content = _app_js_text()

    assert "newsapi.org/v2/everything" not in content
    assert "/v1/proxy/news?query=" in content


def test_csp_allows_blob_connects_for_vrm_texture_loading():
    content = _index_html_text()
    csp_start = content.index('http-equiv="Content-Security-Policy"')
    csp_end = content.index('">', csp_start)
    csp = content[csp_start:csp_end]

    assert "connect-src 'self' data: blob: http: https: ws: wss:" in csp
    assert "img-src 'self' data: blob:" in csp
    assert "frame-ancestors" not in csp


def test_frame_ancestors_is_delivered_by_http_csp_header():
    content = _https_server_text()

    assert "CONTENT_SECURITY_POLICY" in content
    assert "frame-ancestors 'none'" in content
    assert "self.send_header('Content-Security-Policy', CONTENT_SECURITY_POLICY)" in content
