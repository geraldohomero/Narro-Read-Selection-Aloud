"""Controle do mpv via IPC socket Unix.

Funções para enviar comandos JSON ao mpv e encerrar instâncias
associadas ao Narro-RSA.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from typing import Any, Callable

from .constants import MPV_SOCKET
from .subprocess_helper import popen_command, run_command
from .text_formatter import split_text_into_chunks
from .tts_engine import (
    GenerationResult,
    TTSRequest,
    cleanup_chunk_files,
    generate_audio,
    get_chunk_audio_path,
)


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


def append_to_mpv_playlist(audio_path: str, timeout: float = 2.0) -> bool:
    """Envia o arquivo de áudio para a playlist do mpv em execução via IPC.

    Args:
        audio_path: Caminho absoluto para o arquivo de áudio a ser anexado.
        timeout: Tempo limite para o comando IPC.

    Returns:
        ``True`` se o comando foi aceito com sucesso, ``False`` caso contrário.
    """
    res = send_mpv_command(["loadfile", audio_path, "append-play"], timeout=timeout)
    return res is not None and res.get("error") in ("success", None)


def play_chunked_tts(
    request: TTSRequest,
    on_first_chunk_ready: Callable[[subprocess.Popen], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    generate_fn: Callable[..., GenerationResult] | None = None,
) -> tuple[subprocess.Popen | None, threading.Thread | None]:
    """Reproduz texto sintetizado progressivamente em chunks no mpv.

    Gera o primeiro chunk (~220 caracteres) imediatamente e inicia o mpv.
    Gera chunks subsequentes em thread de background e adiciona-os à playlist do mpv
    sem pausas (gapless).

    Args:
        request: Parâmetros da requisição TTS.
        on_first_chunk_ready: Callback opcional executado assim que o mpv é iniciado no chunk 0.
        on_error: Callback opcional chamado em caso de falha de síntese.
        generate_fn: Função de síntese opcional (padrão: generate_audio).

    Returns:
        Tupla (processo_mpv, thread_de_background). thread_de_background é None se
        o texto possuir apenas 1 chunk.
    """
    if generate_fn is None:
        generate_fn = generate_audio

    chunks = split_text_into_chunks(request.text)
    if not chunks:
        if on_error:
            on_error("Texto vazio após formatação")
        return (None, None)

    cleanup_chunk_files()

    chunk_0_path = get_chunk_audio_path(0, request.engine)
    req_0 = TTSRequest(text=chunks[0], voice=request.voice, engine=request.engine, speed=request.speed)
    res_0 = generate_fn(req_0, output_path=chunk_0_path, preformatted=True)

    if not res_0.success:
        if on_error:
            on_error(res_0.error_message)
        return (None, None)

    try:
        if os.path.exists(MPV_SOCKET):
            os.unlink(MPV_SOCKET)
    except OSError:
        pass

    proc = popen_command([
        "mpv",
        "--no-video",
        "--really-quiet",
        f"--input-ipc-server={MPV_SOCKET}",
        f"--speed={request.speed}",
        chunk_0_path,
    ])

    if on_first_chunk_ready:
        on_first_chunk_ready(proc)

    if len(chunks) == 1:
        return (proc, None)

    def _background_chunk_worker() -> None:
        for idx, chunk_text in enumerate(chunks[1:], start=1):
            if proc.poll() is not None:
                break
            if not is_mpv_active():
                if not os.path.exists(MPV_SOCKET):
                    # Aguarda brevemente criação do socket pelo mpv
                    for _ in range(10):
                        time.sleep(0.05)
                        if proc.poll() is not None:
                            break
                        if is_mpv_active():
                            break
                    else:
                        if not is_mpv_active():
                            break
                else:
                    break

            chunk_i_path = get_chunk_audio_path(idx, request.engine)
            req_i = TTSRequest(text=chunk_text, voice=request.voice, engine=request.engine, speed=request.speed)
            res_i = generate_fn(req_i, output_path=chunk_i_path, preformatted=True)
            if not res_i.success:
                if on_error:
                    on_error(res_i.error_message)
                break
            if proc.poll() is not None:
                break
            append_to_mpv_playlist(chunk_i_path)

    bg_thread = threading.Thread(target=_background_chunk_worker, daemon=True)
    bg_thread.start()
    return (proc, bg_thread)


def kill_mpv() -> None:
    """Mata qualquer instância do mpv associada ao Narro-RSA e limpa arquivos de chunks."""
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
    cleanup_chunk_files()

