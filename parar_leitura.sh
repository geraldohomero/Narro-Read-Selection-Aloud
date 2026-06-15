#!/bin/bash
# Parar qualquer leitura TTS em andamento
pkill -f "mpv.*narro-rsa" 2>/dev/null || true
pkill -f "edge-tts.*narro-rsa" 2>/dev/null || true
rm -f /tmp/narro-rsa.lock /tmp/narro-rsa.mp3 2>/dev/null || true
notify-send -i media-playback-stop "Narro-RSA" "Leitura interrompida." -t 2000 2>/dev/null || true
