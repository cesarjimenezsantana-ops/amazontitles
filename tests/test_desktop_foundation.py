from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from openpyxl import Workbook, load_workbook

from amazon_batch_core import load_reference, process_xlsm, sanitize_bullet_point
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

    def test_reference_loader_ignores_title_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["SKU", "Title", "Item Name", "Item Highlight"])
            sheet.append([
                "SKU-1",
                "This reference Title must be ignored",
                "New Item Name",
                "New Item Highlight",
            ])
            workbook.save(reference)

            self.assertEqual(
                load_reference(reference),
                {"SKU-1": ("New Item Name", "New Item Highlight")},
            )

    def test_reference_fields_never_overwrite_uploaded_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.xlsm"
            output = Path(temp_dir) / "output.xlsm"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Template"
            sheet["A1"] = "settings=dataRow=7"
            sheet["B4"], sheet["C4"], sheet["I4"], sheet["J4"] = (
                "Title", "SKU", "Item Name", "Item Highlight"
            )
            sheet["B5"], sheet["C5"], sheet["I5"], sheet["J5"] = (
                "::title",
                "item_sku",
                "item_name[marketplace_id=US]#1.value",
                "item_highlight[marketplace_id=US]#1.value",
            )
            sheet["B7"], sheet["C7"], sheet["I7"], sheet["J7"] = (
                "Original ~ internal catalog title",
                "SKU-1",
                "Old Amazon title",
                "Old highlight",
            )
            sheet["B8"], sheet["C8"], sheet["I8"] = (
                "Already duplicated title",
                "SKU-2",
                "Already duplicated title",
            )
            workbook.save(source)

            stats = process_xlsm(
                source,
                output,
                {
                    "SKU-1": ("New reference Amazon title", "New reference highlight"),
                    "SKU-2": ("Second reference title", None),
                },
                auto_fix_bullets=True,
            )

            self.assertNotIn("error", stats)
            processed = load_workbook(output, read_only=True)["Template"]
            self.assertEqual(processed["B7"].value, "Original ~ internal catalog title")
            self.assertEqual(processed["I7"].value, "New reference Amazon title")
            self.assertEqual(processed["J7"].value, "New reference highlight")
            self.assertEqual(processed["B8"].value, "Already duplicated title")
            sku_1_context = next(
                item["context"] for item in stats["sku_contexts"] if item["sku"] == "SKU-1"
            )
            self.assertEqual(
                sku_1_context["Source Uploaded Title"],
                "Original ~ internal catalog title",
            )
            self.assertEqual(
                sku_1_context["Source Amazon Title (Item Name)"],
                "Old Amazon title",
            )
            title_warnings = [
                warning for warning in stats["warnings"] if warning["field"] == "Title"
            ]
            self.assertEqual(title_warnings, [])

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
