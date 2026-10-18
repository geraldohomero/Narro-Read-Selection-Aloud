"""Tests for narro_rsa.voice_catalog module."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from narro_rsa.voice_catalog import (
    extract_lang_code,
    format_language_search_entry,
    fetch_edge_voices,
    fetch_piper_catalog,
    get_downloaded_piper_voices,
    get_top_edge_quick_voices,
    FALLBACK_EDGE_VOICES,
)


class TestVoiceCatalogExtraction(unittest.TestCase):
    def test_extract_lang_code_with_brackets(self):
        entry_en = "Inglês (Estados Unidos) — Ingles / English (United States) [en-US]"
        self.assertEqual(extract_lang_code(entry_en), "en-US")

        entry_pt = "Português (Brasil) — Portuguese (Brazil) [pt_BR]"
        self.assertEqual(extract_lang_code(entry_pt), "pt_BR")

        entry_zh = "Chinês (China) — Chines / Chinese (China) [zh-CN]"
        self.assertEqual(extract_lang_code(entry_zh), "zh-CN")

    def test_extract_lang_code_fallback_plain(self):
        self.assertEqual(extract_lang_code("en-US"), "en-US")
        self.assertEqual(extract_lang_code("pt_BR"), "pt_BR")
        self.assertEqual(extract_lang_code(""), "")


class TestVoiceCatalogFormatting(unittest.TestCase):
    def test_format_language_search_entry_common_languages(self):
        # pt-BR / pt_BR
        res_pt = format_language_search_entry("pt-BR")
        self.assertTrue(res_pt.endswith("[pt-BR]"))
        self.assertIn("Português", res_pt)
        self.assertIn("Brasil", res_pt)
        self.assertIn("Portuguese", res_pt)

        # en-US: search matches "ingles", "inglês", "english", "estados unidos", "en-US"
        res_en = format_language_search_entry("en-US")
        self.assertTrue(res_en.endswith("[en-US]"))
        self.assertIn("Inglês", res_en)
        self.assertIn("Ingles", res_en)
        self.assertIn("English", res_en)
        self.assertIn("Estados Unidos", res_en)

        # es-MX
        res_es = format_language_search_entry("es-MX")
        self.assertTrue(res_es.endswith("[es-MX]"))
        self.assertIn("Espanhol", res_es)
        self.assertIn("Spanish", res_es)

        # fr-FR
        res_fr = format_language_search_entry("fr-FR")
        self.assertTrue(res_fr.endswith("[fr-FR]"))
        self.assertIn("Francês", res_fr)
        self.assertIn("Frances", res_fr)
        self.assertIn("French", res_fr)

        # de-DE
        res_de = format_language_search_entry("de-DE")
        self.assertTrue(res_de.endswith("[de-DE]"))
        self.assertIn("Alemão", res_de)
        self.assertIn("Alemao", res_de)
        self.assertIn("German", res_de)

        # zh-CN
        res_zh = format_language_search_entry("zh-CN")
        self.assertTrue(res_zh.endswith("[zh-CN]"))
        self.assertIn("Chinês", res_zh)
        self.assertIn("Chines", res_zh)
        self.assertIn("Chinese", res_zh)

        # ja-JP
        res_ja = format_language_search_entry("ja-JP")
        self.assertTrue(res_ja.endswith("[ja-JP]"))
        self.assertIn("Japonês", res_ja)
        self.assertIn("Japones", res_ja)
        self.assertIn("Japanese", res_ja)

        # it-IT
        res_it = format_language_search_entry("it-IT")
        self.assertTrue(res_it.endswith("[it-IT]"))
        self.assertIn("Italiano", res_it)
        self.assertIn("Italian", res_it)

        # ru-RU
        res_ru = format_language_search_entry("ru-RU")
        self.assertTrue(res_ru.endswith("[ru-RU]"))
        self.assertIn("Russo", res_ru)
        self.assertIn("Russian", res_ru)

    def test_format_language_search_entry_unknown_code(self):
        res = format_language_search_entry("xx-YY")
        self.assertTrue(res.endswith("[xx-YY]"))

    def test_format_language_search_entry_with_piper_catalog(self):
        piper_catalog = {
            "ar_JO-kareem-medium": {
                "language": {
                    "code": "ar_JO",
                    "name_native": "العربية",
                    "name_english": "Arabic",
                    "country_english": "Jordan",
                }
            }
        }
        res = format_language_search_entry("ar_JO", piper_catalog=piper_catalog)
        self.assertTrue(res.endswith("[ar_JO]"))
        self.assertIn("Arabic", res)


class TestVoiceCatalogFetchEdge(unittest.TestCase):
    def test_fetch_edge_voices_cached(self):
        mock_voices = [{"ShortName": f"voice-{i}", "Gender": "Female", "Locale": "en-US"} for i in range(60)]
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tf:
            json.dump(mock_voices, tf)
            cache_path = tf.name

        try:
            with patch("narro_rsa.voice_catalog.EDGE_VOICES_CACHE", cache_path):
                voices = fetch_edge_voices()
                self.assertEqual(len(voices), 60)
                self.assertEqual(voices[0]["ShortName"], "voice-0")
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)

    @patch("narro_rsa.voice_catalog.load_edge_voices_cache", return_value=None)
    @patch("narro_rsa.voice_catalog.save_edge_voices_cache")
    def test_fetch_edge_voices_via_asyncio_edge_tts(self, mock_save, mock_load):
        mock_edge_tts_module = MagicMock()
        mock_voices = [{"ShortName": f"v-{i}", "Gender": "Male", "Locale": "pt-BR"} for i in range(70)]
        
        async def mock_list():
            return mock_voices

        mock_edge_tts_module.list_voices = mock_list

        with patch.dict("sys.modules", {"edge_tts": mock_edge_tts_module}):
            voices = fetch_edge_voices()
            self.assertEqual(len(voices), 70)
            mock_save.assert_called_once_with(mock_voices)

    @patch("narro_rsa.voice_catalog.load_edge_voices_cache", return_value=None)
    @patch("narro_rsa.voice_catalog.save_edge_voices_cache")
    @patch("narro_rsa.voice_catalog.run_command")
    def test_fetch_edge_voices_via_cli_fallback(self, mock_run, mock_save, mock_load):
        # Force edge_tts import to fail
        cli_output = (
            "Name                               Gender    ContentCategories      VoicePersonalities\n"
            "---------------------------------  --------  ---------------------  --------------------------------------\n"
        )
        for i in range(55):
            cli_output += f"en-US-Voice{i}Neural             Female    General                Friendly\n"

        mock_run.return_value = MagicMock(returncode=0, stdout=cli_output)

        with patch.dict("sys.modules", {"edge_tts": None}):
            voices = fetch_edge_voices()
            self.assertEqual(len(voices), 55)
            self.assertEqual(voices[0]["ShortName"], "en-US-Voice0Neural")
            self.assertEqual(voices[0]["Locale"], "en-US")
            mock_save.assert_called_once()

    @patch("narro_rsa.voice_catalog.load_edge_voices_cache", return_value=None)
    @patch("narro_rsa.voice_catalog.run_command", side_effect=Exception("No CLI"))
    @patch("narro_rsa.voice_catalog.run_on_host", side_effect=Exception("No CLI"))
    def test_fetch_edge_voices_all_fail_returns_fallback(self, mock_host, mock_run, mock_load):
        with patch.dict("sys.modules", {"edge_tts": None}):
            voices = fetch_edge_voices()
            self.assertEqual(voices, FALLBACK_EDGE_VOICES)


class TestVoiceCatalogFetchPiper(unittest.TestCase):
    def test_fetch_piper_catalog_existing(self):
        mock_data = {"pt_BR-cadu-medium": {"language": {"code": "pt_BR"}}}
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tf:
            json.dump(mock_data, tf)
            cat_path = tf.name

        try:
            with patch("narro_rsa.voice_catalog.CONFIG_DIR", os.path.dirname(cat_path)), \
                 patch("narro_rsa.voice_catalog.PIPER_CATALOG_FILE", cat_path):
                cat = fetch_piper_catalog()
                self.assertIn("pt_BR-cadu-medium", cat)
        finally:
            if os.path.exists(cat_path):
                os.unlink(cat_path)


class TestVoiceCatalogHelpers(unittest.TestCase):
    def test_get_downloaded_piper_voices(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create dummy .onnx files
            f1 = os.path.join(tmp_dir, "pt_BR-cadu-medium.onnx")
            f2 = os.path.join(tmp_dir, "en_US-amy-medium.onnx")
            open(f1, "w").close()
            open(f2, "w").close()

            with patch("narro_rsa.voice_catalog.PIPER_VOICES_DIR", tmp_dir):
                downloaded = get_downloaded_piper_voices()
                codes = [code for code, name in downloaded]
                self.assertEqual(len(codes), 2)
                self.assertIn("pt_BR-cadu-medium", codes)
                self.assertIn("en_US-amy-medium", codes)

    def test_get_top_edge_quick_voices(self):
        top_voices = get_top_edge_quick_voices()
        self.assertEqual(len(top_voices), 10)
        # Check that codes are valid strings
        for code, display in top_voices:
            self.assertTrue(len(code) > 0)
            self.assertTrue(len(display) > 0)
            self.assertIn("Neural", code)


class TestSettingsPageVoiceCatalogIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()

    @patch("narro_rsa.settings_page.fetch_edge_voices")
    @patch("narro_rsa.settings_page.fetch_piper_catalog")
    def test_settings_page_populates_formatted_languages(self, mock_piper, mock_edge):
        mock_edge.return_value = [
            {"ShortName": "en-US-AriaNeural", "Locale": "en-US"},
            {"ShortName": "pt-BR-FranciscaNeural", "Locale": "pt-BR"},
        ]
        mock_piper.return_value = {}
        from narro_rsa.settings_page import SettingsPage
        page = SettingsPage(MagicMock())
        page.current_engine = "edge-tts"
        page.edge_voices = mock_edge.return_value
        page._populate_languages()
        n = page.lang_string_list.get_n_items()
        self.assertEqual(n, 2)
        items = [page.lang_string_list.get_string(i) for i in range(n)]
        self.assertTrue(any("Inglês" in item and "[en-US]" in item for item in items))
        self.assertTrue(any("Português" in item and "[pt-BR]" in item for item in items))

    @patch("narro_rsa.settings_page.fetch_edge_voices")
    @patch("narro_rsa.settings_page.fetch_piper_catalog")
    def test_settings_page_on_dropdown_changed_extracts_real_code(self, mock_piper, mock_edge):
        mock_edge.return_value = [
            {"ShortName": "en-US-AriaNeural", "Locale": "en-US", "FriendlyName": "Aria", "Gender": "Female"},
            {"ShortName": "pt-BR-FranciscaNeural", "Locale": "pt-BR", "FriendlyName": "Francisca", "Gender": "Female"},
        ]
        mock_piper.return_value = {}
        from narro_rsa.settings_page import SettingsPage
        page = SettingsPage(MagicMock())
        page.current_engine = "edge-tts"
        page.edge_voices = mock_edge.return_value
        page._populate_languages()
        
        # Simulate selecting the en-US item in dropdown
        mock_dropdown = MagicMock()
        mock_item = MagicMock()
        mock_item.get_string.return_value = "Inglês (Estados Unidos) — Ingles / English (United States) [en-US]"
        mock_dropdown.get_selected_item.return_value = mock_item

        page._on_lang_dropdown_changed(mock_dropdown, None)
        self.assertEqual(page.selected_lang, "en-US")

        # Verify that only en-US voice is in the liststore
        iter_first = page.voice_liststore.get_iter_first()
        self.assertIsNotNone(iter_first)
        voice_code = page.voice_liststore.get_value(iter_first, 1)
        self.assertEqual(voice_code, "en-US-AriaNeural")


if __name__ == "__main__":
    unittest.main()
