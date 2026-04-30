@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "BIN_DIR=%ROOT_DIR%\tools\bin"

set "STRUCTURE_SCRIPT=%ROOT_DIR%\tools\maint_build_structure.py"
set "EXTRACT_SCRIPT=%ROOT_DIR%\tools\maint_extract_archives.py"
set "THUMB_SCRIPT=%ROOT_DIR%\tools\maint_build_gallery_thumbnails.py"
set "COVER_SCRIPT=%ROOT_DIR%\tools\maint_refresh_covers.py"
set "STRUCTURE_JS_SCRIPT=%ROOT_DIR%\tools\maint_build_structure_js.py"
set "GALLERY_SCRIPT=%ROOT_DIR%\tools\maint_build_gallery_pages.py"
set "CONFIG_SCRIPT=%ROOT_DIR%\tools\build_site_config.py"
set "HISTORY_SCRIPT=%ROOT_DIR%\tools\maint_sync_history.py"
set "FULL_SCRIPT=%ROOT_DIR%\tools\build_gallery_pages_map.py"
set "BUILD_BIN_SCRIPT=%ROOT_DIR%\tools\build_maintenance_bin.py"

set "STRUCTURE_EXE=%BIN_DIR%\maint_build_structure.exe"
set "EXTRACT_EXE=%BIN_DIR%\maint_extract_archives.exe"
set "THUMB_EXE=%BIN_DIR%\maint_build_gallery_thumbnails.exe"
set "COVER_EXE=%BIN_DIR%\maint_refresh_covers.exe"
set "STRUCTURE_JS_EXE=%BIN_DIR%\maint_build_structure_js.exe"
set "GALLERY_EXE=%BIN_DIR%\maint_build_gallery_pages.exe"
set "CONFIG_EXE=%BIN_DIR%\build_site_config.exe"
set "HISTORY_EXE=%BIN_DIR%\maint_sync_history.exe"
set "FULL_EXE=%BIN_DIR%\build_gallery_pages_map.exe"

set "STATUS_LOG=%TEMP%\sitedesign_maintenance_last.log"

echo.
echo ========================================
echo  structure.json maintenance tool
echo ========================================
echo 0: Help
echo 1: Incremental build (sync + extract + covers + JS)
echo 2: Full rebuild
echo 3: Sync structure.json from contents
echo 4: Extract archive contents
echo 5: Generate gallery thumbnails
echo 6: Refresh content covers in structure.json
echo 7: Generate JS files (structure.js + gallery-pages.js + site-config.js)
echo 8: Sync history.txt
echo 9: Diff rebuild (gallery thumbnails + gallery-pages)
echo 10: Build bin executables (cx_Freeze)
echo Other or empty input: Exit
echo.

set /p MENU_NO=Select menu number and press Enter: 

if "%MENU_NO%"=="0" goto :help
if "%MENU_NO%"=="1" goto :incremental
if "%MENU_NO%"=="2" goto :full
if "%MENU_NO%"=="3" goto :structure_sync
if "%MENU_NO%"=="4" goto :extract_archives
if "%MENU_NO%"=="5" goto :gallery_thumbs
if "%MENU_NO%"=="6" goto :refresh_covers
if "%MENU_NO%"=="7" goto :generate_js
if "%MENU_NO%"=="8" goto :history_sync
if "%MENU_NO%"=="9" goto :diff_rebuild
if "%MENU_NO%"=="10" goto :build_bin

echo.
echo No action selected. Exit.
goto :end

:help
echo.
echo [Help]
echo 1: Incremental build - sync structure.json, extract new archives, refresh covers, regenerate JS
echo 2: Full rebuild - all steps including thumbnail generation and history sync
echo 3: Sync structure.json from contents (add/remove series, rebuild content skeletons)
echo 4: Extract PDF/CBZ/ZIP contents
echo 5: Generate gallery thumbnails
echo 6: Refresh content cover paths in structure.json
echo 7: Generate JS files (structure.js + gallery-pages.js + site-config.js)
echo 8: Sync history.txt
echo 9: Diff rebuild for gallery thumbnails and gallery-pages.js
echo 10: Build bin executables with cx_Freeze
goto :end

:incremental
echo.
echo [Incremental build]
call :run_structure_sync
if errorlevel 1 goto :end
call :run_extract_archives
if errorlevel 1 goto :end
call :run_refresh_covers
if errorlevel 1 goto :end
call :run_structure_js
if errorlevel 1 goto :end
call :run_gallery_pages
if errorlevel 1 goto :end
call :run_site_config
goto :end

:full
echo.
echo [Full rebuild]
call :run_full_rebuild
goto :end

:structure_sync
echo.
echo [Sync structure.json from contents]
call :run_structure_sync
goto :end

:extract_archives
echo.
echo [Extract archive contents]
call :run_extract_archives
goto :end

:gallery_thumbs
echo.
echo [Generate gallery thumbnails]
call :run_gallery_thumbnails
goto :end

:refresh_covers
echo.
echo [Refresh content covers]
call :run_refresh_covers
goto :end

:generate_js
echo.
echo [Generate JS files]
call :run_structure_js
if errorlevel 1 goto :end
call :run_gallery_pages
if errorlevel 1 goto :end
call :run_site_config
goto :end

:history_sync
echo.
echo [Sync history.txt]
call :run_history_sync
goto :end

:diff_rebuild
echo.
echo [Diff rebuild]
call :run_gallery_thumbnails_diff
if errorlevel 1 goto :end
call :run_gallery_pages_diff
goto :end

:build_bin
echo.
echo [Build bin executables]
if not exist "%PYTHON_EXE%" (
  echo Error: Python not found: %PYTHON_EXE%
  echo Bin build requires Python and cx_Freeze.
  exit /b 1
)
if not exist "%BUILD_BIN_SCRIPT%" (
  echo Error: Script not found: %BUILD_BIN_SCRIPT%
  exit /b 1
)
pushd "%ROOT_DIR%" >nul
"%PYTHON_EXE%" "%BUILD_BIN_SCRIPT%" build_exe
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" (
  echo Error: build_maintenance_bin.py failed. exit code=%RC%
  exit /b %RC%
)
echo Success: tools\bin updated.
goto :end

:run_full_rebuild
pushd "%ROOT_DIR%" >nul
if exist "%PYTHON_EXE%" (
  call :show_status "full rebuild running..."
  "%PYTHON_EXE%" "%FULL_SCRIPT%" 1>"%STATUS_LOG%" 2>&1
) else (
  if not exist "%FULL_EXE%" (
    popd >nul
    echo Error: Python not found and executable missing: %FULL_EXE%
    exit /b 1
  )
  call :show_status "full rebuild running..."
  "%FULL_EXE%" 1>"%STATUS_LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" goto :build_failed
if exist "%STATUS_LOG%" type "%STATUS_LOG%"
exit /b 0

:run_structure_sync
call :run_python_or_exe "%STRUCTURE_SCRIPT%" "%STRUCTURE_EXE%" "maint_build_structure.py --sync running..." --sync
exit /b %ERRORLEVEL%

:run_extract_archives
call :run_python_or_exe "%EXTRACT_SCRIPT%" "%EXTRACT_EXE%" "maint_extract_archives.py running..."
exit /b %ERRORLEVEL%

:run_gallery_thumbnails
call :run_python_or_exe "%THUMB_SCRIPT%" "%THUMB_EXE%" "maint_build_gallery_thumbnails.py running..."
exit /b %ERRORLEVEL%

:run_gallery_thumbnails_diff
call :run_python_or_exe "%THUMB_SCRIPT%" "%THUMB_EXE%" "maint_build_gallery_thumbnails.py --diff running..." --diff
exit /b %ERRORLEVEL%

:run_refresh_covers
call :run_python_or_exe "%COVER_SCRIPT%" "%COVER_EXE%" "maint_refresh_covers.py running..."
exit /b %ERRORLEVEL%

:run_structure_js
call :run_python_or_exe "%STRUCTURE_JS_SCRIPT%" "%STRUCTURE_JS_EXE%" "maint_build_structure_js.py running..."
exit /b %ERRORLEVEL%

:run_gallery_pages
call :run_python_or_exe "%GALLERY_SCRIPT%" "%GALLERY_EXE%" "maint_build_gallery_pages.py running..."
exit /b %ERRORLEVEL%

:run_gallery_pages_diff
call :run_python_or_exe "%GALLERY_SCRIPT%" "%GALLERY_EXE%" "maint_build_gallery_pages.py --diff running..." --diff
exit /b %ERRORLEVEL%

:run_site_config
call :run_python_or_exe "%CONFIG_SCRIPT%" "%CONFIG_EXE%" "build_site_config.py running..."
exit /b %ERRORLEVEL%

:run_history_sync
call :run_python_or_exe "%HISTORY_SCRIPT%" "%HISTORY_EXE%" "maint_sync_history.py running..."
exit /b %ERRORLEVEL%

:run_python_or_exe
set "SCRIPT_PATH=%~1"
set "EXE_PATH=%~2"
set "STATUS_TEXT=%~3"
set "EXTRA_ARGS="
if not "%~4"=="" set "EXTRA_ARGS=%~4"
if not "%~5"=="" set "EXTRA_ARGS=%EXTRA_ARGS% %~5"
if not "%~6"=="" set "EXTRA_ARGS=%EXTRA_ARGS% %~6"
if not "%~7"=="" set "EXTRA_ARGS=%EXTRA_ARGS% %~7"
if not "%~8"=="" set "EXTRA_ARGS=%EXTRA_ARGS% %~8"
if not "%~9"=="" set "EXTRA_ARGS=%EXTRA_ARGS% %~9"
pushd "%ROOT_DIR%" >nul
if exist "%PYTHON_EXE%" (
  if not exist "%SCRIPT_PATH%" (
    popd >nul
    echo Error: Script not found: %SCRIPT_PATH%
    exit /b 1
  )
  call :show_status "%STATUS_TEXT%"
  "%PYTHON_EXE%" "%SCRIPT_PATH%" %EXTRA_ARGS% 1>"%STATUS_LOG%" 2>&1
) else (
  if not exist "%EXE_PATH%" (
    popd >nul
    echo Error: Python not found and executable missing: %EXE_PATH%
    exit /b 1
  )
  call :show_status "%STATUS_TEXT%"
  "%EXE_PATH%" %EXTRA_ARGS% 1>"%STATUS_LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" goto :build_failed
if exist "%STATUS_LOG%" type "%STATUS_LOG%"
exit /b 0

:build_failed
call :show_status "failed"
echo Error: Build step failed. exit code=%RC%
if exist "%STATUS_LOG%" (
  echo.
  echo [Last script output]
  type "%STATUS_LOG%"
)
exit /b %RC%

:show_status
cls
echo.
echo ========================================
echo  structure.json maintenance tool
echo ========================================
echo  status: %~1
echo.
exit /b 0

:end
echo.
echo Done.
endlocal

echo.
echo Done.
endlocal
