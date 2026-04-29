import tempfile
import unittest
from pathlib import Path

from tools import build_gallery_pages_map


class GalleryDiffBuildTests(unittest.TestCase):
    def test_select_gallery_paths_for_diff_matches_parent_or_child_dirs(self):
        gallery_paths = [
            "photo/honey2/A/index.html",
            "photo/honey2/B/index.html",
            "photo/honey3/C/index.html",
        ]

        selected = build_gallery_pages_map.select_gallery_paths_for_diff(
            gallery_paths,
            ["photo/honey2/A", "photo/honey3"],
        )

        self.assertEqual(
            selected,
            ["photo/honey2/A/index.html", "photo/honey3/C/index.html"],
        )

    def test_load_existing_gallery_pages_map_from_js(self):
        content = (
            "/** test */\n"
            "window.galleryPagesMap = {\"photo/a/index.html\":[{\"type\":\"image\"}]};\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gallery-pages.js"
            path.write_text(content, encoding="utf-8")
            loaded = build_gallery_pages_map.load_existing_gallery_pages_map(str(path))

        self.assertIsInstance(loaded, dict)
        self.assertIn("photo/a/index.html", loaded)


if __name__ == "__main__":
    unittest.main()
