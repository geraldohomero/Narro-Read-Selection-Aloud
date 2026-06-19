#!/bin/bash
# ============================================================================
# install.sh — Instala o Narro-RSA em ~/.local/bin
# ============================================================================

set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "📦 Instalando Narro-RSA…"
echo ""

# Verifica dependências
MISSING=()
command -v wl-paste    >/dev/null 2>&1 || MISSING+=("wl-clipboard")
command -v mpv         >/dev/null 2>&1 || MISSING+=("mpv")
command -v notify-send >/dev/null 2>&1 || MISSING+=("libnotify")
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null || MISSING+=("python3-gobject gtk3")
python3 -c "
import gi
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3
except ValueError:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
" 2>/dev/null || MISSING+=("libappindicator-gtk3")

if ! command -v edge-tts >/dev/null 2>&1 && \
   [ ! -x "${HOME}/.local/bin/edge-tts" ]; then
    MISSING+=("edge-tts (via pipx)")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "⚠️  Dependências faltando:"
    for dep in "${MISSING[@]}"; do
        echo "   - $dep"
    done
    echo ""
    echo "Instale com:"
    echo "   sudo dnf install wl-clipboard mpv libnotify python3-gobject gtk3"
    echo "   pipx install edge-tts"
    echo ""
    read -rp "Continuar mesmo assim? [s/N] " answer
    if [[ ! "$answer" =~ ^[sS]$ ]]; then
        exit 1
    fi
fi

# Cria diretório se não existir
mkdir -p "$INSTALL_DIR"

# Copia e torna executável
cp "$SCRIPT_DIR/ler_texto.py" "$INSTALL_DIR/ler_texto.py"
cp "$SCRIPT_DIR/ler_texto.sh" "$INSTALL_DIR/ler_texto.sh"
cp "$SCRIPT_DIR/parar_leitura.sh" "$INSTALL_DIR/parar_leitura.sh"
chmod +x "$INSTALL_DIR/ler_texto.py"
chmod +x "$INSTALL_DIR/ler_texto.sh"
chmod +x "$INSTALL_DIR/parar_leitura.sh"

echo "✅ Instalado em $INSTALL_DIR:"
echo "   - ler_texto.py        (app GTK principal)"
echo "   - ler_texto.sh        (wrapper para atalho)"
echo "   - parar_leitura.sh    (parar leitura)"
echo ""
echo "📋 Configure o atalho no GNOME:"
echo "   Configurações → Teclado → Atalhos personalizados"
echo ""
echo "   Atalho — Leitor TTS (para + abre):"
echo "     Nome:    Leitor TTS"
echo "     Comando: bash -c \"\$HOME/.local/bin/ler_texto.sh\""
echo "     Tecla:   Ctrl+\\ (sugestão)"
echo ""
echo "   💡 O atalho Ctrl+\\ automaticamente para qualquer leitura"
echo "      em andamento e abre a interface com o texto copiado."
echo ""
echo "🎉 Pronto! Copie texto no Okular (Ctrl+C) e use Ctrl+\\ para ler."
