from __future__ import annotations

import json
import unittest
from urllib.request import urlopen

from amazon_batch_core import sanitize_bullet_point
from app_paths import RESOURCE_DIR
from desktop_app import LocalApplicationServer


class DesktopFoundationTests(unittest.TestCase):
    def test_packaged_resources_exist(self) -> None:
        self.assertTrue((RESOURCE_DIR / "templates" / "index.html").is_file())
        self.assertTrue((RESOURCE_DIR / "static" / "app.js").is_file())
        self.assertTrue(any(RESOURCE_DIR.glob("*.xlsx")))

    def test_range_separator_remains_readable(self) -> None:
        fixed, actions = sanitize_bullet_point("Range: 120~150 miles")
        self.assertEqual(fixed, "Range: 120-150 miles")
        self.assertIn("replaced ~ with -", actions)

    def test_local_server_uses_loopback_and_random_port(self) -> None:
        server = LocalApplicationServer()
        server.start()
        try:
            self.assertRegex(server.url, r"^http://127\.0\.0\.1:\d+/$")
            with urlopen(f"{server.url}api/health", timeout=5) as response:
                payload = json.load(response)
            self.assertEqual(payload, {"ok": True})
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
