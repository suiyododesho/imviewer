"""Shared helpers for maintenance tools working with site/structure.json."""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict

if getattr(sys, "frozen", False):
    ROOT = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
else:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_env_site_dir = os.environ.get("IMVIEWER_SITE_DIR")
if _env_site_dir and os.path.isdir(_env_site_dir):
    SITE_DIR = os.path.abspath(_env_site_dir)
else:
    SITE_DIR = os.path.join(ROOT, "site")
CONTENTS_DIR = os.path.join(SITE_DIR, "contents")
THUMBNAIL_DIR = os.path.join(SITE_DIR, "thumbnail")
STRUCTURE_JSON_PATH = os.path.join(SITE_DIR, "structure.json")
STRUCTURE_JS_PATH = os.path.join(SITE_DIR, "js", "structure.js")

GENRE_META_KEYS = {
    "name",
    "path",
    "note",
    "labels",
    "class",
    "classname",
    "browse",
    "searchkey",
    "searchkeyname",
    "entries",
}
THUMBNAIL_DIR_SUFFIXES = (
    "_tn", "_pdf_tn", "_cbz_tn", "_zip_tn",  # legacy
    "_zip", "_rar", "_7z",  # legacy/current non-gallery generated caches
)
MEDIA_FILE_EXTENSIONS = {
    ".pdf",
    ".cbz",
    ".zip",
    ".rar",
    ".7z",
    ".html",
    ".htm",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".avif",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".mpeg",
    ".mpg",
}

# Extensions treated as single-file archive galleries (each file = one content entry)
ARCHIVE_CONTENT_EXTENSIONS = frozenset({".pdf", ".cbz", ".zip", ".rar", ".7z"})
# Image/video extensions that are raw media inside a gallery directory
DIRECT_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"})
DIRECT_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".mov", ".wmv", ".mpeg", ".mpg"})
# DPI for rendering PDF pages as JPEG images
PDF_RENDER_DPI = 150
# DPI for rendering PDF pages as gallery content images.
CONTENT_RENDER_DPI = 200
# Long edge size (px) used for all generated thumbnails.
THUMBNAIL_LONG_EDGE_PX = 200
# Long edge size (px) used for generated gallery content images.
CONTENT_LONG_EDGE_PX = 2200


def norm_rel(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def load_structure(path: str = STRUCTURE_JSON_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_structure(structure: dict, path: str = STRUCTURE_JSON_PATH) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
        f.write("\n")


def get_genres_map(structure: dict) -> OrderedDict[str, dict]:
    genres = structure.get("genres", {}) if isinstance(structure, dict) else {}
    if isinstance(genres, dict):
        return OrderedDict((str(key), value) for key, value in genres.items())

    # Compatibility with the old singleton-array format.
    ordered: OrderedDict[str, dict] = OrderedDict()
    if isinstance(genres, list):
        for item in genres:
            if not isinstance(item, dict):
                continue
            for key, value in item.items():
                ordered[str(key)] = value
    return ordered


def set_genres_map(structure: dict, genres_map: OrderedDict[str, dict]) -> dict:
    structure["genres"] = dict(genres_map)
    return structure


def get_series_entries_map(genre_data: dict) -> OrderedDict[str, dict]:
    if not isinstance(genre_data, dict):
        return OrderedDict()

    explicit_entries = genre_data.get("entries")
    if isinstance(explicit_entries, dict):
        return OrderedDict(
            (str(key), value)
            for key, value in explicit_entries.items()
            if isinstance(value, dict)
        )

    return OrderedDict(
        (str(key), value)
        for key, value in genre_data.items()
        if key not in GENRE_META_KEYS and isinstance(value, dict)
    )


def iter_series_entries(structure: dict):
    for genre_key, genre_data in get_genres_map(structure).items():
        if not isinstance(genre_data, dict):
            continue
        for series_key, series_data in get_series_entries_map(genre_data).items():
            yield genre_key, genre_data, series_key, series_data


def _looks_like_generated_thumbnail_dir(name: str) -> bool:
    lowered = name.lower()
    return lowered in {"thumbnail", "src"} or lowered.endswith(THUMBNAIL_DIR_SUFFIXES)


def _content_display_name(rel_path: str) -> str:
    name = os.path.basename(norm_rel(rel_path).rstrip("/"))
    stem, ext = os.path.splitext(name)
    return stem if ext else name


def _scan_series_children(series_root_abs: str) -> tuple[list[str], list[tuple[str, str]], bool]:
    subdirs: list[str] = []
    archive_files: list[tuple[str, str]] = []
    has_direct_media = False

    for child_name in sorted(os.listdir(series_root_abs), key=str.lower):
        if child_name.startswith("."):
            continue
        if _looks_like_generated_thumbnail_dir(child_name):
            continue

        child_abs = os.path.join(series_root_abs, child_name)
        if os.path.isdir(child_abs):
            subdirs.append(child_name)
            continue
        if not os.path.isfile(child_abs):
            continue

        ext = os.path.splitext(child_name)[1].lower()
        if ext in ARCHIVE_CONTENT_EXTENSIONS:
            archive_files.append((child_name, ext.lstrip(".")))
        elif ext in DIRECT_IMAGE_EXTENSIONS | DIRECT_VIDEO_EXTENSIONS:
            has_direct_media = True

    return subdirs, archive_files, has_direct_media


def scan_contents_entries(series_root_rel: str) -> list[dict]:
    normalized_root = norm_rel(series_root_rel)
    if not normalized_root:
        return []

    series_root_abs = os.path.join(CONTENTS_DIR, normalized_root)
    if not os.path.isdir(series_root_abs):
        return []

    subdirs, archive_files, has_direct_media = _scan_series_children(series_root_abs)

    if not subdirs and not archive_files:
        if has_direct_media:
            return [{
                "path": normalized_root,
                "cover": "",
                "name": _content_display_name(normalized_root),
                "note": "",
            }]
        return []

    # Archive files are represented by their generated directory paths
    # (e.g., "foo.pdf" -> "foo_pdf") and never by the original file path.
    subdir_set = {s.lower() for s in subdirs}
    generated_archive_dirs: list[str] = []
    for child_name, _archive_kind in archive_files:
        archive_rel = norm_rel(os.path.join(normalized_root, child_name))
        generated_rel = get_archive_content_dir_rel(archive_rel)
        generated_name = os.path.basename(generated_rel)
        if generated_name.lower() in subdir_set:
            continue
        generated_archive_dirs.append(generated_name)

    all_subdirs = sorted(set(subdirs + generated_archive_dirs), key=str.lower)

    entries: list[dict] = []
    for child_name in all_subdirs:
        child_rel = norm_rel(os.path.join(normalized_root, child_name))
        entries.append({
            "path": child_rel,
            "cover": "",
            "name": _content_display_name(child_rel),
            "note": "",
        })

    entries.sort(key=lambda e: e["name"].lower())
    return entries


def _candidate_cover_paths_for_content(rel_path: str) -> list[str]:
    normalized = norm_rel(rel_path)
    candidates: list[str] = []
    abs_path = os.path.join(CONTENTS_DIR, normalized)

    if os.path.isdir(abs_path):
        candidates.extend([
            f"thumbnail/{normalized}/cover.jpg",
            f"thumbnail/{normalized}/001.jpg",
            # Legacy generated layout
            f"thumbnail/{normalized}_tn/cover.jpg",
            f"thumbnail/{normalized}_tn/001.jpg",
            # Backward compatibility (legacy in-contents locations)
            f"{normalized}_tn/cover.jpg",
            f"{normalized}_tn/001.jpg",
            f"{normalized}/src/thumbnail/cover.jpg",
            f"{normalized}/thumbnail/cover.jpg",
            f"{normalized}/cover.jpg",
        ])
        return [norm_rel(item) for item in candidates]

    stem, ext = os.path.splitext(normalized)
    ext_name = ext.lstrip(".").lower()
    if ext_name:
        candidates.append(f"thumbnail/{stem}_{ext_name}/cover.jpg")
        candidates.append(f"thumbnail/{stem}_{ext_name}/001.jpg")
        # Legacy generated layout
        candidates.append(f"thumbnail/{stem}_{ext_name}_tn/cover.jpg")
        candidates.append(f"thumbnail/{stem}_{ext_name}_tn/001.jpg")
        # Backward compatibility (legacy in-contents locations)
        candidates.append(f"{stem}_{ext_name}_tn/cover.jpg")
        # 001.jpg is the first extracted page for PDF/CBZ archives.
        candidates.append(f"{stem}_{ext_name}_tn/001.jpg")
    candidates.extend([
        f"thumbnail/{stem}_tn/cover.jpg",
        f"thumbnail/{stem}_tn/001.jpg",
        # Backward compatibility (legacy in-contents locations)
        f"{stem}_tn/cover.jpg",
        f"{stem}_tn/001.jpg",
        f"{stem}_cover.jpg",
    ])
    return [norm_rel(item) for item in candidates]


def find_cover_for_content(rel_path: str) -> str:
    for candidate in _candidate_cover_paths_for_content(rel_path):
        if candidate.startswith("thumbnail/"):
            candidate_abs = os.path.join(SITE_DIR, candidate)
        else:
            candidate_abs = os.path.join(CONTENTS_DIR, candidate)
        if os.path.isfile(candidate_abs):
            return candidate
    return ""


def generate_contents_entries(series_root_rel: str) -> list[dict]:
    normalized_root = norm_rel(series_root_rel)
    if not normalized_root:
        return []

    series_root_abs = os.path.join(CONTENTS_DIR, normalized_root)
    if not os.path.isdir(series_root_abs):
        return []

    subdirs, archive_files, has_direct_media = _scan_series_children(series_root_abs)

    generated_archive_dirs: list[str] = []
    for archive_name, archive_kind in archive_files:
        archive_abs = os.path.join(series_root_abs, archive_name)
        archive_rel = norm_rel(os.path.join(normalized_root, archive_name))
        target_rel = get_archive_content_dir_rel(archive_rel)
        extract_kwargs = {"long_edge_px": CONTENT_LONG_EDGE_PX}
        if archive_kind == "pdf":
            extract_kwargs["dpi"] = CONTENT_RENDER_DPI

        target_abs = os.path.join(CONTENTS_DIR, target_rel)
        try:
            extract_archive_pages_to_dir(archive_abs, target_abs, archive_kind=archive_kind, **extract_kwargs)
        except Exception as exc:
            print(f"  [archive extract error] {archive_rel}: {exc}")
            continue

        target_name = os.path.basename(target_rel)
        if os.path.isdir(target_abs):
            generated_archive_dirs.append(target_name)

    # If the directory contains only raw images/videos (no subdirs, no archives),
    # treat the directory itself as a single gallery content entry.
    all_subdirs = sorted(set(subdirs + generated_archive_dirs), key=str.lower)

    if not all_subdirs and not archive_files:
        if has_direct_media:
            return [{
                "path": normalized_root,
                "cover": find_cover_for_content(normalized_root),
                "name": _content_display_name(normalized_root),
                "note": "",
            }]
        return []

    entries: list[dict] = []
    for child_name in all_subdirs:
        child_rel = norm_rel(os.path.join(normalized_root, child_name))
        entries.append({
            "path": child_rel,
            "cover": find_cover_for_content(child_rel),
            "name": _content_display_name(child_rel),
            "note": "",
        })
    # Sort combined list by name (case-insensitive)
    entries.sort(key=lambda e: e["name"].lower())
    return entries


def collect_gallery_html_paths_for_content(content_path: str) -> list[str]:
    normalized = norm_rel(content_path)
    if not normalized:
        return []

    abs_path = os.path.join(CONTENTS_DIR, normalized)
    if os.path.isfile(abs_path):
        if os.path.splitext(normalized)[1].lower() in {".html", ".htm"}:
            return [normalized]
        return []

    if not os.path.isdir(abs_path):
        return []

    result: list[str] = []
    for root, dirs, files in os.walk(abs_path):
        dirs[:] = sorted(
            [d for d in dirs if not (d.lower() == "thumbnail" and os.path.basename(root).lower() == "src")],
            key=str.lower,
        )
        for name in sorted(files, key=str.lower):
            if os.path.splitext(name)[1].lower() not in {".html", ".htm"}:
                continue
            file_abs = os.path.join(root, name)
            result.append(norm_rel(os.path.relpath(file_abs, CONTENTS_DIR)))
    return result


def collect_gallery_file_paths_for_content(content_path: str) -> list[str]:
    """Return gallery entry paths for a content item.

    For HTML content or directories containing HTML: returns the HTML file paths.
    For archive-backed content directories: returns the generated directory path.
    For directories containing only raw images/videos: returns the directory path itself.
    """
    normalized = norm_rel(content_path)
    if not normalized:
        return []

    abs_path = os.path.join(CONTENTS_DIR, normalized)

    # Single file
    if os.path.isfile(abs_path):
        ext = os.path.splitext(normalized)[1].lower()
        if ext in {".html", ".htm"}:
            return [normalized]
        if ext == ".pdf":
            generated = get_pdf_content_dir_rel(normalized)
            return [generated] if os.path.isdir(os.path.join(CONTENTS_DIR, generated)) else []
        if ext == ".cbz":
            generated = get_cbz_content_dir_rel(normalized)
            return [generated] if os.path.isdir(os.path.join(CONTENTS_DIR, generated)) else []
        return []

    if not os.path.isdir(abs_path):
        return []

    # Directory: HTML files take priority (recursive)
    html_files = collect_gallery_html_paths_for_content(content_path)
    if html_files:
        return html_files

    # No HTML: include generated archive directories if present.
    generated_archive_paths: list[str] = []
    try:
        children = sorted(os.listdir(abs_path), key=str.lower)
    except OSError:
        return []
    for name in children:
        if name.startswith("."):
            continue
        if _looks_like_generated_thumbnail_dir(name):
            continue
        if name.lower().endswith("_pdf") or name.lower().endswith("_cbz"):
            generated_archive_paths.append(norm_rel(os.path.join(normalized, name)))
    if generated_archive_paths:
        return generated_archive_paths

    # No HTML, no archives: if directory has raw images/videos, use directory itself
    for name in children:
        ext = os.path.splitext(name)[1].lower()
        if ext in DIRECT_IMAGE_EXTENSIONS | DIRECT_VIDEO_EXTENSIONS:
            return [normalized]

    return []


def iter_content_entries(structure: dict):
    for genre_key, genre_data, series_key, series_data in iter_series_entries(structure):
        for item in series_data.get("contents", []):
            if not isinstance(item, dict):
                continue
            path = norm_rel(item.get("path", ""))
            if not path:
                continue
            yield genre_key, genre_data, series_key, series_data, item


def get_pdf_thumb_dir_rel(pdf_rel: str) -> str:
    """Return the relative path of the thumbnail directory for a PDF file."""
    stem = os.path.splitext(norm_rel(pdf_rel))[0]
    return f"thumbnail/{stem}_pdf"


def get_cbz_thumb_dir_rel(cbz_rel: str) -> str:
    """Return the relative path of the thumbnail directory for a CBZ file."""
    stem = os.path.splitext(norm_rel(cbz_rel))[0]
    return f"thumbnail/{stem}_cbz"


def get_pdf_content_dir_rel(pdf_rel: str) -> str:
    """Return the relative path of the generated content directory for a PDF file."""
    stem = os.path.splitext(norm_rel(pdf_rel))[0]
    return f"{stem}_pdf"


def get_cbz_content_dir_rel(cbz_rel: str) -> str:
    """Return the relative path of the generated content directory for a CBZ file."""
    stem = os.path.splitext(norm_rel(cbz_rel))[0]
    return f"{stem}_cbz"


def get_zip_content_dir_rel(zip_rel: str) -> str:
    """Return the relative path of the generated content directory for a ZIP file."""
    stem = os.path.splitext(norm_rel(zip_rel))[0]
    return f"{stem}_zip"


def get_archive_content_dir_rel(archive_rel: str) -> str:
    normalized = norm_rel(archive_rel)
    stem, ext = os.path.splitext(normalized)
    ext_name = ext.lstrip(".").lower()
    if ext_name == "pdf":
        return f"{stem}_pdf"
    if ext_name == "cbz":
        return f"{stem}_cbz"
    if ext_name == "zip":
        return f"{stem}_zip"
    if ext_name == "rar":
        return f"{stem}_rar"
    if ext_name == "7z":
        return f"{stem}_7z"
    return normalized


def resize_image_to_long_edge(image, long_edge_px: int = THUMBNAIL_LONG_EDGE_PX):
    """Resize PIL image so that its long edge becomes long_edge_px.

    The image is never upscaled.
    """
    from PIL import Image

    rgb = image.convert("RGB")
    width, height = rgb.size
    max_edge = max(width, height)
    if max_edge <= 0 or max_edge <= long_edge_px:
        return rgb

    scale = long_edge_px / float(max_edge)
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return rgb.resize(new_size, Image.Resampling.LANCZOS)


def extract_pdf_pages_to_dir(
    pdf_abs: str,
    thumb_dir_abs: str,
    dpi: int = PDF_RENDER_DPI,
    long_edge_px: int | None = THUMBNAIL_LONG_EDGE_PX,
) -> list[str]:
    """Render each PDF page as a JPEG image into thumb_dir_abs.

    Skips pages that already exist and are newer than the PDF.
    Returns the list of output file paths (all pages, not only newly generated).
    """
    import fitz  # pymupdf
    from PIL import Image

    os.makedirs(thumb_dir_abs, exist_ok=True)
    pdf_mtime = os.path.getmtime(pdf_abs)
    output_paths: list[str] = []

    with fitz.open(pdf_abs) as doc:
        for i, page in enumerate(doc):
            dst = os.path.join(thumb_dir_abs, f"{i + 1:03d}.jpg")
            needs_render = True
            if os.path.isfile(dst):
                try:
                    needs_render = os.path.getmtime(dst) < pdf_mtime
                except OSError:
                    pass
            if needs_render:
                # Render close to target size first, then normalize exactly to long-edge rule.
                page_long_edge = max(float(page.rect.width), float(page.rect.height))
                target_scale = (long_edge_px / page_long_edge) if (long_edge_px and page_long_edge > 0) else 1.0
                base_scale = dpi / 72.0
                scale = min(base_scale, max(target_scale, 0.01)) if long_edge_px else max(base_scale, 0.01)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                with Image.frombytes("RGB", [pix.width, pix.height], pix.samples) as im:
                    out = resize_image_to_long_edge(im, long_edge_px) if long_edge_px else im.convert("RGB")
                    out.save(dst, format="JPEG", quality=85, optimize=True)
            output_paths.append(dst)

    return output_paths


def extract_cbz_pages_to_dir(cbz_abs: str, thumb_dir_abs: str, long_edge_px: int | None = THUMBNAIL_LONG_EDGE_PX) -> list[str]:
    """Extract images from a CBZ (zip) archive into thumb_dir_abs as numbered JPEGs.

    Skips files that already exist and are newer than the archive.
    Returns the list of output file paths.
    """
    import io
    import zipfile

    from PIL import Image, ImageOps

    os.makedirs(thumb_dir_abs, exist_ok=True)
    cbz_mtime = os.path.getmtime(cbz_abs)
    output_paths: list[str] = []

    with zipfile.ZipFile(cbz_abs, "r") as zf:
        image_names = sorted(
            name for name in zf.namelist()
            if os.path.splitext(name)[1].lower() in DIRECT_IMAGE_EXTENSIONS
            and not os.path.basename(name).startswith(".")
        )
        for i, name in enumerate(image_names):
            dst = os.path.join(thumb_dir_abs, f"{i + 1:03d}.jpg")
            needs_extract = True
            if os.path.isfile(dst):
                try:
                    needs_extract = os.path.getmtime(dst) < cbz_mtime
                except OSError:
                    pass
            if needs_extract:
                data = zf.read(name)
                with Image.open(io.BytesIO(data)) as im:
                    prepared = ImageOps.exif_transpose(im)
                    out = resize_image_to_long_edge(prepared, long_edge_px) if long_edge_px else prepared.convert("RGB")
                    out.save(dst, format="JPEG", quality=85, optimize=True)
            output_paths.append(dst)

    return output_paths


def extract_zip_pages_to_dir(zip_abs: str, thumb_dir_abs: str, long_edge_px: int | None = THUMBNAIL_LONG_EDGE_PX) -> list[str]:
    return extract_cbz_pages_to_dir(zip_abs, thumb_dir_abs, long_edge_px=long_edge_px)


def extract_archive_pages_to_dir(
    archive_abs: str,
    output_dir_abs: str,
    archive_kind: str | None = None,
    dpi: int = PDF_RENDER_DPI,
    long_edge_px: int | None = THUMBNAIL_LONG_EDGE_PX,
) -> list[str]:
    kind = (archive_kind or os.path.splitext(archive_abs)[1].lstrip(".")).lower()
    if kind == "pdf":
        return extract_pdf_pages_to_dir(archive_abs, output_dir_abs, dpi=dpi, long_edge_px=long_edge_px)
    if kind in {"cbz", "zip"}:
        return extract_zip_pages_to_dir(archive_abs, output_dir_abs, long_edge_px=long_edge_px)
    raise ValueError(f"Unsupported archive type: {kind}")


def write_structure_js(structure: dict, path: str = STRUCTURE_JS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("/**\n")
        out.write(" * Auto-generated from site/structure.json.\n")
        out.write(" * Do not edit manually.\n")
        out.write(" */\n\n")
        out.write("window.siteStructure = ")
        json.dump(structure, out, ensure_ascii=False, indent=2)
        out.write(";\n")