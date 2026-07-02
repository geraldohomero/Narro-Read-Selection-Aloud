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
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null || MISSING+=("gtk4")
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
    echo "   sudo dnf install wl-clipboard mpv libnotify python3-gobject gtk3 gtk4"
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
cp "$SCRIPT_DIR/config_dialog.py" "$INSTALL_DIR/config_dialog.py"
cp "$SCRIPT_DIR/ler_texto.sh" "$INSTALL_DIR/ler_texto.sh"
cp "$SCRIPT_DIR/parar_leitura.sh" "$INSTALL_DIR/parar_leitura.sh"
cp "$SCRIPT_DIR/pausar_leitura.sh" "$INSTALL_DIR/pausar_leitura.sh"
chmod +x "$INSTALL_DIR/ler_texto.py"
chmod +x "$INSTALL_DIR/config_dialog.py"
chmod +x "$INSTALL_DIR/ler_texto.sh"
chmod +x "$INSTALL_DIR/parar_leitura.sh"
chmod +x "$INSTALL_DIR/pausar_leitura.sh"

# Copia o pacote narro_rsa/
mkdir -p "$INSTALL_DIR/narro_rsa"
cp "$SCRIPT_DIR"/narro_rsa/*.py "$INSTALL_DIR/narro_rsa/"

echo "✅ Instalado em $INSTALL_DIR:"
echo "   - ler_texto.py        (entrypoint do player GTK)"
echo "   - config_dialog.py    (diálogo de configurações GTK4)"
echo "   - ler_texto.sh        (wrapper para atalho)"
echo "   - parar_leitura.sh    (parar leitura)"
echo "   - pausar_leitura.sh   (pausar/retomar leitura)"
echo "   - narro_rsa/          (pacote Python do projeto)"
echo ""

# Função para configurar atalhos de teclado no GNOME
configure_gnome_shortcuts() {
    if ! command -v gsettings >/dev/null 2>&1; then
        return 1
    fi

    # Verifica se o GNOME está em execução
    if [ "${XDG_CURRENT_DESKTOP:-}" != "GNOME" ] && [ "${GDMSESSION:-}" != "gnome" ] && [ "${GNOME_SHELL_SESSION_MODE:-}" = "" ]; then
        return 2
    fi

    echo "⚙️  Configurando atalhos de teclado no GNOME…"

    KEY_PATH="org.gnome.settings-daemon.plugins.media-keys"
    CUSTOM_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

    READ_NAME="Leitor TTS (Narro)"
    READ_CMD="bash -c \"\$HOME/.local/bin/ler_texto.sh\""
    READ_BINDING="<Super><Alt>l"

    READ_ALT_NAME="Leitor TTS (Narro) [Ctrl+\\]"
    READ_ALT_CMD="bash -c \"\$HOME/.local/bin/ler_texto.sh\""
    READ_ALT_BINDING="<Primary>backslash"

    PAUSE_NAME="Pausar leitura TTS (Narro)"
    PAUSE_CMD="bash -c \"\$HOME/.local/bin/pausar_leitura.sh\""
    PAUSE_BINDING="<Super><Alt>j"

    STOP_NAME="Parar leitura TTS (Narro)"
    STOP_CMD="bash -c \"\$HOME/.local/bin/parar_leitura.sh\""
    STOP_BINDING="<Super><Alt>k"

    # Obtém a lista atual de atalhos personalizados
    current_list_str=$(gsettings get $KEY_PATH custom-keybindings 2>/dev/null || echo "[]")
    
    # Limpa a lista para processamento
    cleaned_list=$(echo "$current_list_str" | tr -d '[]'"'" | tr ',' '\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep -v '^$') || true
    
    existing_paths=()
    for item in $cleaned_list; do
        if [ "$item" != "@as" ]; then
            existing_paths+=("$item")
        fi
    done

    READ_PATH=""
    READ_ALT_PATH=""
    PAUSE_PATH=""
    STOP_PATH=""

    # Procura se os atalhos já existem
    for path in "${existing_paths[@]}"; do
        name=$(gsettings get "${KEY_PATH}.custom-keybinding:${path}" name 2>/dev/null || echo "")
        name=$(echo "$name" | tr -d "'\"")
        if [ "$name" = "$READ_NAME" ]; then
            READ_PATH="$path"
        elif [ "$name" = "$READ_ALT_NAME" ]; then
            READ_ALT_PATH="$path"
        elif [ "$name" = "$PAUSE_NAME" ]; then
            PAUSE_PATH="$path"
        elif [ "$name" = "$STOP_NAME" ]; then
            STOP_PATH="$path"
        fi
    done

    # Determina o próximo índice customizado disponível
    max_idx=-1
    for path in "${existing_paths[@]}"; do
        if [[ "$path" =~ custom([0-9]+)/$ ]]; then
            idx="${BASH_REMATCH[1]}"
            if [ "$idx" -gt "$max_idx" ]; then
                max_idx="$idx"
            fi
        fi
    done

    if [ -z "$READ_PATH" ]; then
        max_idx=$((max_idx + 1))
        READ_PATH="${CUSTOM_PATH}/custom${max_idx}/"
        existing_paths+=("$READ_PATH")
    fi

    if [ -z "$READ_ALT_PATH" ]; then
        max_idx=$((max_idx + 1))
        READ_ALT_PATH="${CUSTOM_PATH}/custom${max_idx}/"
        existing_paths+=("$READ_ALT_PATH")
    fi

    if [ -z "$PAUSE_PATH" ]; then
        max_idx=$((max_idx + 1))
        PAUSE_PATH="${CUSTOM_PATH}/custom${max_idx}/"
        existing_paths+=("$PAUSE_PATH")
    fi

    if [ -z "$STOP_PATH" ]; then
        max_idx=$((max_idx + 1))
        STOP_PATH="${CUSTOM_PATH}/custom${max_idx}/"
        existing_paths+=("$STOP_PATH")
    fi

    # Configura os atalhos
    gsettings set "${KEY_PATH}.custom-keybinding:${READ_PATH}" name "$READ_NAME"
    gsettings set "${KEY_PATH}.custom-keybinding:${READ_PATH}" command "$READ_CMD"
    gsettings set "${KEY_PATH}.custom-keybinding:${READ_PATH}" binding "$READ_BINDING"

    gsettings set "${KEY_PATH}.custom-keybinding:${READ_ALT_PATH}" name "$READ_ALT_NAME"
    gsettings set "${KEY_PATH}.custom-keybinding:${READ_ALT_PATH}" command "$READ_ALT_CMD"
    gsettings set "${KEY_PATH}.custom-keybinding:${READ_ALT_PATH}" binding "$READ_ALT_BINDING"

    gsettings set "${KEY_PATH}.custom-keybinding:${PAUSE_PATH}" name "$PAUSE_NAME"
    gsettings set "${KEY_PATH}.custom-keybinding:${PAUSE_PATH}" command "$PAUSE_CMD"
    gsettings set "${KEY_PATH}.custom-keybinding:${PAUSE_PATH}" binding "$PAUSE_BINDING"

    gsettings set "${KEY_PATH}.custom-keybinding:${STOP_PATH}" name "$STOP_NAME"
    gsettings set "${KEY_PATH}.custom-keybinding:${STOP_PATH}" command "$STOP_CMD"
    gsettings set "${KEY_PATH}.custom-keybinding:${STOP_PATH}" binding "$STOP_BINDING"

    # Atualiza a lista master de atalhos personalizados
    new_list_elements=()
    for path in "${existing_paths[@]}"; do
        new_list_elements+=("'$path'")
    done

    joined_list=$(IFS=,; echo "${new_list_elements[*]}")
    formatted_list="[$joined_list]"

    gsettings set $KEY_PATH custom-keybindings "$formatted_list"

    echo "   ✓ Atalho \"$READ_NAME\" configurado para Super+Alt+L"
    echo "   ✓ Atalho \"$READ_ALT_NAME\" configurado para Ctrl+\\"
    echo "   ✓ Atalho \"$PAUSE_NAME\" configurado para Super+Alt+J"
    echo "   ✓ Atalho \"$STOP_NAME\" configurado para Super+Alt+K"
    return 0
}

if configure_gnome_shortcuts; then
    echo ""
    echo "🎉 Atalhos do GNOME configurados automaticamente!"
    echo "   - Super+Alt+L: Iniciar leitura (Leitor TTS)"
    echo "   - Ctrl+\\: Iniciar leitura direta (copia e lê)"
    echo "   - Super+Alt+J: Pausar/Retomar leitura"
    echo "   - Super+Alt+K: Parar leitura"
    echo ""
    echo "🎉 Pronto! Selecione um texto e use Ctrl+\\ ou copie (Ctrl+C) e use Super+Alt+L para ler."
else
    ret=$?
    echo "📋 Configure os atalhos de teclado no GNOME manualmente:"
    echo "   Configurações → Teclado → Atalhos personalizados"
    echo ""
    echo "   Atalho 1 — Abrir Leitor TTS:"
    echo "     Nome:    Leitor TTS (Narro)"
    echo "     Comando: bash -c \"\$HOME/.local/bin/ler_texto.sh\""
    echo "     Tecla:   Super+Alt+L"
    echo ""
    echo "   Atalho 2 — Abrir Leitor TTS (direto):"
    echo "     Nome:    Leitor TTS (Narro) [Ctrl+\\\\]"
    echo "     Comando: bash -c \"\$HOME/.local/bin/ler_texto.sh\""
    echo "     Tecla:   Ctrl+\\"
    echo ""
    echo "   Atalho 3 — Pausar/Retomar leitura (opcional):"
    echo "     Nome:    Pausar leitura TTS (Narro)"
    echo "     Comando: bash -c \"\$HOME/.local/bin/pausar_leitura.sh\""
    echo "     Tecla:   Super+Alt+J"
    echo ""
    echo "   Atalho 4 — Parar leitura (opcional):"
    echo "     Nome:    Parar leitura TTS (Narro)"
    echo "     Comando: bash -c \"\$HOME/.local/bin/parar_leitura.sh\""
    echo "     Tecla:   Super+Alt+K"
    echo ""
    if [ $ret -eq 2 ]; then
        echo "💡 Nota: Atalhos não configurados automaticamente porque você não está em uma sessão GNOME."
    else
        echo "💡 Nota: Atalhos não configurados automaticamente porque o comando 'gsettings' não foi encontrado."
    fi
fi

