"""Generate site/js/gallery-pages.js and gallery thumbnails."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from urllib.parse import unquote

from PIL import Image, ImageOps

try:
    from .history_manager import parse_history
    from .maint_structure_lib import (
        CONTENTS_DIR, DIRECT_IMAGE_EXTENSIONS,
        DIRECT_VIDEO_EXTENSIONS, SITE_DIR, STRUCTURE_JSON_PATH, THUMBNAIL_LONG_EDGE_PX,
        collect_gallery_file_paths_for_content, collect_gallery_html_paths_for_content,
        get_archive_content_dir_rel, get_cbz_content_dir_rel, get_pdf_content_dir_rel,
        iter_content_entries, load_structure, norm_rel, resize_image_to_long_edge,
    )
except ImportError:
    from history_manager import parse_history
    from maint_structure_lib import (
        CONTENTS_DIR, DIRECT_IMAGE_EXTENSIONS,
        DIRECT_VIDEO_EXTENSIONS, SITE_DIR, STRUCTURE_JSON_PATH, THUMBNAIL_LONG_EDGE_PX,
        collect_gallery_file_paths_for_content, collect_gallery_html_paths_for_content,
        get_archive_content_dir_rel, get_cbz_content_dir_rel, get_pdf_content_dir_rel,
        iter_content_entries, load_structure, norm_rel, resize_image_to_long_edge,
    )

JS_DIR = os.path.join(SITE_DIR, "js")
GALLERY_PAGES_PATH = os.path.join(JS_DIR, "gallery-pages.js")
HISTORY_PATH = os.path.join(SITE_DIR, "history.txt")

NEXT_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*<img[^>]*alt=["\']次へ["\']', re.IGNORECASE | re.DOTALL)
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif))["\']', re.IGNORECASE)
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif')
VIDEO_EXTENSIONS = ('.avi', '.mpg', '.mpeg', '.mp4', '.mkv', '.wmv', '.mov')


def resolve_rel(base_file_rel, target_rel):
    base_dir = os.path.dirname(base_file_rel)
    joined = os.path.normpath(os.path.join(base_dir, unquote(target_rel)))
    return norm_rel(joined)


def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def parse_page(page_rel, gallery_root_rel=None):
    page_abs = os.path.join(CONTENTS_DIR, page_rel)
    if not os.path.isfile(page_abs):
        return None, None

    text = read_text(page_abs)
    img_candidates = [m.group(1) for m in IMG_RE.finditer(text)]
    img_rel = None
    gallery_root_prefix = norm_rel(gallery_root_rel).rstrip('/') + '/' if gallery_root_rel else None

    for cand in img_candidates:
        if cand.lower().startswith('data:'):
            continue
        resolved = resolve_rel(page_rel, cand)
        if gallery_root_prefix and not resolved.startswith(gallery_root_prefix):
            continue
        if os.path.isfile(os.path.join(CONTENTS_DIR, resolved)):
            img_rel = resolved
            break

    if img_rel is None:
        for cand in img_candidates:
            if cand.lower().startswith('data:'):
                continue
            resolved = resolve_rel(page_rel, cand)
            if os.path.isfile(os.path.join(CONTENTS_DIR, resolved)):
                img_rel = resolved
                break

    next_rel = None
    match = NEXT_RE.search(text)
    if match:
        next_href = match.group(1)
        if next_href and next_href != '#':
            next_rel = resolve_rel(page_rel, next_href)

    return img_rel, next_rel


def gather_gallery_pages(start_rel):
    pages = []
    seen = set()
    current = norm_rel(start_rel)
    gallery_root_rel = os.path.dirname(current)

    for _ in range(2000):
        if current in seen:
            break
        seen.add(current)
        img_rel, next_rel = parse_page(current, gallery_root_rel)
        if img_rel:
            pages.append({
                'type': 'image',
                'image': f"contents/{img_rel}",
                'html': f"contents/{current}",
            })
        if not next_rel:
            break
        current = next_rel

    return pages


def gather_media_from_gallery_tree(start_rel):
    """Gather image/video pages starting from an HTML file anchor.

    Also accepts a directory path for galleries with no HTML entry point.
    """
    page_abs = os.path.join(CONTENTS_DIR, start_rel)
    is_dir = os.path.isdir(page_abs)
    if not is_dir and not os.path.isfile(page_abs):
        return []
    if not is_dir and os.path.splitext(start_rel)[1].lower() not in {".html", ".htm"}:
        return []

    gallery_root_abs = page_abs if os.path.isdir(page_abs) else os.path.dirname(page_abs)
    media_pages = []

    for root, dirs, files in os.walk(gallery_root_abs):
        dirs[:] = sorted(
            [d for d in dirs if not (d.lower() == 'thumbnail' and os.path.basename(root).lower() == 'src')],
            key=str.lower,
        )
        for name in sorted(files, key=str.lower):
            lower_name = name.lower()
            file_abs = os.path.join(root, name)
            file_rel = norm_rel(os.path.relpath(file_abs, CONTENTS_DIR))
            if lower_name.endswith(IMAGE_EXTENSIONS):
                media_pages.append({
                    'type': 'image',
                    'image': f"contents/{file_rel}",
                    'html': f"contents/{start_rel}",
                })
            elif lower_name.endswith(VIDEO_EXTENSIONS):
                media_pages.append({
                    'type': 'video',
                    'video': f"contents/{file_rel}",
                    'html': f"contents/{start_rel}",
                    'label': os.path.splitext(name)[0],
                    'ext': os.path.splitext(name)[1].lstrip('.').lower(),
                })

    video_index = 0
    pages = []
    for page in media_pages:
        if page.get('type') == 'video':
            video_index += 1
            page['thumbNumber'] = video_index
        pages.append(page)

    return pages


def dedupe_pages(pages):
    seen_media = set()
    unique = []
    for page in pages:
        media_key = page.get('image') or page.get('video') or page.get('html')
        if not media_key or media_key in seen_media:
            continue
        seen_media.add(media_key)
        unique.append(page)
    return unique


def media_uri_to_rel(uri):
    value = str(uri or '')
    if not value:
        return ''
    if value.startswith('thumbnail/'):
        return norm_rel(value[len('thumbnail/'):])
    if value.startswith('contents/'):
        return norm_rel(value[len('contents/'):])
    return norm_rel(value)


def media_uri_to_abs(uri):
    value = str(uri or '')
    if not value:
        return ''
    if value.startswith('thumbnail/'):
        return os.path.join(SITE_DIR, norm_rel(value))
    if value.startswith('contents/'):
        return os.path.join(CONTENTS_DIR, norm_rel(value[len('contents/'):]))
    return os.path.join(CONTENTS_DIR, norm_rel(value))


def _get_gallery_thumbnail_dir_rel(gallery_path):
    normalized = norm_rel(gallery_path).rstrip('/')
    ext = os.path.splitext(normalized)[1].lower()

    if ext in ('.pdf', '.cbz'):
        return None
    if ext in ('.html', '.htm'):
        return f'thumbnail/{os.path.dirname(normalized)}'
    return f'thumbnail/{normalized}'


def _get_gallery_media_base_uri(gallery_path):
    normalized = norm_rel(gallery_path).rstrip('/')
    ext = os.path.splitext(normalized)[1].lower()
    if ext in ('.html', '.htm'):
        normalized = os.path.dirname(normalized)
    return f'contents/{normalized}' if normalized else 'contents'


def _strip_base_prefix(value, base):
    normalized_value = norm_rel(value)
    normalized_base = norm_rel(base).rstrip('/')
    if not normalized_base:
        return normalized_value
    prefix = normalized_base + '/'
    if normalized_value.startswith(prefix):
        return normalized_value[len(prefix):]
    return normalized_value


def compact_gallery_pages(gallery_path, pages):
    media_base = _get_gallery_media_base_uri(gallery_path)
    thumb_base = _get_gallery_thumbnail_dir_rel(gallery_path)
    compact_pages = []

    for page in pages:
        page_type = page.get('type') or ('video' if page.get('video') else 'image')
        if page_type == 'video':
            item = [
                'v',
                _strip_base_prefix(page.get('video', ''), media_base),
                page.get('thumbNumber') or None,
                page.get('label') or '',
                (page.get('ext') or '').lower(),
            ]
        else:
            item = [
                'i',
                _strip_base_prefix(page.get('image', ''), media_base),
            ]
            thumbnail = page.get('thumbnail', '')
            if thumbnail:
                relative_thumb = _strip_base_prefix(thumbnail, thumb_base or media_base)
                if relative_thumb != item[1] or not thumb_base:
                    item.append(relative_thumb)

        while len(item) > 2 and item[-1] in ('', None):
            item.pop()
        compact_pages.append(item)

    compact = {'b': media_base, 'p': compact_pages, 's': build_gallery_signature(gallery_path, pages)}
    if thumb_base:
        compact['t'] = thumb_base
    return compact


def build_gallery_signature(gallery_path, pages):
    media_base = _get_gallery_media_base_uri(gallery_path)
    signature_items = []
    for page in pages:
        page_type = page.get('type') or ('video' if page.get('video') else 'image')
        raw_uri = page.get('video', '') if page_type == 'video' else page.get('image', '')
        rel_name = _strip_base_prefix(raw_uri, media_base)
        try:
            file_size = os.path.getsize(media_uri_to_abs(raw_uri))
        except OSError:
            file_size = -1
        prefix = 'v' if page_type == 'video' else 'i'
        signature_items.append([prefix, rel_name, file_size])
    payload = json.dumps(signature_items, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha1(payload).hexdigest()


def get_entry_signature(entry):
    if isinstance(entry, dict):
        value = entry.get('s')
        if isinstance(value, str) and value:
            return value
    return None


def detect_changed_gallery_paths(gallery_paths, existing_map):
    changed = []
    existing_map = existing_map if isinstance(existing_map, dict) else {}
    for gallery_path in gallery_paths:
        source_gallery_path = resolve_gallery_source_path(gallery_path)
        pages = collect_gallery_pages_for_path(source_gallery_path)
        current_signature = build_gallery_signature(source_gallery_path, pages)
        if current_signature != get_entry_signature(existing_map.get(gallery_path)):
            changed.append(gallery_path)
    return changed


def count_gallery_pages_entry(entry):
    if isinstance(entry, list):
        return len(entry)
    if isinstance(entry, dict):
        pages = entry.get('p')
        if isinstance(pages, list):
            return len(pages)
    return 0


def ensure_gallery_prebuilt_thumbnails(gallery_path, pages):
    thumb_dir_rel = _get_gallery_thumbnail_dir_rel(gallery_path)
    if not thumb_dir_rel:
        for page in pages:
            if page.get('type') == 'image' and page.get('image'):
                page['thumbnail'] = page.get('image')
        return 0, 0

    thumb_dir_rel = norm_rel(thumb_dir_rel)
    thumb_dir_abs = os.path.join(SITE_DIR, thumb_dir_rel)
    os.makedirs(thumb_dir_abs, exist_ok=True)
    generated = 0
    reused = 0
    thumb_index = 0

    for page in pages:
        if page.get('type') != 'image':
            continue
        src_abs = media_uri_to_abs(page.get('image'))
        if not src_abs:
            continue
        if not os.path.isfile(src_abs):
            continue

        thumb_index += 1
        thumb_name = f'{thumb_index:03d}.jpg'
        thumb_rel = norm_rel(os.path.join(thumb_dir_rel, thumb_name))
        thumb_abs = os.path.join(SITE_DIR, thumb_rel)
        cover_abs = os.path.join(SITE_DIR, norm_rel(os.path.join(thumb_dir_rel, 'cover.jpg')))
        needs_build = True
        if os.path.isfile(thumb_abs):
            try:
                needs_build = os.path.getmtime(thumb_abs) < os.path.getmtime(src_abs)
            except OSError:
                needs_build = True

        if needs_build:
            try:
                with Image.open(src_abs) as im:
                    prepared = ImageOps.exif_transpose(im)
                    thumb = resize_image_to_long_edge(prepared, THUMBNAIL_LONG_EDGE_PX)
                    thumb.save(thumb_abs, format='JPEG', quality=84, optimize=True)
                    if thumb_index == 1:
                        thumb.save(cover_abs, format='JPEG', quality=84, optimize=True)
                generated += 1
            except Exception:
                page['thumbnail'] = page.get('image')
                continue
        else:
            reused += 1
            if thumb_index == 1 and (not os.path.isfile(cover_abs) or os.path.getmtime(cover_abs) < os.path.getmtime(thumb_abs)):
                try:
                    with Image.open(thumb_abs) as im:
                        im.convert('RGB').save(cover_abs, format='JPEG', quality=84, optimize=True)
                except Exception:
                    pass

        page['thumbnail'] = thumb_rel

    return generated, reused


def assign_gallery_thumbnail_refs(gallery_path, pages, generate_files=False):
    if generate_files:
        return ensure_gallery_prebuilt_thumbnails(gallery_path, pages)

    thumb_dir_rel = _get_gallery_thumbnail_dir_rel(gallery_path)
    if not thumb_dir_rel:
        for page in pages:
            if page.get('type') == 'image' and page.get('image'):
                page['thumbnail'] = page.get('image')
        return 0, 0

    thumb_dir_rel = norm_rel(thumb_dir_rel)
    thumb_index = 0
    for page in pages:
        if page.get('type') != 'image' or not page.get('image'):
            continue
        thumb_index += 1
        page['thumbnail'] = norm_rel(os.path.join(thumb_dir_rel, f'{thumb_index:03d}.jpg'))
    return 0, 0


def resolve_gallery_source_path(gallery_path: str) -> str:
    """Return a concrete gallery source path.

    New flow stores extracted pages in directories (e.g. xxx_pdf/, xxx_cbz/).
    Keep legacy compatibility by mapping pdf/cbz paths to those directories if present.
    """
    normalized = norm_rel(gallery_path)
    ext = os.path.splitext(normalized)[1].lower()
    if ext in {'.pdf', '.cbz', '.zip', '.rar', '.7z'}:
        mapped = get_archive_content_dir_rel(normalized)
        return mapped if os.path.isdir(os.path.join(CONTENTS_DIR, mapped)) else normalized
    return normalized


def collect_gallery_pages_for_path(source_gallery_path: str) -> list[dict]:
    gallery_abs = os.path.join(CONTENTS_DIR, source_gallery_path)
    if os.path.isdir(gallery_abs):
        return dedupe_pages(gather_media_from_gallery_tree(source_gallery_path))

    pages_by_link = gather_gallery_pages(source_gallery_path)
    pages_by_scan = gather_media_from_gallery_tree(source_gallery_path)
    return dedupe_pages(pages_by_link + pages_by_scan)


def iter_gallery_paths(structure_obj):
    seen = set()
    for _genre_key, _genre_data, _series_key, _series_data, item in iter_content_entries(structure_obj):
        for gallery_path in collect_gallery_file_paths_for_content(item.get('path', '')):
            normalized = norm_rel(gallery_path)
            if normalized in seen:
                continue
            seen.add(normalized)
            yield normalized


def load_existing_gallery_pages_map(path):
    if not os.path.isfile(path):
        return None
    text = read_text(path)
    match = re.search(r'window\.galleryPagesMap\s*=\s*(\{.*\})\s*;', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_history_dir(path):
    normalized = norm_rel(str(path or '').strip())
    if normalized.startswith('contents/'):
        normalized = normalized[len('contents/'):]
    return normalized.rstrip('/')


def _is_same_or_child(path, parent):
    return path == parent or path.startswith(parent + '/')


def select_gallery_paths_for_diff(gallery_paths, target_dirs):
    targets = [
        _normalize_history_dir(item)
        for item in (target_dirs or [])
        if _normalize_history_dir(item)
    ]
    if not targets:
        return []
    selected = []
    for gallery_path in gallery_paths:
        gallery_root = norm_rel(os.path.dirname(gallery_path)).rstrip('/')
        for target in targets:
            if _is_same_or_child(gallery_root, target) or _is_same_or_child(target, gallery_root):
                selected.append(gallery_path)
                break
    return selected


def write_gallery_pages_js(result):
    text = render_gallery_pages_js(result)
    os.makedirs(JS_DIR, exist_ok=True)
    with open(GALLERY_PAGES_PATH, 'w', encoding='utf-8', newline='\n') as out:
        out.write(text)


def render_gallery_pages_js(result):
    lines = [
        '/**',
        ' * Auto-generated gallery pages map from site/structure.json.',
        ' * Do not edit manually.',
        ' */',
        'window.resolveGalleryPageEntries = window.resolveGalleryPageEntries || function resolveGalleryPageEntries(value, fallbackHtml) {',
        '  if (Array.isArray(value)) return value;',
        '  if (!value || !Array.isArray(value.p)) return [];',
        '  if (Array.isArray(value.__pages)) return value.__pages;',
        '  const normalize = (path) => String(path || "").replace(/\\\\/g, "/").replace(/^\\/+/, "");',
        '  const join = (base, path) => {',
        '    const normalizedPath = normalize(path);',
        '    if (!normalizedPath) return "";',
        '    if (normalizedPath.startsWith("contents/") || normalizedPath.startsWith("thumbnail/")) return normalizedPath;',
        '    const normalizedBase = normalize(base).replace(/\\/+$/, "");',
        '    return normalizedBase ? normalizedBase + "/" + normalizedPath : normalizedPath;',
        '  };',
        '  const stem = (path) => {',
        '    const normalizedPath = normalize(path);',
        '    const fileName = normalizedPath.split("/").pop() || normalizedPath;',
        '    return fileName.replace(/\\.[^.]+$/, "");',
        '  };',
        '  const ext = (path) => {',
        '    const match = /\\.([^.]+)$/.exec(String(path || ""));',
        '    return match ? match[1].toLowerCase() : "";',
        '  };',
        '  const base = value.b || "";',
        '  const thumbBase = value.t || "";',
        '  const html = join("", fallbackHtml || "");',
        '  value.__pages = value.p.map((item) => {',
        '    if (!Array.isArray(item) || item.length === 0) return null;',
        '    if (item[0] === "v") {',
        '      const video = join(base, item[1]);',
        '      return { type: "video", video, html, thumbNumber: Number(item[2]) > 0 ? Number(item[2]) : null, label: item[3] || stem(item[1] || video), ext: String(item[4] || ext(item[1] || video)).toLowerCase() };',
        '    }',
        '    const image = join(base, item[1]);',
        '    const thumbnail = item.length >= 3 && item[2] ? join(thumbBase || base, item[2]) : join(thumbBase || base, item[1]);',
        '    return { type: "image", image, thumbnail, html, label: stem(item[1] || image) };',
        '  }).filter(Boolean);',
        '  return value.__pages;',
        '};',
        'window.galleryPagesMap = ' + json.dumps(result, ensure_ascii=False, separators=(',', ':')) + ';',
        '',
    ]
    return '\n'.join(lines)


def build_gallery_pages_map(structure: dict, diff: bool = False, generate_thumbnails: bool = False) -> tuple[dict, dict]:
    all_gallery_paths = list(iter_gallery_paths(structure))
    target_gallery_paths = list(all_gallery_paths)
    result = {}
    metadata = {"incremental_mode": False, "generated": 0, "reused": 0, "skipped": False}

    if diff:
        history_data = parse_history(HISTORY_PATH)
        history_targets = list(history_data.next_dirs) + list(history_data.next_force_dirs)
        existing_map = load_existing_gallery_pages_map(GALLERY_PAGES_PATH)
        selected = select_gallery_paths_for_diff(all_gallery_paths, history_targets)
        if existing_map is not None:
            valid_galleries = set(all_gallery_paths)
            result = {key: value for key, value in existing_map.items() if key in valid_galleries}
            metadata["incremental_mode"] = True
            detected = detect_changed_gallery_paths(all_gallery_paths, result)
            target_gallery_paths = sorted(set(selected) | set(detected))
            if not target_gallery_paths:
                # T01-03: No diff targets after all checks. Skip generation loop and JS write.
                metadata["skipped"] = True
                metadata["gallery_count"] = len(result)
                metadata["page_count"] = sum(count_gallery_pages_entry(v) for v in result.values())
                return result, metadata
        else:
            target_gallery_paths = sorted(set(selected))

    thumb_generated = 0
    thumb_reused = 0
    for gallery_path in target_gallery_paths:
        source_gallery_path = resolve_gallery_source_path(gallery_path)
        pages = collect_gallery_pages_for_path(source_gallery_path)
        if not pages:
            result.pop(gallery_path, None)
            continue
        generated_count, reused_count = assign_gallery_thumbnail_refs(source_gallery_path, pages, generate_files=generate_thumbnails)
        thumb_generated += generated_count
        thumb_reused += reused_count
        result[gallery_path] = compact_gallery_pages(source_gallery_path, pages)

    metadata["generated"] = thumb_generated
    metadata["reused"] = thumb_reused
    metadata["gallery_count"] = len(result)
    metadata["page_count"] = sum(count_gallery_pages_entry(v) for v in result.values())
    return result, metadata


def verify_gallery_map_count(structure: dict, map_data: dict) -> tuple[bool, int, int]:
    """Verify that generated gallery map count matches iter_gallery_paths count."""
    expected_count = len(list(iter_gallery_paths(structure)))
    actual_count = len(map_data) if isinstance(map_data, dict) else 0
    return expected_count == actual_count, expected_count, actual_count


def generate_gallery_thumbnails(structure: dict, diff: bool = False) -> dict:
    all_gallery_paths = list(iter_gallery_paths(structure))
    target_gallery_paths = list(all_gallery_paths)
    metadata = {"incremental_mode": False, "generated": 0, "reused": 0, "skipped": False}

    if diff:
        history_data = parse_history(HISTORY_PATH)
        history_targets = list(history_data.next_dirs) + list(history_data.next_force_dirs)
        selected = select_gallery_paths_for_diff(all_gallery_paths, history_targets)
        target_gallery_paths = selected
        metadata["incremental_mode"] = True
        if not history_targets:
            # T01-03: No history targets → 0 diff targets. Skip heavy processing.
            metadata["skipped"] = True
            metadata["gallery_count"] = 0
            return metadata

    thumb_generated = 0
    thumb_reused = 0
    processed = 0
    for gallery_path in target_gallery_paths:
        source_gallery_path = resolve_gallery_source_path(gallery_path)
        pages = collect_gallery_pages_for_path(source_gallery_path)
        if not pages:
            continue
        generated_count, reused_count = assign_gallery_thumbnail_refs(source_gallery_path, pages, generate_files=True)
        thumb_generated += generated_count
        thumb_reused += reused_count
        processed += 1

    metadata["generated"] = thumb_generated
    metadata["reused"] = thumb_reused
    metadata["gallery_count"] = processed
    return metadata


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Generate gallery-pages.js from structure.json')
    parser.add_argument('--diff', action='store_true', help='Rebuild only galleries matching history.txt entries')
    parser.add_argument('--full', action='store_true', help='Force full rebuild')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    diff_mode = args.diff and not args.full
    structure = load_structure(STRUCTURE_JSON_PATH)
    result, metadata = build_gallery_pages_map(structure, diff=diff_mode, generate_thumbnails=False)
    if metadata.get("skipped"):
        print("No diff targets (history.txt empty). Skipped gallery-pages rebuild. Existing map kept.")
        print(f"Galleries: {metadata['gallery_count']}, pages: {metadata['page_count']}")
        return 0
    write_gallery_pages_js(result)
    print(f"Generated {GALLERY_PAGES_PATH}")
    print(f"Galleries: {metadata['gallery_count']}, pages: {metadata['page_count']}")
    print(f"Gallery thumbnails: generated={metadata['generated']}, reused={metadata['reused']}")
    ok, expected_count, actual_count = verify_gallery_map_count(structure, result)
    print(f"Verify gallery map count: expected={expected_count}, actual={actual_count}")
    if not ok:
        print("Error: gallery map count mismatch.")
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())