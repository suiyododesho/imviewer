"""Regenerate series contents in site/structure.json."""

from __future__ import annotations

import argparse
import json
import os

try:
    from .maint_structure_lib import CONTENTS_DIR, get_genres_map, get_series_entries_map, iter_series_entries, load_structure, norm_rel, save_structure, scan_contents_entries
except ImportError:
    from maint_structure_lib import CONTENTS_DIR, get_genres_map, get_series_entries_map, iter_series_entries, load_structure, norm_rel, save_structure, scan_contents_entries


def find_unregistered_series_paths(structure: dict) -> list[dict]:
    missing: list[dict] = []

    for genre_key, genre_data in get_genres_map(structure).items():
        if not isinstance(genre_data, dict):
            continue

        genre_root_rel = norm_rel(genre_data.get("path", "")).rstrip("/")
        if not genre_root_rel:
            continue

        genre_root_abs = os.path.join(CONTENTS_DIR, genre_root_rel)
        if not os.path.isdir(genre_root_abs):
            continue

        registered_paths = {
            norm_rel(series_data.get("path", "")).rstrip("/")
            for series_data in get_series_entries_map(genre_data).values()
            if isinstance(series_data, dict)
        }

        for child_name in sorted(os.listdir(genre_root_abs), key=str.lower):
            if child_name.startswith("."):
                continue

            child_abs = os.path.join(genre_root_abs, child_name)
            if not os.path.isdir(child_abs):
                continue

            series_rel = norm_rel(os.path.join(genre_root_rel, child_name)).rstrip("/")
            if not series_rel or series_rel in registered_paths:
                continue

            missing.append({
                "genre": genre_key,
                "path": series_rel,
                "name": child_name,
            })

    return missing


def _make_unique_series_key(existing_keys: set[str], base_name: str) -> str:
    key = base_name or "series"
    if key not in existing_keys:
        return key

    index = 2
    while True:
        candidate = f"{key} ({index})"
        if candidate not in existing_keys:
            return candidate
        index += 1


def _make_scaffold_contents(series_path: str) -> list[dict]:
    entries = scan_contents_entries(series_path)
    return [
        {
            "path": item.get("path", ""),
            "cover": "",
            "name": item.get("name", ""),
            "note": "",
        }
        for item in entries
    ]


def scaffold_missing_series(structure: dict, targets: list[str] | None = None) -> tuple[dict, list[dict]]:
    added: list[dict] = []
    target_list = targets or []

    for genre_key, genre_data in get_genres_map(structure).items():
        if not isinstance(genre_data, dict):
            continue

        genre_root_rel = norm_rel(genre_data.get("path", "")).rstrip("/")
        if not genre_root_rel or not _matches_targets(genre_root_rel, target_list):
            continue

        genre_root_abs = os.path.join(CONTENTS_DIR, genre_root_rel)
        if not os.path.isdir(genre_root_abs):
            continue

        series_entries = get_series_entries_map(genre_data)
        registered_paths = {
            norm_rel(series_data.get("path", "")).rstrip("/")
            for series_data in series_entries.values()
            if isinstance(series_data, dict)
        }
        existing_keys = set(series_entries.keys())

        if isinstance(genre_data.get("entries"), dict):
            target_map = genre_data["entries"]
        else:
            target_map = genre_data

        for child_name in sorted(os.listdir(genre_root_abs), key=str.lower):
            if child_name.startswith("."):
                continue

            child_abs = os.path.join(genre_root_abs, child_name)
            if not os.path.isdir(child_abs):
                continue

            series_rel = norm_rel(os.path.join(genre_root_rel, child_name)).rstrip("/")
            if not series_rel or series_rel in registered_paths or not _matches_targets(series_rel, target_list):
                continue

            series_key = _make_unique_series_key(existing_keys, child_name)
            existing_keys.add(series_key)
            registered_paths.add(series_rel)

            scaffold_entry = {
                "path": series_rel,
                "name": child_name,
                "series": "",
                "main-person": "",
                "persons": [],
                "labels": [],
                "note": "",
                "contents": _make_scaffold_contents(series_rel),
                "exturl": [],
            }
            target_map[series_key] = scaffold_entry
            added.append({
                "genre": genre_key,
                "series": series_key,
                "path": series_rel,
                "count": len(scaffold_entry["contents"]),
            })

    return structure, added


def _matches_targets(series_path: str, targets: list[str]) -> bool:
    normalized_series_path = norm_rel(series_path).rstrip("/")
    if not targets:
        return True
    for raw in targets:
        target = norm_rel(raw).rstrip("/")
        if not target:
            continue
        if normalized_series_path == target or normalized_series_path.startswith(target + "/") or target.startswith(normalized_series_path + "/"):
            return True
    return False


def rebuild_structure_contents(structure: dict, targets: list[str] | None = None) -> tuple[dict, list[dict]]:
    changed: list[dict] = []
    deleted_series: list[tuple[str, str, str]] = []
    target_list = targets or []

    for genre_key, _genre_data, series_key, series_data in iter_series_entries(structure):
        series_path = norm_rel(series_data.get("path", ""))
        if not series_path or not _matches_targets(series_path, target_list):
            continue

        series_abs = os.path.join(CONTENTS_DIR, series_path)
        if not (os.path.isdir(series_abs) or os.path.isfile(series_abs)):
            deleted_series.append((genre_key, series_key, series_path))
            continue

        generated = scan_contents_entries(series_path)
        if series_data.get("contents") != generated:
            changed.append({
                "genre": genre_key,
                "series": series_key,
                "path": series_path,
                "count": len(generated),
            })
            series_data["contents"] = generated

    if deleted_series:
        for genre_key, series_key, series_path in deleted_series:
            genre_data = get_genres_map(structure).get(genre_key)
            if not isinstance(genre_data, dict):
                continue

            entry_map = get_series_entries_map(genre_data)
            if series_key not in entry_map:
                continue

            if isinstance(genre_data.get("entries"), dict):
                del genre_data["entries"][series_key]
            else:
                del genre_data[series_key]

            changed.append({
                "genre": genre_key,
                "series": series_key,
                "path": series_path,
                "count": 0,
                "removed": True,
            })
    return structure, changed


def sync_structure_from_contents(structure: dict, targets: list[str] | None = None) -> tuple[dict, list[dict]]:
    updated, added = scaffold_missing_series(structure, targets)
    updated, changed = rebuild_structure_contents(updated, targets)
    return updated, added + changed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate contents lists in structure.json")
    parser.add_argument("--diff", nargs="*", default=None, help="Only rebuild matching series paths")
    parser.add_argument("--add-missing-series", action="store_true", help="Scaffold missing series entries from site/contents")
    parser.add_argument("--sync", action="store_true", help="Add/remove series and rebuild contents skeletons from site/contents")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    structure = load_structure()
    if args.sync:
        updated, changed = sync_structure_from_contents(structure, args.diff)
    elif args.add_missing_series:
        updated, changed = scaffold_missing_series(structure, args.diff)
    else:
        updated, changed = rebuild_structure_contents(structure, args.diff)

    if args.dry_run:
        print(json.dumps(changed, ensure_ascii=False, indent=2))
        return 0

    save_structure(updated)
    if args.sync:
        print(f"Synchronized {len(changed)} structure.json series entries")
    elif args.add_missing_series:
        print(f"Added {len(changed)} series scaffolds to structure.json")
    else:
        print(f"Updated structure.json contents for {len(changed)} series")
    for item in changed:
        if item.get("removed"):
            print(f"  {item['genre']}:{item['series']} -> removed ({item['path']})")
        elif args.add_missing_series:
            print(f"  {item['genre']}:{item['series']} -> {item['path']} ({item['count']} scaffold contents)")
        else:
            print(f"  {item['genre']}:{item['series']} -> {item['path']} ({item['count']} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())