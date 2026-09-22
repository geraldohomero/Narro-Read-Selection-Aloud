# Narro - Ler seleção em voz alta

<p align="center">
  <img src="assets/com.github.geraldohomero.NarroRsa.png" alt="Narro-RSA Logo" width="128" height="128">
</p>

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

Leitor de texto em voz alta com suporte a Edge TTS (online) e Piper TTS (offline) para o GNOME/Wayland, apresentando uma aplicação GTK4 nativa totalmente integrada e suporte para empacotamento Flatpak.

Selecione texto em qualquer aplicativo, copie com Ctrl+C, e use um atalho de teclado para abrir o player TTS — com controles de Play/Pause/Stop, seleção de motor/idioma/voz, controle de velocidade e visualizador de histórico de leitura.

![image-hero](assets/image-hero.png)

## Funcionalidades

- **Janela GTK4 Nativa Integrada**: Visualize, edite e leia o texto do clipboard diretamente de uma linda interface integrada ao visual do GNOME.
- **Ícone de Desktop Sóbrio**: Ícone personalizado transparente em formato de folha de papel compatível com as diretrizes do GNOME/Flatpak.
- **Dois Motores de Síntese**: Edge TTS (vozes neurais da nuvem) e Piper TTS (vozes locais ultrarrápidas rodando totalmente offline).
- **Atalhos de Teclado Auto-configurados**: Configura automaticamente as teclas de atalho globais no primeiro início da interface gráfica.
- **Diálogo de Configurações Dinâmico**: Permite gerenciar as vozes disponíveis, monitorar o download de modelos locais (Piper) com barra de progresso em tempo real e alterar o motor de reprodução.
- **Controle de Velocidade em Tempo Real**: Altere a velocidade da fala dinamicamente via mpv.
- **Indicador de Bandeja do Sistema**: Um indicador na bandeja (AppIndicator) opcional rodando no host que permite controlar e abrir a aplicação rapidamente.

---

## Opções de Instalação

### Opção 1: Flatpak (Recomendado e Autossuficiente)

A instalação via Flatpak é a mais simples. Ela empacota todas as dependências em uma sandbox, não requer configuração manual no host e configura os atalhos de teclado no GNOME automaticamente.

#### 1. Instale o pacote Flatpak:
```bash
flatpak install --user ./com.github.geraldohomero.NarroRsa.flatpak
```
*Ou compile diretamente do manifesto:*
```bash
flatpak-builder --user --install --force-clean --disable-rofiles-fuse build-dir com.github.geraldohomero.NarroRsa.yaml
```

#### 2. Execute a aplicação:
```bash
flatpak run com.github.geraldohomero.NarroRsa
```

*(No primeiro início da interface, os atalhos de teclado personalizados no GNOME serão criados automaticamente direcionados para o Flatpak!)*

---

## Atalhos de Teclado no GNOME

O aplicativo gerencia a criação desses atalhos de forma automática no GNOME:

- **Ler área de transferência** (`Super+Alt+L`): `flatpak run com.github.geraldohomero.NarroRsa --play`
- **Ler seleção direta** (`Ctrl+\`): `flatpak run com.github.geraldohomero.NarroRsa --primary`
- **Pausar/Retomar** (`Super+Alt+J`): `flatpak run com.github.geraldohomero.NarroRsa --pause`
- **Parar reprodução** (`Super+Alt+K`): `flatpak run com.github.geraldohomero.NarroRsa --stop`

---

## Desinstalação

Para remover a aplicação Flatpak:
```bash
flatpak remove com.github.geraldohomero.NarroRsa
```

---

## Estrutura do Projeto

```
narro-read-selection-aloud/
├── main_window.py         # Janela Principal GTK4 / Libadwaita (com navegação integrada e menu Hambúrguer)
├── ler_texto.py           # Daemon do leitor e bandeja
├── narro_rsa/             # Pacote Python com lógica do projeto
│   ├── translations.py    # Dicionário de traduções centralizado
│   ├── reader_page.py     # Componente da interface do Leitor
│   ├── settings_page.py   # Página de Configurações com busca integrada
│   ├── constants.py       # Constantes e caminhos centralizados
│   ├── settings.py        # Gerenciamento de preferências
│   ├── mpv_control.py     # Controles via socket IPC Unix para o mpv
│   ├── text_formatter.py  # Limpeza de texto para leituras de PDFs
│   ├── clipboard.py       # Resolução inteligente de clipboard Wayland
│   ├── subprocess_helper.py # Utilitários de subprocessos e daemon
│   └── tts_engine.py      # Gerador de áudio (Edge-TTS + Piper)
├── com.github.geraldohomero.NarroRsa.flatpak      # Pacote Flatpak completo autocontido
├── com.github.geraldohomero.NarroRsa.yaml         # Manifesto Flatpak
├── com.github.geraldohomero.NarroRsa.desktop      # Entrada de atalho desktop
├── com.github.geraldohomero.NarroRsa.metainfo.xml # Metadados AppStream
└── assets/                # Ícone e recursos visuais
```

## Licença

MIT
