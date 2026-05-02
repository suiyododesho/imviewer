# content_add ツール

ローカルマシンでコンテンツ追加処理（アーカイブ展開・サムネイル生成等）を実行し、サーバーにアップロードするツールです。

## ディレクトリ構成

```
content_add/
├── readme.md             # このファイル
└── workspace/            # テンプレートworkspace（git管理対象）
    ├── content_add.bat          # メインスクリプト
    ├── content_add_config.json  # 設定ファイル（サーバーパス等）
    └── contents/                # 追加コンテンツを配置するディレクトリ
```

実際に使用する際は `workspace/` を複製・改名して使います（複製後のディレクトリはgit管理対象外）。

## セットアップ（初回）

1. `workspace/` ディレクトリを複製し、任意の名前に変更します。
   - 例：運用システムごとに `myserver/` のような名前にする
2. 複製したディレクトリの `content_add_config.json` を編集します。

```json
{
  "server": {
    "site_dir": "Z:\\path\\to\\server\\site"
  }
}
```

`server.site_dir` にサーバー上の `site/` ディレクトリへのパスを設定します（UNCパスまたは割り当てドライブレターで指定）。

## 使用手順

1. `contents/` に追加したいアーカイブファイルを配置します。
   - サーバーの `site/contents/` と同じディレクトリ構造にします。
   - 例：`contents/comic/[著者名] タイトル/第01巻.zip`

2. `content_add.bat` をダブルクリック（または管理者権限が必要な場合はコマンドプロンプトから実行）します。

3. スクリプトが以下の3フェーズで自動処理されます。
   - **Fetch**：サーバーから最新の `structure.json` を取得
   - **Process**：アーカイブ展開・サムネイル生成・JS生成をローカルで実行
   - **Upload**：生成物（`contents/`・`thumbnail/`・`structure.json`・JSファイル）をサーバーへ差分コピー

## 注意事項

- `content_add.bat` の実行にはプロジェクトの `.venv` が必要です。
- サーバーの `site/` ディレクトリがエクスプローラーから参照できる状態（ドライブマウント等）でないとUploadが失敗します。
- 処理中にエラーが発生した場合、その時点で処理を中断します。エラーメッセージを確認してください。
