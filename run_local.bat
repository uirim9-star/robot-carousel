@echo off
rem robot-carousel PC part. Task Scheduler calls run_hidden.vbs, which calls this.
rem No bypassPermissions: only the tools listed below are allowed.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ==== [%date% %time%] start >> "data\local.log"
call claude -p --settings "%USERPROFILE%\.claude\settings.unattended.json" --allowedTools "Read" "Glob" "Grep" "Edit" "Write" "Bash(git:*)" "Bash(python:*)" -- "Read ROUTINE.md and follow it exactly." >> "data\local.log" 2>&1
echo ==== [%date% %time%] exit=%errorlevel% >> "data\local.log"
