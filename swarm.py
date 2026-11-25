"""Subagenten und Schwarm: ein Agent delegiert Teilaufgaben an parallel laufende Kind-Agenten.

- `subagent`: eine fokussierte Teilaufgabe an einen Kind-Agenten delegieren (blockierend).
- `swarm`: mehrere Arbeitspakete mit getrennten Schreibbereichen (scope) parallel ausführen.
Kind-Agenten arbeiten im selben Workspace, haben einen eigenen Verlauf, eigene Logs und
Statistik (wird nach Abschluss in die Statistik der Aufgabe übernommen) und können selbst
keine weiteren Subagenten starten.
"""
import os
import re
import threading
import time

STAT_MERGE_KEYS = ("prompt_tokens", "cached_tokens", "completion_tokens", "calls", "retries",
                   "compressions", "cost_usd", "tool_calls", "green_suites", "subagents")

_SCOPE_DESC = ("Liste von Pfaden (relativ zum Workspace), in die dieser Subagent schreiben "
               "darf, z. B. [\"src/parser/\", \"tests/test_parser.py\"]. Leer = ganzer Workspace.")

SUBAGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "subagent",
        "description": "Delegiert eine klar abgegrenzte Teilaufgabe an einen Subagenten mit "
                       "eigenem, frischem Kontext (z. B. Modul implementieren und testen, "
                       "Fehlerursache untersuchen, Testsuite für ein Modul schreiben, Code-Review). "
                       "Der Subagent sieht deinen Verlauf NICHT – gib ihm alle nötigen Details. "
                       "Blockiert, bis er fertig ist, und liefert seinen Bericht zurück.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Kurzer Name, z. B. 'parser-tests'"},
            "instructions": {"type": "string",
                             "description": "Ausführlicher Arbeitsauftrag inkl. Kontext, "
                                            "Schnittstellen, Akzeptanzkriterien"},
            "scope": {"type": "array", "items": {"type": "string"}, "description": _SCOPE_DESC}},
            "required": ["name", "instructions"]}}},
    {"type": "function", "function": {
        "name": "swarm",
        "description": "Startet einen Schwarm: mehrere Subagenten arbeiten PARALLEL an "
                       "unabhängigen Arbeitspaketen im selben Workspace. Jedes Paket braucht "
                       "einen eigenen, überschneidungsfreien Schreibbereich (scope). Blockiert, "
                       "bis alle fertig sind, und liefert alle Berichte. Danach integrierst du "
                       "die Ergebnisse und lässt die gesamte Testsuite laufen.",
        "parameters": {"type": "object", "properties": {
            "tasks": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "instructions": {"type": "string"},
                "scope": {"type": "array", "items": {"type": "string"},
                          "description": _SCOPE_DESC}},
                "required": ["name", "instructions", "scope"]}}},
            "required": ["tasks"]}}},
]

SUBAGENT_PROMPT_SECTION = """
SUBAGENTEN UND SCHWARM
- Mit `subagent` delegierst du eine abgegrenzte Teilaufgabe an einen Agenten mit frischem
  Kontext; mit `swarm` lässt du bis zu {max_sub} Arbeitspakete parallel bearbeiten.
- Sinnvoll für unabhängige Module, umfangreiche Testsuiten, Fehlersuche, Reviews. Nicht für
  Kleinigkeiten, die du selbst schneller erledigst.
- Subagenten sehen deinen Verlauf nicht: Gib Ziel, Schnittstellen (Signaturen, Datenformate),
  relevante Dateien, Teststrategie und Akzeptanzkriterien vollständig an.
- Jedes Schwarm-Paket bekommt einen eigenen, überschneidungsfreien Schreibbereich (scope).
  Lege gemeinsame Schnittstellen VORHER in DESIGN.md bzw. im Code fest.
- Prüfe die Berichte kritisch, lies die geänderten Dateien, integriere und führe danach die
  gesamte Testsuite aus. Vermerke delegierte Pakete und Ergebnisse in PROGRESS.md.
"""

COORDINATOR_SECTION = """
ROLLE: SCHWARM-KOORDINATOR
Du leitest einen Schwarm von Subagenten. Vorgehen:
1. Analysiere die Aufgabe, entwirf die Architektur in DESIGN.md mit klaren Modulgrenzen und
   Schnittstellen und lege das Projektgerüst an (Pakete, Stubs, gemeinsame Typen).
2. Schreibe PLAN.md: Arbeitspakete mit Abhängigkeiten, Scope (Dateien) und Akzeptanzkriterien.
3. Starte unabhängige Pakete mit `swarm` parallel; abhängige Pakete in späteren Wellen.
4. Nach jeder Welle: Berichte prüfen, Code lesen, Integrationstests schreiben, gesamte
   Testsuite ausführen, Fehler selbst beheben oder gezielt per `subagent` beheben lassen.
5. Halte PROGRESS.md aktuell (Wellen, Pakete, Status). `finish` erst, wenn alles integriert
   und die gesamte Testsuite grün ist.
"""

SUB_SYSTEM_PROMPT = """Du bist ein Subagent in einem autonomen Entwicklerteam. Ein \
Hauptagent hat dir ein Arbeitspaket aus einem größeren Projekt übertragen. Niemand \
beantwortet Rückfragen – entscheide selbst und dokumentiere Annahmen im Bericht.

UMGEBUNG
- Gemeinsamer Workspace: {workspace} (andere Subagenten arbeiten evtl. gleichzeitig darin).
- Dein Schreibbereich (scope): {scope}
  Ändere ausschließlich Dateien in diesem Bereich (write_file erzwingt das; halte dich auch
  bei bash daran). Andere Dateien darfst du lesen.
- Werkzeuge: bash, read_file, write_file, list_dir, finish. Tool-Ausgaben werden auf {limit}
  Zeichen gekürzt. Zeitbudget: {max_hours} Stunden.

ARBEITSWEISE
1. Lies zuerst die relevanten Dateien (DESIGN.md, Schnittstellen, bestehender Code).
2. Test-driven: Tests zu deinem Paket schreiben, nach jedem Schritt ausführen (gezielt deine
   Tests, z. B. `python3 -m pytest -q tests/test_xyz.py`).
3. Bei dreimaligem Scheitern am selben Fehler den Ansatz wechseln.
4. Rufe `finish` auf, wenn dein Paket fertig ist und deine Tests grün sind. Der `summary`
   ist dein Bericht an den Hauptagenten: was umgesetzt wurde, Dateien, Schnittstellen,
   Teststand (Zahlen), Annahmen, offene Probleme.
"""


def slug(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text)).strip("-").lower()
    return s[:30] or "sub"


def _norm_scope(agent, scope):
    """Scope-Pfade auflösen (müssen im Workspace liegen)."""
    out = []
    for p in scope or []:
        if not isinstance(p, str) or not p.strip():
            continue
        real = agent.guard.resolve(p)
        if not (real == agent.workspace or real.startswith(agent.workspace + os.sep)):
            raise ValueError(f"Scope '{p}' liegt außerhalb des Workspace")
        out.append(real)
    return out


def scopes_overlap(a, b):
    for x in a:
        for y in b:
            if x == y or x.startswith(y.rstrip(os.sep) + os.sep) or \
                    y.startswith(x.rstrip(os.sep) + os.sep):
                return True
    return False


def _mtimes(root):
    from agent import SKIP_DIRS
    res = {}
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(r, f)
            try:
                res[p] = os.path.getmtime(p)
            except OSError:
                pass
    return res


def _changed_files(root, before):
    after = _mtimes(root)
    changed = [p for p, m in after.items() if before.get(p) != m]
    deleted = [p for p in before if p not in after]
    rel = lambda p: os.path.relpath(p, root)  # noqa: E731
    return sorted(rel(p) for p in changed), sorted(rel(p) for p in deleted)


class SubagentManager:
    """Hängt an einem (Haupt-)Agenten und verwaltet dessen Kind-Agenten."""

    def __init__(self, agent):
        self.agent = agent
        self.children = {}          # name -> Agent (laufend)
        self.lock = threading.Lock()

    # ------------------------------------------------------------- Anzeige / Statistik
    def live_stats(self):
        with self.lock:
            kids = list(self.children.values())
        tot = {}
        for c in kids:
            s = c.live_stats()
            for k in STAT_MERGE_KEYS:
                tot[k] = tot.get(k, 0) + (s.get(k, 0) or 0)
        return tot

    def info(self):
        with self.lock:
            kids = list(self.children.items())
        return [{"name": n, "status": c.status, "calls": c.stats["calls"],
                 "tool_calls": c.stats["tool_calls"], "context_tokens": c.context_tokens,
                 "cost_usd": c.stats["cost_usd"], "scope": [os.path.relpath(s, c.workspace)
                                                            for s in (c.scope or [])],
                 "last": (list(c.logs)[-1] if c.logs else "")} for n, c in kids]

    # ------------------------------------------------------------- Ausführung
    def _make_child(self, name, instructions, scope):
        from agent import Agent
        a = self.agent
        n = a.stats.get("subagents", 0) + 1
        a.stats["subagents"] = n
        sid = f"{n:03d}-{slug(name)}"
        task = {"id": f"{a.task['id']}/{sid}", "title": name, "prompt": instructions,
                "parent_title": a.task.get("title", ""), "mode": "sub"}
        child = Agent(task, a.cfg, a.client, a.workspace,
                      os.path.join(a.data_dir, "sub", sid), sleep=a.sleep, clock=a.clock,
                      depth=a.depth + 1, scope=scope, stop_event=a.stop_event,
                      sub_semaphore=a.sub_semaphore)
        child.on_log = lambda line, nm=name: a.log(f"  ↳ [{nm}] {line}", child_line=True)
        return child

    def run_batch(self, specs):
        """specs: Liste (name, instructions, scope_real). -> Liste Ergebnis-dicts."""
        a = self.agent
        before = _mtimes(a.workspace)
        children = []
        used = set()
        for name, instr, scope in specs:
            nm = name
            i = 2
            while nm in used:
                nm = f"{name}-{i}"
                i += 1
            used.add(nm)
            children.append((nm, self._make_child(nm, instr, scope)))
        results = {}

        def run_one(nm, child):
            acquired = False
            try:
                while not a.stop_event.is_set():
                    if a.sub_semaphore.acquire(timeout=0.5):
                        acquired = True
                        break
                if not acquired:
                    results[nm] = {"outcome": "stopped", "message": "gestoppt"}
                    return
                with self.lock:
                    self.children[nm] = child
                results[nm] = child.run()
            except Exception as e:  # pragma: no cover
                results[nm] = {"outcome": "error", "message": f"Interner Fehler: {e}"}
            finally:
                if acquired:
                    a.sub_semaphore.release()

        threads = []
        for nm, child in children:
            th = threading.Thread(target=run_one, args=(nm, child), daemon=True,
                                  name=f"sub-{nm}")
            th.start()
            threads.append(th)
        a.log(f"Subagenten gestartet: {', '.join(nm for nm, _ in children)}")
        for th in threads:
            th.join()
        out = []
        for nm, child in children:
            with self.lock:
                self.children.pop(nm, None)
            for k in STAT_MERGE_KEYS:
                if k == "subagents":
                    continue
                a.stats[k] += child.stats.get(k, 0) or 0
            res = results.get(nm, {"outcome": "error", "message": "kein Ergebnis"})
            res = dict(res, name=nm, stats=dict(child.stats), last_text=child.last_text)
            out.append(res)
        changed, deleted = _changed_files(a.workspace, before)
        return out, changed, deleted

    def format_report(self, results, changed, deleted):
        from sandbox import truncate
        limit = int(self.agent.cfg["tool_output_limit"])
        per = max(1500, (limit - 2500) // max(1, len(results)))
        parts = []
        for r in results:
            s = r["stats"]
            body = r.get("message") or ""
            if r["outcome"] == "no_tool" and r.get("last_text"):
                body += "\nLetzte Nachricht: " + r["last_text"]
            parts.append(
                f"## Subagent '{r['name']}': {r['outcome']}\n"
                f"Calls: {s.get('calls', 0)}, Tool-Calls: {s.get('tool_calls', 0)}, "
                f"Tokens: {s.get('prompt_tokens', 0) + s.get('completion_tokens', 0)}\n"
                f"Bericht:\n{truncate(body, per)}")
        files = "\n".join(changed[:150]) or "(keine)"
        if len(changed) > 150:
            files += f"\n... und {len(changed) - 150} weitere"
        txt = "\n\n".join(parts) + f"\n\n## Geänderte Dateien im Workspace\n{files}"
        if deleted:
            txt += "\n\n## Gelöschte Dateien\n" + "\n".join(deleted[:50])
        txt += ("\n\nPrüfe die Ergebnisse (Dateien lesen, gesamte Testsuite ausführen) und "
                "aktualisiere PROGRESS.md.")
        return txt

    def _check_auth(self, results):
        from agent import AuthError
        for r in results:
            if r["outcome"] == "auth":
                raise AuthError(r["message"])

    def tool_subagent(self, args):
        name = str(args.get("name") or "subagent")
        instr = args.get("instructions")
        if not isinstance(instr, str) or len(instr.strip()) < 20:
            return "Fehler: 'instructions' fehlt oder ist zu knapp (ausführlich beschreiben)."
        try:
            scope = _norm_scope(self.agent, args.get("scope"))
        except Exception as e:
            return f"Fehler im scope: {e}"
        results, changed, deleted = self.run_batch([(name, instr, scope)])
        self._check_auth(results)
        return self.format_report(results, changed, deleted)

    def tool_swarm(self, args):
        tasks = args.get("tasks")
        max_sub = int(self.agent.cfg["max_subagents"])
        if not isinstance(tasks, list) or not tasks:
            return "Fehler: 'tasks' muss eine nicht-leere Liste sein."
        if len(tasks) > max_sub:
            return (f"Fehler: höchstens {max_sub} Arbeitspakete pro Schwarm "
                    f"({len(tasks)} angegeben). Teile in Wellen auf.")
        specs = []
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                return f"Fehler: Paket {i + 1} ist kein Objekt."
            instr = t.get("instructions")
            if not isinstance(instr, str) or len(instr.strip()) < 20:
                return f"Fehler: Paket {i + 1} hat keine ausführlichen 'instructions'."
            try:
                scope = _norm_scope(self.agent, t.get("scope"))
            except Exception as e:
                return f"Fehler im scope von Paket {i + 1}: {e}"
            if not scope and len(tasks) > 1:
                return (f"Fehler: Paket {i + 1} ('{t.get('name')}') hat keinen scope. Im Schwarm "
                        "braucht jedes Paket einen eigenen Schreibbereich.")
            specs.append((str(t.get("name") or f"paket-{i + 1}"), instr, scope))
        for i in range(len(specs)):
            for j in range(i + 1, len(specs)):
                if scopes_overlap(specs[i][2], specs[j][2]):
                    return (f"Fehler: Die Schreibbereiche von '{specs[i][0]}' und "
                            f"'{specs[j][0]}' überschneiden sich. Bitte disjunkt aufteilen.")
        t0 = time.time()
        results, changed, deleted = self.run_batch(specs)
        self._check_auth(results)
        head = (f"# Schwarm beendet: {len(results)} Pakete, "
                f"{sum(1 for r in results if r['outcome'] == 'finished')} erfolgreich, "
                f"Dauer {int(time.time() - t0)} s\n\n")
        return head + self.format_report(results, changed, deleted)
