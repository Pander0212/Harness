import json
import os

import pytest

from agent import Agent, classify_error
from fakes import FakeAPIError, FakeClient, FakeTimeout, resp, tool

TASK = {"id": "t1", "title": "Testaufgabe", "prompt": "Baue etwas."}


def make_agent(cfg, client, sleeps, clock=None, resume=False, task=TASK):
    kw = {}
    if clock:
        kw["clock"] = clock
    ws = os.path.join(cfg.path_of("workspaces_dir"), task["id"])
    dd = os.path.join(cfg.path_of("data_dir"), "tasks", task["id"])
    return Agent(task, cfg, client, ws, dd, resume=resume, sleep=sleeps.append, **kw)


def finish():
    return tool("finish", summary="fertig")


# ------------------------------------------------------------ Fehlerbehandlung

def test_retry_then_success_uses_backoff(cfg, sleeps):
    client = FakeClient([FakeAPIError(500), FakeAPIError(429), FakeTimeout("timeout"),
                         finish()])
    a = make_agent(cfg, client, sleeps)
    out = a.run()
    assert out["outcome"] == "finished"
    assert sleeps == [10, 20, 40]
    assert a.stats["retries"] == 3
    # Anfrage wurde identisch erneut gesendet
    assert client.requests[0]["messages"] == client.requests[3]["messages"]


def test_four_retries_then_success(cfg, sleeps):
    client = FakeClient([FakeAPIError(502)] * 4 + [finish()])
    out = make_agent(cfg, client, sleeps).run()
    assert out["outcome"] == "finished"
    assert sleeps == [10, 20, 40, 60]


def test_gives_up_after_four_retries(cfg, sleeps):
    client = FakeClient([FakeAPIError(503, "down")] * 5 + [finish()])
    a = make_agent(cfg, client, sleeps)
    out = a.run()
    assert out["outcome"] == "error"
    assert "503" in out["message"]
    assert len(client.requests) == 5
    assert sleeps == [10, 20, 40, 60]
    assert "503" in json.load(open(a.stats_path))["last_error"]


def test_incomplete_response_appends_continue(cfg, sleeps):
    client = FakeClient([resp(content="Ich schreibe jetzt den Pars", finish_reason="length"),
                         finish()])
    out = make_agent(cfg, client, sleeps).run()
    assert out["outcome"] == "finished"
    msgs = client.requests[1]["messages"]
    assert msgs[-2] == {"role": "assistant", "content": "Ich schreibe jetzt den Pars"}
    assert msgs[-1] == {"role": "user", "content": "continue"}
    assert sleeps == [10]


def test_empty_and_refused_responses_are_retried(cfg, sleeps):
    refused = resp(content="", finish_reason="content_filter")
    client = FakeClient([resp(content=""), refused, finish()])
    a = make_agent(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    assert a.stats["retries"] == 2


def test_no_choices_is_retried(cfg, sleeps):
    from types import SimpleNamespace as NS
    client = FakeClient([NS(choices=[], usage=None, error={"message": "x"}), finish()])
    assert make_agent(cfg, client, sleeps).run()["outcome"] == "finished"


def test_auth_error_aborts_immediately(cfg, sleeps):
    client = FakeClient([FakeAPIError(401, "invalid key"), finish()])
    out = make_agent(cfg, client, sleeps).run()
    assert out["outcome"] == "auth"
    assert len(client.requests) == 1
    assert sleeps == []


def test_context_error_compresses_then_retries(cfg, sleeps):
    ctx_err = FakeAPIError(400, "This model's maximum context length is 200000 tokens")
    client = FakeClient([tool("bash", command="echo hi"), ctx_err,
                         resp(content="ZUSAMMENFASSUNG: alles gut"), finish()])
    a = make_agent(cfg, client, sleeps)
    out = a.run()
    assert out["outcome"] == "finished"
    assert a.stats["compressions"] == 1
    last = client.requests[-1]["messages"]
    assert "ZUSAMMENFASSUNG: alles gut" in last[-1]["content"]
    assert len(last) == 3  # system, aufgabe, zusammenfassung
    assert sleeps == []


def test_classify_error():
    assert classify_error(FakeAPIError(403)) == "auth"
    assert classify_error(FakeAPIError(413, "payload")) == "context"
    assert classify_error(FakeAPIError(400, "too many tokens")) == "context"
    assert classify_error(FakeAPIError(400, "bad tool schema")) == "retry"
    assert classify_error(FakeAPIError(500)) == "retry"
    assert classify_error(ConnectionError("reset")) == "retry"


# ------------------------------------------------------------ Schleife

def test_tool_loop_writes_and_reads_files(cfg, sleeps):
    client = FakeClient([
        tool("write_file", path="sub/a.txt", content="hallo"),
        tool("read_file", path="sub/a.txt"),
        tool("list_dir", path=".", recursive=True),
        tool("bash", command="cat sub/a.txt && echo ok"),
        finish()])
    a = make_agent(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    tool_msgs = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    assert "Bytes" in tool_msgs[0]["content"]
    assert tool_msgs[1]["content"] == "hallo"
    assert "a.txt" in tool_msgs[2]["content"]
    assert "exit_code=0" in tool_msgs[3]["content"] and "hallook" in tool_msgs[3]["content"]
    assert a.stats["tool_calls"] == 5


def test_stops_after_four_replies_without_tool(cfg, sleeps):
    client = FakeClient(default=resp(content="Ich denke nach."))
    out = make_agent(cfg, client, sleeps).run()
    assert out["outcome"] == "no_tool"
    assert len(client.requests) == 4


def test_no_tool_streak_resets(cfg, sleeps):
    talk = resp(content="hm")
    client = FakeClient([talk, talk, talk, tool("bash", command="true"), talk, talk, talk,
                         finish()])
    assert make_agent(cfg, client, sleeps).run()["outcome"] == "finished"


def test_max_hours(cfg, sleeps, clock):
    cfg.data["max_hours"] = 1

    def slow(kwargs):
        clock.advance(1800)
        return tool("bash", command="true")
    client = FakeClient(default=slow)
    out = make_agent(cfg, client, sleeps, clock=clock).run()
    assert out["outcome"] == "max_hours"
    assert len(client.requests) == 2


def test_invalid_json_arguments(cfg, sleeps):
    client = FakeClient([resp(calls=[("bash", "{kaputt")]), finish()])
    make_agent(cfg, client, sleeps).run()
    tool_msg = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][0]
    assert "ungültige JSON" in tool_msg["content"]


def test_tool_output_truncated(cfg, sleeps):
    client = FakeClient([tool("bash", command="python3 -c \"print('x'*40000)\""), finish()])
    make_agent(cfg, client, sleeps).run()
    tool_msg = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][0]
    assert len(tool_msg["content"]) <= 15000
    assert "gekürzt" in tool_msg["content"]


def test_bash_timeout(cfg, sleeps):
    client = FakeClient([tool("bash", command="sleep 30", timeout=1), finish()])
    make_agent(cfg, client, sleeps).run()
    tool_msg = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][0]
    assert "TIMEOUT" in tool_msg["content"]


def test_path_guard_in_tools(cfg, sleeps, tmp_path):
    outside = tmp_path / "geheim.txt"
    outside.write_text("secret")
    client = FakeClient([tool("read_file", path=str(outside)),
                         tool("write_file", path="../../geheim2.txt", content="x"),
                         finish()])
    make_agent(cfg, client, sleeps).run()
    tool_msgs = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    assert "verweigert" in tool_msgs[0]["content"]
    assert "verweigert" in tool_msgs[1]["content"]
    assert not (tmp_path / "geheim2.txt").exists()


# ------------------------------------------------------------ Statistik / Logs

def test_stats_and_jsonl(cfg, sleeps):
    client = FakeClient([resp(calls=[("bash", {"command": "true"})], prompt=2_000_000,
                              completion=1_000_000, cached=500_000), finish()])
    a = make_agent(cfg, client, sleeps)
    a.run()
    st = json.load(open(a.stats_path))
    assert st["prompt_tokens"] == 2_001_000
    assert st["cached_tokens"] == 500_000
    assert st["completion_tokens"] == 1_000_100
    assert st["calls"] == 2
    expected = (2_001_000 * 0.135 + 1_000_100 * 2.25) / 1e6
    assert abs(st["cost_usd"] - expected) < 1e-9
    lines = [json.loads(x) for x in open(os.path.join(a.data_dir, "conversation.jsonl"))]
    kinds = {x["type"] for x in lines}
    assert {"message", "usage", "end"} <= kinds
    assert any(x["type"] == "message" and x["message"]["role"] == "tool" for x in lines)


def test_green_suite_detection(cfg, sleeps):
    code = "def test_a():\n    assert 1 + 1 == 2\n"
    client = FakeClient([tool("write_file", path="test_x.py", content=code),
                         tool("bash", command="python3 -m pytest -q -p no:cacheprovider"),
                         finish()])
    a = make_agent(cfg, client, sleeps)
    a.run()
    assert a.stats["green_suites"] == 1


# ------------------------------------------------------------ Komprimierung

def test_compression_at_threshold(cfg, sleeps):
    cfg.data["compress_at"] = 5000
    client = FakeClient([
        resp(calls=[("write_file", {"path": "PROGRESS.md", "content": "- [x] Lexer\n- [ ] Parser"})],
             prompt=6000),
        resp(content="Zusammenfassung: Lexer fertig, Parser offen."),
        finish()])
    a = make_agent(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    assert a.stats["compressions"] == 1
    # Zusammenfassungs-Anfrage enthält den Verlauf + Aufforderung
    assert "KONTEXT-KOMPRIMIERUNG" in client.requests[1]["messages"][-1]["content"]
    new = client.requests[2]["messages"]
    assert len(new) == 3
    assert new[1]["content"].startswith("# Aufgabe: Testaufgabe")
    body = new[2]["content"]
    assert "Lexer fertig, Parser offen" in body
    assert "- [ ] Parser" in body          # PROGRESS.md neu eingelesen
    assert "PROGRESS.md" in body


def test_compression_fallback_when_summary_too_long(cfg, sleeps):
    cfg.data["compress_at"] = 5000
    client = FakeClient([
        resp(calls=[("bash", {"command": "true"})], prompt=6000),
        FakeAPIError(400, "context length exceeded"),
        resp(content="Kurzfassung"),
        finish()])
    a = make_agent(cfg, client, sleeps)
    assert a.run()["outcome"] == "finished"
    fallback = client.requests[2]
    assert "tools" not in fallback
    assert "Verlauf (gekürzt)" in fallback["messages"][1]["content"]


# ------------------------------------------------------------ Fortsetzen / finish

def test_resume_reads_progress(cfg, sleeps):
    ws = os.path.join(cfg.path_of("workspaces_dir"), "t1")
    os.makedirs(ws)
    open(os.path.join(ws, "PROGRESS.md"), "w").write("- [x] Schritt 1\n- [ ] Schritt 2")
    client = FakeClient([finish()])
    make_agent(cfg, client, sleeps, resume=True).run()
    first = client.requests[0]["messages"]
    assert "FORTSETZUNG" in first[2]["content"]
    assert "Schritt 2" in first[2]["content"]


def test_finish_rejected_when_tests_fail(cfg, sleeps):
    cfg.data["verify_on_finish"] = True
    bad = "def test_a():\n    assert False\n"
    good = "def test_a():\n    assert True\n"
    client = FakeClient([tool("write_file", path="test_a.py", content=bad), finish(),
                         tool("write_file", path="test_a.py", content=good), finish()])
    a = make_agent(cfg, client, sleeps)
    out = a.run()
    assert out["outcome"] == "finished"
    assert a.stats["finish_rejections"] == 1
    rejected = [m for m in client.requests[2]["messages"] if m["role"] == "tool"][-1]
    assert "ABGELEHNT" in rejected["content"]
    assert len(client.requests) == 4


def test_stop_event(cfg, sleeps):
    client = FakeClient(default=tool("bash", command="true"))
    a = make_agent(cfg, client, sleeps)
    a.stop()
    assert a.run()["outcome"] == "stopped"
