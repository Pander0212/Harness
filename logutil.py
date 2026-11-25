"""Einfache Log-Rotation mit gzip für JSONL- und Textlogs."""
import gzip
import os
import shutil
import threading

_lock = threading.Lock()


def rotate_if_needed(path, max_bytes, keep=5):
    try:
        if os.path.getsize(path) < max_bytes:
            return False
    except OSError:
        return False
    with _lock:
        try:
            if os.path.getsize(path) < max_bytes:
                return False
        except OSError:
            return False
        oldest = f"{path}.{keep}.gz"
        if os.path.exists(oldest):
            os.remove(oldest)
        for i in range(keep - 1, 0, -1):
            src = f"{path}.{i}.gz"
            if os.path.exists(src):
                os.replace(src, f"{path}.{i + 1}.gz")
        with open(path, "rb") as fi, gzip.open(f"{path}.1.gz", "wb") as fo:
            shutil.copyfileobj(fi, fo)
        open(path, "w").close()
        return True


class AppendLog:
    """Thread-sicheres Anhängen an eine Datei mit Größenbegrenzung."""

    def __init__(self, path, max_bytes, keep=5):
        self.path = path
        self.max_bytes = max_bytes
        self.keep = keep
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, text):
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(text)
            rotate_if_needed(self.path, self.max_bytes, self.keep)
