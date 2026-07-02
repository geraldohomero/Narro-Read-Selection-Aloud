# Narro - Ler seleção em voz alta

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

Leitor de texto em voz alta com suporte a Edge TTS (online) e Piper TTS (offline) para o GNOME/Wayland.

Selecione texto em qualquer aplicativo, copie com Ctrl+C, e use um atalho de teclado para abrir o player TTS — com controles de Play/Pause/Stop, seleção de motor/idioma/voz e controle de velocidade.

![Player TTS](https://img.shields.io/badge/GTK3-Player-blue?style=for-the-badge)

![image-hero](assets/image-hero.png)

## Funcionalidades

- Controles completos de reprodução (Play, Pause, Stop).
- Dois motores de síntese suportados: Edge TTS (vozes neurais da nuvem) e Piper TTS (vozes locais ultrarrápidas rodando totalmente offline).
- Nova aba de seleção de voz estruturada em: Voz -> Engine (Edge TTS ou Piper TTS) -> Língua -> Selecionar.
- Diálogo de configuração nativo em GTK4 que permite listar as vozes disponíveis, visualizar o status de download do modelo local (para o Piper) e baixá-los diretamente pela interface com uma barra de progresso em tempo real.
- As vozes baixadas do Piper são guardadas em uma pasta local do usuário (`~/.config/narro-rsa/piper-voices/`).
- Controle de velocidade em tempo real via mpv (aplicável a ambos os motores).
- Interface GTK nativa integrada visualmente com o GNOME.
- Barra de status com informações de feedback do processo.

## Dependências

Escolha o comando correspondente à sua distribuição Linux para instalar as dependências do sistema:

### Fedora
```bash
sudo dnf install wl-clipboard mpv libnotify python3-gobject gtk3 gtk4 libappindicator-gtk3
```

### Ubuntu / Debian
```bash
sudo apt install wl-clipboard mpv libnotify-bin python3-gi gir1.2-gtk-3.0 gir1.2-gtk-4.0 gir1.2-ayatanaappindicator3-0.1
```

### Arch Linux / Manjaro
```bash
sudo pacman -S wl-clipboard mpv libnotify python-gobject gtk3 gtk4 libayatana-appindicator
```

### Motores de Síntese de Voz Python (Todas as distros)
```bash
pipx install edge-tts
# Opcional para TTS local offline:
pipx install piper-tts
```

Nota: Para usar o Piper TTS, garanta que o binário do `piper` esteja disponível no seu PATH de execução ou instalado diretamente em `~/.local/bin/piper`.

## Instalação

```bash
git clone https://github.com/geraldohomero/narro-rsa.git
cd narro-rsa
bash install.sh
```

O script `install.sh` copia os arquivos necessários para `~/.local/bin/` (incluindo o pacote `narro_rsa/`) e verifica as dependências.

## Desinstalação

Para remover completamente o Narro-RSA do sistema:

```bash
bash uninstall.sh
```

O script remove:
- Scripts e pacote instalados em `~/.local/bin/`
- Configurações salvas e vozes locais do Piper em `~/.config/narro-rsa/`
- Arquivos temporários em `$XDG_RUNTIME_DIR` (e `/tmp/` para instalações antigas)
- Processos em andamento (mpv, edge-tts, piper)

Após desinstalar, lembre-se de remover manualmente os atalhos de teclado configurados no GNOME.

## Configuração dos atalhos no GNOME

> [!NOTE]
> Os scripts `install.sh` e `uninstall.sh` agora configuram e removem esses atalhos **automaticamente** caso você utilize o ambiente GNOME.

Se precisar configurá-los ou ajustá-los manualmente, abra: Configurações -> Teclado -> Atalhos de teclado -> Atalhos personalizados:

### Atalho 1 — Abrir Leitor TTS
- Nome: `Leitor TTS (Narro)`
- Comando: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- Atalho: `Super+Alt+L`

### Atalho 2 — Abrir Leitor TTS (direto)
- Nome: `Leitor TTS (Narro) [Ctrl+\]`
- Comando: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- Atalho: `Ctrl+\` (Captura a seleção de texto ativa automaticamente sem a necessidade de Ctrl+C)

### Atalho 3 — Pausar/Retomar leitura (opcional)
- Nome: `Pausar leitura TTS (Narro)`
- Comando: `bash -c "$HOME/.local/bin/pausar_leitura.sh"`
- Atalho: `Super+Alt+J`

### Atalho 4 — Parar leitura (opcional)
- Nome: `Parar leitura TTS (Narro)`
- Comando: `bash -c "$HOME/.local/bin/parar_leitura.sh"`
- Atalho: `Super+Alt+K`

## Como usar

1. Abra um documento ou PDF (por exemplo, no Okular).
2. Selecione o texto desejado com a ferramenta de seleção.
3. Copie com Ctrl+C.
4. Pressione Super+Alt+L (ou o atalho configurado).
5. O player abrirá na tray do sistema.
6. Vá em Configurações para escolher o motor (Edge TTS ou Piper TTS), idioma e voz.
7. No diálogo que se abrirá, escolha a voz desejada. Caso esteja configurando o Piper, clique em "Baixar voz selecionada" antes de confirmar a seleção.
8. Clique em Play para iniciar a leitura.
9. Use Pause para pausar/retomar e Stop para parar.

## Estrutura do Projeto

```
narro-read-selection-aloud/
├── ler_texto.py           # Entrypoint — single-instance lock, signals, GTK main loop
├── config_dialog.py       # Diálogo de configurações GTK4 (processo separado)
├── narro_rsa/             # Pacote Python com a lógica do projeto
│   ├── __init__.py
│   ├── constants.py       # Constantes e caminhos centralizados
│   ├── settings.py        # Carrega/salva preferências JSON
│   ├── mpv_control.py     # Comunicação IPC com mpv via socket Unix
│   ├── text_formatter.py  # Formatação de texto para TTS (limpeza de PDFs)
│   ├── clipboard.py       # Captura de texto do clipboard (Wayland)
│   ├── tts_engine.py      # Motor TTS (Edge-TTS + Piper)
│   └── indicator.py       # AppIndicator3 na tray do GNOME
├── ler_texto.sh           # Wrapper shell para atalho do GNOME
├── parar_leitura.sh       # Script para interromper a leitura
├── install.sh             # Instalador do sistema
├── uninstall.sh           # Desinstalador
├── assets/                # Imagens e recursos visuais
└── README.md              # Documentação do projeto
```

## Licença

MIT
