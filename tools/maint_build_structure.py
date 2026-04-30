"""Regenerate series contents in site/structure.json."""

from __future__ import annotations

import argparse
import json
import os

try:
    from .maint_structure_lib import CONTENTS_DIR, generate_contents_entries, get_genres_map, iter_series_entries, load_structure, norm_rel, save_structure
except ImportError:
    from maint_structure_lib import CONTENTS_DIR, generate_contents_entries, get_genres_map, iter_series_entries, load_structure, norm_rel, save_structure


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

        generated = generate_contents_entries(series_path)
        if series_data.get("contents") != generated:
            changed.append({
                "genre": genre_key,
                "series": series_key,
                "path": series_path,
                "count": len(generated),
            })
            series_data["contents"] = generated

    if deleted_series:
        genres = structure.get("genres", {})
        for genre_key, series_key, series_path in deleted_series:
            genre_data = get_genres_map(structure).get(genre_key)
            if isinstance(genre_data, dict) and series_key in genre_data:
                del genre_data[series_key]
                changed.append({
                    "genre": genre_key,
                    "series": series_key,
                    "path": series_path,
                    "count": 0,
                    "removed": True,
                })
    return structure, changed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate contents lists in structure.json")
    parser.add_argument("--diff", nargs="*", default=None, help="Only rebuild matching series paths")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    structure = load_structure()
    updated, changed = rebuild_structure_contents(structure, args.diff)

    if args.dry_run:
        print(json.dumps(changed, ensure_ascii=False, indent=2))
        return 0

    save_structure(updated)
    print(f"Updated structure.json contents for {len(changed)} series")
    for item in changed:
        if item.get("removed"):
            print(f"  {item['genre']}:{item['series']} -> removed ({item['path']})")
        else:
            print(f"  {item['genre']}:{item['series']} -> {item['path']} ({item['count']} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())