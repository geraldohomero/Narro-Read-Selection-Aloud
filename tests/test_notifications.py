"""Unit tests for notifications module in Narro-RSA."""

import unittest
from unittest.mock import MagicMock, patch

from narro_rsa.translations import _


class TestNotificationTranslations(unittest.TestCase):
    def test_notification_keys_exist_in_all_languages(self):
        from narro_rsa.translations import TRANSLATIONS
        keys = [
            "notify_reading",
            "notify_no_text",
            "notify_paused",
            "notify_resumed",
            "notify_stopped",
        ]
        for lang in ("en", "pt_BR", "zh_CN"):
            for k in keys:
                self.assertIn(k, TRANSLATIONS[lang], f"Missing key '{k}' in language '{lang}'")


class TestNotificationSender(unittest.TestCase):
    def test_send_notification_notify_lib(self):
        from narro_rsa.notifications import send_notification
        with patch("narro_rsa.notifications._send_via_libnotify", return_value=True) as mock_lib:
            res = send_notification("Narro-RSA", "Test message")
            self.assertTrue(res)
            mock_lib.assert_called_once_with("Narro-RSA", "Test message", "dialog-information", 3000)

    def test_send_notification_fallback_to_cli(self):
        from narro_rsa.notifications import send_notification
        with patch("narro_rsa.notifications._send_via_libnotify", return_value=False):
            with patch("narro_rsa.notifications._send_via_notify_send", return_value=True) as mock_cli:
                res = send_notification("Narro-RSA", "Test fallback")
                self.assertTrue(res)
    def test_preview_text(self):
        from narro_rsa.notifications import preview_text
        self.assertEqual(preview_text("   Hello   world!   "), "Hello world!")
        long_str = "A" * 100
        preview = preview_text(long_str, max_chars=20)
        self.assertEqual(preview, "A" * 20 + "...")


if __name__ == "__main__":
    unittest.main()
