"""MPRIS 2 (Media Player Remote Interfacing Specification) service for Narro-RSA.

Provides native media playback controls in GNOME Shell (Quick Settings and
Notification Center / Calendar) without disturbing desktop banner notifications.
"""

from __future__ import annotations
import os
import sys
import warnings
from typing import Callable, Optional

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib


MPRIS_INTROSPECTION_XML = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek">
      <arg direction="in" name="Offset" type="x"/>
    </method>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
"""


class MPRISService:
    """Manages the MPRIS 2 D-Bus interface for Narro-RSA."""

    def __init__(
        self,
        app_id: str = "com.github.geraldohomero.NarroRsa",
        identity: str = "Narro-RSA",
        on_play: Optional[Callable[[], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_raise: Optional[Callable[[], None]] = None,
    ):
        self.app_id = app_id
        self.identity = identity
        self.bus_name = f"org.mpris.MediaPlayer2.{app_id}"
        self.on_play = on_play
        self.on_pause = on_pause
        self.on_play_pause = on_play_pause
        self.on_stop = on_stop
        self.on_raise = on_raise

        self._playback_status: str = "Stopped"
        self._title: str = ""
        self._text: str = ""
        self._speed: float = 1.0

        self._connection: Optional[Gio.DBusConnection] = None
        self._owner_id: int = 0
        self._registration_ids: list[int] = []
        self._node_info: Optional[Gio.DBusNodeInfo] = None

        try:
            self._node_info = Gio.DBusNodeInfo.new_for_xml(MPRIS_INTROSPECTION_XML)
        except Exception as e:
            warnings.warn(f"Failed to parse MPRIS XML: {e}")

    @property
    def playback_status(self) -> str:
        return self._playback_status

    @property
    def is_published(self) -> bool:
        return self._owner_id != 0 or len(self._registration_ids) > 0

    def publish(self, title: str = "", text: str = "", speed: float = 1.0) -> bool:
        """Publishes the MPRIS service on the session bus."""
        self._playback_status = "Playing"
        self._speed = speed
        self._title = title or (text[:80].strip() if text else "Narro-RSA")
        self._text = text

        if self.is_published:
            self.emit_playback_status_changed()
            self.emit_metadata_changed()
            return True

        if not self._node_info:
            return False

        try:
            if not self._connection:
                self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception as e:
            # Session bus not available (e.g. sandbox or test environment)
            return False

        try:
            for iface_info in self._node_info.interfaces:
                reg_id = self._connection.register_object(
                    "/org/mpris/MediaPlayer2",
                    iface_info,
                    self._on_method_call,
                    self._on_get_property,
                    self._on_set_property,
                )
                self._registration_ids.append(reg_id)

            flags = (
                Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT
                | Gio.BusNameOwnerFlags.REPLACE
            )
            self._owner_id = Gio.bus_own_name_on_connection(
                self._connection,
                self.bus_name,
                flags,
                self._on_name_acquired,
                self._on_name_lost,
            )
            return True
        except Exception as e:
            self.unpublish()
            return False

    def unpublish(self) -> None:
        """Unregisters D-Bus objects and releases the well-known bus name."""
        self._playback_status = "Stopped"
        if self._connection and self._registration_ids:
            try:
                self.emit_playback_status_changed()
            except Exception:
                pass

        if self._owner_id != 0:
            try:
                Gio.bus_unown_name(self._owner_id)
            except Exception:
                pass
            self._owner_id = 0

        if self._connection:
            for reg_id in self._registration_ids:
                try:
                    self._connection.unregister_object(reg_id)
                except Exception:
                    pass
            self._registration_ids.clear()

    def set_playback_status(self, status: str) -> None:
        """Updates playback status ('Playing', 'Paused', or 'Stopped')."""
        if self._playback_status == status:
            return
        self._playback_status = status
        self.emit_playback_status_changed()

    def set_metadata(self, text: str, title: str = "") -> None:
        """Updates track metadata and text preview."""
        self._text = text
        self._title = title or (text[:80].strip() if text else "Narro-RSA")
        self.emit_metadata_changed()

    def emit_playback_status_changed(self) -> None:
        """Notifies GNOME Shell of a playback status change."""
        self._emit_properties_changed({
            "PlaybackStatus": GLib.Variant("s", self._playback_status)
        })

    def emit_metadata_changed(self) -> None:
        """Notifies GNOME Shell of updated metadata."""
        self._emit_properties_changed({
            "Metadata": self._build_metadata_variant()
        })

    def _build_metadata_variant(self) -> GLib.Variant:
        title_text = self._title or self.identity
        metadata = {
            "mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/CurrentTrack"),
            "xesam:title": GLib.Variant("s", title_text),
            "xesam:artist": GLib.Variant("as", [self.identity]),
            "xesam:album": GLib.Variant("s", "Narro-RSA TTS"),
        }
        return GLib.Variant("a{sv}", metadata)

    def _emit_properties_changed(self, changed_dict: dict[str, GLib.Variant]) -> None:
        if not self._connection or not self._registration_ids:
            return
        try:
            params = GLib.Variant(
                "(sa{sv}as)",
                (
                    "org.mpris.MediaPlayer2.Player",
                    changed_dict,
                    [],
                ),
            )
            self._connection.emit_signal(
                None,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                params,
            )
        except Exception:
            pass

    def _on_name_acquired(self, conn, name: str) -> None:
        pass

    def _on_name_lost(self, conn, name: str) -> None:
        pass

    def _on_method_call(
        self,
        connection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters,
        invocation,
    ) -> None:
        try:
            if interface_name == "org.mpris.MediaPlayer2":
                if method_name == "Raise":
                    if self.on_raise:
                        self.on_raise()
                elif method_name == "Quit":
                    if self.on_stop:
                        self.on_stop()
                    self.unpublish()

            elif interface_name == "org.mpris.MediaPlayer2.Player":
                if method_name == "Play":
                    if self.on_play:
                        self.on_play()
                    self.set_playback_status("Playing")
                elif method_name == "Pause":
                    if self.on_pause:
                        self.on_pause()
                    self.set_playback_status("Paused")
                elif method_name == "PlayPause":
                    if self.on_play_pause:
                        self.on_play_pause()
                    elif self._playback_status == "Paused":
                        if self.on_play:
                            self.on_play()
                        self.set_playback_status("Playing")
                    else:
                        if self.on_pause:
                            self.on_pause()
                        self.set_playback_status("Paused")
                elif method_name == "Stop":
                    if self.on_stop:
                        self.on_stop()
                    self.set_playback_status("Stopped")
                    self.unpublish()
        finally:
            invocation.return_value(None)

    def _on_get_property(
        self,
        connection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        if interface_name == "org.mpris.MediaPlayer2":
            if property_name == "Identity":
                return GLib.Variant("s", self.identity)
            if property_name == "CanQuit":
                return GLib.Variant("b", True)
            if property_name == "CanRaise":
                return GLib.Variant("b", self.on_raise is not None)
            if property_name == "HasTrackList":
                return GLib.Variant("b", False)
            if property_name in ("SupportedUriSchemes", "SupportedMimeTypes"):
                return GLib.Variant("as", [])

        elif interface_name == "org.mpris.MediaPlayer2.Player":
            if property_name == "PlaybackStatus":
                return GLib.Variant("s", self._playback_status)
            if property_name == "Rate":
                return GLib.Variant("d", self._speed)
            if property_name == "Metadata":
                return self._build_metadata_variant()
            if property_name == "Volume":
                return GLib.Variant("d", 1.0)
            if property_name == "Position":
                return GLib.Variant("x", 0)
            if property_name == "MinimumRate":
                return GLib.Variant("d", 0.5)
            if property_name == "MaximumRate":
                return GLib.Variant("d", 4.0)
            if property_name in ("CanGoNext", "CanGoPrevious", "CanSeek"):
                return GLib.Variant("b", False)
            if property_name in ("CanPlay", "CanPause", "CanControl"):
                return GLib.Variant("b", True)

        return None

    def _on_set_property(
        self,
        connection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
    ) -> bool:
        if interface_name == "org.mpris.MediaPlayer2.Player":
            if property_name == "Rate":
                self._speed = value.get_double()
                return True
        return False
