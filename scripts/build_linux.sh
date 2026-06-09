#!/bin/bash
# ────────────────────────────────────────────────────────────────────────────
# FlashTool — Build Linux Package (.deb + standalone binary)
# ────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="FlashTool"
APP_VERSION="1.2.0"
BUILD_DIR="$SCRIPT_DIR/dist"
DEB_DIR="$BUILD_DIR/deb_package"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo "amd64")

echo "╔══════════════════════════════════════════════════════╗"
echo "║  ⚡ FlashTool Build — Linux                         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Setup venv & deps ──────────────────────────────────────────────
echo "📦 [1/4] Setting up build environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip --version >/dev/null 2>&1 || python -m ensurepip --upgrade
pip install -q -r requirements.txt
pip install -q pyinstaller

# ── Step 2: Build with PyInstaller ─────────────────────────────────────────
echo "🔨 [2/4] Building standalone binary with PyInstaller..."
pyinstaller FlashTool.spec --clean --noconfirm 2>&1 | tail -5

if [ ! -f "$BUILD_DIR/FlashTool" ]; then
    echo "❌ Build failed: $BUILD_DIR/FlashTool not found"
    exit 1
fi

BINARY_SIZE=$(du -h "$BUILD_DIR/FlashTool" | cut -f1)
echo "  ✅ Binary built: $BUILD_DIR/FlashTool ($BINARY_SIZE)"

# ── Step 3: Create .deb package ────────────────────────────────────────────
echo "📦 [3/4] Creating .deb package..."

DEB_NAME="${APP_NAME,,}_${APP_VERSION}_${ARCH}"
DEB_ROOT="$DEB_DIR/$DEB_NAME"

# Clean previous
rm -rf "$DEB_ROOT"

# Directory structure
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/$APP_NAME"

# Copy binary
cp "$BUILD_DIR/FlashTool" "$DEB_ROOT/usr/bin/flashtool"
chmod 755 "$DEB_ROOT/usr/bin/flashtool"

# Copy bundled assets (e.g. vbmeta_verification_disabled.img)
mkdir -p "$DEB_ROOT/usr/share/$APP_NAME/assets/e11"
mkdir -p "$DEB_ROOT/usr/share/$APP_NAME/assets/ps11"
if [ -d "$SCRIPT_DIR/assets/e11" ]; then
    cp -r "$SCRIPT_DIR/assets/e11/." "$DEB_ROOT/usr/share/$APP_NAME/assets/e11/"
fi
if [ -d "$SCRIPT_DIR/assets/ps11" ]; then
    cp -r "$SCRIPT_DIR/assets/ps11/." "$DEB_ROOT/usr/share/$APP_NAME/assets/ps11/"
fi

# DEBIAN/control
cat > "$DEB_ROOT/DEBIAN/control" << EOF
Package: flashtool
Version: $APP_VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: android-tools-adb, android-tools-fastboot
Maintainer: FlashTool <flashtool@local>
Description: G6 ROM Flash Tool
 Cross-platform desktop application for flashing ROM images
 onto G6 (RAMBA) devices. Features auto-detection of image files,
 real-time progress tracking, and a modern dark UI.
Homepage: https://github.com/flashtool
EOF

# DEBIAN/postinst
cat > "$DEB_ROOT/DEBIAN/postinst" << 'EOF'
#!/bin/bash
if which gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
echo "⚡ FlashTool installed successfully!"
echo "  Run: flashtool"
exit 0
EOF
chmod 755 "$DEB_ROOT/DEBIAN/postinst"

# Copy icon
mkdir -p "$DEB_ROOT/usr/share/pixmaps"
cp "$SCRIPT_DIR/assets/icon.png" "$DEB_ROOT/usr/share/pixmaps/flashtool.png"

cat > "$DEB_ROOT/usr/share/applications/flashtool.desktop" << EOF
[Desktop Entry]
Name=FlashTool
Comment=G6 ROM Flash Tool
Exec=flashtool
Icon=/usr/share/pixmaps/flashtool.png
Terminal=false
Type=Application
StartupWMClass=flashtool
Categories=Utility;Development;
Keywords=flash;rom;android;fastboot;adb;
EOF

# Build .deb
dpkg-deb --build "$DEB_ROOT" "$BUILD_DIR/$DEB_NAME.deb" 2>/dev/null

DEB_SIZE=$(du -h "$BUILD_DIR/$DEB_NAME.deb" | cut -f1)
echo "  ✅ .deb package: $BUILD_DIR/$DEB_NAME.deb ($DEB_SIZE)"

# ── Step 4: Summary ───────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Build Complete!                                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Standalone: dist/FlashTool                         ║"
echo "║  Installer:  dist/${DEB_NAME}.deb  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Install .deb:"
echo "  sudo dpkg -i dist/$DEB_NAME.deb"
echo ""
echo "Or run standalone:"
echo "  ./dist/FlashTool"
