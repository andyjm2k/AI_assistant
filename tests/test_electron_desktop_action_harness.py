from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ELECTRON_MAIN = PROJECT_ROOT / "electron-app" / "main" / "main.js"
ELECTRON_PRELOAD = PROJECT_ROOT / "electron-app" / "main" / "preload.js"
ELECTRON_ACTION_HARNESS = PROJECT_ROOT / "electron-app" / "main" / "action-harness.js"
ELECTRON_AVATAR = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.js"
ELECTRON_AVATAR_HTML = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.html"


def test_desktop_action_harness_ipc_and_tools_are_wired():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    preload = ELECTRON_PRELOAD.read_text(encoding="utf-8")

    assert 'require("./action-harness")' in main
    assert 'ipcMain.handle("desktop:start-action-harness"' in main
    assert 'ipcMain.handle("desktop:stop-action-harness"' in main
    assert 'ipcMain.handle("desktop:capture-action-harness"' in main
    assert "startActionHarness" in preload
    assert "stopActionHarness" in preload
    assert "captureActionHarness" in preload

    for tool_name in [
        "desktop_action_capture_window",
        "desktop_action_mouse",
        "desktop_action_key",
        "desktop_action_type_text",
        "desktop_action_wait",
        "desktop_action_stop",
    ]:
        assert tool_name in main

    assert "getDesktopActionHarnessTooling()" in main
    assert "executeDesktopActionHarnessTool(toolName, args)" in main
    assert "requireUsableActionHarnessTarget" in main
    assert "not the taskbar or a toolbar" in main
    assert "Windows shell/taskbar" in main
    assert "Inspect the attached visual result" in main
    assert "formatDesktopToolCallForTranscript" in main
    assert "shouldUseDesktopNativeTools" in main
    assert "using text fallback tool calls" in main
    assert "sanitizeDesktopMessagesForTextFallback" in main
    assert "buildRequestMessagesWithCurrentToolMode" in main
    assert "appendTextToDesktopMessage" in main
    assert "shouldFlattenDesktopVisualContentForFallback" in main
    assert "keepLatestDesktopVisualMessageOnly" in main
    assert "countDesktopImagePartsInMessages" in main
    assert "DESKTOP_ACTION_HARNESS_CAPTURE_FORMAT = \"jpeg\"" in main
    assert "DESKTOP_ACTION_HARNESS_CAPTURE_MAX_IMAGE_WIDTH = 800" in main
    assert "DESKTOP_ACTION_HARNESS_CAPTURE_CLEANUP_INTERVAL_MS" in main
    assert "serializeDesktopChatRequestBody" in main
    assert "serializeMs" in main
    assert "captureMaxImageWidth: normalizeActionHarnessCaptureMaxImageWidth" in main
    assert "captureJpegQuality: normalizeActionHarnessCaptureJpegQuality" in main
    assert "play request start" in main
    assert "Desktop action completed." in main
    assert "image attachment" in main
    assert "normalizeDesktopActionMouseAction" in main
    assert "coordinateSpace" in main
    assert "Do not use x/y if a grid cell can be identified" in main
    assert "Desktop play mode tool format is strict" in main
    assert "output exactly one <tool_call> block and no other text" in main
    assert "Do not use type, button, click, screenX, or clientX" in main
    assert "top-left of the entire screenshot/window" in main
    assert "Never restart counting columns or rows" in main
    assert "the grid covers the full screenshot, not just the game board" in main
    assert "Continuous play: after every tool result" in main
    assert "Use the provided play memory" in main
    assert "captureActionHarnessVisualAfterAction" in main
    assert "DESKTOP_ACTION_HARNESS_CONTINUE_NUDGE_LIMIT" in main
    assert "DESKTOP_ACTION_HARNESS_DEFAULT_LOOP_BUDGET = 80" in main
    assert "DESKTOP_ACTION_HARNESS_DEFAULT_NUDGE_INTERVAL = 5" in main
    assert "DESKTOP_ACTION_HARNESS_ARM_COUNTDOWN_MS = 5000" in main
    assert "normalizeActionHarnessLoopBudget" in main
    assert "normalizeActionHarnessNudgeInterval" in main
    assert "normalizeActionHarnessActionDelayMs" in main
    assert "loopBudget: normalizeActionHarnessLoopBudget" in main
    assert "nudgeInterval: normalizeActionHarnessNudgeInterval" in main
    assert "actionDelayMs: normalizeActionHarnessActionDelayMs" in main
    assert "armEndsAt" in main
    assert "armStartedAt" in main
    assert "state.visible = true" in main
    assert "arming cancelled before target bind" in main
    assert "getActionHarnessActionDelayMs" in main
    assert "playModeLoopBudgetAtRequestStart" in main
    assert "getActionHarnessLoopBudget()" in main
    assert "shouldRunActionHarnessLoopIteration" in main
    assert "shouldInsertActionHarnessDecisionNudge" in main
    assert "buildActionHarnessDecisionNudge" in main
    assert "DESKTOP_ACTION_HARNESS_CONTINUE_NUDGE_LIMIT = 12" in main
    assert "DESKTOP_ACTION_HARNESS_MEMORY_MAX_ITEMS" in main
    assert "Play memory from this session" in main
    assert "appendActionHarnessPlayMemory" in main
    assert "injectActionHarnessPlayMemoryMessage" in main
    assert "desktop_action_set_goal" in main
    assert "Text-entry workflow" in main
    assert "successAssessment" in main
    assert "nudging continuous play" in main
    assert "DESKTOP_ACTION_HARNESS_CHAT_TIMEOUT_MS" in main
    assert "DESKTOP_ACTION_HARNESS_CONTEXT_TAIL_MESSAGES" in main
    assert "compactDesktopActionHarnessMessagesForRequest" in main
    assert "isOutdatedActionHarnessDefaultGrid" in main
    assert "columns === 48 && rows === 32" in main
    assert "maximum: actionHarness.MAX_GRID_COLUMNS" in main
    assert "getUsableForegroundActionHarnessTarget" in main
    assert "binding play mode target with grid" in main
    assert "initial capture failed after target bind" in main
    assert "options.hideAvatar !== true" in main
    assert "hideAvatar: options.hideAvatar === true" in main
    assert "toolResponseParts" in main
    assert "I selected a desktop action for the harness." in main
    assert "transcriptToolRegex" in main
    assert "mouse warning" in main
    assert 'role: "tool"' not in main
    assert "tool_call_id" not in main


def test_desktop_action_harness_windows_bridge_has_grid_and_input_primitives():
    harness = ELECTRON_ACTION_HARNESS.read_text(encoding="utf-8")

    assert "GetForegroundWindow" in harness
    assert "const DEFAULT_GRID_COLUMNS = 24;" in harness
    assert "const DEFAULT_GRID_ROWS = 16;" in harness
    assert "const MAX_GRID_COLUMNS = 96;" in harness
    assert "const MAX_GRID_ROWS = 64;" in harness
    assert "CopyFromScreen" in harness
    assert "Draw-CatbotGrid" in harness
    assert "Save-CatbotBitmap" in harness
    assert "ImageFormat]::Jpeg" in harness
    assert "maxImageWidth" in harness
    assert "image/jpeg" in harness
    assert "$Height - $headerHeight" in harness
    assert "$Width - $headerWidth" in harness
    assert "SetCursorPos" in harness
    assert "SendInput" in harness
    assert "GetCursorPos" in harness
    assert "Move-CatbotCursor" in harness
    assert "Cursor verification mismatch" in harness
    assert "verified = $verified" in harness
    assert "coordinateToScreenPoint" in harness
    assert "mouseTargetToScreenPoint" in harness
    assert "processName = $processName" in harness
    assert "keybd_event" in harness
    assert "gridCellToScreenPoint" in harness
    assert "const requestedClicks = Number(options.clicks);" in harness
    assert "requireActive: options.requireActive === true" in harness
    assert "Focus-CatbotTarget $targetHwnd $false" in harness
    assert "function gridColumnIndex(label)" in harness
    assert "Use a label like A1, C4, or AA12" in harness
    assert "[char] ([int] (65 + ($value % 26)))" in harness
    assert "columns = $columns" in harness
    assert "rows = $rows" in harness
    assert "Mouse input requires either a grid cell or finite x/y coordinates." in harness
    assert "MAX_GRID_COLUMNS" in harness
    assert "MAX_GRID_ROWS" in harness


def test_desktop_action_harness_avatar_hud_controls_are_wired():
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")
    avatar_html = ELECTRON_AVATAR_HTML.read_text(encoding="utf-8")

    assert 'data-quick-action="play"' in avatar_html
    assert "action-arming-overlay" in avatar_html
    assert "action-arming-countdown" in avatar_html
    assert "Select the required active window now" in avatar_html
    assert 'data-hud-panel-button="desktop"' in avatar_html
    assert 'data-hud-panel="desktop"' in avatar_html
    assert "hud-action-start-btn" in avatar_html
    assert "hud-action-capture-btn" in avatar_html
    assert "hud-play-loop-budget" in avatar_html
    assert "hud-play-nudge-interval" in avatar_html
    assert "hud-play-action-delay" in avatar_html
    assert "hud-play-capture-width" in avatar_html
    assert "hud-play-capture-quality" in avatar_html
    assert "Set loop budget to -1 for indefinite play" in avatar_html
    assert "Action delay is the wait before the next screenshot" in avatar_html
    assert "Lower capture width or JPEG quality improves play-loop speed" in avatar_html

    assert "startActionHarnessFromHud" in avatar
    assert "ACTION_HARNESS_ARM_COUNTDOWN_MS = 5000" in avatar
    assert "syncActionHarnessArmingOverlay" in avatar
    assert "action-harness-arming" in avatar
    assert "Click or Alt-Tab to the target app" in avatar
    assert "stopActionHarnessFromHud" in avatar
    assert "captureActionHarnessFromHud" in avatar
    assert "setQuickHudVisible(true)" in avatar
    assert "currentState.actionHarness?.playMode" in avatar
    assert "actionHarnessImageDataUrl" in avatar
    assert "hudPlayLoopBudget" in avatar
    assert "hudPlayNudgeInterval" in avatar
    assert "hudPlayActionDelay" in avatar
    assert "hudPlayCaptureWidth" in avatar
    assert "hudPlayCaptureQuality" in avatar
    assert "loopBudget" in avatar
    assert "nudgeInterval" in avatar
    assert "actionDelayMs" in avatar
    assert "captureMaxImageWidth" in avatar
    assert "captureJpegQuality" in avatar
    assert "Capturing play window grid" in avatar
    assert "Initial grid capture failed; use Capture Grid to retry" in avatar
