"""Regenerate series contents in site/structure.json."""

from __future__ import annotations

import argparse
import json

try:
    from .maint_structure_lib import generate_contents_entries, iter_series_entries, load_structure, norm_rel, save_structure
except ImportError:
    from maint_structure_lib import generate_contents_entries, iter_series_entries, load_structure, norm_rel, save_structure


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
    target_list = targets or []
    for genre_key, _genre_data, series_key, series_data in iter_series_entries(structure):
        series_path = norm_rel(series_data.get("path", ""))
        if not series_path or not _matches_targets(series_path, target_list):
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
        print(f"  {item['genre']}:{item['series']} -> {item['path']} ({item['count']} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())