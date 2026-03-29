# -*- mode: python ; coding: utf-8 -*-
# image_editor.spec
# PyInstaller 빌드 설정 파일
# 사용법: pyinstaller image_editor.spec

import sys
from pathlib import Path

block_cipher = None

# rembg 모델 파일 위치 (설치된 패키지 내)
import rembg
rembg_path = Path(rembg.__file__).parent

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # rembg 모델 포함
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    console=False,           # GUI 앱: 콘솔창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # 아이콘이 있으면 'assets/icon.ico' 로 변경
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
