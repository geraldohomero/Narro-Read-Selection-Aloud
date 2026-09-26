"""Unit tests for MPRIS service in Narro-RSA."""

import unittest
from unittest.mock import MagicMock, patch
import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib


class TestMPRISService(unittest.TestCase):
    def test_mpris_xml_valid(self):
        """Test that the MPRIS XML introspection definition is syntactically valid."""
        from narro_rsa.mpris import MPRIS_INTROSPECTION_XML
        node = Gio.DBusNodeInfo.new_for_xml(MPRIS_INTROSPECTION_XML)
        self.assertIsNotNone(node)
        interface_names = [iface.name for iface in node.interfaces]
        self.assertIn("org.mpris.MediaPlayer2", interface_names)
        self.assertIn("org.mpris.MediaPlayer2.Player", interface_names)

    def test_mpris_service_initial_state(self):
        """Test initial state of MPRISService."""
        from narro_rsa.mpris import MPRISService
        service = MPRISService()
        self.assertEqual(service.playback_status, "Stopped")
        self.assertFalse(service.is_published)

    def test_mpris_get_property_media_player2(self):
        """Test getting properties from org.mpris.MediaPlayer2 interface."""
        from narro_rsa.mpris import MPRISService
        service = MPRISService(identity="Test-Narro")
        prop_val = service._on_get_property(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", "Identity")
        self.assertEqual(prop_val.unpack(), "Test-Narro")

        can_quit = service._on_get_property(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", "CanQuit")
        self.assertTrue(can_quit.unpack())

        has_tracklist = service._on_get_property(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", "HasTrackList")
        self.assertFalse(has_tracklist.unpack())

    def test_mpris_get_property_player(self):
        """Test getting properties from org.mpris.MediaPlayer2.Player interface."""
        from narro_rsa.mpris import MPRISService
        service = MPRISService()
        service.set_playback_status("Playing")
        service.set_metadata("This is a test speech synthesis preview text.")

        status = service._on_get_property(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "PlaybackStatus")
        self.assertEqual(status.unpack(), "Playing")

        metadata = service._on_get_property(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Metadata")
        unpacked_meta = metadata.unpack()
        self.assertIn("xesam:title", unpacked_meta)
        self.assertEqual(unpacked_meta["xesam:title"], "This is a test speech synthesis preview text.")
        self.assertIn("xesam:artist", unpacked_meta)
        self.assertEqual(unpacked_meta["xesam:artist"], ["Narro-RSA"])
        self.assertIn("mpris:trackid", unpacked_meta)

    def test_mpris_method_calls(self):
        """Test handling of method calls on org.mpris.MediaPlayer2.Player."""
        from narro_rsa.mpris import MPRISService
        on_play = MagicMock()
        on_pause = MagicMock()
        on_stop = MagicMock()
        on_play_pause = MagicMock()

        service = MPRISService(
            on_play=on_play,
            on_pause=on_pause,
            on_play_pause=on_play_pause,
            on_stop=on_stop
        )

        mock_invocation = MagicMock()

        # Play
        service._on_method_call(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Play", None, mock_invocation)
        on_play.assert_called_once()
        self.assertEqual(service.playback_status, "Playing")

        # Pause
        service._on_method_call(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Pause", None, mock_invocation)
        on_pause.assert_called_once()
        self.assertEqual(service.playback_status, "Paused")

        # PlayPause
        service._on_method_call(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "PlayPause", None, mock_invocation)
        on_play_pause.assert_called_once()

        # Stop
        service._on_method_call(None, None, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Stop", None, mock_invocation)
        on_stop.assert_called_once()
        self.assertEqual(service.playback_status, "Stopped")

    def test_mpris_publish_and_unpublish(self):
        """Test publish and unpublish flow with mocked connection."""
        from narro_rsa.mpris import MPRISService

        mock_connection = MagicMock()
        mock_connection.register_object.side_effect = [101, 102]

        with patch("gi.repository.Gio.bus_get_sync", return_value=mock_connection):
            with patch("gi.repository.Gio.bus_own_name_on_connection", return_value=201) as mock_own:
                service = MPRISService()
                success = service.publish(title="Test preview", text="Full text sample")
                self.assertTrue(success)
                self.assertTrue(service.is_published)
                self.assertEqual(service.playback_status, "Playing")
                mock_own.assert_called_once()

                # Unpublish
                with patch("gi.repository.Gio.bus_unown_name") as mock_unown:
                    service.unpublish()
                    self.assertFalse(service.is_published)
                    self.assertEqual(service.playback_status, "Stopped")
                    mock_unown.assert_called_once_with(201)
                    self.assertEqual(mock_connection.unregister_object.call_count, 2)


if __name__ == "__main__":
    unittest.main()
