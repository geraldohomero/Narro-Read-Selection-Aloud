"""Desktop notifications helper for Narro-RSA.

Supports libnotify via PyGObject with fallback to notify-send CLI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional


_NOTIFY_INITIALIZED: bool = False


def _init_libnotify() -> bool:
    global _NOTIFY_INITIALIZED
    if _NOTIFY_INITIALIZED:
        return True
    try:
        import gi
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify
        if Notify.init("Narro-RSA"):
            _NOTIFY_INITIALIZED = True
            return True
    except Exception:
        pass
    return False


def _send_via_libnotify(title: str, message: str, icon: str = "dialog-information", timeout_ms: int = 3000) -> bool:
    try:
        if not _init_libnotify():
            return False
        from gi.repository import Notify
        n = Notify.Notification.new(title, message, icon)
        n.set_timeout(timeout_ms)
        return bool(n.show())
    except Exception:
        return False


def _send_via_notify_send(title: str, message: str, icon: str = "dialog-information", timeout_ms: int = 3000) -> bool:
    try:
        notify_bin = shutil.which("notify-send")
        if not notify_bin and os.path.exists("/usr/bin/notify-send"):
            notify_bin = "/usr/bin/notify-send"
        if not notify_bin:
            return False
        cmd = [
            notify_bin,
            "-a", "Narro-RSA",
            "-i", icon,
            "-t", str(timeout_ms),
            title,
            message,
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def send_notification(
    title: str,
    message: str,
    icon: str = "dialog-information",
    timeout_ms: int = 3000,
) -> bool:
    """Envia uma notificação desktop utilizando libnotify ou notify-send."""
    if _send_via_libnotify(title, message, icon, timeout_ms):
        return True
    return _send_via_notify_send(title, message, icon, timeout_ms)


def preview_text(text: str, max_chars: int = 60) -> str:
    """Limpa e formata uma prévia do texto para exibição na notificação."""
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "..."
