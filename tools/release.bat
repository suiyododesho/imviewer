@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "RELEASE_SCRIPT=%ROOT_DIR%\tools\release.py"

echo.
echo ========================================
echo  リリースツール system / data 分離版
echo ========================================
echo 1: システム更新 minor
echo 2: システム更新 major
echo 3: システム更新 dry-run
echo 4: データ更新
echo 5: データ更新 dry-run
echo 6: データ更新 rollback
echo 7: データ更新 rollback 指定
echo.
echo その他の入力または空入力で終了します。
echo.
echo 番号を入力してください
set /p "MENU_NO=> "
if "%MENU_NO%"=="" goto :end
if "%MENU_NO%"=="1" goto :system_release
if "%MENU_NO%"=="2" goto :system_release_major
if "%MENU_NO%"=="3" goto :system_dry_run
if "%MENU_NO%"=="4" goto :data_release
if "%MENU_NO%"=="5" goto :data_dry_run
if "%MENU_NO%"=="6" goto :data_rollback
if "%MENU_NO%"=="7" goto :data_rollback_ver

echo.
echo 指定された番号は対象外です。終了します。
goto :end

:system_release
echo.
echo システム更新を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release system
if errorlevel 1 goto :end
echo 完了: システム更新が完了しました。
goto :end

:system_release_major
echo.
echo システム major 更新を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release system --major
if errorlevel 1 goto :end
echo 完了: システム major 更新が完了しました。
goto :end

:system_dry_run
echo.
echo システム dry-run を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release system --dry-run
if errorlevel 1 goto :end
echo 完了: システム dry-run が完了しました。
goto :end

:data_release
echo.
echo データ更新を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release data
if errorlevel 1 goto :end
echo 完了: データ更新が完了しました。
goto :end

:data_dry_run
echo.
echo データ dry-run を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release data --dry-run
if errorlevel 1 goto :end
echo 完了: データ dry-run が完了しました。
goto :end

:data_rollback
echo.
echo データ rollback を開始します...
call :check_env
if errorlevel 1 goto :end
call :run_release data --rollback
if errorlevel 1 goto :end
echo 完了: データ rollback が完了しました。
goto :end

:data_rollback_ver
echo.
echo ロールバックするデータ版を入力してください 例: v1.2
set /p "TARGET_VER=> "
if "%TARGET_VER%"=="" goto :data_rollback_ver_cancel
call :check_env
if errorlevel 1 goto :end
call :run_release data --rollback --version %TARGET_VER%
if errorlevel 1 goto :end
echo 完了: データ rollback が完了しました。
goto :end

:data_rollback_ver_cancel
echo キャンセルしました。
goto :end

:run_release
pushd "%ROOT_DIR%" >nul
"%PYTHON_EXE%" "%RELEASE_SCRIPT%" %*
set "RC=%ERRORLEVEL%"
popd >nul
if "%RC%"=="0" goto :run_release_ok
echo エラー: release.py の実行に失敗しました。終了コード=%RC%
exit /b %RC%

:run_release_ok
exit /b 0

:check_env
if exist "%PYTHON_EXE%" goto :check_release_script
echo エラー: Python 実行ファイルが見つかりません: %PYTHON_EXE%
exit /b 1

:check_release_script
if exist "%RELEASE_SCRIPT%" goto :check_env_ok
echo エラー: スクリプトが見つかりません: %RELEASE_SCRIPT%
exit /b 1

:check_env_ok
exit /b 0

:end
echo.
pause

