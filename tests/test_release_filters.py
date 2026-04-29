import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import release


class ReleaseFilterTests(unittest.TestCase):
    def test_collect_structure_targets_from_structure_json(self):
        sample = {
            "project-a": {
                "banner": "banner/sample.jpg",
                "person-a": {
                    "exturl": [{"url": "photo/alpha/orig/index_orig.html"}],
                    "galleries": [
                        {
                            "path": "photo/alpha/main/index_main.html",
                            "thumbnail": "thumbnail/alpha_001.jpg",
                        }
                    ],
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            structure_path = Path(tmp) / "structure.json"
            structure_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

            with patch.object(release, "STRUCTURE_JSON_PATH", str(structure_path)):
                photo_dirs, thumbnails, banners = release._collect_structure_release_targets()

        self.assertIn("photo/alpha/main", photo_dirs)
        self.assertIn("photo/alpha/orig", photo_dirs)
        self.assertIn("thumbnail/alpha_001.jpg", thumbnails)
        self.assertIn("banner/sample.jpg", banners)

    def test_split_releasable_photo_dirs_skips_unreferenced_history_dirs(self):
        sample = {
            "project-a": {
                "person-a": {
                    "galleries": [
                        {
                            "path": "photo/alpha/main/index_main.html",
                            "thumbnail": "thumbnail/alpha_001.jpg",
                        }
                    ],
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            structure_path = Path(tmp) / "structure.json"
            structure_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

            with patch.object(release, "STRUCTURE_JSON_PATH", str(structure_path)):
                included, skipped = release._split_releasable_photo_dirs([
                    "photo/alpha/main",
                    "photo/not-listed/item",
                ])

        self.assertEqual(included, ["photo/alpha/main"])
        self.assertEqual(skipped, ["photo/not-listed/item"])

    def test_force_dirs_are_always_included(self):
        sample = {
            "project-a": {
                "person-a": {
                    "galleries": [
                        {
                            "path": "photo/alpha/main/index_main.html",
                            "thumbnail": "thumbnail/alpha_001.jpg",
                        }
                    ],
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            structure_path = Path(tmp) / "structure.json"
            structure_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

            with patch.object(release, "STRUCTURE_JSON_PATH", str(structure_path)):
                included, skipped = release._split_releasable_photo_dirs(
                    ["photo/alpha/main", "photo/not-listed/item"],
                    ["photo/manual-css"]
                )

        self.assertEqual(included, ["photo/alpha/main", "photo/manual-css"])
        self.assertEqual(skipped, ["photo/not-listed/item"])


if __name__ == "__main__":
    unittest.main()
