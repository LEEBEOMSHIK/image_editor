# -*- mode: python ; coding: utf-8 -*-
# image_editor_mac.spec
# PyInstaller macOS 빌드 설정 파일
# 사용법: pyinstaller image_editor_mac.spec

import sys
from pathlib import Path

block_cipher = None

import rembg
rembg_path = Path(rembg.__file__).parent

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (str(rembg_path), 'rembg'),
        ('images', 'images'),
    ],
    hiddenimports=[
        'rembg',
        'rembg.sessions',
        'rembg.sessions.u2net',
        'onnxruntime',
        'onnxruntime.capi',
        'PIL',
        'PIL.Image',
        'cv2',
        'numpy',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'ui.main_window',
        'ui.canvas',
        'ui.toolbar',
        'ui.status_bar',
        'ui.export_dialog',
        'core.image_processor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ImageEditorPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,   # macOS에서 Finder 드롭 지원
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/main.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ImageEditorPro',
)

app = BUNDLE(
    coll,
    name='ImageEditorPro.app',
    icon='images/main.png',
    bundle_identifier='com.imageproeditor.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
    },
)
