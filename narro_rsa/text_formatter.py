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


def split_text_into_chunks(
    text: str,
    first_chunk_max_chars: int = 220,
    next_chunk_max_chars: int = 600,
) -> list[str]:
    """Divide o texto em chunks lógicos respeitando limites de caracteres e pontuação.

    O chunk 0 tem limite reduzido (first_chunk_max_chars) para que a reprodução
    possa iniciar de imediato com latência quase nula. Chunks subsequentes usam
    next_chunk_max_chars.

    Args:
        text: Texto bruto a ser lido.
        first_chunk_max_chars: Tamanho máximo em caracteres do primeiro chunk (padrão: 220).
        next_chunk_max_chars: Tamanho máximo dos chunks subsequentes (padrão: 600).

    Returns:
        Lista de strings correspondendo aos chunks em ordem.
    """
    cleaned = format_text_for_tts(text)
    if not cleaned:
        return []

    if len(cleaned) <= first_chunk_max_chars:
        return [cleaned]

    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?…;:])\s+', cleaned) if s.strip()]
    if not raw_sentences:
        return []

    items = list(raw_sentences)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    while items:
        item = items.pop(0)
        limit = first_chunk_max_chars if not chunks else next_chunk_max_chars
        needed = len(item) if not current_chunk else 1 + len(item)

        if current_len + needed <= limit:
            current_chunk.append(item)
            current_len += needed
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk).strip())
                current_chunk = []
                current_len = 0
                items.insert(0, item)
            else:
                # O item sozinho excede o limite do chunk vazio atual.
                # Tenta quebrar em limites de cláusula/vírgula
                comma_parts = [p.strip() for p in re.split(r'(?<=[,])\s+', item) if p.strip()]
                if len(comma_parts) > 1:
                    items = comma_parts + items
                else:
                    # Tenta quebrar em palavras
                    words = [w.strip() for w in re.split(r'\s+', item) if w.strip()]
                    if len(words) > 1:
                        items = words + items
                    else:
                        # Palavra individual única maior que o limite: coloca no chunk e finaliza
                        current_chunk.append(item)
                        chunks.append(" ".join(current_chunk).strip())
                        current_chunk = []
                        current_len = 0

    if current_chunk:
        chunks.append(" ".join(current_chunk).strip())

    return [c for c in chunks if c]

