# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_kb7.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'turtlebeach_kb7.streamdeck',
        'turtlebeach_kb7.lighting',
        'turtlebeach_kb7.steelseries',
        'turtlebeach_kb7.theme_generator',
        'turtlebeach_kb7.minecraft',
        'turtlebeach_kb7.win_hid',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KB7_Command_Center',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/kb7_app.ico'],
)
