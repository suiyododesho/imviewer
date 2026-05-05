# M06 T00 Report (2026-05-03)

## Scope
- Implemented only T00 (measurement foundation).
- Added plan/dry-run flow first.
- Executed UC1/UC2 apply after approval and appended measured logs.

## Changed Files
- tools/maint_metrics.py
- tools/build_gallery_pages_map.py
- tools/maint_metadata.py
- tests/test_maint_build_structure.py
- tests/test_maint_metadata_metrics.py
- .specify/M06/tasks.md

## Implementation Summary
- Added reusable metrics module (`imviewer.m06.metrics.v1`) with:
  - run/stage timing (`duration_ms`)
  - count metrics (`scanned_count`, `generated_count`)
  - transfer metrics (`transfer_files`, `transfer_bytes`)
  - before/after compare block using previous JSONL record (`compare.delta_*`)
- UC1 (`tools/build_gallery_pages_map.py`):
  - Added `--plan` / `--dry-run` / `--metrics-log`
  - `--plan` prints planned stages only and writes metrics log
  - Apply path now records per-step metrics
- UC2 (`tools/maint_metadata.py`):
  - Added `plan` subcommand (alias of apply dry-run)
  - Added `--metrics-log` to `export` / `apply` / `plan`
  - Added staged metrics for CSV load and metadata apply/persist

## Test Results
Command:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_maint_build_structure tests.test_maint_metadata_metrics
```

Result:
- Passed: 23
- Failed: 0
- Errors: 0

## Measurement Results (Plan/Dry-run)
### UC1 plan
Command:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/build_gallery_pages_map.py --plan --metrics-log .artifacts/M06/metrics/t00_uc1_plan.jsonl
```

Log:
- .artifacts/M06/metrics/t00_uc1_plan.jsonl
- totals: scanned_count=0, generated_count=0, transfer_files=0, transfer_bytes=0, duration_ms=0
- planned stages: 8

### UC2 plan (dry-run)
Command:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_metadata.py plan --input tools/metadata.csv --metrics-log .artifacts/M06/metrics/t00_uc2_plan.jsonl
```

Log:
- .artifacts/M06/metrics/t00_uc2_plan.jsonl
- totals: scanned_count=6, generated_count=0, transfer_files=0, transfer_bytes=0, duration_ms=57
- stage breakdown:
  - load_csv: duration_ms=1, scanned_count=3
  - apply_metadata_to_structure: duration_ms=55, scanned_count=3, changed=0

## Measurement Results (Apply with before/after compare)
### UC1 apply
Commands:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/build_gallery_pages_map.py --metrics-log .artifacts/M06/metrics/t00_uc1_apply.jsonl
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/build_gallery_pages_map.py --metrics-log .artifacts/M06/metrics/t00_uc1_apply.jsonl
```

Log:
- .artifacts/M06/metrics/t00_uc1_apply.jsonl
- 1st apply totals: duration_ms=45043, scanned_count=84782, generated_count=348, transfer_files=348, transfer_bytes=54261873
- 2nd apply totals: duration_ms=12281, scanned_count=85640, generated_count=5, transfer_files=5, transfer_bytes=171566
- compare (2nd vs 1st): delta_duration_ms=-32762, delta_generated_count=-343, delta_transfer_files=-343, delta_transfer_bytes=-54090307

### UC2 apply
Commands:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_metadata.py apply --input tools/metadata.csv --metrics-log .artifacts/M06/metrics/t00_uc2_apply.jsonl
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_metadata.py apply --input tools/metadata.csv --metrics-log .artifacts/M06/metrics/t00_uc2_apply.jsonl
```

Log:
- .artifacts/M06/metrics/t00_uc2_apply.jsonl
- 1st apply totals: duration_ms=1, scanned_count=6, generated_count=0, transfer_files=0, transfer_bytes=0
- 2nd apply totals: duration_ms=0, scanned_count=6, generated_count=0, transfer_files=0, transfer_bytes=0
- compare (2nd vs 1st): delta_duration_ms=-1, delta_generated_count=0, delta_transfer_files=0, delta_transfer_bytes=0

## Tasks.md Reflection
- T00-01: completed
- T00-02: completed
- T00-03: completed
