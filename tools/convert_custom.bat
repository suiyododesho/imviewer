@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "SCRIPT_PATH=%ROOT_DIR%\tools\convert.py"
set "CONFIG_PATH=%ROOT_DIR%\tools\convert_config.json"

if not exist "%PYTHON_EXE%" (
  echo Error: Python executable was not found.
  echo %PYTHON_EXE%
  pause
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo Error: Script file was not found.
  echo %SCRIPT_PATH%
  pause
  exit /b 1
)

pushd "%ROOT_DIR%" >nul
"%PYTHON_EXE%" "%SCRIPT_PATH%" --config "%CONFIG_PATH%"
set "RC=%ERRORLEVEL%"
popd >nul

echo.
if "%RC%"=="0" (
  echo Video conversion finished.
) else (
  echo Video conversion failed. See convert.error for details.
)
pause
exit /b %RC%
