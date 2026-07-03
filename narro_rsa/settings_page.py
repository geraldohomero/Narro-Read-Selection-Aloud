"""Settings page component for Narro-RSA."""

from __future__ import annotations
import json
import os
import sys
import threading
import urllib.request
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from narro_rsa.constants import CONFIG_DIR, EDGE_VOICES_CACHE, PIPER_VOICES_DIR
from narro_rsa.mpv_control import send_mpv_command
from narro_rsa.settings import load_settings, save_settings
from narro_rsa.translations import _

# ============================================================================
# Helpers de Cache de Vozes
# ============================================================================

def load_edge_voices_cache() -> list[dict] | None:
    """Carrega o cache local de vozes Edge-TTS."""
    try:
        if os.path.exists(EDGE_VOICES_CACHE):
            with open(EDGE_VOICES_CACHE, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except (json.JSONDecodeError, OSError):
        pass
    return None

def save_edge_voices_cache(voices: list[dict]) -> None:
    """Salva o cache local de vozes Edge-TTS."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(EDGE_VOICES_CACHE, "w", encoding="utf-8") as fh:
            json.dump(voices, fh, ensure_ascii=False)
    except OSError:
        pass

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


class SettingsPage(Gtk.Box):
    def __init__(self, main_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_window = main_window

        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(16)
        self.set_margin_bottom(16)

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
        self._build_ui()

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
        self.lang_combo.connect("changed", self._on_lang_combo_changed)

        # Conecta seleção do painel de vozes
        voice_selection = self.voice_treeview.get_selection()
        voice_selection.set_mode(Gtk.SelectionMode.SINGLE)
        voice_selection.connect("changed", self._on_voice_selection_changed)

        # Aplica o tema imediatamente
        self._apply_theme()

        # Inicia carregamento assíncrono dos catálogos
        threading.Thread(target=self._load_catalogs_thread, daemon=True).start()

    def _apply_css(self):
        css_provider = Gtk.CssProvider()
        css_code = """
            .active-voice-frame {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: alpha(@theme_selected_bg_color, 0.1);
                padding: 12px;
            }
            .list-frame {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: @theme_base_color;
            }
        """
        css_provider.load_from_string(css_code)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        # ── Seção de Voz Ativa no Topo ──
        active_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        active_box.add_css_class("active-voice-frame")
        self.active_voice_lbl = Gtk.Label()
        self.active_voice_lbl.set_halign(Gtk.Align.START)
        active_box.append(self.active_voice_lbl)
        self.append(active_box)

        # Painel Superior de Configurações (Grid)
        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(10)
        grid.set_hexpand(True)
        self.append(grid)

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

        # 6. Idioma da Interface (UI Language)
        self.ui_lang_label = Gtk.Label()
        self.ui_lang_label.set_halign(Gtk.Align.START)
        grid.attach(self.ui_lang_label, 0, 3, 1, 1)

        self.ui_lang_combo = Gtk.ComboBoxText()
        self.ui_lang_combo.append("en", "English")
        self.ui_lang_combo.append("pt_BR", "Português (Brasil)")
        self.ui_lang_combo.append("zh_CN", "简体中文")
        self.ui_lang_combo.set_hexpand(True)
        self.ui_lang_combo.set_active_id(self.current_ui_lang)
        self.ui_lang_combo.connect("changed", self._on_ui_lang_changed)
        grid.attach(self.ui_lang_combo, 1, 3, 3, 1)

        # Separador / Título para vozes
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        self.voices_header_label = Gtk.Label()
        self.voices_header_label.set_halign(Gtk.Align.START)
        self.append(self.voices_header_label)

        # ScrolledWindow + TreeView de Vozes
        self.voice_scrolled = Gtk.ScrolledWindow()
        self.voice_scrolled.set_vexpand(True)
        self.voice_scrolled.set_min_content_height(180)
        self.voice_scrolled.add_css_class("list-frame")
        self.append(self.voice_scrolled)

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

        col_code = Gtk.TreeViewColumn("", renderer_text, text=1)
        col_code.set_expand(False)
        col_code.set_resizable(True)
        self.voice_treeview.append_column(col_code)

        col_name = Gtk.TreeViewColumn("", renderer_text, text=2)
        col_name.set_expand(True)
        col_name.set_resizable(True)
        self.voice_treeview.append_column(col_name)

        col_gender = Gtk.TreeViewColumn("", renderer_text, text=3)
        col_gender.set_expand(False)
        col_gender.set_resizable(True)
        self.voice_treeview.append_column(col_gender)

        col_status = Gtk.TreeViewColumn("", renderer_text, text=4)
        col_status.set_expand(False)
        col_status.set_resizable(True)
        self.voice_treeview.append_column(col_status)

        col_size = Gtk.TreeViewColumn("", renderer_text, text=6)
        col_size.set_expand(False)
        col_size.set_resizable(True)
        self.voice_treeview.append_column(col_size)

        # Model: Col 0: selected, Col 1: code, Col 2: name, Col 3: gender/quality, Col 4: status, Col 5: is_downloaded, Col 6: size, Col 7: onnx_url, Col 8: json_url
        self.voice_liststore = Gtk.ListStore(bool, str, str, str, str, bool, str, str, str)
        self.voice_treeview.set_model(self.voice_liststore)

        # Painel do Piper
        self.piper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.append(self.piper_box)

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

    def _update_ui_texts(self):
        """Atualiza dinamicamente as strings da UI conforme o idioma da sessão."""
        self.engine_label.set_text(_("engine"))
        self.theme_label.set_text(_("theme"))
        self.search_label.set_text(_("search_label"))
        self.lang_label.set_text(_("lang"))
        self.speed_title.set_text(_("speed"))
        self.ui_lang_label.set_text(_("ui_lang_title"))

        # Placeholder do campo de busca
        self.search_entry.set_placeholder_text(_("search_placeholder"))

        # Repopula combo de temas para aplicar as traduções locais
        self._repopulate_theme_combo()

        # Cabeçalho da tabela de vozes
        self.voices_header_label.set_markup(f"<b>{_('voices')}</b>")

        # Nomes das colunas da tabela de vozes
        cols = self.voice_treeview.get_columns()
        if len(cols) >= 6:
            cols[1].set_title(_("col_code"))
            cols[2].set_title(_("col_name"))
            cols[3].set_title(_("col_gender"))
            cols[4].set_title(_("col_status"))
            cols[5].set_title(_("col_size"))

        # Botões de download do Piper
        self.download_btn.set_label(_("download"))
        self.remove_btn.set_label(_("remove"))

        # Atualiza a velocidade
        self.speed_value_label.set_markup(f"<b>{self.current_speed:.2f}x</b>")

        # Atualiza rótulo de voz ativa
        self._update_current_selection_label()

    def _repopulate_theme_combo(self):
        self.theme_combo.remove_all()
        self.theme_combo.append("light", _("light"))
        self.theme_combo.append("dark", _("dark"))
        self.theme_combo.set_active_id(self.current_theme)

    def _load_catalogs_thread(self):
        """Método em segundo plano para obter as listas de vozes da Microsoft e do Piper."""
        # 1. Tenta baixar o catálogo do Edge TTS via urllib
        self.edge_voices = load_edge_voices_cache()
        if not self.edge_voices:
            try:
                # Faz requisição direta utilizando urllib para contornar sandboxing
                url = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list"
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read().decode("utf-8")
                    self.edge_voices = json.loads(data)
                    save_edge_voices_cache(self.edge_voices)
            except Exception as e:
                print(f"Erro ao baixar vozes do Edge: {e}")
                self.edge_voices = FALLBACK_EDGE_VOICES

        # 2. Tenta baixar o catálogo do Piper
        piper_catalog_path = os.path.join(CONFIG_DIR, "piper_voices.json")
        try:
            if not os.path.exists(piper_catalog_path):
                url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read().decode("utf-8")
                    with open(piper_catalog_path, "w", encoding="utf-8") as fh:
                        fh.write(data)
            
            with open(piper_catalog_path, "r", encoding="utf-8") as fh:
                self.piper_catalog = json.load(fh)
        except Exception as e:
            print(f"Erro no catálogo do Piper: {e}")
            self.piper_catalog = {}

        # Notifica o thread do GTK de que os dados estão prontos
        GLib.idle_add(self._on_catalogs_loaded)

    def get_language_name_for_voice(self, engine, voice_code):
        """Retorna o nome do idioma legível por humanos a partir de um código de voz."""
        if engine == "edge-tts":
            # Ex: pt-BR-AntonioNeural -> pt-BR
            parts = voice_code.split("-")
            if len(parts) >= 2:
                return f"{parts[0]}-{parts[1]}"
            return voice_code
        else:
            # Ex: pt_BR-cadu-medium -> pt_BR
            parts = voice_code.split("-")
            if len(parts) >= 1:
                return parts[0]
            return voice_code

    def _on_catalogs_loaded(self):
        """Callback após download bem sucedido das vozes."""
        self._populate_languages()
        self._select_initial_language()
        self._populate_voices()
        self._select_current_voice_in_treeview()

    def _populate_languages(self):
        """Popula o dropdown de idiomas de acordo com o mecanismo (Engine)."""
        self.lang_liststore.clear()
        langs = set()

        if self.current_engine == "edge-tts":
            if self.edge_voices:
                for v in self.edge_voices:
                    locale = v.get("Locale", "")
                    if locale:
                        langs.add(locale)
        else:
            if self.piper_catalog:
                for voice_key, v_info in self.piper_catalog.items():
                    lang_code = v_info.get("language", {}).get("code", "")
                    if lang_code:
                        langs.add(lang_code)

        for l in sorted(list(langs)):
            self.lang_liststore.append([l])

    def _select_initial_language(self):
        """Tenta selecionar o idioma correto de forma proativa."""
        # Se houver uma voz ativa, escolhe o idioma correspondente a ela
        target_lang = None
        if self.current_voice:
            target_lang = self.get_language_name_for_voice(self.current_engine, self.current_voice)

        if not target_lang:
            target_lang = "pt-BR" if self.current_engine == "edge-tts" else "pt_BR"

        # Procura no model do filtro
        treeiter = self.lang_filter_model.get_iter_first()
        found = False
        while treeiter:
            val = self.lang_filter_model.get_value(treeiter, 0)
            if val == target_lang:
                self.lang_combo.set_active_iter(treeiter)
                self.selected_lang = val
                found = True
                break
            treeiter = self.lang_filter_model.iter_next(treeiter)

        if not found:
            # Seleciona o primeiro elemento se não encontrou o idioma padrão
            first_iter = self.lang_filter_model.get_iter_first()
            if first_iter:
                self.lang_combo.set_active_iter(first_iter)
                self.selected_lang = self.lang_filter_model.get_value(first_iter, 0)

    def lang_filter_visible_func(self, model, treeiter, data):
        """Filtro de busca para a caixa de seleção do idioma."""
        if not self.filter_text:
            return True
        val = model.get_value(treeiter, 0)
        return self.filter_text.lower() in val.lower()

    def _on_search_changed(self, entry):
        self.filter_text = entry.get_text()
        self.lang_filter_model.refilter()
        # Se o idioma atual sumir, seleciona o primeiro visível
        active_iter = self.lang_combo.get_active_iter()
        if not active_iter:
            first_iter = self.lang_filter_model.get_iter_first()
            if first_iter:
                self.lang_combo.set_active_iter(first_iter)

    def _on_engine_changed(self, combo):
        if self._is_initializing_combos:
            return
        new_engine = combo.get_active_id()
        if not new_engine or new_engine == self.current_engine:
            return

        self.current_engine = new_engine
        save_settings(engine=new_engine)

        # Limpa voz atual para evitar inconsistências cruzadas
        self.current_voice = None
        save_settings(voice=None)

        # Repopula
        self._populate_languages()
        self._select_initial_language()
        self._populate_voices()
        self._update_buttons_state()
        self._update_current_selection_label()

    def _on_lang_combo_changed(self, combo):
        treeiter = combo.get_active_iter()
        if treeiter:
            self.selected_lang = self.lang_filter_model.get_value(treeiter, 0)
            self._populate_voices()
            self._select_current_voice_in_treeview()
            self._update_buttons_state()

    def _populate_voices(self):
        """Preenche o ListStore das vozes aplicando filtros de idioma."""
        self.voice_liststore.clear()
        if not self.selected_lang:
            return

        if self.current_engine == "edge-tts":
            # Oculta painel de download
            self.piper_box.set_visible(False)
            if not self.edge_voices:
                return

            for v in self.edge_voices:
                locale = v.get("Locale", "")
                if locale == self.selected_lang:
                    code = v.get("ShortName", "")
                    name = v.get("FriendlyName", "").split(" - ")[0]
                    # Limpa nome redundante
                    name = name.replace("Microsoft ", "").replace(" Online (Natural)", "")
                    gender = v.get("Gender", "Unknown")
                    is_active = (code == self.current_voice)
                    self.voice_liststore.append([
                        is_active,  # Radio ativo
                        code,       # Código da voz
                        name,       # Nome amigável
                        gender,     # Gênero
                        _("status_downloaded"),  # Status (sempre ativo)
                        True,       # Baixado (sempre True para nuvem)
                        "N/A",      # Tamanho
                        "",         # ONNX Url
                        ""          # JSON Url
                    ])
        else:
            # Mostra painel de download
            self.piper_box.set_visible(True)
            if not self.piper_catalog:
                return

            for voice_key, v_info in self.piper_catalog.items():
                lang_code = v_info.get("language", {}).get("code", "")
                if lang_code == self.selected_lang:
                    code = voice_key
                    # Limpa o código para exibição amigável
                    # pt_BR-cadu-medium -> Cadu (Medium)
                    parts = code.split("-")
                    if len(parts) >= 2:
                        name = parts[1].capitalize()
                        quality = f"({parts[2].capitalize()})" if len(parts) > 2 else ""
                        name_display = f"{name} {quality}".strip()
                    else:
                        name_display = code

                    gender = v_info.get("language", {}).get("family", "Unknown")
                    if "gender" in v_info:
                        gender = v_info["gender"].capitalize()

                    # Verifica arquivos locais
                    onnx_path = os.path.join(PIPER_VOICES_DIR, f"{code}.onnx")
                    is_downloaded = os.path.exists(onnx_path)
                    status_str = _("status_downloaded") if is_downloaded else _("status_not_downloaded")

                    # Tamanho do download
                    total_bytes = 0
                    files_dict = v_info.get("files", {})
                    for filepath, f_meta in files_dict.items():
                        total_bytes += f_meta.get("size_bytes", 0)
                    size_mb = f"{total_bytes / (1024*1024):.1f} MB" if total_bytes > 0 else "Unknown"

                    # Monta urls de download
                    onnx_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{code}.onnx"
                    json_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{code}.onnx.json"

                    is_active = (code == self.current_voice)
                    self.voice_liststore.append([
                        is_active,       # Radio ativo
                        code,            # Código da voz
                        name_display,    # Nome amigável
                        gender,          # Gênero
                        status_str,      # Status local
                        is_downloaded,   # Bool baixado
                        size_mb,         # Tamanho
                        onnx_url,        # URL ONNX
                        json_url         # URL JSON
                    ])

    def _select_current_voice_in_treeview(self):
        """Seleciona graficamente a voz ativa atual no TreeView."""
        if not self.current_voice:
            return

        selection = self.voice_treeview.get_selection()
        treeiter = self.voice_liststore.get_iter_first()
        while treeiter:
            code = self.voice_liststore.get_value(treeiter, 1)
            if code == self.current_voice:
                selection.select_iter(treeiter)
                # Garante que o botão de opção gráfica reflita
                self._on_voice_radio_toggled(None, self.voice_liststore.get_path(treeiter).to_string())
                break
            treeiter = self.voice_liststore.iter_next(treeiter)

    def _on_voice_selection_changed(self, selection):
        self._update_buttons_state()

    def _on_voice_radio_toggled(self, renderer, path_str):
        """Atualiza a voz ativa quando o botão de opção (Radio) é acionado na tabela."""
        path = Gtk.TreePath.new_from_string(path_str)
        treeiter = self.voice_liststore.get_iter(path)
        if not treeiter:
            return

        # Desmarca todos
        temp_iter = self.voice_liststore.get_iter_first()
        while temp_iter:
            self.voice_liststore.set_value(temp_iter, 0, False)
            temp_iter = self.voice_liststore.iter_next(temp_iter)

        # Marca o selecionado
        self.voice_liststore.set_value(treeiter, 0, True)

        # Salva configuração
        code = self.voice_liststore.get_value(treeiter, 1)
        is_downloaded = self.voice_liststore.get_value(treeiter, 5)

        # Apenas ativa a voz no arquivo se ela estiver baixada (no caso do Piper)
        if self.current_engine == "edge-tts" or is_downloaded:
            self.current_voice = code
            save_settings(voice=code)

        self._update_current_selection_label()
        self._update_buttons_state()

        # Avisa a janela principal para atualizar o badge de voz ativa se necessário
        if hasattr(self.main_window, "_load_and_update_settings"):
            self.main_window._load_and_update_settings()

    def _update_current_selection_label(self):
        """Altera o indicador superior de voz configurada."""
        engine = "Online" if self.current_engine == "edge-tts" else "Offline"
        voice = self.current_voice or "None"
        self.active_voice_lbl.set_markup(_("active_voice", voice=voice, engine=engine))

    def _update_buttons_state(self):
        """Habilita/desabilita controles e mensagens de status do Piper."""
        if self.current_engine == "edge-tts":
            self.info_label.set_markup(_("online_ready"))
            return

        selection = self.voice_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            self.download_btn.set_sensitive(False)
            self.remove_btn.set_sensitive(False)
            self.info_label.set_text("")
            return

        code = model.get_value(treeiter, 1)
        is_downloaded = model.get_value(treeiter, 5)

        if self.is_downloading:
            self.download_btn.set_sensitive(False)
            self.remove_btn.set_sensitive(False)
            self.theme_combo.set_sensitive(False)
            self.engine_combo.set_sensitive(False)
            return

        self.theme_combo.set_sensitive(True)
        self.engine_combo.set_sensitive(True)

        if is_downloaded:
            self.download_btn.set_sensitive(False)
            self.remove_btn.set_sensitive(True)
            self.info_label.set_markup(f"<span foreground='green'><b>{_('ready')}</b></span>")
        else:
            self.download_btn.set_sensitive(True)
            self.remove_btn.set_sensitive(False)
            self.info_label.set_markup(f"<span foreground='orange'>{_('not_downloaded')}</span>")

    def _on_theme_changed(self, combo):
        theme = combo.get_active_id()
        if not theme:
            return
        self.current_theme = theme
        save_settings(theme=theme)
        self._apply_theme()

        # Avisa a janela principal do novo tema
        if hasattr(self.main_window, "_load_and_update_settings"):
            self.main_window._load_and_update_settings()

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

        # Avisa a janela principal do novo limite de velocidade
        if hasattr(self.main_window, "_load_and_update_settings"):
            self.main_window._load_and_update_settings()

    def _on_download_clicked(self, btn):
        if self.is_downloading:
            return

        selection = self.voice_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            return

        code = model.get_value(treeiter, 1)
        onnx_url = model.get_value(treeiter, 7)
        json_url = model.get_value(treeiter, 8)

        self.is_downloading = True
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self._update_buttons_state()

        # Inicia download em thread separada
        self.download_thread = threading.Thread(
            target=self._download_voice_thread,
            args=(code, onnx_url, json_url),
            daemon=True
        )
        self.download_thread.start()

    def _download_voice_thread(self, voice_code, onnx_url, json_url):
        os.makedirs(PIPER_VOICES_DIR, exist_ok=True)
        onnx_dest = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx")
        json_dest = os.path.join(PIPER_VOICES_DIR, f"{voice_code}.onnx.json")

        try:
            # Callback para atualizar a barra de progresso no loop de idle do GTK
            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    percent = min(percent, 100)
                    size_mb = f"{total_size / (1024*1024):.1f}"
                    GLib.idle_add(
                        self.progress_bar.set_fraction,
                        float(percent / 100.0)
                    )
                    GLib.idle_add(
                        self.info_label.set_markup,
                        _("down_progress", percent=percent, size=size_mb)
                    )

            GLib.idle_add(self.info_label.set_text, _("down_settings"))
            urllib.request.urlretrieve(json_url, json_dest)

            GLib.idle_add(self.info_label.set_text, _("down_model", voice=voice_code))
            urllib.request.urlretrieve(onnx_url, onnx_dest, report_hook)

            def on_success():
                self.is_downloading = False
                self.progress_bar.set_visible(False)
                # Define a voz como ativa após o download
                self.current_voice = voice_code
                save_settings(voice=voice_code)

                # Repopula para atualizar a coluna 'Status' de baixado
                self._populate_voices()
                self._select_current_voice_in_treeview()
                self._update_buttons_state()
                self._update_current_selection_label()

                # Notifica a janela principal
                if hasattr(self.main_window, "_load_and_update_settings"):
                    self.main_window._load_and_update_settings()

            GLib.idle_add(on_success)

        except Exception as e:
            def on_error(err_msg):
                self.is_downloading = False
                self.progress_bar.set_visible(False)
                self.info_label.set_markup(f"<span foreground='red'><b>{_('err_download', error=err_msg)}</b></span>")
                self._update_buttons_state()

            GLib.idle_add(on_error, str(e))

    def _on_remove_clicked(self, btn):
        selection = self.voice_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            return

        code = model.get_value(treeiter, 1)

        # Janela de diálogo nativa GTK4 para confirmação
        dialog = Gtk.MessageDialog(
            transient_for=self.main_window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("confirm_title")
        )
        dialog.set_informative_text(_("confirm_text", voice=code))

        def on_confirm_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                try:
                    onnx_dest = os.path.join(PIPER_VOICES_DIR, f"{code}.onnx")
                    json_dest = os.path.join(PIPER_VOICES_DIR, f"{code}.onnx.json")
                    if os.path.exists(onnx_dest):
                        os.unlink(onnx_dest)
                    if os.path.exists(json_dest):
                        os.unlink(json_dest)

                    if self.current_voice == code:
                        self.current_voice = None
                        save_settings(voice=None)

                    self._populate_voices()
                    self._update_buttons_state()
                    self._update_current_selection_label()

                    # Notifica a janela principal
                    if hasattr(self.main_window, "_load_and_update_settings"):
                        self.main_window._load_and_update_settings()

                except Exception as e:
                    self.info_label.set_markup(f"<span foreground='red'><b>{_('err_remove', error=str(e))}</b></span>")
            
            dialog.destroy()

        dialog.connect("response", on_confirm_response)
        dialog.present()

    def _on_ui_lang_changed(self, combo):
        lang_code = combo.get_active_id()
        if not lang_code or lang_code == self.current_ui_lang:
            return
        self.current_ui_lang = lang_code
        save_settings(ui_lang=lang_code)
        
        # Recarrega traduções da própria página
        self._update_ui_texts()
        
        # Notifica a janela principal para atualizar todos os textos e sub-páginas
        if hasattr(self.main_window, "update_ui_texts"):
            self.main_window.update_ui_texts()
