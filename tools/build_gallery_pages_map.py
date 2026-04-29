"""Compatibility wrapper for legacy maintenance flow.

This script keeps the old entry point but delegates work to the split
maintenance tools introduced for the new structure.json schema.
"""

from __future__ import annotations

import argparse

try:
    from .maint_build_gallery_pages import (
        GALLERY_PAGES_PATH,
        build_gallery_pages_map,
        load_existing_gallery_pages_map,
        select_gallery_paths_for_diff,
        write_gallery_pages_js,
    )
    from .maint_build_structure import rebuild_structure_contents
    from .maint_build_structure_js import main as build_structure_js_main
    from .maint_structure_lib import STRUCTURE_JSON_PATH, load_structure, save_structure
    from .maint_sync_history import PHOTO_DIR, HISTORY_PATH, sync_history
except ImportError:
    from maint_build_gallery_pages import (
        GALLERY_PAGES_PATH,
        build_gallery_pages_map,
        load_existing_gallery_pages_map,
        select_gallery_paths_for_diff,
        write_gallery_pages_js,
    )
    from maint_build_structure import rebuild_structure_contents
    from maint_build_structure_js import main as build_structure_js_main
    from maint_structure_lib import STRUCTURE_JSON_PATH, load_structure, save_structure
    from maint_sync_history import PHOTO_DIR, HISTORY_PATH, sync_history


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Generate derived JS files from structure.json')
    parser.add_argument('--diff', action='store_true', help='Rebuild only galleries matching history.txt entries')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    structure = load_structure(STRUCTURE_JSON_PATH)

    updated_structure, changed = rebuild_structure_contents(structure)
    save_structure(updated_structure)
    if changed:
        print(f'Updated structure.json contents for {len(changed)} series')

    build_structure_js_main()

    result, metadata = build_gallery_pages_map(updated_structure, diff=args.diff)
    write_gallery_pages_js(result)
    print(f'Generated {GALLERY_PAGES_PATH}')
    print(f"Galleries: {metadata['gallery_count']}, pages: {metadata['page_count']}")
    print(f"Gallery thumbnails: generated={metadata['generated']}, reused={metadata['reused']}")

    new_dirs = sync_history(PHOTO_DIR, HISTORY_PATH)
    if new_dirs:
        print(f'Recorded {len(new_dirs)} new photo directories to history.txt (next: block)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
