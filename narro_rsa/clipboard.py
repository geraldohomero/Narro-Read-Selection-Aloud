"""Acesso à área de transferência do Wayland.

Captura texto do clipboard usando ``wl-paste``.
"""

from __future__ import annotations

import subprocess


def get_clipboard_text() -> str:
    """Captura texto da área de transferência via ``wl-paste`` (Wayland).

    Returns:
        Texto bruto do clipboard (sem formatação TTS),
        ou string vazia em caso de erro.
    """
    try:
        result = subprocess.run(
            ["wl-paste"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""
