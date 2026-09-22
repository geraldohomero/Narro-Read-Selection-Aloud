import os
import sys
import subprocess
from narro_rsa.constants import LOCKFILE

IS_FLATPAK = os.path.exists("/.flatpak-info")

def run_command(args, **kwargs):
    """Executa um comando no ambiente local (sandbox Flatpak ou host se fora do Flatpak)."""
    return subprocess.run(args, **kwargs)

def popen_command(args, **kwargs):
    """Inicia um subprocesso no ambiente local (sandbox Flatpak ou host se fora do Flatpak)."""
    return subprocess.Popen(args, **kwargs)

def run_on_host(args, **kwargs):
    """Executa explicitamente um comando no host se estiver rodando dentro do Flatpak."""
    if IS_FLATPAK:
        args = ["flatpak-spawn", "--host"] + [str(a) for a in args]
    return subprocess.run(args, **kwargs)

def popen_on_host(args, **kwargs):
    """Inicia explicitamente um subprocesso no host se estiver rodando dentro do Flatpak."""
    if IS_FLATPAK:
        args = ["flatpak-spawn", "--host"] + [str(a) for a in args]
    return subprocess.Popen(args, **kwargs)

def check_host_file_exists(path: str) -> bool:
    """Verifica se um arquivo existe no host quando dentro do Flatpak."""
    if IS_FLATPAK:
        try:
            res = subprocess.run(["flatpak-spawn", "--host", "test", "-f", path], capture_output=True, timeout=1)
            return res.returncode == 0
        except OSError:
            return False
    return os.path.exists(path)

def check_pid_active(pid: int) -> bool:
    """Verifica se um PID está ativo."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def check_and_start_daemon():
    """Verifica se o daemon ler_texto.py está ativo.
    
    Dentro do Flatpak ou quando executando a aplicação unificada, a janela principal
    e o modo CLI gerenciam a reprodução diretamente sem necessitar de daemon externo.
    """
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r", encoding="utf-8") as fh:
                pid = int(fh.read().strip())
            if not check_pid_active(pid):
                try:
                    os.unlink(LOCKFILE)
                except OSError:
                    pass
        except (ValueError, OSError):
            try:
                os.unlink(LOCKFILE)
            except OSError:
                pass

