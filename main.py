"""Einstiegspunkt: startet Scheduler und Web-UI."""
import argparse
import logging
import logging.handlers
import os
import signal
import sys
import threading

import config as config_mod
from config import Config, DEFAULTS
from manager import Manager
from webui import UIServer


def setup_logging(cfg):
    d = cfg.path_of("data_dir")
    os.makedirs(d, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(d, "harness.log"), maxBytes=10 * 1024 * 1024, backupCount=3,
        encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root = logging.getLogger("harness")
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)


def _utf8_console():
    # Windows-Konsole: Sonderzeichen (→, ä) dürfen das Logging nicht stören
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv=None):
    _utf8_console()
    ap = argparse.ArgumentParser(description="Autonomer Coding-Agent-Harness")
    ap.add_argument("--config", default=config_mod.CONFIG_PATH)
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)

    if not os.path.exists(args.config):
        cfg = Config(args.config, data=dict(DEFAULTS))
        cfg.save()
        print(f"Neue Konfiguration angelegt: {args.config} – API-Key und Modell im UI setzen.")
    cfg = Config(args.config)
    setup_logging(cfg)
    log = logging.getLogger("harness")

    manager = Manager(cfg)
    ui = UIServer(manager, host=args.host, port=args.port)
    if not manager.sandbox_ok:
        log.warning("bash läuft NICHT abgeschottet: %s", manager.sandbox_msg)
    log.info("Web-UI: http://%s:%s/", ui.host, ui.port)
    if not manager.shell_ok:
        log.warning(manager.shell_msg)
    if os.name == "nt" and not os.environ.get("HARNESS_NO_BROWSER"):
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{ui.port}/")
        except Exception:
            pass
    ui.serve_background()
    manager.start_background()

    stop = threading.Event()

    def handle(signum, frame):
        log.info("Signal %s – fahre herunter (Agenten werden beim Neustart fortgesetzt)", signum)
        stop.set()

    signal.signal(signal.SIGINT, handle)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle)
    while not stop.is_set():
        stop.wait(1)
    manager.shutdown()
    ui.shutdown()
    log.info("Beendet.")


if __name__ == "__main__":
    main()
