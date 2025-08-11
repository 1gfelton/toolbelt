@echo off
echo Building Payette Toolbelt Desktop App...
python build.py
if %ERRORLEVEL% EQU 0 (
    echo Build successful! Check dist/ folder
) else (
    echo Build failed!
)
pause