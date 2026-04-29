@echo off
REM HTTPサーバー起動スクリプト
REM このスクリプトを実行すると、site/ ディレクトリでHTTPサーバーが起動します

cd /d "%~dp0site"

echo.
echo ==========================================
echo HTTPサーバーを起動しています...
echo ==========================================
echo.
echo 📍 ディレクトリ: %CD%
echo 🌐 アクセスURL: http://localhost:8080/index.html
echo 🛑 停止する場合: Ctrl + C を押してください
echo.
echo ==========================================
echo.

python -m http.server 8080

pause
