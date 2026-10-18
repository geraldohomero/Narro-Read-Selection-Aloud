"""Voice catalog management and language search formatting for Narro-RSA."""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
from typing import Any

from narro_rsa.constants import (
    CONFIG_DIR,
    EDGE_TTS_BIN,
    EDGE_VOICES_CACHE,
    PIPER_VOICES_DIR,
)
from narro_rsa.subprocess_helper import run_command, run_on_host

PIPER_CATALOG_FILE: str = os.path.join(CONFIG_DIR, "piper_voices.json")

# Fallback Edge-TTS voices if completely offline on first launch
FALLBACK_EDGE_VOICES: list[dict[str, Any]] = [
    {"ShortName": "pt-BR-AntonioNeural", "Gender": "Male", "FriendlyName": "Microsoft Antonio Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-BR-FranciscaNeural", "Gender": "Female", "FriendlyName": "Microsoft Francisca Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-BR-ThalitaMultilingualNeural", "Gender": "Female", "FriendlyName": "Microsoft Thalita Online (Natural) - Portuguese (Brazil)", "Locale": "pt-BR"},
    {"ShortName": "pt-PT-DuarteNeural", "Gender": "Male", "FriendlyName": "Microsoft Duarte Online (Natural) - Portuguese (Portugal)", "Locale": "pt-PT"},
    {"ShortName": "pt-PT-RaquelNeural", "Gender": "Female", "FriendlyName": "Microsoft Raquel Online (Natural) - Portuguese (Portugal)", "Locale": "pt-PT"},
    {"ShortName": "en-US-AriaNeural", "Gender": "Female", "FriendlyName": "Microsoft Aria Online (Natural) - English (United States)", "Locale": "en-US"},
    {"ShortName": "en-US-GuyNeural", "Gender": "Male", "FriendlyName": "Microsoft Guy Online (Natural) - English (United States)", "Locale": "en-US"},
    {"ShortName": "es-ES-AlvaroNeural", "Gender": "Male", "FriendlyName": "Microsoft Alvaro Online (Natural) - Spanish (Spain)", "Locale": "es-ES"},
    {"ShortName": "es-ES-ElviraNeural", "Gender": "Female", "FriendlyName": "Microsoft Elvira Online (Natural) - Spanish (Spain)", "Locale": "es-ES"},
    {"ShortName": "fr-FR-HenriNeural", "Gender": "Male", "FriendlyName": "Microsoft Henri Online (Natural) - French (France)", "Locale": "fr-FR"},
    {"ShortName": "de-DE-ConradNeural", "Gender": "Male", "FriendlyName": "Microsoft Conrad Online (Natural) - German (Germany)", "Locale": "de-DE"}
]

# Comprehensive multilingual language name mappings
# Keys support both hyphen ('en-US') and underscore ('en_US')
LANGUAGE_NAMES_MAP: dict[str, str] = {
    # Portuguese
    "pt-BR": "Português (Brasil) — Portugues / Portuguese (Brazil)",
    "pt_BR": "Português (Brasil) — Portugues / Portuguese (Brazil)",
    "pt-PT": "Português (Portugal) — Portugues / Portuguese (Portugal)",
    "pt_PT": "Português (Portugal) — Portugues / Portuguese (Portugal)",

    # English
    "en-US": "Inglês (Estados Unidos) — Ingles / English (United States)",
    "en_US": "Inglês (Estados Unidos) — Ingles / English (United States)",
    "en-GB": "Inglês (Reino Unido) — Ingles / English (United Kingdom)",
    "en_GB": "Inglês (Reino Unido) — Ingles / English (United Kingdom)",
    "en-AU": "Inglês (Austrália) — Ingles / English (Australia)",
    "en_AU": "Inglês (Austrália) — Ingles / English (Australia)",
    "en-CA": "Inglês (Canadá) — Ingles / English (Canada)",
    "en_CA": "Inglês (Canadá) — Ingles / English (Canada)",
    "en-IE": "Inglês (Irlanda) — Ingles / English (Ireland)",
    "en_IE": "Inglês (Irlanda) — Ingles / English (Ireland)",
    "en-IN": "Inglês (Índia) — Ingles / English (India)",
    "en_IN": "Inglês (Índia) — Ingles / English (India)",
    "en-NZ": "Inglês (Nova Zelândia) — Ingles / English (New Zealand)",
    "en_NZ": "Inglês (Nova Zelândia) — Ingles / English (New Zealand)",
    "en-ZA": "Inglês (África do Sul) — Ingles / English (South Africa)",
    "en_ZA": "Inglês (África do Sul) — Ingles / English (South Africa)",
    "en-SG": "Inglês (Singapura) — Ingles / English (Singapore)",
    "en-PH": "Inglês (Filipinas) — Ingles / English (Philippines)",
    "en-HK": "Inglês (Hong Kong) — Ingles / English (Hong Kong)",
    "en-KE": "Inglês (Quênia) — Ingles / English (Kenya)",
    "en-NG": "Inglês (Nigéria) — Ingles / English (Nigeria)",
    "en-TZ": "Inglês (Tanzânia) — Ingles / English (Tanzania)",

    # Spanish
    "es-ES": "Espanhol (Espanha) — Spanish (Spain)",
    "es_ES": "Espanhol (Espanha) — Spanish (Spain)",
    "es-MX": "Espanhol (México) — Espanhol / Spanish (Mexico)",
    "es_MX": "Espanhol (México) — Espanhol / Spanish (Mexico)",
    "es-AR": "Espanhol (Argentina) — Spanish (Argentina)",
    "es_AR": "Espanhol (Argentina) — Spanish (Argentina)",
    "es-CO": "Espanhol (Colômbia) — Colombia / Spanish (Colombia)",
    "es_CO": "Espanhol (Colômbia) — Colombia / Spanish (Colombia)",
    "es-CL": "Espanhol (Chile) — Spanish (Chile)",
    "es_CL": "Espanhol (Chile) — Spanish (Chile)",
    "es-US": "Espanhol (Estados Unidos) — Spanish (United States)",
    "es_US": "Espanhol (Estados Unidos) — Spanish (United States)",
    "es-PE": "Espanhol (Peru) — Spanish (Peru)",
    "es-VE": "Espanhol (Venezuela) — Spanish (Venezuela)",
    "es-UY": "Espanhol (Uruguai) — Spanish (Uruguay)",
    "es-BO": "Espanhol (Bolívia) — Spanish (Bolivia)",
    "es-CR": "Espanhol (Costa Rica) — Spanish (Costa Rica)",
    "es-CU": "Espanhol (Cuba) — Spanish (Cuba)",
    "es-DO": "Espanhol (República Dominicana) — Spanish (Dominican Republic)",
    "es-EC": "Espanhol (Equador) — Spanish (Ecuador)",
    "es-GT": "Espanhol (Guatemala) — Spanish (Guatemala)",
    "es-HN": "Espanhol (Honduras) — Spanish (Honduras)",
    "es-NI": "Espanhol (Nicarágua) — Spanish (Nicaragua)",
    "es-PA": "Espanhol (Panamá) — Spanish (Panama)",
    "es-PR": "Espanhol (Porto Rico) — Spanish (Puerto Rico)",
    "es-PY": "Espanhol (Paraguai) — Spanish (Paraguay)",
    "es-SV": "Espanhol (El Salvador) — Spanish (El Salvador)",

    # French
    "fr-FR": "Francês (França) — Frances / French (France)",
    "fr_FR": "Francês (França) — Frances / French (France)",
    "fr-CA": "Francês (Canadá) — Frances / French (Canada)",
    "fr_CA": "Francês (Canadá) — Frances / French (Canada)",
    "fr-BE": "Francês (Bélgica) — Frances / French (Belgium)",
    "fr_BE": "Francês (Bélgica) — Frances / French (Belgium)",
    "fr-CH": "Francês (Suíça) — Frances / French (Switzerland)",
    "fr_CH": "Francês (Suíça) — Frances / French (Switzerland)",

    # German
    "de-DE": "Alemão (Alemanha) — Alemao / German (Germany)",
    "de_DE": "Alemão (Alemanha) — Alemao / German (Germany)",
    "de-AT": "Alemão (Áustria) — Alemao / German (Austria)",
    "de_AT": "Alemão (Áustria) — Alemao / German (Austria)",
    "de-CH": "Alemão (Suíça) — Alemao / German (Switzerland)",
    "de_CH": "Alemão (Suíça) — Alemao / German (Switzerland)",

    # Italian
    "it-IT": "Italiano (Itália) — Italian (Italy)",
    "it_IT": "Italiano (Itália) — Italian (Italy)",

    # Russian
    "ru-RU": "Russo (Rússia) — Russian (Russia)",
    "ru_RU": "Russo (Rússia) — Russian (Russia)",

    # Chinese
    "zh-CN": "Chinês (China) — Chines / Chinese (China) [中文/普通话]",
    "zh_CN": "Chinês (China) — Chines / Chinese (China) [中文/普通话]",
    "zh-TW": "Chinês (Taiwan) — Chines / Chinese (Taiwan) [国语/國語]",
    "zh_TW": "Chinês (Taiwan) — Chines / Chinese (Taiwan) [国语/國語]",
    "zh-HK": "Chinês (Hong Kong) — Chines / Chinese (Hong Kong) [粤语/廣東話]",
    "zh_HK": "Chinês (Hong Kong) — Chines / Chinese (Hong Kong) [粤语/廣東話]",

    # Japanese & Korean
    "ja-JP": "Japonês (Japão) — Japones / Japanese (Japan)",
    "ja_JP": "Japonês (Japão) — Japones / Japanese (Japan)",
    "ko-KR": "Coreano (Coreia do Sul) — Korean (South Korea)",
    "ko_KR": "Coreano (Coreia do Sul) — Korean (South Korea)",

    # Arabic
    "ar-SA": "Árabe (Arábia Saudita) — Arabe / Arabic (Saudi Arabia)",
    "ar_SA": "Árabe (Arábia Saudita) — Arabe / Arabic (Saudi Arabia)",
    "ar-EG": "Árabe (Egito) — Arabe / Arabic (Egypt)",
    "ar_EG": "Árabe (Egito) — Arabe / Arabic (Egypt)",
    "ar-AE": "Árabe (Emirados Árabes) — Arabe / Arabic (UAE)",
    "ar_AE": "Árabe (Emirados Árabes) — Arabe / Arabic (UAE)",
    "ar-JO": "Árabe (Jordânia) — Arabe / Arabic (Jordan)",
    "ar_JO": "Árabe (Jordânia) — Arabe / Arabic (Jordan)",

    # European languages
    "nl-NL": "Holandês (Holanda) — Holandes / Dutch (Netherlands)",
    "nl_NL": "Holandês (Holanda) — Holandes / Dutch (Netherlands)",
    "nl-BE": "Holandês (Bélgica) — Holandes / Dutch (Belgium)",
    "nl_BE": "Holandês (Bélgica) — Holandes / Dutch (Belgium)",
    "pl-PL": "Polonês (Polônia) — Polones / Polish (Poland)",
    "pl_PL": "Polonês (Polônia) — Polones / Polish (Poland)",
    "sv-SE": "Sueco (Suécia) — Swedish (Sweden)",
    "sv_SE": "Sueco (Suécia) — Swedish (Sweden)",
    "da-DK": "Dinamarquês (Dinamarca) — Dinamarques / Danish (Denmark)",
    "da_DK": "Dinamarquês (Dinamarca) — Dinamarques / Danish (Denmark)",
    "fi-FI": "Finlandês (Finlândia) — Finlandes / Finnish (Finland)",
    "fi_FI": "Finlandês (Finlândia) — Finlandes / Finnish (Finland)",
    "nb-NO": "Norueguês (Noruega) — Noruegues / Norwegian (Norway)",
    "no-NO": "Norueguês (Noruega) — Noruegues / Norwegian (Norway)",
    "no_NO": "Norueguês (Noruega) — Noruegues / Norwegian (Norway)",
    "tr-TR": "Turco (Turquia) — Turkish (Turkey)",
    "tr_TR": "Turco (Turquia) — Turkish (Turkey)",
    "uk-UA": "Ucraniano (Ucrânia) — Ukrainian (Ukraine)",
    "uk_UA": "Ucraniano (Ucrânia) — Ukrainian (Ukraine)",
    "el-GR": "Grego (Grécia) — Greek (Greece)",
    "el_GR": "Grego (Grécia) — Greek (Greece)",
    "cs-CZ": "Tcheco (República Tcheca) — Czech (Czech Republic)",
    "cs_CZ": "Tcheco (República Tcheca) — Czech (Czech Republic)",
    "hu-HU": "Húngaro (Hungria) — Hungaro / Hungarian (Hungary)",
    "hu_HU": "Húngaro (Hungria) — Hungaro / Hungarian (Hungary)",
    "ro-RO": "Romeno (Romênia) — Romanian (Romania)",
    "ro_RO": "Romeno (Romênia) — Romanian (Romania)",
    "ca-ES": "Catalão (Espanha) — Catalao / Catalan (Spain)",
    "ca_ES": "Catalão (Espanha) — Catalao / Catalan (Spain)",

    # Asian languages
    "hi-IN": "Hindi (Índia) — Hindi (India)",
    "hi_IN": "Hindi (Índia) — Hindi (India)",
    "id-ID": "Indonésio (Indonésia) — Indonesio / Indonesian (Indonesia)",
    "id_ID": "Indonésio (Indonésia) — Indonesio / Indonesian (Indonesia)",
    "th-TH": "Tailandês (Tailândia) — Tailandes / Thai (Thailand)",
    "th_TH": "Tailandês (Tailândia) — Tailandes / Thai (Thailand)",
    "vi-VN": "Vietnamita (Vietnã) — Vietnamese (Vietnam)",
    "vi_VN": "Vietnamita (Vietnã) — Vietnamese (Vietnam)",
}

# Base language code mappings for fallback formatting
BASE_LANGUAGES: dict[str, tuple[str, str, str]] = {
    "af": ("Africâner", "Africaner", "Afrikaans"),
    "am": ("Amárico", "Amarico", "Amharic"),
    "ar": ("Árabe", "Arabe", "Arabic"),
    "az": ("Azeri", "Azeri", "Azerbaijani"),
    "bg": ("Búlgaro", "Bulgaro", "Bulgarian"),
    "bn": ("Bengali", "Bengali", "Bengali"),
    "bs": ("Bósnio", "Bosnio", "Bosnian"),
    "ca": ("Catalão", "Catalao", "Catalan"),
    "cs": ("Tcheco", "Tcheco", "Czech"),
    "cy": ("Galês", "Gales", "Welsh"),
    "da": ("Dinamarquês", "Dinamarques", "Danish"),
    "de": ("Alemão", "Alemao", "German"),
    "el": ("Grego", "Grego", "Greek"),
    "en": ("Inglês", "Ingles", "English"),
    "es": ("Espanhol", "Espanhol", "Spanish"),
    "et": ("Estoniano", "Estoniano", "Estonian"),
    "eu": ("Basco", "Basco", "Basque"),
    "fa": ("Persa", "Persa", "Persian"),
    "fi": ("Finlandês", "Finlandes", "Finnish"),
    "fil": ("Filipino", "Filipino", "Filipino"),
    "fr": ("Francês", "Frances", "French"),
    "ga": ("Irlandês", "Irlandes", "Irish"),
    "gl": ("Galego", "Galego", "Galician"),
    "gu": ("Guzerate", "Guzerate", "Gujarati"),
    "he": ("Hebraico", "Hebraico", "Hebrew"),
    "hi": ("Hindi", "Hindi", "Hindi"),
    "hr": ("Croata", "Croata", "Croatian"),
    "hu": ("Húngaro", "Hungaro", "Hungarian"),
    "hy": ("Armênio", "Armenio", "Armenian"),
    "id": ("Indonésio", "Indonesio", "Indonesian"),
    "is": ("Islandês", "Islandes", "Icelandic"),
    "it": ("Italiano", "Italiano", "Italian"),
    "ja": ("Japonês", "Japones", "Japanese"),
    "jv": ("Javanês", "Javanes", "Javanese"),
    "ka": ("Georgiano", "Georgiano", "Georgian"),
    "kk": ("Cazaque", "Cazaque", "Kazakh"),
    "km": ("Khmer", "Khmer", "Khmer"),
    "kn": ("Canarês", "Canares", "Kannada"),
    "ko": ("Coreano", "Coreano", "Korean"),
    "lo": ("Laosiano", "Laosiano", "Lao"),
    "lt": ("Lituano", "Lituano", "Lithuanian"),
    "lv": ("Letão", "Letao", "Latvian"),
    "mk": ("Macedônio", "Macedonio", "Macedonian"),
    "ml": ("Malaiala", "Malaiala", "Malayalam"),
    "mn": ("Mongol", "Mongol", "Mongolian"),
    "mr": ("Marata", "Marata", "Marathi"),
    "ms": ("Malaio", "Malaio", "Malay"),
    "mt": ("Maltês", "Maltes", "Maltese"),
    "my": ("Birmanês", "Birmanes", "Burmese"),
    "nb": ("Norueguês", "Noruegues", "Norwegian"),
    "ne": ("Nepalês", "Nepales", "Nepali"),
    "nl": ("Holandês", "Holandes", "Dutch"),
    "nn": ("Norueguês", "Noruegues", "Norwegian"),
    "no": ("Norueguês", "Noruegues", "Norwegian"),
    "pl": ("Polonês", "Polones", "Polish"),
    "ps": ("Pashto", "Pashto", "Pashto"),
    "pt": ("Português", "Portugues", "Portuguese"),
    "ro": ("Romeno", "Romeno", "Romanian"),
    "ru": ("Russo", "Russo", "Russian"),
    "si": ("Cingalês", "Cingales", "Sinhala"),
    "sk": ("Eslovaco", "Eslovaco", "Slovak"),
    "sl": ("Esloveno", "Esloveno", "Slovenian"),
    "so": ("Somali", "Somali", "Somali"),
    "sq": ("Albanês", "Albanes", "Albanian"),
    "sr": ("Sérvio", "Servio", "Serbian"),
    "su": ("Sundanês", "Sundanes", "Sundanese"),
    "sv": ("Sueco", "Sueco", "Swedish"),
    "sw": ("Suaíli", "Suaili", "Swahili"),
    "ta": ("Tâmil", "Tamil", "Tamil"),
    "te": ("Telugu", "Telugu", "Telugu"),
    "th": ("Tailandês", "Tailandes", "Thai"),
    "tr": ("Turco", "Turco", "Turkish"),
    "uk": ("Ucraniano", "Ucraniano", "Ukrainian"),
    "ur": ("Urdu", "Urdu", "Urdu"),
    "uz": ("Uzbeque", "Uzbeque", "Uzbek"),
    "vi": ("Vietnamita", "Vietnamita", "Vietnamese"),
    "zh": ("Chinês", "Chines", "Chinese"),
    "zu": ("Zulu", "Zulu", "Zulu"),
}


def load_edge_voices_cache() -> list[dict[str, Any]] | None:
    """Carrega o cache local de vozes Edge-TTS se for válido e tiver ao menos 50 vozes."""
    try:
        if os.path.exists(EDGE_VOICES_CACHE):
            with open(EDGE_VOICES_CACHE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list) and len(data) >= 50:
                    return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_edge_voices_cache(voices: list[dict[str, Any]]) -> None:
    """Salva o cache local de vozes Edge-TTS."""
    try:
        os.makedirs(os.path.dirname(EDGE_VOICES_CACHE), exist_ok=True)
        with open(EDGE_VOICES_CACHE, "w", encoding="utf-8") as fh:
            json.dump(voices, fh, ensure_ascii=False)
    except OSError:
        pass


def extract_lang_code(formatted_entry: str) -> str:
    """Extracts the language code from a formatted search entry.

    E.g. 'Inglês (Estados Unidos) — Ingles / English (United States) [en-US]' -> 'en-US'
         'Português (Brasil) — Portuguese (Brazil) [pt_BR]' -> 'pt_BR'
    """
    if not formatted_entry:
        return ""
    entry = formatted_entry.strip()
    if "[" in entry and entry.endswith("]"):
        return entry[entry.rfind("[") + 1 : -1].strip()
    return entry


def format_language_search_entry(lang_code: str, piper_catalog: dict | None = None) -> str:
    """Formats a language entry for Gtk.DropDown search.

    Formats as: '{localized_names} [{lang_code}]'
    Allows matching by Portuguese (accented/unaccented), English, and country/code.
    """
    if not lang_code:
        return ""

    # 1. Exact match in pre-defined comprehensive dictionary
    if lang_code in LANGUAGE_NAMES_MAP:
        return f"{LANGUAGE_NAMES_MAP[lang_code]} [{lang_code}]"

    alt_code = lang_code.replace("_", "-") if "_" in lang_code else lang_code.replace("-", "_")
    if alt_code in LANGUAGE_NAMES_MAP:
        return f"{LANGUAGE_NAMES_MAP[alt_code]} [{lang_code}]"

    # 2. Check piper_catalog language metadata if available
    if piper_catalog:
        for voice_info in piper_catalog.values():
            lang_info = voice_info.get("language", {})
            if lang_info.get("code") in (lang_code, alt_code):
                name_native = lang_info.get("name_native", "")
                name_english = lang_info.get("name_english", "")
                country_english = lang_info.get("country_english", "")
                parts = []
                if name_native and name_native != name_english:
                    parts.append(name_native)
                if name_english:
                    country_str = f" ({country_english})" if country_english else ""
                    parts.append(f"{name_english}{country_str}")
                if parts:
                    return f"{' — '.join(parts)} [{lang_code}]"
                break

    # 3. Base language mapping
    norm = lang_code.replace("_", "-")
    lang_prefix = norm.split("-")[0].lower()
    if lang_prefix in BASE_LANGUAGES:
        pt_acc, pt_noacc, eng = BASE_LANGUAGES[lang_prefix]
        region = norm.split("-")[1].upper() if "-" in norm else ""
        if region:
            return f"{pt_acc} ({region}) — {pt_noacc} / {eng} ({region}) [{lang_code}]"
        return f"{pt_acc} — {pt_noacc} / {eng} [{lang_code}]"

    # 4. Fallback for completely unrecognized codes
    return f"{lang_code} [{lang_code}]"


def _parse_edge_tts_cli_output(text: str) -> list[dict[str, Any]]:
    """Parses output from 'edge-tts --list-voices' into standard voice dicts."""
    voices: list[dict[str, Any]] = []
    lines = text.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("Name") or line.startswith("----") or line.startswith("Exception"):
            continue
        parts = line.split()
        if len(parts) >= 2 and "-" in parts[0]:
            name = parts[0]
            gender = parts[1]
            locale_parts = name.split("-")
            locale = f"{locale_parts[0]}-{locale_parts[1]}"
            speaker = locale_parts[-1].replace("Neural", "")
            friendly_name = f"Microsoft {speaker} Online (Natural) - {locale}"
            voices.append({
                "ShortName": name,
                "Gender": gender,
                "Locale": locale,
                "FriendlyName": friendly_name,
            })
    return voices


def fetch_edge_voices() -> list[dict[str, Any]]:
    """Loads Edge-TTS voices from cache, edge_tts module, or CLI fallback.

    Ensures at least 50+ voices are retrieved (typically 322+).
    """
    cached = load_edge_voices_cache()
    if cached and len(cached) >= 50:
        return cached

    voices: list[dict[str, Any]] = []

    # 1. Try python edge_tts module
    try:
        import asyncio
        import edge_tts
        voices = asyncio.run(edge_tts.list_voices())
    except Exception:
        voices = []

    # 2. If python module failed or returned too few voices, try CLI
    if not voices or len(voices) < 50:
        candidates = [
            EDGE_TTS_BIN,
            shutil.which("edge-tts"),
            os.path.expanduser("~/anaconda3/bin/edge-tts"),
            "/usr/bin/edge-tts",
            "/app/bin/edge-tts",
            "edge-tts",
        ]
        # Keep non-empty unique candidates
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                unique_candidates.append(c)

        for bin_path in unique_candidates:
            try:
                res = run_command([bin_path, "--list-voices"], capture_output=True, text=True, timeout=30)
                if res.returncode == 0 and res.stdout:
                    parsed = _parse_edge_tts_cli_output(res.stdout)
                    if len(parsed) >= 50:
                        voices = parsed
                        break
            except Exception:
                pass

            # Try run_on_host as well if inside flatpak
            try:
                res_host = run_on_host([bin_path, "--list-voices"], capture_output=True, text=True, timeout=30)
                if res_host.returncode == 0 and res_host.stdout:
                    parsed = _parse_edge_tts_cli_output(res_host.stdout)
                    if len(parsed) >= 50:
                        voices = parsed
                        break
            except Exception:
                pass

    if voices and len(voices) >= 50:
        save_edge_voices_cache(voices)
        return voices

    # Fallback to previously cached or built-in list
    if cached:
        return cached
    return FALLBACK_EDGE_VOICES


def fetch_piper_catalog() -> dict[str, Any]:
    """Reads or downloads the Piper voice catalog (piper_voices.json)."""
    try:
        if not os.path.exists(PIPER_CATALOG_FILE):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode("utf-8")
                with open(PIPER_CATALOG_FILE, "w", encoding="utf-8") as fh:
                    fh.write(data)

        with open(PIPER_CATALOG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def format_piper_voice_display_name(voice_code: str, piper_catalog: dict | None = None) -> str:
    """Formats a human-friendly display name for a Piper voice."""
    parts = voice_code.split("-")
    if len(parts) >= 2:
        name = parts[1].capitalize()
        quality = f"({parts[2].capitalize()})" if len(parts) > 2 else ""
        return f"{name} {quality}".strip()
    return voice_code


def get_downloaded_piper_voices(piper_catalog: dict | None = None) -> list[tuple[str, str]]:
    """Returns sorted list of downloaded Piper voices: [(voice_code, display_name), ...]."""
    downloaded: list[tuple[str, str]] = []
    if os.path.isdir(PIPER_VOICES_DIR):
        try:
            for fname in os.listdir(PIPER_VOICES_DIR):
                if fname.endswith(".onnx"):
                    voice_code = fname[:-5]
                    display_name = format_piper_voice_display_name(voice_code, piper_catalog)
                    downloaded.append((voice_code, display_name))
        except OSError:
            pass

    downloaded.sort(key=lambda item: item[0])
    return downloaded


def get_top_edge_quick_voices(edge_voices: list[dict[str, Any]] | None = None) -> list[tuple[str, str]]:
    """Returns the top 10 recommended Edge-TTS quick voices: [(voice_code, display_name), ...]."""
    top_defaults = [
        ("pt-BR-FranciscaNeural", "Francisca (Português - Brasil)"),
        ("pt-BR-AntonioNeural", "Antonio (Português - Brasil)"),
        ("en-US-AriaNeural", "Aria (English - US)"),
        ("en-US-GuyNeural", "Guy (English - US)"),
        ("es-ES-ElviraNeural", "Elvira (Español - España)"),
        ("fr-FR-HenriNeural", "Henri (Français - France)"),
        ("de-DE-ConradNeural", "Conrad (Deutsch - Deutschland)"),
        ("it-IT-ElsaNeural", "Elsa (Italiano - Italia)"),
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (Chinese - China)"),
        ("ja-JP-NanamiNeural", "Nanami (Japanese - Japan)"),
    ]
    return top_defaults
