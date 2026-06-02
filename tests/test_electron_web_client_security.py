from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ELECTRON_MAIN = PROJECT_ROOT / "electron-app" / "main" / "main.js"
ELECTRON_PACKAGE = PROJECT_ROOT / "electron-app" / "package.json"
ELECTRON_AVATAR_HTML = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.html"


def _main_js_text() -> str:
    return ELECTRON_MAIN.read_text(encoding="utf-8")


def test_web_client_window_does_not_receive_privileged_preload():
    content = _main_js_text()
    start = content.index("function createWebClientWindow()")
    end = content.index("function showControlPanel()", start)
    section = content[start:end]

    assert 'preload: path.join(__dirname, "preload.js")' not in section
    assert "sandbox: true" in section
    assert "installWebClientNavigationGuards(webClientWindow);" in section


def test_web_client_window_has_navigation_guards():
    content = _main_js_text()

    assert "function installWebClientNavigationGuards" in content
    assert "setWindowOpenHandler" in content
    assert "will-navigate" in content
    assert "isAllowedWebClientNavigation(url)" in content


def test_electron_package_does_not_bundle_env_file():
    content = ELECTRON_PACKAGE.read_text(encoding="utf-8")

    assert '".env"' not in content


def test_external_url_and_auth_storage_are_hardened():
    content = _main_js_text()

    assert "function openSafeExternalUrl" in content
    assert "isSafeExternalUrl" in content
    assert "safeStorage.encryptString" in content
    assert "accessTokenSecret" in content
    assert "chatApiKeySecret" in content


def test_avatar_csp_allows_blob_connects_for_vrm_texture_loading():
    content = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")

    assert "connect-src 'self' data: blob: http: https:" in content
    assert "img-src 'self' data: blob:" in content
    assert "frame-ancestors" not in content
