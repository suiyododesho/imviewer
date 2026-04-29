import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.history_manager import parse_history, write_history, HistoryData


class HistoryForceDirsTests(unittest.TestCase):
    def test_parse_next_force_dirs(self):
        raw = textwrap.dedent(
            """
            next:
              force_dirs:
                - photo/naked-cherry-css
              dirs:
                - photo/naked-cherry01/桜亜美利
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.txt"
            path.write_text(raw, encoding="utf-8")
            data = parse_history(str(path))

        self.assertEqual(data.next_force_dirs, ["photo/naked-cherry-css"])
        self.assertEqual(data.next_dirs, ["photo/naked-cherry01/桜亜美利"])

    def test_write_history_preserves_force_dirs(self):
        data = HistoryData()
        data.next_force_dirs = ["photo/naked-cherry-css"]
        data.next_dirs = ["photo/naked-cherry01/桜亜美利"]
        data.versions = [
            {
                "key": "v1.2",
                "released": "2026-04-11 12:00:00",
                "force_dirs": ["photo/extra-css"],
                "dirs": ["photo/example/item"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.txt"
            write_history(str(path), data)
            written = path.read_text(encoding="utf-8")

        self.assertIn("force_dirs:", written)
        self.assertIn("- photo/naked-cherry-css", written)
        self.assertIn("- photo/extra-css", written)

    def test_write_history_keeps_empty_force_dirs_headers(self):
        data = HistoryData()
        data.next_dirs = ["photo/girly-daze/櫻井美優"]
        data.versions = [
            {
                "key": "v1.2",
                "released": "2026-04-11 12:00:00",
                "force_dirs": [],
                "dirs": ["photo/example/item"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.txt"
            write_history(str(path), data)
            written = path.read_text(encoding="utf-8")

        self.assertIn("next:\n  force_dirs:\n  dirs:\n    - photo/girly-daze/櫻井美優\n", written)
        self.assertIn("v1.2:\n  released: 2026-04-11 12:00:00\n  force_dirs:\n  dirs:\n    - photo/example/item\n", written)


if __name__ == "__main__":
    unittest.main()
