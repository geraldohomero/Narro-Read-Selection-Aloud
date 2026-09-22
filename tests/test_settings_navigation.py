import unittest
from unittest.mock import patch, MagicMock
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

class TestSettingsNavigation(unittest.TestCase):
    def test_settings_page_is_navigation_page(self):
        from narro_rsa.settings_page import SettingsPage
        self.assertTrue(issubclass(SettingsPage, Adw.NavigationPage))

    def test_settings_has_dropdown_with_search_methods(self):
        from narro_rsa.settings_page import SettingsPage
        self.assertTrue(hasattr(SettingsPage, "_on_lang_dropdown_changed"))
        self.assertTrue(hasattr(SettingsPage, "_populate_languages"))
        self.assertTrue(hasattr(SettingsPage, "_select_initial_language"))
        self.assertTrue(hasattr(SettingsPage, "update_ui_texts"))

    def test_main_window_has_navigation_methods(self):
        from main_window import MainWindow
        self.assertTrue(hasattr(MainWindow, "show_settings_page"))
        self.assertTrue(hasattr(MainWindow, "update_ui_texts"))

if __name__ == "__main__":
    unittest.main()
