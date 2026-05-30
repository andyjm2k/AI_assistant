from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ELECTRON_AVATAR = ROOT / "electron-app" / "renderer" / "avatar" / "avatar.js"


def test_desktop_stt_is_explicit_toggle_without_capture_cutoff():
    avatar = ELECTRON_AVATAR.read_text(encoding="utf-8")

    assert "function isMicrophoneCaptureActive()" in avatar
    assert "micStartPromise" in avatar
    assert "micStopRequestedDuringStart" in avatar
    assert "Trigger voice chat again to stop" in avatar
    assert "if (isMicrophoneCaptureActive())" in avatar
    assert "stopMicrophoneRecording();" in avatar
    assert "function cutOffSpeechForMicrophoneCapture()" in avatar
    assert "speechGeneration += 1;" in avatar
    assert "cutOffSpeechForMicrophoneCapture();" in avatar

    assert "VOICE_CAPTURE_MAX_MS" not in avatar
    assert "setTimeout(stopMicrophoneRecording" not in avatar
    assert "startMicSilenceDetection" not in avatar
    assert "VOICE_CAPTURE_SILENCE_MS" not in avatar
    assert "VOICE_CAPTURE_START_GRACE_MS" not in avatar
