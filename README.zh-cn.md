# Narro - 朗读选中文本 (Read Selection Aloud)

<p align="center">
  <img src="assets/com.github.geraldohomero.NarroRsa.png" alt="Narro-RSA Logo" width="128" height="128">
</p>

[English](README.md) | [Português (Brasil)](README.pt-br.md) | [简体中文](README.zh-cn.md)

适用于 GNOME/Wayland 的文本转语音 (TTS) 朗读工具，支持 Edge TTS (在线) 和 Piper TTS (离线)。现已全面支持原生 GTK4 窗口应用整合及 Flatpak 打包支持。

在任何应用程序中选择文本，使用 Ctrl+C 复制，然后使用键盘快捷键打开 TTS 播放器 —— 包含播放/暂停/停止控制、引擎/语言/声音选择、语速控制以及历史文本查看器。

![image-hero](assets/image-hero.png)

## 功能特性

- **集成式 GTK4 原生窗口**：直接在精美的 GNOME HIG 界面中查看、编辑并朗读剪贴板文本。
- **端庄的桌面图标**：符合 GNOME/Flatpak 桌面规范的自定义透明文档图标。
- **双语音合成引擎**：支持 Edge TTS (云端神经网络语音) 和 Piper TTS (运行于本地且完全离线的极速语音)。
- **自动配置键盘快捷键**：在首次启动图形界面时，自动为您在 GNOME 中注册全局快捷键。
- **动态配置对话框**：直接在主窗口中管理可用声音、展示 Piper 本地语音下载进度（带实时进度条），并设置偏好。
- **实时语速控制**：通过集成 mpv 播放器实时动态调整语音播放速度。
- **系统托盘集成**：可选的运行于宿主机的系统托盘指示器 (AppIndicator)，以便快速调出或控制应用。

---

## 安装方式

### 方案 1：Flatpak 安装（推荐，完全独立）

使用 Flatpak 是最简便的安装方法。它将所有依赖项隔离打包在沙盒中，不需要在宿主机手动配置各种底层库，并在首次启动时自动写入 GNOME 键盘快捷键。

#### 1. 在本地编译并安装 Flatpak 包：
```bash
flatpak-builder --user --install --force-clean --disable-rofiles-fuse build-dir com.github.geraldohomero.NarroRsa.yaml
```

#### 2. 运行应用：
```bash
flatpak run com.github.geraldohomero.NarroRsa
```

*(在首次启动图形界面时，GNOME 自定义快捷键将自动创建并指向 Flatpak 命令！)*

---

### 方案 2：传统安装（宿主机脚本）

如果您更倾向于直接使用系统的 Python 解释器在宿主机运行：

#### 1. 安装系统依赖项：
- **Fedora**: `sudo dnf install wl-clipboard mpv libnotify python3-gobject gtk3 gtk4 libappindicator-gtk3`
- **Ubuntu/Debian**: `sudo apt install wl-clipboard mpv libnotify-bin python3-gi gir1.2-gtk-3.0 gir1.2-gtk-4.0 gir1.2-ayatanaappindicator3-0.1`
- **Arch Linux**: `sudo pacman -S wl-clipboard mpv libnotify python-gobject gtk3 gtk4 libayatana-appindicator`

#### 2. 安装 Python TTS 发音引擎：
```bash
pipx install edge-tts
pipx install piper-tts  # 可选的离线本地 TTS 发音引擎
```

#### 3. 运行安装程序：
```bash
git clone https://github.com/geraldohomero/narro-rsa.git
cd narro-rsa
bash install.sh
```

---

## GNOME 快捷键

应用会自动为您在 GNOME 中配置对应的快捷键，执行的命令由于安装方式的不同而有所区别：

### 针对 Flatpak 安装：
- **朗读剪贴板** (`Super+Alt+L`): `flatpak run com.github.geraldohomero.NarroRsa --play`
- **直接朗读选中文本** (`Ctrl+\`): `flatpak run com.github.geraldohomero.NarroRsa --primary`
- **暂停/恢复播放** (`Super+Alt+J`): `flatpak run com.github.geraldohomero.NarroRsa --pause`
- **停止播放** (`Super+Alt+K`): `flatpak run com.github.geraldohomero.NarroRsa --stop`

### 针对传统安装：
- **朗读剪贴板** (`Super+Alt+L`): `bash -c "$HOME/.local/bin/ler_texto.sh"`
- **直接朗读选中文本** (`Ctrl+\`): `bash -c "$HOME/.local/bin/ler_texto.sh --primary"`
- **暂停/恢复播放** (`Super+Alt+J`): `bash -c "$HOME/.local/bin/pausar_leitura.sh"`
- **停止播放** (`Super+Alt+K`): `bash -c "$HOME/.local/bin/parar_leitura.sh"`

---

## 卸载步骤

### 卸载 Flatpak 应用：
```bash
flatpak remove com.github.geraldohomero.NarroRsa
```

### 卸载宿主机本地脚本：
```bash
bash uninstall.sh
```

---

## 项目结构

```
narro-read-selection-aloud/
├── main_window.py         # 入口点及 GTK4 主窗口 (带有 Gtk.Stack 与汉堡包导航菜单)
├── ler_texto.py           # AppIndicator3 托盘守护进程 (GTK3)
├── narro_rsa/             # 包含核心业务逻辑的 Python 包
│   ├── translations.py    # 集中式多语言翻译与格式化辅助模块
│   ├── reader_page.py     # 朗读播放器界面 GTK4 组件
│   ├── settings_page.py   # 配置设置界面 GTK4 组件
│   ├── constants.py       # 集中管理路径和常量
│   ├── settings.py        # 加载/保存 JSON 首选项
│   ├── mpv_control.py     # 通过 Unix 域套接字与 mpv 进行 IPC 通信
│   ├── text_formatter.py  # 朗读文本前置格式化（净化PDF噪声）
│   ├── clipboard.py       # Wayland 剪贴板文本捕获
│   ├── subprocess_helper.py # 子进程与守护进程辅助工具
│   └── tts_engine.py      # 音频生成引擎 (Edge-TTS + Piper)
├── com.github.geraldohomero.NarroRsa.yaml         # Flatpak 清单
├── com.github.geraldohomero.NarroRsa.desktop      # 桌面快捷方式条目
├── com.github.geraldohomero.NarroRsa.metainfo.xml # AppStream 元数据
├── install.sh             # 宿主机安装脚本
└── assets/                # 图标及其他视觉资源
```

## 许可证

MIT
