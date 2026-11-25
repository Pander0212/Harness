"""Scheduler: Queue, parallele Agenten-Threads, Drosselung, Endlosmodus, Persistenz."""
import collections
import glob
import logging
import os
import random
import re
import shutil
import tarfile
import threading
import time

from agent import Agent, GiveUpError, AuthError, StoppedError
from config import atomic_write_json, read_json
from generator import generate_task, TOPIC_NAMES
from sandbox import init_windows_sandbox, sandbox_status, shell_status

log = logging.getLogger("harness")

STAT_KEYS = ("prompt_tokens", "cached_tokens", "completion_tokens", "calls", "retries",
             "compressions", "cost_usd", "tool_calls", "green_suites", "subagents",
             "overload_waits")

BUILTIN_TOPICS = {"sql": "database", "interpreter": "compiler", "git": "devtools",
                  "http": "network", "riscv": "emulation"}


def slugify(text):
    s = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "aufgabe"


def make_client(cfg):
    from openai import OpenAI
    total = float(cfg["request_timeout"])
    read = float(cfg.get("stall_timeout", 300)) if cfg.get("stream", True) else total
    try:  # Timeout-Klasse der jeweiligen openai-Version (httpx bzw. Nachfolger)
        from openai import Timeout
        timeout = Timeout(total, connect=30.0, read=read)
    except Exception:
        timeout = read
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"],
                  timeout=timeout, max_retries=0)


class Manager:
    def __init__(self, cfg, client_factory=make_client, clock=time.time, sleep=None,
                 tasks_dir=None, rng=None):
        self.cfg = cfg
        self.client_factory = client_factory
        self.clock = clock
        self.agent_sleep = sleep
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.data_dir = cfg.path_of("data_dir")
        self.ws_dir = cfg.path_of("workspaces_dir")
        self.tasks_dir = tasks_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.ws_dir, exist_ok=True)
        self.state_path = os.path.join(self.data_dir, "state.json")
        self.history_path = os.path.join(self.data_dir, "history.json")
        self.tasks = {}          # id -> meta
        self.queue = []          # ids
        self.agents = {}         # id -> Agent
        self.threads = {}        # id -> Thread
        self.history = read_json(self.history_path, [])
        self.events = collections.deque(maxlen=100)
        self.client = None
        self.auth_error = ""
        self.paused = False
        self.shutting_down = False
        self.generating = False
        self.gen_thread = None
        self.gen_agent = None
        self.next_gen_time = 0
        self.gen_error = ""
        # Drosselung
        self.effective_parallel = int(cfg["max_parallel"])
        self.sub_semaphore = threading.BoundedSemaphore(max(1, int(cfg["max_total_subagents"])))
        self.error_times = []
        self.last_error_time = None
        self.throttle_note = ""
        # Verdienst-Statistik
        self.start_time = clock()
        self.cost_samples = collections.deque(maxlen=24 * 60 + 5)
        self.last_sample = 0
        self.base_totals = {k: 0 for k in STAT_KEYS}
        if os.name == "nt":
            init_windows_sandbox(cfg)
        self.sandbox_ok, self.sandbox_msg = sandbox_status(cfg)
        sh_ok, sh_msg = shell_status()
        self.shell_ok, self.shell_msg = sh_ok, ("" if sh_ok else sh_msg)
        self._load()

    # ------------------------------------------------------------- Persistenz
    def _load(self):
        st = read_json(self.state_path, None)
        if st is None:
            self.builtin_loaded = []
            self._add_builtin_tasks()
            self.event("Eingebaute Aufgaben geladen")
        else:
            self.tasks = st.get("tasks", {})
            self.queue = [i for i in st.get("queue", []) if i in self.tasks]
            self.cfg.data["endless_mode"] = st.get("endless_mode", self.cfg["endless_mode"])
            self.paused = st.get("paused", False)
            self.base_totals.update(st.get("generator_totals", {}))
            interrupted = [i for i, t in self.tasks.items()
                           if t["status"] in ("läuft", "startet") or t["status"].startswith("retry")]
            for i in reversed(interrupted):
                self.tasks[i]["status"] = "wartet"
                self.tasks[i]["resume"] = True
                if i in self.queue:
                    self.queue.remove(i)
                self.queue.insert(0, i)
            if interrupted:
                self.event(f"{len(interrupted)} unterbrochene Aufgabe(n) werden fortgesetzt")
            self.builtin_loaded = st.get("builtin_loaded")
            if self.builtin_loaded is None:  # ältere state.json: anhand der Titel erkennen
                titles = {t["title"] for t in self.tasks.values()}
                self.builtin_loaded = [os.path.basename(p) for p in self._builtin_files()
                                       if self._read_task_file(p)[0] in titles]
            n = self._add_builtin_tasks()
            if n:
                self.event(f"{n} neue eingebaute Aufgabe(n) zur Queue hinzugefügt")
        self.save()

    def save(self):
        with self.lock:
            atomic_write_json(self.state_path, {
                "tasks": self.tasks, "queue": self.queue,
                "endless_mode": self.cfg["endless_mode"], "paused": self.paused,
                "generator_totals": self.base_totals,
                "builtin_loaded": getattr(self, "builtin_loaded", [])})

    def _save_history(self):
        atomic_write_json(self.history_path, self.history)

    def event(self, text):
        line = time.strftime("%Y-%m-%d %H:%M:%S ") + text
        self.events.append(line)
        log.info(text)

    def _builtin_files(self):
        def order(p):
            m = re.match(r"(\d+)", os.path.basename(p))
            return (int(m.group(1)) if m else 10 ** 6, os.path.basename(p))
        return sorted(glob.glob(os.path.join(self.tasks_dir, "*.md")), key=order)

    @classmethod
    def _read_task_file(cls, path):
        """-> (titel, text, optionen). Optionaler Kopf zwischen '---'-Zeilen:
        spec_docs: true/false, mode: single/swarm, topic: <bereich>"""
        with open(path, encoding="utf-8") as f:
            text = f.read()
        opts = {}
        m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    v = v.strip()
                    opts[k.strip()] = {"true": True, "false": False}.get(v.lower(), v)
            text = text[m.end():]
        title, body = cls._split_title(text, os.path.basename(path))
        return title, body, opts

    def _add_builtin_tasks(self):
        """Fügt alle noch nicht geladenen tasks/*.md hinzu. -> Anzahl."""
        n = 0
        for path in self._builtin_files():
            name = os.path.basename(path)
            if name in self.builtin_loaded:
                continue
            title, body, opts = self._read_task_file(path)
            key = re.sub(r"^\d+[_-]", "", os.path.splitext(name)[0])
            topic = opts.get("topic") or BUILTIN_TOPICS.get(key.split("_")[0], key)
            self.add_task(title, body, topic=topic, source="eingebaut",
                          mode=opts.get("mode", "single"), spec_docs=opts.get("spec_docs"))
            self.builtin_loaded.append(name)
            n += 1
        return n

    @staticmethod
    def _split_title(text, fallback):
        lines = text.strip().splitlines()
        if lines and lines[0].startswith("#"):
            return lines[0].lstrip("# ").strip(), "\n".join(lines[1:]).strip()
        return fallback, text

    # ------------------------------------------------------------- Aufgabenverwaltung
    def _new_id(self, title):
        base = slugify(title)
        i, tid = 1, base
        while tid in self.tasks or os.path.exists(os.path.join(self.ws_dir, tid)):
            i += 1
            tid = f"{base}-{i}"
        return tid

    def task_dir(self, tid):
        return os.path.join(self.data_dir, "tasks", tid)

    def add_task(self, title, prompt, topic="", source="manuell", front=False, mode="single",
                 spec_docs=None):
        with self.lock:
            title = (title or "").strip() or "Aufgabe"
            tid = self._new_id(title)
            d = self.task_dir(tid)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "task.md"), "w", encoding="utf-8") as f:
                f.write(prompt)
            self.tasks[tid] = {"id": tid, "title": title, "topic": topic, "source": source,
                               "status": "wartet", "weak": False, "resume": False,
                               "created": self.clock(), "started": None, "finished": None,
                               "last_error": "", "note": "", "stats": {},
                               "mode": "swarm" if mode == "swarm" else "single",
                               "spec_docs": spec_docs if isinstance(spec_docs, bool) else None}
            if front:
                self.queue.insert(0, tid)
            else:
                self.queue.append(tid)
            self.save()
            self.event(f"Aufgabe hinzugefügt: {title} ({source}"
                       f"{', Schwarm' if mode == 'swarm' else ''})")
            return tid

    def get_prompt(self, tid):
        with open(os.path.join(self.task_dir(tid), "task.md"), encoding="utf-8") as f:
            return f.read()

    def move(self, tid, direction):
        with self.lock:
            if tid not in self.queue:
                return False
            i = self.queue.index(tid)
            if direction == "top":
                j = 0
            elif direction == "bottom":
                j = len(self.queue) - 1
            else:
                j = max(0, min(len(self.queue) - 1, i + (-1 if direction == "up" else 1)))
            self.queue.insert(j, self.queue.pop(i))
            self.save()
            return True

    def delete(self, tid):
        with self.lock:
            if tid in self.agents:
                return False
            if tid in self.queue:
                self.queue.remove(tid)
            t = self.tasks.pop(tid, None)
            if t:
                shutil.rmtree(self.task_dir(tid), ignore_errors=True)
                self.event(f"Aufgabe gelöscht: {t['title']}")
            self.save()
            return t is not None

    def stop(self, tid):
        with self.lock:
            if tid in self.agents:
                self.agents[tid].stop()
                self.tasks[tid]["note"] = "Stop angefordert"
                return True
            if tid in self.queue:
                self.queue.remove(tid)
                self.tasks[tid]["status"] = "gestoppt"
                self.save()
                return True
            return False

    def resume(self, tid):
        """Fortsetzen: vorne in die Queue, setzt über PROGRESS.md fort."""
        with self.lock:
            t = self.tasks.get(tid)
            if not t or tid in self.agents:
                return False
            t["status"] = "wartet"
            t["resume"] = True
            t["note"] = "Fortsetzen angefordert"
            if tid in self.queue:
                self.queue.remove(tid)
            self.queue.insert(0, tid)
            self.save()
            return True

    def start_now(self, tid):
        """Start: sofort starten (unabhängig vom Parallelitätslimit)."""
        with self.lock:
            t = self.tasks.get(tid)
            if not t or tid in self.agents or self.auth_error or self.shutting_down:
                return False
            if t["status"] != "wartet":
                t["resume"] = True
            if tid in self.queue:
                self.queue.remove(tid)
            self._start(tid)
            return True

    def restart(self, tid):
        """Neustart: Workspace und Statistik verwerfen, von vorn beginnen."""
        with self.lock:
            t = self.tasks.get(tid)
            if not t:
                return False
            if tid in self.agents:
                t["pending_restart"] = True
                self.agents[tid].stop()
                return True
            self._reset(tid)
            return True

    def _reset(self, tid):
        t = self.tasks[tid]
        shutil.rmtree(os.path.join(self.ws_dir, tid), ignore_errors=True)
        d = self.task_dir(tid)
        for fn in os.listdir(d):
            if fn != "task.md":
                p = os.path.join(d, fn)
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
        t.update(status="wartet", resume=False, weak=False, stats={}, last_error="",
                 note="neu gestartet", started=None, finished=None)
        t.pop("pending_restart", None)
        if tid in self.queue:
            self.queue.remove(tid)
        self.queue.insert(0, tid)
        self.save()
        self.event(f"Neustart: {t['title']}")

    def set_endless(self, on):
        with self.lock:
            self.cfg.data["endless_mode"] = bool(on)
            self.cfg.save()
            self.save()

    def set_paused(self, on):
        with self.lock:
            self.paused = bool(on)
            self.save()

    def settings_changed(self, keys):
        with self.lock:
            self.client = None
            if self.auth_error:
                self.event("Einstellungen gespeichert – Auth-Sperre aufgehoben")
            self.auth_error = ""
            if "max_total_subagents" in keys:
                self.sub_semaphore = threading.BoundedSemaphore(
                    max(1, int(self.cfg["max_total_subagents"])))
            if "max_parallel" in keys:
                self.effective_parallel = int(self.cfg["max_parallel"])
                self.throttle_note = ""
                self.error_times.clear()

    def reset_throttle(self):
        with self.lock:
            self.effective_parallel = int(self.cfg["max_parallel"])
            self.error_times.clear()
            self.throttle_note = ""
            self.event(f"Drosselung zurückgesetzt – Parallelität {self.effective_parallel}")

    def clear_auth(self):
        with self.lock:
            self.auth_error = ""
            self.client = None

    # ------------------------------------------------------------- Scheduling
    def _get_client(self):
        if self.client is None:
            self.client = self.client_factory(self.cfg)
        return self.client

    def config_problem(self):
        if self.cfg["require_sandbox"] and self.cfg["sandbox"] != "none" \
                and not self.sandbox_ok:
            return ("Sandbox nicht verfügbar – aus Sicherheitsgründen werden keine Agenten "
                    f"gestartet: {self.sandbox_msg}")
        if not self.cfg["api_key"]:
            return "Kein API-Key eingestellt"
        if not self.cfg["model"]:
            return "Kein Modell eingestellt"
        return ""

    def _update_throttle(self, now):
        window = float(self.cfg["throttle_window_min"]) * 60
        recover = float(self.cfg["throttle_recover_min"]) * 60
        maxp = int(self.cfg["max_parallel"])
        self.error_times = [t for t in self.error_times if now - t <= window]
        if len(self.error_times) >= int(self.cfg["throttle_errors"]):
            if self.effective_parallel > 1:
                self.effective_parallel -= 1
                self.throttle_note = (f"Gedrosselt auf {self.effective_parallel} wegen "
                                      f"{len(self.error_times)} Abbrüchen in "
                                      f"{self.cfg['throttle_window_min']} min")
                self.event(self.throttle_note)
            self.error_times.clear()
        if self.effective_parallel > maxp:
            self.effective_parallel = maxp
        if self.effective_parallel < maxp and self.last_error_time is not None \
                and now - self.last_error_time >= recover:
            self.effective_parallel += 1
            self.last_error_time = now  # nächste Erhöhung frühestens nach weiteren 30 min
            self.throttle_note = ("" if self.effective_parallel >= maxp else
                                  f"Erholung: Parallelität {self.effective_parallel}/{maxp}")
            self.event(f"Parallelität wieder erhöht auf {self.effective_parallel}")

    def record_error(self, now=None):
        now = self.clock() if now is None else now
        self.error_times.append(now)
        self.last_error_time = now

    def tick(self):
        with self.lock:
            now = self.clock()
            self._update_throttle(now)
            self._sample_cost(now)
            if self.shutting_down or self.paused or self.auth_error or self.config_problem():
                return
            while self.queue and len(self.agents) < self.effective_parallel:
                if self._start(self.queue.pop(0)) is False:
                    break  # nie in einer Schleife hängen bleiben
            if (self.cfg["endless_mode"] and not self.queue and not self.generating
                    and len(self.agents) < self.effective_parallel
                    and now >= self.next_gen_time):
                self._start_generator()

    def _start(self, tid):
        """Startet eine Aufgabe. False, wenn das nicht möglich war (Aufgabe bleibt vorn)."""
        t = self.tasks[tid]
        try:
            client = self._get_client()
        except Exception as e:
            self.auth_error = f"API-Client konnte nicht erstellt werden: {e}"
            self.event(self.auth_error)
            self.queue.insert(0, tid)
            return False
        task = {"id": tid, "title": t["title"], "prompt": self.get_prompt(tid),
                "mode": t.get("mode", "single"), "spec_docs": t.get("spec_docs")}
        ag = Agent(task, self.cfg, client, os.path.join(self.ws_dir, tid), self.task_dir(tid),
                   resume=bool(t.get("resume")), sleep=self.agent_sleep, clock=self.clock,
                   sub_semaphore=self.sub_semaphore)
        self.agents[tid] = ag
        t["status"] = "läuft"
        t["started"] = t.get("started") or self.clock()
        t["note"] = "fortgesetzt" if t.get("resume") else ""
        th = threading.Thread(target=self._run_agent, args=(tid, ag), daemon=True,
                              name=f"agent-{tid}")
        self.threads[tid] = th
        self.save()
        self.event(f"Start: {t['title']}" + (" (Fortsetzung)" if t.get("resume") else ""))
        th.start()

    def _run_agent(self, tid, ag):
        try:
            outcome = ag.run()
        except Exception as e:  # pragma: no cover - Agent fängt selbst ab
            outcome = {"outcome": "error", "message": f"Interner Fehler: {e}"}
        self._on_done(tid, ag, outcome)

    def _on_done(self, tid, ag, outcome):
        archive = False
        with self.lock:
            self.agents.pop(tid, None)
            self.threads.pop(tid, None)
            t = self.tasks.get(tid)
            if t is None:
                return
            t["stats"] = {k: ag.stats.get(k, 0) for k in STAT_KEYS}
            t["stats"]["active_seconds"] = ag.stats.get("active_seconds", 0)
            t["last_error"] = ag.stats.get("last_error", "") if outcome["outcome"] in (
                "error", "auth") else t.get("last_error", "")
            kind = outcome["outcome"]
            msg = outcome.get("message", "")
            if t.pop("pending_restart", False):
                self._reset(tid)
                return
            if self.shutting_down and kind == "stopped":
                t["status"] = "wartet"
                t["resume"] = True
                t["note"] = "unterbrochen durch Neustart des Harness"
                if tid not in self.queue:
                    self.queue.insert(0, tid)
                self.save()
                return
            t["resume"] = True  # jeder weitere Start setzt fort
            t["finished"] = self.clock()
            if kind in ("finished", "max_hours"):
                t["status"] = "fertig"
                t["note"] = msg if kind == "max_hours" else "finish: " + msg[:300]
                weak = (t["stats"]["tool_calls"] < int(self.cfg["weak_min_tool_calls"])
                        or t["stats"]["green_suites"] == 0)
                t["weak"] = weak
                if weak:
                    t["status"] = "schwach"
                    t["note"] += " | Qualitätscheck: zu wenige Tool-Calls oder keine grüne Testsuite"
                archive = bool(self.cfg["archive_finished"])
            elif kind == "stopped":
                t["status"] = "gestoppt"
                t["note"] = "vom Benutzer gestoppt"
            elif kind == "no_tool":
                t["status"] = "gestoppt"
                t["note"] = msg
            elif kind == "auth":
                t["status"] = "fehler"
                t["last_error"] = msg
                self.auth_error = msg
                self.event(f"AUTH-FEHLER – keine neuen Aufgaben bis Einstellungen geprüft: {msg}")
            else:
                t["status"] = "fehler"
                t["last_error"] = msg
                self.record_error()
                self.event(f"Abbruch nach Fehlern: {t['title']}: {msg[:200]}")
            self._record_history(t)
            self.save()
            self.event(f"Ende: {t['title']} → {t['status']}")
        if archive:
            self._archive(tid)
        self.tick()  # sofort nächste Aufgabe starten

    def _record_history(self, t):
        entry = {"id": t["id"], "title": t["title"], "topic": t.get("topic", ""),
                 "source": t.get("source"), "status": t["status"], "weak": t["weak"],
                 "tool_calls": t["stats"].get("tool_calls", 0),
                 "green_suites": t["stats"].get("green_suites", 0),
                 "cost_usd": round(t["stats"].get("cost_usd", 0), 4),
                 "finished": t["finished"]}
        self.history = [h for h in self.history if h.get("id") != t["id"]] + [entry]
        self._save_history()

    def _archive(self, tid):
        ws = os.path.join(self.ws_dir, tid)
        if not os.path.isdir(ws):
            return
        adir = self.cfg.path_of("archive_dir")
        os.makedirs(adir, exist_ok=True)
        target = os.path.join(adir, f"{tid}.tar.gz")
        try:
            with tarfile.open(target, "w:gz") as tar:
                tar.add(ws, arcname=tid)
            shutil.rmtree(ws, ignore_errors=True)
            self.event(f"Workspace archiviert: {target}")
        except Exception as e:
            self.event(f"Archivierung fehlgeschlagen ({tid}): {e}")

    # ------------------------------------------------------------- Generator
    def _example_task(self):
        paths = sorted(glob.glob(os.path.join(self.tasks_dir, "*.md")))
        if not paths:
            return ""
        with open(self.rng.choice(paths), encoding="utf-8") as f:
            return f.read()

    def _all_history(self):
        hist = list(self.history)
        known = {h.get("id") for h in hist}
        for t in self.tasks.values():
            if t["id"] not in known:
                hist.append({"id": t["id"], "title": t["title"], "topic": t.get("topic"),
                             "weak": t.get("weak", False)})
        return hist

    def _start_generator(self):
        try:
            client = self._get_client()
        except Exception as e:
            self.auth_error = f"API-Client konnte nicht erstellt werden: {e}"
            self.event(self.auth_error)
            return
        self.generating = True
        hist = self._all_history()
        example = self._example_task()
        gdir = os.path.join(self.data_dir, "generator")
        task = {"id": "_generator", "title": "Aufgaben-Generator", "prompt": "",
                "mode": "generator"}
        ag = Agent(task, self.cfg, client, os.path.join(gdir, "ws"), gdir,
                   resume=True, sleep=self.agent_sleep, clock=self.clock)
        self.gen_agent = ag
        self.event("Queue leer – generiere neue Aufgabe")

        def caller(messages):
            text, _ = ag.request("generator", messages, with_tools=False)
            ag.save_stats()
            return text

        def run():
            result, err, auth, api_err = None, "", False, False
            try:
                result = generate_task(caller, hist, example, rng=self.rng)
            except AuthError as e:
                err, auth = str(e), True
            except GiveUpError as e:
                err, api_err = str(e), True
            except (StoppedError, ValueError) as e:
                err = str(e)
            except Exception as e:
                err = f"Interner Fehler: {e}"
            with self.lock:
                self.generating = False
                self.gen_thread = None
                if result:
                    self.gen_error = ""
                    swarm = self.cfg["subagents_enabled"] and \
                        self.rng.random() < float(self.cfg["swarm_ratio"])
                    self.add_task(result["title"], result["prompt"], topic=result["topic"],
                                  source="generiert", mode="swarm" if swarm else "single")
                else:
                    self.gen_error = err
                    self.next_gen_time = self.clock() + 300
                    self.event(f"Generator fehlgeschlagen: {err[:200]}")
                    if auth:
                        self.auth_error = err
                    elif api_err and not self.shutting_down:
                        self.record_error()
            if result:
                self.tick()

        th = threading.Thread(target=run, daemon=True, name="generator")
        self.gen_thread = th
        th.start()

    # ------------------------------------------------------------- Statistik / UI
    def _task_stats(self, tid):
        if tid in self.agents:
            ag = self.agents[tid]
            live = ag.live_stats()
            s = {k: live.get(k, 0) for k in STAT_KEYS}
            s["active_seconds"] = ag.active_seconds()
            s["context_tokens"] = ag.context_tokens
            return s
        s = dict(self.tasks[tid].get("stats") or {})
        s.setdefault("context_tokens", 0)
        return s

    def totals(self):
        tot = {k: 0 for k in STAT_KEYS}
        for tid in self.tasks:
            s = self._task_stats(tid)
            for k in STAT_KEYS:
                tot[k] += s.get(k, 0) or 0
        gen = self.gen_agent.stats if self.gen_agent else read_json(
            os.path.join(self.data_dir, "generator", "stats.json"), {})
        for k in STAT_KEYS:
            tot[k] += gen.get(k, 0) or 0
        # gelöschte Aufgaben zählen weiter in die Summe (Historie)
        known = set(self.tasks)
        for h in self.history:
            if h.get("id") not in known:
                tot["cost_usd"] += h.get("cost_usd", 0) or 0
        return tot

    def _sample_cost(self, now):
        if now - self.last_sample >= 60 or not self.cost_samples:
            self.cost_samples.append((now, self.totals()["cost_usd"]))
            self.last_sample = now

    def earnings_rate(self):
        """$ pro Stunde, gleitender Schnitt über die letzte Stunde."""
        now = self.clock()
        cost_now = self.totals()["cost_usd"]
        old = None
        for t, c in self.cost_samples:
            if now - t <= 3600:
                old = (t, c)
                break
        if old is None or now - old[0] < 30:
            return 0.0
        return (cost_now - old[1]) / ((now - old[0]) / 3600)

    def snapshot(self):
        with self.lock:
            tasks = []
            order = list(self.agents) + [q for q in self.queue if q not in self.agents]
            rest = sorted((t for t in self.tasks if t not in order),
                          key=lambda i: -(self.tasks[i].get("finished") or 0))
            for pos, tid in enumerate(order + rest[:100]):
                t = self.tasks[tid]
                ag = self.agents.get(tid)
                st = self._task_stats(tid)
                tasks.append({
                    "id": tid, "title": t["title"], "topic": TOPIC_NAMES.get(
                        t.get("topic"), t.get("topic", "")), "source": t.get("source"),
                    "status": ag.status if ag else t["status"],
                    "running": ag is not None, "weak": t.get("weak", False),
                    "mode": t.get("mode", "single"), "spec_docs": t.get("spec_docs"),
                    "subagents_live": ag.subs.info() if ag else [],
                    "request": ag.request_status() if ag else None,
                    "queue_pos": self.queue.index(tid) + 1 if tid in self.queue else None,
                    "stats": st, "last_error": (ag.stats.get("last_error") if ag else
                                                t.get("last_error")) or "",
                    "note": t.get("note", ""), "started": t.get("started"),
                    "finished": t.get("finished"),
                    "logs": list(ag.logs)[-30:] if ag else self._tail_log(tid),
                })
            tot = self.totals()
            rate = self.earnings_rate()
            return {
                "now": self.clock(), "uptime": self.clock() - self.start_time,
                "totals": tot, "rate_per_hour": rate, "projection_24h": rate * 24,
                "running": len(self.agents), "effective_parallel": self.effective_parallel,
                "max_parallel": self.cfg["max_parallel"], "throttle_note": self.throttle_note,
                "queue_len": len(self.queue), "endless_mode": self.cfg["endless_mode"],
                "paused": self.paused, "auth_error": self.auth_error,
                "config_problem": self.config_problem(), "generating": self.generating,
                "gen_error": self.gen_error, "sandbox_ok": self.sandbox_ok,
                "windows": os.name == "nt",
                "sandbox_msg": self.sandbox_msg, "shell_msg": self.shell_msg, "events": list(self.events)[-20:],
                "tasks": tasks, "config": self.cfg.public(),
            }

    def _tail_log(self, tid, n=30):
        p = os.path.join(self.task_dir(tid), "agent.log")
        try:
            with open(p, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 8000))
                lines = f.read().decode("utf-8", errors="replace").splitlines()
            return lines[-n:]
        except OSError:
            return []

    # ------------------------------------------------------------- Lebenszyklus
    def loop(self, interval=1.0):
        while not self.shutting_down:
            try:
                self.tick()
            except Exception:
                log.exception("Fehler im Scheduler")
            time.sleep(interval)

    def start_background(self):
        th = threading.Thread(target=self.loop, daemon=True, name="scheduler")
        th.start()
        return th

    def shutdown(self, timeout=30):
        with self.lock:
            self.shutting_down = True
            order = list(self.agents)
            agents = list(self.agents.values())
            threads = list(self.threads.values())
            if self.gen_agent:
                self.gen_agent.stop()
        for a in agents:
            a.stop()
        deadline = time.time() + timeout
        for th in threads:
            th.join(max(0.1, deadline - time.time()))
        with self.lock:  # unterbrochene Aufgaben in ursprünglicher Reihenfolge vorn
            front = [i for i in order if i in self.queue]
            self.queue = front + [i for i in self.queue if i not in front]
            self.save()
