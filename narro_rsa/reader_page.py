"""Reader page component for Narro-RSA."""

from __future__ import annotations
import os
import signal
import subprocess
import sys
import threading
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, GLib, Gtk, Adw

from narro_rsa.constants import (
    LOCKFILE,
    TMP_TEXT_FILE,
    LAST_READ_FILE,
    MPV_SOCKET,
    DEFAULT_VOICE_EDGE,
    DEFAULT_VOICE_PIPER,
    SPEED_DEFAULT,
)
from narro_rsa.settings import load_settings, save_settings
from narro_rsa.mpv_control import kill_mpv, send_mpv_command
from narro_rsa.tts_engine import EngineType, TTSRequest, generate_audio
from narro_rsa.subprocess_helper import popen_command, check_pid_active, check_and_start_daemon
from narro_rsa.translations import _


class ReaderPage(Gtk.Box):
    def __init__(self, main_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_window = main_window
        self._mpv_process = None
        self._local_thread = None

        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(16)
        self.set_margin_bottom(16)

        self._build_ui()
        self.reload_ui_settings()

    def _build_ui(self):
        # Rótulo de instrução
        self.lbl_instruction = Gtk.Label()
        self.lbl_instruction.set_halign(Gtk.Align.START)
        self.append(self.lbl_instruction)

        # Área de Visualização do Texto (TextView + ScrolledWindow)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(180)
        scrolled.add_css_class("text-area-frame")

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_margin_start(8)
        self.text_view.set_margin_end(8)
        self.text_view.set_margin_top(8)
        self.text_view.set_margin_bottom(8)
        scrolled.set_child(self.text_view)
        self.append(scrolled)

        self.focus_controller = Gtk.EventControllerFocus.new()
        self.focus_controller.connect("enter", self._on_text_view_focus_enter)
        self.focus_controller.connect("leave", self._on_text_view_focus_leave)
        self.text_view.add_controller(self.focus_controller)

        # Carrega texto inicial (do áudio ativo ou do último texto lido)
        initial_text = ""
        from narro_rsa.mpv_control import is_mpv_active
        if is_mpv_active() and os.path.exists(LAST_READ_FILE):
            try:
                with open(LAST_READ_FILE, "r", encoding="utf-8") as fh:
                    initial_text = fh.read().strip()
            except OSError:
                pass
        if not initial_text and os.path.exists(LAST_READ_FILE):
            try:
                with open(LAST_READ_FILE, "r", encoding="utf-8") as fh:
                    initial_text = fh.read().strip()
            except OSError:
                pass
        if not initial_text:
            initial_text = _("no_text")
        self.text_view.get_buffer().set_text(initial_text)

        # Se não havia texto salvo recente, tenta ler o clipboard de forma assíncrona
        if initial_text == _("no_text"):
            self.load_clipboard_async()

        # Rótulo da Voz Ativa
        self.active_voice_lbl = Gtk.Label()
        self.active_voice_lbl.set_halign(Gtk.Align.START)
        self.active_voice_lbl.add_css_class("active-voice-badge")
        self.append(self.active_voice_lbl)

        # Seção de Controle de Velocidade
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        speed_box.set_hexpand(True)
        self.append(speed_box)

        self.speed_lbl = Gtk.Label()
        speed_box.append(self.speed_lbl)

        # Slider de Velocidade
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 4.0, 0.05)
        self.speed_scale.set_draw_value(False)
        self.speed_scale.set_hexpand(True)
        self.speed_scale.connect("value-changed", self._on_speed_scale_changed)
        speed_box.append(self.speed_scale)

        self.speed_value_lbl = Gtk.Label()
        self.speed_value_lbl.set_width_chars(6)
        speed_box.append(self.speed_value_lbl)

        # Barra de Controles (Play, Pause, Stop)
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)
        self.append(controls_box)

        self.play_btn = Gtk.Button()
        self.play_btn.set_icon_name("media-playback-start-symbolic")
        self.play_btn.add_css_class("suggested-action")
        self.play_btn.connect("clicked", self._on_play_clicked)
        controls_box.append(self.play_btn)

        self.pause_btn = Gtk.Button()
        self.pause_btn.set_icon_name("media-playback-pause-symbolic")
        self.pause_btn.connect("clicked", self._on_pause_clicked)
        controls_box.append(self.pause_btn)

        self.stop_btn = Gtk.Button()
        self.stop_btn.set_icon_name("media-playback-stop-symbolic")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.connect("clicked", self._on_stop_clicked)
        controls_box.append(self.stop_btn)

    def reload_ui_settings(self):
        """Carrega e sincroniza as preferências atuais na UI."""
        settings = load_settings()
        engine = settings.get("engine", "edge-tts")
        default_voice = DEFAULT_VOICE_EDGE if engine == "edge-tts" else DEFAULT_VOICE_PIPER
        voice = settings.get("voice") or default_voice
        speed = float(settings.get("speed", SPEED_DEFAULT))

        self.lbl_instruction.set_markup(f"<b>{_('clipboard_label')}</b>")
        self.active_voice_lbl.set_markup(_("voice_active", voice=voice, engine="Online" if engine == "edge-tts" else "Offline"))
        self.speed_lbl.set_text(_("speed"))

        self._is_updating_speed = True
        self.speed_scale.set_value(speed)
        self.speed_value_lbl.set_markup(f"<b>{speed:.2f}x</b>")
        self._is_updating_speed = False

        self.play_btn.set_label(_("play"))
        self.pause_btn.set_label(_("pause"))
        self.stop_btn.set_label(_("stop"))

    def _on_speed_scale_changed(self, scale):
        """Salva a nova velocidade e atualiza em tempo real se mpv estiver rodando."""
        if getattr(self, "_is_updating_speed", False):
            return
        val = scale.get_value()
        speed = round(val, 2)
        self.speed_value_lbl.set_markup(f"<b>{speed:.2f}x</b>")
        save_settings(speed=speed)
        send_mpv_command(["set_property", "speed", speed])

    def _on_text_view_focus_enter(self, controller):
        """Ao focar no campo de texto, limpa a instrução se o usuário ainda não digitou nada."""
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()
        if text == _("no_text"):
            buffer.set_text("")

    def _on_text_view_focus_leave(self, controller):
        """Ao perder o foco, restaura a instrução se o campo ficou em branco."""
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()
        if not text:
            buffer.set_text(_("no_text"))

    def load_clipboard_async(self):
        """Lê a área de transferência de forma 100% assíncrona e não-bloqueante via GDK."""
        display = Gdk.Display.get_default()
        if not display:
            return

        clip = display.get_clipboard()
        prim = display.get_primary_clipboard()

        def _apply_text(text: str):
            if not text or not text.strip():
                return
            cleaned = text.strip()
            if hasattr(self, "text_view"):
                buffer = self.text_view.get_buffer()
                start, end = buffer.get_bounds()
                current = buffer.get_text(start, end, True).strip()
                if current == _("no_text") or not current:
                    buffer.set_text(cleaned)

        def _on_prim_done(p, res):
            try:
                t = p.read_text_finish(res)
                if t and t.strip():
                    _apply_text(t)
            except Exception:
                pass

        def _on_clip_done(c, res):
            try:
                t = c.read_text_finish(res)
                if t and t.strip():
                    _apply_text(t)
                elif prim:
                    prim.read_text_async(None, _on_prim_done)
            except Exception:
                if prim:
                    prim.read_text_async(None, _on_prim_done)

        if clip:
            clip.read_text_async(None, _on_clip_done)
        elif prim:
            prim.read_text_async(None, _on_prim_done)

    def _generate_and_play_local(self, text, voice, speed, engine_name):
        from narro_rsa.constants import MPV_SOCKET
        try:
            try:
                os.unlink(MPV_SOCKET)
            except OSError:
                pass
                
            engine_type = EngineType.PIPER if engine_name == "piper" else EngineType.EDGE_TTS
            request = TTSRequest(text=text, voice=voice, engine=engine_type, speed=speed)
            result = generate_audio(request)
            
            if not result.success:
                return
                
            self._mpv_process = popen_command([
                "mpv",
                "--no-video",
                "--really-quiet",
                f"--input-ipc-server={MPV_SOCKET}",
                f"--speed={speed}",
                result.audio_path
            ])
            self._mpv_process.wait()
        except Exception as e:
            print(f"Erro local: {e}")
        finally:
            try:
                if os.path.exists(MPV_SOCKET):
                    os.unlink(MPV_SOCKET)
            except OSError:
                pass

    def _on_play_clicked(self, btn):
        """Salva o texto e envia sinal para ler, ou reproduz localmente se o daemon não estiver ativo."""
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()

        if not text or text == _("no_text"):
            if hasattr(self.main_window, "show_toast"):
                self.main_window.show_toast(_("no_text_toast"))
            return

        # Escreve o texto ouvido em LAST_READ_FILE
        try:
            with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass

        # Tenta ver se o daemon está ativo
        daemon_active = False
        pid = None
        if os.path.exists(LOCKFILE):
            try:
                with open(LOCKFILE, "r", encoding="utf-8") as fh:
                    pid = int(fh.read().strip())
                if check_pid_active(pid):
                    daemon_active = True
            except (ValueError, OSError):
                pass

        if daemon_active and pid:
            try:
                with open(TMP_TEXT_FILE, "w", encoding="utf-8") as fh:
                    fh.write(text)
                with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                return

            try:
                os.kill(pid, signal.SIGUSR1)
            except OSError:
                pass
        else:
            check_and_start_daemon()
            
            kill_mpv()
            settings = load_settings()
            engine = settings.get("engine", "edge-tts")
            default_voice = DEFAULT_VOICE_EDGE if engine == "edge-tts" else DEFAULT_VOICE_PIPER
            voice = settings.get("voice") or default_voice
            speed = float(settings.get("speed", SPEED_DEFAULT))
            
            self._local_thread = threading.Thread(
                target=self._generate_and_play_local,
                args=(text, voice, speed, engine),
                daemon=True
            )
            self._local_thread.start()

    def _on_pause_clicked(self, btn):
        """Informa ao daemon ou ao mpv local para pausar/retomar."""
        send_mpv_command(["cycle", "pause"])

    def _on_stop_clicked(self, btn):
        """Para a reprodução completamente."""
        kill_mpv()
