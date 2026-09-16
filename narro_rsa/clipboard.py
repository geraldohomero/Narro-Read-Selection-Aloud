"""Acesso à área de transferência do Wayland e X11.

Captura texto do clipboard ou seleção primária com detecção inteligente de atualizações.
"""

from __future__ import annotations

import os
import subprocess
import time

from .constants import LAST_CLIPBOARD_FILE, LAST_PRIMARY_FILE, LAST_READ_FILE
from .subprocess_helper import run_on_host


def _read_tool(cmd: list[str]) -> str:
    """Executa um comando no host e retorna stdout limpo, ou string vazia."""
    try:
        res = run_on_host(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout:
            return res.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _is_wayland_session() -> bool:
    """Verifica se a sessão atual é Wayland."""
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _get_raw_clipboard() -> str:
    """Captura o texto da área de transferência padrão (Ctrl+C)."""
    if _is_wayland_session():
        txt = _read_tool(["wl-paste", "--no-newline"])
        if txt:
            return txt

    for cmd in (["xclip", "-o", "-selection", "clipboard"], ["xsel", "-b", "-o"]):
        txt = _read_tool(cmd)
        if txt:
            return txt

    if not _is_wayland_session():
        txt = _read_tool(["wl-paste", "--no-newline"])
        if txt:
            return txt

    return ""


def _get_raw_primary() -> str:
    """Captura o texto da seleção primária (texto destacado pelo mouse)."""
    if _is_wayland_session():
        txt = _read_tool(["wl-paste", "--primary", "--no-newline"])
        if txt:
            return txt

    for cmd in (["xclip", "-o", "-selection", "primary"], ["xsel", "-p", "-o"]):
        txt = _read_tool(cmd)
        if txt:
            return txt

    if not _is_wayland_session():
        txt = _read_tool(["wl-paste", "--primary", "--no-newline"])
        if txt:
            return txt

    return ""


def _read_saved_file(path: str) -> str:
    """Lê o conteúdo de um arquivo de snapshot salvo se existir."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            pass
    return ""


def _save_snapshot(raw_clip: str, raw_prim: str) -> None:
    """Salva os snapshots do clipboard e seleção primária para rastreamento de mudanças."""
    try:
        with open(LAST_CLIPBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(raw_clip)
    except OSError:
        pass

    try:
        with open(LAST_PRIMARY_FILE, "w", encoding="utf-8") as fh:
            fh.write(raw_prim)
    except OSError:
        pass


def _simulate_copy() -> None:
    """Tenta enviar Ctrl+C para a janela ativa para copiar a seleção em leitores como o Zotero."""
    script = """
import time
try:
    from evdev import UInput, ecodes as e
    cap = {e.EV_KEY: [e.KEY_LEFTCTRL, e.KEY_C]}
    with UInput(cap, name="narro-keyboard") as ui:
        time.sleep(0.02)
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
        ui.syn()
        ui.write(e.EV_KEY, e.KEY_C, 1)
        ui.syn()
        time.sleep(0.02)
        ui.write(e.EV_KEY, e.KEY_C, 0)
        ui.syn()
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
        ui.syn()
        time.sleep(0.02)
except Exception:
    import subprocess
    try:
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+c"], timeout=1)
    except Exception:
        pass
"""
    try:
        run_on_host(["python3", "-c", script], timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        pass


def get_clipboard_text(primary: bool = False) -> str:
    """Captura texto da área de transferência com resolução inteligente.

    Compara a seleção primária (texto selecionado com o mouse) e o clipboard
    padrão (Ctrl+C / cópia explícita). Se um deles tiver conteúdo recém-atualizado,
    prioriza o mais recente, evitando ficar preso em seleções antigas.
    Em aplicativos como o Zotero onde a seleção do leitor não atualiza os buffers
    do SO automaticamente, tenta simular cópia (Ctrl+C) na janela ativa.

    Args:
        primary: Se True (ex: atalho Ctrl+\\), dá preferência à seleção primária
                 caso ambos tenham sido atualizados ou nenhum tenha mudado.
                 Se False (ex: Super+Alt+L), dá preferência ao clipboard padrão.

    Returns:
        Texto bruto da seleção/clipboard, ou string vazia se nenhum encontrado.
    """
    raw_clip = _get_raw_clipboard()
    raw_prim = _get_raw_primary()

    if not raw_clip and not raw_prim:
        if primary:
            _simulate_copy()
            for _ in range(6):
                time.sleep(0.04)
                new_clip = _get_raw_clipboard()
                if new_clip:
                    _save_snapshot(new_clip, "")
                    return new_clip
        return ""

    last_clip = _read_saved_file(LAST_CLIPBOARD_FILE)
    last_prim = _read_saved_file(LAST_PRIMARY_FILE)
    last_read = _read_saved_file(LAST_READ_FILE)

    clip_changed = bool(raw_clip and raw_clip != last_clip and raw_clip != last_read)
    prim_changed = bool(raw_prim and raw_prim != last_prim and raw_prim != last_read)

    if raw_clip and not raw_prim:
        if primary and not clip_changed:
            _simulate_copy()
            for _ in range(6):
                time.sleep(0.04)
                new_clip = _get_raw_clipboard()
                if new_clip and new_clip != raw_clip:
                    _save_snapshot(new_clip, "")
                    return new_clip
        _save_snapshot(raw_clip, "")
        return raw_clip

    if raw_prim and not raw_clip:
        _save_snapshot("", raw_prim)
        return raw_prim

    # 1. Se ambos têm o mesmo texto e esse texto é NOVO (diferente da última leitura):
    if raw_clip == raw_prim and raw_clip != last_read:
        _save_snapshot(raw_clip, raw_prim)
        return raw_clip

    # 2. Se a seleção primária tem texto NOVO (ex: Okular, navegadores, gedit):
    if prim_changed and not clip_changed:
        _save_snapshot(raw_clip, raw_prim)
        return raw_prim

    # 3. Se o clipboard padrão tem texto NOVO (ex: usuário usou Ctrl+C explicitamente):
    if clip_changed and not prim_changed:
        _save_snapshot(raw_clip, raw_prim)
        return raw_clip

    # 4. Se nenhum dos dois tem texto novo (ex: o usuário selecionou texto no leitor do Zotero,
    # que não atualiza a seleção primária nem o clipboard do SO):
    # Simula Ctrl+C na janela ativa para capturar a seleção!
    if primary and not clip_changed and not prim_changed:
        _simulate_copy()
        for _ in range(6):
            time.sleep(0.04)
            new_clip = _get_raw_clipboard()
            if new_clip and new_clip != raw_clip:
                _save_snapshot(new_clip, raw_prim)
                return new_clip
            new_prim = _get_raw_primary()
            if new_prim and new_prim != raw_prim:
                _save_snapshot(raw_clip, new_prim)
                return new_prim

    # 5. Fallback padrão:
    chosen = raw_prim if primary else raw_clip
    _save_snapshot(raw_clip, raw_prim)
    return chosen
