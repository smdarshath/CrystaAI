@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw desktop.py %*) || (start "" pythonw desktop.py %*)
