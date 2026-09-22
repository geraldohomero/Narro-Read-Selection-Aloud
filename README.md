# Narro - Read Selection Aloud

<p align="center">
  <img src="assets/com.github.geraldohomero.NarroRsa.png" alt="Narro-RSA Logo" width="128" height="128">
</p>

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

Text-to-speech (TTS) reader with support for Edge TTS (online) and Piper TTS (offline) for GNOME/Wayland, featuring a fully integrated GTK4 native application and Flatpak support.

Select text in any application, copy it, and use a keyboard shortcut to open the TTS player — featuring Play/Pause/Stop controls, engine/language/voice selection, speed control, and a visual history viewer.

![image-hero](assets/image-hero.png)

## Features

- **Integrated GTK4 Native Window**: View, edit and read clipboard text directly from a beautiful GNOME HIG interface.
- **Sober Desktop Icon**: Custom transparent document icon matching GNOME/Flatpak desktop environments.
- **Two TTS Engines**: Edge TTS (neural cloud voices) and Piper TTS (ultra-fast local voices running completely offline).
- **Auto-Configured Keyboard Shortcuts**: Automatically sets up GNOME global hotkeys on the first launch.
- **Dynamic Settings Dialog**: Inside the main window, view voice catalogs, download local models for Piper with real-time progress bars, and set preferences.
- **Real-Time Speed Control**: Adjust playback speed on the fly via mpv integration.
- **System Tray Integration**: An optional system tray indicator (AppIndicator) running on the host that lets you trigger/open the app quickly.

---

## Installation Options

### Option 1: Flatpak (Recommended & Fully Self-Contained)

Installing via Flatpak is the easiest method. It bundles all dependencies inside a sandbox, requires no manual configuration of libraries on your host system, and sets up GNOME keyboard shortcuts automatically.

#### 1. Install the Flatpak package:
```bash
flatpak install --user ./com.github.geraldohomero.NarroRsa.flatpak
```
*Or build directly from the manifest:*
```bash
flatpak-builder --user --install --force-clean --disable-rofiles-fuse build-dir com.github.geraldohomero.NarroRsa.yaml
```

#### 2. Run the application:
```bash
flatpak run com.github.geraldohomero.NarroRsa
```

*(On the first GUI startup, GNOME custom keyboard shortcuts will be configured automatically to use Flatpak!)*

---

## GNOME Keyboard Shortcuts

The app configures these shortcuts automatically on GNOME:

- **Read Clipboard** (`Super+Alt+L`): `flatpak run com.github.geraldohomero.NarroRsa --play`
- **Read Selection Direct** (`Ctrl+\`): `flatpak run com.github.geraldohomero.NarroRsa --primary`
- **Pause/Resume** (`Super+Alt+J`): `flatpak run com.github.geraldohomero.NarroRsa --pause`
- **Stop Playback** (`Super+Alt+K`): `flatpak run com.github.geraldohomero.NarroRsa --stop`

---

## Uninstallation

To uninstall the Flatpak app:
```bash
flatpak remove com.github.geraldohomero.NarroRsa
```

---

## Project Structure

```
narro-read-selection-aloud/
├── main_window.py         # GTK4 / Libadwaita Main Window (with integrated slide navigation)
├── ler_texto.py           # Tray and reader daemon
├── narro_rsa/             # Python package with project logic
│   ├── translations.py    # Centralized translations dictionary
│   ├── reader_page.py     # Reader UI component
│   ├── settings_page.py   # Settings page with integrated language search
│   ├── constants.py       # Centralized paths and constants
│   ├── settings.py        # Preferences loader and persistence
│   ├── mpv_control.py     # IPC Unix socket controls for mpv
│   ├── text_formatter.py  # Text cleanup for PDF reading
│   ├── clipboard.py       # Intelligent Wayland clipboard resolution
│   ├── subprocess_helper.py # Daemon and process utilities
│   └── tts_engine.py      # Audio generator (Edge-TTS + Piper)
├── com.github.geraldohomero.NarroRsa.flatpak      # Self-contained Flatpak bundle
├── com.github.geraldohomero.NarroRsa.yaml         # Flatpak Manifest
├── com.github.geraldohomero.NarroRsa.desktop      # Desktop entry
├── com.github.geraldohomero.NarroRsa.metainfo.xml # AppStream Metadata
└── assets/                # Icon and visual resources
```

## License

MIT
