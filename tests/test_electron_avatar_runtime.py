from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ELECTRON_AVATAR = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.js"
ELECTRON_AVATAR_HTML = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.html"
PIXI_STATIC_UNIFORM_SYNC = (
    PROJECT_ROOT
    / "electron-app"
    / "renderer"
    / "vendor"
    / "@pixi"
    / "unsafe-eval"
    / "dist"
    / "browser"
    / "unsafe-eval.min.js"
)


def _avatar_js_text() -> str:
    return ELECTRON_AVATAR.read_text(encoding="utf-8")


def test_avatar_model_loads_are_generation_guarded():
    avatar = _avatar_js_text()

    assert "let avatarModelLoadGeneration = 0;" in avatar
    assert "function beginAvatarModelLoad(mode, modelPath)" in avatar
    assert "function isStaleAvatarModelLoad(loadGeneration)" in avatar
    assert 'const loadGeneration = beginAvatarModelLoad("vrm", modelPath);' in avatar
    assert 'const loadGeneration = beginAvatarModelLoad("live2d", modelPath);' in avatar
    assert "disposeGltfSceneResources(gltf);" in avatar
    assert "model?.destroy?.({ children: true, texture: true, baseTexture: true });" in avatar


def test_avatar_vrma_runtime_rejects_stale_async_actions():
    avatar = _avatar_js_text()

    assert "actionStopTimerIds: new Set()" in avatar
    assert "runtime.actionStopTimerIds.clear();" in avatar
    assert "const runtimeAtStop = vrmRuntime;" in avatar
    assert "if (vrmRuntime !== runtimeAtStop)" in avatar
    assert "async function preloadVrmActions(vrm, runtime = vrmRuntime, loadGeneration = avatarModelLoadGeneration)" in avatar
    assert "if (isStaleAvatarModelLoad(loadGeneration) || runtime !== vrmRuntime || vrm !== vrmModel)" in avatar
    assert "if (activeVrm !== vrmModel || runtime !== vrmRuntime)" in avatar


def test_avatar_emote_and_expression_paths_do_not_stomp_user_state():
    avatar = _avatar_js_text()

    assert 'happy: "happy"' in avatar
    assert 'sad: "sad"' in avatar
    assert "const latestState = await window.catbotDesktop.getState();" in avatar
    assert "if (!latestState?.transientExpression || latestExpression !== expression)" in avatar
    assert "vrmModel.blendShapeProxy.update?.();" in avatar


def test_avatar_webgl_restore_is_mode_aware_and_keeps_live2d_looping():
    avatar = _avatar_js_text()

    assert "const shouldStartRenderLoop = !renderLoopActive;" in avatar
    assert "if (!renderLoopActive || !scene || !camera)" in avatar
    assert "if (!webglContextLost && renderer)" in avatar
    assert 'if (currentState.mode !== "live2d")' in avatar
    assert "setStatus(\"VRM renderer paused; Live2D active\");" in avatar
    assert "invalidateAvatarModelLoads();" in avatar
    assert "await loadLive2dModel(currentState.modelPath);" in avatar
    assert "await loadVrmModel(currentState.modelPath);" in avatar


def test_avatar_model_asset_scheme_and_csp_safe_live2d_patch_are_packaged():
    html = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")
    static_uniform_sync = PIXI_STATIC_UNIFORM_SYNC.read_text(encoding="utf-8")

    assert "connect-src 'self' data: blob: catbot-file: http: https:" in html
    assert "../vendor/@pixi/unsafe-eval/dist/browser/unsafe-eval.min.js" in html
    assert "'unsafe-eval'" not in html
    assert "Global PIXI not found." in static_uniform_sync
    assert "systemCheck:function(){}" in static_uniform_sync
    assert "new Function" not in static_uniform_sync
