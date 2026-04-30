"""Extract supported archive contents under site/contents/."""

from __future__ import annotations

import argparse
import os

try:
    from .maint_structure_lib import CONTENTS_DIR, THUMBNAIL_DIR_SUFFIXES, extract_archive_pages_to_dir, get_archive_content_dir_rel, norm_rel
except ImportError:
    from maint_structure_lib import CONTENTS_DIR, THUMBNAIL_DIR_SUFFIXES, extract_archive_pages_to_dir, get_archive_content_dir_rel, norm_rel

SUPPORTED_ARCHIVE_EXTENSIONS = {".pdf", ".cbz", ".zip"}
UNSUPPORTED_ARCHIVE_EXTENSIONS = {".rar", ".7z"}
GENERATED_DIR_SUFFIXES = tuple(sorted(set(THUMBNAIL_DIR_SUFFIXES + ("_pdf", "_cbz", "_zip", "_rar", "_7z"))))


def _should_skip_dir(name: str) -> bool:
    lowered = name.lower()
    return lowered == "thumbnail" or lowered == "src" or lowered.endswith(GENERATED_DIR_SUFFIXES)


def iter_archive_files(contents_dir: str = CONTENTS_DIR):
    for root, dirs, files in os.walk(contents_dir):
        dirs[:] = [d for d in sorted(dirs, key=str.lower) if not d.startswith(".") and not _should_skip_dir(d)]
        for name in sorted(files, key=str.lower):
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_ARCHIVE_EXTENSIONS | UNSUPPORTED_ARCHIVE_EXTENSIONS:
                continue
            archive_abs = os.path.join(root, name)
            archive_rel = norm_rel(os.path.relpath(archive_abs, contents_dir))
            yield archive_rel, archive_abs, ext


def extract_archives(contents_dir: str = CONTENTS_DIR, targets: list[str] | None = None) -> dict:
    target_list = [norm_rel(item).rstrip("/") for item in (targets or []) if norm_rel(item).rstrip("/")]
    extracted: list[str] = []
    skipped: list[dict] = []
    unsupported: list[str] = []

    for archive_rel, archive_abs, ext in iter_archive_files(contents_dir):
        normalized_rel = norm_rel(archive_rel)
        if target_list and not any(
            normalized_rel == target or normalized_rel.startswith(target + "/") or target.startswith(normalized_rel + "/")
            for target in target_list
        ):
            continue

        if ext in UNSUPPORTED_ARCHIVE_EXTENSIONS:
            unsupported.append(normalized_rel)
            continue

        output_rel = get_archive_content_dir_rel(normalized_rel)
        output_abs = os.path.join(contents_dir, output_rel)
        try:
            extract_archive_pages_to_dir(archive_abs, output_abs, archive_kind=ext.lstrip('.'))
            extracted.append(output_rel)
        except Exception as exc:
            skipped.append({"path": normalized_rel, "error": str(exc)})

    return {
        "extracted": extracted,
        "unsupported": unsupported,
        "skipped": skipped,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Extract PDF/CBZ/ZIP contents into generated directories")
    parser.add_argument("paths", nargs="*", help="Only extract matching archive paths or parent directories")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    result = extract_archives(targets=args.paths)
    print(f"Extracted {len(result['extracted'])} archive directories")
    for path in result["extracted"]:
        print(f"  extracted: {path}")
    for path in result["unsupported"]:
        print(f"  unsupported: {path}")
    for item in result["skipped"]:
        print(f"  failed: {item['path']} ({item['error']})")
    return 0 if not result["skipped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
