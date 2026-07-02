"""Gerenciamento de configurações persistentes do Narro-RSA.

Carrega e salva preferências do usuário em JSON, compartilhado
entre o leitor TTS e o diálogo de configurações.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .constants import CONFIG_DIR, CONFIG_FILE


def load_settings() -> dict[str, Any]:
    """Carrega as preferências salvas do disco.

    Returns:
        Dicionário com as configurações. Retorna ``{}`` se o arquivo
        não existir ou estiver corrompido.
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(**kwargs: Any) -> None:
    """Salva as preferências atuais, fazendo merge com as existentes.

    Apenas as chaves fornecidas como keyword arguments são atualizadas.
    Chaves com valor ``None`` são ignoradas.

    Exemplo::

        save_settings(voice="pt-BR-FranciscaNeural", speed=1.5)
    """
    settings = load_settings()
    for key, value in kwargs.items():
        if value is not None:
            settings[key] = value
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, ensure_ascii=False)
    except OSError:
        pass
