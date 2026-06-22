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
