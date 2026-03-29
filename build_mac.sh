#!/usr/bin/env bash
# macOS build script — runs on a Mac with the venv active
set -e

echo "=== ImageEditorPro macOS Build ==="

# Ensure dependencies
pip install pyinstaller Pillow PyQt6 opencv-python numpy "rembg[cpu]"

# Build .app bundle
pyinstaller image_editor_mac.spec --noconfirm

# Package into .pkg using pkgbuild
APP_PATH="dist/ImageEditorPro.app"
PKG_OUT="dist/ImageEditorPro.pkg"

if command -v pkgbuild &>/dev/null; then
    echo "Creating .pkg installer..."
    pkgbuild \
        --component "$APP_PATH" \
        --install-location /Applications \
        "$PKG_OUT"
    echo "PKG created: $PKG_OUT"
else
    echo "pkgbuild not found — skipping .pkg creation (macOS only)"
fi

echo "Build complete. Output: dist/"
