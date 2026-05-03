"""T03 data transfer between structure.json and the M06 SQLite database.

Commands are split into explicit phases:
- import-plan / import-dry-run / import-apply
- export-plan / export-dry-run / export-apply

`plan` and `dry-run` do not write files.
`apply` performs the operation and records metrics.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from .maint_metrics import RunMetrics
    from .maint_structure_lib import get_genres_map, get_series_entries_map
except ImportError:
    from maint_metrics import RunMetrics
    from maint_structure_lib import get_genres_map, get_series_entries_map


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "tools" / "sqlite" / "imviewer_maintenance.sqlite3"
DEFAULT_STRUCTURE_PATH = ROOT_DIR / "site" / "structure.json"
DEFAULT_EXPORT_PATH = ROOT_DIR / ".artifacts" / "M06" / "intermediate" / "structure_from_sqlite.json"


@dataclass
class ImportPlan:
    db_path: Path
    structure_path: Path
    db_exists: bool
    target_counts: dict[str, int]
    existing_counts: dict[str, int]
    entries_without_contents: int


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


def _load_structure(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_db_counts(db_path: Path) -> dict[str, int]:
    counts = {
        "genres": 0,
        "series": 0,
        "contents": 0,
        "persons": 0,
        "labels": 0,
        "content_person_map": 0,
        "content_label_map": 0,
    }
    if not db_path.is_file():
        return counts

    with closing(_connect_ro(db_path)) as conn:
        for table in counts:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0] if row else 0)
    return counts


def _build_import_payload(structure: dict) -> tuple[list[dict], dict[str, int], int]:
    rows: list[dict] = []
    all_persons: set[str] = set()
    all_labels: set[str] = set()
    content_person_rows = 0
    content_label_rows = 0
    entries_without_contents = 0

    for genre_key, genre_data in get_genres_map(structure).items():
        if not isinstance(genre_data, dict):
            continue

        genre_name = str(genre_data.get("name", "")).strip() or genre_key
        genre_path = str(genre_data.get("path", "")).strip() or genre_key

        for entry_key, entry_data in get_series_entries_map(genre_data).items():
            if not isinstance(entry_data, dict):
                continue

            series_key = str(entry_data.get("series", "")).strip() or str(entry_key)
            orig_entry_key = str(entry_key)
            series_name = str(entry_data.get("name", "")).strip() or str(entry_key)
            series_path = str(entry_data.get("path", "")).strip()
            series_note = str(entry_data.get("note", "")).strip()
            persons = [str(v).strip() for v in (entry_data.get("persons") or []) if str(v).strip()]
            labels = [str(v).strip() for v in (entry_data.get("labels") or []) if str(v).strip()]

            contents = entry_data.get("contents") if isinstance(entry_data.get("contents"), list) else []
            content_rows: list[dict] = []
            for index, content in enumerate(contents, start=1):
                if not isinstance(content, dict):
                    continue
                content_path = str(content.get("path", "")).strip()
                if not content_path:
                    continue
                content_cover = str(content.get("cover", "")).strip()
                content_rows.append(
                    {
                        "content_key": f"{index:05d}",
                        "path": content_path,
                        "name": str(content.get("name", "")).strip() or content_path.split("/")[-1],
                        "note": str(content.get("note", "")).strip(),
                        "cover": content_cover,
                    }
                )

            if not content_rows:
                entries_without_contents += 1

            series_cover = str(entry_data.get("cover", "")).strip()

            all_persons.update(persons)
            all_labels.update(labels)
            content_person_rows += len(content_rows) * len(persons)
            content_label_rows += len(content_rows) * len(labels)

            rows.append(
                {
                    "genre_key": genre_key,
                    "genre_name": genre_name,
                    "genre_path": genre_path,
                    "series_key": series_key,
                    "entry_key": orig_entry_key,
                    "series_name": series_name,
                    "series_path": series_path,
                    "series_note": series_note,
                    "series_cover": series_cover,
                    "persons": persons,
                    "labels": labels,
                    "contents": content_rows,
                }
            )

    counts = {
        "genres": len({(row["genre_key"], row["genre_path"]) for row in rows}),
        "series": len(rows),
        "contents": sum(len(row["contents"]) for row in rows),
        "persons": len(all_persons),
        "labels": len(all_labels),
        "content_person_map": content_person_rows,
        "content_label_map": content_label_rows,
    }
    return rows, counts, entries_without_contents


def build_import_plan(db_path: Path, structure_path: Path) -> ImportPlan:
    structure = _load_structure(structure_path)
    _rows, target_counts, entries_without_contents = _build_import_payload(structure)
    existing_counts = _read_db_counts(db_path)

    return ImportPlan(
        db_path=db_path,
        structure_path=structure_path,
        db_exists=db_path.is_file(),
        target_counts=target_counts,
        existing_counts=existing_counts,
        entries_without_contents=entries_without_contents,
    )


def _create_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{stamp}{db_path.suffix}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _default_backup_dir(db_path: Path) -> Path:
    return db_path.parent / "backup"


def apply_import(db_path: Path, structure_path: Path, backup_dir: Path | None, no_backup: bool) -> dict:
    structure = _load_structure(structure_path)
    rows, target_counts, entries_without_contents = _build_import_payload(structure)

    _ensure_parent(db_path)
    if db_path.is_file() and not no_backup:
        _create_backup(db_path, backup_dir or _default_backup_dir(db_path))

    with closing(_connect_rw(db_path)) as conn:
        with conn:
            conn.executescript(
                """
DELETE FROM content_label_map;
DELETE FROM content_person_map;
DELETE FROM gallery_pages;
DELETE FROM contents;
DELETE FROM series;
DELETE FROM persons;
DELETE FROM labels;
DELETE FROM genres;
"""
            )

            genre_id_by_key: dict[str, int] = {}
            for row in rows:
                if row["genre_key"] in genre_id_by_key:
                    continue
                conn.execute(
                    "INSERT INTO genres(genre_key, name, path) VALUES (?, ?, ?)",
                    (row["genre_key"], row["genre_name"], row["genre_path"]),
                )
                genre_id_by_key[row["genre_key"]] = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            persons = sorted({p for row in rows for p in row["persons"]}, key=str.casefold)
            labels = sorted({l for row in rows for l in row["labels"]}, key=str.casefold)

            person_id_by_name: dict[str, int] = {}
            for name in persons:
                conn.execute(
                    "INSERT INTO persons(person_key, display_name) VALUES (?, ?)",
                    (name, name),
                )
                person_id_by_name[name] = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            label_id_by_name: dict[str, int] = {}
            for name in labels:
                conn.execute(
                    "INSERT INTO labels(label_key, display_name) VALUES (?, ?)",
                    (name, name),
                )
                label_id_by_name[name] = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            series_count = 0
            content_count = 0
            for row in rows:
                genre_id = genre_id_by_key[row["genre_key"]]
                conn.execute(
                    """
INSERT INTO series(genre_id, series_key, entry_key, name, path, note, cover, fingerprint)
VALUES (?, ?, ?, ?, ?, ?, ?, '')
""",
                    (
                        genre_id,
                        row["series_key"],
                        row["entry_key"],
                        row["series_name"],
                        row["series_path"],
                        row["series_note"],
                        row["series_cover"],
                    ),
                )
                series_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                series_count += 1

                for content in row["contents"]:
                    conn.execute(
                        """
INSERT INTO contents(series_id, content_key, name, path, note, cover, fingerprint)
VALUES (?, ?, ?, ?, ?, ?, '')
""",
                        (
                            series_id,
                            content["content_key"],
                            content["name"],
                            content["path"],
                            content["note"],
                            content["cover"],
                        ),
                    )
                    content_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                    content_count += 1

                    for person_name in row["persons"]:
                        conn.execute(
                            """
INSERT INTO content_person_map(content_id, person_id, role, sort_order)
VALUES (?, ?, '', 0)
""",
                            (content_id, person_id_by_name[person_name]),
                        )

                    for label_name in row["labels"]:
                        conn.execute(
                            "INSERT INTO content_label_map(content_id, label_id) VALUES (?, ?)",
                            (content_id, label_id_by_name[label_name]),
                        )

    return {
        "series": series_count,
        "contents": content_count,
        "entries_without_contents": entries_without_contents,
        "target_counts": target_counts,
    }


def _unique_entry_key(existing: dict, preferred: str) -> str:
    key = preferred or "entry"
    if key not in existing:
        return key
    index = 2
    while f"{key}-{index}" in existing:
        index += 1
    return f"{key}-{index}"


def export_structure_payload(db_path: Path) -> tuple[dict, dict[str, int]]:
    structure = {"contents-root": "contents", "genres": {}}
    counts = {
        "genres": 0,
        "series": 0,
        "contents": 0,
        "persons": 0,
        "labels": 0,
        "content_person_map": 0,
        "content_label_map": 0,
    }

    if not db_path.is_file():
        return structure, counts

    with closing(_connect_ro(db_path)) as conn:
        genre_rows = conn.execute(
            "SELECT id, genre_key, name, path FROM genres ORDER BY genre_key"
        ).fetchall()
        counts["genres"] = len(genre_rows)

        for genre_id, genre_key, genre_name, genre_path in genre_rows:
            entry_map: dict = {}

            series_rows = conn.execute(
                """
SELECT id, series_key, entry_key, name, path, note, cover
FROM series
WHERE genre_id = ?
ORDER BY series_key
""",
                (genre_id,),
            ).fetchall()
            counts["series"] += len(series_rows)

            for series_id, series_key, db_entry_key, series_name, series_path, series_note, series_cover in series_rows:
                content_rows = conn.execute(
                    """
SELECT id, content_key, name, path, note, cover
FROM contents
WHERE series_id = ?
ORDER BY content_key
""",
                    (series_id,),
                ).fetchall()
                counts["contents"] += len(content_rows)

                persons = [
                    row[0]
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
                    row[0]
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
                        "path": str(path or ""),
                        "cover": str(cover or ""),
                        "name": str(name or ""),
                        "note": str(note or ""),
                    }
                    for _content_id, _content_key, name, path, note, cover in content_rows
                ]

                preferred_key = str(db_entry_key or "").strip() or str(series_key or "").strip() or str(series_path or "").split("/")[-1]
                entry_key = _unique_entry_key(entry_map, preferred_key)
                entry_map[entry_key] = {
                    "path": str(series_path or ""),
                    "name": str(series_name or ""),
                    "series": str(series_key or ""),
                    "main-person": "",
                    "persons": persons,
                    "labels": labels,
                    "note": str(series_note or ""),
                    "cover": str(series_cover or ""),
                    "contents": contents,
                    "exturl": [],
                }

            structure["genres"][str(genre_key)] = {
                "name": str(genre_name or genre_key),
                "path": str(genre_path or genre_key),
                "entries": entry_map,
            }

        counts["persons"] = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
        counts["labels"] = int(conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0])
        counts["content_person_map"] = int(conn.execute("SELECT COUNT(*) FROM content_person_map").fetchone()[0])
        counts["content_label_map"] = int(conn.execute("SELECT COUNT(*) FROM content_label_map").fetchone()[0])

    return structure, counts


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _import_plan_payload(plan: ImportPlan) -> dict:
    return {
        "db_path": str(plan.db_path),
        "structure_path": str(plan.structure_path),
        "db_exists": plan.db_exists,
        "existing_counts": plan.existing_counts,
        "target_counts": plan.target_counts,
        "entries_without_contents": plan.entries_without_contents,
        "will_write": True,
    }


def _run_import_plan(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    structure_path = Path(args.structure)

    started = time.perf_counter()
    plan = build_import_plan(db_path=db_path, structure_path=structure_path)

    metrics = RunMetrics(
        pipeline="m06-t03-structure-import",
        mode="plan",
        log_path=args.metrics_log or None,
    )
    metrics.add_stage(
        name="build_import_plan",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=plan.target_counts["series"] + plan.target_counts["contents"],
        generated_count=plan.target_counts["series"] + plan.target_counts["contents"],
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path), "structure": str(structure_path), "command": args.command},
    )
    payload = metrics.finalize(success=True)

    _print_json(_import_plan_payload(plan))
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


def _run_import_apply(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    structure_path = Path(args.structure)
    backup_dir = Path(args.backup_dir) if args.backup_dir else None

    metrics = RunMetrics(
        pipeline="m06-t03-structure-import",
        mode="apply",
        log_path=args.metrics_log or None,
    )

    plan_started = time.perf_counter()
    plan = build_import_plan(db_path=db_path, structure_path=structure_path)
    metrics.add_stage(
        name="assess_import",
        status="ok",
        duration_ms=int((time.perf_counter() - plan_started) * 1000),
        scanned_count=plan.target_counts["series"] + plan.target_counts["contents"],
        generated_count=0,
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path), "structure": str(structure_path)},
    )

    apply_started = time.perf_counter()
    result = apply_import(
        db_path=db_path,
        structure_path=structure_path,
        backup_dir=backup_dir,
        no_backup=bool(args.no_backup),
    )

    transfer_files = 1 if db_path.is_file() else 0
    transfer_bytes = db_path.stat().st_size if db_path.is_file() else 0
    metrics.add_stage(
        name="import_apply",
        status="ok",
        duration_ms=int((time.perf_counter() - apply_started) * 1000),
        scanned_count=plan.target_counts["series"] + plan.target_counts["contents"],
        generated_count=result["series"] + result["contents"],
        transfer_files=transfer_files,
        transfer_bytes=transfer_bytes,
        details={
            "series": result["series"],
            "contents": result["contents"],
            "entries_without_contents": result["entries_without_contents"],
            "backup_skipped": bool(args.no_backup),
        },
    )
    payload = metrics.finalize(success=True)

    _print_json(_import_plan_payload(build_import_plan(db_path=db_path, structure_path=structure_path)))
    print(f"Applied import: series={result['series']}, contents={result['contents']}")
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


def _run_export_plan(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    output_path = Path(args.output)

    started = time.perf_counter()
    _payload, counts = export_structure_payload(db_path)

    metrics = RunMetrics(
        pipeline="m06-t03-structure-export",
        mode="plan",
        log_path=args.metrics_log or None,
    )
    metrics.add_stage(
        name="build_export_plan",
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        scanned_count=counts["series"] + counts["contents"],
        generated_count=counts["series"] + counts["contents"],
        transfer_files=0,
        transfer_bytes=0,
        details={"db": str(db_path), "output": str(output_path), "command": args.command},
    )
    payload = metrics.finalize(success=True)

    _print_json(
        {
            "db_path": str(db_path),
            "output_path": str(output_path),
            "db_exists": db_path.is_file(),
            "counts": counts,
            "will_write": True,
        }
    )
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


def _run_export_apply(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    output_path = Path(args.output)

    metrics = RunMetrics(
        pipeline="m06-t03-structure-export",
        mode="apply",
        log_path=args.metrics_log or None,
    )

    export_started = time.perf_counter()
    payload, counts = export_structure_payload(db_path)
    _ensure_parent(output_path)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output_path.write_text(text, encoding="utf-8", newline="\n")

    metrics.add_stage(
        name="export_apply",
        status="ok",
        duration_ms=int((time.perf_counter() - export_started) * 1000),
        scanned_count=counts["series"] + counts["contents"],
        generated_count=counts["series"] + counts["contents"],
        transfer_files=1,
        transfer_bytes=output_path.stat().st_size,
        details={"db": str(db_path), "output": str(output_path)},
    )
    metric_payload = metrics.finalize(success=True)

    _print_json(
        {
            "db_path": str(db_path),
            "output_path": str(output_path),
            "counts": counts,
            "output_bytes": output_path.stat().st_size,
        }
    )
    print(f"Metrics log: {metrics.log_path}")
    if metric_payload.get("compare"):
        compare = metric_payload["compare"]
        print(
            "Compare(previous): "
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T03 structure <-> sqlite transfer")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("import-plan", "import-dry-run"):
        p = sub.add_parser(name, help="Plan structure.json -> sqlite import without writing")
        p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
        p.add_argument("--structure", default=str(DEFAULT_STRUCTURE_PATH), help="Input structure.json path")
        p.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")

    p_apply = sub.add_parser("import-apply", help="Apply structure.json -> sqlite import")
    p_apply.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
    p_apply.add_argument("--structure", default=str(DEFAULT_STRUCTURE_PATH), help="Input structure.json path")
    p_apply.add_argument("--backup-dir", default="", help="Backup directory for existing DB")
    p_apply.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    p_apply.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")

    for name in ("export-plan", "export-dry-run"):
        p = sub.add_parser(name, help="Plan sqlite -> intermediate export without writing")
        p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
        p.add_argument("--output", default=str(DEFAULT_EXPORT_PATH), help="Output intermediate json path")
        p.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")

    p_export_apply = sub.add_parser("export-apply", help="Apply sqlite -> intermediate export")
    p_export_apply.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
    p_export_apply.add_argument("--output", default=str(DEFAULT_EXPORT_PATH), help="Output intermediate json path")
    p_export_apply.add_argument("--metrics-log", default="", help="Optional JSONL metrics path")

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.command in ("import-plan", "import-dry-run"):
        return _run_import_plan(args)
    if args.command == "import-apply":
        return _run_import_apply(args)
    if args.command in ("export-plan", "export-dry-run"):
        return _run_export_plan(args)
    if args.command == "export-apply":
        return _run_export_apply(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
