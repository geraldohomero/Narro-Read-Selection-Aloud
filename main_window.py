#!/usr/bin/env python3
"""
Narro-RSA — Janela Principal GTK 4 unificada com páginas Stack
"""

from __future__ import annotations
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
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
    DEFAULT_ENGINE,
    DEFAULT_VOICE_EDGE,
    DEFAULT_VOICE_PIPER,
    SPEED_DEFAULT,
    get_default_piper_voice,
)
from narro_rsa.settings import load_settings, save_settings
from narro_rsa.mpv_control import kill_mpv, send_mpv_command, is_mpv_active, play_chunked_tts
from narro_rsa.tts_engine import EngineType, TTSRequest, generate_audio
from narro_rsa.subprocess_helper import popen_command, check_pid_active, check_and_start_daemon
from narro_rsa.translations import _
from narro_rsa.notifications import send_notification, preview_text

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

        # Navegação hierárquica usando NavigationView
        self.navigation_view = Adw.NavigationView()

        # Página do leitor (página raiz de navegação)
        self.reader_nav_page = Adw.NavigationPage(title=_("title"), tag="reader")

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
        self.reader_nav_page.set_child(self.toolbar_view)
        self.navigation_view.add(self.reader_nav_page)

        # Inicializa a página de configurações integrada
        self.settings_page = SettingsPage(self)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.navigation_view)
        self.set_content(self.toast_overlay)

        self._is_handling_active = False
        self._last_active_time = 0.0

        self.connect("notify::is-active", self._on_window_active)

        # Verifica se os atalhos do GNOME estão configurados, configurando em background se necessário
        def _setup_shortcuts_async():
            changed = configure_gnome_shortcuts(force=False)
            if changed:
                GLib.idle_add(lambda: self.show_toast(_("shortcuts_configured_toast"), timeout=4))

        threading.Thread(target=_setup_shortcuts_async, daemon=True).start()

    def show_toast(self, message: str, timeout: int = 3):
        """Exibe uma notificação flutuante (toast) nativa do GNOME/Adwaita."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        target_overlay = getattr(self, "toast_overlay", None)
        if hasattr(self, "navigation_view"):
            page = self.navigation_view.get_visible_page()
            if page and getattr(page, "get_tag", lambda: "")() == "settings":
                target_overlay = getattr(self, "toast_overlay", None)
            elif hasattr(self, "reader_page") and hasattr(self.reader_page, "toast_overlay"):
                target_overlay = self.reader_page.toast_overlay
        elif hasattr(self, "reader_page") and hasattr(self.reader_page, "toast_overlay"):
            target_overlay = self.reader_page.toast_overlay

        if target_overlay:
            target_overlay.add_toast(toast)

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
        page = self.navigation_view.find_page("settings")
        if not page:
            if not hasattr(self, "settings_page") or self.settings_page is None:
                self.settings_page = SettingsPage(self)
            self.navigation_view.push(self.settings_page)
        elif self.navigation_view.get_visible_page() != page:
            self.navigation_view.push_by_tag("settings")

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
        if hasattr(self, "reader_nav_page"):
            self.reader_nav_page.set_title(_("title"))
        
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
        if hasattr(self, "settings_page") and self.settings_page is not None:
            self.settings_page.update_ui_texts()

    def _load_and_update_settings(self):
        self._apply_theme_from_settings()
        self.reader_page.reload_ui_settings()

    def _on_window_active(self, window, pspec):
        if not window.get_property("is-active"):
            return

        # Proteção contra reentrância de eventos
        if getattr(self, "_is_handling_active", False):
            return
        self._is_handling_active = True

        try:
            now = time.time()
            # Throttling / debounce de 0.5s para evitar storms de eventos do compositor Wayland
            if now - getattr(self, "_last_active_time", 0.0) < 0.5:
                return
            self._last_active_time = now

            self._load_and_update_settings()

            # Sincroniza com áudio ou clipboard ativo se necessário
            if hasattr(self, "reader_page") and hasattr(self.reader_page, "text_view"):
                buffer = self.reader_page.text_view.get_buffer()
                start, end = buffer.get_bounds()
                current_text = buffer.get_text(start, end, True).strip()

                # Se o áudio está tocando e há texto recente ativo, sincroniza
                if is_mpv_active() and os.path.exists(LAST_READ_FILE):
                    try:
                        with open(LAST_READ_FILE, "r", encoding="utf-8") as fh:
                            active_text = fh.read().strip()
                        if active_text and active_text != current_text:
                            buffer.set_text(active_text)
                            return
                    except OSError:
                        pass

                # Se o campo está vazio ou com o aviso, carrega assincronamente via GDK (sem subprocessos)
                if current_text == _("no_text") or not current_text:
                    if hasattr(self.reader_page, "load_clipboard_async"):
                        self.reader_page.load_clipboard_async()
        finally:
            self._is_handling_active = False


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


def get_shortcut_command_prefix() -> str:
    """Retorna o prefixo do comando para configurar os atalhos de teclado do GNOME."""
    if os.path.exists("/.flatpak-info"):
        return "flatpak run com.github.geraldohomero.NarroRsa"

    try:
        res = subprocess.run(
            ["flatpak", "info", "com.github.geraldohomero.NarroRsa"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        if res.returncode == 0:
            return "flatpak run com.github.geraldohomero.NarroRsa"
    except (OSError, subprocess.TimeoutExpired):
        pass

    if shutil.which("narro-rsa"):
        return "narro-rsa"

    return f"{sys.executable} {os.path.abspath(__file__)}"


def _run_gsettings_cmd(args: list[str]) -> str:
    """Executa um comando gsettings no host ou localmente."""
    gsettings_cmd = "/usr/bin/gsettings"
    if os.path.exists("/.flatpak-info"):
        cmd = ["flatpak-spawn", "--host", gsettings_cmd] + args
    else:
        bin_path = gsettings_cmd if os.path.exists(gsettings_cmd) else "gsettings"
        cmd = [bin_path] + args
    env = os.environ.copy()
    for var in ("DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
        if var in os.environ:
            env[var] = os.environ[var]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
        if res.returncode != 0:
            return ""
        return res.stdout.strip()
    except OSError:
        return ""


def configure_gnome_shortcuts(force: bool = False) -> bool:
    """Configura os atalhos de teclado customizados no GNOME via gsettings.
    
    Verifica diretamente no GNOME se os 4 atalhos estão configurados.
    Se algum faltar ou se force=True, adiciona/atualiza os atalhos sem sobrepor outros apps.
    Retorna True se atalhos foram configurados/atualizados, False se já estavam configurados.
    """
    import re

    prefix = get_shortcut_command_prefix()
    tag = " [Flatpak]" if "flatpak" in prefix else ""
    desired_shortcuts = [
        {
            "name": f"Leitor TTS (Narro){tag}",
            "command": f"{prefix} --play",
            "binding": "<Super><Alt>l",
        },
        {
            "name": f"Leitor TTS (Narro) [Ctrl+\\]{tag}",
            "command": f"{prefix} --primary",
            "binding": "<Control>backslash",
        },
        {
            "name": f"Pausar leitura TTS (Narro){tag}",
            "command": f"{prefix} --pause",
            "binding": "<Super><Alt>j",
        },
        {
            "name": f"Parar leitura TTS (Narro){tag}",
            "command": f"{prefix} --stop",
            "binding": "<Super><Alt>k",
        },
    ]

    bindings_str = _run_gsettings_cmd(["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"])
    if not bindings_str and bindings_str != "@as []":
        print("Não foi possível acessar as configurações de atalhos do GNOME.")
        return False

    if bindings_str == "@as []" or not bindings_str:
        current_bindings = []
    else:
        current_bindings = re.findall(r"'(.*?)'", bindings_str)

    # Se não for forçado, verifica se todos os atalhos já estão presentes e corretos
    if not force:
        existing_shortcuts = []
        for path in current_bindings:
            schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
            name = _run_gsettings_cmd(["get", schema, "name"]).strip("'\" ")
            cmd = _run_gsettings_cmd(["get", schema, "command"]).strip("'\" ")
            binding = _run_gsettings_cmd(["get", schema, "binding"]).strip("'\" ")
            existing_shortcuts.append({"name": name, "command": cmd, "binding": binding})

        all_present = True
        for ds in desired_shortcuts:
            matched = any(
                es["name"] == ds["name"] and es["command"] == ds["command"] and es["binding"] == ds["binding"]
                for es in existing_shortcuts
            )
            if not matched:
                all_present = False
                break
        if all_present:
            return False

    # Filtra atalhos anteriores do Narro para evitar duplicações
    new_bindings = []
    for path in current_bindings:
        schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
        name = _run_gsettings_cmd(["get", schema, "name"]).strip("'\" ")
        cmd = _run_gsettings_cmd(["get", schema, "command"]).strip("'\" ")
        if "Narro" in name or "com.github.geraldohomero.NarroRsa" in cmd or "narro-rsa" in cmd:
            continue
        new_bindings.append(path)

    assigned = []
    for shortcut in desired_shortcuts:
        idx = 0
        while True:
            path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{idx}/"
            if path not in new_bindings:
                break
            idx += 1

        new_bindings.append(path)
        assigned.append((path, shortcut))

    array_val = "[" + ", ".join([f"'{p}'" for p in new_bindings]) + "]"
    _run_gsettings_cmd(["set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", array_val])

    for path, shortcut in assigned:
        schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
        _run_gsettings_cmd(["set", schema, "name", shortcut["name"]])
        _run_gsettings_cmd(["set", schema, "command", shortcut["command"]])
        _run_gsettings_cmd(["set", schema, "binding", shortcut["binding"]])

    print("Atalhos do GNOME configurados com sucesso!")
    return True


def main():
    if "--setup-shortcuts" in sys.argv:
        configure_gnome_shortcuts(force=True)
        sys.exit(0)

    if "--play" in sys.argv or "--primary" in sys.argv:
        check_and_start_daemon()
        use_primary = "--primary" in sys.argv
        text = get_clipboard_text(primary=use_primary)
        if not text:
            send_notification("Narro-RSA", _("notify_no_text"), icon="dialog-warning")
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
                with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                sys.exit(0)
                
            try:
                os.kill(pid, signal.SIGUSR1)
            except OSError:
                pass
            sys.exit(0)
            
        try:
            with open(LAST_READ_FILE, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass

        settings = load_settings()
        engine = settings.get("engine", DEFAULT_ENGINE)
        default_voice = DEFAULT_VOICE_EDGE if engine == "edge-tts" else get_default_piper_voice()
        voice = settings.get("voice") or default_voice
        speed = float(settings.get("speed", SPEED_DEFAULT))
        
        preview = preview_text(text, max_chars=80)

        kill_mpv()
        try:
            from narro_rsa.constants import MPV_SOCKET
            try:
                os.unlink(MPV_SOCKET)
            except OSError:
                pass
                
            engine_type = EngineType.PIPER if engine == "piper" else EngineType.EDGE_TTS
            request = TTSRequest(text=text, voice=voice, engine=engine_type, speed=speed)

            from narro_rsa.mpris import MPRISService

            loop = GLib.MainLoop()
            mpris_holder = [None]

            def _on_first_chunk(proc_obj):
                def _on_play():
                    send_mpv_command(["set_property", "pause", False])

                def _on_pause():
                    send_mpv_command(["set_property", "pause", True])

                def _on_play_pause():
                    send_mpv_command(["cycle", "pause"])

                def _on_stop():
                    kill_mpv()

                mpris = MPRISService(
                    on_play=_on_play,
                    on_pause=_on_pause,
                    on_play_pause=_on_play_pause,
                    on_stop=_on_stop,
                )
                mpris.publish(title=preview, text=text, speed=speed)
                mpris_holder[0] = mpris

                def _check_mpv_status():
                    if proc_obj.poll() is not None:
                        if mpris_holder[0]:
                            mpris_holder[0].unpublish()
                        loop.quit()
                        return False

                    res = send_mpv_command(["get_property", "pause"])
                    if isinstance(res, dict) and "data" in res and mpris_holder[0]:
                        is_paused = bool(res["data"])
                        curr_status = mpris_holder[0].playback_status
                        if is_paused and curr_status != "Paused":
                            mpris_holder[0].set_playback_status("Paused")
                        elif not is_paused and curr_status != "Playing":
                            mpris_holder[0].set_playback_status("Playing")

                    return True

                GLib.timeout_add(250, _check_mpv_status)

            err_holder = [None]
            def _on_error(err_msg):
                err_holder[0] = err_msg

            proc, bg_thread = play_chunked_tts(
                request,
                on_first_chunk_ready=_on_first_chunk,
                on_error=_on_error,
                generate_fn=generate_audio,
            )

            if proc is not None:
                def _on_sig(*_):
                    kill_mpv()
                    if mpris_holder[0]:
                        mpris_holder[0].unpublish()
                    loop.quit()

                signal.signal(signal.SIGINT, _on_sig)
                signal.signal(signal.SIGTERM, _on_sig)

                try:
                    loop.run()
                finally:
                    if mpris_holder[0]:
                        mpris_holder[0].unpublish()
                    kill_mpv()
            else:
                err = err_holder[0] or "Erro na síntese de voz"
                send_notification("Narro-RSA", _("toast_playback_error", error=err), icon="dialog-error")
        except Exception as e:
            print(f"Erro na leitura em background: {e}")
            send_notification("Narro-RSA", _("toast_playback_error", error=str(e)), icon="dialog-error")
        sys.exit(0)

    if "--pause" in sys.argv:
        send_mpv_command(["cycle", "pause"])
        sys.exit(0)
        
    if "--stop" in sys.argv:
        kill_mpv()
        sys.exit(0)

    app = NarroApp()
    sys.exit(app.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
