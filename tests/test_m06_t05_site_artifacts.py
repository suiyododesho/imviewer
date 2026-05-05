import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image

from tools import maint_build_site_artifacts
from tools import maint_db_schema
from tools import maint_db_transfer


class M06T05SiteArtifactsTests(unittest.TestCase):
    def _sample_structure(self) -> dict:
        return {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
                        "series-a": {
                            "path": "photo/series-a",
                            "name": "Series A",
                            "series": "series-a",
                            "main-person": "",
                            "persons": ["Model A"],
                            "labels": ["Label A"],
                            "note": "",
                            "cover": "",
                            "contents": [
                                {
                                    "path": "photo/series-a/book01",
                                    "cover": "",
                                    "name": "Book 01",
                                    "note": "",
                                }
                            ],
                            "exturl": [],
                        }
                    },
                }
            },
        }

    def _create_sample_site(self, site_dir: Path) -> None:
        gallery_dir = site_dir / "contents" / "photo" / "series-a" / "book01"
        gallery_dir.mkdir(parents=True, exist_ok=True)
        for index, color in enumerate(((255, 0, 0), (0, 128, 255)), start=1):
            image_path = gallery_dir / f"{index:03d}.jpg"
            Image.new("RGB", (32 + index, 24 + index), color).save(image_path, format="JPEG")

    def _prepare_db(self, tmp: str) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        site_dir = root / "site"
        db_path = root / "maintenance.sqlite3"
        structure_path = root / "structure.json"
        self._create_sample_site(site_dir)
        structure_path.write_text(
            json.dumps(self._sample_structure(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(maint_db_schema.main(["apply", "--db", str(db_path), "--no-backup"]), 0)
        self.assertEqual(
            maint_db_transfer.main(
                [
                    "import-apply",
                    "--structure",
                    str(structure_path),
                    "--db",
                    str(db_path),
                    "--no-backup",
                ]
            ),
            0,
        )
        return db_path, site_dir, structure_path

    def test_plan_and_dry_run_do_not_write_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, site_dir, _structure_path = self._prepare_db(tmp)
            metrics_path = Path(tmp) / "t05-plan.jsonl"

            rc_plan = maint_build_site_artifacts.main(
                [
                    "plan",
                    "--db",
                    str(db_path),
                    "--site-dir",
                    str(site_dir),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )
            rc_dry = maint_build_site_artifacts.main(
                [
                    "dry-run",
                    "--db",
                    str(db_path),
                    "--site-dir",
                    str(site_dir),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )

            self.assertEqual(rc_plan, 0)
            self.assertEqual(rc_dry, 0)
            self.assertFalse((site_dir / "structure.json").exists())
            self.assertFalse((site_dir / "js" / "structure.js").exists())
            self.assertFalse((site_dir / "js" / "gallery-pages.js").exists())
            self.assertFalse((site_dir / "js" / "gallery-pages").exists())

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t05-site-artifacts")
            self.assertEqual(payload["mode"], "plan")

    def test_apply_writes_compat_and_split_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, site_dir, _structure_path = self._prepare_db(tmp)
            metrics_path = Path(tmp) / "t05-apply.jsonl"

            rc = maint_build_site_artifacts.main(
                [
                    "apply",
                    "--db",
                    str(db_path),
                    "--site-dir",
                    str(site_dir),
                    "--metrics-log",
                    str(metrics_path),
                ]
            )

            self.assertEqual(rc, 0)
            self.assertTrue((site_dir / "structure.json").is_file())
            self.assertTrue((site_dir / "js" / "structure.js").is_file())
            self.assertTrue((site_dir / "js" / "gallery-pages.js").is_file())
            self.assertTrue((site_dir / "js" / "gallery-pages" / "manifest.js").is_file())
            self.assertTrue((site_dir / "js" / "gallery-pages" / "chunks" / "photo" / "series-a.js").is_file())

            compat_text = (site_dir / "js" / "gallery-pages.js").read_text(encoding="utf-8")
            manifest_text = (site_dir / "js" / "gallery-pages" / "manifest.js").read_text(encoding="utf-8")
            chunk_text = (site_dir / "js" / "gallery-pages" / "chunks" / "photo" / "series-a.js").read_text(encoding="utf-8")

            self.assertIn("window.galleryPagesMap = ", compat_text)
            self.assertIn("window.galleryPagesManifest = ", manifest_text)
            self.assertIn("window.galleryPagesChunks = window.galleryPagesChunks || {};", chunk_text)

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "m06-t05-site-artifacts")
            self.assertEqual(payload["mode"], "apply")

    def test_plan_reports_split_chunk_smaller_than_compat_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, site_dir, _structure_path = self._prepare_db(tmp)
            metrics_path = Path(tmp) / "t05-size-plan.jsonl"
            stream = io.StringIO()

            with redirect_stdout(stream):
                rc = maint_build_site_artifacts.main(
                    [
                        "plan",
                        "--db",
                        str(db_path),
                        "--site-dir",
                        str(site_dir),
                        "--metrics-log",
                        str(metrics_path),
                    ]
                )

            self.assertEqual(rc, 0)
            plan_json = json.loads(stream.getvalue().split("\nMetrics log:", 1)[0])
            summary = plan_json["size_summary"]
            self.assertGreater(summary["compat_gallery_pages_bytes"], 0)
            self.assertGreater(summary["max_split_chunk_bytes"], 0)
            self.assertGreater(summary["compat_gallery_pages_bytes"], summary["max_split_chunk_bytes"])


if __name__ == "__main__":
    unittest.main()