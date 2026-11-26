import json
import os
import threading
from types import SimpleNamespace as NS

import agent as agent_mod
from agent import Agent
from fakes import FakeAPIError, FakeClient, tool


def chunk(content=None, calls=None, finish=None, usage=None):
    delta = NS(content=content, tool_calls=calls, refusal=None)
    choices = [NS(delta=delta, finish_reason=finish)] if (content or calls or finish) else []
    return NS(choices=choices, usage=usage)


def tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


def finish_stream():
    args = json.dumps({"summary": "fertig"})
    return iter([chunk(calls=[tc(0, "c1", "finish", args[:5])]),
                 chunk(calls=[tc(0, None, None, args[5:])]),
                 chunk(finish="tool_calls"),
                 chunk(usage=NS(prompt_tokens=5000, completion_tokens=40,
                                prompt_tokens_details=NS(cached_tokens=4000)))])


def make(cfg, client, task_id="s1"):
    cfg.data["stream"] = True
    task = {"id": task_id, "title": "T", "prompt": "x"}
    ws = os.path.join(cfg.path_of("workspaces_dir"), task_id)
    dd = os.path.join(cfg.path_of("data_dir"), "tasks", task_id)
    return Agent(task, cfg, client, ws, dd, sleep=lambda s: None)


def test_stream_assembles_tool_calls_and_usage(cfg):
    agent_mod.STREAM_OPTIONS["ok"] = True
    client = FakeClient([finish_stream()])
    a = make(cfg, client)
    assert a.run()["outcome"] == "finished"
    req = client.requests[0]
    assert req["stream"] is True and req["stream_options"] == {"include_usage": True}
    assert a.stats["prompt_tokens"] == 5000 and a.stats["cached_tokens"] == 4000
    assert a.stats["completion_tokens"] == 40


def test_stream_text_and_multiple_calls(cfg):
    stream = iter([chunk(content="Ich lege "), chunk(content="die Dateien an."),
                   chunk(calls=[tc(0, "a", "write_file", '{"path": "a.txt", "content": "1"}'),
                                tc(1, "b", "write_file", '{"path": "b.txt", ')]),
                   chunk(calls=[tc(1, None, None, '"content": "2"}')]),
                   chunk(finish="tool_calls")])
    client = FakeClient([stream, finish_stream()])
    a = make(cfg, client)
    a.run()
    assert open(os.path.join(a.workspace, "a.txt")).read() == "1"
    assert open(os.path.join(a.workspace, "b.txt")).read() == "2"
    msgs = client.requests[1]["messages"]
    assist = [m for m in msgs if m["role"] == "assistant"][0]
    assert assist["content"] == "Ich lege die Dateien an."
    assert [c["id"] for c in assist["tool_calls"]] == ["a", "b"]
    assert a.stats["completion_tokens"] > 0       # ohne usage geschätzt


def test_stream_options_fallback(cfg):
    agent_mod.STREAM_OPTIONS["ok"] = True

    def picky(kwargs):
        if "stream_options" in kwargs:
            return FakeAPIError(400, "unknown parameter: stream_options")
        return finish_stream()
    client = FakeClient(default=picky)
    a = make(cfg, client)
    assert a.run()["outcome"] == "finished"
    assert agent_mod.STREAM_OPTIONS["ok"] is False
    assert a.stats["retries"] == 0
    agent_mod.STREAM_OPTIONS["ok"] = True


def test_stream_broken_midway_continues(cfg):
    def broken():
        yield chunk(content="# SPEC\nTeil eins ")
        raise ConnectionError("connection reset")
    client = FakeClient([broken(), finish_stream()])
    a = make(cfg, client)
    a.run()
    msgs = client.requests[1]["messages"]
    assert msgs[-2] == {"role": "assistant", "content": "# SPEC\nTeil eins "}
    assert msgs[-1] == {"role": "user", "content": "continue"}
    assert a.stats["calls"] == 2 and a.stats["completion_tokens"] > 40


def test_stream_stall_is_retried_as_overload(cfg):
    cfg.data["retry_overloaded_forever"] = True

    class APITimeoutError(Exception):
        pass
    client = FakeClient([APITimeoutError("Request timed out.")] * 12 + [finish_stream()])
    a = make(cfg, client)
    assert a.run()["outcome"] == "finished"
    assert a.stats["overload_waits"] == 12


def test_live_request_status(cfg):
    gate = threading.Event()
    seen = {}

    def slow():
        yield chunk(content="x" * 3500)
        gate.wait(5)
        yield chunk(content="fertig")
        yield chunk(finish="stop")
    client = FakeClient([slow()], default=tool("finish", summary="ok"))
    a = make(cfg, client)
    a.cfg.data["max_no_tool_replies"] = 1
    th = threading.Thread(target=a.run)
    th.start()
    for _ in range(500):
        st = a.request_status()
        if st and st["tokens"] >= 1000:
            seen = st
            break
        threading.Event().wait(0.01)
    gate.set()
    th.join(5)
    assert seen["label"] == "Antwort" and seen["tokens"] == 1000
    assert a.request_status() is None


def test_throttle_reset(cfg, tmp_path):
    from manager import Manager
    (tmp_path / "t").mkdir()
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tmp_path / "t"))
    m.effective_parallel = 1
    m.throttle_note = "Gedrosselt"
    m.reset_throttle()
    assert m.effective_parallel == 4 and m.throttle_note == ""


def test_tool_progress_phase_shown(cfg):
    seen = {}
    gate = threading.Event()

    def buffered():
        yield chunk()
        yield NS(choices=[NS(delta=NS(content=None, tool_calls=None, refusal=None),
                             finish_reason=None)], usage=None,
                 x_nanogpt_tool_progress={"status": "preparing"})
        gate.wait(5)
        yield from finish_stream()
    client = FakeClient([buffered()])
    a = make(cfg, client)
    th = threading.Thread(target=a.run)
    th.start()
    for _ in range(500):
        st = a.request_status()
        if st and st.get("phase"):
            seen = st
            break
        threading.Event().wait(0.01)
    gate.set()
    th.join(5)
    assert seen["phase"] == "preparing"


def test_stall_timeout_setting(cfg):
    assert cfg.update({"stall_timeout": 5}) == ["stall_timeout"] and cfg["stall_timeout"] == 30
