"""Unit tests for CLI shortcuts, MPRIS integration, and notifications in main_window.py."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from narro_rsa.translations import _


class TestCliShortcuts(unittest.TestCase):
    @patch("main_window.get_clipboard_text", return_value="")
    @patch("main_window.send_notification")
    def test_play_empty_clipboard_shows_notification(self, mock_notify, mock_clip):
        import main_window
        test_args = ["main_window.py", "--play"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)
            mock_notify.assert_called_once_with(
                "Narro-RSA",
                _("notify_no_text"),
                icon="dialog-warning"
            )

    @patch("main_window.get_clipboard_text", return_value="Some sample text for reading")
    @patch("main_window.send_notification")
    @patch("main_window.generate_audio")
    @patch("main_window.popen_command")
    @patch("main_window.kill_mpv")
    @patch("narro_rsa.mpris.MPRISService")
    @patch("gi.repository.GLib.MainLoop")
    def test_play_with_text_publishes_mpris_without_banner_notification(
        self, mock_loop_cls, mock_mpris_cls, mock_kill, mock_popen, mock_gen, mock_notify, mock_clip
    ):
        import main_window
        from narro_rsa.tts_engine import GenerationResult
        mock_gen.return_value = GenerationResult(
            success=True,
            audio_path="/tmp/fake.wav",
            engine_name="piper",
            error_message=""
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        mock_mpris_instance = MagicMock()
        mock_mpris_cls.return_value = mock_mpris_instance

        mock_loop_instance = MagicMock()
        mock_loop_cls.return_value = mock_loop_instance

        test_args = ["main_window.py", "--play"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)

            # Assert MPRIS service was instantiated and published
            mock_mpris_cls.assert_called_once()
            mock_mpris_instance.publish.assert_called_once()

            # Assert banner notification was NOT shown
            mock_notify.assert_not_called()

    @patch("main_window.send_mpv_command")
    @patch("main_window.send_notification")
    def test_pause_cycles_mpv_without_banner_notification(self, mock_notify, mock_mpv):
        import main_window
        test_args = ["main_window.py", "--pause"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)
            mock_mpv.assert_called_once_with(["cycle", "pause"])
            mock_notify.assert_not_called()

    @patch("main_window.kill_mpv")
    @patch("main_window.send_notification")
    def test_stop_kills_mpv_without_banner_notification(self, mock_notify, mock_kill):
        import main_window
        test_args = ["main_window.py", "--stop"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)
            mock_kill.assert_called_once()
            mock_notify.assert_not_called()


class TestGnomeShortcutsConfig(unittest.TestCase):
    def test_configure_gnome_shortcuts_when_missing(self):
        import main_window
        # Mock run_gsettings to simulate empty custom-keybindings
        calls = []
        def fake_run(args):
            calls.append(args)
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return "@as []"
            return ""

        with patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertTrue(result)
            # Verify custom-keybindings was set
            set_calls = [c for c in calls if c[0] == "set"]
            self.assertTrue(len(set_calls) > 0)

    def test_configure_gnome_shortcuts_when_already_configured(self):
        import main_window
        bindings = [
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom3/",
        ]
        bindings_str = str(bindings)

        def fake_run(args):
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return bindings_str
            # Return matching commands for custom0..3
            if args[0] == "get":
                schema = args[1]
                key = args[2]
                if key == "command":
                    if "custom0" in schema:
                        return "'flatpak run com.github.geraldohomero.NarroRsa --play'"
                    if "custom1" in schema:
                        return "'flatpak run com.github.geraldohomero.NarroRsa --primary'"
                    if "custom2" in schema:
                        return "'flatpak run com.github.geraldohomero.NarroRsa --pause'"
                    if "custom3" in schema:
                        return "'flatpak run com.github.geraldohomero.NarroRsa --stop'"
                if key == "binding":
                    if "custom0" in schema:
                        return "'<Super><Alt>l'"
                    if "custom1" in schema:
                        return "'<Control>backslash'"
                    if "custom2" in schema:
                        return "'<Super><Alt>j'"
                    if "custom3" in schema:
                        return "'<Super><Alt>k'"
            return ""

        with patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            # Not force -> should detect all 4 are present and return False
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
