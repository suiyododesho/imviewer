# Thumbnail Extraction Tool

Reusable CLI tool:

- `tools/extract_thumbnails.py`

## What It Does

- Accepts one or more start HTML files.
- Finds linked non-index HTML pages from each start file.
- On each linked page, extracts thumbnail images tied to numbered HTML targets (for example `mai1.htm`, `maria02.html`).
- Saves images to `site/thumbnail/` by default.
- Uses filename format: `project_person_001.ext`.

## GitHub Actions – System Release Workflow

### 概要

`.github/workflows/system-release.yml` は、Windows 上でシステムリリース（`tools/release.py system`）を実行し、生成された `releases/*.zip` を GitHub Release アセットとして登録するワークフローです。

### 手動実行手順

1. GitHub リポジトリの **Actions** タブを開く
2. 左サイドバーから **System Release** を選択
3. **Run workflow** ボタンをクリック
4. 必要に応じて以下の入力項目を設定する
5. **Run workflow** で実行開始

### 入力項目 (workflow inputs)

| 入力名 | 型 | デフォルト | 説明 |
|--------|----|-----------|------|
| `major` | boolean | `false` | `true` のときメジャーバージョン (`x+1.0`) にバンプ。`false` のときマイナーバンプ (`x.y+1`) |
| `dry_run` | boolean | `false` | `true` のとき、ファイル変更・アセット upload を行わず対象 tag / zip の検出までをログ出力してジョブを終了する |
| `overwrite` | boolean | `false` | `true` のとき、同名アセットが既に存在する場合は削除して再 upload する。`false` のときはスキップしてログに出す |

### バージョン / タグ運用

- システムバージョンは `site/version_sys.txt` で管理される
- リリース実行時、スクリプトがバージョンをバンプし `release_ver_{version}` 形式のタグを作成する
- タグ名例: `release_ver_0.2`、`release_ver_1.0`

### 生成アセット

- zip ファイル名: `xcity-photobook_{tag_name}_{YYYYMMDD}.zip`
- 収録内容: `site/` 配下（`contents/`, `thumbnail/` を除く）＋ `tools/bin/`（cx_Freeze でビルドした実行ファイル）

### 失敗パターンと対処

| パターン | 対処 |
|----------|------|
| タグが既に存在する | `release.py` が「Git tag は既に存在します」エラーで終了する。ワークフローは冪等性を持たないため、同じバージョンの再 upload は GitHub の Release ページから直接アセットをアップロードするか、ローカルで `gh release upload` コマンドを使用する |
| cx_Freeze のビルドに失敗 | `tools/build_maintenance_bin.py` の依存ライブラリ（`pillow`, `pymupdf` 等）が正しくインストールされているか確認する |
| git push が失敗 | ブランチ保護ルールや GITHUB_TOKEN の権限を確認する。ワークフローに `permissions: contents: write` が付与されていることを確認する |
| zip が見つからない | `releases/` ディレクトリが正しく作成されているか、スクリプトのエラーログを確認する |

### セキュリティ上の注意

- ワークフローには `permissions: contents: write` が付与されている（Release 作成・tag push に必要）
- `GITHUB_TOKEN` は GitHub が自動生成する一時的なトークンであり、ワークフロー終了後に失効する
- Secrets に追加のトークンは不要

## M06 メンテナンス（structure.json 同期）

`site/contents` 配下に新しいフォルダやファイルを追加した場合は、UC1 の validate/apply を実行する前に structure 同期を行ってください。

- `tools\\maintenance.bat` のメニュー `1`（`Sync structure.json from site/contents (add/update first)`）を実行します。
- この同期は `--no-remove-missing` で実行されるため、現在のローカル環境に存在しない項目を誤って削除しないようになっています。

新規コンテンツ登録時の推奨手順:

1. メニュー `1` で `site/structure.json` を `site/contents` から同期する。
2. メニュー `3`（`Validate - Contents import/sync + diff + site artifact generation`）を実行する。
3. メニュー `4`（`Apply - Contents import/sync + diff + site artifact generation`）を実行する。

---

## Usage

From the workspace root:

```powershell
python tools/extract_thumbnails.py "D:\Tool\_mytool\_bulk\xcity\webcrawler\output\juicyhoney_2\src\aja_archives_free_juicyhoney_honey2.html"
```

Multiple start files:

```powershell
python tools/extract_thumbnails.py "path\to\start1.html" "path\to\start2.html"
```

Optional flags:

- `--output-dir <path>`
- `--project-name <name>`
- `--encoding <encoding>`
- `--dry-run`

Example with options:

```powershell
python tools/extract_thumbnails.py "path\to\start.html" --output-dir "site\thumbnail" --dry-run
```

