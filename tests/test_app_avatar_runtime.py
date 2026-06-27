from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_JS = PROJECT_ROOT / "js" / "app.js"


def _app_js_text() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_app_vrm_loads_are_generation_guarded():
    content = _app_js_text()

    assert "let vrmLoadGeneration = 0;" in content
    assert "let vrmActiveModelPath = '';" in content
    assert "function isCurrentVrmLoad(loadGeneration, modelPathSnapshot, modelInstance = vrmModel)" in content
    assert "const requestedGeneration = ++vrmLoadGeneration;" in content
    assert "const requestedModelPath = currentVRMModelPath;" in content
    assert "resolveModelPath(requestedModelPath)" in content
    assert "requestedGeneration !== vrmLoadGeneration || requestedModelPath !== currentVRMModelPath" in content
    assert "disposeStaleVrmLoadResources(scene, renderer, mixer, vrm, gltf?.scene);" in content


def test_app_vrm_cleanup_stops_render_and_animation_timers():
    content = _app_js_text()

    assert "let vrmAnimationFrameId = 0;" in content
    assert "let vrmBlinkCloseTimeout = null;" in content
    assert "let smoothedVrmDelta = 1 / 60;" in content
    assert "function clearVrmBlinkTimers()" in content
    assert "cancelAnimationFrame(vrmAnimationFrameId)" in content
    assert "clearVrmIdleReplayTimer();" in content
    assert "clearVrmAwaitingTtsStart();" in content
    assert "].forEach(clearVrmActionStopTimer);" in content
    assert "vrmProcessingThinkLoopActive = false;" in content


def test_app_vrm_raf_and_blink_callbacks_reject_stale_models():
    content = _app_js_text()

    assert "if (!isCurrentVrmLoad(requestedGeneration, requestedModelPath, vrm))" in content
    assert "vrmAnimationFrameId = requestAnimationFrame(animate);" in content
    assert "vrmBlinkCloseTimeout = setTimeout(() =>" in content
    assert "flushVrmExpressions(vrm);" in content


def test_app_vrm_runtime_matches_desktop_transition_and_delta_smoothing():
    content = _app_js_text()

    assert "const VRM_ACTION_FADE_IN_SECONDS = 0.55;" in content
    assert "const VRM_ACTION_FADE_OUT_SECONDS = 0.85;" in content
    assert "const VRM_IDLE_ACTION_FADE_IN_SECONDS = 0.95;" in content
    assert "const VRM_IDLE_ACTION_FADE_OUT_SECONDS = 0.8;" in content
    assert "const VRM_MAX_ANIMATION_DELTA_SECONDS = 1 / 24;" in content
    assert "const VRM_MAX_PHYSICS_DELTA_SECONDS = 1 / 45;" in content
    assert "const VRM_DELTA_SMOOTHING = 0.18;" in content
    assert "function getStableVrmFrameDeltas(rawDelta)" in content
    assert "const { animationDelta, physicsDelta } = getStableVrmFrameDeltas(rawDelta);" in content
    assert "vrmMixer.update(animationDelta);" in content
    assert "vrmModel.update(physicsDelta);" in content
    assert "vrmIdleVrmaAction.stop();" not in content
    assert "stopVrmAction(vrmIdleVrmaAction, VRM_IDLE_ACTION_FADE_OUT_SECONDS);" in content


def test_app_vrm_transitions_bridge_pose_snapshots_to_avoid_t_pose_flash():
    content = _app_js_text()

    assert "let vrmPoseSnapshotBones = {};" in content
    assert "let vrmLastPoseSnapshot = null;" in content
    assert "let vrmPoseBlend = null;" in content
    assert "const VRM_POSE_TO_ACTION_BLEND_MS = 420;" in content
    assert "const VRM_IDLE_POSE_TO_ACTION_BLEND_MS = 560;" in content
    assert "function createVrmPoseSnapshot()" in content
    assert "function restoreVrmPoseSnapshot(snapshot)" in content
    assert "function applyBlendedVrmPoseSnapshot(fromSnapshot, toSnapshot, weight)" in content
    assert "function startVrmPoseBlendToAction(action, fromSnapshot, durationMs)" in content
    assert "function updateVrmPoseBlend(now = performance.now())" in content
    assert "const poseBlendFromSnapshot = canFadeFromRunningAction" in content
    assert "try { vrmMixer?.update?.(0); } catch (_) {}" in content
    assert "startVrmPoseBlendToAction(nextAction, poseBlendFromSnapshot, poseBlendDurationMs);" in content
    assert "updateVrmPoseBlend(performance.now());" in content
    assert "} else if (!hasRunningVrmAction()) {" in content
    assert "restoreVrmPoseSnapshot(vrmLastPoseSnapshot);" in content
    assert "vrmLastPoseSnapshot = createVrmPoseSnapshot() || vrmLastPoseSnapshot;" in content


def test_app_vrm_renderer_uses_desktop_safe_quality_defaults():
    content = _app_js_text()

    assert "function configureVrmRenderer(rendererInstance)" in content
    assert "VRM_BROWSER_PIXEL_RATIO_CAP = 1.25" in content
    assert "rendererInstance.setPixelRatio(Math.min(VRM_BROWSER_PIXEL_RATIO_CAP, window.devicePixelRatio || 1));" in content
    assert "rendererInstance.outputColorSpace = window.THREE.SRGBColorSpace;" in content
    assert "rendererInstance.toneMapping = window.THREE.NoToneMapping;" in content
    assert "premultipliedAlpha: false" in content
    assert "powerPreference: 'default'" in content
    assert "precision: 'highp'" in content
    assert "configureVrmRenderer(renderer);" in content


def test_app_expression_updates_are_flushed_and_live2d_expression_errors_are_safe():
    content = _app_js_text()

    assert "function flushVrmExpressions(targetVrm = vrmModel)" in content
    assert "targetVrm?.expressionManager?.update?.();" in content
    assert "targetVrm?.blendShapeProxy?.update?.();" in content
    assert "flushVrmExpressions(vrmModel);" in content
    assert "console.warn('Could not apply Live2D expression:', error);" in content
    assert "const resetLive2DExpression = () => {" in content
    assert "resetResult.catch(() => {});" in content
    assert "expressionResult.catch((error) => {" in content


def test_app_model_list_edits_clear_empty_browser_avatar_selection():
    content = _app_js_text()

    assert "if (modelPath !== previousModelPath)" in content
    assert "if (currentVRMModelPath !== previousModelPath)" in content
    assert "if (!vrmModel || vrmActiveModelPath !== currentVRMModelPath)" in content
