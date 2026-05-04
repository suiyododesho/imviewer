"""Tests for T06 NAS sync manifest generation and apply."""

import json
import tempfile
import unittest
from pathlib import Path

from tools import maint_sync_nas
from tools.maint_sync_nas import (
    SyncManifest,
    apply_manifest,
    build_manifest,
    print_plan,
)


class M06T06NasSyncTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_dir(self, tmp: Path, name: str, files: dict[str, bytes]) -> Path:
        """Create a directory with the given files {rel_path: content}."""
        d = tmp / name
        for rel, data in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return d

    # ------------------------------------------------------------------
    # T06-01 / T06-03: plan / dry-run shows correct manifest
    # ------------------------------------------------------------------

    def test_plan_detects_new_and_changed_files(self):
        """build_manifest correctly identifies new and changed files."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {
                "a.txt": b"hello",
                "sub/b.txt": b"world",
                "sub/c.txt": b"same",
            })
            dst = self._make_dir(tmp, "dst", {
                "sub/b.txt": b"DIFFERENT",  # changed
                "sub/c.txt": b"same",       # identical — skip
                # a.txt is absent in dest → new
            })

            manifest = build_manifest(src, dst)

        self.assertEqual(manifest.scanned_source_count, 3)
        self.assertEqual(manifest.scanned_dest_count, 2)
        self.assertEqual(manifest.copy_count, 2)

        reasons = {e.rel_path: e.reason for e in manifest.entries}
        self.assertEqual(reasons.get("a.txt"), "new")
        self.assertEqual(reasons.get("sub/b.txt"), "changed")
        self.assertNotIn("sub/c.txt", reasons)

    def test_plan_empty_when_source_equals_dest(self):
        """No entries when source and dest are byte-for-byte identical."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {
                "js/structure.js": b"var x=1;",
                "structure.json": b'{"a":1}',
            })
            # Copy to dest
            import shutil
            dst = tmp / "dst"
            shutil.copytree(src, dst)

            manifest = build_manifest(src, dst)

        self.assertEqual(manifest.copy_count, 0)
        self.assertEqual(manifest.copy_bytes, 0)

    def test_dry_run_does_not_write_files(self):
        """plan/dry-run: no files are written to dest."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {"new.txt": b"content"})
            dst = tmp / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            # Assert plan shows 1 file
            self.assertEqual(manifest.copy_count, 1)
            # Dest should still be empty (no apply called)
            self.assertEqual(list(dst.rglob("*")), [])

    # ------------------------------------------------------------------
    # T06-02: apply copies files correctly
    # ------------------------------------------------------------------

    def test_apply_copies_new_and_changed_files(self):
        """apply_manifest writes all entries from source to dest."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {
                "a.txt": b"hello",
                "sub/b.txt": b"world",
                "sub/c.txt": b"same",
            })
            dst = self._make_dir(tmp, "dst", {
                "sub/b.txt": b"DIFFERENT",
                "sub/c.txt": b"same",
            })

            manifest = build_manifest(src, dst)
            self.assertEqual(manifest.copy_count, 2)

            result = apply_manifest(manifest)

            self.assertEqual(result["copied"], 2)
            self.assertEqual(result["errors"], [])

            # Verify files on disk (must be checked inside the with block)
            dst_a = dst / "a.txt"
            dst_b = dst / "sub" / "b.txt"
            self.assertTrue(dst_a.exists())
            self.assertEqual(dst_a.read_bytes(), b"hello")
            self.assertEqual(dst_b.read_bytes(), b"world")

    def test_apply_creates_subdirectories(self):
        """apply_manifest creates missing parent directories in dest."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {
                "deep/nested/file.txt": b"data",
            })
            dst = tmp / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            apply_manifest(manifest)

            dest_file = dst / "deep" / "nested" / "file.txt"
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.read_bytes(), b"data")

    # ------------------------------------------------------------------
    # Manifest serialization round-trip
    # ------------------------------------------------------------------

    def test_manifest_roundtrip(self):
        """SyncManifest serializes to dict and back without data loss."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._make_dir(tmp, "src", {"x.js": b"var x=42;"})
            dst = tmp / "dst"
            dst.mkdir()

            manifest = build_manifest(src, dst)
            d = manifest.to_dict()
            restored = SyncManifest.from_dict(d)

        self.assertEqual(manifest.copy_count, restored.copy_count)
        self.assertEqual(manifest.copy_bytes, restored.copy_bytes)
        self.assertEqual(len(manifest.entries), len(restored.entries))
        self.assertEqual(manifest.entries[0].rel_path, restored.entries[0].rel_path)
        self.assertEqual(manifest.entries[0].src_hash, restored.entries[0].src_hash)


if __name__ == "__main__":
    unittest.main()
