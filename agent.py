"""Agent-Kern: Tool-Calling-Schleife, Fehlerbehandlung, Kontext-Komprimierung, Statistik."""
import collections
import json
import os
import re
import threading
import time
import traceback
import uuid

from config import atomic_write_json, read_json
from logutil import AppendLog
from sandbox import BashRunner, PathError, PathGuard, truncate
from swarm import (COORDINATOR_SECTION, SUB_SYSTEM_PROMPT, SUBAGENT_PROMPT_SECTION,
                   SUBAGENT_TOOLS, SubagentManager)

# --------------------------------------------------------------------------- Prompts

SYSTEM_PROMPT = """Du bist ein erfahrener, gründlicher Softwareentwickler und arbeitest \
vollständig autonom an einem größeren Software-Projekt. Niemand beantwortet Rückfragen – \
triff begründete Entscheidungen selbst und dokumentiere sie.

UMGEBUNG
- Dein Arbeitsverzeichnis (Workspace): {workspace}
- Alle bash-Befehle laufen in diesem Verzeichnis. {sandbox_note}
- Werkzeuge: bash (Shell-Befehl mit Timeout), read_file, write_file, list_dir, finish.
- Tool-Ausgaben werden auf {limit} Zeichen gekürzt (Anfang + Ende). Filtere große Ausgaben \
gezielt (z. B. `pytest -q -x`, `| tail -50`, `grep`).
- Python 3 mit pytest steht zur Verfügung. Nutze nur die Standardbibliothek, außer die \
Aufgabe erlaubt ausdrücklich etwas anderes.
- Zeitbudget: maximal {max_hours} Stunden. Der Verlauf wird bei sehr langem Kontext \
automatisch zusammengefasst; halte deshalb deinen Stand in Dateien fest.

ARBEITSWEISE (verbindlich)
1. Test-driven: Schreibe zu jedem Feature zuerst bzw. zeitgleich pytest-Tests. Führe nach \
JEDEM Feature die Tests aus und behebe Fehler, bevor du weitermachst.
2. Pflege DESIGN.md: Architektur, Module, Datenformate, wichtige Entscheidungen samt \
Begründung.
3. Pflege PROGRESS.md: Checkliste aller Teilaufgaben ([x] erledigt / [ ] offen), aktueller \
Stand, nächster konkreter Schritt, bekannte Probleme. Aktualisiere sie nach jedem \
abgeschlossenen Schritt – nach einem Absturz oder Neustart setzt du anhand von PROGRESS.md \
fort.
4. Scheitert derselbe Fehler dreimal hintereinander, wechsle bewusst den Ansatz (anderes \
Design, Problem verkleinern, Debug-Ausgaben, Minimalbeispiel) und notiere das in PROGRESS.md.
5. Arbeite in sinnvollen, überprüfbaren Schritten. Lies Dateien, bevor du sie änderst. \
Schreibe sauberen, gut strukturierten, dokumentierten Code.
6. Rufe `finish` NUR auf, wenn ALLE Anforderungen der Aufgabe umgesetzt sind und die \
gesamte Testsuite grün ist (`python3 -m pytest -q`). Der Harness prüft das beim finish \
nach und lehnt ab, wenn Tests fehlschlagen.
7. Antworte immer mit Tool-Calls, solange es Arbeit gibt. Reiner Text ohne Tool-Call gilt \
als Pause; mehrere Pausen hintereinander beenden die Sitzung.
"""

SUMMARY_PROMPT = """KONTEXT-KOMPRIMIERUNG: Der Gesprächsverlauf wird gleich gelöscht, weil \
das Kontextfenster voll ist. Schreibe JETZT (ohne Tool-Calls, nur Text) eine präzise, \
vollständige Zusammenfassung, mit der du nahtlos weiterarbeiten kannst:
1. Was ist bereits fertig (Module, Dateien, Features, Teststand mit Zahlen)?
2. Architektur und wichtige Designentscheidungen (kurz).
3. Woran wurde zuletzt gearbeitet, welche Fehler sind offen, was wurde schon erfolglos \
versucht?
4. Die nächsten konkreten Schritte in Reihenfolge.
5. Welche Dateien sind für den nächsten Schritt relevant?
Sei konkret (Dateinamen, Funktionsnamen, Fehlermeldungen)."""

NUDGE = ("Du hast keinen Tool-Call verwendet. Arbeite mit den Werkzeugen weiter "
         "(bash, read_file, write_file, list_dir). Wenn wirklich alles fertig ist und "
         "alle Tests grün sind, rufe `finish` auf.")

TOOLS = [
    {"type": "function", "function": {
        "name": "bash",
        "description": "Führt einen bash-Befehl im Workspace aus. Gibt Exit-Code und "
                       "kombinierte stdout/stderr-Ausgabe zurück (gekürzt).",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "Der auszuführende Befehl"},
            "timeout": {"type": "integer", "description": "Timeout in Sekunden (Standard 600)"}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Liest eine Textdatei. Optional ab Zeile `offset` (1-basiert) "
                       "höchstens `limit` Zeilen.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Schreibt (überschreibt) eine Datei vollständig. Ordner werden "
                       "automatisch angelegt.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "Listet einen Ordner auf (optional rekursiv).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Standard: Workspace"},
            "recursive": {"type": "boolean"}}}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Beendet die Aufgabe. NUR aufrufen, wenn alles fertig ist und alle "
                       "Tests grün sind.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "Zusammenfassung des Ergebnisses"}},
            "required": ["summary"]}}},
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv",
             ".mypy_cache"}

# --------------------------------------------------------------------------- Fehler


class AuthError(Exception):
    pass


class GiveUpError(Exception):
    pass


class StoppedError(Exception):
    pass


class ContextTooLongError(Exception):
    pass


class IncompleteResponse(Exception):
    def __init__(self, msg, partial=""):
        super().__init__(msg)
        self.partial = partial


class BadResponse(Exception):
    pass


CONTEXT_WORDS = ("context", "token", "length", "too long", "too large", "maximum")


def error_status(exc):
    st = getattr(exc, "status_code", None)
    if st is None:
        st = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(st) if st is not None else None
    except (TypeError, ValueError):
        return None


def classify_error(exc):
    """-> 'auth' | 'context' | 'incomplete' | 'retry'"""
    if isinstance(exc, IncompleteResponse):
        return "incomplete"
    if isinstance(exc, ContextTooLongError):
        return "context"
    st = error_status(exc)
    msg = str(exc).lower()
    if st in (401, 403):
        return "auth"
    if st == 413:
        return "context"
    if st == 400 and any(w in msg for w in CONTEXT_WORDS):
        return "context"
    return "retry"


def describe_error(exc):
    st = error_status(exc)
    name = type(exc).__name__
    text = str(exc).strip().replace("\n", " ")[:500]
    return f"{name}{f' (HTTP {st})' if st else ''}: {text}"


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# --------------------------------------------------------------------------- Agent


class Agent:
    def __init__(self, task, cfg, client, workspace, data_dir, resume=False,
                 sleep=None, clock=time.time, on_update=None, depth=0, scope=None,
                 stop_event=None, sub_semaphore=None):
        self.task = task                      # dict: id, title, prompt
        self.cfg = cfg
        self.client = client
        self.workspace = os.path.realpath(workspace)
        self.data_dir = data_dir
        self.resume = resume
        self.clock = clock
        self.stop_event = stop_event or threading.Event()
        self.depth = depth                    # 0 = Hauptagent, 1 = Subagent
        self.scope = scope or []              # Schreibbereich eines Subagenten
        self.sub_semaphore = sub_semaphore or threading.BoundedSemaphore(
            max(1, int(cfg["max_total_subagents"])))
        self.on_log = None
        self.last_text = ""
        self.max_hours = float(cfg["subagent_max_hours"] if depth else cfg["max_hours"])
        self.sleep = sleep or (lambda s: self.stop_event.wait(s))
        self.on_update = on_update
        os.makedirs(self.workspace, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

        self.guard = PathGuard(cfg.allowed_dirs(), self.workspace,
                               deny=[cfg.path, cfg.path_of("data_dir")])
        self.bash = BashRunner(self.workspace, cfg.allowed_dirs(), mode=cfg["sandbox"],
                               require=bool(cfg["require_sandbox"]),
                               win_mem_mb=int(cfg["win_job_memory_mb"]),
                               network=cfg["sandbox_network"], protect_files=[cfg.path],
                               output_limit=cfg["tool_output_limit"])
        max_bytes = int(cfg["max_log_mb"] * 1024 * 1024)
        self.convlog = AppendLog(os.path.join(data_dir, "conversation.jsonl"), max_bytes,
                                 cfg["log_keep"])
        self.textlog = AppendLog(os.path.join(data_dir, "agent.log"),
                                 min(max_bytes, 10 * 1024 * 1024), 2)
        self.stats_path = os.path.join(data_dir, "stats.json")
        self.stats = self._load_stats()
        self.logs = collections.deque(maxlen=200)
        self.status = "läuft"
        self.context_tokens = 0
        self.messages = []
        self.no_tool_streak = 0
        self.run_start = None
        self.finished_summary = None
        self.subs = SubagentManager(self)

    # ------------------------------------------------------------- Statistik/Logs
    def _load_stats(self):
        base = {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0,
                "calls": 0, "retries": 0, "compressions": 0, "cost_usd": 0.0,
                "tool_calls": 0, "green_suites": 0, "active_seconds": 0.0,
                "finish_rejections": 0, "runs": 0, "last_error": "", "subagents": 0}
        old = read_json(os.path.join(self.data_dir, "stats.json"), {})
        if self.resume or old:
            base.update({k: v for k, v in old.items() if k in base})
        return base

    def save_stats(self):
        s = dict(self.stats)
        s["task_id"] = self.task["id"]
        s["context_tokens"] = self.context_tokens
        s["active_seconds_now"] = self.active_seconds()
        s["updated"] = self.clock()
        atomic_write_json(self.stats_path, s)

    def active_seconds(self):
        extra = (self.clock() - self.run_start) if self.run_start else 0
        return self.stats["active_seconds"] + extra

    def log(self, line, child_line=False):
        if not child_line:
            line = f"{time.strftime('%H:%M:%S')} {line}"
        self.logs.append(line)
        self.textlog.write(line + "\n")
        if self.on_log:
            try:
                self.on_log(line)
            except Exception:
                pass
        if self.on_update:
            try:
                self.on_update(self)
            except Exception:
                pass

    def _jsonl(self, rec_type, **data):
        rec = {"ts": round(self.clock(), 3), "type": rec_type}
        rec.update(data)
        self.convlog.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _add(self, msg, target=None):
        (self.messages if target is None else target).append(msg)
        self._jsonl("message", message=msg)

    def _estimate_tokens(self, messages):
        return int(len(json.dumps(messages, ensure_ascii=False)) / 3.5)

    def _price(self, prompt, completion):
        return (prompt * self.cfg["price_input_per_m"] +
                completion * self.cfg["price_output_per_m"]) / 1e6

    def _account(self, resp, sent_messages):
        self.stats["calls"] += 1
        usage = _get(resp, "usage")
        pt = int(_get(usage, "prompt_tokens", 0) or 0)
        ct = int(_get(usage, "completion_tokens", 0) or 0)
        details = _get(usage, "prompt_tokens_details")
        cached = int(_get(details, "cached_tokens", 0) or 0)
        if not usage:
            pt = self._estimate_tokens(sent_messages)
        self.stats["prompt_tokens"] += pt
        self.stats["completion_tokens"] += ct
        self.stats["cached_tokens"] += cached
        self.stats["cost_usd"] += self._price(pt, ct)
        self.context_tokens = pt + ct
        self._jsonl("usage", prompt_tokens=pt, completion_tokens=ct, cached_tokens=cached)

    # ------------------------------------------------------------- API-Aufruf
    def subagents_allowed(self):
        return self.depth == 0 and bool(self.cfg["subagents_enabled"]) \
            and self.task.get("mode") != "generator"

    def tools(self):
        return TOOLS + SUBAGENT_TOOLS if self.subagents_allowed() else TOOLS

    def live_stats(self):
        """Eigene Statistik plus laufende Subagenten."""
        s = dict(self.stats)
        for k, v in self.subs.live_stats().items():
            if k != "subagents":
                s[k] = s.get(k, 0) + v
        return s

    def _create(self, messages, with_tools=True):
        kwargs = dict(model=self.cfg["model"], messages=messages)
        if with_tools:
            kwargs["tools"] = self.tools()
        if self.cfg.get("max_output_tokens"):
            kwargs["max_tokens"] = int(self.cfg["max_output_tokens"])
        if self.cfg.get("temperature") is not None:
            kwargs["temperature"] = self.cfg["temperature"]
        return self.client.chat.completions.create(**kwargs)

    def _parse(self, resp):
        choices = _get(resp, "choices") or []
        if not choices:
            err = _get(resp, "error")
            raise BadResponse(f"Leere Antwort (keine choices){': ' + str(err) if err else ''}")
        choice = choices[0]
        msg = _get(choice, "message")
        fr = _get(choice, "finish_reason")
        content = _get(msg, "content") or ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        refusal = _get(msg, "refusal")
        raw_calls = _get(msg, "tool_calls") or []
        if refusal or fr == "content_filter":
            raise BadResponse(f"Antwort abgelehnt ({fr}): {refusal or ''}"[:300])
        if fr == "length":
            raise IncompleteResponse("Antwort abgebrochen (finish_reason=length)", content)
        calls = []
        for tc in raw_calls:
            fn = _get(tc, "function")
            calls.append({"id": _get(tc, "id") or ("call_" + uuid.uuid4().hex[:12]),
                          "type": "function",
                          "function": {"name": _get(fn, "name") or "",
                                       "arguments": _get(fn, "arguments") or "{}"}})
        if not content.strip() and not calls:
            raise BadResponse(f"Leere Antwort (finish_reason={fr})")
        return content, calls

    def request(self, purpose="main", messages=None, with_tools=True):
        """Ein Modellaufruf mit bis zu max_retries Wiederholungen.
        purpose='main' arbeitet auf self.messages (kann komprimieren)."""
        max_retries = int(self.cfg["max_retries"])
        delays = list(self.cfg["retry_delays"]) or [10]
        attempt = 0
        while True:
            self._check_stop()
            msgs = self.messages if purpose == "main" else messages
            try:
                resp = self._create(msgs, with_tools)
                self._account(resp, msgs)
                result = self._parse(resp)
                if attempt:
                    self.status = "läuft"
                return result
            except (StoppedError, AuthError):
                raise
            except Exception as e:
                kind = classify_error(e)
                text = describe_error(e)
                self.stats["last_error"] = text
                self._jsonl("error", error=text, kind=kind, attempt=attempt + 1)
                if kind == "auth":
                    self.log(f"AUTH-FEHLER: {text}")
                    raise AuthError(text)
                attempt += 1
                if attempt > max_retries:
                    self.log(f"Aufgegeben nach {max_retries} Wiederholungen: {text}")
                    raise GiveUpError(text)
                self.stats["retries"] += 1
                self.status = f"retry {attempt}/{max_retries}"
                self.log(f"API-Fehler ({kind}), Versuch {attempt}/{max_retries}: {text}")
                if kind == "context":
                    if purpose != "main":
                        raise ContextTooLongError(text)
                    self.compress("Kontext zu lang (API-Fehler)")
                    self.save_stats()
                    continue
                if kind == "incomplete":
                    partial = (e.partial or "").strip()
                    target = None if purpose == "main" else msgs
                    if partial:
                        self._add({"role": "assistant", "content": partial}, target)
                    self._add({"role": "user", "content": "continue"}, target)
                self.save_stats()
                delay = delays[min(attempt - 1, len(delays) - 1)]
                self.sleep(delay)
                self._check_stop()

    def _check_stop(self):
        if self.stop_event.is_set():
            raise StoppedError("gestoppt")

    # ------------------------------------------------------------- Komprimierung
    def _read_ws_file(self, name, limit=6000):
        p = os.path.join(self.workspace, name)
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return truncate(f.read(), limit)
        except OSError:
            return None

    def file_tree(self, max_entries=200):
        out = []
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            rel = os.path.relpath(root, self.workspace)
            for fn in sorted(files):
                path = fn if rel == "." else os.path.join(rel, fn)
                try:
                    size = os.path.getsize(os.path.join(root, fn))
                except OSError:
                    size = 0
                out.append(f"{path} ({size} B)")
                if len(out) >= max_entries:
                    out.append("... (weitere Dateien)")
                    return "\n".join(out)
        return "\n".join(out) or "(leer)"

    def _condensed_transcript(self, max_chars=300000):
        parts = []
        for m in self.messages[2:]:
            role = m.get("role")
            c = m.get("content") or ""
            if role == "tool":
                c = truncate(c, 1500)
            elif role == "assistant":
                c = truncate(c, 4000)
                for tc in m.get("tool_calls") or []:
                    c += f"\n[Tool-Call {tc['function']['name']}: " \
                         f"{truncate(tc['function']['arguments'], 800)}]"
            else:
                c = truncate(c, 3000)
            parts.append(f"### {role}\n{c}")
        text = "\n\n".join(parts)
        return truncate(text, max_chars)

    def _workspace_snapshot(self):
        prog = self._read_ws_file("PROGRESS.md", 8000)
        design = self._read_ws_file("DESIGN.md", 6000)
        s = "\n\n## Aktueller Inhalt von PROGRESS.md\n" + (prog or "(nicht vorhanden)")
        s += "\n\n## Aktueller Inhalt von DESIGN.md\n" + (design or "(nicht vorhanden)")
        s += "\n\n## Dateien im Workspace\n" + self.file_tree()
        return s

    def compress(self, reason=""):
        self.status = "komprimiert"
        self.log(f"Kontext-Komprimierung ({reason}), ca. {self.context_tokens} Tokens")
        summary = None
        req = list(self.messages) + [{"role": "user", "content": SUMMARY_PROMPT}]
        if self.context_tokens < int(self.cfg["context_limit"]) - 8000:
            try:
                summary, _ = self.request("summary", req, with_tools=True)
            except ContextTooLongError:
                summary = None
        if not summary or not summary.strip():
            req = [{"role": "system", "content": "Du fasst Arbeitsverläufe eines "
                    "Software-Agenten präzise zusammen."},
                   {"role": "user", "content": f"Aufgabe:\n{truncate(self.task['prompt'], 6000)}"
                    f"\n\nVerlauf (gekürzt):\n{self._condensed_transcript()}\n\n{SUMMARY_PROMPT}"}]
            summary, _ = self.request("summary", req, with_tools=False)
        self.stats["compressions"] += 1
        n = self.stats["compressions"]
        self._jsonl("compression", number=n, summary=summary)
        new = self._base_messages()
        body = (f"# KONTEXT-KOMPRIMIERUNG #{n}\nDer bisherige Verlauf wurde wegen "
                f"Kontextlänge zusammengefasst. Deine eigene Zusammenfassung:\n\n{summary}"
                f"{self._workspace_snapshot()}\n\nLies jetzt die für den nächsten Schritt "
                "relevanten Dateien erneut ein (read_file), führe die Tests aus und arbeite "
                "an der nächsten offenen Teilaufgabe weiter.")
        self.messages = []
        for m in new:
            self._add(m)
        self._add({"role": "user", "content": body})
        self.context_tokens = self._estimate_tokens(self.messages)
        self.status = "läuft"
        self.save_stats()

    # ------------------------------------------------------------- Start
    def _system_prompt(self):
        note = ("bash läuft in einer bubblewrap-Sandbox: nur erlaubte Ordner sind "
                "beschreibbar." if self.bash.use_bwrap else
                "Bleibe strikt in deinem Workspace.")
        if os.name == "nt":
            note += (" System: Windows, Befehle laufen in Git Bash (python/python3 und "
                     "pytest sind verfügbar; Pfade mit / schreiben).")
        if self.depth:
            scope = ", ".join(os.path.relpath(x, self.workspace) for x in self.scope) \
                or "gesamter Workspace"
            return SUB_SYSTEM_PROMPT.format(workspace=self.workspace, scope=scope,
                                            limit=self.cfg["tool_output_limit"],
                                            max_hours=self.max_hours)
        text = SYSTEM_PROMPT.format(workspace=self.workspace, sandbox_note=note,
                                    limit=self.cfg["tool_output_limit"],
                                    max_hours=self.max_hours)
        if self.subagents_allowed():
            text += SUBAGENT_PROMPT_SECTION.format(max_sub=self.cfg["max_subagents"])
            if self.task.get("mode") == "swarm":
                text += COORDINATOR_SECTION
        return text

    def _base_messages(self):
        if self.depth:
            design = self._read_ws_file("DESIGN.md", 8000)
            return [{"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content":
                     f"# Arbeitspaket: {self.task['title']}\n(Teil des Projekts "
                     f"\"{self.task.get('parent_title', '')}\")\n\n{self.task['prompt']}"
                     + (f"\n\n## DESIGN.md des Projekts\n{design}" if design else "")}]
        return [{"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": f"# Aufgabe: {self.task['title']}\n\n"
                 f"{self.task['prompt']}\n\nArbeitsverzeichnis: {self.workspace}"}]

    def _init_messages(self):
        self.messages = []
        for m in self._base_messages():
            self._add(m)
        has_progress = os.path.exists(os.path.join(self.workspace, "PROGRESS.md"))
        if self.depth:
            self._add({"role": "user", "content": "Beginne jetzt mit deinem Arbeitspaket."})
        elif self.resume or has_progress:
            self._add({"role": "user", "content":
                       "# FORTSETZUNG\nDiese Aufgabe wurde bereits begonnen und nach einem "
                       "Neustart, Absturz oder Abbruch wieder aufgenommen."
                       f"{self._workspace_snapshot()}\n\nVerschaffe dir einen Überblick "
                       "(relevante Dateien lesen, Tests ausführen) und setze an der nächsten "
                       "offenen Stelle laut PROGRESS.md fort."})
            self.log("Setze anhand PROGRESS.md fort")
        else:
            self._add({"role": "user", "content":
                       "Beginne jetzt. Lege zuerst DESIGN.md und PROGRESS.md an."})
        self.context_tokens = self._estimate_tokens(self.messages)

    # ------------------------------------------------------------- Tools
    def _tool_bash(self, args):
        cmd = args.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return "Fehler: 'command' fehlt"
        timeout = args.get("timeout") or self.cfg["bash_timeout"]
        try:
            timeout = max(1, min(int(timeout), int(self.cfg["bash_max_timeout"])))
        except (TypeError, ValueError):
            timeout = self.cfg["bash_timeout"]
        code, out, _ = self.bash.run(cmd, timeout=timeout, stop_event=self.stop_event)
        if code == 0 and "pytest" in cmd and re.search(r"\b\d+ passed", out) \
                and not re.search(r"\b\d+ (failed|error)", out):
            self.stats["green_suites"] += 1
        return f"exit_code={code}\n{out}"

    def _tool_read(self, args):
        p = self.guard.resolve(args.get("path", ""))
        if os.path.isdir(p):
            return f"Fehler: {p} ist ein Ordner (list_dir benutzen)"
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        off, lim = args.get("offset"), args.get("limit")
        if off or lim:
            lines = text.splitlines(keepends=True)
            start = max(int(off or 1), 1) - 1
            end = start + int(lim) if lim else len(lines)
            text = "".join(lines[start:end])
            if not text:
                return f"(keine Zeilen im Bereich; Datei hat {len(lines)} Zeilen)"
        return text if text else "(leere Datei)"

    def _tool_write(self, args):
        p = self.guard.resolve(args.get("path", ""))
        if self.scope and not any(p == s or p.startswith(s.rstrip(os.sep) + os.sep)
                                  for s in self.scope):
            return ("Fehler: außerhalb deines Schreibbereichs (scope: " +
                    ", ".join(os.path.relpath(s, self.workspace) for s in self.scope) + ")")
        content = args.get("content")
        if not isinstance(content, str):
            return "Fehler: 'content' muss ein String sein"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: {len(content.encode('utf-8'))} Bytes nach {p} geschrieben"

    def _tool_list(self, args):
        p = self.guard.resolve(args.get("path") or ".")
        if not os.path.isdir(p):
            return f"Fehler: {p} ist kein Ordner"
        out = []
        if args.get("recursive"):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                rel = os.path.relpath(root, p)
                for d in dirs:
                    out.append(os.path.join(rel, d).lstrip("./") + "/")
                for fn in sorted(files):
                    fp = os.path.join(root, fn)
                    out.append(f"{os.path.normpath(os.path.join(rel, fn))}  "
                               f"({os.path.getsize(fp) if os.path.exists(fp) else 0} B)")
                if len(out) > 1000:
                    out.append("... (gekürzt)")
                    break
        else:
            for e in sorted(os.scandir(p), key=lambda e: e.name):
                if e.is_dir():
                    out.append(e.name + "/")
                else:
                    try:
                        out.append(f"{e.name}  ({e.stat().st_size} B)")
                    except OSError:
                        out.append(e.name)
        return "\n".join(out) or "(leer)"

    def _tool_finish(self, args):
        summary = str(args.get("summary") or "")
        if self.cfg["verify_on_finish"] and not self.depth and \
                self.stats["finish_rejections"] < int(self.cfg["max_finish_rejections"]):
            code, out, _ = self.bash.run(self.cfg.get("verify_command") or
                                         "python3 -m pytest -q -p no:cacheprovider 2>&1 | tail -60",
                                         timeout=int(self.cfg["bash_max_timeout"]),
                                         stop_event=self.stop_event)
            green = code == 0 and re.search(r"\b\d+ passed", out) and \
                not re.search(r"\b\d+ (failed|errors?)\b", out)
            if not green:
                self.stats["finish_rejections"] += 1
                self.log("finish abgelehnt: Testsuite nicht grün")
                return (False, "finish ABGELEHNT: Die Testsuite ist nicht grün "
                        "(oder es wurden keine Tests gefunden). Ausgabe von "
                        f"`python3 -m pytest -q`:\n{out}\nBehebe die Probleme und rufe "
                        "finish danach erneut auf.")
            self.stats["green_suites"] += 1
        self.finished_summary = summary
        return (True, "Aufgabe als abgeschlossen markiert.")

    def execute_tool(self, call):
        """Führt einen Tool-Call aus. -> (ergebnistext, finished)"""
        name = call["function"]["name"]
        raw = call["function"]["arguments"] or "{}"
        self.stats["tool_calls"] += 1
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            if not isinstance(args, dict):
                raise ValueError("Argumente sind kein Objekt")
        except ValueError as e:
            return f"Fehler: ungültige JSON-Argumente ({e}). Bitte erneut senden.", False
        short = json.dumps(args, ensure_ascii=False)
        if name == "write_file":
            short = f"{args.get('path')} ({len(str(args.get('content', '')))} Zeichen)"
        elif name == "subagent":
            short = f"{args.get('name')} scope={args.get('scope') or 'Workspace'}"
        elif name == "swarm" and isinstance(args.get("tasks"), list):
            short = ", ".join(f"{t.get('name')}→{t.get('scope')}" for t in args["tasks"]
                              if isinstance(t, dict))
        short = short.replace("\n", " ")
        self.log(f"→ {name} {short[:160] + ('…' if len(short) > 160 else '')}")
        try:
            if name == "bash":
                res = self._tool_bash(args)
            elif name == "read_file":
                res = self._tool_read(args)
            elif name == "write_file":
                res = self._tool_write(args)
            elif name == "list_dir":
                res = self._tool_list(args)
            elif name == "finish":
                done, res = self._tool_finish(args)
                return res, done
            elif name in ("subagent", "swarm") and self.subagents_allowed():
                res = (self.subs.tool_subagent(args) if name == "subagent"
                       else self.subs.tool_swarm(args))
            else:
                res = f"Fehler: unbekanntes Tool '{name}'"
        except PathError as e:
            res = f"Fehler: {e}"
        except FileNotFoundError as e:
            res = f"Fehler: Datei nicht gefunden: {e.filename}"
        except (StoppedError, AuthError):
            raise
        except Exception as e:
            res = f"Fehler bei {name}: {type(e).__name__}: {e}"
        return truncate(res, int(self.cfg["tool_output_limit"])), False

    # ------------------------------------------------------------- Hauptschleife
    def stop(self):
        self.stop_event.set()

    def run(self):
        """Führt den Agenten aus. -> dict(outcome, message)"""
        self.run_start = self.clock()
        self.stats["runs"] += 1
        self.status = "läuft"
        outcome = {"outcome": "error", "message": "unbekannt"}
        try:
            self._init_messages()
            self.log(f"Start: {self.task['title']}" +
                     (f" | {self.bash.warning}" if self.bash.warning else ""))
            max_secs = self.max_hours * 3600
            while True:
                self._check_stop()
                if self.active_seconds() >= max_secs:
                    outcome = {"outcome": "max_hours",
                               "message": f"MAX_HOURS ({self.max_hours} h) erreicht"}
                    break
                if self.context_tokens >= int(self.cfg["compress_at"]):
                    self.compress("Schwelle erreicht")
                content, calls = self.request("main")
                msg = {"role": "assistant", "content": content or None}
                if calls:
                    msg["tool_calls"] = calls
                self._add(msg)
                if content.strip():
                    self.last_text = content.strip()[-3000:]
                    self.log("💬 " + truncate(content.strip().replace("\n", " "), 200))
                if not calls:
                    self.no_tool_streak += 1
                    if self.no_tool_streak >= int(self.cfg["max_no_tool_replies"]):
                        outcome = {"outcome": "no_tool",
                                   "message": f"{self.no_tool_streak} Antworten ohne "
                                              "Tool-Call in Folge"}
                        break
                    self._add({"role": "user", "content": NUDGE})
                    self.save_stats()
                    continue
                self.no_tool_streak = 0
                finished = False
                added = 0
                for call in calls:
                    res, done = self.execute_tool(call)
                    self._add({"role": "tool", "tool_call_id": call["id"], "content": res})
                    added += len(res)
                    finished = finished or done
                self.context_tokens += int(added / 3.5)
                self.save_stats()
                if finished:
                    outcome = {"outcome": "finished",
                               "message": truncate(self.finished_summary or "", 2000)}
                    break
        except StoppedError:
            outcome = {"outcome": "stopped", "message": "gestoppt"}
        except AuthError as e:
            outcome = {"outcome": "auth", "message": str(e)}
        except GiveUpError as e:
            outcome = {"outcome": "error", "message": str(e)}
        except Exception as e:  # Programmfehler: sauber abbrechen
            tb = traceback.format_exc()
            self._jsonl("crash", traceback=tb)
            outcome = {"outcome": "error", "message": f"Interner Fehler: {e}"}
        finally:
            self.stats["active_seconds"] = self.active_seconds()
            self.run_start = None
            if outcome["outcome"] in ("error", "auth"):
                self.stats["last_error"] = outcome["message"]
            self.save_stats()
            self._jsonl("end", **outcome)
            self.log(f"Ende: {outcome['outcome']} – {truncate(outcome['message'], 200)}")
        return outcome
