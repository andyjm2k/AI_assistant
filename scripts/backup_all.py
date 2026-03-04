#!/usr/bin/env python3
"""
Create a ZIP backup of the CATBot project directory.

The archive is written to PROJECT_ROOT/backups and can run while services stay up.
"""
from __future__ import annotations

import argparse
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from urllib import parse as urlparse
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"


def _log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [backup_all] {message}", flush=True)


def _send_telegram_message(chat_id: Optional[str], text: str) -> None:
    if not chat_id:
        return
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        _log("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urlparse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urlrequest.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(request, timeout=12) as response:
            response.read()
    except Exception as exc:
        _log(f"Failed to send Telegram notification: {exc}")


def _format_bytes(size: int) -> str:
    value = float(max(0, size))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{size} B"


def _iter_files_for_backup(project_root: Path, backups_dir: Path) -> Tuple[List[Tuple[Path, str]], List[str]]:
    files: List[Tuple[Path, str]] = []
    warnings: List[str] = []
    backups_dir_resolved = backups_dir.resolve()

    def _on_walk_error(exc: OSError) -> None:
        warnings.append(f"{exc.filename}: {exc.strerror}")

    for dirpath, dirnames, filenames in os.walk(project_root, topdown=True, onerror=_on_walk_error):
        current_dir = Path(dirpath)

        filtered_dirs: List[str] = []
        for dirname in dirnames:
            candidate = current_dir / dirname
            try:
                if candidate.resolve() == backups_dir_resolved:
                    continue
            except OSError as exc:
                warnings.append(f"{candidate}: {exc}")
            filtered_dirs.append(dirname)
        dirnames[:] = filtered_dirs

        for filename in filenames:
            file_path = current_dir / filename
            try:
                arcname = str(file_path.relative_to(project_root)).replace("\\", "/")
            except ValueError:
                warnings.append(f"{file_path}: cannot build relative archive path")
                continue
            files.append((file_path, arcname))

    files.sort(key=lambda item: item[1])
    return files, warnings


def create_backup_archive(project_root: Path, backups_dir: Path) -> Tuple[Path, int, int, List[str]]:
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = backups_dir / f"catbot_backup_{timestamp}.zip"

    files, warnings = _iter_files_for_backup(project_root=project_root, backups_dir=backups_dir)
    added = 0
    skipped = 0

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as zipf:
        for file_path, arcname in files:
            try:
                zipf.write(file_path, arcname=arcname)
                added += 1
            except (FileNotFoundError, PermissionError, OSError) as exc:
                skipped += 1
                warnings.append(f"{file_path}: {exc}")

    return archive_path, added, skipped, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a ZIP backup of the CATBot project.")
    parser.add_argument("--chat-id", help="Telegram chat ID for status notifications.")
    parser.add_argument("--requested-by", help="Telegram user ID that requested backup.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chat_id = (args.chat_id or "").strip() or None
    requested_by = (args.requested_by or "").strip() or "unknown"
    started_at = time.time()

    _log(f"Backup requested by telegram user {requested_by}")
    _send_telegram_message(chat_id, "Backup requested. Creating ZIP archive now.")

    try:
        archive_path, added, skipped, warnings = create_backup_archive(
            project_root=PROJECT_ROOT,
            backups_dir=BACKUPS_DIR,
        )
    except Exception as exc:
        message = f"Backup failed: {exc}"
        _log(message)
        _send_telegram_message(chat_id, message)
        return 1

    elapsed = time.time() - started_at
    archive_size = archive_path.stat().st_size if archive_path.exists() else 0
    message = (
        "CATBot backup completed.\n"
        f"Archive: {archive_path}\n"
        f"Size: {_format_bytes(archive_size)}\n"
        f"Files added: {added}\n"
        f"Files skipped: {skipped}\n"
        f"Duration: {elapsed:.1f}s"
    )
    if warnings:
        message += f"\nWarnings: {len(warnings)} (see process logs for details)"

    _log(message)
    if warnings:
        for warning in warnings[:20]:
            _log(f"warning: {warning}")
        if len(warnings) > 20:
            _log(f"warning: ... and {len(warnings) - 20} more")
    _send_telegram_message(chat_id, message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
