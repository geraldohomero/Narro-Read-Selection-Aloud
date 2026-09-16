import os
import sys
import subprocess
from narro_rsa.constants import LOCKFILE

IS_FLATPAK = os.path.exists("/.flatpak-info")

def run_on_host(args, **kwargs):
    """Executa um comando no host se estiver rodando dentro do Flatpak."""
    if IS_FLATPAK:
        # Garante que passamos os argumentos como strings
        args = ["flatpak-spawn", "--host"] + [str(a) for a in args]
    return subprocess.run(args, **kwargs)

def popen_on_host(args, **kwargs):
    """Inicia um subprocesso no host se estiver rodando dentro do Flatpak."""
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
    """Verifica se um PID está ativo no host ou no sandbox."""
    if IS_FLATPAK:
        try:
            res = subprocess.run(["flatpak-spawn", "--host", "kill", "-0", str(pid)], capture_output=True, timeout=1)
            return res.returncode == 0
        except OSError:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

def find_installed_daemon() -> str | None:
    """Procura o script ler_texto.py no host nos caminhos do Flatpak ou no local bin antigo."""
    paths = [
        os.path.expanduser("~/.local/share/flatpak/app/com.github.geraldohomero.NarroRsa/current/active/files/bin/ler_texto.py"),
        "/var/lib/flatpak/app/com.github.geraldohomero.NarroRsa/current/active/files/bin/ler_texto.py",
        os.path.expanduser("~/.local/bin/ler_texto.py")
    ]
    for p in paths:
        if check_host_file_exists(p):
            return p
    return None

def check_and_start_daemon():
    """Garante que o daemon ler_texto.py esteja executando em segundo plano."""
    daemon_running = False
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r", encoding="utf-8") as fh:
                pid = int(fh.read().strip())
            if check_pid_active(pid):
                daemon_running = True
            else:
                try:
                    os.unlink(LOCKFILE)
                except OSError:
                    pass
        except (ValueError, OSError):
            try:
                os.unlink(LOCKFILE)
            except OSError:
                pass

    if not daemon_running:
        if IS_FLATPAK:
            host_script = find_installed_daemon()
            if host_script:
                subprocess.Popen(
                    [
                        "flatpak-spawn",
                        "--host",
                        "sh",
                        "-c",
                        f'nohup python3 "{host_script}" --daemon >/dev/null 2>&1 &',
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
        else:
            # Em modo tradicional, localiza ler_texto.py no mesmo diretório do arquivo principal
            script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
            ler_texto_script = os.path.join(script_dir, "ler_texto.py")
            if os.path.exists(ler_texto_script):
                subprocess.Popen(
                    [sys.executable, ler_texto_script, "--daemon"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
