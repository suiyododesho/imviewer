# M06 T04 実装レポート

作成日: 2026-05-04
担当: Copilot (GPT-5.3-Codex)

## 対象

- T04-01 series 単位 fingerprint 定義
- T04-02 変更 series のみ再処理する判定器を実装
- T04-03 plan コマンドで「対象・理由」を表示

## 実装内容

1. `tools/maint_series_diff.py` を拡張
- `plan` / `dry-run` / `apply` を実装
- SQLite の canonical データから series fingerprint (SHA-256) を算出
- `series.fingerprint` との比較で差分対象を抽出
- 理由を `missing_fingerprint` / `fingerprint_changed` で出力
- `apply` は DB更新前バックアップ作成、トランザクション更新、失敗時のバックアップ復元（rollback前提）を実装
- `--diff` 指定で対象 series path の絞り込みに対応
- `--output-targets` で差分対象パスをファイル出力可能
- `--write-history-targets` で `history.txt` の `next.force_dirs` に差分対象を連携（UC1 diff入力へ接続）
- `RunMetrics` で `.artifacts/M06/metrics/` に計測を記録

2. `tools/maint_metadata.py` を拡張（UC2接続）
- `apply` / `plan` に `--diff-targets-file` を追加
- T04で出力した差分対象パスファイルを読み込み、対象seriesの行のみ適用/計画

3. テスト追加/更新
- `tests/test_m06_t04_series_diff.py`
  - plan/dry-run 非破壊
  - fingerprint changed / unchanged 判定
  - applyでfingerprint更新・backup作成・targets出力・history連携
  - apply失敗時のrollback復元
- `tests/test_m06_t04_uc2_diff_connect.py`
  - UC2 plan が `--diff-targets-file` で対象行を絞り込むこと

4. `.specify/M06/tasks.md` 更新
- T04-01, T04-02, T04-03 を完了 (`[x]`) に変更

## 変更ファイル

- `tools/maint_series_diff.py` (updated)
- `tools/maint_metadata.py` (updated)
- `tests/test_m06_t04_series_diff.py` (updated)
- `tests/test_m06_t04_uc2_diff_connect.py` (new)
- `.specify/M06/tasks.md` (updated)

## テスト結果

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_m06_t04_series_diff tests.test_m06_t04_uc2_diff_connect
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_maint_metadata_metrics tests.test_t01_improvements
```

結果:
- Ran 5 tests in 0.707s
- Ran 9 tests in 0.045s
- OK

## 計測結果

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_series_diff.py plan --metrics-log .artifacts/M06/metrics/m06-t04-series-diff.jsonl
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_series_diff.py dry-run --metrics-log .artifacts/M06/metrics/m06-t04-series-diff.jsonl
```

計測ログ:
- `.artifacts/M06/metrics/m06-t04-series-diff.jsonl`

最新2回の主な値:
- scanned_count: 4 -> 4
- generated_count: 4 -> 4
- transfer_files: 0 -> 0
- transfer_bytes: 0 -> 0
- compare delta: duration_ms=0, generated=0, transfer_files=0, transfer_bytes=0

## 接続方法（UC1/UC2）

- UC1（既存 diff 入力）
  - `maint_series_diff.py plan/apply --write-history-targets` で `history.txt next.force_dirs` に反映
  - 既存の `maint_build_gallery_pages.py --diff` / `maint_build_gallery_thumbnails.py --diff` がそのまま利用可能

- UC2（既存 metadata apply フロー）
  - `maint_series_diff.py plan/apply --output-targets <file>` で差分対象ファイルを生成
  - `maint_metadata.py plan/apply --diff-targets-file <file>` で対象を絞って適用
