# メンテナンスツール改修仕様（データ追加・更新運用）

## 1. 背景

現行の `tools/build_gallery_pages_map.py` は以下を一体で実行している。

- `site/structure.json` 読み込み
- `site/js/structure.js` 生成
- `site/js/gallery-pages.js` 生成
- ギャラリーサムネイル生成
- `site/history.txt` 追記

一方、`site仕様書` では `structure.json` の `contents` をシリーズ配下ディレクトリから再生成する運用に変更された。
このため、データ追加・更新のユースケースごとに処理を分割し、再実行時の影響範囲を限定できる構成が必要。

## 2. 改修の目的

- `contents` を自動再生成できるようにする。
- `main-person` / `persons` をシリーズ単位で保持し、コンテンツ単位では扱わない。
- 差分更新（限定再生成）と全量再生成を明確に分離する。
- 既存運用（`history.txt` を使った差分リリース）を維持する。

## 3. 対象と非対象

### 対象

- `tools/build_gallery_pages_map.py` の機能分割または置換
- `structure.json` の `contents` 自動再生成
- `structure.js` / `gallery-pages.js` 生成フロー再構成
- `history.txt` 同期処理の分離

### 非対象

- フロントエンド表示ロジックの仕様変更（HTML/CSS/JSのUI挙動）
- リリースバージョン規約そのもの（`release.py` のポリシー）

## 4. ユースケース別の必要処理

### UC-1: 新規追加（シリーズ/人物/ギャラリー）

1. `site/contents/` へデータ追加
2. `structure.json` のシリーズメタを更新（`main-person`, `persons`, `series`, `labels` 等）
3. `contents` 再生成
4. `structure.js` 再生成
5. `gallery-pages.js` 再生成
6. 必要に応じて `history.txt` 同期

### UC-2: リネーム（シリーズ配下ディレクトリ名変更）

1. ディレクトリリネーム
2. `contents` 再生成
3. `structure.js` / `gallery-pages.js` 再生成
4. `contents[*].note` が空に戻ることを許容

### UC-3: 軽微更新（画像差し替え・ページ追加）

1. ギャラリー配下メディア更新
2. `gallery-pages.js` を差分再生成（`--diff`）
3. 必要なら `history.txt` 同期

### UC-4: 全量再構築

1. `contents` 全量再生成
2. `structure.js` 全量再生成
3. `gallery-pages.js` 全量再生成
4. サムネイル全量再生成（必要時）

## 5. ツール分割仕様

以下の分割を推奨する（ファイル名は固定要求ではないが、責務分離は必須）。

### 5-1. `tools/maint_build_structure.py`

- 役割: `structure.json` の `contents` を再生成
- 入力:
  - `site/structure.json`
  - `site/contents/`
- 出力:
  - 更新済み `site/structure.json`
- ルール:
  - `contents[*].name` はディレクトリ名
  - `contents[*].path` は `contents-root` からの相対パス
  - `contents[*].cover` は生成済みカバー画像パス
  - `contents[*].note` は空文字
  - `main-person` / `persons` はシリーズ単位項目として保持（コンテンツには持たない）
- オプション:
  - `--diff`: 指定シリーズ/指定ディレクトリのみ再生成
  - `--dry-run`: 変更内容の表示のみ

### 5-2. `tools/maint_build_structure_js.py`

- 役割: `site/structure.json` から `site/js/structure.js` を生成
- 入力: `site/structure.json`
- 出力: `site/js/structure.js`

### 5-3. `tools/maint_build_gallery_pages.py`

- 役割: `site/js/gallery-pages.js` 生成、および必要なギャラリーサムネイル生成
- 入力:
  - `site/structure.json`
  - `site/contents/`
- 出力:
  - `site/js/gallery-pages.js`
  - `site/contents/**/src/thumbnail/*.jpg`（必要時）
- オプション:
  - `--diff`: `history.txt` の `next` / `force_dirs` に一致する対象のみ更新
  - `--full`: 全量再生成

### 5-4. `tools/maint_sync_history.py`

- 役割: `site/contents/photo/` と `site/history.txt` の差分同期
- 入力:
  - `site/contents/photo/`
  - `site/history.txt`
- 出力:
  - 更新済み `site/history.txt`

## 6. 現行スクリプトからの移行要件

`tools/build_gallery_pages_map.py` については以下のいずれかを満たすこと。

- 方針A: 機能を新スクリプトへ分割し、旧スクリプトは廃止
- 方針B: 旧スクリプトを薄いオーケストレータに変更し、内部で分割済み処理を呼ぶ

必須条件:

- 「`contents` 再生成」と「`gallery-pages.js` 生成」を独立実行できること
- `history.txt` 同期を任意実行にできること（自動追記の固定挙動を避ける）

## 7. CLI仕様（最小）

- `python tools/maint_build_structure.py [--diff] [--dry-run]`
- `python tools/maint_build_structure_js.py`
- `python tools/maint_build_gallery_pages.py [--diff|--full]`
- `python tools/maint_sync_history.py`

推奨（運用簡素化）:

- `tools/maintenance.bat` でユースケース別プリセットを提供
  - 例: `maintenance.bat add`, `maintenance.bat rename`, `maintenance.bat diff`, `maintenance.bat full`

## 8. データ整合性ルール

- `structure.json` のシリーズ定義は手動編集領域として保持
- `contents` は再生成時に機械出力を正とする
- `contents[*].note` は再生成で空になる可能性を許容
- パスはすべて `/` 区切りの相対パスで保持

## 9. 受け入れ条件

- AC-1: 新規追加後に `contents` が自動生成される
- AC-2: リネーム後に `path` / `name` / `cover` が再生成結果へ追従する
- AC-3: `main-person` / `persons` がコンテンツ単位へ展開されない
- AC-4: `gallery-pages.js` を差分更新できる
- AC-5: `history.txt` 同期を単体実行できる
- AC-6: 全量再構築で `structure.js` / `gallery-pages.js` が再生成される

## 10. 実装順序（推奨）

1. `maint_build_structure.py` 実装
2. `maint_build_structure_js.py` 実装
3. `maint_build_gallery_pages.py` 実装（既存ロジック移植）
4. `maint_sync_history.py` 実装
5. `maintenance.bat` 更新
6. 旧 `build_gallery_pages_map.py` を互換ラッパ化または廃止
