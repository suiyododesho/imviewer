"""Compatibility wrapper for the full maintenance pipeline."""

from __future__ import annotations

import argparse

try:
    from .build_site_config import main as build_site_config_main
    from .maint_build_gallery_pages import main as build_gallery_pages_main
    from .maint_build_gallery_thumbnails import main as build_gallery_thumbnails_main
    from .maint_build_structure import main as build_structure_main
    from .maint_build_structure_js import main as build_structure_js_main
    from .maint_extract_archives import main as extract_archives_main
    from .maint_refresh_covers import main as refresh_covers_main
    from .maint_sync_history import main as sync_history_main
except ImportError:
    from build_site_config import main as build_site_config_main
    from maint_build_gallery_pages import main as build_gallery_pages_main
    from maint_build_gallery_thumbnails import main as build_gallery_thumbnails_main
    from maint_build_structure import main as build_structure_main
    from maint_build_structure_js import main as build_structure_js_main
    from maint_extract_archives import main as extract_archives_main
    from maint_refresh_covers import main as refresh_covers_main
    from maint_sync_history import main as sync_history_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Run the full maintenance pipeline')
    parser.add_argument('--diff', action='store_true', help='Run diff mode for gallery thumbnails and gallery-pages')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    diff_args = ['--diff'] if args.diff else []

    steps = [
        (build_structure_main, ['--sync']),
        (extract_archives_main, []),
        (build_gallery_thumbnails_main, diff_args),
        (refresh_covers_main, []),
        (build_structure_js_main, []),
        (build_gallery_pages_main, diff_args),
        (build_site_config_main, []),
        (sync_history_main, []),
    ]

    for func, step_args in steps:
        rc = func(step_args) if step_args else func()
        if rc:
            return rc
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
