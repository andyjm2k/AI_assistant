"""Unit tests for scripts/check_prereqs.py (CATBot prerequisite checker)."""
import pytest
from scripts.check_prereqs import check_git, check_node, check_python, check_uv


def test_check_python_returns_tuple():
    """check_python returns (bool, str)."""
    ok, msg = check_python()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    # On a dev machine Python is usually present; either ok or not with a message
    if ok:
        assert "3" in msg or "Python" in msg
    else:
        assert "python.org" in msg or "3.11" in msg


def test_check_node_returns_tuple():
    """check_node returns (bool, str)."""
    ok, msg = check_node()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    if not ok:
        assert "nodejs" in msg.lower() or "Node" in msg


def test_check_git_returns_tuple():
    """check_git returns (bool, str)."""
    ok, msg = check_git()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    if not ok:
        assert "git" in msg.lower() or "Git" in msg


def test_check_uv_returns_tuple():
    """check_uv returns (bool, str)."""
    ok, msg = check_uv()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    if not ok:
        assert "uv" in msg.lower()


def test_main_exits_zero_or_one(monkeypatch):
    """main() exits 0 when all checks pass, 1 when any fail."""
    from scripts import check_prereqs

    # Force all checks to pass
    monkeypatch.setattr(check_prereqs, "check_python", lambda: (True, "ok"))
    monkeypatch.setattr(check_prereqs, "check_node", lambda: (True, "ok"))
    monkeypatch.setattr(check_prereqs, "check_git", lambda: (True, "ok"))
    monkeypatch.setattr(check_prereqs, "check_uv", lambda: (True, "ok"))
    assert check_prereqs.main() == 0

    # Force one to fail
    monkeypatch.setattr(check_prereqs, "check_python", lambda: (False, "missing"))
    assert check_prereqs.main() == 1
