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
import sys
import re
import unicodedata
import hashlib

try:
    from .maint_structure_lib import (
        get_genres_map,
        get_series_entries_map,
        load_structure,
        save_structure,
    )
except ImportError:
    from maint_structure_lib import (
        get_genres_map,
        get_series_entries_map,
        load_structure,
        save_structure,
    )

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


# ── export ────────────────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
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

    print(f"Exported {len(rows)} entries to: {output_path}")


# ── apply ─────────────────────────────────────────────────────────────────────

def cmd_apply(args: argparse.Namespace) -> None:
    input_path = args.input
    dry_run: bool = args.dry_run

    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Load CSV
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

    # Load structure
    structure = load_structure()
    genres_map = get_genres_map(structure)

    changed = 0
    not_found = 0

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

        if entry_changed:
            changed += 1

    if dry_run:
        print(f"\nDry-run complete: {changed} entries would be updated, {not_found} not found.")
    else:
        if changed:
            save_structure(structure)
            print(f"Applied: {changed} entries updated, {not_found} not found. Saved to structure.json.")
        else:
            print(f"No changes detected. ({not_found} not found)")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _default_csv_path() -> str:
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tools_dir, "metadata.csv")


def main() -> None:
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

    args = parser.parse_args()
    if args.command == "export":
        cmd_export(args)
    elif args.command == "apply":
        cmd_apply(args)


if __name__ == "__main__":
    main()
