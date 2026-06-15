#!/usr/bin/env python3
"""
edge-tts-okular — Leitor TTS com interface gráfica GTK para Okular/GNOME (Wayland)

Uso: Selecione texto no Okular → Ctrl+C → pressione o atalho global
     Uma janela GTK aparecerá com controles de play/pause/stop, voz e velocidade.

Dependências: edge-tts (pipx), mpv, wl-clipboard, python3-gobject, gtk3
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, Gdk

import subprocess
import threading
import signal
import json
import socket
import os
import sys
import tempfile
import time
import re

# ============================================================================
# Configurações
# ============================================================================

EDGE_TTS_BIN = os.path.expanduser("~/.local/bin/edge-tts")
TMP_AUDIO = "/tmp/edge-tts-okular.mp3"
MPV_SOCKET = "/tmp/edge-tts-okular-mpv.sock"
LOCKFILE = "/tmp/edge-tts-okular.lock"
CONFIG_DIR = os.path.expanduser("~/.config/edge-tts-okular")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

VOICES = [
    # (código, idioma, gênero, descrição)
    ("pt-BR-AntonioNeural",               "Português BR",  "Masculino", "Geral"),
    ("pt-BR-FranciscaNeural",             "Português BR",  "Feminino",  "Geral"),
    ("pt-BR-ThalitaMultilingualNeural",   "Português BR",  "Feminino",  "Multilíngue"),
    ("pt-PT-DuarteNeural",                "Português PT",  "Masculino", "Geral"),
    ("pt-PT-RaquelNeural",                "Português PT",  "Feminino",  "Geral"),
    ("en-US-AriaNeural",                  "English US",     "Female",   "News, Novel"),
    ("en-US-ChristopherNeural",           "English US",     "Male",     "News, Novel"),
    ("en-US-AvaNeural",                   "English US",     "Female",   "Conversation"),
    ("en-US-BrianNeural",                 "English US",     "Male",     "Conversation"),
    ("en-US-AndrewNeural",                "English US",     "Male",     "Conversation"),
    ("en-US-EmmaMultilingualNeural",      "English US",     "Female",   "Multilingual"),
    ("en-GB-RyanNeural",                  "English GB",     "Male",     "Geral"),
    ("en-GB-SoniaNeural",                 "English GB",     "Female",   "Geral"),
    ("es-ES-AlvaroNeural",                "Español ES",     "Masculino","Geral"),
    ("es-ES-ElviraNeural",                "Español ES",     "Femenino", "Geral"),
    ("fr-FR-HenriNeural",                 "Français FR",    "Masculin", "Geral"),
    ("fr-FR-DeniseNeural",               "Français FR",    "Féminin",  "Geral"),
    ("de-DE-ConradNeural",                "Deutsch DE",     "Männlich", "Geral"),
    ("de-DE-KatjaNeural",                 "Deutsch DE",     "Weiblich", "Geral"),
]

# Velocidade: slider de 0.5x a 4.0x (convertido para formato edge-tts)
SPEED_MIN = 0.5
SPEED_MAX = 4.0
SPEED_DEFAULT = 1.0
SPEED_STEP = 0.1

# ============================================================================
# Formatação de texto
# ============================================================================

def _fix_spaced_letters(text):
    """Corrige palavras com letras separadas por espaços (artefato de PDF).

    Exemplos:
        'c a m p o'     → 'campo'
        'p r o f u n d a' → 'profunda'
        'u m a'         → 'uma'
        'u m'           → 'um'

    Usa heurística: sequências de 3+ caracteres únicos separados por espaços
    são provavelmente palavras quebradas. Para sequências de 2 caracteres
    (como 'u m'), verifica contra uma lista de palavras comuns em português.
    """
    # Palavras curtas comuns que aparecem com espaços em PDFs
    common_two_letter = {
        'um', 'em', 'ao', 'ou', 'eu', 'se', 'de', 'da', 'do', 'no', 'na',
        'os', 'as', 'me', 'te', 'lá', 'cá', 'já', 'há', 'ir', 'só', 'má',
    }
    common_three_letter = {
        'uma', 'que', 'com', 'por', 'mas', 'dos', 'das', 'nos', 'nas',
        'sua', 'seu', 'são', 'não', 'ele', 'ela', 'foi', 'ser', 'ter',
        'sem', 'nem', 'até', 'sob', 'bem', 'sim', 'fim', 'diz', 'vem',
    }

    def replace_spaced(match):
        spaced = match.group(0)
        joined = spaced.replace(' ', '')
        return joined

    # Padrão: 3 ou mais letras individuais separadas por espaços
    # Ex: "c a m p o" → captura como sequência de "letra espaço letra espaço..."
    text = re.sub(
        r'(?<![a-zA-ZÀ-ÿ])([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])(?: ([a-zA-ZÀ-ÿ])){1,}(?![a-zA-ZÀ-ÿ])',
        replace_spaced,
        text
    )

    # Para "u m a" e similares com 3 letras: tratado acima
    # Para "u m" e similares com 2 letras: tratamento específico
    def replace_two_letter(match):
        a, b = match.group(1), match.group(2)
        joined = a + b
        if joined.lower() in common_two_letter:
            return joined
        return match.group(0)  # Mantém como está se não for palavra conhecida

    text = re.sub(
        r'(?<![a-zA-ZÀ-ÿ])([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])(?![a-zA-ZÀ-ÿ])',
        replace_two_letter,
        text
    )

    return text


def format_text_for_tts(text):
    """Formata o texto para leitura TTS, removendo artefatos comuns de PDFs.

    - Remove caracteres de controle e invisíveis
    - Junta palavras hifenizadas em quebra de linha (ex: 'pala-\\nvra' → 'palavra')
    - Corrige letras separadas por espaços (kerning de PDF): 'c a m p o' → 'campo'
    - Remove pontuação espúria após hifenização (ex: 'his-;' → 'his-')
    - Normaliza quebras de linha e espaços múltiplos
    - Remove espaços antes de pontuação
    - Remove linhas compostas apenas por números (numeração de páginas)
    """
    if not text:
        return ""

    # Remove caracteres de controle (exceto \n e \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Remove caracteres Unicode invisíveis (zero-width, soft hyphen, etc.)
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060\ufeff\u00ad]', '', text)

    # Remove pontuação espúria colada em hifenização: "his-;" → "his-"
    text = re.sub(r'(\w)-[;,.:!?]+(\s)', r'\1-\2', text)

    # Junta palavras hifenizadas em quebra de linha: "pala-\nvra" → "palavra"
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)

    # Substitui quebras de linha por espaço
    text = text.replace('\n', ' ').replace('\r', ' ')

    # Substitui tabulações por espaço
    text = text.replace('\t', ' ')

    # Normaliza espaços múltiplos em um só
    text = re.sub(r' {2,}', ' ', text)

    # Corrige letras separadas por espaços (kerning de PDF)
    text = _fix_spaced_letters(text)

    # Remove espaços antes de pontuação: "texto ." → "texto."
    text = re.sub(r'\s+([.,;:!?\)\]])', r'\1', text)

    # Remove linhas que são apenas números (paginação de PDFs)
    text = re.sub(r'\b\d{1,4}\b(?=\s|$)', '', text)

    # Normaliza espaços novamente após remoções
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
        text = result.stdout.strip()
        # Formata o texto para leitura TTS
        text = format_text_for_tts(text)
        return text
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
        subprocess.run(
            ["pkill", "-f", "mpv.*edge-tts-okular"],
            capture_output=True, timeout=3
        )
    except Exception:
        pass
    # Limpa socket
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
# Aplicação GTK
# ============================================================================

class TTSPlayerWindow(Gtk.Window):
    """Janela principal do leitor TTS."""

    def __init__(self, initial_text=""):
        super().__init__(title="Leitor TTS — edge-tts")
        self.set_default_size(480, 360)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_border_width(14)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()  # Visível em todos os workspaces

        # Estado
        self.mpv_process = None
        self.tts_thread = None
        self.is_paused = False
        self.is_playing = False
        self.is_generating = False

        # Estilo CSS
        self._apply_css()

        # Layout principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)

        # --- Título ---
        title_label = Gtk.Label()
        title_label.set_markup(
            '<span size="large" weight="bold">🔊 Leitor TTS</span>'
        )
        title_label.set_halign(Gtk.Align.START)
        vbox.pack_start(title_label, False, False, 0)

        # --- Área de texto ---
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(120)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_editable(True)
        self.text_view.set_left_margin(8)
        self.text_view.set_right_margin(8)
        self.text_view.set_top_margin(8)
        self.text_view.set_bottom_margin(8)
        self.text_view.get_buffer().set_text(initial_text)

        scroll.add(self.text_view)
        frame.add(scroll)
        vbox.pack_start(frame, True, True, 0)

        # --- Seletores (Voz e Velocidade) ---
        selectors_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Voz
        voice_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        voice_label = Gtk.Label()
        voice_label.set_markup("<b>Voz</b>")
        voice_label.set_halign(Gtk.Align.START)
        voice_box.pack_start(voice_label, False, False, 0)

        self.voice_combo = Gtk.ComboBoxText()
        for code, lang, gender, desc in VOICES:
            self.voice_combo.append(code, f"{lang} — {gender} ({code})")
        # Restaura a voz salva ou usa a primeira
        saved = load_settings()
        saved_voice = saved.get("voice", "")
        voice_codes = [v[0] for v in VOICES]
        if saved_voice in voice_codes:
            self.voice_combo.set_active(voice_codes.index(saved_voice))
        else:
            self.voice_combo.set_active(0)
        self.voice_combo.connect("changed", self._on_voice_changed)
        voice_box.pack_start(self.voice_combo, False, False, 0)

        selectors_box.pack_start(voice_box, True, True, 0)

        # Velocidade (slider)
        speed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        speed_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        speed_label = Gtk.Label()
        speed_label.set_markup("<b>Velocidade</b>")
        speed_label.set_halign(Gtk.Align.START)
        speed_header.pack_start(speed_label, False, False, 0)

        self.speed_value_label = Gtk.Label()
        # Restaura a velocidade salva ou usa o padrão
        saved = load_settings()
        saved_speed = saved.get("speed", SPEED_DEFAULT)
        saved_speed = max(SPEED_MIN, min(SPEED_MAX, float(saved_speed)))
        self.speed_value_label.set_markup(
            f'<span color="#a6e3a1" weight="bold">{saved_speed:.1f}x</span>'
        )
        self.speed_value_label.set_halign(Gtk.Align.END)
        speed_header.pack_end(self.speed_value_label, False, False, 0)

        speed_box.pack_start(speed_header, False, False, 0)

        adjustment = Gtk.Adjustment(
            value=saved_speed,
            lower=SPEED_MIN,
            upper=SPEED_MAX,
            step_increment=SPEED_STEP,
            page_increment=0.5,
        )
        self.speed_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment
        )
        self.speed_scale.set_draw_value(False)
        self.speed_scale.set_digits(1)
        self.speed_scale.set_hexpand(True)
        # Marcas de referência no slider
        self.speed_scale.add_mark(0.5, Gtk.PositionType.BOTTOM, "0.5x")
        self.speed_scale.add_mark(1.0, Gtk.PositionType.BOTTOM, "1x")
        self.speed_scale.add_mark(2.0, Gtk.PositionType.BOTTOM, "2x")
        self.speed_scale.add_mark(3.0, Gtk.PositionType.BOTTOM, "3x")
        self.speed_scale.add_mark(4.0, Gtk.PositionType.BOTTOM, "4x")
        self.speed_scale.connect("value-changed", self._on_speed_changed)
        speed_box.pack_start(self.speed_scale, False, False, 0)

        selectors_box.pack_start(speed_box, True, True, 0)

        vbox.pack_start(selectors_box, False, False, 0)

        # --- Barra de status ---
        self.status_label = Gtk.Label()
        self.status_label.set_markup(
            '<span color="gray">Pronto — cole ou edite o texto e clique ▶ Play</span>'
        )
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        vbox.pack_start(self.status_label, False, False, 0)

        # --- Botões de controle ---
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls_box.set_halign(Gtk.Align.CENTER)

        self.play_btn = Gtk.Button()
        self.play_btn.set_label("▶  Play")
        self.play_btn.get_style_context().add_class("suggested-action")
        self.play_btn.set_size_request(120, 40)
        self.play_btn.connect("clicked", self.on_play)
        controls_box.pack_start(self.play_btn, False, False, 0)

        self.pause_btn = Gtk.Button()
        self.pause_btn.set_label("⏸  Pause")
        self.pause_btn.set_size_request(120, 40)
        self.pause_btn.set_sensitive(False)
        self.pause_btn.connect("clicked", self.on_pause)
        controls_box.pack_start(self.pause_btn, False, False, 0)

        self.stop_btn = Gtk.Button()
        self.stop_btn.set_label("⏹  Stop")
        self.stop_btn.get_style_context().add_class("destructive-action")
        self.stop_btn.set_size_request(120, 40)
        self.stop_btn.set_sensitive(False)
        self.stop_btn.connect("clicked", self.on_stop)
        controls_box.pack_start(self.stop_btn, False, False, 0)

        vbox.pack_start(controls_box, False, False, 8)

        # --- Sinal de fechamento ---
        self.connect("destroy", self.on_quit)

    def _apply_css(self):
        """Aplica CSS customizado para a janela."""
        css = b"""
        window {
            background-color: #1e1e2e;
        }
        label {
            color: #cdd6f4;
        }
        textview {
            background-color: #313244;
            color: #cdd6f4;
            font-family: 'Cantarell', sans-serif;
            font-size: 13px;
        }
        textview text {
            background-color: #313244;
            color: #cdd6f4;
        }
        combobox button {
            background-color: #45475a;
            color: #cdd6f4;
            border-color: #585b70;
            border-radius: 6px;
            padding: 4px 8px;
        }
        combobox button:hover {
            background-color: #585b70;
        }
        frame {
            border-color: #45475a;
            border-radius: 8px;
        }
        button {
            border-radius: 8px;
            font-weight: bold;
            font-size: 13px;
        }
        button.suggested-action {
            background-color: #a6e3a1;
            color: #1e1e2e;
        }
        button.suggested-action:hover {
            background-color: #94e2d5;
        }
        button.destructive-action {
            background-color: #f38ba8;
            color: #1e1e2e;
        }
        button.destructive-action:hover {
            background-color: #eba0ac;
        }
        .status-generating {
            color: #f9e2af;
        }
        .status-playing {
            color: #a6e3a1;
        }
        .status-paused {
            color: #89b4fa;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _set_status(self, text, style_class=None):
        """Atualiza a barra de status (thread-safe)."""
        def update():
            self.status_label.set_markup(text)
            ctx = self.status_label.get_style_context()
            for cls in ["status-generating", "status-playing", "status-paused"]:
                ctx.remove_class(cls)
            if style_class:
                ctx.add_class(style_class)
        GLib.idle_add(update)

    def _set_controls(self, play=True, pause=False, stop=False, selectors=True):
        """Habilita/desabilita controles (thread-safe)."""
        def update():
            self.play_btn.set_sensitive(play)
            self.pause_btn.set_sensitive(pause)
            self.stop_btn.set_sensitive(stop)
            self.voice_combo.set_sensitive(selectors)
            # O slider de velocidade fica sempre ativo para ajuste em tempo real
            self.speed_scale.set_sensitive(True)
            self.text_view.set_editable(selectors)
        GLib.idle_add(update)

    def _get_text(self):
        """Obtém o texto do TextView."""
        buf = self.text_view.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, True).strip()

    def _get_voice(self):
        """Obtém o código da voz selecionada."""
        return self.voice_combo.get_active_id() or "pt-BR-AntonioNeural"

    def _get_speed_multiplier(self):
        """Obtém o valor do slider como multiplicador (0.5–4.0)."""
        return self.speed_scale.get_value()

    def _on_voice_changed(self, combo):
        """Salva a voz selecionada."""
        voice = combo.get_active_id()
        if voice:
            save_settings(voice=voice)

    def _on_speed_changed(self, scale):
        """Atualiza o label e, se estiver tocando, altera a velocidade em tempo real."""
        value = scale.get_value()
        self.speed_value_label.set_markup(
            f'<span color="#a6e3a1" weight="bold">{value:.1f}x</span>'
        )
        save_settings(speed=value)
        # Ajusta velocidade do mpv em tempo real se estiver reproduzindo
        if (self.is_playing or self.is_paused) and \
                self.mpv_process and self.mpv_process.poll() is None:
            send_mpv_command(["set_property", "speed", value])

    # ------------------------------------------------------------------
    # Ações dos botões
    # ------------------------------------------------------------------

    def on_play(self, _button):
        """Inicia a geração do TTS e reprodução."""
        text = self._get_text()
        if not text:
            self._set_status(
                '<span color="#f38ba8">⚠ Nenhum texto para ler.</span>'
            )
            return

        # Se estava pausado, resume
        if self.is_paused and self.mpv_process and self.mpv_process.poll() is None:
            send_mpv_command(["cycle", "pause"])
            self.is_paused = False
            self.is_playing = True
            self._set_status(
                '<span color="#a6e3a1">▶ Reproduzindo…</span>',
                "status-playing"
            )
            self._set_controls(play=False, pause=True, stop=True, selectors=False)
            return

        # Nova reprodução
        voice = self._get_voice()
        speed = self._get_speed_multiplier()

        self.is_generating = True
        self._set_controls(play=False, pause=False, stop=True, selectors=False)
        self._set_status(
            '<span color="#f9e2af">⏳ Gerando áudio…</span>',
            "status-generating"
        )

        self.tts_thread = threading.Thread(
            target=self._generate_and_play,
            args=(text, voice, speed),
            daemon=True,
        )
        self.tts_thread.start()

    def on_pause(self, _button):
        """Pausa ou retoma a reprodução."""
        if not self.mpv_process or self.mpv_process.poll() is not None:
            return

        send_mpv_command(["cycle", "pause"])

        if self.is_paused:
            # Retomar
            self.is_paused = False
            self.is_playing = True
            self._set_status(
                '<span color="#a6e3a1">▶ Reproduzindo…</span>',
                "status-playing"
            )
            self.play_btn.set_label("▶  Play")
            self._set_controls(play=False, pause=True, stop=True, selectors=False)
        else:
            # Pausar
            self.is_paused = True
            self.is_playing = False
            self._set_status(
                '<span color="#89b4fa">⏸ Pausado</span>',
                "status-paused"
            )
            self.play_btn.set_label("▶  Retomar")
            self._set_controls(play=True, pause=True, stop=True, selectors=False)

    def on_stop(self, _button):
        """Para a reprodução."""
        self._stop_playback()
        self._set_status(
            '<span color="#cdd6f4">⏹ Parado — pronto para nova leitura</span>'
        )
        self.play_btn.set_label("▶  Play")
        self._set_controls(play=True, pause=False, stop=False, selectors=True)

    def on_quit(self, _window):
        """Limpa tudo ao fechar."""
        # Salva preferências antes de sair
        save_settings(
            voice=self._get_voice(),
            speed=self._get_speed_multiplier(),
        )
        self._stop_playback()
        cleanup()
        Gtk.main_quit()

    # ------------------------------------------------------------------
    # Lógica de reprodução
    # ------------------------------------------------------------------

    def _stop_playback(self):
        """Para qualquer reprodução em andamento."""
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

        # Remove arquivo de áudio temporário
        try:
            os.unlink(TMP_AUDIO)
        except OSError:
            pass

    def _generate_and_play(self, text, voice, initial_speed):
        """Gera o áudio com edge-tts e reproduz com mpv (roda em thread).

        O áudio é sempre gerado em velocidade normal (+0%). O controle de
        velocidade é feito pelo mpv em tempo real, permitindo ajustes
        durante a reprodução.
        """
        # Formata o texto antes de enviar para o TTS
        text = format_text_for_tts(text)
        try:
            # Limpa reprodução anterior
            self._stop_playback()
            self.is_generating = True

            # Remove arquivo antigo
            try:
                os.unlink(TMP_AUDIO)
            except OSError:
                pass

            # Gera áudio sempre em velocidade normal — o mpv controla o speed
            result = subprocess.run(
                [
                    EDGE_TTS_BIN,
                    "--text", text,
                    "--voice", voice,
                    "--rate", "+0%",
                    "--write-media", TMP_AUDIO,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Verifica se ainda devemos continuar (usuário pode ter clicado Stop)
            if not self.is_generating:
                return

            if result.returncode != 0 or not os.path.exists(TMP_AUDIO):
                self._set_status(
                    '<span color="#f38ba8">❌ Erro ao gerar áudio. '
                    "Verifique a conexão.</span>"
                )
                self._set_controls(play=True, pause=False, stop=False, selectors=True)
                return

            # Inicia mpv com IPC socket para controle
            self.is_generating = False
            self.is_playing = True
            self._set_status(
                '<span color="#a6e3a1">▶ Reproduzindo…</span>',
                "status-playing"
            )
            self._set_controls(play=False, pause=True, stop=True, selectors=False)

            # Remove socket antigo
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

            # Aguarda mpv terminar
            self.mpv_process.wait()

            # Verifica se terminou naturalmente (não foi parado pelo usuário)
            if self.is_playing:
                self.is_playing = False
                self._set_controls(
                    play=False, pause=False, stop=False, selectors=False
                )
                # Contagem regressiva de 5 segundos antes de fechar
                for i in range(5, 0, -1):
                    self._set_status(
                        f'<span color="#cdd6f4">✅ Leitura finalizada — fechando em {i}s…</span>'
                    )
                    time.sleep(1)
                    # Se o usuário interagiu (ex: clicou Play novamente), cancela
                    if self.is_playing or self.is_generating:
                        return
                # Fecha a janela
                GLib.idle_add(self.close)

        except subprocess.TimeoutExpired:
            self._set_status(
                '<span color="#f38ba8">❌ Timeout — o edge-tts demorou demais.</span>'
            )
            self._set_controls(play=True, pause=False, stop=False, selectors=True)
        except Exception as e:
            self._set_status(
                f'<span color="#f38ba8">❌ Erro: {str(e)[:80]}</span>'
            )
            self._set_controls(play=True, pause=False, stop=False, selectors=True)


# ============================================================================
# Main
# ============================================================================

def main():
    # Verifica se já há uma instância rodando (toggle: fecha a anterior)
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        try:
            os.unlink(LOCKFILE)
        except OSError:
            pass

    # Cria lockfile com PID
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))

    # Captura texto da clipboard
    text = get_clipboard_text()

    # Cria e mostra a janela
    win = TTSPlayerWindow(initial_text=text)
    win.show_all()

    # Auto-play: se há texto, inicia a leitura automaticamente ao abrir
    if text:
        GLib.idle_add(win.on_play, None)

    # Limpa lockfile ao sair
    def handle_signal(sig, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        Gtk.main()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
