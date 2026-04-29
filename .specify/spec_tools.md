# ツール群の仕様書

- batファイルは例外なく全てshift-jisで、pyファイルはutf-8で保存すること。

## メンテナンスツール

`tools/build_gallery_pages_map.py` は、`site/structure.json` と関連JSを再生成する統合エントリです。

### 実行と出力

- 実行コマンド: `python tools/build_gallery_pages_map.py`
- 差分モード: `python tools/build_gallery_pages_map.py --diff`
- 主な出力:
  - `site/structure.json`
  - `site/js/structure.js`
  - `site/js/gallery-pages.js`

### 再作成条件

- `structure.json` の `contents` 再構築は、現状の実装では `--diff` 指定時も全シリーズを対象に実行される。
- PDF/CBZ からのコンテンツ画像抽出処理（`*_pdf/`, `*_cbz/` ディレクトリ生成）は、対象シリーズの走査時に毎回呼ばれる。
- ただし、実ファイルの再生成はタイムスタンプで抑制される。
  - PDF: 既存ページ画像 (`001.jpg` など) の更新時刻が PDF ファイルより新しい、または同等なら再レンダリングしない。
  - CBZ: 既存ページ画像の更新時刻が CBZ ファイルより新しい、または同等なら再抽出しない。
  - 既存ページ画像が無い場合、またはアーカイブの方が新しい場合のみ、そのページを再生成する。
- `gallery-pages.js` は毎回再書き込みされる。
  - ただし `--diff` かつ既存 `gallery-pages.js` がある場合は、`history.txt` の `next.dirs` と `next.force_dirs` に一致するギャラリーのみ再計算する。
  - 再計算対象外のギャラリーは既存マップを再利用する。

### 補足

- PDF/CBZ の元ファイルは保持し、削除しない。
- `structure.json` に載せるのは、抽出後の `*_pdf/`, `*_cbz/` ディレクトリのパスであり、PDF/CBZ ファイルパスは載せない。

## リリース作業ツール

## 動画コンバータツール

`site/contents/photo`以下にある動画ファイルを、ブラウザで再生可能な形式（MP4/H.264）に変換するツールです。変換後のファイルは同じディレクトリに保存されます。変換元のファイルは削除されません。

変換対象のファイル: AVI, MPG, MPEG, MKV, WMV 形式の動画ファイル

### 実装ファイル

- tools/convert.bat: デフォルト設定で変換を行う起動用バッチファイル
- tools/convert_custom.bat: convert_config.jsonの設定で変換を行うバッチファイル
- tools/convert_config.json: 変換のカスタム設定を記述するJSONファイル
- tools/convert.py: FFmpeg による変換処理の実装（失敗時は VLC 代替フローへフォールバック）
- tools/convert_vlc.bat: VLC 変換を単独実行するバッチファイル
- tools/convert_vlc.py: VLC による代替変換処理の実装（Pythonスクリプト）

### 変換仕様(default)

- 変換後のファイル形式: MP4
- 動画コーデック: H.264
- 音声コーデック: AAC
- 解像度: 元の動画と同じ
- フレームレート: 元の動画と同じ
- ビットレート: 自動調整（品質優先）
- 品質: 中品質（CRF 24相当）
- 第1変換ツール: FFmpeg（コマンドラインオプション例: `ffmpeg -i input.mkv -c:v libx264 -crf 24 -c:a aac output.mp4`）
- 第2変換ツール: VLC（FFmpeg で失敗した場合の代替フロー。デインタレース `yadif` を有効にして MP4/H.264 に変換する）
- 変換後のファイル名: 元のファイル名を、拡張子だけ`.mp4`に変更（例: `video.mkv` → `video.mp4`）

### 変換仕様(custom)

変換の設定を `convert_config.json` でカスタマイズ可能です。ブラウザで再生させる都合、出力形式は MP4/H.264 系のままとします。

#### JSON設定ファイルのサポート項目一覧

```json
{
  "ffmpeg_path": "C:\\Tool\\bin\\ffmpeg.exe",
  "vlc_path": "C:\\Program Files\\VLC\\vlc.exe",
  "upscale": true,
  "resolution": "",
  "frame_rate": "",
  "bit_rate": "",
  "quality": 24,
  "ffmpeg_options": ""
}
```

- `ffmpeg_path`
  - 使用する FFmpeg バイナリのパス。
  - 例: `"C:\\Tool\\bin\\ffmpeg.exe"`
  - 指定時は `convert.py` の FFmpeg 実行に利用する。
  - コマンドライン引数 `--ffmpeg` が指定された場合は、そちらを優先する。

- `vlc_path`
  - 使用する VLC バイナリ (`vlc.exe`) のパス。
  - 例: `"C:\\Program Files\\VLC\\vlc.exe"`
  - `convert.py` のフォールバック実行、および `convert_vlc.py` 単独実行時に利用する。
  - コマンドライン引数 `--vlc` が指定された場合は、そちらを優先する。

- `upscale`
  - `true / false` を指定するブール値。
  - `true` の場合、入力動画の **縦幅が 480px 未満** のときのみ、高さ 480px へアスペクト比を維持して拡大する。
  - 横幅は比率に応じて自動計算し、偶数値に補正する。
  - `false` の場合はアップスケールを行わない。
  - `resolution` が指定されている場合は、そちらの明示解像度指定を優先する。

- `resolution`
  - 出力解像度の明示指定。
  - 形式: `"幅x高さ"` 例: `"1920x1080"`
  - 指定時は、元動画をアスペクト比維持でその枠内に収め、必要に応じて余白を付加する。
  - 空文字や不正値の場合は未指定扱い。

- `frame_rate`
  - 出力フレームレート。
  - 例: `30`, `29.97`
  - 空文字や不正値の場合は元動画の値を使用する。

- `bit_rate`
  - 出力ビットレート。
  - 例: `"2000k"`, `"3M"`
  - 空文字や不正値の場合は自動調整とする。

- `quality`
  - FFmpeg で使用する品質値（CRF相当）。
  - 例: `24`
  - 有効範囲は `0` ～ `51`。
  - 値が小さいほど高品質・高容量、大きいほど低品質・低容量。

- `ffmpeg_options`
  - FFmpeg に追加で渡したいコマンドラインオプション文字列。
  - 例: `"-preset slow"`
  - `convert.py` の FFmpeg 経路でのみ使用する。

#### 設定値の補足ルール

- 空文字・無効な値はデフォルト設定が使用される。
- `convert_custom.bat` はこの JSON 設定を読み込んで実行する。
- `convert.py` は **FFmpeg → 失敗時のみ VLC フォールバック** の順で実行する。
- `convert_vlc.py` は VLC 単独の代替フローとして使える。

### 実行方法

1. `convert_config.json`を必要に応じて編集して保存します。
2. デフォルト設定で変換を行う場合は、convert.batをダブルクリックで実行します。内部では `convert.py` がまず FFmpeg で一括変換し、失敗したファイルのみ自動的に VLC の代替フローへ切り替えます。カスタム設定で変換を行う場合は、convert_custom.batをダブルクリックで実行します。
3. VLC だけを単独で使いたい場合は、convert_vlc.bat に動画ファイルをドラッグ＆ドロップするか、ダブルクリック後に対象パスを入力して実行します。
4. 変換が完了すると、変換されたMP4ファイルが元の動画ファイルと同じディレクトリに保存されます。元の動画ファイルはそのまま残ります。

### ログ仕様

変換の進行状況やエラーは、標準出力にprogress情報を出力しつつ、実行エラーはconvert.errorファイルに記録されます。（エラーが発生したときのみ）

進行状況のログには以下の情報が含まれます。
- 変換開始時刻
- 変換対象ファイル名
- 変換完了時刻

エラーログには以下の情報が含まれます。
- エラー発生時刻
- 変換対象ファイル名
- エラー内容（FFmpegのエラーメッセージなど）
