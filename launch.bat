@echo off
rem Launch QQQ x SCHD Rebalance Buddy (window GUI)
setlocal
cd /d "%~dp0"

set "PY="
if exist "C://Python314//pythonw.exe" set "PY=C://Python314//pythonw.exe"
if not defined PY (
  for %%P in (pythonw.exe) do if not defined PY if exist "%%~$PATH:P" set "PY=%%~$PATH:P"
)
if not defined PY (
  for %%P in (python.exe) do if not defined PY if exist "%%~$PATH:P" set "PY=%%~$PATH:P"
)
if not defined PY (
  echo Python 3 with tkinter was not found on this computer.
  echo Please install Python 3.10+ from https://www.python.org/downloads/
  pause
  exit /b 1
)

start "" "%PY%" "main.py"
exit /b 0
