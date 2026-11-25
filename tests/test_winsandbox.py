"""Logik-Tests der Windows-Sandbox (laufen auf jedem System, ohne Windows-API)."""
import os

import pytest

import sandbox
import winsandbox
from fakes import FakeClient
from manager import Manager


@pytest.fixture
def no_labels(monkeypatch):
    monkeypatch.setattr(winsandbox, "prepare_workspace", lambda p, strict: os.makedirs(p, exist_ok=True))


def fake_runner(behaviour):
    """behaviour(level, command) -> (code, out); simuliert die Sandbox."""
    calls = []

    def run(level, command, ws):
        calls.append((level, command))
        return behaviour(level, command, ws)
    return run, calls


def good(level, cmd, ws):
    if cmd.startswith("echo ok"):
        return 0, "ok"
    if "python" in cmd:
        return 0, "42"
    if cmd.startswith("echo x"):
        return 1, "Permission denied"   # Datei wird nicht angelegt
    if cmd.startswith("cat"):
        return 1, "Permission denied"
    if "net session" in cmd:
        return 0, "rc=2"
    if cmd.startswith("ls"):
        return 2, "Permission denied"
    return 1, ""


def test_selftest_strict_ok(tmp_path, no_labels):
    run, calls = fake_runner(good)
    res = winsandbox.selftest(run, str(tmp_path / "ws"), str(tmp_path), str(tmp_path / "c.json"),
                              str(tmp_path / "home"))
    assert res["level"] == "strict" and all(ok for _, ok, _ in res["checks"])
    assert "Benutzerprofil" in res["message"]


def test_selftest_falls_back_to_lowil(tmp_path, no_labels):
    def beh(level, cmd, ws):
        if level == "strict" and "python" in cmd:
            return 1, "python.exe: Zugriff verweigert"
        if level == "lowil" and cmd.startswith("ls"):
            return 0, "Dokumente"
        return good(level, cmd, ws)
    run, _ = fake_runner(beh)
    res = winsandbox.selftest(run, str(tmp_path / "ws"), str(tmp_path), str(tmp_path / "c.json"),
                              str(tmp_path / "home"))
    assert res["level"] == "lowil"


def test_selftest_detects_write_outside(tmp_path, no_labels):
    outside = tmp_path / ".sandbox-probe.txt"

    def beh(level, cmd, ws):
        if cmd.startswith("echo x"):
            outside.write_text("x")      # Sandbox wirkt nicht!
            return 0, ""
        return good(level, cmd, ws)
    run, _ = fake_runner(beh)
    res = winsandbox.selftest(run, str(tmp_path / "ws"), str(tmp_path), str(tmp_path / "c.json"),
                              None)
    assert res["level"] is None
    assert "Schreiben außerhalb blockiert" in res["message"]
    assert not outside.exists()


def test_selftest_detects_readable_config(tmp_path, no_labels):
    def beh(level, cmd, ws):
        if cmd.startswith("cat"):
            return 0, '{"api_key": "geheim"}'
        return good(level, cmd, ws)
    run, _ = fake_runner(beh)
    res = winsandbox.selftest(run, str(tmp_path / "ws"), str(tmp_path), str(tmp_path / "c.json"),
                              None)
    assert res["level"] is None and "config.json" in res["message"]


def test_required_sandbox_blocks_bash(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: (False, "bwrap fehlt"))
    monkeypatch.setattr(sandbox, "IS_WINDOWS", False)
    r = sandbox.BashRunner(str(tmp_path), [str(tmp_path)], mode="auto", require=True)
    code, out, _ = r.run("echo hallo > x.txt")
    assert code == 126 and "deaktiviert" in out
    assert not (tmp_path / "x.txt").exists()


def test_required_sandbox_blocks_scheduler(cfg, tmp_path, monkeypatch):
    import manager as mgr
    monkeypatch.setattr(mgr, "sandbox_status", lambda c: (False, "bwrap fehlt"))
    cfg.data["sandbox"] = "auto"
    (tmp_path / "t").mkdir()
    client = FakeClient()
    m = Manager(cfg, client_factory=lambda c: client, tasks_dir=str(tmp_path / "t"))
    m.add_task("A", "x")
    m.tick()
    assert not m.agents and client.requests == []
    assert "Sandbox nicht verfügbar" in m.snapshot()["config_problem"]
    cfg.data["require_sandbox"] = False
    assert m.config_problem() == ""


def test_bwrap_hides_mounts(tmp_path):
    cmd = " ".join(sandbox.build_bwrap_cmd("true", str(tmp_path), [str(tmp_path)]))
    for h in ("/home", "/root", "/mnt", "/media"):
        if os.path.isdir(h):
            assert f"--tmpfs {h}" in cmd
