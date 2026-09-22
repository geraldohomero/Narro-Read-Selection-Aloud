"""Indicador AppIndicator3 na tray do GNOME para o Narro-RSA.

Gerencia o ícone na tray, menu de controle de reprodução,
e coordena a geração e reprodução de áudio TTS.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")

# AppIndicator3 — fallback para AyatanaAppIndicator3 se disponível
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

from gi.repository import GLib, Gtk

from .clipboard import get_clipboard_text
from .constants import (
    APPINDICATOR_ID,
    DEFAULT_VOICE_EDGE,
    DEFAULT_VOICE_PIPER,
    MPV_SOCKET,
    SPEED_DEFAULT,
    SPEED_MAX,
    SPEED_MIN,
    TMP_AUDIO_MP3,
    TMP_AUDIO_WAV,
    TMP_TEXT_FILE,
    VALID_ENGINES,
)
from .mpv_control import kill_mpv, send_mpv_command
from .settings import load_settings, save_settings
from .subprocess_helper import popen_command
from .tts_engine import EngineType, TTSRequest, generate_audio


class TTSIndicator:
    """Indicador único AppIndicator3 na tray do GNOME.

    Um só ícone na tray com menu contendo Play, Pausar, Stop,
    Configurações, Status e Fechar.
    """

    # Ícones simbólicos Adwaita
    ICON_IDLE = "audio-speakers-symbolic"
    ICON_GENERATING = "content-loading-symbolic"
    ICON_PLAYING = "media-playback-start-symbolic"
    ICON_PAUSED = "media-playback-pause-symbolic"

    def __init__(self) -> None:
        # Estado de reprodução
        self._mpv_process: subprocess.Popen | None = None
        self._tts_thread: threading.Thread | None = None
        self._is_paused: bool = False
        self._is_playing: bool = False
        self._is_generating: bool = False

        # Carrega preferências
        self._reload_settings()

        # Indicador na tray
        self._indicator = AppIndicator3.Indicator.new(
            APPINDICATOR_ID,
            self.ICON_IDLE,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_title("Narro-RSA")

        self._build_menu()
        self._indicator.set_menu(self._menu)

    # ------------------------------------------------------------------
    # Carregamento de configurações
    # ------------------------------------------------------------------

    def _reload_settings(self) -> None:
        """Carrega (ou recarrega) as preferências do disco."""
        saved = load_settings()

        self._current_engine = saved.get("engine", "edge-tts")
        if self._current_engine not in VALID_ENGINES:
            self._current_engine = "edge-tts"

        self._current_voice = saved.get("voice") or (
            DEFAULT_VOICE_EDGE
            if self._current_engine == "edge-tts"
            else DEFAULT_VOICE_PIPER
        )

        speed = float(saved.get("speed", SPEED_DEFAULT))
        self._current_speed = max(SPEED_MIN, min(SPEED_MAX, speed))

    # ------------------------------------------------------------------
    # Menu principal
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Monta o menu dropdown do indicador principal."""
        self._menu = Gtk.Menu()

        # Cabeçalho (não-clicável)
        header = Gtk.MenuItem(label="Narro-RSA")
        header.set_sensitive(False)
        self._menu.append(header)

        # Abrir Aplicativo
        self._open_app_item = Gtk.MenuItem(label="Abrir")
        self._open_app_item.connect("activate", self._on_open_app)
        self._menu.append(self._open_app_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Play / Retomar
        self._play_item = Gtk.MenuItem(label="Play")
        self._play_item.connect("activate", self._on_play)
        self._menu.append(self._play_item)

        # Pausar
        self._pause_item = Gtk.MenuItem(label="Pausar")
        self._pause_item.connect("activate", self._on_pause)
        self._pause_item.set_sensitive(False)
        self._menu.append(self._pause_item)

        # Stop
        self._stop_item = Gtk.MenuItem(label="Stop")
        self._stop_item.connect("activate", self._on_stop)
        self._stop_item.set_sensitive(False)
        self._menu.append(self._stop_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Configurações
        config_item = Gtk.MenuItem(label="Configurações")
        config_item.connect("activate", self._on_configuracoes)
        self._menu.append(config_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Status (não-clicável)
        self._status_item = Gtk.MenuItem(label="Pronto")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Fechar
        quit_item = Gtk.MenuItem(label="Fechar")
        quit_item.connect("activate", self._on_quit)
        self._menu.append(quit_item)

        self._menu.show_all()

    # ------------------------------------------------------------------
    # Atualização de estado — ícone e itens do menu
    # ------------------------------------------------------------------

    def _update_indicator_state(self) -> None:
        """Atualiza ícone e sensibilidade dos itens do menu."""
        def _update() -> None:
            if self._is_generating:
                self._indicator.set_icon_full(self.ICON_GENERATING, "Gerando")
                self._play_item.set_label("Play")
                self._play_item.set_sensitive(False)
                self._pause_item.set_sensitive(False)
                self._stop_item.set_sensitive(True)
                self._status_item.set_label("Gerando áudio…")

            elif self._is_playing:
                self._indicator.set_icon_full(self.ICON_PLAYING, "Reproduzindo")
                self._play_item.set_label("Play")
                self._play_item.set_sensitive(False)
                self._pause_item.set_label("Pausar")
                self._pause_item.set_sensitive(True)
                self._stop_item.set_sensitive(True)
                self._status_item.set_label("Reproduzindo…")

            elif self._is_paused:
                self._indicator.set_icon_full(self.ICON_PAUSED, "Pausado")
                self._play_item.set_label("Retomar")
                self._play_item.set_sensitive(True)
                self._pause_item.set_label("Pausar")
                self._pause_item.set_sensitive(False)
                self._stop_item.set_sensitive(True)
                self._status_item.set_label("Pausado")

            else:
                self._indicator.set_icon_full(self.ICON_IDLE, "Pronto")
                self._play_item.set_label("Play")
                self._play_item.set_sensitive(True)
                self._pause_item.set_label("Pausar")
                self._pause_item.set_sensitive(False)
                self._stop_item.set_sensitive(False)
                self._status_item.set_label("Pronto")

        GLib.idle_add(_update)

    def _set_status(self, message: str) -> None:
        """Atualiza o label de status de forma thread-safe."""
        GLib.idle_add(self._status_item.set_label, message)

    # ------------------------------------------------------------------
    # Callbacks do menu
    # ------------------------------------------------------------------

    def _on_play(self, _item: Gtk.MenuItem) -> None:
        """Play ou Retomar via menu principal."""
        if self._is_paused:
            self._resume_playback()
        elif not self._is_playing and not self._is_generating:
            self._start_new_reading()

    def _on_pause(self, _item: Gtk.MenuItem) -> None:
        """Pausa a reprodução via menu."""
        if self._is_playing:
            self._pause_playback()

    def _on_stop(self, _item: Gtk.MenuItem) -> None:
        """Para a reprodução via menu."""
        self._stop_playback()
        self._update_indicator_state()

    def _on_open_app(self, _item: Gtk.MenuItem) -> None:
        """Abre a janela principal do aplicativo."""
        try:
            subprocess.Popen(["flatpak", "run", "com.github.geraldohomero.NarroRsa"])
        except OSError:
            script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            main_script = os.path.join(script_dir, "main_window.py")
            if not os.path.exists(main_script):
                main_script = os.path.join(script_dir, "narro-rsa")
            
            if os.access(main_script, os.X_OK) and not main_script.endswith(".py"):
                subprocess.Popen([main_script])
            else:
                subprocess.Popen([sys.executable, main_script])

    def _on_configuracoes(self, _item: Gtk.MenuItem) -> None:
        """Abre a janela de configurações do aplicativo."""
        try:
            subprocess.Popen(["flatpak", "run", "com.github.geraldohomero.NarroRsa", "--settings"])
        except OSError:
            script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            main_script = os.path.join(script_dir, "main_window.py")
            if not os.path.exists(main_script):
                main_script = os.path.join(script_dir, "narro-rsa")
            
            if os.access(main_script, os.X_OK) and not main_script.endswith(".py"):
                subprocess.Popen([main_script, "--settings"])
            else:
                subprocess.Popen([sys.executable, main_script, "--settings"])

    def _on_quit(self, _item: Gtk.MenuItem) -> None:
        """Encerra o aplicativo."""
        save_settings(
            voice=self._current_voice,
            speed=self._current_speed,
            engine=self._current_engine,
        )
        self._stop_playback()
        Gtk.main_quit()

    # ------------------------------------------------------------------
    # Controles de reprodução
    # ------------------------------------------------------------------

    def _start_new_reading(self, text: str | None = None) -> None:
        """Inicia a leitura (lê o texto passado, de arquivo temporário ou do clipboard)."""
        if not text:
            if os.path.exists(TMP_TEXT_FILE):
                try:
                    with open(TMP_TEXT_FILE, "r", encoding="utf-8") as fh:
                        text = fh.read()
                    os.unlink(TMP_TEXT_FILE)
                except OSError:
                    pass

        if not text:
            text = get_clipboard_text()

        if not text:
            self._set_status("Nenhum texto encontrado")
            return

        try:
            from narro_rsa.constants import LAST_READ_FILE
            with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass

        # Recarrega configurações mais recentes (podem ter sido alteradas
        # pelo diálogo de configurações GTK4)
        self._reload_settings()

        self._is_generating = True
        self._update_indicator_state()

        self._tts_thread = threading.Thread(
            target=self._generate_and_play,
            args=(text, self._current_voice, self._current_speed),
            daemon=True,
        )
        self._tts_thread.start()

    def _pause_playback(self) -> None:
        """Pausa a reprodução atual."""
        if not self._mpv_process or self._mpv_process.poll() is not None:
            return
        send_mpv_command(["cycle", "pause"])
        self._is_paused = True
        self._is_playing = False
        self._update_indicator_state()

    def _resume_playback(self) -> None:
        """Retoma a reprodução pausada."""
        if not self._mpv_process or self._mpv_process.poll() is not None:
            return
        send_mpv_command(["cycle", "pause"])
        self._is_paused = False
        self._is_playing = True
        self._update_indicator_state()

    def _stop_playback(self) -> None:
        """Para completamente a reprodução e limpa recursos."""
        self._is_playing = False
        self._is_paused = False
        self._is_generating = False

        if self._mpv_process and self._mpv_process.poll() is None:
            try:
                self._mpv_process.terminate()
                self._mpv_process.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self._mpv_process.kill()
                except OSError:
                    pass

        self._mpv_process = None
        kill_mpv()

        for path in (TMP_AUDIO_MP3, TMP_AUDIO_WAV):
            try:
                os.unlink(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Geração e reprodução (thread de background)
    # ------------------------------------------------------------------

    def _generate_and_play(
        self, text: str, voice: str, speed: float
    ) -> None:
        """Gera o áudio com TTS e reproduz com mpv (roda em thread)."""
        engine_name = self._current_engine  # Definido cedo para o except

        try:
            self._stop_playback()
            self._is_generating = True
            self._update_indicator_state()

            engine_type = (
                EngineType.PIPER
                if self._current_engine == "piper"
                else EngineType.EDGE_TTS
            )

            request = TTSRequest(
                text=text,
                voice=voice,
                engine=engine_type,
                speed=speed,
            )

            result = generate_audio(request)
            engine_name = result.engine_name

            if not self._is_generating:
                return  # Foi cancelado durante a geração

            if not result.success:
                self._set_status(f"Erro: {result.error_message}")
                self._is_generating = False
                self._update_indicator_state()
                return

            # Inicia reprodução com mpv
            self._is_generating = False
            self._is_playing = True
            self._update_indicator_state()

            try:
                os.unlink(MPV_SOCKET)
            except OSError:
                pass

            self._mpv_process = popen_command(
                [
                    "mpv",
                    "--no-video",
                    "--really-quiet",
                    f"--input-ipc-server={MPV_SOCKET}",
                    f"--speed={speed}",
                    result.audio_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._mpv_process.wait()

            if self._is_playing:
                self._is_playing = False
                self._set_status("Leitura finalizada")
                self._update_indicator_state()

        except subprocess.TimeoutExpired:
            self._set_status(f"Timeout — {engine_name} demorou")
            self._is_generating = False
            self._update_indicator_state()
        except Exception as exc:
            self._set_status(f"Erro: {str(exc)[:50]}")
            self._is_generating = False
            self._update_indicator_state()

    # ------------------------------------------------------------------
    # Sinal SIGUSR1 — nova leitura via atalho de teclado
    # ------------------------------------------------------------------

    def handle_new_reading_signal(self) -> None:
        """Chamado via SIGUSR1 quando o atalho é pressionado novamente.

        Usa ``GLib.timeout_add`` em vez de ``time.sleep`` para evitar
        bloquear o thread principal dentro de um signal handler.
        """
        if self._is_playing or self._is_paused or self._is_generating:
            self._stop_playback()
            # Agenda a nova leitura com um pequeno atraso (sem bloquear)
            GLib.timeout_add(200, self._deferred_start_reading)
        else:
            GLib.idle_add(self._start_new_reading)

    def _deferred_start_reading(self) -> bool:
        """Callback de GLib.timeout_add para iniciar nova leitura.

        Returns:
            ``False`` para não repetir o timeout.
        """
        self._start_new_reading()
        return False

    def toggle_pause(self) -> None:
        """Alterna a pausa de forma thread-safe (seguro para signal handlers)."""
        def _toggle() -> None:
            if self._is_playing:
                self._pause_playback()
            elif self._is_paused:
                self._resume_playback()
        GLib.idle_add(_toggle)

