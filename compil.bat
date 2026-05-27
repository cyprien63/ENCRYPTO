@echo off
setlocal enabledelayedexpansion

echo =========================================
echo       ENCRYPTO Compiler (Windows)
echo =========================================
echo.

rem Check for virtual environment
if not exist ".venv" (
    echo [ERROR] Virtual environment ^(.venv^) not found.
    echo [HINT] Please run run.bat first to initialize the environment.
    pause
    exit /b 1
)

rem Activate virtual environment
echo [INFO] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Activation script not found.
    pause
    exit /b 1
)

rem Install/Check dependencies
echo [INFO] Installing/Checking dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

rem Generate icon.ico from image.png if needed
if not exist "icon.ico" (
    echo [INFO] Generating icon.ico from image.png...
    python build\make_icon.py
)

rem Create output directories
if not exist "version compiler\windows" mkdir "version compiler\windows"

echo.
echo Select target platform:
echo 1. Windows ^(.exe^)
echo 2. Linux ^(.AppImage^)
echo.

set /p choice="Enter choice (1-2): "

if "!choice!"=="1" goto compile_windows
if "!choice!"=="2" goto compile_linux
goto end

:compile_windows
call :do_windows
goto end

:compile_linux
call :do_linux
goto end

:do_windows
echo [INFO] Compiling for Windows...
pyinstaller --noconfirm --onedir --windowed ^
    --distpath "version compiler\windows" ^
    --add-data "web;web" ^
    --add-data "image.png;." ^
    --icon "icon.ico" ^
    --hidden-import webview ^
    --hidden-import webview.platforms.winforms ^
    --hidden-import webview.platforms.win32_edge ^
    --hidden-import cryptography.hazmat.backends.openssl ^
    --hidden-import PIL ^
    --hidden-import PIL._imaging ^
    --collect-all cryptography ^
    --collect-all PIL ^
    --name "ENCRYPTO" app.py
if !errorlevel! neq 0 (
    echo [ERROR] PyInstaller failed.
    pause
    exit /b 1
)
echo [SUCCESS] Folder created in 'version compiler\windows\ENCRYPTO\'
echo [INFO] Contains: ENCRYPTO.exe + web\ folder + image.png + all DLLs.
exit /b 0

:do_linux
echo [INFO] Compiling for Linux...
where wsl >nul 2>&1
if !errorlevel! equ 0 (
    call :find_wsl_distro
    if !errorlevel! equ 0 (
        echo [INFO] Building via WSL...
        !WSL_CMD! --cd "%CD%" bash build/build_linux.sh
        if !errorlevel! equ 0 (
            echo [SUCCESS] AppImage created in 'version compiler/linux/'
            exit /b 0
        )
        echo [WARNING] WSL build failed.
        goto :try_docker
    )
)

:try_docker
where docker >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Building via Docker...
    docker run --rm -v "%CD%:/app" -w /app ubuntu:22.04 bash build/build_linux_docker.sh
    if !errorlevel! equ 0 (
        echo [SUCCESS] AppImage created in 'version compiler/linux/'
        exit /b 0
    )
    echo [WARNING] Docker build failed.
)
if !errorlevel! neq 0 (
    echo [INFO] Pour compiler manuellement depuis WSL :
    echo   wsl --cd "%CD%" bash build/build_linux.sh
    echo.
    echo [INFO] Ou depuis un terminal WSL deja ouvert, tapez :
    echo   cd "$^(wslpath '%%CD%%'^)"
    echo   bash build/build_linux.sh
)
exit /b 0

:find_wsl_distro

set WSL_CMD=wsl

rem Test WSL avec timeout 5s pour eviter de bloquer si WSL est casse
powershell -Command "try { $p = Start-Process wsl -ArgumentList '-l -q' -NoNewWindow -RedirectStandardOutput '%TEMP%\wsl_distros.txt' -PassThru; if (-not $p.WaitForExit(5000)) { $p.Kill(); exit 1 }; $d = Get-Content '%TEMP%\wsl_distros.txt' -ErrorAction SilentlyContinue; if (-not $d) { exit 1 }; exit 0 } catch { exit 1 }" >nul 2>&1

if !errorlevel! neq 0 exit /b 1

rem Essayer la distribution par defaut
powershell -Command "try { $p = Start-Process wsl -ArgumentList 'bash -c \"exit 0\"' -NoNewWindow -PassThru; if (-not $p.WaitForExit(8000)) { $p.Kill(); exit 1 }; exit $p.ExitCode } catch { exit 1 }" >nul 2>&1

if !errorlevel! equ 0 exit /b 0

rem Essayer Ubuntu explicitement
powershell -Command "try { $p = Start-Process wsl -ArgumentList '-d Ubuntu bash -c \"exit 0\"' -NoNewWindow -PassThru; if (-not $p.WaitForExit(8000)) { $p.Kill(); exit 1 }; exit $p.ExitCode } catch { exit 1 }" >nul 2>&1

if !errorlevel! equ 0 (

    set WSL_CMD=wsl -d Ubuntu

    exit /b 0

)

exit /b 1

:end
echo.
echo Compilation process finished.
pause
exit /b