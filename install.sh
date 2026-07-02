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
FEDORA_PKGS=()
UBUNTU_PKGS=()
ARCH_PKGS=()
PIP_PKGS=()

if ! command -v wl-paste >/dev/null 2>&1; then
    FEDORA_PKGS+=("wl-clipboard")
    UBUNTU_PKGS+=("wl-clipboard")
    ARCH_PKGS+=("wl-clipboard")
fi

if ! command -v mpv >/dev/null 2>&1; then
    FEDORA_PKGS+=("mpv")
    UBUNTU_PKGS+=("mpv")
    ARCH_PKGS+=("mpv")
fi

if ! command -v notify-send >/dev/null 2>&1; then
    FEDORA_PKGS+=("libnotify")
    UBUNTU_PKGS+=("libnotify-bin")
    ARCH_PKGS+=("libnotify")
fi

if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null; then
    FEDORA_PKGS+=("python3-gobject" "gtk3")
    UBUNTU_PKGS+=("python3-gi" "gir1.2-gtk-3.0")
    ARCH_PKGS+=("python-gobject" "gtk3")
fi

if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null; then
    FEDORA_PKGS+=("gtk4")
    UBUNTU_PKGS+=("gir1.2-gtk-4.0")
    ARCH_PKGS+=("gtk4")
fi

if ! python3 -c "
import gi
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3
except ValueError:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
" 2>/dev/null; then
    FEDORA_PKGS+=("libappindicator-gtk3")
    UBUNTU_PKGS+=("gir1.2-ayatanaappindicator3-0.1")
    ARCH_PKGS+=("libayatana-appindicator")
fi

if ! command -v edge-tts >/dev/null 2>&1 && \
   [ ! -x "${HOME}/.local/bin/edge-tts" ]; then
    PIP_PKGS+=("edge-tts")
fi

if [ ${#FEDORA_PKGS[@]} -gt 0 ] || [ ${#PIP_PKGS[@]} -gt 0 ]; then
    echo "⚠️  Dependências faltando:"
    
    if ! command -v wl-paste >/dev/null 2>&1; then echo "   - wl-clipboard"; fi
    if ! command -v mpv >/dev/null 2>&1; then echo "   - mpv"; fi
    if ! command -v notify-send >/dev/null 2>&1; then echo "   - libnotify"; fi
    if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null; then echo "   - python3-gobject / gtk3"; fi
    if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null; then echo "   - gtk4"; fi
    if ! python3 -c "
import gi
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3
except ValueError:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
" 2>/dev/null; then echo "   - libappindicator-gtk3 / AyatanaAppIndicator3"; fi
    if [ ${#PIP_PKGS[@]} -gt 0 ]; then echo "   - edge-tts (via pipx)"; fi
    
    echo ""
    echo "Instale com:"

    # Detecta a distribuição
    DISTRO="unknown"
    if [ -f /etc/os-release ]; then
        OS_ID=$(grep -E '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
        OS_LIKE=$(grep -E '^ID_LIKE=' /etc/os-release | cut -d= -f2 | tr -d '"' || echo "")
        if [[ "$OS_ID" == "fedora" || "$OS_LIKE" =~ "fedora" ]]; then
            DISTRO="fedora"
        elif [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" || "$OS_LIKE" =~ "ubuntu" || "$OS_LIKE" =~ "debian" ]]; then
            DISTRO="ubuntu"
        elif [[ "$OS_ID" == "arch" || "$OS_LIKE" =~ "arch" || "$OS_ID" == "manjaro" || "$OS_LIKE" =~ "manjaro" ]]; then
            DISTRO="arch"
        fi
    fi

    case "$DISTRO" in
        fedora)
            if [ ${#FEDORA_PKGS[@]} -gt 0 ]; then
                echo "   sudo dnf install ${FEDORA_PKGS[*]}"
            fi
            ;;
        ubuntu)
            if [ ${#UBUNTU_PKGS[@]} -gt 0 ]; then
                echo "   sudo apt install ${UBUNTU_PKGS[*]}"
            fi
            ;;
        arch)
            if [ ${#ARCH_PKGS[@]} -gt 0 ]; then
                echo "   sudo pacman -S ${ARCH_PKGS[*]}"
            fi
            ;;
        *)
            echo "   • Fedora: sudo dnf install ${FEDORA_PKGS[*]}"
            echo "   • Ubuntu/Debian: sudo apt install ${UBUNTU_PKGS[*]}"
            echo "   • Arch Linux: sudo pacman -S ${ARCH_PKGS[*]}"
            ;;
    esac

    if [ ${#PIP_PKGS[@]} -gt 0 ]; then
        echo "   pipx install edge-tts"
    fi
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

    # -------------------------------------------------------------
    # Limpeza prévia de atalhos Narro existentes e duplicados
    # -------------------------------------------------------------
    current_list_str=$(gsettings get $KEY_PATH custom-keybindings 2>/dev/null || echo "[]")
    cleaned_list=$(echo "$current_list_str" | tr -d '[]'"'" | tr ',' '\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep -v '^$') || true
    
    existing_paths=()
    for item in $cleaned_list; do
        if [ "$item" != "@as" ]; then
            existing_paths+=("$item")
        fi
    done

    paths_to_keep=()
    for path in "${existing_paths[@]}"; do
        name=$(gsettings get "${KEY_PATH}.custom-keybinding:${path}" name 2>/dev/null || echo "")
        name=$(echo "$name" | tr -d "'\"" | xargs)
        if [[ "$name" == "Leitor TTS (Narro)" ]] || [[ "$name" == "Leitor TTS (Narro) [Ctrl+\\]" ]] || [[ "$name" == "Pausar leitura TTS (Narro)" ]] || [[ "$name" == "Parar leitura TTS (Narro)" ]] || [[ "$name" == "tts-tablet" ]]; then
            gsettings reset-recursively "${KEY_PATH}.custom-keybinding:${path}" 2>/dev/null || true
        else
            paths_to_keep+=("$path")
        fi
    done

    # -------------------------------------------------------------
    # Configuração dos novos atalhos com caminhos absolutos
    # -------------------------------------------------------------
    READ_NAME="Leitor TTS (Narro)"
    READ_CMD="${HOME}/.local/bin/ler_texto.sh"
    READ_BINDING="<Super><Alt>l"

    READ_ALT_NAME="Leitor TTS (Narro) [Ctrl+\\]"
    READ_ALT_CMD="${HOME}/.local/bin/ler_texto.sh --primary"
    READ_ALT_BINDING="<Primary>backslash"

    PAUSE_NAME="Pausar leitura TTS (Narro)"
    PAUSE_CMD="${HOME}/.local/bin/pausar_leitura.sh"
    PAUSE_BINDING="<Super><Alt>j"

    STOP_NAME="Parar leitura TTS (Narro)"
    STOP_CMD="${HOME}/.local/bin/parar_leitura.sh"
    STOP_BINDING="<Super><Alt>k"

    # Determina o próximo índice customizado disponível
    max_idx=-1
    for path in "${paths_to_keep[@]}"; do
        if [[ "$path" =~ custom([0-9]+)/$ ]]; then
            idx="${BASH_REMATCH[1]}"
            if [ "$idx" -gt "$max_idx" ]; then
                max_idx="$idx"
            fi
        fi
    done

    max_idx=$((max_idx + 1))
    READ_PATH="${CUSTOM_PATH}/custom${max_idx}/"
    paths_to_keep+=("$READ_PATH")

    max_idx=$((max_idx + 1))
    READ_ALT_PATH="${CUSTOM_PATH}/custom${max_idx}/"
    paths_to_keep+=("$READ_ALT_PATH")

    max_idx=$((max_idx + 1))
    PAUSE_PATH="${CUSTOM_PATH}/custom${max_idx}/"
    paths_to_keep+=("$PAUSE_PATH")

    max_idx=$((max_idx + 1))
    STOP_PATH="${CUSTOM_PATH}/custom${max_idx}/"
    paths_to_keep+=("$STOP_PATH")

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
    for path in "${paths_to_keep[@]}"; do
        new_list_elements+=("'$path'")
    done

    joined_list=$(IFS=,; echo "${new_list_elements[*]}")
    formatted_list="[$joined_list]"

    gsettings set $KEY_PATH custom-keybindings "$formatted_list"

    # Desativa notificações para o wl-clipboard no GNOME para evitar popups irritantes de foco
    current_apps=$(gsettings get org.gnome.desktop.notifications application-children 2>/dev/null || echo "[]")
    if [[ ! "$current_apps" =~ "io-github-bugaevc-wl-clipboard" ]]; then
        new_apps=$(echo "$current_apps" | sed "s/\]$/, 'io-github-bugaevc-wl-clipboard'\]/")
        gsettings set org.gnome.desktop.notifications application-children "$new_apps" 2>/dev/null || true
    fi
    gsettings set org.gnome.desktop.notifications.application:/org/gnome/desktop/notifications/application/io-github-bugaevc-wl-clipboard/ enable false 2>/dev/null || true
    gsettings set org.gnome.desktop.notifications.application:/org/gnome/desktop/notifications/application/io-github-bugaevc-wl-clipboard/ show-banners false 2>/dev/null || true
    gsettings set org.gnome.desktop.notifications.application:/org/gnome/desktop/notifications/application/io-github-bugaevc-wl-clipboard/ application-id "'io.github.bugaevc.wl-clipboard'" 2>/dev/null || true

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
    echo "   - Ctrl+\\: Iniciar leitura direta da seleção"
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
    echo "     Comando: ${HOME}/.local/bin/ler_texto.sh"
    echo "     Tecla:   Super+Alt+L"
    echo ""
    echo "   Atalho 2 — Abrir Leitor TTS (direto):"
    echo "     Nome:    Leitor TTS (Narro) [Ctrl+\\\\]"
    echo "     Comando: ${HOME}/.local/bin/ler_texto.sh --primary"
    echo "     Tecla:   Ctrl+\\"
    echo ""
    echo "   Atalho 3 — Pausar/Retomar leitura (opcional):"
    echo "     Nome:    Pausar leitura TTS (Narro)"
    echo "     Comando: ${HOME}/.local/bin/pausar_leitura.sh"
    echo "     Tecla:   Super+Alt+J"
    echo ""
    echo "   Atalho 4 — Parar leitura (opcional):"
    echo "     Nome:    Parar leitura TTS (Narro)"
    echo "     Comando: ${HOME}/.local/bin/parar_leitura.sh"
    echo "     Tecla:   Super+Alt+K"
    echo ""
    if [ $ret -eq 2 ]; then
        echo "💡 Nota: Atalhos não configurados automaticamente porque você não está em uma sessão GNOME."
    else
        echo "💡 Nota: Atalhos não configurados automaticamente porque o comando 'gsettings' não foi encontrado."
    fi
fi

