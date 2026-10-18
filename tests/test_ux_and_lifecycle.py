"""Unit tests for UX improvements and lifecycle management in Narro-RSA."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import narro_rsa.mpv_control as mpv_ctrl
from narro_rsa.translations import _


class TestMpvLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.test_socket = os.path.join(self.tmpdir.name, "test_mpv.sock")
        self._orig_socket = mpv_ctrl.MPV_SOCKET
        mpv_ctrl.MPV_SOCKET = self.test_socket

    def tearDown(self):
        mpv_ctrl.MPV_SOCKET = self._orig_socket

    def test_is_mpv_active_no_socket(self):
        self.assertFalse(mpv_ctrl.is_mpv_active())

    def test_is_mpv_active_stale_socket_cleans_up(self):
        with open(self.test_socket, "w") as f:
            f.write("")
        self.assertTrue(os.path.exists(self.test_socket))
        self.assertFalse(mpv_ctrl.is_mpv_active())
        self.assertFalse(os.path.exists(self.test_socket))

    def test_is_mpv_active_running(self):
        with open(self.test_socket, "w") as f:
            f.write("")
        with patch("narro_rsa.mpv_control.send_mpv_command", return_value={"error": "success", "data": False}):
            self.assertTrue(mpv_ctrl.is_mpv_active())
            self.assertTrue(os.path.exists(self.test_socket))


class TestTranslations(unittest.TestCase):
    def test_no_text_toast_translations_exist(self):
        from narro_rsa.translations import TRANSLATIONS
        for lang in ("en", "pt_BR", "zh_CN"):
            self.assertIn("no_text_toast", TRANSLATIONS[lang])
            self.assertTrue(len(TRANSLATIONS[lang]["no_text_toast"]) > 0)


    def test_quick_selector_translations_exist(self):
        from narro_rsa.translations import TRANSLATIONS
        for lang in ("en", "pt_BR", "zh_CN"):
            for key in ("quick_engine_label", "quick_voice_label", "no_piper_voices_downloaded"):
                self.assertIn(key, TRANSLATIONS[lang])
                self.assertTrue(len(TRANSLATIONS[lang][key]) > 0)


class TestMainWindowMethods(unittest.TestCase):
    def test_main_window_has_show_toast(self):
        from main_window import MainWindow
        self.assertTrue(hasattr(MainWindow, "show_toast"))

    def test_configure_gnome_shortcuts_already_configured(self):
        from main_window import configure_gnome_shortcuts
        with patch("main_window._run_gsettings_cmd") as mock_gsettings:
            # Simulate GNOME with shortcuts already set
            mock_gsettings.side_effect = lambda args: "@as []" if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"] else ""
            res = configure_gnome_shortcuts(force=True)
            self.assertTrue(res)

    def test_reader_page_has_load_clipboard_async(self):
        from narro_rsa.reader_page import ReaderPage
        self.assertTrue(hasattr(ReaderPage, "load_clipboard_async"))

    def test_reader_page_load_clipboard_async_safe_without_display(self):
        from narro_rsa.reader_page import ReaderPage
        mock_page = MagicMock(spec=ReaderPage)
        # Deve executar com segurança sem lançar exceção mesmo se display for None
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            ReaderPage.load_clipboard_async(mock_page)

    def test_main_window_active_debounce_and_reentrancy(self):
        import time
        from main_window import MainWindow

        mock_win = MagicMock(spec=MainWindow)
        mock_win._is_handling_active = False
        mock_win._last_active_time = time.time()
        mock_win._load_and_update_settings = MagicMock()
        mock_win.reader_page = MagicMock()

        mock_gobj_win = MagicMock()
        mock_gobj_win.get_property.return_value = True

        # Teste 1: Chamada imediata subsequente deve ser ignorada pelo debounce
        MainWindow._on_window_active(mock_win, mock_gobj_win, None)
        mock_win._load_and_update_settings.assert_not_called()

        # Teste 2: Proteção contra reentrância quando _is_handling_active = True
        mock_win._is_handling_active = True
        mock_win._last_active_time = 0.0
        MainWindow._on_window_active(mock_win, mock_gobj_win, None)
        mock_win._load_and_update_settings.assert_not_called()

        # Teste 3: Chamada após intervalo (> 0.5s) e sem reentrância deve executar
        mock_win._is_handling_active = False
        mock_win._last_active_time = 0.0
        mock_buffer = MagicMock()
        mock_buffer.get_bounds.return_value = (0, 0)
        mock_buffer.get_text.return_value = _("no_text")
        mock_win.reader_page.text_view.get_buffer.return_value = mock_buffer

        with patch("narro_rsa.mpv_control.is_mpv_active", return_value=False):
            MainWindow._on_window_active(mock_win, mock_gobj_win, None)
            mock_win._load_and_update_settings.assert_called_once()
            mock_win.reader_page.load_clipboard_async.assert_called_once()


class TestReaderPageFeedback(unittest.TestCase):
    def test_generate_and_play_local_error_shows_toast(self):
        from narro_rsa.reader_page import ReaderPage
        from narro_rsa.tts_engine import GenerationResult
        mock_win = MagicMock()
        mock_page = MagicMock(spec=ReaderPage)
        mock_page.main_window = mock_win

        failed_res = GenerationResult(success=False, audio_path="", engine_name="piper", error_message="Model file missing")
        with patch("narro_rsa.reader_page.generate_audio", return_value=failed_res):
            with patch("gi.repository.GLib.idle_add") as mock_idle:
                ReaderPage._generate_and_play_local(mock_page, "Hello text", "voice1", 1.0, "piper")
                mock_idle.assert_called_once()
                fn = mock_idle.call_args[0][0]
                self.assertEqual(fn, mock_win.show_toast)


class TestReaderPageQuickSelectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()

    def test_reader_page_has_quick_selectors_and_search(self):
        from narro_rsa.reader_page import ReaderPage
        page = ReaderPage(MagicMock())
        self.assertTrue(hasattr(page, "quick_engine_dropdown"))
        self.assertTrue(hasattr(page, "quick_voice_dropdown"))
        self.assertTrue(hasattr(page, "quick_voice_codes"))
        self.assertTrue(hasattr(page, "_populate_quick_voices"))
        self.assertTrue(page.quick_voice_dropdown.get_enable_search())

    @patch("narro_rsa.reader_page.fetch_edge_voices")
    @patch("narro_rsa.reader_page.get_top_edge_quick_voices")
    @patch("narro_rsa.reader_page.load_settings")
    def test_populate_quick_voices_edge_tts(self, mock_load, mock_get_top, mock_fetch):
        mock_load.return_value = {"engine": "edge-tts", "voice": "pt-BR-FranciscaNeural"}
        mock_get_top.return_value = [
            ("pt-BR-FranciscaNeural", "Francisca (Português - Brasil)"),
            ("en-US-AriaNeural", "Aria (English - US)"),
        ]
        mock_fetch.return_value = []
        from narro_rsa.reader_page import ReaderPage
        page = ReaderPage(MagicMock())
        page._populate_quick_voices()

        self.assertEqual(len(page.quick_voice_codes), 2)
        self.assertEqual(page.quick_voice_codes[0], "pt-BR-FranciscaNeural")
        self.assertEqual(page.quick_voice_dropdown.get_selected(), 0)

    @patch("narro_rsa.reader_page.fetch_edge_voices")
    @patch("narro_rsa.reader_page.get_top_edge_quick_voices")
    @patch("narro_rsa.reader_page.load_settings")
    def test_populate_quick_voices_edge_tts_custom_voice_prepended(self, mock_load, mock_get_top, mock_fetch):
        mock_load.return_value = {"engine": "edge-tts", "voice": "it-IT-DiegoNeural"}
        mock_get_top.return_value = [
            ("pt-BR-FranciscaNeural", "Francisca (Português - Brasil)"),
            ("en-US-AriaNeural", "Aria (English - US)"),
        ]
        mock_fetch.return_value = [
            {"ShortName": "it-IT-DiegoNeural", "FriendlyName": "Diego (Italiano)"}
        ]
        from narro_rsa.reader_page import ReaderPage
        page = ReaderPage(MagicMock())
        page._populate_quick_voices()

        self.assertEqual(page.quick_voice_codes[0], "it-IT-DiegoNeural")
        self.assertEqual(page.quick_voice_dropdown.get_selected(), 0)

    @patch("narro_rsa.reader_page.fetch_piper_catalog")
    @patch("narro_rsa.reader_page.get_downloaded_piper_voices")
    @patch("narro_rsa.reader_page.load_settings")
    def test_populate_quick_voices_piper_with_downloaded(self, mock_load, mock_get_downloaded, mock_piper_cat):
        mock_load.return_value = {"engine": "piper", "voice": "pt_BR-faber-medium"}
        mock_get_downloaded.return_value = [
            ("pt_BR-faber-medium", "Faber (Medium)"),
            ("en_US-amy-medium", "Amy (Medium)"),
        ]
        mock_piper_cat.return_value = {}
        from narro_rsa.reader_page import ReaderPage
        page = ReaderPage(MagicMock())
        page._populate_quick_voices()

        self.assertTrue(page.quick_voice_dropdown.get_sensitive())
        self.assertEqual(len(page.quick_voice_codes), 2)
        self.assertIn("pt_BR-faber-medium", page.quick_voice_codes)
        self.assertEqual(page.quick_voice_dropdown.get_selected(), 0)
        model = page.quick_voice_dropdown.get_model()
        first_item = model.get_string(0)
        self.assertIn("Português (Brasil)", first_item)
        self.assertIn("Faber (Medium)", first_item)

    @patch("narro_rsa.reader_page.get_downloaded_piper_voices")
    @patch("narro_rsa.reader_page.load_settings")
    def test_populate_quick_voices_piper_empty_disables_dropdown(self, mock_load, mock_get_downloaded):
        mock_load.return_value = {"engine": "piper", "voice": None}
        mock_get_downloaded.return_value = []
        from narro_rsa.reader_page import ReaderPage
        page = ReaderPage(MagicMock())
        page._populate_quick_voices()

        self.assertFalse(page.quick_voice_dropdown.get_sensitive())
        self.assertEqual(len(page.quick_voice_codes), 0)
        model = page.quick_voice_dropdown.get_model()
        self.assertEqual(model.get_string(0), _("no_piper_voices_downloaded"))

    @patch("narro_rsa.reader_page.save_settings")
    @patch("narro_rsa.reader_page.load_settings")
    @patch("narro_rsa.reader_page.get_downloaded_piper_voices")
    def test_quick_engine_changed_saves_settings_and_updates_ui(self, mock_piper, mock_load, mock_save):
        mock_load.return_value = {"engine": "piper", "voice": "pt_BR-faber-medium"}
        mock_piper.return_value = [("pt_BR-faber-medium", "Faber (Medium)")]
        from narro_rsa.reader_page import ReaderPage
        mock_win = MagicMock()
        page = ReaderPage(mock_win)

        # Switch to Edge TTS (index 1)
        page.quick_engine_dropdown.set_selected(1)
        mock_save.assert_called()
        calls = [c.kwargs for c in mock_save.call_args_list if "engine" in c.kwargs]
        self.assertTrue(any(c.get("engine") == "edge-tts" for c in calls))

    @patch("narro_rsa.reader_page.save_settings")
    @patch("narro_rsa.reader_page.load_settings")
    @patch("narro_rsa.reader_page.get_top_edge_quick_voices")
    def test_quick_voice_changed_saves_settings_and_updates_ui(self, mock_edge, mock_load, mock_save):
        mock_load.return_value = {"engine": "edge-tts", "voice": "pt-BR-FranciscaNeural"}
        mock_edge.return_value = [
            ("pt-BR-FranciscaNeural", "Francisca (Português - Brasil)"),
            ("en-US-AriaNeural", "Aria (English - US)"),
        ]
        from narro_rsa.reader_page import ReaderPage
        mock_win = MagicMock()
        page = ReaderPage(mock_win)

        # Switch voice to index 1 (en-US-AriaNeural)
        page.quick_voice_dropdown.set_selected(1)
        mock_save.assert_called()
        calls = [c.kwargs for c in mock_save.call_args_list if "voice" in c.kwargs]
        self.assertTrue(any(c.get("voice") == "en-US-AriaNeural" for c in calls))


if __name__ == "__main__":
    unittest.main()

