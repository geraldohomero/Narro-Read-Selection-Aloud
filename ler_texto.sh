#!/bin/bash
# Wrapper para chamar o leitor TTS Python via atalho de teclado do GNOME
# Ao pressionar o atalho (Ctrl+\), primeiro para qualquer leitura em andamento
# e depois abre a interface.

# 1. Para leitura em andamento (silenciosamente)
pkill -f "mpv.*narro-rsa" 2>/dev/null || true
pkill -f "edge-tts.*narro-rsa" 2>/dev/null || true
rm -f /tmp/narro-rsa.lock /tmp/narro-rsa.mp3 /tmp/narro-rsa-mpv.sock 2>/dev/null || true

# 2. Copia o texto selecionado para o clipboard (sem precisar de Ctrl+C manual)
SELECTED=$(wl-paste --primary 2>/dev/null)
if [ -n "$SELECTED" ]; then
    printf '%s' "$SELECTED" | wl-copy 2>/dev/null
fi

# 3. Abre a interface GTK
exec python3 "$HOME/.local/bin/ler_texto.py" "$@"
