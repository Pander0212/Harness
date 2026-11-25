import base64
import json
import time
import urllib.error
import urllib.request

import pytest

from fakes import FakeClient
from manager import Manager
from webui import UIServer


@pytest.fixture
def server(cfg, tmp_path):
    (tmp_path / "t").mkdir()
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tmp_path / "t"))
    m.paused = True
    ui = UIServer(m, host="127.0.0.1", port=0)
    ui.serve_background()
    yield m, ui, f"http://127.0.0.1:{ui.port}"
    ui.shutdown()


def get(url, auth=None):
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode()


def post(url, data, header=True, auth=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if header:
        req.add_header("X-Harness", "1")
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def test_index_and_state(server):
    m, ui, base = server
    code, html = get(base + "/")
    assert code == 200 and "Agent-Harness" in html
    code, body = get(base + "/api/state")
    st = json.loads(body)
    assert st["max_parallel"] == 4 and "totals" in st
    assert st["config"]["api_key"].endswith("test") and "sk-" not in st["config"]["api_key"]


def test_add_move_delete_via_api(server):
    m, ui, base = server
    a = post(base + "/api/task/add", {"title": "Eins", "prompt": "Text 1"})["id"]
    b = post(base + "/api/task/add", {"title": "Zwei", "prompt": "Text 2"})["id"]
    post(base + "/api/task/move", {"id": b, "dir": "up"})
    assert m.queue == [b, a]
    _, body = get(base + f"/api/task/{a}")
    assert json.loads(body)["prompt"] == "Text 1"
    post(base + "/api/task/delete", {"id": a})
    assert m.queue == [b]
    post(base + "/api/endless", {"on": True})
    assert m.cfg["endless_mode"] is True


def test_settings_update(server):
    m, ui, base = server
    r = post(base + "/api/settings", {"model": "neu", "max_parallel": 50,
                                      "api_key": "••••••••test",
                                      "allowed_dirs": "./workspaces\n/srv/x"})
    assert r["ok"]
    assert m.cfg["model"] == "neu"
    assert m.cfg["max_parallel"] == 20          # auf Maximum begrenzt
    assert m.cfg["api_key"] == "sk-test"         # maskierter Key unverändert
    assert m.cfg["allowed_dirs"] == ["./workspaces", "/srv/x"]
    saved = json.load(open(m.cfg.path))
    assert saved["model"] == "neu"


def test_post_requires_header(server):
    m, ui, base = server
    with pytest.raises(urllib.error.HTTPError) as e:
        post(base + "/api/task/add", {"prompt": "x"}, header=False)
    assert e.value.code == 403


def test_public_bind_requires_password(cfg, tmp_path):
    (tmp_path / "t").mkdir()
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tmp_path / "t"))
    with pytest.raises(SystemExit):
        UIServer(m, host="0.0.0.0", port=0)


def test_password_protection(cfg, tmp_path):
    cfg.data["ui_password"] = "pw123"
    (tmp_path / "t").mkdir()
    m = Manager(cfg, client_factory=lambda c: FakeClient(), tasks_dir=str(tmp_path / "t"))
    ui = UIServer(m, host="0.0.0.0", port=0)
    ui.serve_background()
    base = f"http://127.0.0.1:{ui.port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            get(base + "/api/state")
        assert e.value.code == 401
        with pytest.raises(urllib.error.HTTPError):
            get(base + "/api/state", auth="admin:falsch")
        code, _ = get(base + "/api/state", auth="admin:pw123")
        assert code == 200
    finally:
        ui.shutdown()


def test_add_with_mode_and_toggle(server):
    m, ui, base = server
    a = post(base + "/api/task/add", {"title": "S", "prompt": "x", "mode": "swarm"})["id"]
    assert m.tasks[a]["mode"] == "swarm"
    post(base + "/api/task/mode", {"id": a, "mode": "single"})
    assert m.tasks[a]["mode"] == "single"
    r = post(base + "/api/settings", {"max_subagents": 99, "swarm_ratio": 2,
                                      "subagents_enabled": False})
    assert m.cfg["max_subagents"] == 20 and m.cfg["swarm_ratio"] == 1.0
    assert m.cfg["subagents_enabled"] is False
