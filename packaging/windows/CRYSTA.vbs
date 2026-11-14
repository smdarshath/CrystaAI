' Double-click to start CRYSTA AI without a console window (needs Python + pywebview installed once: see install.ps1)
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
sh.CurrentDirectory = root
On Error Resume Next
sh.Run "pyw """ & root & "\desktop.py""", 0, False
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "pythonw """ & root & "\desktop.py""", 0, False
End If
