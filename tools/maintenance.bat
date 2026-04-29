@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "BIN_DIR=%ROOT_DIR%\tools\bin"

set "THUMB_SCRIPT=%ROOT_DIR%\tools\generate_thumbnails.py"
set "CONFIG_SCRIPT=%ROOT_DIR%\tools\build_site_config.py"
set "BUILD_SCRIPT=%ROOT_DIR%\tools\build_gallery_pages_map.py"
set "BUILD_BIN_SCRIPT=%ROOT_DIR%\tools\build_maintenance_bin.py"

set "THUMB_EXE=%BIN_DIR%\generate_thumbnails.exe"
set "CONFIG_EXE=%BIN_DIR%\build_site_config.exe"
set "BUILD_EXE=%BIN_DIR%\build_gallery_pages_map.exe"

set "STATUS_LOG=%TEMP%\sitedesign_maintenance_last.log"

echo.
echo ========================================
echo  structure.json maintenance tool
echo ========================================
echo 0: Help
echo 1: Run all (thumbnail + site-config + gallery-pages)
echo 2: Generate thumbnails
echo 3: Build site-config and gallery-pages
echo 4: Diff build (gallery-pages --diff)
echo 5: Build bin executables (cx_Freeze)
echo Other or empty input: Exit
echo.

set /p MENU_NO=Select menu number and press Enter: 

if "%MENU_NO%"=="0" goto :help
if "%MENU_NO%"=="1" goto :all
if "%MENU_NO%"=="2" goto :thumb
if "%MENU_NO%"=="3" goto :build
if "%MENU_NO%"=="4" goto :build_diff
if "%MENU_NO%"=="5" goto :build_bin

echo.
echo No action selected. Exit.
goto :end

:help
echo.
echo [Help]
echo This batch runs site maintenance scripts.
echo If Python exists in .venv, python scripts are used first.
echo If Python does not exist, executables in tools\bin are used.
echo.
echo 1: Run all
echo 2: Thumbnails only
echo 3: site-config + gallery-pages
echo 4: Diff build for gallery-pages
echo 5: Build bin executables with cx_Freeze
goto :end

:all
echo.
echo [Run all]
call :run_thumbnail
if errorlevel 1 goto :end
call :run_build
if errorlevel 1 goto :end
goto :end

:thumb
echo.
echo [Generate thumbnails]
call :run_thumbnail
goto :end

:build
echo.
echo [Build site-config and gallery-pages]
call :run_build
goto :end

:build_diff
echo.
echo [Diff build]
call :run_build_diff
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

:run_thumbnail
if exist "%PYTHON_EXE%" (
  if not exist "%THUMB_SCRIPT%" (
    echo Error: Script not found: %THUMB_SCRIPT%
    exit /b 1
  )
  pushd "%ROOT_DIR%" >nul
  echo Running: generate_thumbnails.py
  "%PYTHON_EXE%" "%THUMB_SCRIPT%"
  set "RC=%ERRORLEVEL%"
  popd >nul
) else (
  if not exist "%THUMB_EXE%" (
    echo Error: Python not found and executable missing: %THUMB_EXE%
    exit /b 1
  )
  pushd "%ROOT_DIR%" >nul
  echo Running: generate_thumbnails.exe
  "%THUMB_EXE%"
  set "RC=%ERRORLEVEL%"
  popd >nul
)
if not "%RC%"=="0" (
  echo Error: thumbnail step failed. exit code=%RC%
  exit /b %RC%
)
echo Success: thumbnails
exit /b 0

:run_build
call :run_site_config
if errorlevel 1 exit /b %ERRORLEVEL%
call :run_gallery_pages
if errorlevel 1 exit /b %ERRORLEVEL%
echo Success: site-config + gallery-pages
exit /b 0

:run_build_diff
call :run_site_config
if errorlevel 1 exit /b %ERRORLEVEL%
call :run_gallery_pages_diff
if errorlevel 1 exit /b %ERRORLEVEL%
echo Success: diff build
exit /b 0

:run_site_config
pushd "%ROOT_DIR%" >nul
if exist "%PYTHON_EXE%" (
  if not exist "%CONFIG_SCRIPT%" (
    popd >nul
    echo Error: Script not found: %CONFIG_SCRIPT%
    exit /b 1
  )
  call :show_status "build_site_config.py running..."
  "%PYTHON_EXE%" "%CONFIG_SCRIPT%" 1>"%STATUS_LOG%" 2>&1
) else (
  if not exist "%CONFIG_EXE%" (
    popd >nul
    echo Error: Python not found and executable missing: %CONFIG_EXE%
    exit /b 1
  )
  call :show_status "build_site_config.exe running..."
  "%CONFIG_EXE%" 1>"%STATUS_LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" goto :build_failed
exit /b 0

:run_gallery_pages
pushd "%ROOT_DIR%" >nul
if exist "%PYTHON_EXE%" (
  if not exist "%BUILD_SCRIPT%" (
    popd >nul
    echo Error: Script not found: %BUILD_SCRIPT%
    exit /b 1
  )
  call :show_status "build_gallery_pages_map.py running..."
  "%PYTHON_EXE%" "%BUILD_SCRIPT%"
) else (
  if not exist "%BUILD_EXE%" (
    popd >nul
    echo Error: Python not found and executable missing: %BUILD_EXE%
    exit /b 1
  )
  call :show_status "build_gallery_pages_map.exe running..."
  "%BUILD_EXE%"
)
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" goto :build_failed
exit /b 0

:run_gallery_pages_diff
pushd "%ROOT_DIR%" >nul
if exist "%PYTHON_EXE%" (
  if not exist "%BUILD_SCRIPT%" (
    popd >nul
    echo Error: Script not found: %BUILD_SCRIPT%
    exit /b 1
  )
  call :show_status "build_gallery_pages_map.py --diff running..."
  "%PYTHON_EXE%" "%BUILD_SCRIPT%" --diff
) else (
  if not exist "%BUILD_EXE%" (
    popd >nul
    echo Error: Python not found and executable missing: %BUILD_EXE%
    exit /b 1
  )
  call :show_status "build_gallery_pages_map.exe --diff running..."
  "%BUILD_EXE%" --diff
)
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" goto :build_failed
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
