import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import maint_uc_cli


class M06T07UnifiedCliTests(unittest.TestCase):
    def _create_structure_json(self, path: Path) -> None:
        payload = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "photo",
                    "path": "photo",
                    "entries": {},
                }
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def _create_metadata_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["genre", "entry_key", "name", "main-person", "persons", "labels", "note"],
            )
            writer.writeheader()

    def _create_minimum_schema_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript(
                """
                CREATE TABLE genres (
                    id INTEGER PRIMARY KEY,
                    genre_key TEXT,
                    name TEXT,
                    path TEXT
                );
                CREATE TABLE series (
                    id INTEGER PRIMARY KEY,
                    genre_id INTEGER,
                    series_key TEXT,
                    entry_key TEXT,
                    name TEXT,
                    path TEXT,
                    note TEXT,
                    cover TEXT,
                    fingerprint TEXT
                );
                CREATE TABLE contents (
                    id INTEGER PRIMARY KEY,
                    series_id INTEGER,
                    content_key TEXT,
                    name TEXT,
                    path TEXT,
                    note TEXT,
                    cover TEXT,
                    fingerprint TEXT
                );
                CREATE TABLE persons (id INTEGER PRIMARY KEY, person_key TEXT, display_name TEXT);
                CREATE TABLE labels (id INTEGER PRIMARY KEY, label_key TEXT, display_name TEXT);
                CREATE TABLE content_person_map (
                    content_id INTEGER,
                    person_id INTEGER,
                    role TEXT,
                    sort_order INTEGER
                );
                CREATE TABLE content_label_map (content_id INTEGER, label_id INTEGER);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def test_plan_uc1_runs_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "maintenance.sqlite3"
            self._create_minimum_schema_db(db_path)
            structure_path = root / "structure.json"
            self._create_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            state_file = root / "state" / "state.jsonl"
            log_dir = root / "logs"
            metrics_log = root / "metrics.jsonl"

            rc = maint_uc_cli.main(
                [
                    "--state-file",
                    str(state_file),
                    "--log-dir",
                    str(log_dir),
                    "--metrics-log",
                    str(metrics_log),
                    "plan",
                    "uc1",
                    "--db",
                    str(db_path),
                    "--structure",
                    str(structure_path),
                    "--site-dir",
                    str(site_dir),
                ]
            )

            self.assertEqual(rc, 0)
            self.assertTrue(state_file.is_file())
            self.assertTrue(metrics_log.is_file())
            self.assertFalse((site_dir / "structure.js").exists())

    def test_validate_uc2_and_plan_uc2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "maintenance.sqlite3"
            self._create_minimum_schema_db(db_path)
            structure_path = root / "structure.json"
            self._create_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            csv_path = root / "metadata.csv"
            self._create_metadata_csv(csv_path)
            diff_path = root / "targets.txt"
            diff_path.write_text("", encoding="utf-8", newline="\n")

            state_file = root / "state" / "state.jsonl"
            log_dir = root / "logs"
            metrics_log = root / "metrics.jsonl"

            rc_validate = maint_uc_cli.main(
                [
                    "--state-file",
                    str(state_file),
                    "--log-dir",
                    str(log_dir),
                    "--metrics-log",
                    str(metrics_log),
                    "validate",
                    "uc2",
                    "--db",
                    str(db_path),
                    "--structure",
                    str(structure_path),
                    "--site-dir",
                    str(site_dir),
                    "--input-csv",
                    str(csv_path),
                    "--diff-targets-file",
                    str(diff_path),
                ]
            )

            self.assertEqual(rc_validate, 0)
            self.assertTrue(state_file.is_file())

    def test_validate_uc1_allows_missing_db_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "sqlite" / "maintenance.sqlite3"
            db_path.parent.mkdir(parents=True, exist_ok=True)

            structure_path = root / "structure.json"
            self._create_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            state_file = root / "state" / "state.jsonl"
            log_dir = root / "logs"
            metrics_log = root / "metrics.jsonl"

            rc_validate = maint_uc_cli.main(
                [
                    "--state-file",
                    str(state_file),
                    "--log-dir",
                    str(log_dir),
                    "--metrics-log",
                    str(metrics_log),
                    "validate",
                    "uc1",
                    "--db",
                    str(db_path),
                    "--structure",
                    str(structure_path),
                    "--site-dir",
                    str(site_dir),
                ]
            )

            self.assertEqual(rc_validate, 0)
            self.assertTrue(state_file.is_file())

    def test_apply_requires_approve_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "maintenance.sqlite3"
            self._create_minimum_schema_db(db_path)
            structure_path = root / "structure.json"
            self._create_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            rc = maint_uc_cli.main(
                [
                    "apply",
                    "uc1",
                    "--db",
                    str(db_path),
                    "--structure",
                    str(structure_path),
                    "--site-dir",
                    str(site_dir),
                ]
            )
            self.assertEqual(rc, 2)

    def test_rollback_restores_from_latest_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sqlite_dir = root / "sqlite"
            backup_dir = sqlite_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)

            db_path = sqlite_dir / "imviewer_maintenance.sqlite3"
            db_path.write_text("new", encoding="utf-8", newline="\n")

            first_backup = backup_dir / "imviewer_maintenance_20260101_000000.sqlite3.bak"
            first_backup.write_text("old-1", encoding="utf-8", newline="\n")
            latest_backup = backup_dir / "imviewer_maintenance_20260102_000000.sqlite3.bak"
            latest_backup.write_text("old-2", encoding="utf-8", newline="\n")

            state_file = root / "state" / "state.jsonl"
            metrics_log = root / "metrics.jsonl"

            rc = maint_uc_cli.main(
                [
                    "--state-file",
                    str(state_file),
                    "--metrics-log",
                    str(metrics_log),
                    "rollback",
                    "--db",
                    str(db_path),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(db_path.read_text(encoding="utf-8"), "old-2")
            self.assertTrue(state_file.is_file())
            self.assertTrue(metrics_log.is_file())


if __name__ == "__main__":
    unittest.main()
