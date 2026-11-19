@echo off
REM Start Jeevandhara with one command (Windows): double-click run.bat
REM Creates backend\.venv and installs dependencies the first time.
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
    echo Creating virtual environment in backend\.venv ...
    py -3 -m venv backend\.venv 2>nul || python -m venv backend\.venv
    if errorlevel 1 (
        echo Could not create a virtual environment. Please install Python 3.9+ from python.org.
        pause
        exit /b 1
    )
)

if not exist "backend\.venv\.requirements-installed" (
    echo Installing dependencies ...
    "backend\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    "backend\.venv\Scripts\python.exe" -m pip install --quiet -r backend\requirements.txt
    if errorlevel 1 (
        echo Installing dependencies failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    type nul > "backend\.venv\.requirements-installed"
)

if "%PORT%"=="" set PORT=8000
REM Open the browser a few seconds after the server starts.
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:%PORT%/"
"backend\.venv\Scripts\python.exe" backend\main.py
pause
