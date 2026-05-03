"""T04 series-level fingerprint planning and apply.

Commands:
- plan / dry-run: inspect changed series and reasons (non-destructive)
- apply: persist computed fingerprints to ``series.fingerprint`` safely

Connection helpers for existing diff inputs are included:
- output changed series paths to a text file
- append changed series paths to ``history.txt`` next.force_dirs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from .history_manager import parse_history, write_history
    from .maint_metrics import RunMetrics
except ImportError:
    from history_manager import parse_history, write_history
    from maint_metrics import RunMetrics


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "tools" / "sqlite" / "imviewer_maintenance.sqlite3"
DEFAULT_HISTORY_PATH = ROOT_DIR / "site" / "history.txt"
DEFAULT_TARGETS_PATH = ROOT_DIR / ".artifacts" / "M06" / "intermediate" / "t04-diff-targets.txt"


@dataclass
class SeriesPayload:
    series_id: int
    genre_key: str
    series_key: str
    entry_key: str
    name: str
    path: str
    note: str
    cover: str
    persons: list[str]
    labels: list[str]
    contents: list[dict]
    stored_fingerprint: str


@dataclass
class DiffPlan:
    db_path: Path
    db_exists: bool
    scanned_series: int
    changed_series: list[dict]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _norm_rel(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().strip("/")


def _matches_targets(series_path: str, targets: list[str]) -> bool:
    normalized = _norm_rel(series_path)
    if not targets:
        return True
    for raw in targets:
        target = _norm_rel(raw)
        if not target:
            continue
        if normalized == target or normalized.startswith(target + "/") or target.startswith(normalized + "/"):
            return True
    return False


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _default_backup_dir(db_path: Path) -> Path:
    return db_path.parent / "backup"


def _create_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{stamp}{db_path.suffix}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _load_series_payloads(db_path: Path, targets: list[str] | None = None) -> list[SeriesPayload]:
    if not db_path.is_file():
        return []

    target_paths = targets or []
    payloads: list[SeriesPayload] = []

    with closing(_connect_ro(db_path)) as conn:
        series_rows = conn.execute(
            """
SELECT s.id, g.genre_key, s.series_key, s.entry_key, s.name, s.path, s.note, s.cover, s.fingerprint
FROM series s
JOIN genres g ON g.id = s.genre_id
ORDER BY g.genre_key, s.series_key, s.id
"""
        ).fetchall()

        for series_id, genre_key, series_key, entry_key, name, path, note, cover, fingerprint in series_rows:
            path_str = str(path or "")
            if not _matches_targets(path_str, target_paths):
                continue

            content_rows = conn.execute(
                """
SELECT content_key, name, path, note, cover
FROM contents
WHERE series_id = ?
ORDER BY content_key, id
""",
                (series_id,),
            ).fetchall()

            persons = [
                str(row[0])
                for row in conn.execute(
                    """
SELECT DISTINCT p.display_name
FROM content_person_map m
JOIN persons p ON p.id = m.person_id
JOIN contents c ON c.id = m.content_id
WHERE c.series_id = ?
ORDER BY p.display_name
""",
                    (series_id,),
                ).fetchall()
            ]
            labels = [
                str(row[0])
                for row in conn.execute(
                    """
SELECT DISTINCT l.display_name
FROM content_label_map m
JOIN labels l ON l.id = m.label_id
JOIN contents c ON c.id = m.content_id
WHERE c.series_id = ?
ORDER BY l.display_name
""",
                    (series_id,),
                ).fetchall()
            ]

            contents = [
                {
                    "content_key": str(content_key or ""),
                    "name": str(content_name or ""),
                    "path": str(content_path or ""),
                    "note": str(content_note or ""),
                    "cover": str(content_cover or ""),
                }
                for content_key, content_name, content_path, content_note, content_cover in content_rows
            ]

            payloads.append(
                SeriesPayload(
                    series_id=int(series_id),
                    genre_key=str(genre_key or ""),
                    series_key=str(series_key or ""),
                    entry_key=str(entry_key or ""),
                    name=str(name or ""),
                    path=path_str,
                    note=str(note or ""),
                    cover=str(cover or ""),
                    persons=persons,
                    labels=labels,
                    contents=contents,
                    stored_fingerprint=str(fingerprint or ""),
                )
            )

    return payloads


def compute_series_fingerprint(series: SeriesPayload) -> str:
    canonical = {
        "genre_key": series.genre_key,
        "series_key": series.series_key,
        "entry_key": series.entry_key,
        "name": series.name,
        "path": series.path,
        "note": series.note,
        "cover": series.cover,
        "persons": sorted(series.persons, key=str.casefold),
        "labels": sorted(series.labels, key=str.casefold),
        "contents": series.contents,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_plan(db_path: Path, targets: list[str] | None = None) -> DiffPlan:
    payloads = _load_series_payloads(db_path, targets)
    changed: list[dict] = []

    for item in payloads:
        computed = compute_series_fingerprint(item)
        stored = item.stored_fingerprint.strip()

        if not stored:
            reason = "missing_fingerprint"
        elif stored != computed:
            reason = "fingerprint_changed"
        else:
            continue

        changed.append(
            {
                "genre": item.genre_key,
                "series": item.series_key,
                "entry_key": item.entry_key,
                "path": item.path,
                "reason": reason,
                "stored_fingerprint": stored,
                "computed_fingerprint": computed,
            }
        )

    return DiffPlan(
        db_path=db_path,
        db_exists=db_path.is_file(),
        scanned_series=len(payloads),
        changed_series=changed,
    )


def _changed_series_paths(plan: DiffPlan) -> list[str]:
    paths = {_norm_rel(item.get("path", "")) for item in plan.changed_series}
    return sorted((p for p in paths if p), key=str.casefold)


def write_targets_file(targets_path: Path, series_paths: list[str]) -> int:
    _ensure_parent(targets_path)
    text = "\n".join(series_paths)
    if text:
        text += "\n"
    targets_path.write_text(text, encoding="utf-8", newline="\n")
    return len(series_paths)


def merge_history_force_dirs(history_path: Path, series_paths: list[str]) -> int:
    data = parse_history(str(history_path))
    existing = {_norm_rel(p) for p in list(data.next_dirs) + list(data.next_force_dirs)}

    added = 0
    for path in series_paths:
        normalized = _norm_rel(path)
        if not normalized or normalized in existing:
            continue
        data.next_force_dirs.append(normalized)
        existing.add(normalized)
        added += 1

    if added > 0:
        write_history(str(history_path), data)
    return added


def apply_plan(
    db_path: Path,
    plan: DiffPlan,
    backup_dir: Path | None,
    no_backup: bool,
    rollback_restore_on_error: bool,
) -> dict:
    changed = plan.changed_series
    if not changed:
        return {"applied_count": 0, "backup_path": ""}

    _ensure_parent(db_path)
    backup_path: Path | None = None
    if db_path.is_file() and not no_backup:
        backup_path = _create_backup(db_path, backup_dir or _default_backup_dir(db_path))

    try:
        with closing(_connect_rw(db_path)) as conn:
            with conn:
                applied_count = 0
                for item in changed:
                    rc = conn.execute(
                        """
UPDATE series
SET fingerprint = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
WHERE path = ?
""",
                        (item["computed_fingerprint"], item["path"]),
                    ).rowcount
                    applied_count += int(rc)
    except Exception:
        if rollback_restore_on_error and backup_path is not None and backup_path.is_file():
            shutil.copy2(backup_path, db_path)
        raise

    return {
        "applied_count": applied_count,
        "backup_path": str(backup_path) if backup_path is not None else "",
    }


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T04 series diff planning from SQLite fingerprints")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "dry-run", "apply"):
        p = sub.add_parser(name, help="Show changed series and reasons without writing")
        p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
        p.add_argument("--diff", nargs="*", default=None, help="Only inspect matching series paths")
        p.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")
        p.add_argument(
            "--output-targets",
            default="",
            help="Optional output file path for changed series paths (one path per line)",
        )
        p.add_argument(
            "--write-history-targets",
            action="store_true",
            help="Merge changed series paths into history.txt next.force_dirs",
        )
        p.add_argument(
            "--history-path",
            default=str(DEFAULT_HISTORY_PATH),
            help="history.txt path used with --write-history-targets",
        )
    p_apply = sub.choices["apply"]
    p_apply.add_argument("--backup-dir", default="", help="Backup directory for DB before apply")
    p_apply.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    p_apply.add_argument(
        "--no-rollback-restore",
        action="store_true",
        help="On apply failure, do not restore DB file from backup copy",
    )
    return parser.parse_args(argv)


def _print_compare(metric_payload: dict) -> None:
    if metric_payload.get("compare"):
        compare = metric_payload["compare"]
        print(
            "Compare(previous): "
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )


def _run_plan_like(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    started = time.perf_counter()
    plan = build_plan(db_path=db_path, targets=args.diff)

    paths = _changed_series_paths(plan)
    output_targets_count = 0
    history_added_count = 0

    if args.output_targets:
        output_targets_count = write_targets_file(Path(args.output_targets), paths)
    if args.write_history_targets:
        history_added_count = merge_history_force_dirs(Path(args.history_path), paths)

    metrics = RunMetrics(
        pipeline="m06-t04-series-diff",
        mode="plan",
        log_path=args.metrics_log or None,
    )
    metrics.add_stage(
        name="series_diff_plan",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=plan.scanned_series,
        generated_count=len(plan.changed_series),
        transfer_files=int(bool(args.output_targets)) + int(bool(args.write_history_targets and history_added_count > 0)),
        transfer_bytes=0,
        details={
            "db": str(db_path),
            "command": args.command,
            "output_targets_count": output_targets_count,
            "history_added_count": history_added_count,
        },
    )
    metric_payload = metrics.finalize(success=True)

    output = {
        "db_path": str(plan.db_path),
        "db_exists": plan.db_exists,
        "scanned_series": plan.scanned_series,
        "changed_series_count": len(plan.changed_series),
        "changed_series": plan.changed_series,
        "changed_series_paths": paths,
        "will_write": False,
    }
    if args.output_targets:
        output["targets_file"] = str(Path(args.output_targets))
    if args.write_history_targets:
        output["history_path"] = str(Path(args.history_path))
        output["history_added_count"] = history_added_count

    _print_json(output)
    print(f"Metrics log: {metrics.log_path}")
    _print_compare(metric_payload)
    return 0


def _run_apply(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    backup_dir = Path(args.backup_dir) if args.backup_dir else None

    metrics = RunMetrics(
        pipeline="m06-t04-series-diff",
        mode="apply",
        log_path=args.metrics_log or None,
    )

    plan_started = time.perf_counter()
    plan = build_plan(db_path=db_path, targets=args.diff)
    paths = _changed_series_paths(plan)
    metrics.add_stage(
        name="assess_series_diff",
        status="ok",
        duration_ms=int((time.perf_counter() - plan_started) * 1000),
        scanned_count=plan.scanned_series,
        generated_count=len(plan.changed_series),
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path), "command": args.command},
    )

    output_targets_count = 0
    history_added_count = 0
    apply_result = {"applied_count": 0, "backup_path": ""}

    try:
        apply_started = time.perf_counter()
        apply_result = apply_plan(
            db_path=db_path,
            plan=plan,
            backup_dir=backup_dir,
            no_backup=bool(args.no_backup),
            rollback_restore_on_error=not bool(args.no_rollback_restore),
        )
        metrics.add_stage(
            name="apply_series_fingerprint",
            status="ok",
            duration_ms=int((time.perf_counter() - apply_started) * 1000),
            scanned_count=len(plan.changed_series),
            generated_count=apply_result["applied_count"],
            transfer_files=1 if apply_result["applied_count"] > 0 and db_path.is_file() else 0,
            transfer_bytes=db_path.stat().st_size if apply_result["applied_count"] > 0 and db_path.is_file() else 0,
            details={"backup_path": apply_result["backup_path"], "backup_skipped": bool(args.no_backup)},
        )

        connect_started = time.perf_counter()
        if args.output_targets:
            output_targets_count = write_targets_file(Path(args.output_targets), paths)
        if args.write_history_targets:
            history_added_count = merge_history_force_dirs(Path(args.history_path), paths)
        metrics.add_stage(
            name="connect_diff_targets",
            status="ok",
            duration_ms=int((time.perf_counter() - connect_started) * 1000),
            scanned_count=len(paths),
            generated_count=output_targets_count + history_added_count,
            transfer_files=int(bool(args.output_targets)) + int(bool(args.write_history_targets and history_added_count > 0)),
            transfer_bytes=0,
            details={
                "output_targets_count": output_targets_count,
                "history_added_count": history_added_count,
                "history_path": str(Path(args.history_path)),
            },
        )
    except Exception as exc:
        metrics.add_stage(
            name="apply_series_fingerprint",
            status="failed",
            duration_ms=0,
            scanned_count=len(plan.changed_series),
            generated_count=0,
            transfer_files=0,
            transfer_bytes=0,
            details={"error": str(exc)},
        )
        metrics.finalize(success=False)
        print(f"ERROR: apply failed: {exc}", file=sys.stderr)
        print(f"Metrics log: {metrics.log_path}")
        return 1

    metric_payload = metrics.finalize(success=True)
    post_plan = build_plan(db_path=db_path, targets=args.diff)
    _print_json(
        {
            "db_path": str(plan.db_path),
            "db_exists": plan.db_exists,
            "scanned_series_before": plan.scanned_series,
            "changed_series_count_before": len(plan.changed_series),
            "changed_series_paths": paths,
            "applied_count": apply_result["applied_count"],
            "backup_path": apply_result["backup_path"],
            "changed_series_count_after": len(post_plan.changed_series),
            "will_write": apply_result["applied_count"] > 0,
            "targets_file": str(Path(args.output_targets)) if args.output_targets else "",
            "history_path": str(Path(args.history_path)) if args.write_history_targets else "",
            "history_added_count": history_added_count,
        }
    )
    print(f"Metrics log: {metrics.log_path}")
    _print_compare(metric_payload)
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.command in ("plan", "dry-run"):
        return _run_plan_like(args)
    if args.command == "apply":
        return _run_apply(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
