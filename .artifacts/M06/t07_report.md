# T07 Implementation Report

Date: 2026-05-04
Task: T07 (UC1/UC2 unified CLI)

## 1) Changed files

- .specify/M06/tasks.md
- .specify/spec_renewal.md
- tools/maint_uc_cli.py
- tools/maintenance.bat
- tools/maintenance_manual.md
- tests/test_m06_t07_uc_cli.py
- .artifacts/M06/metrics/t07-uc1-plan.jsonl
- .artifacts/M06/metrics/t07-uc2-plan.jsonl
- .artifacts/M06/state/t07-uc-cli-state.jsonl
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t03-import-plan.log
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t04-series-diff-plan.log
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t05-site-artifacts-plan.log
- .artifacts/M06/logs/20260504_191423_8050f97b30_uc2-metadata-plan.log

## 2) Test results

Executed command:

- d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests/test_m06_t07_uc_cli.py

Result summary:

- Ran: 4 tests
- Passed: 4
- Failed: 0
- Total duration: about 1.9s

Covered cases:

- UC1 plan works and does not write site outputs
- UC2 validate path and plan path work
- apply requires explicit --approve
- rollback restores DB from latest backup

## 3) Measurement results (plan-only)

Executed commands:

- d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py --metrics-log .artifacts/M06/metrics/t07-uc1-plan.jsonl plan uc1
- d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py --metrics-log .artifacts/M06/metrics/t07-uc2-plan.jsonl plan uc2

UC1 plan metrics (.artifacts/M06/metrics/t07-uc1-plan.jsonl):

- success: true
- total duration_ms: 2016
- stages:
  - t03-import-plan: 292 ms
  - t04-series-diff-plan: 215 ms
  - t05-site-artifacts-plan: 1472 ms
- transfer_files: 0
- transfer_bytes: 0

UC2 plan metrics (.artifacts/M06/metrics/t07-uc2-plan.jsonl):

- success: true
- total duration_ms: 180
- stages:
  - uc2-metadata-plan: 179 ms
- transfer_files: 0
- transfer_bytes: 0

## 4) Scope guard

- This implementation adds/updates T07-related CLI/menu/docs/tests only.
- No destructive apply execution was performed during measurement/reporting.
- apply command is implemented with explicit safety gate (--approve) and maintenance.bat confirmation prompts.
