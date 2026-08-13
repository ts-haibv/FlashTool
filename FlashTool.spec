# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for FlashTool."""

import sys
import os

block_cipher = None

# Keep the asset contract in one place.  E9/E10 are included automatically
# when their exact model assets are supplied; they must never fall back to
# another model's vbmeta image.
ROM_ASSET_PROFILES = ('e9', 'e10', 'e11', 'ps10', 'ps11')
ROM_ASSET_DATA = [
    (os.path.join('assets', profile), os.path.join('assets', profile))
    for profile in ROM_ASSET_PROFILES
    if os.path.isdir(os.path.join('assets', profile))
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/icon.png', 'assets'),
        *ROM_ASSET_DATA,
        ('flash_ps10.sh', '.'),
        ('flash_ps11.sh', '.'),
        ('flash_e11.sh', '.'),
        ('flash_e10.sh', '.'),
        ('flash_e9.sh', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'flash_tool',
        'flash_tool.config',
        'flash_tool.device_manager',
        'flash_tool.flash_worker',
        'flash_tool.profiles',
        'flash_tool.profiles.g6_ramba',
        'flash_tool.profiles.script_device',
        'flash_tool.profiles.auto_detect',
        'flash_tool.ui',
        'flash_tool.ui.theme',
        'flash_tool.ui.step_widget',
        'flash_tool.ui.log_panel',
        'flash_tool.ui.main_window',
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

# Include customtkinter data files
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)
a.datas += [(os.path.join('customtkinter', f), os.path.join(ctk_path, f), 'DATA')
            for f in os.listdir(ctk_path)
            if os.path.isfile(os.path.join(ctk_path, f))]

# Recursively add customtkinter subdirs
for root, dirs, files in os.walk(ctk_path):
    for f in files:
        src = os.path.join(root, f)
        rel = os.path.relpath(src, os.path.dirname(ctk_path))
        a.datas.append((rel, src, 'DATA'))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FlashTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.png',
)
