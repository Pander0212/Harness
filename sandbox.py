"""Pfadschutz, Ausgabe-Kürzung und bash-Ausführung (optional in bubblewrap)."""
import os
import shutil
import signal
import site
import subprocess
import sys
import tempfile
import threading
import time

IS_WINDOWS = os.name == "nt"


def truncate(text, limit=15000):
    """Kürzt auf `limit` Zeichen: Anfang + Ende bleiben erhalten."""
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    half = max(1, (limit - 100) // 2)
    cut = len(text) - 2 * half
    return (text[:half] + f"\n\n... [{cut} characters truncated] ...\n\n" + text[-half:])


class PathError(Exception):
    pass


class PathGuard:
    """Erlaubt Dateizugriffe nur innerhalb der allowed_dirs (nach realpath-Auflösung)."""

    def __init__(self, allowed_dirs, workspace, deny=()):
        self.allowed = [os.path.realpath(d) for d in allowed_dirs]
        self.workspace = os.path.realpath(workspace)
        self.deny = [os.path.realpath(d) for d in deny]

    @staticmethod
    def _inside(path, root):
        try:
            return os.path.commonpath([path, root]) == root
        except ValueError:  # andere Laufwerke unter Windows
            return False

    def resolve(self, path):
        if not isinstance(path, str) or not path.strip():
            raise PathError("Empty path")
        p = os.path.expanduser(path.strip())
        if not os.path.isabs(p):
            p = os.path.join(self.workspace, p)
        real = os.path.realpath(p)  # löst Symlinks und .. auf
        for d in self.deny:
            if real == d or self._inside(real, d):
                raise PathError(f"Access denied: {path}")
        if not any(self._inside(real, root) for root in self.allowed):
            raise PathError(
                f"Access denied: {path} is outside the allowed directories "
                f"({', '.join(self.allowed)})")
        return real


_bwrap_status = None
_bwrap_lock = threading.Lock()


def bwrap_available():
    """(ok, meldung). Prüft, ob bwrap installiert ist und tatsächlich funktioniert."""
    global _bwrap_status
    with _bwrap_lock:
        if _bwrap_status is not None:
            return _bwrap_status
        if IS_WINDOWS or not sys.platform.startswith("linux"):
            _bwrap_status = (False, "bwrap nur unter Linux verfügbar")
        elif not shutil.which("bwrap"):
            _bwrap_status = (False, "bwrap (bubblewrap) ist nicht installiert")
        else:
            try:
                r = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev",
                                    "--proc", "/proc", "true"],
                                   capture_output=True, timeout=20)
                if r.returncode == 0:
                    _bwrap_status = (True, "bwrap aktiv")
                else:
                    _bwrap_status = (False, "bwrap funktioniert nicht: " +
                                     r.stderr.decode(errors="replace").strip()[:300])
            except Exception as e:  # pragma: no cover
                _bwrap_status = (False, f"bwrap-Test fehlgeschlagen: {e}")
        return _bwrap_status


def _python_dirs():
    dirs = {sys.prefix, os.path.dirname(os.path.realpath(sys.executable))}
    try:
        dirs.add(site.getusersitepackages())
    except Exception:
        pass
    return [d for d in dirs if d and os.path.isdir(d)]


def build_bwrap_cmd(command, workspace, writable_dirs,
                    hidden=("/home", "/root", "/mnt", "/media", "/run/user"),
                    protect_files=(), network=True):
    cmd = ["bwrap", "--die-with-parent", "--new-session",
           "--ro-bind", "/", "/",
           "--dev", "/dev", "--proc", "/proc",
           "--tmpfs", "/tmp", "--tmpfs", "/var/tmp"]
    for h in hidden:
        if os.path.isdir(h):
            cmd += ["--tmpfs", h]
    # Python-Installation (venv / user site) wieder lesbar machen, falls versteckt
    for d in _python_dirs():
        if any(d == h or d.startswith(h.rstrip("/") + "/") for h in hidden):
            cmd += ["--ro-bind", d, d]
    for d in writable_dirs:
        os.makedirs(d, exist_ok=True)
        cmd += ["--bind", d, d]
    for f in protect_files:
        if os.path.exists(f):
            cmd += ["--ro-bind", "/dev/null", f]
    cmd += ["--unshare-pid", "--unshare-ipc", "--unshare-uts"]
    if not network:
        cmd += ["--unshare-net"]
    cmd += ["--setenv", "HOME", workspace, "--setenv", "TMPDIR", "/tmp",
            "--chdir", workspace, "/bin/bash", "-c", command]
    return cmd


def _kill_tree(proc):
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def find_windows_bash():
    """Git Bash suchen (nicht die WSL-bash.exe aus System32)."""
    cands = []
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands += [os.path.join(base, "Git", "bin", "bash.exe"),
                      os.path.join(base, "Programs", "Git", "bin", "bash.exe")]
    git = shutil.which("git")
    if git:  # ...\Git\cmd\git.exe -> ...\Git\bin\bash.exe
        cands.append(os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe"))
    for c in cands:
        if os.path.isfile(c):
            return c
    b = shutil.which("bash")
    if b and "system32" not in b.lower():
        return b
    return None


def shell_status():
    """(ok, meldung) für die Shell der Agenten."""
    if IS_WINDOWS:
        b = find_windows_bash()
        if not b:
            return (False, "Windows: Git Bash nicht gefunden – bitte 'Git for Windows' "
                           "installieren (git-scm.com), sonst funktionieren die "
                           "bash-Befehle der Agenten nicht.")
        return (True, f"Git Bash: {b}")
    return (True, "/bin/bash")


# python3/pip3 auf Windows auf das Python des Harness umleiten
WIN_SHIM = ('python3() { python "$@"; }; pip3() { python -m pip "$@"; }; '
            'export -f python3 pip3 2>/dev/null; ')


# --------------------------------------------------------------------------- Windows

WIN_STATE = {"level": None, "message": "Windows-Sandbox noch nicht geprüft", "checks": []}
_win_lock = threading.Lock()


def init_windows_sandbox(cfg):
    """Einmalig beim Start: Schutzmarkierungen setzen und Sandbox selbst testen."""
    import winsandbox
    with _win_lock:
        if cfg["sandbox"] == "none":
            WIN_STATE.update(level=None, message="Sandbox in config.json deaktiviert")
            return WIN_STATE
        if not find_windows_bash():
            WIN_STATE.update(level=None, message=shell_status()[1])
            return WIN_STATE
        winsandbox.suppress_error_dialogs()
        try:
            winsandbox.protect(cfg.path)
            winsandbox.protect(cfg.path_of("data_dir"))
            winsandbox.grant_python_read()
        except Exception as e:
            WIN_STATE.update(level=None, message=f"Schutz von config.json/data fehlgeschlagen: {e}")
            return WIN_STATE
        ws_root = cfg.path_of("workspaces_dir")

        def run_fn(level, command, workspace):
            r = BashRunner(workspace, [workspace], mode="auto", require=True,
                           output_limit=2000, win_level=level)
            code, out, _ = r.run(command, timeout=60)
            return code, out
        want = cfg.get("win_sandbox_level", "auto")
        levels = ["strict", "lowil"] if want not in ("strict", "lowil") else [want]
        cache = os.path.join(cfg.path_of("data_dir"), "sandbox_level.txt")
        try:  # zuletzt funktionierende Stufe zuerst testen
            with open(cache, encoding="utf-8") as f:
                last = f.read().strip()
            if last in levels:
                levels.remove(last)
                levels.insert(0, last)
        except OSError:
            pass
        res = winsandbox.selftest(run_fn, ws_root, cfg.base_dir, cfg.path,
                                  os.path.expanduser("~"), levels=levels)
        if res["level"]:
            for d in cfg.allowed_dirs():
                try:
                    winsandbox.prepare_workspace(d, strict=res["level"] == "strict")
                except Exception as e:
                    res["message"] += f" (Hinweis: {d} nicht vorbereitet: {e})"
        if res["level"]:
            try:
                with open(cache, "w", encoding="utf-8") as f:
                    f.write(res["level"])
            except OSError:
                pass
        WIN_STATE.update(res)
        return WIN_STATE


def sandbox_status(cfg):
    """(ok, meldung) – ist die bash-Sandbox auf diesem System aktiv?"""
    if cfg["sandbox"] == "none":
        return False, "Sandbox in config.json deaktiviert (\"sandbox\": \"none\")"
    if IS_WINDOWS:
        return bool(WIN_STATE["level"]), WIN_STATE["message"]
    return bwrap_available()


class _PopenProc:
    """Popen mit derselben Schnittstelle wie winsandbox.SandboxedProcess."""

    def __init__(self, argv, **kw):
        self.p = subprocess.Popen(argv, **kw)
        self.pid = self.p.pid

    @property
    def returncode(self):
        return self.p.returncode

    def wait(self, timeout=None):
        return self.p.wait(timeout=timeout)

    def kill(self):
        _kill_tree(self.p)

    def close(self):
        if not IS_WINDOWS:
            try:  # Hintergrundprozesse der Session aufräumen
                os.killpg(self.p.pid, signal.SIGKILL)
            except Exception:
                pass


class BashRunner:
    def __init__(self, workspace, writable_dirs, mode="auto", network=True,
                 protect_files=(), output_limit=15000, require=False, win_level=None,
                 win_mem_mb=2048):
        self.workspace = os.path.realpath(workspace)
        self.writable_dirs = writable_dirs
        self.network = network
        self.protect_files = protect_files
        self.output_limit = output_limit
        self.use_bwrap = False
        self.win_level = None
        self.win_mem_mb = win_mem_mb
        self.blocked = ""
        self.warning = ""
        if mode == "none":
            self.warning = "WARNUNG: Sandbox deaktiviert, bash läuft NICHT abgeschottet."
        elif IS_WINDOWS:
            self.win_level = win_level or WIN_STATE["level"]
            if not self.win_level:
                msg = WIN_STATE["message"]
                if require:
                    self.blocked = msg
                else:
                    self.warning = f"WARNUNG: bash läuft NICHT abgeschottet ({msg})."
            elif win_level is None:
                import winsandbox
                try:
                    winsandbox.prepare_workspace(self.workspace,
                                                 strict=self.win_level == "strict")
                except Exception as e:
                    self.blocked = f"Workspace konnte nicht vorbereitet werden: {e}"
        else:
            ok, msg = bwrap_available()
            if ok:
                self.use_bwrap = True
            elif require:
                self.blocked = msg
            else:
                self.warning = f"WARNUNG: bash läuft NICHT abgeschottet ({msg})."

    def _argv(self, command):
        if self.use_bwrap:
            return build_bwrap_cmd(command, self.workspace, self.writable_dirs,
                                   protect_files=self.protect_files,
                                   network=self.network)
        if IS_WINDOWS:
            bash = find_windows_bash()
            return [bash, "-c", WIN_SHIM + command] if bash else command
        return ["/bin/bash", "-c", command]

    def _spawn(self, argv, env, out):
        if self.win_level:
            import winsandbox
            tmp = os.path.join(self.workspace, ".tmp")
            os.makedirs(tmp, exist_ok=True)
            env.update(TMP=tmp, TEMP=tmp, HOME=self.workspace)
            return winsandbox.SandboxedProcess(argv, self.workspace, env, out,
                                               strict=self.win_level == "strict",
                                               mem_mb=self.win_mem_mb)
        kwargs = dict(cwd=self.workspace, stdout=out, stderr=subprocess.STDOUT,
                      stdin=subprocess.DEVNULL, env=env)
        if IS_WINDOWS:
            kwargs["shell"] = isinstance(argv, str)
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        return _PopenProc(argv, **kwargs)

    def run(self, command, timeout=600, stop_event=None):
        """Gibt (exit_code, ausgabe, timed_out) zurück."""
        if self.blocked:
            return (126, "ERROR: the sandbox is not available, bash is disabled for "
                    f"security reasons. ({self.blocked})", False)
        os.makedirs(self.workspace, exist_ok=True)
        argv = self._argv(command)
        if self.win_level and not isinstance(argv, list):
            return (126, "ERROR: Git Bash not found – bash is disabled.", False)
        env = dict(os.environ)
        env.pop("HARNESS_CONFIG", None)
        for k in list(env):
            if "API_KEY" in k.upper() or k.upper().startswith("OPENAI"):
                env.pop(k)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if IS_WINDOWS:
            # venv-Python (mit pytest) zuerst im PATH, UTF-8 für Ausgaben
            env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
        with tempfile.TemporaryFile() as out:
            try:
                proc = self._spawn(argv, env, out)
            except OSError as e:
                return 126, f"ERROR: process could not be started: {e}", False
            deadline = time.monotonic() + timeout
            timed_out = stopped = False
            while True:
                try:
                    proc.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() > deadline:
                        timed_out = True
                    elif stop_event is not None and stop_event.is_set():
                        stopped = True
                    if timed_out or stopped:
                        proc.kill()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            pass
                        break
            proc.close()
            out.flush()
            size = os.fstat(out.fileno()).st_size
            lim = self.output_limit * 4
            out.seek(0)
            if size > lim:
                head = out.read(lim // 2)
                out.seek(size - lim // 2)
                tail = out.read()
                text = (head.decode("utf-8", errors="replace") +
                        f"\n... [{size - lim} bytes skipped] ...\n" +
                        tail.decode("utf-8", errors="replace"))
            else:
                text = out.read().decode("utf-8", errors="replace")
        if timed_out:
            text += f"\n[TIMEOUT after {timeout}s – process killed]"
        if stopped:
            text += "\n[Aborted: the agent was stopped]"
        code = proc.returncode if proc.returncode is not None else -9
        return code, text, timed_out
