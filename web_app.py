from __future__ import annotations

import csv
import os
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from amazon_batch_core import (
    ITEM_HIGHLIGHT_MAX_LENGTH,
    find_default_reference,
    load_reference,
    process_xlsm,
    update_xlsm_cells,
)
from amazon_report_error_fixer import fix_from_report
from app_paths import APP_VERSION, RESOURCE_DIR, WEB_OUTPUT_DIR, ensure_app_directories
from ai_optimizer import ai_status, configure_ai, optimize_field
from desktop_bridge import consume_selected_folder, register_selected_folder


BASE_DIR = RESOURCE_DIR
MAX_UPLOAD_MB = 600

ensure_app_directories()
app = Flask(
    __name__,
    static_folder=str(RESOURCE_DIR / "static"),
    template_folder=str(RESOURCE_DIR / "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _json_error(message: str, status: int = 400):
    response = jsonify({"error": message})
    response.status_code = status
    return response


def _has_suffix(filename: str, suffixes: tuple[str, ...]) -> bool:
    return Path(filename).suffix.lower() in suffixes


def _safe_upload_name(filename: str, fallback: str) -> str:
    return secure_filename(filename) or fallback


def _safe_relative_upload_path(filename: str, fallback: str) -> Path:
    raw_name = (filename or fallback).replace("\\", "/")
    parts = [
        part
        for part in PurePosixPath(raw_name).parts
        if part not in {"", ".", "..", "/"}
    ]
    safe_parts = [secure_filename(part) for part in parts]
    safe_parts = [part for part in safe_parts if part]
    if not safe_parts:
        return Path(fallback)
    return Path(*safe_parts)


@app.get("/")
def index():
    default_reference = find_default_reference(BASE_DIR)
    return render_template(
        "index.html",
        default_reference=default_reference.name if default_reference else None,
        max_upload_mb=MAX_UPLOAD_MB,
        item_highlight_max_length=ITEM_HIGHLIGHT_MAX_LENGTH,
        app_version=APP_VERSION,
    )


@app.get("/app-icon.png")
def app_icon():
    return send_file(BASE_DIR / "packaging" / "assets" / "app-icon.png", mimetype="image/png")


@app.post("/api/process")
def process_files():
    template_files = [
        file for file in request.files.getlist("templates") if file and file.filename
    ]
    folder_token = request.form.get("folder_token", "")
    selected_folder = consume_selected_folder(folder_token) if folder_token else None
    if not template_files and selected_folder is None:
        return _json_error("Upload Amazon .xlsm files, a folder, or a .zip archive.")

    reference_upload = request.files.get("reference")
    review_mode = request.form.get("review_mode", "manual")
    if review_mode not in {"manual", "review", "automatic"}:
        return _json_error("Choose a valid review mode.")
    auto_fix_bullets = review_mode in {"review", "automatic"}
    job_id = uuid.uuid4().hex[:12]
    job_dir = WEB_OUTPUT_DIR / "jobs" / job_id
    upload_dir = job_dir / "uploads"
    output_dir = job_dir / "processed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if reference_upload and reference_upload.filename:
        if not _has_suffix(reference_upload.filename, (".xlsx", ".xlsm")):
            return _json_error("The reference must be an .xlsx or .xlsm workbook.")
        reference_name = _safe_upload_name(reference_upload.filename, "reference.xlsx")
        reference_path = upload_dir / reference_name
        reference_upload.save(reference_path)
    else:
        default_reference = find_default_reference(BASE_DIR)
        if default_reference is None:
            return _json_error(
                "No local reference workbook was found. Upload the SKU reference .xlsx file."
            )
        reference_path = default_reference

    try:
        reference = load_reference(reference_path)
    except Exception as exc:  # noqa: BLE001 - show a concise import-friendly error
        return _json_error(f"I could not read the reference workbook: {exc}", 422)

    processed = []
    errors = []
    all_warnings = []
    all_corrections = []
    all_sku_contexts: dict[str, dict[str, str]] = {}

    template_sources: list[tuple[str, Path]] = []
    total_extracted_bytes = 0
    seen_paths: set[str] = set()
    if selected_folder is not None:
        for folder_file in sorted(selected_folder.rglob("*.xlsm")):
            if folder_file.name.startswith("~$"):
                continue
            relative = Path(selected_folder.name) / folder_file.relative_to(selected_folder)
            display_name = _safe_relative_upload_path(relative.as_posix(), "template.xlsm").as_posix()
            if display_name not in seen_paths:
                seen_paths.add(display_name)
                template_sources.append((display_name, folder_file))
        if not template_sources:
            errors.append({"filename": selected_folder.name, "error": "The selected folder contains no .xlsm files."})
    for storage_file in template_files:
        original_name = storage_file.filename or "template.xlsm"
        if _has_suffix(original_name, (".zip",)):
            archive_name = _safe_upload_name(original_name, "templates.zip")
            archive_path = upload_dir / archive_name
            storage_file.save(archive_path)
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    workbook_entries = [
                        entry for entry in archive.infolist()
                        if not entry.is_dir()
                        and _has_suffix(entry.filename, (".xlsm",))
                        and not PurePosixPath(entry.filename).name.startswith("~$")
                    ]
                    if not workbook_entries:
                        errors.append({"filename": original_name, "error": "The ZIP contains no .xlsm files."})
                        continue
                    for entry in workbook_entries:
                        total_extracted_bytes += int(entry.file_size)
                        if total_extracted_bytes > MAX_UPLOAD_MB * 1024 * 1024:
                            raise ValueError("The uncompressed ZIP contents exceed the upload limit.")
                        safe_path = _safe_relative_upload_path(entry.filename, "template.xlsm")
                        display_name = safe_path.as_posix()
                        if display_name in seen_paths:
                            raise ValueError(f"Duplicate workbook path: {display_name}")
                        seen_paths.add(display_name)
                        source_path = upload_dir / safe_path
                        source_path.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as source, source_path.open("wb") as target:
                            target.write(source.read())
                        template_sources.append((display_name, source_path))
            except (zipfile.BadZipFile, ValueError, OSError) as exc:
                errors.append({"filename": original_name, "error": f"ZIP could not be opened: {exc}"})
            continue

        safe_path = _safe_relative_upload_path(original_name, "template.xlsm")
        display_name = safe_path.as_posix()
        if safe_path.name.startswith("~$"):
            errors.append({"filename": display_name, "error": "Excel temporary owner file was skipped."})
            continue
        if not _has_suffix(safe_path.name, (".xlsm",)):
            errors.append({"filename": original_name, "error": "Only .xlsm files and .zip archives are supported."})
            continue
        if display_name in seen_paths:
            errors.append({"filename": display_name, "error": "A workbook with this path was already added."})
            continue
        seen_paths.add(display_name)
        source_path = upload_dir / safe_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        storage_file.save(source_path)
        template_sources.append((display_name, source_path))

    for display_name, source_path in template_sources:
        safe_path = Path(display_name)
        output_path = output_dir / safe_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            stats = process_xlsm(
                source_path,
                output_path,
                reference,
                auto_fix_bullets=auto_fix_bullets,
                item_highlight_max_length=ITEM_HIGHLIGHT_MAX_LENGTH,
            )
        except Exception as exc:  # noqa: BLE001 - keep batch processing resilient
            errors.append({"filename": display_name, "error": str(exc)})
            continue

        if "error" in stats:
            errors.append({"filename": display_name, "error": str(stats["error"])})
            continue

        file_warnings = [
            {"filename": display_name, **warning}
            for warning in stats.get("warnings", [])
        ]
        file_corrections = [
            {"filename": display_name, **correction}
            for correction in stats.get("corrections", [])
        ]
        all_warnings.extend(file_warnings)
        all_corrections.extend(file_corrections)
        for sku_context in stats.get("sku_contexts", []):
            context_key = f"{display_name}\u0000{sku_context['sku']}\u0000{sku_context['row']}"
            all_sku_contexts[context_key] = sku_context.get("context", {})

        processed.append(
            {
                "filename": display_name,
                "updated": stats["updated"],
                "removed": stats["removed"],
                "new_strings": stats["new_strings"],
                "final_rows": stats["final_rows"],
                "warnings": len(file_warnings),
                "corrections": len(file_corrections),
                "html_cleaned": stats.get("html_cleaned", 0),
                "field_truncated": stats.get("field_truncated", 0),
                "prohibited_phrases_removed": stats.get("prohibited_phrases_removed", 0),
                "text_fields_cleaned": stats.get("text_fields_cleaned", 0),
                "title_exceeded_75": stats.get("title_exceeded_75", 0),
                "highlight_exceeded_125": stats.get("highlight_exceeded_125", 0),
                "highlight_missing": stats.get("highlight_missing", 0),
                "title_has_special": stats.get("title_has_special", 0),
                "highlight_has_special": stats.get("highlight_has_special", 0),
            }
        )

    if not processed:
        return _json_error(
            "No templates could be processed. Review the errors and try again.",
            422,
        )

    zip_path = job_dir / "focus_amazon_processed.zip"
    warning_report_path = job_dir / "amazon_text_alerts.csv"
    correction_report_path = job_dir / "amazon_text_corrections.csv"
    summary_report_path = job_dir / "amazon_batch_summary.csv"
    if all_warnings:
        with warning_report_path.open("w", newline="", encoding="utf-8") as report_file:
            writer = csv.DictWriter(
                report_file,
                fieldnames=[
                    "filename",
                    "sku",
                    "row",
                    "column",
                    "field",
                    "length",
                    "issues",
                    "preview",
                ],
            )
            writer.writeheader()
            for warning in all_warnings:
                writer.writerow(
                    {
                        **warning,
                        "issues": "; ".join(warning["issues"]),
                    }
                )

    if all_corrections:
        with correction_report_path.open("w", newline="", encoding="utf-8") as report_file:
            writer = csv.DictWriter(
                report_file,
                fieldnames=[
                    "filename",
                    "sku",
                    "row",
                    "column",
                    "field",
                    "original_length",
                    "fixed_length",
                    "issues_before",
                    "actions",
                    "original",
                    "fixed",
                ],
            )
            writer.writeheader()
            for correction in all_corrections:
                writer.writerow(
                    {
                        **correction,
                        "issues_before": "; ".join(correction["issues_before"]),
                        "actions": "; ".join(correction["actions"]),
                    }
                )

    summary_fields = [
        "filename",
        "updated",
        "removed",
        "new_strings",
        "final_rows",
        "warnings",
        "corrections",
        "html_cleaned",
        "field_truncated",
        "prohibited_phrases_removed",
        "text_fields_cleaned",
        "title_exceeded_75",
        "highlight_exceeded_125",
        "highlight_missing",
        "title_has_special",
        "highlight_has_special",
    ]
    with summary_report_path.open("w", newline="", encoding="utf-8") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(processed)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for output_file in sorted(output_dir.rglob("*.xlsm")):
            zip_file.write(
                output_file,
                arcname=output_file.relative_to(output_dir).as_posix(),
            )
        zip_file.write(summary_report_path, arcname=summary_report_path.name)
        if all_warnings:
            zip_file.write(warning_report_path, arcname=warning_report_path.name)
        if all_corrections:
            zip_file.write(correction_report_path, arcname=correction_report_path.name)

    totals = {
        "updated": sum(int(item["updated"]) for item in processed),
        "removed": sum(int(item["removed"]) for item in processed),
        "warnings": len(all_warnings),
        "corrections": len(all_corrections),
        "html_cleaned": sum(int(item["html_cleaned"]) for item in processed),
        "field_truncated": sum(int(item["field_truncated"]) for item in processed),
        "prohibited_phrases_removed": sum(
            int(item["prohibited_phrases_removed"]) for item in processed
        ),
        "text_fields_cleaned": sum(int(item["text_fields_cleaned"]) for item in processed),
        "title_exceeded_75": sum(int(item["title_exceeded_75"]) for item in processed),
        "highlight_exceeded_125": sum(
            int(item["highlight_exceeded_125"]) for item in processed
        ),
        "highlight_missing": sum(int(item["highlight_missing"]) for item in processed),
        "title_has_special": sum(int(item["title_has_special"]) for item in processed),
        "highlight_has_special": sum(
            int(item["highlight_has_special"]) for item in processed
        ),
    }

    return jsonify(
        {
            "job_id": job_id,
            "reference_count": len(reference),
            "auto_fix_bullets": auto_fix_bullets,
            "review_mode": review_mode,
            "item_highlight_max_length": ITEM_HIGHLIGHT_MAX_LENGTH,
            "processed": processed,
            "errors": errors,
            "warnings": all_warnings,
            "corrections": all_corrections,
            "sku_contexts": all_sku_contexts,
            "totals": totals,
            "download_url": url_for("download_job", job_id=job_id),
        }
    )


@app.post("/api/review/<job_id>")
def apply_review(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        abort(404)
    job_dir = WEB_OUTPUT_DIR / "jobs" / job_id
    output_dir = job_dir / "processed"
    if not output_dir.is_dir():
        abort(404)

    payload = request.get_json(silent=True) or {}
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        return _json_error("No review decisions were received.")

    grouped: dict[str, list[dict]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            return _json_error("A review decision is invalid.")
        filename = str(decision.get("filename", ""))
        relative = _safe_relative_upload_path(filename, "")
        target = output_dir / relative
        try:
            target.resolve().relative_to(output_dir.resolve())
        except ValueError:
            return _json_error("A reviewed file path is invalid.")
        if not target.is_file() or target.suffix.lower() != ".xlsm":
            return _json_error(f"The reviewed file was not found: {filename}")
        column = str(decision.get("column", "")).upper()
        row = decision.get("row")
        if not re.fullmatch(r"[A-Z]{1,3}", column) or not isinstance(row, int) or row < 1:
            return _json_error("A reviewed cell reference is invalid.")
        grouped.setdefault(filename, []).append(
            {"column": column, "row": row, "value": str(decision.get("value", ""))}
        )

    try:
        for filename, changes in grouped.items():
            update_xlsm_cells(output_dir / _safe_relative_upload_path(filename, ""), changes)
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"I could not apply the reviewed changes: {exc}", 422)

    zip_path = job_dir / "focus_amazon_processed.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for output_file in sorted(output_dir.rglob("*.xlsm")):
            zip_file.write(output_file, arcname=output_file.relative_to(output_dir).as_posix())
        for report_name in ("amazon_batch_summary.csv", "amazon_text_alerts.csv", "amazon_text_corrections.csv"):
            report_path = job_dir / report_name
            if report_path.is_file():
                zip_file.write(report_path, arcname=report_path.name)

    return jsonify({"ok": True, "download_url": url_for("download_job", job_id=job_id)})


@app.post("/api/fix-report")
def fix_report_files():
    source_upload = request.files.get("source")
    report_upload = request.files.get("processing_report")
    if not source_upload or not source_upload.filename:
        return _json_error("Upload the original Amazon .xlsm file.")
    if not report_upload or not report_upload.filename:
        return _json_error("Upload the Amazon processing-summary .xlsm file.")
    if not _has_suffix(source_upload.filename, (".xlsm",)):
        return _json_error("The original Amazon flat file must be an .xlsm workbook.")
    if not _has_suffix(report_upload.filename, (".xlsm",)):
        return _json_error("The Amazon processing summary must be an .xlsm workbook.")

    job_id = uuid.uuid4().hex[:12]
    job_dir = WEB_OUTPUT_DIR / "report_jobs" / job_id
    upload_dir = job_dir / "uploads"
    output_dir = job_dir / "processed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_name = _safe_upload_name(source_upload.filename, "amazon-flat-file.xlsm")
    report_name = _safe_upload_name(report_upload.filename, "amazon-processing-summary.xlsm")
    source_path = upload_dir / source_name
    report_path = upload_dir / report_name
    source_upload.save(source_path)
    report_upload.save(report_path)

    output_path = output_dir / f"{Path(source_name).stem}-retry-corrected.xlsm"
    try:
        result = fix_from_report(source_path, report_path, output_path)
    except Exception as exc:  # noqa: BLE001 - surface workbook/report issues in the UI
        return _json_error(f"I could not build the retry workbook: {exc}", 422)

    zip_path = job_dir / "amazon_report_fix.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for key in ("output", "changes", "manual", "summary"):
            report_file = result.get(key)
            if isinstance(report_file, Path) and report_file.is_file():
                zip_file.write(report_file, arcname=report_file.name)

    return jsonify(
        {
            "job_id": job_id,
            "mode": "report_fix",
            "source_skus": result["source_skus"],
            "report_skus": result["report_skus"],
            "removed_clean_success_skus": result["removed_clean_success_skus"],
            "kept_retry_skus": result["kept_retry_skus"],
            "not_processed_in_report_kept": result["not_processed_in_report_kept"],
            "corrections_applied": result["corrections_applied"],
            "manual_review_items": result["manual_review_items"],
            "download_url": url_for("download_report_job", job_id=job_id),
        }
    )


@app.get("/download/<job_id>")
def download_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        abort(404)
    zip_path = WEB_OUTPUT_DIR / "jobs" / job_id / "focus_amazon_processed.zip"
    if not zip_path.is_file():
        abort(404)
    return send_file(
        zip_path,
        as_attachment=True,
        download_name="focus_amazon_processed.zip",
        mimetype="application/zip",
    )


@app.get("/download-file/<job_id>/<path:filename>")
def download_processed_file(job_id: str, filename: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        abort(404)
    output_dir = WEB_OUTPUT_DIR / "jobs" / job_id / "processed"
    relative = _safe_relative_upload_path(filename, "")
    target = output_dir / relative
    try:
        target.resolve().relative_to(output_dir.resolve())
    except ValueError:
        abort(404)
    if not target.is_file() or target.suffix.lower() != ".xlsm":
        abort(404)
    return send_file(target, as_attachment=True, download_name=target.name)


@app.post("/api/export/<job_id>")
def create_selected_export(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        abort(404)
    job_dir = WEB_OUTPUT_DIR / "jobs" / job_id
    output_dir = job_dir / "processed"
    if not output_dir.is_dir():
        abort(404)
    payload = request.get_json(silent=True) or {}
    filenames = payload.get("filenames")
    if not isinstance(filenames, list) or not filenames:
        return _json_error("Select at least one processed file to export.")
    selected: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for filename in filenames:
        relative = _safe_relative_upload_path(str(filename), "")
        target = output_dir / relative
        try:
            target.resolve().relative_to(output_dir.resolve())
        except ValueError:
            return _json_error("An export path is invalid.")
        if not target.is_file() or target.suffix.lower() != ".xlsm":
            return _json_error(f"The processed file was not found: {filename}", 404)
        key = relative.as_posix()
        if key not in seen:
            seen.add(key)
            selected.append((relative, target))
    export_token = uuid.uuid4().hex[:12]
    export_path = job_dir / f"selected-{export_token}.zip"
    with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, target in selected:
            archive.write(target, arcname=relative.as_posix())
        if bool(payload.get("include_reports")):
            for report_name in ("amazon_batch_summary.csv", "amazon_text_alerts.csv", "amazon_text_corrections.csv"):
                report_path = job_dir / report_name
                if report_path.is_file():
                    archive.write(report_path, arcname=report_name)
    return jsonify({"download_url": url_for("download_selected_export", job_id=job_id, export_token=export_token)})


@app.get("/download-selection/<job_id>/<export_token>")
def download_selected_export(job_id: str, export_token: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id) or not re.fullmatch(r"[a-f0-9]{12}", export_token):
        abort(404)
    export_path = WEB_OUTPUT_DIR / "jobs" / job_id / f"selected-{export_token}.zip"
    if not export_path.is_file():
        abort(404)
    return send_file(export_path, as_attachment=True, download_name="focus_amazon_selected.zip")


@app.get("/download-report/<job_id>")
def download_report_job(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        abort(404)
    zip_path = WEB_OUTPUT_DIR / "report_jobs" / job_id / "amazon_report_fix.zip"
    if not zip_path.is_file():
        abort(404)
    return send_file(
        zip_path,
        as_attachment=True,
        download_name="amazon_report_fix.zip",
        mimetype="application/zip",
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/desktop/register-folder")
def register_desktop_folder():
    expected_token = os.environ.get("FOCUS_DESKTOP_TOKEN", "")
    supplied_token = request.headers.get("X-Focus-Desktop-Token", "")
    if not expected_token or supplied_token != expected_token:
        abort(403)
    payload = request.get_json(silent=True) or {}
    selected = register_selected_folder(str(payload.get("path", "")))
    if selected is None:
        return _json_error("The selected folder is unavailable.", 404)
    return jsonify(selected)


@app.get("/api/ai/status")
def get_ai_status():
    return jsonify(ai_status())


@app.post("/api/ai/config")
def set_ai_config():
    payload = request.get_json(silent=True) or {}
    try:
        configure_ai(str(payload.get("api_key", "")), str(payload.get("model", "gpt-5.6-terra")))
    except ValueError as exc:
        return _json_error(str(exc))
    return jsonify(ai_status())


@app.post("/api/ai/optimize")
def ai_optimize():
    payload = request.get_json(silent=True) or {}
    context = payload.get("context") or {}
    if not isinstance(context, dict):
        return _json_error("The SKU context is invalid.")
    safe_context: dict[str, str] = {}
    context_characters = 0
    for key, value in context.items():
        safe_key = str(key)[:160]
        safe_value = str(value)[:8000].strip()
        if not safe_value:
            continue
        remaining = 40000 - context_characters
        if remaining <= 0:
            break
        safe_value = safe_value[:remaining]
        safe_context[safe_key] = safe_value
        context_characters += len(safe_key) + len(safe_value)
    try:
        result = optimize_field(str(payload.get("field", "")), str(payload.get("current", "")), safe_context)
    except ValueError as exc:
        return _json_error(str(exc), 422)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("OpenAI optimization failed: %s", type(exc).__name__)
        return _json_error("OpenAI could not optimize this field. Check the API key, connection, and account limits.", 502)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
