#!/usr/bin/env python3
"""Narro-RSA — Leitor TTS com indicador na tray do GNOME (Wayland).

Uso: Selecione texto no Okular → Ctrl+C → pressione o atalho global
     Um único ícone aparecerá na tray do GNOME com todos os controles
     (Play, Pausar, Stop, Configurações) no menu.

Dependências: edge-tts (pipx), mpv, wl-clipboard, python3-gobject, gtk3,
              libappindicator-gtk3 + extensão AppIndicator no GNOME Shell
"""

from __future__ import annotations

import os
import signal
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from narro_rsa.clipboard import get_clipboard_text
from narro_rsa.constants import LOCKFILE, MPV_SOCKET, TMP_AUDIO_MP3, TMP_AUDIO_WAV, TMP_TEXT_FILE
from narro_rsa.indicator import TTSIndicator
from narro_rsa.mpv_control import kill_mpv


def _cleanup() -> None:
    """Remove arquivos temporários e encerra o mpv."""
    kill_mpv()
    for path in (TMP_AUDIO_MP3, TMP_AUDIO_WAV, LOCKFILE, MPV_SOCKET, TMP_TEXT_FILE):
        try:
            os.unlink(path)
        except OSError:
            pass


def _acquire_single_instance(text: str) -> bool:
    """Verifica se já há uma instância rodando.

    Se já existe uma instância ativa, escreve o texto no arquivo temporário,
    envia SIGUSR1 para ela e encerra.

    Returns:
        ``True`` se esta é a instância principal (pode continuar).
        Não retorna se outra instância estiver ativa (faz ``sys.exit(0)``).
    """
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r", encoding="utf-8") as fh:
                old_pid = int(fh.read().strip())
            # Verifica se o processo realmente existe
            os.kill(old_pid, 0)
            
            if text:
                try:
                    with open(TMP_TEXT_FILE, "w", encoding="utf-8") as fh:
                        fh.write(text)
                except OSError:
                    pass

            # Envia SIGUSR1 para a instância existente (nova leitura)
            os.kill(old_pid, signal.SIGUSR1)
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            try:
                os.unlink(LOCKFILE)
            except OSError:
                pass

    # Cria lockfile com PID
    with open(LOCKFILE, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))

    return True


def main() -> None:
    """Ponto de entrada principal do Narro-RSA."""
    use_primary = "--primary" in sys.argv
    text = get_clipboard_text(primary=use_primary)

    _acquire_single_instance(text)

    # Cria o indicador na tray
    indicator = TTSIndicator()

    # SIGUSR1 — nova leitura via atalho
    def on_sigusr1(_sig: int, _frame: object) -> None:
        indicator.handle_new_reading_signal()

    signal.signal(signal.SIGUSR1, on_sigusr1)

    # SIGUSR2 — alternar pausa via atalho
    def on_sigusr2(_sig: int, _frame: object) -> None:
        indicator.toggle_pause()

    signal.signal(signal.SIGUSR2, on_sigusr2)


    # SIGTERM — encerramento limpo
    def on_sigterm(_sig: int, _frame: object) -> None:
        indicator._stop_playback()
        _cleanup()
        Gtk.main_quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_sigterm)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Auto-play: se já carregou com texto inicial
    if text:
        GLib.idle_add(indicator._start_new_reading, text)

    try:
        Gtk.main()
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
