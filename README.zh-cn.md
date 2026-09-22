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

#### 1. 安装 Flatpak 包：
```bash
flatpak install --user ./com.github.geraldohomero.NarroRsa.flatpak
```
*或直接从清单构建：*
```bash
flatpak-builder --user --install --force-clean --disable-rofiles-fuse build-dir com.github.geraldohomero.NarroRsa.yaml
```

#### 2. 运行应用：
```bash
flatpak run com.github.geraldohomero.NarroRsa
```

*(在首次启动图形界面时，GNOME 自定义快捷键将自动创建并指向 Flatpak 命令！)*

---

## GNOME 快捷键

应用会自动为您在 GNOME 中配置对应的快捷键：

- **朗读剪贴板** (`Super+Alt+L`): `flatpak run com.github.geraldohomero.NarroRsa --play`
- **直接朗读选中文本** (`Ctrl+\`): `flatpak run com.github.geraldohomero.NarroRsa --primary`
- **暂停/恢复播放** (`Super+Alt+J`): `flatpak run com.github.geraldohomero.NarroRsa --pause`
- **停止播放** (`Super+Alt+K`): `flatpak run com.github.geraldohomero.NarroRsa --stop`

---

## 卸载步骤

卸载 Flatpak 应用：
```bash
flatpak remove com.github.geraldohomero.NarroRsa
```

---

## 项目结构

```
narro-read-selection-aloud/
├── main_window.py         # GTK4 / Libadwaita 主窗口 (内置滑动页面导航与汉堡菜单)
├── ler_texto.py           # 托盘与后台朗读守护进程
├── narro_rsa/             # 包含核心业务逻辑的 Python 包
│   ├── translations.py    # 集中式多语言翻译与格式化辅助模块
│   ├── reader_page.py     # 朗读播放器界面组件
│   ├── settings_page.py   # 集成语言搜索的配置设置界面
│   ├── constants.py       # 集中管理路径和常量
│   ├── settings.py        # 加载/保存 JSON 首选项
│   ├── mpv_control.py     # 通过 Unix 域套接字与 mpv 进行 IPC 通信
│   ├── text_formatter.py  # 朗读文本前置格式化（净化PDF噪声）
│   ├── clipboard.py       # 智能 Wayland 剪贴板解析
│   ├── subprocess_helper.py # 子进程与守护进程辅助工具
│   └── tts_engine.py      # 音频生成引擎 (Edge-TTS + Piper)
├── com.github.geraldohomero.NarroRsa.flatpak      # 独立自包含 Flatpak 安装包
├── com.github.geraldohomero.NarroRsa.yaml         # Flatpak 清单
├── com.github.geraldohomero.NarroRsa.desktop      # 桌面快捷方式条目
├── com.github.geraldohomero.NarroRsa.metainfo.xml # AppStream 元数据
└── assets/                # 图标及其他视觉资源
```

## 许可证

MIT
