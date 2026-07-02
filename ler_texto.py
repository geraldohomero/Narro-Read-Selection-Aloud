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

import urllib.request

# ============================================================================
# Configurações
# ============================================================================

EDGE_TTS_BIN     = os.path.expanduser("~/.local/bin/edge-tts")
PIPER_BIN        = os.path.expanduser("~/.local/bin/piper")
LOCKFILE         = "/tmp/narro-rsa.lock"
MPV_SOCKET       = "/tmp/narro-rsa-mpv.sock"
CONFIG_DIR       = os.path.expanduser("~/.config/narro-rsa")
CONFIG_FILE      = os.path.join(CONFIG_DIR, "settings.json")
PIPER_VOICES_DIR = os.path.join(CONFIG_DIR, "piper-voices")
TMP_AUDIO_MP3    = "/tmp/narro-rsa.mp3"
TMP_AUDIO_WAV    = "/tmp/narro-rsa.wav"

APPINDICATOR_ID  = "narro-rsa"

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
    ("es-AR-TomasNeural",                 "Español AR",    "Masculino", "Geral"),
    ("es-AR-ElenaNeural",                 "Español AR",    "Femenino",  "Geral"),
    ("es-MX-JorgeNeural",                 "Español MX",    "Masculino", "Geral"),
    ("es-MX-DaliaNeural",                 "Español MX",    "Femenino",  "Geral"),
    ("fr-FR-HenriNeural",                 "Français FR",   "Masculin",  "Geral"),
    ("fr-FR-DeniseNeural",                "Français FR",   "Féminin",   "Geral"),
    ("de-DE-ConradNeural",                "Deutsch DE",    "Männlich",  "Geral"),
    ("de-DE-KatjaNeural",                 "Deutsch DE",    "Weiblich",  "Geral"),
]

# Velocidades predefinidas para o submenu
SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.0]
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
    for f in [TMP_AUDIO_MP3, TMP_AUDIO_WAV, LOCKFILE, MPV_SOCKET]:
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


def save_settings(voice=None, speed=None, engine=None):
    """Salva as preferências atuais."""
    settings = load_settings()
    if voice is not None:
        settings["voice"] = voice
    if speed is not None:
        settings["speed"] = speed
    if engine is not None:
        settings["engine"] = engine
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f)
    except OSError:
        pass
def get_downloaded_piper_voices():
    """Retorna um dicionário mapeando código de idioma (ex: 'pt_BR') a uma lista
    de tuplas (código_voz, nome_exibição) para as vozes do Piper já baixadas."""
    downloaded = {}
    if not os.path.exists(PIPER_VOICES_DIR):
        return downloaded
    for filename in os.listdir(PIPER_VOICES_DIR):
        if filename.endswith(".onnx"):
            voice_code = filename[:-5]  # remove '.onnx'
            # Tenta inferir idioma e detalhes do nome
            parts = voice_code.split("-")
            if len(parts) >= 1:
                lang_code = parts[0]
                name = parts[1] if len(parts) > 1 else voice_code
                quality = parts[2] if len(parts) > 2 else ""
                display_name = f"{name} ({quality})" if quality else name
                downloaded.setdefault(lang_code, []).append((voice_code, display_name))
    return downloaded


# ============================================================================
# Indicador na tray do GNOME
# ============================================================================

class TTSIndicator:
    """Indicador único AppIndicator3 na tray do GNOME.

    Um só ícone na tray com menu contendo Play, Pausar, Stop, Configurações,
    Status e Fechar.
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
        self.current_engine = saved.get("engine", "edge-tts")
        if self.current_engine not in ("edge-tts", "piper"):
            self.current_engine = "edge-tts"

        self.current_voice = saved.get("voice", None)
        if not self.current_voice:
            if self.current_engine == "edge-tts":
                self.current_voice = "pt-BR-FranciscaNeural"
            else:
                self.current_voice = "pt_BR-cadu-medium"

        self.current_speed = float(saved.get("speed", SPEED_DEFAULT))
        self.current_speed = max(0.5, min(4.0, self.current_speed))

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
        self.is_building_menu = True
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

        # Configurações
        self.config_item = Gtk.MenuItem(label="Configurações")
        self.config_item.connect("activate", self._on_configuracoes)
        self.main_menu.append(self.config_item)

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
        if hasattr(self, 'ind_main') and self.ind_main:
            self.ind_main.set_menu(self.main_menu)
        self.is_building_menu = False

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

    def _on_configuracoes(self, _item):
        """Abre o diálogo de configurações GTK4 em um processo separado."""
        script_dir = os.path.dirname(os.path.realpath(__file__))
        config_script = os.path.join(script_dir, "config_dialog.py")
        subprocess.Popen([sys.executable, config_script])

    def _on_quit(self, _item):
        save_settings(voice=self.current_voice, speed=self.current_speed, engine=self.current_engine)
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

        # Recarrega configurações mais recentes salvas pelo diálogo GTK4
        saved = load_settings()
        self.current_engine = saved.get("engine", "edge-tts")
        if self.current_engine not in ("edge-tts", "piper"):
            self.current_engine = "edge-tts"

        self.current_voice = saved.get("voice", None)
        if not self.current_voice:
            if self.current_engine == "edge-tts":
                self.current_voice = "pt-BR-FranciscaNeural"
            else:
                self.current_voice = "pt_BR-cadu-medium"

        self.current_speed = float(saved.get("speed", SPEED_DEFAULT))
        self.current_speed = max(0.5, min(4.0, self.current_speed))

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
        for f in (TMP_AUDIO_MP3, TMP_AUDIO_WAV):
            try:
                os.unlink(f)
            except OSError:
                pass

    def _generate_and_play(self, text, voice, initial_speed):
        """Gera o áudio com edge-tts ou piper e reproduz com mpv (roda em thread)."""
        text = format_text_for_tts(text)
        try:
            self._stop_playback()
            self.is_generating = True
            self._update_indicator_state()

            # Determina o arquivo temporário e o comando de acordo com o engine
            if self.current_engine == "piper":
                tmp_audio = TMP_AUDIO_WAV
                model_path = os.path.join(PIPER_VOICES_DIR, f"{voice}.onnx")
                
                if not os.path.exists(model_path):
                    GLib.idle_add(self.status_item.set_label, "Erro: Voz Piper não baixada")
                    self.is_generating = False
                    self._update_indicator_state()
                    return

                try:
                    os.unlink(tmp_audio)
                except OSError:
                    pass

                # Tenta usar o binário local em ~/.local/bin/piper, se não existir busca no PATH
                piper_bin = PIPER_BIN if os.path.exists(PIPER_BIN) else "piper"

                result = subprocess.run(
                    [
                        piper_bin,
                        "--model", model_path,
                        "--output_file", tmp_audio,
                    ],
                    input=text.encode("utf-8"),
                    capture_output=True,
                    timeout=120,
                )
                engine_name = "piper"
            else:
                tmp_audio = TMP_AUDIO_MP3
                try:
                    os.unlink(tmp_audio)
                except OSError:
                    pass

                result = subprocess.run(
                    [
                        EDGE_TTS_BIN,
                        "--text", text,
                        "--voice", voice,
                        "--rate", "+0%",
                        "--write-media", tmp_audio,
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                engine_name = "edge-tts"

            if not self.is_generating:
                return

            if result.returncode != 0 or not os.path.exists(tmp_audio):
                GLib.idle_add(self.status_item.set_label, f"Erro ao gerar áudio ({engine_name})")
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
                    tmp_audio,
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
            GLib.idle_add(self.status_item.set_label, f"Timeout — {engine_name} demorou")
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
