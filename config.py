"""Konfiguration: Laden, Defaults, atomisches Speichern."""
import copy
import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("HARNESS_CONFIG", os.path.join(BASE_DIR, "config.json"))

DEFAULTS = {
    "api_key": "",
    "base_url": "https://nano-gpt.com/api/v1",
    "model": "",
    "max_parallel": 4,
    "max_parallel_limit": 20,
    "max_hours": 36,
    "context_limit": 200000,
    "compress_at": 170000,
    "max_output_tokens": 16384,
    "temperature": None,
    "request_timeout": 900,
    "tool_output_limit": 15000,
    "bash_timeout": 600,
    "bash_max_timeout": 3600,
    "max_no_tool_replies": 4,
    "max_retries": 10,
    "retry_delays": [5],         # Wartezeit vor Retry 1, 2, ...; letzter Wert gilt weiter
    "retry_after_max": 60,       # 429 mit Retry-After: höchstens so lange warten
    "allowed_dirs": ["./workspaces"],
    "workspaces_dir": "./workspaces",
    "data_dir": "./data",
    "archive_dir": "./archive",
    "archive_finished": False,
    "endless_mode": True,
    "price_input_per_m": 0.135,
    "price_output_per_m": 2.25,
    "sandbox": "auto",          # auto | bwrap | none
    "sandbox_network": True,     # Netzwerk in der bwrap-Sandbox erlauben (pip etc.)
    "require_sandbox": True,     # ohne funktionierende Sandbox keine Agenten starten
    "win_job_memory_mb": 2048,   # Windows: Speicherlimit je bash-Befehl (0 = aus)
    "verify_on_finish": True,    # finish nur akzeptieren, wenn pytest grün ist
    "subagents_enabled": True,   # Tools subagent/swarm für Hauptagenten
    "max_subagents": 4,          # max. Pakete pro Schwarm
    "max_total_subagents": 8,    # max. gleichzeitig laufende Subagenten insgesamt
    "subagent_max_hours": 6,
    "swarm_ratio": 0.25,         # Anteil generierter Aufgaben im Schwarm-Modus
    "max_finish_rejections": 5,
    "weak_min_tool_calls": 20,
    "throttle_errors": 3,
    "throttle_window_min": 10,
    "throttle_recover_min": 30,
    "max_log_mb": 50,
    "log_keep": 5,
    "ui_host": "127.0.0.1",
    "ui_port": 8765,
    "ui_password": "",
}

# Felder, die über das UI geändert werden dürfen
EDITABLE = {
    "api_key": str, "base_url": str, "model": str, "max_parallel": int,
    "allowed_dirs": list, "max_hours": float, "endless_mode": bool,
    "archive_finished": bool, "verify_on_finish": bool, "subagents_enabled": bool,
    "max_subagents": int, "max_total_subagents": int, "swarm_ratio": float,
    "max_retries": int, "retry_delays": list,
}

_lock = threading.Lock()


def resolve_path(p, base=BASE_DIR):
    p = os.path.expanduser(str(p))
    if not os.path.isabs(p):
        p = os.path.join(base, p)
    return os.path.realpath(p)


class Config:
    def __init__(self, path=None, data=None):
        self.path = path or CONFIG_PATH
        self.data = copy.deepcopy(DEFAULTS)
        if data is not None:
            self.data.update(data)
        elif os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        self.base_dir = os.path.dirname(os.path.abspath(self.path))

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def path_of(self, key):
        return resolve_path(self.data[key], self.base_dir)

    def allowed_dirs(self):
        dirs = [resolve_path(d, self.base_dir) for d in self.data.get("allowed_dirs") or []]
        ws = self.path_of("workspaces_dir")
        if ws not in dirs:
            dirs.append(ws)
        return dirs

    def update(self, changes):
        """Validiert und übernimmt UI-Änderungen. Gibt Liste der geänderten Keys zurück."""
        changed = []
        for k, v in changes.items():
            if k not in EDITABLE:
                continue
            typ = EDITABLE[k]
            if k == "api_key" and (v is None or v == "" or "•" in str(v)):
                continue  # maskierter Key -> unverändert lassen
            if k == "retry_delays":
                if isinstance(v, str):
                    v = v.replace(";", ",").split(",")
                if not isinstance(v, list):
                    v = [v]
                v = [max(0.0, min(float(x), 600.0)) for x in v if str(x).strip()] or [5.0]
                v = [int(x) if x == int(x) else x for x in v]
            elif typ is list:
                if isinstance(v, str):
                    v = [x.strip() for x in v.splitlines() if x.strip()]
                v = [str(x) for x in v]
            elif typ is bool:
                v = bool(v)
            else:
                v = typ(v)
            if k == "max_retries":
                v = max(0, min(int(v), 100))
            if k in ("max_subagents", "max_total_subagents"):
                v = max(1, min(int(v), 20))
            if k == "swarm_ratio":
                v = max(0.0, min(float(v), 1.0))
            if k == "max_parallel":
                v = max(1, min(int(v), int(self.data["max_parallel_limit"])))
            if self.data.get(k) != v:
                self.data[k] = v
                changed.append(k)
        return changed

    def save(self):
        with _lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            if os.name == "nt":  # neue Datei -> No-Read-Up-Markierung erneut setzen
                try:
                    import winsandbox
                    winsandbox.protect(self.path)
                except Exception:
                    pass

    def public(self):
        d = copy.deepcopy(self.data)
        k = d.get("api_key") or ""
        d["api_key"] = ("•" * 8 + k[-4:]) if k else ""
        d["ui_password"] = "•" * 8 if d.get("ui_password") else ""
        return d


def atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default
