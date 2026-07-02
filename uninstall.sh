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
)

TMP_FILES=(
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

echo ""
echo "✅ Narro-RSA foi completamente removido!"
echo ""
echo "📋 Lembrete: Remova manualmente os atalhos de teclado no GNOME:"
echo "   Configurações → Teclado → Atalhos personalizados"
echo "   - Remova o atalho \"Leitor TTS\""
echo "   - Remova o atalho \"Parar leitura TTS\" (se configurado)"
