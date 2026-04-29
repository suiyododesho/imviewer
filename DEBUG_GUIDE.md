# 🔧 "サイトの読み込みに失敗しました" エラー対処法

## 🚨 よくある原因と解決策

### 原因 1: file:// プロトコルで開いている

**症状:**
- アドレスバーに `file:///C:/Users/...` と表示されている
- ブラウザコンソールに CORS エラーが表示される

**解決策:**
HTTPサーバーを起動してアクセスしてください。

```bash
# site/ ディレクトリで実行
python -m http.server 8080

# ブラウザで以下にアクセス
http://localhost:8080/index.html
```

---

### 原因 2: structure.json または生成済み JS が不足している

**症状:**
- エラーメッセージに「Site structure not loaded. Make sure structure.js is included.」が含まれている
- `site/js/structure.js` または `site/js/gallery-pages.js` の読み込みに失敗している
- `structure.json` を修正したのに画面に反映されない

**確認:**
```
site/ ディレクトリに以下が存在するか確認
  - d:\Tool\_mytool\_bulk\sitedesign\site\structure.json
  - d:\Tool\_mytool\_bulk\sitedesign\site\js\structure.js
  - d:\Tool\_mytool\_bulk\sitedesign\site\js\gallery-pages.js
```

**解決策:**
- `site/structure.json` を正本として修正してください
- 修正後、ワークスペース直下で以下を実行して生成物を再作成してください

```powershell
cd d:\Tool\_mytool\_bulk\sitedesign
.\.venv\Scripts\python.exe tools\build_gallery_pages_map.py
```

- サムネイル補完も必要なら、その前に以下を実行してください

```powershell
cd d:\Tool\_mytool\_bulk\sitedesign
.\.venv\Scripts\python.exe tools\generate_thumbnails.py
```

- HTTPサーバーが `site/` ディレクトリで起動しているか確認

---

### 原因 3: トップディレクトリで HTTPサーバーを起動している

**症状:**
- HTTPサーバーが 「site/」ディレクトリではなく、「sitedesign/」で起動している

**確認:**
ターミナルに表示されるメッセージで確認:
```
✓ 正: cd site && python -m http.server 8080
     (site/ の中で実行)

✗ 誤: cd sitedesign && python -m http.server 8080
     (site フォルダの親で実行)
```

**解決策:**
```bash
# 正しい方法
cd d:\Tool\_mytool\_bulk\sitedesign\site
python -m http.server 8080
```

---

## 🔍 デバッグ手順

### ステップ 1: 開発者ツールを開く

ブラウザで `F12` を押すか、右クリック → 「検査」で開発者ツールを開く

### ステップ 2: コンソールタブを確認

- **Console** タブを選択
- 赤いエラーメッセージを確認
- エラーメッセージの詳細をメモ

**例:**
```
Site structure not loaded. Make sure structure.js is included.
```

### ステップ 3: Network タブで確認

- **Network** タブを選択
- index.html をリロード (Ctrl+Shift+R)
- 「structure.js」「gallery-pages.js」「style.css」を探す
- ステータスコードを確認:
  - `200` = OK
  - `404` = ファイルが見つからない
  - `0` または CORS エラー = サーバー接続エラー

---

## ✅ デバッグツールを使用

最も簡単な方法は、デバッグツールを使用することです:

```
http://localhost:8080/debug.html
```

このページから:
1. 「完全診断を実行」ボタンをクリック
2. すべての診断結果を確認
3. 問題のある項目を特定

---

## ⚡ クイック修正チェックリスト

- [ ] HTTPサーバーが起動している (`python -m http.server 8080`)
- [ ] `site/` ディレクトリで実行している
- [ ] ブラウザで `http://localhost:8080/index.html` にアクセス している
- [ ] `site/structure.json` ファイルが存在する
- [ ] `site/js/structure.js` と `site/js/gallery-pages.js` が生成済みである
- [ ] CSS/JS ファイルが読み込まれている（コンソールにエラーがない）

---

## 🛠️ HTTPサーバーの起動（詳細）

### Windows PowerShell

```powershell
# site ディレクトリに移動
cd d:\Tool\_mytool\_bulk\sitedesign\site

# サーバー起動
python -m http.server 8080

# または特定のバージョンの Python を指定
python3 -m http.server 8080

# サーバーを停止: Ctrl+C
```

### macOS/Linux

```bash
cd /path/to/sitedesign/site
python3 -m http.server 8080
```

### Node.js を使用

```bash
cd site
npx http-server -c-1 -p 8080
```

### VS Code Live Server

1. VS Code で `index.html` を開く
2. 右クリック → "Open with Live Server"

---

## 📊 トラブルシューティングツリー

```
エラーが発生している
│
├─ file:// で開いている？
│  └─ YES → HTTPサーバーで起動 (python -m http.server 8080)
│
├─ site/ ディレクトリで起動している？
│  └─ NO → cd site コマンドで移動してから起動
│
├─ structure.json を修正した直後？
│  └─ YES → tools/build_gallery_pages_map.py を実行して JS を再生成
│
├─ structure.js / gallery-pages.js が存在する？
│  └─ NO → tools/build_gallery_pages_map.py を実行
│
├─ ポート 8080 が使用可能？
│  └─ NO → 別のポート使用 (python -m http.server 8081)
│
└─ コンソールにエラーが表示される？
   └─ YES → エラーメッセージを記録
```

---

## 📞 さらにサポートが必要な場合

以下の情報を用意してください:

1. **エラーメッセージ全文** (コンソールから)
2. **ブラウザ種・バージョン**
3. **HTTPサーバーの起動コマンド**
4. **ファイルパス**
5. **スクリーンショット** (あれば)

これらから問題を特定できます。
