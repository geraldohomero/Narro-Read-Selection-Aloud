# Narro - Read Selection Aloud

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

Text-to-speech (TTS) reader with support for Edge TTS (online) and Piper TTS (offline) for GNOME/Wayland.

Select text in any application, copy it with Ctrl+C, and use a keyboard shortcut to open the TTS player — featuring Play/Pause/Stop controls, engine/language/voice selection, and speed control.

![TTS Player](https://img.shields.io/badge/GTK3-Player-blue?style=for-the-badge)

![image-hero](assets/image-hero.png)

## Features

- Full playback controls (Play, Pause, Stop).
- Two supported text-to-speech engines: Edge TTS (cloud neural voices) and Piper TTS (ultra-fast local voices running completely offline).
- New voice selection tab structured as: Voice -> Engine (Edge TTS or Piper TTS) -> Language -> Select.
- Native GTK4 configuration dialog that lists available voices, displays the download status of local models (for Piper), and lets you download them directly within the UI with a real-time progress bar.
- Downloaded Piper voices are stored in the user's local config folder (`~/.config/narro-rsa/piper-voices/`).
- Real-time speed control via mpv (applicable to both engines).
- Native GTK interface visually integrated with GNOME.
- Status bar providing process feedback.

## Dependencies

| Package | Installation |
|---|---|
| edge-tts | pipx install edge-tts |
| piper-tts | pipx install piper-tts or install the piper binary in your PATH (e.g., ~/.local/bin/piper) |
| mpv | sudo dnf install mpv |
| wl-clipboard | sudo dnf install wl-clipboard |
| python3-gobject | sudo dnf install python3-gobject |
| gtk3 | sudo dnf install gtk3 |
| gtk4 | sudo dnf install gtk4 |
| libnotify | sudo dnf install libnotify |

Commands to install dependencies:

```bash
sudo dnf install wl-clipboard mpv python3-gobject gtk3 gtk4 libnotify
pipx install edge-tts
```

Note: To use Piper TTS, ensure that the `piper` binary is available in your execution PATH or installed directly in `~/.local/bin/piper`.

## Installation

```bash
git clone https://github.com/geraldohomero/narro-rsa.git
cd narro-rsa
bash install.sh
```

The `install.sh` script copies the required files to `~/.local/bin/` (including the `narro_rsa/` package) and checks dependencies.

## Uninstallation

To completely remove Narro-RSA from your system:

```bash
bash uninstall.sh
```

The script removes:
- Installed scripts and packages in `~/.local/bin/`
- Saved settings and local Piper voices in `~/.config/narro-rsa/`
- Temporary files in `$XDG_RUNTIME_DIR` (and `/tmp/` for older installations)
- Running processes (mpv, edge-tts, piper)

After uninstalling, remember to manually remove the configured keyboard shortcuts in GNOME.

## GNOME Keyboard Shortcuts Configuration

> [!NOTE]
> The `install.sh` and `uninstall.sh` scripts now configure and remove these shortcuts **automatically** if you are running GNOME.

If you need to configure or adjust them manually, open: Settings -> Keyboard -> Keyboard Shortcuts -> Custom Shortcuts:

### Shortcut 1 — Open TTS Reader
- Name: `Leitor TTS (Narro)`
- Command: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- Shortcut: `Super+Alt+L`

### Shortcut 2 — Open TTS Reader (direct)
- Name: `Leitor TTS (Narro) [Ctrl+\]`
- Command: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- Shortcut: `Ctrl+\` (Automatically captures the active text selection without needing Ctrl+C)

### Shortcut 3 — Pause/Resume TTS reading (optional)
- Name: `Pausar leitura TTS (Narro)`
- Command: `bash -c "$HOME/.local/bin/pausar_leitura.sh"`
- Shortcut: `Super+Alt+J`

### Shortcut 4 — Stop TTS reading (optional)
- Name: `Parar leitura TTS (Narro)`
- Command: `bash -c "$HOME/.local/bin/parar_leitura.sh"`
- Shortcut: `Super+Alt+K`

## How to Use

1. Open a document or PDF (for example, in Okular).
2. Select the desired text using the selection tool.
3. Copy it with Ctrl+C.
4. Press Super+Alt+L (or your configured shortcut).
5. The player will open in the system tray.
6. Go to Settings to choose the engine (Edge TTS or Piper TTS), language, and voice.
7. In the dialog that opens, select your preferred voice. If configuring Piper, click "Download selected voice" before confirming the selection.
8. Click Play to start reading.
9. Use Pause to pause/resume and Stop to stop.

## Project Structure

```
narro-read-selection-aloud/
├── ler_texto.py           # Entrypoint — single-instance lock, signals, GTK main loop
├── config_dialog.py       # GTK4 configuration dialog (separate process)
├── narro_rsa/             # Python package with project logic
│   ├── __init__.py
│   ├── constants.py       # Centralized paths and constants
│   ├── settings.py        # Load/save JSON preferences
│   ├── mpv_control.py     # IPC communication with mpv via Unix socket
│   ├── text_formatter.py  # Text formatting for TTS (cleaning PDFs)
│   ├── clipboard.py       # Clipboard text capture (Wayland)
│   ├── tts_engine.py      # TTS Engine (Edge-TTS + Piper)
│   └── indicator.py       # AppIndicator3 in the GNOME tray
├── ler_texto.sh           # Shell wrapper for GNOME shortcut
├── parar_leitura.sh       # Script to stop reading
├── install.sh             # System installer
├── uninstall.sh           # Uninstaller
├── assets/                # Images and visual assets
└── README.md              # Project documentation
```

## License

MIT
