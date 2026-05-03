import json
import tempfile
import unittest
from pathlib import Path

from tools import maint_db_schema
from tools import maint_db_transfer


class M06T03DbTransferTests(unittest.TestCase):
    def _sample_structure(self) -> dict:
        return {
            "contents-root": "contents",
            "genres": {
                "comic": {
                    "name": "漫画",
                    "path": "comic",
                    "entries": {
                        "[テスト][著者A] 作品タイトルA": {
                            "path": "comic/series-a",
                            "name": "Series A",
                            "series": "series-a",
                            "main-person": "",
                            "persons": ["Person A", "Person B"],
                            "labels": ["Label A", "Label B"],
                            "note": "Series note",
                            "contents": [
                                {
                                    "path": "comic/series-a/book-01",
                                    "cover": "thumbnail/comic/series-a/book-01/cover.jpg",
                                    "name": "Book 01",
                                    "note": "Book note",
                                },
                                {
                                    "path": "comic/series-a/book-02",
                                    "cover": "thumbnail/comic/series-a/book-02/cover.jpg",
                                    "name": "Book 02",
                                    "note": "",
                                },
                            ],
                            "exturl": [],
                        }
                    },
                },
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
                        "[テスト][モデルP] 写真集タイトルP": {
                            "path": "photo/series-p",
                            "name": "Series P",
                            "series": "series-p",
                            "main-person": "",
                            "persons": ["Model P"],
                            "labels": ["Label P"],
                            "note": "",
                            "contents": [
                                {
                                    "path": "photo/series-p",
                                    "cover": "thumbnail/photo/series-p/cover.jpg",
                                    "name": "Series P",
                                    "note": "",
                                }
                            ],
                            "exturl": [],
                        }
                    },
                },
            },
        }

    def _normalize_structure(self, structure: dict) -> list[dict]:
        normalized: list[dict] = []
        genres = structure.get("genres") or {}
        for genre_key, genre_data in genres.items():
            entries = (genre_data or {}).get("entries") or {}
            for entry_key, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                normalized.append(
                    {
                        "genre": genre_key,
                        "entry_key": str(entry_key),
                        "path": str(entry.get("path") or ""),
                        "name": str(entry.get("name") or ""),
                        "series": str(entry.get("series") or ""),
                        "labels": sorted(str(v) for v in (entry.get("labels") or [])),
                        "persons": sorted(str(v) for v in (entry.get("persons") or [])),
                        "note": str(entry.get("note") or ""),
                        "cover": str(entry.get("cover") or ""),
                        "contents": [
                            {
                                "path": str(c.get("path") or ""),
                                "name": str(c.get("name") or ""),
                                "note": str(c.get("note") or ""),
                                "cover": str(c.get("cover") or ""),
                            }
                            for c in (entry.get("contents") or [])
                            if isinstance(c, dict)
                        ],
                    }
                )
        normalized.sort(key=lambda row: (row["genre"], row["path"], row["name"]))
        for row in normalized:
            row["contents"].sort(key=lambda c: c["path"])
        return normalized

    def test_import_plan_and_dry_run_do_not_create_db_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            structure_path = Path(tmp) / "structure.json"
            db_path = Path(tmp) / "maintenance.sqlite3"
            metrics_path = Path(tmp) / "metrics-import-plan.jsonl"
            structure_path.write_text(json.dumps(self._sample_structure(), ensure_ascii=False), encoding="utf-8")

            rc_plan = maint_db_transfer.main(
                [
                    "import-plan",
                    "--structure",
                    str(structure_path),
                    "--db",
                    str(db_path),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )
            rc_dry = maint_db_transfer.main(
                [
                    "import-dry-run",
                    "--structure",
                    str(structure_path),
                    "--db",
                    str(db_path),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )

            self.assertEqual(rc_plan, 0)
            self.assertEqual(rc_dry, 0)
            self.assertFalse(db_path.exists())
            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t03-structure-import")
            self.assertEqual(payload["mode"], "plan")

    def test_export_plan_and_dry_run_do_not_write_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "maintenance.sqlite3"
            output_path = Path(tmp) / "intermediate.json"
            metrics_path = Path(tmp) / "metrics-export-plan.jsonl"

            rc_schema = maint_db_schema.main(["apply", "--db", str(db_path), "--no-backup"])
            self.assertEqual(rc_schema, 0)

            rc_plan = maint_db_transfer.main(
                [
                    "export-plan",
                    "--db",
                    str(db_path),
                    "--output",
                    str(output_path),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )
            rc_dry = maint_db_transfer.main(
                [
                    "export-dry-run",
                    "--db",
                    str(db_path),
                    "--output",
                    str(output_path),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )

            self.assertEqual(rc_plan, 0)
            self.assertEqual(rc_dry, 0)
            self.assertFalse(output_path.exists())
            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t03-structure-export")
            self.assertEqual(payload["mode"], "plan")

    def test_roundtrip_structure_to_sqlite_and_back_keeps_major_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            structure_path = Path(tmp) / "structure.json"
            db_path = Path(tmp) / "maintenance.sqlite3"
            output_path = Path(tmp) / "intermediate.json"

            source = self._sample_structure()
            structure_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            rc_schema = maint_db_schema.main(["apply", "--db", str(db_path), "--no-backup"])
            self.assertEqual(rc_schema, 0)

            rc_import = maint_db_transfer.main(
                [
                    "import-apply",
                    "--structure",
                    str(structure_path),
                    "--db",
                    str(db_path),
                    "--no-backup",
                ]
            )
            self.assertEqual(rc_import, 0)

            rc_export = maint_db_transfer.main(
                [
                    "export-apply",
                    "--db",
                    str(db_path),
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(rc_export, 0)

            exported = json.loads(output_path.read_text(encoding="utf-8"))

            source_norm = self._normalize_structure(source)
            exported_norm = self._normalize_structure(exported)

            self.assertEqual(len(source_norm), len(exported_norm))
            self.assertEqual(source_norm, exported_norm)


if __name__ == "__main__":
    unittest.main()
