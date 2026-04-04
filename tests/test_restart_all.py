"""Unit tests for scripts/restart_all.py."""

from scripts import restart_all


class _FakeStopAllModule:
    def __init__(self, processes):
        self._processes = processes

    def _load_processes_with_cim(self):
        return self._processes


def test_required_service_signatures_skip_studio_when_unavailable(monkeypatch):
    monkeypatch.setattr(restart_all, "_studio_available", lambda: False)

    signatures = restart_all._required_service_signatures()

    assert restart_all.STUDIO_SERVICE_KEY not in signatures
    assert "mcp_browser_use_http_server" in signatures


def test_required_service_signatures_include_studio_when_available(monkeypatch):
    monkeypatch.setattr(restart_all, "_studio_available", lambda: True)

    signatures = restart_all._required_service_signatures()

    assert signatures[restart_all.STUDIO_SERVICE_KEY] == restart_all.STUDIO_SERVICE_SIGNATURES


def test_get_service_signature_hits_matches_launcher_and_child_variants():
    stop_all_module = _FakeStopAllModule(
        {
            101: {
                "cmd": r'"C:\Users\pc\CATBot\venv\Scripts\python.exe" scripts\start_mcp_browser_server.py',
            },
            202: {
                "cmd": '"C:\\Users\\pc\\CATBot\\venv\\Scripts\\python.exe" -m src.servers.proxy_server',
            },
            303: {
                "cmd": '"C:\\Users\\pc\\CATBot\\mcp-browser-use\\.venv\\Scripts\\python.exe" -m mcp_server_browser_use.cli server',
            },
        }
    )
    required = {
        "proxy_server": {"src.servers.proxy_server"},
        "mcp_browser_server": {"scripts/start_mcp_browser_server.py"},
        "mcp_browser_use_http_server": {
            "scripts/start_mcp_browser_use_http_server.py",
            "mcp-server-browser-use server",
            "mcp_server_browser_use.cli server",
        },
    }

    hits = restart_all._get_service_signature_hits(stop_all_module, required)

    assert hits == {
        "proxy_server",
        "mcp_browser_server",
        "mcp_browser_use_http_server",
    }


def test_get_service_signature_hits_matches_studio_absolute_executable_command():
    stop_all_module = _FakeStopAllModule(
        {
            404: {
                "cmd": (
                    '"C:\\Users\\pc\\CATBot\\venv\\Scripts\\autogenstudio.exe" '
                    'serve --team config/team-config.json --host 0.0.0.0 --port 8084'
                ),
            }
        }
    )
    required = {
        restart_all.STUDIO_SERVICE_KEY: set(restart_all.STUDIO_SERVICE_SIGNATURES),
    }

    hits = restart_all._get_service_signature_hits(stop_all_module, required)

    assert hits == {restart_all.STUDIO_SERVICE_KEY}
