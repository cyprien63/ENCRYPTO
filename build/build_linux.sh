#!/bin/bash
# ENCRYPTO Linux Build Script (WSL/Linux natif)
# Construction manuelle AppDir 100% autonome (GTK/WebKit/PyGObject inclus)
set -e

cd "$(dirname "$0")/.."
PROJECT_DIR="$PWD"

echo "[INFO] Nettoyage..."
rm -rf dist/ __pycache__/ *.spec .build_staging .build_recipe AppDir
find "$PROJECT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
rm -f "version compiler/linux"/*.AppImage 2>/dev/null || true
mkdir -p "version compiler/linux"

# Verifier que apt est disponible (Debian/Ubuntu)
if ! command -v apt-get &> /dev/null; then
    echo "[ERROR] Ce script necessite apt (Debian/Ubuntu)."
    echo "[HINT] Utilisez build/build_linux_docker.sh sur d'autres distributions."
    exit 1
fi

echo "[INFO] Installation des dependances systeme..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
    python3 python3-pip python3-venv python3-gi python3-gi-cairo \
    gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0 libgtk-3-0 \
    libgdk-pixbuf2.0-0 libjavascriptcoregtk-4.1-0 \
    libcairo2 wget fuse libfuse2 squashfs-tools file curl

echo "[INFO] Telechargement de Portable Python 3.10 (build standalone)..."
mkdir -p AppDir/opt
wget -qO- "https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.10.13+20240107-x86_64-unknown-linux-gnu-install_only.tar.gz" | tar -xz -C AppDir/opt/
mv AppDir/opt/python AppDir/opt/python3.10

echo "[INFO] Installation des dependances pip dans l'AppDir..."
AppDir/opt/python3.10/bin/python3 -m pip install --upgrade pip --quiet
AppDir/opt/python3.10/bin/python3 -m pip install --no-warn-script-location -r requirements.txt --quiet

echo "[INFO] Integration des paquets systeme (GTK/WebKit) depuis le systeme hote..."
SYSTEM_PKGS="python3-gi python3-gi-cairo gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0 libgtk-3-0 libgdk-pixbuf2.0-0 libjavascriptcoregtk-4.1-0 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libglib2.0-0 libgobject-2.0-0 libharfbuzz0b libfontconfig1 libfreetype6 libpixman-1-0 libpng16-16 libjpeg-turbo8 libepoxy0 libatk1.0-0 libatk-bridge2.0-0 libxml2 libsoup-3.0-0"

mkdir -p /tmp/debs
cd /tmp/debs
apt-get download $(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances $SYSTEM_PKGS 2>/dev/null | grep "^\w" | sort -u) 2>/dev/null || true

for deb in *.deb; do
    [ -f "$deb" ] && dpkg-deb -x "$deb" "$PROJECT_DIR/AppDir/" 2>/dev/null || true
done

cd "$PROJECT_DIR"
rm -rf /tmp/debs

echo "[INFO] Verification des modules systeme dans AppDir..."
if [ ! -f "AppDir/usr/lib/python3/dist-packages/gi/__init__.py" ]; then
    echo "[WARNING] gi module manquant, copie depuis le systeme..."
    mkdir -p AppDir/usr/lib/python3/dist-packages
    cp -a /usr/lib/python3/dist-packages/gi AppDir/usr/lib/python3/dist-packages/
    find AppDir/usr/lib/python3/dist-packages/gi -name "*.pyc" -delete
fi

if [ ! -f "AppDir/usr/lib/girepository-1.0/Gtk-3.0.typelib" ]; then
    echo "[WARNING] Typelibs manquantes, copie depuis le systeme..."
    mkdir -p AppDir/usr/lib/girepository-1.0
    cp -a /usr/lib/girepository-1.0/*.typelib AppDir/usr/lib/girepository-1.0/ 2>/dev/null || true
fi

echo "[INFO] Copie des fichiers applicatifs..."
mkdir -p AppDir/opt/ENCRYPTO
cp app.py AppDir/opt/ENCRYPTO/
cp -r src AppDir/opt/ENCRYPTO/
cp -r web AppDir/opt/ENCRYPTO/
cp image.png AppDir/opt/ENCRYPTO/
cp LICENSE.txt AppDir/opt/ENCRYPTO/
cp docs/preinstall.txt AppDir/opt/ENCRYPTO/
cp docs/postinstall.txt AppDir/opt/ENCRYPTO/

ln -sf opt/ENCRYPTO/app.py AppDir/app.py
ln -sf opt/ENCRYPTO/src AppDir/src
ln -sf opt/ENCRYPTO/web AppDir/web
ln -sf opt/ENCRYPTO/image.png AppDir/image.png
ln -sf opt/ENCRYPTO/LICENSE.txt AppDir/LICENSE.txt

rm -rf AppDir/usr/lib/x86_64-linux-gnu/dri 2>/dev/null || true
rm -f AppDir/usr/lib/x86_64-linux-gnu/libEGL* 2>/dev/null || true
rm -f AppDir/usr/lib/x86_64-linux-gnu/libGLX* 2>/dev/null || true
rm -f AppDir/usr/lib/x86_64-linux-gnu/libGLdispatch* 2>/dev/null || true

echo "[INFO] Creation du AppRun..."
cat > AppDir/AppRun << 'RUN'
#!/bin/bash
APPDIR="$(cd "$(dirname "$0")" && pwd)"

export PYTHONHOME="${APPDIR}/opt/python3.10"
export PYTHONPATH="${APPDIR}/usr/lib/python3/dist-packages:${APPDIR}/usr/lib/python3.10/dist-packages:${APPDIR}/opt/python3.10/lib/python3.10/site-packages"
export PATH="${APPDIR}/opt/python3.10/bin:${APPDIR}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:${APPDIR}/usr/lib/x86_64-linux-gnu:${APPDIR}/opt/python3.10/lib:${APPDIR}/usr/lib:${LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="${APPDIR}/usr/lib/girepository-1.0:${APPDIR}/usr/lib/x86_64-linux-gnu/girepository-1.0:${GI_TYPELIB_PATH}"
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
[ ! -e "${APPDIR}/opt/python3.10/bin/python" ] && ln -sf python3 "${APPDIR}/opt/python3.10/bin/python"
exec "${APPDIR}/opt/python3.10/bin/python3" "${APPDIR}/app.py" "$@"
RUN
chmod +x AppDir/AppRun

echo "[INFO] Creation du fichier .desktop..."
cat > AppDir/ENCRYPTO.desktop << EOF
[Desktop Entry]
Type=Application
Name=ENCRYPTO
Exec=ENCRYPTO
Icon=ENCRYPTO
Categories=Utility;
Terminal=false
EOF
cp image.png AppDir/ENCRYPTO.png

echo "[INFO] Telechargement de appimagetool..."
wget -q "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x appimagetool-x86_64.AppImage

echo "[INFO] Creation de l'AppImage finale..."
"./appimagetool-x86_64.AppImage" --appimage-extract > /dev/null 2>&1
./squashfs-root/AppRun AppDir "version compiler/linux/ENCRYPTO-x86_64.AppImage"

echo "[INFO] Nettoyage..."
rm -rf appimagetool-x86_64.AppImage squashfs-root AppDir dist/ __pycache__/ *.spec

echo "[SUCCESS] AppImage autonome creee."
ls -lh "version compiler/linux/ENCRYPTO-x86_64.AppImage"
