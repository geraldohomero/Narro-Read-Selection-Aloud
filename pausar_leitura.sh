#!/bin/bash
# Alternar pausa da leitura TTS
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCKFILE="$RUNTIME_DIR/narro-rsa.lock"

if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill -USR2 "$OLD_PID" 2>/dev/null
        notify-send -i media-playback-pause "Narro-RSA" "Pausa alternada." -t 1500 2>/dev/null || true
        exit 0
    fi
fi
