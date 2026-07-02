# py-audioplayer

A simple but fully functional desktop audio player written in Python 3.10+, built with **tkinter** for the GUI and **VLC (python-vlc)** for playback.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- Plays **MP3, WAV, FLAC, OGG, AAC/M4A, WMA** (anything VLC can play)
- Playlist management: add files, add a whole folder, remove, clear, reorder (Move Up/Down)
- **Save/Load playlists** in M3U (and PLS) format
- Play / Pause / Stop / Previous / Next / Restart controls
- **Loop** mode (restarts the playlist when it ends) and **Shuffle** mode (never repeats the same track twice in a row)
- Real-time **seek slider** with elapsed/total time display
- **Volume slider** (0–100%), persisted across sessions
- **Drag & drop** audio files or folders from Explorer into the playlist (via `tkinterdnd2`)
- Double-click a playlist entry to play it
- Status bar with current track and playback state
- Remembers the **last used folders** for audio files and playlists in a JSON config file (`%APPDATA%\PyAudioPlayer\config.json` on Windows)
- Keyboard: `Space` = play/pause, `Ctrl+O` = open files, `Delete` = remove selected

## Requirements

- **Python 3.10+**
- **VLC media player must be installed** on your system — python-vlc is a binding to VLC's `libvlc` and will not work without it. Download: <https://www.videolan.org/vlc/>
  - Important: use the VLC architecture that matches your Python (64-bit Python needs 64-bit VLC).
- Python packages (see `requirements.txt`): `python-vlc`, `mutagen`, `tkinterdnd2`

## Installation

```bat
git clone https://github.com/iceman-twitch/py-audioplayer.git
cd py-audioplayer

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

## Run

```bat
python audio_player.py
```

## Build a Windows .exe (PyInstaller)

```bat
venv\Scripts\activate
pip install -r requirements-dev.txt
build_exe.bat
```

The executable lands in `dist\PyAudioPlayer\PyAudioPlayer.exe`. VLC still has to be installed on the machine that runs the exe.

## Configuration

The app stores its settings in `%APPDATA%\PyAudioPlayer\config.json`:

```json
{
  "last_audio_folder": "C:/Users/User/Music",
  "last_playlist_folder": "C:/Users/User/Playlists",
  "volume": 80
}
```

Delete the file to reset to defaults.

## Project layout

| File | Purpose |
|------|---------|
| `audio_player.py` | The whole application (GUI + playback + playlist + config) |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Runtime deps + PyInstaller |
| `py-audioplayer.spec` | PyInstaller build spec |
| `build_exe.bat` | One-command exe build |

## License

See [LICENSE](LICENSE).
