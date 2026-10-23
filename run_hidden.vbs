' Runs run_local.bat without a console window. Finds its own folder (no hardcoded Korean path).
Dim fso, shell, here
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run """" & here & "\run_local.bat""", 0, False
