"""Initialize and migrate the M06 SQLite maintenance database schema.

This tool is intentionally split into non-destructive planning and explicit apply:

- ``plan`` / ``dry-run``: show what would change, do not write files
- ``apply``: execute schema initialization or migration

Migration policy:
- Schema changes are versioned in ``schema_migrations``.
- New migrations are append-only and applied in ascending version order.
- Existing DB files are backed up before schema updates.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from .maint_metrics import RunMetrics
except ImportError:
    from maint_metrics import RunMetrics


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "tools" / "sqlite" / "imviewer_maintenance.sqlite3"


SCHEMA_TABLES: tuple[str, ...] = (
    "genres",
    "series",
    "contents",
    "gallery_pages",
    "persons",
    "labels",
    "content_person_map",
    "content_label_map",
    "jobs",
    "snapshots",
)


MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (
        1,
        "t02_initial_schema",
        """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY,
    genre_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY,
    genre_id INTEGER NOT NULL,
    series_key TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    cover TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (genre_id, series_key),
    UNIQUE (path),
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contents (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL,
    content_key TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    cover TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (series_id, content_key),
    UNIQUE (path),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gallery_pages (
    id INTEGER PRIMARY KEY,
    content_id INTEGER NOT NULL,
    page_no INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    file_mtime_ns INTEGER NOT NULL DEFAULT 0,
    fingerprint TEXT NOT NULL DEFAULT '',
    UNIQUE (content_id, page_no),
    UNIQUE (relative_path),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY,
    person_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY,
    label_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS content_person_map (
    content_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (content_id, person_id, role),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS content_label_map (
    content_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL,
    PRIMARY KEY (content_id, label_id),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    started_at TEXT,
    ended_at TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_type TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (snapshot_type, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_series_fingerprint ON series(fingerprint);
CREATE INDEX IF NOT EXISTS idx_series_name ON series(name);
CREATE INDEX IF NOT EXISTS idx_contents_series_id ON contents(series_id);
CREATE INDEX IF NOT EXISTS idx_contents_fingerprint ON contents(fingerprint);
CREATE INDEX IF NOT EXISTS idx_contents_name ON contents(name);
CREATE INDEX IF NOT EXISTS idx_gallery_pages_content_id ON gallery_pages(content_id);
CREATE INDEX IF NOT EXISTS idx_gallery_pages_fingerprint ON gallery_pages(fingerprint);
CREATE INDEX IF NOT EXISTS idx_content_person_map_person_id ON content_person_map(person_id, content_id);
CREATE INDEX IF NOT EXISTS idx_content_label_map_label_id ON content_label_map(label_id, content_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_requested_at ON jobs(status, requested_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_persons_display_name ON persons(display_name);
CREATE INDEX IF NOT EXISTS idx_labels_display_name ON labels(display_name);
""",
    ),
    (
        2,
        "t03_series_entry_key",
        """
ALTER TABLE series ADD COLUMN entry_key TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_series_entry_key ON series(entry_key);
""",
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _connect_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _existing_tables(db_path: Path) -> list[str]:
    if not db_path.is_file():
        return []
    with closing(_connect_ro(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return [str(row[0]) for row in rows]


def _current_schema_version(conn: sqlite3.Connection) -> int:
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not has_table:
        return 0
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0] if row else 0)


def _pending_migrations(current_version: int) -> list[tuple[int, str, str]]:
    return [m for m in MIGRATIONS if m[0] > current_version]


def _default_backup_dir(db_path: Path) -> Path:
    return db_path.parent / "backup"


def _create_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{stamp}{db_path.suffix}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


@dataclass
class PlanResult:
    db_path: Path
    db_exists: bool
    current_version: int
    pending_versions: list[int]
    existing_tables: list[str]
    will_write: bool
    requires_backup: bool


def build_plan(db_path: Path) -> PlanResult:
    db_exists = db_path.is_file()
    existing_tables: list[str] = []
    current_version = 0

    if db_exists:
        existing_tables = _existing_tables(db_path)
        with closing(_connect_ro(db_path)) as conn:
            current_version = _current_schema_version(conn)

    pending = _pending_migrations(current_version)
    pending_versions = [m[0] for m in pending]
    will_write = (not db_exists) or bool(pending)
    requires_backup = db_exists and will_write

    return PlanResult(
        db_path=db_path,
        db_exists=db_exists,
        current_version=current_version,
        pending_versions=pending_versions,
        existing_tables=existing_tables,
        will_write=will_write,
        requires_backup=requires_backup,
    )


def apply_plan(db_path: Path, backup_dir: Path | None, no_backup: bool) -> dict:
    plan = build_plan(db_path)
    if not plan.will_write:
        return {
            "applied_versions": [],
            "backup_path": "",
            "plan": plan,
        }

    _ensure_parent(db_path)
    backup_path: Path | None = None
    if plan.requires_backup and not no_backup:
        use_backup_dir = backup_dir or _default_backup_dir(db_path)
        backup_path = _create_backup(db_path, use_backup_dir)

    with closing(_connect_rw(db_path)) as conn:
        current_version = _current_schema_version(conn)
        pending = _pending_migrations(current_version)

        applied_versions: list[int] = []
        if pending:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )
                    """
                )

                for version, description, sql_script in pending:
                    conn.executescript(sql_script)
                    conn.execute(
                        "INSERT OR REPLACE INTO schema_migrations(version, description, applied_at) VALUES (?, ?, ?)",
                        (version, description, _utc_now_iso()),
                    )
                    applied_versions.append(version)

    return {
        "applied_versions": applied_versions,
        "backup_path": str(backup_path) if backup_path is not None else "",
        "plan": plan,
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize and migrate M06 SQLite schema")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "dry-run"):
        p = sub.add_parser(name, help="Show schema init/migration plan without writing")
        p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
        p.add_argument("--metrics-log", default="", help="Optional JSONL output path for metrics")

    p_apply = sub.add_parser("apply", help="Apply schema initialization/migrations")
    p_apply.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
    p_apply.add_argument("--backup-dir", default="", help="Backup directory for existing DB")
    p_apply.add_argument("--no-backup", action="store_true", help="Skip backup creation before update")
    p_apply.add_argument("--metrics-log", default="", help="Optional JSONL output path for metrics")
    return parser.parse_args(argv)


def _print_plan(plan: PlanResult) -> None:
    payload = {
        "db_path": str(plan.db_path),
        "db_exists": plan.db_exists,
        "current_version": plan.current_version,
        "pending_versions": plan.pending_versions,
        "existing_tables": plan.existing_tables,
        "will_write": plan.will_write,
        "requires_backup": plan.requires_backup,
    }
    print("Migration policy: append-only versions in schema_migrations, ascending apply order")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_plan(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    started = time.perf_counter()
    plan = build_plan(db_path)

    metrics = RunMetrics(
        pipeline="m06-t02-sqlite-schema",
        mode="plan",
        log_path=args.metrics_log or None,
    )
    metrics.add_stage(
        name="plan_schema",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=len(plan.existing_tables),
        generated_count=len(plan.pending_versions),
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path), "command": args.command},
    )
    payload = metrics.finalize(success=True)

    _print_plan(plan)
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
    db_path = Path(args.db)
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    metrics = RunMetrics(
        pipeline="m06-t02-sqlite-schema",
        mode="apply",
        log_path=args.metrics_log or None,
    )

    plan_started = time.perf_counter()
    plan = build_plan(db_path)
    metrics.add_stage(
        name="assess_schema",
        status="ok",
        duration_ms=int((time.perf_counter() - plan_started) * 1000),
        scanned_count=len(plan.existing_tables),
        generated_count=len(plan.pending_versions),
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path)},
    )

    apply_started = time.perf_counter()
    result = apply_plan(db_path, backup_dir=backup_dir, no_backup=args.no_backup)

    transfer_files = 0
    transfer_bytes = 0
    if db_path.is_file():
        transfer_files += 1
        transfer_bytes += db_path.stat().st_size

    backup_path = result.get("backup_path") or ""
    if backup_path and Path(backup_path).is_file():
        transfer_files += 1
        transfer_bytes += Path(backup_path).stat().st_size

    metrics.add_stage(
        name="apply_schema",
        status="ok",
        duration_ms=int((time.perf_counter() - apply_started) * 1000),
        scanned_count=len(plan.existing_tables),
        generated_count=len(result.get("applied_versions") or []),
        transfer_files=transfer_files,
        transfer_bytes=transfer_bytes,
        details={
            "db": str(db_path),
            "applied_versions": result.get("applied_versions") or [],
            "backup_path": backup_path,
            "backup_skipped": bool(args.no_backup),
        },
    )

    payload = metrics.finalize(success=True)
    _print_plan(build_plan(db_path))
    print(f"Applied versions: {result.get('applied_versions') or []}")
    if backup_path:
        print(f"Backup created: {backup_path}")
    else:
        print("Backup created: (none)")
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
    if args.command in ("plan", "dry-run"):
        return _run_plan(args)
    if args.command == "apply":
        return _run_apply(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())