import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools import maint_db_schema


class M06T02DbSchemaTests(unittest.TestCase):
    def test_plan_and_dry_run_do_not_create_db_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            metrics_path = Path(tmp) / "metrics-plan.jsonl"

            rc_plan = maint_db_schema.main([
                "plan",
                "--db",
                str(db_path),
                "--metrics-log",
                str(metrics_path),
            ])
            rc_dry = maint_db_schema.main([
                "dry-run",
                "--db",
                str(db_path),
                "--metrics-log",
                str(metrics_path),
            ])

            self.assertEqual(rc_plan, 0)
            self.assertEqual(rc_dry, 0)
            self.assertFalse(db_path.exists())

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t02-sqlite-schema")
            self.assertEqual(payload["mode"], "plan")
            self.assertTrue(payload["success"])

    def test_apply_creates_required_tables_indexes_and_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            metrics_path = Path(tmp) / "metrics-apply.jsonl"

            rc = maint_db_schema.main([
                "apply",
                "--db",
                str(db_path),
                "--no-backup",
                "--metrics-log",
                str(metrics_path),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(db_path.is_file())

            with closing(sqlite3.connect(str(db_path))) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                table_rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                table_names = {row[0] for row in table_rows}

                for table in maint_db_schema.SCHEMA_TABLES:
                    self.assertIn(table, table_names)
                self.assertIn("schema_migrations", table_names)

                index_rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
                index_names = {row[0] for row in index_rows}
                self.assertIn("idx_series_fingerprint", index_names)
                self.assertIn("idx_contents_fingerprint", index_names)
                self.assertIn("idx_jobs_status_requested_at", index_names)

                conn.execute(
                    "INSERT INTO genres(genre_key, name, path) VALUES (?, ?, ?)",
                    ("photo", "Photo", "photo"),
                )
                genre_id = conn.execute("SELECT id FROM genres WHERE genre_key='photo'").fetchone()[0]

                conn.execute(
                    "INSERT INTO series(genre_id, series_key, name, path) VALUES (?, ?, ?, ?)",
                    (genre_id, "s01", "Series-1", "photo/s01"),
                )

                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO series(genre_id, series_key, name, path) VALUES (?, ?, ?, ?)",
                        (genre_id, "s01", "Series-duplicate", "photo/s01-dup"),
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO series(genre_id, series_key, name, path) VALUES (?, ?, ?, ?)",
                        (999999, "s02", "Broken", "photo/s02"),
                    )
                conn.rollback()

    def test_apply_existing_db_creates_backup_before_schema_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "existing.sqlite3"
            backup_dir = Path(tmp) / "backup"

            with closing(sqlite3.connect(str(db_path))) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sentinel(id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO sentinel(value) VALUES ('before')")
                conn.commit()

            rc = maint_db_schema.main([
                "apply",
                "--db",
                str(db_path),
                "--backup-dir",
                str(backup_dir),
            ])
            self.assertEqual(rc, 0)

            backups = list(backup_dir.glob("existing_*.sqlite3.bak"))
            self.assertGreaterEqual(len(backups), 1)

            with closing(sqlite3.connect(str(db_path))) as conn:
                row = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 1").fetchone()
                self.assertEqual(int(row[0]), 1)


if __name__ == "__main__":
    unittest.main()