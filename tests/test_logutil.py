import gzip
import os

from logutil import AppendLog


def test_rotation_with_gzip_and_limit(tmp_path):
    p = tmp_path / "conv.jsonl"
    log = AppendLog(str(p), max_bytes=1000, keep=3)
    for i in range(200):
        log.write(f'{{"i": {i}, "pad": "{"x" * 50}"}}\n')
    assert os.path.getsize(p) < 1000
    rotated = sorted(f for f in os.listdir(tmp_path) if f.endswith(".gz"))
    assert rotated == ["conv.jsonl.1.gz", "conv.jsonl.2.gz", "conv.jsonl.3.gz"]
    with gzip.open(tmp_path / "conv.jsonl.1.gz", "rt") as f:
        assert '"i":' in f.read()
