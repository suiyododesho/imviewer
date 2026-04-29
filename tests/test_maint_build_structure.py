import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import maint_build_structure
from tools import maint_build_gallery_pages
from tools import maint_structure_lib


class MaintBuildStructureTests(unittest.TestCase):
    def test_rebuild_structure_contents_generates_direct_children(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "00001": {
                        "path": "photo/alpha",
                        "name": "Alpha",
                        "series": "Alpha",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                        "contents": [],
                        "exturl": [],
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            series_dir = contents_dir / "photo" / "alpha"
            (series_dir / "book01" / "src" / "thumbnail").mkdir(parents=True)
            (series_dir / "book01" / "src" / "thumbnail" / "cover.jpg").write_bytes(b"x")
            (series_dir / "book02").mkdir(parents=True)
            (series_dir / "book02_pdf").mkdir(parents=True)
            (series_dir / "book03.pdf").write_text("pdf", encoding="utf-8")
            (series_dir / "book03_pdf" / "cover.jpg").parent.mkdir(parents=True)
            (series_dir / "book03_pdf" / "cover.jpg").write_bytes(b"x")

            with patch.object(maint_build_structure, "generate_contents_entries") as mock_generate:
                mock_generate.return_value = [
                    {"path": "photo/alpha/book01", "cover": "thumbnail/photo/alpha/book01/cover.jpg", "name": "book01", "note": ""},
                    {"path": "photo/alpha/book02", "cover": "", "name": "book02", "note": ""},
                    {"path": "photo/alpha/book03.pdf", "cover": "thumbnail/photo/alpha/book03_pdf/cover.jpg", "name": "book03", "note": ""},
                ]
                updated, changed = maint_build_structure.rebuild_structure_contents(structure)

        contents = updated["genres"]["photo"]["00001"]["contents"]
        self.assertEqual(len(contents), 3)
        self.assertEqual(changed[0]["count"], 3)
        self.assertEqual(contents[2]["name"], "book03")

    def test_rebuild_structure_contents_ignores_stray_src_directory(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "00001": {
                        "path": "photo/alpha",
                        "name": "Alpha",
                        "series": "Alpha",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                        "contents": [],
                        "exturl": [],
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            series_dir = contents_dir / "photo" / "alpha"
            (series_dir / "book01").mkdir(parents=True)
            (series_dir / "src" / "thumbnail").mkdir(parents=True)

            with patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)):
                entries = maint_structure_lib.generate_contents_entries("photo/alpha")

        self.assertEqual([item["path"] for item in entries], ["photo/alpha/book01"])

    def test_iter_gallery_paths_discovers_nested_html_under_content(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "00001": {
                        "path": "photo/alpha",
                        "name": "Alpha",
                        "series": "Alpha",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                        "contents": [
                            {"path": "photo/alpha/book01", "cover": "", "name": "book01", "note": ""}
                        ],
                        "exturl": [],
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            gallery_dir = contents_dir / "photo" / "alpha" / "book01" / "scene01"
            gallery_dir.mkdir(parents=True)
            (gallery_dir / "index.html").write_text("<html></html>", encoding="utf-8")
            (gallery_dir / "extra.html").write_text("<html></html>", encoding="utf-8")

            with patch.object(maint_build_gallery_pages, "CONTENTS_DIR", str(contents_dir)), patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)):
                found = list(maint_build_gallery_pages.iter_gallery_paths(structure))

        self.assertEqual(found, [
            "photo/alpha/book01/scene01/extra.html",
            "photo/alpha/book01/scene01/index.html",
        ])

    def test_find_cover_for_content_prefers_thumbnail_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            contents_dir = site_dir / "contents"
            thumb_dir = site_dir / "thumbnail"
            (contents_dir / "photo" / "alpha" / "book01").mkdir(parents=True)
            (thumb_dir / "photo" / "alpha" / "book01").mkdir(parents=True)
            (thumb_dir / "photo" / "alpha" / "book01" / "cover.jpg").write_bytes(b"x")

            with patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)), patch.object(maint_structure_lib, "SITE_DIR", str(site_dir)):
                cover = maint_structure_lib.find_cover_for_content("photo/alpha/book01")

        self.assertEqual(cover, "thumbnail/photo/alpha/book01/cover.jpg")

    def test_find_cover_for_content_legacy_contents_path_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            contents_dir = site_dir / "contents"
            (contents_dir / "photo" / "alpha" / "book01" / "src" / "thumbnail").mkdir(parents=True)
            (contents_dir / "photo" / "alpha" / "book01" / "src" / "thumbnail" / "cover.jpg").write_bytes(b"x")

            with patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)), patch.object(maint_structure_lib, "SITE_DIR", str(site_dir)):
                cover = maint_structure_lib.find_cover_for_content("photo/alpha/book01")

        self.assertEqual(cover, "photo/alpha/book01/src/thumbnail/cover.jpg")

    def test_generate_contents_entries_uses_generated_pdf_directory_not_pdf_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            contents_dir = site_dir / "contents"
            series_dir = contents_dir / "comic" / "series-a"
            series_dir.mkdir(parents=True)
            (series_dir / "book01.pdf").write_bytes(b"%PDF-1.7")

            def _fake_extract(pdf_abs, out_dir_abs, **_kwargs):
                out_dir = Path(out_dir_abs)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "001.jpg").write_bytes(b"jpeg")
                return [str(out_dir / "001.jpg")]

            with (
                patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)),
                patch.object(maint_structure_lib, "SITE_DIR", str(site_dir)),
                patch.object(maint_structure_lib, "extract_pdf_pages_to_dir", side_effect=_fake_extract),
            ):
                entries = maint_structure_lib.generate_contents_entries("comic/series-a")

        self.assertEqual([item["path"] for item in entries], ["comic/series-a/book01_pdf"])

    def test_generate_contents_entries_uses_generated_cbz_directory_not_cbz_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            contents_dir = site_dir / "contents"
            series_dir = contents_dir / "comic" / "series-b"
            series_dir.mkdir(parents=True)
            (series_dir / "book02.cbz").write_bytes(b"PK")

            def _fake_extract(cbz_abs, out_dir_abs, **_kwargs):
                out_dir = Path(out_dir_abs)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "001.jpg").write_bytes(b"jpeg")
                return [str(out_dir / "001.jpg")]

            with (
                patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)),
                patch.object(maint_structure_lib, "SITE_DIR", str(site_dir)),
                patch.object(maint_structure_lib, "extract_cbz_pages_to_dir", side_effect=_fake_extract),
            ):
                entries = maint_structure_lib.generate_contents_entries("comic/series-b")

        self.assertEqual([item["path"] for item in entries], ["comic/series-b/book02_cbz"])


if __name__ == "__main__":
    unittest.main()