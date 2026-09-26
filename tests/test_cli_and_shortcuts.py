"""Unit tests for CLI shortcuts and notifications in main_window.py."""
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

    @patch("main_window.get_clipboard_text", return_value="Some sample text")
    @patch("main_window.get_clipboard_text", return_value="Some sample text for reading")
    @patch("main_window.send_notification")
    @patch("main_window.generate_audio")
    @patch("main_window.popen_command")
    @patch("main_window.kill_mpv")
    def test_play_with_text_shows_reading_notification(
        self, mock_kill, mock_popen, mock_gen, mock_notify, mock_clip
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
        mock_proc.wait.return_value = 0
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
            mock_notify.assert_called_once()
            args, kwargs = mock_notify.call_args
            self.assertEqual(args[0], "Narro-RSA")
            self.assertIn(_("notify_reading"), args[1])
            self.assertIn("Some sample text", args[1])

            # Assert MPRIS service was instantiated and published
            mock_mpris_cls.assert_called_once()
            mock_mpris_instance.publish.assert_called_once()

            # Assert banner notification was NOT shown
            mock_notify.assert_not_called()

    @patch("main_window.send_mpv_command")
    @patch("main_window.send_notification")
    def test_pause_shows_notification(self, mock_notify, mock_mpv):
    def test_pause_cycles_mpv_without_banner_notification(self, mock_notify, mock_mpv):
        import main_window
        mock_mpv.side_effect = [{"data": False}, None]
        test_args = ["main_window.py", "--pause"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)
            mock_notify.assert_called_once_with(
                "Narro-RSA",
                _("notify_paused"),
                icon="media-playback-pause-symbolic"
            )
            mock_mpv.assert_called_once_with(["cycle", "pause"])
            mock_notify.assert_not_called()

    @patch("main_window.is_mpv_active", return_value=True)
    @patch("main_window.kill_mpv")
    @patch("main_window.send_notification")
    def test_stop_shows_notification(self, mock_notify, mock_kill, mock_active):
    def test_stop_kills_mpv_without_banner_notification(self, mock_notify, mock_kill):
        import main_window
        test_args = ["main_window.py", "--stop"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)
            mock_notify.assert_called_once_with(
                "Narro-RSA",
                _("notify_stopped"),
                icon="media-playback-stop-symbolic"
            )
            mock_kill.assert_called_once()
            mock_notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
