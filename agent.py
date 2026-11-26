"""Agent-Kern: Tool-Calling-Schleife, Fehlerbehandlung, Kontext-Komprimierung, Statistik."""
import collections
import json
import os
import random
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

SYSTEM_PROMPT = """You are an experienced, meticulous software engineer working fully \
autonomously on a substantial software project. Nobody will answer questions – make \
well-reasoned decisions yourself and document them.

ENVIRONMENT
- Your working directory (workspace): {workspace}
- All bash commands run in this directory. {sandbox_note}
- Tools: bash (shell command with timeout), read_file, write_file, list_dir, finish.
- Each of your responses is limited to {max_out} tokens (including tool-call arguments). \
Therefore write large files in parts: write_file for the first part, then write_file with \
append=true (at most ~300 lines each), or split the code into modules.
- Tool output is truncated to {limit} characters (beginning + end). Filter large output \
deliberately (e.g. `pytest -q -x`, `| tail -50`, `grep`).
- Python 3 with pytest is available. Use only the standard library unless the task \
explicitly allows otherwise.
- Time budget: at most {max_hours} hours. When the context gets very long, the history is \
summarized automatically, so keep your state in files.

WORKING RULES (mandatory)
1. Test-driven: write pytest tests before or alongside every feature. Run the tests after \
EVERY feature and fix failures before moving on.
2. Maintain DESIGN.md: architecture, modules, data formats, key decisions with rationale.
3. Maintain PROGRESS.md: checklist of all subtasks ([x] done / [ ] open), current state, \
the next concrete step, known issues. Update it after every completed step – after a \
crash or restart you will resume from PROGRESS.md.
4. If the same error fails three times in a row, deliberately change your approach \
(different design, shrink the problem, debug output, minimal example) and note it in \
PROGRESS.md.
5. Work in sensible, verifiable steps. Read files before changing them. Write clean, \
well-structured, documented code.
6. Call `finish` ONLY when ALL requirements of the task are implemented and the entire \
test suite passes (`python3 -m pytest -q`). The harness verifies this on finish and \
rejects it if tests fail.
7. Always respond with tool calls while there is work to do. Plain text without a tool \
call counts as a pause; several pauses in a row end the session.
"""

SUMMARY_PROMPT = """CONTEXT COMPRESSION: The conversation history is about to be cleared \
because the context window is full. Write NOW (no tool calls, text only) a precise, \
complete summary that lets you continue seamlessly:
1. What is already done (modules, files, features, test status with numbers)?
2. Architecture and important design decisions (briefly).
3. What were you working on last, which errors are open, what has already been tried \
without success?
4. The next concrete steps in order.
5. Which files are relevant for the next step?
Be specific (file names, function names, error messages)."""

SPEC_SYSTEM = ("You are an experienced software architect. You write precise, complete "
               "technical documents that a development team can implement and test "
               "without asking questions.")

SPEC_PROMPT = """Before implementation starts, a binding technical specification is \
needed for the following project. It will be stored as docs/SPEC.md; the developer will \
implement exactly according to it.

# Project: {title}

{prompt}

---
Now write the complete SPEC.md (Markdown only, no preamble, no comment before or after). \
Length: at least {words} words. Structure:
1. Purpose, scope, non-goals, glossary
2. Architecture: packages/modules with responsibilities and dependencies
3. Public interfaces: for every module all classes/functions with exact signatures \
(Python type annotations), parameters, return values, exceptions
4. Data formats and algorithms in detail (file formats, encodings, invariants, \
complexity)
5. Exact behavior including edge cases and error handling (with error messages)
6. Detailed examples (input → expected output)
7. Performance requirements and acceptance criteria"""

TESTPLAN_PROMPT = """Now write the binding test catalog docs/TESTPLAN.md matching this \
specification (Markdown only, no preamble). Length: at least {words} words. For every \
module, numbered test cases (e.g. LEX-001) with concrete inputs and exactly expected \
outputs or exceptions; edge cases; property/randomized tests with a fixed seed; \
integration and end-to-end scenarios; performance tests. For each test case state in \
which pytest file it should be implemented."""

DOCS_NOTE = ("The docs/ folder contains the binding specification (docs/SPEC.md) and the "
             "test catalog (docs/TESTPLAN.md). Read both completely with read_file before "
             "you start. Implement exactly according to SPEC.md, implement every test case "
             "from TESTPLAN.md as a pytest test (IDs as comments) and consult them again "
             "whenever something is unclear. Deviate only with a rationale in DESIGN.md.")

TRUNCATED_TOOL_MSG = (
    "Your last response was cut off at the output limit ({limit} tokens); the tool call "
    "was incomplete and was NOT executed. Split large content: write the file in several "
    "parts (first part with write_file, further parts with write_file and append=true, at "
    "most ~300 lines each) or break it into several modules. Continue now with the first "
    "part.")

NUDGE = ("You did not use a tool call. Keep working with the tools (bash, read_file, "
         "write_file, list_dir). If everything is truly finished and all tests pass, "
         "call `finish`.")

TOOLS = [
    {"type": "function", "function": {
        "name": "bash",
        "description": "Runs a bash command in the workspace. Returns the exit code and the "
                       "combined stdout/stderr output (truncated).",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 600)"}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Reads a text file. Optionally starting at line `offset` (1-based), "
                       "at most `limit` lines.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Writes (overwrites) a file. With append=true the content is appended "
                       "to an existing file – use this to write large files in several "
                       "parts. Parent directories are created automatically.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "description": "append to the file instead of "
                                                         "overwriting it"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "Lists a directory (optionally recursive).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Default: workspace"},
            "recursive": {"type": "boolean"}}}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Ends the task. Call ONLY when everything is done and all tests "
                       "pass.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "Summary of the result"}},
            "required": ["summary"]}}},
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", ".tmp",
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
    def __init__(self, msg, partial="", tool_truncated=False):
        super().__init__(msg)
        self.partial = partial
        self.tool_truncated = tool_truncated  # ein Tool-Call wurde abgeschnitten


class BadResponse(Exception):
    pass


class OverloadedResponse(Exception):
    """Modell/Server meldet Überlastung (auch als Antworttext)."""


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
    if is_overload(exc):
        return "overloaded"
    return "retry"


OVERLOAD_STATUS = (429, 502, 503, 504, 529)
OVERLOAD_RE = re.compile(r"\bbusy\b|overload|over capacity|at capacity|try again|"
                         r"temporarily unavailable|service unavailable|too many requests|"
                         r"rate.?limit|server is overloaded|timed out|timeout", re.I)
# strenger für normalen Antworttext (damit echte Antworten nicht verwechselt werden)
OVERLOAD_TEXT_RE = re.compile(r"\bis (currently )?busy\b|overloaded|over capacity|"
                              r"please try again (later|in a)|temporarily unavailable|"
                              r"service unavailable|too many requests", re.I)


def is_overload(exc):
    if isinstance(exc, OverloadedResponse):
        return True
    return error_status(exc) in OVERLOAD_STATUS or bool(OVERLOAD_RE.search(str(exc)))


def retry_after(exc):
    """Sekunden aus dem Retry-After-Header (nur bei 429/503), sonst None."""
    if error_status(exc) not in (429, 503):
        return None
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        v = headers.get("retry-after") or headers.get("Retry-After")
        return max(0.0, float(v)) if v is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def describe_error(exc):
    st = error_status(exc)
    name = type(exc).__name__
    text = str(exc).strip().replace("\n", " ")[:500]
    return f"{name}{f' (HTTP {st})' if st else ''}: {text}"


STREAM_OPTIONS = {"ok": True}


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


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
        self.req_info = None          # laufende Anfrage (für die Live-Anzeige)
        self.req_label = "Antwort"
        self.subs = SubagentManager(self)

    # ------------------------------------------------------------- Statistik/Logs
    def _load_stats(self):
        base = {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0,
                "calls": 0, "retries": 0, "compressions": 0, "cost_usd": 0.0,
                "tool_calls": 0, "green_suites": 0, "active_seconds": 0.0,
                "finish_rejections": 0, "runs": 0, "last_error": "", "subagents": 0,
                "overload_waits": 0}
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
            ct = int((_get(resp, "out_chars", 0) or 0) / 3.5)
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

    def request_status(self):
        """Laufende Anfrage für das UI: Bezeichnung, Sekunden, empfangene Tokens (ca.)."""
        r = self.req_info
        if not r:
            return None
        return {"label": r["label"], "seconds": round(self.clock() - r["started"]),
                "tokens": int(r["chars"] / 3.5), "phase": r.get("phase", "")}

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
        create = self.client.chat.completions.create
        self.req_info = {"label": self.req_label, "started": self.clock(), "chars": 0}
        try:
            if not self.cfg.get("stream", True):
                return create(**kwargs)
            kwargs["stream"] = True
            if STREAM_OPTIONS["ok"]:
                kwargs["stream_options"] = {"include_usage": True}
            try:
                result = create(**kwargs)
            except Exception as e:
                if "stream_options" in kwargs and error_status(e) in (400, 422) \
                        and "stream" in str(e).lower():
                    STREAM_OPTIONS["ok"] = False  # Anbieter kennt stream_options nicht
                    kwargs.pop("stream_options")
                    result = create(**kwargs)
                else:
                    raise
            if _get(result, "choices") is not None or _get(result, "error") is not None:
                return result  # Anbieter hat trotz stream=True eine normale Antwort geschickt
            return self._collect_stream(result, messages)
        finally:
            self.req_info = None

    def _collect_stream(self, stream, messages=None):
        """Setzt eine gestreamte Antwort zusammen; zeigt den Fortschritt live an."""
        content, calls, refusal = [], {}, ""
        fr, usage, nchars = None, None, 0
        try:
            for chunk in stream:
                if self.stop_event.is_set():
                    raise StoppedError("gestoppt")
                u = _get(chunk, "usage")
                if u:
                    usage = u
                prog = _get(chunk, "x_nanogpt_tool_progress") or \
                    (_get(chunk, "model_extra") or {}).get("x_nanogpt_tool_progress")
                if prog and self.req_info is not None:
                    self.req_info["phase"] = str(_get(prog, "status") or "")[:30]
                for ch in _get(chunk, "choices") or []:
                    d = _get(ch, "delta") or _get(ch, "message")
                    c = _get(d, "content")
                    if isinstance(c, str) and c:
                        content.append(c)
                        nchars += len(c)
                    r = _get(d, "reasoning_content") or _get(d, "reasoning")
                    if isinstance(r, str):
                        nchars += len(r)
                    rf = _get(d, "refusal")
                    if rf:
                        refusal += rf
                    for tc in _get(d, "tool_calls") or []:
                        i = _get(tc, "index", 0) or 0
                        slot = calls.setdefault(i, {"id": None, "name": "", "arguments": ""})
                        if _get(tc, "id"):
                            slot["id"] = _get(tc, "id")
                        fn = _get(tc, "function")
                        if _get(fn, "name"):
                            slot["name"] += _get(fn, "name")
                        a = _get(fn, "arguments")
                        if a:
                            slot["arguments"] += a
                            nchars += len(a)
                    f = _get(ch, "finish_reason")
                    if f:
                        fr = f
                if self.req_info is not None:
                    self.req_info["chars"] = nchars
        except StoppedError:
            raise
        except Exception as e:
            text = "".join(content)
            if nchars and messages is not None:  # empfangene Tokens trotzdem verbuchen
                self._account(_NS(usage=None, out_chars=nchars), messages)
            if text.strip():
                raise IncompleteResponse(f"Stream abgebrochen: {describe_error(e)}", text)
            raise
        finally:
            close = getattr(stream, "close", None)
            if close:
                try:
                    close()
                except Exception:
                    pass
        tcs = [_NS(id=c["id"], type="function",
                   function=_NS(name=c["name"], arguments=c["arguments"] or "{}"))
               for _, c in sorted(calls.items())]
        msg = _NS(content="".join(content), tool_calls=tcs or None, refusal=refusal or None)
        return _NS(choices=[_NS(message=msg, finish_reason=fr)] if (content or tcs or fr
                                                                     or refusal) else [],
                   usage=usage, out_chars=nchars)

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
            raise IncompleteResponse("Antwort abgebrochen (finish_reason=length)", content,
                                     tool_truncated=bool(raw_calls))
        calls = []
        for tc in raw_calls:
            fn = _get(tc, "function")
            calls.append({"id": _get(tc, "id") or ("call_" + uuid.uuid4().hex[:12]),
                          "type": "function",
                          "function": {"name": _get(fn, "name") or "",
                                       "arguments": _get(fn, "arguments") or "{}"}})
        if not calls and content.strip() and len(content) < 600 \
                and OVERLOAD_TEXT_RE.search(content):
            raise OverloadedResponse(f"Modell überlastet: {content.strip()[:200]}")
        if not content.strip() and not calls:
            raise BadResponse(f"Leere Antwort (finish_reason={fr})")
        return content, calls

    def request(self, purpose="main", messages=None, with_tools=True):
        """Ein Modellaufruf mit bis zu max_retries Wiederholungen.
        purpose='main' arbeitet auf self.messages (kann komprimieren)."""
        max_retries = int(self.cfg["max_retries"])
        delays = list(self.cfg["retry_delays"]) or [5]
        attempt = 0
        waits = 0
        while True:
            self._check_stop()
            msgs = self.messages if purpose == "main" else messages
            t0 = time.time()
            est = self._estimate_tokens(msgs)
            try:
                resp = self._create(msgs, with_tools)
                self._account(resp, msgs)
                result = self._parse(resp)
                self._jsonl("request", ok=True, secs=round(time.time() - t0, 1),
                            ctx=self.context_tokens or est, purpose=purpose)
                if attempt:
                    self.status = "läuft"
                return result
            except (StoppedError, AuthError):
                raise
            except Exception as e:
                kind = classify_error(e)
                text = describe_error(e)
                self._jsonl("request", ok=False, secs=round(time.time() - t0, 1), ctx=est,
                            purpose=purpose, kind=kind, error=text[:200])
                self.stats["last_error"] = text
                self._jsonl("error", error=text, kind=kind, attempt=attempt + 1)
                if kind == "auth":
                    self.log(f"AUTH-FEHLER: {text}")
                    raise AuthError(text)
                if kind == "overloaded" and self.cfg.get("retry_overloaded_forever", True):
                    # Überlastung: endlos weiter versuchen, zählt nicht gegen max_retries
                    waits += 1
                    self.stats["retries"] += 1
                    self.stats["overload_waits"] = self.stats.get("overload_waits", 0) + 1
                    self.status = f"überlastet – Versuch {waits}"
                    if waits == 1 or waits % 12 == 0:
                        self.log(f"Modell überlastet, versuche weiter (#{waits}): {text[:160]}")
                    if waits % 12 == 0:
                        self.save_stats()
                    delay = float(self.cfg.get("overload_delay", 5))
                    ra = retry_after(e)
                    if ra is not None:
                        delay = max(delay, min(ra, float(self.cfg.get("retry_after_max", 60))))
                    self.sleep(self._jitter(delay))
                    self._check_stop()
                    continue
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
                    partial = e.partial or ""
                    target = None if purpose == "main" else msgs
                    if partial.strip():
                        self._add({"role": "assistant", "content": partial}, target)
                    if getattr(e, "tool_truncated", False):
                        self._add({"role": "user", "content": TRUNCATED_TOOL_MSG.format(
                            limit=self.cfg.get("max_output_tokens") or "?")}, target)
                    else:
                        self._add({"role": "user", "content": "continue"}, target)
                self.save_stats()
                delay = delays[min(attempt - 1, len(delays) - 1)]
                ra = retry_after(e)
                if ra is not None:  # Rate-Limit: Vorgabe des Anbieters respektieren
                    delay = max(delay, min(ra, float(self.cfg.get("retry_after_max", 60))))
                self.sleep(self._jitter(delay))
                self._check_stop()

    def _jitter(self, delay):
        j = float(self.cfg.get("retry_jitter", 0) or 0)
        return delay * random.uniform(1 - j, 1 + j) if j else delay

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
                    out.append("... (more files)")
                    return "\n".join(out)
        return "\n".join(out) or "(empty)"

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

    def docs_exist(self):
        d = os.path.join(self.workspace, "docs")
        return all(os.path.exists(os.path.join(d, f)) for f in ("SPEC.md", "TESTPLAN.md"))

    def prepare_docs(self):
        """Erzeugt docs/SPEC.md und docs/TESTPLAN.md (lange Ausgaben werden per
        'continue' fortgesetzt und zusammengesetzt)."""
        d = os.path.join(self.workspace, "docs")
        os.makedirs(d, exist_ok=True)
        words = int(int(self.cfg.get("spec_doc_tokens", 12000)) * 0.6)
        msgs = []
        self._add({"role": "system", "content": SPEC_SYSTEM}, msgs)
        self._add({"role": "user", "content": SPEC_PROMPT.format(
            title=self.task["title"], prompt=self.task["prompt"], words=words)}, msgs)
        for fname, follow in (("SPEC.md", None), ("TESTPLAN.md", TESTPLAN_PROMPT)):
            path = os.path.join(d, fname)
            if follow:
                self._add({"role": "user", "content": follow.format(words=words)}, msgs)
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    self._add({"role": "assistant", "content": f.read()}, msgs)
                continue
            self.status = f"erstellt {fname}"
            self.req_label = fname
            self.log(f"Erzeuge docs/{fname} (Ziel ca. {words} Wörter)")
            start = len(msgs)
            text, _ = self.request("docs", msgs, with_tools=False)
            parts = [m["content"] for m in msgs[start:] if m["role"] == "assistant"]
            full = "".join(parts + [text]).strip()
            del msgs[start:]
            self._add({"role": "assistant", "content": full}, msgs)
            with open(path, "w", encoding="utf-8") as f:
                f.write(full + "\n")
            self.log(f"docs/{fname} fertig ({len(full.split())} Wörter)")
        self.status = "läuft"
        self.req_label = "Antwort"
        self.save_stats()

    def _workspace_snapshot(self):
        prog = self._read_ws_file("PROGRESS.md", 8000)
        design = self._read_ws_file("DESIGN.md", 6000)
        s = "\n\n## Current content of PROGRESS.md\n" + (prog or "(does not exist)")
        s += "\n\n## Current content of DESIGN.md\n" + (design or "(does not exist)")
        s += "\n\n## Files in the workspace\n" + self.file_tree()
        if self.docs_exist():
            s += ("\n\nBinding: docs/SPEC.md (specification) and docs/TESTPLAN.md "
                  "(test catalog). Re-read the sections relevant to the next step before "
                  "you continue.")
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
            req = [{"role": "system", "content": "You precisely summarize the work history "
                    "of a software agent."},
                   {"role": "user", "content": f"Task:\n{truncate(self.task['prompt'], 6000)}"
                    f"\n\nHistory (abridged):\n{self._condensed_transcript()}\n\n{SUMMARY_PROMPT}"}]
            summary, _ = self.request("summary", req, with_tools=False)
        self.stats["compressions"] += 1
        n = self.stats["compressions"]
        self._jsonl("compression", number=n, summary=summary)
        new = self._base_messages()
        body = (f"# CONTEXT COMPRESSION #{n}\nThe previous history was summarized because "
                f"of its length. Your own summary:\n\n{summary}"
                f"{self._workspace_snapshot()}\n\nNow re-read the files relevant to the next "
                "step (read_file), run the tests and continue with the next open subtask.")
        self.messages = []
        for m in new:
            self._add(m)
        self._add({"role": "user", "content": body})
        self.context_tokens = self._estimate_tokens(self.messages)
        self.status = "läuft"
        self.save_stats()

    # ------------------------------------------------------------- Start
    def _system_prompt(self):
        note = ("bash runs in a bubblewrap sandbox: only the allowed directories are "
                "writable." if self.bash.use_bwrap else
                "Stay strictly inside your workspace.")
        if os.name == "nt":
            note += (" System: Windows, commands run in Git Bash (python/python3 and pytest "
                     "are available; write paths with /).")
        if self.depth:
            scope = ", ".join(os.path.relpath(x, self.workspace) for x in self.scope) \
                or "entire workspace"
            return SUB_SYSTEM_PROMPT.format(workspace=self.workspace, scope=scope,
                                            limit=self.cfg["tool_output_limit"],
                                            max_out=self.cfg.get("max_output_tokens") or 8000,
                                            max_hours=self.max_hours)
        text = SYSTEM_PROMPT.format(workspace=self.workspace, sandbox_note=note,
                                    limit=self.cfg["tool_output_limit"],
                                    max_out=self.cfg.get("max_output_tokens") or "about 8000",
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
                     f"# Work package: {self.task['title']}\n(part of the project "
                     f"\"{self.task.get('parent_title', '')}\")\n\n{self.task['prompt']}"
                     + (f"\n\n## Project DESIGN.md\n{design}" if design else "")
                     + ("\n\nThe binding specification is in docs/SPEC.md, the test "
                        "catalog in docs/TESTPLAN.md – read the sections relevant to your "
                        "package." if self.docs_exist() else "")}]
        return [{"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": f"# Task: {self.task['title']}\n\n"
                 f"{self.task['prompt']}\n\nWorking directory: {self.workspace}"}]

    def _init_messages(self):
        self.messages = []
        for m in self._base_messages():
            self._add(m)
        has_progress = os.path.exists(os.path.join(self.workspace, "PROGRESS.md"))
        if self.depth:
            self._add({"role": "user", "content": "Start working on your work package now."})
        elif self.resume or has_progress:
            self._add({"role": "user", "content":
                       "# RESUMING\nThis task was started earlier and is being resumed "
                       "after a restart, crash or interruption."
                       f"{self._workspace_snapshot()}\n\nGet an overview (read the relevant "
                       "files, run the tests) and continue at the next open point according "
                       "to PROGRESS.md."})
            self.log("Setze anhand PROGRESS.md fort")
        else:
            note = (DOCS_NOTE + " ") if self.docs_exist() else ""
            self._add({"role": "user", "content":
                       f"{note}Start now. First create DESIGN.md and PROGRESS.md."})
        self.context_tokens = self._estimate_tokens(self.messages)

    # ------------------------------------------------------------- Tools
    def _tool_bash(self, args):
        cmd = args.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return "Error: 'command' is missing"
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
            return f"Error: {p} is a directory (use list_dir)"
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        off, lim = args.get("offset"), args.get("limit")
        if off or lim:
            lines = text.splitlines(keepends=True)
            start = max(int(off or 1), 1) - 1
            end = start + int(lim) if lim else len(lines)
            text = "".join(lines[start:end])
            if not text:
                return f"(no lines in this range; the file has {len(lines)} lines)"
        return text if text else "(empty file)"

    def _tool_write(self, args):
        p = self.guard.resolve(args.get("path", ""))
        if self.scope and not any(p == s or p.startswith(s.rstrip(os.sep) + os.sep)
                                  for s in self.scope):
            return ("Error: outside your write scope (scope: " +
                    ", ".join(os.path.relpath(s, self.workspace) for s in self.scope) + ")")
        content = args.get("content")
        if not isinstance(content, str):
            return "Error: 'content' must be a string"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        append = bool(args.get("append"))
        with open(p, "a" if append else "w", encoding="utf-8") as f:
            f.write(content)
        n = len(content.encode("utf-8"))
        if append:
            return f"OK: appended {n} bytes to {p} (file now {os.path.getsize(p)} bytes)"
        return f"OK: wrote {n} bytes to {p}"

    def _tool_list(self, args):
        p = self.guard.resolve(args.get("path") or ".")
        if not os.path.isdir(p):
            return f"Error: {p} is not a directory"
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
                    out.append("... (truncated)")
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
        return "\n".join(out) or "(empty)"

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
                return (False, "finish REJECTED: the test suite is not green (or no "
                        "tests were found). Output of "
                        f"`python3 -m pytest -q`:\n{out}\nFix the problems and call "
                        "finish again afterwards.")
            self.stats["green_suites"] += 1
        self.finished_summary = summary
        return (True, "Task marked as finished.")

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
            return f"Error: invalid JSON arguments ({e}). Please send the call again.", False
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
                res = f"Error: unknown tool '{name}'"
        except PathError as e:
            res = f"Error: {e}"
        except FileNotFoundError as e:
            res = f"Error: file not found: {e.filename}"
        except (StoppedError, AuthError):
            raise
        except Exception as e:
            res = f"Error in {name}: {type(e).__name__}: {e}"
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
            want_docs = self.task.get("spec_docs")
            if want_docs is None:
                want_docs = bool(self.cfg.get("spec_docs"))
            if (self.depth == 0 and want_docs
                    and self.task.get("mode") != "generator" and not self.docs_exist()
                    and not os.path.exists(os.path.join(self.workspace, "PROGRESS.md"))):
                try:
                    self.prepare_docs()
                except GiveUpError as e:
                    self.log(f"Spezifikation konnte nicht erzeugt werden, starte ohne: {e}")
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
