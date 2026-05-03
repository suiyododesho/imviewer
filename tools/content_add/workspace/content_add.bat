@echo off
setlocal enabledelayedexpansion
chcp 932 >nul

set "WORKSPACE_DIR=%~dp0"
if "!WORKSPACE_DIR:~-1!"=="\" set "WORKSPACE_DIR=!WORKSPACE_DIR:~0,-1!"

for %%I in ("!WORKSPACE_DIR!\..\..") do set "TOOLS_DIR=%%~fI"
for %%I in ("!TOOLS_DIR!\..")        do set "ROOT_DIR=%%~fI"

set "PYTHON_EXE=!ROOT_DIR!\.venv\Scripts\python.exe"
set "CONFIG_FILE=!WORKSPACE_DIR!\content_add_config.json"
set "IMVIEWER_SITE_DIR=!WORKSPACE_DIR!"

:: Parse arguments (--diff: incremental mode using history.txt targets)
set "DIFF_FLAG="
:parse_args
if "%~1"=="--diff" (
    set "DIFF_FLAG=--diff"
    shift
    goto :parse_args
)

echo.
echo ========================================
echo  content_add tool
echo ========================================
echo.
if "!DIFF_FLAG!"=="--diff" (echo  Mode: DIFF ^(incremental^)) else (echo  Mode: FULL)
echo.

if not exist "!PYTHON_EXE!" (
    echo [ERROR] Python not found: !PYTHON_EXE!
    goto :end
)

if not exist "!CONFIG_FILE!" (
    echo [ERROR] Config file not found: !CONFIG_FILE!
    echo Please edit content_add_config.json with the server site_dir.
    goto :end
)

:: Read server.site_dir from config
set "SERVER_SITE_DIR="
set "TMP_SITE_DIR_FILE=%TEMP%\imviewer_content_add_site_dir_%RANDOM%.txt"
"!PYTHON_EXE!" -c "import json,sys; c=json.load(open(sys.argv[1], 'r', encoding='utf-8')); print(str(c.get('server', {}).get('site_dir', '')).strip())" "!CONFIG_FILE!" > "!TMP_SITE_DIR_FILE!" 2>nul
if exist "!TMP_SITE_DIR_FILE!" (
    set /p SERVER_SITE_DIR=<"!TMP_SITE_DIR_FILE!"
    del /q "!TMP_SITE_DIR_FILE!" >nul 2>&1
)

if "!SERVER_SITE_DIR!"=="" (
    echo [ERROR] server.site_dir is empty in config
    goto :end
)

if "!SERVER_SITE_DIR!"=="Z:\path\to\server\site" (
    echo [ERROR] server.site_dir is not configured. Please edit content_add_config.json.
    goto :end
)

if not exist "!SERVER_SITE_DIR!\" (
    echo [ERROR] Server site dir not found: !SERVER_SITE_DIR!
    goto :end
)

echo Workspace dir  : !WORKSPACE_DIR!
echo Server site dir: !SERVER_SITE_DIR!
echo.

:: ===== FETCH PHASE =====
echo [1/3] Fetch: copying structure.json from server...
robocopy "!SERVER_SITE_DIR!" "!WORKSPACE_DIR!" structure.json /IS /IT /NFL /NDL /NJH
if !ERRORLEVEL! GEQ 8 (
    echo [ERROR] robocopy failed during fetch. exit code=!ERRORLEVEL!
    goto :end
)
echo Fetch complete.
echo.

:: ===== PROCESS PHASE =====
echo [2/3] Process: running maintenance scripts...
echo.

echo [2-1] Sync structure.json from contents...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_build_structure.py" --sync --no-remove-missing
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_build_structure.py failed. exit code=!RC!
    goto :end
)
echo.

echo [2-2] Extract archives...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_extract_archives.py"
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_extract_archives.py failed. exit code=!RC!
    goto :end
)
echo.

echo [2-3] Generate gallery thumbnails...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_build_gallery_thumbnails.py" !DIFF_FLAG!
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_build_gallery_thumbnails.py failed. exit code=!RC!
    goto :end
)
echo.

echo [2-4] Refresh content covers...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_refresh_covers.py"
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_refresh_covers.py failed. exit code=!RC!
    goto :end
)
echo.

echo [2-5] Generate JS files (structure.js)...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_build_structure_js.py"
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_build_structure_js.py failed. exit code=!RC!
    goto :end
)

echo [2-6] Generate JS files (gallery-pages.js)...
pushd "!ROOT_DIR!" >nul
"!PYTHON_EXE!" "!TOOLS_DIR!\maint_build_gallery_pages.py" !DIFF_FLAG!
set "RC=!ERRORLEVEL!"
popd >nul
if not "!RC!"=="0" (
    echo [ERROR] maint_build_gallery_pages.py failed. exit code=!RC!
    goto :end
)
echo.

echo Process complete.
echo.

:: ===== UPLOAD PHASE =====
echo [3/3] Upload: copying results to server...
echo.

echo Uploading contents/...
if exist "!WORKSPACE_DIR!\contents\" (
    robocopy "!WORKSPACE_DIR!\contents" "!SERVER_SITE_DIR!\contents" /E /NFL /NDL /NJH
    if !ERRORLEVEL! GEQ 8 (
        echo [ERROR] robocopy failed during contents upload. exit code=!ERRORLEVEL!
        goto :end
    )
) else (
    echo No contents directory. Skipping.
)
echo.

echo Uploading thumbnail/...
if exist "!WORKSPACE_DIR!\thumbnail\" (
    robocopy "!WORKSPACE_DIR!\thumbnail" "!SERVER_SITE_DIR!\thumbnail" /E /NFL /NDL /NJH
    if !ERRORLEVEL! GEQ 8 (
        echo [ERROR] robocopy failed during thumbnail upload. exit code=!ERRORLEVEL!
        goto :end
    )
) else (
    echo No thumbnail directory. Skipping.
)
echo.

echo Uploading structure.json and JS files...
if not exist "!SERVER_SITE_DIR!\js\" mkdir "!SERVER_SITE_DIR!\js"
robocopy "!WORKSPACE_DIR!" "!SERVER_SITE_DIR!" structure.json /IS /IT /NFL /NDL /NJH
if !ERRORLEVEL! GEQ 8 (
    echo [ERROR] robocopy failed during structure.json upload. exit code=!ERRORLEVEL!
    goto :end
)
if exist "!WORKSPACE_DIR!\js\structure.js" (
    robocopy "!WORKSPACE_DIR!\js" "!SERVER_SITE_DIR!\js" structure.js /IS /IT /NFL /NDL /NJH
    if !ERRORLEVEL! GEQ 8 (
        echo [ERROR] robocopy failed during structure.js upload. exit code=!ERRORLEVEL!
        goto :end
    )
)
if exist "!WORKSPACE_DIR!\js\gallery-pages.js" (
    robocopy "!WORKSPACE_DIR!\js" "!SERVER_SITE_DIR!\js" gallery-pages.js /IS /IT /NFL /NDL /NJH
    if !ERRORLEVEL! GEQ 8 (
        echo [ERROR] robocopy failed during gallery-pages.js upload. exit code=!ERRORLEVEL!
        goto :end
    )
)
echo.

echo ========================================
echo  All done!
echo ========================================

:end
endlocal
pause