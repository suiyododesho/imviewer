# T09 Implementation Report

Date: 2026-05-05
Task: T09 (品質保証と復旧)

## 1) Changed files

### New files
- tests/test_m06_t09_failure_injection.py

### Modified files
- tools/maintenance_manual.md  (T09-03: 障害復旧手順セクション追加)
- .specify/M06/tasks.md  (T09チェック反映)

### Deleted files (T09-04: 検証用中間生成物の削除)
- .artifacts/M06/metrics/m06-t02-sqlite-schema.jsonl
- .artifacts/M06/metrics/m06-t02-sqlite-schema-real.jsonl
- .artifacts/M06/metrics/m06-t03-structure-export.jsonl
- .artifacts/M06/metrics/m06-t03-structure-export-real.jsonl
- .artifacts/M06/metrics/m06-t03-structure-export-real2.jsonl
- .artifacts/M06/metrics/m06-t03-structure-import.jsonl
- .artifacts/M06/metrics/m06-t03-structure-import-real.jsonl
- .artifacts/M06/metrics/m06-t03-structure-import-real2.jsonl
- .artifacts/M06/metrics/m06-t04-series-diff.jsonl
- .artifacts/M06/metrics/m06-t05-site-artifacts.jsonl
- .artifacts/M06/intermediate/structure_from_sqlite.json
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t03-import-plan.log
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t04-series-diff-plan.log
- .artifacts/M06/logs/20260504_191417_d8e3f6826c_t05-site-artifacts-plan.log
- .artifacts/M06/logs/20260504_191423_8050f97b30_uc2-metadata-plan.log

## 2) Test results

### T09専用テスト

Executed command:
```
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests.test_m06_t09_failure_injection -v
```

Result summary:
- Ran: 15 tests
- Passed: 15
- Failed: 0
- Total duration: about 2.2s

### テストクラスと検証内容

#### T09Unit_UcCliStateLog (T09-01)
- `test_state_log_records_run_id_and_success` — plan 成功時に state ログに run_id/success/command/workflow が記録される
- `test_state_log_records_each_step` — UC1 plan の各ステップ名が state ログに含まれる

#### T09Unit_ValidateResumHint (T09-01)
- `test_resume_hint_appears_when_previous_run_failed` — 前回失敗レコードがある場合に validate が resume_hint に run_id を含む

#### T09Unit_RollbackNoBackup (T09-01)
- `test_rollback_without_backup_returns_nonzero` — バックアップ不在の rollback は非ゼロ終了し、元 DB を壊さない

#### T09Inject_WorkflowMidFailure (T09-02: 途中失敗)
- `test_uc1_plan_stops_on_first_step_failure` — 1ステップ目失敗で後続ステップが実行されず success=false が記録される
- `test_uc1_plan_stops_on_second_step_failure` — 2ステップ目失敗で3ステップ目が実行されない
- `test_rollback_after_failed_apply_restores_db` — 失敗 apply 後に rollback を実行すると DB が正常バックアップから復元される

#### T09Inject_NasDisconnect (T09-02: NAS切断)
- `test_apply_records_errors_on_copy_failure` — copy2 が OSError で全失敗する場合、errors リストにエラーが記録される
- `test_apply_partial_failure_reports_correct_counts` — 1ファイルだけ失敗した場合、copied + errors == total が保証される
- `test_apply_empty_dest_directory_missing_still_creates` — 宛先サブディレクトリが存在しない場合も apply は自動作成する
- `test_dry_run_never_writes_even_when_copy_would_fail` — plan/dry-run は dest に何も書き込まない

#### T09Inject_CsvMalformed (T09-02: CSV不正)
- `test_csv_missing_genre_and_entry_key_rows_are_skipped_not_crash` — genre/entry_key 欠損行はスキップされ、クラッシュしない
- `test_csv_unknown_genre_warns_but_does_not_crash` — 存在しない genre を指定しても WARNING だけで終了コードは正常
- `test_csv_entirely_empty_rows_plan_shows_zero_changes` — ヘッダのみ CSV は 0 件更新として正常終了
- `test_csv_semicolon_edge_cases_in_list_fields` — 前後の余分なセミコロンは除去されて正しく比較される

### M06系テスト全体（回帰確認）

Executed command:
```
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest discover -s tests -p "test_m06_*.py" -v
```

Result summary:
- Ran: 39 tests
- Passed: 39
- Failed: 0
- Total duration: about 10.4s

## 3) T09-03: 復旧手順の整備内容

`tools/maintenance_manual.md` に「障害復旧手順（T09-03）」セクションを追加した。

追加内容:
1. **apply 途中失敗** — state/logs 確認 → rollback → plan 再実行 → apply の手順
2. **NAS 同期切断** — 再接続後に plan で差分再スキャン、apply 再実行（冪等設計のため安全）
3. **CSV 不正入力** — よくある問題（0件更新、文字化け、unknown genre、セミコロン余分）の表と対処法
4. **validate エラー / resume_hint** — エラーリスト対応 + rollback → plan → apply の順
5. **ロールバック目標時間** — DB rollback 30秒以内 / plan 再実行 2〜5秒以内

## 4) T09-04: 中間生成物削除

削除対象の分類:
- `metrics/m06-t0[2345]-*` — テスト実行時のテンポラリパスを含む検証用metrics（`t02-schema.jsonl` など正式な記録は保持）
- `intermediate/structure_from_sqlite.json` — T03検証時の中間エクスポートファイル（必要時に再生成可能）
- `logs/*.log` — T07実装検証時のplan実行ログ4ファイル

削除後の保持ファイル (metrics):
- t00_uc1/uc2_{plan,apply}.jsonl — T00計測基盤の before/after 比較記録
- t02-schema.jsonl — T02スキーマ正式計測
- t05-site-artifacts-{plan,apply}.jsonl — T05計測記録
- t06-nas-sync.jsonl — T06 NAS同期計測
- t07-uc1/uc2-plan.jsonl — T07統合CLI計測
- uc2-metadata-*.jsonl — UC2メタデータ反映計測

## 5) Scope guard

- T09対象外のコード（tools/*.py 本体）は修正していない
- plan/dry-run テストは全て非破壊（apply未実行）
- 削除はすべて .artifacts/M06 配下の検証用中間生成物のみ
