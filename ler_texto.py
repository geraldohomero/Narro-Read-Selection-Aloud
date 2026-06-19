#!/usr/bin/env python3
"""
Narro-RSA — Leitor TTS com indicador na tray do GNOME (Wayland)

Uso: Selecione texto no Okular → Ctrl+C → pressione o atalho global
     Um único ícone aparecerá na tray do GNOME com todos os controles
     (Play, Pausar, Stop, Voz, Velocidade) no menu.

Dependências: edge-tts (pipx), mpv, wl-clipboard, python3-gobject, gtk3,
              libappindicator-gtk3 + extensão AppIndicator no GNOME Shell
"""

import gi
gi.require_version("Gtk", "3.0")

# AppIndicator3 — fallback para AyatanaAppIndicator3 se disponível
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

from gi.repository import Gtk, GLib

import subprocess
import threading
import signal
import json
import socket
import os
import sys
import time
import re

# ============================================================================
# Configurações
# ============================================================================

EDGE_TTS_BIN = os.path.expanduser("~/.local/bin/edge-tts")
TMP_AUDIO    = "/tmp/narro-rsa.mp3"
MPV_SOCKET   = "/tmp/narro-rsa-mpv.sock"
LOCKFILE     = "/tmp/narro-rsa.lock"
CONFIG_DIR   = os.path.expanduser("~/.config/narro-rsa")
CONFIG_FILE  = os.path.join(CONFIG_DIR, "settings.json")

APPINDICATOR_ID = "narro-rsa"

VOICES = [
    # (código, idioma, gênero, descrição)
    ("pt-BR-AntonioNeural",               "Português BR",  "Masculino", "Geral"),
    ("pt-BR-FranciscaNeural",             "Português BR",  "Feminino",  "Geral"),
    ("pt-BR-ThalitaMultilingualNeural",   "Português BR",  "Feminino",  "Multilíngue"),
    ("pt-PT-DuarteNeural",                "Português PT",  "Masculino", "Geral"),
    ("pt-PT-RaquelNeural",                "Português PT",  "Feminino",  "Geral"),
    ("en-US-AriaNeural",                  "English US",    "Female",    "News, Novel"),
    ("en-US-ChristopherNeural",           "English US",    "Male",      "News, Novel"),
    ("en-US-AvaNeural",                   "English US",    "Female",    "Conversation"),
    ("en-US-BrianNeural",                 "English US",    "Male",      "Conversation"),
    ("en-US-AndrewNeural",                "English US",    "Male",      "Conversation"),
    ("en-US-EmmaMultilingualNeural",      "English US",    "Female",    "Multilingual"),
    ("en-GB-RyanNeural",                  "English GB",    "Male",      "Geral"),
    ("en-GB-SoniaNeural",                 "English GB",    "Female",    "Geral"),
    ("es-ES-AlvaroNeural",                "Español ES",    "Masculino", "Geral"),
    ("es-ES-ElviraNeural",                "Español ES",    "Femenino",  "Geral"),
    ("fr-FR-HenriNeural",                 "Français FR",   "Masculin",  "Geral"),
    ("fr-FR-DeniseNeural",                "Français FR",   "Féminin",   "Geral"),
    ("de-DE-ConradNeural",                "Deutsch DE",    "Männlich",  "Geral"),
    ("de-DE-KatjaNeural",                 "Deutsch DE",    "Weiblich",  "Geral"),
]

# Velocidades predefinidas para o submenu
SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0]
SPEED_DEFAULT = 1.0

# ============================================================================
# Formatação de texto
# ============================================================================

def _fix_spaced_letters(text):
    """Corrige palavras com letras separadas por espaços (artefato de PDF)."""
    common_two_letter = {
        'um', 'em', 'ao', 'ou', 'eu', 'se', 'de', 'da', 'do', 'no', 'na',
        'os', 'as', 'me', 'te', 'lá', 'cá', 'já', 'há', 'ir', 'só', 'má',
    }

    def replace_spaced(match):
        return match.group(0).replace(' ', '')

    text = re.sub(
        r'(?<![a-zA-ZÀ-ÿ])([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])(?: ([a-zA-ZÀ-ÿ])){1,}(?![a-zA-ZÀ-ÿ])',
        replace_spaced, text
    )

    def replace_two_letter(match):
        a, b = match.group(1), match.group(2)
        joined = a + b
        return joined if joined.lower() in common_two_letter else match.group(0)

    text = re.sub(
        r'(?<![a-zA-ZÀ-ÿ])([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])(?![a-zA-ZÀ-ÿ])',
        replace_two_letter, text
    )
    return text


def format_text_for_tts(text):
    """Formata o texto para leitura TTS, removendo artefatos comuns de PDFs."""
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060\ufeff\u00ad]', '', text)
    text = re.sub(r'(\w)-[;,.:!?]+(\s)', r'\1-\2', text)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    text = re.sub(r' {2,}', ' ', text)
    text = _fix_spaced_letters(text)
    text = re.sub(r'\s+([.,;:!?\)\]])', r'\1', text)
    text = re.sub(r'\b\d{1,4}\b(?=\s|$)', '', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


# ============================================================================
# Funções auxiliares
# ============================================================================

def get_clipboard_text():
    """Captura texto da área de transferência via wl-paste (Wayland)."""
    try:
        result = subprocess.run(
            ["wl-paste"], capture_output=True, text=True, timeout=3
        )
        return format_text_for_tts(result.stdout.strip())
    except Exception:
        return ""


def send_mpv_command(command):
    """Envia um comando JSON IPC para o mpv."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        payload = json.dumps({"command": command}) + "\n"
        sock.sendall(payload.encode())
        response = sock.recv(4096).decode()
        sock.close()
        return json.loads(response)
    except Exception:
        return None


def kill_mpv():
    """Mata qualquer instância do mpv associada a este script."""
    try:
        subprocess.run(["pkill", "-f", "mpv.*narro-rsa"],
                       capture_output=True, timeout=3)
    except Exception:
        pass
    try:
        os.unlink(MPV_SOCKET)
    except OSError:
        pass


def cleanup():
    """Remove arquivos temporários."""
    kill_mpv()
    for f in [TMP_AUDIO, LOCKFILE, MPV_SOCKET]:
        try:
            os.unlink(f)
        except OSError:
            pass


def load_settings():
    """Carrega as preferências salvas (voz e velocidade)."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(voice=None, speed=None):
    """Salva as preferências atuais."""
    settings = load_settings()
    if voice is not None:
        settings["voice"] = voice
    if speed is not None:
        settings["speed"] = speed
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f)
    except OSError:
        pass


# ============================================================================
# Indicador na tray do GNOME
# ============================================================================

class TTSIndicator:
    """Indicador único AppIndicator3 na tray do GNOME.

    Um só ícone na tray com menu contendo Play, Pausar, Stop, Voz,
    Velocidade, Status e Fechar.
    """

    # Ícones simbólicos Adwaita
    ICON_IDLE       = "audio-speakers-symbolic"
    ICON_GENERATING = "content-loading-symbolic"
    ICON_PLAYING    = "media-playback-start-symbolic"
    ICON_PAUSED     = "media-playback-pause-symbolic"

    PASSIVE = AppIndicator3.IndicatorStatus.PASSIVE
    ACTIVE  = AppIndicator3.IndicatorStatus.ACTIVE

    def __init__(self):
        # Estado de reprodução
        self.mpv_process   = None
        self.tts_thread    = None
        self.is_paused     = False
        self.is_playing    = False
        self.is_generating = False

        # Carrega preferências
        saved = load_settings()
        voice_codes = [v[0] for v in VOICES]
        self.current_voice = saved.get("voice", VOICES[0][0])
        if self.current_voice not in voice_codes:
            self.current_voice = VOICES[0][0]
        self.current_speed = float(saved.get("speed", SPEED_DEFAULT))
        self.current_speed = max(SPEED_OPTIONS[0],
                                 min(SPEED_OPTIONS[-1], self.current_speed))

        # ── Indicador único na tray ───────────────────────────────────
        self.ind_main = AppIndicator3.Indicator.new(
            APPINDICATOR_ID,
            self.ICON_IDLE,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.ind_main.set_status(self.ACTIVE)
        self.ind_main.set_title("Narro-RSA")
        self._build_main_menu()
        self.ind_main.set_menu(self.main_menu)

    # ------------------------------------------------------------------
    # Menu principal
    # ------------------------------------------------------------------

    def _build_main_menu(self):
        """Monta o menu dropdown do indicador principal."""
        self.main_menu = Gtk.Menu()

        # Cabeçalho (não-clicável)
        hdr = Gtk.MenuItem(label="Narro-RSA")
        hdr.set_sensitive(False)
        self.main_menu.append(hdr)
        self.main_menu.append(Gtk.SeparatorMenuItem())

        # Play / Retomar
        self.play_item = Gtk.MenuItem(label="Play")
        self.play_item.connect("activate", self._on_play)
        self.main_menu.append(self.play_item)

        # Pausar
        self.pause_item = Gtk.MenuItem(label="Pausar")
        self.pause_item.connect("activate", self._on_pause)
        self.pause_item.set_sensitive(False)
        self.main_menu.append(self.pause_item)

        # Stop
        self.stop_item = Gtk.MenuItem(label="Stop")
        self.stop_item.connect("activate", self._on_stop)
        self.stop_item.set_sensitive(False)
        self.main_menu.append(self.stop_item)

        self.main_menu.append(Gtk.SeparatorMenuItem())

        # ── Submenu Voz ──────────────────────────────────────────────
        voice_item = Gtk.MenuItem(label="Voz")
        voice_submenu = Gtk.Menu()
        voice_groups: dict = {}
        for code, lang, gender, desc in VOICES:
            voice_groups.setdefault(lang, []).append((code, gender, desc))
        self.voice_radio_items: dict = {}
        group_radio = None
        for lang_name, voices_in_lang in voice_groups.items():
            lhdr = Gtk.MenuItem(label=lang_name)
            lhdr.set_sensitive(False)
            voice_submenu.append(lhdr)
            voice_submenu.append(Gtk.SeparatorMenuItem())
            for code, gender, desc in voices_in_lang:
                radio = Gtk.RadioMenuItem.new_with_label_from_widget(
                    group_radio, f"{gender} — {desc}"
                )
                if group_radio is None:
                    group_radio = radio
                if code == self.current_voice:
                    radio.set_active(True)
                radio.connect("toggled", self._on_voice_toggled, code)
                voice_submenu.append(radio)
                self.voice_radio_items[code] = radio
        voice_item.set_submenu(voice_submenu)
        self.main_menu.append(voice_item)

        # ── Submenu Velocidade ────────────────────────────────────────
        speed_item = Gtk.MenuItem(label="Velocidade")
        speed_submenu = Gtk.Menu()
        self.speed_radio_items: dict = {}
        speed_group = None
        for speed_val in SPEED_OPTIONS:
            label = f"{speed_val:.2g}x"
            if speed_val == 1.0:
                label += "  (normal)"
            radio = Gtk.RadioMenuItem.new_with_label_from_widget(speed_group, label)
            if speed_group is None:
                speed_group = radio
            if abs(speed_val - self.current_speed) < 0.01:
                radio.set_active(True)
            radio.connect("toggled", self._on_speed_toggled, speed_val)
            speed_submenu.append(radio)
            self.speed_radio_items[speed_val] = radio
        speed_item.set_submenu(speed_submenu)
        self.main_menu.append(speed_item)

        self.main_menu.append(Gtk.SeparatorMenuItem())

        # Status (não-clicável)
        self.status_item = Gtk.MenuItem(label="Pronto")
        self.status_item.set_sensitive(False)
        self.main_menu.append(self.status_item)

        self.main_menu.append(Gtk.SeparatorMenuItem())

        # Fechar
        quit_item = Gtk.MenuItem(label="Fechar")
        quit_item.connect("activate", self._on_quit)
        self.main_menu.append(quit_item)

        self.main_menu.show_all()

    # ------------------------------------------------------------------
    # Atualização de estado — ícone e itens do menu
    # ------------------------------------------------------------------

    def _update_indicator_state(self):
        """Atualiza ícone e sensibilidade dos itens do menu."""
        def update():
            if self.is_generating:
                self.ind_main.set_icon_full(self.ICON_GENERATING, "Gerando")
                self.play_item.set_label("Play")
                self.play_item.set_sensitive(False)
                self.pause_item.set_sensitive(False)
                self.stop_item.set_sensitive(True)
                self.status_item.set_label("Gerando áudio…")

            elif self.is_playing:
                self.ind_main.set_icon_full(self.ICON_PLAYING, "Reproduzindo")
                self.play_item.set_label("Play")
                self.play_item.set_sensitive(False)
                self.pause_item.set_label("Pausar")
                self.pause_item.set_sensitive(True)
                self.stop_item.set_sensitive(True)
                self.status_item.set_label("Reproduzindo…")

            elif self.is_paused:
                self.ind_main.set_icon_full(self.ICON_PAUSED, "Pausado")
                self.play_item.set_label("Retomar")
                self.play_item.set_sensitive(True)
                self.pause_item.set_label("Pausar")
                self.pause_item.set_sensitive(False)
                self.stop_item.set_sensitive(True)
                self.status_item.set_label("Pausado")

            else:
                self.ind_main.set_icon_full(self.ICON_IDLE, "Pronto")
                self.play_item.set_label("Play")
                self.play_item.set_sensitive(True)
                self.pause_item.set_label("Pausar")
                self.pause_item.set_sensitive(False)
                self.stop_item.set_sensitive(False)
                self.status_item.set_label("Pronto")

        GLib.idle_add(update)

    # ------------------------------------------------------------------
    # Callbacks de reprodução
    # ------------------------------------------------------------------

    def _on_pause(self, _item):
        """Pausa a reprodução via menu."""
        if self.is_playing:
            self._pause_playback()

    def _on_stop(self, _item):
        """Para a reprodução via menu."""
        self._stop_playback()
        self._update_indicator_state()

    # ------------------------------------------------------------------
    # Callbacks do menu principal
    # ------------------------------------------------------------------

    def _on_play(self, _item):
        """Play ou Retomar via menu principal."""
        if self.is_paused:
            self._resume_playback()
        elif not self.is_playing and not self.is_generating:
            self._start_new_reading()

    def _on_voice_toggled(self, radio, voice_code):
        if radio.get_active():
            self.current_voice = voice_code
            save_settings(voice=voice_code)

    def _on_speed_toggled(self, radio, speed_val):
        if radio.get_active():
            self.current_speed = speed_val
            save_settings(speed=speed_val)
            if (self.is_playing or self.is_paused) and \
                    self.mpv_process and self.mpv_process.poll() is None:
                send_mpv_command(["set_property", "speed", speed_val])

    def _on_quit(self, _item):
        save_settings(voice=self.current_voice, speed=self.current_speed)
        self._stop_playback()
        cleanup()
        Gtk.main_quit()

    # ------------------------------------------------------------------
    # Controles de reprodução
    # ------------------------------------------------------------------

    def _start_new_reading(self):
        """Captura texto do clipboard e inicia a leitura."""
        text = get_clipboard_text()
        if not text:
            GLib.idle_add(self.status_item.set_label, "Nenhum texto no clipboard")
            return
        self.is_generating = True
        self._update_indicator_state()
        self.tts_thread = threading.Thread(
            target=self._generate_and_play,
            args=(text, self.current_voice, self.current_speed),
            daemon=True,
        )
        self.tts_thread.start()

    def _pause_playback(self):
        if not self.mpv_process or self.mpv_process.poll() is not None:
            return
        send_mpv_command(["cycle", "pause"])
        self.is_paused = True
        self.is_playing = False
        self._update_indicator_state()

    def _resume_playback(self):
        if not self.mpv_process or self.mpv_process.poll() is not None:
            return
        send_mpv_command(["cycle", "pause"])
        self.is_paused = False
        self.is_playing = True
        self._update_indicator_state()

    def _stop_playback(self):
        self.is_playing = False
        self.is_paused = False
        self.is_generating = False
        if self.mpv_process and self.mpv_process.poll() is None:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=3)
            except Exception:
                try:
                    self.mpv_process.kill()
                except Exception:
                    pass
        self.mpv_process = None
        kill_mpv()
        try:
            os.unlink(TMP_AUDIO)
        except OSError:
            pass

    def _generate_and_play(self, text, voice, initial_speed):
        """Gera o áudio com edge-tts e reproduz com mpv (roda em thread).

        O áudio é gerado em velocidade normal (+0%). O mpv controla a
        velocidade em tempo real, permitindo ajustes durante a reprodução.
        """
        text = format_text_for_tts(text)
        try:
            self._stop_playback()
            self.is_generating = True
            self._update_indicator_state()

            try:
                os.unlink(TMP_AUDIO)
            except OSError:
                pass

            result = subprocess.run(
                [
                    EDGE_TTS_BIN,
                    "--text", text,
                    "--voice", voice,
                    "--rate", "+0%",
                    "--write-media", TMP_AUDIO,
                ],
                capture_output=True, text=True, timeout=120,
            )

            if not self.is_generating:
                return

            if result.returncode != 0 or not os.path.exists(TMP_AUDIO):
                GLib.idle_add(self.status_item.set_label, "Erro ao gerar áudio")
                self.is_generating = False
                self._update_indicator_state()
                return

            self.is_generating = False
            self.is_playing = True
            self._update_indicator_state()

            try:
                os.unlink(MPV_SOCKET)
            except OSError:
                pass

            self.mpv_process = subprocess.Popen(
                [
                    "mpv",
                    "--no-video",
                    "--really-quiet",
                    f"--input-ipc-server={MPV_SOCKET}",
                    f"--speed={initial_speed}",
                    TMP_AUDIO,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.mpv_process.wait()

            if self.is_playing:
                self.is_playing = False
                GLib.idle_add(self.status_item.set_label, "Leitura finalizada")
                self._update_indicator_state()

        except subprocess.TimeoutExpired:
            GLib.idle_add(self.status_item.set_label, "Timeout — edge-tts demorou")
            self.is_generating = False
            self._update_indicator_state()
        except Exception as e:
            GLib.idle_add(self.status_item.set_label, f"Erro: {str(e)[:50]}")
            self.is_generating = False
            self._update_indicator_state()

    # ------------------------------------------------------------------
    # Sinal SIGUSR1 — nova leitura via atalho de teclado
    # ------------------------------------------------------------------

    def handle_new_reading_signal(self):
        """Chamado via SIGUSR1 quando o atalho é pressionado novamente."""
        if self.is_playing or self.is_paused or self.is_generating:
            self._stop_playback()
            time.sleep(0.2)
        GLib.idle_add(self._start_new_reading)


# ============================================================================
# Main
# ============================================================================

def main():
    # Verifica se já há uma instância rodando
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r") as f:
                old_pid = int(f.read().strip())
            # Envia SIGUSR1 para a instância existente (nova leitura)
            os.kill(old_pid, signal.SIGUSR1)
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            try:
                os.unlink(LOCKFILE)
            except OSError:
                pass

    # Cria lockfile com PID
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))

    # Cria o indicador na tray
    indicator = TTSIndicator()

    # SIGUSR1 — nova leitura via atalho
    def on_sigusr1(sig, frame):
        indicator.handle_new_reading_signal()

    signal.signal(signal.SIGUSR1, on_sigusr1)

    # SIGTERM/SIGINT — encerramento limpo
    def handle_exit(sig, frame):
        indicator._stop_playback()
        cleanup()
        Gtk.main_quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Auto-play: captura texto do clipboard e inicia automaticamente
    text = get_clipboard_text()
    if text:
        GLib.idle_add(indicator._start_new_reading)

    try:
        Gtk.main()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
