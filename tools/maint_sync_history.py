"""Synchronize history.txt pending dirs with current photo content directories."""

from __future__ import annotations

import os

try:
    from .history_manager import parse_history, write_history
    from .maint_structure_lib import CONTENTS_DIR, norm_rel
except ImportError:
    from history_manager import parse_history, write_history
    from maint_structure_lib import CONTENTS_DIR, norm_rel

PHOTO_DIR = os.path.join(CONTENTS_DIR, 'photo')
HISTORY_PATH = os.path.join(os.path.dirname(CONTENTS_DIR), 'history.txt')


def get_all_photo_content_dirs(photo_dir: str) -> set[str]:
    paths: set[str] = set()
    if not os.path.isdir(photo_dir):
        return paths
    for series in sorted(os.listdir(photo_dir), key=str.lower):
        series_abs = os.path.join(photo_dir, series)
        if not os.path.isdir(series_abs):
            continue
        for content_name in sorted(os.listdir(series_abs), key=str.lower):
            content_abs = os.path.join(series_abs, content_name)
            if not os.path.isdir(content_abs):
                continue
            if content_name.lower().endswith((
                '_tn', '_pdf_tn', '_cbz_tn', '_zip_tn',  # legacy
                '_pdf', '_cbz', '_zip', '_rar', '_7z',  # current
            )):
                continue
            paths.add(norm_rel(f'photo/{series}/{content_name}'))
    return paths


def detect_new_photo_dirs(photo_dir, history_data):
    current_paths = get_all_photo_content_dirs(photo_dir)
    known_paths = history_data.all_known_dirs()
    return sorted(current_paths - known_paths)


def sync_history(photo_dir: str = PHOTO_DIR, history_path: str = HISTORY_PATH) -> list[str]:
    data = parse_history(history_path)
    new_paths = detect_new_photo_dirs(photo_dir, data)
    if not new_paths:
        return []
    data.next_dirs.extend(new_paths)
    write_history(history_path, data)
    return new_paths


def main() -> int:
    new_paths = sync_history()
    if not new_paths:
        print('No new photo directories detected.')
        return 0
    print(f'Recorded {len(new_paths)} new photo directories to history.txt (next: block):')
    for path in new_paths:
        print(f'  {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())