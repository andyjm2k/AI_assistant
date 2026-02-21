# Awake Word Plan (Additive to Press-to-Talk)

## Goals and constraints

This plan adds an **optional awake-word trigger** to the current speech-to-text flow while keeping existing press-to-talk behavior intact.

- Keep press-to-talk (`start-record-btn`, semicolon hold-to-talk) unchanged.
- Add awake-word as a separate mode that can be toggled in Tool Settings.
- Reuse the same downstream transcription + chat submission path already used after manual recording.
- Prefer local/offline components and avoid subscription services.
- Work on iOS Safari where technically possible.

---

## Current integration points (existing code)

The current path already has clean touchpoints we can build on:

1. Microphone capture via `initAudioRecording()` + `AudioWorkletNode` (`recorder-worklet`).
2. Manual trigger paths:
   - Mic button click -> `toggleRecording()`.
   - Keyboard `;` key down/up -> `toggleRecording()`.
3. Existing recording lifecycle:
   - `startRecording()` begins capture.
   - `stopRecording()` ends capture and prepares audio blob.
4. Existing transcription endpoint call in `sendDataToWhisper(audioBlob)`.
5. Existing post-transcription handoff to chat pipeline via `fetchOpenAIResponse(transcribedText)`.

So the awake-word feature should call existing recording/transcription functions rather than replacing them.

---

## Recommended architecture

## 1) Add an independent AwakeWordController

Create a dedicated controller module/object (for example in `js/app.js` near STT logic or as `js/awake-word.js`) with responsibilities:

- Start/stop a low-power background listener.
- Process short audio frames from mic stream.
- Run wake-word inference.
- On wake hit, trigger a normal recording session using existing functions.
- Cooldown/debounce to prevent repeated triggers.

Important: the controller should never alter button/key event handlers for press-to-talk.

## 2) Detection strategy (no subscription first)

Use a **local wake-word engine in browser**:

- Preferred: open-source tiny model running in ONNX Runtime Web / WebAssembly in a Web Worker.
- Alternative: Porcupine Web SDK if acceptable licensing/access-key model for your project.

Recommended default approach:

- Keep all inference local in the client.
- Ship one default wake phrase model (e.g., "hey catbot").
- Optionally allow selecting from a few predefined models later.

Why this approach:

- No recurring cloud speech subscription.
- Better privacy (audio stays local until wake detected and normal transcription begins).
- Lower latency than cloud keyword spotting.

## 3) iOS Safari support strategy

iOS Safari constraints:

- Audio contexts must start from explicit user gesture.
- Background/continuous capture may pause when tab is backgrounded.
- CPU/battery budgets are tighter.

Plan for iOS compatibility:

- Require user to tap "Enable Awake Word" once per session to unlock mic/audio context.
- Run detection at reduced sample rate / frame cadence (e.g., 16 kHz mono, hop 20–40 ms).
- Add an "iOS compatibility mode" (lower sensitivity + longer cooldown) to reduce false positives and battery drain.
- Graceful fallback: if continuous wake listening is blocked, show status and keep press-to-talk fully available.

## 4) Integrate by layering on existing transcription path

Flow:

1. AwakeWordController listening is ON.
2. Wake phrase detected.
3. Controller calls existing `startRecording()`.
4. Record until either:
   - silence timeout reached (simple VAD timer), or
   - max utterance duration reached (e.g., 8–12 s), or
   - user taps stop.
5. Controller calls existing `stopRecording()`.
6. Existing `stopRecording()` -> existing `sendDataToWhisper()` -> existing `fetchOpenAIResponse()`.

This preserves your current STT/chat behavior and keeps one transcription pipeline.

## 5) Tool Settings + HTML configuration

Add Tool Settings controls:

- `Awake Word Mode` (toggle)
- `Wake Phrase` (text/select; start with fixed options for reliability)
- `Sensitivity` (range slider)
- `Post-wake max recording seconds`
- `Wake cooldown seconds`
- Optional: `Play earcon on wake` toggle

Persist in existing `toolSettings` object and load/apply through existing settings functions.

Suggested keys in settings JSON:

- `awakeWordEnabled: boolean`
- `awakeWordPhrase: string`
- `awakeWordSensitivity: number`
- `awakeWordMaxDurationSec: number`
- `awakeWordCooldownSec: number`
- `awakeWordIosCompatMode: boolean`

---

## Implementation phases

## Phase 0: Non-invasive scaffolding

- Add UI toggle + settings persistence only.
- Add status indicator text (e.g., "Awake Word: Off / Listening / Triggered / Blocked on this browser").
- No behavior changes to press-to-talk.

## Phase 1: Wake detection MVP

- Add AwakeWordController with start/stop lifecycle.
- Route mic frames to detector worker.
- On hit, trigger existing recording lifecycle.
- Add cooldown and duplicate-trigger protection.

## Phase 2: VAD and UX hardening

- Add post-wake silence timeout.
- Add start/stop earcons and visual indicator.
- Add iOS compatibility defaults and error messaging.

## Phase 3: Quality tuning

- Tune thresholds with real background noise data.
- Add per-device preset hints.
- Add diagnostics panel (false triggers, misses, average activation latency).

---

## Test plan

## Functional tests

1. Press-to-talk regression:
   - Mic button start/stop works exactly as before.
   - Semicolon shortcut works exactly as before.
2. Awake-word on/off:
   - Off: no automatic triggers.
   - On: wake phrase starts recording.
3. Pipeline continuity:
   - Wake-triggered recording reaches Whisper endpoint and receives transcript.
   - Transcript still auto-submits to chat response path.
4. Settings persistence:
   - Awake-word settings survive reload via `toolSettings`.

## Browser/device matrix

- Chrome desktop (baseline)
- Edge desktop
- Safari macOS
- Safari iOS (latest available)
- Optional Android Chrome

## Audio quality tests

- Quiet room true-positive rate.
- Moderate background noise false-positive rate.
- TV/music nearfield scenario.
- Multiple speaker voices near device.

## Performance tests

- CPU usage while idle listening.
- Battery impact on iPhone for 10/30 minute sessions.
- Memory growth/leaks over long listening sessions.

## Failure-mode tests

- Microphone permission denied/revoked.
- Audio context suspended/resumed.
- Tab background/foreground transitions.
- Network unavailable during downstream Whisper call.

---

## Security and privacy checks

1. **Least-audio retention**
   - Keep rolling buffer in memory only.
   - Clear buffers immediately when not needed.
2. **No unintended upload**
   - Do not send pre-wake audio to server.
   - Upload only post-wake utterance via existing transcription call.
3. **User consent and transparency**
   - Clear UI state when listening is active.
   - Explicit first-use consent explanation.
4. **Abuse/trigger hardening**
   - Cooldown window after wake.
   - Optional confidence threshold and multi-frame confirmation.
5. **Input hardening**
   - Validate wake phrase config length/charset.
   - Clamp numeric settings (sensitivity, durations).
6. **Logging hygiene**
   - Avoid logging raw transcripts/audio buffers in production.
   - Keep diagnostic logs behind explicit debug flag.

---

## Recommendation summary

Use an **additive AwakeWordController** that runs local wake detection (non-subscription) and triggers the existing `startRecording()`/`stopRecording()` flow. This meets all eight constraints: it preserves press-to-talk, is toggleable/configurable in Tool Settings UI, can be tuned for iOS Safari behavior, and reuses the current transcription pipeline with explicit test and security plans.
