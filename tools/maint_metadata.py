"""Manage entry metadata (main-person, labels, persons, series, note) via CSV.

Usage:
  # Export current metadata from structure.json to CSV
  python maint_metadata.py export [--output metadata.csv]

  # Apply CSV metadata back to structure.json (dry-run to preview changes)
  python maint_metadata.py apply [--input metadata.csv] [--dry-run]

CSV columns (export omits `series`; on apply `series` will be set from `name` if missing):
    genre       : genre key (comic / photo / gamecg ...)
    entry_key   : entry key in structure.json
    name        : display name (read-only, not written back)
    main-person : main author/person string
    persons     : semicolon-separated list  (e.g. "人物A;人物B")
    labels      : semicolon-separated list  (e.g. "成人向け;完結")
    note        : free-form note string
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import re
import unicodedata
import hashlib
import time

try:
    from .maint_structure_lib import (
        get_genres_map,
        get_series_entries_map,
        load_structure,
        save_structure,
        write_structure_js,
    )
    from .maint_metrics import RunMetrics
except ImportError:
    from maint_structure_lib import (
        get_genres_map,
        get_series_entries_map,
        load_structure,
        save_structure,
        write_structure_js,
    )
    from maint_metrics import RunMetrics

# ── CSV layout ────────────────────────────────────────────────────────────────
CSV_COLUMNS = ["genre", "entry_key", "name", "main-person", "persons", "labels", "note"]
# Allow `name` to be updated from CSV (export includes name; apply now writes it back)
EDITABLE_FIELDS = ["name", "main-person", "series", "persons", "labels", "note"]
LIST_FIELDS = {"persons", "labels"}
LIST_SEP = ";"


# ── helpers ───────────────────────────────────────────────────────────────────

def _list_to_csv(values: list) -> str:
    """Encode a JSON list to a semicolon-delimited cell value."""
    return LIST_SEP.join(str(v) for v in values if v)


def _csv_to_list(cell: str) -> list[str]:
    """Decode a semicolon-delimited cell value to a list of strings."""
    return [v.strip() for v in cell.split(LIST_SEP) if v.strip()]


def _slugify_to_ascii(text: str) -> str:
    """Create an ASCII slug from `text`.

    - Normalize (NFKD) and remove combining marks
    - Keep ASCII alnum characters, replace other runs with '-'
    - Lowercase
    - If result is empty (e.g. non-latin scripts), return a stable hex-based fallback
    """
    if not text:
        return ""
    orig = text
    # Normalize and remove diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("M"))
    text = text.lower()
    # Replace non-ascii alnum with hyphen
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    if text:
        return text
    # Fallback: stable short hex of original utf-8 bytes
    h = hashlib.sha1(orig.encode('utf-8')).hexdigest()[:8]
    return f"x{h}"


def _regenerate_gallery_pages_js() -> tuple[bool, str]:
    """Regenerate site/js/gallery-pages.js by invoking maint_build_gallery_pages.py."""
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(tools_dir, ".."))
    script_path = os.path.join(tools_dir, "maint_build_gallery_pages.py")

    if not os.path.isfile(script_path):
        return False, f"Script not found: {script_path}"

    python_exe = sys.executable or "python"
    try:
        proc = subprocess.run(
            [python_exe, script_path],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    if proc.returncode == 0:
        return True, ""

    detail = (proc.stderr or proc.stdout or "").strip()
    if detail:
        detail = detail.splitlines()[-1]
    else:
        detail = f"exit code={proc.returncode}"
    return False, detail


# ── export ────────────────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    metrics = RunMetrics(
        pipeline="uc2-metadata-export",
        mode="apply",
        log_path=args.metrics_log or None,
    )
    started = time.perf_counter()
    structure = load_structure()
    output_path = args.output

    rows: list[dict] = []
    for genre_key, genre_data in get_genres_map(structure).items():
        if not isinstance(genre_data, dict):
            continue
        for entry_key, entry_data in get_series_entries_map(genre_data).items():
            if not isinstance(entry_data, dict):
                continue
            # Export: do not include `series` column by policy; editors will edit `name` only.
            row: dict[str, str] = {
                "genre": genre_key,
                "entry_key": entry_key,
                "name": entry_data.get("name", ""),
                "main-person": entry_data.get("main-person", ""),
                "persons": _list_to_csv(entry_data.get("persons") or []),
                "labels": _list_to_csv(entry_data.get("labels") or []),
                "note": entry_data.get("note", ""),
            }
            rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    metrics.add_stage(
        name="metadata_export",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=len(rows),
        generated_count=len(rows),
        transfer_files=1,
        transfer_bytes=os.path.getsize(output_path) if os.path.isfile(output_path) else 0,
        details={"output": output_path},
    )
    metrics.finalize(success=True)

    print(f"Exported {len(rows)} entries to: {output_path}")
    print(f"Metrics log: {metrics.log_path}")


# ── apply ─────────────────────────────────────────────────────────────────────

def cmd_apply(args: argparse.Namespace) -> None:
    input_path = args.input
    dry_run: bool = args.dry_run
    metrics = RunMetrics(
        pipeline="uc2-metadata-apply",
        mode="plan" if dry_run else "apply",
        log_path=args.metrics_log or None,
    )

    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Load CSV
    load_started = time.perf_counter()
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    with open(input_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            genre = row.get("genre", "").strip()
            entry_key = row.get("entry_key", "").strip()
            if not genre or not entry_key:
                print(f"  WARNING: row {i} skipped (missing genre or entry_key)")
                continue
            # If `series` column absent or empty, create slug from `name` per policy
            series_val = (row.get("series") or "").strip()
            if not series_val:
                series_val = _slugify_to_ascii((row.get("name") or "").strip())
            row["series"] = series_val
            rows_by_key[(genre, entry_key)] = row
    metrics.add_stage(
        name="load_csv",
        status="ok",
        duration_ms=int((time.perf_counter() - load_started) * 1000),
        scanned_count=len(rows_by_key),
        generated_count=0,
        transfer_files=0,
        transfer_bytes=0,
        details={"input": input_path},
    )

    # Load structure
    apply_started = time.perf_counter()
    structure = load_structure()
    genres_map = get_genres_map(structure)

    changed = 0
    not_found = 0
    path_changed = False

    for (genre_key, entry_key), row in rows_by_key.items():
        genre_data = genres_map.get(genre_key)
        if genre_data is None:
            print(f"  WARNING: genre '{genre_key}' not found (entry '{entry_key}' skipped)")
            not_found += 1
            continue

        entries_map = get_series_entries_map(genre_data)
        entry_data = entries_map.get(entry_key)
        if entry_data is None:
            print(f"  WARNING: entry '{entry_key}' not found in genre '{genre_key}'")
            not_found += 1
            continue

        entry_changed = False
        for field in EDITABLE_FIELDS:
            csv_val = row.get(field, "").strip()
            if field in LIST_FIELDS:
                new_val = _csv_to_list(csv_val)
                old_val = entry_data.get(field) or []
                if old_val != new_val:
                    if dry_run:
                        print(f"  [DRY] {genre_key}/{entry_key}: {field}: {old_val!r} -> {new_val!r}")
                    else:
                        entry_data[field] = new_val
                    entry_changed = True
            else:
                old_val = entry_data.get(field, "")
                if old_val != csv_val:
                    if dry_run:
                        print(f"  [DRY] {genre_key}/{entry_key}: {field}: {old_val!r} -> {csv_val!r}")
                    else:
                        entry_data[field] = csv_val
                    entry_changed = True
                    if field == "path":
                        path_changed = True

        if entry_changed:
            changed += 1

    metrics.add_stage(
        name="apply_metadata_to_structure",
        status="ok",
        duration_ms=int((time.perf_counter() - apply_started) * 1000),
        scanned_count=len(rows_by_key),
        generated_count=changed,
        transfer_files=0,
        transfer_bytes=0,
        details={"changed": changed, "not_found": not_found},
    )

    if dry_run:
        print(f"\nDry-run complete: {changed} entries would be updated, {not_found} not found.")
        payload = metrics.finalize(success=True)
        print(f"Metrics log: {metrics.log_path}")
        if payload.get("compare"):
            compare = payload["compare"]
            print(
                "Compare(previous): "
                f"duration_ms={compare['delta_duration_ms']}, "
                f"generated={compare['delta_generated_count']}, "
                f"transfer_files={compare['delta_transfer_files']}, "
                f"transfer_bytes={compare['delta_transfer_bytes']}"
            )
    else:
        save_started = time.perf_counter()
        transfer_files = 0
        transfer_bytes = 0
        if changed:
            save_structure(structure)
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            structure_path = os.path.join(root_dir, "site", "structure.json")
            structure_js_path = os.path.join(root_dir, "site", "js", "structure.js")
            gallery_pages_path = os.path.join(root_dir, "site", "js", "gallery-pages.js")

            if os.path.isfile(structure_path):
                transfer_files += 1
                transfer_bytes += os.path.getsize(structure_path)
            try:
                write_structure_js(structure)
                if os.path.isfile(structure_js_path):
                    transfer_files += 1
                    transfer_bytes += os.path.getsize(structure_js_path)
                if path_changed:
                    ok, detail = _regenerate_gallery_pages_js()
                    if os.path.isfile(gallery_pages_path):
                        transfer_files += 1
                        transfer_bytes += os.path.getsize(gallery_pages_path)
                    if ok:
                        print(
                            f"Applied: {changed} entries updated, {not_found} not found. "
                            "Saved to structure.json and regenerated site/js/structure.js + site/js/gallery-pages.js."
                        )
                    else:
                        print(
                            f"Applied: {changed} entries updated, {not_found} not found. "
                            f"Saved to structure.json and regenerated site/js/structure.js. (gallery-pages.js regen failed: {detail})"
                        )
                else:
                    print(
                        f"Applied: {changed} entries updated, {not_found} not found. "
                        "Saved to structure.json and regenerated site/js/structure.js. "
                        "(gallery-pages.js skipped: no path changes)"
                    )
            except Exception as exc:
                print(f"Applied: {changed} entries updated, {not_found} not found. Saved to structure.json. (structure.js regen failed: {exc})")
        else:
            print(f"No changes detected. ({not_found} not found)")

        metrics.add_stage(
            name="persist_and_regenerate",
            status="ok",
            duration_ms=int((time.perf_counter() - save_started) * 1000),
            scanned_count=changed,
            generated_count=changed,
            transfer_files=transfer_files,
            transfer_bytes=transfer_bytes,
            details={"changed": changed, "path_changed": path_changed, "gallery_pages_skipped": not path_changed},
        )
        payload = metrics.finalize(success=True)
        print(f"Metrics log: {metrics.log_path}")
        if payload.get("compare"):
            compare = payload["compare"]
            print(
                "Compare(previous): "
                f"duration_ms={compare['delta_duration_ms']}, "
                f"generated={compare['delta_generated_count']}, "
                f"transfer_files={compare['delta_transfer_files']}, "
                f"transfer_bytes={compare['delta_transfer_bytes']}"
            )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _default_csv_path() -> str:
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tools_dir, "metadata.csv")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Export/apply entry metadata (labels, persons, etc.) via CSV."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # export
    p_export = sub.add_parser("export", help="Export metadata from structure.json to CSV")
    p_export.add_argument(
        "--output", "-o",
        default=_default_csv_path(),
        metavar="FILE",
        help="Output CSV path (default: tools/metadata.csv)",
    )
    p_export.add_argument(
        "--metrics-log",
        default="",
        metavar="FILE",
        help="Optional JSONL output path for metrics log",
    )

    # apply
    p_apply = sub.add_parser("apply", help="Apply metadata from CSV to structure.json")
    p_apply.add_argument(
        "--input", "-i",
        default=_default_csv_path(),
        metavar="FILE",
        help="Input CSV path (default: tools/metadata.csv)",
    )
    p_apply.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview changes without writing to structure.json",
    )
    p_apply.add_argument(
        "--metrics-log",
        default="",
        metavar="FILE",
        help="Optional JSONL output path for metrics log",
    )

    # plan (alias to apply --dry-run)
    p_plan = sub.add_parser("plan", help="Preview apply result without writing")
    p_plan.add_argument(
        "--input", "-i",
        default=_default_csv_path(),
        metavar="FILE",
        help="Input CSV path (default: tools/metadata.csv)",
    )
    p_plan.add_argument(
        "--metrics-log",
        default="",
        metavar="FILE",
        help="Optional JSONL output path for metrics log",
    )

    args = parser.parse_args(argv)
    if args.command == "export":
        cmd_export(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "plan":
        args.dry_run = True
        cmd_apply(args)


if __name__ == "__main__":
    main()
