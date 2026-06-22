#!/usr/bin/env python3
"""
Interactive setup wizard for the CATBot Electron desktop avatar app.
Writes electron-app/.env and electron-app/config/default-desktop-config.json.
"""

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ELECTRON_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = ELECTRON_ROOT.parent
CONFIG_PATH = ELECTRON_ROOT / "config" / "default-desktop-config.json"
ENV_PATH = ELECTRON_ROOT / ".env"
PROJECT_ENV_PATH = PROJECT_ROOT / ".env"


def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def prompt_yes_no(text: str, default: bool = True) -> bool:
    default_label = "Y/n" if default else "y/N"
    raw = prompt(f"{text} ({default_label})", "y" if default else "n").lower()
    return raw in {"y", "yes", "1", "true"}


def scan_models(extension: str) -> list[str]:
  model_root = PROJECT_ROOT / "model_avatar"
  paths: list[str] = []
  if not model_root.exists():
      return paths

  pattern = f"*.{extension.lstrip('.')}"
  for file_path in model_root.rglob(pattern):
      relative = file_path.relative_to(PROJECT_ROOT).as_posix()
      paths.append(relative)
  return sorted(paths)


def choose_default_model(default_mode: str, current_default: str) -> str:
    models = scan_models(".model3.json" if default_mode == "live2d" else ".vrm")
    if not models:
        return current_default

    label = "Live2D" if default_mode == "live2d" else "VRM"
    print(f"\nAvailable {label} models:")
    for index, model in enumerate(models, start=1):
        print(f"  {index}. {model}")

    response = prompt(f"\nDefault desktop {label} model (number or path)", current_default)
    if response.isdigit():
        chosen_index = int(response) - 1
        if 0 <= chosen_index < len(models):
            return models[chosen_index]
    return response


def read_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("\n--- CATBot Electron desktop avatar wizard ---\n")
    print("This configures the separate Electron desktop companion.")
    print("The existing browser HTML client is not modified.\n")

    existing_env = read_env_file(ENV_PATH)
    project_env = read_env_file(PROJECT_ENV_PATH)
    existing_config = {}
    if CONFIG_PATH.exists():
        existing_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    default_mode = prompt(
        "Default avatar mode (vrm/live2d)",
        existing_env.get("ELECTRON_AVATAR_MODE", existing_config.get("mode", "vrm"))
    ).lower()
    if default_mode not in {"vrm", "live2d"}:
        default_mode = "vrm"

    current_model = existing_env.get(
        "ELECTRON_DEFAULT_MODEL_PATH",
        existing_config.get("modelPath", "model_avatar/CATBot/CATBot.vrm")
    )
    default_model = choose_default_model(default_mode, current_model)
    web_client_url = prompt(
        "CATBot web client URL",
        existing_env.get("ELECTRON_CATBOT_WEB_URL", existing_config.get("webClientUrl", "http://127.0.0.1:8000"))
    )
    proxy_base_url = prompt(
        "CATBot API/proxy URL",
        existing_env.get("ELECTRON_CATBOT_PROXY_URL", existing_config.get("proxyBaseUrl", web_client_url or "http://127.0.0.1:8000"))
    )
    chat_endpoint = prompt(
        "Desktop chat completions endpoint",
        existing_env.get(
            "ELECTRON_CHAT_ENDPOINT",
            existing_config.get("chatEndpoint", project_env.get("OPENAI_API_BASE", "http://localhost:1234/v1/chat/completions"))
        )
    )
    chat_model = prompt(
        "Desktop chat model (blank uses server default)",
        existing_env.get("ELECTRON_CHAT_MODEL", existing_config.get("chatModel", project_env.get("OPENAI_MODEL", "")))
    )
    chat_system_prompt = prompt(
        "Desktop chat system prompt",
        existing_env.get(
            "ELECTRON_CHAT_SYSTEM_PROMPT",
            existing_config.get(
                "chatSystemPrompt",
                "You are CATBot, a concise desktop companion. Give helpful, practical answers in a few sentences unless the user asks for detail."
            )
        )
    )
    speak_chat_replies = prompt_yes_no(
        "Speak desktop chat replies through the avatar",
        str(existing_env.get("ELECTRON_SPEAK_CHAT_REPLIES", existing_config.get("speakChatReplies", True))).lower() == "true"
    )
    trust_local_certificates = prompt_yes_no(
        "Trust configured local CATBot HTTPS certificates for web/API URLs",
        str(existing_env.get("ELECTRON_TRUST_LOCAL_CERTIFICATES", existing_config.get("trustLocalCertificates", True))).lower() == "true"
    )
    start_control_panel = prompt_yes_no(
        "Open control panel on launch",
        str(existing_env.get("ELECTRON_START_CONTROL_PANEL", existing_config.get("showControlPanelOnLaunch", True))).lower() == "true"
    )
    start_to_tray = prompt_yes_no(
        "Start to tray instead of opening the control panel",
        str(existing_env.get("ELECTRON_START_TO_TRAY", existing_config.get("startToTray", False))).lower() == "true"
    )
    launch_at_login = prompt_yes_no(
        "Launch CATBot Desktop Avatar when you sign in to Windows",
        str(existing_env.get("ELECTRON_LAUNCH_AT_LOGIN", existing_config.get("launchAtLogin", False))).lower() == "true"
    )
    start_click_through = prompt_yes_no(
        "Start in click-through mode",
        str(existing_env.get("ELECTRON_START_CLICK_THROUGH", existing_config.get("clickThrough", True))).lower() == "true"
    )
    always_on_top = prompt_yes_no(
        "Keep avatar always on top",
        str(existing_env.get("ELECTRON_ALWAYS_ON_TOP", existing_config.get("alwaysOnTop", True))).lower() == "true"
    )
    opacity = prompt(
        "Default avatar opacity",
        str(existing_env.get("ELECTRON_WINDOW_OPACITY", existing_config.get("opacity", 1)))
    )
    scale = prompt(
        "Default avatar scale",
        str(existing_env.get("ELECTRON_AVATAR_SCALE", existing_config.get("scale", 1)))
    )
    tts_endpoint = prompt(
        "TTS endpoint for desktop speech preview",
        existing_env.get(
            "ELECTRON_TTS_ENDPOINT",
            project_env.get("TTS_ENDPOINT", existing_config.get("ttsEndpoint", ""))
        )
    )
    tts_model = prompt(
        "TTS model for desktop speech preview",
        existing_env.get(
            "ELECTRON_TTS_MODEL",
            project_env.get("TTS_MODEL", existing_config.get("ttsModel", "tts-1"))
        )
    )
    tts_voice = prompt(
        "TTS voice for desktop speech preview",
        existing_env.get(
            "ELECTRON_TTS_VOICE",
            project_env.get("TTS_VOICE", existing_config.get("ttsVoice", "alloy"))
        )
    )
    width = prompt("Avatar window width", str(existing_config.get("windowBounds", {}).get("width", 480)))
    height = prompt("Avatar window height", str(existing_config.get("windowBounds", {}).get("height", 640)))
    x = prompt("Avatar start X", str(existing_config.get("windowBounds", {}).get("x", 80)))
    y = prompt("Avatar start Y", str(existing_config.get("windowBounds", {}).get("y", 80)))

    env_values = {
        "ELECTRON_AVATAR_MODE": default_mode,
        "ELECTRON_CATBOT_WEB_URL": web_client_url,
        "ELECTRON_CATBOT_PROXY_URL": proxy_base_url,
        "ELECTRON_DEFAULT_MODEL_PATH": default_model,
        "ELECTRON_START_CONTROL_PANEL": "true" if start_control_panel else "false",
        "ELECTRON_START_TO_TRAY": "true" if start_to_tray else "false",
        "ELECTRON_LAUNCH_AT_LOGIN": "true" if launch_at_login else "false",
        "ELECTRON_START_CLICK_THROUGH": "true" if start_click_through else "false",
        "ELECTRON_ALWAYS_ON_TOP": "true" if always_on_top else "false",
        "ELECTRON_WINDOW_OPACITY": opacity,
        "ELECTRON_AVATAR_SCALE": scale,
        "ELECTRON_CHAT_ENDPOINT": chat_endpoint,
        "ELECTRON_CHAT_MODEL": chat_model,
        "ELECTRON_CHAT_SYSTEM_PROMPT": chat_system_prompt,
        "ELECTRON_SPEAK_CHAT_REPLIES": "true" if speak_chat_replies else "false",
        "ELECTRON_TRUST_LOCAL_CERTIFICATES": "true" if trust_local_certificates else "false",
        "ELECTRON_TTS_ENDPOINT": tts_endpoint,
        "ELECTRON_TTS_MODEL": tts_model,
        "ELECTRON_TTS_VOICE": tts_voice
    }
    write_env(env_values)

    config = {
        "mode": default_mode,
        "modelPath": default_model,
        "scale": float(scale),
        "opacity": float(opacity),
        "clickThrough": start_click_through,
        "alwaysOnTop": always_on_top,
        "moveMode": False,
        "visible": True,
        "quickHudVisible": False,
        "showControlPanelOnLaunch": start_control_panel,
        "startToTray": start_to_tray,
        "launchAtLogin": launch_at_login,
        "expression": existing_config.get("expression", "neutral"),
        "speechBubbleText": "",
        "speechTriggerId": 0,
        "speechDurationMs": int(existing_config.get("speechDurationMs", 2600)),
        "webClientUrl": web_client_url,
        "proxyBaseUrl": proxy_base_url,
        "ttsEndpoint": tts_endpoint,
        "ttsModel": tts_model or "tts-1",
        "ttsVoice": tts_voice or "alloy",
        "chatEndpoint": chat_endpoint,
        "chatModel": chat_model,
        "chatSystemPrompt": chat_system_prompt,
        "desktopChatHistory": existing_config.get("desktopChatHistory", []),
        "speakChatReplies": speak_chat_replies,
        "vrmGraphicsQuality": existing_config.get("vrmGraphicsQuality", "medium"),
        "trustLocalCertificates": trust_local_certificates,
        "vrmTransforms": existing_config.get("vrmTransforms", {}),
        "windowBounds": {
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height)
        },
        "controlBounds": existing_config.get(
            "controlBounds",
            {
                "x": 620,
                "y": 120,
                "width": 420,
                "height": 720
            }
        ),
        "webClientBounds": existing_config.get(
            "webClientBounds",
            {
                "x": 1080,
                "y": 80,
                "width": 1120,
                "height": 820
            }
        )
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"\nWrote {ENV_PATH}")
    print(f"Wrote {CONFIG_PATH}")
    print("You can now launch the Electron desktop companion with: npm start")
    print("To build a Windows installer later: npm run dist:win")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
