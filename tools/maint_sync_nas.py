"""T06 NAS sync optimization: manifest-based differential file copy.

Commands:
- plan   : scan source vs dest, build manifest, display summary (no copy)
- dry-run: alias for plan (shows transfer plan without executing)
- apply  : execute copies listed in manifest (writes to dest)

Manifest tracks which files are new/changed between source and dest.
Change detection: size + SHA-1 hash comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

try:
    from .maint_metrics import RunMetrics, default_metrics_log_path
except ImportError:
    from maint_metrics import RunMetrics, default_metrics_log_path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = ROOT_DIR / "site"
DEFAULT_MANIFEST_PATH = ROOT_DIR / ".artifacts" / "M06" / "manifests" / "nas-sync.json"


# ---------------------------------------------------------------------------
# Hash / scan helpers
# ---------------------------------------------------------------------------

def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_dir(root: Path) -> dict[str, dict]:
    """Return {rel_path: {bytes, hash}} for all files under root."""
    result: dict[str, dict] = {}
    if not root.exists():
        return result
    for abs_path in root.rglob("*"):
        if not abs_path.is_file():
            continue
        rel = abs_path.relative_to(root).as_posix()
        size = abs_path.stat().st_size
        result[rel] = {"bytes": size, "hash": None}
    return result


def _fill_hashes(root: Path, entries: dict[str, dict]) -> None:
    for rel, info in entries.items():
        if info["hash"] is None:
            info["hash"] = _sha1(root / rel)


# ---------------------------------------------------------------------------
# Manifest dataclass
# ---------------------------------------------------------------------------

@dataclass
class ManifestEntry:
    rel_path: str
    action: Literal["copy"]
    src_bytes: int
    src_hash: str
    reason: Literal["new", "changed"]


@dataclass
class SyncManifest:
    run_id: str
    generated_at: str
    source_dir: str
    dest_dir: str
    scanned_source_count: int
    scanned_dest_count: int
    copy_count: int
    copy_bytes: int
    entries: list[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "entries"}
        d["entries"] = [asdict(e) for e in self.entries]
        return d

    @staticmethod
    def from_dict(d: dict) -> "SyncManifest":
        entries = [ManifestEntry(**e) for e in d.get("entries", [])]
        kwargs = {k: v for k, v in d.items() if k != "entries"}
        return SyncManifest(**kwargs, entries=entries)


# ---------------------------------------------------------------------------
# Core build plan
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def build_manifest(source_dir: Path, dest_dir: Path) -> SyncManifest:
    """Scan source and dest, return manifest of files to copy."""
    src_entries = _scan_dir(source_dir)
    dst_entries = _scan_dir(dest_dir)

    # Fill hashes only for potential candidates (all source files)
    _fill_hashes(source_dir, src_entries)

    entries: list[ManifestEntry] = []
    for rel, src_info in sorted(src_entries.items()):
        if rel not in dst_entries:
            reason: Literal["new", "changed"] = "new"
        else:
            dst_info = dst_entries[rel]
            # Fast path: same size → compute dest hash only if needed
            if dst_info["bytes"] == src_info["bytes"]:
                dst_hash = _sha1(dest_dir / rel)
                if dst_hash == src_info["hash"]:
                    continue  # identical — skip
            reason = "changed"
        entries.append(ManifestEntry(
            rel_path=rel,
            action="copy",
            src_bytes=src_info["bytes"],
            src_hash=src_info["hash"],
            reason=reason,
        ))

    copy_bytes = sum(e.src_bytes for e in entries)
    return SyncManifest(
        run_id=uuid.uuid4().hex,
        generated_at=_iso_now(),
        source_dir=str(source_dir),
        dest_dir=str(dest_dir),
        scanned_source_count=len(src_entries),
        scanned_dest_count=len(dst_entries),
        copy_count=len(entries),
        copy_bytes=copy_bytes,
        entries=entries,
    )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_manifest(manifest: SyncManifest) -> dict:
    """Copy files listed in the manifest from source to dest."""
    source_dir = Path(manifest.source_dir)
    dest_dir = Path(manifest.dest_dir)
    copied = 0
    copied_bytes = 0
    errors: list[str] = []

    for entry in manifest.entries:
        src = source_dir / entry.rel_path
        dst = dest_dir / entry.rel_path
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
            copied_bytes += entry.src_bytes
        except OSError as exc:
            errors.append(f"{entry.rel_path}: {exc}")

    return {
        "copied": copied,
        "copied_bytes": copied_bytes,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Pretty print helpers
# ---------------------------------------------------------------------------

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def print_plan(manifest: SyncManifest, verbose: bool = False) -> None:
    print(f"Source : {manifest.source_dir}")
    print(f"Dest   : {manifest.dest_dir}")
    print(f"Scanned: {manifest.scanned_source_count} source files, {manifest.scanned_dest_count} dest files")
    new_count = sum(1 for e in manifest.entries if e.reason == "new")
    changed_count = sum(1 for e in manifest.entries if e.reason == "changed")
    print(f"To copy: {manifest.copy_count} files ({new_count} new, {changed_count} changed) "
          f"= {_human_bytes(manifest.copy_bytes)}")
    if verbose and manifest.entries:
        print()
        max_path = max(len(e.rel_path) for e in manifest.entries)
        for e in manifest.entries:
            tag = "[NEW]     " if e.reason == "new" else "[CHANGED] "
            print(f"  {tag}{e.rel_path:<{max_path}}  {_human_bytes(e.src_bytes):>10}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T06 NAS sync: manifest-based differential copy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--source", default=str(DEFAULT_SOURCE_DIR),
                        help="Source directory (default: site/)")
    shared.add_argument("--dest", required=True,
                        help="Destination directory (NAS path)")
    shared.add_argument("--verbose", action="store_true",
                        help="List each planned file")
    shared.add_argument("--metrics-log", default=None,
                        help="JSONL metrics log path")
    shared.add_argument("--manifest-out", default=None,
                        help="Save generated manifest JSON to this path")

    for name in ("plan", "dry-run"):
        sub.add_parser(name, parents=[shared],
                       help="Show sync plan without copying")

    apply_p = sub.add_parser("apply", parents=[shared],
                              help="Execute file copy from manifest")
    apply_p.add_argument("--manifest-in", default=None,
                         help="Use an existing manifest JSON instead of rebuilding")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)

    source_dir = Path(args.source)
    dest_dir = Path(args.dest)
    metrics_log = args.metrics_log or default_metrics_log_path("t06-nas-sync")
    is_apply = args.command == "apply"

    if not source_dir.exists():
        print(f"[ERROR] Source dir not found: {source_dir}")
        return 1
    if is_apply and not dest_dir.exists():
        print(f"[ERROR] Dest dir not found for apply: {dest_dir}")
        return 1

    metrics = RunMetrics("t06-nas-sync", args.command, log_path=metrics_log)

    # ---- Build manifest ----
    manifest: SyncManifest
    if is_apply and getattr(args, "manifest_in", None):
        manifest_in_path = Path(args.manifest_in)
        with open(manifest_in_path, encoding="utf-8") as fh:
            manifest = SyncManifest.from_dict(json.load(fh))
        # Allow dest override in apply even when reusing manifest
        if str(dest_dir) != manifest.dest_dir:
            manifest.dest_dir = str(dest_dir)
        print(f"[manifest-in] Loaded {manifest.copy_count} entries from {manifest_in_path}")
    else:
        t0 = time.perf_counter()
        stage_token = metrics.begin_stage("scan", monitor_paths=[str(source_dir)],
                                          details={"dest_dir": str(dest_dir)})
        manifest = build_manifest(source_dir, dest_dir)
        metrics.end_stage(stage_token, status="ok", details={
            "copy_count": manifest.copy_count,
            "copy_bytes": manifest.copy_bytes,
            "new_count": sum(1 for e in manifest.entries if e.reason == "new"),
            "changed_count": sum(1 for e in manifest.entries if e.reason == "changed"),
        })

    # ---- Save manifest if requested ----
    manifest_out = getattr(args, "manifest_out", None)
    if manifest_out:
        manifest_out_path = Path(manifest_out)
        manifest_out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_out_path, "w", encoding="utf-8") as fh:
            json.dump(manifest.to_dict(), fh, ensure_ascii=False, indent=2)
        print(f"Manifest saved: {manifest_out_path}")

    # ---- Display plan ----
    print_plan(manifest, verbose=getattr(args, "verbose", False))

    if not is_apply:
        print("\n[dry-run] No files copied. Use 'apply' to execute.")
        metrics.finalize(True)
        return 0

    if manifest.copy_count == 0:
        print("\nNothing to copy. Dest is up to date.")
        metrics.finalize(True)
        return 0

    # ---- Apply ----
    print(f"\nCopying {manifest.copy_count} files to {dest_dir} ...")
    copy_token = metrics.begin_stage("copy", monitor_paths=[str(dest_dir)],
                                     details={"copy_count": manifest.copy_count})
    result = apply_manifest(manifest)
    metrics.end_stage(copy_token, status="ok" if not result["errors"] else "partial",
                      details={
                          "copied": result["copied"],
                          "copied_bytes": result["copied_bytes"],
                          "error_count": len(result["errors"]),
                      })

    print(f"Copied : {result['copied']} files ({_human_bytes(result['copied_bytes'])})")
    if result["errors"]:
        print(f"Errors : {len(result['errors'])}")
        for err in result["errors"]:
            print(f"  [ERROR] {err}")

    success = not result["errors"]
    metrics.finalize(success)
    print(f"Metrics log: {metrics_log}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
