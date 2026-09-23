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


class TestMainWindowMethods(unittest.TestCase):
    def test_main_window_has_show_toast(self):
        from main_window import MainWindow
        self.assertTrue(hasattr(MainWindow, "show_toast"))

    def test_configure_gnome_shortcuts_cached(self):
        from main_window import configure_gnome_shortcuts
        with tempfile.TemporaryDirectory() as tmp_config:
            marker = os.path.join(tmp_config, ".shortcuts_configured_v3")
            with open(marker, "w") as f:
                f.write("configured")
            with patch("narro_rsa.constants.CONFIG_DIR", tmp_config):
                with patch("subprocess.run") as mock_run:
                    configure_gnome_shortcuts(force=False)
                    mock_run.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
