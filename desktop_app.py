from __future__ import annotations

import logging
import multiprocessing
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from waitress import create_server

from app_paths import APP_NAME, LOG_DIR, ensure_app_directories, remove_expired_jobs
from desktop_bridge import DesktopBridge
from web_app import app


LOGGER = logging.getLogger("focus_amazon_tools")


def configure_logging() -> Path:
    ensure_app_directories()
    log_path = LOG_DIR / "focus-amazon-tools.log"
    LOGGER.setLevel(logging.INFO)
    if not LOGGER.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        LOGGER.addHandler(handler)
    return log_path


class LocalApplicationServer:
    def __init__(self) -> None:
        self._server = create_server(
            app,
            host="127.0.0.1",
            port=0,
            threads=max(4, min(16, (os.cpu_count() or 2) * 2)),
            clear_untrusted_proxy_headers=True,
        )
        self.port = int(self._server.effective_port)
        self._thread = threading.Thread(
            target=self._run,
            name="focus-amazon-local-server",
            daemon=True,
        )
        self._stopping = threading.Event()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def _run(self) -> None:
        try:
            self._server.run()
        except Exception:
            if not self._stopping.is_set():
                LOGGER.exception("The local application server stopped unexpectedly.")

    def start(self) -> None:
        self._thread.start()
        LOGGER.info("Local application server started on %s", self.url)

    def stop(self) -> None:
        LOGGER.info("Stopping local application server.")
        self._stopping.set()
        self._server.close()
        self._thread.join(timeout=5)


def show_startup_error(message: str) -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
        return

    if sys.platform == "darwin":
        import subprocess

        escaped = message.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                f'display alert "{APP_NAME}" message "{escaped}" as critical',
            ],
            check=False,
        )


def run_desktop_app() -> None:
    log_path = configure_logging()
    server: LocalApplicationServer | None = None

    try:
        removed_jobs = remove_expired_jobs()
        if removed_jobs:
            LOGGER.info("Removed %s expired job folders.", removed_jobs)

        server = LocalApplicationServer()
        server.start()

        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.create_window(
            APP_NAME,
            server.url,
            width=1220,
            height=820,
            min_size=(900, 650),
            confirm_close=False,
            text_select=True,
            js_api=DesktopBridge(),
        )
        webview.start(debug=False, private_mode=False)
    except Exception:
        LOGGER.exception("The desktop window could not be started.")
        show_startup_error(
            f"{APP_NAME} could not start. Details were written to:\n{log_path}"
        )
        raise
    finally:
        if server is not None:
            server.stop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_desktop_app()
