import json
import os
import time

import pytest

from config import Config
from fakes import FakeAPIError, FakeClient, resp, tool
from manager import Manager

GEN_TEXT = "TITEL: Raytracer mit BVH\n---\n" + " ".join(["Anforderung"] * 700) + " pytest"


def finish():
    return tool("finish", summary="ok")


def make(cfg, tmp_path, client, clock=None, **kw):
    tdir = tmp_path / "tasks_empty"
    tdir.mkdir(exist_ok=True)
    m = Manager(cfg, client_factory=lambda c: client, sleep=lambda s: None,
                clock=clock or time.time, tasks_dir=str(tdir), **kw)
    return m


def wait_idle(m, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        with m.lock:
            if not m.agents and not m.generating:
                return
        time.sleep(0.02)
    raise AssertionError("Agenten laufen noch")


def test_builtin_tasks_loaded(cfg, tmp_path):
    tdir = tmp_path / "tasks"
    tdir.mkdir()
    (tdir / "1_sql.md").write_text("# SQL-Datenbank\nText")
    (tdir / "2_riscv.md").write_text("# RISC-V\nText")
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    assert [m.tasks[i]["title"] for i in m.queue] == ["SQL-Datenbank", "RISC-V"]
    assert m.tasks[m.queue[0]]["topic"] == "database"
    assert m.get_prompt(m.queue[0]) == "Text"


def test_queue_add_move_delete_persist(cfg, tmp_path):
    m = make(cfg, tmp_path, FakeClient())
    a = m.add_task("A", "a")
    b = m.add_task("B", "b")
    c = m.add_task("C", "c")
    assert m.queue == [a, b, c]
    m.move(c, "up")
    assert m.queue == [a, c, b]
    m.move(b, "top")
    assert m.queue == [b, a, c]
    m.move(b, "down")
    assert m.queue == [a, b, c]
    d = m.add_task("D", "d", front=True)
    assert m.queue[0] == d
    assert m.delete(a)
    assert a not in m.tasks and a not in m.queue
    m2 = make(cfg, tmp_path, FakeClient())
    assert m2.queue == [d, b, c]


def test_abort_then_next_task_starts(cfg, tmp_path):
    cfg.data["max_parallel"] = 1
    client = FakeClient([FakeAPIError(500)] * 5 + [finish()])
    m = make(cfg, tmp_path, client)
    m.effective_parallel = 1
    a = m.add_task("Kaputt", "x")
    b = m.add_task("Gut", "y")
    m.tick()
    wait_idle(m)
    assert m.tasks[a]["status"] == "fehler"
    assert "500" in m.tasks[a]["last_error"]
    assert m.tasks[b]["status"] in ("fertig", "schwach")
    assert m.queue == []
    # Workspace bleibt erhalten, Fortsetzen möglich
    assert os.path.isdir(os.path.join(m.ws_dir, a))
    client.script = [finish()]
    assert m.resume(a)
    assert m.queue == [a]
    m.tick()
    wait_idle(m)
    assert m.tasks[a]["status"] in ("fertig", "schwach")
    first = client.requests[-1]["messages"]
    assert any("FORTSETZUNG" in (x.get("content") or "") for x in first)


def test_auth_error_blocks_new_tasks(cfg, tmp_path):
    cfg.data["max_parallel"] = 1
    client = FakeClient([FakeAPIError(401, "bad key")], default=finish())
    m = make(cfg, tmp_path, client)
    m.effective_parallel = 1
    a = m.add_task("A", "x")
    b = m.add_task("B", "y")
    m.tick()
    wait_idle(m)
    assert m.tasks[a]["status"] == "fehler"
    assert "bad key" in m.auth_error
    m.tick()
    assert m.tasks[b]["status"] == "wartet" and m.queue == [b]
    assert m.snapshot()["auth_error"]
    m.settings_changed(["api_key"])
    m.tick()
    wait_idle(m)
    assert m.tasks[b]["status"] in ("fertig", "schwach")


def test_throttle_down_and_recover(cfg, tmp_path, clock):
    m = make(cfg, tmp_path, FakeClient(), clock=clock)
    assert m.effective_parallel == 4
    for _ in range(3):
        m.record_error()
        clock.advance(60)
    m.tick()
    assert m.effective_parallel == 3
    assert "Gedrosselt" in m.snapshot()["throttle_note"]
    # Fehler verteilt über > 10 min zählen nicht
    for i in range(3):
        if i:
            clock.advance(400)
        m.record_error()
    m.tick()
    assert m.effective_parallel == 3
    clock.advance(29 * 60)
    m.tick()
    assert m.effective_parallel == 3
    clock.advance(61)
    m.tick()
    assert m.effective_parallel == 4
    clock.advance(10 * 3600)
    m.tick()
    assert m.effective_parallel == 4  # nicht über das Maximum


def test_throttle_never_below_one(cfg, tmp_path, clock):
    cfg.data["max_parallel"] = 1
    m = make(cfg, tmp_path, FakeClient(), clock=clock)
    for _ in range(6):
        m.record_error()
    m.tick()
    assert m.effective_parallel == 1


def test_parallel_limit_respected(cfg, tmp_path):
    cfg.data["max_parallel"] = 2
    m = make(cfg, tmp_path, FakeClient(default=tool("bash", command="sleep 0.3")))
    m.effective_parallel = 2
    ids = [m.add_task(f"T{i}", "x") for i in range(4)]
    m.tick()
    assert len(m.agents) == 2 and len(m.queue) == 2
    for i in ids:
        m.stop(i)
    wait_idle(m)
    statuses = sorted(m.tasks[i]["status"] for i in ids)
    assert statuses == ["gestoppt"] * 4


def test_weak_marking_and_history(cfg, tmp_path):
    m = make(cfg, tmp_path, FakeClient([finish()]))
    a = m.add_task("Mini", "x", topic="crypto")
    m.tick()
    wait_idle(m)
    assert m.tasks[a]["status"] == "schwach" and m.tasks[a]["weak"]
    hist = json.load(open(m.history_path))
    assert hist[-1]["weak"] and hist[-1]["topic"] == "crypto"


def test_not_weak_with_tool_calls_and_green_suite(cfg, tmp_path):
    cfg.data["weak_min_tool_calls"] = 3
    script = [tool("write_file", path="test_a.py", content="def test_a():\n    pass\n"),
              tool("bash", command="python3 -m pytest -q -p no:cacheprovider"),
              finish()]
    m = make(cfg, tmp_path, FakeClient(script))
    a = m.add_task("Echt", "x")
    m.tick()
    wait_idle(m)
    assert m.tasks[a]["status"] == "fertig" and not m.tasks[a]["weak"]


def test_endless_mode_generates_new_task(cfg, tmp_path):
    cfg.data["endless_mode"] = True

    def answer(kwargs):
        if "tools" not in kwargs:
            return resp(content=GEN_TEXT)
        return finish()
    client = FakeClient(default=answer)
    m = make(cfg, tmp_path, client)
    m.tick()
    end = time.time() + 10
    while time.time() < end and not m.tasks:
        time.sleep(0.02)
    wait_idle(m)
    t = next(iter(m.tasks.values()))
    assert t["title"] == "Raytracer mit BVH" and t["source"] == "generiert"
    assert t["status"] in ("fertig", "schwach")
    gen_req = [r for r in client.requests if "tools" not in r][0]
    assert "BEREITS VORHANDENE PROJEKTE" in gen_req["messages"][1]["content"]
    assert m.totals()["calls"] >= 2


def test_endless_off_no_generation(cfg, tmp_path):
    client = FakeClient()
    m = make(cfg, tmp_path, client)
    m.tick()
    assert not m.generating and client.requests == []


def test_interrupted_tasks_resume_after_restart(cfg, tmp_path):
    m = make(cfg, tmp_path, FakeClient(default=tool("bash", command="sleep 0.2")))
    a = m.add_task("Lang", "x")
    b = m.add_task("Wartend", "y")
    m.effective_parallel = 1
    m.tick()
    time.sleep(0.3)
    m.shutdown(timeout=10)
    assert m.tasks[a]["status"] == "wartet" and m.tasks[a]["resume"]
    assert m.queue[0] == a
    st = json.load(open(m.state_path))
    st["tasks"][a]["status"] = "läuft"  # harter Absturz simulieren
    st["queue"] = [b]
    json.dump(st, open(m.state_path, "w"))
    m2 = make(cfg, tmp_path, FakeClient())
    assert m2.queue == [a, b] and m2.tasks[a]["resume"]


def test_restart_resets_workspace(cfg, tmp_path):
    m = make(cfg, tmp_path, FakeClient([tool("write_file", path="x.txt", content="1"),
                                        finish()]))
    a = m.add_task("R", "x")
    m.tick()
    wait_idle(m)
    assert os.path.exists(os.path.join(m.ws_dir, a, "x.txt"))
    m.paused = True
    assert m.restart(a)
    assert not os.path.exists(os.path.join(m.ws_dir, a))
    assert m.queue == [a] and m.tasks[a]["stats"] == {} and not m.tasks[a]["resume"]


def test_archive_finished(cfg, tmp_path):
    cfg.data["archive_finished"] = True
    m = make(cfg, tmp_path, FakeClient([tool("write_file", path="x.txt", content="1"),
                                        finish()]))
    a = m.add_task("Arch", "x")
    m.tick()
    wait_idle(m)
    time.sleep(0.2)
    assert os.path.exists(os.path.join(cfg.path_of("archive_dir"), f"{a}.tar.gz"))
    assert not os.path.exists(os.path.join(m.ws_dir, a))


def test_snapshot_totals_and_rate(cfg, tmp_path, clock):
    client = FakeClient([resp(calls=[("bash", {"command": "true"})], prompt=1_000_000,
                              completion=100_000), finish()])
    m = make(cfg, tmp_path, client, clock=clock)
    m.tick()  # erste Kosten-Stichprobe bei 0
    a = m.add_task("Kosten", "x")
    m.tick()
    wait_idle(m)
    clock.advance(1800)
    snap = m.snapshot()
    assert snap["totals"]["prompt_tokens"] == 1_001_000
    cost = snap["totals"]["cost_usd"]
    assert abs(snap["rate_per_hour"] - cost * 2) < 1e-6
    assert abs(snap["projection_24h"] - cost * 48) < 1e-6
    assert snap["tasks"][0]["id"] == a


def test_missing_config_blocks_start(cfg, tmp_path):
    cfg.data["api_key"] = ""
    client = FakeClient()
    m = make(cfg, tmp_path, client)
    m.add_task("A", "x")
    m.tick()
    assert not m.agents and "API-Key" in m.snapshot()["config_problem"]


def test_generated_task_swarm_mode(cfg, tmp_path):
    cfg.data["endless_mode"] = True
    cfg.data["swarm_ratio"] = 1.0
    started = []

    def answer(kwargs):
        if "tools" not in kwargs:
            return resp(content=GEN_TEXT)
        started.append(kwargs["messages"][0]["content"])
        return finish()
    m = make(cfg, tmp_path, FakeClient(default=answer))
    m.tick()
    end = time.time() + 10
    while time.time() < end and not started:
        time.sleep(0.02)
    m.cfg.data["endless_mode"] = False
    wait_idle(m)
    t = next(iter(m.tasks.values()))
    assert t["mode"] == "swarm"
    assert "SCHWARM-KOORDINATOR" in started[0]


def test_snapshot_shows_live_subagents(cfg, tmp_path):
    import threading as th
    go = th.Event()
    instr = "Implementiere das Modul vollständig inklusive Tests."

    def brain(kw):
        sysmsg = kw["messages"][0]["content"]
        n = sum(1 for x in kw["messages"] if x["role"] == "tool")
        if "Subagent in einem autonomen" in sysmsg:
            if n == 0:
                return tool("bash", command="true")
            go.wait(5)
            return finish()
        if n == 0:
            return resp(calls=[("subagent", {"name": "helfer", "instructions": instr})])
        return finish()
    m = make(cfg, tmp_path, FakeClient(default=brain))
    a = m.add_task("Mit Helfer", "x", mode="swarm")
    m.tick()
    end = time.time() + 5
    snap = None
    while time.time() < end:
        snap = m.snapshot()
        live = snap["tasks"][0]["subagents_live"]
        if live and live[0]["calls"] >= 1:
            break
        time.sleep(0.02)
    task = snap["tasks"][0]
    assert task["mode"] == "swarm"
    assert task["subagents_live"][0]["name"] == "helfer"
    assert task["stats"]["calls"] >= 2   # Hauptagent + laufender Subagent
    go.set()
    wait_idle(m)
    assert m.tasks[a]["stats"]["subagents"] == 1


def test_client_creation_failure_does_not_hang(cfg, tmp_path):
    import threading as th

    def broken(c):
        raise ImportError("No module named 'httpx'")
    (tmp_path / "t2").mkdir()
    m = Manager(cfg, client_factory=broken, tasks_dir=str(tmp_path / "t2"))
    a = m.add_task("A", "x")
    t = th.Thread(target=m.tick)
    t.start()
    t.join(3)
    assert not t.is_alive()                     # keine Endlosschleife
    assert "httpx" in m.auth_error and m.queue == [a]
    cfg.data["endless_mode"] = True
    m.queue.clear()
    m.auth_error = ""
    m.tick()
    assert not m.generating and "httpx" in m.auth_error


def test_task_front_matter_and_incremental_builtin_load(cfg, tmp_path):
    tdir = tmp_path / "tasks_fm"
    tdir.mkdir()
    (tdir / "1_sql.md").write_text("# SQL\nText A")
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    assert len(m.tasks) == 1
    (tdir / "2_neu.md").write_text("---\nspec_docs: false\nmode: swarm\ntopic: crypto\n---\n"
                                   "# Neue Aufgabe\nText B")
    (tdir / "10_zehn.md").write_text("# Zehn\nText C")
    m2 = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    titles = [m2.tasks[i]["title"] for i in m2.queue]
    assert titles == ["SQL", "Neue Aufgabe", "Zehn"]        # numerisch sortiert, nichts doppelt
    neu = next(t for t in m2.tasks.values() if t["title"] == "Neue Aufgabe")
    assert neu["spec_docs"] is False and neu["mode"] == "swarm" and neu["topic"] == "crypto"
    assert m2.get_prompt(neu["id"]) == "Text B"
    m3 = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    assert len(m3.tasks) == 3


def test_old_state_without_builtin_list(cfg, tmp_path):
    tdir = tmp_path / "tasks_old"
    tdir.mkdir()
    (tdir / "1_a.md").write_text("# Alt\nx")
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    st = json.load(open(m.state_path))
    del st["builtin_loaded"]                      # Zustand einer älteren Version
    json.dump(st, open(m.state_path, "w"))
    (tdir / "2_b.md").write_text("# Neu\ny")
    m2 = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tdir))
    assert sorted(t["title"] for t in m2.tasks.values()) == ["Alt", "Neu"]


def test_per_task_spec_docs_override(cfg, tmp_path):
    cfg.data["spec_docs"] = True

    def brain(kw):
        if "tools" not in kw:
            return resp(content="# DOC\n" + "x " * 50)
        return finish()
    client = FakeClient(default=brain)
    m = make(cfg, tmp_path, client)
    a = m.add_task("Ohne", "x", spec_docs=False)
    m.tick()
    wait_idle(m)
    assert not [r for r in client.requests if "tools" not in r]
    assert not os.path.exists(os.path.join(m.ws_dir, a, "docs"))
    cfg.data["spec_docs"] = False
    b = m.add_task("Mit", "y", spec_docs=True)
    m.tick()
    wait_idle(m)
    assert os.path.exists(os.path.join(m.ws_dir, b, "docs", "SPEC.md"))
