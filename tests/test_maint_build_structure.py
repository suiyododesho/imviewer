import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import io
from contextlib import redirect_stdout

from tools.history_manager import HistoryData
from tools import build_gallery_pages_map
from tools import maint_build_gallery_pages
from tools import maint_build_gallery_thumbnails
from tools import maint_build_structure
from tools import maint_extract_archives
from tools import maint_refresh_covers
from tools import maint_structure_lib


class MaintBuildStructureTests(unittest.TestCase):
    def test_scaffold_missing_series_adds_series_with_blank_metadata(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
                        "00001": {
                            "path": "photo/alpha",
                            "name": "Alpha",
                            "series": "",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                            "contents": [],
                            "exturl": [],
                        }
                    },
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            (contents_dir / "photo" / "alpha").mkdir(parents=True)
            (contents_dir / "photo" / "beta").mkdir(parents=True)

            generated_contents = [
                {"path": "photo/beta/book01", "cover": "", "name": "book01", "note": "memo"}
            ]
            with patch.object(maint_build_structure, "CONTENTS_DIR", str(contents_dir)), patch.object(
                maint_build_structure, "scan_contents_entries", return_value=generated_contents
            ):
                updated, added = maint_build_structure.scaffold_missing_series(structure)

        scaffold = updated["genres"]["photo"]["entries"]["beta"]
        self.assertEqual(scaffold["path"], "photo/beta")
        self.assertEqual(scaffold["name"], "beta")
        self.assertEqual(scaffold["series"], "")
        self.assertEqual(scaffold["main-person"], "")
        self.assertEqual(scaffold["persons"], [])
        self.assertEqual(scaffold["labels"], [])
        self.assertEqual(scaffold["exturl"], [])
        self.assertEqual(scaffold["contents"], [
            {"path": "photo/beta/book01", "cover": "", "name": "book01", "note": ""}
        ])
        self.assertEqual(added, [{"genre": "photo", "series": "beta", "path": "photo/beta", "count": 1}])

    def test_find_unregistered_series_paths_detects_new_content_directories(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
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
                    },
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            (contents_dir / "photo" / "alpha").mkdir(parents=True)
            (contents_dir / "photo" / "beta").mkdir(parents=True)

            with patch.object(maint_build_structure, "CONTENTS_DIR", str(contents_dir)):
                missing = maint_build_structure.find_unregistered_series_paths(structure)

        self.assertEqual(missing, [{"genre": "photo", "path": "photo/beta", "name": "beta"}])

    def test_rebuild_structure_contents_removes_missing_series(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "comic": {
                    "name": "漫画",
                    "path": "comic",
                    "00001": {
                        "path": "comic/exists",
                        "name": "Exists",
                        "series": "Exists",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                        "contents": [],
                        "exturl": [],
                    },
                    "00002": {
                        "path": "comic/missing",
                        "name": "Missing",
                        "series": "Missing",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                        "contents": [],
                        "exturl": [],
                    },
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            (contents_dir / "comic" / "exists").mkdir(parents=True)

            with patch.object(maint_build_structure, "CONTENTS_DIR", str(contents_dir)), patch.object(
                maint_build_structure, "scan_contents_entries", return_value=[]
            ):
                updated, changed = maint_build_structure.rebuild_structure_contents(structure)

        comic_genre = updated["genres"]["comic"]
        self.assertIn("00001", comic_genre)
        self.assertNotIn("00002", comic_genre)
        removed = [item for item in changed if item.get("removed")]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["series"], "00002")

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

            with patch.object(maint_build_structure, "CONTENTS_DIR", str(contents_dir)), patch.object(
                maint_build_structure, "scan_contents_entries"
            ) as mock_scan:
                mock_scan.return_value = [
                    {"path": "photo/alpha/book01", "cover": "", "name": "book01", "note": ""},
                    {"path": "photo/alpha/book02", "cover": "", "name": "book02", "note": ""},
                    {"path": "photo/alpha/book03.pdf", "cover": "", "name": "book03", "note": ""},
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

    def test_scan_contents_entries_maps_pdf_file_to_generated_pdf_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            series_dir = contents_dir / "comic" / "series-c"
            series_dir.mkdir(parents=True)
            (series_dir / "book03.pdf").write_bytes(b"%PDF-1.7")

            with patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)):
                entries = maint_structure_lib.scan_contents_entries("comic/series-c")

        self.assertEqual([item["path"] for item in entries], ["comic/series-c/book03_pdf"])

    def test_gather_media_from_gallery_tree_sorts_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            gallery_dir = contents_dir / "photo" / "alpha" / "book01"
            gallery_dir.mkdir(parents=True)
            (gallery_dir / "002.jpg").write_bytes(b"jpeg")
            (gallery_dir / "001.jpg").write_bytes(b"jpeg")
            (gallery_dir / "000_cover.jpg").write_bytes(b"jpeg")

            with patch.object(maint_build_gallery_pages, "CONTENTS_DIR", str(contents_dir)):
                pages = maint_build_gallery_pages.gather_media_from_gallery_tree("photo/alpha/book01")

        self.assertEqual(
            [Path(page["image"]).name for page in pages if page.get("type") == "image"],
            ["000_cover.jpg", "001.jpg", "002.jpg"],
        )

    def test_build_gallery_pages_map_diff_detects_renamed_files_without_history(self):
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

        old_pages = [
            {
                "type": "image",
                "image": "contents/photo/alpha/book01/001.jpg",
                "thumbnail": "thumbnail/photo/alpha/book01/001.jpg",
                "html": "contents/photo/alpha/book01",
            },
            {
                "type": "image",
                "image": "contents/photo/alpha/book01/002.jpg",
                "thumbnail": "thumbnail/photo/alpha/book01/002.jpg",
                "html": "contents/photo/alpha/book01",
            },
        ]
        existing_map = {
            "photo/alpha/book01": maint_build_gallery_pages.compact_gallery_pages("photo/alpha/book01", old_pages)
        }

        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            contents_dir = site_dir / "contents"
            gallery_dir = contents_dir / "photo" / "alpha" / "book01"
            gallery_dir.mkdir(parents=True)
            (gallery_dir / "000_cover.jpg").write_bytes(b"jpeg")
            (gallery_dir / "002.jpg").write_bytes(b"jpeg")

            with (
                patch.object(maint_build_gallery_pages, "CONTENTS_DIR", str(contents_dir)),
                patch.object(maint_build_gallery_pages, "SITE_DIR", str(site_dir)),
                patch.object(maint_structure_lib, "CONTENTS_DIR", str(contents_dir)),
                patch.object(maint_build_gallery_pages, "load_existing_gallery_pages_map", return_value=existing_map),
                patch.object(maint_build_gallery_pages, "parse_history", return_value=HistoryData()),
            ):
                result, metadata = maint_build_gallery_pages.build_gallery_pages_map(structure, diff=True)

        self.assertTrue(metadata["incremental_mode"])
        self.assertEqual(result["photo/alpha/book01"]["p"][0][:2], ["i", "000_cover.jpg"])

    def test_compact_gallery_pages_strips_repeated_prefixes(self):
        pages = [
            {
                "type": "image",
                "image": "contents/photo/alpha/book01/001.jpg",
                "thumbnail": "thumbnail/photo/alpha/book01/001.jpg",
                "html": "contents/photo/alpha/book01",
            },
            {
                "type": "video",
                "video": "contents/photo/alpha/book01/clip.mp4",
                "html": "contents/photo/alpha/book01",
                "thumbNumber": 1,
                "label": "clip",
                "ext": "mp4",
            },
        ]

        compact = maint_build_gallery_pages.compact_gallery_pages("photo/alpha/book01", pages)

        self.assertEqual(compact["b"], "contents/photo/alpha/book01")
        self.assertEqual(compact["t"], "thumbnail/photo/alpha/book01")
        self.assertEqual(compact["p"][0], ["i", "001.jpg"])
        self.assertEqual(compact["p"][1], ["v", "clip.mp4", 1, "clip", "mp4"])

    def test_build_gallery_pages_map_main_runs_split_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "uc1-apply.jsonl"
            with (
                patch.object(build_gallery_pages_map, "build_structure_main", return_value=0) as mock_structure,
                patch.object(build_gallery_pages_map, "extract_archives_main", return_value=0) as mock_extract,
                patch.object(build_gallery_pages_map, "build_gallery_thumbnails_main", return_value=0) as mock_thumbs,
                patch.object(build_gallery_pages_map, "refresh_covers_main", return_value=0) as mock_covers,
                patch.object(build_gallery_pages_map, "build_structure_js_main", return_value=0) as mock_structure_js,
                patch.object(build_gallery_pages_map, "build_gallery_pages_main", return_value=0) as mock_gallery_pages,
                patch.object(build_gallery_pages_map, "build_site_config_main", return_value=0) as mock_site_config,
                patch.object(build_gallery_pages_map, "sync_history_main", return_value=0) as mock_history,
            ):
                rc = build_gallery_pages_map.main(["--metrics-log", str(metrics_path)])

        self.assertEqual(rc, 0)
        mock_structure.assert_called_once_with(["--sync"])
        mock_extract.assert_called_once_with([])
        mock_thumbs.assert_called_once_with([])
        mock_covers.assert_called_once_with([])
        mock_structure_js.assert_called_once_with([])
        mock_gallery_pages.assert_called_once_with([])
        mock_site_config.assert_called_once_with([])
        mock_history.assert_called_once_with([])

    def test_build_gallery_pages_map_plan_mode_does_not_execute_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "uc1-plan.jsonl"
            with (
                patch.object(build_gallery_pages_map, "build_structure_main", return_value=0) as mock_structure,
                patch.object(build_gallery_pages_map, "extract_archives_main", return_value=0) as mock_extract,
                patch.object(build_gallery_pages_map, "build_gallery_thumbnails_main", return_value=0) as mock_thumbs,
                patch.object(build_gallery_pages_map, "refresh_covers_main", return_value=0) as mock_covers,
                patch.object(build_gallery_pages_map, "build_structure_js_main", return_value=0) as mock_structure_js,
                patch.object(build_gallery_pages_map, "build_gallery_pages_main", return_value=0) as mock_gallery_pages,
                patch.object(build_gallery_pages_map, "build_site_config_main", return_value=0) as mock_site_config,
                patch.object(build_gallery_pages_map, "sync_history_main", return_value=0) as mock_history,
            ):
                rc = build_gallery_pages_map.main(["--plan", "--metrics-log", str(metrics_path)])

        self.assertEqual(rc, 0)
        mock_structure.assert_not_called()
        mock_extract.assert_not_called()
        mock_thumbs.assert_not_called()
        mock_covers.assert_not_called()
        mock_structure_js.assert_not_called()
        mock_gallery_pages.assert_not_called()
        mock_site_config.assert_not_called()
        mock_history.assert_not_called()

    def test_build_gallery_pages_map_writes_metrics_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "uc1-metrics.jsonl"
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = build_gallery_pages_map.main(["--plan", "--metrics-log", str(metrics_path)])

            self.assertEqual(rc, 0)
            self.assertTrue(metrics_path.is_file())
            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "uc1-maintenance")
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["success"], True)
            self.assertEqual(payload["schema"], "imviewer.m06.metrics.v1")

    def test_main_add_missing_series_writes_scaffold_entries(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {}
                }
            }
        }

        with patch.object(maint_build_structure, "load_structure", return_value=structure), patch.object(
            maint_build_structure, "scaffold_missing_series", return_value=(structure, [{"genre": "photo", "series": "beta", "path": "photo/beta", "count": 0}])
        ) as mock_scaffold, patch.object(maint_build_structure, "save_structure") as mock_save:
            rc = maint_build_structure.main(["--add-missing-series"])

        self.assertEqual(rc, 0)
        mock_scaffold.assert_called_once_with(structure, None)
        mock_save.assert_called_once_with(structure)

    def test_sync_structure_from_contents_adds_and_rebuilds(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
                        "alpha": {
                            "path": "photo/alpha",
                            "name": "alpha",
                            "series": "",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                            "contents": [{"path": "photo/alpha/old", "cover": "", "name": "old", "note": ""}],
                            "exturl": [],
                        }
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            (contents_dir / "photo" / "alpha").mkdir(parents=True)
            (contents_dir / "photo" / "beta").mkdir(parents=True)

            def _scan(series_path):
                if series_path == "photo/alpha":
                    return [{"path": "photo/alpha/book01", "cover": "", "name": "book01", "note": ""}]
                if series_path == "photo/beta":
                    return [{"path": "photo/beta/book02", "cover": "", "name": "book02", "note": ""}]
                return []

            with patch.object(maint_build_structure, "CONTENTS_DIR", str(contents_dir)), patch.object(
                maint_build_structure, "scan_contents_entries", side_effect=_scan
            ):
                updated, changed = maint_build_structure.sync_structure_from_contents(structure)

        self.assertIn("beta", updated["genres"]["photo"]["entries"])
        self.assertEqual(updated["genres"]["photo"]["entries"]["alpha"]["contents"], [{"path": "photo/alpha/book01", "cover": "", "name": "book01", "note": ""}])
        self.assertEqual(updated["genres"]["photo"]["entries"]["beta"]["contents"], [{"path": "photo/beta/book02", "cover": "", "name": "book02", "note": ""}])
        self.assertEqual(len(changed), 2)

    def test_refresh_content_covers_updates_structure_entries(self):
        structure = {
            "contents-root": "contents",
            "genres": {
                "photo": {
                    "name": "写真集",
                    "path": "photo",
                    "entries": {
                        "alpha": {
                            "path": "photo/alpha",
                            "name": "alpha",
                            "series": "",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                            "contents": [{"path": "photo/alpha/book01", "cover": "", "name": "book01", "note": ""}],
                            "exturl": [],
                        }
                    }
                }
            }
        }

        updated, changed = maint_refresh_covers.refresh_content_covers(structure)
        self.assertEqual(updated["genres"]["photo"]["entries"]["alpha"]["contents"][0]["cover"], "")
        self.assertEqual(changed, [])

        with patch.object(maint_refresh_covers, "find_cover_for_content", return_value="thumbnail/photo/alpha/book01/cover.jpg"):
            updated, changed = maint_refresh_covers.refresh_content_covers(structure)

        self.assertEqual(updated["genres"]["photo"]["entries"]["alpha"]["contents"][0]["cover"], "thumbnail/photo/alpha/book01/cover.jpg")
        self.assertEqual(changed[0]["path"], "photo/alpha/book01")

    def test_assign_gallery_thumbnail_refs_without_generation(self):
        pages = [
            {"type": "image", "image": "contents/photo/alpha/book01/001.jpg", "html": "contents/photo/alpha/book01"},
            {"type": "image", "image": "contents/photo/alpha/book01/002.jpg", "html": "contents/photo/alpha/book01"},
        ]

        generated, reused = maint_build_gallery_pages.assign_gallery_thumbnail_refs("photo/alpha/book01", pages, generate_files=False)

        self.assertEqual((generated, reused), (0, 0))
        self.assertEqual(pages[0]["thumbnail"], "thumbnail/photo/alpha/book01/001.jpg")
        self.assertEqual(pages[1]["thumbnail"], "thumbnail/photo/alpha/book01/002.jpg")

    def test_extract_archives_supports_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            contents_dir = Path(tmp) / "contents"
            archive_path = contents_dir / "photo" / "alpha" / "book01.zip"
            archive_path.parent.mkdir(parents=True)
            archive_path.write_bytes(b"PK")

            with patch.object(maint_extract_archives, "CONTENTS_DIR", str(contents_dir)), patch.object(
                maint_extract_archives, "extract_archive_pages_to_dir", return_value=[]
            ) as mock_extract:
                result = maint_extract_archives.extract_archives(str(contents_dir))

        self.assertEqual(result["unsupported"], [])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(result["extracted"], ["photo/alpha/book01_zip"])
        mock_extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()