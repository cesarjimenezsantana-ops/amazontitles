"""
Focus Camera - Amazon Flat File Batch Updater
=============================================
Updates Title (column B), Item Name (column I), and Item Highlight (column J)
in Amazon .xlsm files using the revised title reference workbook.
SKUs that are not present in the reference workbook are removed from the
template.

Dependencies:
    pip install -r requirements.txt

CLI usage:
    python focus_amazon_batch_updater.py

Web usage:
    python web_app.py

Expected CLI folder structure:
    /
    |-- focus_amazon_batch_updater.py
    |-- Amazon Title reference.xlsx
    |   or reference/Amazon Title reference.xlsx
    |-- input/
    |   |-- 0_3D_PRINTED_PRODUCT-BACKDROP.xlsm
    |   |-- 0_OTHER_TEMPLATE.xlsm
    |   `-- ...
    `-- output/
        `-- (processed files)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from amazon_batch_core import (
    REFERENCE_FILENAME,
    find_default_reference,
    load_reference,
    process_xlsm,
)


BASE_DIR = Path(__file__).resolve().parent
REFERENCE_FILE = find_default_reference(BASE_DIR)
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"


def main() -> None:
    print("=" * 60)
    print("  Focus Camera - Amazon Flat File Batch Updater")
    print("=" * 60)

    if REFERENCE_FILE is None:
        print("\n[ERROR] Reference workbook not found.")
        print(f"  Place '{REFERENCE_FILENAME}' in this folder")
        print("  or inside a folder named 'reference/'.")
        sys.exit(1)

    if not INPUT_DIR.is_dir():
        print(f"\n[ERROR] Input folder not found: {INPUT_DIR}")
        sys.exit(1)

    xlsm_files = sorted(INPUT_DIR.glob("*.xlsm"))
    if not xlsm_files:
        print(f"\n[ERROR] No .xlsm files were found in '{INPUT_DIR}/'")
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\nLoading reference: {REFERENCE_FILE}")
    reference = load_reference(REFERENCE_FILE)
    print(f"  -> {len(reference):,} SKUs in reference\n")

    print(f"Files to process: {len(xlsm_files)}")
    print("-" * 60)

    total_updated = 0
    total_removed = 0
    total_warnings = 0
    errors: list[tuple[str, str]] = []

    for index, source in enumerate(xlsm_files, 1):
        destination = OUTPUT_DIR / source.name
        print(f"[{index:>3}/{len(xlsm_files)}] {source.name} ...", end=" ", flush=True)
        try:
            stats = process_xlsm(source, destination, reference)
            if "error" in stats:
                print(f"SKIPPED - {stats['error']}")
                errors.append((source.name, str(stats["error"])))
            else:
                warning_count = len(stats.get("warnings", []))
                total_updated += int(stats["updated"])
                total_removed += int(stats["removed"])
                total_warnings += warning_count
                print(
                    f"OK  |  updated: {int(stats['updated']):>4}  "
                    f"removed: {int(stats['removed']):>4}  "
                    f"final rows: {int(stats['final_rows'])}  "
                    f"alerts: {warning_count:>3}"
                )
        except Exception as exc:  # noqa: BLE001 - CLI reports each file and continues
            message = str(exc)
            print(f"ERROR - {message}")
            errors.append((source.name, message))

    print("-" * 60)
    print("\nFINAL SUMMARY")
    print(f"  Processed files : {len(xlsm_files) - len(errors)}/{len(xlsm_files)}")
    print(f"  Updated SKUs    : {total_updated:,}")
    print(f"  Removed rows    : {total_removed:,}")
    print(f"  Bullet alerts   : {total_warnings:,}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for filename, message in errors:
            print(f"    - {filename}: {message}")

    print(f"\nFiles ready in: {os.path.abspath(OUTPUT_DIR)}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
