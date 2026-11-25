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
                   "compressions", "cost_usd", "tool_calls", "green_suites", "subagents",
                   "overload_waits")

_SCOPE_DESC = ("List of paths (relative to the workspace) this subagent may write to, "
               "e.g. [\"src/parser/\", \"tests/test_parser.py\"]. Empty = entire workspace.")

SUBAGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "subagent",
        "description": "Delegates a clearly bounded subtask to a subagent with its own fresh "
                       "context (e.g. implement and test a module, investigate the cause of "
                       "a bug, write a test suite for a module, code review). The subagent "
                       "does NOT see your history – give it every necessary detail. Blocks "
                       "until it is done and returns its report.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Short name, e.g. 'parser-tests'"},
            "instructions": {"type": "string",
                             "description": "Detailed assignment including context, "
                                            "interfaces and acceptance criteria"},
            "scope": {"type": "array", "items": {"type": "string"}, "description": _SCOPE_DESC}},
            "required": ["name", "instructions"]}}},
    {"type": "function", "function": {
        "name": "swarm",
        "description": "Starts a swarm: several subagents work IN PARALLEL on independent "
                       "work packages in the same workspace. Every package needs its own, "
                       "non-overlapping write scope. Blocks until all are done and returns "
                       "all reports. Afterwards you integrate the results and run the entire "
                       "test suite.",
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
SUBAGENTS AND SWARM
- With `subagent` you delegate a bounded subtask to an agent with a fresh context; with
  `swarm` up to {max_sub} work packages are processed in parallel.
- Useful for independent modules, large test suites, debugging, reviews. Not for small
  things you can do faster yourself.
- Subagents do not see your history: give the goal, interfaces (signatures, data formats),
  relevant files, test strategy and acceptance criteria completely.
- Every swarm package gets its own, non-overlapping write scope. Define shared interfaces
  BEFOREHAND in DESIGN.md or in code.
- Review the reports critically, read the changed files, integrate and then run the entire
  test suite. Record delegated packages and results in PROGRESS.md.
"""

COORDINATOR_SECTION = """
ROLE: SWARM COORDINATOR
You lead a swarm of subagents. Procedure:
1. Analyze the task, design the architecture in DESIGN.md with clear module boundaries and
   interfaces, and create the project skeleton (packages, stubs, shared types).
2. Write PLAN.md: work packages with dependencies, scope (files) and acceptance criteria.
3. Start independent packages in parallel with `swarm`; dependent packages in later waves.
4. After each wave: review the reports, read the code, write integration tests, run the
   entire test suite, fix errors yourself or have them fixed specifically via `subagent`.
5. Keep PROGRESS.md up to date (waves, packages, status). Call `finish` only when everything
   is integrated and the entire test suite passes.
"""

SUB_SYSTEM_PROMPT = """You are a subagent in an autonomous development team. A lead agent \
has assigned you a work package from a larger project. Nobody will answer questions – \
decide yourself and document assumptions in your report.

ENVIRONMENT
- Shared workspace: {workspace} (other subagents may be working in it at the same time).
- Your write scope: {scope}
  Change only files inside this scope (write_file enforces it; respect it with bash as
  well). You may read other files.
- Tools: bash, read_file, write_file (append=true to append), list_dir, finish.
  Tool output is truncated to {limit} characters. Time budget: {max_hours} hours.
- Your responses are limited to {max_out} tokens: write large files in parts
  (write_file, then write_file with append=true, at most ~300 lines each).

WORKING RULES
1. First read the relevant files (DESIGN.md, interfaces, existing code).
2. Test-driven: write tests for your package and run them after every step (specifically
   your tests, e.g. `python3 -m pytest -q tests/test_xyz.py`).
3. If the same error fails three times, change your approach.
4. Call `finish` when your package is done and your tests pass. The `summary` is your
   report to the lead agent: what was implemented, files, interfaces, test status
   (numbers), assumptions, open problems.
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
            raise ValueError(f"scope '{p}' is outside the workspace")
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
                 "cost_usd": c.stats["cost_usd"], "request": c.request_status(), "scope": [os.path.relpath(s, c.workspace)
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
                    results[nm] = {"outcome": "stopped", "message": "stopped"}
                    return
                with self.lock:
                    self.children[nm] = child
                results[nm] = child.run()
            except Exception as e:  # pragma: no cover
                results[nm] = {"outcome": "error", "message": f"internal error: {e}"}
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
            res = results.get(nm, {"outcome": "error", "message": "no result"})
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
                body += "\nLast message: " + r["last_text"]
            parts.append(
                f"## Subagent '{r['name']}': {r['outcome']}\n"
                f"Calls: {s.get('calls', 0)}, Tool-Calls: {s.get('tool_calls', 0)}, "
                f"Tokens: {s.get('prompt_tokens', 0) + s.get('completion_tokens', 0)}\n"
                f"Report:\n{truncate(body, per)}")
        files = "\n".join(changed[:150]) or "(none)"
        if len(changed) > 150:
            files += f"\n... and {len(changed) - 150} more"
        txt = "\n\n".join(parts) + f"\n\n## Changed files in the workspace\n{files}"
        if deleted:
            txt += "\n\n## Deleted files\n" + "\n".join(deleted[:50])
        txt += ("\n\nReview the results (read the files, run the entire test suite) and "
                "update PROGRESS.md.")
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
            return "Error: 'instructions' is missing or too short (describe the assignment in detail)."
        try:
            scope = _norm_scope(self.agent, args.get("scope"))
        except Exception as e:
            return f"Error in scope: {e}"
        results, changed, deleted = self.run_batch([(name, instr, scope)])
        self._check_auth(results)
        return self.format_report(results, changed, deleted)

    def tool_swarm(self, args):
        tasks = args.get("tasks")
        max_sub = int(self.agent.cfg["max_subagents"])
        if not isinstance(tasks, list) or not tasks:
            return "Error: 'tasks' must be a non-empty list."
        if len(tasks) > max_sub:
            return (f"Error: at most {max_sub} work packages per swarm "
                    f"({len(tasks)} given). Split them into waves.")
        specs = []
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                return f"Error: package {i + 1} is not an object."
            instr = t.get("instructions")
            if not isinstance(instr, str) or len(instr.strip()) < 20:
                return f"Error: package {i + 1} has no detailed 'instructions'."
            try:
                scope = _norm_scope(self.agent, t.get("scope"))
            except Exception as e:
                return f"Error in the scope of package {i + 1}: {e}"
            if not scope and len(tasks) > 1:
                return (f"Error: package {i + 1} ('{t.get('name')}') has no scope. In a swarm "
                        "every package needs its own write scope.")
            specs.append((str(t.get("name") or f"package-{i + 1}"), instr, scope))
        for i in range(len(specs)):
            for j in range(i + 1, len(specs)):
                if scopes_overlap(specs[i][2], specs[j][2]):
                    return (f"Error: the write scopes of '{specs[i][0]}' and "
                            f"'{specs[j][0]}' overlap. Please split them disjointly.")
        t0 = time.time()
        results, changed, deleted = self.run_batch(specs)
        self._check_auth(results)
        head = (f"# Swarm finished: {len(results)} packages, "
                f"{sum(1 for r in results if r['outcome'] == 'finished')} successful, "
                f"duration {int(time.time() - t0)} s\n\n")
        return head + self.format_report(results, changed, deleted)
