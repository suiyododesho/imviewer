#!/usr/bin/env python3
"""Build frozen maintenance executables into tools/bin using cx_Freeze."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    from cx_Freeze import Executable, setup
except ImportError as exc:
    raise SystemExit(
        "cx_Freeze is required. Install it with: pip install cx_Freeze"
    ) from exc

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
BIN_DIR = TOOLS_DIR / "bin"


def clean_bin_dir(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> int:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    clean_bin_dir(BIN_DIR)

    if len(sys.argv) == 1:
        sys.argv.append("build_exe")

    options = {
        "build_exe": {
            "build_exe": str(BIN_DIR),
            "includes": [
                "build_site_config",
                "history_manager",
                "maint_build_gallery_pages",
                "maint_build_gallery_thumbnails",
                "maint_build_structure",
                "maint_build_structure_js",
                "maint_extract_archives",
                "maint_refresh_covers",
                "maint_structure_lib",
                "maint_sync_history",
            ],
            "excludes": ["tkinter"],
        }
    }

    executables = [
        Executable(
            script=str(TOOLS_DIR / "maint_build_structure.py"),
            target_name="maint_build_structure.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_extract_archives.py"),
            target_name="maint_extract_archives.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_build_gallery_thumbnails.py"),
            target_name="maint_build_gallery_thumbnails.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_refresh_covers.py"),
            target_name="maint_refresh_covers.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_build_structure_js.py"),
            target_name="maint_build_structure_js.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_build_gallery_pages.py"),
            target_name="maint_build_gallery_pages.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "build_site_config.py"),
            target_name="build_site_config.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "maint_sync_history.py"),
            target_name="maint_sync_history.exe",
        ),
        Executable(
            script=str(TOOLS_DIR / "build_gallery_pages_map.py"),
            target_name="build_gallery_pages_map.exe",
        ),
    ]

    setup(
        name="maintenance-tools",
        version="1.1.0",
        description="Frozen maintenance tools",
        options=options,
        executables=executables,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
