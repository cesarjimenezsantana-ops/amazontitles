from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path


APP_NAME = "Focus Amazon Tools"
APP_ID = "com.focusamazontools.desktop"
APP_VERSION = "1.1.3"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    override = os.environ.get("FOCUS_AMAZON_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if not _is_frozen():
        return resource_dir() / "web_output"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "focus-amazon-tools"
    return Path.home() / ".local" / "share" / "focus-amazon-tools"


RESOURCE_DIR = resource_dir()
APP_DATA_DIR = user_data_dir()
WEB_OUTPUT_DIR = APP_DATA_DIR
LOG_DIR = APP_DATA_DIR / "logs"


def ensure_app_directories() -> None:
    WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def remove_expired_jobs(max_age_days: int = 14) -> int:
    cutoff = time.time() - (max_age_days * 24 * 60 * 60)
    removed = 0
    for group_name in ("jobs", "report_jobs"):
        group_dir = WEB_OUTPUT_DIR / group_name
        if not group_dir.is_dir():
            continue
        for job_dir in group_dir.iterdir():
            if not job_dir.is_dir():
                continue
            try:
                if job_dir.stat().st_mtime < cutoff:
                    shutil.rmtree(job_dir)
                    removed += 1
            except OSError:
                continue
    return removed
