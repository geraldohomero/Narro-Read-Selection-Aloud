"""Unit tests for CLI shortcuts, MPRIS integration, and notifications in main_window.py."""

import os
import shutil
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


class TestConstantsAndVoiceHelper(unittest.TestCase):
    def test_default_engine_is_piper(self):
        from narro_rsa.constants import DEFAULT_ENGINE
        self.assertEqual(DEFAULT_ENGINE, "piper")

    def test_get_default_piper_voice_faber_exists(self):
        import tempfile
        from narro_rsa import constants
        with tempfile.TemporaryDirectory() as tmpdir:
            faber_path = os.path.join(tmpdir, "pt_BR-faber-medium.onnx")
            with open(faber_path, "w") as f:
                f.write("dummy")
            with patch.object(constants, "PIPER_VOICES_DIR", tmpdir):
                self.assertEqual(constants.get_default_piper_voice(), "pt_BR-faber-medium")

    def test_get_default_piper_voice_cadu_exists(self):
        import tempfile
        from narro_rsa import constants
        with tempfile.TemporaryDirectory() as tmpdir:
            cadu_path = os.path.join(tmpdir, "pt_BR-cadu-medium.onnx")
            with open(cadu_path, "w") as f:
                f.write("dummy")
            with patch.object(constants, "PIPER_VOICES_DIR", tmpdir):
                self.assertEqual(constants.get_default_piper_voice(), "pt_BR-cadu-medium")

    def test_get_default_piper_voice_fallback_to_other_onnx(self):
        import tempfile
        from narro_rsa import constants
        with tempfile.TemporaryDirectory() as tmpdir:
            other_path = os.path.join(tmpdir, "en_US-amy-medium.onnx")
            with open(other_path, "w") as f:
                f.write("dummy")
            with patch.object(constants, "PIPER_VOICES_DIR", tmpdir):
                self.assertEqual(constants.get_default_piper_voice(), "en_US-amy-medium")

    def test_get_default_piper_voice_empty_or_missing_dir(self):
        import tempfile
        from narro_rsa import constants
        non_existent = os.path.join(tempfile.gettempdir(), "non_existent_piper_dir_test_123")
        with patch.object(constants, "PIPER_VOICES_DIR", non_existent):
            self.assertEqual(constants.get_default_piper_voice(), constants.DEFAULT_VOICE_PIPER)


class TestShortcutCommandPrefix(unittest.TestCase):
    def test_prefix_inside_flatpak(self):
        import main_window
        with patch("os.path.exists", side_effect=lambda p: p == "/.flatpak-info"):
            self.assertEqual(
                main_window.get_shortcut_command_prefix(),
                "flatpak run com.github.geraldohomero.NarroRsa"
            )

    def test_prefix_flatpak_info_on_host(self):
        import main_window
        mock_proc = MagicMock(returncode=0)
        with patch("os.path.exists", return_value=False), \
             patch("subprocess.run", return_value=mock_proc):
            self.assertEqual(
                main_window.get_shortcut_command_prefix(),
                "flatpak run com.github.geraldohomero.NarroRsa"
            )

    def test_prefix_narro_rsa_in_path(self):
        import main_window
        mock_proc = MagicMock(returncode=1)
        with patch("os.path.exists", return_value=False), \
             patch("subprocess.run", return_value=mock_proc), \
             patch("shutil.which", side_effect=lambda b: "/usr/bin/narro-rsa" if b == "narro-rsa" else None):
            self.assertEqual(
                main_window.get_shortcut_command_prefix(),
                "narro-rsa"
            )

    def test_prefix_python_fallback(self):
        import main_window
        mock_proc = MagicMock(returncode=1)
        with patch("os.path.exists", return_value=False), \
             patch("subprocess.run", return_value=mock_proc), \
             patch("shutil.which", return_value=None):
            expected = f"{sys.executable} {os.path.abspath(main_window.__file__)}"
            self.assertEqual(
                main_window.get_shortcut_command_prefix(),
                expected
            )


class TestGnomeShortcutsConfig(unittest.TestCase):
    @patch("subprocess.run")
    def test_run_gsettings_cmd_forwards_env(self, mock_run):
        import main_window
        mock_run.return_value = MagicMock(returncode=0, stdout="test-val\n")
        custom_env = {
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/test-bus",
            "DISPLAY": ":99",
            "WAYLAND_DISPLAY": "wayland-1",
            "XDG_RUNTIME_DIR": "/run/user/1000",
        }
        with patch.dict(os.environ, custom_env, clear=False), \
             patch("os.path.exists", return_value=False):
            res = main_window._run_gsettings_cmd(["get", "some.schema", "key"])
            self.assertEqual(res, "test-val")
            self.assertTrue(mock_run.called)
            called_env = mock_run.call_args[1].get("env", {})
            for k, v in custom_env.items():
                self.assertEqual(called_env.get(k), v)

    def test_configure_gnome_shortcuts_when_missing(self):
        import main_window
        calls = []
        def fake_run(args):
            calls.append(args)
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return "@as []"
            return ""

        with patch("main_window.get_shortcut_command_prefix", return_value="narro-rsa"), \
             patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertTrue(result)
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
            if args[0] == "get":
                schema = args[1]
                key = args[2]
                if key == "name":
                    if "custom0" in schema:
                        return "'Leitor TTS (Narro)'"
                    if "custom1" in schema:
                        return "'Leitor TTS (Narro) [Ctrl+\\]'"
                    if "custom2" in schema:
                        return "'Pausar leitura TTS (Narro)'"
                    if "custom3" in schema:
                        return "'Parar leitura TTS (Narro)'"
                if key == "command":
                    if "custom0" in schema:
                        return "'narro-rsa --play'"
                    if "custom1" in schema:
                        return "'narro-rsa --primary'"
                    if "custom2" in schema:
                        return "'narro-rsa --pause'"
                    if "custom3" in schema:
                        return "'narro-rsa --stop'"
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

        with patch("main_window.get_shortcut_command_prefix", return_value="narro-rsa"), \
             patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertFalse(result)

    def test_configure_gnome_shortcuts_rebinds_on_name_mismatch(self):
        import main_window
        bindings = [
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom3/",
        ]
        bindings_str = str(bindings)
        calls = []

        def fake_run(args):
            calls.append(args)
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return bindings_str
            if args[0] == "get":
                schema = args[1]
                key = args[2]
                if key == "name":
                    return "'Old Name Mismatch'"
                if key == "command":
                    if "custom0" in schema:
                        return "'narro-rsa --play'"
                    if "custom1" in schema:
                        return "'narro-rsa --primary'"
                    if "custom2" in schema:
                        return "'narro-rsa --pause'"
                    if "custom3" in schema:
                        return "'narro-rsa --stop'"
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

        with patch("main_window.get_shortcut_command_prefix", return_value="narro-rsa"), \
             patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertTrue(result)
            set_calls = [c for c in calls if c[0] == "set"]
            self.assertTrue(len(set_calls) > 0)

    def test_configure_gnome_shortcuts_rebinds_on_command_mismatch(self):
        import main_window
        bindings = [
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom3/",
        ]
        bindings_str = str(bindings)
        calls = []

        def fake_run(args):
            calls.append(args)
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return bindings_str
            if args[0] == "get":
                schema = args[1]
                key = args[2]
                if key == "name":
                    if "custom0" in schema:
                        return "'Leitor TTS (Narro)'"
                    if "custom1" in schema:
                        return "'Leitor TTS (Narro) [Ctrl+\\]'"
                    if "custom2" in schema:
                        return "'Pausar leitura TTS (Narro)'"
                    if "custom3" in schema:
                        return "'Parar leitura TTS (Narro)'"
                if key == "command":
                    # Mismatch on custom0
                    if "custom0" in schema:
                        return "'old-app --play'"
                    if "custom1" in schema:
                        return "'narro-rsa --primary'"
                    if "custom2" in schema:
                        return "'narro-rsa --pause'"
                    if "custom3" in schema:
                        return "'narro-rsa --stop'"
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

        with patch("main_window.get_shortcut_command_prefix", return_value="narro-rsa"), \
             patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertTrue(result)
            set_calls = [c for c in calls if c[0] == "set"]
            self.assertTrue(len(set_calls) > 0)

    def test_configure_gnome_shortcuts_rebinds_on_binding_mismatch(self):
        import main_window
        bindings = [
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2/",
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom3/",
        ]
        bindings_str = str(bindings)
        calls = []

        def fake_run(args):
            calls.append(args)
            if args == ["get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]:
                return bindings_str
            if args[0] == "get":
                schema = args[1]
                key = args[2]
                if key == "name":
                    if "custom0" in schema:
                        return "'Leitor TTS (Narro)'"
                    if "custom1" in schema:
                        return "'Leitor TTS (Narro) [Ctrl+\\]'"
                    if "custom2" in schema:
                        return "'Pausar leitura TTS (Narro)'"
                    if "custom3" in schema:
                        return "'Parar leitura TTS (Narro)'"
                if key == "command":
                    if "custom0" in schema:
                        return "'narro-rsa --play'"
                    if "custom1" in schema:
                        return "'narro-rsa --primary'"
                    if "custom2" in schema:
                        return "'narro-rsa --pause'"
                    if "custom3" in schema:
                        return "'narro-rsa --stop'"
                if key == "binding":
                    # Mismatch on custom1
                    if "custom0" in schema:
                        return "'<Super><Alt>l'"
                    if "custom1" in schema:
                        return "'<Super>F9'"
                    if "custom2" in schema:
                        return "'<Super><Alt>j'"
                    if "custom3" in schema:
                        return "'<Super><Alt>k'"
            return ""

        with patch("main_window.get_shortcut_command_prefix", return_value="narro-rsa"), \
             patch("main_window._run_gsettings_cmd", side_effect=fake_run):
            result = main_window.configure_gnome_shortcuts(force=False)
            self.assertTrue(result)
            set_calls = [c for c in calls if c[0] == "set"]
            self.assertTrue(len(set_calls) > 0)


class TestDefaultEngineUsage(unittest.TestCase):
    @patch("main_window.get_clipboard_text", return_value="Sample reading text")
    @patch("main_window.send_notification")
    @patch("main_window.generate_audio")
    @patch("main_window.popen_command")
    @patch("main_window.kill_mpv")
    @patch("narro_rsa.mpris.MPRISService")
    @patch("gi.repository.GLib.MainLoop")
    @patch("main_window.load_settings", return_value={})
    def test_main_cli_defaults_to_piper_engine(
        self, mock_settings, mock_loop_cls, mock_mpris_cls, mock_kill, mock_popen, mock_gen, mock_notify, mock_clip
    ):
        import main_window
        from narro_rsa.tts_engine import GenerationResult, EngineType
        mock_gen.return_value = GenerationResult(
            success=True,
            audio_path="/tmp/fake.wav",
            engine_name="piper",
            error_message=""
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        test_args = ["main_window.py", "--play"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main_window.main()
            self.assertEqual(cm.exception.code, 0)

            # Check that generate_audio was called with EngineType.PIPER
            mock_gen.assert_called_once()
            tts_req = mock_gen.call_args[0][0]
            self.assertEqual(tts_req.engine, EngineType.PIPER)


if __name__ == "__main__":
    unittest.main()


