"""Windows-Sandbox für die bash-Befehle der Agenten (nur Standardbibliothek, ctypes).

Jeder Befehl startet mit einem eingeschränkten Token:
- Integritätsstufe "Low": Schreiben nur in Ordner, die ausdrücklich als "Low" markiert
  sind (die Workspaces). Alles andere (Windows, Programme, Benutzerprofil, Harness,
  .venv, Registry) ist für den Prozess schreibgeschützt.
- Alle Privilegien entfernt, Administratoren-Gruppe nur noch "deny-only": keine
  Admin-Befehle, kein Treiber-/Dienst-/System-Zugriff.
- Stufe "strict" zusätzlich mit einschränkenden SIDs (wie die Chrome-Sandbox): Lesen
  nur dort, wo Jeder/Benutzer/RESTRICTED Rechte haben – das Benutzerprofil
  (Dokumente, Desktop, Downloads, AppData) ist damit auch nicht mehr lesbar.
- Job-Objekt: alle Unterprozesse bleiben im Job (kein Ausbruch), Speicherlimit,
  keine Zwischenablage, kein Herunterfahren/Abmelden, Beenden des ganzen Baums.
config.json und der data-Ordner bekommen die Markierung "No-Read-Up": Prozesse mit
niedriger Integrität können sie nicht einmal lesen (API-Key bleibt geheim).

Da die Wirksamkeit vom System abhängt, prüft `selftest` beim Start alles nach.
"""
import os
import subprocess
import sys
import threading

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:  # pragma: no cover - nur unter Windows
    import ctypes
    import msvcrt
    from ctypes import wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    adv = ctypes.WinDLL("advapi32", use_last_error=True)

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wt.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [("Label", SID_AND_ATTRIBUTES)]

    class TOKEN_GROUPS(ctypes.Structure):
        _fields_ = [("GroupCount", wt.DWORD), ("Groups", SID_AND_ATTRIBUTES * 1)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR),
                    ("lpTitle", wt.LPWSTR), ("dwX", wt.DWORD), ("dwY", wt.DWORD),
                    ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
                    ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD),
                    ("dwFillAttribute", wt.DWORD), ("dwFlags", wt.DWORD),
                    ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
                    ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE),
                    ("hStdOutput", wt.HANDLE), ("hStdError", wt.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE),
                    ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wt.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wt.DWORD), ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class JOBOBJECT_BASIC_UI_RESTRICTIONS(ctypes.Structure):
        _fields_ = [("UIRestrictionsClass", wt.DWORD)]

    def _fn(lib, name, restype, *argtypes):
        f = getattr(lib, name)
        f.restype = restype
        f.argtypes = argtypes
        return f

    GetCurrentProcess = _fn(k32, "GetCurrentProcess", wt.HANDLE)
    CloseHandle = _fn(k32, "CloseHandle", wt.BOOL, wt.HANDLE)
    LocalFree = _fn(k32, "LocalFree", ctypes.c_void_p, ctypes.c_void_p)
    WaitForSingleObject = _fn(k32, "WaitForSingleObject", wt.DWORD, wt.HANDLE, wt.DWORD)
    GetExitCodeProcess = _fn(k32, "GetExitCodeProcess", wt.BOOL, wt.HANDLE,
                             ctypes.POINTER(wt.DWORD))
    ResumeThread = _fn(k32, "ResumeThread", wt.DWORD, wt.HANDLE)
    TerminateProcess = _fn(k32, "TerminateProcess", wt.BOOL, wt.HANDLE, wt.UINT)
    CreateJobObjectW = _fn(k32, "CreateJobObjectW", wt.HANDLE, ctypes.c_void_p, wt.LPCWSTR)
    SetInformationJobObject = _fn(k32, "SetInformationJobObject", wt.BOOL, wt.HANDLE,
                                  ctypes.c_int, ctypes.c_void_p, wt.DWORD)
    AssignProcessToJobObject = _fn(k32, "AssignProcessToJobObject", wt.BOOL, wt.HANDLE,
                                   wt.HANDLE)
    TerminateJobObject = _fn(k32, "TerminateJobObject", wt.BOOL, wt.HANDLE, wt.UINT)
    OpenProcessToken = _fn(adv, "OpenProcessToken", wt.BOOL, wt.HANDLE, wt.DWORD,
                           ctypes.POINTER(wt.HANDLE))
    GetTokenInformation = _fn(adv, "GetTokenInformation", wt.BOOL, wt.HANDLE, ctypes.c_int,
                              ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD))
    CreateRestrictedToken = _fn(adv, "CreateRestrictedToken", wt.BOOL, wt.HANDLE, wt.DWORD,
                                wt.DWORD, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p,
                                wt.DWORD, ctypes.c_void_p, ctypes.POINTER(wt.HANDLE))
    SetTokenInformation = _fn(adv, "SetTokenInformation", wt.BOOL, wt.HANDLE, ctypes.c_int,
                              ctypes.c_void_p, wt.DWORD)
    ConvertStringSidToSidW = _fn(adv, "ConvertStringSidToSidW", wt.BOOL, wt.LPCWSTR,
                                 ctypes.POINTER(ctypes.c_void_p))
    GetLengthSid = _fn(adv, "GetLengthSid", wt.DWORD, ctypes.c_void_p)
    CreateProcessAsUserW = _fn(adv, "CreateProcessAsUserW", wt.BOOL, wt.HANDLE, wt.LPCWSTR,
                               ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL,
                               wt.DWORD, ctypes.c_void_p, wt.LPCWSTR,
                               ctypes.POINTER(STARTUPINFOW),
                               ctypes.POINTER(PROCESS_INFORMATION))
    ConvertSD = _fn(adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", wt.BOOL,
                    wt.LPCWSTR, wt.DWORD, ctypes.POINTER(ctypes.c_void_p),
                    ctypes.c_void_p)
    GetSecurityDescriptorSacl = _fn(adv, "GetSecurityDescriptorSacl", wt.BOOL,
                                    ctypes.c_void_p, ctypes.POINTER(wt.BOOL),
                                    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wt.BOOL))
    ConvertSidToStringSidW = _fn(adv, "ConvertSidToStringSidW", wt.BOOL, ctypes.c_void_p,
                                 ctypes.POINTER(ctypes.c_void_p))
    GetSecurityDescriptorDacl = _fn(adv, "GetSecurityDescriptorDacl", wt.BOOL,
                                    ctypes.c_void_p, ctypes.POINTER(wt.BOOL),
                                    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wt.BOOL))
    SetErrorMode = _fn(k32, "SetErrorMode", wt.UINT, wt.UINT)

    class TOKEN_DEFAULT_DACL(ctypes.Structure):
        _fields_ = [("DefaultDacl", ctypes.c_void_p)]

    SetNamedSecurityInfoW = _fn(adv, "SetNamedSecurityInfoW", wt.DWORD, wt.LPWSTR,
                                ctypes.c_int, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.c_void_p)

TOKEN_ASSIGN_PRIMARY, TOKEN_DUPLICATE, TOKEN_QUERY, TOKEN_ADJUST_DEFAULT = 0x1, 0x2, 0x8, 0x80
DISABLE_MAX_PRIVILEGE = 0x1
SE_GROUP_INTEGRITY = 0x20
SE_GROUP_LOGON_ID = 0xC0000000
TokenUser, TokenGroups, TokenDefaultDacl, TokenIntegrityLevel = 1, 2, 6, 25
STATUS_DLL_INIT_FAILED = 0xC0000142
# keine Fehlerdialoge (z. B. 0xc0000142) für Kindprozesse – sie erben den Fehlermodus
SEM_FAILCRITICALERRORS, SEM_NOGPFAULTERRORBOX, SEM_NOOPENFILEERRORBOX = 0x1, 0x2, 0x8000
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x400
LOW_IL_SID = "S-1-16-4096"
ADMINS_SID = "S-1-5-32-544"
RESTRICTING_SIDS = ["S-1-1-0", "S-1-5-32-545", "S-1-5-11", "S-1-5-12"]  # Jeder, Benutzer,
RESTRICTED_SID = "S-1-5-12"                                              # Auth., RESTRICTED
CREATE_SUSPENDED, CREATE_NEW_PROCESS_GROUP = 0x4, 0x200
CREATE_UNICODE_ENVIRONMENT, CREATE_NO_WINDOW = 0x400, 0x08000000
STARTF_USESTDHANDLES = 0x100
JOB_OBJECT_LIMIT_JOB_MEMORY, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x200, 0x2000
JobObjectBasicUIRestrictions, JobObjectExtendedLimitInformation = 4, 9
UILIMIT_ALL = 0xFF  # Handles, Zwischenablage, Systemparameter, Desktop, Herunterfahren …
SE_FILE_OBJECT, LABEL_SECURITY_INFORMATION = 1, 0x10
WAIT_OBJECT_0 = 0

LABEL_LOW_DIR = "S:(ML;OICI;NW;;;LW)"            # Low: von der Sandbox beschreibbar
LABEL_PROTECT_DIR = "S:(ML;OICI;NWNRNX;;;ME)"    # Medium + No-Read-Up
LABEL_PROTECT_FILE = "S:(ML;;NWNRNX;;;ME)"

_create_lock = threading.Lock()


def _err(what):
    code = ctypes.get_last_error()
    return OSError(code, f"{what} fehlgeschlagen (Windows-Fehler {code})")


def _sid(s):
    p = ctypes.c_void_p()
    if not ConvertStringSidToSidW(s, ctypes.byref(p)):
        raise _err(f"ConvertStringSidToSid({s})")
    return p


# --------------------------------------------------------------------------- Labels / ACLs

def set_label(path, sddl):
    """Setzt die Integritäts-Markierung (Mandatory Label) einer Datei/eines Ordners."""
    psd = ctypes.c_void_p()
    if not ConvertSD(sddl, 1, ctypes.byref(psd), None):
        raise _err("ConvertStringSecurityDescriptor")
    try:
        present, defaulted = wt.BOOL(), wt.BOOL()
        pacl = ctypes.c_void_p()
        if not GetSecurityDescriptorSacl(psd, ctypes.byref(present), ctypes.byref(pacl),
                                         ctypes.byref(defaulted)):
            raise _err("GetSecurityDescriptorSacl")
        rc = SetNamedSecurityInfoW(os.path.abspath(path), SE_FILE_OBJECT,
                                   LABEL_SECURITY_INFORMATION, None, None, None, pacl)
        if rc != 0:
            raise OSError(rc, f"Markierung von {path} fehlgeschlagen (Windows-Fehler {rc})")
    finally:
        LocalFree(psd)


def _icacls(path, grant):
    r = subprocess.run(["icacls", os.path.abspath(path), "/grant", grant, "/Q"],
                       capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OSError(f"icacls {path}: {r.stdout.strip()} {r.stderr.strip()}")


def prepare_workspace(path, strict):
    """Ordner für die Sandbox beschreibbar machen (Low-Markierung, ggf. RESTRICTED-Recht)."""
    os.makedirs(path, exist_ok=True)
    set_label(path, LABEL_LOW_DIR)
    if strict:
        _icacls(path, f"*{RESTRICTED_SID}:(OI)(CI)M")


def grant_read(path):
    """Leserecht für eingeschränkte Tokens (z. B. Python-Installation)."""
    if os.path.isdir(path):
        _icacls(path, f"*{RESTRICTED_SID}:(OI)(CI)RX")


def protect(path):
    """No-Read-Up: Sandbox-Prozesse können die Datei/den Ordner weder lesen noch schreiben."""
    if os.path.isdir(path):
        set_label(path, LABEL_PROTECT_DIR)
    elif os.path.exists(path):
        set_label(path, LABEL_PROTECT_FILE)


# --------------------------------------------------------------------------- Token / Prozess

def suppress_error_dialogs():
    """Fehlerfenster wie 'Anwendung konnte nicht korrekt gestartet werden' unterdrücken.
    Der Modus wird von allen Kindprozessen geerbt."""
    try:
        SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX)
    except Exception:
        pass


def _sid_str(psid):
    out = ctypes.c_void_p()
    if not ConvertSidToStringSidW(psid, ctypes.byref(out)):
        raise _err("ConvertSidToStringSid")
    try:
        return ctypes.wstring_at(out.value)
    finally:
        LocalFree(out)


def _user_sid_str(token):
    size = wt.DWORD()
    GetTokenInformation(token, TokenUser, None, 0, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not GetTokenInformation(token, TokenUser, buf, size, ctypes.byref(size)):
        raise _err("GetTokenInformation(TokenUser)")
    return _sid_str(SID_AND_ATTRIBUTES.from_buffer(buf).Sid)


def _set_default_dacl(tok, user_sid, logon_sid):
    """Standard-DACL für neue Objekte des Prozesses: ohne RESTRICTED/Logon-SID könnte der
    eingeschränkte Prozess seine eigenen Objekte nicht öffnen (-> 0xc0000142)."""
    sddl = f"D:(A;;GA;;;SY)(A;;GA;;;{user_sid})(A;;GA;;;RC)"
    if logon_sid:
        sddl += f"(A;;GA;;;{logon_sid})"
    psd = ctypes.c_void_p()
    if not ConvertSD(sddl, 1, ctypes.byref(psd), None):
        raise _err("ConvertStringSecurityDescriptor(DefaultDacl)")
    try:
        present, defaulted = wt.BOOL(), wt.BOOL()
        pacl = ctypes.c_void_p()
        if not GetSecurityDescriptorDacl(psd, ctypes.byref(present), ctypes.byref(pacl),
                                         ctypes.byref(defaulted)):
            raise _err("GetSecurityDescriptorDacl")
        dd = TOKEN_DEFAULT_DACL(pacl)
        if not SetTokenInformation(tok, TokenDefaultDacl, ctypes.byref(dd),
                                   ctypes.sizeof(dd)):
            raise _err("SetTokenInformation(DefaultDacl)")
    finally:
        LocalFree(psd)


def _make_token(strict):
    cur = wt.HANDLE()
    if not OpenProcessToken(GetCurrentProcess(), TOKEN_ASSIGN_PRIMARY | TOKEN_DUPLICATE |
                            TOKEN_QUERY | TOKEN_ADJUST_DEFAULT, ctypes.byref(cur)):
        raise _err("OpenProcessToken")
    keep = []
    try:
        admins = _sid(ADMINS_SID)
        keep.append(admins)
        disable = (SID_AND_ATTRIBUTES * 1)()
        disable[0].Sid = admins
        restrict, n_restrict, logon = None, 0, None
        if strict:
            sids = [_sid(s) for s in RESTRICTING_SIDS]
            keep += sids
            logon = _logon_sid(cur, keep)
            if logon:
                sids.append(logon)
            restrict = (SID_AND_ATTRIBUTES * len(sids))()
            for i, s in enumerate(sids):
                restrict[i].Sid = s
            n_restrict = len(sids)
        tok = wt.HANDLE()
        if not CreateRestrictedToken(cur, DISABLE_MAX_PRIVILEGE, 1, disable, 0, None,
                                     n_restrict, restrict, ctypes.byref(tok)):
            raise _err("CreateRestrictedToken")
        if strict:
            try:
                _set_default_dacl(tok, _user_sid_str(cur),
                                  _sid_str(logon) if logon else None)
            except Exception:
                CloseHandle(tok)
                raise
        low = _sid(LOW_IL_SID)
        keep.append(low)
        tml = TOKEN_MANDATORY_LABEL()
        tml.Label.Sid = low
        tml.Label.Attributes = SE_GROUP_INTEGRITY
        if not SetTokenInformation(tok, TokenIntegrityLevel, ctypes.byref(tml),
                                   ctypes.sizeof(tml) + GetLengthSid(low)):
            CloseHandle(tok)
            raise _err("SetTokenInformation(IntegrityLevel)")
        return tok
    finally:
        CloseHandle(cur)
        for p in keep:
            if isinstance(p, ctypes.c_void_p) and p.value:
                LocalFree(p)


def _logon_sid(token, keep):
    """Logon-SID (für den Zugriff auf Fensterstation/Desktop) aus dem Token holen."""
    size = wt.DWORD()
    GetTokenInformation(token, TokenGroups, None, 0, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not GetTokenInformation(token, TokenGroups, buf, size, ctypes.byref(size)):
        return None
    tg = TOKEN_GROUPS.from_buffer(buf)
    arr = (SID_AND_ATTRIBUTES * tg.GroupCount).from_address(
        ctypes.addressof(tg) + TOKEN_GROUPS.Groups.offset)
    for g in arr:
        if (g.Attributes & SE_GROUP_LOGON_ID) == SE_GROUP_LOGON_ID:
            keep.append(buf)  # Puffer am Leben halten
            return ctypes.c_void_p(g.Sid)
    return None


def _make_job(mem_mb, ui_limits):
    job = CreateJobObjectW(None, None)
    if not job:
        raise _err("CreateJobObject")
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    if mem_mb:
        flags |= JOB_OBJECT_LIMIT_JOB_MEMORY
        info.JobMemoryLimit = int(mem_mb) * 1024 * 1024
    info.BasicLimitInformation.LimitFlags = flags
    if not SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                   ctypes.byref(info), ctypes.sizeof(info)):
        CloseHandle(job)
        raise _err("SetInformationJobObject(Limits)")
    if ui_limits:
        ui = JOBOBJECT_BASIC_UI_RESTRICTIONS(UILIMIT_ALL)
        SetInformationJobObject(job, JobObjectBasicUIRestrictions, ctypes.byref(ui),
                                ctypes.sizeof(ui))
    return job


class SandboxedProcess:
    """Gleiche Schnittstelle wie nötig von subprocess.Popen: wait/kill/returncode."""

    def __init__(self, argv, cwd, env, out_file, strict, mem_mb=2048):
        self.returncode = None
        self.job = _make_job(mem_mb, ui_limits=strict)
        tok = None
        try:
            tok = _make_token(strict)
            cmdline = subprocess.list2cmdline(argv)
            cmd_buf = ctypes.create_unicode_buffer(cmdline)
            block = "".join(f"{k}={v}\0" for k, v in
                            sorted(env.items(), key=lambda kv: kv[0].upper())) + "\0"
            env_buf = (ctypes.c_wchar * len(block))(*block)
            out_h = msvcrt.get_osfhandle(out_file.fileno())
            nul = open(os.devnull, "rb")
            in_h = msvcrt.get_osfhandle(nul.fileno())
            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(si)
            si.dwFlags = STARTF_USESTDHANDLES
            si.hStdInput, si.hStdOutput, si.hStdError = in_h, out_h, out_h
            pi = PROCESS_INFORMATION()
            flags = (CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP |
                     CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW)
            with _create_lock:  # Handles nur kurz vererbbar machen
                os.set_handle_inheritable(out_h, True)
                os.set_handle_inheritable(in_h, True)
                try:
                    ok = CreateProcessAsUserW(tok, None, cmd_buf, None, None, True, flags,
                                              env_buf, cwd, ctypes.byref(si),
                                              ctypes.byref(pi))
                    err = None if ok else _err("CreateProcessAsUser")
                finally:
                    os.set_handle_inheritable(out_h, False)
                    nul.close()
            if err:
                raise err
            self.hproc = pi.hProcess
            self.pid = pi.dwProcessId
            if not AssignProcessToJobObject(self.job, pi.hProcess):
                e = _err("AssignProcessToJobObject")
                TerminateProcess(pi.hProcess, 1)
                CloseHandle(pi.hThread)
                raise e
            ResumeThread(pi.hThread)
            CloseHandle(pi.hThread)
        except Exception:
            CloseHandle(self.job)
            self.job = None
            raise
        finally:
            if tok:
                CloseHandle(tok)

    def wait(self, timeout=None):
        ms = 0xFFFFFFFF if timeout is None else int(timeout * 1000)
        if WaitForSingleObject(self.hproc, ms) != WAIT_OBJECT_0:
            raise subprocess.TimeoutExpired("sandbox", timeout)
        code = wt.DWORD()
        GetExitCodeProcess(self.hproc, ctypes.byref(code))
        self.returncode = code.value if code.value < 0x80000000 else code.value - 2 ** 32
        return self.returncode

    def kill(self):
        if self.job:
            TerminateJobObject(self.job, 1)

    def close(self):
        """Beendet alle verbliebenen Prozesse des Jobs (auch Hintergrundprozesse)."""
        if self.job:
            TerminateJobObject(self.job, 1)
            CloseHandle(self.job)
            self.job = None
        if getattr(self, "hproc", None):
            CloseHandle(self.hproc)
            self.hproc = None


# --------------------------------------------------------------------------- Selbsttest

def _hex(code):
    return f"0x{(code or 0) & 0xFFFFFFFF:08X}"


def selftest(run_fn, ws_root, base_dir, protected_file, home, levels=("strict", "lowil")):
    """run_fn(level, command, workspace) -> (code, output).
    Liefert dict(level, checks, message): level 'strict', 'lowil' oder None."""
    probe_ws = os.path.join(ws_root, ".sandbox-selftest")
    outside = os.path.join(base_dir, ".sandbox-probe.txt")
    report = []
    for level in levels:
        checks = []
        try:
            prepare_workspace(ws_root, strict=(level == "strict"))
            prepare_workspace(probe_ws, strict=(level == "strict"))
            if os.path.exists(outside):
                os.remove(outside)
            q = lambda p: p.replace("\\", "/")  # noqa: E731
            # Kanarienvogel: startet überhaupt ein Prozess? Sonst Stufe sofort verwerfen.
            code, out = run_fn(level, "echo start-ok", probe_ws)
            if code != 0 or "start-ok" not in out:
                hint = (" (DLL-Initialisierung fehlgeschlagen)"
                        if (code or 0) & 0xFFFFFFFF == STATUS_DLL_INIT_FAILED else "")
                checks.append(("Prozessstart", False, f"Code {_hex(code)}{hint} {out[-150:]}"))
                report.append((level, checks))
                continue
            code, out = run_fn(level, 'echo ok > inside.txt && cat inside.txt', probe_ws)
            checks.append(("Schreiben im Workspace", code == 0 and "ok" in out, out[-200:]))
            code, out = run_fn(level, 'python -c "print(6*7)"', probe_ws)
            checks.append(("Python im Workspace", code == 0 and "42" in out, out[-200:]))
            run_fn(level, f'echo x > "{q(outside)}"', probe_ws)
            blocked = not os.path.exists(outside)
            checks.append(("Schreiben außerhalb blockiert", blocked, ""))
            code, out = run_fn(level, f'cat "{q(protected_file)}"', probe_ws)
            checks.append(("config.json (API-Key) nicht lesbar", code != 0, ""))
            code, out = run_fn(level, 'net session >/dev/null 2>&1; echo rc=$?', probe_ws)
            checks.append(("Keine Admin-Rechte", "rc=0" not in out, out[-100:]))
            if level == "strict" and home:
                code, out = run_fn(level, f'ls "{q(home)}"', probe_ws)
                checks.append(("Benutzerprofil nicht lesbar", code != 0, ""))
        except Exception as e:
            checks.append((f"Sandbox-Start ({level})", False, str(e)[:300]))
        finally:
            if os.path.exists(outside):
                try:
                    os.remove(outside)
                except OSError:
                    pass
        report.append((level, checks))
        if all(ok for _, ok, _ in checks):
            names = {"strict": "streng: Schreiben nur im Workspace, kein Lesen des "
                               "Benutzerprofils, keine Admin-Rechte",
                     "lowil": "Schreiben nur im Workspace, keine Admin-Rechte "
                              "(Lesen anderer Dateien möglich)"}
            return {"level": level, "checks": checks, "message": f"Windows-Sandbox aktiv ({names[level]})"}
    failed = "; ".join(f"{lvl}: " + ", ".join(f"{n} ✗ {d}".strip() for n, ok, d in ch if not ok)
                       for lvl, ch in report)
    return {"level": None, "checks": report[-1][1] if report else [],
            "message": "Windows-Sandbox nicht funktionsfähig – " + failed}


def grant_python_read():
    """Python-Installation und venv für eingeschränkte Tokens lesbar machen."""
    for p in {sys.prefix, getattr(sys, "base_prefix", sys.prefix),
              os.path.dirname(os.path.realpath(sys.executable))}:
        try:
            grant_read(p)
        except Exception:
            pass
