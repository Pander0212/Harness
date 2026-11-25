import os

import pytest

from sandbox import BashRunner, PathError, PathGuard, build_bwrap_cmd, truncate


def test_truncate_keeps_head_and_tail():
    text = "A" * 10000 + "MITTE" + "B" * 10000
    out = truncate(text, 15000)
    assert len(out) <= 15000
    assert out.startswith("A" * 100) and out.endswith("B" * 100)
    assert "gekürzt" in out and "MITTE" not in out
    assert truncate("kurz", 15000) == "kurz"


@pytest.fixture
def dirs(tmp_path):
    ws = tmp_path / "ws" / "task"
    ws.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (other / "secret.txt").write_text("x")
    return tmp_path, ws, other


def test_relative_paths_inside(dirs):
    root, ws, _ = dirs
    g = PathGuard([str(root / "ws")], str(ws))
    assert g.resolve("a/b.txt") == os.path.realpath(ws / "a" / "b.txt")


def test_dotdot_escape_blocked(dirs):
    root, ws, _ = dirs
    g = PathGuard([str(ws)], str(ws))
    with pytest.raises(PathError):
        g.resolve("../../other/secret.txt")
    with pytest.raises(PathError):
        g.resolve("/etc/passwd")
    with pytest.raises(PathError):
        g.resolve("")


def test_symlink_escape_blocked(dirs):
    root, ws, other = dirs
    os.symlink(other, ws / "link")
    g = PathGuard([str(ws)], str(ws))
    with pytest.raises(PathError):
        g.resolve("link/secret.txt")


def test_prefix_trick_blocked(dirs):
    root, ws, _ = dirs
    evil = root / "ws" / "task-evil"
    evil.mkdir()
    g = PathGuard([str(ws)], str(ws))
    with pytest.raises(PathError):
        g.resolve(str(evil / "x"))


def test_deny_list(dirs):
    root, ws, _ = dirs
    cfgfile = root / "ws" / "config.json"
    cfgfile.write_text("{}")
    g = PathGuard([str(root / "ws")], str(ws), deny=[str(cfgfile)])
    with pytest.raises(PathError):
        g.resolve(str(cfgfile))


def test_bash_runs_in_workspace(dirs):
    _, ws, _ = dirs
    r = BashRunner(str(ws), [str(ws)], mode="none")
    code, out, to = r.run("pwd; exit 3", timeout=10)
    assert code == 3 and out.strip() == os.path.realpath(ws) and not to
    assert "NICHT abgeschottet" in r.warning


def test_bash_hides_api_key_env(dirs, monkeypatch):
    _, ws, _ = dirs
    monkeypatch.setenv("OPENAI_API_KEY", "geheim")
    r = BashRunner(str(ws), [str(ws)], mode="none")
    _, out, _ = r.run("echo ${OPENAI_API_KEY:-leer}", timeout=10)
    assert out.strip() == "leer"


def test_bash_timeout_kills_children(dirs):
    _, ws, _ = dirs
    r = BashRunner(str(ws), [str(ws)], mode="none")
    code, out, to = r.run("sleep 20 & sleep 20", timeout=1)
    assert to and "TIMEOUT" in out


def test_bwrap_command_layout(tmp_path):
    ws = str(tmp_path / "ws")
    cfgf = tmp_path / "config.json"
    cfgf.write_text("{}")
    cmd = build_bwrap_cmd("ls", ws, [ws], protect_files=[str(cfgf)], network=False)
    s = " ".join(cmd)
    assert cmd[0] == "bwrap" and "--ro-bind / /" in s
    assert f"--bind {ws} {ws}" in s
    assert f"--ro-bind /dev/null {cfgf}" in s
    assert "--unshare-net" in s and cmd[-3:] == ["/bin/bash", "-c", "ls"]
    # versteckte Ordner (tmpfs) kommen vor den beschreibbaren Binds
    if "--tmpfs /home" in s:
        assert s.index("--tmpfs /home") < s.index(f"--bind {ws}")
