# VRM Graphics Quality and Performance Plan

## Goal

Give the Electron desktop avatar explicit `Low`, `Medium`, and `High` VRM graphics profiles that:

- preserve authored VRM/MToon material detail on capable hardware;
- improve texture clarity, edge quality, color handling, and shader fidelity;
- use hardware-accelerated WebGL intentionally;
- let lower-spec devices trade visual quality for stable VRMA animation;
- report the effective renderer/GPU state so quality problems can be diagnosed;
- fail safely when a GPU, driver, model, or WebGL context cannot support the requested profile.

The first implementation should default existing installations to `Medium`. An optional `Auto` mode can be added after the three manual profiles are measured and stable.

## Implementation Status

Implemented in `feature/vrm-graphics-quality`:

- persistent Low, Medium, and High settings;
- profile-specific WebGL context options, pixel ratios, texture limits, anisotropy, and frame targets;
- authored MToon/PBR materials in Medium and High;
- unlit compatibility materials in Low;
- decoded-texture memory budgeting;
- GPU, WebGL, FPS, frame-time, draw-call, geometry, and texture diagnostics;
- renderer reloads when context-level quality settings change;
- hidden-avatar render pausing and elapsed-time-correct 30/60 FPS scheduling;
- state migration, companion-profile persistence, tests, and packaged-app verification.

Deferred follow-up work remains `Auto` quality, KTX2/Basis asset conversion, post-processing, and experimental self-shadowing.

## Current-State Review

### The current renderer deliberately selects low quality

`electron-app/renderer/avatar/avatar.js` currently creates the Three.js renderer with:

- `antialias: false`;
- `powerPreference: "low-power"`;
- `precision: "mediump"`;
- a device-pixel-ratio cap of `1.25`;
- no tone mapping;
- one ambient light and one directional light.

This is hardware-accelerated WebGL unless Chromium has disabled GPU acceleration, but it explicitly asks the browser for a low-power GPU configuration.

### Authored VRM shaders and material detail are discarded

Every loaded VRM currently passes through `applyDesktopMaterialFallback()`. That replaces every authored material, including MToon shader materials, with `THREE.MeshBasicMaterial`.

Consequences:

- shade textures, normal maps, matcaps, rim lighting, emissive detail, MToon outlines, and other authored material controls are lost;
- scene lights no longer affect the fallback material;
- the avatar appears flatter than the source VRM;
- the existing material conversion is destructive, so changing to a higher quality at runtime requires reloading the model.

The highest-impact visual improvement is to preserve the original VRM/MToon materials in `Medium` and `High`, rather than designing a new custom shader first.

### Textures are always reduced to 1024 pixels

`DESKTOP_MAX_TEXTURE_SIZE` is fixed at `1024`, and every recognized texture is downscaled during model load.

The texture collector currently only recognizes:

- `map`;
- `emissiveMap`;
- `normalMap`;
- `roughnessMap`;
- `metalnessMap`;
- `alphaMap`.

MToon has additional shader textures such as shade, matcap, rim, outline-width, and UV animation textures. These need to be included in texture accounting, disposal, and quality policy.

### Shipped models have materially different GPU costs

A scan of the embedded VRM assets found:

| Model | Embedded textures | Largest texture | Approx. decoded RGBA | Vertices | Morph targets |
| --- | ---: | ---: | ---: | ---: | ---: |
| `CATBot/CATBot.vrm` | 34 | 2048 | 228 MB | 261k | 456 |
| `Eva/Eva.vrm` | 34 | 2048 | 136 MB | 223k | 399 |
| `vroidhub/AKUMAKO.vrm` | 80 | 2048 | 564 MB | 177k | 443 |
| `vroidhub/mech-suit.vrm` | 14 | 4096 | 412 MB | 69k | 6 |
| `vroidhub/squiggle.vrm` | 5 | 4096 | 80 MB | 100k | 0 |

File size is not a sufficient quality selector. Profiles need both a maximum texture dimension and an estimated decoded-texture memory budget.

### The animation loop has CPU-side scaling opportunities

The renderer currently:

- renders on every `requestAnimationFrame`, including high-refresh displays;
- disables Electron background throttling;
- applies the model transform every frame even when it has not changed;
- updates look-at, animation mixer, pose blending, spring bones, expressions, and rendering every frame;
- creates a full body-and-finger pose snapshot every rendered frame;
- preloads the configured VRMA action library for every VRM 1.0 model.

Low quality therefore needs CPU/animation controls as well as cheaper shaders. Animation time must continue to use elapsed time so reducing render frequency does not slow the VRMA clip.

### Existing state and UI are suitable extension points

Persistent desktop settings are owned by:

- `electron-app/config/default-desktop-config.json`;
- `DEFAULT_STATE` and state normalization in `electron-app/main/main.js`;
- IPC state access in `electron-app/main/preload.js`;
- the integrated settings HUD in `electron-app/renderer/avatar/avatar.html` and `avatar.js`;
- the secondary control panel in `electron-app/renderer/control-panel/`.

The integrated avatar HUD should be the primary quality control. The secondary control panel should retain parity while it remains packaged.

## Proposed User Experience

Add a `VRM graphics quality` selector:

- `Low` — prioritizes stable animation and low memory use.
- `Medium` — balanced default.
- `High` — preserves source detail and prefers the high-performance GPU.

Show a compact effective-status line:

`High requested · High active · NVIDIA/ANGLE · 60 FPS`

If a safety cap is applied, make it visible:

`High requested · Medium active · software WebGL detected`

Changing profiles may show a short `Reloading avatar graphics…` state because WebGL context attributes and destructively resized textures cannot all be changed in place.

## Initial Quality Profiles

These values are starting points and must be validated on the model matrix below.

| Setting | Low | Medium | High |
| --- | --- | --- | --- |
| Renderer power preference | `low-power` | `default` | `high-performance` |
| Shader precision | `mediump` | `highp` | `highp` |
| MSAA | Off | On | On |
| Pixel-ratio cap | `1.0` | `1.25` | `min(devicePixelRatio, 2.0)` |
| Texture dimension cap | 512 | 1024 | Up to 4096, capability/budget limited |
| Decoded texture budget | 128 MB | 256 MB | 512 MB |
| Material mode | Unlit compatibility | Authored MToon/PBR, expensive extras reduced only if measured | Full authored MToon/PBR |
| Texture anisotropy | 1 | Up to 4 | Up to 8 or device maximum |
| Render target | 30 FPS | 60 FPS | 60 FPS or display refresh after profiling |
| Spring-bone update | 30 Hz | 60 Hz | 60 Hz |
| Look-at/manual idle update | 30 Hz | 60 Hz | 60 Hz |
| Pose snapshot policy | Transitions/actions only | Transitions/actions only | Transitions/actions only |
| Shadows | Off | Off | Experimental, off by default until measured |
| Hidden-window rendering | Paused | Paused | Paused |

Important constraints:

- `powerPreference` is a browser hint, not a guarantee that Windows will choose a discrete GPU.
- High mode must respect `renderer.capabilities.maxTextureSize`.
- A texture-memory budget can reduce individual High textures when a model would otherwise exceed a safe allocation.
- Do not globally enable expensive post-processing in the first release. A transparent desktop avatar gains more from correct MToon materials, texture resolution, anisotropy, and MSAA than from bloom or screen-space effects.

## Target Architecture

### 1. Isolate renderer-quality policy

Add a renderer module such as:

`electron-app/renderer/avatar/vrm-quality.js`

It should own:

- profile definitions;
- profile normalization;
- renderer constructor options;
- texture collection and memory estimation;
- texture resize decisions;
- material policy;
- anisotropy and mipmap policy;
- frame/update intervals;
- runtime capability clamping;
- effective-quality diagnostics.

This avoids adding another large subsystem directly to the existing `avatar.js`.

### 2. Persist requested quality separately from effective quality

Add persistent state:

```json
{
  "vrmGraphicsQuality": "medium"
}
```

Keep runtime-only diagnostics out of the persisted state:

```js
{
  requestedQuality: "high",
  effectiveQuality: "medium",
  downgradeReason: "software-webgl",
  renderer: "...",
  fps: 48,
  frameTimeP95Ms: 27.4,
  drawCalls: 31,
  triangles: 174000,
  textures: 34,
  estimatedTextureMemoryMb: 228
}
```

Validate the persisted value in `main.js`; unknown values should become `medium`.

### 3. Recreate the renderer when context attributes change

MSAA, power preference, and requested precision are WebGL context creation options. A profile transition should:

1. invalidate pending model/VRMA loads;
2. stop the render loop;
3. remove and dispose the current VRM;
4. dispose the Three.js renderer and force context loss where supported;
5. construct a renderer using the new profile;
6. rebuild scene lights and camera state;
7. reload the selected model;
8. restore transform, expression, active speech state, and animation intent;
9. restart the loop and update diagnostics.

Debounce profile changes so rapid selector changes cause only one reload.

### 4. Preserve authored materials by default

Replace unconditional `applyDesktopMaterialFallback()` with a profile-aware material path:

- `High`: retain authored MToon and glTF PBR materials unchanged except for safe color-space, filtering, and compatibility fixes.
- `Medium`: initially retain authored materials as well. Disable individual expensive MToon features only after profiling proves a useful gain.
- `Low`: convert to a compatibility material using base color, diffuse map, alpha map, opacity, alpha test, side, skinning, morph targets, and vertex colors.

The Low conversion must preserve:

- skinned-mesh support;
- morph-target expressions and lip sync;
- alpha-cutout hair and clothing;
- material sidedness and depth behavior;
- render order where transparency requires it.

Use one comprehensive `collectMaterialTextures()` path for budgeting and disposal. It must include standard materials, MToon accessors, and texture-valued shader uniforms.

### 5. Apply a budgeted texture policy

Before resizing textures:

1. collect unique textures;
2. read source dimensions and semantic role;
3. estimate decoded GPU memory including mip overhead;
4. clamp against WebGL maximum texture size;
5. assign profile caps;
6. reduce textures until the profile budget is met.

Suggested priority:

1. base color and alpha/detail masks;
2. normal and shade textures;
3. emissive and matcap;
4. rim, roughness, and metalness;
5. lower-impact utility textures.

Avoid scaling every texture to the same dimension when a small utility map is already adequate.

For each retained texture:

- keep color maps in sRGB;
- keep normal, roughness, metalness, and masks in linear color space;
- enable mipmaps where supported;
- use trilinear minification;
- apply profile-limited anisotropy;
- mark the texture for upload only after all changes are complete.

### 6. Improve the light and color pipeline carefully

Keep `SRGBColorSpace` output.

Create a stable transparent-avatar light rig:

- soft key directional light;
- weaker fill or hemisphere light;
- optional rim light for non-MToon/PBR materials.

Do not enable ACES tone mapping globally without side-by-side model validation. It can improve PBR models but can alter authored MToon colors. If needed, make tone mapping material/profile aware.

Do not enable shadow maps in the initial High profile. First restore MToon materials and measure their cost. Self-shadowing can be evaluated as a separate High-only enhancement.

### 7. Separate render rate from animation time

Use one scheduler with profile-specific rates:

- animation mixer time advances using real elapsed time;
- rendering can be capped at 30 FPS in Low;
- spring-bone and look-at updates can run at a fixed rate;
- expressions and lip sync remain responsive;
- large frame gaps reset spring physics as they do now.

Remove the unconditional per-frame pose snapshot. Capture/reuse snapshots only when:

- starting or ending an action;
- beginning a pose blend;
- switching from VRMA playback to manual idle;
- explicitly needed for recovery.

Cache the model transform and only write scene position/scale/rotation when state changes.

Pause the VRM render/update loop while the avatar window is hidden. Render one frame after visibility, focus, resize, model, expression, or settings changes.

Keep `backgroundThrottling: false` only if speech/animation behavior demonstrably requires it while visible. Otherwise remove it and control scheduling explicitly.

### 8. Add GPU and frame diagnostics

Main process:

- expose whether Electron hardware acceleration is enabled;
- expose `app.getGPUFeatureStatus()`;
- expose basic GPU information after Electron reports GPU readiness;
- do not expose unnecessary device identifiers outside local diagnostics.

Renderer:

- collect rolling FPS and p50/p95 frame time;
- time animation/physics and render work separately;
- expose `renderer.info.render.calls`, triangles, programs, geometries, and textures;
- report WebGL version, maximum texture size, and maximum anisotropy;
- count WebGL context losses.

Show this in the existing HUD diagnostics panel and include a copyable JSON summary.

### 9. Add safety downgrade rules

Manual quality should normally remain fixed. Safety conditions may reduce the effective profile:

- software-only or disabled WebGL/GPU features;
- repeated WebGL context loss;
- model texture estimate above the profile budget;
- unsupported high precision or texture size;
- model load or shader compilation failure.

Fallback order:

`High authored` -> `Medium authored` -> `Low unlit` -> existing static fallback image.

Log the exact reason and keep the user's requested profile unchanged so it can be retried after a driver or hardware change.

### 10. Add optional adaptive quality after manual profiles are stable

An `Auto` option can start at Medium and use sustained measurements:

- downgrade after p95 frame time exceeds the target for several seconds;
- upgrade only after a longer stable headroom period;
- use hysteresis and a cooldown to avoid oscillation;
- never change profile in the middle of a model load;
- defer upgrades during active speech or VRMA transitions;
- expose both requested `Auto` and effective `Low/Medium/High`.

Auto should be a later phase because it is only useful after each manual profile has predictable costs.

## Implementation Phases

### Phase 1: State, diagnostics, and baseline measurements

Files:

- `electron-app/config/default-desktop-config.json`
- `electron-app/main/main.js`
- `electron-app/main/preload.js`
- `electron-app/renderer/avatar/avatar.html`
- `electron-app/renderer/avatar/avatar.js`
- `electron-app/renderer/control-panel/*`
- `tests/test_electron_avatar_runtime.py`

Work:

- add and validate `vrmGraphicsQuality`;
- add the quality selector to both settings surfaces;
- add safe GPU diagnostics IPC;
- add renderer/frame diagnostics without changing visual behavior;
- record baseline screenshots and performance for the test matrix.

Exit criteria:

- requested quality persists;
- diagnostics identify hardware acceleration and effective WebGL capabilities;
- no change to model appearance or animation behavior yet.

### Phase 2: Profile-aware renderer lifecycle

Files:

- new `electron-app/renderer/avatar/vrm-quality.js`
- `electron-app/renderer/avatar/avatar.js`
- `electron-app/renderer/avatar/avatar.html`

Work:

- define the three profiles;
- move renderer creation and resize policy behind the profile module;
- implement safe renderer/model recreation;
- apply pixel ratio, MSAA, precision, and power preference;
- preserve state across reload;
- add context-loss downgrade behavior.

Exit criteria:

- changing profile reliably recreates the renderer once;
- stale model and VRMA loads cannot attach to the new renderer;
- repeated profile changes do not leak textures, materials, mixers, or contexts.

### Phase 3: Material and texture fidelity

Work:

- stop replacing materials in Medium and High;
- implement comprehensive MToon/PBR texture collection;
- apply correct color spaces, filtering, mipmaps, and anisotropy;
- implement profile dimension and decoded-memory budgets;
- retain the compatibility material only for Low and safety fallback;
- add model-load diagnostics for texture and material decisions.

Exit criteria:

- CATBot/Eva material detail is visibly closer to the source VRM in Medium and High;
- High retains 2K source detail on the standard models;
- heavy 4K/80-texture models remain within the configured memory budget;
- alpha hair, expressions, lip sync, and VRMA skinning remain correct.

### Phase 4: Animation smoothness and CPU scaling

Work:

- add profile-specific render/update rates;
- eliminate unconditional frame snapshots and unchanged transform writes;
- pause hidden-window rendering;
- measure and tune spring-bone rates;
- consider lazy VRMA loading in Low if preload memory/CPU is material.

Exit criteria:

- Low maintains correctly timed VRMA playback at a 30 FPS render target;
- animation does not run in slow motion when frames are skipped;
- speech lip sync and expression updates remain responsive;
- idle CPU/GPU use falls when the avatar is hidden.

### Phase 5: Validation, adaptive mode, and optional asset optimization

After manual profiles are accepted:

- add `Auto`;
- evaluate KTX2/Basis GPU-compressed textures for bundled models;
- evaluate offline optimized model variants or a model-analysis tool;
- evaluate High-only self-shadowing as a separately measurable feature;
- consider a dependency upgrade in its own change set, not mixed with the quality refactor.

KTX2 is valuable for VRAM and upload time, but it changes the asset pipeline and requires GLTFLoader/KTX2Loader integration plus transcoder packaging. It should not block the initial quality profiles.

## Validation Matrix

Test at minimum:

### Models

- `CATBot/CATBot.vrm` — default, high vertices/morphs, 34 textures.
- `Eva/Eva.vrm` — standard VRMA behavior.
- `vroidhub/AKUMAKO.vrm` — extreme texture/material count.
- `vroidhub/mech-suit.vrm` — 4K texture pressure.
- `vroidhub/ghost-spider.vrm` — small compatibility case.
- one VRM 0.x model and one VRM 1.0 model.

### Hardware classes

- integrated Intel/AMD GPU laptop;
- discrete NVIDIA/AMD GPU system;
- high-DPI display;
- 60 Hz and high-refresh display;
- Chromium software-rendering/fallback case where practical.

### Behaviors

- idle, look-at, blink, expressions, and lip sync;
- each standard VRMA action;
- AutoDance VRMA playback;
- transparent hair and clothing;
- profile switching during idle, speech, and animation;
- model switching immediately after profile switching;
- hide/show, display scale change, window resize, sleep/resume;
- WebGL context loss and recovery;
- packaged Windows build, not only `npm start`.

### Measurements

Capture for each model/profile/device:

- average FPS and p95 frame time;
- animation/physics CPU time;
- render CPU time;
- draw calls and triangles;
- texture count and estimated decoded memory;
- renderer process working set;
- GPU process memory where available;
- model load time and first-frame time;
- context-loss count;
- reference screenshot.

## Acceptance Criteria

### High

- uses authored MToon/PBR materials;
- requests high-performance rendering;
- preserves standard-model 2K textures unless a documented capability or budget limit applies;
- has visibly sharper textures and edges than the current implementation;
- keeps VRMA animation stable on a representative discrete GPU;
- does not exceed the configured texture budget silently.

### Medium

- is the default;
- preserves authored materials;
- remains stable on representative integrated graphics;
- targets 60 FPS at the default 480x640 avatar window;
- has bounded texture memory and no repeated context loss.

### Low

- uses the compatibility material and reduced texture/pixel cost;
- maintains correct skinning, morph expressions, alpha cutouts, lip sync, and VRMA timing;
- targets a stable 30 FPS on the low-spec test device;
- lowers GPU/CPU use materially versus Medium;
- can recover to Medium or High through a clean model/renderer reload.

### General

- all quality changes persist;
- effective quality and downgrade reason are visible;
- no renderer, texture, material, mixer, timer, or object-URL leaks after repeated switches;
- no regression to Live2D mode;
- all existing Electron avatar runtime tests pass;
- new tests cover quality normalization, reload generation guards, diagnostics IPC, and fallback order.

## Recommended Delivery Structure

Implement this as four reviewable changes:

1. quality state, settings UI, and diagnostics;
2. renderer recreation and profile infrastructure;
3. authored materials plus texture budgeting;
4. animation scheduling, performance tuning, and final validation.

Keep dependency upgrades, KTX2 asset conversion, post-processing, and experimental shadows out of the first three changes. They would make visual regressions and performance changes harder to attribute.

## Primary Technical Decision

The project should not begin by writing a new custom avatar shader. The immediate problem is that the existing loader already supplies purpose-built VRM/MToon shaders and the desktop path discards them.

The correct first move is:

1. preserve authored MToon/PBR materials in Medium and High;
2. add renderer and texture quality profiles;
3. scale CPU animation work independently;
4. measure;
5. only add custom shader effects when a specific visual gap remains.
