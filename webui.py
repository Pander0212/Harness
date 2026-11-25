"""Web-UI über http.server: eine HTML-Seite + JSON-API."""
import base64
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html")
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class UIServer:
    def __init__(self, manager, host=None, port=None):
        self.m = manager
        cfg = manager.cfg
        self.host = host or cfg["ui_host"]
        self.port = cfg["ui_port"] if port is None else port
        if self.host not in LOCAL_HOSTS and not cfg["ui_password"]:
            raise SystemExit("ui_host ist öffentlich, aber kein ui_password gesetzt – "
                             "Start verweigert. Bitte ui_password in config.json setzen.")
        handler = self._make_handler()
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def serve_background(self):
        th = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="ui")
        th.start()
        return th

    def shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _make_handler(self):
        ui = self
        m = self.m

        class H(BaseHTTPRequestHandler):
            server_version = "Harness/1.0"

            def log_message(self, *a):
                pass

            def _auth_ok(self):
                pw = m.cfg["ui_password"]
                if not pw:
                    return True
                h = self.headers.get("Authorization", "")
                if h.startswith("Basic "):
                    try:
                        user_pw = base64.b64decode(h[6:]).decode("utf-8")
                    except Exception:
                        return False
                    return hmac.compare_digest(user_pw.split(":", 1)[-1], pw)
                return False

            def _send(self, code, body, ctype="application/json; charset=utf-8"):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, ensure_ascii=False)
                if isinstance(body, str):
                    body = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(body)

            def _deny(self):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Harness"')
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                if not self._auth_ok():
                    return self._deny()
                path = self.path.split("?")[0]
                if path in ("/", "/index.html"):
                    with open(HTML_PATH, "rb") as f:
                        return self._send(200, f.read(), "text/html; charset=utf-8")
                if path == "/api/state":
                    return self._send(200, m.snapshot())
                if path.startswith("/api/task/"):
                    tid = path.rsplit("/", 1)[-1]
                    if tid not in m.tasks:
                        return self._send(404, {"error": "unbekannt"})
                    return self._send(200, {"id": tid, "prompt": m.get_prompt(tid)})
                return self._send(404, {"error": "nicht gefunden"})

            def do_POST(self):
                if not self._auth_ok():
                    return self._deny()
                # einfacher CSRF-Schutz: nur per fetch() mit eigenem Header
                if self.headers.get("X-Harness") != "1":
                    return self._send(403, {"error": "fehlender Header"})
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 2_000_000:
                        return self._send(413, {"error": "zu groß"})
                    data = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return self._send(400, {"error": "ungültiges JSON"})
                try:
                    res = ui.action(self.path.split("?")[0], data)
                except (ValueError, TypeError, KeyError) as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200 if res.get("ok", True) else 400, res)

        return H

    def action(self, path, d):
        m = self.m
        tid = d.get("id")
        if path == "/api/task/add":
            prompt = (d.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("Aufgabentext fehlt")
            new = m.add_task(d.get("title") or prompt.splitlines()[0][:60], prompt,
                             topic=d.get("topic", ""), source="manuell",
                             front=bool(d.get("front")), mode=d.get("mode", "single"))
            return {"ok": True, "id": new}
        if path == "/api/task/mode":
            t = m.tasks.get(tid)
            if not t or tid in m.agents:
                return {"ok": False, "error": "nur für nicht laufende Aufgaben"}
            t["mode"] = "swarm" if d.get("mode") == "swarm" else "single"
            m.save()
            return {"ok": True}
        if path == "/api/task/move":
            return {"ok": m.move(tid, d.get("dir", "up"))}
        if path == "/api/task/delete":
            return {"ok": m.delete(tid)}
        if path == "/api/task/start":
            return {"ok": m.start_now(tid)}
        if path == "/api/task/stop":
            return {"ok": m.stop(tid)}
        if path == "/api/task/restart":
            return {"ok": m.restart(tid)}
        if path == "/api/task/resume":
            return {"ok": m.resume(tid)}
        if path == "/api/endless":
            m.set_endless(d.get("on"))
            return {"ok": True}
        if path == "/api/pause":
            m.set_paused(d.get("on"))
            return {"ok": True}
        if path == "/api/throttle_reset":
            m.reset_throttle()
            return {"ok": True}
        if path == "/api/clear_auth":
            m.clear_auth()
            return {"ok": True}
        if path == "/api/settings":
            changed = m.cfg.update(d)
            m.cfg.save()
            m.settings_changed(changed)
            return {"ok": True, "changed": changed}
        return {"ok": False, "error": "unbekannte Aktion"}
