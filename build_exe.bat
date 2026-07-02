@echo off
REM Build a standalone Windows executable with PyInstaller.
REM Creates the venv and installs deps automatically if needed.

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

if not exist venv\Scripts\pyinstaller.exe (
    echo Installing dependencies...
    pip install -r requirements-dev.txt
)

pyinstaller --onefile --windowed --name "Py AudioPlayer" audio_player.py
echo.
echo Done. Executable: dist\PyAudioPlayer\PyAudioPlayer.exe
