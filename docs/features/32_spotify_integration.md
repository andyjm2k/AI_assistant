# Spotify Integration

## Product Purpose
Spotify integration expands CATBot beyond productivity and research into media control. It combines an OAuth bootstrap flow with a structured playback skill so the assistant can search tracks, inspect devices, and start playback for the user.

## User-Facing Behavior
- Users can authorize CATBot against Spotify through a browser-based OAuth flow.
- After authorization, playback commands can use persisted tokens without requiring repeated manual setup.
- The Spotify skill can search tracks, inspect player devices, and issue playback commands.
- When tokens expire, the integration can refresh them or direct the user back through the authorization flow.

## How It Works
- `src/servers/proxy_server.py` exposes `/spotify/authorize` and `/spotify/callback` for the OAuth bootstrap flow.
- `/spotify/authorize` creates a short-lived state token, stores it in `spotify_oauth_pending_states`, and redirects the user to Spotify Accounts with the configured scopes.
- `/spotify/callback` validates the state, exchanges the authorization code for tokens, and persists `SPOTIFY_ACCESS_TOKEN` and optionally `SPOTIFY_REFRESH_TOKEN` back into `.env` while also updating the running process state.
- Helper functions such as `_spotify_redirect_uri()`, `_spotify_client_id()`, `_spotify_client_secret()`, `_cleanup_spotify_oauth_states()`, and `_spotify_token_request_headers()` keep the OAuth logic explicit and validated.
- `src/skills/builtin/spotify_player_skill.py` is the structured skill layer for search, device lookup, token refresh, track normalization, and playback actions.
- The manifest `src/skills/manifests/spotify_player.skill.json` wires the skill into the CATBot skill framework.

## Expanded Flow Diagram
```mermaid
flowchart TD
    User[Authorize in browser] --> Auth[/spotify/authorize]
    Auth --> State[Create pending OAuth state]
    State --> SpotifyAccounts[Spotify authorization page]
    SpotifyAccounts --> Callback[/spotify/callback]
    Callback --> Validate[Validate state and code]
    Validate --> Exchange[Token exchange with Spotify]
    Exchange --> Persist[Persist access/refresh tokens]
    Persist --> Skill[spotify_player skill]
    Skill --> Search[Track/device search]
    Skill --> Playback[Playback commands]
    Skill --> Refresh[Refresh token when needed]
```

## Primary Code References
- `src/servers/proxy_server.py`
  OAuth routes: `/spotify/authorize` and `/spotify/callback`.
- `src/servers/proxy_server.py`
  OAuth helpers: `_spotify_redirect_uri()`, `_spotify_client_id()`, `_spotify_client_secret()`, `_cleanup_spotify_oauth_states()`, `_spotify_token_request_headers()`, and `_extract_spotify_error_message(...)`.
- `src/skills/builtin/spotify_player_skill.py`
  Playback/search/device and token-refresh logic.
- `src/skills/manifests/spotify_player.skill.json`
  Skill registration manifest.
- `tests/test_spotify_oauth.py`
  OAuth flow validation.
- `tests/test_skills_framework.py`
  Skill behavior coverage for search, playback, and token refresh paths.

## Data and Dependencies
- Depends on Spotify developer credentials and a registered redirect URI.
- Stores access and refresh tokens in environment-backed configuration.
- Playback commands depend on an available Spotify Connect device and the proper user scopes.

## Constraints and Notes
- Spotify's redirect URI rules are strict, and the code explicitly rejects unsupported localhost-style configurations.
- The OAuth state store is in-memory and time-limited, which is appropriate for the short-lived browser redirect flow.
- This is a focused playback/search integration, not a full media library management feature.

## Related Docs
- [Skills Framework](42_skills_framework.md)
- [Authenticated Personal Workspace](02_authenticated_personal_workspace.md)
- [Operational Tooling](44_operational_tooling.md)
