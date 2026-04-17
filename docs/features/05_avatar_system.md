# Avatar System

## Product Purpose
The avatar system gives CATBot a visual embodiment layer. It supports both 2D Live2D models and 3D VRM models so the assistant can be presented as a character rather than a plain UI shell.

## User-Facing Behavior
- Users can switch between Live2D and VRM modes.
- The app scans the local `model_avatar/` directory for available assets.
- UI controls let the user tune model size, offsets, position, rotation, and VRM version.

## How It Works
- `index.html` includes separate rendering containers for Live2D and VRM.
- `js/app.js` loads external rendering libraries, initializes the chosen mode, and applies the current settings to the selected model.
- `src/servers/proxy_server.py` implements the `/v1/model-avatar/scan` endpoint, which recursively locates `.model3.json` and `.vrm` files.
- The avatar selection state is part of the same broader settings/companion system.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Scan[Scan Avatar Assets] --> Proxy[/v1/model-avatar/scan]
    Proxy --> Files[model_avatar directory tree]
    Files --> Lists[Live2D list and VRM list]
    Lists --> UI[Dropdowns and settings panel]
    UI --> Mode{Avatar mode}
    Mode --> Live2D[Load Live2D model]
    Mode --> VRM[Load VRM model]
    Live2D --> Render[Render to canvas]
    VRM --> Render
```

## Primary Code References
- `index.html`
  Elements: `live2d-container`, `vrm-container`, mode radios, model dropdowns, range controls, scan button.
- `js/app.js`
  Main areas: Live2D initialization, VRM module loading, model selection, scan integration, transform application, mode switching.
- `src/servers/proxy_server.py`
  Functions and routes: avatar scan helper and `/v1/model-avatar/scan`.
- `tests/test_model_avatar_scan.py`
  Role: verifies model discovery behavior.

## Data and Dependencies
- Uses `model_avatar/` as the asset root.
- Depends on external browser-side rendering libraries for Live2D, Pixi, Three.js, and VRM support.
- Avatar settings can be persisted via companions and local settings state.

## Constraints and Notes
- Avatar assets must already exist locally.
- The rendering path is frontend-heavy and depends on successful browser library loading.
- Live2D and VRM are separate runtime modes, not a unified renderer.

## Related Docs
- [Expressive Assistant Presence](06_expressive_assistant_presence.md)
- [Character Profiles and Companions](04_character_profiles_and_companions.md)
- [Voice Output](08_voice_output.md)

