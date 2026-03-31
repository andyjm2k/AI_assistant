"""Regression tests for the Windows start.bat wrapper."""

from pathlib import Path


def test_start_bat_anchors_paths_to_script_directory():
    """start.bat should work when launched from outside the repo root."""
    start_bat = Path(__file__).resolve().parents[1] / "start.bat"
    content = start_bat.read_text(encoding="utf-8")

    assert '%~dp0' in content
    assert 'cd /d "%ROOT%"' in content
    assert 'call "%ROOT%\\venv\\Scripts\\activate.bat"' in content
    assert '"%ROOT%\\venv\\Scripts\\python.exe" "%ROOT%\\scripts\\start_all.py"' in content
