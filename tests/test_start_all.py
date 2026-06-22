"""Unit tests for scripts/start_all.py."""

import shutil
import tempfile
from pathlib import Path


def test_resolve_autogenstudio_command_prefers_env(monkeypatch):
    from scripts import start_all

    monkeypatch.setenv("AUTOGENSTUDIO_CMD", r"C:\studio\Scripts\autogenstudio.exe")
    monkeypatch.setattr(start_all.shutil, "which", lambda _: None)

    resolved = start_all._resolve_autogenstudio_command()

    assert resolved == r"C:\studio\Scripts\autogenstudio.exe"


def test_resolve_autogenstudio_command_uses_venv_executable(monkeypatch):
    from scripts import start_all

    root = Path.cwd() / f"setup-env-{next(tempfile._get_candidate_names())}"
    studio_exe = root / "venv" / "Scripts" / "autogenstudio.exe"
    python_exe = root / "venv" / "Scripts" / "python.exe"
    studio_exe.parent.mkdir(parents=True, exist_ok=True)
    studio_exe.write_text("", encoding="utf-8")
    python_exe.write_text("", encoding="utf-8")

    try:
        monkeypatch.delenv("AUTOGENSTUDIO_CMD", raising=False)
        monkeypatch.setattr(start_all, "PROJECT_ROOT", root)
        monkeypatch.setattr(start_all, "VENV_PYTHON", str(python_exe))
        monkeypatch.setattr(start_all.shutil, "which", lambda _: None)

        resolved = start_all._resolve_autogenstudio_command()

        assert resolved == str(studio_exe)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_command_lines_skips_studio_when_unavailable():
    from scripts import start_all

    commands = start_all._build_command_lines(None)

    assert len(commands) == 6
    assert all("8084" not in command for command in commands)


def test_build_command_lines_includes_studio_when_available():
    from scripts import start_all

    commands = start_all._build_command_lines(r"C:\studio\Scripts\autogenstudio.exe")

    assert len(commands) == 7
    assert any("autogenstudio.exe" in command and "8084" in command for command in commands)


def test_build_child_env_sets_project_root_and_active_venv(monkeypatch):
    from scripts import start_all

    root = Path.cwd() / f"setup-env-{next(tempfile._get_candidate_names())}"
    venv_dir = root / "custom-venv"
    scripts_dir = venv_dir / "Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    python_exe = scripts_dir / "python.exe"
    python_exe.write_text("", encoding="utf-8")

    try:
        monkeypatch.setattr(start_all, "PROJECT_ROOT", root)
        monkeypatch.setattr(start_all, "VENV_PYTHON", str(python_exe))

        env = start_all._build_child_env()

        assert env["CATBOT_PROJECT_ROOT"] == str(root)
        assert env["CATBOT_INSTALL_ROOT"] == str(root)
        assert env["CATBOT_WORKSPACE"] == str(root)
        assert env["CATBOT_VENV_PYTHON"] == str(python_exe)
        assert env["VIRTUAL_ENV"] == str(venv_dir)
        assert env["PATH"].split(";")[0] == str(scripts_dir)
        assert env["PYTHONPATH"].split(";")[0] == str(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_selected_workflow_backend_uses_resolved_venv_python(monkeypatch):
    from scripts import start_all

    captured = {}
    monkeypatch.setattr(start_all, "VENV_PYTHON", r"C:\CATBot\venv\Scripts\python.exe")

    def fake_check(python_exe):
        captured["python_exe"] = python_exe
        return True, "AG2 OK"

    monkeypatch.setattr(start_all, "check_workflow_backend", fake_check)

    assert start_all._check_selected_workflow_backend() == (True, "AG2 OK")
    assert captured["python_exe"] == r"C:\CATBot\venv\Scripts\python.exe"


def test_launch_in_new_cmd_uses_new_console_flag_on_windows(monkeypatch):
    from scripts import start_all

    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs

        class DummyProc:
            def poll(self):
                return None

        return DummyProc()

    monkeypatch.setattr(start_all.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(start_all.os, "name", "nt")
    monkeypatch.setattr(start_all.subprocess, "CREATE_NEW_CONSOLE", 16, raising=False)

    start_all._launch_in_new_cmd(["python", "-m", "example"], env={"X": "1"})

    assert captured["command"] == ["python", "-m", "example"]
    assert captured["kwargs"]["creationflags"] == 16


def test_main_fails_when_service_exits_immediately(monkeypatch):
    from scripts import start_all

    class DeadProc:
        def poll(self):
            return 1

    monkeypatch.setattr(start_all.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(start_all, "_check_selected_workflow_backend", lambda: (True, "AG2 OK"))
    monkeypatch.setattr(start_all, "_build_child_env", lambda: {"X": "1"})
    monkeypatch.setattr(start_all, "_resolve_autogenstudio_command", lambda: None)
    monkeypatch.setattr(
        start_all,
        "_build_launch_specs",
        lambda studio: [("svc-a", ["python", "svc-a.py"], True), ("svc-b", ["python", "svc-b.py"], True)],
    )
    monkeypatch.setattr(
        start_all,
        "_launch_in_new_cmd",
        lambda command, env=None, new_console=True: DeadProc(),
    )
    monkeypatch.setattr(start_all, "_wait_for_required_ports", lambda ports, timeout_seconds=20.0: set())
    monkeypatch.setattr(start_all.time, "sleep", lambda _: None)

    assert start_all.main() == 1


def test_main_retries_without_new_console_after_immediate_exit(monkeypatch):
    from scripts import start_all

    class DeadProc:
        def poll(self):
            return 1

    class LiveProc:
        def poll(self):
            return None

    launches = []

    def fake_launch(command_line, env=None, new_console=True):
        launches.append((command_line, new_console))
        if new_console:
            return DeadProc()
        return LiveProc()

    monkeypatch.setattr(start_all.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(start_all, "_check_selected_workflow_backend", lambda: (True, "AG2 OK"))
    monkeypatch.setattr(start_all, "_build_child_env", lambda: {"X": "1"})
    monkeypatch.setattr(start_all, "_resolve_autogenstudio_command", lambda: None)
    monkeypatch.setattr(
        start_all,
        "_build_launch_specs",
        lambda studio: [("svc-a", ["python", "svc-a.py"], True)],
    )
    monkeypatch.setattr(start_all, "_launch_in_new_cmd", fake_launch)
    monkeypatch.setattr(start_all, "_wait_for_required_ports", lambda ports, timeout_seconds=20.0: set())
    monkeypatch.setattr(start_all.time, "sleep", lambda _: None)

    assert start_all.main() == 0
    assert launches == [(["python", "svc-a.py"], True), (["python", "svc-a.py"], False)]


def test_main_fails_when_ports_never_open(monkeypatch):
    from scripts import start_all

    class LiveProc:
        def poll(self):
            return None

    monkeypatch.setattr(start_all.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(start_all, "_check_selected_workflow_backend", lambda: (True, "AG2 OK"))
    monkeypatch.setattr(start_all, "_build_child_env", lambda: {"X": "1"})
    monkeypatch.setattr(start_all, "_resolve_autogenstudio_command", lambda: None)
    monkeypatch.setattr(
        start_all,
        "_build_launch_specs",
        lambda studio: [("svc-a", ["python", "svc-a.py"], True)],
    )
    monkeypatch.setattr(
        start_all,
        "_launch_in_new_cmd",
        lambda command, env=None, new_console=True: LiveProc(),
    )
    monkeypatch.setattr(start_all, "_wait_for_required_ports", lambda ports, timeout_seconds=20.0: {8000})
    monkeypatch.setattr(start_all.time, "sleep", lambda _: None)

    assert start_all.main() == 1


def test_main_warns_for_optional_service_exit_but_succeeds(monkeypatch):
    from scripts import start_all

    class DeadProc:
        def poll(self):
            return 1

    class LiveProc:
        def poll(self):
            return None

    launch_results = iter([LiveProc(), DeadProc(), DeadProc()])

    monkeypatch.setattr(start_all.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(start_all, "_check_selected_workflow_backend", lambda: (True, "AG2 OK"))
    monkeypatch.setattr(start_all, "_build_child_env", lambda: {"X": "1"})
    monkeypatch.setattr(start_all, "_resolve_autogenstudio_command", lambda: None)
    monkeypatch.setattr(
        start_all,
        "_build_launch_specs",
        lambda studio: [
            ("svc-a", ["python", "svc-a.py"], True),
            ("svc-optional", ["python", "svc-optional.py"], False),
        ],
    )
    monkeypatch.setattr(
        start_all,
        "_launch_in_new_cmd",
        lambda command, env=None, new_console=True: next(launch_results),
    )
    monkeypatch.setattr(start_all, "_wait_for_required_ports", lambda ports, timeout_seconds=20.0: set())
    monkeypatch.setattr(start_all.time, "sleep", lambda _: None)

    assert start_all.main() == 0
