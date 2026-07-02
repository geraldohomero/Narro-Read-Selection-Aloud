#!/bin/bash
# ============================================================================
# uninstall.sh — Remove completamente o Narro-RSA do sistema
# ============================================================================

set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/narro-rsa"
PIPER_DIR="${CONFIG_DIR}/piper-voices"

INSTALLED_FILES=(
    "$INSTALL_DIR/ler_texto.py"
    "$INSTALL_DIR/config_dialog.py"
    "$INSTALL_DIR/ler_texto.sh"
    "$INSTALL_DIR/parar_leitura.sh"
    "$INSTALL_DIR/pausar_leitura.sh"
)
INSTALLED_DIRS=(
    "$INSTALL_DIR/narro_rsa"
)

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"

TMP_FILES=(
    "$RUNTIME_DIR/narro-rsa.mp3"
    "$RUNTIME_DIR/narro-rsa.wav"
    "$RUNTIME_DIR/narro-rsa.lock"
    "$RUNTIME_DIR/narro-rsa-mpv.sock"
    # Fallback para /tmp (instalações antigas)
    "/tmp/narro-rsa.mp3"
    "/tmp/narro-rsa.wav"
    "/tmp/narro-rsa.lock"
    "/tmp/narro-rsa-mpv.sock"
)

echo "🗑️  Desinstalação do Narro-RSA"

echo ""

# Mostra o que será removido
echo "Os seguintes itens serão removidos:"
echo ""
echo "  📂 Scripts instalados:"
for f in "${INSTALLED_FILES[@]}"; do
    if [ -f "$f" ]; then
        echo "     ✓ $f"
    else
        echo "     ✗ $f (não encontrado)"
    fi
done

echo ""
echo "  ⚙️  Configurações:"
if [ -d "$CONFIG_DIR" ]; then
    echo "     ✓ $CONFIG_DIR/"
    if [ -d "$PIPER_DIR" ]; then
        echo "     ✓ $PIPER_DIR/ (Vozes do Piper baixadas)"
    fi
else
    echo "     ✗ $CONFIG_DIR/ (não encontrado)"
fi

echo ""
echo "  🧹 Arquivos temporários:"
for f in "${TMP_FILES[@]}"; do
    if [ -f "$f" ] || [ -S "$f" ]; then
        echo "     ✓ $f"
    else
        echo "     ✗ $f (não encontrado)"
    fi
done

echo ""
read -rp "⚠️  Deseja continuar com a desinstalação? [s/N] " answer
if [[ ! "$answer" =~ ^[sS]$ ]]; then
    echo "❌ Desinstalação cancelada."
    exit 0
fi

echo ""

# 1. Para qualquer leitura em andamento
echo "⏹  Parando processos em andamento…"
pkill -f "mpv.*narro-rsa" 2>/dev/null || true
pkill -f "edge-tts.*narro-rsa" 2>/dev/null || true
pkill -f "piper.*narro-rsa" 2>/dev/null || true
pkill -f "ler_texto.py" 2>/dev/null || true
pkill -f "config_dialog.py" 2>/dev/null || true

# 2. Remove scripts instalados
echo "🗂️  Removendo scripts de $INSTALL_DIR…"
for f in "${INSTALLED_FILES[@]}"; do
    if [ -f "$f" ]; then
        rm -f "$f"
        echo "   ✓ Removido: $f"
    fi
done
for d in "${INSTALLED_DIRS[@]}"; do
    if [ -d "$d" ]; then
        rm -rf "$d"
        echo "   ✓ Removido: $d/"
    fi
done

# 3. Remove configurações
echo "⚙️  Removendo configurações…"
if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    echo "   ✓ Removido: $CONFIG_DIR/"
fi

# 4. Remove arquivos temporários
echo "🧹 Removendo arquivos temporários…"
for f in "${TMP_FILES[@]}"; do
    if [ -f "$f" ] || [ -S "$f" ]; then
        rm -f "$f"
        echo "   ✓ Removido: $f"
    fi
done

# Função para remover os atalhos de teclado do GNOME
remove_gnome_shortcuts() {
    if ! command -v gsettings >/dev/null 2>&1; then
        return
    fi

    echo "⚙️  Removendo atalhos de teclado do GNOME…"

    KEY_PATH="org.gnome.settings-daemon.plugins.media-keys"
    
    READ_NAME="Leitor TTS (Narro)"
    READ_ALT_NAME="Leitor TTS (Narro) [Ctrl+\\]"
    PAUSE_NAME="Pausar leitura TTS (Narro)"
    STOP_NAME="Parar leitura TTS (Narro)"

    # Obtém a lista atual de atalhos personalizados
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
        name=$(echo "$name" | tr -d "'\"")
        if [ "$name" = "$READ_NAME" ] || [ "$name" = "$READ_ALT_NAME" ] || [ "$name" = "$PAUSE_NAME" ] || [ "$name" = "$STOP_NAME" ]; then
            # Reseta as chaves deste atalho específico
            gsettings reset-recursively "${KEY_PATH}.custom-keybinding:${path}" 2>/dev/null || true
        else
            paths_to_keep+=("$path")
        fi
    done

    # Reconstrói a lista de caminhos para atualizar o custom-keybindings
    if [ ${#paths_to_keep[@]} -gt 0 ]; then
        new_list_elements=()
        for path in "${paths_to_keep[@]}"; do
            new_list_elements+=("'$path'")
        done
        joined_list=$(IFS=,; echo "${new_list_elements[*]}")
        formatted_list="[$joined_list]"
    else
        formatted_list="@as []"
    fi

    gsettings set $KEY_PATH custom-keybindings "$formatted_list" 2>/dev/null || true
    echo "   ✓ Atalhos do Narro-RSA removidos do GNOME."
}

remove_gnome_shortcuts

echo ""
echo "✅ Narro-RSA foi completamente removido!"

