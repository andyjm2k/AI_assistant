# Model-Role Separation

## Product Purpose
CATBot does not force every interaction through a single model choice. It separates normal conversation, tool-oriented reasoning, and vision processing into distinct model roles so the product can tune latency, cost, and capability per workload.

## User-Facing Behavior
- The settings panel exposes separate selectors for `Base Chat Model`, `Tool Processing Model`, and `Vision Model`.
- Normal chat requests use the base chat model.
- Tool-heavy flows can switch to the tool model without changing the user-facing default conversation model.
- Clipboard image mode and webcam mode can use a different, vision-capable model path.
- Companion profiles persist all three model choices, so a saved character setup can restore the full stack.

## How It Works
- `index.html` defines the three model dropdowns: `base-model-dropdown`, `tool-model-dropdown`, and `vision-model-dropdown`.
- `js/app.js` initializes `baseModel`, `toolModel`, and `visionModel` with independent defaults, then keeps those values in sync with the settings UI.
- `fetchAvailableModels()` in `js/app.js` queries the backend model-discovery route and repopulates the dropdowns while preserving preferred values from current settings or a loaded companion.
- `populateModelDropdown()` normalizes and restores the selected model after discovery so model refreshes do not silently discard the user's choice.
- `getCurrentModel(isToolRequest = false)` centralizes model selection logic for outbound requests. Standard chat flows resolve to `baseModel`, while tool-driven paths can opt into `toolModel`.
- Vision-specific flows bypass the normal chat selector and explicitly use `visionModel` in clipboard and webcam request builders.
- `src/servers/proxy_server.py` exposes `/v1/proxy/models`, which calls the configured OpenAI-compatible models endpoint, extracts model IDs with `_extract_openai_compatible_model_ids()`, and returns a normalized payload for the frontend.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Settings[Settings UI in index.html] --> BaseDrop[Base model dropdown]
    Settings --> ToolDrop[Tool model dropdown]
    Settings --> VisionDrop[Vision model dropdown]

    BaseDrop --> JS[js/app.js state]
    ToolDrop --> JS
    VisionDrop --> JS

    JS --> FetchModels[fetchAvailableModels]
    FetchModels --> ProxyModels[/v1/proxy/models]
    ProxyModels --> Endpoint[Configured model endpoint]
    Endpoint --> ProxyModels
    ProxyModels --> Populate[populateModelDropdown]
    Populate --> JS

    JS --> ChatReq[Standard chat request]
    JS --> ToolReq[Tool or workflow request]
    JS --> VisionReq[Clipboard or webcam request]

    ChatReq --> BaseModel[baseModel]
    ToolReq --> ToolModel[toolModel]
    VisionReq --> VisionModel[visionModel]
```

## Primary Code References
- `index.html`
  UI definitions for the model-role controls at the settings panel.
- `js/app.js`
  Key state: `baseModel`, `toolModel`, `visionModel`, plus `defaultBaseModel`, `defaultToolModel`, and `defaultVisionModel`.
- `js/app.js`
  Key functions: `fetchAvailableModels()`, `populateModelDropdown()`, and `getCurrentModel(isToolRequest = false)`.
- `js/app.js`
  Companion integration: `getToolSettingsFromDOM()` and `loadToolSettings()` persist and restore the three model-role fields.
- `src/servers/proxy_server.py`
  Backend discovery route: `@app.get("/v1/proxy/models")`.
- `src/servers/proxy_server.py`
  Helper functions: `_extract_openai_compatible_model_ids()` and `_build_openai_compatible_models_payload()`.

## Data and Dependencies
- Depends on an OpenAI-compatible models endpoint configured through CATBot settings or environment defaults.
- The frontend stores role selections inside the current tool settings object and companion snapshots.
- Vision flows depend on the chosen model actually supporting image input; the UI separation makes that distinction visible but does not guarantee provider capability.

## Constraints and Notes
- Model-role separation improves flexibility, but it also means the user can configure incompatible combinations if a provider does not support a selected task type.
- The backend normalizes model listings from external providers, but provider metadata can still be incomplete or inconsistent.
- Some product surfaces still call `getCurrentModel()` for standard text requests, so role discipline depends on the specific request builder choosing the right path.

## Related Docs
- [Responsive Web Chat App](03_responsive_web_chat_app.md)
- [Character Profiles and Companions](04_character_profiles_and_companions.md)
- [Multimodal Inputs](10_multimodal_inputs.md)
