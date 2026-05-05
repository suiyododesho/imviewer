# T02 実装レポート

実施日: 2026-05-03  
ブランチ: feature/M06-maintenance-speedup

---

## 概要

T02（SQLite スキーマ基盤）を実装。

- `plan` / `dry-run` を非破壊で先行実装
- `apply` 明示時のみ DB 作成・更新を実施
- `schema_migrations` による append-only マイグレーション方針を導入
- DB 更新前バックアップを実装
- 最小テーブル群 + 一意制約 + 外部キー + 索引を実装

---

## 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `tools/maint_db_schema.py` | T02 新規CLI（plan/dry-run/apply, migration, backup, metrics） |
| `tests/test_m06_t02_db_schema.py` | T02 受け入れ条件向けユニットテスト3件 |
| `.specify/M06/tasks.md` | T02-01〜T02-03 を完了チェックに更新 |

---

## 実装内容

### T02-01 DB 初期化コマンドと migration 方針

- 新規CLI: `tools/maint_db_schema.py`
- サブコマンド:
  - `plan`（非破壊）
  - `dry-run`（`plan` の別名）
  - `apply`（明示時のみ更新）
- migration 方針:
  - `schema_migrations(version, description, applied_at)` で管理
  - append-only でバージョン追加
  - version 昇順で適用

### T02-02 最小テーブル群

実装済みテーブル:

- `genres`
- `series`
- `contents`
- `gallery_pages`
- `persons`
- `labels`
- `content_person_map`
- `content_label_map`
- `jobs`
- `snapshots`

### T02-03 一意制約・外部キー・索引

- 一意制約: 主要キー（例: `genres.genre_key`, `series(genre_id, series_key)`, `contents(series_id, content_key)`, `gallery_pages(content_id, page_no)` など）
- 外部キー: `series -> genres`, `contents -> series`, `gallery_pages -> contents`, map テーブル -> 親テーブル
- 索引: 差分判定/検索向けに `fingerprint`, `name`, map 参照列, `jobs(status, requested_at)`, `snapshots(created_at)` などを作成

---

## テスト結果

実行コマンド:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe -m unittest tests/test_m06_t02_db_schema.py
```

結果:

- Ran 3 tests
- OK

テスト内容:

1. `plan` / `dry-run` では DB ファイルを作成しない（非破壊）
2. `apply` で最小テーブル群・索引を作成し、UNIQUE/FK 制約が有効
3. 既存 DB 更新時にバックアップが生成される

---

## 計測結果

計測ログ:

- `.artifacts/M06/metrics/t02-schema.jsonl`

実行:

1. `plan`（新規DB想定）
2. `apply`（初期スキーマ適用）
3. `plan`（適用後の差分なし確認）

主要値（ログ抜粋）:

- apply 時
  - `duration_ms`: 7938
  - `generated_count`: 2（stage合算）
  - `transfer_files`: 1
  - `transfer_bytes`: 163840
- apply 後 plan 時
  - `pending_versions`: 0
  - `will_write`: false

---

## 受け入れ条件確認

| 条件 | 結果 |
|---|---|
| 空DBを再現可能 | ✅ `apply` で空DBから全テーブルを生成 |
| 差分判定と検索で必要な索引がある | ✅ fingerprint/name/map/jobs/snapshots 系索引を実装 |
| DB更新前バックアップが作成される | ✅ 既存DBに対する `apply` でバックアップ生成をテスト確認 |
