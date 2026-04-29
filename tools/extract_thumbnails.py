from __future__ import annotations

import argparse
import base64
import re
import shutil
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urlparse


HTML_LINK_PATTERN = re.compile(
    r"(?:href\s*=\s*['\"]([^'\"]+\.(?:html?|HTML?))['\"]|"
    r"MM_openBrWindow\(\s*['\"]([^'\"]+\.(?:html?|HTML?))['\"])",
    re.IGNORECASE,
)
ANCHOR_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)>(?P<inner>.*?)</a>", re.IGNORECASE | re.DOTALL
)
IMG_PATTERN = re.compile(
    r"<img\b[^>]*src\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE | re.DOTALL
)
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
NUMBERED_TARGET_PATTERN = re.compile(r"\d+\.(?:html?|HTML?)$")
PROJECT_PATTERN = re.compile(r"(honey\d+)", re.IGNORECASE)


@dataclass
class PageResult:
    page_name: str
    person_name: str
    saved_count: int
    saved_names: list[str]


@dataclass
class RunResult:
    start_file: Path
    project_name: str
    linked_pages: int
    saved_files: list[Path]
    page_results: list[PageResult]
    skipped_pages: list[str]
    unresolved_start_links: list[str]


def sanitize_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "unknown"


def decode_data_url(src: str) -> tuple[bytes | None, str | None]:
    match = re.match(r"data:(image/[^;]+);base64,(.*)", src, re.IGNORECASE | re.DOTALL)
    if not match:
        return None, None

    mime = match.group(1).lower()
    payload = re.sub(r"\s+", "", match.group(2))
    data = base64.b64decode(payload)
    ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime, ".img")
    return data, ext


def read_text(path: Path, encoding: str) -> str:
    return path.read_text(encoding=encoding, errors="ignore")


def find_project_name(start_file: Path, override: str | None) -> str:
    if override:
        return sanitize_name(override)
    match = PROJECT_PATTERN.search(start_file.stem)
    if match:
        return match.group(1).lower()
    return sanitize_name(start_file.stem)


def resolve_start_link_target(start_dir: Path, target: str) -> Path | None:
    target = target.strip()
    if not target:
        return None

    candidates: list[Path] = []

    # Normal relative target.
    candidates.append((start_dir / target).resolve())

    # URL-like targets (//fs.xcity.jp/... or https://...).
    parsed = urlparse(target if re.match(r"^[a-z]+://", target, re.IGNORECASE) else f"https:{target}" if target.startswith("//") else target)
    path_only = parsed.path.strip()
    if path_only:
        parts = [p for p in path_only.split("/") if p]
        if parts:
            basename = Path(parts[-1]).name
            if basename:
                candidates.append((start_dir / basename).resolve())
        if len(parts) >= 2:
            parent = sanitize_name(parts[-2].lower())
            stem = Path(parts[-1]).stem.lower()
            mirrored = start_dir / f"aja_archives_free_juicyhoney_{parent}_{stem}.html"
            candidates.append(mirrored.resolve())

            # Some crawls drop numeric suffixes in mirrored filenames (ex: yuma2 -> yuma).
            parent_no_num = re.sub(r"\d+$", "", parent)
            if parent_no_num and parent_no_num != parent:
                candidates.append(
                    (start_dir / f"aja_archives_free_juicyhoney_{parent_no_num}_{stem}.html").resolve()
                )

            # Fallback: resolve by stem only if unique.
            by_stem = list(start_dir.glob(f"aja_archives_free_juicyhoney_*_{stem}.html"))
            if len(by_stem) == 1:
                candidates.append(by_stem[0].resolve())
            elif stem and re.search(r"\d$", stem):
                stem_no_num = re.sub(r"\d+$", "", stem)
                by_stem_no_num = list(
                    start_dir.glob(f"aja_archives_free_juicyhoney_*_{stem_no_num}.html")
                )
                if len(by_stem_no_num) == 1:
                    candidates.append(by_stem_no_num[0].resolve())

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.suffix.lower() not in {".html", ".htm"}:
            continue
        if candidate.exists():
            return candidate

    return None


def find_linked_pages(start_file: Path, start_text: str) -> tuple[list[Path], list[str]]:
    found: list[Path] = []
    seen: set[Path] = set()
    unresolved: list[str] = []

    for href_a, href_b in HTML_LINK_PATTERN.findall(start_text):
        target = unescape(href_a or href_b).strip()
        if not target:
            continue

        candidate = resolve_start_link_target(start_file.parent, target)
        if candidate is None:
            unresolved.append(target)
            continue

        name = candidate.name.lower()
        if name.startswith("index"):
            continue
        if candidate == start_file:
            continue
        if not candidate.exists():
            continue

        if candidate not in seen:
            seen.add(candidate)
            found.append(candidate)

    return found, unresolved


def extract_person_name(page: Path, text: str) -> str:
    title_match = TITLE_PATTERN.search(text)
    if title_match:
        return sanitize_name(unescape(title_match.group(1)).strip())
    return sanitize_name(page.stem)


def find_anchor_target(attrs: str) -> str | None:
    onclick_match = re.search(
        r"MM_openBrWindow\(\s*['\"]([^'\"]+)['\"]", attrs, re.IGNORECASE
    )
    onclick_target = unescape(onclick_match.group(1)).strip() if onclick_match else ""
    if onclick_target and Path(onclick_target).suffix.lower() in {".html", ".htm"}:
        return onclick_target

    href_match = re.search(r"href\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.IGNORECASE)
    href_target = unescape(href_match.group(1)).strip() if href_match else ""
    if href_target and Path(href_target).suffix.lower() in {".html", ".htm"}:
        return href_target

    return None


def next_available_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path

    stem = base_path.stem
    suffix = base_path.suffix
    dup = 1
    while True:
        candidate = base_path.with_name(f"{stem}_dup{dup:02d}{suffix}")
        if not candidate.exists():
            return candidate
        dup += 1


def extract_for_start_file(
    start_file: Path,
    output_dir: Path,
    project_name_override: str | None,
    encoding: str,
    dry_run: bool,
) -> RunResult:
    start_file = start_file.resolve()
    if not start_file.exists():
        raise FileNotFoundError(f"Start file not found: {start_file}")

    project_name = find_project_name(start_file, project_name_override)
    start_text = read_text(start_file, encoding)
    linked_pages, unresolved_start_links = find_linked_pages(start_file, start_text)

    saved_files: list[Path] = []
    skipped_pages: list[str] = []
    page_results: list[PageResult] = []

    for page in linked_pages:
        text = read_text(page, encoding)
        person_name = extract_person_name(page, text)

        sequence = 0
        page_saved_names: list[str] = []

        for anchor in ANCHOR_PATTERN.finditer(text):
            attrs = anchor.group("attrs") or ""
            inner = anchor.group("inner") or ""

            target = find_anchor_target(attrs)
            if not target:
                continue

            target_base = Path(target).name
            target_lower = target_base.lower()
            if target_lower.startswith("index"):
                continue
            if not NUMBERED_TARGET_PATTERN.search(target_base):
                continue

            img_match = IMG_PATTERN.search(inner)
            if not img_match:
                continue

            src = unescape(img_match.group(1)).strip()
            sequence += 1
            stem = sanitize_name(f"{project_name}_{person_name}_{sequence:03d}")

            if src.lower().startswith("data:image/"):
                data, ext = decode_data_url(src)
                if data is None or ext is None:
                    sequence -= 1
                    continue
                out_path = next_available_path(output_dir / f"{stem}{ext}")
                if not dry_run:
                    out_path.write_bytes(data)
            else:
                src_path = (page.parent / src).resolve()
                if not src_path.exists():
                    sequence -= 1
                    continue
                ext = src_path.suffix or ".img"
                out_path = next_available_path(output_dir / f"{stem}{ext}")
                if not dry_run:
                    shutil.copy2(src_path, out_path)

            saved_files.append(out_path)
            page_saved_names.append(out_path.name)

        if page_saved_names:
            page_results.append(
                PageResult(
                    page_name=page.name,
                    person_name=person_name,
                    saved_count=len(page_saved_names),
                    saved_names=page_saved_names,
                )
            )
        else:
            skipped_pages.append(page.name)

    return RunResult(
        start_file=start_file,
        project_name=project_name,
        linked_pages=len(linked_pages),
        saved_files=saved_files,
        page_results=page_results,
        skipped_pages=skipped_pages,
        unresolved_start_links=unresolved_start_links,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract thumbnail images from one or more start HTML files and "
            "save them under site/thumbnail-style filenames."
        )
    )
    parser.add_argument(
        "start_html_files",
        nargs="+",
        help="Start HTML files to process (one or more).",
    )
    parser.add_argument(
        "--output-dir",
        default="site/thumbnail",
        help="Directory to save extracted thumbnails. Default: site/thumbnail",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Optional project name override. Default: derive from start file name.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding used when reading HTML files. Default: utf-8",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run extraction logic without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    total_linked = 0
    total_saved = 0

    for start in args.start_html_files:
        start_path = Path(start)
        result = extract_for_start_file(
            start_file=start_path,
            output_dir=output_dir,
            project_name_override=args.project_name,
            encoding=args.encoding,
            dry_run=args.dry_run,
        )

        total_linked += result.linked_pages
        total_saved += len(result.saved_files)

        print(f"start={result.start_file}")
        print(f"project={result.project_name}")
        print(f"linked_pages={result.linked_pages}")
        print(f"saved={len(result.saved_files)}")
        print(f"output_dir={output_dir}")

        if result.page_results:
            print("pages:")
            for page_result in result.page_results:
                print(
                    f"- {page_result.page_name} | {page_result.person_name} | "
                    f"{page_result.saved_count}"
                )

        if result.skipped_pages:
            print(f"skipped_without_matches={len(result.skipped_pages)}")
            for name in result.skipped_pages:
                print(f"- {name}")

        if result.unresolved_start_links:
            print(f"unresolved_start_links={len(result.unresolved_start_links)}")
            for target in result.unresolved_start_links[:10]:
                print(f"- {target}")

        print("-")

    print(f"total_start_files={len(args.start_html_files)}")
    print(f"total_linked_pages={total_linked}")
    print(f"total_saved={total_saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
