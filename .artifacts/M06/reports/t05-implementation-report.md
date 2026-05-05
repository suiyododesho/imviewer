# M06 T05 Implementation Report

Date: 2026-05-04

## Scope

Implemented T05 only:

- T05-01 DB-origin structure artifact generation
- T05-02 Split gallery-pages generation (genre/series units)
- T05-03 Compatibility output retention (single gallery-pages.js)

## Changed Files

- tools/maint_build_site_artifacts.py
- tools/maint_build_gallery_pages.py
- tests/test_m06_t05_site_artifacts.py
- .specify/M06/tasks.md
- .artifacts/M06/metrics/t05-site-artifacts-plan.jsonl

## Implementation Summary

### 1) New T05 CLI

Added `tools/maint_build_site_artifacts.py` with explicit command split:

- `plan` / `dry-run`: non-destructive planning only
- `apply`: writes artifacts

Key options:

- `--db`
- `--site-dir`
- `--gallery-output {compat,split,both}`
- `--metrics-log`

### 2) DB-origin artifact generation

Plan/apply now export structure data from SQLite and generate:

- `site/structure.json`
- `site/js/structure.js`

### 3) gallery-pages split generation + compatibility mode

From the same DB-origin structure payload:

- compatibility output
  - `site/js/gallery-pages.js`
- split outputs
  - `site/js/gallery-pages/manifest.js`
  - `site/js/gallery-pages/chunks/<genre>/<series>.js`

`apply` in split modes removes the previous split directory before writing, to avoid stale chunk files.

### 4) Reuse of existing renderer

Refactored `tools/maint_build_gallery_pages.py` to expose reusable text rendering:

- `render_gallery_pages_js(result)`

This avoids duplicated JS emission logic across tools.

## Test Results

Executed:

- `d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_m06_t05_site_artifacts`

Result:

- 3 tests run
- all passed

Covered checks:

- `plan` / `dry-run` do not write artifacts
- `apply` writes compat + split outputs
- split chunk max size is smaller than compat payload in plan report

## Measurement Results

Executed non-destructive measurement command:

- `d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_build_site_artifacts.py plan --db tools/sqlite/imviewer_maintenance.sqlite3 --site-dir site --gallery-output both --metrics-log .artifacts/M06/metrics/t05-site-artifacts-plan.jsonl`

Observed plan payload summary:

- scanned_count: 31
- generated_count: 8 planned files
- gallery_count: 27
- page_count: 4744
- split_chunk_count: 4
- compat_gallery_pages_bytes: 136110
- max_split_chunk_bytes: 83257
- min_split_chunk_bytes: 3601

Saved metrics log:

- `.artifacts/M06/metrics/t05-site-artifacts-plan.jsonl`

## tasks.md Reflection

Updated T05 checklist to completed:

- T05-01 [x]
- T05-02 [x]
- T05-03 [x]
