import json
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
    package = json.loads(ELECTRON_PACKAGE.read_text(encoding="utf-8"))
    build = package["build"]
    packaged_files = build["files"]

    assert "!**/.env" in packaged_files
    assert "!**/.env.*" in packaged_files
    assert all(item not in {".env", ".env.example"} for item in packaged_files)
    assert build["afterPack"] == "scripts/after-pack-security-audit.js"


def test_electron_package_excludes_runtime_secrets_and_memory_data():
    package = json.loads(ELECTRON_PACKAGE.read_text(encoding="utf-8"))
    packaged_files = set(package["build"]["files"])

    assert {
        "!**/*.key",
        "!**/*.log",
        "!**/*.p12",
        "!**/*.pem",
        "!**/*.pfx",
        "!**/*.sqlite",
        "!**/*.sqlite3",
        "!**/*.zip",
        "!**/auth_users.json",
        "!**/desktop-auth.json",
        "!**/embeddings.npy",
        "!**/metadata.json",
        "!**/telegram_user_links.json",
        "!**/memory_data/**/*",
    }.issubset(packaged_files)


def test_electron_package_excludes_redundant_nested_model_archive():
    package = json.loads(ELECTRON_PACKAGE.read_text(encoding="utf-8"))
    model_resource = next(
        item
        for item in package["build"]["extraResources"]
        if item.get("to") == "model_avatar"
    )

    assert "!**/*.zip" in model_resource["filter"]


def test_external_url_and_auth_storage_are_hardened():
    content = _main_js_text()

    assert "function openSafeExternalUrl" in content
    assert "isSafeExternalUrl" in content
    assert "safeStorage.encryptString" in content
    assert "accessTokenSecret" in content
    assert "chatApiKeySecret" in content


def test_desktop_logout_clears_proxy_auth_cookie():
    content = _main_js_text()

    assert "const DEFAULT_AUTH_COOKIE_NAME = \"catbot_auth_token\"" in content
    assert "process.env.AUTH_COOKIE_NAME" in content
    assert "function clearDesktopProxyAuthCookie()" in content
    assert "session.defaultSession.cookies.remove(cookieOrigin, cookieName)" in content
    assert "clearDesktopProxyAuthCookie();" in content


def test_avatar_csp_allows_blob_connects_for_vrm_texture_loading():
    content = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")

    assert "connect-src 'self' data: blob: catbot-file: http: https:" in content
    assert "img-src 'self' data: blob:" in content
    assert "script-src 'self' 'unsafe-inline';" in content
    assert "'unsafe-eval'" not in content
    assert "frame-ancestors" not in content


def test_avatar_loads_pixi_static_uniform_sync_before_live2d_plugin():
    content = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")
    pixi_script = '<script src="../vendor/pixi.js/pixi.min.js"></script>'
    safe_uniform_script = '<script src="../vendor/@pixi/unsafe-eval/dist/browser/unsafe-eval.min.js"></script>'
    live2d_plugin_script = '<script src="../vendor/pixi-live2d-display/index.min.js"></script>'

    assert pixi_script in content
    assert safe_uniform_script in content
    assert live2d_plugin_script in content
    assert content.index(pixi_script) < content.index(safe_uniform_script) < content.index(live2d_plugin_script)
