@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "THUMB_SCRIPT=%ROOT_DIR%\tools\generate_thumbnails.py"
set "BUILD_SCRIPT=%ROOT_DIR%\tools\build_gallery_pages_map.py"
set "CONFIG_SCRIPT=%ROOT_DIR%\tools\build_site_config.py"
set "STATUS_LOG=%TEMP%\sitedesign_maintenance_last.log"

echo.
echo ========================================
echo  structure.json メンテナンスツール 
echo ========================================
echo 0: ヘルプ
echo 1: 全実施 (サムネイル作成 + サイト設定js生成 + ページ構造更新)
echo 2: サムネイル作成
echo 3: サイト設定js生成 + ページ構造(js)更新
echo 4: 差分ビルド (history.txt の next 対象のみページ構造更新)
echo その他 (空文字を含む): 何もしない
echo.

set /p MENU_NO=番号を入力して Enter を押してください: 

if "%MENU_NO%"=="0" goto :help
if "%MENU_NO%"=="1" goto :all
if "%MENU_NO%"=="2" goto :thumb
if "%MENU_NO%"=="3" goto :build
if "%MENU_NO%"=="4" goto :build_diff

echo.
echo 指定された番号は実行対象外です。何も行わず終了します。
goto :end

:help
echo.
echo [ヘルプ]
echo このバッチは structure.json 編集後のメンテナンス実行用です。
echo 実行前に structure.json の編集が必要です。
echo.
echo 1: 全部実行
echo 2: サムネイルのみ
echo 3: サイト設定JS生成 + ページ構造JS更新
echo 4: 差分ビルド (history.txt の next 対象のみページ構造JS更新)
goto :end

:all
echo.
echo [全実施] サムネイル作成、サイト設定js生成、ページ構造更新を実行します。
call :run_thumbnail
if errorlevel 1 goto :end
call :run_build
goto :end

:thumb
echo.
echo [サムネイル作成] を実行します。
call :run_thumbnail
goto :end

:build
echo.
echo [サイト設定js生成 + ページ構造(js)更新] を実行します。
call :run_build
goto :end

:build_diff
echo.
echo [差分ビルド] サイト設定js生成 + history.txt の next 対象のみページ構造(js)更新を実行します。
call :run_build_diff
goto :end

:run_thumbnail
if not exist "%PYTHON_EXE%" (
  echo エラー: Python 実行ファイルが見つかりません: %PYTHON_EXE%
  exit /b 1
)
if not exist "%THUMB_SCRIPT%" (
  echo エラー: スクリプトが見つかりません: %THUMB_SCRIPT%
  exit /b 1
)
pushd "%ROOT_DIR%" >nul
echo 実行中: generate_thumbnails.py
"%PYTHON_EXE%" "%THUMB_SCRIPT%"
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" (
  echo エラー: generate_thumbnails.py の実行に失敗しました。終了コード=%RC%
  exit /b %RC%
)
echo 完了: サムネイル作成
exit /b 0

:run_build
if not exist "%PYTHON_EXE%" (
  echo エラー: Python 実行ファイルが見つかりません: %PYTHON_EXE%
  exit /b 1
)
if not exist "%CONFIG_SCRIPT%" (
  echo エラー: スクリプトが見つかりません: %CONFIG_SCRIPT%
  exit /b 1
)
if not exist "%BUILD_SCRIPT%" (
  echo エラー: スクリプトが見つかりません: %BUILD_SCRIPT%
  exit /b 1
)

pushd "%ROOT_DIR%" >nul
call :show_status "build_site_config.py 実行中..."
"%PYTHON_EXE%" "%CONFIG_SCRIPT%" 1>"%STATUS_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :build_failed

call :show_status "build_gallery_pages_map.py 実行中..."
"%PYTHON_EXE%" "%BUILD_SCRIPT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :build_failed

popd >nul
call :show_status "完了"
echo 完了: サイト設定js生成 + ページ構造(js)更新
exit /b 0

:run_build_diff
if not exist "%PYTHON_EXE%" (
  echo エラー: Python 実行ファイルが見つかりません: %PYTHON_EXE%
  exit /b 1
)
if not exist "%CONFIG_SCRIPT%" (
  echo エラー: スクリプトが見つかりません: %CONFIG_SCRIPT%
  exit /b 1
)
if not exist "%BUILD_SCRIPT%" (
  echo エラー: スクリプトが見つかりません: %BUILD_SCRIPT%
  exit /b 1
)

pushd "%ROOT_DIR%" >nul
call :show_status "build_site_config.py 実行中..."
"%PYTHON_EXE%" "%CONFIG_SCRIPT%" 1>"%STATUS_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :build_failed

call :show_status "build_gallery_pages_map.py --diff 実行中..."
"%PYTHON_EXE%" "%BUILD_SCRIPT%" --diff
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :build_failed

popd >nul
call :show_status "完了"
echo 完了: 差分ビルド (history.txt の next 対象のみページ構造(js)更新)
exit /b 0

:build_failed
popd >nul
call :show_status "失敗"
echo エラー: 生成スクリプトの実行に失敗しました。終了コード=%RC%
if exist "%STATUS_LOG%" (
  echo.
  echo [直前スクリプトの出力]
  type "%STATUS_LOG%"
)
exit /b %RC%

:show_status
cls
echo.
echo ========================================
echo  structure.json メンテナンスツール
echo ========================================
echo  現在: %~1
echo.
exit /b 0

:end
echo.
echo 処理を終了します。
endlocal