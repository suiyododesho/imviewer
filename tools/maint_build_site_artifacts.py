"""T05 site artifact generation from the SQLite maintenance database.

Commands:
- plan / dry-run: build the artifact plan without writing files
- apply: write structure and gallery-pages artifacts to the site directory

The tool keeps compatibility output (single gallery-pages.js) and can also emit
split gallery-pages chunks grouped by genre/series for future frontend loading.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:
    from . import maint_build_gallery_pages, maint_structure_lib
    from .maint_build_gallery_pages import build_gallery_pages_map, render_gallery_pages_js
    from .maint_db_transfer import DEFAULT_DB_PATH, export_structure_payload
    from .maint_metrics import RunMetrics
    from .maint_structure_lib import collect_gallery_file_paths_for_content, iter_series_entries, norm_rel
except ImportError:
    import maint_build_gallery_pages
    import maint_structure_lib
    from maint_build_gallery_pages import build_gallery_pages_map, render_gallery_pages_js
    from maint_db_transfer import DEFAULT_DB_PATH, export_structure_payload
    from maint_metrics import RunMetrics
    from maint_structure_lib import collect_gallery_file_paths_for_content, iter_series_entries, norm_rel


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SITE_DIR = ROOT_DIR / "site"


@dataclass(frozen=True)
class PlannedFile:
    path: Path
    text: str
    category: str

    @property
    def bytes(self) -> int:
        return len(self.text.encode("utf-8"))


@dataclass(frozen=True)
class ArtifactPlan:
    db_path: Path
    site_dir: Path
    gallery_output: str
    db_exists: bool
    counts: dict[str, int]
    gallery_count: int
    page_count: int
    split_series_count: int
    files: list[PlannedFile]
    split_existing_files: int


def _render_structure_json(structure: dict) -> str:
    return json.dumps(structure, ensure_ascii=False, indent=2) + "\n"


def _render_structure_js(structure: dict) -> str:
    return (
        "/**\n"
        " * Auto-generated from site/structure.json.\n"
        " * Do not edit manually.\n"
        " */\n\n"
        f"window.siteStructure = {json.dumps(structure, ensure_ascii=False, indent=2)};\n"
    )


def _render_assignment_js(comment: str, variable_name: str, payload: dict) -> str:
    return (
        "/**\n"
        f" * {comment}\n"
        " * Do not edit manually.\n"
        " */\n"
        f"{variable_name} = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )


def _chunk_rel_path(series_path: str) -> Path:
    normalized = norm_rel(series_path)
    if not normalized:
        return Path("js") / "gallery-pages" / "chunks" / "series.js"
    parts = [part for part in normalized.split("/") if part]
    return (Path("js") / "gallery-pages" / "chunks" / Path(*parts)).with_suffix(".js")


def _collect_series_gallery_map(structure: dict, gallery_map: dict) -> tuple[dict, dict]:
    chunks: dict[str, dict] = {}
    genres: dict[str, list[str]] = {}

    for genre_key, _genre_data, series_key, series_data in iter_series_entries(structure):
        series_path = norm_rel(series_data.get("path", ""))
        if not series_path:
            continue
        chunk_map: dict[str, dict] = {}
        seen_paths: set[str] = set()
        for item in series_data.get("contents", []):
            if not isinstance(item, dict):
                continue
            for gallery_path in collect_gallery_file_paths_for_content(item.get("path", "")):
                normalized_gallery_path = norm_rel(gallery_path)
                if not normalized_gallery_path or normalized_gallery_path in seen_paths:
                    continue
                seen_paths.add(normalized_gallery_path)
                if normalized_gallery_path in gallery_map:
                    chunk_map[normalized_gallery_path] = gallery_map[normalized_gallery_path]

        if not chunk_map:
            continue

        ordered_chunk = {
            key: chunk_map[key]
            for key in sorted(chunk_map, key=str.casefold)
        }
        chunks[series_path] = ordered_chunk
        genres.setdefault(str(genre_key), []).append(series_path)

    ordered_chunks = {
        key: chunks[key]
        for key in sorted(chunks, key=str.casefold)
    }
    ordered_genres = {
        key: sorted(value, key=str.casefold)
        for key, value in sorted(genres.items(), key=lambda item: item[0].casefold())
    }
    return ordered_chunks, ordered_genres


def _build_split_gallery_files(structure: dict, gallery_map: dict, site_dir: Path) -> tuple[list[PlannedFile], dict]:
    split_files: list[PlannedFile] = []
    chunks, genres = _collect_series_gallery_map(structure, gallery_map)

    manifest_series: dict[str, dict] = {}
    max_chunk_bytes = 0
    min_chunk_bytes = 0

    for series_path, chunk_payload in chunks.items():
        chunk_rel_path = _chunk_rel_path(series_path)
        chunk_text = _render_assignment_js(
            f"Auto-generated gallery-pages chunk for {series_path}.",
            f"window.galleryPagesChunks[{json.dumps(series_path, ensure_ascii=False)}]",
            chunk_payload,
        )
        planned = PlannedFile(
            path=site_dir / chunk_rel_path,
            text="window.galleryPagesChunks = window.galleryPagesChunks || {};\n" + chunk_text,
            category="gallery-pages-split-chunk",
        )
        split_files.append(planned)
        if max_chunk_bytes == 0 or planned.bytes > max_chunk_bytes:
            max_chunk_bytes = planned.bytes
        if min_chunk_bytes == 0 or planned.bytes < min_chunk_bytes:
            min_chunk_bytes = planned.bytes
        manifest_series[series_path] = {
            "genre": next((genre for genre, paths in genres.items() if series_path in paths), ""),
            "series": series_path,
            "series_key": next(
                (
                    str(series_key)
                    for genre_key, _genre_data, series_key, series_data in iter_series_entries(structure)
                    if norm_rel(series_data.get("path", "")) == series_path
                ),
                "",
            ),
            "entry_key": next(
                (
                    str(series_data.get("series", "") or series_key)
                    for genre_key, _genre_data, series_key, series_data in iter_series_entries(structure)
                    if norm_rel(series_data.get("path", "")) == series_path
                ),
                "",
            ),
            "chunk": chunk_rel_path.as_posix(),
            "gallery_count": len(chunk_payload),
            "page_count": sum(_count_gallery_pages_entry(value) for value in chunk_payload.values()),
            "bytes": planned.bytes,
        }

    manifest_payload = {
        "version": 1,
        "genres": genres,
        "series": manifest_series,
    }
    split_files.insert(
        0,
        PlannedFile(
            path=site_dir / "js" / "gallery-pages" / "manifest.js",
            text=_render_assignment_js(
                "Auto-generated gallery-pages split manifest.",
                "window.galleryPagesManifest",
                manifest_payload,
            ),
            category="gallery-pages-split-manifest",
        ),
    )

    summary = {
        "split_manifest_bytes": split_files[0].bytes if split_files else 0,
        "split_chunk_count": len(chunks),
        "max_split_chunk_bytes": max_chunk_bytes,
        "min_split_chunk_bytes": min_chunk_bytes,
    }
    return split_files, summary


def _count_gallery_pages_entry(entry: dict) -> int:
    pages = entry.get("p") if isinstance(entry, dict) else None
    return len(pages) if isinstance(pages, list) else 0


@contextmanager
def _override_site_paths(site_dir: Path):
    site_dir_str = str(site_dir)
    contents_dir_str = str(site_dir / "contents")
    thumbnail_dir_str = str(site_dir / "thumbnail")
    js_dir_str = str(site_dir / "js")
    structure_json_str = str(site_dir / "structure.json")
    structure_js_str = str(site_dir / "js" / "structure.js")
    gallery_pages_js_str = str(site_dir / "js" / "gallery-pages.js")
    history_str = str(site_dir / "history.txt")

    original = {
        "lib_site": maint_structure_lib.SITE_DIR,
        "lib_contents": maint_structure_lib.CONTENTS_DIR,
        "lib_thumbnail": maint_structure_lib.THUMBNAIL_DIR,
        "lib_structure_json": maint_structure_lib.STRUCTURE_JSON_PATH,
        "lib_structure_js": maint_structure_lib.STRUCTURE_JS_PATH,
        "gallery_site": maint_build_gallery_pages.SITE_DIR,
        "gallery_contents": maint_build_gallery_pages.CONTENTS_DIR,
        "gallery_js": maint_build_gallery_pages.JS_DIR,
        "gallery_pages": maint_build_gallery_pages.GALLERY_PAGES_PATH,
        "gallery_history": maint_build_gallery_pages.HISTORY_PATH,
    }

    maint_structure_lib.SITE_DIR = site_dir_str
    maint_structure_lib.CONTENTS_DIR = contents_dir_str
    maint_structure_lib.THUMBNAIL_DIR = thumbnail_dir_str
    maint_structure_lib.STRUCTURE_JSON_PATH = structure_json_str
    maint_structure_lib.STRUCTURE_JS_PATH = structure_js_str
    maint_build_gallery_pages.SITE_DIR = site_dir_str
    maint_build_gallery_pages.CONTENTS_DIR = contents_dir_str
    maint_build_gallery_pages.JS_DIR = js_dir_str
    maint_build_gallery_pages.GALLERY_PAGES_PATH = gallery_pages_js_str
    maint_build_gallery_pages.HISTORY_PATH = history_str

    try:
        yield
    finally:
        maint_structure_lib.SITE_DIR = original["lib_site"]
        maint_structure_lib.CONTENTS_DIR = original["lib_contents"]
        maint_structure_lib.THUMBNAIL_DIR = original["lib_thumbnail"]
        maint_structure_lib.STRUCTURE_JSON_PATH = original["lib_structure_json"]
        maint_structure_lib.STRUCTURE_JS_PATH = original["lib_structure_js"]
        maint_build_gallery_pages.SITE_DIR = original["gallery_site"]
        maint_build_gallery_pages.CONTENTS_DIR = original["gallery_contents"]
        maint_build_gallery_pages.JS_DIR = original["gallery_js"]
        maint_build_gallery_pages.GALLERY_PAGES_PATH = original["gallery_pages"]
        maint_build_gallery_pages.HISTORY_PATH = original["gallery_history"]


def build_plan(db_path: Path, site_dir: Path, gallery_output: str) -> ArtifactPlan:
    structure, counts = export_structure_payload(db_path)
    split_files: list[PlannedFile] = []

    with _override_site_paths(site_dir):
        gallery_map, metadata = build_gallery_pages_map(structure, diff=False, generate_thumbnails=False)
        if gallery_output in {"split", "both"}:
            split_files, _summary = _build_split_gallery_files(structure, gallery_map, site_dir)

    files = [
        PlannedFile(site_dir / "structure.json", _render_structure_json(structure), "structure-json"),
        PlannedFile(site_dir / "js" / "structure.js", _render_structure_js(structure), "structure-js"),
    ]
    if gallery_output in {"compat", "both"}:
        files.append(
            PlannedFile(
                site_dir / "js" / "gallery-pages.js",
                render_gallery_pages_js(gallery_map),
                "gallery-pages-compat",
            )
        )

    split_existing_files = 0
    if gallery_output in {"split", "both"}:
        files.extend(split_files)
        split_root = site_dir / "js" / "gallery-pages"
        if split_root.exists():
            split_existing_files = sum(1 for path in split_root.rglob("*.js") if path.is_file())

    split_series_count = sum(1 for item in files if item.category == "gallery-pages-split-chunk")
    return ArtifactPlan(
        db_path=db_path,
        site_dir=site_dir,
        gallery_output=gallery_output,
        db_exists=db_path.is_file(),
        counts=counts,
        gallery_count=int(metadata.get("gallery_count", 0)),
        page_count=int(metadata.get("page_count", 0)),
        split_series_count=split_series_count,
        files=files,
        split_existing_files=split_existing_files,
    )


def _size_summary(plan: ArtifactPlan) -> dict[str, int]:
    compat_bytes = next((item.bytes for item in plan.files if item.category == "gallery-pages-compat"), 0)
    split_manifest_bytes = next((item.bytes for item in plan.files if item.category == "gallery-pages-split-manifest"), 0)
    split_chunks = [item.bytes for item in plan.files if item.category == "gallery-pages-split-chunk"]
    return {
        "structure_json_bytes": next((item.bytes for item in plan.files if item.category == "structure-json"), 0),
        "structure_js_bytes": next((item.bytes for item in plan.files if item.category == "structure-js"), 0),
        "compat_gallery_pages_bytes": compat_bytes,
        "split_manifest_bytes": split_manifest_bytes,
        "split_chunk_count": len(split_chunks),
        "max_split_chunk_bytes": max(split_chunks, default=0),
        "min_split_chunk_bytes": min(split_chunks, default=0),
    }


def _plan_payload(plan: ArtifactPlan) -> dict:
    return {
        "db_path": str(plan.db_path),
        "site_dir": str(plan.site_dir),
        "db_exists": plan.db_exists,
        "gallery_output": plan.gallery_output,
        "counts": plan.counts,
        "gallery_count": plan.gallery_count,
        "page_count": plan.page_count,
        "split_series_count": plan.split_series_count,
        "split_existing_files": plan.split_existing_files,
        "size_summary": _size_summary(plan),
        "files": [
            {
                "path": file.path.relative_to(plan.site_dir).as_posix(),
                "bytes": file.bytes,
                "category": file.category,
            }
            for file in plan.files
        ],
        "will_write": True,
    }


def apply_plan(plan: ArtifactPlan) -> dict:
    written_files = 0
    written_bytes = 0

    if plan.gallery_output in {"split", "both"}:
        split_root = plan.site_dir / "js" / "gallery-pages"
        if split_root.exists():
            shutil.rmtree(split_root)

    for item in plan.files:
        item.path.parent.mkdir(parents=True, exist_ok=True)
        item.path.write_text(item.text, encoding="utf-8", newline="\n")
        written_files += 1
        written_bytes += item.path.stat().st_size

    return {
        "written_files": written_files,
        "written_bytes": written_bytes,
        "split_existing_files": plan.split_existing_files,
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T05 site artifact generation from SQLite")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "dry-run"):
        cmd = sub.add_parser(name, help="Show artifact generation plan without writing")
        cmd.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
        cmd.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR), help="Site directory for generated artifacts")
        cmd.add_argument(
            "--gallery-output",
            choices=("compat", "split", "both"),
            default="both",
            help="gallery-pages output mode",
        )
        cmd.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")

    apply_cmd = sub.add_parser("apply", help="Write site artifacts from SQLite")
    apply_cmd.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
    apply_cmd.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR), help="Site directory for generated artifacts")
    apply_cmd.add_argument(
        "--gallery-output",
        choices=("compat", "split", "both"),
        default="both",
        help="gallery-pages output mode",
    )
    apply_cmd.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")
    return parser.parse_args(argv)


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_plan(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    plan = build_plan(Path(args.db), Path(args.site_dir), args.gallery_output)

    metrics = RunMetrics(
        pipeline="m06-t05-site-artifacts",
        mode="plan",
        log_path=args.metrics_log or None,
    )
    metrics.add_stage(
        name="build_site_artifact_plan",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=plan.counts["series"] + plan.counts["contents"],
        generated_count=len(plan.files),
        transfer_files=0,
        transfer_bytes=0,
        details={
            "db": str(plan.db_path),
            "site_dir": str(plan.site_dir),
            "gallery_output": plan.gallery_output,
            "command": args.command,
        },
    )
    payload = metrics.finalize(success=True)

    _print_json(_plan_payload(plan))
    print(f"Metrics log: {metrics.log_path}")
    if payload.get("compare"):
        compare = payload["compare"]
        print(
            "Compare(previous): "
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )
    return 0


def _run_apply(args: argparse.Namespace) -> int:
    plan = build_plan(Path(args.db), Path(args.site_dir), args.gallery_output)
    metrics = RunMetrics(
        pipeline="m06-t05-site-artifacts",
        mode="apply",
        log_path=args.metrics_log or None,
    )

    started = time.perf_counter()
    result = apply_plan(plan)
    metrics.add_stage(
        name="apply_site_artifacts",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=plan.counts["series"] + plan.counts["contents"],
        generated_count=result["written_files"],
        transfer_files=result["written_files"],
        transfer_bytes=result["written_bytes"],
        details={
            "db": str(plan.db_path),
            "site_dir": str(plan.site_dir),
            "gallery_output": plan.gallery_output,
            "replaced_split_files": result["split_existing_files"],
        },
    )
    payload = metrics.finalize(success=True)

    output = _plan_payload(plan)
    output["written_files"] = result["written_files"]
    output["written_bytes"] = result["written_bytes"]
    _print_json(output)
    print(f"Metrics log: {metrics.log_path}")
    if payload.get("compare"):
        compare = payload["compare"]
        print(
            "Compare(previous): "
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.command in {"plan", "dry-run"}:
        return _run_plan(args)
    if args.command == "apply":
        return _run_apply(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())