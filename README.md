# edge-tts-okular

Leitor de texto em voz alta com **edge-tts** para o Okular no GNOME/Wayland (Fedora).

Selecione texto no Okular, copie com `Ctrl+C`, e use um atalho de teclado para abrir o player TTS — com controles de **Play/Pause/Stop**, seletor de **idioma/voz** e **velocidade**.

![Player TTS](https://img.shields.io/badge/GTK3-Player-blue?style=for-the-badge)

## ✨ Funcionalidades

- ▶️ **Play / ⏸ Pause / ⏹ Stop** — Controles completos de reprodução
- 🎙️ **20+ vozes neurais** — Português (BR/PT), English, Español, Français, Deutsch
- ⚡ **Controle de velocidade** — De -50% até +100%
- 🖥️ **Interface GTK nativa** — Integração visual com o GNOME (tema escuro)
- ✏️ **Texto editável** — Edite o texto capturado antes de reproduzir
- 🔔 **Barra de status** — Feedback visual em tempo real
- 🔄 **Toggle** — Pressione o atalho novamente para fechar o player

## 📦 Dependências

| Pacote | Instalação |
|---|---|
| edge-tts | `pipx install edge-tts` |
| mpv | `sudo dnf install mpv` |
| wl-clipboard | `sudo dnf install wl-clipboard` |
| python3-gobject | `sudo dnf install python3-gobject` |
| gtk3 | `sudo dnf install gtk3` |
| libnotify | `sudo dnf install libnotify` |

```bash
sudo dnf install wl-clipboard mpv python3-gobject gtk3 libnotify
pipx install edge-tts
```

## 🚀 Instalação

```bash
git clone https://github.com/SEU_USUARIO/edge-tts-okular.git
cd edge-tts-okular
bash install.sh
```

O script `install.sh` copia os arquivos para `~/.local/bin/` e verifica as dependências.

## 🗑️ Desinstalação

Para remover completamente o edge-tts-okular do sistema:

```bash
bash uninstall.sh
```

O script remove:
- Scripts instalados em `~/.local/bin/`
- Configurações salvas em `~/.config/edge-tts-okular/`
- Arquivos temporários em `/tmp/`
- Processos em andamento

> 💡 Após desinstalar, lembre-se de remover manualmente os atalhos de teclado configurados no GNOME.

## ⌨️ Configuração dos atalhos no GNOME

Abra: **Configurações → Teclado → Atalhos de teclado → Atalhos personalizados**

### Atalho 1 — Abrir Leitor TTS
| Campo | Valor |
|---|---|
| Nome | Leitor TTS |
| Comando | `bash -c "$HOME/.local/bin/ler_texto.sh"` |
| Atalho | `Super+Alt+L` (sugestão) |

### Atalho 2 — Parar leitura (opcional)
| Campo | Valor |
|---|---|
| Nome | Parar leitura TTS |
| Comando | `bash -c "$HOME/.local/bin/parar_leitura.sh"` |
| Atalho | `Super+Alt+K` (sugestão) |

## 🎯 Como usar

1. Abra um PDF no **Okular**
2. Selecione o texto desejado com a ferramenta de seleção
3. Copie com **Ctrl+C**
4. Pressione **Super+Alt+L** (ou o atalho configurado)
5. O player TTS abrirá com o texto capturado
6. Escolha a **voz** e a **velocidade** nos seletores
7. Clique **▶ Play** para iniciar a leitura
8. Use **⏸ Pause** para pausar/retomar e **⏹ Stop** para parar

## 📂 Estrutura

```
edge-tts-okular/
├── ler_texto.py       # App GTK principal (player com controles)
├── ler_texto.sh       # Wrapper shell para atalho do GNOME
├── parar_leitura.sh   # Script para interromper a leitura
├── install.sh         # Instalador
├── uninstall.sh       # Desinstalador
└── README.md
```

## 🗣️ Vozes disponíveis

| Código | Idioma | Gênero |
|---|---|---|
| pt-BR-AntonioNeural | Português BR | Masculino |
| pt-BR-FranciscaNeural | Português BR | Feminino |
| pt-BR-ThalitaMultilingualNeural | Português BR | Feminino (Multilíngue) |
| pt-PT-DuarteNeural | Português PT | Masculino |
| pt-PT-RaquelNeural | Português PT | Feminino |
| en-US-AriaNeural | English US | Female |
| en-US-ChristopherNeural | English US | Male |
| en-US-AvaNeural | English US | Female |
| en-US-BrianNeural | English US | Male |
| en-US-AndrewNeural | English US | Male |
| en-US-EmmaMultilingualNeural | English US | Female (Multilingual) |
| en-GB-RyanNeural | English GB | Male |
| en-GB-SoniaNeural | English GB | Female |
| es-ES-AlvaroNeural | Español ES | Masculino |
| es-ES-ElviraNeural | Español ES | Femenino |
| fr-FR-HenriNeural | Français FR | Masculin |
| fr-FR-DeniseNeural | Français FR | Féminin |
| de-DE-ConradNeural | Deutsch DE | Männlich |
| de-DE-KatjaNeural | Deutsch DE | Weiblich |

> 💡 Para adicionar mais vozes, edite o array `VOICES` em `ler_texto.py`. Liste todas as disponíveis com: `edge-tts --list-voices`

## 📄 Licença

MIT
