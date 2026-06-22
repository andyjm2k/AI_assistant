from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ELECTRON_AVATAR = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.js"
ELECTRON_AVATAR_HTML = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.html"
ELECTRON_AVATAR_CSS = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.css"
ELECTRON_VRM_QUALITY = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "vrm-quality.js"
ELECTRON_MAIN = PROJECT_ROOT / "electron-app" / "main" / "main.js"
ELECTRON_PRELOAD = PROJECT_ROOT / "electron-app" / "main" / "preload.js"
ELECTRON_DEFAULT_CONFIG = PROJECT_ROOT / "electron-app" / "config" / "default-desktop-config.json"
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


def test_avatar_vrm_quality_profiles_preserve_authored_materials_above_low():
    avatar = _avatar_js_text()
    quality = ELECTRON_VRM_QUALITY.read_text(encoding="utf-8")

    assert 'VRM_GRAPHICS_QUALITY_VALUES = Object.freeze(["low", "medium", "high"])' in quality
    assert 'powerPreference: "high-performance"' in quality
    assert 'materialMode: "authored"' in quality
    assert 'textureBudgetBytes: 512 * MIB' in quality
    assert "createVrmTexturePlan(vrm, renderer, effectiveVrmGraphicsQuality)" in avatar
    assert 'if (activeVrmQualityProfile.materialMode === "unlit")' in avatar
    assert "applyDesktopMaterialFallback(vrm);" in avatar
    assert "VRMUtils.removeUnnecessaryVertices?.(vrm.scene);" in avatar


def test_avatar_vrm_quality_change_reloads_context_and_caps_frame_rate():
    avatar = _avatar_js_text()

    assert "function scheduleGraphicsReloadIfNeeded(state)" in avatar
    assert "window.setTimeout(() => window.location.reload(), 80);" in avatar
    assert "activeVrmQualityProfile.targetFps" in avatar
    assert "pendingFrameDelta += clock.getDelta();" in avatar
    assert "if (!currentState.visible)" in avatar
    assert "runningActionKey ||" in avatar


def test_electron_vrm_quality_state_and_gpu_diagnostics_are_exposed():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    preload = ELECTRON_PRELOAD.read_text(encoding="utf-8")
    html = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")
    config = ELECTRON_DEFAULT_CONFIG.read_text(encoding="utf-8")

    assert 'vrmGraphicsQuality: "medium"' in main
    assert "state.vrmGraphicsQuality = normalizeVrmGraphicsQuality(state.vrmGraphicsQuality);" in main
    assert 'ipcMain.handle("desktop:get-graphics-diagnostics"' in main
    assert 'ipcMain.handle("desktop:report-renderer-diagnostics"' in main
    assert "app.getGPUFeatureStatus()" in main
    assert 'app.getGPUInfo("basic")' in main
    assert "getGraphicsDiagnostics:" in preload
    assert "reportRendererDiagnostics:" in preload
    assert 'id="hud-vrm-quality"' in html
    assert '"vrmGraphicsQuality": "medium"' in config


def test_adaptive_hud_uses_a_compact_dock_and_four_contextual_routes():
    html = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")
    css = ELECTRON_AVATAR_CSS.read_text(encoding="utf-8")
    avatar = _avatar_js_text()

    for action in ["chat", "microphone", "screen", "play", "more"]:
        assert f'data-quick-action="{action}"' in html

    assert html.count('class="dock-action') == 5
    for route in ["chat", "character", "desktop", "settings"]:
        assert f'data-hud-panel-button="{route}"' in html
        assert f'data-hud-panel="{route}"' in html

    assert 'role="tab"' in html
    assert 'aria-selected="false"' in html
    assert 'id="quick-chat-form"' in html.split('data-hud-panel="chat"', 1)[1]
    assert 'class="hud-settings-group"' in html
    assert "@media (max-width: 300px)" in css
    assert '.dock-action[data-quick-action="screen"]' in css
    assert "function normalizeHudPanelName(panelName)" in avatar
    assert 'button.setAttribute("aria-selected", isActive ? "true" : "false");' in avatar
    assert 'setHudPanel("chat", { focusInput: true });' in avatar
    assert "Could not autohide quick HUD before sending chat message" not in avatar
