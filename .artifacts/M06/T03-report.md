# T03 実装レポート

実施日: 2026-05-04
ブランチ: feature/M06-maintenance-speedup

## 概要

T03（既存データ移行）を実装した。

- `structure.json -> SQLite` の import CLI を追加
- `SQLite -> 生成用中間データ` の export CLI を追加
- `plan` / `dry-run` を先に実装し、非破壊で対象件数を確認できるようにした
- 既定の SQLite 配置先を `tools/sqlite/imviewer_maintenance.sqlite3` に変更した
- 主要項目（path/name/labels/persons/note/cover）の往復整合性テストを追加した

注意:
- 実DBの配置先は `tools/sqlite/imviewer_maintenance.sqlite3`
- `tools/sqlite/` は Git 管理外に設定済み

## 変更ファイル

- `tools/maint_db_transfer.py`
- `tools/maint_db_schema.py`
- `tests/test_m06_t03_db_transfer.py`
- `.specify/M06/tasks.md`

## 実装内容

### T03-01 structure.json -> SQLite import

新規CLI `tools/maint_db_transfer.py` に以下を追加。

- `import-plan`
- `import-dry-run`
- `import-apply`

import対象:

- genres
- series
- contents
- persons
- labels
- content_person_map
- content_label_map

設計方針:

- `plan` / `dry-run` は件数集計のみで書き込みを行わない
- `apply` は既存データを差し替える前提で関連テーブルを再投入する
- 既存DBがある場合はバックアップを作成可能
- entry に `cover` が未定義でも、import 時に補完せず往復整合性を優先する

### T03-02 SQLite -> 生成用中間データ export

同CLIに以下を追加。

- `export-plan`
- `export-dry-run`
- `export-apply`

export仕様:

- 出力先既定値は `.artifacts/M06/intermediate/structure_from_sqlite.json`
- `genres -> entries -> contents` の JSON を生成
- persons / labels は series 配下の content map から集約して復元
- `exturl` は現時点では空配列で出力

### T03-03 往復整合性テスト

新規テスト `tests/test_m06_t03_db_transfer.py` を追加。

検証内容:

1. `import-plan` / `import-dry-run` が DB ファイルを作成しない
2. `export-plan` / `export-dry-run` が出力ファイルを作成しない
3. 一時DBを使った `structure.json -> SQLite -> intermediate json` 往復で主要項目が一致する

比較対象の主要項目:

- `path`
- `name`
- `series`
- `labels`
- `persons`
- `note`
- `cover`
- `contents[*].path/name/note/cover`

## テスト結果

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_m06_t02_db_schema tests.test_m06_t03_db_transfer
```

結果:

- Ran 6 tests
- OK

補足:

- T02 既存テストも同時に実行し、DBパス変更の影響がないことを確認した

## 計測結果

### 実データ `import-plan`

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_db_transfer.py import-plan --structure site/structure.json --db tools/sqlite/imviewer_maintenance.sqlite3 --metrics-log .artifacts/M06/metrics/m06-t03-structure-import-real.jsonl
```

結果:

- `db_exists`: false
- `target_counts.genres`: 2
- `target_counts.series`: 4
- `target_counts.contents`: 27
- `entries_without_contents`: 0
- `duration_ms`: 0（run total）
- `build_import_plan.duration_ms`: 52
- `transfer_files`: 0
- `transfer_bytes`: 0

ログ保存先:

- `.artifacts/M06/metrics/m06-t03-structure-import-real.jsonl`

### 実データ `import-apply`

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_db_transfer.py import-apply --structure site/structure.json --db tools/sqlite/imviewer_maintenance.sqlite3 --metrics-log .artifacts/M06/metrics/m06-t03-structure-import-real.jsonl
```

結果:

- `existing_counts.genres`: 2
- `existing_counts.series`: 4
- `existing_counts.contents`: 27
- `target_counts.genres`: 2
- `target_counts.series`: 4
- `target_counts.contents`: 27
- `Applied import`: `series=4`, `contents=27`
- `duration_ms`: 495
- `transfer_files`: 1
- `transfer_bytes`: 176128

### 実データ `export-apply`

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_db_transfer.py export-apply --db tools/sqlite/imviewer_maintenance.sqlite3 --output .artifacts/M06/intermediate/structure_from_sqlite.json --metrics-log .artifacts/M06/metrics/m06-t03-structure-export-real.jsonl
```

結果:

- `counts.genres`: 2
- `counts.series`: 4
- `counts.contents`: 27
- `output_bytes`: 12017
- `duration_ms`: 54
- `transfer_files`: 1
- `transfer_bytes`: 12017

ログ保存先:

- `.artifacts/M06/metrics/m06-t03-structure-export-real.jsonl`
- `.artifacts/M06/intermediate/structure_from_sqlite.json`

### テスト内 `apply` 計測

ログ保存先:

- `.artifacts/M06/metrics/m06-t03-structure-import.jsonl`
- `.artifacts/M06/metrics/m06-t03-structure-export.jsonl`

最新の往復テスト実行ログ要約:

- import apply
  - `series`: 2
  - `contents`: 3
  - `duration_ms`: 11
  - `transfer_files`: 1
  - `transfer_bytes`: 163840
- export apply
  - `generated_count`: 5
  - `duration_ms`: 2
  - `transfer_files`: 1
  - `transfer_bytes`: 1668

## 受け入れ条件確認

- 主要項目（path/name/labels/persons/note/cover）が欠落なく往復できる: OK
- テストで差分を検出できる: OK

## 実施後確認

- 実DBからの export でも `genres=2`, `series=4`, `contents=27` を確認
- 出力JSONの構造は `genres -> entries -> contents` を維持
- 現在の実データでは `persons` / `labels` は 0 件
