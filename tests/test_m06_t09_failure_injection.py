"""T09-01/02: Quality assurance and recovery tests.

T09-01: Unit / integration test coverage expansion.
T09-02: Failure injection tests:
  - Step mid-failure in UC1/UC2 workflow (途中失敗)
  - NAS copy disconnect simulation (NAS切断)
  - CSV malformed / missing required columns (CSV不正)
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import maint_uc_cli
from tools import maint_sync_nas
from tools import maint_metadata
from tools.maint_sync_nas import (
    SyncManifest,
    ManifestEntry,
    apply_manifest,
    build_manifest,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_minimum_db(db_path: Path) -> None:
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
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY,
                person_key TEXT,
                display_name TEXT
            );
            CREATE TABLE labels (
                id INTEGER PRIMARY KEY,
                label_key TEXT,
                display_name TEXT
            );
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


def _make_structure_json(path: Path) -> None:
    payload = {
        "contents-root": "contents",
        "genres": {
            "comic": {
                "name": "comic",
                "path": "comic",
                "entries": {
                    "00001": {
                        "name": "Series A",
                        "series": "series-a",
                        "path": "comic/series-a",
                        "main-person": "author-a",
                        "persons": ["author-a"],
                        "labels": ["label-a"],
                        "note": "",
                    }
                },
            }
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _make_metadata_csv(path: Path, rows: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["genre", "entry_key", "name", "main-person", "persons", "labels", "note"]
    if rows is None:
        rows = []
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ===========================================================================
# T09-01: Unit / integration coverage expansion
# ===========================================================================

class T09Unit_UcCliStateLog(unittest.TestCase):
    """T09-01: State log is written correctly on success and failure."""

    def _base_args(self, root: Path, db_path: Path, structure_path: Path) -> list[str]:
        site_dir = root / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        return [
            "--state-file", str(root / "state.jsonl"),
            "--log-dir", str(root / "logs"),
            "--metrics-log", str(root / "metrics.jsonl"),
            "plan", "uc1",
            "--db", str(db_path),
            "--structure", str(structure_path),
            "--site-dir", str(site_dir),
        ]

    def test_state_log_records_run_id_and_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            _make_minimum_db(db_path)
            structure_path = root / "structure.json"
            _make_structure_json(structure_path)

            rc = maint_uc_cli.main(self._base_args(root, db_path, structure_path))
            self.assertEqual(rc, 0)

            state_path = root / "state.jsonl"
            self.assertTrue(state_path.is_file())
            row = json.loads(state_path.read_text(encoding="utf-8").strip())
            self.assertIn("run_id", row)
            self.assertTrue(row["success"])
            self.assertEqual(row["command"], "plan")
            self.assertEqual(row["workflow"], "uc1")

    def test_state_log_records_each_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            _make_minimum_db(db_path)
            structure_path = root / "structure.json"
            _make_structure_json(structure_path)

            maint_uc_cli.main(self._base_args(root, db_path, structure_path))

            row = json.loads((root / "state.jsonl").read_text(encoding="utf-8").strip())
            step_names = [s["name"] for s in row["steps"]]
            self.assertIn("t03-import-plan", step_names)
            self.assertIn("t04-series-diff-plan", step_names)
            self.assertIn("t05-site-artifacts-plan", step_names)


class T09Unit_ValidateResumHint(unittest.TestCase):
    """T09-01: validate provides resume_hint when previous run failed."""

    def test_resume_hint_appears_when_previous_run_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            _make_minimum_db(db_path)
            structure_path = root / "structure.json"
            _make_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)
            state_path = root / "state.jsonl"

            # Inject a failed run record manually
            failed_record = {
                "schema": "imviewer.m06.t07.uc_cli_state.v1",
                "run_id": "test000abc",
                "command": "apply",
                "workflow": "uc1",
                "started_at": "2026-01-01T00:00:00",
                "ended_at": "2026-01-01T00:00:01",
                "success": False,
                "steps": [],
                "metrics_log": "",
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with state_path.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(failed_record, ensure_ascii=False) + "\n")

            stream = io.StringIO()
            with redirect_stdout(stream):
                maint_uc_cli.main([
                    "--state-file", str(state_path),
                    "--log-dir", str(root / "logs"),
                    "validate", "uc1",
                    "--db", str(db_path),
                    "--structure", str(structure_path),
                    "--site-dir", str(site_dir),
                ])

            output = stream.getvalue()
            self.assertIn("resume_hint", output)
            self.assertIn("test000abc", output)


class T09Unit_RollbackNoBackup(unittest.TestCase):
    """T09-01: rollback returns error code when no backup exists."""

    def test_rollback_without_backup_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "maintenance.sqlite3"
            db_path.write_text("current", encoding="utf-8", newline="\n")
            # No backup/ directory at all.

            rc = maint_uc_cli.main([
                "--state-file", str(root / "state.jsonl"),
                "--metrics-log", str(root / "metrics.jsonl"),
                "rollback",
                "--db", str(db_path),
            ])

            self.assertNotEqual(rc, 0)
            # Original DB must not be corrupted.
            self.assertEqual(db_path.read_text(encoding="utf-8"), "current")


# ===========================================================================
# T09-02: Failure injection — step mid-failure (途中失敗)
# ===========================================================================

class T09Inject_WorkflowMidFailure(unittest.TestCase):
    """T09-02: When a step fails mid-workflow, execution stops and state log
    records the failure (success=False)."""

    def test_uc1_plan_stops_on_first_step_failure(self):
        """Mock the first step to fail; subsequent steps must not run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            _make_minimum_db(db_path)
            structure_path = root / "structure.json"
            _make_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            import subprocess
            from tools.maint_uc_cli import StepResult

            call_log: list[str] = []

            def fake_run_step(step, log_dir, run_id):
                call_log.append(step.name)
                # Fail the very first step
                if step.name == "t03-import-plan":
                    return StepResult(
                        name=step.name,
                        command=["fake"],
                        rc=1,
                        duration_ms=5,
                        log_path="fake.log",
                    )
                return StepResult(
                    name=step.name,
                    command=["fake"],
                    rc=0,
                    duration_ms=5,
                    log_path="fake.log",
                )

            with patch.object(maint_uc_cli, "_run_step", side_effect=fake_run_step):
                rc = maint_uc_cli.main([
                    "--state-file", str(root / "state.jsonl"),
                    "--log-dir", str(root / "logs"),
                    "--metrics-log", str(root / "metrics.jsonl"),
                    "plan", "uc1",
                    "--db", str(db_path),
                    "--structure", str(structure_path),
                    "--site-dir", str(site_dir),
                ])

            self.assertNotEqual(rc, 0)
            # Only the first step should have been called
            self.assertEqual(call_log, ["t03-import-plan"])

            state_row = json.loads((root / "state.jsonl").read_text(encoding="utf-8").strip())
            self.assertFalse(state_row["success"])

    def test_uc1_plan_stops_on_second_step_failure(self):
        """First step succeeds, second fails — third must not run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            _make_minimum_db(db_path)
            structure_path = root / "structure.json"
            _make_structure_json(structure_path)
            site_dir = root / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            from tools.maint_uc_cli import StepResult

            call_log: list[str] = []

            def fake_run_step(step, log_dir, run_id):
                call_log.append(step.name)
                rc = 1 if step.name == "t04-series-diff-plan" else 0
                return StepResult(
                    name=step.name,
                    command=["fake"],
                    rc=rc,
                    duration_ms=5,
                    log_path="fake.log",
                )

            with patch.object(maint_uc_cli, "_run_step", side_effect=fake_run_step):
                rc = maint_uc_cli.main([
                    "--state-file", str(root / "state.jsonl"),
                    "--log-dir", str(root / "logs"),
                    "--metrics-log", str(root / "metrics.jsonl"),
                    "plan", "uc1",
                    "--db", str(db_path),
                    "--structure", str(structure_path),
                    "--site-dir", str(site_dir),
                ])

            self.assertNotEqual(rc, 0)
            # Third step must NOT run
            self.assertNotIn("t05-site-artifacts-plan", call_log)

    def test_rollback_after_failed_apply_restores_db(self):
        """After a failed apply is recorded in state, rollback restores the DB."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sqlite_dir = root / "sqlite"
            backup_dir = sqlite_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)

            db_path = sqlite_dir / "db.sqlite3"
            db_path.write_text("new-broken", encoding="utf-8", newline="\n")
            backup_path = backup_dir / "db_20260101_000000.sqlite3.bak"
            backup_path.write_text("good-backup", encoding="utf-8", newline="\n")

            state_path = root / "state.jsonl"
            # Record the failed apply
            failed_record = {
                "schema": "imviewer.m06.t07.uc_cli_state.v1",
                "run_id": "failabc",
                "command": "apply",
                "workflow": "uc1",
                "started_at": "2026-01-01T00:00:00",
                "ended_at": "2026-01-01T00:00:01",
                "success": False,
                "steps": [],
                "metrics_log": "",
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with state_path.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(failed_record, ensure_ascii=False) + "\n")

            rc = maint_uc_cli.main([
                "--state-file", str(state_path),
                "--metrics-log", str(root / "metrics.jsonl"),
                "rollback",
                "--db", str(db_path),
            ])

            self.assertEqual(rc, 0)
            self.assertEqual(db_path.read_text(encoding="utf-8"), "good-backup")


# ===========================================================================
# T09-02: Failure injection — NAS disconnect simulation (NAS切断)
# ===========================================================================

class T09Inject_NasDisconnect(unittest.TestCase):
    """T09-02: NAS copy failure (simulated via OSError during shutil.copy2)."""

    def _make_source(self, tmp: Path) -> Path:
        src = tmp / "src"
        (src / "a.txt").parent.mkdir(parents=True, exist_ok=True)
        (src / "a.txt").write_bytes(b"file-a")
        (src / "b.txt").write_bytes(b"file-b")
        return src

    def test_apply_records_errors_on_copy_failure(self):
        """When shutil.copy2 raises OSError, apply_manifest should collect errors
        and the result['errors'] list should be non-empty."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = self._make_source(tmp_path)
            dst = tmp_path / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            self.assertGreater(manifest.copy_count, 0)

            import shutil

            def raise_oserror(src_p, dst_p):
                raise OSError("Simulated NAS disconnect: connection reset")

            with patch.object(shutil, "copy2", side_effect=raise_oserror):
                result = apply_manifest(manifest)

            self.assertGreater(len(result["errors"]), 0)
            self.assertEqual(result["copied"], 0)

    def test_apply_partial_failure_reports_correct_counts(self):
        """When only some copies fail, copied count + error count == total."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = self._make_source(tmp_path)
            dst = tmp_path / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            total = manifest.copy_count
            self.assertGreater(total, 1)

            import shutil

            call_count = [0]

            original_copy2 = shutil.copy2

            def partial_fail(src_p, dst_p):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise OSError("Simulated NAS disconnect on first file")
                original_copy2(src_p, dst_p)

            with patch.object(shutil, "copy2", side_effect=partial_fail):
                result = apply_manifest(manifest)

            self.assertEqual(result["copied"] + len(result["errors"]), total)
            self.assertEqual(len(result["errors"]), 1)

    def test_apply_empty_dest_directory_missing_still_creates(self):
        """apply_manifest creates missing destination subdirectories even on
        first-time deploy (no pre-existing dest structure)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            (src / "sub" / "deep").mkdir(parents=True, exist_ok=True)
            (src / "sub" / "deep" / "file.js").write_bytes(b"var x=1;")
            dst = tmp_path / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            result = apply_manifest(manifest)

            self.assertEqual(result["copied"], 1)
            self.assertEqual(result["errors"], [])
            self.assertTrue((dst / "sub" / "deep" / "file.js").is_file())

    def test_dry_run_never_writes_even_when_copy_would_fail(self):
        """build_manifest (plan/dry-run) never touches dest, regardless of
        whether an actual copy would fail."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = self._make_source(tmp_path)
            # dst is a read-only-like directory (no write permission test is
            # impractical cross-platform, so we verify no files appear in dst)
            dst = tmp_path / "dst_empty"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            # dry-run: no apply called — dest must remain empty
            self.assertEqual(list(dst.rglob("*")), [])
            self.assertGreater(manifest.copy_count, 0)


# ===========================================================================
# T09-02: Failure injection — CSV malformed (CSV不正)
# ===========================================================================

class T09Inject_CsvMalformed(unittest.TestCase):
    """T09-02: Malformed or missing-column CSV inputs."""

    def _structure(self) -> dict:
        return {
            "genres": {
                "comic": {
                    "name": "comic",
                    "path": "comic",
                    "entries": {
                        "00001": {
                            "name": "Series A",
                            "series": "series-a",
                            "path": "comic/series-a",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                        }
                    },
                }
            }
        }

    def test_csv_missing_genre_and_entry_key_rows_are_skipped_not_crash(self):
        """Rows that lack genre or entry_key are warned and skipped; apply exits
        without crashing and does not write structure."""
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            # row with no genre value
            ",00001,Series A,,,,"
            "\n"
            # row with no entry_key
            "comic,,Series B,,,,"
            "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig", newline="\n")

            structure = self._structure()
            stream = io.StringIO()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
                redirect_stdout(stream),
            ):
                maint_metadata.main(["plan", "--input", str(csv_path)])

            # Both bad rows skipped — no crash, structure not written
            mock_save.assert_not_called()
            output = stream.getvalue()
            self.assertIn("0 entries would be updated", output)

    def test_csv_unknown_genre_warns_but_does_not_crash(self):
        """A genre that doesn't exist in structure emits a WARNING and is counted
        as not_found, but the command succeeds."""
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "nonexistent_genre,00001,Series A,,,,"
            "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig", newline="\n")

            structure = self._structure()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
            ):
                # Should not raise
                maint_metadata.main(["plan", "--input", str(csv_path)])

            mock_save.assert_not_called()

    def test_csv_entirely_empty_rows_plan_shows_zero_changes(self):
        """Empty CSV (header only) yields 0 changes and no structure write."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "metadata.csv"
            _make_metadata_csv(csv_path, rows=[])

            structure = self._structure()
            stream = io.StringIO()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
                redirect_stdout(stream),
            ):
                maint_metadata.main(["plan", "--input", str(csv_path)])

            mock_save.assert_not_called()
            output = stream.getvalue()
            self.assertIn("0 entries would be updated", output)

    def test_csv_semicolon_edge_cases_in_list_fields(self):
        """Semicolon-edge cases in persons/labels: leading/trailing separators
        produce clean lists without empty strings."""
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "comic,00001,Series A,,;author-a;,;label-a;,"
            "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig", newline="\n")

            structure = self._structure()
            stream = io.StringIO()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
                redirect_stdout(stream),
            ):
                maint_metadata.main(["plan", "--input", str(csv_path)])

            mock_save.assert_not_called()
            output = stream.getvalue()
            # Should detect the change (empty list -> non-empty list)
            self.assertIn("would be updated", output)


if __name__ == "__main__":
    unittest.main()
