import random

import pytest

from generator import (TOPIC_KEYS, choose_topic, generate_task, is_duplicate,
                       parse_generated)

LONG = " ".join(["Wort"] * 700) + " pytest"


def test_parse():
    t, b = parse_generated("TITEL: **Raft-Konsens**\n---\n# Ziel\nText")
    assert t == "Raft-Konsens" and b.startswith("# Ziel")
    with pytest.raises(ValueError):
        parse_generated("kein titel")


def test_duplicate_detection():
    hist = ["Eigene SQL-Datenbank mit B+-Baum", "RISC-V Emulator"]
    assert is_duplicate("Eigene SQL Datenbank mit B+ Baum", hist)
    assert is_duplicate("risc-v emulator", hist)
    assert not is_duplicate("Raytracer mit BVH", hist)


def test_topic_changes_from_recent():
    rng = random.Random(1)
    hist = [{"topic": "compiler"}, {"topic": "database"}, {"topic": "network"}]
    for _ in range(200):
        assert choose_topic(hist, rng) not in ("compiler", "database", "network")


def test_weak_topics_chosen_less_often():
    rng = random.Random(2)
    hist = [{"topic": "crypto", "weak": True}, {"topic": "crypto", "weak": True}]
    hist += [{"topic": "x"}] * 3  # damit crypto nicht "zuletzt verwendet" ist
    picks = [choose_topic(hist, rng) for _ in range(3000)]
    share = picks.count("crypto") / len(picks)
    assert share < 1 / len(TOPIC_KEYS) / 3


def test_generate_task_retries_until_valid():
    calls = []
    answers = ["TITEL: Eigene SQL-Datenbank\n---\n" + LONG,     # Duplikat
               "TITEL: Neu\n---\nzu kurz",                    # zu kurz
               "TITEL: CHIP-8 Emulator mit Debugger\n---\n" + LONG]

    def caller(msgs):
        calls.append([m.copy() for m in msgs])
        return answers[len(calls) - 1]
    hist = [{"title": "Eigene SQL-Datenbank", "topic": "database"}]
    t = generate_task(caller, hist, "Beispiel", rng=random.Random(0))
    assert t["title"] == "CHIP-8 Emulator mit Debugger"
    assert t["topic"] in TOPIC_KEYS and t["topic"] != "database"
    assert "Höre erst auf" in t["prompt"]
    assert len(calls) == 3
    assert "zu ähnlich" in calls[1][-1]["content"]
    # Verlauf (bisherige Projekte) wird mitgegeben
    assert "Eigene SQL-Datenbank" in calls[0][1]["content"]


def test_generate_task_gives_up():
    with pytest.raises(ValueError):
        generate_task(lambda m: "Unsinn", [], "x", rng=random.Random(0))
