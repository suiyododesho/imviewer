# メンテナンスマニュアル

## T04 apply（fingerprint更新）運用手順

### 目的

- SQLite の最新データから `series.fingerprint` を更新する
- 変更されたシリーズパスを UC1 / UC2 の既存差分入力に連携する

### 実行手順（メニュー）

- `tools/maintenance.bat` を起動し、`13` を選択する
- メニュー `13` の実行内容:
  - `maint_series_diff.py apply` を実行
  - 変更シリーズパスを `.artifacts/M06/intermediate/t04-diff-targets.txt` に出力
  - 変更シリーズパスを `site/history.txt` の `next.force_dirs` に追記

### UC2 連携

- `tools/maintenance.bat` を起動し、`14` を選択する
- メニュー `14` の実行内容:
  - `maint_metadata.py apply --diff-targets-file .artifacts/M06/intermediate/t04-diff-targets.txt` を実行
  - T04 の差分対象ファイルに含まれるシリーズのみを UC2 metadata apply の対象にする

## rollback 手順（T04 apply）

### rollback が必要なケース

- `maint_series_diff.py apply` が失敗し、DB状態に不整合の可能性がある
- 誤った対象に apply してしまい、fingerprint を復旧したい

### 復旧手順

1. `tools/sqlite/backup/` から最新バックアップを特定する
2. DB を使用するメンテナンス処理をすべて停止する
3. `tools/sqlite/imviewer_maintenance.sqlite3` をバックアップで上書き復元する
4. `maint_series_diff.py plan` を再実行し、変更対象が想定どおりか確認する
5. 確認後に apply を再実行する

### コマンド例（PowerShell）

```powershell
Copy-Item -Force tools/sqlite/backup/imviewer_maintenance_YYYYMMDD_HHMMSS.sqlite3.bak tools/sqlite/imviewer_maintenance.sqlite3
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_series_diff.py plan
```

## 運用上の注意

- 破壊的操作は必ず `plan` / `dry-run` を先に実行する
- 計測ログは `.artifacts/M06/metrics/` に保存し、before/after 比較に使う
- `site/history.txt` の `next.force_dirs` に想定外のエントリが入った場合は、そのエントリのみ削除して plan を再実行する
