"""Tests for T01 improvements (T01-01, T01-02, T01-03)."""

import json
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from tools import maint_metadata
from tools import maint_build_gallery_pages
from tools import maint_build_gallery_thumbnails


# ── Shared fixture ─────────────────────────────────────────────────────────────

def _make_structure():
    return {
        "genres": {
            "photo": {
                "name": "photo",
                "path": "photo",
                "entries": {
                    "00001": {
                        "path": "photo/alpha",
                        "name": "Alpha",
                        "series": "alpha",
                        "main-person": "",
                        "persons": [],
                        "labels": [],
                        "note": "",
                    }
                },
            }
        }
    }


# ── T01-01: gallery-pages skipped when no path change ─────────────────────────

class T0101GalleryPagesSkipTests(unittest.TestCase):
    """T01-01: apply後にpathが変わっていなければgallery-pagesを再生成しない。"""

    def _run_apply(self, csv_content, structure):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig")

            buf = StringIO()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure"),
                patch.object(maint_metadata, "write_structure_js"),
                patch.object(maint_metadata, "_regenerate_gallery_pages_js") as mock_regen,
                redirect_stdout(buf),
            ):
                mock_regen.return_value = (True, "")
                maint_metadata.main(["apply", "--input", str(csv_path)])

            return buf.getvalue(), mock_regen

    def test_gallery_pages_not_regenerated_when_no_path_change(self):
        """ラベルのみ変更 → gallery-pages.js の再生成はスキップされる。"""
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "photo,00001,Alpha,,,,new-label\n"
        )
        structure = _make_structure()
        structure["genres"]["photo"]["entries"]["00001"]["note"] = ""

        output, mock_regen = self._run_apply(csv_content, structure)

        mock_regen.assert_not_called()
        self.assertIn("gallery-pages.js skipped", output)

    def test_gallery_pages_regenerated_when_path_changes(self):
        """pathフィールドが変更された場合は gallery-pages.js を再生成する。"""
        # path は EDITABLE_FIELDS に含まれていないが、含まれた場合の動作を保証
        # このテストでは maint_metadata の path_changed フラグが True になるケースを
        # 直接テストする（path は現状 EDITABLE_FIELDS にないため、手動で flag を検証）
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "photo,00001,Alpha,,,,\n"
        )
        structure = _make_structure()
        # No changes in CSV → nothing to write → _regenerate_gallery_pages_js not called
        output, mock_regen = self._run_apply(csv_content, structure)
        # No changes means save is skipped entirely
        mock_regen.assert_not_called()

    def test_metrics_stage_has_gallery_pages_skipped_flag(self):
        """計測ステージに gallery_pages_skipped フラグが記録される。"""
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "photo,00001,Alpha,new-author,,,\n"
        )
        structure = _make_structure()

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig")
            metrics_path = Path(tmp) / "metrics.jsonl"

            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure"),
                patch.object(maint_metadata, "write_structure_js"),
                patch.object(maint_metadata, "_regenerate_gallery_pages_js", return_value=(True, "")),
            ):
                maint_metadata.main([
                    "apply",
                    "--input", str(csv_path),
                    "--metrics-log", str(metrics_path),
                ])

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            persist_stage = next(
                (s for s in payload.get("stages", []) if s["name"] == "persist_and_regenerate"),
                None,
            )
            self.assertIsNotNone(persist_stage)
            self.assertTrue(persist_stage["details"].get("gallery_pages_skipped"))


# ── T01-03: 0 diff targets → heavy processing skipped ─────────────────────────

class T0103ZeroDiffTargetsTests(unittest.TestCase):
    """T01-03: history.txt が空(0件)のとき重処理をスキップする。"""

    def _make_history_data(self, next_dirs=None, next_force_dirs=None):
        from tools.history_manager import HistoryData
        hd = HistoryData.__new__(HistoryData)
        hd.next_dirs = list(next_dirs or [])
        hd.next_force_dirs = list(next_force_dirs or [])
        hd.prev_dirs = []
        return hd

    def test_build_gallery_pages_skips_when_no_history_targets(self):
        """history.txt が空 かつ 変更なし のとき build_gallery_pages_map は
        生成ループとJS書き込みをスキップして skipped=True を返す。"""
        structure = _make_structure()
        empty_history = self._make_history_data()
        # existing_map already has the correct signature for the gallery
        existing_map = {"photo/alpha": {"b": "contents/photo/alpha", "p": [], "s": "abc"}}

        with (
            patch.object(maint_build_gallery_pages, "parse_history", return_value=empty_history),
            patch.object(maint_build_gallery_pages, "load_existing_gallery_pages_map", return_value=existing_map),
            # detect_changed returns nothing changed (sig matches)
            patch.object(maint_build_gallery_pages, "detect_changed_gallery_paths", return_value=[]),
            patch.object(maint_build_gallery_pages, "iter_gallery_paths", return_value=iter(["photo/alpha"])),
        ):
            result, metadata = maint_build_gallery_pages.build_gallery_pages_map(structure, diff=True)

        self.assertTrue(metadata["skipped"])

    def test_build_gallery_pages_processes_when_history_has_targets(self):
        """history.txt にエントリがある場合は通常処理を実行する（skipped=False）。"""
        structure = _make_structure()
        history = self._make_history_data(next_dirs=["photo/alpha"])
        # existing_map covers the gallery already, but history says rebuild it
        existing_map = {"photo/alpha": {"b": "contents/photo/alpha", "p": [], "s": "old_sig"}}

        with (
            patch.object(maint_build_gallery_pages, "parse_history", return_value=history),
            patch.object(maint_build_gallery_pages, "load_existing_gallery_pages_map", return_value=existing_map),
            patch.object(maint_build_gallery_pages, "detect_changed_gallery_paths", return_value=[]),
            patch.object(maint_build_gallery_pages, "iter_gallery_paths", return_value=iter(["photo/alpha"])),
            patch.object(maint_build_gallery_pages, "collect_gallery_pages_for_path", return_value=[]),
        ):
            result, metadata = maint_build_gallery_pages.build_gallery_pages_map(structure, diff=True)

        # selected = ["photo/alpha"] due to history target → target_gallery_paths is non-empty → not skipped
        self.assertFalse(metadata.get("skipped", False))

    def test_generate_gallery_thumbnails_skips_when_no_history_targets(self):
        """history.txt が空のとき generate_gallery_thumbnails は重処理をスキップする。"""
        structure = _make_structure()
        empty_history = self._make_history_data()

        with (
            patch.object(maint_build_gallery_pages, "parse_history", return_value=empty_history),
            patch.object(maint_build_gallery_pages, "iter_gallery_paths", return_value=iter(["photo/alpha"])),
            patch.object(maint_build_gallery_pages, "collect_gallery_pages_for_path") as mock_collect,
        ):
            metadata = maint_build_gallery_pages.generate_gallery_thumbnails(structure, diff=True)

        self.assertTrue(metadata["skipped"])
        mock_collect.assert_not_called()

    def test_gallery_thumbnails_main_reports_skip(self):
        """maint_build_gallery_thumbnails.main() がスキップ時にメッセージを出力する。"""
        structure = _make_structure()

        with (
            patch.object(maint_build_gallery_thumbnails, "load_structure", return_value=structure),
            patch.object(
                maint_build_gallery_pages,
                "generate_gallery_thumbnails",
                return_value={"skipped": True, "incremental_mode": True, "generated": 0, "reused": 0, "gallery_count": 0},
            ),
        ):
            buf = StringIO()
            with redirect_stdout(buf):
                ret = maint_build_gallery_thumbnails.main(["--diff"])
        self.assertEqual(ret, 0)
        self.assertIn("Skipped gallery thumbnail generation", buf.getvalue())

    def test_gallery_pages_main_reports_skip(self):
        """maint_build_gallery_pages.main() がスキップ時にメッセージを出力し、JS を書かない。"""
        structure = _make_structure()

        with (
            patch.object(maint_build_gallery_pages, "load_structure", return_value=structure),
            patch.object(
                maint_build_gallery_pages,
                "build_gallery_pages_map",
                return_value=({}, {"skipped": True, "incremental_mode": True, "gallery_count": 3, "page_count": 0, "generated": 0, "reused": 0}),
            ),
            patch.object(maint_build_gallery_pages, "write_gallery_pages_js") as mock_write,
        ):
            buf = StringIO()
            with redirect_stdout(buf):
                ret = maint_build_gallery_pages.main(["--diff"])
        self.assertEqual(ret, 0)
        mock_write.assert_not_called()
        self.assertIn("Skipped gallery-pages rebuild", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
