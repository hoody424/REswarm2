@echo off
echo ==============================================================
echo  Building Turtle Beach KB7 Command Center Standalone App (.exe)
echo ==============================================================
python -m PyInstaller --clean KB7_Command_Center.spec
echo.
echo [+] Standalone executable ready at: dist\KB7_Command_Center.exe
pause
