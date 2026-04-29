"""Generate site/js/gallery-pages.js and gallery thumbnails."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.parse import unquote

from PIL import Image, ImageOps

try:
    from .history_manager import parse_history
    from .maint_structure_lib import (
        ARCHIVE_CONTENT_EXTENSIONS, CONTENTS_DIR, DIRECT_IMAGE_EXTENSIONS,
        DIRECT_VIDEO_EXTENSIONS, SITE_DIR, STRUCTURE_JSON_PATH, THUMBNAIL_LONG_EDGE_PX,
        collect_gallery_file_paths_for_content, collect_gallery_html_paths_for_content,
        extract_cbz_pages_to_dir, extract_pdf_pages_to_dir,
        get_cbz_thumb_dir_rel, get_pdf_thumb_dir_rel,
        iter_content_entries, load_structure, norm_rel, resize_image_to_long_edge,
    )
except ImportError:
    from history_manager import parse_history
    from maint_structure_lib import (
        ARCHIVE_CONTENT_EXTENSIONS, CONTENTS_DIR, DIRECT_IMAGE_EXTENSIONS,
        DIRECT_VIDEO_EXTENSIONS, SITE_DIR, STRUCTURE_JSON_PATH, THUMBNAIL_LONG_EDGE_PX,
        collect_gallery_file_paths_for_content, collect_gallery_html_paths_for_content,
        extract_cbz_pages_to_dir, extract_pdf_pages_to_dir,
        get_cbz_thumb_dir_rel, get_pdf_thumb_dir_rel,
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
    image_pages = []
    video_pages = []
    video_index = 0

    for root, dirs, files in os.walk(gallery_root_abs):
        dirs[:] = sorted(
            [d for d in dirs if not (d.lower() == 'thumbnail' and os.path.basename(root).lower() == 'src')],
            key=str.lower,
        )
        for name in files:
            lower_name = name.lower()
            file_abs = os.path.join(root, name)
            file_rel = norm_rel(os.path.relpath(file_abs, CONTENTS_DIR))
            if lower_name.endswith(IMAGE_EXTENSIONS):
                image_pages.append({
                    'type': 'image',
                    'image': f"contents/{file_rel}",
                    'html': f"contents/{start_rel}",
                })
            elif lower_name.endswith(VIDEO_EXTENSIONS):
                video_index += 1
                video_pages.append({
                    'type': 'video',
                    'video': f"contents/{file_rel}",
                    'html': f"contents/{start_rel}",
                    'thumbNumber': video_index,
                    'label': os.path.splitext(name)[0],
                    'ext': os.path.splitext(name)[1].lstrip('.').lower(),
                })
    return image_pages + video_pages


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


def gather_pages_from_pdf(pdf_content_rel: str) -> list[dict]:
    """Extract all pages of a PDF file as images and return page entries."""
    pdf_abs = os.path.join(CONTENTS_DIR, norm_rel(pdf_content_rel))
    if not os.path.isfile(pdf_abs):
        return []
    thumb_dir_rel = get_pdf_thumb_dir_rel(pdf_content_rel)
    thumb_dir_abs = os.path.join(SITE_DIR, thumb_dir_rel)
    try:
        page_paths = extract_pdf_pages_to_dir(pdf_abs, thumb_dir_abs)
    except Exception as exc:
        print(f"  [PDF error] {pdf_content_rel}: {exc}")
        return []
    pages = []
    for abs_path in page_paths:
        img_rel = norm_rel(os.path.relpath(abs_path, SITE_DIR))
        pages.append({
            'type': 'image',
            'image': img_rel,
            'html': f'contents/{norm_rel(pdf_content_rel)}',
        })
    return pages


def gather_pages_from_cbz(cbz_content_rel: str) -> list[dict]:
    """Extract all images from a CBZ archive and return page entries."""
    cbz_abs = os.path.join(CONTENTS_DIR, norm_rel(cbz_content_rel))
    if not os.path.isfile(cbz_abs):
        return []
    thumb_dir_rel = get_cbz_thumb_dir_rel(cbz_content_rel)
    thumb_dir_abs = os.path.join(SITE_DIR, thumb_dir_rel)
    try:
        page_paths = extract_cbz_pages_to_dir(cbz_abs, thumb_dir_abs)
    except Exception as exc:
        print(f"  [CBZ error] {cbz_content_rel}: {exc}")
        return []
    pages = []
    for abs_path in page_paths:
        img_rel = norm_rel(os.path.relpath(abs_path, SITE_DIR))
        pages.append({
            'type': 'image',
            'image': img_rel,
            'html': f'contents/{norm_rel(cbz_content_rel)}',
        })
    return pages


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
    os.makedirs(JS_DIR, exist_ok=True)
    with open(GALLERY_PAGES_PATH, 'w', encoding='utf-8', newline='\n') as out:
        out.write('/**\n')
        out.write(' * Auto-generated gallery pages map from site/structure.json.\n')
        out.write(' * Do not edit manually.\n')
        out.write(' */\n')
        out.write('window.galleryPagesMap = ')
        json.dump(result, out, ensure_ascii=False, separators=(',', ':'))
        out.write(';\n')


def build_gallery_pages_map(structure: dict, diff: bool = False) -> tuple[dict, dict]:
    all_gallery_paths = list(iter_gallery_paths(structure))
    target_gallery_paths = list(all_gallery_paths)
    result = {}
    metadata = {"incremental_mode": False, "generated": 0, "reused": 0}

    if diff:
        history_data = parse_history(HISTORY_PATH)
        history_targets = list(history_data.next_dirs) + list(history_data.next_force_dirs)
        existing_map = load_existing_gallery_pages_map(GALLERY_PAGES_PATH)
        selected = select_gallery_paths_for_diff(all_gallery_paths, history_targets)
        if existing_map is not None:
            valid_galleries = set(all_gallery_paths)
            result = {key: value for key, value in existing_map.items() if key in valid_galleries}
            metadata["incremental_mode"] = True
            target_gallery_paths = selected

    thumb_generated = 0
    thumb_reused = 0
    for gallery_path in target_gallery_paths:
        ext = os.path.splitext(gallery_path)[1].lower()
        gallery_abs = os.path.join(CONTENTS_DIR, gallery_path)
        if ext == '.pdf':
            pages = gather_pages_from_pdf(gallery_path)
            # PDF pages are already at display resolution; generate gallery thumbnails
            generated_count, reused_count = ensure_gallery_prebuilt_thumbnails(gallery_path, pages)
            thumb_generated += generated_count
            thumb_reused += reused_count
        elif ext == '.cbz':
            pages = gather_pages_from_cbz(gallery_path)
            generated_count, reused_count = ensure_gallery_prebuilt_thumbnails(gallery_path, pages)
            thumb_generated += generated_count
            thumb_reused += reused_count
        elif os.path.isdir(gallery_abs):
            pages = gather_media_from_gallery_tree(gallery_path)
            pages = dedupe_pages(pages)
            generated_count, reused_count = ensure_gallery_prebuilt_thumbnails(gallery_path, pages)
            thumb_generated += generated_count
            thumb_reused += reused_count
        else:
            pages_by_link = gather_gallery_pages(gallery_path)
            pages_by_scan = gather_media_from_gallery_tree(gallery_path)
            pages = dedupe_pages(pages_by_link + pages_by_scan)
            generated_count, reused_count = ensure_gallery_prebuilt_thumbnails(gallery_path, pages)
            thumb_generated += generated_count
            thumb_reused += reused_count
        if not pages:
            continue
        result[gallery_path] = pages

    metadata["generated"] = thumb_generated
    metadata["reused"] = thumb_reused
    metadata["gallery_count"] = len(result)
    metadata["page_count"] = sum(len(v) for v in result.values())
    return result, metadata


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Generate gallery-pages.js from structure.json')
    parser.add_argument('--diff', action='store_true', help='Rebuild only galleries matching history.txt entries')
    parser.add_argument('--full', action='store_true', help='Force full rebuild')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    diff_mode = args.diff and not args.full
    structure = load_structure(STRUCTURE_JSON_PATH)
    result, metadata = build_gallery_pages_map(structure, diff=diff_mode)
    write_gallery_pages_js(result)
    print(f"Generated {GALLERY_PAGES_PATH}")
    print(f"Galleries: {metadata['gallery_count']}, pages: {metadata['page_count']}")
    print(f"Gallery thumbnails: generated={metadata['generated']}, reused={metadata['reused']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())