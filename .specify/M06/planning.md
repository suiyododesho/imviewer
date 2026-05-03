# planning.md

作戦を考えるための記録

## 現状調査の一次結果（コード読解ベース）

実測の秒数まではまだ取れていませんが、現行実装を見る限り、時間がかかりやすいポイントはかなり明確です。

UC1の標準フローが重い工程を毎回通る設計
content_add.bat:76 で毎回、構造同期→アーカイブ展開→サムネ生成→カバー更新→JS生成を順番実行しています。
さらに content_add.bat:148 と content_add.bat:160 で NAS へ contents と thumbnail を再走査コピーしています。
差分モードは実装済みですが、ここでは使っていません。

差分モードでも「全件確認」が残る
ギャラリー差分はありますが、maint_build_gallery_pages.py:538 で全ギャラリーを再検査して変更検知しています。
また maint_build_gallery_pages.py:132 の再帰走査と maint_build_gallery_pages.py:543 の再構築ループが大きいデータで効きます。

structure と JS は全量書き出し
maint_structure_lib.py:91 と maint_structure_lib.py:616 で全量 dump。
構造同期も maint_build_structure.py:36 と maint_build_structure.py:179 でディレクトリ全走査寄りです。

UC2（CSV編集）は更新後の再生成が過剰
メタデータ適用後に maint_metadata.py:236 と maint_metadata.py:237 で structure.js と gallery-pages.js を再生成しています。
ただし、現在の編集対象 maint_metadata.py:51 は path を変えないため、gallery-pages.js 再生成は多くのケースで不要です（ここは即効で削減可能）。

フロントは全ページで大きいデータを読む構造
トップ含む各ページで index.html:69, index.html:70, project.html:64, person.html:76, gallery.html:1076 のように structure.js / gallery-pages.js を読み込んでいます。
表示効率と軽量化を両立するには、データ分割配信が有効です。

## 抜本対策の方向性（DBも視野）

結論としては「DBを運用中サイトの実行基盤にする」のではなく、
「メンテナンス時の正本をDB化し、静的サイト用アーティファクトを生成する」構成が最適です。
（サーバ不要・ローカル完結という現方針と両立）

正本を SQLite 化
管理対象を tables 化（genre, series, content, gallery_page, person, label, 履歴, ジョブ）。
CSVは入出力インターフェースとして残す。

生成物は今まで通り静的ファイル
site 側には structure 系JSON/JS と gallery-pages 系JSON/JSを生成。
フロントは段階的に「全量1ファイル」から「ジャンル/シリーズ単位の分割JSON」へ移行。

差分判定を hash ベースへ
series 単位で content fingerprint を保持し、変化した series だけ再処理。
これで UC1 の「全件再抽出・全件再サムネ・全件再マップ」から脱却。

NAS 転送は manifest 同期
変更ファイルリストを先に作り、必要ファイルのみ転送。
robocopy 一発再帰より通信時間と誤操作リスクを下げやすいです。

## UC別の改善案

UC1 コンテンツ追加
準備した新規フォルダのみ取り込み
→ DBに upsert
→ 影響 series のみ展開/サムネ/map再生成
→ 変更ファイルのみNASへ反映

UC2 メタデータ編集
DBからCSV export（必要列のみ）
→ 手動編集
→ validate + dry-run
→ DB反映
→ structure系のみ再生成（gallery-pagesは path 変更時のみ）

まず着手すべき順序（効果が大きい順）

計測を先に入れる（処理時間・走査件数・転送バイト）
metadata apply で gallery-pages 再生成を条件化
content_add の標準経路を差分寄りに変更
生成データの分割（まずは gallery-pages を series 単位）
SQLite 正本 + 生成パイプラインへ段階移行
次に私が出せる具体成果

計測設計書（どの処理で何を記録するか、ログ形式、KPI）
SQLite スキーマ案と移行手順（現行 structure.json 互換）
UC1/UC2 の新CLI案（安全な dry-run / plan / apply を含む）
フロントの段階移行案（既存ページ互換を保つロード戦略）