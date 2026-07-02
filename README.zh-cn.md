# Narro - 朗读选中文本 (Read Selection Aloud)

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

适用于 GNOME/Wayland 的文本转语音 (TTS) 朗读工具，支持 Edge TTS (在线) 和 Piper TTS (离线)。

在任何应用程序中选择文本，使用 Ctrl+C 复制，然后使用键盘快捷键打开 TTS 播放器 —— 包含播放/暂停/停止控制、引擎/语言/声音选择以及语速控制。

![TTS Player](https://img.shields.io/badge/GTK3-Player-blue?style=for-the-badge)

![image-hero](assets/image-hero.png)

## 功能特性

- 完整的播放控制（播放、暂停、停止）。
- 支持两种语音合成引擎：Edge TTS (云端神经网络语音) 和 Piper TTS (运行于本地且完全离线的极速语音)。
- 全新的语音选择标签页，结构为：声音 -> 引擎 (Edge TTS 或 Piper TTS) -> 语言 -> 选择。
- 原生 GTK4 配置对话框，可以列出可用声音，显示本地模型（Piper）的下载状态，并允许直接在界面中下载模型（带实时进度条）。
- 已下载的 Piper 声音保存在用户本地配置文件夹中 (`~/.config/narro-rsa/piper-voices/`)。
- 通过 mpv 进行实时语速控制（适用于两种引擎）。
- 原生 GTK 界面，与 GNOME 视觉深度集成。
- 状态栏提供进程反馈信息。

## 依赖项

| 软件包 | 安装方式 |
|---|---|
| edge-tts | pipx install edge-tts |
| piper-tts | pipx install piper-tts 或将 piper 二进制文件安装到 PATH (例如 ~/.local/bin/piper) |
| mpv | sudo dnf install mpv |
| wl-clipboard | sudo dnf install wl-clipboard |
| python3-gobject | sudo dnf install python3-gobject |
| gtk3 | sudo dnf install gtk3 |
| gtk4 | sudo dnf install gtk4 |
| libnotify | sudo dnf install libnotify |

安装依赖项的命令：

```bash
sudo dnf install wl-clipboard mpv python3-gobject gtk3 gtk4 libnotify
pipx install edge-tts
```

注意：若要使用 Piper TTS，请确保 `piper` 可执行文件在您的运行 PATH 中，或者直接安装在 `~/.local/bin/piper`。

## 安装步骤

```bash
git clone https://github.com/geraldohomero/narro-rsa.git
cd narro-rsa
bash install.sh
```

`install.sh` 脚本会将所需的文件复制到 `~/.local/bin/`（包括 `narro_rsa/` 包）并检查依赖项。

## 卸载步骤

要从系统中完全删除 Narro-RSA：

```bash
bash uninstall.sh
```

该脚本将删除：
- 安装在 `~/.local/bin/` 中的脚本和包
- 保存在 `~/.config/narro-rsa/` 中的设置和本地 Piper 语音
- `$XDG_RUNTIME_DIR`（以及旧版本安装的 `/tmp/`）中的临时文件
- 正在运行的进程 (mpv, edge-tts, piper)

卸载后，请记得手动删除在 GNOME 中配置的键盘快捷键。

## GNOME 快捷键配置

> [!NOTE]
> 如果您使用的是 GNOME 环境，`install.sh` 和 `uninstall.sh` 脚本现在将**自动**配置和删除这些快捷键。

如果您需要手动配置或调整它们，请打开：设置 -> 键盘 -> 键盘快捷键 -> 自定义快捷键：

### 快捷键 1 —— 打开 TTS 朗读器
- 名称: `Leitor TTS (Narro)`
- 命令: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- 快捷键: `Super+Alt+L`

### 快捷键 2 —— 直接打开 TTS 朗读器 (自动复制并朗读)
- 名称: `Leitor TTS (Narro) [Ctrl+\]`
- 命令: `bash -c "$HOME/.local/bin/ler_texto.sh"`
- 快捷键: `Ctrl+\` (自动捕获当前选中的文本并开始朗读，无需先按 Ctrl+C 复制)

### 快捷键 3 —— 暂停/恢复 TTS 朗读 (可选)
- 名称: `Pausar leitura TTS (Narro)`
- 命令: `bash -c "$HOME/.local/bin/pausar_leitura.sh"`
- 快捷键: `Super+Alt+J`

### 快捷键 4 —— 停止 TTS 朗读 (可选)
- 名称: `Parar leitura TTS (Narro)`
- 命令: `bash -c "$HOME/.local/bin/parar_leitura.sh"`
- 快捷键: `Super+Alt+K`

## 使用方法

1. 打开一个文档或 PDF（例如在 Okular 中）。
2. 使用选择工具选中所需的文本。
3. 使用 Ctrl+C 复制。
4. 按下 Super+Alt+L（或您配置的快捷键）。
5. 播放器将在系统托盘中打开。
6. 进入“设置”选择引擎（Edge TTS 或 Piper TTS）、语言和声音。
7. 在打开的对话框中选择您喜欢的声音。如果配置的是 Piper，请在确认选择之前点击“下载所选声音”。
8. 点击“播放”开始朗读。
9. 使用“暂停”进行暂停/恢复，使用“停止”结束朗读。

## 项目结构

```
narro-read-selection-aloud/
├── ler_texto.py           # 入口点 —— 单例锁、信号、GTK 主循环
├── config_dialog.py       # GTK4 配置对话框（独立进程）
├── narro_rsa/             # 包含项目逻辑的 Python 包
│   ├── __init__.py
│   ├── constants.py       # 集中管理常量和路径
│   ├── settings.py        # 加载/保存 JSON 偏好设置
│   ├── mpv_control.py     # 通过 Unix 套接字与 mpv 进行 IPC 通信
│   ├── text_formatter.py  # 用于 TTS 的文本格式化（清理 PDF 文本）
│   ├── clipboard.py       # 剪贴板文本捕获 (Wayland)
│   ├── tts_engine.py      # TTS 引擎 (Edge-TTS + Piper)
│   └── indicator.py       # GNOME 托盘中的 AppIndicator3
├── ler_texto.sh           # GNOME 快捷键的 Shell 包装器
├── parar_leitura.sh       # 停止朗读的脚本
├── install.sh             # 系统安装脚本
├── uninstall.sh           # 卸载脚本
├── assets/                # 图像和视觉资源
└── README.md              # 项目文档
```

## 许可证

MIT
