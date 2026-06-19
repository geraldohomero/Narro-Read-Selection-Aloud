#!/bin/bash
# Wrapper para chamar o leitor TTS Python via atalho de teclado do GNOME
# Ao pressionar o atalho (Ctrl+\):
#   - Se o indicador já está rodando: envia SIGUSR1 para nova leitura
#   - Se não está rodando: inicia o indicador na tray

LOCKFILE="/tmp/narro-rsa.lock"

# 1. Copia o texto selecionado para o clipboard (sem precisar de Ctrl+C manual)
SELECTED=$(wl-paste --primary 2>/dev/null)
if [ -n "$SELECTED" ]; then
    printf '%s' "$SELECTED" | wl-copy 2>/dev/null
fi

# 2. Verifica se o indicador já está rodando
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        # Instância ativa — envia SIGUSR1 para nova leitura
        kill -USR1 "$OLD_PID" 2>/dev/null
        exit 0
    else
        # Lockfile obsoleto — limpa
        rm -f "$LOCKFILE" /tmp/narro-rsa.mp3 /tmp/narro-rsa-mpv.sock 2>/dev/null
        pkill -f "mpv.*narro-rsa" 2>/dev/null || true
    fi
fi

# 3. Inicia o indicador na tray
exec python3 "$HOME/.local/bin/ler_texto.py" "$@"
