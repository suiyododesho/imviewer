@echo off
setlocal
chcp 932 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "SCRIPT_PATH=%ROOT_DIR%\tools\convert_vlc.py"

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

if "%~1"=="" (
  echo.
  set /p INPUT_PATH=Enter a video file or folder path: 
  if "%INPUT_PATH%"=="" (
    echo No path was entered. Exit.
    pause
    exit /b 0
  )
  pushd "%ROOT_DIR%" >nul
  "%PYTHON_EXE%" "%SCRIPT_PATH%" "%INPUT_PATH%"
  set "RC=%ERRORLEVEL%"
  popd >nul
) else (
  pushd "%ROOT_DIR%" >nul
  "%PYTHON_EXE%" "%SCRIPT_PATH%" %*
  set "RC=%ERRORLEVEL%"
  popd >nul
)

echo.
if "%RC%"=="0" (
  echo VLC conversion finished.
) else (
  echo VLC conversion failed. See convert.error for details.
)
pause
exit /b %RC%
