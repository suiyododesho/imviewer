@echo off
chcp 932 >nul
setlocal

set "SCRIPT_DIR=%~dp0"

echo.
echo ========================================
echo  imviewer update wrapper (calls update.ps1)
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy RemoteSigned -File "%SCRIPT_DIR%update.ps1" %*

endlocal
