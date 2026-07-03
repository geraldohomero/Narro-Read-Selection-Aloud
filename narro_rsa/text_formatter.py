"""Formatação de texto para leitura TTS.

Remove artefatos comuns de PDFs (hifenização, letras espaçadas,
caracteres de controle) para melhorar a qualidade da síntese de voz.
"""

from __future__ import annotations

import re

# Palavras portuguesas de duas letras que não devem ser "coladas"
_COMMON_TWO_LETTER: frozenset[str] = frozenset({
    "um", "em", "ao", "ou", "eu", "se", "de", "da", "do", "no", "na",
    "os", "as", "me", "te", "lá", "cá", "já", "há", "ir", "só", "má",
})

# Padrão para 3+ letras separadas por espaços (artefato de PDF)
_SPACED_LETTERS_RE = re.compile(
    r'(?<![a-zA-ZÀ-ÿ])'
    r'([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])'
    r'(?: ([a-zA-ZÀ-ÿ])){1,}'
    r'(?![a-zA-ZÀ-ÿ])'
)

# Padrão para 2 letras separadas por espaço
_TWO_LETTER_RE = re.compile(
    r'(?<![a-zA-ZÀ-ÿ])([a-zA-ZÀ-ÿ]) ([a-zA-ZÀ-ÿ])(?![a-zA-ZÀ-ÿ])'
)


def _fix_spaced_letters(text: str) -> str:
    """Corrige palavras com letras separadas por espaços (artefato de PDF).

    Exemplos::

        "c o n h e c i m e n t o"  →  "conhecimento"
        "d e"                       →  "de"  (palavra comum)
        "z q"                       →  "z q" (mantém, não é palavra)
    """
    def _collapse_spaced(match: re.Match[str]) -> str:
        return match.group(0).replace(" ", "")

    text = _SPACED_LETTERS_RE.sub(_collapse_spaced, text)

    def _collapse_two_letter(match: re.Match[str]) -> str:
        a, b = match.group(1), match.group(2)
        joined = a + b
        return joined if joined.lower() in _COMMON_TWO_LETTER else match.group(0)

    return _TWO_LETTER_RE.sub(_collapse_two_letter, text)


def format_text_for_tts(text: str) -> str:
    """Formata o texto para leitura TTS, removendo artefatos comuns de PDFs.

    Operações realizadas (em ordem):
    1. Remove caracteres de controle e Unicode invisíveis
    2. Corrige hifenização de quebra de linha
    3. Normaliza espaços em branco
    4. Corrige letras espaçadas (artefato de PDF)
    5. Remove espaços antes de pontuação
    6. Remove números isolados (paginação de PDF)

    Args:
        text: Texto bruto copiado do clipboard.

    Returns:
        Texto limpo e pronto para síntese de voz.
    """
    if not text:
        return ""

    # 1. Remove caracteres de controle e Unicode invisíveis
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060\ufeff\u00ad]', '', text)

    # 1.5 Remove linhas contendo apenas números (ex: número de página isolado no PDF)
    lines = text.splitlines()
    filtered_lines = []
    for line in lines:
        if line.strip().isdigit():
            continue
        filtered_lines.append(line)
    text = "\n".join(filtered_lines)

    # 2. Corrige hifenização
    text = re.sub(r'(\w)-[;,.:!?]+(\s)', r'\1-\2', text)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)

    # 3. Normaliza espaços em branco
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    text = re.sub(r' {2,}', ' ', text)

    # 4. Corrige letras espaçadas
    text = _fix_spaced_letters(text)

    # 5. Remove espaços antes de pontuação
    text = re.sub(r'\s+([.,;:!?\)\]])', r'\1', text)

    # 6. Normalização final de espaços
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()
