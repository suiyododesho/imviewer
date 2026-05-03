"""Generate gallery thumbnail files for content entries in structure.json."""

from __future__ import annotations

import argparse

try:
    from .maint_build_gallery_pages import generate_gallery_thumbnails
    from .maint_structure_lib import load_structure
except ImportError:
    from maint_build_gallery_pages import generate_gallery_thumbnails
    from maint_structure_lib import load_structure


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate gallery thumbnail files from structure.json")
    parser.add_argument("--diff", action="store_true", help="Rebuild only galleries matching history.txt entries")
    parser.add_argument("--full", action="store_true", help="Force full rebuild")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    diff_mode = args.diff and not args.full
    structure = load_structure()
    metadata = generate_gallery_thumbnails(structure, diff=diff_mode)
    if metadata.get("skipped"):
        print("No diff targets (history.txt empty). Skipped gallery thumbnail generation.")
        return 0
    print(f"Gallery thumbnail targets: {metadata['gallery_count']}")
    print(f"Gallery thumbnails: generated={metadata['generated']}, reused={metadata['reused']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
