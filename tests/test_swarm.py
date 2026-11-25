import json
import os
import re
import threading
import time

import pytest

from agent import Agent
from fakes import FakeAPIError, resp, tool, FakeClient
from swarm import scopes_overlap

SUB_MARK = "Subagent in einem autonomen"


def spawn(**args):
    return resp(calls=[("subagent", args)])


def tool_count(msgs):
    return sum(1 for m in msgs if m["role"] == "tool")


def is_sub(kwargs):
    return SUB_MARK in kwargs["messages"][0]["content"]


def sub_name(kwargs):
    return re.search(r"# Arbeitspaket: (\S+)", kwargs["messages"][1]["content"]).group(1)


def make_agent(cfg, client, task=None, **kw):
    task = task or {"id": "t1", "title": "Projekt", "prompt": "Baue etwas."}
    ws = os.path.join(cfg.path_of("workspaces_dir"), task["id"])
    dd = os.path.join(cfg.path_of("data_dir"), "tasks", task["id"])
    return Agent(task, cfg, client, ws, dd, sleep=lambda s: None, **kw)


def default_sub(kwargs):
    """Subagent: schreibt eine Datei in seinen Bereich und meldet fertig."""
    name = sub_name(kwargs)
    if tool_count(kwargs["messages"]) == 0:
        return tool("write_file", path=f"{name}/out.txt", content=name)
    return tool("finish", summary=f"Paket {name} fertig, 3 Tests grün")


INSTR = "Implementiere das Modul vollständig inklusive Tests und Dokumentation."


def test_subagent_tool_runs_child_and_reports(cfg):
    def brain(kw):
        if is_sub(kw):
            return default_sub(kw)
        if tool_count(kw["messages"]) == 0:
            return spawn(name="lexer", instructions=INSTR, scope=["lexer"])
        return tool("finish", summary="ok")
    client = FakeClient(default=brain)
    a = make_agent(cfg, client)
    assert a.run()["outcome"] == "finished"
    report = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"][0]["content"]
    assert "Subagent 'lexer': finished" in report
    assert "Paket lexer fertig" in report
    assert "lexer/out.txt" in report            # geänderte Dateien
    assert open(os.path.join(a.workspace, "lexer", "out.txt")).read() == "lexer"
    assert a.stats["subagents"] == 1
    assert a.stats["calls"] == 4                # 2 eigene + 2 des Subagenten
    sub_dirs = os.listdir(os.path.join(a.data_dir, "sub"))
    assert sub_dirs == ["001-lexer"]
    conv = os.path.join(a.data_dir, "sub", "001-lexer", "conversation.jsonl")
    assert any(json.loads(x)["type"] == "end" for x in open(conv))
    assert any("[lexer]" in line for line in a.logs)


def test_subagent_has_no_spawn_tools_and_own_prompt(cfg):
    seen = []

    def brain(kw):
        if is_sub(kw):
            seen.append({t["function"]["name"] for t in kw["tools"]})
            return default_sub(kw)
        if tool_count(kw["messages"]) == 0:
            names = {t["function"]["name"] for t in kw["tools"]}
            assert {"subagent", "swarm"} <= names
            return spawn(name="x", instructions=INSTR, scope=["x"])
        return tool("finish", summary="ok")
    a = make_agent(cfg, FakeClient(default=brain))
    a.run()
    assert seen and all("subagent" not in s and "swarm" not in s for s in seen)


def test_swarm_runs_in_parallel(cfg):
    barrier = threading.Barrier(3, timeout=10)

    def brain(kw):
        if is_sub(kw):
            if tool_count(kw["messages"]) == 0:
                barrier.wait()   # alle drei müssen gleichzeitig laufen
            return default_sub(kw)
        if tool_count(kw["messages"]) == 0:
            return tool("swarm", tasks=[
                {"name": n, "instructions": INSTR, "scope": [n]} for n in ("a", "b", "c")])
        return tool("finish", summary="ok")
    client = FakeClient(default=brain)
    a = make_agent(cfg, client)
    assert a.run()["outcome"] == "finished"
    report = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"][0]["content"]
    assert "3 Pakete, 3 erfolgreich" in report
    for n in "abc":
        assert os.path.exists(os.path.join(a.workspace, n, "out.txt"))
    assert a.stats["subagents"] == 3


def test_swarm_rejects_overlapping_or_missing_scopes(cfg):
    calls = []

    def brain(kw):
        n = tool_count(kw["messages"])
        calls.append(n)
        if n == 0:
            return tool("swarm", tasks=[{"name": "a", "instructions": INSTR, "scope": ["src"]},
                                        {"name": "b", "instructions": INSTR,
                                         "scope": ["src/b.py"]}])
        if n == 1:
            return tool("swarm", tasks=[{"name": "a", "instructions": INSTR, "scope": []},
                                        {"name": "b", "instructions": INSTR, "scope": ["b"]}])
        if n == 2:
            return tool("swarm", tasks=[{"name": str(i), "instructions": INSTR, "scope": [str(i)]}
                                        for i in range(9)])
        if n == 3:
            return tool("swarm", tasks=[{"name": "a", "instructions": INSTR,
                                         "scope": ["../../ausbruch"]}])
        return tool("finish", summary="ok")
    client = FakeClient(default=brain)
    a = make_agent(cfg, client)
    a.run()
    res = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    assert "überschneiden" in res[0]
    assert "keinen scope" in res[1]
    assert "höchstens 4" in res[2]
    assert "scope" in res[3] and "Fehler" in res[3]
    assert a.stats["subagents"] == 0


def test_scope_enforced_for_write(cfg):
    def brain(kw):
        if is_sub(kw):
            n = tool_count(kw["messages"])
            if n == 0:
                return tool("write_file", path="fremd/x.txt", content="x")
            return tool("finish", summary="done")
        if tool_count(kw["messages"]) == 0:
            return spawn(name="s", instructions=INSTR, scope=["meins"])
        return tool("finish", summary="ok")
    client = FakeClient(default=brain)
    a = make_agent(cfg, client)
    a.run()
    sub_req = [r for r in client.requests if is_sub(r)][-1]
    res = [m["content"] for m in sub_req["messages"] if m["role"] == "tool"][0]
    assert "außerhalb deines Schreibbereichs" in res
    assert not os.path.exists(os.path.join(a.workspace, "fremd"))


def test_failed_subagent_is_reported_and_parent_continues(cfg):
    def brain(kw):
        if is_sub(kw):
            return FakeAPIError(500, "sub kaputt")
        if tool_count(kw["messages"]) == 0:
            return spawn(name="s", instructions=INSTR)
        return tool("finish", summary="ok")
    client = FakeClient(default=brain)
    a = make_agent(cfg, client)
    assert a.run()["outcome"] == "finished"
    report = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"][0]["content"]
    assert "Subagent 's': error" in report and "sub kaputt" in report
    assert a.stats["retries"] == 4             # Retries des Subagenten zählen mit


def test_subagent_auth_error_aborts_parent(cfg):
    def brain(kw):
        if is_sub(kw):
            return FakeAPIError(401, "bad key")
        return spawn(name="s", instructions=INSTR)
    a = make_agent(cfg, FakeClient(default=brain))
    out = a.run()
    assert out["outcome"] == "auth"


def test_stop_propagates_to_subagents(cfg):
    started = threading.Event()

    def brain(kw):
        if is_sub(kw):
            started.set()
            return tool("bash", command="sleep 0.2")
        return spawn(name="lang", instructions=INSTR)
    a = make_agent(cfg, FakeClient(default=brain))
    th = threading.Thread(target=lambda: setattr(a, "out", a.run()))
    th.start()
    assert started.wait(5)
    assert a.subs.info()[0]["name"] == "lang"
    assert a.live_stats()["calls"] > a.stats["calls"]   # laufender Subagent zählt live mit
    a.stop()
    th.join(10)
    assert a.out["outcome"] == "stopped"


def test_global_subagent_limit(cfg):
    cfg.data["max_total_subagents"] = 1
    active, peak = [0], [0]
    lock = threading.Lock()

    def brain(kw):
        if is_sub(kw):
            if tool_count(kw["messages"]) == 0:
                with lock:
                    active[0] += 1
                    peak[0] = max(peak[0], active[0])
                time.sleep(0.05)
                return tool("write_file", path=f"{sub_name(kw)}/x", content="1")
            with lock:
                active[0] -= 1
            return tool("finish", summary="ok")
        if tool_count(kw["messages"]) == 0:
            return tool("swarm", tasks=[{"name": n, "instructions": INSTR, "scope": [n]}
                                        for n in ("a", "b", "c")])
        return tool("finish", summary="ok")
    a = make_agent(cfg, FakeClient(default=brain))
    assert a.run()["outcome"] == "finished"
    assert peak[0] == 1


def test_swarm_mode_prompt_and_disable(cfg):
    task = {"id": "s1", "title": "P", "prompt": "x", "mode": "swarm"}
    client = FakeClient([tool("finish", summary="ok")])
    make_agent(cfg, client, task=task).run()
    sysmsg = client.requests[0]["messages"][0]["content"]
    assert "SCHWARM-KOORDINATOR" in sysmsg and "SUBAGENTEN UND SCHWARM" in sysmsg
    cfg.data["subagents_enabled"] = False
    client = FakeClient([tool("finish", summary="ok")])
    make_agent(cfg, client, task={"id": "s2", "title": "P", "prompt": "x"}).run()
    assert "SUBAGENTEN" not in client.requests[0]["messages"][0]["content"]
    assert "swarm" not in {t["function"]["name"] for t in client.requests[0]["tools"]}


def test_scopes_overlap():
    assert scopes_overlap(["/w/src"], ["/w/src/a.py"])
    assert scopes_overlap(["/w/a"], ["/w/a"])
    assert not scopes_overlap(["/w/src"], ["/w/src2"])
    assert not scopes_overlap(["/w/a", "/w/b"], ["/w/c"])
