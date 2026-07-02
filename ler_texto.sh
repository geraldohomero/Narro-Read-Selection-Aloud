#!/bin/bash
# Wrapper para chamar o leitor TTS Python via atalho de teclado do GNOME
# Ao pressionar o atalho (Ctrl+\):
#   - Se o indicador já está rodando: envia SIGUSR1 para nova leitura
#   - Se não está rodando: inicia o indicador na tray


# 1. Inicia o indicador na tray
exec python3 "$HOME/.local/bin/ler_texto.py" "$@"
