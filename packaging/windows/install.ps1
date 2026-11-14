# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File packaging\windows\install.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Write-Host "Python 3.9+ is required: https://www.python.org/downloads/ (tick 'Add to PATH')"; exit 1 }
py -m pip install --user pywebview psutil
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\CRYSTA AI.lnk")
$lnk.TargetPath = "wscript.exe"
$lnk.Arguments = "`"$root\packaging\windows\CRYSTA.vbs`""
$lnk.WorkingDirectory = $root
$lnk.Description = "CRYSTA AI"
$lnk.Save()
Write-Host "Done. Double-click 'CRYSTA AI' on your Desktop. Self-test: py desktop.py --check"
