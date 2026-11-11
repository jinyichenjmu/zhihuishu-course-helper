@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Please create .venv and install requirements-build.txt first. & pause & exit /b 1)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name CourseHelper-Public --add-data "snapshot.js;." --collect-all DrissionPage main.py
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
copy /Y README.md "dist\CourseHelper-Public\README.md" >nul
echo Build complete: dist\CourseHelper-Public
pause
