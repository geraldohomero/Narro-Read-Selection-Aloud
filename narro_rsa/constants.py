"""Constantes de caminhos e configuração do Narro-RSA.

Centraliza todas as constantes usadas pelos módulos do projeto,
evitando duplicação entre ler_texto.py e config_dialog.py.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Caminhos de binários
# ---------------------------------------------------------------------------
EDGE_TTS_BIN: str = os.path.expanduser("~/.local/bin/edge-tts")
PIPER_BIN: str = os.path.expanduser("~/.local/bin/piper")

# ---------------------------------------------------------------------------
# Caminhos de runtime (preferência por XDG_RUNTIME_DIR com fallback /tmp)
# ---------------------------------------------------------------------------
_BASE_RUNTIME_DIR: str = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
_RUNTIME_DIR: str = os.path.join(_BASE_RUNTIME_DIR, "narro-rsa")
try:
    os.makedirs(_RUNTIME_DIR, exist_ok=True)
except OSError:
    _RUNTIME_DIR = _BASE_RUNTIME_DIR

LOCKFILE: str = os.path.join(_RUNTIME_DIR, "narro-rsa.lock")
MPV_SOCKET: str = os.path.join(_RUNTIME_DIR, "narro-rsa-mpv.sock")
TMP_AUDIO_MP3: str = os.path.join(_RUNTIME_DIR, "narro-rsa.mp3")
TMP_AUDIO_WAV: str = os.path.join(_RUNTIME_DIR, "narro-rsa.wav")
TMP_TEXT_FILE: str = os.path.join(_RUNTIME_DIR, "narro-rsa-text.txt")
LAST_READ_FILE: str = os.path.join(_RUNTIME_DIR, "narro-rsa-last-text.txt")

# ---------------------------------------------------------------------------
# Caminhos de configuração persistente
# ---------------------------------------------------------------------------
CONFIG_DIR: str = os.path.expanduser("~/.config/narro-rsa")
CONFIG_FILE: str = os.path.join(CONFIG_DIR, "settings.json")
PIPER_VOICES_DIR: str = os.path.join(CONFIG_DIR, "piper-voices")
EDGE_VOICES_CACHE: str = os.path.join(CONFIG_DIR, "edge_voices.json")

# ---------------------------------------------------------------------------
# Identificadores
# ---------------------------------------------------------------------------
APPINDICATOR_ID: str = "narro-rsa"

# ---------------------------------------------------------------------------
# Velocidade
# ---------------------------------------------------------------------------
SPEED_OPTIONS: list[float] = [
    0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.0,
]
SPEED_DEFAULT: float = 1.0
SPEED_MIN: float = 0.5
SPEED_MAX: float = 4.0

# ---------------------------------------------------------------------------
# Vozes padrão por engine
# ---------------------------------------------------------------------------
DEFAULT_VOICE_EDGE: str = "pt-BR-FranciscaNeural"
DEFAULT_VOICE_PIPER: str = "pt_BR-cadu-medium"
VALID_ENGINES: tuple[str, ...] = ("edge-tts", "piper")
