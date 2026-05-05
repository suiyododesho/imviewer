import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import maint_db_schema, maint_series_diff
from tools.history_manager import parse_history


class M06T04SeriesDiffTests(unittest.TestCase):
    def _setup_db(self, db_path: Path) -> None:
        rc = maint_db_schema.main(["apply", "--db", str(db_path), "--no-backup"])
        self.assertEqual(rc, 0)

    def _insert_sample_series(self, db_path: Path, *, stored_fingerprint: str) -> None:
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                "INSERT INTO genres(genre_key, name, path) VALUES (?, ?, ?)",
                ("comic", "Comic", "comic"),
            )
            genre_id = int(conn.execute("SELECT id FROM genres WHERE genre_key='comic'").fetchone()[0])
            conn.execute(
                """
INSERT INTO series(genre_id, series_key, entry_key, name, path, note, cover, fingerprint)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
                (
                    genre_id,
                    "series-a",
                    "00001",
                    "Series A",
                    "comic/series-a",
                    "note-a",
                    "thumbnail/comic/series-a/cover.jpg",
                    stored_fingerprint,
                ),
            )
            series_id = int(conn.execute("SELECT id FROM series WHERE series_key='series-a'").fetchone()[0])

            conn.execute(
                """
INSERT INTO contents(series_id, content_key, name, path, note, cover, fingerprint)
VALUES (?, ?, ?, ?, ?, ?, '')
""",
                (
                    series_id,
                    "00001",
                    "Book 01",
                    "comic/series-a/book-01",
                    "",
                    "thumbnail/comic/series-a/book-01/cover.jpg",
                ),
            )
            conn.commit()

    def test_plan_and_dry_run_report_missing_fingerprint_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            metrics_path = Path(tmp) / "metrics-plan.jsonl"

            self._setup_db(db_path)
            self._insert_sample_series(db_path, stored_fingerprint="")

            before_stat = db_path.stat()

            out_plan = io.StringIO()
            with redirect_stdout(out_plan):
                rc_plan = maint_series_diff.main(
                    ["plan", "--db", str(db_path), "--metrics-log", str(metrics_path)]
                )

            out_dry = io.StringIO()
            with redirect_stdout(out_dry):
                rc_dry = maint_series_diff.main(
                    ["dry-run", "--db", str(db_path), "--metrics-log", str(metrics_path)]
                )

            after_stat = db_path.stat()

            self.assertEqual(rc_plan, 0)
            self.assertEqual(rc_dry, 0)
            self.assertEqual(before_stat.st_size, after_stat.st_size)
            self.assertEqual(before_stat.st_mtime_ns, after_stat.st_mtime_ns)

            plan_output = out_plan.getvalue().strip()
            plan_json = json.loads(plan_output.split("\nMetrics log:", 1)[0])
            self.assertEqual(plan_json["changed_series_count"], 1)
            self.assertEqual(plan_json["changed_series"][0]["reason"], "missing_fingerprint")
            self.assertEqual(plan_json["changed_series"][0]["path"], "comic/series-a")

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t04-series-diff")
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["success"], True)

    def test_plan_reports_fingerprint_changed_and_excludes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            self._setup_db(db_path)
            self._insert_sample_series(db_path, stored_fingerprint="deadbeef")

            first_plan = maint_series_diff.build_plan(db_path)
            self.assertEqual(first_plan.scanned_series, 1)
            self.assertEqual(len(first_plan.changed_series), 1)
            self.assertEqual(first_plan.changed_series[0]["reason"], "fingerprint_changed")

            computed = first_plan.changed_series[0]["computed_fingerprint"]
            with closing(sqlite3.connect(str(db_path))) as conn:
                conn.execute(
                    "UPDATE series SET fingerprint = ? WHERE series_key = ?",
                    (computed, "series-a"),
                )
                conn.commit()

            second_plan = maint_series_diff.build_plan(db_path)
            self.assertEqual(second_plan.scanned_series, 1)
            self.assertEqual(second_plan.changed_series, [])

    def test_apply_updates_fingerprint_and_connects_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            backup_dir = Path(tmp) / "backup"
            targets_path = Path(tmp) / "t04-targets.txt"
            history_path = Path(tmp) / "history.txt"

            self._setup_db(db_path)
            self._insert_sample_series(db_path, stored_fingerprint="")

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = maint_series_diff.main(
                    [
                        "apply",
                        "--db",
                        str(db_path),
                        "--backup-dir",
                        str(backup_dir),
                        "--output-targets",
                        str(targets_path),
                        "--write-history-targets",
                        "--history-path",
                        str(history_path),
                    ]
                )

            self.assertEqual(rc, 0)

            backups = list(backup_dir.glob("m06_*.sqlite3.bak"))
            self.assertGreaterEqual(len(backups), 1)

            self.assertTrue(targets_path.is_file())
            targets = targets_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(targets, ["comic/series-a"])

            history = parse_history(str(history_path))
            self.assertIn("comic/series-a", history.next_force_dirs)

            post_plan = maint_series_diff.build_plan(db_path)
            self.assertEqual(post_plan.changed_series, [])

            payload = json.loads(stream.getvalue().split("\nMetrics log:", 1)[0])
            self.assertEqual(payload["applied_count"], 1)
            self.assertEqual(payload["changed_series_count_after"], 0)

    def test_apply_failure_restores_db_from_backup_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "m06.sqlite3"
            backup_dir = Path(tmp) / "backup"

            self._setup_db(db_path)
            self._insert_sample_series(db_path, stored_fingerprint="")

            with patch.object(maint_series_diff, "_connect_rw", side_effect=RuntimeError("boom")):
                rc = maint_series_diff.main(
                    [
                        "apply",
                        "--db",
                        str(db_path),
                        "--backup-dir",
                        str(backup_dir),
                    ]
                )

            self.assertEqual(rc, 1)
            backups = list(backup_dir.glob("m06_*.sqlite3.bak"))
            self.assertGreaterEqual(len(backups), 1)

            with closing(sqlite3.connect(str(db_path))) as conn:
                row = conn.execute("SELECT fingerprint FROM series WHERE series_key='series-a'").fetchone()
                self.assertEqual(str(row[0] or ""), "")


if __name__ == "__main__":
    unittest.main()
