"""Auswertung der API-Anfragen: Erfolgsquote, Dauer und Verdienst je Kontextgröße.

Aufruf:  python3 analyze.py            (letzte 6 Stunden)
         python3 analyze.py 24         (letzte 24 Stunden)
"""
import collections
import glob
import json
import os
import sys
import time

from config import Config

BUCKETS = [(0, 25_000), (25_000, 50_000), (50_000, 100_000), (100_000, 150_000),
           (150_000, 10 ** 9)]


def bucket(ctx):
    for lo, hi in BUCKETS:
        if lo <= ctx < hi:
            return f"{lo // 1000:>3}k-{(str(hi // 1000) + 'k') if hi < 10 ** 9 else '':<5}"
    return "?"


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 6
    cfg = Config()
    since = time.time() - hours * 3600
    pin, pout = cfg["price_input_per_m"], cfg["price_output_per_m"]
    files = glob.glob(os.path.join(cfg.path_of("data_dir"), "**", "conversation.jsonl"),
                      recursive=True)
    req = collections.defaultdict(lambda: {"ok": 0, "fail": 0, "secs_ok": 0.0,
                                           "secs_fail": 0.0})
    kinds = collections.Counter()
    errors = collections.Counter()
    usd = 0.0
    tok_in = tok_out = n_usage = 0
    ratios = []
    for fn in files:
        try:
            f = open(fn, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("ts", 0) < since:
                    continue
                t = r.get("type")
                if t == "request":
                    b = req[bucket(int(r.get("ctx") or 0))]
                    if r.get("ok"):
                        b["ok"] += 1
                        b["secs_ok"] += r.get("secs", 0)
                    else:
                        b["fail"] += 1
                        b["secs_fail"] += r.get("secs", 0)
                        kinds[r.get("kind", "?")] += 1
                        errors[(r.get("error") or "")[:90]] += 1
                elif t == "usage":
                    n_usage += 1
                    tok_in += r.get("prompt_tokens", 0)
                    tok_out += r.get("completion_tokens", 0)
                    if r.get("est"):
                        ratios.append(r.get("prompt_tokens", 0) / max(1, r["est"]))
                    usd += (r.get("prompt_tokens", 0) * pin +
                            r.get("completion_tokens", 0) * pout) / 1e6
    print(f"Zeitraum: letzte {hours:g} h  |  Protokolle: {len(files)}")
    print(f"Erfolgreiche Aufrufe: {n_usage}  |  Input {tok_in / 1e6:.2f} M  |  "
          f"Output {tok_out / 1e6:.3f} M  |  Verdienst {usd:.2f} USD "
          f"({usd / hours:.2f} USD/h)")
    if ratios:
        ratios.sort()
        med = ratios[len(ratios) // 2]
        print(f"Gemeldete Input-Tokens / eigene Schätzung (Median): {med:.2f}"
              + ("  -> Anbieter meldet deutlich weniger als geschickt (evtl. ohne Cache)!"
                 if med < 0.6 else ""))
    if not req:
        print("\nNoch keine Anfrage-Messungen (erst ab dieser Version vorhanden).")
        return
    print("\nKontext     ok   fehl  Erfolg  Ø s (ok)  Ø s (fehl)  Wartezeit fehl (min)")
    for lo, hi in BUCKETS:
        k = bucket(lo)
        if k not in req:
            continue
        b = req[k]
        n = b["ok"] + b["fail"]
        print(f"{k}  {b['ok']:>5}  {b['fail']:>5}  {100 * b['ok'] / n:5.1f}%  "
              f"{b['secs_ok'] / max(1, b['ok']):8.1f}  {b['secs_fail'] / max(1, b['fail']):10.1f}"
              f"  {b['secs_fail'] / 60:12.1f}")
    print("\nFehlerarten:", ", ".join(f"{k}: {v}" for k, v in kinds.most_common()))
    print("Häufigste Fehlermeldungen:")
    for msg, n in errors.most_common(5):
        print(f"  {n:>5} × {msg}")


if __name__ == "__main__":
    main()
