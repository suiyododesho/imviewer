"""Extract supported archive contents under site/contents/."""

from __future__ import annotations

import argparse
import json
import os

try:
    from .maint_structure_lib import CONTENTS_DIR, CONTENT_RENDER_DPI, ROOT, THUMBNAIL_DIR_SUFFIXES, extract_archive_pages_to_dir, get_archive_content_dir_rel, norm_rel
except ImportError:
    from maint_structure_lib import CONTENTS_DIR, CONTENT_RENDER_DPI, ROOT, THUMBNAIL_DIR_SUFFIXES, extract_archive_pages_to_dir, get_archive_content_dir_rel, norm_rel

SUPPORTED_ARCHIVE_EXTENSIONS = {".pdf", ".cbz", ".zip"}
UNSUPPORTED_ARCHIVE_EXTENSIONS = {".rar", ".7z"}
GENERATED_DIR_SUFFIXES = tuple(sorted(set(THUMBNAIL_DIR_SUFFIXES + ("_pdf", "_cbz", "_zip", "_rar", "_7z"))))
DEFAULT_CONFIG_PATH = os.path.join(ROOT, "tools", "maintenance_config.json")
DEFAULT_ARCHIVE_LONG_EDGE_PX = 2000
DEFAULT_PDF_RENDER_DPI = CONTENT_RENDER_DPI


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


def _parse_positive_int(value, fallback: int | None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def load_archive_extract_settings(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    settings = {
        "long_edge_px": DEFAULT_ARCHIVE_LONG_EDGE_PX,
        "pdf_render_dpi": DEFAULT_PDF_RENDER_DPI,
    }

    if not config_path or not os.path.isfile(config_path):
        return settings

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return settings

    section = data.get("archive_extract") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        return settings

    settings["long_edge_px"] = _parse_positive_int(section.get("long_edge_px"), settings["long_edge_px"])
    settings["pdf_render_dpi"] = _parse_positive_int(section.get("pdf_render_dpi"), settings["pdf_render_dpi"])
    return settings


def extract_archives(
    contents_dir: str = CONTENTS_DIR,
    targets: list[str] | None = None,
    long_edge_px: int = DEFAULT_ARCHIVE_LONG_EDGE_PX,
    pdf_render_dpi: int = DEFAULT_PDF_RENDER_DPI,
) -> dict:
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
            extract_archive_pages_to_dir(
                archive_abs,
                output_abs,
                archive_kind=ext.lstrip('.'),
                dpi=pdf_render_dpi,
                long_edge_px=long_edge_px,
            )
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
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to maintenance config JSON")
    parser.add_argument("--long-edge", type=int, default=None, help="Target long edge for extracted images")
    parser.add_argument("--pdf-dpi", type=int, default=None, help="PDF render DPI before resize")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config_settings = load_archive_extract_settings(args.config)
    long_edge_px = _parse_positive_int(args.long_edge, config_settings["long_edge_px"])
    pdf_render_dpi = _parse_positive_int(args.pdf_dpi, config_settings["pdf_render_dpi"])

    result = extract_archives(
        targets=args.paths,
        long_edge_px=long_edge_px,
        pdf_render_dpi=pdf_render_dpi,
    )
    print(f"Extracted {len(result['extracted'])} archive directories")
    print(f"  settings: long_edge_px={long_edge_px}, pdf_render_dpi={pdf_render_dpi}")
    for path in result["extracted"]:
        print(f"  extracted: {path}")
    for path in result["unsupported"]:
        print(f"  unsupported: {path}")
    for item in result["skipped"]:
        print(f"  failed: {item['path']} ({item['error']})")
    return 0 if not result["skipped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
