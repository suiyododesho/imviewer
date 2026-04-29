---
name: 'extractor'
agent: agent
model: Auto (copilot)
tools: [vscode, execute, read, agent, edit, search, browser]
description: '指定したhtmlを起点にリンク先をたどり、各人物ページに埋め込まれたサムネイル画像を抽出して site/thumbnail/ に保存する。honey名抽出、人物名抽出、連番命名が必要なときに使う。'
---

指定したhtmlファイルを起点に、人物ごとのフォトギャラリーサムネイル画像を抽出して保存してください。

このプロンプトでは、ワークスペース内の固定ツール `tools/extract_thumbnails.py` を必ず使って処理すること。
ただし、実行環境や対象サイト構造の都合でPython実行が不可能な場合は、代替手順で作業を継続し、その差分を吸収するためにツール改修まで行うこと。

## 入力

- 起点htmlファイルを1個以上受け取る。
- 複数指定時は、指定順に先頭から順次処理する。
- 例:
  - site/contents/src/aja_archives_free_juicyhoney_honey2.html
  - site/contents/src/aja_archives_free_juicyhoney_honey4.html

## 実行内容

1. 受け取った起点htmlファイル群をそのまま `tools/extract_thumbnails.py` に渡して実行する。
2. 既定では `site/thumbnail/` に保存する。
3. 検証のみを行う場合は `--dry-run` を使う。

補足:

- 指定した起点html単体でページが完結しており、同一ページ内に抽出対象サムネイルがある場合もある。
- その場合は、起点html自体も抽出対象として処理する（リンク先ページが0件でも終了しない）。

実行コマンド例（PowerShell / ワークスペースルート）:

```powershell
.\.venv\Scripts\python.exe tools\extract_thumbnails.py "<start1.html>" "<start2.html>"
```

ドライラン例:

```powershell
.\.venv\Scripts\python.exe tools\extract_thumbnails.py "<start1.html>" --dry-run
```

## 抽出ルール

- 抽出ロジック（index除外、番号付きhtmlリンク判定、人物名/title抽出、連番命名、重複回避）は `tools/extract_thumbnails.py` の実装に従う。
- プロンプト側で同等ロジックを再実装しない。常にツールを呼び出す。
- 人名が `title` 要素などから特定できない場合は、`site/contents/index_juicyhoney.html` を参照して補完する。
- `site/contents/index_juicyhoney.html` 参照後も特定不能な場合は、安全な代替名を用いて保存し、報告に「人名特定不可」と明記する。

## Python利用不可時の代替手順

- `tools/extract_thumbnails.py` の実行に失敗した場合は、まず実行方法を切り替えて再試行する。
  - 例: `python` / `py -3` / 仮想環境python の切り替え。
- それでもPython実行不可、または対象HTML構造が既存ツールで処理不能な場合は、以下の順で対応する。
  1. その場で実行可能な手段（PowerShellやJS等）で抽出作業を完遂する。
  2. 代替手順で吸収した仕様差分（DOM構造、属性パターン、命名例外など）を整理する。
  3. `tools/extract_thumbnails.py` を改修し、次回以降は同ケースをツール単体で再実行できる状態にする。
  4. 必要に応じてREADMEや本プロンプトの手順を更新する。
- 一時的な場当たり対応で終わらせず、再利用性向上を目的に必ずツールへ知見を還元する。

## 保存先

- 保存場所: `site/thumbnail/`
- 保存先ディレクトリが存在しない場合は、ツール側で作成される。

## 命名規則

- 形式: `企画名_人名_フォトギャラリー番号.jpg`
- 例: `honey2_薫まい_001.jpg`

各要素の決め方:

- 企画名
  - 起点htmlファイル名から `honey*` を抽出して使う（必要に応じて `--project-name` で上書き可）。
- 人物名
  - アクセス先htmlの `title` 要素から抽出する。
  - 前後の不要な空白は除去する。
  - ファイル名に使えない文字が含まれる場合は、安全な文字に置換する。
- フォトギャラリー番号
  - 人物ごとに、保存した順番で `001` 始まりの3桁連番を付ける。
  - 文書順に `001`, `002`, `003` ... とする。

## 保存時の注意

- 既存ファイルがある場合は上書きせず、ツールの重複回避命名（`_dupXX`）に従う。
- 実行失敗時は、失敗した引数とエラーメッセージをそのまま報告する。
- 代替手順を使った場合は、なぜPython方式が使えなかったか、どの差分をツール改修へ反映したかを報告する。
- 人名補完で `site/contents/index_juicyhoney.html` を参照した場合は、どのように補完したかを報告する。

## 完了時の報告

以下を簡潔に報告する。

- 起点htmlファイル
- たどった人物ページ数
- 保存した画像数
- 保存先ディレクトリ
- 保存できなかったファイルがあれば、その理由
- 実行コマンド
- （該当時）代替手順の内容
- （該当時）ツール改修内容

## 実行例

入力:

- `site/contents/src/aja_archives_free_juicyhoney_honey2.html`

期待される保存例（ツール実行結果に従う）:

- `site/thumbnail/honey2_薫まい_001.jpg`
- `site/thumbnail/honey2_薫まい_002.jpg`
- `site/thumbnail/honey2_山口まゆ_001.jpg`

