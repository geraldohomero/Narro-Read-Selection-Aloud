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
from .subprocess_helper import run_on_host


def send_mpv_command(command: list[Any]) -> dict[str, Any] | None:
    """Envia um comando JSON IPC para o mpv.

    Args:
        command: Lista de argumentos do comando mpv
                 (ex: ``["cycle", "pause"]``).

    Returns:
        Dicionário com a resposta do mpv, ou ``None`` em caso de erro.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(MPV_SOCKET)
            payload = json.dumps({"command": command}) + "\n"
            sock.sendall(payload.encode("utf-8"))
            response = sock.recv(4096).decode("utf-8")
            return json.loads(response)
    except (OSError, json.JSONDecodeError, ConnectionError):
        return None


def kill_mpv() -> None:
    """Mata qualquer instância do mpv associada ao Narro-RSA."""
    try:
        run_on_host(
            ["pkill", "-f", "mpv.*narro-rsa"],
            capture_output=True,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass
    try:
        os.unlink(MPV_SOCKET)
    except OSError:
        pass
