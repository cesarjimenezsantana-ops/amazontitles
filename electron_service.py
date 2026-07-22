from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
from logging.handlers import RotatingFileHandler

from waitress import create_server

from app_paths import LOG_DIR, ensure_app_directories, remove_expired_jobs
from web_app import app


def configure_logging() -> None:
    logger = logging.getLogger("focus_amazon_tools")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = RotatingFileHandler(
        LOG_DIR / "focus-amazon-tools.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)


def main() -> None:
    ensure_app_directories()
    configure_logging()
    remove_expired_jobs()
    server = create_server(
        app,
        host="127.0.0.1",
        port=0,
        threads=max(4, min(16, (os.cpu_count() or 2) * 2)),
        clear_untrusted_proxy_headers=True,
    )
    stopping = threading.Event()

    def stop_server(*_args) -> None:
        if stopping.is_set():
            return
        stopping.set()
        server.close()

    signal.signal(signal.SIGTERM, stop_server)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, stop_server)

    print(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{int(server.effective_port)}/",
                "pid": os.getpid(),
                "log": str(LOG_DIR / "focus-amazon-tools.log"),
            }
        ),
        flush=True,
    )
    try:
        server.run()
    except (OSError, ValueError):
        if not stopping.is_set():
            logging.getLogger("focus_amazon_tools").exception("Electron service stopped unexpectedly.")
            raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr, flush=True)
        raise
