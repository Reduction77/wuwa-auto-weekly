@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "$pythonPath = if (Test-Path '.venv\Scripts\pythonw.exe') { (Resolve-Path '.venv\Scripts\pythonw.exe').Path } else { (Get-Command pythonw.exe -ErrorAction Stop).Source }; Start-Process -FilePath $pythonPath -ArgumentList 'main.py' -WorkingDirectory (Get-Location).Path -Verb RunAs -WindowStyle Hidden"
if errorlevel 1 pause
