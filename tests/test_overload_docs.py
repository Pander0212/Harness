import os
import threading
from types import SimpleNamespace as NS

from agent import Agent, classify_error
from fakes import FakeAPIError, FakeClient, resp, tool

BUSY = "evolve-beta is busy please try again in a few seconds"
TASK = {"id": "t1", "title": "Mini-DB", "prompt": "Baue eine kleine Datenbank."}


def make(cfg, client, sleeps, task=TASK):
    ws = os.path.join(cfg.path_of("workspaces_dir"), task["id"])
    dd = os.path.join(cfg.path_of("data_dir"), "tasks", task["id"])
    return Agent(task, cfg, client, ws, dd, sleep=sleeps.append)


def finish():
    return tool("finish", summary="ok")


# ------------------------------------------------------------ Überlastung

def test_overload_classification():
    assert classify_error(FakeAPIError(503, "x")) == "overloaded"
    assert classify_error(FakeAPIError(529, "x")) == "overloaded"
    assert classify_error(FakeAPIError(429, "x")) == "overloaded"
    assert classify_error(FakeAPIError(500, BUSY)) == "overloaded"
    assert classify_error(FakeAPIError(500, "internal")) == "retry"
    assert classify_error(FakeAPIError(401, BUSY)) == "auth"


def test_overload_retries_forever(cfg, sleeps):
    cfg.data.update(retry_overloaded_forever=True, overload_delay=5)
    client = FakeClient([FakeAPIError(503, BUSY)] * 40 + [finish()])
    a = make(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"      # max_retries=4 greift nicht
    assert sleeps == [5] * 40
    assert a.stats["overload_waits"] == 40


def test_busy_as_answer_text_is_retried(cfg, sleeps):
    cfg.data.update(retry_overloaded_forever=True, overload_delay=5)
    client = FakeClient([resp(content=BUSY)] * 6 + [finish()])
    a = make(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"      # nicht als "Antwort ohne Tool" gezählt
    sent = client.requests[-1]["messages"]
    assert not any(BUSY in (m.get("content") or "") for m in sent)


def test_busy_in_error_body(cfg, sleeps):
    cfg.data.update(retry_overloaded_forever=True)
    client = FakeClient([NS(choices=[], usage=None, error={"message": BUSY})] * 8 + [finish()])
    assert make(cfg, client, sleeps).run()["outcome"] == "finished"


def test_normal_text_not_mistaken_for_busy(cfg, sleeps):
    cfg.data.update(retry_overloaded_forever=True)
    text = "Ich passe den Parser an und versuche es dann erneut mit den Tests."
    client = FakeClient([resp(content=text), finish()])
    a = make(cfg, client, sleeps)
    a.run()
    assert a.stats["overload_waits"] == 0


def test_stop_ends_overload_loop(cfg):
    cfg.data.update(retry_overloaded_forever=True, overload_delay=0.05)
    client = FakeClient(default=FakeAPIError(503, BUSY))
    a = make(cfg, client, [])
    a.sleep = lambda s: a.stop_event.wait(s)
    th = threading.Thread(target=lambda: setattr(a, "out", a.run()))
    th.start()
    while len(client.requests) < 3:
        pass
    a.stop()
    th.join(5)
    assert a.out["outcome"] == "stopped"


def test_jitter_range(cfg, sleeps):
    cfg.data.update(retry_overloaded_forever=True, overload_delay=5, retry_jitter=0.2)
    client = FakeClient([FakeAPIError(503, BUSY)] * 50 + [finish()])
    make(cfg, client, sleeps).run()
    assert all(4.0 <= s <= 6.0 for s in sleeps) and len(set(sleeps)) > 1


# ------------------------------------------------------------ Spezifikation

SPEC = "# SPEC\n" + "Spezifikationstext " * 50
PLAN = "# TESTPLAN\n" + "Testfall " * 50


def doc_brain(kw):
    if "tools" not in kw:
        last = kw["messages"][-1]["content"]
        return resp(content=PLAN if "test catalog" in last else SPEC)
    return finish()


def test_docs_generated_and_referenced(cfg, sleeps):
    cfg.data["spec_docs"] = True
    client = FakeClient(default=doc_brain)
    a = make(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    d = os.path.join(a.workspace, "docs")
    assert open(os.path.join(d, "SPEC.md")).read().startswith("# SPEC")
    assert open(os.path.join(d, "TESTPLAN.md")).read().startswith("# TESTPLAN")
    plan_req = [r for r in client.requests if "tools" not in r][1]
    assert any(m["role"] == "assistant" and m["content"].startswith("# SPEC")
               for m in plan_req["messages"])        # SPEC im Kontext des Testplans
    first = [r for r in client.requests if "tools" in r][0]["messages"]
    assert "docs/SPEC.md" in first[-1]["content"]
    assert a.stats["calls"] == 3                       # 2 Dokumente + 1 Arbeitsschritt


def test_docs_long_output_is_continued_and_joined(cfg, sleeps):
    cfg.data["spec_docs"] = True
    script = [resp(content="# SPEC\nTeil eins, ", finish_reason="length"),
              resp(content="Teil zwei."), resp(content=PLAN), finish()]
    client = FakeClient(script)
    a = make(cfg, client, sleeps)
    a.run()
    spec = open(os.path.join(a.workspace, "docs", "SPEC.md")).read()
    assert spec.strip() == "# SPEC\nTeil eins, Teil zwei."
    assert client.requests[1]["messages"][-1] == {"role": "user", "content": "continue"}


def test_docs_not_regenerated_on_resume(cfg, sleeps):
    cfg.data["spec_docs"] = True
    a = make(cfg, FakeClient(default=doc_brain), sleeps)
    a.run()
    client = FakeClient([finish()])
    b = make(cfg, client, sleeps)
    b.run()
    assert len(client.requests) == 1
    assert "docs/SPEC.md" in client.requests[0]["messages"][-1]["content"]


def test_docs_failure_does_not_stop_task(cfg, sleeps):
    cfg.data["spec_docs"] = True
    client = FakeClient([FakeAPIError(500)] * 5 + [finish()])
    a = make(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    assert not a.docs_exist()
