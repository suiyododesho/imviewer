import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import maint_metadata


class MaintMetadataMetricsTests(unittest.TestCase):
    def test_plan_command_writes_metrics_without_saving_structure(self):
        csv_content = "genre,entry_key,name,main-person,persons,labels,note\nphoto,00001,Alpha,,,,'\n"
        structure = {
            "genres": {
                "photo": {
                    "name": "photo",
                    "path": "photo",
                    "entries": {
                        "00001": {
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

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig")
            metrics_path = Path(tmp) / "uc2-plan.jsonl"

            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
            ):
                maint_metadata.main(["plan", "--input", str(csv_path), "--metrics-log", str(metrics_path)])

            mock_save.assert_not_called()
            self.assertTrue(metrics_path.is_file())
            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(payload["pipeline"], "uc2-metadata-apply")
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["success"], True)


if __name__ == "__main__":
    unittest.main()
