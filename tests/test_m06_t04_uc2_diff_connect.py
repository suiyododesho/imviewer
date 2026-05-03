import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import maint_metadata


class M06T04Uc2DiffConnectTests(unittest.TestCase):
    def test_plan_filters_metadata_targets_by_diff_targets_file(self):
        csv_content = (
            "genre,entry_key,name,main-person,persons,labels,note\n"
            "comic,00001,Series A,author-a,person-a,label-a,note-a\n"
            "comic,00002,Series B,author-b,person-b,label-b,note-b\n"
        )
        structure = {
            "genres": {
                "comic": {
                    "name": "comic",
                    "path": "comic",
                    "entries": {
                        "00001": {
                            "name": "Series A",
                            "series": "series-a",
                            "path": "comic/series-a",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                        },
                        "00002": {
                            "name": "Series B",
                            "series": "series-b",
                            "path": "comic/series-b",
                            "main-person": "",
                            "persons": [],
                            "labels": [],
                            "note": "",
                        },
                    },
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "metadata.csv"
            csv_path.write_text(csv_content, encoding="utf-8-sig")
            targets_path = Path(tmp) / "targets.txt"
            targets_path.write_text("comic/series-a\n", encoding="utf-8")
            metrics_path = Path(tmp) / "uc2-plan.jsonl"

            stream = io.StringIO()
            with (
                patch.object(maint_metadata, "load_structure", return_value=structure),
                patch.object(maint_metadata, "save_structure") as mock_save,
                redirect_stdout(stream),
            ):
                maint_metadata.main(
                    [
                        "plan",
                        "--input",
                        str(csv_path),
                        "--diff-targets-file",
                        str(targets_path),
                        "--metrics-log",
                        str(metrics_path),
                    ]
                )

            mock_save.assert_not_called()
            output = stream.getvalue()
            self.assertIn("1 entries would be updated", output)
            self.assertIn("1 skipped by diff filter", output)

            payload = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            stage = next(item for item in payload["stages"] if item["name"] == "apply_metadata_to_structure")
            self.assertEqual(stage["generated_count"], 1)


if __name__ == "__main__":
    unittest.main()
