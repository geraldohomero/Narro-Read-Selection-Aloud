"""Motor de síntese de voz (TTS) do Narro-RSA.

Suporta dois backends:
- **Edge-TTS** (online): Usa a API Microsoft Edge TTS.
- **Piper** (offline): Usa modelos ONNX locais.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from .constants import (
    EDGE_TTS_BIN,
    PIPER_BIN,
    PIPER_VOICES_DIR,
    TMP_AUDIO_MP3,
    TMP_AUDIO_WAV,
    _RUNTIME_DIR,
)
from .subprocess_helper import run_command
from .text_formatter import format_text_for_tts


class EngineType(Enum):
    """Tipos de engine TTS suportados."""
    EDGE_TTS = "edge-tts"
    PIPER = "piper"


class GenerationResult(NamedTuple):
    """Resultado da geração de áudio TTS."""
    success: bool
    audio_path: str
    engine_name: str
    error_message: str


@dataclass(frozen=True)
class TTSRequest:
    """Parâmetros para uma requisição de geração TTS."""
    text: str
    voice: str
    engine: EngineType
    speed: float


def _remove_file_silent(path: str) -> None:
    """Remove um arquivo sem lançar exceção se não existir."""
    try:
        os.unlink(path)
    except OSError:
        pass


def _generate_with_edge_tts(
    text: str, voice: str, output_path: str | None = None
) -> GenerationResult:
    """Gera áudio usando Edge-TTS (online).

    Args:
        text: Texto formatado para síntese.
        voice: Código da voz Edge-TTS (ex: ``pt-BR-FranciscaNeural``).
        output_path: Caminho customizado para o arquivo de áudio gerado.

    Returns:
        Resultado da geração com caminho do arquivo MP3.
    """
    tmp_audio = output_path if output_path else TMP_AUDIO_MP3
    _remove_file_silent(tmp_audio)

    edge_tts_bin = EDGE_TTS_BIN if os.path.exists(EDGE_TTS_BIN) else "edge-tts"

    result = run_command(
        [
            edge_tts_bin,
            "--text", text,
            "--voice", voice,
            "--rate", "+0%",
            "--write-media", tmp_audio,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0 or not os.path.exists(tmp_audio):
        return GenerationResult(
            success=False,
            audio_path="",
            engine_name="edge-tts",
            error_message=f"edge-tts retornou código {result.returncode}",
        )

    return GenerationResult(
        success=True,
        audio_path=tmp_audio,
        engine_name="edge-tts",
        error_message="",
    )


def _generate_with_piper(
    text: str, voice: str, output_path: str | None = None
) -> GenerationResult:
    """Gera áudio usando Piper (offline).

    Args:
        text: Texto formatado para síntese.
        voice: Código da voz Piper (ex: ``pt_BR-cadu-medium``).
        output_path: Caminho customizado para o arquivo de áudio gerado.

    Returns:
        Resultado da geração com caminho do arquivo WAV.
    """
    tmp_audio = output_path if output_path else TMP_AUDIO_WAV
    model_path = os.path.join(PIPER_VOICES_DIR, f"{voice}.onnx")

    if not os.path.exists(model_path):
        return GenerationResult(
            success=False,
            audio_path="",
            engine_name="piper",
            error_message="Voz Piper não baixada",
        )

    _remove_file_silent(tmp_audio)

    # Busca binário local; fallback para PATH
    piper_bin = PIPER_BIN if os.path.exists(PIPER_BIN) else "piper"

    result = run_command(
        [
            piper_bin,
            "--model", model_path,
            "--output_file", tmp_audio,
        ],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )

    if result.returncode != 0 or not os.path.exists(tmp_audio):
        return GenerationResult(
            success=False,
            audio_path="",
            engine_name="piper",
            error_message=f"piper retornou código {result.returncode}",
        )

    return GenerationResult(
        success=True,
        audio_path=tmp_audio,
        engine_name="piper",
        error_message="",
    )


def generate_audio(
    request: TTSRequest,
    output_path: str | None = None,
    preformatted: bool = False,
) -> GenerationResult:
    """Gera áudio TTS a partir de uma requisição.

    Aplica formatação de texto antes da síntese (a menos que preformatted=True)
    e despacha para o backend apropriado.

    Args:
        request: Parâmetros da requisição TTS.
        output_path: Caminho customizado para o arquivo de saída.
        preformatted: Se True, não reaplica formatação no texto.

    Returns:
        Resultado da geração com status, caminho e mensagem de erro.

    Raises:
        subprocess.TimeoutExpired: Se o backend demorar mais de 120s.
    """
    formatted_text = request.text if preformatted else format_text_for_tts(request.text)
    if not formatted_text:
        return GenerationResult(
            success=False,
            audio_path="",
            engine_name=request.engine.value,
            error_message="Texto vazio após formatação",
        )

    if request.engine == EngineType.PIPER:
        return _generate_with_piper(formatted_text, request.voice, output_path=output_path)
    return _generate_with_edge_tts(formatted_text, request.voice, output_path=output_path)


def get_chunk_audio_path(index: int, engine: EngineType) -> str:
    """Retorna o caminho do arquivo de áudio temporário para um determinado chunk."""
    ext = "wav" if engine == EngineType.PIPER else "mp3"
    return os.path.join(_RUNTIME_DIR, f"narro-chunk-{index}.{ext}")


def cleanup_chunk_files() -> None:
    """Remove todos os arquivos temporários de chunks (narro-chunk-*) do diretório de runtime."""
    if not os.path.exists(_RUNTIME_DIR):
        return
    try:
        for fname in os.listdir(_RUNTIME_DIR):
            if fname.startswith("narro-chunk-"):
                _remove_file_silent(os.path.join(_RUNTIME_DIR, fname))
    except OSError:
        pass
