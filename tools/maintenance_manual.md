# メンテナンスマニュアル

## 本マニュアルの目的

- 日常のメンテナンス作業を、ユースケース単位で安全に実行するための手順を示す
- 破壊的操作の前に必ず plan または dry-run を実行し、想定どおりの変更だけを apply する
- 中断時に状態ログと実行ログを確認し、復旧や再開を行いやすくする

## 事前確認

- 仮想環境の Python を使用する
- 破壊的操作（apply / rollback）の前に、対象と差分を plan で確認する
- 実行ログ保存先
  - 状態ログ: .artifacts/M06/state/t07-uc-cli-state.jsonl
  - ステップログ: .artifacts/M06/logs/
  - 計測ログ: .artifacts/M06/metrics/

## ユースケース1: コンテンツ取り込み・差分反映・サイト生成

### こういう時に実施

- contents 配下の追加・更新を structure と生成物に反映したい
- 差分判定を行い、必要なシリーズだけ再処理したい

### 追加コンテンツの配置先（バッチ実行前）

- `tools/maintenance.bat` を使う場合は、追加する PDF や画像入りディレクトリ（またはアーカイブ）を `site/contents/` 配下へ配置する
- 配置は最終公開構成に合わせる（例: `site/contents/comic/[著者名] タイトル/`）
- `tools/content_add/content_add.bat` を使う運用では、`tools/content_add/<workspace>/contents/` 配下に同じ構造で配置する

### 推奨手順

1. Plan（非破壊）　→ バッチ: メニュー **1**
2. Validate（事前チェック + 非破壊検証）　→ バッチ: メニュー **3**
3. Apply（承認付きで反映）　→ バッチ: メニュー **5**

### コマンド例（PowerShell）

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py plan uc1
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py validate uc1
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py apply uc1 --approve
```

### 実行内容の概要

- DB 取り込み計画の確認
- シリーズ差分の確認
- サイトアーティファクト生成計画の確認または反映

## ユースケース2: メタデータCSVの編集反映

### こういう時に実施

- CSV で編集した name / labels / persons / note などを structure に反映したい
- 差分対象ファイルを使って反映範囲を絞りたい

### 推奨手順

1. 必要に応じて CSV を出力　→ バッチ: メニュー **8**
2. Plan（非破壊）　→ バッチ: メニュー **2**
3. Validate（事前チェック + 非破壊検証）　→ バッチ: メニュー **4**
4. Apply（承認付きで反映）　→ バッチ: メニュー **6**

### コマンド例（PowerShell）

CSV 出力:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_metadata.py export --output tools/metadata.csv
```

反映:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py plan uc2
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py validate uc2
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py apply uc2 --approve
```

### 補足

- apply 時は .artifacts/M06/intermediate/t04-diff-targets.txt を利用して対象を絞り込む

## ユースケース3: DBの復旧（rollback）

### こういう時に実施

- apply 失敗後に DB の整合性が不安な場合
- 想定外の反映を取り消して直前状態へ戻したい場合

### 推奨手順

1. 影響するメンテナンス処理を停止する
2. rollback を実行する　→ バッチ: メニュー **7**
3. plan を再実行して対象差分を確認する　→ バッチ: メニュー **1** または **2**

### コマンド例（PowerShell）

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py rollback
```

必要に応じて `--backup <path>` で復元元を明示できる。

## maintenance.bat からの実行

- tools/maintenance.bat は作業内容ベースの必須メニューを表示する
- 旧来の粒度が細かい単機能メニューは非推奨
- 実運用では統合CLIを優先して使用する

## 運用上の注意

- 破壊的操作は必ず plan または dry-run を先に実行する
- 計測ログは .artifacts/M06/metrics/ に保存し、before/after 比較に使う
- site/history.txt の next.force_dirs に想定外エントリが入った場合は、そのエントリのみ削除して plan を再実行する
- 長時間処理や失敗時は .artifacts/M06/state/t07-uc-cli-state.jsonl と .artifacts/M06/logs/ を確認して再開判断する

