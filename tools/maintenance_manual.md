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

---

## 障害復旧手順（T09-03）

### 障害種別と対応フロー

#### 1. apply 途中失敗（ステップ実行エラー）

**症状**: `apply` の実行中にステップ（t03/t04/t05 のどれか）が失敗し、終了コードが非ゼロになった。

**確認手順**:

```powershell
# 最後の実行状態を確認
Get-Content .artifacts\M06\state\t07-uc-cli-state.jsonl | Select-Object -Last 1 | ConvertFrom-Json

# 失敗したステップのログを確認
Get-ChildItem .artifacts\M06\logs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

**復旧手順**:

1. 失敗ステップのログを確認し、原因を特定する
2. 原因が DB の不整合や部分書き込みの場合は rollback を実行する（→ メニュー **7**）
3. rollback 後は plan を再実行し、差分を再確認してから apply し直す

```powershell
# rollback
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py rollback

# 再確認
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py plan uc1

# 再apply（問題解消後）
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py apply uc1 --approve
```

#### 2. NAS 同期切断（コピー中の接続失敗）

**症状**: `maint_sync_nas.py apply` の実行中に接続が切れ、部分的にコピーが完了した状態になった。

**確認手順**:

```powershell
# 最後の計測ログを確認
Get-Content .artifacts\M06\metrics\t06-nas-sync.jsonl | Select-Object -Last 1 | ConvertFrom-Json
```

**復旧手順**:

1. NAS の接続を回復する
2. `plan` を再実行してコピー済み/未コピーを再スキャンする  
   （コピー済みファイルはハッシュ一致で自動スキップされる）
3. `apply` を再実行する

```powershell
# 再plan（自動差分検出）
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_sync_nas.py plan --source site --dest <NAS_PATH>

# 再apply
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_sync_nas.py apply --source site --dest <NAS_PATH>
```

> **NAS同期は冪等設計**のため、切断後の再実行は安全です。コピー済みファイルを再転送することはありません。

#### 3. CSV 不正入力（メタデータ反映失敗）

**症状**: CSV の列名誤り・必須列欠損・文字コード誤りにより `maint_metadata.py` が意図通りに動作しなかった。

**確認手順**:

```powershell
# plan で変更対象件数を確認（0件なら CSV が正しく読まれていない可能性）
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_metadata.py plan --input tools/metadata.csv
```

**よくある問題と対処**:

| 症状 | 確認ポイント | 対処 |
|------|------------|------|
| 更新対象が 0 件 | genre/entry_key 列が正しいか確認 | CSV を修正して再 plan |
| 文字化け警告 | CSV のエンコーディングが UTF-8-BOM でない | Excel 保存時に「CSV UTF-8（BOM付き）」を選択 |
| WARNING: genre '...' not found | structure.json のジャンルキーと一致しているか | genre 列の値を structure.json の genres キーに揃える |
| persons/labels が空になる | セミコロン区切りの先頭・末尾に余分な `;` | `author-a;author-b` の形式を使う（前後に `;` 不要） |

**復旧手順**:

1. CSV を修正する（上表を参照）
2. `plan` で変更対象件数を再確認する
3. 問題がなければ `apply` を実行する

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py plan uc2
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py apply uc2 --approve
```

#### 4. validate のエラー / resume_hint 表示

**症状**: `validate` を実行したら `"errors"` リストにパス不存在などが報告された。

**確認手順**:

```powershell
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py validate uc1
# または
d:/Tool/_mytool/imviewer/.venv/Scripts/python.exe tools/maint_uc_cli.py validate uc2
```

`"resume_hint"` に前回失敗の `run_id` が含まれている場合、未完了の apply が記録されている。

**復旧手順**:

1. `"errors"` リストの内容に従ってパスや設定を修正する
2. 必要なら rollback で DB を安定状態に戻す
3. plan → apply の順で再実行する

### ロールバック目標時間

| 操作 | 目標復旧時間 |
|------|------------|
| DB rollback のみ | 30 秒以内 |
| plan 再実行 (UC1) | 5 秒以内 |
| plan 再実行 (UC2) | 2 秒以内 |
| NAS 再同期（差分のみ） | 転送量に依存、初回より大幅短縮 |

