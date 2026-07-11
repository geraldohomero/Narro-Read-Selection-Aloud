#!/usr/bin/env python3
"""
Narro-RSA — Janela Principal GTK 4 unificada com páginas Stack
"""

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

Adw.init()

from narro_rsa.clipboard import get_clipboard_text
from narro_rsa.constants import (
    LOCKFILE,
    TMP_TEXT_FILE,
    LAST_READ_FILE,
    DEFAULT_VOICE_EDGE,
    DEFAULT_VOICE_PIPER,
    SPEED_DEFAULT,
)
from narro_rsa.settings import load_settings, save_settings
from narro_rsa.mpv_control import kill_mpv, send_mpv_command
from narro_rsa.tts_engine import EngineType, TTSRequest, generate_audio
from narro_rsa.subprocess_helper import popen_on_host, check_pid_active, check_and_start_daemon
from narro_rsa.translations import _

from narro_rsa.reader_page import ReaderPage
from narro_rsa.settings_page import SettingsPage


# ============================================================================
# Janela Principal
# ============================================================================

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("title"))
        self.set_default_size(550, 480)

        # Garante o daemon rodando
        check_and_start_daemon()

        self._apply_css()

        # StyleManager setup
        self.style_manager = Adw.StyleManager.get_default()
        self._apply_theme_from_settings()

        # Layout usando ToolbarView
        self.toolbar_view = Adw.ToolbarView()

        # Configuração da HeaderBar (Libadwaita HeaderBar)
        self.header_bar = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header_bar)

        self.header_title = Adw.WindowTitle()
        self.header_title.set_title(_("title"))
        self.header_bar.set_title_widget(self.header_title)

        # Botão Hambúrguer na HeaderBar (inicialmente visível)
        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.header_bar.pack_end(self.menu_btn)

        popover = Gtk.Popover()
        self.menu_btn.set_popover(popover)

        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        popover_box.set_margin_start(8)
        popover_box.set_margin_end(8)
        popover_box.set_margin_top(8)
        popover_box.set_margin_bottom(8)
        popover.set_child(popover_box)

        settings_menu_btn = Gtk.Button(label=_("settings"))
        settings_menu_btn.set_has_frame(False)
        settings_menu_btn.set_halign(Gtk.Align.START)
        settings_menu_btn.connect("clicked", lambda x: (popover.popdown(), self.show_settings_page()))
        popover_box.append(settings_menu_btn)

        about_menu_btn = Gtk.Button(label=_("about"))
        about_menu_btn.set_has_frame(False)
        about_menu_btn.set_halign(Gtk.Align.START)
        about_menu_btn.connect("clicked", lambda x: (popover.popdown(), self.show_about_dialog()))
        popover_box.append(about_menu_btn)

        # Inicializa a página do leitor e define como conteúdo do ToolbarView
        self.reader_page = ReaderPage(self)
        self.toolbar_view.set_content(self.reader_page)
        self.set_content(self.toolbar_view)

        self.connect("notify::is-active", self._on_window_active)

    def _apply_css(self):
        css_provider = Gtk.CssProvider()
        css_code = """
            .text-area-frame {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: @theme_base_color;
            }
            .active-voice-badge {
                border: 1px solid @theme_borders;
                border-radius: 8px;
                background-color: alpha(@theme_selected_bg_color, 0.1);
                padding: 10px 14px;
                font-size: 10.5pt;
            }
            scale {
                margin: 4px 0;
            }
        """
        css_provider.load_from_string(css_code)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _apply_theme_from_settings(self):
        settings = load_settings()
        theme_val = settings.get("theme", "light")
        if theme_val == "dark":
            self.style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        elif theme_val == "light":
            self.style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
        else:
            self.style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def show_settings_page(self):
        self.settings_page = SettingsPage(self)
        self.settings_page.present()

    def show_about_dialog(self):
        about = Adw.AboutWindow()
        about.set_transient_for(self)
        about.set_modal(True)
        about.set_developer_name("Geraldo Homero")
        about.set_version("1.1.0")
        about.set_comments(_("about_comments"))
        about.set_copyright("Copyright © 2026 Geraldo Homero")
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_application_icon("com.github.geraldohomero.NarroRsa")
        about.present()

    def update_ui_texts(self):
        """Atualiza todas as strings de tradução da aplicação quando a linguagem muda."""
        self.header_title.set_title(_("title"))
        
        # Reconstrói popover do hambúrguer
        popover = self.menu_btn.get_popover()
        if popover:
            popover_box = popover.get_child()
            if popover_box:
                child = popover_box.get_first_child()
                while child:
                    next_child = child.get_next_sibling()
                    popover_box.remove(child)
                    child = next_child
                
                settings_menu_btn = Gtk.Button(label=_("settings"))
                settings_menu_btn.set_has_frame(False)
                settings_menu_btn.set_halign(Gtk.Align.START)
                settings_menu_btn.connect("clicked", lambda x: (popover.popdown(), self.show_settings_page()))
                popover_box.append(settings_menu_btn)

                about_menu_btn = Gtk.Button(label=_("about"))
                about_menu_btn.set_has_frame(False)
                about_menu_btn.set_halign(Gtk.Align.START)
                about_menu_btn.connect("clicked", lambda x: (popover.popdown(), self.show_about_dialog()))
                popover_box.append(about_menu_btn)
        
        # Repassa atualizações para os filhos
        self.reader_page.reload_ui_settings()

    def _load_and_update_settings(self):
        self._apply_theme_from_settings()
        self.reader_page.reload_ui_settings()

    def _on_window_active(self, window, pspec):
        if window.get_property("is-active"):
            self._load_and_update_settings()
            
            # Sincroniza com áudio ou clipboard ativo se necessário
            if hasattr(self.reader_page, "text_view"):
                from narro_rsa.constants import MPV_SOCKET
                buffer = self.reader_page.text_view.get_buffer()
                start, end = buffer.get_bounds()
                current_text = buffer.get_text(start, end, True).strip()
                
                if os.path.exists(MPV_SOCKET):
                    try:
                        if os.path.exists(LAST_READ_FILE):
                            with open(LAST_READ_FILE, "r", encoding="utf-8") as fh:
                                active_text = fh.read().strip()
                            if active_text and active_text != current_text:
                                buffer.set_text(active_text)
                                return
                    except OSError:
                        pass

                if current_text == _("no_text") or not current_text:
                    initial_text = ""
                    if os.path.exists(LAST_READ_FILE):
                        try:
                            with open(LAST_READ_FILE, "r", encoding="utf-8") as fh:
                                initial_text = fh.read().strip()
                        except OSError:
                            pass
                    if not initial_text:
                        initial_text = get_clipboard_text()
                    if initial_text:
                        buffer.set_text(initial_text)


# ============================================================================
# Aplicação GTK
# ============================================================================

class NarroApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.geraldohomero.NarroRsa")

    def do_activate(self):
        win = MainWindow(self)
        win.present()
        if "--settings" in sys.argv:
            win.show_settings_page()


def configure_gnome_shortcuts():
    """Configura os atalhos de teclado customizados no GNOME via gsettings."""
    import re
    
    def run_gsettings(args):
        if os.path.exists("/.flatpak-info"):
            cmd = ["flatpak-spawn", "--host", "gsettings"] + args
        else:
            cmd = ["gsettings"] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            return res.stdout.strip()
        except OSError:
            return ""

    bindings_str = run_gsettings(["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"])
    if bindings_str == "@as []" or not bindings_str:
        current_bindings = []
    else:
        current_bindings = re.findall(r"'(.*?)'", bindings_str)

    desired_shortcuts = [
        {
            "name": "Leitor TTS (Narro) [Flatpak]",
            "command": "flatpak run com.github.geraldohomero.NarroRsa --play",
            "binding": "<Super><Alt>l"
        },
        {
            "name": "Leitor TTS (Narro) [Ctrl+\\] [Flatpak]",
            "command": "flatpak run com.github.geraldohomero.NarroRsa --primary",
            "binding": "<Primary>backslash"
        },
        {
            "name": "Pausar leitura TTS (Narro) [Flatpak]",
            "command": "flatpak run com.github.geraldohomero.NarroRsa --pause",
            "binding": "<Super><Alt>j"
        },
        {
            "name": "Parar leitura TTS (Narro) [Flatpak]",
            "command": "flatpak run com.github.geraldohomero.NarroRsa --stop",
            "binding": "<Super><Alt>k"
        }
    ]

    new_bindings = []
    for path in current_bindings:
        schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
        name = run_gsettings(["get", schema, "name"])
        if "Narro" in name:
            continue
        new_bindings.append(path)

    for shortcut in desired_shortcuts:
        idx = 0
        while True:
            path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{idx}/"
            if path not in new_bindings:
                break
            idx += 1
        
        new_bindings.append(path)
        schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
        run_gsettings(["set", schema, "name", shortcut["name"]])
        run_gsettings(["set", schema, "command", shortcut["command"]])
        run_gsettings(["set", schema, "binding", shortcut["binding"]])

    array_val = "[" + ", ".join([f"'{p}'" for p in new_bindings]) + "]"
    run_gsettings(["set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", array_val])
    print("Atalhos do GNOME configurados com sucesso para usar o Flatpak!")


def main():
    if "--setup-shortcuts" in sys.argv:
        configure_gnome_shortcuts()
        sys.exit(0)

    if "--play" in sys.argv or "--primary" in sys.argv:
        check_and_start_daemon()
        use_primary = "--primary" in sys.argv
        text = get_clipboard_text(primary=use_primary)
        if not text:
            sys.exit(0)
            
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
            except OSError:
                sys.exit(0)
                
            if os.path.exists("/.flatpak-info"):
                subprocess.run(["flatpak-spawn", "--host", "kill", "-USR1", str(pid)])
            else:
                os.kill(pid, signal.SIGUSR1)
            sys.exit(0)
            
        try:
            with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass

        settings = load_settings()
        engine = settings.get("engine", "edge-tts")
        default_voice = DEFAULT_VOICE_EDGE if engine == "edge-tts" else DEFAULT_VOICE_PIPER
        voice = settings.get("voice") or default_voice
        speed = float(settings.get("speed", SPEED_DEFAULT))
        
        kill_mpv()
        try:
            from narro_rsa.constants import MPV_SOCKET
            try:
                os.unlink(MPV_SOCKET)
            except OSError:
                pass
                
            engine_type = EngineType.PIPER if engine == "piper" else EngineType.EDGE_TTS
            request = TTSRequest(text=text, voice=voice, engine=engine_type, speed=speed)
            result = generate_audio(request)
            if result.success:
                proc = popen_on_host([
                    "mpv",
                    "--no-video",
                    "--really-quiet",
                    f"--input-ipc-server={MPV_SOCKET}",
                    f"--speed={speed}",
                    result.audio_path
                ])
                proc.wait()
        except Exception as e:
            print(f"Erro na leitura em background: {e}")
        sys.exit(0)

    if "--pause" in sys.argv:
        send_mpv_command(["cycle", "pause"])
        sys.exit(0)
        
    if "--stop" in sys.argv:
        kill_mpv()
        sys.exit(0)

    try:
        configure_gnome_shortcuts()
    except Exception as e:
        print(f"Erro configurando atalhos: {e}")

    app = NarroApp()
    sys.exit(app.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
