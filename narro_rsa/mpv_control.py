"""Controle do mpv via IPC socket Unix.

Funções para enviar comandos JSON ao mpv e encerrar instâncias
associadas ao Narro-RSA.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from typing import Any

from .constants import MPV_SOCKET
from .subprocess_helper import run_command


def send_mpv_command(command: list[Any], timeout: float = 0.5) -> dict[str, Any] | None:
    """Envia um comando JSON IPC para o mpv.

    Args:
        command: Lista de argumentos do comando mpv
                 (ex: ``["cycle", "pause"]``).
        timeout: Tempo limite em segundos para conexão e resposta.

    Returns:
        Dicionário com a resposta do mpv, ou ``None`` em caso de erro.
    """
    if not os.path.exists(MPV_SOCKET):
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(MPV_SOCKET)
            payload = json.dumps({"command": command}) + "\n"
            sock.sendall(payload.encode("utf-8"))
            response = sock.recv(4096).decode("utf-8")
            return json.loads(response)
    except (OSError, json.JSONDecodeError, ConnectionError):
        return None


def is_mpv_active() -> bool:
    """Verifica se o mpv está realmente em execução e respondendo ao IPC."""
    if not os.path.exists(MPV_SOCKET):
        return False
    res = send_mpv_command(["get_property", "pause"], timeout=0.2)
    if res is None or res.get("error") not in ("success", None):
        # Socket órfão/stale detectado; limpa para evitar bloqueios futuros
        try:
            os.unlink(MPV_SOCKET)
        except OSError:
            pass
        return False
    return True


def kill_mpv() -> None:
    """Mata qualquer instância do mpv associada ao Narro-RSA."""
    try:
        send_mpv_command(["quit"], timeout=0.3)
    except Exception:
        pass
    try:
        run_command(
            ["pkill", "-f", "mpv.*narro-rsa"],
            capture_output=True,
            timeout=1,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass
    try:
        if os.path.exists(MPV_SOCKET):
            os.unlink(MPV_SOCKET)
    except OSError:
        pass
