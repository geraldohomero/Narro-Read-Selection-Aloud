"""Acesso à área de transferência do Wayland.

Captura texto do clipboard usando ``wl-paste``.
"""

from __future__ import annotations

import subprocess

from .subprocess_helper import run_on_host


def get_clipboard_text(primary: bool = False) -> str:
    """Captura texto da área de transferência via ``wl-paste`` (Wayland) ou X11.

    Args:
        primary: Se True, lê a seleção primária (texto selecionado).
                 Se False, lê o clipboard padrão (Ctrl+C).

    Returns:
        Texto bruto do clipboard/seleção (sem formatação TTS),
        ou string vazia em caso de erro.
    """
    # 1. Tenta ferramentas X11 via XWayland para evitar foco/alertas
    if primary:
        for cmd in (["xclip", "-o", "-selection", "primary"], ["xsel", "-p", "-o"]):
            try:
                res = run_on_host(cmd, capture_output=True, text=True, timeout=1)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except OSError:
                continue
    else:
        for cmd in (["xclip", "-o", "-selection", "clipboard"], ["xsel", "-b", "-o"]):
            try:
                res = run_on_host(cmd, capture_output=True, text=True, timeout=1)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except OSError:
                continue

    # 2. Fallback para wl-paste nativo
    cmd = ["wl-paste"]
    if primary:
        cmd.append("--primary")
    try:
        result = run_on_host(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""
