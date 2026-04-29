#!/bin/bash
# HTTPサーバー起動スクリプト
# このスクリプトを実行すると、site/ ディレクトリでHTTPサーバーが起動します

cd "$(dirname "$0")/site"

echo ""
echo "=========================================="
echo "HTTPサーバーを起動しています..."
echo "=========================================="
echo ""
echo "📍 ディレクトリ: $PWD"
echo "🌐 アクセスURL: http://localhost:8080/index.html"
echo "🛑 停止する場合: Ctrl + C を押してください"
echo ""
echo "=========================================="
echo ""

python3 -m http.server 8080
