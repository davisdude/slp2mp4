
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/slp2mp4/gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),  # Include the src directory
        ('src/slp2mp4/defaults.toml', 'slp2mp4'),  # Include default config
    ],
    hiddenimports=[
        'slp2mp4',
        'slp2mp4.config',
        'slp2mp4.modes',
        'slp2mp4.modes.single',
        'slp2mp4.modes.directory',
        'slp2mp4.modes.replay_manager',
        'slp2mp4.orchestrator',
        'slp2mp4.video',
        'slp2mp4.replay',
        'slp2mp4.ffmpeg',
        'slp2mp4.dolphin',
        'slp2mp4.dolphin.runner',
        'slp2mp4.dolphin.comm',
        'slp2mp4.dolphin.ini',
        'slp2mp4.util',
        'slippi',
        'tomli',
        'tomli_w',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='slp2mp4-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Don't show console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)
