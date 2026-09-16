"""Unit tests for intelligent clipboard resolution in Narro-RSA."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import narro_rsa.clipboard as clip


class TestClipboardResolution(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        clip.LAST_CLIPBOARD_FILE = os.path.join(self.tmpdir.name, "last_clip.txt")
        clip.LAST_PRIMARY_FILE = os.path.join(self.tmpdir.name, "last_prim.txt")
        clip.LAST_READ_FILE = os.path.join(self.tmpdir.name, "last_read.txt")

    def _write_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_zotero_copy_overrides_stale_primary(self):
        """User copies new text in Zotero/Okular (Ctrl+C). Primary holds stale selection."""
        self._write_file(clip.LAST_CLIPBOARD_FILE, "Old text")
        self._write_file(clip.LAST_PRIMARY_FILE, "Stale selection")
        self._write_file(clip.LAST_READ_FILE, "Old text")

        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if any("primary" in arg for arg in cmd):
                mock.stdout = "Stale selection"
            else:
                mock.stdout = "New text copied from Zotero"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            # User presses Ctrl+\ (passes primary=True)
            result = clip.get_clipboard_text(primary=True)
            self.assertEqual(result, "New text copied from Zotero")

    def test_web_selection_overrides_old_clipboard(self):
        """User selects new text in browser without Ctrl+C. Clipboard holds old text."""
        self._write_file(clip.LAST_CLIPBOARD_FILE, "Old clipboard")
        self._write_file(clip.LAST_PRIMARY_FILE, "Old selection")
        self._write_file(clip.LAST_READ_FILE, "Old clipboard")

        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if any("primary" in arg for arg in cmd):
                mock.stdout = "Fresh web selection"
            else:
                mock.stdout = "Old clipboard"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            # User presses Ctrl+\ (passes primary=True)
            result = clip.get_clipboard_text(primary=True)
            self.assertEqual(result, "Fresh web selection")

    def test_both_same_text(self):
        """When user copies in browser, both primary and clipboard have same text."""
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "Identical text"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            result = clip.get_clipboard_text(primary=True)
            self.assertEqual(result, "Identical text")

    def test_rereading_same_text(self):
        """When user triggers shortcut again without new changes, re-reads existing text."""
        self._write_file(clip.LAST_CLIPBOARD_FILE, "Current text")
        self._write_file(clip.LAST_PRIMARY_FILE, "Current text")
        self._write_file(clip.LAST_READ_FILE, "Current text")

        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "Current text"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            result = clip.get_clipboard_text(primary=True)
            self.assertEqual(result, "Current text")

    def test_empty_both(self):
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = ""
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            self.assertEqual(clip.get_clipboard_text(primary=True), "")
            self.assertEqual(clip.get_clipboard_text(primary=False), "")

    def test_only_clipboard_has_text(self):
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "" if any("primary" in arg for arg in cmd) else "Only clip"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            self.assertEqual(clip.get_clipboard_text(primary=True), "Only clip")
            self.assertEqual(clip.get_clipboard_text(primary=False), "Only clip")

    def test_only_primary_has_text(self):
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "Only prim" if any("primary" in arg for arg in cmd) else ""
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            self.assertEqual(clip.get_clipboard_text(primary=True), "Only prim")
            self.assertEqual(clip.get_clipboard_text(primary=False), "Only prim")

    def test_first_run_zotero_copy_vs_last_read(self):
        """On first check where no snapshot exists, but last_read matches old primary."""
        self._write_file(clip.LAST_READ_FILE, "Old selection")

        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "Old selection" if any("primary" in arg for arg in cmd) else "Zotero copy"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            self.assertEqual(clip.get_clipboard_text(primary=True), "Zotero copy")


    def test_zotero_simulate_copy_when_neither_changed(self):
        """User has selected text in Zotero (neither buffer changed). _simulate_copy triggers new clipboard text."""
        self._write_file(clip.LAST_CLIPBOARD_FILE, "Old text")
        self._write_file(clip.LAST_PRIMARY_FILE, "Old text")
        self._write_file(clip.LAST_READ_FILE, "Old text")

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            mock = MagicMock()
            mock.returncode = 0
            if any("python3" in arg for arg in cmd):
                call_count += 1
                mock.stdout = "OK"
                return mock
            if any("primary" in arg for arg in cmd):
                mock.stdout = "Old text"
            else:
                # Before simulation, clipboard is "Old text"; after simulation, it updates to "Copied from Zotero"
                mock.stdout = "Copied from Zotero" if call_count > 0 else "Old text"
            return mock

        with patch("narro_rsa.clipboard.run_on_host", side_effect=mock_run):
            result = clip.get_clipboard_text(primary=True)
            self.assertEqual(result, "Copied from Zotero")
            self.assertGreater(call_count, 0)


if __name__ == "__main__":
    unittest.main()
