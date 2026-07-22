from __future__ import annotations

import secrets
from pathlib import Path


_SELECTED_FOLDERS: dict[str, Path] = {}


def consume_selected_folder(token: str) -> Path | None:
    return _SELECTED_FOLDERS.pop(token, None)


def register_selected_folder(folder_value: str) -> dict[str, str] | None:
    folder = Path(folder_value).expanduser().resolve()
    if not folder.is_dir():
        return None
    token = secrets.token_urlsafe(24)
    _SELECTED_FOLDERS[token] = folder
    count = sum(1 for path in folder.rglob("*.xlsm") if not path.name.startswith("~$"))
    return {"token": token, "name": folder.name, "count": str(count)}


class DesktopBridge:
    def choose_template_folder(self) -> dict[str, str] | None:
        import webview

        window = webview.windows[0] if webview.windows else None
        if window is None:
            return None
        result = window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
        if not result:
            return None
        return register_selected_folder(result[0])
