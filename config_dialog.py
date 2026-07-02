#!/usr/bin/env python3
"""
Narro-RSA — Diálogo de Configurações em GTK 4 (Mecanismo -> Dropdown Idioma -> Voz)
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio

import os
import sys
import json
import urllib.request
import threading
import socket
import asyncio

# ============================================================================
# Configurações & Caminhos
# ============================================================================

CONFIG_DIR        = os.path.expanduser("~/.config/narro-rsa")
CONFIG_FILE       = os.path.join(CONFIG_DIR, "settings.json")
PIPER_VOICES_DIR  = os.path.join(CONFIG_DIR, "piper-voices")
EDGE_VOICES_CACHE = os.path.join(CONFIG_DIR, "edge_voices.json")
MPV_SOCKET        = "/tmp/narro-rsa-mpv.sock"

# ============================================================================
# Helpers de Configurações
# ============================================================================

def load_settings():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(voice=None, speed=None, engine=None, theme=None, ui_lang=None):
    settings = load_settings()
    if voice is not None:
        settings["voice"] = voice
    if speed is not None:
        settings["speed"] = speed
    if engine is not None:
        settings["engine"] = engine
    if theme is not None:
        settings["theme"] = theme
    if ui_lang is not None:
        settings["ui_lang"] = ui_lang
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f)
    except OSError:
        pass


def send_mpv_command(command):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(MPV_SOCKET)
        payload = json.dumps({"command": command}) + "\n"
        sock.sendall(payload.encode())
        response = sock.recv(4096).decode()
        sock.close()
        return json.loads(response)
    except Exception:
        return None


def load_edge_voices_cache():
    try:
        if os.path.exists(EDGE_VOICES_CACHE):
            with open(EDGE_VOICES_CACHE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_edge_voices_cache(voices):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(EDGE_VOICES_CACHE, "w") as f:
            json.dump(voices, f)
    except Exception:
        pass

# ============================================================================
# Dicionário de Traduções
# ============================================================================

TRANSLATIONS = {
    "en": {
        "title": "Settings — Narro-RSA",
        "header_title": "Narro-RSA Settings",
        "engine": "Engine:",
        "lang": "Language:",
        "theme": "Theme:",
        "system": "System",
        "light": "Light",
        "dark": "Dark",
        "voices": "Available voices:",
        "speed": "Speed:",
        "close": "Close",
        "download": "Download selected voice",
        "remove": "Remove selected voice",
        "cat_downloading": "Downloading voice catalog...",
        "offline_cat_downloading": "Downloading offline voice catalog...",
        "err_cat": "Error loading catalog: {error}",
        "err_download_piper_cat": "Error downloading Piper catalog: {error}",
        "err_open_piper_cat": "Error opening Piper catalog: {error}",
        "err_update_online_cat": "Error updating online catalog: {error}",
        "online_ready": "Online voice ready for use!",
        "ready": "Voice ready for use!",
        "not_downloaded": "Voice not downloaded. Click 'Download selected voice'.",
        "start_download": "Starting download...",
        "down_settings": "Downloading settings...",
        "down_model": "Downloading model {voice}...",
        "down_progress": "Downloading: {percent}% ({size} MB)",
        "down_finished": "Download finished!",
        "confirm_title": "Confirm deletion",
        "confirm_text": "Do you really want to remove the files for voice {voice}?",
        "err_remove": "Error removing files: {error}",
        "err_download": "Error downloading voice: {error}",
        "col_code": "Code",
        "col_name": "Name",
        "col_gender": "Gender",
        "col_model": "Model",
        "col_quality": "Quality",
        "col_status": "Status",
        "col_size": "Size",
        "status_downloaded": "Downloaded",
        "status_not_downloaded": "Not downloaded",
        "ui_lang_title": "Interface Language",
        "col_engine": "Engine",
        "col_lang": "Language",
        "col_voice": "Voice",
        "active_voice": "Active Voice: {voice} ({engine})",
        "search_placeholder": "Search...",
        "search_label": "Search:",
    },
    "pt_BR": {
        "title": "Configurações — Narro-RSA",
        "header_title": "Configurações do Narro-RSA",
        "engine": "Mecanismo:",
        "lang": "Idioma:",
        "theme": "Tema:",
        "system": "Sistema",
        "light": "Claro",
        "dark": "Escuro",
        "voices": "Vozes disponíveis:",
        "speed": "Velocidade:",
        "close": "Fechar",
        "download": "Baixar voz selecionada",
        "remove": "Remover voz selecionada",
        "cat_downloading": "Baixando catálogo de vozes...",
        "offline_cat_downloading": "Baixando catálogo de vozes offline...",
        "err_cat": "Erro ao carregar catálogo: {error}",
        "err_download_piper_cat": "Erro ao baixar catálogo Piper: {error}",
        "err_open_piper_cat": "Erro ao abrir catálogo Piper: {error}",
        "err_update_online_cat": "Erro ao atualizar catálogo online: {error}",
        "online_ready": "Voz online pronta para uso!",
        "ready": "Voz pronta para uso!",
        "not_downloaded": "Voz não baixada. Clique em 'Baixar voz selecionada'.",
        "start_download": "Iniciando download...",
        "down_settings": "Baixando configurações...",
        "down_model": "Baixando modelo {voice}...",
        "down_progress": "Baixando: {percent}% ({size} MB)",
        "down_finished": "Download finalizado!",
        "confirm_title": "Confirmar exclusão",
        "confirm_text": "Deseja realmente remover os arquivos da voz {voice}?",
        "err_remove": "Erro ao remover arquivos: {error}",
        "err_download": "Erro ao baixar voz: {error}",
        "col_code": "Código",
        "col_name": "Nome",
        "col_gender": "Gênero",
        "col_model": "Modelo",
        "col_quality": "Qualidade",
        "col_status": "Status",
        "col_size": "Tamanho",
        "status_downloaded": "Baixado",
        "status_not_downloaded": "Não baixado",
        "ui_lang_title": "Idioma da Interface",
        "col_engine": "Mecanismo",
        "col_lang": "Idioma",
        "col_voice": "Voz",
        "active_voice": "Voz Ativa: {voice} ({engine})",
        "search_placeholder": "Buscar...",
        "search_label": "Buscar:",
    },
    "zh_CN": {
        "title": "设置 — Narro-RSA",
        "header_title": "Narro-RSA 设置",
        "engine": "语音引擎:",
        "lang": "语言:",
        "theme": "主题:",
        "system": "系统",
        "light": "浅色",
        "dark": "深色",
        "voices": "可用语音:",
        "speed": "语速:",
        "close": "关闭",
        "download": "下载所选语音",
        "remove": "删除所选语音",
        "cat_downloading": "正在下载语音目录...",
        "offline_cat_downloading": "正在下载离线语音目录...",
        "err_cat": "加载目录错误: {error}",
        "err_download_piper_cat": "下载 Piper 目录错误: {error}",
        "err_open_piper_cat": "打开 Piper 目录错误: {error}",
        "err_update_online_cat": "更新在线目录错误: {error}",
        "online_ready": "在线语音已就绪！",
        "ready": "语音已就绪！",
        "not_downloaded": "语音未下载。点击 '下载所选语音'。",
        "start_download": "开始下载...",
        "down_settings": "正在下载设置...",
        "down_model": "正在下载模型 {voice}...",
        "down_progress": "正在下载: {percent}% ({size} MB)",
        "down_finished": "下载完成！",
        "confirm_title": "确认删除",
        "confirm_text": "您确定要删除语音 {voice} 的文件吗？",
        "err_remove": "删除文件错误: {error}",
        "err_download": "下载语音错误: {error}",
        "col_code": "代码",
        "col_name": "名称",
        "col_gender": "性别",
        "col_model": "模型",
        "col_quality": "音质",
        "col_status": "状态",
        "col_size": "大小",
        "status_downloaded": "已下载",
        "status_not_downloaded": "未下载",
        "ui_lang_title": "界面语言",
        "col_engine": "引擎",
        "col_lang": "语言",
        "col_voice": "语音",
        "active_voice": "当前语音: {voice} ({engine})",
        "search_placeholder": "搜索...",
        "search_label": "搜索:",
    }
}

def _(key, **kwargs):
    settings = load_settings()
    ui_lang = settings.get("ui_lang", "en")
    if ui_lang not in TRANSLATIONS:
        ui_lang = "en"
    text = TRANSLATIONS[ui_lang].get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text

# Lista simplificada para fallback se estiver offline no primeiro carregamento
FALLBACK_EDGE_VOICES = [
    {"ShortName": "pt-BR-AntonioNeural", "Gender": "Male", "FriendlyName": "Microsoft Antonio Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-BR-FranciscaNeural", "Gender": "Female", "FriendlyName": "Microsoft Francisca Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-BR-ThalitaMultilingualNeural", "Gender": "Female", "FriendlyName": "Microsoft Thalita Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-PT-DuarteNeural", "Gender": "Male", "FriendlyName": "Microsoft Duarte Online (Natural) - Portuguese (Portugal)", "Locale": "pt-PT"},
    {"ShortName": "pt-PT-RaquelNeural", "Gender": "Female", "FriendlyName": "Microsoft Raquel Online (Natural) - Portuguese (Portugal)", "Locale": "pt-PT"},
    {"ShortName": "en-US-AriaNeural", "Gender": "Female", "FriendlyName": "Microsoft Aria Online (Natural) - English (United States)", "Locale": "en-US"},
    {"ShortName": "en-US-GuyNeural", "Gender": "Male", "FriendlyName": "Microsoft Guy Online (Natural) - English (United States)", "Locale": "en-US"},
    {"ShortName": "es-ES-AlvaroNeural", "Gender": "Male", "FriendlyName": "Microsoft Alvaro Online (Natural) - Spanish (Spain)", "Locale": "es-ES"},
    {"ShortName": "es-ES-ElviraNeural", "Gender": "Female", "FriendlyName": "Microsoft Elvira Online (Natural) - Spanish (Spain)", "Locale": "es-ES"},
    {"ShortName": "fr-FR-HenriNeural", "Gender": "Male", "FriendlyName": "Microsoft Henri Online (Natural) - French (France)", "Locale": "fr-FR"},
    {"ShortName": "de-DE-ConradNeural", "Gender": "Male", "FriendlyName": "Microsoft Conrad Online (Natural) - German (Germany)", "Locale": "de-DE"}
]

# ============================================================================
# Janela Principal GTK 4
# ============================================================================

class ConfigWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("title"))
        self.set_default_size(640, 680)

        # Carrega preferências salvas
        self.settings = load_settings()
        self.current_engine = self.settings.get("engine", "edge-tts")
        if self.current_engine not in ("edge-tts", "piper"):
            self.current_engine = "edge-tts"

        self.current_voice = self.settings.get("voice", None)
        self.current_speed = float(self.settings.get("speed", 1.0))
        self.current_theme = self.settings.get("theme", "light")
        if self.current_theme not in ("light", "dark"):
            self.current_theme = "light"
        self.current_ui_lang = self.settings.get("ui_lang", "en")

        self.is_downloading = False
        self.download_thread = None
        self.filter_text = ""
        self.selected_lang = None

        # Listas de catálogos dinâmicos
        self.edge_voices = None
        self.piper_catalog = None

        self._apply_css()

        # Configuração da HeaderBar (GNOME HIG)
        header_bar = Gtk.HeaderBar()
        self.set_titlebar(header_bar)

        self.header_title_label = Gtk.Label()
        self.header_title_label.set_markup(f"<span font='12' weight='bold'>{_('header_title')}</span>")
        header_bar.set_title_widget(self.header_title_label)

        # Botão Hambúrguer (Menu de Idioma da UI)
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        header_bar.pack_end(menu_button)

        self.popover = Gtk.Popover()
        menu_button.set_popover(self.popover)

        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        popover_box.set_margin_start(12)
        popover_box.set_margin_end(12)
        popover_box.set_margin_top(12)
        popover_box.set_margin_bottom(12)
        self.popover.set_child(popover_box)

        self.popover_title_label = Gtk.Label()
        self.popover_title_label.set_markup(f"<b>{_('ui_lang_title')}</b>")
        popover_box.append(self.popover_title_label)

        self.lang_en_radio = Gtk.CheckButton(label="English")
        self.lang_pt_radio = Gtk.CheckButton(label="Português (Brasil)")
        self.lang_pt_radio.set_group(self.lang_en_radio)
        self.lang_zh_radio = Gtk.CheckButton(label="简体中文")
        self.lang_zh_radio.set_group(self.lang_en_radio)

        if self.current_ui_lang == "pt_BR":
            self.lang_pt_radio.set_active(True)
        elif self.current_ui_lang == "zh_CN":
            self.lang_zh_radio.set_active(True)
        else:
            self.lang_en_radio.set_active(True)

        self.lang_en_radio.connect("toggled", self._on_ui_lang_radio_toggled, "en")
        self.lang_pt_radio.connect("toggled", self._on_ui_lang_radio_toggled, "pt_BR")
        self.lang_zh_radio.connect("toggled", self._on_ui_lang_radio_toggled, "zh_CN")

        popover_box.append(self.lang_en_radio)
        popover_box.append(self.lang_pt_radio)
        popover_box.append(self.lang_zh_radio)

        # Layout principal da janela (vertical)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        main_box.set_margin_top(18)
        main_box.set_margin_bottom(18)
        self.set_child(main_box)

        # ── Seção de Voz Ativa no Topo ──
        active_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        active_box.add_css_class("active-voice-frame")
        self.active_voice_lbl = Gtk.Label()
        self.active_voice_lbl.set_halign(Gtk.Align.START)
        active_box.append(self.active_voice_lbl)
        main_box.append(active_box)

        # ==========================================
        # Painel Superior de Configurações (Grid)
        # ==========================================
        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(10)
        grid.set_hexpand(True)
        main_box.append(grid)

        # 1. Mecanismo (Engine)
        self.engine_label = Gtk.Label()
        self.engine_label.set_halign(Gtk.Align.START)
        grid.attach(self.engine_label, 0, 0, 1, 1)

        self.engine_combo = Gtk.ComboBoxText()
        self.engine_combo.append("edge-tts", "Edge TTS (Online)")
        self.engine_combo.append("piper", "Piper TTS (Offline)")
        self.engine_combo.set_hexpand(True)
        grid.attach(self.engine_combo, 1, 0, 1, 1)

        # 2. Tema
        self.theme_label = Gtk.Label()
        self.theme_label.set_halign(Gtk.Align.START)
        grid.attach(self.theme_label, 2, 0, 1, 1)

        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.set_hexpand(True)
        grid.attach(self.theme_combo, 3, 0, 1, 1)

        # 3. Busca de Idioma
        self.search_label = Gtk.Label()
        self.search_label.set_halign(Gtk.Align.START)
        grid.attach(self.search_label, 0, 1, 1, 1)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        grid.attach(self.search_entry, 1, 1, 1, 1)

        # 4. Idioma (Dropdown / Gtk.ComboBox)
        self.lang_label = Gtk.Label()
        self.lang_label.set_halign(Gtk.Align.START)
        grid.attach(self.lang_label, 2, 1, 1, 1)

        # Model e filtro para o dropdown de idiomas
        self.lang_liststore = Gtk.ListStore(str)
        self.lang_filter_model = Gtk.TreeModelFilter(child_model=self.lang_liststore)
        self.lang_filter_model.set_visible_func(self.lang_filter_visible_func)

        self.lang_combo = Gtk.ComboBox.new_with_model(self.lang_filter_model)
        self.lang_combo.set_hexpand(True)
        renderer_lang = Gtk.CellRendererText()
        self.lang_combo.pack_start(renderer_lang, True)
        self.lang_combo.add_attribute(renderer_lang, "text", 0)
        grid.attach(self.lang_combo, 3, 1, 1, 1)

        # 5. Velocidade da Voz
        self.speed_title = Gtk.Label()
        self.speed_title.set_halign(Gtk.Align.START)
        grid.attach(self.speed_title, 0, 2, 1, 1)

        speed_scale_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        speed_scale_box.set_hexpand(True)
        grid.attach(speed_scale_box, 1, 2, 3, 1)

        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 4.0, 0.05)
        self.speed_scale.set_value(self.current_speed)
        self.speed_scale.set_draw_value(False)
        self.speed_scale.set_hexpand(True)
        speed_scale_box.append(self.speed_scale)

        self.speed_value_label = Gtk.Label()
        self.speed_value_label.set_width_chars(6)
        speed_scale_box.append(self.speed_value_label)

        # Separador / Título para vozes
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        self.voices_header_label = Gtk.Label()
        self.voices_header_label.set_markup(f"<b>{_('voices')}</b>")
        self.voices_header_label.set_halign(Gtk.Align.START)
        main_box.append(self.voices_header_label)

        # ScrolledWindow + TreeView de Vozes
        self.voice_scrolled = Gtk.ScrolledWindow()
        self.voice_scrolled.set_vexpand(True)
        self.voice_scrolled.add_css_class("list-frame")
        main_box.append(self.voice_scrolled)

        self.voice_treeview = Gtk.TreeView()
        self.voice_scrolled.set_child(self.voice_treeview)

        # Colunas de Vozes (Sel., Código, Nome, Gênero/Qualidade, Status, Tamanho)
        self.renderer_radio = Gtk.CellRendererToggle()
        self.renderer_radio.set_radio(True)
        self.renderer_radio.connect("toggled", self._on_voice_radio_toggled)

        col_sel = Gtk.TreeViewColumn("Sel.", self.renderer_radio)
        col_sel.add_attribute(self.renderer_radio, "active", 0)
        col_sel.set_expand(False)
        self.voice_treeview.append_column(col_sel)

        renderer_text = Gtk.CellRendererText()

        col_code = Gtk.TreeViewColumn(_("col_code"), renderer_text, text=1)
        col_code.set_expand(False)
        col_code.set_resizable(True)
        self.voice_treeview.append_column(col_code)

        col_name = Gtk.TreeViewColumn(_("col_name"), renderer_text, text=2)
        col_name.set_expand(True)
        col_name.set_resizable(True)
        self.voice_treeview.append_column(col_name)

        col_gender = Gtk.TreeViewColumn(_("col_gender"), renderer_text, text=3)
        col_gender.set_expand(False)
        col_gender.set_resizable(True)
        self.voice_treeview.append_column(col_gender)

        col_status = Gtk.TreeViewColumn(_("col_status"), renderer_text, text=4)
        col_status.set_expand(False)
        col_status.set_resizable(True)
        self.voice_treeview.append_column(col_status)

        col_size = Gtk.TreeViewColumn(_("col_size"), renderer_text, text=6)
        col_size.set_expand(False)
        col_size.set_resizable(True)
        self.voice_treeview.append_column(col_size)

        # Model: Col 0: selected, Col 1: code, Col 2: name, Col 3: gender/quality, Col 4: status, Col 5: is_downloaded, Col 6: size, Col 7: onnx_url, Col 8: json_url
        self.voice_liststore = Gtk.ListStore(bool, str, str, str, str, bool, str, str, str)
        self.voice_treeview.set_model(self.voice_liststore)

        # Painel do Piper
        self.piper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.append(self.piper_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.piper_box.append(btn_box)

        self.download_btn = Gtk.Button()
        self.download_btn.set_hexpand(True)
        btn_box.append(self.download_btn)

        self.remove_btn = Gtk.Button()
        self.remove_btn.set_hexpand(True)
        btn_box.append(self.remove_btn)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        self.progress_bar.set_show_text(True)
        self.piper_box.append(self.progress_bar)

        self.info_label = Gtk.Label()
        self.info_label.set_halign(Gtk.Align.START)
        self.piper_box.append(self.info_label)

        # Divisor no rodapé
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Botão Fechar no rodapé
        close_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(close_btn_box)

        self.close_btn = Gtk.Button()
        self.close_btn.set_halign(Gtk.Align.END)
        self.close_btn.set_hexpand(True)
        self.close_btn.add_css_class("suggested-action")
        close_btn_box.append(self.close_btn)

        # Inicializa textos da UI segundo o idioma atual
        self._update_ui_texts()

        # Define estado inicial do mecanismo
        self._is_initializing_combos = True
        self.engine_combo.set_active_id(self.current_engine)
        self._is_initializing_combos = False

        # Conecta os sinais
        self.engine_combo.connect("changed", self._on_engine_changed)
        self.theme_combo.connect("changed", self._on_theme_changed)
        self.speed_scale.connect("value-changed", self._on_speed_scale_changed)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.download_btn.connect("clicked", self._on_download_clicked)
        self.remove_btn.connect("clicked", self._on_remove_clicked)
        self.close_btn.connect("clicked", self._on_close_clicked)
        self.lang_combo.connect("changed", self._on_lang_combo_changed)

        # Conecta seleção do painel de vozes
        voice_selection = self.voice_treeview.get_selection()
        voice_selection.set_mode(Gtk.SelectionMode.SINGLE)
        voice_selection.connect("changed", self._on_voice_selection_changed)

        # Aplica o tema imediatamente
        self._apply_theme()

        # Carga assíncrona dos catálogos (Edge e Piper)
        threading.Thread(target=self._load_catalogs_thread, daemon=True).start()

    def _apply_css(self):
        css_provider = Gtk.CssProvider()
        css_code = """
            .list-frame {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: @theme_base_color;
            }
            .active-voice-frame {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: alpha(@theme_selected_bg_color, 0.1);
                padding: 12px;
                margin-bottom: 5px;
            }
            .active-voice-frame label {
                font-size: 11pt;
            }
            .section-title {
                font-weight: bold;
                margin-top: 8px;
            }
            scale {
                margin: 4px 0;
            }
            progressbar {
                margin-top: 4px;
            }
        """
        css_provider.load_from_string(css_code)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _update_ui_texts(self):
        # Atualiza a barra de título
        self.set_title(_("title"))
        self.header_title_label.set_markup(f"<span font='12' weight='bold'>{_('header_title')}</span>")
        self.popover_title_label.set_markup(f"<b>{_('ui_lang_title')}</b>")

        # Rótulos da Grade
        self.theme_label.set_text(_("theme"))
        self._repopulate_theme_combo()

        # Rótulos e Botões
        self.engine_label.set_text(_("engine"))
        self.lang_label.set_text(_("lang"))
        self.search_label.set_text(_("search_label"))
        self.speed_title.set_text(_("speed"))
        self.close_btn.set_label(_("close"))
        self.download_btn.set_label(_("download"))
        self.remove_btn.set_label(_("remove"))
        self.speed_value_label.set_markup(f"<b>{self.current_speed:.2f}x</b>")
        self.search_entry.set_placeholder_text(_("search_placeholder"))
        self.voices_header_label.set_markup(f"<b>{_('voices')}</b>")

        # Atualiza títulos das colunas dinamicamente
        cols = self.voice_treeview.get_columns()
        if len(cols) >= 6:
            cols[1].set_title(_("col_code"))
            cols[2].set_title(_("col_name") if self.current_engine == "edge-tts" else _("col_model"))
            cols[3].set_title(_("col_gender") if self.current_engine == "edge-tts" else _("col_quality"))
            cols[4].set_title(_("col_status"))
            cols[5].set_title(_("col_size"))

        # Atualiza a exibição da voz selecionada
        self._update_current_selection_label()

        # Atualiza as tabelas se carregadas
        if self.edge_voices or self.piper_catalog:
            self._on_catalogs_loaded()

    def _repopulate_theme_combo(self):
        self._is_initializing_combos = True
        self.theme_combo.remove_all()
        self.theme_combo.append("light", _("light"))
        self.theme_combo.append("dark", _("dark"))
        self.theme_combo.set_active_id(self.current_theme)
        self._is_initializing_combos = False

    def _on_ui_lang_radio_toggled(self, button, lang_code):
        if button.get_active():
            self.current_ui_lang = lang_code
            save_settings(ui_lang=lang_code)
            self._update_ui_texts()
            self.popover.popdown()

    def _load_catalogs_thread(self):
        # 1. Carrega vozes Edge do cache primeiro
        self.edge_voices = load_edge_voices_cache()
        if self.edge_voices:
            GLib.idle_add(self._on_catalogs_loaded)

        # 2. Carrega catálogo do Piper
        voices_json_path = os.path.join(PIPER_VOICES_DIR, "voices.json")
        if not os.path.exists(voices_json_path):
            GLib.idle_add(self.info_label.set_markup, f"<span color='orange'>{_('offline_cat_downloading')}</span>")
            try:
                os.makedirs(PIPER_VOICES_DIR, exist_ok=True)
                url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
                urllib.request.urlretrieve(url, voices_json_path)
            except Exception as e:
                msg = _("err_download_piper_cat", error=e)
                GLib.idle_add(self.info_label.set_text, msg)

        try:
            with open(voices_json_path, "r") as f:
                self.piper_catalog = json.load(f)
        except Exception as e:
            self.piper_catalog = {}
            print(_("err_open_piper_cat", error=e))

        # 3. Busca catálogo Edge atualizado da nuvem para atualizar o cache
        try:
            import edge_tts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            voices = loop.run_until_complete(edge_tts.list_voices())
            loop.close()

            formatted_voices = []
            for v in voices:
                formatted_voices.append({
                    "Name": v.get("Name", ""),
                    "ShortName": v.get("ShortName", ""),
                    "Gender": v.get("Gender", ""),
                    "Locale": v.get("Locale", ""),
                    "FriendlyName": v.get("FriendlyName", ""),
                })
            save_edge_voices_cache(formatted_voices)
            self.edge_voices = formatted_voices
        except Exception as e:
            print(_("err_update_online_cat", error=e))
            if not self.edge_voices:
                self.edge_voices = FALLBACK_EDGE_VOICES

        GLib.idle_add(self._on_catalogs_loaded)

    def get_language_name_for_voice(self, engine, voice_code):
        if not voice_code:
            return None
        if engine == "edge-tts":
            if self.edge_voices:
                for v in self.edge_voices:
                    if v["ShortName"] == voice_code:
                        return v["FriendlyName"].split(" - ")[-1]
        else:
            if self.piper_catalog:
                voice_info = self.piper_catalog.get(voice_code)
                if voice_info:
                    lang_info = voice_info.get("language", {})
                    name = lang_info.get("name_english", "")
                    country = lang_info.get("country_english", "")
                    return f"{name} ({country})" if country else name
        return None

    def _on_catalogs_loaded(self):
        self._is_initializing_combos = True
        try:
            self._populate_languages()
            self._select_initial_language()
        finally:
            self._is_initializing_combos = False

    def _populate_languages(self):
        self._is_populating_langs = True
        try:
            self.lang_liststore.clear()
            languages = set()
            
            if self.current_engine == "edge-tts":
                if self.edge_voices:
                    for v in self.edge_voices:
                        lang_name = v["FriendlyName"].split(" - ")[-1]
                        if lang_name:
                            languages.add(lang_name)
            else: # piper
                if self.piper_catalog:
                    for voice_code, info in self.piper_catalog.items():
                        lang_info = info.get("language", {})
                        name = lang_info.get("name_english", "")
                        country = lang_info.get("country_english", "")
                        lang_name = f"{name} ({country})" if country else name
                        if lang_name:
                            languages.add(lang_name)
                            
            sorted_langs = sorted(list(languages))
            for lang in sorted_langs:
                self.lang_liststore.append([lang])
        finally:
            self._is_populating_langs = False

    def _select_initial_language(self):
        initial_lang = self.get_language_name_for_voice(self.current_engine, self.current_voice)
        
        languages = []
        for row in self.lang_liststore:
            languages.append(row[0])
            
        fallback_lang = "Portuguese (Brazil)"
        if not initial_lang:
            if fallback_lang in languages:
                initial_lang = fallback_lang
            elif languages:
                initial_lang = languages[0]
                
        # Seleciona no dropdown de idiomas
        model = self.lang_filter_model
        treeiter = model.get_iter_first()
        while treeiter:
            if model[treeiter][0] == initial_lang:
                self.lang_combo.set_active_iter(treeiter)
                break
            treeiter = model.iter_next(treeiter)

    def lang_filter_visible_func(self, model, treeiter, data):
        if not self.filter_text:
            return True
        lang_name = str(model[treeiter][0]).lower() if model[treeiter][0] is not None else ""
        return self.filter_text in lang_name

    def _on_search_changed(self, entry):
        self.filter_text = entry.get_text().strip().lower()
        self.lang_filter_model.refilter()
        iter_first = self.lang_filter_model.get_iter_first()
        if iter_first:
            self.lang_combo.set_active_iter(iter_first)

    def _on_engine_changed(self, combo):
        if getattr(self, "_is_initializing_combos", False):
            return
        engine = combo.get_active_id()
        if not engine:
            return
        self.current_engine = engine
        save_settings(engine=engine)

        # Atualiza títulos das colunas dinamicamente
        cols = self.voice_treeview.get_columns()
        if len(cols) >= 4:
            cols[2].set_title(_("col_name") if engine == "edge-tts" else _("col_model"))
            cols[3].set_title(_("col_gender") if engine == "edge-tts" else _("col_quality"))

        self._populate_languages()
        self._select_initial_language()

    def _on_lang_combo_changed(self, combo):
        if getattr(self, "_is_populating_langs", False):
            return
        treeiter = combo.get_active_iter()
        if treeiter:
            selected_lang = self.lang_filter_model[treeiter][0]
            self.selected_lang = selected_lang
            self._populate_voices()

    def _populate_voices(self):
        self.voice_liststore.clear()
        if not self.selected_lang:
            self._update_buttons_state()
            return
            
        if self.current_engine == "edge-tts":
            if self.edge_voices:
                for v in self.edge_voices:
                    lang_name = v["FriendlyName"].split(" - ")[-1]
                    if lang_name == self.selected_lang:
                        code = v["ShortName"]
                        is_selected = (code == self.current_voice)
                        friendly_name = v["FriendlyName"].split(" - ")[0]
                        gender = v["Gender"]
                        
                        self.voice_liststore.append([
                            is_selected,
                            code,
                            friendly_name,
                            gender,
                            "Online",
                            True, # is_downloaded
                            "-",
                            "",
                            ""
                        ])
        else: # piper
            if self.piper_catalog:
                for voice_code, info in self.piper_catalog.items():
                    lang_info = info.get("language", {})
                    name = lang_info.get("name_english", "")
                    country = lang_info.get("country_english", "")
                    lang_name = f"{name} ({country})" if country else name
                    
                    if lang_name == self.selected_lang:
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
                        status_str = _("status_downloaded") if is_downloaded else _("status_not_downloaded")
                        size_str = f"{size_bytes / (1024*1024):.1f} MB"

                        onnx_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_rel}"
                        json_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{json_rel}"

                        is_selected = (voice_code == self.current_voice)

                        self.voice_liststore.append([
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
                        
        self._select_current_voice_in_treeview()
        self._update_buttons_state()

    def _select_current_voice_in_treeview(self):
        model = self.voice_liststore
        treeiter = model.get_iter_first()
        while treeiter:
            if model[treeiter][0]: # is_selected
                selection = self.voice_treeview.get_selection()
                selection.select_iter(treeiter)
                path = model.get_path(treeiter)
                self.voice_treeview.scroll_to_cell(path, None, True, 0.5, 0.0)
                break
            treeiter = model.iter_next(treeiter)

    def _on_voice_selection_changed(self, selection):
        if getattr(self, "_is_toggling_voice", False):
            return
        model, treeiter = selection.get_selected()
        if treeiter:
            path = model.get_path(treeiter)
            self._on_voice_radio_toggled(None, path.to_string())

    def _on_voice_radio_toggled(self, renderer, path_str):
        if getattr(self, "_is_toggling_voice", False):
            return
        self._is_toggling_voice = True
        try:
            path = Gtk.TreePath.new_from_string(path_str)
            child_iter = self.voice_liststore.get_iter(path)

            voice_code = self.voice_liststore[child_iter][1]

            # Reseta seleção antiga e define a nova
            child_iter_str = self.voice_liststore.get_path(child_iter).to_string()
            for row in self.voice_liststore:
                row_path = row.path.to_string()
                row[0] = (row_path == child_iter_str)

            self.current_voice = voice_code
            save_settings(voice=voice_code)

            self._update_buttons_state()
            self._update_current_selection_label()
        finally:
            self._is_toggling_voice = False

    def _update_current_selection_label(self):
        engine_display = "Edge TTS" if self.current_engine == "edge-tts" else "Piper TTS"
        text = _("active_voice", voice=self.current_voice, engine=engine_display)
        self.active_voice_lbl.set_markup(f"<b>{text}</b>")

    def _update_buttons_state(self):
        is_piper = (self.current_engine == "piper")
        if is_piper:
            self.piper_box.set_visible(True)
            selection = self.voice_treeview.get_selection()
            model, treeiter = selection.get_selected()
            if treeiter:
                voice_code = model[treeiter][1]
                status_str = model[treeiter][4]
                is_downloaded = model[treeiter][5]

                if self.is_downloading:
                    self.download_btn.set_sensitive(False)
                    self.remove_btn.set_sensitive(False)
                else:
                    self.download_btn.set_sensitive(not is_downloaded)
                    self.remove_btn.set_sensitive(is_downloaded)

                if is_downloaded:
                    self.info_label.set_markup(f"<span color='green'>{_('ready')}</span>")
                else:
                    self.info_label.set_markup(f"<span color='orange'>{_('not_downloaded')}</span>")
            else:
                self.download_btn.set_sensitive(False)
                self.remove_btn.set_sensitive(False)
                self.info_label.set_text("")
        else:
            self.piper_box.set_visible(False)
            self.download_btn.set_sensitive(False)
            self.remove_btn.set_sensitive(False)
            self.info_label.set_text("")

    def _on_theme_changed(self, combo):
        if getattr(self, "_is_initializing_combos", False):
            return
        theme = combo.get_active_id()
        if not theme:
            return
        self.current_theme = theme
        save_settings(theme=theme)
        self._apply_theme()

    def _apply_theme(self):
        theme_val = self.current_theme
        gtk_settings = Gtk.Settings.get_default()
        if not gtk_settings:
            return

        if theme_val == "dark":
            gtk_settings.set_property("gtk-application-prefer-dark-theme", True)
        else:
            gtk_settings.set_property("gtk-application-prefer-dark-theme", False)

    def _on_speed_scale_changed(self, scale):
        val = scale.get_value()
        self.current_speed = round(val, 2)
        self.speed_value_label.set_markup(f"<b>{self.current_speed:.2f}x</b>")
        save_settings(speed=self.current_speed)
        send_mpv_command(["set_property", "speed", self.current_speed])

    def _on_download_clicked(self, btn):
        if self.is_downloading:
            return

        selection = self.voice_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            return

        voice_code = model[treeiter][1]
        onnx_url = model[treeiter][7]
        json_url = model[treeiter][8]

        self.is_downloading = True
        self.download_btn.set_sensitive(False)
        self.remove_btn.set_sensitive(False)
        self.theme_combo.set_sensitive(False)
        self.engine_combo.set_sensitive(False)
        self.lang_combo.set_sensitive(False)
        self.voice_treeview.set_sensitive(False)
        self.search_entry.set_sensitive(False)

        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text(_("start_download"))

        self.download_thread = threading.Thread(
            target=self._download_voice_thread,
            args=(voice_code, onnx_url, json_url),
            daemon=True
        )
        self.download_thread.start()

    def _download_voice_thread(self, voice_code, onnx_url, json_url):
        dest_onnx = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
        dest_json = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx.json")

        try:
            os.makedirs(PIPER_VOICES_DIR, exist_ok=True)
            GLib.idle_add(self.progress_bar.set_text, _("down_settings"))
            urllib.request.urlretrieve(json_url, dest_json)
            GLib.idle_add(self.progress_bar.set_fraction, 0.05)

            GLib.idle_add(self.progress_bar.set_text, _("down_model", voice=voice_code))

            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = 0.05 + (downloaded / total_size) * 0.90
                    percent = min(0.99, percent)
                    GLib.idle_add(self.progress_bar.set_fraction, percent)
                    txt = _("down_progress", percent=int(percent*100), size=f"{downloaded / (1024*1024):.1f}")
                    GLib.idle_add(self.progress_bar.set_text, txt)

            urllib.request.urlretrieve(onnx_url, dest_onnx, reporthook=report_hook)

            GLib.idle_add(self.progress_bar.set_fraction, 1.0)
            GLib.idle_add(self.progress_bar.set_text, _("down_finished"))

            def on_success():
                self.is_downloading = False
                self.progress_bar.set_visible(False)
                self.theme_combo.set_sensitive(True)
                self.engine_combo.set_sensitive(True)
                self.lang_combo.set_sensitive(True)
                self.voice_treeview.set_sensitive(True)
                self.search_entry.set_sensitive(True)

                save_settings(voice=voice_code, engine="piper")
                self.current_voice = voice_code

                self._populate_voices()

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
                self.progress_bar.set_visible(False)
                self.theme_combo.set_sensitive(True)
                self.engine_combo.set_sensitive(True)
                self.lang_combo.set_sensitive(True)
                self.voice_treeview.set_sensitive(True)
                self.search_entry.set_sensitive(True)
                self._update_buttons_state()

                err_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("err_download", error=""),
                )
                err_dialog.format_secondary_text(err_msg)
                err_dialog.connect("response", lambda d, r: d.destroy())
                err_dialog.present()

            GLib.idle_add(on_error, str(e))

    def _on_remove_clicked(self, btn):
        selection = self.voice_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            return

        voice_code = model[treeiter][1]
        dest_onnx = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
        dest_json = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx.json")

        confirm = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("confirm_title"),
        )
        confirm.format_secondary_text(_("confirm_text", voice=voice_code))

        def on_confirm_response(dialog, response):
            dialog.destroy()
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
                                text=_("err_remove", error=""),
                            )
                            err_dialog.format_secondary_text(str(e))
                            err_dialog.connect("response", lambda d, r: d.destroy())
                            err_dialog.present()
                            return
                self._populate_voices()

        confirm.connect("response", on_confirm_response)
        confirm.present()

    def _on_close_clicked(self, btn):
        self.close()

# ============================================================================
# Application
# ============================================================================

class ConfigApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.narro.ConfigDialog")

    def do_activate(self):
        win = ConfigWindow(self)
        win.present()


def main():
    app = ConfigApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
