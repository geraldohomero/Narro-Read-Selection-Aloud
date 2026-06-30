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
# Diálogo de Seleção de Voz (GTK3 Nativo)
# ============================================================================

class VoiceSelectionDialog(Gtk.Dialog):
    def __init__(self, parent_window, engine, language_name, current_voice):
        super().__init__(
            title=f"Selecionar Voz — {engine.upper()}",
            transient_for=parent_window,
            flags=0
        )
        self.set_default_size(500, 400)
        self.engine = engine
        self.language_name = language_name
        self.selected_voice_code = current_voice
        self.download_thread = None
        self.is_downloading = False

        # Adiciona botões na área de ação
        self.ok_button = self.add_button("Selecionar", Gtk.ResponseType.OK)
        self.cancel_button = self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        
        # Constrói o conteúdo
        vbox = self.get_content_area()
        vbox.set_spacing(10)
        vbox.set_border_width(15)

        # Label de Título
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>Selecione uma voz para {language_name} ({engine}):</b>")
        title_label.set_xalign(0.0)
        vbox.pack_start(title_label, False, False, 0)

        # ScrolledWindow para o TreeView
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.IN)
        vbox.pack_start(scrolled_window, True, True, 0)

        # Barra de Progresso (oculta por padrão)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_no_show_all(True)
        self.progress_bar.hide()
        vbox.pack_start(self.progress_bar, False, False, 0)

        # Label de informações adicionais/erros
        self.info_label = Gtk.Label()
        self.info_label.set_xalign(0.0)
        vbox.pack_start(self.info_label, False, False, 0)

        # Caixa de botões do Piper (Download e Exclusão)
        self.piper_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.download_btn = Gtk.Button(label="Baixar voz selecionada")
        self.download_btn.connect("clicked", self._on_download_clicked)
        self.piper_btn_box.pack_start(self.download_btn, True, True, 0)

        self.remove_btn = Gtk.Button(label="Remover voz selecionada")
        self.remove_btn.connect("clicked", self._on_remove_clicked)
        self.piper_btn_box.pack_start(self.remove_btn, True, True, 0)

        vbox.pack_start(self.piper_btn_box, False, False, 0)

        if self.engine == "piper":
            loc_label = Gtk.Label()
            loc_label.set_markup(f"<small><i>Local das vozes: {PIPER_VOICES_DIR}</i></small>")
            loc_label.set_xalign(0.0)
            vbox.pack_start(loc_label, False, False, 0)

        # Configura o TreeView
        self.treeview = Gtk.TreeView()
        scrolled_window.add(self.treeview)

        # Coluna do botão de rádio
        self.renderer_radio = Gtk.CellRendererToggle()
        self.renderer_radio.set_radio(True)
        self.renderer_radio.connect("toggled", self._on_radio_toggled)

        column_radio = Gtk.TreeViewColumn("Sel.", self.renderer_radio)
        column_radio.add_attribute(self.renderer_radio, "active", 0)
        self.treeview.append_column(column_radio)

        # Configura as colunas de acordo com o engine
        if self.engine == "edge-tts":
            # ListStore: [selecionado, código, gênero, descrição]
            self.liststore = Gtk.ListStore(bool, str, str, str)
            self.treeview.set_model(self.liststore)

            renderer_text = Gtk.CellRendererText()
            self.treeview.append_column(Gtk.TreeViewColumn("Código/Voz", renderer_text, text=1))
            self.treeview.append_column(Gtk.TreeViewColumn("Gênero", renderer_text, text=2))
            self.treeview.append_column(Gtk.TreeViewColumn("Descrição", renderer_text, text=3))

            self._populate_edge_voices()
        else:  # piper
            # ListStore: [selecionado, código, nome, qualidade, status_str, is_downloaded, size_str, onnx_url, json_url]
            self.liststore = Gtk.ListStore(bool, str, str, str, str, bool, str, str, str)
            self.treeview.set_model(self.liststore)

            renderer_text = Gtk.CellRendererText()
            self.treeview.append_column(Gtk.TreeViewColumn("Modelo", renderer_text, text=2))
            self.treeview.append_column(Gtk.TreeViewColumn("Qualidade", renderer_text, text=3))
            self.treeview.append_column(Gtk.TreeViewColumn("Status", renderer_text, text=4))
            self.treeview.append_column(Gtk.TreeViewColumn("Tamanho", renderer_text, text=6))

            self.piper_btn_box.show_all()
            self._populate_piper_voices()

        self.show_all()
        self._update_buttons_state()

    def _populate_edge_voices(self):
        self.liststore.clear()
        found_match = False
        rows = []
        for code, lang, gender, desc in VOICES:
            if lang == self.language_name:
                is_selected = (code == self.selected_voice_code)
                if is_selected:
                    found_match = True
                rows.append([is_selected, code, gender, desc])
        if not found_match and len(rows) > 0:
            rows[0][0] = True
            self.selected_voice_code = rows[0][1]
        for r in rows:
            self.liststore.append(r)

    def _populate_piper_voices(self):
        self.liststore.clear()
        voices_json_path = os.path.join(PIPER_VOICES_DIR, "voices.json")
        if not os.path.exists(voices_json_path):
            self.info_label.set_markup("<span color='orange'>Baixando catálogo de vozes...</span>")
            threading.Thread(target=self._download_catalog_thread, daemon=True).start()
            return

        try:
            with open(voices_json_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.info_label.set_text(f"Erro ao carregar catálogo: {e}")
            return

        piper_lang_map = {
            "Português BR": "pt_BR",
            "Português PT": "pt_PT",
            "English US": "en_US",
            "English GB": "en_GB",
            "Español ES": "es_ES",
            "Español AR": "es_AR",
            "Español MX": "es_MX",
            "Français FR": "fr_FR",
            "Deutsch DE": "de_DE"
        }
        target_lang = piper_lang_map.get(self.language_name, "pt_BR")

        rows = []
        found_match = False
        for voice_code, info in data.items():
            lang_code = info.get("language", {}).get("code")
            if lang_code == target_lang:
                onnx_rel = None
                json_rel = None
                size_bytes = 0
                for filepath, fileinfo in info.get("files", {}).items():
                    if filepath.endswith(".onnx"):
                        onnx_rel = filepath
                        size_bytes = fileinfo.get("size_bytes", 0)
                    elif filepath.endswith(".onnx.json"):
                        json_rel = filepath

                if not onnx_rel:
                    continue

                dest_onnx = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
                is_downloaded = os.path.exists(dest_onnx)
                status_str = "Baixado" if is_downloaded else "Não baixado"
                size_str = f"{size_bytes / (1024*1024):.1f} MB"
                
                onnx_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_rel}"
                json_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{json_rel}"

                is_selected = (voice_code == self.selected_voice_code)
                if is_selected:
                    found_match = True

                rows.append([
                    is_selected,
                    voice_code,
                    info.get("name"),
                    info.get("quality"),
                    status_str,
                    is_downloaded,
                    size_str,
                    onnx_url,
                    json_url
                ])

        if not found_match and len(rows) > 0:
            rows[0][0] = True
            self.selected_voice_code = rows[0][1]

        for r in rows:
            self.liststore.append(r)
        self.info_label.set_text("")

    def _download_catalog_thread(self):
        try:
            os.makedirs(PIPER_VOICES_DIR, exist_ok=True)
            url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
            voices_json_path = os.path.join(PIPER_VOICES_DIR, "voices.json")
            urllib.request.urlretrieve(url, voices_json_path)
            GLib.idle_add(self._populate_piper_voices)
        except Exception as e:
            GLib.idle_add(self.info_label.set_text, f"Erro ao baixar catálogo: {e}")

    def _on_radio_toggled(self, renderer, path):
        for row in self.liststore:
            row[0] = False
        self.liststore[path][0] = True
        self.selected_voice_code = self.liststore[path][1]
        self._update_buttons_state()

    def _update_buttons_state(self):
        if self.engine == "edge-tts":
            self.ok_button.set_sensitive(True)
            self.piper_btn_box.hide()
        else:
            self.piper_btn_box.show_all()
            selected_row = None
            for row in self.liststore:
                if row[0]:
                    selected_row = row
                    break
            if selected_row:
                is_downloaded = selected_row[5]
                self.ok_button.set_sensitive(is_downloaded)
                self.download_btn.set_sensitive(not is_downloaded)
                self.remove_btn.set_sensitive(is_downloaded)
                if is_downloaded:
                    self.info_label.set_markup("<span color='green'>Voz pronta para uso!</span>")
                else:
                    self.info_label.set_markup("<span color='orange'>Voz não baixada. Clique em 'Baixar voz selecionada'.</span>")
            else:
                self.ok_button.set_sensitive(False)
                self.download_btn.set_sensitive(False)
                self.remove_btn.set_sensitive(False)

    def _on_download_clicked(self, btn):
        if self.is_downloading:
            return
        selected_row = None
        for row in self.liststore:
            if row[0]:
                selected_row = row
                break
        if not selected_row:
            return

        voice_code = selected_row[1]
        onnx_url = selected_row[7]
        json_url = selected_row[8]

        self.is_downloading = True
        self.download_btn.set_sensitive(False)
        self.ok_button.set_sensitive(False)
        self.cancel_button.set_sensitive(False)
        self.treeview.set_sensitive(False)
        self.progress_bar.show()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Iniciando download...")

        self.download_thread = threading.Thread(
            target=self._download_voice_thread,
            args=(voice_code, onnx_url, json_url),
            daemon=True
        )
        self.download_thread.start()

    def _on_remove_clicked(self, btn):
        selected_row = None
        for row in self.liststore:
            if row[0]:
                selected_row = row
                break
        if not selected_row:
            return

        voice_code = selected_row[1]
        dest_onnx = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
        dest_json = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx.json")

        confirm = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Confirmar exclusão",
        )
        confirm.format_secondary_text(f"Deseja realmente remover os arquivos da voz {voice_code}?")
        response = confirm.run()
        confirm.destroy()

        if response == Gtk.ResponseType.YES:
            for f in (dest_onnx, dest_json):
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except OSError as e:
                        err_dialog = Gtk.MessageDialog(
                            transient_for=self,
                            flags=Gtk.DialogFlags.MODAL,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.OK,
                            text="Erro ao remover arquivos",
                        )
                        err_dialog.format_secondary_text(str(e))
                        err_dialog.run()
                        err_dialog.destroy()
                        return

            self._populate_piper_voices()
            self._update_buttons_state()

    def _download_voice_thread(self, voice_code, onnx_url, json_url):
        dest_onnx = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
        dest_json = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx.json")

        try:
            os.makedirs(PIPER_VOICES_DIR, exist_ok=True)
            GLib.idle_add(self.progress_bar.set_text, "Baixando configurações...")
            urllib.request.urlretrieve(json_url, dest_json)
            GLib.idle_add(self.progress_bar.set_fraction, 0.05)

            GLib.idle_add(self.progress_bar.set_text, f"Baixando modelo {voice_code}...")
            
            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = 0.05 + (downloaded / total_size) * 0.90
                    percent = min(0.99, percent)
                    GLib.idle_add(self.progress_bar.set_fraction, percent)
                    GLib.idle_add(self.progress_bar.set_text, f"Baixando: {int(percent*100)}% ({downloaded / (1024*1024):.1f} MB)")

            urllib.request.urlretrieve(onnx_url, dest_onnx, reporthook=report_hook)

            GLib.idle_add(self.progress_bar.set_fraction, 1.0)
            GLib.idle_add(self.progress_bar.set_text, "Download finalizado!")

            def on_success():
                self.is_downloading = False
                self.progress_bar.hide()
                self.cancel_button.set_sensitive(True)
                self.treeview.set_sensitive(True)
                self._populate_piper_voices()
                self._update_buttons_state()
            GLib.idle_add(on_success)

        except Exception as e:
            for f in (dest_onnx, dest_json):
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
            def on_error(err_msg):
                self.is_downloading = False
                self.progress_bar.hide()
                self.cancel_button.set_sensitive(True)
                self.treeview.set_sensitive(True)
                self._update_buttons_state()

                err_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Erro ao baixar voz",
                )
                err_dialog.format_secondary_text(err_msg)
                err_dialog.run()
                err_dialog.destroy()
            GLib.idle_add(on_error, str(e))


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
        self.current_engine = saved.get("engine", "edge-tts")
        if self.current_engine not in ("edge-tts", "piper"):
            self.current_engine = "edge-tts"

        self.current_voice = saved.get("voice", None)
        if self.current_engine == "edge-tts":
            voice_codes = [v[0] for v in VOICES]
            if not self.current_voice or self.current_voice not in voice_codes:
                self.current_voice = VOICES[0][0]
        else:
            if not self.current_voice:
                self.current_voice = "pt_BR-cadu-medium"

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

        # ── Submenu Voz ──────────────────────────────────────────────
        voice_item = Gtk.MenuItem(label="Voz")
        voice_submenu = Gtk.Menu()

        # Engine: Edge-TTS
        edge_menu_item = Gtk.MenuItem(label="Edge TTS")
        edge_submenu = Gtk.Menu()

        edge_langs = sorted(list(set(v[1] for v in VOICES)))
        edge_group_radio = None
        for lang in edge_langs:
            lang_item = Gtk.MenuItem(label=lang)
            lang_submenu = Gtk.Menu()
            
            # Vozes do Edge TTS listadas diretamente com rádio
            lang_voices = [v for v in VOICES if v[1] == lang]
            for code, _, gender, desc in lang_voices:
                radio = Gtk.RadioMenuItem.new_with_label_from_widget(
                    edge_group_radio, f"{gender} — {desc}"
                )
                if edge_group_radio is None:
                    edge_group_radio = radio
                if self.current_engine == "edge-tts" and code == self.current_voice:
                    radio.set_active(True)
                radio.connect("toggled", self._on_voice_selected_from_menu, "edge-tts", code)
                lang_submenu.append(radio)
                
            lang_item.set_submenu(lang_submenu)
            edge_submenu.append(lang_item)

        edge_menu_item.set_submenu(edge_submenu)
        voice_submenu.append(edge_menu_item)

        # Engine: Piper TTS
        piper_menu_item = Gtk.MenuItem(label="Piper TTS")
        piper_submenu = Gtk.Menu()

        downloaded_piper = get_downloaded_piper_voices()

        piper_lang_map = {
            "Português BR": "pt_BR",
            "Português PT": "pt_PT",
            "English US": "en_US",
            "English GB": "en_GB",
            "Español ES": "es_ES",
            "Español AR": "es_AR",
            "Español MX": "es_MX",
            "Français FR": "fr_FR",
            "Deutsch DE": "de_DE"
        }
        piper_group_radio = None
        for lang_name, lang_code in piper_lang_map.items():
            lang_item = Gtk.MenuItem(label=lang_name)
            lang_submenu = Gtk.Menu()
            
            lang_downloaded = downloaded_piper.get(lang_code, [])
            if lang_downloaded:
                for voice_code, display_name in lang_downloaded:
                    radio = Gtk.RadioMenuItem.new_with_label_from_widget(
                        piper_group_radio, display_name
                    )
                    if piper_group_radio is None:
                        piper_group_radio = radio
                    if self.current_engine == "piper" and voice_code == self.current_voice:
                        radio.set_active(True)
                    radio.connect("toggled", self._on_voice_selected_from_menu, "piper", voice_code)
                    lang_submenu.append(radio)
                
                lang_submenu.append(Gtk.SeparatorMenuItem())
                
                outras_item = Gtk.MenuItem(label="Outras vozes...")
                outras_item.connect("activate", self._on_select_voice_dialog, "piper", lang_name)
                lang_submenu.append(outras_item)
            else:
                baixar_item = Gtk.MenuItem(label="Baixar vozes...")
                baixar_item.connect("activate", self._on_select_voice_dialog, "piper", lang_name)
                lang_submenu.append(baixar_item)
                
            lang_item.set_submenu(lang_submenu)
            piper_submenu.append(lang_item)

        piper_menu_item.set_submenu(piper_submenu)
        voice_submenu.append(piper_menu_item)

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

    def _on_select_voice_dialog(self, menu_item, engine, language_name):
        def on_selected(selected_voice):
            self.current_engine = engine
            self.current_voice = selected_voice
            save_settings(voice=selected_voice, engine=engine)
            self.status_item.set_label(f"Voz: {selected_voice} ({engine})")
            self._build_main_menu()

        dialog = VoiceSelectionDialog(
            parent_window=None,
            engine=engine,
            language_name=language_name,
            current_voice=self.current_voice
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            on_selected(dialog.selected_voice_code)
        else:
            self._build_main_menu()
        dialog.destroy()

    def _on_voice_selected_from_menu(self, radio, engine, voice_code):
        if radio.get_active():
            self.current_engine = engine
            self.current_voice = voice_code
            save_settings(voice=voice_code, engine=engine)
            self.status_item.set_label(f"Voz: {voice_code} ({engine})")

    def _on_speed_toggled(self, radio, speed_val):
        if radio.get_active():
            self.current_speed = speed_val
            save_settings(speed=speed_val)
            if (self.is_playing or self.is_paused) and \
                    self.mpv_process and self.mpv_process.poll() is None:
                send_mpv_command(["set_property", "speed", speed_val])

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
