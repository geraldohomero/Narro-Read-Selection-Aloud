"""Controle do mpv via IPC socket Unix.

Funções para enviar comandos JSON ao mpv e encerrar instâncias
associadas ao Narro-RSA.
"""

from __future__ import annotations

import concurrent.futures
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


def append_to_mpv_playlist(audio_path: str, timeout: float = 2.0, max_retries: int = 5) -> bool:
    """Envia o arquivo de áudio para a playlist do mpv em execução via IPC.

    Args:
        audio_path: Caminho absoluto para o arquivo de áudio a ser anexado.
        timeout: Tempo limite para o comando IPC.
        max_retries: Número de tentativas caso o socket esteja momentaneamente ocupado.

    Returns:
        ``True`` se o comando foi aceito com sucesso, ``False`` caso contrário.
    """
    for _ in range(max_retries):
        res = send_mpv_command(["loadfile", audio_path, "append-play"], timeout=timeout)
        if res is not None and res.get("error") in ("success", None):
            return True
        if not os.path.exists(MPV_SOCKET):
            break
        time.sleep(0.05)
    return False


def play_chunked_tts(
    request: TTSRequest,
    on_first_chunk_ready: Callable[[subprocess.Popen], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    generate_fn: Callable[..., GenerationResult] | None = None,
    max_workers: int = 3,
) -> tuple[subprocess.Popen | None, threading.Thread | None]:
    """Reproduz texto sintetizado progressivamente em chunks no mpv.

    Gera o primeiro chunk imediatamente e inicia o mpv com --idle=yes caso haja múltiplos
    chunks para garantir reprodução gapless contínua sem encerramento prematuro.
    Gera chunks subsequentes adiantados em background (até max_workers em paralelo)
    e anexa-os ordenadamente à playlist do mpv. Ao anexar o último chunk, instrui
    o mpv a desativar o modo idle (idle=no) para que ele encerre normalmente ao
    término da audição de todos os trechos.

    Args:
        request: Parâmetros da requisição TTS.
        on_first_chunk_ready: Callback opcional executado assim que o mpv é iniciado no chunk 0.
        on_error: Callback opcional chamado em caso de falha de síntese.
        generate_fn: Função de síntese opcional (padrão: generate_audio).
        max_workers: Quantidade de chunks sintetizados em paralelo em background (padrão: 3).

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

    mpv_cmd = [
        "mpv",
        "--no-video",
        "--really-quiet",
        f"--input-ipc-server={MPV_SOCKET}",
        f"--speed={request.speed}",
    ]
    if len(chunks) > 1:
        mpv_cmd.append("--idle=yes")
    mpv_cmd.append(chunk_0_path)

    proc = popen_command(mpv_cmd)

    if on_first_chunk_ready:
        on_first_chunk_ready(proc)

    if len(chunks) == 1:
        return (proc, None)

    def _background_chunk_worker() -> None:
        num_chunks = len(chunks)
        worker_count = min(max_workers, num_chunks - 1)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=worker_count)
        futures: dict[int, concurrent.futures.Future[tuple[int, str, GenerationResult]]] = {}

        def _synth_worker(idx: int, text: str) -> tuple[int, str, GenerationResult]:
            c_path = get_chunk_audio_path(idx, request.engine)
            c_req = TTSRequest(text=text, voice=request.voice, engine=request.engine, speed=request.speed)
            c_res = generate_fn(c_req, output_path=c_path, preformatted=True)
            return idx, c_path, c_res

        # Submete chunks subsequentes (1 .. num_chunks - 1)
        for idx in range(1, num_chunks):
            futures[idx] = executor.submit(_synth_worker, idx, chunks[idx])

        try:
            for idx in range(1, num_chunks):
                if proc.poll() is not None:
                    break

                fut = futures[idx]
                # Aguarda o chunk atual terminar verificando periodicamente se o mpv continua vivo
                while proc.poll() is None and not fut.done():
                    try:
                        fut.result(timeout=0.1)
                        break
                    except concurrent.futures.TimeoutError:
                        continue

                if proc.poll() is not None:
                    break

                _, chunk_i_path, res_i = fut.result()
                if not res_i.success:
                    if on_error:
                        on_error(res_i.error_message)
                    send_mpv_command(["set_property", "idle", "no"])
                    break

                if proc.poll() is not None:
                    break

                append_to_mpv_playlist(chunk_i_path)

                # Se foi o último chunk, instrui o mpv a desativar idle para encerrar ao fim da playlist
                if idx == num_chunks - 1:
                    for _ in range(5):
                        res = send_mpv_command(["set_property", "idle", "no"])
                        if res is not None and res.get("error") in ("success", None):
                            break
                        if proc.poll() is not None:
                            break
                        time.sleep(0.05)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

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

