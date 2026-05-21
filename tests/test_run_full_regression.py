"""Unit tests for the master regression runner."""

import shutil
import tempfile
from pathlib import Path


def _scratch_test_root() -> Path:
    root = Path.cwd() / "scratch" / f"regression-runner-test-{next(tempfile._get_candidate_names())}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_default_suite_order_matches_registry():
    from scripts import run_full_regression

    registry = run_full_regression.build_suite_registry()

    assert tuple(registry) == run_full_regression.DEFAULT_SUITE_ORDER
    assert set(registry) == set(run_full_regression.DEFAULT_SUITE_ORDER)


def test_expand_suite_names_defaults_to_all_and_accepts_commas():
    from scripts import run_full_regression

    assert run_full_regression._expand_suite_names(None) == list(run_full_regression.DEFAULT_SUITE_ORDER)
    assert run_full_regression._expand_suite_names(["python-tests,electron-verify", "javascript-syntax"]) == [
        "python-tests",
        "electron-verify",
        "javascript-syntax",
    ]


def test_python_tests_suite_runs_all_pytest_tests_with_workspace_cache(monkeypatch):
    from scripts import run_full_regression

    root = _scratch_test_root()
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    (tests_dir / "test_b.py").write_text("def test_b():\n    assert True\n", encoding="utf-8")
    commands = []

    def fake_run_command(command, *, cwd, env, timeout_seconds):
        commands.append({
            "command": command,
            "cwd": cwd,
            "env": env,
            "timeout_seconds": timeout_seconds,
        })
        return 0

    monkeypatch.setattr(run_full_regression, "_run_command", fake_run_command)
    try:
        context = run_full_regression.RegressionContext(
            project_root=root,
            python_exe="python",
            env={"PATH": ""},
        )

        result = run_full_regression.run_python_tests(context)

        assert result.status == "PASS"
        assert result.message == "2 files run"
        assert [item["cwd"] for item in commands] == [root, root]
        assert commands[0]["command"][:4] == ["python", "-m", "pytest", str(Path("tests") / "test_a.py")]
        assert commands[1]["command"][:4] == ["python", "-m", "pytest", str(Path("tests") / "test_b.py")]
        assert "-v" in commands[0]["command"]
        cache_option_index = commands[0]["command"].index("-o")
        cache_arg = commands[0]["command"][cache_option_index + 1]
        assert cache_arg == f"cache_dir={root / 'scratch' / 'regression' / 'pytest_cache'}"
        assert (root / "scratch" / "regression" / "pytest_cache").is_dir()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_javascript_discovery_uses_owned_sources_and_excludes_vendor():
    from scripts import run_full_regression

    root = _scratch_test_root()
    try:
        owned = root / "electron-app" / "renderer" / "avatar" / "avatar.js"
        vendor = root / "electron-app" / "renderer" / "avatar" / "vendor" / "ignored.js"
        app_js = root / "js" / "app.js"
        root_js = root / "recorder-worklet-processor.js"
        for path in (owned, vendor, app_js, root_js):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("const ok = true;\n", encoding="utf-8")

        discovered = {
            str(path.relative_to(root)).replace("\\", "/")
            for path in run_full_regression.discover_javascript_syntax_files(root)
        }

        assert "electron-app/renderer/avatar/avatar.js" in discovered
        assert "electron-app/renderer/avatar/vendor/ignored.js" not in discovered
        assert "js/app.js" in discovered
        assert "recorder-worklet-processor.js" in discovered
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_javascript_syntax_suite_checks_each_discovered_file(monkeypatch):
    from scripts import run_full_regression

    root = _scratch_test_root()
    first = root / "js" / "app.js"
    second = root / "electron-app" / "main" / "main.js"
    commands = []

    try:
        first.parent.mkdir(parents=True, exist_ok=True)
        second.parent.mkdir(parents=True, exist_ok=True)
        first.write_text("const a = 1;\n", encoding="utf-8")
        second.write_text("const b = 2;\n", encoding="utf-8")

        monkeypatch.setattr(run_full_regression.shutil, "which", lambda *args, **kwargs: "node")
        monkeypatch.setattr(run_full_regression, "discover_javascript_syntax_files", lambda project_root: [first, second])

        def fake_run_command(command, *, cwd, env, timeout_seconds):
            commands.append(command)
            return 0

        monkeypatch.setattr(run_full_regression, "_run_command", fake_run_command)
        context = run_full_regression.RegressionContext(
            project_root=root,
            python_exe="python",
            env={"PATH": ""},
        )

        result = run_full_regression.run_javascript_syntax(context)

        assert result.status == "PASS"
        assert commands == [
            ["node", "--check", str(Path("js") / "app.js")],
            ["node", "--check", str(Path("electron-app") / "main" / "main.js")],
        ]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_context_uses_workspace_temp_dir(monkeypatch):
    from scripts import run_full_regression

    root = _scratch_test_root()
    try:
        monkeypatch.setattr(run_full_regression, "resolve_project_root", lambda: root)
        monkeypatch.setattr(run_full_regression, "resolve_venv_python", lambda project_root: "python")
        monkeypatch.setattr(run_full_regression, "build_script_env", lambda project_root, python_exe: {"PATH": ""})

        context = run_full_regression.build_context()

        expected_tmp = root / "scratch" / "regression" / "tmp"
        assert context.env["TEMP"] == str(expected_tmp)
        assert context.env["TMP"] == str(expected_tmp)
        assert context.env["TMPDIR"] == str(expected_tmp)
        assert expected_tmp.is_dir()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_main_rejects_unknown_suite(capsys):
    from scripts import run_full_regression

    exit_code = run_full_regression.main(["--suite", "missing-suite"])

    assert exit_code == 2
    assert "Unknown regression suite" in capsys.readouterr().err
