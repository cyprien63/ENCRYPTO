@echo off
title ENCRYPTO Launcher
echo =========================================
echo       ENCRYPTO launcher for Windows      
echo =========================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3 and try again.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo [INFO] Creating virtual environment .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Install/Upgrade dependencies
echo [INFO] Installing/Checking dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Run application
echo [INFO] Launching ENCRYPTO...
python app.py
if %errorlevel% neq 0 (
    echo [WARNING] ENCRYPTO exited with an error code.
    pause
)

exit /b 0

