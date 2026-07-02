"""
py-audioplayer — a simple, fully functional audio player.

GUI:      tkinter (+ tkinterdnd2 for drag & drop, optional)
Playback: python-vlc (requires VLC installed on the system)
Metadata: mutagen (track durations)

Python 3.10+
"""

from __future__ import annotations

import json
import os
import random
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

try:
    import vlc
except (ImportError, OSError) as exc:  # OSError if libvlc is missing
    tk.Tk().withdraw()
    messagebox.showerror(
        "VLC not found",
        "python-vlc / libVLC could not be loaded.\n\n"
        "Install VLC media player (https://www.videolan.org) and the\n"
        "python-vlc package (pip install python-vlc), then try again.\n\n"
        f"Details: {exc}",
    )
    sys.exit(1)

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

APP_NAME = "Py Audio Player"
APP_VERSION = "1.1.0"

# --- Winamp-inspired dark skin -------------------------------------------
C_BG = "#1e1e28"        # window background
C_PANEL = "#14141c"     # sunken panels / playlist
C_FG = "#c8c8d4"        # normal text
C_DIM = "#70708a"       # secondary text
C_LCD_BG = "#060a06"    # LCD display background
C_LCD_FG = "#00ff66"    # classic Winamp green
C_ACCENT = "#00e07f"    # highlights / active toggles
C_SHUFFLE = "#3fb4ff"   # shuffle-active color
C_BTN = "#2a2a3a"       # button face
C_BTN_ACTIVE = "#3a3a52"
C_SELECT = "#2d3f5e"    # playlist selection
LCD_FONT = ("Consolas", 18, "bold")
LCD_FONT_SMALL = ("Consolas", 10, "bold")

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma"}
PLAYLIST_EXTENSIONS = {".m3u", ".m3u8", ".pls"}

AUDIO_FILETYPES = [
    ("Audio files", "*.mp3 *.wav *.flac *.ogg *.aac *.m4a *.wma"),
    ("MP3", "*.mp3"), ("WAV", "*.wav"), ("FLAC", "*.flac"),
    ("OGG", "*.ogg"), ("AAC / M4A", "*.aac *.m4a"), ("WMA", "*.wma"),
    ("All files", "*.*"),
]
PLAYLIST_FILETYPES = [
    ("Playlists", "*.m3u *.m3u8 *.pls"),
    ("M3U playlist", "*.m3u *.m3u8"),
    ("PLS playlist", "*.pls"),
    ("All files", "*.*"),
]


def config_path() -> Path:
    """Config lives in the user's app-data folder (falls back to home)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    folder = base / "PyAudioPlayer"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "config.json"


class Config:
    """Persists last-used folders (and volume) across sessions."""

    DEFAULTS = {
        "last_audio_folder": str(Path.home()),
        "last_playlist_folder": str(Path.home()),
        "volume": 80,
    }

    def __init__(self) -> None:
        self.path = config_path()
        self.data = dict(self.DEFAULTS)
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
        except OSError:
            pass

    def get_folder(self, key: str) -> str:
        folder = self.data.get(key, "")
        return folder if os.path.isdir(folder) else str(Path.home())

    def set_folder(self, key: str, file_or_dir: str) -> None:
        p = Path(file_or_dir)
        folder = p if p.is_dir() else p.parent
        self.data[key] = str(folder)
        self.save()


class Track:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        self.name = Path(path).name
        self.duration = self._read_duration()

    def _read_duration(self) -> float:
        if MutagenFile is not None:
            try:
                meta = MutagenFile(self.path)
                if meta is not None and meta.info is not None:
                    return float(meta.info.length or 0.0)
            except Exception:
                pass
        return 0.0


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class AudioPlayerApp:
    UPDATE_MS = 250  # UI refresh interval

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("760x520")
        self.root.minsize(600, 420)

        self.config = Config()

        self.vlc_instance = vlc.Instance("--no-video", "--quiet")
        self.player = self.vlc_instance.media_player_new()

        self.playlist: list[Track] = []
        self.current_index: int | None = None
        self.loop_enabled = False
        self.shuffle_enabled = False
        self.seeking = False          # True while user drags the seek slider
        self.track_finished = False   # set by VLC end-of-track event

        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached,
                            self._on_track_end)

        self._apply_style()
        self._build_menu()
        self._build_ui()
        self._setup_dnd()

        self.set_volume(self.config.data.get("volume", 80))
        self.volume_var.set(self.config.data.get("volume", 80))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(self.UPDATE_MS, self._tick)

    # ------------------------------------------------------------------ UI

    def _apply_style(self) -> None:
        self.root.configure(bg=C_BG)
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=C_BG, foreground=C_FG,
                        fieldbackground=C_PANEL, bordercolor=C_PANEL,
                        lightcolor=C_BG, darkcolor=C_BG)
        style.configure("Treeview", background=C_PANEL, foreground=C_FG,
                        fieldbackground=C_PANEL, rowheight=22,
                        font=("Segoe UI", 9), borderwidth=0)
        style.map("Treeview",
                  background=[("selected", C_SELECT)],
                  foreground=[("selected", C_LCD_FG)])
        style.configure("Treeview.Heading", background=C_BTN,
                        foreground=C_FG, relief="flat",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading", background=[("active", C_BTN_ACTIVE)])

        style.configure("Horizontal.TScale", troughcolor=C_PANEL,
                        background=C_ACCENT, bordercolor=C_PANEL,
                        lightcolor=C_ACCENT, darkcolor=C_ACCENT)
        style.configure("Vertical.TScrollbar", troughcolor=C_PANEL,
                        background=C_BTN, bordercolor=C_PANEL,
                        arrowcolor=C_FG)
        style.map("Vertical.TScrollbar",
                  background=[("active", C_BTN_ACTIVE)])

    def _make_btn(self, parent, text, command, width=8) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, width=width,
            bg=C_BTN, fg=C_FG, activebackground=C_BTN_ACTIVE,
            activeforeground=C_LCD_FG, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C_PANEL,
            font=("Segoe UI", 9), cursor="hand2", padx=4, pady=3)

    def _build_menu(self) -> None:
        menu_kw = dict(bg=C_PANEL, fg=C_FG, activebackground=C_SELECT,
                       activeforeground=C_LCD_FG, bd=0)
        menubar = tk.Menu(self.root, **menu_kw)

        file_menu = tk.Menu(menubar, tearoff=0, **menu_kw)
        file_menu.add_command(label="Open File(s)...", accelerator="Ctrl+O",
                              command=self.add_files)
        file_menu.add_command(label="Add Folder...", command=self.add_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Open Playlist...", command=self.load_playlist)
        file_menu.add_command(label="Save Playlist...", command=self.save_playlist)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        play_menu = tk.Menu(menubar, tearoff=0, **menu_kw)
        play_menu.add_command(label="Play", command=self.play)
        play_menu.add_command(label="Pause / Resume", command=self.pause)
        play_menu.add_command(label="Stop", command=self.stop)
        play_menu.add_separator()
        play_menu.add_command(label="Previous", command=self.previous_track)
        play_menu.add_command(label="Next", command=self.next_track)
        play_menu.add_command(label="Restart Track", command=self.restart_track)
        menubar.add_cascade(label="Playback", menu=play_menu)

        help_menu = tk.Menu(menubar, tearoff=0, **menu_kw)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-o>", lambda e: self.add_files())
        self.root.bind("<space>", self._space_pressed)

    def _build_ui(self) -> None:
        # --- LCD display panel (Winamp-style) ---
        lcd = tk.Frame(self.root, bg=C_LCD_BG, bd=2, relief="sunken")
        lcd.pack(fill="x", padx=8, pady=(8, 4))
        self.time_label = tk.Label(lcd, text="00:00 / 00:00",
                                   bg=C_LCD_BG, fg=C_LCD_FG, font=LCD_FONT,
                                   anchor="w", padx=10)
        self.time_label.pack(fill="x", pady=(6, 0))
        self.track_label = tk.Label(lcd, text="*** PY AUDIO PLAYER ***",
                                    bg=C_LCD_BG, fg=C_LCD_FG,
                                    font=LCD_FONT_SMALL, anchor="w", padx=10)
        self.track_label.pack(fill="x", pady=(0, 6))

        # --- playlist ---
        list_frame = tk.Frame(self.root, bg=C_BG)
        list_frame.pack(fill="both", expand=True, padx=8)

        columns = ("title", "duration")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="extended")
        self.tree.heading("title", text="Track")
        self.tree.heading("duration", text="Duration")
        self.tree.column("title", anchor="w")
        self.tree.column("duration", width=90, anchor="center", stretch=False)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

        scroll = ttk.Scrollbar(list_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # --- playlist management buttons ---
        pl_bar = tk.Frame(self.root, bg=C_BG)
        pl_bar.pack(fill="x", padx=8, pady=4)
        for text, cmd in (
            ("+ Files", self.add_files),
            ("+ Folder", self.add_folder),
            ("− Remove", self.remove_selected),
            ("Clear", self.clear_playlist),
            ("▲ Up", lambda: self.move_selected(-1)),
            ("▼ Down", lambda: self.move_selected(1)),
        ):
            self._make_btn(pl_bar, text, cmd).pack(side="left", padx=2)

        # --- seek slider ---
        seek_frame = tk.Frame(self.root, bg=C_BG)
        seek_frame.pack(fill="x", padx=8, pady=2)
        self.seek_var = tk.DoubleVar(value=0.0)
        self.seek_scale = ttk.Scale(seek_frame, from_=0.0, to=1000.0,
                                    variable=self.seek_var, orient="horizontal")
        self.seek_scale.pack(fill="x", expand=True)
        self.seek_scale.bind("<ButtonPress-1>", self._seek_start)
        self.seek_scale.bind("<ButtonRelease-1>", self._seek_end)

        # --- transport controls ---
        ctrl = tk.Frame(self.root, bg=C_BG)
        ctrl.pack(fill="x", padx=8, pady=(2, 4))
        for text, cmd in (
            ("⏮", self.previous_track),
            ("▶", self.play),
            ("⏸", self.pause),
            ("⏹", self.stop),
            ("⏭", self.next_track),
            ("↺", self.restart_track),
        ):
            btn = self._make_btn(ctrl, text, cmd, width=4)
            btn.configure(font=("Segoe UI", 11))
            btn.pack(side="left", padx=2)

        self.loop_btn = self._make_btn(ctrl, "LOOP", self.toggle_loop, width=7)
        self.loop_btn.configure(fg=C_DIM)
        self.loop_btn.pack(side="left", padx=(12, 2))
        self.shuffle_btn = self._make_btn(ctrl, "SHUFFLE", self.toggle_shuffle,
                                          width=8)
        self.shuffle_btn.configure(fg=C_DIM)
        self.shuffle_btn.pack(side="left", padx=2)

        tk.Label(ctrl, text="VOL", bg=C_BG, fg=C_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(16, 4))
        self.volume_var = tk.IntVar(value=80)
        self.volume_scale = ttk.Scale(
            ctrl, from_=0, to=100, orient="horizontal", length=120,
            command=lambda v: self.set_volume(int(float(v))))
        self.volume_scale.configure(variable=self.volume_var)
        self.volume_scale.pack(side="left")

        # --- status bar ---
        self.status_var = tk.StringVar(value="Ready — add some audio files.")
        status = tk.Label(self.root, textvariable=self.status_var,
                          bg=C_PANEL, fg=C_DIM, anchor="w",
                          font=("Segoe UI", 8), padx=8, pady=3)
        status.pack(fill="x", side="bottom")

    def _setup_dnd(self) -> None:
        if not _DND_AVAILABLE:
            return
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind("<<Drop>>", self._on_drop)

    # ------------------------------------------------------------ playlist

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add audio files",
            initialdir=self.config.get_folder("last_audio_folder"),
            filetypes=AUDIO_FILETYPES)
        if paths:
            self.config.set_folder("last_audio_folder", paths[0])
            self._add_paths(paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Add all audio files from folder",
            initialdir=self.config.get_folder("last_audio_folder"))
        if not folder:
            return
        self.config.set_folder("last_audio_folder", folder)
        files = sorted(
            p for p in Path(folder).iterdir()
            if p.suffix.lower() in AUDIO_EXTENSIONS)
        if files:
            self._add_paths([str(p) for p in files])
        else:
            self.status_var.set("No audio files found in that folder.")

    def _add_paths(self, paths) -> None:
        added = 0
        for path in paths:
            p = Path(path)
            if p.suffix.lower() in PLAYLIST_EXTENSIONS:
                self._load_playlist_file(str(p))
                continue
            if p.suffix.lower() not in AUDIO_EXTENSIONS or not p.is_file():
                continue
            track = Track(str(p))
            self.playlist.append(track)
            self.tree.insert("", "end", values=(
                track.name,
                fmt_time(track.duration) if track.duration else "--:--"))
            added += 1
        if added:
            self.status_var.set(f"Added {added} track(s). "
                                f"{len(self.playlist)} in playlist.")

    def remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        indices = sorted((self.tree.index(item) for item in selected),
                         reverse=True)
        for idx in indices:
            if idx == self.current_index:
                self.stop()
                self.current_index = None
            elif self.current_index is not None and idx < self.current_index:
                self.current_index -= 1
            del self.playlist[idx]
        for item in selected:
            self.tree.delete(item)
        self._refresh_highlight()
        self.status_var.set(f"{len(self.playlist)} track(s) in playlist.")

    def clear_playlist(self) -> None:
        self.stop()
        self.playlist.clear()
        self.current_index = None
        self.tree.delete(*self.tree.get_children())
        self.track_label.config(text="*** PY AUDIO PLAYER ***")
        self.status_var.set("Playlist cleared.")

    def move_selected(self, delta: int) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        indices = [self.tree.index(item) for item in selected]
        items = list(zip(indices, selected))
        items.sort(reverse=(delta > 0))
        current_track = (self.playlist[self.current_index]
                         if self.current_index is not None else None)
        for idx, item in items:
            new_idx = idx + delta
            if not (0 <= new_idx < len(self.playlist)):
                return  # block the whole move if any item would fall off
            self.playlist[idx], self.playlist[new_idx] = \
                self.playlist[new_idx], self.playlist[idx]
            self.tree.move(item, "", new_idx)
        if current_track is not None:
            self.current_index = self.playlist.index(current_track)
        self._refresh_highlight()

    def _on_drop(self, event) -> None:
        paths = self.root.tk.splitlist(event.data)
        expanded: list[str] = []
        for path in paths:
            p = Path(path)
            if p.is_dir():
                expanded.extend(
                    str(f) for f in sorted(p.iterdir())
                    if f.suffix.lower() in AUDIO_EXTENSIONS)
            else:
                expanded.append(str(p))
        self._add_paths(expanded)

    def _on_double_click(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            self.play_index(self.tree.index(item))

    # --------------------------------------------------- playlist file I/O

    def load_playlist(self) -> None:
        path = filedialog.askopenfilename(
            title="Open playlist",
            initialdir=self.config.get_folder("last_playlist_folder"),
            filetypes=PLAYLIST_FILETYPES)
        if not path:
            return
        self.config.set_folder("last_playlist_folder", path)
        self._load_playlist_file(path)

    def _load_playlist_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            messagebox.showerror("Open playlist", f"Could not read playlist:\n{exc}")
            return
        base = Path(path).parent
        entries: list[str] = []
        if Path(path).suffix.lower() == ".pls":
            for line in lines:
                if line.lower().startswith("file") and "=" in line:
                    entries.append(line.split("=", 1)[1].strip())
        else:  # m3u / m3u8
            entries = [ln.strip() for ln in lines
                       if ln.strip() and not ln.startswith("#")]
        resolved = []
        for entry in entries:
            p = Path(entry)
            if not p.is_absolute():
                p = base / p
            if p.is_file():
                resolved.append(str(p))
        self._add_paths(resolved)
        self.status_var.set(f"Loaded playlist: {Path(path).name} "
                            f"({len(resolved)} track(s) found).")

    def save_playlist(self) -> None:
        if not self.playlist:
            messagebox.showinfo("Save playlist", "The playlist is empty.")
            return
        path = filedialog.asksaveasfilename(
            title="Save playlist",
            initialdir=self.config.get_folder("last_playlist_folder"),
            defaultextension=".m3u",
            filetypes=[("M3U playlist", "*.m3u"), ("PLS playlist", "*.pls")])
        if not path:
            return
        self.config.set_folder("last_playlist_folder", path)
        try:
            if Path(path).suffix.lower() == ".pls":
                self._write_pls(path)
            else:
                self._write_m3u(path)
        except OSError as exc:
            messagebox.showerror("Save playlist", f"Could not save playlist:\n{exc}")
            return
        self.status_var.set(f"Playlist saved: {Path(path).name}")

    def _write_m3u(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#EXTM3U\n")
            for track in self.playlist:
                fh.write(f"#EXTINF:{int(track.duration)},{track.name}\n")
                fh.write(track.path + "\n")

    def _write_pls(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[playlist]\n")
            for i, track in enumerate(self.playlist, start=1):
                fh.write(f"File{i}={track.path}\n")
                fh.write(f"Title{i}={track.name}\n")
                fh.write(f"Length{i}={int(track.duration)}\n")
            fh.write(f"NumberOfEntries={len(self.playlist)}\n")
            fh.write("Version=2\n")

    # ------------------------------------------------------------ playback

    def play_index(self, index: int) -> None:
        if not (0 <= index < len(self.playlist)):
            return
        track = self.playlist[index]
        if not os.path.isfile(track.path):
            self.status_var.set(f"File not found: {track.name}")
            return
        self.current_index = index
        self.track_finished = False
        media = self.vlc_instance.media_new(track.path)
        self.player.set_media(media)
        self.player.play()
        self._refresh_highlight()
        self.track_label.config(text=track.name.upper())
        self.status_var.set(f"Playing: {track.name}")

    def play(self) -> None:
        state = self.player.get_state()
        if state == vlc.State.Paused:
            self.player.set_pause(0)
            self.status_var.set(f"Playing: {self._current_name()}")
        elif state in (vlc.State.Playing,):
            pass
        elif self.current_index is not None:
            self.play_index(self.current_index)
        elif self.playlist:
            self.play_index(0)

    def pause(self) -> None:
        state = self.player.get_state()
        if state == vlc.State.Playing:
            self.player.set_pause(1)
            self.status_var.set(f"Paused: {self._current_name()}")
        elif state == vlc.State.Paused:
            self.player.set_pause(0)
            self.status_var.set(f"Playing: {self._current_name()}")

    def stop(self) -> None:
        self.player.stop()
        self.track_finished = False
        self.seek_var.set(0)
        self.time_label.config(text="00:00 / 00:00")
        if self.current_index is not None:
            self.status_var.set(f"Stopped: {self._current_name()}")

    def restart_track(self) -> None:
        if self.current_index is not None:
            self.play_index(self.current_index)

    def next_track(self, auto: bool = False) -> None:
        if not self.playlist:
            return
        if self.shuffle_enabled:
            nxt = self._random_index()
        else:
            cur = self.current_index if self.current_index is not None else -1
            nxt = cur + 1
            if nxt >= len(self.playlist):
                if self.loop_enabled or not auto:
                    nxt = 0
                else:
                    self.stop()
                    self.status_var.set("End of playlist.")
                    return
        self.play_index(nxt)

    def previous_track(self) -> None:
        if not self.playlist:
            return
        cur = self.current_index if self.current_index is not None else 0
        self.play_index((cur - 1) % len(self.playlist))

    def _random_index(self) -> int:
        if len(self.playlist) == 1:
            return 0
        choices = [i for i in range(len(self.playlist))
                   if i != self.current_index]
        return random.choice(choices)

    def toggle_loop(self) -> None:
        self.loop_enabled = not self.loop_enabled
        self.loop_btn.config(
            fg=C_LCD_FG if self.loop_enabled else C_DIM,
            bg=C_BTN_ACTIVE if self.loop_enabled else C_BTN,
            highlightbackground=C_ACCENT if self.loop_enabled else C_PANEL)

    def toggle_shuffle(self) -> None:
        self.shuffle_enabled = not self.shuffle_enabled
        self.shuffle_btn.config(
            fg=C_SHUFFLE if self.shuffle_enabled else C_DIM,
            bg=C_BTN_ACTIVE if self.shuffle_enabled else C_BTN,
            highlightbackground=C_SHUFFLE if self.shuffle_enabled else C_PANEL)

    def set_volume(self, value: int) -> None:
        self.player.audio_set_volume(int(value))
        self.config.data["volume"] = int(value)

    def _on_track_end(self, event) -> None:
        # Called from a VLC thread — just flag it; _tick handles it in the
        # tkinter thread.
        self.track_finished = True

    def _current_name(self) -> str:
        if self.current_index is not None and self.current_index < len(self.playlist):
            return self.playlist[self.current_index].name
        return ""

    # ------------------------------------------------------------- seeking

    def _seek_start(self, event) -> None:
        self.seeking = True

    def _seek_end(self, event) -> None:
        self.seeking = False
        if self.player.get_media() is not None and self.player.is_seekable():
            self.player.set_position(self.seek_var.get() / 1000.0)

    # ---------------------------------------------------------------- tick

    def _tick(self) -> None:
        if self.track_finished:
            self.track_finished = False
            self.next_track(auto=True)

        state = self.player.get_state()
        if state in (vlc.State.Playing, vlc.State.Paused):
            length_ms = self.player.get_length()
            pos_ms = self.player.get_time()
            if length_ms > 0:
                if not self.seeking:
                    self.seek_var.set(self.player.get_position() * 1000.0)
                self.time_label.config(
                    text=f"{fmt_time(pos_ms / 1000)} / {fmt_time(length_ms / 1000)}")
        self.root.after(self.UPDATE_MS, self._tick)

    def _refresh_highlight(self) -> None:
        items = self.tree.get_children()
        self.tree.selection_remove(*items)
        if self.current_index is not None and self.current_index < len(items):
            item = items[self.current_index]
            self.tree.selection_set(item)
            self.tree.see(item)

    # ---------------------------------------------------------------- misc

    def _space_pressed(self, event) -> None:
        # Don't hijack space while typing in an entry-like widget.
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Text)):
            return
        if self.player.get_state() == vlc.State.Playing:
            self.pause()
        else:
            self.play()

    def show_about(self) -> None:
        messagebox.showinfo(
            "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "A simple audio player built with tkinter and libVLC.\n"
            "Supports MP3, WAV, FLAC, OGG, AAC/M4A and WMA.\n\n"
            "Playback engine: VLC (python-vlc)")

    def on_close(self) -> None:
        self.config.save()
        try:
            self.player.stop()
            self.player.release()
            self.vlc_instance.release()
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    root = TkinterDnD.Tk() if _DND_AVAILABLE else tk.Tk()
    AudioPlayerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
