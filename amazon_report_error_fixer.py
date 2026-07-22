"""
Create a corrected Amazon flat-file retry from an Amazon processing summary.

The script keeps only SKUs that still need attention, removes SKUs that Amazon
already accepted cleanly, fixes the common text issues, and preserves the XLSM
container.
"""

from __future__ import annotations

import argparse
import copy
import csv
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from amazon_batch_core import (
    q,
    col_letters,
    col_num,
    detect_template_sheet,
    sanitize_bullet_point,
    sanitize_text_field,
)


XML_NS = "http://www.w3.org/XML/1998/namespace"
MAX_LENGTH_RE = re.compile(r"allowed maximum \((\d+) characters\)", re.I)
PROHIBITED_RE = re.compile(r"prohibited phrases \[([^\]]+)\]", re.I)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def letters_for_col(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def normalize_space(value: str) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def strip_html(value: str) -> str:
    without_tags = HTML_TAG_RE.sub(" ", str(value or ""))
    without_entities = (
        without_tags.replace("&nbsp;", " ")
        .replace("&amp;", " and ")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", " ")
        .replace("&gt;", " ")
    )
    return normalize_space(without_entities)


def compact_marketing_text(value: str, max_length: int) -> tuple[str, list[str]]:
    cleaned, actions = sanitize_bullet_point(value, max_length=10_000)
    parts = [part.strip(" ,;") for part in cleaned.split(",") if part.strip(" ,;")]
    if parts and len(cleaned) > max_length:
        selected: list[str] = []
        for part in parts:
            candidate = ", ".join([*selected, part])
            if len(candidate) <= max_length:
                selected.append(part)
            if selected:
                cleaned = ", ".join(selected)
                actions.append(f"prioritized complete segments up to {max_length} characters")

    shortened, more_actions = sanitize_bullet_point(cleaned, max_length=max_length)
    actions.extend(action for action in more_actions if action not in actions)
    return shortened, actions


@dataclass
class ProcessingReport:
    pure_success_skus: set[str] = field(default_factory=set)
    errored_skus: set[str] = field(default_factory=set)
    report_skus: set[str] = field(default_factory=set)
    errors_by_sku: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    summary: dict[str, int] = field(default_factory=dict)


class XlsmTemplate:
    def __init__(self, path: Path):
        self.path = path
        self.zin = zipfile.ZipFile(path, "r")
        self.sheet_part = detect_template_sheet(self.zin)
        if not self.sheet_part:
            raise ValueError("The workbook does not contain a Template sheet.")
        self.shared_root, self.strings, self.string_index = self._read_shared_strings()
        self.sheet_root = ET.fromstring(self.zin.read(self.sheet_part))
        self.sheet_data = self.sheet_root.find(q("sheetData"))
        if self.sheet_data is None:
            raise ValueError("The Template sheet does not contain sheetData.")
        self.rows = {int(row.get("r")): row for row in self.sheet_data.findall(q("row"))}

    def close(self) -> None:
        self.zin.close()

    def _read_shared_strings(self) -> tuple[ET.Element, list[str], dict[str, int]]:
        root = ET.fromstring(self.zin.read("xl/sharedStrings.xml"))
        strings = [
            "".join(text.text or "" for text in si.findall(".//" + q("t")))
            for si in root
        ]
        index: dict[str, int] = {}
        for idx, value in enumerate(strings):
            if value not in index:
                index[value] = idx
        return root, strings, index

    def shared_index(self, value: str) -> int:
        if value in self.string_index:
            return self.string_index[value]
        si_el = ET.SubElement(self.shared_root, q("si"))
        text_el = ET.SubElement(si_el, q("t"))
        if value != value.strip() or "  " in value:
            text_el.set(f"{{{XML_NS}}}space", "preserve")
        text_el.text = value
        self.strings.append(value)
        self.string_index[value] = len(self.strings) - 1
        return self.string_index[value]

    def cell_text(self, cell: ET.Element | None) -> str:
        if cell is None:
            return ""
        if cell.get("t") == "inlineStr":
            text = cell.find(q("is") + "/" + q("t"))
            return text.text or "" if text is not None else ""
        value = cell.find(q("v"))
        if value is None or value.text is None:
            return ""
        if cell.get("t") == "s":
            try:
                return self.strings[int(value.text)]
            except (ValueError, IndexError):
                return ""
        return value.text

    def row_values(self, row_number: int) -> dict[str, str]:
        row = self.rows.get(row_number)
        if row is None:
            return {}
        return {
            col_letters(cell.get("r", "")): self.cell_text(cell)
            for cell in row.findall(q("c"))
            if cell.get("r")
        }

    def headers(self) -> dict[str, str]:
        return self.row_values(4)

    def attrs(self) -> dict[str, str]:
        return self.row_values(5)

    def attr_to_col(self) -> dict[str, str]:
        return {value: col for col, value in self.attrs().items() if value}

    def data_start_row(self) -> int:
        settings = " ".join(self.row_values(1).values())
        match = re.search(r"dataRow=(\d+)", settings)
        return int(match.group(1)) if match else 7

    def cells_for_row(self, row: ET.Element) -> dict[str, ET.Element]:
        return {
            col_letters(cell.get("r", "")): cell
            for cell in row.findall(q("c"))
            if cell.get("r")
        }

    def row_sku(self, row: ET.Element, sku_col: str) -> str:
        return self.cell_text(self.cells_for_row(row).get(sku_col)).strip()

    def set_cell_text(
        self,
        row: ET.Element,
        cells: dict[str, ET.Element],
        letter: str,
        value: str,
    ) -> None:
        cell = cells.get(letter)
        row_number = int(row.get("r", "0"))
        if cell is None:
            cell = ET.Element(q("c"))
            cell.set("r", f"{letter}{row_number}")
            target = col_num(letter)
            position = len(row)
            for idx, existing in enumerate(row):
                if col_num(col_letters(existing.get("r", ""))) > target:
                    position = idx
                    break
            row.insert(position, cell)
            cells[letter] = cell

        for child in list(cell):
            cell.remove(child)
        cell.set("t", "s")
        value_el = ET.SubElement(cell, q("v"))
        value_el.text = str(self.shared_index(value))

    def clear_cell(self, cells: dict[str, ET.Element], letter: str) -> bool:
        cell = cells.get(letter)
        if cell is None or not list(cell):
            return False
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)
        return True

    def renumber_row(self, row: ET.Element, new_number: int) -> None:
        row.set("r", str(new_number))
        for cell in row.findall(q("c")):
            if cell.get("r"):
                letter = col_letters(cell.get("r", ""))
                cell.set("r", f"{letter}{new_number}")

    def replace_data_rows(self, rows: list[ET.Element], data_start: int, sku_col: str) -> None:
        for child in list(self.sheet_data):
            self.sheet_data.remove(child)

        preserved = []
        for row_number, row in sorted(self.rows.items()):
            if row_number >= data_start:
                continue
            if row_number == data_start - 1:
                sku = self.row_sku(row, sku_col) if sku_col else ""
                if sku and sku != "ABC123":
                    continue
            preserved.append(row)
        for row in preserved:
            self.sheet_data.append(row)

        row_number = data_start
        for row in rows:
            self.renumber_row(row, row_number)
            self.sheet_data.append(row)
            row_number += 1

        dimension = self.sheet_root.find(q("dimension"))
        if dimension is not None:
            current = dimension.get("ref", "A1:A1")
            dimension.set("ref", re.sub(r"\d+$", str(row_number - 1), current))

    def save(self, output_path: Path) -> None:
        self.shared_root.set("count", str(len(self.strings)))
        self.shared_root.set("uniqueCount", str(len(self.strings)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in self.zin.infolist():
                if item.filename == self.sheet_part:
                    data = ET.tostring(self.sheet_root, encoding="utf-8", xml_declaration=True)
                elif item.filename == "xl/sharedStrings.xml":
                    data = ET.tostring(self.shared_root, encoding="utf-8", xml_declaration=True)
                else:
                    data = self.zin.read(item.filename)
                zout.writestr(item, data)


def parse_processing_report(path: Path) -> ProcessingReport:
    workbook = XlsmTemplate(path)
    try:
        headers = workbook.headers()
        attrs = workbook.attrs()
        rows = workbook.rows
        report = ProcessingReport()

        for row_number, row in rows.items():
            if row_number < 7:
                continue
            cells = workbook.cells_for_row(row)
            sku = workbook.cell_text(cells.get("D")).strip()
            if not sku or sku == "ABC123":
                continue
            status = workbook.cell_text(cells.get("A")).strip()
            errors = workbook.cell_text(cells.get("B")).strip()
            report.report_skus.add(sku)
            if status == "SUCCESS" and errors in {"", "0"}:
                report.pure_success_skus.add(sku)
            else:
                report.errored_skus.add(sku)

        with zipfile.ZipFile(path, "r") as zin:
            for name in zin.namelist():
                if not name.startswith("xl/comments") or not name.endswith(".xml"):
                    continue
                comments_root = ET.fromstring(zin.read(name))
                for comment in comments_root.findall(".//" + q("comment")):
                    ref = comment.get("ref", "")
                    match = re.match(r"([A-Z]+)(\d+)", ref)
                    if not match:
                        continue
                    col, row_number = match.group(1), int(match.group(2))
                    text = "".join(
                        text_el.text or "" for text_el in comment.findall(".//" + q("t"))
                    )
                    text = text.replace("_x000d_", " ").strip()
                    if "ERROR" not in text:
                        continue
                    sku = workbook.row_values(row_number).get("D", "").strip()
                    if not sku or sku == "ABC123":
                        continue
                    report.errors_by_sku[sku].append(
                        {
                            "report_row": row_number,
                            "report_col": col,
                            "header": headers.get(col, ""),
                            "attr": attrs.get(col, ""),
                            "message": normalize_space(text),
                        }
                    )

        report.summary = {
            "report_skus": len(report.report_skus),
            "pure_success_skus": len(report.pure_success_skus),
            "errored_skus": len(report.errored_skus),
            "error_comments": sum(len(items) for items in report.errors_by_sku.values()),
        }
        return report
    finally:
        workbook.close()


def source_columns(workbook: XlsmTemplate) -> dict[str, str]:
    attrs = workbook.attr_to_col()
    return {
        "listing_status": attrs.get("::listing_status", "A"),
        "title": attrs.get("::title", "B"),
        "sku": attrs.get("contribution_sku#1.value", "C"),
        "item_name": attrs.get(
            "item_name[marketplace_id=ATVPDKIKX0DER][language_tag=en_US]#1.value", "I"
        ),
        "item_highlight": attrs.get(
            "title_differentiation[marketplace_id=ATVPDKIKX0DER][language_tag=en_US]#1.value",
            "J",
        ),
        "brand": attrs.get(
            "brand[marketplace_id=ATVPDKIKX0DER][language_tag=en_US]#1.value", ""
        ),
        "product_description": attrs.get(
            "product_description[marketplace_id=ATVPDKIKX0DER][language_tag=en_US]#1.value",
            "",
        ),
    }


def source_attr_lookup(workbook: XlsmTemplate) -> dict[str, str]:
    return workbook.attr_to_col()


def write_report(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fix_from_report(source_path: Path, report_path: Path, output_path: Path) -> dict[str, Any]:
    report = parse_processing_report(report_path)
    source = XlsmTemplate(source_path)
    changes: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []

    try:
        cols = source_columns(source)
        attr_cols = source_attr_lookup(source)
        data_start = source.data_start_row()
        keep_rows: list[ET.Element] = []
        source_skus: set[str] = set()
        removed_success = 0
        not_processed = 0

        rows_sorted = sorted(source.rows.items())
        for row_number, row in rows_sorted:
            cells = source.cells_for_row(row)
            sku = source.cell_text(cells.get(cols["sku"])).strip()
            if not sku or sku == "ABC123":
                continue
            if row_number < data_start:
                # Broken prior output: the first data row was shifted into the
                # example row. Only rescue that specific row; preserve earlier
                # header rows as template structure.
                if row_number != data_start - 1 or sku == "ABC123":
                    continue
                if sku in {"SKU", "contribution_sku#1.value"}:
                    continue
                if sku in report.report_skus:
                    continue
                pass

            source_skus.add(sku)
            if sku in report.pure_success_skus:
                removed_success += 1
                continue
            if sku not in report.report_skus:
                not_processed += 1
            keep_rows.append(copy.deepcopy(row))

        # Apply corrections on copied rows.
        for row in keep_rows:
            cells = source.cells_for_row(row)
            sku = source.cell_text(cells.get(cols["sku"])).strip()
            sku_errors = report.errors_by_sku.get(sku, [])

            def update_text(letter: str, new_value: str, reason: str) -> None:
                if not letter:
                    return
                old_value = source.cell_text(cells.get(letter))
                if new_value != old_value:
                    source.set_cell_text(row, cells, letter, new_value)
                    changes.append(
                        {
                            "sku": sku,
                            "row": row.get("r", ""),
                            "column": letter,
                            "field": source.headers().get(letter, ""),
                            "reason": reason,
                            "old_length": len(old_value),
                            "new_length": len(new_value),
                            "old_value": old_value,
                            "new_value": new_value,
                        }
                    )

            for field_name in ("title", "item_name"):
                letter = cols.get(field_name, "")
                old = source.cell_text(cells.get(letter))
                if old:
                    fixed, actions = compact_marketing_text(old, 200)
                    update_text(letter, fixed, "; ".join(actions) or "title validated")

            highlight_col = cols["item_highlight"]
            highlight = source.cell_text(cells.get(highlight_col))
            if highlight:
                fixed, actions = compact_marketing_text(highlight, 125)
                phrase_fixed, phrase_actions = sanitize_text_field(
                    fixed,
                    125,
                    "Item Highlight",
                    remove_prohibited_phrases=True,
                )
                fixed = normalize_space(phrase_fixed.strip(" ,;-"))
                actions.extend(action for action in phrase_actions if action not in actions)
                update_text(highlight_col, fixed, "; ".join(actions) or "highlight validated")

            description_col = cols.get("product_description", "")
            description = source.cell_text(cells.get(description_col)) if description_col else ""
            if description and HTML_TAG_RE.search(description):
                update_text(description_col, strip_html(description), "removed HTML from Product Description")

            if any(
                "Product Description' is required but missing" in error["message"]
                for error in sku_errors
            ) and description_col and not description:
                title = source.cell_text(cells.get(cols["item_name"])) or source.cell_text(cells.get(cols["title"]))
                highlight = source.cell_text(cells.get(highlight_col))
                generated = normalize_space(f"{title}. {highlight}.")
                update_text(description_col, generated, "created Product Description from title and highlight")

            if any(
                "brand name" in error["message"].lower()
                or "approval to list in this brand" in error["message"].lower()
                or "brand value was not consistent" in error["message"].lower()
                for error in sku_errors
            ):
                brand_col = cols.get("brand", "")
                if brand_col and source.clear_cell(cells, brand_col):
                    changes.append(
                        {
                            "sku": sku,
                            "row": row.get("r", ""),
                            "column": brand_col,
                            "field": source.headers().get(brand_col, ""),
                            "reason": "cleared Brand Name to avoid changing the brand on an existing ASIN",
                            "old_length": "",
                            "new_length": 0,
                            "old_value": "(cleared)",
                            "new_value": "",
                        }
                    )

            if any("Maximum Sample Rate" in error["message"] for error in sku_errors):
                for attr in (
                    "maximum_sample_rate[marketplace_id=ATVPDKIKX0DER]#1.value",
                    "maximum_sample_rate[marketplace_id=ATVPDKIKX0DER]#1.unit",
                ):
                    letter = attr_cols.get(attr, "")
                    if letter and source.clear_cell(cells, letter):
                        changes.append(
                            {
                                "sku": sku,
                                "row": row.get("r", ""),
                                "column": letter,
                                "field": source.headers().get(letter, ""),
                                "reason": "cleared Amazon-rejected Maximum Sample Rate",
                                "old_length": "",
                                "new_length": 0,
                                "old_value": "(cleared)",
                                "new_value": "",
                            }
                        )

            if any("California Proposition 65" in error["message"] for error in sku_errors):
                prop65_attrs = [
                    "california_proposition_65[marketplace_id=ATVPDKIKX0DER]#1.chemical_names#2",
                    "california_proposition_65[marketplace_id=ATVPDKIKX0DER]#1.chemical_names#3",
                    "california_proposition_65[marketplace_id=ATVPDKIKX0DER]#1.chemical_names#4",
                    "california_proposition_65[marketplace_id=ATVPDKIKX0DER]#1.chemical_names#5",
                ]
                for attr in prop65_attrs:
                    letter = attr_cols.get(attr, "")
                    if letter and source.clear_cell(cells, letter):
                        changes.append(
                            {
                                "sku": sku,
                                "row": row.get("r", ""),
                                "column": letter,
                                "field": source.headers().get(letter, ""),
                                "reason": "cleared extra California Prop 65 occurrences",
                                "old_length": "",
                                "new_length": 0,
                                "old_value": "(cleared)",
                                "new_value": "",
                            }
                        )

            for error in sku_errors:
                message = error["message"]
                attr = error["attr"]
                letter = attr_cols.get(attr, "")
                max_match = MAX_LENGTH_RE.search(message)
                if letter and max_match:
                    max_length = int(max_match.group(1))
                    old = source.cell_text(cells.get(letter))
                    if old:
                        fixed, actions = compact_marketing_text(old, max_length)
                        update_text(letter, fixed, "; ".join(actions) or f"trimmed to {max_length} characters")
                phrase_match = PROHIBITED_RE.search(message)
                if letter and phrase_match:
                    old = source.cell_text(cells.get(letter))
                    fixed = old
                    for phrase in [part.strip() for part in phrase_match.group(1).split(",")]:
                        fixed = re.sub(re.escape(phrase), "", fixed, flags=re.I)
                    fixed = normalize_space(fixed.strip(" ,;-"))
                    update_text(letter, fixed, "removed prohibited Amazon phrase")

                lower = message.lower()
                if not letter and any(
                    marker in lower
                    for marker in (
                        "listing data provided is different",
                        "product type",
                        "image has been identified",
                        "variation",
                    )
                ):
                    manual.append(
                        {
                            "sku": sku,
                            "report_row": error["report_row"],
                            "report_col": error["report_col"],
                            "field": error["header"],
                            "message": message,
                            "suggested_action": "requires external data or a manual decision in Seller Central",
                        }
                    )

        source.replace_data_rows(keep_rows, data_start, cols["sku"])
        source.save(output_path)

        output_base = output_path.with_suffix("")
        changes_path = output_base.parent / f"{output_base.name}-corrections.csv"
        manual_path = output_base.parent / f"{output_base.name}-manual-review.csv"
        summary_path = output_base.parent / f"{output_base.name}-summary.csv"

        write_report(
            changes_path,
            changes,
            [
                "sku",
                "row",
                "column",
                "field",
                "reason",
                "old_length",
                "new_length",
                "old_value",
                "new_value",
            ],
        )
        write_report(
            manual_path,
            manual,
            ["sku", "report_row", "report_col", "field", "message", "suggested_action"],
        )
        summary_rows = [
            {"metric": "source_skus", "value": len(source_skus)},
            {"metric": "report_skus", "value": len(report.report_skus)},
            {"metric": "removed_clean_success_skus", "value": removed_success},
            {"metric": "kept_retry_skus", "value": len(keep_rows)},
            {"metric": "not_processed_in_report_kept", "value": not_processed},
            {"metric": "corrections_applied", "value": len(changes)},
            {"metric": "manual_review_items", "value": len(manual)},
        ]
        write_report(summary_path, summary_rows, ["metric", "value"])

        return {
            "output": output_path,
            "changes": changes_path,
            "manual": manual_path,
            "summary": summary_path,
            "source_skus": len(source_skus),
            "removed_clean_success_skus": removed_success,
            "kept_retry_skus": len(keep_rows),
            "not_processed_in_report_kept": not_processed,
            "corrections_applied": len(changes),
            "manual_review_items": len(manual),
            **report.summary,
        }
    finally:
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Amazon flat-file errors from a processing summary.")
    parser.add_argument("source", type=Path, help="Original uploaded .xlsm flat file")
    parser.add_argument("report", type=Path, help="Amazon processing-summary .xlsm")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Corrected retry .xlsm path")
    args = parser.parse_args()

    result = fix_from_report(args.source, args.report, args.output)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
