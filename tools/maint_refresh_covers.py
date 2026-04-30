"""Refresh content cover paths in site/structure.json."""

from __future__ import annotations

import argparse
import json

try:
    from .maint_structure_lib import find_cover_for_content, iter_content_entries, load_structure, norm_rel, save_structure
except ImportError:
    from maint_structure_lib import find_cover_for_content, iter_content_entries, load_structure, norm_rel, save_structure


def _matches_targets(content_path: str, targets: list[str]) -> bool:
    normalized_content_path = norm_rel(content_path).rstrip("/")
    if not targets:
        return True
    for raw in targets:
        target = norm_rel(raw).rstrip("/")
        if not target:
            continue
        if normalized_content_path == target or normalized_content_path.startswith(target + "/") or target.startswith(normalized_content_path + "/"):
            return True
    return False


def refresh_content_covers(structure: dict, targets: list[str] | None = None) -> tuple[dict, list[dict]]:
    changed: list[dict] = []
    target_list = targets or []

    for genre_key, _genre_data, series_key, _series_data, item in iter_content_entries(structure):
        content_path = norm_rel(item.get("path", ""))
        if not content_path or not _matches_targets(content_path, target_list):
            continue
        cover = find_cover_for_content(content_path)
        if item.get("cover") == cover:
            continue
        item["cover"] = cover
        changed.append({
            "genre": genre_key,
            "series": series_key,
            "path": content_path,
            "cover": cover,
        })

    return structure, changed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Refresh content cover paths in structure.json")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("paths", nargs="*", help="Only refresh matching content paths")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    structure = load_structure()
    updated, changed = refresh_content_covers(structure, args.paths)

    if args.dry_run:
        print(json.dumps(changed, ensure_ascii=False, indent=2))
        return 0

    save_structure(updated)
    print(f"Refreshed {len(changed)} content cover paths")
    for item in changed:
        print(f"  {item['genre']}:{item['series']} -> {item['path']} ({item['cover']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
