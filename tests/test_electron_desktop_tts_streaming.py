from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ELECTRON_MAIN = PROJECT_ROOT / "electron-app" / "main" / "main.js"
ELECTRON_PRELOAD = PROJECT_ROOT / "electron-app" / "main" / "preload.js"
ELECTRON_AVATAR = PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.js"


def test_desktop_tts_streaming_ipc_is_wired_for_avatar_renderer():
    preload = ELECTRON_PRELOAD.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "synthesizePreviewSpeechStream" in preload
    assert "desktop:synthesize-preview-speech-stream" in preload
    assert "desktop:cancel-preview-speech-stream" in preload
    assert "playStreamingSpeechPreviewChunk" in avatar
    assert "playStreamingSpeechPreviewChunks" in avatar
    assert "streamSpeechPreviewChunkToPcmQueue" in avatar
    assert "playPcmSpeechPreviewBytes" in avatar
    assert "window.catbotDesktop.synthesizePreviewSpeechStream" in avatar


def test_desktop_tts_voice_catalog_ipc_is_wired_for_selectors():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    preload = ELECTRON_PRELOAD.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")
    control_panel = (PROJECT_ROOT / "electron-app" / "renderer" / "control-panel" / "control-panel.js").read_text(encoding="utf-8")

    assert 'ipcMain.handle("desktop:list-tts-voices"' in main
    assert "listDesktopTtsVoices" in main
    assert "listTtsVoices" in preload
    assert "populateHudTtsVoiceOptions" in avatar
    assert "populateTtsVoiceOptions" in control_panel


def test_desktop_avatar_cleans_up_finished_dance_actions_before_idle():
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "function stopCompletedNonIdleVrmActions()" in avatar
    assert 'actionKey === "idle"' in avatar
    assert "action.clampWhenFinished" in avatar
    assert "restoreVrmPoseSnapshot(finishedPose, vrmRuntime)" in avatar
    assert "stopCompletedNonIdleVrmActions();" in avatar


def test_desktop_screen_context_toggle_persists_across_prompts():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")
    avatar_html = (PROJECT_ROOT / "electron-app" / "renderer" / "avatar" / "avatar.html").read_text(encoding="utf-8")

    assert "screenContextMode: false" in main
    assert "state.screenContextMode = Boolean(state.screenContextMode);" in main
    assert "let screenContextModeEnabled = Boolean(currentState.screenContextMode);" in avatar
    assert "screenContextModeEnabled = !screenContextModeEnabled;" in avatar
    assert "setState({ screenContextMode: screenContextModeEnabled })" in avatar
    assert "Each prompt will include a fresh screenshot." in avatar
    assert "const shouldCaptureScreenContext = Boolean(!options.screenImageDataUrl && screenContextModeEnabled);" in avatar
    assert "const pendingScreenSnapshotForPrompt = !shouldCaptureScreenContext && !options.screenImageDataUrl" in avatar
    assert 'title="Toggle screen context"' in avatar_html


def test_desktop_voice_chat_sends_with_issue_note_when_screen_snapshot_fails():
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert 'setVoiceCaptureStatus("Capturing screen...", "sending");' in avatar
    assert "Screen context was toggled on, but no screenshot could be attached because capture failed" in avatar
    assert 'setVoiceCaptureStatus("Screenshot unavailable; sending voice prompt...", "sending");' in avatar
    assert "const promptNotes = [screenContextIssueNote, actionHarnessIssueNote].filter(Boolean);" in avatar
    assert 'const messageForModel = promptNotes.length ? `${text}\\n\\n[${promptNotes.join(" ")}]` : text;' in avatar
    assert "message: messageForModel" in avatar
    assert "historyUserText: options.historyUserText || text" in avatar
    assert "options.screenImageDataUrl || screenSnapshot?.dataUrl || pendingScreenSnapshotForPrompt?.dataUrl" in avatar


def test_desktop_tts_treats_octet_stream_pcm_as_audio_for_pocket_fast_path():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")

    assert "shouldTreatDesktopTtsBytesAsPcm" in main
    assert 'normalized.includes("application/octet-stream")' in main
    assert '"audio/pcm, audio/l16;q=0.95, application/octet-stream;q=0.9' in main
    assert "buildDesktopWavArrayBufferFromPcm" in main


def test_desktop_pocket_streaming_uses_quality_buffering_defaults():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "requestBody.max_tokens = 256;" in main
    assert "requestBody.frames_after_eos = 4;" in main
    assert "SPEECH_PREVIEW_PCM_INITIAL_BUFFER_SECONDS = 4.00" in avatar
    assert "SPEECH_PREVIEW_PCM_SCHEDULE_LEAD_SECONDS = 0.45" in avatar
    assert "TTS_STREAMING_UTTERANCE_CHUNK_MAX_CHARS = 360" in avatar
    assert "splitStreamingTtsUtteranceChunks(text)" in avatar
    assert "speechPreviewPcmNextPlayTime = ctx.currentTime + SPEECH_PREVIEW_PCM_INITIAL_BUFFER_SECONDS" in avatar


def test_desktop_streaming_preserves_and_decodes_pcm_format_metadata():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "getDesktopTtsPcmFormat(contentType, response.headers)" in main
    assert "pcmEncoding: pcmFormat.encoding" in main
    assert "bitsPerSample: pcmFormat.bitsPerSample" in main
    assert "normalizeSpeechPreviewPcmFormat" in avatar
    assert "Float32Array" in avatar
    assert "Int16Array" in avatar
    assert "playPcmSpeechPreviewBytes(joined.subarray(0, alignedLength), sampleRate, channels, previewToken, pcmFormat)" in avatar


def test_desktop_streaming_scheduler_logs_underruns_and_coalesces_short_chunks():
    main = ELECTRON_MAIN.read_text(encoding="utf-8")
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert 'text.includes("[tts pcm]")' in main
    assert "speechPreviewPcmNextPlayTime" in avatar
    assert "SPEECH_PREVIEW_PCM_UNDERRUN_WARN_SECONDS = 0.05" in avatar
    assert "JSON.stringify(payload)" in avatar
    assert 'logSpeechPreviewPcm("debug", "scheduled chunk"' in avatar
    assert 'logSpeechPreviewPcm("warn", "queue underrun risk"' in avatar
    assert '"audioContext.currentTime": currentTime' in avatar
    assert "audioBuffer.copyToChannel(channelSamples, channel)" in avatar
    assert 'format.encoding === "float32"' in avatar
    assert "? 24000" in avatar
    assert "Math.ceil(sampleRate * channels * pcmFormat.bytesPerSample * 0.1)" in main
    assert "flushPendingPcmChunks(false)" in main
    assert "flushPendingPcmChunks(true)" in main
    assert "upstreamChunkCount" in main


def test_desktop_streaming_bubble_timing_uses_pcm_playback_schedule():
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "let speechPreviewLastPcmSchedule = null;" in avatar
    assert "speechPreviewLastPcmSchedule = {" in avatar
    assert "queueSpeechBubbleSentencesForAudioWindow(" in avatar
    assert "scheduleChunkSpeechBubbleFromPcmTiming();" in avatar
    assert "chunkAudioStartTime" in avatar
    assert "chunkAudioEndTime" in avatar

    on_started = avatar.split("onStarted: (data) => {", 1)[1].split("    onChunk: flushPcmBytes", 1)[0]
    assert "scheduleSpeechBubbleSentences(chunkText, fallbackDurationMs, previewToken)" not in on_started


def test_backend_tts_rtf_logging_is_wired():
    proxy = (PROJECT_ROOT / "src" / "servers" / "proxy_server.py").read_text(encoding="utf-8")

    assert 'print(f"[tts rtf] {label} {json.dumps(payload, sort_keys=True)}"' in proxy
    assert '"embedded_pocket_stream"' in proxy
    assert '"embedded_pocket_buffered"' in proxy
    assert '"proxy_tts_stream"' in proxy
    assert '"proxy_tts_buffered"' in proxy
    assert "first_chunk_ms" in proxy
    assert "audio_ms" in proxy
    assert "rtf=round(audio_ms / wall_ms, 3)" in proxy
