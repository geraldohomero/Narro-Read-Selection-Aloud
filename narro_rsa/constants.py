"""Constantes de caminhos e configuração do Narro-RSA.

Centraliza todas as constantes usadas pelos módulos do projeto,
evitando duplicação entre ler_texto.py e config_dialog.py.
"""

from __future__ import annotations

import os
import shutil

def _resolve_binary(name: str, flatpak_path: str, fallback_path: str) -> str:
    if os.path.exists(flatpak_path):
        return flatpak_path
    expanded = os.path.expanduser(fallback_path)
    if os.path.exists(expanded):
        return expanded
    which = shutil.which(name)
    if which:
        return which
    return name

# ---------------------------------------------------------------------------
# Caminhos de binários
# ---------------------------------------------------------------------------
EDGE_TTS_BIN: str = _resolve_binary("edge-tts", "/app/bin/edge-tts", "~/.local/bin/edge-tts")
PIPER_BIN: str = _resolve_binary("piper", "/app/bin/piper", "~/.local/bin/piper")

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
LAST_PRIMARY_FILE: str = os.path.join(_RUNTIME_DIR, "narro-rsa-last-primary.txt")
LAST_CLIPBOARD_FILE: str = os.path.join(_RUNTIME_DIR, "narro-rsa-last-clipboard.txt")

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
DEFAULT_ENGINE: str = "piper"
VALID_ENGINES: tuple[str, ...] = ("edge-tts", "piper")


def get_default_piper_voice() -> str:
    """Retorna a voz padrão do Piper disponível ou preferencial.

    Verifica se pt_BR-faber-medium ou pt_BR-cadu-medium existem em PIPER_VOICES_DIR.
    Se nenhuma das duas existir, busca qualquer arquivo .onnx presente na pasta e retorna seu stem.
    Se a pasta estiver vazia ou não existir, retorna DEFAULT_VOICE_PIPER ("pt_BR-cadu-medium").
    """
    if os.path.isdir(PIPER_VOICES_DIR):
        for candidate in ("pt_BR-faber-medium", "pt_BR-cadu-medium"):
            if os.path.exists(os.path.join(PIPER_VOICES_DIR, f"{candidate}.onnx")) or os.path.exists(os.path.join(PIPER_VOICES_DIR, candidate)):
                return candidate
        try:
            onnx_files = sorted([f for f in os.listdir(PIPER_VOICES_DIR) if f.endswith(".onnx")])
            if onnx_files:
                return os.path.splitext(onnx_files[0])[0]
        except OSError:
            pass
    return DEFAULT_VOICE_PIPER

