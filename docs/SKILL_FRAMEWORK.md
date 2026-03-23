# CATBot Skill Framework

## Overview
CATBot includes a modular skill framework in `src/skills/` for registering, loading, executing, and packaging tool collections.

Core capabilities:
- Skill + tool abstractions (`BaseSkill`, `BaseTool`)
- Manifest-based loading (`*.skill.json`)
- Registry with alias/ambiguity handling
- Async execution with normalized result shape and hooks
- OpenAI/MCP tool schema export
- Auth-protected REST API via proxy server (`/v1/skills/*`)
- `.catbotskill` export/import for skill sharing

## Architecture
- `src/skills/base.py`: Base classes and validation logic.
- `src/skills/models.py`: Dataclass models for skill/tool metadata and execution context/result.
- `src/skills/exceptions.py`: Framework-specific exceptions.
- `src/skills/loader.py`: Manifest parsing + Python target resolution.
- `src/skills/registry.py`: Runtime registration and tool resolution.
- `src/skills/executor.py`: Tool execution engine.
- `src/skills/manager.py`: High-level API combining loader/registry/executor/packager.
- `src/skills/package.py`: `.catbotskill` archive export/import.
- `src/skills/skill_server.py`: FastAPI router/app for skill management.
- `src/skills/builtin/`: Built-in compatibility entrypoints/shims.
- `src/skills/github/`: Encapsulated GitHub skill package and integration services.
- `src/skills/manifests/`: Built-in manifests.

## Built-in Skills
- `core`: `ping`, `echo`
- `filesystem`: `list_files`, `read_text`, `write_text` (root-sandboxed)
- `GitHubProjectManager`: `initialize_repository`, `status`, `fetch`, `pull`, `push`, `sync`, `create_branch`, `checkout_branch`, `bump_version`, `commit_versioned_change`, `create_pull_request`, `list_pull_requests`, `repository_info`, `publish_release`
- `image_generation`: `generate_image` (OpenRouter Seedream 4.5 image generation)
- `googleworkspace_cli`: `check_cli`, `check_auth`, `list_available_commands`, `run_readonly_command` (Google Workspace CLI wrappers)
- `spotify_player`: `search_tracks`, `play_track`, `play_playlist` (Spotify Web API search + playback wrappers)
- `testkit`: `analyze_text`, `render_template`, `context_snapshot` (reference/demo skill)

### Spotify Player Setup Notes
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are required for Spotify API authentication.
- `SPOTIFY_REFRESH_TOKEN` is the recommended playback credential. Before `play_track` or `play_playlist`, the skill validates the current playback token and silently refreshes it when it has expired.
- `SPOTIFY_ACCESS_TOKEN` is optional. If present, the skill will validate it before playback and only fall back to `SPOTIFY_REFRESH_TOKEN` when needed.
- `SPOTIFY_REDIRECT_URI` must exactly match a redirect URI registered in your Spotify app. Do not use `localhost`: Spotify's current redirect URI rules prohibit localhost aliases, and CATBot's HTTPS certificate will not validate for `https://localhost:8002`.
- For CATBot's built-in HTTPS flow, use your trusted local cert hostname, for example `https://laura-pc.local:8002/spotify/callback` when `HTTPS_CERT_HOSTNAME=laura-pc.local`.
- After the proxy is running, open `https://<your HTTPS_CERT_HOSTNAME>:8002/spotify/authorize` once to complete the Spotify authorization-code flow. CATBot will exchange the code, then persist `SPOTIFY_REFRESH_TOKEN` and `SPOTIFY_ACCESS_TOKEN` back into `.env`.
- Search endpoints use Spotify client-credentials auth. Playback and device endpoints use user authorization with the `user-modify-playback-state` and `user-read-playback-state` scopes.
- `SPOTIFY_DEVICE_ID` is optional and can be used as the default Spotify Connect device for playback commands.

## Proxy API Endpoints
Skills endpoints are mounted on `src.servers.proxy_server` and follow the existing JWT auth model.

Public Spotify OAuth helpers:
- `GET /spotify/authorize`: Starts CATBot's Spotify authorization flow.
- `GET /spotify/callback`: Spotify OAuth callback that exchanges the code and updates `.env`.

- `GET /v1/skills`: List loaded skills
- `GET /v1/skills/tools`: List loaded tools
- `GET /v1/skills/tools/openai`: List tools as OpenAI function schema
- `GET /v1/skills/tools/mcp`: List tools in MCP-style schema
- `POST /v1/skills/manifests/load`: Load manifests from directory
- `POST /v1/skills/tools/execute`: Execute a tool
- `DELETE /v1/skills/{skill_name}`: Unregister skill
- `POST /v1/skills/packages/export`: Export a skill to `.catbotskill`
- `POST /v1/skills/packages/import`: Import `.catbotskill` and optionally load it

## .catbotskill Format
A `.catbotskill` file is a ZIP archive with:
- `package.json`: Package metadata (`format`, skill name, module target, timestamp)
- `manifests/<name>.skill.json`: Skill manifest
- `sources/<python-module-path>.py`: Optional source files (one or many)
- Manifest `package_sources` (optional): package/module roots to include in exports

Safety behavior:
- Archive members are validated to block path traversal (`..`, absolute paths)
- Source extraction is constrained under provided `source_root`

## Example Usage
```python
from src.skills import SkillManager

manager = SkillManager.from_manifest_directory("src/skills/manifests")

# Execute tool
result = await manager.execute_tool("core.ping", {})

# Export
manager.export_skill_package(
    "core",
    "scratch/core.catbotskill",
    include_sources=True,
)

# Import
manager.import_skill_package(
    package_path="scratch/core.catbotskill",
    manifest_dir="src/skills/manifests",
    load_skill=True,
    replace=True,
    overwrite=True,
)
```

## Working Example: `image_generation` Skill

The built-in `image_generation.generate_image` tool is a practical example of the framework in action:
- loaded from manifest (`src/skills/manifests/image_generation.skill.json`)
- resolved/registered by `SkillManager`
- executed through the same normalized `execute_tool` path as every other skill
- exposed automatically via `/v1/skills/tools` and `/v1/skills/tools/execute`

### 1) Execute via `SkillManager` (Python)
```python
from pathlib import Path

from src.skills import SkillContext, SkillManager

manager = SkillManager.from_manifest_directory("src/skills/manifests")

result = await manager.execute_tool(
    "image_generation.generate_image",
    {
        "prompt": "A watercolor painting of a cat astronaut",
        "output_dir": "images/demo",
        "aspect_ratio": "1:1",
    },
    context=SkillContext(scratch_dir=Path("./scratch")),
)

print(result.success)
print(result.data["images"][0]["relative_path"])  # e.g. images/demo/generated_..._1.png
```

### 2) Execute via Skills API
```bash
# 1) Authenticate with /v1/auth/login and copy access_token
# 2) Execute image tool
curl -X POST http://localhost:8002/v1/skills/tools/execute \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "image_generation.generate_image",
    "arguments": {
      "prompt": "A cinematic photo of a futuristic city at sunrise",
      "output_dir": "images/demo",
      "save_to_disk": true
    },
    "context": {
      "scratch_dir": "scratch"
    }
  }'
```

### 3) Expected result shape
Tool execution returns the framework-normalized response shape:
- `success` / `message` / `error_code` / `tool_name`
- `data` containing image metadata such as:
  - `images[].path`
  - `images[].relative_path`
  - `images[].mime_type`
  - `image_count`

## Configuration
- `SKILLS_MANIFEST_DIR` (optional): Override default manifest directory used at proxy startup.
