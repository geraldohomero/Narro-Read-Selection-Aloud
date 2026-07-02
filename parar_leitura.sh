#!/bin/bash
# Parar qualquer leitura TTS em andamento
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
pkill -f "mpv.*narro-rsa" 2>/dev/null || true
pkill -f "edge-tts.*narro-rsa" 2>/dev/null || true
rm -f "$RUNTIME_DIR/narro-rsa.lock" "$RUNTIME_DIR/narro-rsa.mp3" "$RUNTIME_DIR/narro-rsa.wav" 2>/dev/null || true
notify-send -i media-playback-stop "Narro-RSA" "Leitura interrompida." -t 2000 2>/dev/null || true
