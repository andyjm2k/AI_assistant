import importlib.util
import shutil
import uuid
import zipfile
from pathlib import Path


def _load_backup_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "backup_all.py"
    spec = importlib.util.spec_from_file_location("backup_all_module", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_backup_archive_excludes_backups_directory() -> None:
    backup_all = _load_backup_module()

    temp_dir = Path.cwd() / "tests_tmp_backup" / f"backup-test-{uuid.uuid4().hex}"
    project_root = temp_dir
    backups_dir = project_root / "backups"

    try:
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        backups_dir.mkdir(parents=True, exist_ok=True)
        (project_root / "README.md").write_text("hello", encoding="utf-8")
        (project_root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (backups_dir / "old_backup.zip").write_bytes(b"old")

        archive_path, added, skipped, warnings = backup_all.create_backup_archive(project_root, backups_dir)

        assert archive_path.parent == backups_dir
        assert archive_path.exists()
        assert added >= 2
        assert skipped == 0
        assert warnings == []

        with zipfile.ZipFile(archive_path, "r") as zipf:
            names = set(zipf.namelist())

        assert "README.md" in names
        assert "src/app.py" in names
        assert not any(name.startswith("backups/") for name in names)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
