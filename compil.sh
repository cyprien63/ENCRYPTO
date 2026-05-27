#!/bin/bash
# =========================================
#       ENCRYPTO Compiler (Linux)
# =========================================

clear
echo "========================================="
echo "      ENCRYPTO Compiler (Linux)        "
echo "========================================="
echo ""

echo "[INFO] Nettoyage des résidus système..."
rm -rf build/ dist/ __pycache__/ *.spec .build_staging 2>/dev/null || true
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "Select target platform:"
echo "1. Linux AppImage (python-appimage)"
echo "2. Linux AppImage full standalone (Docker + linuxdeploy, WebKitGTK inclus)"
echo "3. Windows (.exe via cross-compile - run compil.bat on Windows)"
echo ""

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "[INFO] Compilation Linux AppImage..."
        bash build/build_linux.sh
        ;;
    2)
        echo "[INFO] Compilation Linux AppImage full standalone..."
        if command -v docker &> /dev/null; then
            bash build/build_linux_full.sh
        else
            echo "[ERROR] Docker est requis. Installez Docker puis réessayez."
            exit 1
        fi
        ;;
    3)
        echo "[INFO] Pour compiler pour Windows, exécutez compil.bat sur une machine Windows."
        ;;
    *)
        echo "[ERROR] Choix invalide."
        ;;
esac

echo ""
echo "Compilation terminée."
