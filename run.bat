@echo off
chcp 65001 >nul
cd /d "%~dp0"
set MPLCONFIGDIR=%TEMP%\mplconfig
if not exist "%MPLCONFIGDIR%" mkdir "%MPLCONFIGDIR%"
"C:\ProgramData\Anaconda3\python.exe" run.py
if errorlevel 1 (
  echo.
  echo 程序异常退出，请截图错误信息反馈。
  pause
)
