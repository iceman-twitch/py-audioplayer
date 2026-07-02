# PyInstaller spec for Py Audio Player.
# Build with:  pyinstaller --noconfirm --clean py-audioplayer.spec
#
# Note: VLC media player must still be installed on the target machine —
# python-vlc loads the system libvlc.dll at runtime.

a = Analysis(
    ["audio_player.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["tkinterdnd2"],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyAudioPlayer",
    console=False,
    upx=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="PyAudioPlayer",
)
