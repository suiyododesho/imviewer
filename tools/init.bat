@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "DB_SCHEMA_SCRIPT=%ROOT_DIR%\tools\maint_db_schema.py"
set "DB_PATH=%ROOT_DIR%\tools\sqlite\imviewer_maintenance.sqlite3"

echo.
echo ========================================
echo  M06 DB initialization tool
echo ========================================
echo 0: Help
echo 1: Plan - DB schema init/migration (no write)
echo 2: Apply - DB schema init/migration (approval required)
echo Other or empty input: Exit
echo.

set "MENU_NO=%~1"
if not defined MENU_NO (
  set /p MENU_NO=Select menu number and press Enter: 
)
set "MENU_NO=%MENU_NO:\"=%"
echo [DEBUG] MENU_NO="%MENU_NO%"
echo.

if "%MENU_NO%"=="0" goto :help
if "%MENU_NO%"=="1" goto :plan
if "%MENU_NO%"=="2" goto :apply

echo No action selected. Exit.
goto :end

:help
echo.
echo [Help]
echo 1: Show DB schema initialization/migration plan without write
echo 2: Apply DB schema initialization/migration
echo.
echo NOTE: Run this tool once before first UC1/UC2 operation on a new environment.
goto :end

:plan
echo.
echo [Plan: DB schema init/migration]
call :run_schema plan
goto :end

:apply
echo.
echo [Apply: DB schema init/migration]
set "INIT_CONFIRM="
set /p INIT_CONFIRM=Type INIT to execute DB initialization: 
if /I not "%INIT_CONFIRM%"=="INIT" (
  echo Canceled.
  goto :end
)
call :run_schema apply
goto :end

:run_schema
if not exist "%PYTHON_EXE%" (
  echo Error: Python not found: %PYTHON_EXE%
  exit /b 1
)
if not exist "%DB_SCHEMA_SCRIPT%" (
  echo Error: Script not found: %DB_SCHEMA_SCRIPT%
  exit /b 1
)
pushd "%ROOT_DIR%" >nul
"%PYTHON_EXE%" "%DB_SCHEMA_SCRIPT%" %* --db "%DB_PATH%"
set "RC=%ERRORLEVEL%"
popd >nul
if not "%RC%"=="0" (
  echo Error: DB schema command failed. exit code=%RC%
  exit /b %RC%
)
exit /b 0

:end
echo.
echo Done.
endlocal
